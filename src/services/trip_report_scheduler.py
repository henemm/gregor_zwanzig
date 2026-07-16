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
import time as time_module
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple
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
from services.day_comparison import DayComparison
from services.daylight_service import DaylightWindow
from services.notification_service import NotificationService, TripReportRequest
from services.user_tier import sms_allowed
from utils.geo import degrees_to_compass, haversine_km
from utils.timezone import tz_for_coords

if TYPE_CHECKING:
    from app.trip import Stage, Trip
    from services.report_config_resolver import ReportRenderOptions

# Issue #766: Inter-Mail-Delay beim Sammelversand, um Rate-Limits (452) zu
# vermeiden. Hinweis: `time` ist hier die datetime.time-Klasse — der echte
# Zeit-Modul wird als `time_module` importiert.
INTER_MAIL_DELAY_SECONDS = 2

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

        active_trips = self._get_active_trips(report_type)
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

    def send_reports_for_hour(self, current_hour: int) -> Tuple[int, int]:
        """
        Send reports for trips whose configured time matches current_hour.

        Called hourly by the scheduler. Checks both morning and evening
        times per trip against the current hour.

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
            current_hour: Current hour (0-23) in Europe/Vienna

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
            "route", self._user_id, current_hour, settings=self._settings,
        )

    def _collect_due_trips(self, current_hour: int) -> List[Tuple["Trip", str]]:
        """Sammelt alle (trip, report_type)-Paare, die zur gegebenen Stunde fällig sind.

        Issue #1207: Extrahiert aus `send_reports_for_hour` fuer Delegation
        durch `TripDispatchStrategy.collect_due()` -- Morgen- UND
        Abend-Fälligkeit werden VOR dem Versand gesammelt, damit das
        Inter-Mail-Delay über beide Slots hinweg greift.
        """
        due: List[Tuple["Trip", str]] = []
        for trip in self._get_active_trips("morning"):
            if self._get_morning_hour(trip) == current_hour:
                due.append((trip, "morning"))
        for trip in self._get_active_trips("evening"):
            if self._get_evening_hour(trip) == current_hour:
                due.append((trip, "evening"))
        return due

    def _process_pending_markers(self, current_hour: int, due_trip_ids_now: set) -> int:
        """Issue #1012 (b2): Verarbeitet offene Nachliefer-Marker VOR den
        regulären Slots. Für jeden Marker:
        - Trip regulär JETZT fällig (beliebiger report_type) -> Marker
          verfällt ersatzlos (AC-7), kein Re-Send hier (der reguläre Slot
          übernimmt).
        - Zuvor fehlende Segmente liefern jetzt Daten -> vollständiges
          Briefing mit Hinweis-Präfix nachliefern, Marker entfernen (AC-6).
        - Weiterhin fehlende Daten -> kein Re-Send, attempts += 1 (Lärmschutz).

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

            if trip is None or trip_id in due_trip_ids_now:
                self._remove_pending_marker(trip_id)
                continue

            target_date = date.fromisoformat(entry["date"])
            report_type = entry["report_type"]
            segments = self._convert_trip_to_segments(trip, target_date)
            if not segments:
                self._remove_pending_marker(trip_id)
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
    ) -> None:
        """Issue #1012 (b2): Schreibt/ersetzt den Nachliefer-Marker eines Trips.

        Read-Modify-Write auf data/users/<uid>/pending_briefings.json —
        ersetzt einen ggf. bestehenden Marker desselben Trips (keine Duplikate).
        """
        path = get_data_dir(self._user_id) / "pending_briefings.json"
        data = _load_pending_entries(path)
        entries = [e for e in data.get("entries", []) if e.get("trip_id") != trip.id]
        slot_hour = (
            self._get_morning_hour(trip) if report_type == "morning"
            else self._get_evening_hour(trip)
        )
        entries.append({
            "trip_id": trip.id,
            "report_type": report_type,
            "date": target_date.isoformat(),
            "slot_hour": slot_hour,
            "failed_segment_ids": failed_segment_ids,
            "attempts": 0,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        })
        data["entries"] = entries
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
        """Get configured morning hour for trip (default: 7)."""
        if trip.report_config and trip.report_config.morning_time:
            return trip.report_config.morning_time.hour
        return 7

    def _get_evening_hour(self, trip: "Trip") -> int:
        """Get configured evening hour for trip (default: 18)."""
        if trip.report_config and trip.report_config.evening_time:
            return trip.report_config.evening_time.hour
        return 18

    def _get_active_trips(self, report_type: str) -> List["Trip"]:
        """
        Get trips that are active for the given report type.

        - morning: Trips with a stage for today
        - evening: Trips with a stage for tomorrow

        Args:
            report_type: "morning" or "evening"

        Returns:
            List of active Trip objects
        """
        all_trips = load_all_trips(user_id=self._user_id)
        target_date = self._get_target_date(report_type)
        now_utc = datetime.now(timezone.utc)

        active = []
        for trip in all_trips:
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

        logger.debug(f"Active trips for {target_date}: {[t.id for t in active]}")
        return active

    def _get_target_date(self, report_type: str) -> date:
        """
        Get the target date for the report type.

        Args:
            report_type: "morning" or "evening"

        Returns:
            date object (today for morning, tomorrow for evening)
        """
        today = date.today()
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

    def select_test_stage(self, trip: "Trip", report_type: str) -> Optional["Stage"]:
        """Pick the stage to use for a TEST briefing when no stage matches today/tomorrow.

        Issue #768 — Test-Pfad-Fallback (NICHT der reguläre Scheduler):

        - Wählt die zeitlich **nächste kommende** Etappe mit ``date >= heute``
          (kleinstes Datum). ``trip.get_future_stages`` ist strikt ``>`` und schließt
          „heute" aus — daher hier eine eigene ``>=``-Auswahl.
        - Liegen **alle** Etappen in der Vergangenheit, fällt es auf die chronologisch
          **erste** (früheste) Etappe zurück.
        - Leere ``stages`` → ``None``.

        Args:
            trip: Trip object.
            report_type: "morning" or "evening" (nicht ausschlaggebend für die Wahl,
                Teil des Kontrakts für Aufrufer-Symmetrie).

        Returns:
            Die gewählte Stage oder None bei leeren stages.
        """
        if not trip.stages:
            return None
        today = date.today()
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
        return self._send_trip_report(trip, report_type, allow_test_fallback=True)

    def send_on_demand_report(self, trip: "Trip", report_type: str) -> bool:
        """
        Send an on-demand full briefing triggered by an inbound heute/morgen command.

        Issue #1007: Wiederverwendung des Test-Versand-Pfads (#768), aber OHNE
        Etappen-Fallback (kein Ausweichen auf eine andere Etappe, wenn am
        Zieltag keine Etappe liegt) und OHNE „[TEST]"-Präfix — stattdessen eine
        dezente „auf Anfrage"-Kennzeichnung im Mail-Body.

        Args:
            trip: Trip object
            report_type: "morning" (heute) or "evening" (morgen)

        Returns:
            Outcome string: "sent" | "no_stage" | "no_weather" | "no_channels"
            (Issue #1007 Adversary-Fix F001/F002 — Outcome-Unterscheidung statt
            eines bloßen bool, damit der Aufrufer "keine Etappe" von "keine
            Wetterdaten" und von "kein Kanal aktiv" unterscheiden kann).
        """
        if report_type not in ("morning", "evening"):
            raise ValueError(f"Invalid report_type: {report_type}")
        return self._send_trip_report_outcome(trip, report_type, on_demand=True)

    def _send_trip_report(
        self,
        trip: "Trip",
        report_type: str,
        allow_test_fallback: bool = False,
        on_demand: bool = False,
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
            trip, report_type, allow_test_fallback=allow_test_fallback, on_demand=on_demand,
        )
        return outcome in ("sent", "no_channels")

    def _send_trip_report_outcome(
        self,
        trip: "Trip",
        report_type: str,
        allow_test_fallback: bool = False,
        on_demand: bool = False,
        catchup_prefix: str | None = None,
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

        Returns:
            "no_stage" if no matching stage, "no_weather" if the weather
            fetch failed, "no_channels" if stage+weather were fine but no
            channel is configured for the trip, "sent" otherwise.

        Raises:
            Exception: If weather fetch or email send fails
        """
        logger.info(f"Generating {report_type} report for trip: {trip.name}")

        # 1. Convert trip to segments
        target_date = self._get_target_date(report_type)
        segments = self._convert_trip_to_segments(trip, target_date)

        # Issue #768: Test-Pfad-Fallback — wenn am regulären Zieldatum keine
        # Etappe liegt, weicht NUR der Test-Versand auf die nächste kommende
        # (bzw. früheste) Etappe aus. Der reguläre Scheduler (Default False)
        # bleibt unberührt (AC-7).
        if not segments and allow_test_fallback:
            fb = self.select_test_stage(trip, report_type)
            if fb is not None:
                target_date = fb.date
                segments = self._convert_trip_to_segments(trip, target_date)

        if not segments:
            logger.warning(f"No segments for trip {trip.id} on {target_date}")
            return "no_stage"

        logger.debug(f"Created {len(segments)} segments for {trip.id}")

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
        segment_weather = self._fetch_weather(segments)

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
                    from services.official_alerts import get_official_alerts_for_location
                    sw.official_alerts = get_official_alerts_for_location(*coord)
                except Exception:
                    logger.warning(
                        "trip_report_scheduler: official_alerts nicht ladbar",
                        exc_info=True,
                    )
                    sw.official_alerts = []

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

        # 4. Night weather (evening reports only)
        night_weather = None
        if report_type == "evening" and segment_weather:
            night_weather = self._fetch_night_weather(segment_weather[-1])

        # 6. Multi-day trend (configurable per report type — via Resolver, Issue #1208)
        #    Built BEFORE the thunder forecast (#1275): both must reflect the
        #    SAME actual future stage(s), never today's last segment.
        multi_day_trend = None
        if segment_weather and render_options.show_multi_day_trend:
            multi_day_trend = self._build_stage_trend(trip, target_date, tz=trip_tz)

        # 5. Thunder forecast (+1/+2 days) — Issue #1275
        #    Same data source as the outlook table, so SMS/Telegram/E-Mail-
        #    Vorschau agree with it. When the multi-day trend was already built
        #    (evening default) its rows are REUSED — no second weather fetch.
        #    Only offsets not covered by the trend fall back to a dedicated
        #    single-stage fetch (typically morning, where the trend is off).
        thunder_forecast = self._build_thunder_forecast_from_trend_or_fetch(
            trip, target_date, tz=trip_tz, multi_day_trend=multi_day_trend,
        )

        # 7. Usable daylight (F11) — via Resolver (Issue #1208)
        daylight_window = None
        if render_options.show_daylight:
            try:
                from services.daylight_service import compute_usable_daylight
                first_seg = segments[0]
                # Route max elevation from all waypoints in stage
                route_max_elev = stage_stats.get("max_elevation_m", first_seg.start_point.elevation_m) if stage_stats else first_seg.start_point.elevation_m
                # Collect all forecast data points for weather corrections
                all_forecast_data = []
                for sw in segment_weather:
                    if sw.timeseries and sw.timeseries.data:
                        all_forecast_data.extend(sw.timeseries.data)
                daylight_window = compute_usable_daylight(
                    lat=first_seg.start_point.lat,
                    lon=first_seg.start_point.lon,
                    target_date=target_date,
                    elevation_m=first_seg.start_point.elevation_m,
                    route_max_elevation_m=float(route_max_elev),
                    forecast_data=all_forecast_data,
                )
            except Exception as e:
                logger.warning(f"Daylight computation failed for {trip.id}: {e}")

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
            stability_result=stability_result,
            daylight_window=daylight_window,
            day_comparison=day_comparison,
            exposed_sections=exposed_sections,
            allow_test_fallback=allow_test_fallback,
            on_demand=on_demand,
            catchup_prefix=catchup_prefix,
            partial_outage_hint=partial_outage_hint,
            render_options=render_options,
        )
        result = self._notification_service.send_trip_report(request)
        errors = request.failed_segments

        # Issue #393: Briefing-Log für Cockpit-Kachel "Was geht heute raus".
        # Issue #1007 Adversary-Fix F001: bei explizit konfiguriertem "kein
        # Kanal aktiv" wird KEIN Log-Eintrag mit channels=[] geschrieben.
        if not result.no_channel_configured:
            self._append_briefing_log(trip.id, report_type, result.sent_channels)

        logger.info(f"Trip report sent: {trip.name} ({report_type})")

        # 9. Issue #1012: Teilausfall-Marker (Service-Error-Mail wurde bereits
        # vom NotificationService verschickt, weil failed_segments im Request
        # mitgeliefert wurden).
        if errors and not on_demand:
            self._write_pending_marker(
                trip, report_type, target_date,
                failed_segment_ids=[str(s.segment.segment_id) for s in errors],
            )

        # 10. Save weather snapshot for alert comparison
        # Issue #1007: On-Demand-Abruf (heute/morgen-Kommando) ist read-only
        # gegenüber Snapshot-/Alert-Zustand — Baseline bleibt das letzte
        # reguläre Briefing. Ein On-Demand-Abruf für nur EINEN Zieltag würde
        # sonst die kombinierte Momentaufnahme (heute+morgen) mit dem einen
        # Zieltag überschreiben und Alerts/Vortag-Vergleich für den jeweils
        # anderen Tag verfälschen.
        if not on_demand:
            try:
                from services.weather_snapshot import WeatherSnapshotService
                _snapshot_svc = WeatherSnapshotService(self._user_id)
                _snapshot_svc.save(trip.id, segment_weather, target_date)
                _snapshot_svc.save_dated(trip.id, target_date, segment_weather)
            except Exception as e:
                logger.warning(f"Failed to save weather snapshot for {trip.id}: {e}")

            # 10. Issue #816 (B): Briefing = neue, stabile Alert-Referenz → das
            # Melde-Gedächtnis des Trips zurücksetzen, damit der nächste Alert
            # wieder gegen das frische Briefing vergleicht. Issue #1007: nicht
            # bei On-Demand-Abruf (s.o.).
            self._reset_alert_state_after_briefing(trip.id)

        return "no_channels" if result.no_channel_configured else "sent"

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
        daylight_window: Optional[DaylightWindow],
        day_comparison: Optional[DayComparison],
        exposed_sections: list,
        allow_test_fallback: bool,
        on_demand: bool,
        catchup_prefix: str | None,
        partial_outage_hint: str | None = None,
        render_options: Optional["ReportRenderOptions"] = None,
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
            stability_result=stability_result,
            daylight_window=daylight_window,
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
            send_telegram=config is not None and config.send_telegram,
            test_prefix=allow_test_fallback,
            on_demand_prefix=on_demand,
            catchup_prefix=catchup_prefix,
            partial_outage_hint=partial_outage_hint,
            failed_segments=errors,
            on_demand=on_demand,
            render_options=render_options,
        )

    def _reset_alert_state_after_briefing(self, trip_id: str) -> None:
        """Issue #816 (B): Alert-Melde-Gedächtnis nach Briefing-Versand löschen."""
        try:
            from services.alert_state import AlertStateService
            AlertStateService(user_id=self._user_id).reset(trip_id)
        except Exception as e:
            logger.warning(f"Failed to reset alert_state for {trip_id}: {e}")

    def _append_briefing_log(self, trip_id: str, kind: str, channels: List[str]) -> None:
        """Issue #393: Hängt einen Briefing-Versand-Eintrag an briefing_log.json an.

        Wird von Go (GET /api/cockpit/status) read-only gelesen. Kein Bereinigen —
        das Frontend filtert auf "heute".
        """
        path = get_data_dir(self._user_id) / "briefing_log.json"
        data = json.loads(path.read_text()) if path.exists() else {"entries": []}
        data["entries"].append({
            "trip_id": trip_id,
            "kind": kind,
            "sent_at": datetime.now(tz=timezone.utc).isoformat(),
            "channels": channels,
        })
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

        Creates a temporary segment at the arrival point spanning two days
        so the provider returns data for both evening and next morning.

        Args:
            last_segment: Weather data for the last segment of the day

        Returns:
            NormalizedTimeseries covering arrival hour through 06:00 next day
        """
        from providers.base import get_provider
        from services.segment_weather import SegmentWeatherService

        seg = last_segment.segment
        arrival = seg.end_time
        next_morning = datetime.combine(
            arrival.date() + timedelta(days=1),
            datetime.min.time(),
            tzinfo=timezone.utc,
        ).replace(hour=6)

        # Create a temporary segment spanning arrival → 06:00 next day
        night_segment = TripSegment(
            segment_id=999,
            start_point=seg.end_point,
            end_point=seg.end_point,
            start_time=arrival,
            end_time=next_morning,
            duration_hours=(next_morning - arrival).total_seconds() / 3600,
            distance_km=0.0,
            ascent_m=0.0,
            descent_m=0.0,
        )

        try:
            provider = get_provider("openmeteo")
            service = SegmentWeatherService(provider)
            # Bug #288: night fetch is part of the per-stage data; ensemble
            # is added once per trip via _enrich_ensemble_for_trip().
            night_data = service.fetch_segment_weather(night_segment, enrich_ensemble=False)
            return night_data.timeseries
        except Exception as e:
            logger.warning(f"Failed to fetch night weather: {e}")
            # Fallback: use last segment's timeseries (evening hours only)
            if last_segment.timeseries and last_segment.timeseries.data:
                return last_segment.timeseries
            return None

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
        tz=None,
    ) -> Optional[list[dict]]:
        """
        Build trend rows for each future stage (v4.0 column layout).

        SPEC: docs/specs/modules/multi_day_trend.md v4.0
        """
        from providers.openmeteo import (
            OPENMETEO_MAX_FORECAST_DAYS,
            is_within_forecast_horizon,
        )
        from services.weather_metrics import aggregate_stage

        WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

        future_stages = trip.get_future_stages(target_date)
        if not future_stages:
            return None

        trend = []
        today = date.today()
        for stage in future_stages[:3]:
            if not is_within_forecast_horizon(stage.date, today):
                logger.debug(
                    "Stage %s (%s) beyond Open-Meteo forecast horizon (today+%d), skipping trend",
                    stage.id, stage.date, OPENMETEO_MAX_FORECAST_DAYS,
                )
                continue
            try:
                segments = self._convert_trip_to_segments(trip, stage.date)
                if not segments:
                    continue

                seg_weather = self._fetch_weather(segments)
                if not seg_weather:
                    continue

                # fix-911-visual-table AC-4: Ensemble-Confidence auch für die
                # Trend-/Ausblick-Etappen berechnen (Hauptpfad macht das in
                # _enrich_ensemble_for_trip; ohne diesen Schritt blieb
                # confidence_pct_min None → ACC-Spalte zeigte „–").
                self._enrich_ensemble_for_trip(trip, seg_weather)

                agg = aggregate_stage(seg_weather)

                temp_lo = int(agg.temp_min_c) if agg.temp_min_c is not None else None
                temp_hi = int(agg.temp_max_c) if agg.temp_max_c is not None else None
                precip_mm = float(agg.precip_sum_mm or 0.0)
                wind_kmh = int(agg.wind_max_kmh or 0)
                wind_dir = degrees_to_compass(agg.wind_direction_avg_deg)
                thunder_level = agg.thunder_level_max
                thunder = thunder_level.name if thunder_level is not None else "NONE"
                note = _trend_note(thunder, precip_mm, wind_kmh)

                # Issue #640: Build HourlyValue samples from timeseries for @-time tokens.
                # Uses local hours (Bug #398/#401: tz required). No extra API call.
                from src.output.tokens.dto import HourlyValue
                from app.models import ThunderLevel as _TL
                from utils.timezone import local_hour as _lh
                _tz = tz if tz is not None else __import__("zoneinfo").ZoneInfo("UTC")
                _hourly_precip: list = []
                _hourly_wind: list = []
                _hourly_gust: list = []
                _hourly_thunder: list = []
                _THUNDER_NUM = {_TL.NONE: 0, _TL.MED: 1, _TL.HIGH: 2}
                for sw in seg_weather:
                    if sw.timeseries is None:
                        continue
                    for dp in sw.timeseries.data:
                        lh = _lh(dp.ts, _tz)
                        if dp.precip_1h_mm is not None:
                            _hourly_precip.append(HourlyValue(hour=lh, value=dp.precip_1h_mm))
                        if dp.wind10m_kmh is not None:
                            _hourly_wind.append(HourlyValue(hour=lh, value=dp.wind10m_kmh))
                        if dp.gust_kmh is not None:
                            _hourly_gust.append(HourlyValue(hour=lh, value=dp.gust_kmh))
                        if dp.thunder_level is not None:
                            _hourly_thunder.append(HourlyValue(
                                hour=lh, value=float(_THUNDER_NUM.get(dp.thunder_level, 0))
                            ))

                # Resolve per-metric sms_threshold from trip display config (AC-2)
                _sms_thr: dict = {}
                dc = getattr(trip, "display_config", None)
                if dc is not None:
                    for mc in dc.metrics:
                        if mc.sms_threshold is not None:
                            _sms_thr[mc.metric_id] = mc.sms_threshold

                # Issue #721: confidence_pct from stage-level aggregate (min over segments)
                _conf_pct = (
                    round(agg.confidence_pct_min)
                    if agg.confidence_pct_min is not None else None
                )

                trend.append(dict(
                    weekday=WEEKDAYS_DE[stage.date.weekday()],
                    # Issue #1275: explicit calendar date so the thunder forecast
                    # can reuse this row (matched by date, gap-safe) instead of
                    # re-fetching the same stage. Additive — consumers read only
                    # their known keys (format_trend_tokens).
                    date=stage.date,
                    name=stage.name,
                    temp_lo=temp_lo,
                    temp_hi=temp_hi,
                    precip_mm=precip_mm,
                    wind_dir=wind_dir,
                    wind_kmh=wind_kmh,
                    thunder=thunder,
                    note=note,
                    hourly_precip=tuple(_hourly_precip),
                    hourly_wind=tuple(_hourly_wind),
                    hourly_gust=tuple(_hourly_gust),
                    hourly_thunder=tuple(_hourly_thunder),
                    **{k: v for k, v in {
                        "sms_threshold_precip": _sms_thr.get("precipitation"),
                        "sms_threshold_wind": _sms_thr.get("wind"),
                        "sms_threshold_gust": _sms_thr.get("gust"),
                        "sms_threshold_thunder": _sms_thr.get("thunder"),
                        "confidence_pct": _conf_pct,
                        # AC-13 (#911): Regenwahrscheinlichkeit für PR-Spalte in OutlookTable
                        "rain_probability_pct": agg.pop_max_pct,
                    }.items() if v is not None},
                ))
            except Exception as e:
                logger.warning(f"Failed to build trend for stage {stage.id}: {e}")
                continue

        return trend if trend else None

    def _build_thunder_forecast_from_trend_or_fetch(
        self,
        trip,
        target_date: date,
        tz=None,
        multi_day_trend=None,
    ) -> Optional[dict]:
        """Issue #1275: derive the +1/+2 thunder forecast from the SAME data as
        the E-Mail-Outlook table.

        Primary path — reuse the already-built ``multi_day_trend`` rows, matched
        by explicit calendar date (``row["date"] == target_date + offset``):
        NO extra weather fetch in the evening default, where the trend exists.

        Fallback — only for offsets NOT present in the trend (trend disabled,
        typically morning, or the stage is beyond the 3-row trend window): run
        the dedicated single-stage fetch + aggregation, fail-soft.
        """
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
                forecast[key] = self._thunder_entry_from_trend_row(row, fc_date, tz)
            else:
                missing_dates.add(fc_date)

        if missing_dates:
            fetched = self._collect_future_stage_weather(
                trip, target_date, tz=tz, wanted_dates=missing_dates,
            )
            fetched_fc = (
                self._build_thunder_forecast(fetched, target_date, tz=tz)
                if fetched else None
            ) or {}
            for _offset, key in [(1, "+1"), (2, "+2")]:
                if key not in forecast and key in fetched_fc:
                    forecast[key] = fetched_fc[key]

        return forecast if forecast else None

    def _thunder_entry_from_trend_row(
        self,
        row: dict,
        fc_date: date,
        tz=None,
    ) -> dict:
        """Map one ``multi_day_trend`` row to a thunder_forecast entry (#1275).

        Level from ``row["thunder"]`` (name string), earliest "ab HH:MM" from
        ``row["hourly_thunder"]`` (HourlyValue samples, already local hour). The
        return format matches ``_build_thunder_forecast`` so all downstream
        consumers (SMS/Telegram/E-Mail-Vorschau) stay unchanged.
        """
        from app.models import ThunderLevel

        try:
            level = ThunderLevel[row.get("thunder") or "NONE"]
        except KeyError:
            level = ThunderLevel.NONE
        _NUM = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}
        when = None
        if level != ThunderLevel.NONE:
            hours = [
                int(hv.hour)
                for hv in (row.get("hourly_thunder") or ())
                if hv.value == _NUM[level]
            ]
            if hours:
                when = f"{min(hours):02d}:00"
        if level == ThunderLevel.NONE:
            text = "Kein Gewitter erwartet"
        elif level == ThunderLevel.MED:
            text = f"Gewitter möglich ab {when}" if when else "Gewitter möglich"
        else:
            text = (
                f"Starkes Gewitter erwartet ab {when}"
                if when else "Starkes Gewitter erwartet"
            )
        return {
            "date": fc_date.strftime("%d.%m.%Y"),
            "level": level,
            "text": text,
        }

    def _collect_future_stage_weather(
        self,
        trip,
        target_date: date,
        tz=None,
        wanted_dates=None,
    ) -> List[SegmentWeatherData]:
        """Issue #1275: fetch weather for the actual next future stages,
        aggregated later across ALL their segments.

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
        """
        from providers.openmeteo import is_within_forecast_horizon

        collected: List[SegmentWeatherData] = []
        today = date.today()
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
        tz=None,
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
            tz: Trip timezone for local-date/-hour resolution.

        Returns:
            Dict with "+1" and/or "+2" entries, or None if no thunder data.
        """
        from app.models import ThunderLevel

        # Back-compat: accept a single SegmentWeatherData. Duck-typed rather
        # than isinstance() to survive the app.models / src.app.models
        # dual-import split.
        if not isinstance(segments, (list, tuple)):
            segments = [segments]
        if not segments:
            return None

        _ORD = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}

        def _local(dt):
            return dt.astimezone(tz) if tz else dt

        forecast = {}
        for offset, key in [(1, "+1"), (2, "+2")]:
            fc_date = target_date + timedelta(days=offset)
            thunder_dps = [
                dp
                for sw in segments
                if sw.timeseries and sw.timeseries.data
                for dp in sw.timeseries.data
                if _local(dp.ts).date() == fc_date and dp.thunder_level
            ]
            if not thunder_dps:
                continue

            # F002: determine the peak level first, then the CHRONOLOGICALLY
            # earliest data point carrying it — never rely on segment/list
            # order (two segments both HIGH at different hours must yield the
            # earlier hour). Mirrors _thunder_entry_from_trend_row's min()-logic.
            level = max(
                (dp.thunder_level for dp in thunder_dps),
                key=lambda lv: _ORD.get(lv, 0),
            )
            earliest_ts = min(
                dp.ts for dp in thunder_dps if dp.thunder_level == level
            )
            when = _local(earliest_ts).strftime("%H:%M")
            if level == ThunderLevel.NONE:
                text = "Kein Gewitter erwartet"
            elif level == ThunderLevel.MED:
                text = f"Gewitter möglich ab {when}"
            else:
                text = f"Starkes Gewitter erwartet ab {when}"
            forecast[key] = {
                "date": fc_date.strftime("%d.%m.%Y"),
                "level": level,
                "text": text,
            }

        return forecast if forecast else None
