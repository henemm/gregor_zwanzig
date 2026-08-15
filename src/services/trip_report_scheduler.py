"""
Trip report scheduler service.

Feature 3.3: Scheduled trip weather reports (Morning 07:00, Evening 18:00).
Generates and sends HTML email reports for active trips.

SPEC: docs/specs/modules/trip_report_scheduler.md v1.0
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import threading
import time as time_module
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, NamedTuple, Optional, Tuple
from zoneinfo import ZoneInfo

import httpx

from app.config import Settings
from app.loader import get_data_dir, load_all_trips, save_trip
from app.models import (
    NormalizedTimeseries,
    SegmentWeatherData,
    SegmentWeatherSummary,
    StabilityResult,
    TripSegment,
)
from services import alert_daily_limit
from services.alert_briefing_anchor import (
    briefing_target_day_is_current,
    record_briefing_dispatch_failure,
    reset_alert_memory,
    write_anchor_and_reset_memory,
)
from services.briefing_slots import BriefingSlotStore
from services.day_comparison import DayComparison
from services.notification_service import NotificationService, TripReportRequest
from services.user_tier import premium_sms_allowed, sms_allowed
from utils.geo import haversine_km
from utils.timezone import local_dt, tz_for_coords

if TYPE_CHECKING:
    from app.trip import Stage, Trip
    from services.report_config_resolver import ReportRenderOptions

# Issue #766: Inter-Mail-Delay beim Sammelversand, um Rate-Limits (452) zu
# vermeiden. Hinweis: `time` ist hier die datetime.time-Klasse — der echte
# Zeit-Modul wird als `time_module` importiert.
INTER_MAIL_DELAY_SECONDS = 2


class OnDemandErgebnis(NamedTuple):
    """Fix #1795 AC-7: Rückgabetyp von ``send_on_demand_report`` — ein bloßer
    Outcome-String (die frühere ``-> bool``-Annotation war seit #1007 ohnehin
    falsch) reicht dem Aufrufer nicht, WELCHER Ortstag tatsächlich benutzt
    wurde (``_send_trip_report_outcome`` löst ihn intern über
    ``datetime.now(timezone.utc)`` zum Ausführungs-, nicht Empfangszeitpunkt
    auf). Ein NamedTuple ist nicht ``True`` und fällt in einem Normalisierer,
    der noch mit dem alten bool/str rechnet, laut in den else-Zweig — eine
    vergessene Migrationsstelle wird sichtbar rot, nicht still falsch.
    """
    outcome: str
    zieltag: date

# Issue #1113: >75 % fehlende Segmente -> Guard wie Totalausfall (#1012);
# Retry-Budget pro Segment bei transienten Fetch-Fehlern (1s/2s Backoff).
OUTAGE_WITHHOLD_RATIO = 0.75
FETCH_RETRY_ATTEMPTS = 2
FETCH_RETRY_BACKOFF_SECONDS = 1

# Adversary Finding F002: nur HTTP 5xx/Timeout/Overloaded gelten als
# transient und rechtfertigen einen Retry — alles andere (z. B. ungültige
# Koordinaten) wird sofort als has_error markiert, kein Sleep.
# Adversary Finding F005: Text-Marker "timeout" matcht nicht den echten
# httpx-Fehlertext ("timed out") — daher zuerst über den Exception-TYP
# pruefen (deckt auch die vom Provider gewrappte Fehlerkette via __cause__
# ab), Text-Marker nur als Fallback fuer nicht-httpx-Fehlerquellen.
_TRANSIENT_FETCH_ERROR_MARKERS = (
    "502", "503", "504", "timeout", "timed out", "overloaded",
)

# Issue #1725: Ausgaenge, die den Slot fuer diesen Ortstag abschliessen.
# `channels_unreachable` fehlt bewusst -- dort hat per Definition
# (`sent = bool(sent_channels)`) niemand etwas bekommen, das ist der einzige
# beabsichtigte Nachholfall. `no_weather` steht dagegen drin: ohne Vermerk
# gaebe es eine stuendliche "keine Daten"-Mail plus stuendlichen vollen
# Wetterabruf gegen das Kontingent (#1329), waehrend der #1012-Pending-Marker
# die Nachlieferung bereits abdeckt.
VERMERK_AUSGAENGE = frozenset({"sent", "no_stage", "no_weather", "no_channels"})

# Issue #1725: Breite des Faelligkeitsfensters in Ortsstunden.
# `konfigurierte_stunde <= ortsstunde < konfigurierte_stunde + 3`. Drei
# Stunden decken den an Umstellungstagen ausfallenden Cron-Tick (1 Stunde,
# `robfig/cron/v3`) mit Reserve fuer einen gescheiterten, nicht wiederholten
# HTTP-Post (`scheduler.triggerEndpointForUser`). Eine Deckelung am Tagesende ist nicht
# noetig: fuer Slot 22 sind es die Ortsstunden 22 und 23, ab Ortsmitternacht
# wechselt der Ortstag und `0 >= 22` ist falsch. Die Alternative „bis
# Tagesende" wurde verworfen, weil sie neu angelegte oder aus `paused_until`
# zurueckkehrende Trips RUECKWIRKEND feuern liesse (AC-10) --
# `_get_active_trips` prueft nur die Etappe, nicht das Anlagedatum.
NACHHOL_FENSTER_STUNDEN = 3


def _is_transient_fetch_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        return status_code in (502, 503, 504)
    if isinstance(exc, httpx.TimeoutException) or isinstance(
        getattr(exc, "__cause__", None), httpx.TimeoutException
    ):
        return True
    message = str(exc).lower()
    return any(marker in message for marker in _TRANSIENT_FETCH_ERROR_MARKERS)

logger = logging.getLogger("trip_report_scheduler")


def _slot_stunde(trip: "Trip", report_type: str) -> int:
    """Konfigurierte Ortsstunde eines Slots — EINE Fassung fuer den Sammellauf
    und fuer das Faelligkeits-Praedikat (#1594)."""
    rc = trip.report_config
    zeit = None
    if rc is not None:
        zeit = rc.morning_time if report_type == "morning" else rc.evening_time
    if zeit is not None:
        return zeit.hour
    return 7 if report_type == "morning" else 18


def trip_briefing_due_at(
    trip: "Trip", moment: datetime, *, user_id: str,
) -> bool:
    """Ist fuer diesen Trip zum Zeitpunkt ``moment`` ein geplantes Briefing
    faellig? — das REINE Faelligkeits-Praedikat (Issue #1594).

    Beantwortet dieselbe Frage wie :meth:`TripReportSchedulerService._collect_due_trips`
    (Aktiv-Filter + Faelligkeits-Fenster + Vermerk), aber SEITENEFFEKTFREI und
    fuer EINEN Trip: kein `save_trip()`, kein Versand, keine Reservierung.

    🔴 Ohne den ``skip_next``-Zweig aus ``_get_active_trips()``: der konsumiert
    das Nutzer-Kennzeichen „naechstes Briefing ueberspringen" per
    Read-Modify-Write MIT ``save_trip()`` bei JEDEM Aufruf. Wuerde die
    Vorlauf-Sperre jene Methode mitbenutzen, verbrauchte sie den Wunsch im
    15-Minuten-Alarmtakt, bevor der Briefing-Scheduler ihn je saehe — das
    Briefing kaeme trotzdem. Fuer die Faelligkeit ist der Unterschied
    folgenlos: ein uebersprungenes Briefing bleibt ein geplantes Briefing.

    Alle uebrigen Aktiv-Filter sind zwingend enthalten (AC-8): Etappe am
    Zieltag, ``paused_at``, ``report_config.enabled``, ``paused_until``. Fehlt
    einer, schwiege der Alarm fuer einen Trip OHNE geplantes Briefing — ohne
    Ersatz, also verschluckt statt ersetzt (Fehlerklasse #1555/#1584).

    Args:
        trip: der Trip.
        moment: Zeitpunkt (UTC), gegen den geprueft wird — die Vorlauf-Sperre
            wertet dasselbe Praedikat auch gegen spaetere Zeitpunkte aus.
        user_id: echte Nutzer-Kennung (Mandantentrennung, nie ``"default"``) —
            traegt den Vermerk-Speicher.
    """
    from services.trip_day import trip_local_now

    if trip.paused_at is not None:
        return False
    rc = trip.report_config
    if rc is not None:
        if rc.enabled is False:
            return False
        if rc.paused_until is not None:
            pu = rc.paused_until
            if pu.tzinfo is None:
                pu = pu.replace(tzinfo=timezone.utc)
            if moment < pu:
                return False

    vor_ort = trip_local_now(trip, moment)
    store = BriefingSlotStore(user_id)
    for report_type, zieltag in (
        ("morning", vor_ort.date()),
        ("evening", vor_ort.date() + timedelta(days=1)),
    ):
        if trip.get_stage_for_date(zieltag) is None:
            continue
        stunde = _slot_stunde(trip, report_type)
        if not stunde <= vor_ort.hour < stunde + NACHHOL_FENSTER_STUNDEN:
            continue
        # Der Vermerk beendet das Nachhol-Fenster, sobald das Briefing raus
        # ist — sonst schwiege der Alarm bis zu drei Stunden nach einem
        # bereits zugestellten Briefing. Nach einem GESCHEITERTEN Versand
        # traegt er nicht (reserve-then-release, `:565-571`); dort endet die
        # Sperre ueber den Briefing-Anker (`check_briefing_imminent`, R6).
        if store.is_recorded(
            trip.id, report_type, vor_ort.date(), zone=vor_ort.tzinfo,
        ):
            continue
        return True
    return False


def _trend_note(thunder: str, precip_mm: float, wind_kmh: int) -> str | None:
    """Returns a hint text when conditions are notable, else None."""
    notes = []
    if thunder != "NONE":
        notes.append("Gewitter möglich")
    if precip_mm > 5:
        notes.append(f"Regen {precip_mm:.0f} mm")
    if wind_kmh > 40:
        notes.append(f"Böen bis {wind_kmh} km/h")
    return " · ".join(notes) if notes else None


def _night_thunder_hours(night_weather, fc_date: date, to_local):
    """``night_weather`` -> ``(Ortszeit-Stunde, ThunderLevel)`` fuer EINEN Tag.

    Issue #1651: die Nacht-Zeitreihe (Ankunft heute -> 06:00 morgen) ist fuer
    die Stunden, die sie abdeckt, die massgebliche Quelle des Nacht-Zusatzes
    -- dieselbe, aus der auch die „Nacht am Ziel"-Tabelle derselben Mail
    entsteht. ``None`` (keine Reihe, keine Punkte am Zieltag) heisst: keine
    Gegenquelle, es gilt allein die eigene Etappen-Reihe.
    """
    data = getattr(night_weather, "data", None)
    if not data:
        return None
    hours = [
        (to_local(dp.ts).hour, dp.thunder_level)
        for dp in data
        if dp.thunder_level is not None and to_local(dp.ts).date() == fc_date
    ]
    return hours or None


def _parse_hhmm(value: str) -> Optional[time]:
    """Parse 'HH:MM' to a time; returns None on malformed input.

    Issue #296 — used to consume persisted Naismith arrival_calculated values.
    """
    try:
        return time.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _load_pending_entries(path: Path) -> dict:
    """Issue #1012 Adversary-Fix F001: liest pending_briefings.json robust.

    Fehlende oder kaputte Datei (z.B. abgebrochener Schreibvorgang) liefert ein
    leeres Schema statt eine ungefangene JSONDecodeError zu werfen, die sonst
    den kompletten stündlichen Versandlauf VOR dem regulären Versand crasht
    (HTTP 500, kein Trip bekommt sein Briefing).
    """
    if not path.exists():
        return {"entries": []}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Corrupt pending_briefings.json at {path}, ignoring: {e}")
        return {"entries": []}


def _write_pending_data(path: Path, data: dict) -> None:
    """Atomarer Schreibvorgang (tmp + os.replace) — verhindert eine halb
    geschriebene Datei bei einem Absturz mitten im Schreibvorgang."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2))
    os.replace(tmp_path, path)


@dataclasses.dataclass
class CorruptTripObservability:
    """Ergebnis eines Beobachtbarkeits-Laufs (Issue #1262 AC-4)."""

    skipped_count: int
    corrupt_files: List[str]
    newly_notified: List[str]


def _mq_notify_infra(filename: str, detail: str) -> None:
    """Produktions-``notify``: sendet genau EINE MQ-Meldung (Prioritaet
    ``high``) an Instanz ``infra`` ueber den etablierten claude-mq-Helper
    (``src.lib.mq_notify.send_mq``, gleiches Ziel wie
    ``/home/hem/claude-mq/send.sh``, aber ohne Subprozess-Aufruf).

    Ist im AC-4-Test durch einen aufrufsprotokollierenden Spy ersetzt (Seam)
    — hier keine Geschaeftslogik-Mocks. Fail-soft bereits in ``send_mq``
    eingebaut: ohne ``CLAUDE_MQ_SECRET`` (z.B. lokale Testlaeufe) wird
    still uebersprungen, ein Versandfehler wird nur geloggt — der Zaehler
    bleibt in jedem Fall sichtbar (kein Crash des Scheduler-Laufs)."""
    from lib.mq_notify import send_mq

    subject = f"Kaputter Trip beim Laden uebersprungen: {filename}"
    send_mq("gregor", "infra", "high", subject, detail)


def record_corrupt_trip_observability(
    user_id: str,
    notify: Optional[callable] = None,
) -> CorruptTripObservability:
    """Issue #1262 AC-4: macht beim Laden uebersprungene/kaputte Trips sichtbar.

    Scannt ``get_briefings_dir(user_id)``, versucht jede Datei ueber den echten
    Loader-Pfad (``load_trip``) zu laden und zaehlt die nicht ladbaren. Fuer
    jede NEU entdeckte kaputte Datei wird ``notify(filename, detail)`` genau
    EINMAL aufgerufen (Dedup-Schluessel = Dateiname, persistent ueber Laeufe).
    Der Dedup-Zustand und der letzte Zaehler landen als Diagnostics-Datei unter
    ``get_data_dir(user_id)/diagnostics`` (Status-Sichtbarkeit).
    """
    from app.loader import get_briefings_dir, get_data_dir, load_trip

    briefings_dir = get_briefings_dir(user_id)
    corrupt: List[Tuple[str, str]] = []
    if briefings_dir.exists():
        for path in sorted(briefings_dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and raw.get("kind") == "vergleich":
                    continue
                load_trip(raw)
            except Exception as exc:  # noqa: BLE001 — jede Ladefehlerursache zaehlt
                corrupt.append((path.name, str(exc)))

    diag_dir = get_data_dir(user_id) / "diagnostics"
    state_path = diag_dir / "corrupt_trips.json"
    already: set[str] = set()
    if state_path.exists():
        try:
            already = set(json.loads(state_path.read_text(encoding="utf-8")).get("notified", []))
        except (json.JSONDecodeError, OSError):
            already = set()

    newly: List[str] = []
    for filename, detail in corrupt:
        if filename in already:
            continue
        already.add(filename)
        newly.append(filename)
        if notify is not None:
            notify(filename, detail)

    diag_dir.mkdir(parents=True, exist_ok=True)
    # Adversary F001: atomarer Schreib (tmp + os.replace) statt write_text —
    # ein Absturz mitten im Schreiben (Restart/Deploy/OOM) darf das
    # Dedup-Gedaechtnis nicht zerstoeren, sonst meldet der naechste Tick ALLE
    # zuvor gemeldeten kaputten Trips erneut per MQ.
    _write_pending_data(state_path, {
        "notified": sorted(already),
        "last_skipped_count": len(corrupt),
        "last_run": datetime.now(timezone.utc).isoformat(),
    })

    return CorruptTripObservability(
        skipped_count=len(corrupt),
        corrupt_files=[name for name, _ in corrupt],
        newly_notified=newly,
    )


# Issue #1756: In-Process-Lock gegen doppelten manuellen Trip-Versand.
# Modul-Ebene (nicht instanz-gebunden): pro Request entsteht eine neue
# TripReportSchedulerService-Instanz (api/routers/scheduler.py), ein
# Instanzattribut würde daher nie mit sich selbst kollidieren. Wirkt nur
# innerhalb eines Systemd-Prozesses (siehe Spec „Known Limitations").
_send_locks: Dict[Tuple[str, str, str], bool] = {}
_send_locks_guard = threading.Lock()


def _try_acquire_send_lock(user_id: str, trip_id: str, report_type: str) -> bool:
    key = (user_id, trip_id, report_type)
    with _send_locks_guard:
        if _send_locks.get(key):
            return False
        _send_locks[key] = True
        return True


def _release_send_lock(user_id: str, trip_id: str, report_type: str) -> None:
    key = (user_id, trip_id, report_type)
    with _send_locks_guard:
        _send_locks.pop(key, None)


class TripReportSchedulerService:
    """
    Service for scheduled trip weather reports.

    Generates and sends trip weather reports (HTML email)
    for all active trips at scheduled times.

    Example:
        >>> service = TripReportSchedulerService()
        >>> service.send_reports("morning")  # Send reports for today's trips
    """

    def __init__(self, settings: Optional[Settings] = None, user_id: str = "default") -> None:
        """
        Initialize the service.

        Args:
            settings: App settings (default: load from config)
            user_id: User identifier for data scoping
        """
        self._settings = settings if settings else Settings().with_user_profile(user_id)
        self._notification_service = NotificationService(self._settings, user_id)
        self._user_id = user_id

    def send_reports(self, report_type: str) -> int:
        """
        Send reports for all active trips.

        Args:
            report_type: "morning" or "evening"

        Returns:
            Number of reports successfully sent
        """
        if not self._settings.can_send_email():
            logger.error("SMTP not configured, cannot send trip reports")
            return 0

        # Issue #1724 AC-9: EIN "Jetzt" fuer den ganzen Lauf -- kein Trip
        # darf eine andere Sekunde sehen als der naechste.
        now_utc = datetime.now(timezone.utc)
        active_trips = self._get_active_trips(report_type, now_utc)
        logger.info(f"Found {len(active_trips)} active trips for {report_type} reports")

        sent_count = 0
        for i, trip in enumerate(active_trips):
            try:
                self._send_trip_report(trip, report_type)
                sent_count += 1
                # Issue #766: 2s Pause zwischen aufeinanderfolgenden Mails
                # (nicht nach der letzten), um SMTP-Rate-Limits zu vermeiden.
                if i < len(active_trips) - 1:
                    time_module.sleep(INTER_MAIL_DELAY_SECONDS)
            except Exception as e:
                logger.error(f"Failed to send report for trip {trip.id}: {e}")

        logger.info(f"Sent {sent_count}/{len(active_trips)} {report_type} reports")
        return sent_count

    def send_due_reports(self, now_utc: datetime) -> Tuple[int, int]:
        """
        Send reports for trips whose configured time matches their LOCAL hour.

        Called hourly by the scheduler. Checks both morning and evening
        times per trip against the hour in that trip's own timezone.

        Issue #1724: hiess bis dahin `send_reports_for_hour(current_hour)` und
        bekam eine in `Europe/Vienna` vorberechnete Stunde. Der Name war Teil
        des Fehlers -- "die Stunde" gibt es nicht, es gibt nur die Stunde
        EINER Zone. Uebergeben wird jetzt der Zeitpunkt; die Stunde entsteht je
        Trip (ADR-0051 Regel 2).

        Issue #766: Sammelt alle fälligen Mails, sendet sie mit 2s Pause
        zwischen aufeinanderfolgenden Versendungen (Rate-Limit-Schutz) und
        liefert ein (sent, failed)-Tuple zurück, damit der Status-Endpoint
        Teilfehler sichtbar machen kann.

        Issue #1207: Thin-Wrapper -- delegiert an den geteilten
        Versand-Orchestrator (`run_briefing_dispatch`), der das Skelett
        (Settings, Fälligkeits-/Delay-/Tally-Schleife) mit dem
        Compare-Versandweg teilt. Verhalten unverändert (AC-3).

        Adversary Fix-Loop F002: reicht das bereits von dieser Instanz
        gehaltene `self._settings` durch (statt es im Orchestrator neu laden
        zu lassen) -- ein per Konstruktor injiziertes Settings-Objekt wird
        so nicht mehr stillschweigend verworfen.

        Args:
            now_utc: Zeitpunkt des Laufs (zeitzonenbehaftet, UTC).

        Returns:
            Tuple (sent, failed): Anzahl erfolgreich versendeter und
            fehlgeschlagener Reports.
        """
        # Issue #1262 AC-4: Beobachtbarkeit uebersprungener/kaputter Trips —
        # einmal pro Scheduler-Lauf, fail-soft (darf den Sendelauf nie
        # crashen, auch wenn SMTP nicht konfiguriert ist). Trip-spezifisch
        # (basiert auf load_all_trips/briefings) -- bewusst NICHT im
        # geteilten run_briefing_dispatch, der auch den Compare-Versandweg
        # bedient.
        try:
            record_corrupt_trip_observability(self._user_id, notify=_mq_notify_infra)
        except Exception as e:
            logger.warning("record_corrupt_trip_observability fehlgeschlagen: %s", e)

        from services.dispatch_orchestrator import run_briefing_dispatch

        return run_briefing_dispatch(
            "route", self._user_id, now_utc, settings=self._settings,
        )

    def _collect_due_trips(self, now_utc: datetime) -> List[Tuple["Trip", str, date]]:
        """Sammelt alle (trip, report_type, ortstag)-Tripel, die JETZT fällig sind.

        Issue #1207: Extrahiert aus dem Sendelauf fuer Delegation durch
        `TripDispatchStrategy.collect_due()` -- Morgen- UND Abend-Fälligkeit
        werden VOR dem Versand gesammelt, damit das Inter-Mail-Delay über
        beide Slots hinweg greift.

        Issue #1724 (ADR-0051 Regel 2): der Parameter ist ein ZEITPUNKT, keine
        vorberechnete Stunde. Eine Stunde traegt immer die Zone dessen, der sie
        ausgerechnet hat -- frueher `Europe/Vienna`, eine Konstante ohne
        fachliche Herleitung. Die Stunde entsteht jetzt je Trip aus DESSEN
        Ortszeit, damit ein auf 07:00 gestelltes Briefing ueberall um 07:00
        Ortszeit ankommt statt um 17:00 (Auckland) oder 22:00 des Vortages
        (PCT).

        Issue #1725: Faelligkeit ist ein FENSTER, keine Stundengleichheit --
        `konfigurierte_stunde <= ortsstunde < konfigurierte_stunde +
        NACHHOL_FENSTER_STUNDEN`, kombiniert mit dem Vermerk-Filter unten.
        Ein Ortstag hat nicht immer 24 Stunden: am Fruehjahrs-Umstellungstag
        fehlt eine Ortsstunde ersatzlos (ein auf 02:00 gestelltes Briefing
        entfiel), am Herbsttag existiert sie zweimal (es ging zweimal raus).
        Das Fenster faengt zusaetzlich den Cron-Tick auf, der an genau diesen
        Tagen weltweit fuer ALLE Nutzer ausfaellt (`cron.New(cron.WithLocation)`
        in `internal/scheduler/scheduler.go`, Verhalten von `robfig/cron/v3`).
        Erst der Vermerk macht das Fenster gefahrlos -- ohne ihn waere `>=`
        stuendlicher Serienversand.

        Drittes Element ist der ORTSTAG DES LAUFS -- zusammen mit
        Trip-Kennung und Slot der Idempotenz-Schluessel. Ausdruecklich NICHT
        `target_date`: das Abend-Briefing berichtet ueber morgen, gehoert aber
        zum heutigen Slot. Ortstag und Ortsstunde entstehen aus EINER
        Zonen-Aufloesung (`trip_local_now`) -- zwei koennen an der Tagesgrenze
        auseinanderfallen (#1697).

        Der Vermerk-Filter sitzt HIER und nicht erst im Versand (Pruefort =
        Wirkort): `_process_pending_markers` raeumt den #1012-Nachliefer-Marker
        weg, sobald der Trip in `due_trip_ids_now` steht -- eine unehrlich
        lange Liste legte den Nachliefermechanismus lautlos still. Und er sitzt
        NACH `_get_active_trips`, weil dort `skip_next` bei jedem Sammellauf
        konsumiert wird (RMW auf `report_config`), unabhaengig von der
        Faelligkeit.
        """
        from services.trip_day import trip_local_now

        store = BriefingSlotStore(self._user_id)
        due: List[Tuple["Trip", str, date]] = []
        for report_type, slot_stunde in (
            ("morning", self._get_morning_hour),
            ("evening", self._get_evening_hour),
        ):
            for trip in self._get_active_trips(report_type, now_utc):
                vor_ort = trip_local_now(trip, now_utc)
                stunde = slot_stunde(trip)
                if not stunde <= vor_ort.hour < stunde + NACHHOL_FENSTER_STUNDEN:
                    continue
                ortstag = vor_ort.date()
                if store.is_recorded(
                    trip.id, report_type, ortstag, zone=vor_ort.tzinfo,
                ):
                    continue
                due.append((trip, report_type, ortstag))
        return due

    def _dispatch_due_item(
        self, trip: "Trip", report_type: str, local_day: date,
    ) -> Optional[str]:
        """Versand EINES faelligen Slots, abgesichert durch den Vermerk (#1725).

        Reserve-then-release: der Vermerk entsteht VOR dem Versandversuch und
        wird nur bei `channels_unreachable` oder einer Ausnahme wieder
        zurueckgenommen. Stirbt der Prozess mitten im Versand, bleibt er
        stehen -- nie doppelt, im schlimmsten Fall ein ausgelassener Slot.

        Ausschliesslich `TripDispatchStrategy.dispatch_one` ruft diese Methode.
        Dadurch bleiben die On-Demand-Pfade (Test-Knopf, Inbound-Kommandos,
        Legacy-CLI) vom Vermerk unberuehrt, ohne dass ein zusaetzliches Flag
        noetig waere (AC-12) -- sie rufen `_send_trip_report_outcome` direkt.

        Returns:
            Den Ausgang des Versandversuchs -- oder `None`, wenn gar keiner
            stattfand (Slot bereits vermerkt oder Sperre nicht zu bekommen,
            fail-closed, AC-13). Eine Ausnahme aus dem Versand wird nach dem
            `release` WEITERGEREICHT, nicht geschluckt.
        """
        from services.trip_day import trip_tz

        store = BriefingSlotStore(self._user_id)
        if not store.reserve(trip.id, report_type, local_day, zone=trip_tz(trip)):
            logger.warning(
                "Slot %s/%s am %s nicht reservierbar -- kein Versandversuch",
                trip.id, report_type, local_day,
            )
            return None
        try:
            outcome = self._send_trip_report_outcome(trip, report_type)
        except Exception:
            store.release(trip.id, report_type, local_day)
            raise
        if outcome in VERMERK_AUSGAENGE:
            store.record_outcome(trip.id, report_type, local_day, outcome)
        else:
            store.release(trip.id, report_type, local_day)
        return outcome

    def _process_pending_markers(self, now_utc: datetime, due_trip_ids_now: set) -> int:
        """Issue #1012 (b2): Verarbeitet offene Nachliefer-Marker VOR den
        regulären Slots. Für jeden Marker:
        - Trip regulär JETZT fällig (beliebiger report_type) -> Marker
          verfällt ersatzlos (AC-7), kein Re-Send hier (der reguläre Slot
          übernimmt).
        - Zuvor fehlende Segmente liefern jetzt Daten -> vollständiges
          Briefing mit Hinweis-Präfix nachliefern, Marker entfernen (AC-6).
        - Weiterhin fehlende Daten -> kein Re-Send, attempts += 1 (Lärmschutz).

        Issue #1662: Ein Versandfehler-Marker (`reason == "dispatch_error"`)
        weicht an zwei Stellen ab — er verfällt, sobald sein Zieltag vorbei
        ist, und er überlebt die reguläre Fälligkeit, bis der reguläre Versand
        dieser Stunde tatsächlich gelungen ist. Die Segment-Schnittmenge wird
        für ihn übersprungen (`failed_segment_ids` ist per Definition leer).

        Returns:
            Anzahl erfolgreich nachgelieferter Briefings (zählt als 'sent').
        """
        path = get_data_dir(self._user_id) / "pending_briefings.json"
        entries = _load_pending_entries(path).get("entries", [])
        if not entries:
            return 0

        all_trips = {t.id: t for t in load_all_trips(user_id=self._user_id)}
        delivered = 0

        for entry in entries:
            trip_id = entry.get("trip_id")
            trip = all_trips.get(trip_id)
            # Issue #1662: Versandfehler-Vermerke gehen einen eigenen Weg —
            # `failed_segment_ids` ist bei ihnen per Definition leer, die
            # Segment-Schnittmenge unten waere also immer leer und zoege den
            # sachlich falschen Schluss "jetzt liegen vollstaendige Daten vor".
            is_dispatch_error = entry.get("reason") == "dispatch_error"

            if trip is None:
                self._remove_pending_marker(trip_id)
                continue

            # Issue #1662 AC-4: Verfall ueber den Zieltag (geteilte, reine
            # Entscheidungsfunktion) — ein Morgen-Briefing von gestern ist
            # heute wertlos und wird nicht mehr zugestellt.
            # Issue #1727 S5b (ADR-0044): der Vergleichstag ist der ORTSTAG
            # DIESER Tour und kommt von hier — `now_utc` liegt als Parameter
            # vor, `trip` steht im Zugriff. Vorher loeste die Funktion still
            # `date.today()` auf: im Mismatch-Fenster verfiel der Vermerk einen
            # Tag zu frueh (Briefing nie nachgeliefert) oder wurde einen Tag zu
            # lange weitergeschleppt.
            from services.trip_day import trip_local_today

            if is_dispatch_error and not briefing_target_day_is_current(
                entry.get("date"), today=trip_local_today(trip, now_utc),
            ):
                self._remove_pending_marker(trip_id)
                continue

            if trip_id in due_trip_ids_now:
                # Issue #1662 AC-5/AC-6 (Punkt 6): Ein Versandfehler-Vermerk
                # verfaellt hier NICHT mehr blind. Der regulaere Versand dieser
                # Stunde ist der "letzte Versuch" — gelingt er, raeumt
                # `_send_trip_report_outcome` den Vermerk weg; scheitert er
                # erneut, schreibt derselbe Fehlerpfad einen frischen. Ein
                # zusaetzlicher Catch-up-Versand hier erzeugte dagegen eine
                # zweite, fast inhaltsgleiche Nachricht wenige Minuten vor dem
                # regulaeren Briefing.
                if not is_dispatch_error:
                    self._remove_pending_marker(trip_id)
                continue

            target_date = date.fromisoformat(entry["date"])
            report_type = entry["report_type"]
            segments = self._convert_trip_to_segments(trip, target_date)
            if not segments:
                self._remove_pending_marker(trip_id)
                continue

            if is_dispatch_error:
                # Issue #1662 AC-3: eigener Text — bei einem Versandfehler
                # waren die Daten nie das Problem, und der Nutzer hat kein
                # "Vorher", das aktualisiert wuerde. Kein Technikjargon.
                prefix = (
                    f"Nachgeliefert — die Zustellung um "
                    f"{entry.get('slot_hour')}:00 ist fehlgeschlagen"
                )
                self._remove_pending_marker(trip_id)
                outcome = self._send_trip_report_outcome(
                    trip, report_type, catchup_prefix=prefix,
                )
                if outcome == "sent":
                    delivered += 1
                continue

            segment_weather = self._fetch_weather(segments)
            failed_ids_now = {
                str(s.segment.segment_id) for s in segment_weather if s.has_error
            }
            previously_failed = set(entry.get("failed_segment_ids") or [])
            if previously_failed & failed_ids_now:
                # Mindestens ein zuvor fehlendes Segment liefert weiterhin
                # keine Daten -> kein Re-Send, nie zwei identische Briefings.
                self._bump_pending_marker_attempts(trip_id)
                continue

            was_complete_failure = len(previously_failed) >= len(segments)
            if was_complete_failure:
                prefix = (
                    f"Nachgeliefert — der Wetterdienst war um "
                    f"{entry.get('slot_hour')}:00 nicht erreichbar"
                )
            elif failed_ids_now:
                # Adversary Finding F003: ein (neues) Segment schlägt beim
                # Nachliefer-Versuch fehl, obwohl kein zuvor bekanntes
                # Segment mehr betroffen ist — "vollständig" wäre hier
                # widersprüchlich zum gleichzeitig gesetzten
                # partial_outage_hint (siehe _send_trip_report_outcome).
                prefix = "Aktualisiert — weiterhin unvollständig, Details im Hinweis"
            else:
                prefix = "Aktualisiert — jetzt mit vollständigen Daten"
            # Marker zuerst entfernen (RMW) — schlägt die Nachlieferung
            # erneut (teilweise) fehl, schreibt der reguläre Sendepfad
            # selbst einen frischen Marker (siehe _send_trip_report_outcome).
            self._remove_pending_marker(trip_id)
            outcome = self._send_trip_report_outcome(
                trip, report_type, catchup_prefix=prefix,
            )
            if outcome == "sent":
                delivered += 1

        return delivered

    def _write_pending_marker(
        self,
        trip: "Trip",
        report_type: str,
        target_date: date,
        failed_segment_ids: List[str],
        reason: Optional[str] = None,
    ) -> None:
        """Issue #1012 (b2): Schreibt/ersetzt den Nachliefer-Marker eines Trips.

        Read-Modify-Write auf data/users/<uid>/pending_briefings.json —
        ersetzt einen ggf. bestehenden Marker desselben Trips (keine Duplikate).

        `reason` (Issue #1662): `"dispatch_error"` kennzeichnet einen
        Versandfehler-Vermerk (leere `failed_segment_ids`). Ohne Angabe bleibt
        das Feld weg — Bestandsmarker (Wetterfehler) sind unveraendert, es ist
        keine Migration noetig (Go ignoriert unbekannte Felder).
        """
        path = get_data_dir(self._user_id) / "pending_briefings.json"
        data = _load_pending_entries(path)
        entries = [e for e in data.get("entries", []) if e.get("trip_id") != trip.id]
        slot_hour = (
            self._get_morning_hour(trip) if report_type == "morning"
            else self._get_evening_hour(trip)
        )
        marker = {
            "trip_id": trip.id,
            "report_type": report_type,
            "date": target_date.isoformat(),
            "slot_hour": slot_hour,
            "failed_segment_ids": failed_segment_ids,
            "attempts": 0,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        if reason is not None:
            marker["reason"] = reason
        entries.append(marker)
        data["entries"] = entries
        _write_pending_data(path, data)

    def _mark_briefing_undelivered(
        self, trip: "Trip", report_type: str, target_date: date, *, on_demand: bool,
    ) -> None:
        """Issue #1662 AC-1: Vermerkt ein Briefing, das NIEMAND bekommen hat.

        EINE Stelle fuer beide Ausgaenge eines vollstaendig gescheiterten
        Versands, damit sie nicht auseinanderlaufen (dieselbe Erwaegung, aus der
        #1629 den Anker in `_anchor_and_reset` gebuendelt hat): der Versand
        wirft (E-Mail-Pfad) ODER er wirft nicht, aber die Zustellbilanz ist leer
        (SMS-/Telegram-Fehler sind fail-soft). Haenge der Vermerk nur am ersten
        Fall, waere ein Briefing genau dann still verloren, wenn E-Mail gar
        nicht konfiguriert ist (Adversary-Befund F001 — betrifft den geplanten
        Premium-SMS-Weg auf ein Garmin inReach).

        Kein betroffener Wetterabschnitt: bei einem Versandfehler waren die
        Daten nie das Problem. Ad-hoc-Abruf bleibt gegenueber gespeichertem
        Zustand wirkungslos (#1007, AC-7).
        """
        if on_demand:
            return
        self._write_pending_marker(
            trip, report_type, target_date,
            failed_segment_ids=[], reason="dispatch_error",
        )

    def _clear_dispatch_error_marker(self, trip_id: str) -> None:
        """Issue #1662 AC-5: Ein gelungener Versand macht den
        Versandfehler-Vermerk dieses Trips gegenstandslos.

        Entfernt ausschliesslich Versandfehler-Vermerke (RMW) —
        Wetterfehler-Vermerke (#1012) bleiben unberuehrt, sie haengen an einer
        anderen Bedingung (Segment-Schnittmenge).
        """
        path = get_data_dir(self._user_id) / "pending_briefings.json"
        if not path.exists():
            return
        data = _load_pending_entries(path)
        rest = [
            e for e in data.get("entries", [])
            if not (e.get("trip_id") == trip_id and e.get("reason") == "dispatch_error")
        ]
        if len(rest) == len(data.get("entries", [])):
            return
        data["entries"] = rest
        _write_pending_data(path, data)

    def _remove_pending_marker(self, trip_id: str) -> None:
        """Issue #1012 (b2): Entfernt den Nachliefer-Marker eines Trips (RMW)."""
        path = get_data_dir(self._user_id) / "pending_briefings.json"
        if not path.exists():
            return
        data = _load_pending_entries(path)
        data["entries"] = [
            e for e in data.get("entries", []) if e.get("trip_id") != trip_id
        ]
        _write_pending_data(path, data)

    def _bump_pending_marker_attempts(self, trip_id: str) -> None:
        """Issue #1012 (b2, Lärmschutz): attempts += 1, Marker bleibt bestehen."""
        path = get_data_dir(self._user_id) / "pending_briefings.json"
        if not path.exists():
            return
        data = _load_pending_entries(path)
        for e in data.get("entries", []):
            if e.get("trip_id") == trip_id:
                e["attempts"] = e.get("attempts", 0) + 1
        _write_pending_data(path, data)

    def _get_morning_hour(self, trip: "Trip") -> int:
        """Get configured morning hour for trip (default: 7).

        Issue #1594: die Regel steht in `_slot_stunde()` — dieselbe Fassung,
        die das Faelligkeits-Praedikat der Vorlauf-Sperre benutzt.
        """
        return _slot_stunde(trip, "morning")

    def _get_evening_hour(self, trip: "Trip") -> int:
        """Get configured evening hour for trip (default: 18). S. oben."""
        return _slot_stunde(trip, "evening")

    def _get_active_trips(self, report_type: str, now_utc: datetime) -> List["Trip"]:
        """
        Get trips that are active for the given report type.

        - morning: Trips with a stage for today
        - evening: Trips with a stage for tomorrow

        Issue #1724: "heute" ist der ORTStag DIESES Trips (ADR-0044), nicht
        das Datum der Serveruhr. Der Zieltag wird deshalb IN der Schleife je
        Trip bestimmt -- vorher stand er davor und galt fuer alle gleich. In
        Auckland lag er dadurch bis zu zwoelf Stunden am Tag daneben, und
        `get_stage_for_date` vergleicht strikt: kein Treffer heisst, der Trip
        wird still uebersprungen.

        Args:
            report_type: "morning" or "evening"
            now_utc: Zeitpunkt des Laufs. Pflichtparameter -- ein Default auf
                die Systemuhr wuerde genau die Umgebungsuhr wieder einfuehren,
                die ADR-0051 Regel 3 verbietet.

        Returns:
            List of active Trip objects
        """
        all_trips = load_all_trips(user_id=self._user_id)

        active = []
        for trip in all_trips:
            target_date = self._get_target_date(report_type, trip, now_utc)
            if trip.get_stage_for_date(target_date) is None:
                continue
            # Issue #995: Trip-Detail-Pause-Button (Go-Feld paused_at) unterdrückt
            # den automatischen Versand. NUR hier — NICHT in load_all_trips(),
            # sonst würde der Alert-Dispatch (trip_alert.py) fälschlich mit
            # unterdrückt. Manueller Test-Versand (send_test_report) umgeht diese
            # Funktion ohnehin und bleibt unberührt.
            if trip.paused_at is not None:
                continue
            rc = trip.report_config
            if rc is not None:
                if rc.enabled is False:
                    continue
                if rc.paused_until is not None:
                    # Ensure tz-aware comparison
                    pu = rc.paused_until
                    if pu.tzinfo is None:
                        pu = pu.replace(tzinfo=timezone.utc)
                    if now_utc < pu:
                        continue
                if rc.skip_next is True:
                    # Consume the flag: RMW
                    new_rc = dataclasses.replace(rc, skip_next=False)
                    new_trip = dataclasses.replace(trip, report_config=new_rc)
                    save_trip(new_trip, user_id=self._user_id)
                    continue
            active.append(trip)

        logger.debug(f"Active trips ({report_type}): {[t.id for t in active]}")
        return active

    def _get_target_date(self, report_type: str, trip: "Trip", now_utc: datetime) -> date:
        """
        Get the target date for the report type.

        Issue #1724 (ADR-0044): "heute" ist der Ortstag DIESES Trips. Vorher
        stand hier `date.today()` -- das Datum der Prozess-Zeitzone, auf dem
        Server `Etc/UTC`. Das war der in #1697 ausdruecklich offen gelassene
        Briefing-Pfad.

        Args:
            report_type: "morning" or "evening"
            trip: Trip, dessen Ortszeit den Kalendertag bestimmt
            now_utc: Zeitpunkt des Laufs (Pflichtparameter, s.
                `_get_active_trips`)

        Returns:
            date object (Ortstag fuer morning, Ortstag+1 fuer evening)
        """
        from services.trip_day import trip_local_today

        today = trip_local_today(trip, now_utc)
        if report_type == "morning":
            return today
        else:  # evening
            return today + timedelta(days=1)

    def _compute_stage_stats(self, stage) -> dict:
        """Compute aggregate stats for a stage from its waypoints."""
        wps = stage.waypoints
        if len(wps) < 2:
            return {}

        total_dist = 0.0
        total_ascent = 0.0
        total_descent = 0.0
        max_elev = max(wp.elevation_m for wp in wps)

        for i in range(len(wps) - 1):
            total_dist += haversine_km(
                wps[i].lat, wps[i].lon, wps[i + 1].lat, wps[i + 1].lon,
            )
            diff = wps[i + 1].elevation_m - wps[i].elevation_m
            if diff > 0:
                total_ascent += diff
            else:
                total_descent += abs(diff)

        return {
            "distance_km": round(total_dist, 1),
            "ascent_m": round(total_ascent),
            "descent_m": round(total_descent),
            "max_elevation_m": max_elev,
        }

    def select_test_stage(
        self, trip: "Trip", report_type: str, now_utc: datetime,
    ) -> Optional["Stage"]:
        """Pick the stage to use for a TEST briefing when no stage matches today/tomorrow.

        Issue #768 — Test-Pfad-Fallback (NICHT der reguläre Scheduler):

        - Wählt die zeitlich **nächste kommende** Etappe mit ``date >= heute``
          (kleinstes Datum). ``trip.get_future_stages`` ist strikt ``>`` und schließt
          „heute" aus — daher hier eine eigene ``>=``-Auswahl.
        - Liegen **alle** Etappen in der Vergangenheit, fällt es auf die chronologisch
          **erste** (früheste) Etappe zurück.
        - Leere ``stages`` → ``None``.

        Issue #1727 S5b (ADR-0044): „heute" ist der Ortstag DIESES Trips, nicht
        der Tag der Prozess-Zeitzone (auf dem Server `Etc/UTC`). Sonst zaehlte
        eine ortszeitlich bereits vergangene Etappe noch als „kommend" — der
        Test-Versand nahm die falsche Etappe. `now_utc` ist Pflichtparameter
        (ADR-0051 Regel 3): der Zeitpunkt kommt vom Aufrufer, damit der ganze
        Briefing-Aufbau auf EINER Zeitabfrage steht.

        Args:
            trip: Trip object.
            report_type: "morning" or "evening" (nicht ausschlaggebend für die Wahl,
                Teil des Kontrakts für Aufrufer-Symmetrie).
            now_utc: Zeitpunkt des Laufs (Pflichtparameter, s. `_get_target_date`).

        Returns:
            Die gewählte Stage oder None bei leeren stages.
        """
        from services.trip_day import trip_local_today

        if not trip.stages:
            return None
        today = trip_local_today(trip, now_utc)
        upcoming = sorted(
            (s for s in trip.stages if s.date >= today),
            key=lambda s: s.date,
        )
        if upcoming:
            return upcoming[0]
        return min(trip.stages, key=lambda s: s.date)

    def send_test_report(self, trip: "Trip", report_type: str) -> bool:
        """
        Send a manual test report for a trip.

        Public wrapper around _send_trip_report for UI-triggered sends.

        Issue #768: Test-Pfad aktiviert den Etappen-Fallback und kennzeichnet
        die Mail als Vorschau ([TEST]-Präfix + Hinweiszeile).

        Args:
            trip: Trip object
            report_type: "morning" or "evening"

        Returns:
            True if report was sent, False if no matching stage data found

        Raises:
            ValueError: If report_type is invalid
            Exception: If email sending fails
        """
        if report_type not in ("morning", "evening"):
            raise ValueError(f"Invalid report_type: {report_type}")
        # Issue #1725 (Adversary F006): `angefordert=True` — dieser Weg traegt
        # das Inbound-Kommando „report" (`trip_command_processor._trigger_report`).
        return self._send_trip_report(
            trip, report_type, allow_test_fallback=True, angefordert=True,
        )

    def send_test_report_outcome(self, trip: "Trip", report_type: str) -> str:
        """
        Public outcome-returning variant of send_test_report() (Issue #1325).

        Analog zum bestehenden send_on_demand_report()-Muster (#1007): lässt
        Aufrufer (API-Router) "no_stage" von "no_weather" unterscheiden,
        statt beides auf einen bloßen bool zu kollabieren. send_test_report()
        selbst bleibt für seine 6 bestehenden bool-Aufrufer unangetastet.

        Args:
            trip: Trip object
            report_type: "morning" or "evening"

        Returns:
            Outcome string: "sent" | "no_stage" | "no_weather" | "no_channels" |
            "channels_unreachable"

        Raises:
            ValueError: If report_type is invalid
        """
        if report_type not in ("morning", "evening"):
            raise ValueError(f"Invalid report_type: {report_type}")
        # Issue #1756: Idempotenz-Lock gegen doppelten Versand bei erneutem Klick.
        if not _try_acquire_send_lock(self._user_id, trip.id, report_type):
            return "already_in_progress"
        try:
            # Issue #1725 (Adversary F006): `angefordert=True` — dieser Weg traegt
            # den Test-Versand-Knopf (`api/routers/scheduler.send_test_trip_report`).
            return self._send_trip_report_outcome(
                trip, report_type, allow_test_fallback=True, angefordert=True,
            )
        finally:
            _release_send_lock(self._user_id, trip.id, report_type)

    def send_on_demand_report(self, trip: "Trip", report_type: str) -> OnDemandErgebnis:
        """
        Send an on-demand full briefing triggered by an inbound heute/morgen command.

        Issue #1007: Wiederverwendung des Test-Versand-Pfads (#768), aber OHNE
        Etappen-Fallback (kein Ausweichen auf eine andere Etappe, wenn am
        Zieltag keine Etappe liegt) und OHNE „[TEST]"-Präfix — stattdessen eine
        dezente „auf Anfrage"-Kennzeichnung im Mail-Body.

        Fix #1795 AC-7: der Zieltag wird HIER einmal aufgelöst (Ortstag, s.
        `_get_target_date`) und an `_send_trip_report_outcome` durchgereicht
        — derselbe Wert kommt im Rückgabe-`zieltag` an, statt dass ein
        Aufrufer ihn ein zweites Mal aus `received_at` raten muss (Nebengewinn:
        `_trigger_on_demand` verliert dadurch seinen eigenen `target_date`-
        Parameter).

        Args:
            trip: Trip object
            report_type: "morning" (heute) or "evening" (morgen)

        Returns:
            OnDemandErgebnis(outcome, zieltag) — outcome: "sent" | "no_stage" |
            "no_weather" | "no_channels" | "channels_unreachable" (Issue #1007
            Adversary-Fix F001/F002 — Outcome-Unterscheidung statt eines
            bloßen bool, damit der Aufrufer "keine Etappe" von "keine
            Wetterdaten" und von "kein Kanal aktiv" unterscheiden kann);
            zieltag: der TATSAECHLICH benutzte Ortstag.
        """
        if report_type not in ("morning", "evening"):
            raise ValueError(f"Invalid report_type: {report_type}")
        zieltag = self._get_target_date(report_type, trip, datetime.now(timezone.utc))
        # Issue #1756: geteilter Lock-Key-Raum mit send_test_report_outcome().
        if not _try_acquire_send_lock(self._user_id, trip.id, report_type):
            return OnDemandErgebnis(outcome="already_in_progress", zieltag=zieltag)
        try:
            # Issue #1725: `angefordert=True` NEBEN `on_demand=True` — die beiden
            # bedeuten Verschiedenes, siehe `_send_trip_report_outcome`.
            outcome = self._send_trip_report_outcome(
                trip, report_type, on_demand=True, angefordert=True, target_date=zieltag,
            )
        finally:
            _release_send_lock(self._user_id, trip.id, report_type)
        return OnDemandErgebnis(outcome=outcome, zieltag=zieltag)

    def _send_trip_report(
        self,
        trip: "Trip",
        report_type: str,
        allow_test_fallback: bool = False,
        on_demand: bool = False,
        angefordert: bool = False,
    ) -> bool:
        """
        Generate and send report for a single trip — legacy bool wrapper.

        Issue #1007 Adversary-Fix F001: die öffentlichen Aufrufer
        (send_test_report, send_reports, send_reports_for_hour) behalten ihre
        EXAKTE bool-Semantik von vorher (True auch bei "no_channels" —
        pre-existing Verhalten, nicht Teil dieses Issues). Die Outcome-
        Unterscheidung steckt in _send_trip_report_outcome().

        Returns:
            True if report was sent (or generated but no channel was
            configured), False if no matching stage/weather data found.
        """
        outcome = self._send_trip_report_outcome(
            trip, report_type, allow_test_fallback=allow_test_fallback,
            on_demand=on_demand, angefordert=angefordert,
        )
        return outcome in ("sent", "no_channels")

    def _send_trip_report_outcome(
        self,
        trip: "Trip",
        report_type: str,
        allow_test_fallback: bool = False,
        on_demand: bool = False,
        catchup_prefix: str | None = None,
        angefordert: bool = False,
        target_date: date | None = None,
    ) -> str:
        """
        Generate and send report for a single trip.

        Args:
            trip: Trip object
            report_type: "morning" or "evening"
            catchup_prefix: Issue #1012 (b2) — Hinweiszeile für nachgelieferte
                Briefings ("Nachgeliefert …" / "Aktualisiert …"), wird von
                _process_pending_markers() bei erfolgreicher Nachlieferung
                gesetzt.
            angefordert: Issue #1725 (Adversary F006) — der Versand geht auf
                eine Nutzeranfrage zurück (SMS „heute"/„morgen", Test-Versand-
                Knopf, Inbound-Kommando „report") statt auf den regulären Slot.
                Fließt AUSSCHLIESSLICH in den `briefing_log.json`-Eintrag, damit
                die Rückwärts-Ableitung ihn überspringen kann (AC-12).
                🔴 Bewusst NICHT `on_demand` mitbenutzt: dieses Flag trägt
                sieben weitere Bedeutungen über acht Lesestellen (weil
                `_mark_briefing_undelivered` zweimal vorkommt; vor diesem Fix
                waren es neun — die neunte, der Log-Eintrag, ist jetzt
                `angefordert`), die für Test-Versand und „report" allesamt
                unerwünscht wären. Es
                unterdrückt den Ausfall-Hinweisversand
                (`send_no_data_hint`-Zweig im Totalausfall), setzt eine
                „auf Anfrage"-Kennzeichnung in den Mail-Text
                (`on_demand_prefix` in `_build_trip_report_request`), hält
                Anker und Alarm-Gedächtnis an
                (`write_anchor_and_reset_memory` in `_anchor_and_reset`),
                unterdrückt beide Nachliefer-Marker
                (`_mark_briefing_undelivered` im Ausnahme- UND im
                `channels_unreachable`-Zweig, `_write_pending_marker` beim
                Teilausfall), verhindert das Aufräumen des
                Versandfehler-Vermerks (`_clear_dispatch_error_marker`) und
                die Entdopplung amtlicher Warnungen
                (`record_official_alerts_reported`). Ein Flag mit zwei
                Bedeutungen führt den nächsten Leser in die Irre.
                Absichtlich Namen statt Zeilennummern: diese Aufzählung stand
                zuerst mit Zahlen hier und zeigte nach dem eigenen Commit um
                30 Zeilen daneben — ausgerechnet der Verweis auf die
                Log-Zeile landete auf dem Gegenbeispiel (Adversary F008).
            target_date: Fix #1795 — optionaler, bereits aufgelöster Ortstag.
                Gesetzt (von `send_on_demand_report`): wird STATT der
                internen `datetime.now(timezone.utc)`-Auflösung unten benutzt
                — EINE Auflösung, kein Zweitauflöser. `None` (Default): die
                sechs bestehenden Aufrufer bleiben unverändert, die Funktion
                löst den Zieltag wie bisher selbst zum Ausführungszeitpunkt
                auf.

        Returns:
            "no_stage" if no matching stage, "no_weather" if the weather
            fetch failed, "no_channels" if stage+weather were fine but no
            channel is configured for the trip, "channels_unreachable" if a
            channel was configured but none was actually reached (Issue
            #1403 AC-4), "sent" otherwise.

        Raises:
            Exception: If weather fetch or email send fails
        """
        logger.info(f"Generating {report_type} report for trip: {trip.name}")

        # 1. Convert trip to segments
        # Issue #1727 S5b: EINE Zeitabfrage fuer den gesamten Briefing-Aufbau,
        # hier oben gebunden statt weiter unten mehrfach implizit aufgeloest.
        # Sie speist Zieltag, Etappen-Rueckfall, Klemme, Ausblick und
        # Gewitter-Ausblick — zwischen ihnen liegt ein Wetterabruf mit
        # Retry-Backoff und damit moeglicherweise eine Mitternacht
        # (gemessener Praezedenzfall: dispatch_orchestrator.py:157-163).
        now_utc = datetime.now(timezone.utc)
        # Issue #1724: Zieltag aus der Ortszeit DIESES Trips (ADR-0044).
        # Fix #1795: ein bereits aufgeloester `target_date` (s. Docstring)
        # ersetzt die interne Auflösung — kein zweiter Auflöser.
        if target_date is None:
            target_date = self._get_target_date(report_type, trip, now_utc)
        segments = self._convert_trip_to_segments(trip, target_date)

        # Issue #768: Test-Pfad-Fallback — wenn am regulären Zieldatum keine
        # Etappe liegt, weicht NUR der Test-Versand auf die nächste kommende
        # (bzw. früheste) Etappe aus. Der reguläre Scheduler (Default False)
        # bleibt unberührt (AC-7).
        if not segments and allow_test_fallback:
            fb = self.select_test_stage(trip, report_type, now_utc)
            if fb is not None:
                target_date = fb.date
                segments = self._convert_trip_to_segments(trip, target_date)

        if not segments:
            logger.warning(f"No segments for trip {trip.id} on {target_date}")
            return "no_stage"

        logger.debug(f"Created {len(segments)} segments for {trip.id}")

        # Issue #1325: Datums-Klemme NUR für den Wetter-Abruf im Test-
        # Fallback-Pfad. target_date (Stage-Header, Marker, Snapshot, s.u.)
        # bleibt unverändert auf dem echten (ggf. vergangenen) Etappendatum —
        # nur die Segment-Zeiten, die in _fetch_weather() gehen, wandern auf
        # "heute", damit ein echter Forecast statt eines toten
        # Vergangenheits-Requests entsteht.
        #
        # Issue #1727 S5b (ADR-0044): verglichen wird gegen den ORTSTAG der
        # Tour. `target_date` ist bereits ortsrichtig (`_get_target_date` ->
        # `trip_local_today`); ein roher `date.today()` daneben stellte zwei
        # verschiedene Tagesbegriffe in denselben `<`-Vergleich.
        from services.trip_day import trip_local_today

        heute_am_ort = trip_local_today(trip, now_utc)
        weather_segments = segments
        if allow_test_fallback and target_date < heute_am_ort:
            weather_segments = self._clamp_segments_to_today(
                segments, target_date, today=heute_am_ort,
            )

        # 1b. Compute local timezone from coordinates for display
        # (tz_for_coords now imported top-level — Bug #401)
        trip_tz = tz_for_coords(segments[0].start_point.lat, segments[0].start_point.lon)

        # Issue #1208: EINZIGER Ableitungspfad report_config → render-wirksame
        # Optionen; ersetzt 5 Direktzugriffe + den Patch-Hack (779) weiter unten.
        from services.report_config_resolver import resolve_report_render_options
        render_options = resolve_report_render_options(
            trip.report_config, trip.display_config, report_type,
        )

        # 2. Wind exposition detection (before weather fetch, needs TripSegments)
        from services.wind_exposition import WindExpositionService
        try:
            min_elev_kwargs = {}
            if trip.report_config and trip.report_config.wind_exposition_min_elevation_m is not None:
                min_elev_kwargs["min_elevation_m"] = trip.report_config.wind_exposition_min_elevation_m
            exposed_sections = WindExpositionService().detect_exposed_from_segments(
                segments, **min_elev_kwargs
            )
        except Exception as e:
            logger.warning(f"Wind exposition detection failed for {trip.id}: {e}")
            exposed_sections = []

        # 3. Fetch weather for each segment
        segment_weather = self._fetch_weather(weather_segments)

        # Issue #1087: amtliche Warnungen pro eindeutigem Segment-Startpunkt,
        # strukturell kein Fetch bei official_alerts_enabled=False (analog
        # comparison_engine.py Fetch-Gating, #1040-Pointer-Muster).
        if trip.official_alerts_enabled is not False:
            seen_coords: set[tuple[float, float]] = set()
            for sw in segment_weather:
                if sw.has_error:
                    continue
                coord = (
                    round(sw.segment.start_point.lat, 3),
                    round(sw.segment.start_point.lon, 3),
                )
                if coord in seen_coords:
                    continue
                seen_coords.add(coord)
                try:
                    from services.official_alerts import get_official_alerts_with_status
                    sw.official_alerts, sw.official_alerts_unavailable = (
                        get_official_alerts_with_status(
                            *coord,
                            window_start=segments[0].start_time,
                            window_end=segments[-1].end_time,
                        )
                    )
                except Exception:
                    logger.warning(
                        "trip_report_scheduler: official_alerts nicht ladbar",
                        exc_info=True,
                    )
                    sw.official_alerts = []
                    # Issue #1348: unerwarteter Fehler (z.B. Import) -> im Zweifel
                    # sicherheitsseitig warnen statt schweigen.
                    sw.official_alerts_unavailable = True

        # Issue #1113: Schwelle statt binärem Totalausfall (#1012) —
        # _fetch_weather() liefert bei Provider-Fehlern pro Segment einen
        # has_error=True-Platzhalter statt einer leeren Liste, die Liste ist
        # also nie leer.
        error_segments = [s for s in segment_weather if s.has_error]
        error_ratio = len(error_segments) / len(segment_weather) if segment_weather else 1.0
        partial_outage_hint = None

        if not segment_weather or error_ratio > OUTAGE_WITHHOLD_RATIO:
            logger.warning(f"All-failed weather data for trip {trip.id}")
            if not on_demand:
                # On-Demand (#1007) erzeugt weder Hinweis-Versand noch Marker —
                # der Bot antwortet synchron mit eigenem Hinweistext.
                config = trip.report_config
                self._notification_service.send_no_data_hint(
                    trip,
                    report_type,
                    send_email=not config or config.send_email,
                    send_sms=config is not None and config.send_sms and sms_allowed(self._user_id),
                    send_telegram=config is not None and config.send_telegram,
                    # Issue #1676 S2a: eigenes Tier-Gate (nur premium), NICHT
                    # sms_allowed() -- das laesst standard durch (Spec D7).
                    send_premium_sms=(
                        config is not None
                        and config.send_premium_sms
                        and premium_sms_allowed(self._user_id)
                    ),
                )
                self._write_pending_marker(
                    trip, report_type, target_date,
                    failed_segment_ids=[str(s.segment.segment_id) for s in error_segments],
                )
            return "no_weather"
        elif error_segments:
            # Teilausfall unterhalb der Schwelle: Hinweis statt Rückhalten.
            missing = ", ".join(f"Segment {s.segment.segment_id}" for s in error_segments)
            partial_outage_hint = (
                f"Hinweis: Für folgende Abschnitte liegen aktuell keine Wetterdaten vor "
                f"({missing}) — eine Aktualisierung wird nachgeliefert."
            )

        # 2b. Ensemble-Anreicherung: 1 API-Call für letzten Waypoint der letzten Etappe
        self._enrich_ensemble_for_trip(trip, segment_weather)

        # 2c. F12 / Issue #122 (refactored Issue #479):
        # Stabilitäts-Label für die kommenden Etappen — wird aus den bereits
        # vorhandenen `confidence_pct_min`-Werten der Folge-Segmente
        # abgeleitet; kein separater Z500-API-Call mehr.
        stability_result = None
        try:
            from services.weather_pattern import WeatherPatternService
            stability_result = WeatherPatternService().compute_for_trip(
                trip, target_date, segment_weather
            )
        except Exception as e:
            logger.warning(f"WeatherPatternService failed for {trip.id}: {e}")

        # 3. Stage info for header
        stage = trip.get_stage_for_date(target_date)
        stage_name = trip.numbered_stage_label(stage) if stage else None
        stage_stats = self._compute_stage_stats(stage) if stage else None

        # 4. Night weather (both report types — Issue #1313)
        night_weather = None
        if segment_weather:
            night_weather = self._fetch_night_weather(segment_weather[-1])

        # 6. Multi-day trend (configurable per report type — via Resolver, Issue #1208)
        #    Built BEFORE the thunder forecast (#1275): both must reflect the
        #    SAME actual future stage(s), never today's last segment.
        #    Fix #1486: `.rows` ist der unveraenderte Bestandswert, `.state`/
        #    `.horizon_days` benennen zusaetzlich, warum der Ausblick entfaellt.
        multi_day_trend = None
        outlook_state = None
        outlook_horizon_days = None
        if segment_weather and render_options.show_multi_day_trend:
            trend_result = self._build_stage_trend(
                trip, target_date, now_utc=now_utc, tz=trip_tz,
                report_type=report_type,
            )
            multi_day_trend = trend_result.rows
            outlook_state = trend_result.state
            outlook_horizon_days = trend_result.horizon_days

        # 5. Thunder forecast (+1/+2 days) — Issue #1275
        #    Same data source as the outlook table, so SMS/Telegram/E-Mail-
        #    Vorschau agree with it. When the multi-day trend was already built
        #    (evening default) its rows are REUSED — no second weather fetch.
        #    Only offsets not covered by the trend fall back to a dedicated
        #    single-stage fetch (typically morning, where the trend is off).
        #    Issue #1651: `night_weather` (Schritt 4, oben) wird durchgereicht,
        #    damit der Satz ein Gewitter ausserhalb des Tagesfensters nennt --
        #    aus DERSELBEN Reihe, die daneben als Nacht-Tabelle steht.
        thunder_forecast = self._build_thunder_forecast_from_trend_or_fetch(
            trip, target_date, now_utc=now_utc, tz=trip_tz,
            multi_day_trend=multi_day_trend, night_weather=night_weather,
        )

        # 7b. Vortag-Vergleich (Issue #750): gestrigen Snapshot laden + Deltas
        # berechnen. Fail-soft — fehlt der Vortag, bleibt day_comparison None.
        # Issue #1208: Patch-Hack (`trip.display_config.show_compact_summary =
        # trip.report_config.show_compact_summary`) entfaellt ersatzlos — der
        # Resolver liest show_compact_summary bereits aus report_config,
        # keine Mutation von trip.display_config mehr noetig.
        day_comparison = None
        if render_options.show_yesterday_comparison:
            try:
                from services.weather_snapshot import WeatherSnapshotService
                from services.day_comparison import DayComparisonService
                yday = WeatherSnapshotService(self._user_id).load_dated(
                    trip.id, target_date - timedelta(days=1))
                if yday:
                    day_comparison = DayComparisonService().compare(segment_weather, yday)
            except Exception as e:
                logger.warning(f"Vortag-Vergleich übersprungen für {trip.id}: {e}")
                day_comparison = None

        # 7c. Issue #1439: Starkregen-Kurzfristhinweis (planmaessiger Pfad) —
        # Segment-Auswahl/Naehe-Guard/Budget-Gate/Fetch laufen VOR dem Bau des
        # TripReportRequest, damit ein zu weit entferntes Segment oder ein
        # ausgeschoepftes Tagesbudget keinen Nowcast-Call verursacht. Liefert
        # nur Rohdaten (intensity_label, onset_minutes) — die Textformatierung
        # (Renderer-Aufruf) passiert im NotificationService (Architektur-Grenze).
        starkregen_nowcast = self._build_starkregen_hint(
            trip, segments, datetime.now(timezone.utc),
        )

        # 8. NotificationService: render + send (Issue #1022).
        # Der Scheduler liefert nur noch ein DTO; Renderer-/Transport-Imports
        # bleiben im NotificationService.
        request = self._build_trip_report_request(
            trip=trip,
            report_type=report_type,
            segment_weather=segment_weather,
            trip_tz=trip_tz,
            stage_name=stage_name,
            stage_stats=stage_stats,
            night_weather=night_weather,
            thunder_forecast=thunder_forecast,
            multi_day_trend=multi_day_trend,
            outlook_state=outlook_state,
            outlook_horizon_days=outlook_horizon_days,
            stability_result=stability_result,
            day_comparison=day_comparison,
            exposed_sections=exposed_sections,
            allow_test_fallback=allow_test_fallback,
            on_demand=on_demand,
            catchup_prefix=catchup_prefix,
            partial_outage_hint=partial_outage_hint,
            render_options=render_options,
            starkregen_nowcast=starkregen_nowcast,
        )
        # 8b. Issue #1467 S2 AG5: Anker und Melde-Gedächtnis hängen an EINER
        # Bedingung, in EINEM geteilten Baustein, den auch der Ortsvergleich
        # benutzt. Beides steht HIER oben, weil der Fehlerpfad des Versands
        # (unten) exakt denselben Aufruf braucht (#1629) — zwei Fassungen
        # dürften auseinanderlaufen, dieser eine darf es nicht.
        # Issue #1007: On-Demand-Abruf (heute/morgen-Kommando) ist read-only
        # gegenüber Snapshot-/Alert-Zustand — Baseline bleibt das letzte
        # reguläre Briefing. Ein On-Demand-Abruf für nur EINEN Zieltag würde
        # sonst die kombinierte Momentaufnahme (heute+morgen) mit dem einen
        # Zieltag überschreiben und Alerts/Vortag-Vergleich für den jeweils
        # anderen Tag verfälschen (`write_anchor_and_reset_memory` steigt bei
        # on_demand=True aus, hier wird nichts nachgebaut).
        # Issue #816 (B): Briefing = neue, stabile Alert-Referenz → das
        # Melde-Gedächtnis des Trips zurücksetzen, damit der nächste Alert
        # wieder gegen das frische Briefing vergleicht.
        def _write_briefing_anchor() -> None:
            try:
                from services.weather_snapshot import WeatherSnapshotService
                _snapshot_svc = WeatherSnapshotService(self._user_id)
                _snapshot_svc.save(trip.id, segment_weather, target_date)
                _snapshot_svc.save_dated(trip.id, target_date, segment_weather)
            except Exception as e:
                logger.warning(f"Failed to save weather snapshot for {trip.id}: {e}")

        def _anchor_and_reset() -> None:
            write_anchor_and_reset_memory(
                user_id=self._user_id,
                entity_ids=[trip.id],
                write_anchor=_write_briefing_anchor,
                on_demand=on_demand,
                reset_memory=self._reset_alert_state_after_briefing,
                # Issue #1461 S3b-1: Briefing-Zeitstempel unter der PROTOKOLL-
                # Kennung (hier deckungsgleich mit der Anker-Kennung).
                briefing_entity_id=trip.id,
                briefing_entity_type="trip",
            )

        # Issue #1629: Wirft der Versand (E-Mail propagiert, SMS/Telegram sind
        # fail-soft), fiel bisher alles darunter aus — insbesondere der Anker.
        # Ergebnis am 08.08.: ein ganzer Tag ohne Abweichungs-Alarm. Ein bloß
        # nicht zustellbares Briefing (`result.sent == False`) schreibt ihn seit
        # jeher; hier wird nur Gleichbehandlung hergestellt. Bewusst
        # `except Exception` — Auslöser war der Empfänger-Schutz, es kann jeder
        # Kanalfehler sein. Der Block umschließt AUSSCHLIESSLICH den
        # Versandaufruf: über dem Wetterabruf entstünde ein Anker aus
        # unvollständigen Daten, also eine Referenz, die nie ein Briefing war
        # (AC-10).
        try:
            result = self._notification_service.send_trip_report(request)
        except Exception as exc:
            record_briefing_dispatch_failure(
                user_id=self._user_id, kind="route", entity_id=trip.id, error=exc,
            )
            _anchor_and_reset()
            # Issue #1662: Hier ist laut Zustellbilanz KEIN Kanal durchgekommen
            # (sonst wäre die Ausnahme gar nicht bis hierher gelangt) — das
            # Briefing wird zur Nachlieferung vorgemerkt, statt ersatzlos
            # verloren zu gehen. Zweiter Aufrufer derselben Stelle: der
            # ausnahmefreie Weg unten (`not result.sent`).
            self._mark_briefing_undelivered(
                trip, report_type, target_date, on_demand=on_demand,
            )
            # Unverändert weiterreichen: `dispatch_orchestrator` zählt den Lauf
            # weiterhin als fehlgeschlagen und protokolliert ihn (AC-3).
            raise
        errors = request.failed_segments

        # Issue #1439 AC-6: ein erfolgreich versendeter Kurzfristhinweis
        # schreibt denselben Radar-Cooldown, den ein echter Radar-Alert nach
        # Versand ohnehin schreibt (trip_alert.py:935) — Wiederverwendung des
        # bestehenden Throttles statt eines neuen State-Mechanismus. Der
        # naechste 15-Minuten-Poll ist dadurch an seiner ERSTEN Pruefung
        # bereits blockiert (kein widerspruechlicher Folge-Alert).
        if starkregen_nowcast and result.sent:
            from services.throttle_store import ThrottleStore
            ThrottleStore(self._user_id).record("radar", trip.id, datetime.now(timezone.utc))

        # Issue #393: Briefing-Log für Cockpit-Kachel "Was geht heute raus".
        # Issue #1007 Adversary-Fix F001: bei explizit konfiguriertem "kein
        # Kanal aktiv" wird KEIN Log-Eintrag mit channels=[] geschrieben.
        # Issue #1403: dieselbe Unterscheidung gilt für die Protokollzeile —
        # "Trip report sent" nur bei tatsächlichem Versand, sonst eine
        # abweichende Warnzeile, damit echter und ausgebliebener Versand im
        # Protokoll unterscheidbar sind.
        # Issue #1403 AC-4: ein Kanal kann konfiguriert, aber technisch nicht
        # erreichbar sein (z.B. Telegram ohne gültige Bot-Verbindung) —
        # result.sent_channels bleibt dann leer, obwohl no_channel_configured
        # False ist (result.sent ist die ehrliche Zustellfähigkeits-Aussage,
        # notification_service.py:408). Gleiche Konsequenz wie beim
        # "kein Kanal aktiv"-Fall: kein briefing_log-Eintrag (sonst täuscht ein
        # Eintrag mit channels=[] der Cockpit-Kachel #393/#1007 einen Versand
        # vor), aber eine eigene, unterscheidbare Protokollzeile.
        if result.no_channel_configured:
            logger.warning(
                f"Trip report NOT sent (no channel configured): {trip.name} ({report_type})"
            )
        elif not result.sent:
            logger.warning(
                f"Trip report NOT sent (configured channel unreachable): {trip.name} ({report_type})"
            )
        else:
            # Issue #1847: die Erfolgszeile nennt zusaetzlich die tatsaechlich
            # zugestellten Kanaele und — sofern E-Mail dabei war — den
            # E-Mail-Empfaenger. Vorbild ist der Compare-Pfad
            # (scheduler_dispatch_service.py:571, "Compare preset %s sent to
            # %s"): dort war "Versand gemeldet, Postfach leer" in einer Minute
            # aufgeklaert, hier kostete dieselbe Falle eine Stunde (vierte
            # Wiederholung: #1351, #1403, #1782, #1847). Bewusst UNMASKIERT —
            # eine Maskierung machte gregor-test@ und gregor-staging@
            # ununterscheidbar und verfehlte genau den Zweck.
            mail_empfaenger = (
                self._settings.mail_to if "email" in result.sent_channels else None
            )
            self._append_briefing_log(
                trip.id, report_type, result.sent_channels,
                angefordert=angefordert, mail_empfaenger=mail_empfaenger,
            )
            logger.info(
                "Trip report sent: %s (%s) via %s%s",
                trip.name,
                report_type,
                ",".join(result.sent_channels),
                f" to {mail_empfaenger}" if mail_empfaenger else "",
            )

        # 8c. Issue #1662 AC-5: Der gelungene Versand macht einen offenen
        # Versandfehler-Vermerk gegenstandslos — der Nutzer hat sein Briefing
        # auf dem regulären Weg bekommen, eine Nachlieferung würde doppeln.
        if result.sent and not on_demand:
            self._clear_dispatch_error_marker(trip.id)

        # 9. Issue #1012: Teilausfall-Marker (Service-Error-Mail wurde bereits
        # vom NotificationService verschickt, weil failed_segments im Request
        # mitgeliefert wurden).
        if errors and not on_demand:
            self._write_pending_marker(
                trip, report_type, target_date,
                failed_segment_ids=[str(s.segment.segment_id) for s in errors],
            )

        # 10. Save weather snapshot for alert comparison — der Anker-Aufruf
        # selbst steht bei 8b (siehe dort), damit Erfolgs- und Fehlerpfad des
        # Versands nachweislich denselben benutzen (#1629).
        # Issue #1614 Teil 1: eine amtliche Warnung, die bereits erfolgreich im
        # Trip-Briefing gemeldet wurde, darf der unabhaengige 15-Minuten-
        # Alarm-Checker nicht bis zu 15 Minuten spaeter nochmal als eigene,
        # redundante Nachricht verschicken. Beide Bedingungen sind zwingend:
        # result.sent (sonst waere eine NIE zugestellte Warnung faelschlich
        # als "gemeldet" markiert, AC-4) UND not on_demand (Ad-hoc-Abruf
        # bleibt read-only, #1007, AC-3). VOR write_anchor_and_reset_memory,
        # damit ein Exception-Pfad dort das Record nicht verschluckt.
        if result.sent and not on_demand:
            all_official_alerts = [
                a for sw in segment_weather for a in (sw.official_alerts or [])
            ]
            if all_official_alerts:
                from services.alert_briefing_anchor import record_official_alerts_reported
                record_official_alerts_reported(
                    user_id=self._user_id, entity_id=trip.id, alerts=all_official_alerts,
                )

        _anchor_and_reset()

        if result.no_channel_configured:
            # Kein Vermerk: hier ist nichts ausgefallen, es war nichts
            # vorgesehen (#1662 — Abgrenzung zum Zweig darunter).
            return "no_channels"
        if not result.sent:
            # Issue #1403 AC-4: konfiguriert, aber kein Kanal tatsächlich
            # betreten (z.B. Telegram ohne gültige Bot-Verbindung) — ehrlich
            # unterscheidbar vom "no_channels"-Fall oben.
            # Issue #1662 AC-1: Auch hier hat NIEMAND das Briefing bekommen —
            # nur eben ohne Ausnahme (SMS/Telegram sind fail-soft). Deshalb
            # derselbe Vermerk wie im `except`-Zweig; "unerreichbar" bleibt
            # dabei ein Ergebnis und wird KEINE Ausnahme.
            self._mark_briefing_undelivered(
                trip, report_type, target_date, on_demand=on_demand,
            )
            return "channels_unreachable"
        return "sent"

    def _build_trip_report_request(
        self,
        *,
        trip: "Trip",
        report_type: str,
        segment_weather: list[SegmentWeatherData],
        trip_tz: ZoneInfo,
        stage_name: str | None,
        stage_stats: dict | None,
        night_weather: Optional[NormalizedTimeseries],
        thunder_forecast: Optional[dict],
        multi_day_trend: Optional[list[dict]],
        stability_result: Optional[StabilityResult],
        outlook_state=None,
        outlook_horizon_days: Optional[int] = None,
        day_comparison: Optional[DayComparison],
        exposed_sections: list,
        allow_test_fallback: bool,
        on_demand: bool,
        catchup_prefix: str | None,
        partial_outage_hint: str | None = None,
        render_options: Optional["ReportRenderOptions"] = None,
        starkregen_nowcast: Optional[Tuple[str, int]] = None,
    ) -> TripReportRequest:
        """Baut das DTO, das an den NotificationService übergeben wird (Issue #1022).

        WEATHER-04: Fehlerhafte Segmente werden explizit als `failed_segments`
        übergeben, damit der NotificationService bei SMS-only-Trips eine
        Service-E-Mail verschicken kann.
        """
        config = trip.report_config
        errors = [s for s in segment_weather if s.has_error]
        return TripReportRequest(
            trip=trip,
            report_type=report_type,
            segment_weather=segment_weather,
            trip_tz=trip_tz,
            stage_name=stage_name,
            stage_stats=stage_stats,
            night_weather=night_weather,
            thunder_forecast=thunder_forecast,
            multi_day_trend=multi_day_trend,
            outlook_state=outlook_state,
            outlook_horizon_days=outlook_horizon_days,
            stability_result=stability_result,
            day_comparison=day_comparison,
            exposed_sections=exposed_sections,
            report_config=config,
            display_config=trip.display_config,
            profile=trip.aggregation.profile,
            shortcode=getattr(trip, 'shortcode', None) or None,
            stage_total=len(trip.stages) if trip.stages else None,
            trip_url=f"https://gregor20.henemm.com/trips/{trip.id}",
            send_email=not config or config.send_email,
            send_sms=config is not None and config.send_sms and sms_allowed(self._user_id),
            # Issue #1676 S2a: eigenes Tier-Gate (nur premium), NICHT
            # sms_allowed() -- das laesst standard durch (Spec D7).
            send_premium_sms=(
                config is not None
                and config.send_premium_sms
                and premium_sms_allowed(self._user_id)
            ),
            send_telegram=config is not None and config.send_telegram,
            test_prefix=allow_test_fallback,
            on_demand_prefix=on_demand,
            catchup_prefix=catchup_prefix,
            partial_outage_hint=partial_outage_hint,
            failed_segments=errors,
            on_demand=on_demand,
            render_options=render_options,
            starkregen_nowcast=starkregen_nowcast,
        )

    def _build_starkregen_hint(
        self,
        trip: "Trip",
        segments: List[TripSegment],
        now_utc: datetime,
    ) -> Optional[Tuple[str, int]]:
        """Starkregen-Kurzfristhinweis (Issue #1439): liefert die Rohdaten
        (``intensity_label``, ``onset_minutes``) fuer den planmaessigen
        Briefing-Pfad, wenn der bereits produktive `RadarNowcastService`
        (#656) fuer den Startpunkt des aktiven/naechsten Segments Starkregen
        innerhalb von `NOWCAST_HORIZON_MIN` erkennt.

        Architektur-Grenze (`tests/unit/test_notification_service.py::
        test_scheduler_has_no_output_imports`): der Scheduler liefert nur ein
        DTO, KEINEN Renderer-Aufruf — die Textformatierung
        (`format_starkregen_hint()`) passiert in `notification_service.py`.

        Segment-Auswahl nach derselben Grundregel wie
        `TripAlertService.check_radar_alerts()` (trip_alert.py:917-955):
        aktives Segment, sonst Vorschau auf das erste. Den tagesuebergreifenden
        Vortags-Rueckgriff des Alarm-Pfads (Issue #1667 S3) hat dieser Pfad
        BEWUSST nicht — `_get_target_date` ist strikt vorwaertsgerichtet
        (morgens `today`, abends `today+1`) und die Briefing-Kopfdaten stammen
        aus `trip.get_stage_for_date(target_date)`; ein Vortags-Rueckgriff
        erzeugte hier ein Briefing mit heutiger Etappe im Kopf und gestriger
        Koordinate im Regenhinweis. Die Live-Ueberwachung eines noch laufenden
        Vortagssegments ist Aufgabe von `check_radar_alerts()` (alle ~15 min),
        nicht der zweimal taeglichen Briefing-Erzeugung.
        Naehe-Guard und Budget-Gate laufen VOR dem
        Fetch — ein zu weit entferntes Segment oder ausgeschoepftes Tagesbudget
        verursacht keinen Nowcast-Call (AC-1/AC-2). Fail-soft bei Fetch-Fehlern
        (ADR-0018, AC-4).
        """
        if not segments:
            return None

        active = None
        for seg in segments:
            if seg.start_time <= now_utc <= seg.end_time:
                active = seg
                break
        if active is None:
            if now_utc < segments[0].start_time:
                active = segments[0]
            else:
                return None

        from services.radar_service import NOWCAST_HORIZON_MIN

        if active.start_time > now_utc:
            minutes_until_start = (active.start_time - now_utc).total_seconds() / 60.0
            if minutes_until_start > NOWCAST_HORIZON_MIN:
                return None

        # Issue #1726: reine Lesestelle (bucht nie), liest aber denselben
        # Zaehler wie der Alarm-Pfad — also auf dem Kalendertag der TOUR.
        from services.trip_day import anchor_tz

        if not alert_daily_limit.is_allowed(
            self._user_id, now_utc, anchor_tz(trip, now_utc), reason="nowcast",
        ):
            return None

        from services.radar_service import INTENSITY_HEAVY, RadarNowcastService

        lat = active.start_point.lat
        lon = active.start_point.lon
        try:
            radar_svc = RadarNowcastService()
            # Issue #1329 C2: der Scheduler ist ein Hintergrund-/Cron-Prozess
            # wie der 15-Minuten-Alarm-Poll, kein direkter Nutzerklick.
            result = radar_svc.get_nowcast(lat, lon, priority="polling")
        except Exception as e:
            logger.warning(f"Starkregen-Kurzfristhinweis: Nowcast fehlgeschlagen fuer {trip.id}: {e}")
            return None

        if result.onset_minutes is None or result.intensity_label != INTENSITY_HEAVY:
            return None

        return (result.intensity_label, result.onset_minutes)

    def _reset_alert_state_after_briefing(self, trip_id: str) -> None:
        """Issue #816 (B): Alert-Melde-Gedächtnis nach Briefing-Versand löschen.

        Issue #1467 S2 AG5: nur noch überschreibbare Naht — die Reset-Logik
        (inkl. fail-soft und Log) liegt in `reset_alert_memory()`, der EINEN
        Fassung für Trip und Ortsvergleich. Kein Nachbau hier.
        """
        reset_alert_memory(user_id=self._user_id, entity_id=trip_id)

    def _append_briefing_log(
        self, trip_id: str, kind: str, channels: List[str], angefordert: bool = False,
        mail_empfaenger: Optional[str] = None,
    ) -> None:
        """Issue #393: Hängt einen Briefing-Versand-Eintrag an briefing_log.json an.

        Wird von Go (GET /api/cockpit/status) read-only gelesen. Kein Bereinigen —
        das Frontend filtert auf "heute".

        Issue #1725 (Adversary F004/F006): `angefordert` hält fest, dass der
        Eintrag aus einem vom Nutzer ANGEFORDERTEN Versand stammt und nicht aus
        dem regulären Slot. Angefordert sind alle drei Wege, die AC-12
        aufzählt: SMS „heute"/„morgen" (`send_on_demand_report`), der
        Test-Versand-Knopf (`send_test_report_outcome`, gerufen von
        `api/routers/scheduler.send_test_trip_report`) und das Inbound-Kommando
        „report" (`send_test_report`, gerufen von
        `trip_command_processor._trigger_report`). Die
        Rückwärts-Ableitung in `briefing_slots._log_bezeugt_versand`
        überspringt solche Einträge — ohne das Feld nähme eine Nutzeranfrage
        dem Nutzer sein reguläres Briefing desselben Ortstags (AC-12).

        Der Eintrag selbst wird weiterhin geschrieben: ihn wegzulassen änderte
        die Cockpit-Kachel #393, und das ist eine andere Scheibe. Der
        JSON-Schlüssel heißt weiterhin `on_demand` — er ist das Wire-Format,
        das `briefing_slots` liest; Go liest die Datei nur
        (`store.LoadBriefingLog`, kein Schreibpfad), ignoriert unbekannte
        Felder und schreibt sie deshalb auch nicht weg.

        Issue #1847: `mail_empfaenger` hält fest, an WELCHE Adresse das
        Briefing per E-Mail ging — sonst ist „Versand gemeldet, Postfach leer"
        nachträglich nicht mehr auflösbar (vierte Wiederholung derselben Falle:
        #1351, #1403, #1782, #1847). Der Schlüssel `mail_to` entsteht nur, wenn
        E-Mail auch tatsächlich zugestellt wurde — ein Eintrag, der bei JEDEM
        Versand eine Adresse nennt, wäre keine Zustell-Aussage. Rein additiv:
        die bestehenden Schlüssel bleiben unverändert, Go ignoriert den neuen
        (s.o.).
        """
        path = get_data_dir(self._user_id) / "briefing_log.json"
        data = json.loads(path.read_text()) if path.exists() else {"entries": []}
        eintrag: Dict[str, object] = {
            "trip_id": trip_id,
            "kind": kind,
            "sent_at": datetime.now(tz=timezone.utc).isoformat(),
            "channels": channels,
            "on_demand": angefordert,
        }
        if mail_empfaenger:
            eintrag["mail_to"] = mail_empfaenger
        data["entries"].append(eintrag)
        # Issue #1614: ein frischer Nutzer ohne jedes vorherige Datenverzeichnis
        # (kein Trip-Snapshot, kein Alert-State) hatte hier noch kein
        # Zielverzeichnis — path.write_text() scheiterte mit FileNotFoundError.
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    def _convert_trip_to_segments(
        self,
        trip: "Trip",
        target_date: date
    ) -> List[TripSegment]:
        """Thin delegator — real logic lives in services.trip_segments (Issue #822).

        Behaviour is bit-identical to the previous inline implementation;
        the refactor is a pure Extract Function with no semantic change.
        """
        from services.trip_segments import convert_trip_to_segments
        return convert_trip_to_segments(trip, target_date)

    def _clamp_segments_to_today(
        self, segments: List[TripSegment], from_date: date, today: date,
    ) -> List[TripSegment]:
        """Shift segment start_time/end_time from `from_date` to today (Issue #1325).

        Pure helper — kein Netz-/IO-Zugriff. Erhält den Uhrzeit-Anteil, nur
        das Kalenderdatum wandert um `today - from_date` Tage nach vorne.
        Ausschließlich für den Wetter-Abruf-Input im Test-Fallback-Pfad
        genutzt, damit ein veralteter Test-Trip (alle Etappen in der
        Vergangenheit) trotzdem einen echten Forecast statt eines toten
        historischen Datums bekommt.

        Issue #1727 S5b: `today` kommt PFLICHTWEISE vom Aufrufer, der ihn dort
        bereits ortsrichtig hat (`trip_local_today`). Diese Funktion sieht kein
        `Trip`-Objekt und könnte den Ortstag gar nicht selbst bestimmen — ein
        eigenes `date.today()` verschob die Segmentzeiten im Mismatch-Fenster
        um einen Tag zu wenig oder zu weit (ADR-0044).
        """
        delta_days = (today - from_date).days
        if delta_days <= 0:
            return segments
        shift = timedelta(days=delta_days)
        return [
            dataclasses.replace(
                seg,
                start_time=seg.start_time + shift,
                end_time=seg.end_time + shift,
            )
            for seg in segments
        ]

    def _fetch_weather(
        self,
        segments: List[TripSegment],
        provider=None,
    ) -> List[SegmentWeatherData]:
        """
        Fetch weather data for all segments.

        Uses SegmentWeatherService with provider fallback chain.

        Args:
            segments: List of TripSegment objects
            provider: Optional WeatherProvider instance. When None (default),
                the standard OpenMeteo provider is used. Injecting a
                FixtureProvider here enables the Demo-Mode (Issue #483)
                without any Live-API call.

        Returns:
            List of SegmentWeatherData objects
        """
        from providers.base import get_provider
        from services.segment_weather import SegmentWeatherService

        # OpenMeteo with automatic regional model selection (AROME, ICON-D2, ECMWF)
        # — unless caller injects an alternative provider (Issue #483: Demo-Mode).
        if provider is None:
            provider = get_provider("openmeteo")
        service = SegmentWeatherService(provider)

        weather_data = []
        # Adversary Finding F002: sobald EIN Segment trotz aller Retries
        # endgültig gescheitert ist, deutet das auf einen andauernden
        # Provider-Ausfall hin (nicht auf einen einzelnen Ausreißer) — die
        # restlichen Segmente desselben Aufrufs bekommen dann nur noch 1
        # Versuch (kein Sleep), damit der >75 %-Guard einen Totalausfall in
        # Sekunden statt Minuten erkennt (~150 User im sequenziellen
        # Scheduler-Loop).
        fail_fast = False
        for segment in segments:
            last_error: Exception | None = None
            returned_error_data: SegmentWeatherData | None = None
            attempts = 1 if fail_fast else FETCH_RETRY_ATTEMPTS + 1
            for attempt in range(attempts):
                try:
                    # Bug #288: Skip ensemble per-segment; will be added once via
                    # _enrich_ensemble_for_trip() to keep API-Calls at 1/Report.
                    data = service.fetch_segment_weather(segment, enrich_ensemble=False)
                except Exception as e:
                    last_error = e
                    returned_error_data = None
                    has_more_attempts = attempt < attempts - 1
                    if has_more_attempts and _is_transient_fetch_error(e):
                        # Issue #1113: kurzer Backoff gegen transiente 503er,
                        # bevor der Fehler-Platzhalter erzeugt wird.
                        time_module.sleep(FETCH_RETRY_BACKOFF_SECONDS * (attempt + 1))
                        continue
                    logger.error(
                        f"Weather fetch failed for segment {segment.segment_id} "
                        f"after {attempt + 1} attempt(s): {e}"
                    )
                    break
                if data.has_error:
                    # Adversary F005-Folgefund: SegmentWeatherService faengt
                    # ProviderRequestError bereits intern ab (WEATHER-04) und
                    # liefert statt eines Raise ein has_error-Objekt zurueck.
                    # Der echte Provider (openmeteo.py) wirft IMMER diese
                    # Exception-Klasse, daher muss die Retry-Pruefung auch
                    # den Rueckgabewert inspizieren — nicht nur geworfene
                    # Exceptions —, sonst greift der Retry gegen den echten
                    # Produktionscode-Pfad nie.
                    last_error = RuntimeError(data.error_message)
                    returned_error_data = data
                    has_more_attempts = attempt < attempts - 1
                    if has_more_attempts and _is_transient_fetch_error(last_error):
                        time_module.sleep(FETCH_RETRY_BACKOFF_SECONDS * (attempt + 1))
                        continue
                    logger.error(
                        f"Weather fetch failed for segment {segment.segment_id} "
                        f"after {attempt + 1} attempt(s): {data.error_message}"
                    )
                    break
                weather_data.append(data)
                last_error = None
                returned_error_data = None
                break
            if last_error is not None:
                # Adversary Finding F004: Fail-Fast nur, wenn dieses Segment
                # sein volles Retry-Budget durchlaufen hat UND der letzte
                # Fehler transient war — das ist das "Provider ist wirklich
                # down"-Signal. Ein sofortiger nicht-transienter Fehler
                # (z. B. ungueltige Koordinaten, 0 Retries verbraucht) darf
                # den Retry-Anspruch der Folgesegmente nicht zerstoeren.
                if attempt == attempts - 1 and _is_transient_fetch_error(last_error):
                    fail_fast = True
                if returned_error_data is not None:
                    # SegmentWeatherService lieferte bereits ein vollstaendiges
                    # has_error-Objekt (korrekter provider-Name) — kein neuer
                    # Platzhalter noetig.
                    weather_data.append(returned_error_data)
                else:
                    # WEATHER-04: Error-Placeholder statt auslassen
                    error_data = SegmentWeatherData(
                        segment=segment,
                        timeseries=None,
                        aggregated=SegmentWeatherSummary(),
                        fetched_at=datetime.now(timezone.utc),
                        provider="unknown",
                        has_error=True,
                        error_message=str(last_error),
                    )
                    weather_data.append(error_data)

        return weather_data

    def _fetch_night_weather(
        self,
        last_segment: SegmentWeatherData,
    ) -> Optional[NormalizedTimeseries]:
        """
        Fetch night weather from arrival until 06:00 next morning.

        Issue #1315: thin delegator — the actual fetch lives in
        ``services.segment_weather.fetch_night_weather`` so the Vorschau
        (preview_service) can reuse the exact same behaviour (Konsolidierung,
        kein Duplikat). Versand-Verhalten unveraendert.
        """
        from services.segment_weather import fetch_night_weather
        return fetch_night_weather(last_segment)

    def _enrich_ensemble_for_trip(
        self,
        trip: "Trip",
        weather_data: List[SegmentWeatherData],
    ) -> None:
        """Bug #288: Add ensemble-spread confidence once per trip.

        Performs a single Ensemble-API call for the last waypoint of the
        last stage, then propagates confidence_pct / spread_t2m_k /
        spread_precip_mm onto every DataPoint of every segment. Finally,
        SegmentWeatherSummary.confidence_pct_min is set retroactively
        (the dataclass is not frozen).

        Args:
            trip: Trip whose last stage / last waypoint anchors the call.
            weather_data: Segment-weather list to enrich in-place.
        """
        from providers.base import get_provider
        from providers.openmeteo import OpenMeteoProvider
        from app.config import Location

        if not weather_data or not trip.stages:
            return

        # 1. Last waypoint of last non-empty stage (Issue #805: pause stages have 0 waypoints)
        last_wp = next(
            (s.last_waypoint for s in reversed(trip.stages) if s.waypoints),
            None,
        )
        if last_wp is None:
            return
        location = Location(
            latitude=last_wp.lat,
            longitude=last_wp.lon,
            name=last_wp.name or "Ziel",
            elevation_m=last_wp.elevation_m,
        )

        # 2. Derive time range from weather_data
        all_starts = [w.segment.start_time for w in weather_data if w.segment]
        all_ends = [w.segment.end_time for w in weather_data if w.segment]
        if not all_starts or not all_ends:
            return
        start = min(all_starts)
        end = max(all_ends)

        # 3. Ensemble-API call (best-effort: failures must not crash report)
        provider = get_provider("openmeteo")
        if not isinstance(provider, OpenMeteoProvider):
            return
        try:
            spreads = provider._fetch_ensemble_spread(location, start, end)
        except Exception as e:
            logger.warning("_enrich_ensemble_for_trip: ensemble fetch failed: %s", e)
            return

        if not spreads:
            return

        # 4. Timestamp-normalised lookup (mirrors openmeteo.py:770-787)
        now_utc = datetime.now(timezone.utc)
        spreads_naive: Dict[datetime, Tuple[Optional[float], Optional[float]]] = {}
        for k, v in spreads.items():
            k_naive = k.replace(tzinfo=None) if k.tzinfo is not None else k
            spreads_naive[k_naive] = v

        self._apply_ensemble_spreads(weather_data, spreads_naive, now_utc)

    def _apply_ensemble_spreads(
        self,
        weather_data: List[SegmentWeatherData],
        spreads_naive: Dict[datetime, Tuple[Optional[float], Optional[float]]],
        now_utc: datetime,
    ) -> None:
        """Propagate pre-computed ensemble spreads onto DataPoints and set confidence_pct_min.

        No API call — works exclusively on provided data. Extracted from
        _enrich_ensemble_for_trip() to allow direct testing without a live provider.
        """
        from providers.openmeteo import compute_confidence_pct

        # 5. Propagate confidence onto every DataPoint of every segment
        for weather_item in weather_data:
            seg = weather_item.segment
            seg_start = seg.start_time if seg is not None else None
            seg_end = seg.end_time if seg is not None else None

            # 5a. Per-DataPoint enrichment when timeseries exists
            if weather_item.timeseries is not None:
                for dp in weather_item.timeseries.data:
                    dp_ts_naive = dp.ts.replace(tzinfo=None) if dp.ts.tzinfo else dp.ts
                    spread = spreads_naive.get(dp_ts_naive)
                    if spread is None:
                        continue
                    s_t, s_p = spread
                    dp.spread_t2m_k = s_t
                    dp.spread_precip_mm = s_p
                    if s_t is not None and s_p is not None:
                        dp_ts_utc = dp.ts if dp.ts.tzinfo else dp.ts.replace(tzinfo=timezone.utc)
                        lead_h = max(0.0, (dp_ts_utc - now_utc).total_seconds() / 3600.0)
                        dp.confidence_pct = compute_confidence_pct(s_t, s_p, lead_h)

                # 6a. confidence_pct_min from DataPoints (SegmentWeatherSummary not frozen)
                valid_conf = [
                    dp.confidence_pct
                    for dp in weather_item.timeseries.data
                    if dp.confidence_pct is not None
                ]
                if valid_conf:
                    weather_item.aggregated.confidence_pct_min = min(valid_conf)
                    continue

            # 5b/6b. Fallback: aggregate confidence directly from spreads within
            # the segment time window (when timeseries is missing or empty)
            if seg_start is None or seg_end is None:
                continue
            seg_start_naive = (
                seg_start.replace(tzinfo=None) if seg_start.tzinfo else seg_start
            )
            seg_end_naive = (
                seg_end.replace(tzinfo=None) if seg_end.tzinfo else seg_end
            )
            spread_confs: List[float] = []
            for ts_naive, (s_t, s_p) in spreads_naive.items():
                if ts_naive < seg_start_naive or ts_naive > seg_end_naive:
                    continue
                if s_t is None or s_p is None:
                    continue
                ts_utc = ts_naive.replace(tzinfo=timezone.utc)
                lead_h = max(0.0, (ts_utc - now_utc).total_seconds() / 3600.0)
                spread_confs.append(compute_confidence_pct(s_t, s_p, lead_h))
            if spread_confs:
                weather_item.aggregated.confidence_pct_min = min(spread_confs)

    def _build_stage_trend(
        self,
        trip,
        target_date: date,
        now_utc: datetime,
        tz=None,
        report_type: str = "evening",
    ):
        """
        Build trend rows for each future stage (v4.0 column layout).

        SPEC: docs/specs/modules/multi_day_trend.md v5.0

        Fix #1486: liefert ein ``TrendResult`` statt ``Optional[list[dict]]``.
        ``result.rows`` ist UNVERAENDERT der bisherige Rueckgabewert (Liste
        mit >= 1 Zeile oder ``None``) — der Thunder-Reuse-Pfad (#1275) und der
        Vorschau-Vergleich (ADR-0025/#1297) lesen genau dieses Feld weiter.
        ``result.state`` benennt zusaetzlich, WARUM der Ausblick entfaellt
        (vorher fuenf Ausstiege, alle mit demselben stummen ``None``).

        Issue #1727 S5b (ADR-0044/ADR-0051 Regel 3): ``now_utc`` ist
        PFLICHTPARAMETER ohne Default. Der Vorhersage-Horizont wird gegen den
        ORTSTAG der Tour gemessen (``trip_local_today``), nicht gegen den
        Servertag — ``stage.date`` ist ein Etappentag mit Ortstag-Semantik, ein
        Servertag daneben mischt zwei Tagesbegriffe. Und der Zeitpunkt kommt
        vom Aufrufer, weil zwischen dessen Zeitabfrage und diesem Aufruf ein
        Wetterabruf mit Retry-Backoff liegt: eine eigene Aufloesung koennte
        bereits den naechsten Ortstag tragen, waehrend ``target_date`` noch auf
        dem alten steht.
        """
        from app.models import OutlookState, TrendResult
        from providers.openmeteo import (
            OPENMETEO_MAX_FORECAST_DAYS,
            is_within_forecast_horizon,
        )
        from services.trip_day import trip_local_today
        from services.weather_metrics import aggregate_stage

        WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

        future_stages = trip.get_future_stages(target_date)
        if not future_stages:
            # Klasse A: normaler Tourabschluss — bewusst KEIN Log.
            return TrendResult(rows=None, state=OutlookState.NO_STAGES)

        trend = []
        # Fix #1486: Ausfallgruende sammeln. Kommt am Ende WENIGSTENS EINE
        # Zeile zustande, gilt FOUND (Bestandsverhalten `trend if trend`);
        # sonst gewinnt UNAVAILABLE vor BEYOND_HORIZON (Stoerung geht vor
        # Information).
        failures: set = set()
        horizon_days: Optional[int] = None
        today = trip_local_today(trip, now_utc)
        for stage in future_stages[:3]:
            if not is_within_forecast_horizon(stage.date, today):
                # Fix #1486: war logger.debug — im Betrieb unsichtbar.
                logger.warning(
                    "Stage %s (%s) beyond Open-Meteo forecast horizon (today+%d), skipping trend",
                    stage.id, stage.date, OPENMETEO_MAX_FORECAST_DAYS,
                )
                failures.add(OutlookState.BEYOND_HORIZON)
                horizon_days = OPENMETEO_MAX_FORECAST_DAYS
                continue
            try:
                segments = self._convert_trip_to_segments(trip, stage.date)
                if not segments:
                    # Fix #1486: bisher voellig stumm.
                    logger.warning(
                        "Stage %s (%s): kein Ausblick — keine Segmente aufloesbar",
                        stage.id, stage.date,
                    )
                    failures.add(OutlookState.UNAVAILABLE)
                    continue

                seg_weather = self._fetch_weather(segments)
                if not seg_weather:
                    # Fix #1486: bisher voellig stumm.
                    logger.warning(
                        "Stage %s (%s): kein Ausblick — keine Wetterdaten",
                        stage.id, stage.date,
                    )
                    failures.add(OutlookState.UNAVAILABLE)
                    continue

                # fix-911-visual-table AC-4: Ensemble-Confidence auch für die
                # Trend-/Ausblick-Etappen berechnen (Hauptpfad macht das in
                # _enrich_ensemble_for_trip; ohne diesen Schritt blieb
                # confidence_pct_min None → ACC-Spalte zeigte „–").
                self._enrich_ensemble_for_trip(trip, seg_weather)

                agg = aggregate_stage(seg_weather)

                # Epic #1301 B4: Zeilenbau in geteilten Baustein extrahiert
                # (build_outlook_row, Trip/Compare-Teilungs-Invariante).
                # note bleibt trip-eigen (kein Feld von build_outlook_row),
                # aus denselben Werten berechnet, die build_outlook_row intern
                # aus `agg` ableitet.
                from output.renderers.email.outlook import build_outlook_row

                _thunder_name = (
                    agg.thunder_level_max.name
                    if agg.thunder_level_max is not None else "NONE"
                )
                note = _trend_note(
                    _thunder_name,
                    float(agg.precip_sum_mm or 0.0),
                    int(agg.wind_max_kmh or 0),
                )

                _tz = tz if tz is not None else ZoneInfo("UTC")
                _flat_points = [
                    dp for sw in seg_weather if sw.timeseries is not None
                    for dp in sw.timeseries.data
                ]

                # Resolve per-metric sms_threshold from trip display config (AC-2)
                _sms_thr: dict = {}
                dc = getattr(trip, "display_config", None)
                if dc is not None:
                    for mc in dc.metrics:
                        if mc.sms_threshold is not None:
                            _sms_thr[mc.metric_id] = mc.sms_threshold

                # Issue #1653: konfiguriertes Tagesfenster durchreichen, damit
                # die Gewitter-Zelle des Ausblicks Tag und Nacht am selben
                # Fenster trennt wie die Gewitter-Vorschau (#1651).
                from app.day_window import resolve_configured_window

                _rc = getattr(trip, "report_config", None)
                _win_start, _win_end = resolve_configured_window(
                    getattr(_rc, "day_window_start_hour", None),
                    getattr(_rc, "day_window_end_hour", None),
                )
                row = build_outlook_row(
                    agg, _flat_points, WEEKDAYS_DE[stage.date.weekday()], _tz,
                    sms_thresholds=_sms_thr,
                    # #1720 S1: ungekollabierte Konfiguration durchreichen,
                    # nicht selbst aufloesen -- Renderer-Vokabular gehoert in
                    # die Ausgabeschicht (test_scheduler_has_no_output_imports).
                    trip_display_config=dc, report_type=report_type,
                    day_window_start_hour=_win_start,
                    day_window_end_hour=_win_end,
                )
                # Issue #1275: explicit calendar date so the thunder forecast
                # can reuse this row (matched by date, gap-safe) instead of
                # re-fetching the same stage. Additive — consumers read only
                # their known keys (format_trend_tokens).
                row["date"] = stage.date
                row["name"] = stage.name
                row["note"] = note

                trend.append(row)
            except Exception as e:
                logger.warning(f"Failed to build trend for stage {stage.id}: {e}")
                failures.add(OutlookState.UNAVAILABLE)
                continue

        if trend:
            return TrendResult(rows=trend, state=OutlookState.FOUND)
        if OutlookState.UNAVAILABLE in failures:
            return TrendResult(rows=None, state=OutlookState.UNAVAILABLE)
        if OutlookState.BEYOND_HORIZON in failures:
            return TrendResult(
                rows=None,
                state=OutlookState.BEYOND_HORIZON,
                horizon_days=horizon_days,
            )
        # Unerreichbar (future_stages ist hier nicht leer und jede Etappe
        # nimmt genau einen der Ausgaenge) — fail-soft auf Klasse A.
        return TrendResult(rows=None, state=OutlookState.NO_STAGES)

    def _build_thunder_forecast_from_trend_or_fetch(
        self,
        trip,
        target_date: date,
        now_utc: datetime,
        tz: Optional[ZoneInfo],
        multi_day_trend=None,
        night_weather=None,
    ) -> Optional[dict]:
        """Issue #1275: derive the +1/+2 thunder forecast from the SAME data as
        the E-Mail-Outlook table.

        Primary path — reuse the already-built ``multi_day_trend`` rows, matched
        by explicit calendar date (``row["date"] == target_date + offset``):
        NO extra weather fetch in the evening default, where the trend exists.

        Fallback — only for offsets NOT present in the trend (trend disabled,
        typically morning, or the stage is beyond the 3-row trend window): run
        the dedicated single-stage fetch + aggregation, fail-soft.

        Issue #1402: `tz` ist PFLICHTPARAMETER (kein `=None`-Default mehr) --
        beide Aufrufer (Versandpfad + Vorschau) übergeben immer eine echte,
        aus Koordinaten aufgeloeste Zone; Tests, die den Fail-soft-Pfad ohne
        aufloesbaren Ort pruefen, übergeben weiterhin bewusst `tz=None`.

        Issue #1498 (Fall 2): beide Bauwege klemmen auf das geteilte
        Tagesfenster (Default 04-19, pro Trip konfigurierbar) — vorher las
        die Vorschau den vollen Kalendertag 00-23 und behauptete damit
        Nachtstunden („ab 02:00"), fuer die die Nacht-Tabelle derselben
        Mail mit eigener Quelle (`night_weather`) zustaendig ist; die zwei
        Aussagen widersprachen sich an einer echt zugestellten Staging-Mail.
        Die Vorschau ist eine TAGES-Aussage und nutzt dasselbe Fenster wie
        SMS/Telegram/Fusszeile (ADR-0025).

        Issue #1651: ``night_weather`` (dieselbe Reihe, die auch die
        „Nacht am Ziel"-Tabelle speist) laesst den Satz ein Gewitter
        AUSSERHALB des Fensters zusaetzlich nennen -- angehaengt an ``text``,
        die Tages-Aussage (``level``/``hour``) bleibt geklemmt. Beide
        Aufrufer (Versand und Vorschau) reichen sie durch; genau das traegt
        die Paritaet aus AC-9/AC-11.

        Issue #1727 S5b: ``now_utc`` ist PFLICHTPARAMETER und wird
        unveraendert an ``_collect_future_stage_weather`` durchgereicht —
        diese Funktion trifft selbst KEINE Tagesentscheidung (kein eigener
        Fundort), sie haelt nur den Zeitpunkt auf demselben Weg wie der
        Rest des Briefing-Aufbaus.
        """
        from app.day_window import resolve_configured_window

        def _local(dt):
            # #1402: nie .astimezone(tz) auf einem naiven ts -- local_dt geht
            # ueber den zentralen Naiv-Guard (Hausnorm "naiv = UTC", #1345).
            return local_dt(dt, tz) if tz else dt

        _rc = getattr(trip, "report_config", None)
        win_start, win_end = resolve_configured_window(
            getattr(_rc, "day_window_start_hour", None),
            getattr(_rc, "day_window_end_hour", None),
        )
        forecast: dict = {}
        trend_by_date = {
            row["date"]: row
            for row in (multi_day_trend or [])
            if row.get("date") is not None
        }
        missing_dates: set = set()
        for offset, key in [(1, "+1"), (2, "+2")]:
            fc_date = target_date + timedelta(days=offset)
            row = trend_by_date.get(fc_date)
            if row is not None:
                forecast[key] = self._thunder_entry_from_trend_row(
                    row, fc_date, window_start=win_start, window_end=win_end,
                    # "+2" liegt jenseits der Nacht-Reihe (endet 06:00 morgen)
                    # -- dort gibt es keine Gegenquelle (Spec, Punkt 4).
                    night_hourly=(
                        _night_thunder_hours(night_weather, fc_date, _local)
                        if offset == 1 else None
                    ),
                )
            else:
                missing_dates.add(fc_date)

        if missing_dates:
            fetched = self._collect_future_stage_weather(
                trip, target_date, now_utc=now_utc, wanted_dates=missing_dates,
            )
            fetched_fc = (
                self._build_thunder_forecast(
                    fetched, target_date, tz=tz,
                    window_start=win_start, window_end=win_end,
                    night_weather=night_weather,
                )
                if fetched else None
            ) or {}
            for _offset, key in [(1, "+1"), (2, "+2")]:
                if key not in forecast and key in fetched_fc:
                    forecast[key] = fetched_fc[key]

        # Fix #1482: "Etappe existiert, aber keine Daten" von "gar keine Etappe"
        # unterscheiden. Nur der erste Fall ist eine Datenluecke und muss in der
        # Kurzform als "TH+:?" erscheinen statt als Entwarnung "TH+:-".
        # Der Marker liegt unter einem eigenen Schluessel, NICHT unter "+1"/"+2"
        # — die E-Mail-Renderer iterieren genau diese beiden und lesen dort
        # 'date'/'text'; ein Eintrag ohne diese Felder wuerde sie brechen.
        # Fail-soft wie der Rest dieser Methode: ohne Trip-Objekt (Vorschau-Pfad)
        # gibt es keine Etappenliste — dann bleibt es beim Bestandsverhalten.
        future_stages = (
            trip.get_future_stages(target_date) if trip is not None else []
        )
        stage_dates = {s.date for s in future_stages}
        gaps = {
            key
            for offset, key in [(1, "+1"), (2, "+2")]
            if key not in forecast and target_date + timedelta(days=offset) in stage_dates
        }
        if gaps:
            forecast["_gap_offsets"] = gaps

        return forecast if forecast else None

    def _thunder_entry_from_trend_row(
        self,
        row: dict,
        fc_date: date,
        *,
        window_start: Optional[int] = None,
        window_end: Optional[int] = None,
        night_hourly=None,
    ) -> dict:
        """Map one ``multi_day_trend`` row to a thunder_forecast entry (#1275).

        Level und "ab HH:MM" aus den ``row["hourly_thunder"]``-Proben
        (HourlyValue, bereits Ortszeit-Stunde) INNERHALB des Tagesfensters
        ``window_start``..``window_end`` (#1498 Fall 2; ``None`` -> Default
        4/19 via ``resolve_configured_window``). ``row["thunder"]``
        (Kalendertags-Maximum) dient nur noch als Fail-soft, wenn keine
        Stundenprobe im Fenster liegt. The return format matches
        ``_build_thunder_forecast`` so all downstream consumers
        (SMS/Telegram/E-Mail-Vorschau) stay unchanged.

        Issue #1402: der frühere ``tz``-Parameter wurde entfernt — er wurde
        nirgends im Funktionskörper gelesen (die Lokalisierung ist bereits
        VOR dieser Stelle in ``row["hourly_thunder"]`` erfolgt, s. o.). Ein
        ungenutzter ``tz=None``-Parameter täuschte Zeitzonen-Bezug vor, ohne
        ihn zu haben — irreführender als ein sichtbarer Rückfall.

        Issue #1474 Adversary F004: die vormals lokale ``{NONE:0,MED:1,HIGH:2}``-
        Kopie kannte ``LOW`` nicht -- Lookup warf ``KeyError`` und riss den
        Versandpfad mit. ``thunder_label_value()`` ist die geteilte Render-
        Skala (auch ``hourly_thunder`` selbst wird darüber gebaut, s.
        ``outlook.py::build_outlook_row``), also bleibt der Werte-Vergleich
        konsistent statt einer zweiten, driftenden Kopie.

        Issue #1651: ``night_hourly`` (optional, ``(Stunde, ThunderLevel)``-
        Paare aus ``night_weather``) laesst den Satz ein Gewitter AUSSERHALB
        des Fensters zusaetzlich NENNEN. Rein additiv -- ``level``/``hour``
        (die Tages-Aussage, aus der SMS und Ampel lesen) bleiben geklemmt,
        nur ``text`` waechst um den Halbsatz.
        """
        from app.day_window import (
            format_night_addendum, hour_in_window, night_addendum,
            resolve_configured_window,
        )
        from app.models import ThunderLevel
        from app.thunder_scale import (
            thunder_label_value, thunder_ordinal, thunder_signal_label,
            union_of_max_carriers,
        )

        win_start, win_end = resolve_configured_window(window_start, window_end)
        # Rueckabbildung Sample-Wert -> Level ueber die geteilte Render-Skala
        # selbst (#1474: keine Handkopie).
        _value_to_level = {thunder_label_value(lv): lv for lv in ThunderLevel}
        all_hourly = tuple(row.get("hourly_thunder") or ())
        windowed = [
            hv for hv in all_hourly
            if hour_in_window(int(hv.hour), win_start, win_end)
        ]
        if windowed:
            # Issue #1498 (Fall 2): Level aus den Stundenproben IM Fenster,
            # nicht aus dem Kalendertags-Maximum `row["thunder"]` — sonst
            # setzt ein reines Nachtgewitter (02:00) die Tages-Vorschau.
            # Sortierung ueber thunder_ordinal (ADR-0025, Entscheidung 3:
            # Skalen getrennt).
            level = max(
                (
                    _value_to_level.get(int(hv.value), ThunderLevel.NONE)
                    for hv in windowed
                ),
                key=thunder_ordinal,
            )
            # Issue #1680 S5b: die tragende Zutat der TAGES-Stufe, aus der
            # S5a-Traegerquelle `row["hourly_thunder_signals"]` und mit
            # DEMSELBEN Fensterfilter, der oben `windowed` erzeugt -- eine
            # zweite, unabhaengige Fensterauflösung waere genau die
            # Fehlerklasse aus #1653/#1498 (Stufe aus dem einen, Herkunft aus
            # dem anderen Fenster). Vorbild: `helpers.format_trend_tokens()`.
            carriers = union_of_max_carriers(
                (stufe, traeger)
                for stunde, stufe, traeger in (
                    row.get("hourly_thunder_signals") or ()
                )
                if hour_in_window(int(stunde), win_start, win_end)
            )
        else:
            # Fail-soft (Known Limitation): ohne Stundenproben im Fenster
            # keine Klemmung — Kalendertags-Maximum wie bisher, nie eine
            # blinde Entwarnung ueber unbeobachtete Stunden (#1331-Lehre).
            try:
                level = ThunderLevel[row.get("thunder") or "NONE"]
            except KeyError:
                level = ThunderLevel.NONE
            # Issue #1680 S5b (Spec AC-8): zu einer Stufe aus dem
            # Kalendertags-Maximum gibt es KEINE zum Fenster passende
            # Traegerquelle -- "keine Herkunft" ist hier die einzig ehrliche
            # Antwort, nicht die Herkunft irgendeiner unbeobachteten Stunde.
            carriers = None
        when = None
        hour = None
        if level != ThunderLevel.NONE:
            hours = [
                int(hv.hour)
                for hv in windowed
                if hv.value == thunder_label_value(level)
            ]
            if hours:
                hour = min(hours)
                when = f"{hour:02d}:00"
        if level == ThunderLevel.NONE:
            text = "Kein Gewitter erwartet"
        elif level == ThunderLevel.LOW:
            text = f"Leichtes Gewitter möglich ab {when}" if when else "Leichtes Gewitter möglich"
        elif level == ThunderLevel.MED:
            text = f"Gewitter möglich ab {when}" if when else "Gewitter möglich"
        else:
            text = (
                f"Starkes Gewitter erwartet ab {when}"
                if when else "Starkes Gewitter erwartet"
            )
        # Issue #1680 S5b: die Herkunft steht unmittelbar hinter der
        # Tagesaussage -- VOR dem Nacht-Halbsatz und (weil sie Teil von `text`
        # ist) auch vor dem Hagel-Zusatz, den erst der Renderer anhaengt.
        # Der Level-Check steht bewusst HIER, am Wirkort: "Kein Gewitter
        # erwartet" traegt nie eine Herkunft (Spec AC-6), und ohne
        # Traegerliste entsteht kein leerer ·-Trenner (Spec AC-11).
        if level != ThunderLevel.NONE and carriers:
            text += " · " + ", ".join(thunder_signal_label(n) for n in carriers)
        # Issue #1651: das Gewitter AUSSERHALB des Fensters wird angehaengt
        # genannt. Quelle sind dieselben, ohnehin vorliegenden Stundenproben
        # der Zeile -- fuer 00:00-06:00 des Folgetags schlaegt `night_hourly`
        # sie, weil dieselbe Reihe daneben als Nacht-Tabelle steht.
        own_hourly = [
            (int(hv.hour), _value_to_level.get(int(hv.value), ThunderLevel.NONE))
            for hv in all_hourly
        ]
        add = night_addendum(own_hourly, night_hourly, win_start, win_end)
        if add:
            text += format_night_addendum(*add)
        return {
            "date": fc_date.strftime("%d.%m.%Y"),
            "level": level,
            # ADR-0025, Entscheidung 4: die Stunde wird durchgereicht, damit der
            # SMS-Pfad sie nicht erfinden muss. None = keine Stunde bekannt.
            "hour": hour,
            "text": text,
            # Issue #1475 Nachbesserung (Punkt 4a): auch der PRIMAERE Pfad
            # (Trend-Zeile, Abend-Default) traegt das Hagel-Kennzeichen --
            # sonst waere der Wurzelfix im Regelbetrieb wirkungslos und nur
            # im Fallback-Fetch sichtbar. Quelle: build_outlook_row()["hail"].
            "hail": row.get("hail"),
        }

    def _collect_future_stage_weather(
        self,
        trip,
        target_date: date,
        now_utc: datetime,
        wanted_dates=None,
    ) -> List[SegmentWeatherData]:
        """Issue #1275: fetch weather for the actual next future stages,
        aggregated later across ALL their segments.

        Issue #1402: der frühere ``tz``-Parameter wurde entfernt — er wurde
        nirgends im Funktionskörper gelesen (diese Methode liefert rohe
        ``SegmentWeatherData``, keine formatierten Uhrzeiten; die
        Lokalisierung passiert erst nachgelagert). Ein ungenutzter
        ``tz=None``-Parameter täuschte Zeitzonen-Bezug vor, ohne ihn zu
        haben.

        Used only as the FALLBACK when the multi-day trend does not already
        cover a needed offset (see _build_thunder_forecast_from_trend_or_fetch).
        ``wanted_dates`` limits the fetch to exactly the uncovered calendar
        day(s); defaults to {+1, +2}.

        Reuses the exact fetch/enrich chain of `_build_stage_trend` so the
        thunder forecast and the E-Mail-Outlook table share ONE data source.
        Matching is by explicit calendar date (``stage.date == target_date +
        offset``), NOT by list position — a rest day (no stage on that
        calendar day) therefore yields an absent entry instead of silently
        borrowing a later stage's weather (see spec Known Limitations).

        Fail-soft: a per-stage fetch error is logged and the stage skipped, so
        the corresponding TH+ key is simply absent (SMS shows ``TH+:-``) —
        the report is never blocked.

        Issue #1727 S5b (ADR-0044/ADR-0051 Regel 3): ``now_utc`` ist
        PFLICHTPARAMETER, der Horizont wird gegen den ORTSTAG der Tour
        gemessen. Dieser Rueckfall liegt noch HINTER dem Trend-Bauweg, also
        noch spaeter im Wetterabruf — eine eigene Zeitaufloesung koennte hier
        bereits auf dem naechsten Ortstag stehen (s. ``_build_stage_trend``).
        """
        from providers.openmeteo import is_within_forecast_horizon
        from services.trip_day import trip_local_today

        # #1498 (Fall 2, Beifang): ohne Trip-Objekt (Vorschau-Pfad, s.
        # Fail-soft-Zusage oben und #1482-Guard im Aufrufer) gibt es keine
        # Etappenliste — vorher stuerzte genau dieser Fall mit
        # AttributeError, sobald der Trend einen Offset nicht abdeckte.
        # Issue #1727 S5b: Reihenfolge bewusst UNVERAENDERT — dieser Ausstieg
        # steht VOR der Zonen-Aufloesung, die ohne Trip nicht ginge.
        if trip is None:
            return []

        collected: List[SegmentWeatherData] = []
        today = trip_local_today(trip, now_utc)
        wanted = wanted_dates if wanted_dates is not None else {
            target_date + timedelta(days=1),
            target_date + timedelta(days=2),
        }
        for stage in trip.get_future_stages(target_date):
            if stage.date not in wanted:
                continue
            if not is_within_forecast_horizon(stage.date, today):
                continue
            try:
                segments = self._convert_trip_to_segments(trip, stage.date)
                if not segments:
                    continue
                seg_weather = self._fetch_weather(segments)
                if not seg_weather:
                    continue
                self._enrich_ensemble_for_trip(trip, seg_weather)
                collected.extend(seg_weather)
            except Exception as e:
                logger.warning(
                    f"Thunder-forecast fetch failed for stage {stage.id}: {e}"
                )
                continue
        return collected

    def _build_thunder_forecast(
        self,
        segments,
        target_date: date,
        tz: Optional[ZoneInfo],
        *,
        window_start: Optional[int] = None,
        window_end: Optional[int] = None,
        night_weather=None,
    ) -> Optional[dict]:
        """
        Build thunder forecast for +1 and +2 days.

        Issue #1275: aggregates the thunder level over ALL segments of the
        given future stage(s) — not just a single (today's-last) segment — so
        SMS/Telegram/E-Mail-Vorschau agree with the E-Mail-Outlook table (which
        uses ``aggregate_stage`` over the same future-stage segments). A data
        point counts for a calendar day by its LOCAL date (TZ-correct).

        Args:
            segments: A single ``SegmentWeatherData`` (back-compat) or a list
                of them — typically the segments of the actual next stage(s).
            target_date: Base date; entries are keyed by day offset (+1/+2).
            tz: Trip timezone for local-date/-hour resolution. Kann `None`
                sein (s. u.), ist aber PFLICHT anzugeben -- kein stiller
                Default mehr.

        Returns:
            Dict with "+1" and/or "+2" entries, or None if no thunder data.

        Issue #1402: `tz` ist jetzt PFLICHTPARAMETER (kein `=None`-Default
        mehr) -- alle Aufrufer (der interne Kettenaufruf aus
        `_build_thunder_forecast_from_trend_or_fetch` UND alle Tests)
        übergeben ihn bereits immer explizit, wenn auch teils bewusst als
        `None` (fail-soft-Pfade ohne aufloesbaren Ort). Ein WEGGELASSENER
        Aufruf faellt jetzt sofort mit `TypeError` auf, statt lautlos UTC zu
        rendern.

        Issue #1474 Adversary F005: die vormals lokale ``{NONE:0,MED:1,HIGH:2}``-
        Kopie kannte ``LOW`` nicht -- ``_ORD.get(lv, 0)`` gab LOW denselben
        Rang wie NONE (konnte gegen NONE verlieren) UND der Text-Zweig fiel
        mangels eigenem LOW-Fall in den ELSE-Zweig ("Starkes Gewitter
        erwartet"), das genaue Gegenteil der AC-6-Deckelung. ``thunder_ordinal()``
        ist die geteilte Sortier-Skala -- kein zweites, driftendes Ordinal.
        """
        from app.models import ThunderLevel
        from app.thunder_scale import thunder_ordinal, thunder_signal_label
        # Issue #1475 Nachbesserung (Punkt 4a): das Hagel-Aggregat kommt ueber
        # den kanonischen Basis-Metrik-Weg (``summarize_points`` ->
        # ``_compute_hail_flag`` -> ``hail_priority``) statt ueber einen
        # direkten Renderer-Import — der Scheduler darf per Architektur-Wache
        # (tests/unit/test_notification_service.py) nichts aus ``output``
        # ziehen ausser dem einen erlaubten geteilten Baustein.
        from services.weather_metrics import summarize_points

        # Back-compat: accept a single SegmentWeatherData. Duck-typed rather
        # than isinstance() to survive the app.models / src.app.models
        # dual-import split.
        if not isinstance(segments, (list, tuple)):
            segments = [segments]
        if not segments:
            return None

        def _local(dt):
            # Issue #1402: NIE .astimezone(tz) direkt auf einem naiven dp.ts
            # -- das deutet die Prozess-Zeitzone statt der Hausnorm "naiv =
            # UTC" (#1345). local_dt() geht ueber den zentralen Naiv-Guard.
            return local_dt(dt, tz) if tz else dt

        # Issue #1498 (Fall 2): nur Stunden im geteilten Tagesfenster zaehlen
        # — die Vorschau ist eine Tages-Aussage; Nachtstunden gehoeren der
        # Nacht-Tabelle. Liegt im Fenster gar kein Datenpunkt, entsteht KEIN
        # Eintrag — das greift in `_gap_offsets` (#1482) als ehrliche
        # Datenluecke ("?") statt einer blinden Entwarnung (#1331-Lehre).
        from app.day_window import (
            format_night_addendum, hour_in_window, night_addendum,
            resolve_configured_window,
        )
        win_start, win_end = resolve_configured_window(window_start, window_end)

        forecast = {}
        for offset, key in [(1, "+1"), (2, "+2")]:
            fc_date = target_date + timedelta(days=offset)
            # Issue #1651: der volle Kalendertag wird zuerst gesammelt, damit
            # die Stunden AUSSERHALB des Fensters fuer den Nacht-Zusatz zur
            # Verfuegung stehen. `thunder_dps` -- die Tages-Aussage -- bleibt
            # unveraendert auf das Fenster geklemmt (#1498 Fall 2).
            day_dps = [
                dp
                for sw in segments
                if sw.timeseries and sw.timeseries.data
                for dp in sw.timeseries.data
                if _local(dp.ts).date() == fc_date and dp.thunder_level
            ]
            thunder_dps = [
                dp for dp in day_dps
                if hour_in_window(_local(dp.ts).hour, win_start, win_end)
            ]
            if not thunder_dps:
                continue

            # F002: determine the peak level first, then the CHRONOLOGICALLY
            # earliest data point carrying it — never rely on segment/list
            # order (two segments both HIGH at different hours must yield the
            # earlier hour). Mirrors _thunder_entry_from_trend_row's min()-logic.
            level = max(
                (dp.thunder_level for dp in thunder_dps),
                key=thunder_ordinal,
            )
            earliest_ts = min(
                dp.ts for dp in thunder_dps if dp.thunder_level == level
            )
            earliest_local = _local(earliest_ts)
            when = earliest_local.strftime("%H:%M")
            if level == ThunderLevel.NONE:
                text = "Kein Gewitter erwartet"
            elif level == ThunderLevel.LOW:
                text = f"Leichtes Gewitter möglich ab {when}"
            elif level == ThunderLevel.MED:
                text = f"Gewitter möglich ab {when}"
            else:
                text = f"Starkes Gewitter erwartet ab {when}"
            # Issue #1680 S5b: der ohnehin vorhandene summarize_points()-Aufruf
            # (bisher nur fuer `hail_flag`, s.u.) wird in eine Variable
            # gehoben und zusaetzlich um die Traegerliste der Tagesstufe
            # gelesen. Beide Groessen entstehen ueber DIESELBE `thunder_dps`-
            # Menge, aus der auch `level` stammt -- kein zweiter Datenzugriff,
            # keine zweite Fensterfilterung.
            summary = summarize_points(thunder_dps)
            carriers = getattr(summary, "thunder_level_max_signals", None)
            # Herkunft unmittelbar hinter der Tagesaussage, VOR dem
            # Nacht-Halbsatz (und damit vor dem Hagel-Zusatz des Renderers).
            # Level-Check am Wirkort (Spec AC-6), Traeger-Guard gegen den
            # leeren ·-Trenner bei Alt-Fixturen ohne Traegerfeld (AC-11).
            if level != ThunderLevel.NONE and carriers:
                text += " · " + ", ".join(
                    thunder_signal_label(n) for n in carriers
                )
            # Issue #1651: Nacht-Zusatz, wortgleich zum Trend-Weg (eine
            # Wortlaut-Quelle: format_night_addendum). `night_weather` reicht
            # nur bis 06:00 des Folgetags und ist deshalb allein fuer "+1"
            # eine Gegenquelle; "+2" traegt ausschliesslich seine eigene Reihe.
            add = night_addendum(
                [(_local(dp.ts).hour, dp.thunder_level) for dp in day_dps],
                _night_thunder_hours(night_weather, fc_date, _local)
                if offset == 1 else None,
                win_start, win_end,
            )
            if add:
                text += format_night_addendum(*add)
            forecast[key] = {
                "date": fc_date.strftime("%d.%m.%Y"),
                "level": level,
                # ADR-0025, Entscheidung 4: echte Stunde durchreichen statt sie
                # im SMS-Renderer zu erfinden. Bei NONE gibt es keine Stunde.
                "hour": None if level == ThunderLevel.NONE else earliest_local.hour,
                "text": text,
                # Issue #1475 Nachbesserung (Punkt 4a): Hagel-Kennzeichen der
                # Vorschau — ueber DIESELBE thunder_dps-Menge, die auch
                # level/hour liefert (kein zweiter Datenzugriff). Beeinflusst
                # `level` an keiner Stelle (AC-10).
                "hail": getattr(summary, "hail_flag", None),
            }

        return forecast if forecast else None
