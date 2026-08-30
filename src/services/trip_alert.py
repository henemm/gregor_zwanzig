"""
Trip alert service - sends immediate alerts on significant weather changes.

Feature 3.4: Alert bei Änderungen (Story 3)
Detects significant weather changes and sends alert emails with throttling.

SPEC: docs/specs/modules/trip_alert.md v2.0
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Iterable, List, Optional

from app.config import Settings
from app.models import SegmentWeatherData, WeatherChange
from services import alert_channel_threshold, alert_daily_limit, alert_input_capture, alert_log
from services.alert_briefing_anchor import record_alert_anchor_rejected
import services.alert_urgency as alert_urgency
from services.alert_gate import (
    HAZARD_CLASS_WET,
    _WET_METRICS,
    check_event_identity_gate,
    check_nowcast_gate,
    check_official_alert_gate,
    deviation_overtakes_cooldown,
    last_deviation_urgency,
    last_nowcast_precip_mm,
    radar_overtakes_cooldown,
    record_event_identity,
    record_nowcast_sent,
    resolve_hazard_class,
)
from services.deviation_alert_engine import DeviationAlertEngine
from services.notification_service import (
    NotificationResult,
    NotificationService,
    RadarAlertRequest,
)
from output.renderers.alert.segments import normalize_segment_id
from services.rain_extent import derive_rain_zones  # Issue #2051 S2a
from services.trip_segments import measured_segment_km  # Issue #2036
from services.point_weather import AlertEvaluationConfig, TripSegmentWeatherAdapter
from services.corridor_threshold import CorridorHit
from services.throttle_store import ThrottleStore
from services.trip_day import anchor_tz, trip_local_today
from services.user_tier import premium_sms_allowed, sms_allowed
from services.weather_change_detection import WeatherChangeDetectionService
from utils.timezone import (
    day_offset, format_reference_at, local_dt, local_fmt, to_utc, tz_for_coords,
)

if TYPE_CHECKING:
    from app.trip import Trip

logger = logging.getLogger("trip_alert")

# Gesamt-Zeitbudget je check_all_trips()-Lauf (Issue #1447): der
# Go-Scheduler wartet pro Nutzer maximal 120s (scheduler.go:82) und bricht
# danach die HTTP-Verbindung ab, ohne dass der Python-Lauf davon erfaehrt.
# 90s Reserve gegenueber diesen 120s, analog FETCH_DEADLINE_SECONDS in
# providers/meteofrance.py und providers/dwd.py.
ALERT_RUN_DEADLINE_SECONDS = 90.0

# Sperrzeit-Scope des Trip-Nowcast im geteilten `ThrottleStore` (#1213).
# Ausschliesslich mit Trip-Kennungen belegt — der Vergleichs-Nowcast bekam mit
# #1467 S3 deshalb einen eigenen Scope (`compare_radar`) statt diesen hier.
_RADAR_THROTTLE_SCOPE = "radar"

# Issue #1661: Hoechstalter des UNDATIERTEN Rueckfall-Ankers. Auffangnetz, das
# NUR greift, wenn die Datei kein lesbares `target_date` traegt — ein
# vorhandener, aber falscher Tag wird vom Datumsabgleich erledigt; ein
# Altersnetz wuerde dort ein inhaltlich falsches Datum durchwinken, solange es
# frisch geschrieben ist. Derselbe Zahlenwert wie beim Ortsvergleich
# (`compare_alert._MAX_ANCHOR_AGE`) und aus demselben Grund (Briefings laufen
# 1-2x/Tag) — geteilt wird der WERT, nicht der Code: die Trip-Seite hat mit
# `target_date` ein schaerferes Kriterium als der Ortsvergleich (Spec A2/A3).
_MAX_UNDATED_ANCHOR_AGE = timedelta(hours=26)

# Issue #1916 (ADR-0056): Alterungs-Ceiling fuer den opportunistischen
# Schreibtrigger (b) des rollierenden Alarm-Ankers. Kein vom PO bestaetigter
# Fixwert (Spec "Known Limitations"), deshalb benannte Konstante statt
# Hartverdrahtung. 4h ≈ 16 Check-Laeufe (15-Min-Takt, scheduler.go:145) —
# gross genug, um das Δ-Vergleichsfenster nicht auf einen einzelnen Lauf zu
# verkleinern (Trend-Erkennungs-Invariante, AC-9), klein genug, um das
# #1916-Symptom (~24h alte Basis nach gescheitertem Briefing) zuverlaessig
# zu kappen (AC-8).
_ALARM_ANCHOR_CEILING = timedelta(hours=4)

# Issue #2020: Ueberholungs-Faktor der Nowcast-Sperre gegen das Briefing.
# Analog RADAR_ONSET_THRESHOLD_MIN-Muster (#2009/ADR-0021) -- eine benannte
# Konstante statt Hartverdrahtung.
_BRIEFING_OVERTAKE_FACTOR = 2.0

# Issue #2020 F008 (PO-Entscheid 2026-08-21): absolute Relevanz-Untergrenze
# der Ueberholungsregel, in mm je Vergleichsstunde -- ersetzt die fruehere
# Spitzenraten-Untergrenze (max_rate_mm_h >= HEAVY_RAIN_THRESHOLD_MM_H).
# Zweck unveraendert (verhindert, dass Nieselregen alarmiert, nur weil die
# Ankuendigung noch kleiner war), aber jetzt an derselben Groesse wie der
# Faktor-Vergleich (window_precip_mm) gemessen statt an einer Spitzenrate:
# anhaltender, nicht-spitzer Regen (F008: 3,9 mm/h ueber 50 Min) uebertraf
# eine Ankuendigung deutlich, wurde aber von der alten Ratenschwelle
# ausgesperrt, obwohl er real die Ankuendigung ueberholte.
_OVERTAKE_MIN_ABSOLUTE_MM = 2.0

# Issue #1460 (P1a, loest #1444 S1 ab): der Wertebereich (`corridors[].notify`)
# ist KEIN Alarm-Ausloeser mehr -- eine absolute Grenze widerspricht ADR-0009
# (Alarme sind Abweichungs-Waechter). Der frueher hier gefuehrte
# `corridor:`-Schluesselraum im Melde-Gedaechtnis entfaellt damit ersatzlos;
# einziger Regler ist die Empfindlichkeitsstufe (s. ADR-0043).


def _as_aware_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Naive Zeitangaben als UTC lesen (Issue #1460, P4). Segment-Zeiten aus
    Alt-Schnappschuessen koennen tz-los sein; ein Vergleich naiv-vs-aware
    wuerde sonst mit TypeError den gesamten amtlichen Check kippen."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _change_to_capture_dict(change: WeatherChange) -> dict:
    """Rohe Aenderungswerte im ChangePayload-Schema (#1948, AC-1/AC-9)."""
    return {
        "metric": change.metric,
        "old_value": change.old_value,
        "new_value": change.new_value,
        "delta": change.delta,
        "threshold": change.threshold,
        "severity": change.severity.value,
        "direction": change.direction,
        "segment_id": change.segment_id,
    }


def _delta_event_window(
    changes: List[WeatherChange], weather: List[SegmentWeatherData],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Zeitintervall aus den Segmentfenstern der NASSEN Aenderungen (Issue
    #2050 S4c, Spec Implementation Details Punkt 2).

    `WeatherChange.occurred_at` ist in drei von vier Erzeugungspfaden `None`
    (Befund B der Kontext-Kartierung) und deshalb als Zeitbezug fuer den
    Δ-Zweig ungeeignet. Stattdessen werden `window_start`/`window_end` aus den
    Start-/Endzeitpunkten der betroffenen Trip-Segmente gebildet. Laesst sich
    fuer KEINE der uebergebenen Aenderungen ein Segment mit vollstaendiger
    Start-/Endzeit auffinden, bleiben beide Werte `None` -- `_times_overlap()`
    liefert dafuer fail-soft `False` (AC-9), kein Absturz."""
    segments = {
        normalize_segment_id(sw.segment.segment_id): sw.segment for sw in weather
    }
    starts: list[datetime] = []
    ends: list[datetime] = []
    for change in changes:
        segment = segments.get(normalize_segment_id(change.segment_id))
        if segment is None or segment.start_time is None or segment.end_time is None:
            continue
        starts.append(segment.start_time)
        ends.append(segment.end_time)
    if not starts or not ends:
        return None, None
    return min(starts), max(ends)


@dataclass(frozen=True)
class AlertCheckRunResult:
    """Ergebnis eines check_all_trips()-Laufs (Issue #1447 Teil A) statt des
    frueheren blossen int-Rueckgabewerts -- macht Teilerfolg (Deadline-
    Abbruch) explizit sichtbar statt ihn in einer einzelnen Zahl zu
    verstecken."""

    alerts_sent: int
    checked: int
    skipped: int
    duration_s: float
    hit_deadline: bool


def radar_alert_due(result: object, threshold_min: int) -> bool:
    """Return True when rain onset is within threshold_min minutes.

    Issue #2050 S2b: ein BEREITS LAUFENDES Ereignis loest ebenfalls aus. Bis
    hierher entschied allein `onset_minutes`, und endete der Regen innerhalb
    der laufenden Viertelstunde, gab es keinen Beginn mehr in der Zukunft --
    der Alarm fiel ersatzlos aus, obwohl es gerade regnete (Bruchstelle 1).
    """
    onset = getattr(result, "onset_minutes", None)
    if onset is not None and onset <= threshold_min:
        return True
    return bool(getattr(result, "already_running", False))


def _zonen_messwert(result):
    """Issue #2051 S2a (E4): ein Nowcast-Ergebnis OHNE verwertbare Frames ist
    fuer die Zonenbildung `None`, kein "trocken".

    `throttled` (Budget-Drosselung) und `data_unavailable` (Ausfall der
    Quelle) heissen beide "keine Beobachtung an diesem Punkt". Als trocken
    gewertet wuerden sie eine Nass-Zone TRENNEN und damit eine Aussage ueber
    das Wetter erfinden, die die Daten nicht hergeben.
    """
    if result is None:
        return None
    if getattr(result, "throttled", False) or getattr(result, "data_unavailable", False):
        return None
    return result


def _messluecken_felder(punkte, ergebnisse) -> dict:
    """Zahl und km-Lage der AUSGEFALLENEN Messpunkte der Ausdehnungs-Messung
    (Issue #2050 S4b, Anforderung E-1).

    Eine Luecke ist ein Punkt ohne verwertbares Ergebnis (`None`): geworfener
    Abruf, `throttled` und `data_unavailable` sind derselbe Fall in
    verschiedener Form (`_zonen_messwert`). `derive_rain_zones` uebergeht sie
    kommentarlos — ohne diese Buchfuehrung waere eine Ausdehnung aus vier von
    sechs Punkten nachtraeglich nicht von einer vollstaendig vermessenen zu
    unterscheiden.

    Das Feld entsteht IMMER, sobald die Mehrpunkt-Abfrage lief — auch mit
    leerer `gap_km`-Liste. Eine Absenz hiesse sonst zugleich "alles gemessen",
    "Alteintrag von vor dieser Scheibe" und "Ableitung gescheitert", also
    genau die Ununterscheidbarkeit, die diese Ableitung beseitigen soll.

    Die km-Lage stammt aus derselben Groesse, aus der auch die Zonen ihre
    Spanne bilden (`distance_from_start_km`), auf eine Nachkommastelle
    gerundet wie die gemessene Spanne im Text.
    """
    luecken = [
        round(punkt.distance_from_start_km, 1)
        for punkt, ergebnis in zip(punkte, ergebnisse) if ergebnis is None
    ]
    return {
        "measurement_gaps": {
            "points_total": len(ergebnisse),
            "points_measured": len(ergebnisse) - len(luecken),
            "gap_km": luecken,
        }
    }


def _radar_e1_fields(
    *, entity_id: str, result, now_utc: datetime, onset_dt: datetime,
    active, snapshot, punkte=None, zonen_ergebnisse=None,
) -> dict:
    """Die fuenf E-1-Groessen des Radar-Nowcast-Zweigs (Issue #2050 S6).

    EINE Ableitung fuer alle drei Protokollstellen dieses Zweigs
    (Briefing-Gate, Ereignis-Identitaet, Versand) — sonst stuende derselbe
    Vorfall je nach Ausgang mit verschiedenen Zeitangaben im Protokoll.

    `snapshot` ist zugleich die Vergleichsbasis, deren Ankuendigung das
    Briefing-Gate ueberhaupt erst begruendet; fehlt sie, bleibt `reference_at`
    weg statt erfunden zu werden. `source` ist der ROHE Quellen-Schluessel,
    NICHT `radar_svc.source_label(...)`: die Beschriftung ist ein zweites
    Vokabular fuer dieselbe Sache (Regel O1) und aendert sich ausserdem, was
    rueckwirkend die Bedeutung alter Eintraege verschoebe (Spec-Abschnitt
    "Korrektur: `source` ist immer der rohe Schluessel").

    Absicherung wie die Nachbarschritte derselben Schleife (Nowcast-Abruf,
    Unterdrueckungs-Protokoll): die Ableitung steht VOR dem Versand, ein
    Fehler hier duerfte deshalb nie den Alarm verhindern — und erst recht
    nicht die uebrigen Trips desselben Nutzers mitreissen (Muster
    `fix_1479`). Sie scheitert fail-soft zu "gar keine Zusatzfelder", aber
    NICHT still (AC-15): ohne die Meldung behauptete das Protokoll
    faelschlich "diese Groessen gab es hier nicht", wo in Wahrheit ein Defekt
    vorlag.
    """
    try:
        ende_dt = alert_log.nowcast_event_end_at(result, now_utc)
        felder = {
            "lead_time_minutes": result.onset_minutes,
            "event_at": onset_dt.isoformat(),
            "event_end_at": ende_dt.isoformat() if ende_dt else None,
            "measurement_point": {
                "segment_id": normalize_segment_id(active.segment_id),
                "km_from": active.start_point.distance_from_start_km,
                "km_to": active.end_point.distance_from_start_km,
            },
            "reference_at": (
                snapshot[0].fetched_at.isoformat() if snapshot else None
            ),
            "source": result.source,
        }
    except Exception as e:
        logger.warning(
            "alert_log: E-1-Groessen fuer entity_id=%s nicht ableitbar (%s) — "
            "der Alarm laeuft weiter, der Eintrag entsteht ohne diese Felder.",
            entity_id, e,
        )
        return {}
    # Issue #2050 S4b: EIGENER Auffang, bewusst NICHT der gemeinsame oben.
    # Der gibt bei einem Fehler `{}` zurueck — ein Fehler in dieser
    # NACHRANGIGEN Buchfuehrung risse damit alle sechs bestehenden E-1-Groessen
    # mit und loeschte Messpunkt, Ereigniszeit und Quelle aus dem Eintrag. Das
    # waere eine Regression gegen #2050 S6, also schlechter als der Stand vor
    # dieser Scheibe. Scheitert die Ableitung, fehlt genau EIN Feld (AC-9).
    if punkte is not None and zonen_ergebnisse is not None:
        try:
            felder.update(_messluecken_felder(punkte, zonen_ergebnisse))
        except Exception as e:
            logger.warning(
                "alert_log: Messluecken der Ausdehnung fuer entity_id=%s nicht "
                "ableitbar (%s) — der Alarm laeuft weiter, der Eintrag entsteht "
                "ohne dieses Feld, die uebrigen E-1-Groessen bleiben.",
                entity_id, e,
            )
    return felder


def _trip_telegram_style(trip: "Trip") -> str:
    """Issue #1260 S3: aufgelöster Telegram-Stil des Trips ("rich" Default).

    Wird an den Trip-Alarm-Dispatch (Abweichung + amtlich) explizit
    durchgereicht, damit die geteilten Dispatch-Methoden keine implizite
    Kopplung an ein Trip-Feld bekommen (Compare-Pfade bleiben beim Default).
    """
    rc = getattr(trip, "report_config", None)
    if rc is None:
        return "rich"
    return getattr(rc, "telegram_style", "rich") or "rich"


class TripAlertService:
    """
    Service for sending weather change alerts.

    Detects significant weather changes and sends immediate alerts
    with throttling to prevent spam.

    v2.0: Per-trip thresholds via from_trip_config(), file-based throttle persistence,
    check_all_trips() for scheduler integration.

    Example:
        >>> service = TripAlertService()
        >>> sent = service.check_and_send_alerts(trip, cached_weather)
        >>> print(f"Alert sent: {sent}")
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        throttle_hours: int = 2,
        user_id: str = "default",
        radar_service: Optional[object] = None,
        mail_sink: Optional[object] = None,
    ) -> None:
        """
        Initialize the alert service.

        Args:
            settings: App settings (default: load from config)
            throttle_hours: Minimum hours between alerts per trip (default: 2)
            user_id: User identifier for data scoping
            radar_service: Optional RadarNowcastService (DI seam; lazy default)
            mail_sink: Optional callable(subject, body) — captures mail calls in tests
                       (DI seam for AC-4/AC-6; replaces SMTP when set)
        """
        self._settings = settings if settings else Settings().with_user_profile(user_id)
        self._notification_service = NotificationService(self._settings, user_id)
        self._change_detector = WeatherChangeDetectionService()
        self._throttle_hours = throttle_hours
        self._user_id = user_id
        # Issue #1213: gemeinsamer ThrottleStore ersetzt das In-Memory-Dict
        # + die dateibasierte `alert_throttle.json`-Persistenz.
        self._throttle_store = ThrottleStore(user_id)
        # Radar nowcast service (DI seam)
        self._radar_service = radar_service
        # Mail-body capture seam for AC-4/AC-6 testing (replaces SMTP when set)
        self._mail_sink = mail_sink
        # Issue #1461 S3b-2a: Bruecke zwischen `_send_alert()` (bestimmt die
        # Kanal-Schwellen-Unterdrueckung) und `check_and_send_alerts()`
        # (protokolliert sie) -- wird bei jedem `_send_alert()`-Aufruf neu
        # gesetzt, kein dauerhafter Zustand.
        self._last_below_threshold_channels: set[str] = set()

    def _protokolliere_unterdrueckung(
        self, trip: "Trip", *, reason: str, gate_reason: Optional[str], **felder,
    ) -> None:
        """Unterdrueckungs-Protokoll fuer die bis #2050 S3b stillen Stellen des
        Trip-Pfads (Szenario 10, Luecken O3/E3): Aenderungsalarm (Ruhezeit,
        Sperrzeit, Tages-Obergrenze), Doppel-Alarm-Guard und amtliche Warnung.

        `reason` ist der AUSLOESER der Meldung, `gate_reason` der Sperrgrund —
        die beiden duerfen nicht verschmelzen. Das Kanal-Set wird HIER
        aufgeloest: die Funktion ist rein, und der Protokoll-Eintrag braucht
        die Kanaele, die der Nutzer fuer diesen Trip eingeschaltet hat.

        Absicherung je Trip, nicht um den Stapellauf: scheitert der
        Protokoll-Eintrag EINES Trips, verlieren sonst ALLE weiteren Trips
        dieses Nutzers ihren Alarm (Muster `fix_1479`)."""
        try:
            alert_log.append_suppressed_entry(
                self._user_id, entity_id=trip.id, entity_type="trip",
                reason=reason, gate_reason=gate_reason,
                effective_channels=self._effective_alert_channels(trip),
                **felder,
            )
        except Exception as e:
            logger.error(
                "Unterdrueckungs-Protokoll (%s) fuer Trip %s fehlgeschlagen "
                "(%s) — der Alarm blieb aus (Grund: %s), nur der "
                "Protokoll-Eintrag fehlt.", reason, trip.id, e, gate_reason,
            )

    def check_and_send_alerts(
        self,
        trip: "Trip",
        cached_weather: List[SegmentWeatherData],
        fresh_weather: Optional[List[SegmentWeatherData]] = None,
        official_notices: Optional[list] = None,
    ) -> bool:
        """
        Check for weather changes and send alert if significant.

        Args:
            trip: Trip to check
            cached_weather: Previously fetched weather data
            fresh_weather: Optional fresh weather (fetched if not provided)
            official_notices: Issue #1088 — bereits ermittelte neue/gestiegene
                amtliche Warnungen, die bei tatsächlichem Versand in dieselbe
                Nachricht gebündelt werden (kein zweiter Versand).

        Returns:
            True if alert was sent, False otherwise
        """
        # Issue #638 F001: Guard nur abbrechen wenn KEIN Kanal verfügbar ist.
        # Vorher: SMTP-only-Guard → Telegram-only-Nutzer bekam gar keinen Alert.
        if not self._settings.can_send_email() and not self._settings.can_send_telegram():
            logger.error("No alert channel configured (neither SMTP nor Telegram)")
            return False

        # 1a. Create change detector with per-trip priority (Issue #222 W1)
        # Priority: alert_rules > display_config > report_config > catalog defaults
        self._change_detector = self._select_change_detector(trip)

        # 1b. Check if alerts are disabled for this trip (legacy report_config path only)
        # If alert_rules has active rules, those are source-of-truth (disable via rule.enabled=False)
        # Issue #846: ein gesetztes (nicht-deaktiviertes) alert_preset zählt ebenso
        # als aktive Quelle und darf nicht vom report_config-Disable verschluckt werden.
        # Issue #946: metric_alert_levels ist die einzige Alert-Quelle und darf ebenso
        # nicht vom report_config-Disable verschluckt werden.
        has_preset = bool(
            trip.display_config
            and trip.display_config.alert_preset
            and trip.display_config.alert_preset != "deaktiviert"
        )
        has_metric_levels = bool(
            trip.display_config
            and getattr(trip.display_config, "metric_alert_levels", None)
        )
        # Issue #1460 (P1a): Wertebereiche zaehlen NICHT mehr als aktive
        # Alarmquelle -- eine Tour, deren einzige Einstellung ein Wertebereich
        # ist, gilt wieder als "keine aktive Alarmquelle" (Zustand vor #1444 S1).
        has_active_rules = (
            has_preset
            or has_metric_levels
            or any(r.enabled for r in (trip.alert_rules or []))
        )
        if (
            not has_active_rules
            and trip.report_config
            and not trip.report_config.alert_on_changes
        ):
            logger.debug(f"Alerts disabled for trip {trip.id}")
            return False

        # 1. QuietHours-Check (AC-4/5/6): Alert während stiller Stunden unterdrücken
        now_utc = datetime.now(timezone.utc)
        if self._is_quiet_hours(trip, now_utc):
            logger.debug(f"Alert suppressed: quiet hours active for trip {trip.id}")
            # Issue #2050 S3b (Szenario 10, AC-1): benannter Grund statt
            # stillem Abbruch.
            self._protokolliere_unterdrueckung(
                trip, reason=alert_log.REASON_FORECAST_CHANGE,
                gate_reason=alert_log.REASON_QUIET_HOURS,
            )
            return False

        # 1a2. Issue #1594: steht das geplante Briefing dieses Trips unmittelbar
        # bevor und wurde es noch nicht versucht, waere dieser Alarm eine
        # Doppel-Meldung — der Wetterstand kommt Minuten spaeter vollstaendig
        # im Briefing an. Zusaetzliche, rein lesende Stufe nach der Ruhezeit
        # und VOR dem Abruf; die bestehende Reihenfolge bleibt unangetastet
        # (Vereinheitlichung ist #1467 S4).
        if self._is_briefing_imminent(trip, now_utc):
            logger.debug(f"Alert suppressed: briefing imminent for trip {trip.id}")
            return False

        # 1b. Throttle-Check mit per-trip Cooldown (AC-2/3)
        # Issue #2050 S3c: das Gate BLEIBT, aber es bricht nicht mehr sofort
        # ab. Zu diesem Zeitpunkt ist die Schwere der Lage strukturell noch
        # unbekannt — sie entsteht erst aus dem Abruf. Der Aufrufer merkt sich
        # die offene Sperrzeit und entscheidet unten, mit der Dringlichkeit in
        # der Hand (dasselbe Caller-seitige Muster wie #2065/S3b im
        # Radar-Zweig).
        _sperrzeit_offen = self._is_throttled_with_cooldown(trip)
        if _sperrzeit_offen:
            logger.debug(f"Alert throttled for trip {trip.id}")

        # 1c. Issue #1070: Tages-Obergrenze nach Nutzerlevel (Free/Standard/Premium)
        # Issue #1555: reason="forecast_change" reserviert einen Anteil für NowCast.
        # Issue #1726: der Tageszaehler laeuft auf dem KALENDERTAG DER TOUR.
        # Issue #2050 S3c: bei offener Sperrzeit wird diese Stufe hier
        # UEBERSPRUNGEN und spaeter real nachgeholt — die feste Reihenfolge
        # (ADR-0021) bleibt damit gewahrt, und ein Sperrzeit-Durchbruch
        # ueberspringt das Budget nicht stillschweigend mit.
        if not _sperrzeit_offen and not alert_daily_limit.is_allowed(
            self._user_id, now_utc, anchor_tz(trip, now_utc), reason="forecast_change",
        ):
            logger.debug(f"Alert suppressed: daily limit reached for trip {trip.id}")
            # Issue #2050 S3b (Szenario 10, AC-3).
            self._protokolliere_unterdrueckung(
                trip, reason=alert_log.REASON_FORECAST_CHANGE,
                gate_reason=alert_log.REASON_DAILY_LIMIT,
            )
            return False

        # 2. Fetch fresh weather if not provided
        if fresh_weather is None:
            fresh_weather = self._fetch_fresh_weather(cached_weather)

        if not fresh_weather:
            logger.warning(f"No fresh weather data for trip {trip.id}")
            return False

        # 3./4./4b. Issue #1168 (F001-Fix): Detektor-Wahl (inkl. #961-
        # „Aktivieren-Lücke"-Backfill), Change-Detection, Filter significant und
        # Filter-gegen-Melde-Gedächtnis laufen jetzt VOLLSTÄNDIG über die
        # location-generische DeviationAlertEngine — kein `detector=`-Override
        # mehr, die Engine wählt den Detektor selbst aus `eval_config.display_config`
        # + `eval_config.metric_alert_levels` (identisch zu `_select_change_detector()`,
        # jetzt eine gemeinsame Quelle).
        from services.alert_state import AlertStateService
        state_svc = AlertStateService(user_id=self._user_id)
        alert_state = state_svc.load(trip.id)

        cached_points = TripSegmentWeatherAdapter.to_points(cached_weather)
        fresh_points = TripSegmentWeatherAdapter.to_points(fresh_weather)
        eval_config = AlertEvaluationConfig(
            cooldown_minutes=trip.alert_cooldown_minutes,
            quiet_from=trip.alert_quiet_from,
            quiet_to=trip.alert_quiet_to,
            metric_alert_levels=(
                getattr(trip.display_config, "metric_alert_levels", None)
                if trip.display_config else None
            ),
            channels=self._effective_alert_channels(trip),
            display_config=trip.display_config,
            zone=anchor_tz(trip, now_utc),
        )
        engine = DeviationAlertEngine()
        eval_result = engine.evaluate(
            cached=cached_points,
            fresh=fresh_points,
            config=eval_config,
            alert_state=alert_state,
        )
        to_report = list(eval_result.changes) if eval_result.triggered else []
        if not to_report:
            logger.debug(
                f"No changes for trip {trip.id}: {eval_result.suppressed_reason}"
            )
            # Issue #1987 (S1): der frueher hier stehende opportunistische
            # Ceiling-Schreibtrigger (ADR-0056 Trigger b) entfaellt ersatzlos.
            # Er lief in genau diesem Zweig — "kein Alarm gefeuert", also ohne
            # jede Zustellung — und schrieb damit einen Stand fort, den kein
            # Empfaenger je bekommen hat: exakt das, was diese Scheibe
            # verbietet. Die Schutzwirkung gegen eine veraltete
            # Vergleichsbasis geht nicht verloren, sie wandert in den
            # LESEPFAD (`_kanal_anker_kandidat`): ein gealterter Kanal-Merker
            # wird dort nicht mehr als Kandidat herangezogen, statt ihn hier
            # kuenstlich aufzufrischen.
            return False

        logger.info(
            f"Detected {len(to_report)} significant changes for trip {trip.id}"
        )

        # Issue #2050 S3c: die Dringlichkeit dieses Laufs entsteht GENAU EINMAL
        # und traegt drei Entscheidungen — Sperrzeit-Ueberholung,
        # Budget-Durchbruch und den `severity`-Eintrag im Alarm-Protokoll
        # (unten). Zwei unabhaengige Berechnungen desselben Werts koennten
        # still auseinanderlaufen.
        _urgency = alert_urgency.urgency_from_changes(to_report)
        _budget_durchbruch = False

        if _sperrzeit_offen:
            _basis_urgency = last_deviation_urgency(
                user_id=self._user_id, throttle_scope="trip",
                throttle_key=trip.id, throttle_store=self._throttle_store,
            )
            _ueberholt_sperrzeit = deviation_overtakes_cooldown(
                basis_urgency=_basis_urgency, urgency=_urgency,
            )
            # Beide Stufen in EINER Zeile, damit im Nachhinein nachvollziehbar
            # ist, GEGEN WAS entschieden wurde — fuer beide Ausgaenge.
            logger.info(
                "Alert: Sperrzeit-Ueberholung fuer Trip %s geprueft — "
                "Vergleichsbasis %s, Dringlichkeit dieses Laufs %s: %s",
                trip.id, _basis_urgency or "unbekannt", _urgency,
                "Durchbruch" if _ueberholt_sperrzeit else "Sperrzeit bleibt",
            )
            if not _ueberholt_sperrzeit:
                # Derselbe Protokolleintrag wie vor dieser Scheibe (S3b),
                # nur zeitlich hinter den Abruf verschoben — kein neuer Grund.
                self._protokolliere_unterdrueckung(
                    trip, reason=alert_log.REASON_FORECAST_CHANGE,
                    gate_reason=alert_log.REASON_COOLDOWN,
                )
                return False
            # Die Tages-Obergrenze wurde oben wegen der offenen Sperrzeit
            # uebersprungen — der Durchbruch darf sie nicht stillschweigend
            # mit-ueberspringen (Lehre aus #2065, `:1633-1654`). Rein lesend;
            # gebucht wird weiterhin erst nach der Zustellung.
            if not alert_daily_limit.is_allowed(
                self._user_id, now_utc, anchor_tz(trip, now_utc),
                reason="forecast_change",
            ):
                _budget_durchbruch = self._eskalation_bricht_budget(
                    trip, now_utc, _urgency,
                )
                if not _budget_durchbruch:
                    logger.debug(
                        "Alert suppressed (Tages-Obergrenze nach "
                        "Sperrzeit-Durchbruch) for trip %s", trip.id,
                    )
                    self._protokolliere_unterdrueckung(
                        trip, reason=alert_log.REASON_FORECAST_CHANGE,
                        gate_reason=alert_log.REASON_DAILY_LIMIT,
                    )
                    return False

        # Issue #1948 (S1, AC-1): roher Eingangs-Datensatz VOR dem Versand
        # -- capture_user_scoped() ist selbst fail-open.
        capture_id = alert_input_capture.capture_user_scoped(
            self._user_id, entity_type="trip", entity_id=trip.id,
            payload={"changes": [_change_to_capture_dict(c) for c in to_report]},
        )

        # Issue #1916 (AC-1..AC-4): Referenz-Zeitpunkt der TATSAECHLICH
        # verglichenen Vergleichsbasis (nicht der aktuelle Abrufzeitpunkt) —
        # sichtbar im Alarm-Footer statt des generischen Texts.
        reference_at = None
        anchor_fetched = _as_aware_utc(cached_weather[0].fetched_at) if cached_weather else None
        if anchor_fetched is not None:
            reference_at = format_reference_at(
                anchor_fetched,
                tz_for_coords(
                    cached_weather[0].segment.start_point.lat,
                    cached_weather[0].segment.start_point.lon,
                ),
            )

        # Issue #2050 S4c: der Δ-Zweig an der quellenuebergreifenden
        # Ereignis-Identitaet -- streng pruefen, grosszuegig registrieren
        # (Spec Implementation Details Punkt 4). Der Zeitbezug entsteht aus
        # den Segmentfenstern der NASSEN Aenderungen (`_delta_event_window`),
        # `point_at` bleibt fuer diesen Zweig immer `None` (Befund C) -- sonst
        # laese der Bestandscode den Eintrag faelschlich als `nowcast` ein.
        _wet_changes = [c for c in to_report if c.metric in _WET_METRICS]
        _delta_window_start, _delta_window_end = _delta_event_window(
            _wet_changes, fresh_weather,
        )
        _delta_segment_ids = sorted({
            sid for sid in (
                normalize_segment_id(c.segment_id) for c in _wet_changes
            ) if sid
        })
        # Streng (Entscheidung 1): die Klasse ist nur dann 'wet', wenn KEINE
        # Aenderung des Buendels ausserhalb des `wet`-Kanons liegt -- ein
        # einziger nicht-nasser Anteil (auch neben nassen Anteilen) macht die
        # Klasse `None` (AC-5). Nur dann wird die Ereignis-Identitaet
        # ueberhaupt gefragt (AC-6: kein `AlertStateService.load()` sonst).
        _delta_hazard_class = resolve_hazard_class(
            metrics=[c.metric for c in to_report],
        )
        if _delta_hazard_class is not None:
            _identity_gate = check_event_identity_gate(
                user_id=self._user_id, entity_id=trip.id,
                hazard_class=_delta_hazard_class, segment_ids=_delta_segment_ids,
                severity=_urgency, now=now_utc,
                window_start=_delta_window_start, window_end=_delta_window_end,
                source="deviation",
            )
            if not _identity_gate.allowed:
                self._protokolliere_unterdrueckung(
                    trip, reason=alert_log.REASON_FORECAST_CHANGE,
                    gate_reason=_identity_gate.reason,
                )
                return False

        # 5. Send alert; guard: only record throttle/log when at least one
        # configured channel was reachable (AC-1 symmetry with Telegram/Radar).
        notif_result = self._send_alert(
            trip, fresh_weather, to_report, official_notices=official_notices,
            reference_at=reference_at,
        )
        # Issue #1459: Alarm-Protokoll VOR dem Zustellbarkeits-Guard — die
        # Funktion entscheidet selbst, ob der Eintrag nach `entries` (mindestens
        # ein Kanal kam an, Ist-Verhalten) oder nach `not_delivered` geht (D4).
        # Issue #2050 S6 (E-1): Ereigniszeit und Messpunkt nur, wenn ALLE
        # gebuendelten Aenderungen dieses EINEN Eintrags denselben Wert tragen
        # (`unique_or_none`) -- sonst behauptete der Eintrag willkuerlich eines
        # von mehreren Segmenten. Vorwarnzeit und Ereignisende kennt dieser
        # Zweig strukturell nicht; Vergleichsbasis und Quelle stammen aus dem
        # ANKER, der im Erstlauf fehlen darf (dann Absenz statt Erfindung).
        _e1_occurred_at = alert_log.unique_or_none(c.occurred_at for c in to_report)
        _e1_segment_id = alert_log.unique_or_none(c.segment_id for c in to_report)
        alert_log.append_entry(
            self._user_id,
            entity_id=trip.id,
            entity_type="trip",
            changes_count=len(to_report),
            severity=alert_urgency.highest_urgency(
                # Issue #2050 S3c: DERSELBE Wert, der oben ueber Sperrzeit und
                # Budget entschieden hat — nicht neu gerechnet.
                _urgency,
                *[
                    alert_urgency.urgency_from_official_level(a.level)
                    for a, _segment_ids in (official_notices or [])
                ],
            ),
            metrics=alert_log.register_pairs_from_changes(to_report),
            reason=alert_log.REASON_FORECAST_CHANGE,
            effective_channels=eval_config.channels,
            sent_channels=notif_result.delivered_channels,
            reachable_channels=notif_result.sent_channels,
            below_threshold_channels=self._last_below_threshold_channels,
            blocked_reason_codes=notif_result.blocked_reason_codes,
            capture_id=capture_id,
            event_at=(
                _e1_occurred_at.isoformat() if _e1_occurred_at is not None else None
            ),
            measurement_point=(
                {"segment_id": _e1_segment_id} if _e1_segment_id is not None else None
            ),
            reference_at=(
                anchor_fetched.isoformat() if anchor_fetched is not None else None
            ),
            source=cached_weather[0].provider if cached_weather else None,
        )
        delivered = notif_result.sent
        if not delivered:
            logger.warning(
                f"Alert not deliverable on any effective channel for trip "
                f"{trip.id} — kein Throttle/Log"
            )
            return False

        # 6. Issue #816 (B): Melde-Gedächtnis fortschreiben (kein Snapshot-Write
        # mehr — die Briefing-Referenz bleibt stabil bis zum nächsten Briefing).
        now_iso = datetime.now(timezone.utc).isoformat()
        for change in to_report:
            key = f"{change.metric}:{change.segment_id}"
            alert_state[key] = {
                "last_reported_value": float(change.new_value),
                "reported_at": now_iso,
            }
        state_svc.save(trip.id, alert_state)

        # Issue #2050 S4c: grosszuegige Registrierung (Entscheidung 1) --
        # NACH erfolgreicher Zustellung, unabhaengig vom Ergebnis der Pruefung
        # oben (Eskalation, V1-Ausnahme, gemischtes Buendel kommen hier alle
        # an). Ist `_wet_changes` leer, gibt es nichts Nasses zu vermerken;
        # laesst sich kein Zeitfenster bilden, gibt es nichts Sinnvolles zu
        # schreiben (AC-6/AC-7/AC-9 konsistent fortgesetzt). ERST NACH dem
        # obigen `state_svc.save()`: der haelt noch die VOR dieser Scheibe
        # geladene `alert_state`-Momentaufnahme und wuerde einen zuvor
        # geschriebenen `event_identity:`-Schluessel sonst mit ihr
        # ueberschreiben (Read-Modify-Write-Kollision zweier Schreiber auf
        # demselben Zustand).
        if _wet_changes and _delta_window_start is not None and _delta_window_end is not None:
            record_event_identity(
                user_id=self._user_id, entity_id=trip.id,
                hazard_class=HAZARD_CLASS_WET, segment_ids=_delta_segment_ids,
                severity=_urgency, now=datetime.now(timezone.utc),
                window_start=_delta_window_start, window_end=_delta_window_end,
                source="deviation",
            )

        # 7. Update throttle (only on success) + persist
        # Issue #2050 S3c: die Sperrzeit wird MIT der Dringlichkeit dieses
        # Laufs gebucht — Selbstbremsung wie im Radar-Zweig: die naechste Lage
        # muss DIESEN Rang echt uebersteigen, eine gleichrangige Wiederholung
        # ueberholt die eigene, gerade gesetzte Basis nicht mehr.
        self._throttle_store.record(
            "trip", trip.id, datetime.now(timezone.utc), urgency=_urgency,
        )
        # Issue #1070: nur bei tatsaechlichem Versand zaehlen (F001-Symmetrie)
        # Issue #2050 S3c: die hoechste heute in dieser Zone ZUGESTELLTE Stufe
        # waechst bei JEDEM Versand mit (Vergleichsbasis der naechsten
        # Eskalationspruefung); der verbrauchte Durchbruch wird nur gebucht,
        # wenn er diesen Lauf auch getragen hat.
        alert_daily_limit.increment(
            self._user_id, now_utc, anchor_tz(trip, now_utc),
            urgency=_urgency,
            is_escalation_breakthrough=_budget_durchbruch,
        )

        # Issue #1916 Trigger (a): jeder TATSAECHLICH versendete Alarm
        # schreibt einen frischen rollierenden Anker (AC-6), unabhaengig von
        # einem vorherigen Briefing. Issue #1987 (S1): und zwar NUR fuer die
        # Kanaele, die ihn wirklich zugestellt bekommen haben — der einzige
        # verbleibende Schreibtrigger.
        self._write_rolling_alarm_anchor(
            trip.id, trip_local_today(trip, now_utc), fresh_weather,
            notif_result.delivered_channels,
        )

        return True

    def _select_change_detector(self, trip: "Trip") -> WeatherChangeDetectionService:
        """Dünner Wrapper — Detektor-Wahl inkl. #961-„Aktivieren-Lücke"-Backfill
        lebt jetzt in `DeviationAlertEngine._select_detector()` (Issue #1168
        F001-Fix, eine Quelle statt Duplikat). metric_alert_levels bleibt SINGLE
        source of truth (Issue #946); `trip.display_config` liefert den
        Backfill-Auszug. Weiterhin direkt testbar (Trip-Argument, siehe
        `test_issue_946_alert_architecture.py`/`test_bug_alert_metric_lifecycle_matrix.py`).
        """
        config = AlertEvaluationConfig(
            metric_alert_levels=(
                getattr(trip.display_config, "metric_alert_levels", None)
                if trip.display_config else None
            ),
            display_config=trip.display_config,
        )
        return DeviationAlertEngine._select_detector(config)

    def check_all_trips(self) -> AlertCheckRunResult:
        """
        Check all active trips for weather changes and send alerts.

        Called by scheduler every 30 minutes.
        Only checks trips that have at least one stage today or in the future.

        Issue #1447 (Teil A): begrenzt die Gesamtlaufzeit eines Laufs auf
        ALERT_RUN_DEADLINE_SECONDS — deutlich unter den 120s, die der
        Go-Scheduler pro Nutzer wartet, bevor er die HTTP-Verbindung abbricht.
        Wird die Obergrenze vor der naechsten Tour bereits ueberschritten,
        endet der Lauf sofort; bereits geprüfte Touren bleiben unveraendert,
        die verbleibenden zaehlen als uebersprungen.

        Returns:
            AlertCheckRunResult mit Anzahl versendeter Alarme, geprueften
            und uebersprungenen Touren, Gesamtlaufzeit und ob die
            Zeitobergrenze den Lauf beendet hat.
        """
        from app.loader import load_all_trips

        # Issue #1697: "heute" bestimmt sich je Trip aus der ORTSzeit der
        # Tour, nicht der Serveruhr (ADR-0044). now_utc bleibt fuer den
        # gesamten Lauf gleich, damit kein Trip eine andere "Jetzt"-Sekunde
        # sieht als der naechste.
        now_utc = datetime.now(timezone.utc)
        alerts_sent = 0
        checked = 0
        hit_deadline = False
        run_started_at = time.monotonic()
        deadline_at = run_started_at + ALERT_RUN_DEADLINE_SECONDS
        trips = list(load_all_trips(user_id=self._user_id))

        for trip in trips:
            if time.monotonic() > deadline_at:
                hit_deadline = True
                break
            checked += 1
            # Issue #1697: Ortstag dieses Trips — die Zone haengt vom Trip ab,
            # deshalb erst HIER (je Trip), nicht einmal vor der Schleife.
            today = trip_local_today(trip, now_utc)
            # Issue #222 W1: Trips with active alert_rules must be checked even if
            # report_config is missing or alert_on_changes=False — alert_rules is the
            # new source-of-truth (disable via rule.enabled=False).
            # Issue #846: ein gesetztes (nicht-deaktiviertes) alert_preset zählt
            # ebenso als aktive Quelle und muss geprüft werden.
            # Issue #946: metric_alert_levels ist die einzige Alert-Quelle — ein Trip
            # mit gesetzten Per-Metrik-Stufen MUSS geprüft werden, auch ohne preset,
            # alert_rules oder report_config (sonst still übersprungen → nie ein Alert).
            has_preset = bool(
                trip.display_config
                and trip.display_config.alert_preset
                and trip.display_config.alert_preset != "deaktiviert"
            )
            has_metric_levels = bool(
                trip.display_config
                and getattr(trip.display_config, "metric_alert_levels", None)
            )
            # Issue #1460 (P1a): Wertebereiche sind keine aktive Alarmquelle
            # mehr -- eine Tour, die nur Wertebereiche gesetzt hat, wird hier
            # wieder uebersprungen (Zustand vor #1444 S1).
            has_active_rules = (
                has_preset
                or has_metric_levels
                or any(r.enabled for r in (trip.alert_rules or []))
            )
            # Issue #1088 F001: der amtliche Alert-Trigger ist ein eigenständiger,
            # vom Wetter-Delta-Alert unabhängiger Auslöser (Default aktiv). Ein Trip
            # ohne aktive Wetter-Delta-Regel darf NICHT komplett übersprungen werden,
            # solange der amtliche Trigger nicht explizit deaktiviert ist — sonst
            # wird check_official_alert_triggers() unten nie erreicht.
            official_trigger_possible = trip.official_alert_triggers_enabled is not False
            if (
                not has_active_rules
                and (not trip.report_config or not trip.report_config.alert_on_changes)
                and not official_trigger_possible
            ):
                continue

            # Skip expired trips (all stages in the past). Issue #1250 S4
            # Fix-Loop F002: end_date ist None-sicher bei leeren Stages
            # (Editor erlaubt das) — ein Trip ohne Stages ist nicht
            # "abgelaufen", nur nicht dispatchbar, darf also nicht crashen.
            if trip.end_date is not None and trip.end_date < today:
                logger.debug(f"Skipping expired trip {trip.id} (ended {trip.end_date})")
                continue

            # Δ-Anker: hier ist ein Anker DESSELBEN Tages Pflicht (#1661).
            cached = self._get_cached_weather(
                trip, tagesgleicher_anker_noetig=True, now_utc=now_utc,
            )

            # Issue #1088: amtliche Warnungen zusätzlich zum Wetter-Delta prüfen —
            # fail-soft, darf den Zyklus für andere Trips nicht abbrechen.
            official_notices: list = []
            try:
                official_notices = self.check_official_alert_triggers(trip, now_utc=now_utc)
            except Exception as e:
                logger.error(f"Official alert trigger check failed for trip {trip.id}: {e}")

            # #1661 Spec-Korrektur 2026-08-10: ein fehlender oder verworfener
            # Δ-Anker legt NUR den Abweichungs-Alarm still. Stuende dieses Tor
            # wie frueher VOR dem amtlichen Check, wuerde ein Anker vom falschen
            # Tag auch die Unwetterwarnung verschlucken — genau in den Tagen vor
            # dem Aufbruch, in denen sie am meisten zaehlt.
            # Fail-soft wie der Zweig darunter: ein Fehler bei EINER Tour darf
            # den Lauf fuer alle folgenden nicht abbrechen.
            if not cached:
                if official_notices:
                    try:
                        if self._send_official_alert_only(trip, official_notices):
                            alerts_sent += 1
                    except Exception as e:
                        logger.error(f"Official alert send failed for trip {trip.id}: {e}")
                continue

            try:
                weather_sent = self.check_and_send_alerts(
                    trip, cached, official_notices=official_notices,
                )
                if weather_sent:
                    alerts_sent += 1
                elif official_notices:
                    # Kein Wetter-Delta-Alert gefeuert, aber neue/gestiegene amtliche
                    # Warnung(en) — eigenständiger Versand (PO-Entscheidung).
                    if self._send_official_alert_only(
                        trip, official_notices, segments=cached,
                    ):
                        alerts_sent += 1
            except Exception as e:
                logger.error(f"Alert check failed for trip {trip.id}: {e}")

        skipped = len(trips) - checked
        duration_s = time.monotonic() - run_started_at
        if hit_deadline:
            # Kein stilles Weglassen (ADR-0018 sinngemaess): der Abbruch
            # muss sichtbar sein, inklusive Obergrenze und geprueft/uebersprungen.
            logger.warning(
                f"check_all_trips: Zeitobergrenze ({ALERT_RUN_DEADLINE_SECONDS}s) "
                f"ueberschritten fuer user_id={self._user_id} — "
                f"checked={checked} skipped={skipped}"
            )
        logger.info(
            f"check_all_trips: Lauf beendet nach {duration_s:.3f}s fuer "
            f"user_id={self._user_id} (checked={checked} skipped={skipped} "
            f"alerts_sent={alerts_sent})"
        )
        return AlertCheckRunResult(
            alerts_sent=alerts_sent,
            checked=checked,
            skipped=skipped,
            duration_s=duration_s,
            hit_deadline=hit_deadline,
        )

    def _get_cached_weather(
        self, trip: "Trip", *, tagesgleicher_anker_noetig: bool,
        now_utc: Optional[datetime] = None,
    ) -> Optional[List[SegmentWeatherData]]:
        """
        Get cached weather data for a trip from the weather snapshot.

        Loads the dated snapshot for today first (written by morning briefing with
        target_date=today). Falls back to the undated snapshot only when no dated
        file exists yet (first-run / migration). This prevents alerts from using the
        evening briefing snapshot, which has target_date=tomorrow and would cause the
        alert to compare today's nowcast against tomorrow's stage. (Issue #823)

        Issue #1661: der undatierte Rueckfall wurde bis hierher UNGEPRUEFT
        zurueckgegeben, obwohl in der Datei steht, welchen Tag sie beschreibt.
        Er ist zudem kein Ausnahmefall, sondern der REGULAERE Nachtpfad —
        zwischen Mitternacht und dem ersten erfolgreichen Tageslauf greift
        `load_dated(trip, heute)` grundsaetzlich ins Leere. Faellt EIN
        Abend-Briefing aus, beschreibt der Rueckfall die ganze folgende Nacht
        und den Vormittag ueber den falschen Tag (Produktivfall 08.08.2026:
        ~16 h blinde Wache, ~28 stille Laeufe).

        Pruefung, Log und Eskalation sitzen bewusst HIER und nicht im
        Speicher-Layer (Pruefort = Wirkort, Spec A2): sie hat `trip` bereits
        als Parameter.

        WELCHER Aufrufer die Tages-Pruefung bekommt, entscheidet der
        PFLICHT-Parameter `tagesgleicher_anker_noetig` — kein Default, damit
        eine neue Aufrufstelle sich bewusst entscheiden MUSS statt still in die
        falsche Variante zu fallen (Spec-Korrektur 2026-08-10, Phase 6):

        * ``True`` — Abweichungs-Alarm (`check_all_trips` -> `check_and_send_alerts`).
          Der Δ-Vergleich braucht einen Referenzwert DESSELBEN Tages; ein Anker
          vom falschen Tag ist hier schlimmer als gar keiner.
        * ``False`` — amtliche Warnungen (`check_official_alert_triggers`).
          Dieser Pfad nutzt `cached` NICHT als Δ-Vergleichspunkt, sondern nur
          als Routen-Geometrie mit absoluten Zeiten, und ueberspringt vergangene
          Etappen bereits EINZELN (`end_time < now_utc: continue`). Er ist gegen
          einen veralteten Anker also selbst abgesichert und prueft bewusst die
          gesamte Restroute mit Tagen Vorlauf (#1460 P4). Wuerde die
          Tages-Pruefung auch hier greifen, verstummten amtliche Warnungen fuer
          bereits gebriefte, aber noch nicht gestartete Touren (deren undatierter
          Anker traegt `target_date = Starttag`) — schwerer als der behobene
          Schaden. Zwei Anforderungen, zwei Pruefungen.

        Verwerfen heisst genau: `None` zurueckgeben (Spec A4). Weder
        `alert_state` noch Cooldown werden angefasst, der Anker wird NICHT neu
        geschrieben — sonst wuerde aus zeitweiliger Unterdrueckung Dauerstille
        (Lehre `fix_1584c` AC-7).

        Args:
            trip: Trip to get cached weather for
            tagesgleicher_anker_noetig: True nur fuer den Abweichungs-Alarm.
            now_utc: Issue #1697 — "Jetzt" fuer die Ortstag-Aufloesung
                (`trip_local_today`). Optional mit Default auf die echte
                Wanduhr: anders als `tagesgleicher_anker_noetig` ist das
                eine reine "wie spaet ist es"-Frage, kein Verhaltensschalter
                (Begruendung: Spec-Abschnitt "Bewusste Abweichung vom
                'kein Default'-Muster").

        Returns:
            Cached weather data or None if not available/not trustworthy
        """
        try:
            from services.weather_snapshot import WeatherSnapshotService

            svc = WeatherSnapshotService(user_id=self._user_id)
            today = trip_local_today(trip, now_utc or datetime.now(timezone.utc))
            dated = svc.load_dated(trip.id, today)
            if dated is not None:
                return dated

            # Issue #1916 (ADR-0056): rollierender Alarm-Anker als ZWEITE
            # Quelle, VOR dem alten undatierten Rueckfall (Prioritaet:
            # Briefing-Anker > rollierender Anker > undatierter Rueckfall,
            # Spec "Anker-Prioritaetskette"). Unterliegt derselben
            # #823-Tagesgrenze wie der Briefing-Anker (AC-10) — ein Anker vom
            # falschen Tag wird verworfen, NICHT zurueckgegeben; die Funktion
            # faellt dann auf den bestehenden undatierten Rueckfall weiter
            # unten zurueck.
            # Issue #1987 (S1): der Anker wird je Kanal gefuehrt, die Auswahl
            # deshalb je Kanal aufgeloest und danach zu EINEM Stand
            # zusammengefuehrt (s. `_rollierender_anker_kandidat`).
            kanaele = self._effective_alert_channels(trip)
            if not tagesgleicher_anker_noetig:
                # Amtliche Warnungen brauchen aus dem Anker NUR die
                # Routen-Geometrie (s. Docstring) — die ist in jedem
                # Kanal-Merker dieselbe. Erster gefundener genuegt, keine
                # Tages- oder Alterspruefung (unveraendertes Verhalten).
                for channel in sorted(kanaele):
                    rolling = svc.load_alarm_anchor(trip.id, channel)
                    if rolling is not None:
                        return rolling
            else:
                rolling = self._rollierender_anker_kandidat(svc, trip, today, kanaele)
                if rolling is not None:
                    return rolling

            # Fallback: undated snapshot (may be stale after evening briefing)
            undated = svc.load(trip.id)
            anchor_date = (
                svc.load_target_date(trip.id)
                if undated and tagesgleicher_anker_noetig
                else None
            )
        except Exception as e:
            logger.debug(f"No cached weather for trip {trip.id}: {e}")
            return None

        # AC-13/AC-14 gelten fuer BEIDE Aufrufer: "gar kein Anker" laesst auch
        # die Geometrie-Auswertung leerlaufen.
        if not undated:
            self._report_missing_anchor(trip, today)
            return None
        if not tagesgleicher_anker_noetig:
            # Amtliche Warnungen: Geometrie genuegt, s. Docstring.
            return undated
        # Issue #1699: HERKUNFT vor Datum. Ein Snapshot aus einer reinen
        # Abfrage (`glance` u.a., `trip_command_processor`) traegt
        # `target_date = heute` und bestuende die #1661-Pruefung anstandslos —
        # obwohl ihm nie ein Briefing zugrunde lag: der Vergleichspunkt waere
        # nicht verschoben, sondern ERFUNDEN (ADR-0009).
        # Diese Pruefung sitzt bewusst NACH dem amtlichen Ausstieg direkt
        # darueber: fuer amtliche Warnungen liefert derselbe Snapshot nur die
        # Geometrie und ist einwandfrei. Stuende sie davor, verstummten
        # amtliche Warnungen (#1701) — die Gegenrichtung dieses Fixes.
        if not svc.load_briefing_backed(trip.id):
            reason = "not_briefing_backed"
            detail = (
                "stammt aus einer reinen Abfrage, nicht aus einem Briefing "
                "(briefing_backed=false)"
            )
        elif anchor_date == today:
            return undated
        elif anchor_date is None:
            # Altersnetz (A3): NUR bei fehlendem/unlesbarem Datum. Ein fehlender
            # Schreibzeitpunkt ist ebenso wenig vertrauenswuerdig wie ein zu
            # alter — beides taugt nicht als Vergleichspunkt (ADR-0009).
            fetched_at = _as_aware_utc(undated[0].fetched_at)
            age = (datetime.now(timezone.utc) - fetched_at) if fetched_at else None
            if age is not None and age <= _MAX_UNDATED_ANCHOR_AGE:
                return undated
            reason = "too_old"
            detail = (
                f"ohne lesbares target_date und {age.total_seconds() / 3600:.1f} h alt "
                f"(Grenze {_MAX_UNDATED_ANCHOR_AGE.total_seconds() / 3600:.0f} h)"
                if age is not None else "ohne lesbares target_date und ohne Zeitstempel"
            )
        else:
            reason = "wrong_day"
            detail = (
                f"falscher Tag: target_date={anchor_date.isoformat()}, "
                f"heute ist {today.isoformat()}"
            )

        logger.warning(
            "Alarm-Anker fuer Trip %s verworfen (%s) — %s. Kein Abweichungsalarm "
            "bis zum naechsten Briefing-Versand.", trip.id, reason, detail,
        )
        record_alert_anchor_rejected(
            user_id=self._user_id, entity_id=trip.id, reason=reason,
        )
        return None

    def _kanal_anker_kandidat(
        self, svc, trip_id: str, today: date, channel: str,
    ) -> Optional[tuple[datetime, List[SegmentWeatherData]]]:
        """Der GUELTIGE rollierende Merker eines Kanals mit seinem Alter —
        oder `None` (Issue #1987, AC-4/AC-7/AC-8).

        Drei Ausschlussgruende, alle rein LESEND (kein Schreibeffekt, anders
        als der entfallene Trigger b):

        * kein eigener Merker und keine kanallose Altdatei (AC-7),
        * `target_date` ungleich heute — die #823/#1916-Tagesgrenze gilt je
          Kanal, nicht global (AC-8),
        * aelter als `_ALARM_ANCHOR_CEILING` (AC-4).

        Ausgeschlossen heisst IMMER: dieser Kanal faellt auf den
        Tier-1-Briefing-Anker zurueck — nie auf den Merker eines ANDEREN
        Kanals. Das waere eine Vergleichsbasis, die dieser Empfaenger nie
        erhalten hat (Kontaminationsverbot).
        """
        merker = svc.load_alarm_anchor(trip_id, channel)
        if merker is None:
            return None
        if svc.alarm_anchor_target_date(trip_id, channel) != today:
            logger.debug(
                "Rollierender Alarm-Anker fuer Trip %s (%s) verworfen "
                "(falscher Tag).", trip_id, channel,
            )
            return None
        fetched_at = _as_aware_utc(merker[0].fetched_at)
        if fetched_at is None:
            return None
        alter = datetime.now(timezone.utc) - fetched_at
        if alter > _ALARM_ANCHOR_CEILING:
            logger.debug(
                "Rollierender Alarm-Anker fuer Trip %s (%s) verworfen "
                "(%.1f h alt, Grenze %.0f h).", trip_id, channel,
                alter.total_seconds() / 3600,
                _ALARM_ANCHOR_CEILING.total_seconds() / 3600,
            )
            return None
        return fetched_at, merker

    def _rollierender_anker_kandidat(
        self, svc, trip: "Trip", today: date, channels: set,
    ) -> Optional[List[SegmentWeatherData]]:
        """Die EINE gemeinsame Vergleichsbasis aus den Kanal-Kandidaten
        (Issue #1987, AC-11) — oder `None` fuer den Tier-1-Rueckfall.

        Die Ausloese-Entscheidung bleibt EIN gemeinsamer
        `DeviationAlertEngine.evaluate()`-Lauf (E2, ADR-0021) und braucht
        deshalb genau EINEN `cached`-Stand. Gewaehlt wird der AELTESTE
        gueltige Kandidat: nur so geht keinem Kanal eine Aenderung verloren,
        die er noch nicht kennt. Ein bereits aktuellerer Kanal bekommt
        hoechstens eine Wiederholung im Vergleich — davor schuetzt das
        Melde-Gedaechtnis (`alert_state`, ADR-0056 AC-12).

        `channels` ist das ROHE `effective_channels` ohne
        `split_by_threshold()`: der Schwellenfilter braucht die
        Dringlichkeitsstufe, die erst NACH der Change-Detection feststeht —
        hier waere sie nicht berechenbar (Spec, "Klarstellung zum
        Schwellenfilter im Lesepfad").

        Hat auch nur EIN Kanal keinen gueltigen eigenen Merker, faellt die
        Auswahl auf den Tier-1-Briefing-Anker durch (`None`): dieser Kanal
        kennt den Tier-1-Stand als letzten, und der ist auf diesem Pfad
        immer der aeltere — lief naemlich ein Briefing, hat bereits
        `load_dated()` weiter oben zurueckgegeben und diese Methode wird gar
        nicht erreicht.
        """
        if not channels:
            return None
        kandidaten: List[tuple[datetime, List[SegmentWeatherData]]] = []
        for channel in sorted(channels):
            kandidat = self._kanal_anker_kandidat(svc, trip.id, today, channel)
            if kandidat is None:
                return None
            kandidaten.append(kandidat)
        return min(kandidaten, key=lambda paar: paar[0])[1]

    def _report_missing_anchor(self, trip: "Trip", today: date) -> None:
        """Issue #1661 (Teil C, C2): „gar kein Anker" ist zwei verschiedene Dinge.

        Bei einer Tour, deren Laufzeitraum noch nicht begonnen hat, ist das der
        harmlose Normalfall (es lief schlicht noch kein Briefing) — dort nur
        eine DEBUG-Zeile, KEIN Diagnose-Eintrag, sonst erzeugte jede geplante
        Tour taeglich Dauerrauschen (#1199-Muster).

        Laeuft die Tour dagegen bereits, ist die Wache komplett blind, und
        genau das soll auffallen: WARNUNG UND Diagnose-Eintrag.
        """
        laeuft = (
            trip.start_date is not None and trip.end_date is not None
            and trip.start_date <= today <= trip.end_date
        )
        if not laeuft:
            logger.debug(
                "Kein Alarm-Anker fuer Trip %s — Laufzeitraum %s bis %s hat noch "
                "nicht begonnen bzw. ist unbekannt; das ist der Normalfall vor "
                "dem ersten Briefing.", trip.id, trip.start_date, trip.end_date,
            )
            return
        logger.warning(
            "Kein Alarm-Anker fuer Trip %s, obwohl die Tour laeuft (%s bis %s) — "
            "die Abweichungs-Wache ist blind bis zum naechsten Briefing-Versand.",
            trip.id, trip.start_date, trip.end_date,
        )
        record_alert_anchor_rejected(
            user_id=self._user_id, entity_id=trip.id, reason="missing",
        )

    def _write_rolling_alarm_anchor(
        self, trip_id: str, target_date: date, weather: List[SegmentWeatherData],
        channels: Iterable[str],
    ) -> None:
        """Schreibt NUR den rollierenden Alarm-Anker (Issue #1916, ADR-0056)
        — bewusst OHNE `write_anchor_and_reset_memory()`: dieser Schreibpfad
        darf das Melde-Gedaechtnis NICHT zuruecksetzen (AC-12).

        Issue #1987 (S1): je Kanal ein eigener Merker, und `channels` MUSS
        `NotificationResult.delivered_channels` sein — NICHT `sent_channels`
        (nur "betreten", enthaelt auch gescheiterte Transporte, Anti-Pattern
        #656) und NICHT `effective_channels` (konfiguriert, aber nicht
        notwendig zugestellt). Die Vergleichsbasis eines Empfaengers ist das,
        was dieser Empfaenger auf DIESEM Kanal zuletzt tatsaechlich
        zugestellt bekommen hat; ein leeres `channels` schreibt folgerichtig
        gar nichts (AC-1, AC-2, AC-6).
        """
        from services.weather_snapshot import WeatherSnapshotService

        svc = WeatherSnapshotService(user_id=self._user_id)
        for channel in channels:
            svc.save_alarm_anchor(trip_id, target_date, weather, channel)

    def _is_quiet_hours(self, trip: "Trip", now: datetime) -> bool:
        """Check if current time falls within the trip's configured quiet hours.

        Issue #181: Supports midnight-wrap (e.g. 22:00–07:00).
        Returns False when quiet hours are not configured (either field is missing).
        Issue #1168: pure Zeitfenster-Logik lebt jetzt in
        `DeviationAlertEngine.is_quiet_hours()` (location-generisch, 1:1
        übernommen); diese Methode bleibt als Trip-Adapter-Signatur bestehen.

        Args:
            trip: Trip with optional alert_quiet_from / alert_quiet_to fields
            now: Current datetime (caller is responsible for correct timezone)

        Returns:
            True if alerts should be suppressed (quiet hours active)

        Issue #1726: Zone aus `anchor_tz(trip, now)` — der TAGESBEWUSSTEN
        Aufloesung, nicht `trip_tz()`. Ein Trek durch mehrere Zonen braucht die
        Zone SEINER AKTUELLEN Etappe, nicht die des Starttags."""
        return DeviationAlertEngine.is_quiet_hours(
            now, trip.alert_quiet_from, trip.alert_quiet_to,
            anchor_tz(trip, now),
            context_label=trip.id,
        )

    def _is_briefing_imminent(self, trip: "Trip", now: datetime) -> bool:
        """Issue #1594: Steht fuer diesen Trip unmittelbar ein geplantes
        Briefing an, das noch nicht versucht wurde?

        DER gemeinsame Adapter beider Trip-Alarmarten — Aenderungsalarm
        (`check_and_send_alerts`) und amtliche Warnung
        (`_send_official_alert_only`) fragen dieselbe Stufe, direkt nach der
        Ruhezeit und VOR jedem Abruf. Rein lesend; das Faelligkeits-Praedikat
        ist die seiteneffektfreie Fassung aus dem Briefing-Scheduler, die
        `skip_next` NICHT verbraucht.

        Der Anker liegt unter der PROTOKOLL-Kennung `(trip.id, "trip")` — so
        schreibt ihn `trip_report_scheduler` (`briefing_entity_type="trip"`);
        eine andere Kennung faende ihn nie, die Sperre bliebe nach einem
        gescheiterten Versand das ganze Nachholfenster ueber stehen, ohne dass
        es auffiele.
        """
        from services.alert_gate import check_briefing_imminent
        from services.trip_report_scheduler import trip_briefing_due_at

        return check_briefing_imminent(
            user_id=self._user_id, entity_id=trip.id, entity_type="trip",
            now=now, zone=anchor_tz(trip, now),
            briefing_due_at=lambda moment: trip_briefing_due_at(
                trip, moment, user_id=self._user_id,
            ),
        )

    def _is_throttled_with_cooldown(self, trip: "Trip") -> bool:
        """Check if alert is throttled using per-trip cooldown override.

        Issue #181: alert_cooldown_minutes=0 means no limit (always returns False).
        If None, falls back to global throttle_hours default.
        Issue #1168: pure Cooldown-Logik lebt jetzt in
        `DeviationAlertEngine.is_cooldown_active()`; diese Methode bleibt der
        Trip-Adapter, der weiterhin den datei-/dict-basierten Throttle-State hält.

        Args:
            trip: Trip with optional alert_cooldown_minutes field

        Returns:
            True if throttled (too soon since last alert)
        """
        cooldown_minutes = (
            trip.alert_cooldown_minutes
            if trip.alert_cooldown_minutes is not None
            else self._throttle_hours * 60
        )
        return self._throttle_store.is_throttled(
            "trip", trip.id, cooldown_minutes, datetime.now(timezone.utc)
        )

    def get_time_until_next_alert(self, trip: "Trip") -> Optional[timedelta]:
        """
        Get remaining throttle time for a trip.

        Issue #1213 (AC-7): nutzt jetzt den per-Trip-Cooldown (identisch zu
        `_is_throttled_with_cooldown`) statt der globalen `throttle_hours`-
        Einstellung — die Anzeige widersprach zuvor dem tatsächlichen
        Drossel-Verhalten. Signatur wechselt entsprechend von `trip_id: str`
        auf `trip: "Trip"`.

        Args:
            trip: Trip with optional alert_cooldown_minutes field

        Returns:
            Time remaining until next alert allowed, or None if not throttled
        """
        cooldown_minutes = (
            trip.alert_cooldown_minutes
            if trip.alert_cooldown_minutes is not None
            else self._throttle_hours * 60
        )
        last_alert = self._throttle_store.last_sent("trip", trip.id)
        if last_alert is None:
            return None

        elapsed = datetime.now(timezone.utc) - last_alert
        remaining = timedelta(minutes=cooldown_minutes) - elapsed

        if remaining.total_seconds() <= 0:
            return None

        return remaining

    def clear_throttle(self, trip_id: str) -> None:
        """
        Clear throttle for a trip (for testing or manual override).

        Args:
            trip_id: Trip identifier
        """
        self._throttle_store.clear("trip", trip_id)
        logger.debug(f"Throttle cleared for trip {trip_id}")

    # --- Change Detection ---

    def _detect_all_changes(
        self,
        cached_weather: List[SegmentWeatherData],
        fresh_weather: List[SegmentWeatherData],
    ) -> List[WeatherChange]:
        """
        Detect changes across all segments.

        Args:
            cached_weather: Old weather data
            fresh_weather: New weather data

        Returns:
            List of all detected changes
        """
        all_changes = []

        # Match segments by segment_id
        cached_by_id = {w.segment.segment_id: w for w in cached_weather}
        fresh_by_id = {w.segment.segment_id: w for w in fresh_weather}

        for segment_id, cached in cached_by_id.items():
            fresh = fresh_by_id.get(segment_id)
            if fresh is None:
                continue

            # Issue #816 (C): Forecast-Alert ist Δ-only — absolute Regeln entfallen.
            changes = self._change_detector.detect_changes(
                cached, fresh, include_absolute=False
            )
            all_changes.extend(changes)

        return all_changes

    def _filter_significant_changes(
        self,
        changes: List[WeatherChange],
    ) -> List[WeatherChange]:
        """
        Issue #638: Return all changes — any change from an active, configured rule
        is significant regardless of severity. The MODERATE/MAJOR-only filter
        was silently dropping INFO/MINOR alerts (Severity-Falle).

        Args:
            changes: All detected changes

        Returns:
            All detected changes (severity is label only, not filter criterion)
        """
        return list(changes)

    # --- Radar Nowcast ---

    def _get_radar_service(self):
        """Lazy-init radar service."""
        if self._radar_service is None:
            from services.radar_service import RadarNowcastService
            self._radar_service = RadarNowcastService()
        return self._radar_service

    def clear_radar_throttle(self, trip_id: str) -> None:
        """Clear radar throttle for a trip (test helper)."""
        self._throttle_store.clear(_RADAR_THROTTLE_SCOPE, trip_id)

    def _briefing_precip_for_onset(
        self,
        snapshot,
        segment_id,
        onset_dt: datetime,
    ):
        """Return precip_1h_mm from briefing snapshot for onset hour, or None.

        onset_dt: UTC-aware datetime of predicted rain onset.
        segment_id: integer segment id (from convert_trip_to_segments).
        snapshot: List[SegmentWeatherData] from WeatherSnapshotService.load_dated(), or None.
        """
        if snapshot is None:
            return None
        onset_hour = to_utc(onset_dt).replace(minute=0, second=0, microsecond=0)
        for seg_data in snapshot:
            if seg_data.segment.segment_id != segment_id:
                continue
            if seg_data.timeseries is None:
                return None
            for dp in seg_data.timeseries.data:
                dp_ts = dp.ts
                if dp_ts.tzinfo is None:
                    dp_ts = dp_ts.replace(tzinfo=timezone.utc)
                if dp_ts == onset_hour and dp.precip_1h_mm is not None:
                    return dp.precip_1h_mm
            return None
        return None

    def _resolve_alert_segment(self, trip: "Trip", now_utc: datetime, today: date):
        """Segment-Auswahl des ALARM-Pfads -- mit vorgeschalteter, einmaliger
        Nachruestung der gemessenen Wegstrecke (Issue #2036 AC-7).

        AC-7 nennt als Ausloeser ausdruecklich die ERSTE Aufloesung der
        Alarm-Ortsangabe. Der Briefing-Trichter
        (`trip_report_scheduler._convert_trip_to_segments`) ruestet ebenfalls
        nach und bleibt unveraendert bestehen -- er greift aber nicht bei
        einem Trip mit abgeschaltetem Briefing-Versand und auch nicht bei
        einem Nowcast-Alarm VOR dem ersten Briefing des Tages. Genau dort
        bliebe die Etappe sonst dauerhaft auf "Segment N".

        Kein Doppelschreiben: `backfill_stage_distances` kehrt sofort um,
        sobald alle Wegpunkte der Etappe eine Distanz tragen -- der zweite
        Lauf fasst die Trip-Datei nicht mehr an.

        GRENZE: nachgeruestet wird die Etappe von `today`. Faellt die
        Aufloesung auf die Vortagsetappe zurueck (Stufe 2 in
        `resolve_current_segment`, #1667 S3), bleibt diese unvermessen bis
        ihr eigener Tag an der Reihe war -- kein zweiter GPX-Durchlauf pro
        Alarmzyklus, der Lauf hat eine Zeitobergrenze.
        """
        from services.track_resolution import backfill_stage_distances
        from services.trip_segments import resolve_current_segment

        trip = backfill_stage_distances(trip, self._user_id, today)
        return resolve_current_segment(trip, now_utc, today)

    def _protokolliere_radar_unterdrueckung(
        self, trip: "Trip", gate_reason: Optional[str], effective_channels,
        *, convective_checked: Optional[bool] = None,
    ) -> None:
        """Unterdrueckungs-Protokoll des Radar-Zweigs (Issue #2065 zieht die
        bestehende Fassung hierher, weil der Sperrzeit-Fall jetzt an mehreren
        Stellen enden kann).

        `convective_checked` (Issue #2050 S4a, AC-9) reisen die Aufrufer NACH
        dem Nowcast-Abruf mit: fiel die Gewitterpruefung aus, muss der Eintrag
        das festhalten. Vor dem Abruf gibt es die Angabe nicht — dort bleibt
        sie `None` (keine Aussage) statt erfunden zu werden.

        Absicherung je Trip, nicht um den Stapellauf: scheitert der
        Protokoll-Eintrag EINES Trips, verlieren sonst ALLE weiteren Trips
        dieses Nutzers ihren Radar-Alarm (Muster `fix_1479`)."""
        try:
            alert_log.append_suppressed_entry(
                self._user_id, entity_id=trip.id, entity_type="trip",
                reason=alert_log.REASON_NOWCAST, gate_reason=gate_reason,
                effective_channels=effective_channels,
                convective_checked=convective_checked,
            )
        except Exception as e:
            logger.error(
                "Radar alert: Unterdrueckungs-Protokoll fuer Trip %s "
                "fehlgeschlagen (%s) — der Alarm blieb aus (Grund: %s), "
                "nur der Protokoll-Eintrag fehlt.",
                trip.id, e, gate_reason,
            )

    def _eskalation_bricht_budget(
        self, trip: "Trip", now_utc: datetime, urgency: str,
    ) -> bool:
        """Darf diese Lage die erschoepfte Tages-Obergrenze durchbrechen?
        (Issue #2050 S3b, Szenario 7)

        Duenne Bruecke auf den geteilten Baustein — sie haelt die Zone (dieselbe,
        die auch Gate und Buchung benutzen, #1726) und die Protokollzeile an
        EINER Stelle statt an zweien; alle Aufrufstellen entscheiden damit
        garantiert gegen denselben Zaehler.

        Issue #2050 S3c: seit dieser Scheibe rufen BEIDE Zweige die Bruecke —
        Radar und Abweichung. Der Deckel `_MAX_ESCALATION_BREAKTHROUGHS`
        wirkt dadurch geteilt (ein Durchbruch je Zone und Tag ueber beide
        Zweige), nicht addiert."""
        durchbruch = alert_daily_limit.escalation_breaks_through(
            self._user_id, now_utc, anchor_tz(trip, now_utc), urgency,
        )
        # Beide Ausgaenge in EINER Zeile, damit im Nachhinein nachvollziehbar
        # ist, GEGEN WAS entschieden wurde (Muster der Sperrzeit-Ueberholung).
        logger.info(
            "Alert: Budget-Durchbruch fuer Trip %s geprueft — "
            "Dringlichkeit %s: %s",
            trip.id, urgency,
            "Durchbruch" if durchbruch else "Tages-Obergrenze bleibt",
        )
        return durchbruch

    def check_radar_alerts(self) -> int:
        """
        Check all trips for radar-based alerts using segment-aware logic (Issue #822).

        Wählt das aktive oder nächste Segment des Tages und prüft den Nowcast dort.
        Kein Alert bei: leerer Segmentliste, alle Segmente zeitlich vorbei, Throttle
        aktiv oder radar_alert_due=False.

        Sicherheits-Semantik (F001): alert_log + Throttle werden gesetzt,
        sobald mindestens ein Kanal-Zweig tatsächlich betreten wurde — unabhängig
        davon, ob der Versand technisch gelingt. Sind alle Kanäle auf Trip-Ebene
        deaktiviert, bleibt Recording aus (Issue #827).

        Returns the number of radar alerts triggered.
        """
        from app.loader import load_all_trips

        now_utc = datetime.now(timezone.utc)
        sent = 0

        for trip in load_all_trips(user_id=self._user_id):
            # Issue #1697: Ortstag dieses Trips statt Serverdatum (ADR-0044) —
            # je Trip, die Zone haengt vom Trip ab.
            today = trip_local_today(trip, now_utc)
            # Segment-Auswahl (Issue #822 — ersetzt stage.waypoints[0]),
            # seit Issue #1667 S3 tagesuebergreifend: aktiv heute -> aktiv
            # gestern -> Vorschau heute[0] -> nichts. Eine Etappe mit
            # Abendstart und Ankunft nach Mitternacht traegt ihr Ziel-Segment
            # bis in den Folgetag; der heutige Kalendertag allein fand es
            # nicht (`get_stage_for_date` loest strikt per `==` auf).
            # `segment_date` ist das Datum, dem das gewaehlte Segment
            # ENTSTAMMT — nicht zwingend `today`, s. Schnappschuss unten.
            _resolved = self._resolve_alert_segment(trip, now_utc, today)
            if _resolved is None:
                # Keine Etappe an beiden Tagen oder alle Segmente zeitlich
                # vorbei → kein Alert (Option Y der Spec)
                logger.debug(
                    f"Radar alert skipped: kein aktives/naechstes Segment fuer {trip.id}"
                )
                continue
            active, segment_date = _resolved

            # Issue #1697 AC-4: Horizont-Guard — Vorbild
            # `trip_report_scheduler.py::_build_starkregen_hint`. Ein Segment,
            # das erst weit in der Zukunft beginnt, loest keinen Nowcast-Abruf
            # aus (Horizont ~60 min); ohne diesen Guard riefe die neue
            # Ortstag-Etappenwahl in der 22:00-00:00-UTC-Randzeit jede Nacht
            # einen fachlich sinnlosen Nowcast fuer die morgige Etappe ab.
            if active.start_time > now_utc:
                from services.radar_service import NOWCAST_HORIZON_MIN

                minutes_until_start = (active.start_time - now_utc).total_seconds() / 60.0
                if minutes_until_start > NOWCAST_HORIZON_MIN:
                    # #1405-Linie: WAS uebersprungen wird, wird benannt, nicht
                    # nur DASS uebersprungen wird — der Startzeitpunkt macht
                    # die Meldung zu einer Aussage ueber das Segment selbst
                    # (pruefbar, betrieblich brauchbar), statt nur ueber die
                    # Distanz in Minuten.
                    logger.debug(
                        f"Radar alert skipped: Segment beginnt erst in "
                        f"{minutes_until_start:.0f} min (>{NOWCAST_HORIZON_MIN} min "
                        f"Horizont, Start={active.start_time.isoformat()}) fuer {trip.id}"
                    )
                    continue

            # Issue #1752 (Scheibe B zu #1745, D1/D2): Radar-Alarme folgen
            # demselben Kanal-Resolver wie Gewitter-, Aenderungs- und amtliche
            # Alarme — `trip.alert_channels`/`trip.alert_rules` statt der
            # Briefing-Flags. Das Kanal-Set wird GENAU EINMAL berechnet und an
            # allen drei Stellen (Unterdrueckungs-Protokoll, Leer-Check,
            # Versand) geteilt; zwei leicht abweichende Ableitungen waren die
            # Ursache dieses Bugs.
            # D3: bewusst NACH dem Horizont-Guard oben — fuer ein Segment, das
            # zeitlich gar nicht in Frage kommt, darf die `alert_rules`-Union
            # nicht ausgewertet werden.
            # Absicherung je Trip, nicht um den Stapellauf: scheitert die
            # Kanal-Aufloesung EINES Trips (beschaedigte `alert_channels`/
            # `alert_rules` aus der Persistenz), verlieren sonst ALLE weiteren
            # Trips dieses Nutzers ihren Radar-Alarm — bei jedem Scheduler-Tick
            # erneut, bis die Daten repariert sind (Muster `fix_1479`). Breite
            # Klausel + laute Meldung mit Kennung, wie beim Nowcast-Abruf ein
            # paar Zeilen weiter unten.
            try:
                effective_channels = self._effective_alert_channels(trip)
            except Exception as e:
                logger.error(f"Radar alert channel resolution failed for trip {trip.id}: {e}")
                continue

            cooldown_min = (
                trip.alert_cooldown_minutes
                if trip.alert_cooldown_minutes is not None
                else self._throttle_hours * 60
            )
            # Issue #1467 S3: dieselbe Kette wie bisher (Ruhezeit -> Sperrzeit
            # -> Tages-Obergrenze, #1070/#1555), jetzt aus dem geteilten
            # Baustein, den auch der Vergleichs-Nowcast benutzt. Reihenfolge,
            # Scope (`radar`), Schluessel (`trip.id`) und Zustellverhalten
            # bleiben unveraendert — neu ist allein der Protokoll-Eintrag.
            gate = check_nowcast_gate(
                user_id=self._user_id,
                throttle_scope=_RADAR_THROTTLE_SCOPE,
                throttle_key=trip.id,
                cooldown_minutes=cooldown_min,
                quiet_from=trip.alert_quiet_from,
                quiet_to=trip.alert_quiet_to,
                context_label=trip.id,
                now=now_utc,
                zone=anchor_tz(trip, now_utc),
                throttle_store=self._throttle_store,
            )
            # Issue #2065: die SPERRZEIT ist die einzige Stufe der Kette, die
            # eine quantitative Verschaerfung ueberholen darf. Der Lauf haelt
            # deshalb hier nicht mehr an, sondern holt die Daten und
            # entscheidet weiter unten gegen die zuletzt gemeldete Menge.
            # Ruhezeit (#1955, unbrechbar) und Tages-Obergrenze bleiben
            # unveraendert harte Stops.
            _sperrzeit_offen = (
                not gate.allowed and gate.reason == alert_log.REASON_COOLDOWN
            )
            # Issue #2050 S3b (Szenario 7): zweites, davon UNABHAENGIGES
            # Signal. Ein erschoepftes Tagesbudget haelt den Lauf ebenfalls
            # nicht mehr hier an — die Dringlichkeit, gegen die entschieden
            # wird, entsteht erst aus dem Nowcast-Abruf. Die Ruhezeit bleibt
            # der einzige unbrechbare Stop (#1955, AC-21). Beide Gruende
            # schliessen einander an DIESER Stelle aus (`gate.reason` traegt
            # genau einen Wert), die Reihenfolge Ruhezeit -> Sperrzeit ->
            # Tages-Obergrenze bleibt damit unangetastet.
            _budget_erschoepft = (
                not gate.allowed and gate.reason == alert_log.REASON_DAILY_LIMIT
            )
            if not gate.allowed and not _sperrzeit_offen and not _budget_erschoepft:
                logger.debug(
                    f"Radar alert suppressed ({gate.reason}) for trip {trip.id}"
                )
                # Absicherung je Trip, nicht um den Stapellauf: scheitert der
                # Protokoll-Eintrag EINES Trips, verlieren sonst ALLE weiteren
                # Trips dieses Nutzers ihren Radar-Alarm (Muster `fix_1479`).
                # Breite Klausel + laute Meldung mit Kennung, wie beim
                # Nowcast-Abruf ein paar Zeilen weiter unten.
                self._protokolliere_radar_unterdrueckung(
                    trip, gate.reason, effective_channels,
                )
                continue

            # Bis zu RADAR_ZONE_MAX_POINTS get_nowcast-Calls pro Trip
            # (Budget, #1329; Deckel und Abstand aus `trip_segments`) — seit
            # Issue #2017 ab dem Ort, an dem der Nutzer zur MITTE des
            # Vorwarnfensters sein wird, nicht mehr am Startpunkt des
            # Segments (den hat er zu diesem Zeitpunkt laengst verlassen;
            # gemessener Median-Versatz 1,99 km).
            #
            # Issue #2051 S2a: die #2017-Zusicherung "genau EIN Abruf" ist
            # BEWUSST auf eine Obergrenze abgeloest (Spec, Abschnitt
            # "Abgeloeste Zusicherung") — die raeumliche Ausdehnung des
            # Ereignisses braucht mehrere Messpunkte entlang der
            # Reststrecke. Der ERSTE Punkt bleibt der #2017-Messpunkt und
            # traegt unveraendert die Ausloeseregel; die uebrigen liefern
            # ausschliesslich die Zonen. Unterhalb des Punktabstands
            # (Reststrecke < 2 km) bleibt es bei genau einem Abruf.
            #
            # Onset-frei: `_at` ist ein FESTER Zeitpunkt (halbes Fenster),
            # kein aus dem Nowcast-Ergebnis abgeleiteter. Der Onset entsteht
            # erst AUS diesem Abruf (`_onset_dt` unten) — ihn hier zu
            # benutzen waere ein Zirkelschluss.
            #
            # Die Schwelle kommt ueber die MODUL-Referenz, nicht als
            # `from ... import` gebunden: eine beim Import gebundene Kopie
            # liefe still am Drift-Schutz aus #2009 vorbei.
            from services import radar_service as radar_service_mod
            from services import trip_segments as trip_segments_mod

            _at = now_utc + timedelta(
                minutes=radar_service_mod.RADAR_ONSET_THRESHOLD_MIN // 2
            )
            # Absicherung je Trip, nicht um den Stapellauf (Adversary
            # F-ADV1, Muster `fix_1479`): Vor #2017 stand hier ein trivialer
            # Attributzugriff (`active.start_point.lat`); jetzt steht hier ein
            # Aufruf mit Verzweigungen, Datumsarithmetik und iterativem
            # Nachladen des Folgetags. Wirft der fuer EINEN Trip, verloeren
            # sonst ALLE weiteren Trips dieses Nutzers ihren Radar-Alarm —
            # `load_all_trips()` sortiert nicht, es traefe also zufaellig
            # wechselnde Trips, und `api/routers/scheduler.py` faengt darum
            # herum nichts ab.
            # Eigener `try` statt Aufnahme in den Nowcast-`try` unten: der
            # Fehler nimmt denselben Weg (`continue`), bekommt aber eine
            # UNTERSCHEIDBARE Meldung. Unter "Radar nowcast failed" abgelegt
            # waere er stiller als vorher — er kommt gar nicht vom Abruf.
            try:
                # Issue #2051 S2a: die Punktbildung ruft `position_at_time()`
                # selbst — der erste Punkt IST der bisherige Messpunkt.
                _punkte = trip_segments_mod.points_along_remaining_route(
                    trip, active, segment_date, _at,
                )
                _pos = _punkte[0]
            except Exception as e:
                logger.error(
                    "Radar alert: Positionsbestimmung fuer Trip %s "
                    "fehlgeschlagen (%s) — dieser Trip wird uebersprungen, die "
                    "uebrigen Trips dieses Nutzers laufen weiter.",
                    trip.id, e,
                )
                if _sperrzeit_offen:
                    self._protokolliere_radar_unterdrueckung(
                        trip, gate.reason, effective_channels,
                    )
                continue
            lat = _pos.lat
            lon = _pos.lon
            # Hoehe MUSS mitwandern (#1991/#2017): der neue Ort mit der
            # alten Hoehe abgefragt entscheidet im Gebirge ueber Regen oder
            # Schnee. Normalisierung auf ganze Meter HIER, nicht in
            # `position_at_time()` — `get_nowcast` fuehrt `elevation_m` roh
            # in den Cache-Schluessel, und `1000` und `1000.0` erzeugten in
            # #1991 zwei Eintraege fuer denselben Punkt.
            _elevation_m = (
                int(round(_pos.elevation_m)) if _pos.elevation_m is not None else None
            )
            tz = tz_for_coords(lat, lon)
            try:
                radar_svc = self._get_radar_service()
                # Issue #1329 C2: Scheduler-Radar ist ein polling-Check
                # (drosselbar bei Budget-Druck) -- kein Nutzer-Briefing.
                result = radar_svc.get_nowcast(
                    lat, lon, elevation_m=_elevation_m, priority="polling"
                )
            except Exception as e:
                logger.error(f"Radar nowcast failed for trip {trip.id}: {e}")
                # Issue #2050 S4a (AC-2, Anforderung B-4): ein geworfener Abruf
                # ist derselbe Quellenausfall wie das fail-soft-Leerergebnis
                # weiter unten, nur in anderer Form — und er bekommt denselben
                # Grund, UNABHAENGIG davon, ob zufaellig eine Sperrzeit lief.
                # Die bisherige Fassung protokollierte NUR bei offener
                # Sperrzeit, und dann mit `cooldown`: der Regelfall (keine
                # Sperrzeit) blieb voellig still, der Ausnahmefall trug den
                # falschen Grund — die Sperrzeit hat diesen Lauf ja nicht
                # unterdrueckt, die Quelle hat ihn verhindert.
                self._protokolliere_radar_unterdrueckung(
                    trip, alert_log.REASON_DATA_UNAVAILABLE, effective_channels,
                )
                continue

            # Issue #2051 S2a: die uebrigen Punkte der Reststrecke, sequenziell
            # und mit derselben Prioritaet (Muster
            # `compare_radar_alert._detect_triggered_locations`).
            #
            # Anders als der ERSTE Abruf (oben, traegt die Ausloeseregel)
            # bricht ein Fehler hier den Trip NICHT ab: ein Punkt ohne
            # verwertbare Daten ist eine Luecke, weder nass noch trocken (E4),
            # und darf den Alarm nicht kosten. `throttled`/`data_unavailable`
            # sind derselbe Fall in Feldform — keine Frames, aber eben auch
            # kein belegtes "trocken", das eine Zone trennen duerfte.
            _zonen_ergebnisse: list = [_zonen_messwert(result)]
            for _p in _punkte[1:]:
                try:
                    _zonen_ergebnisse.append(
                        _zonen_messwert(
                            radar_svc.get_nowcast(
                                _p.lat, _p.lon,
                                elevation_m=(
                                    int(round(_p.elevation_m))
                                    if _p.elevation_m is not None else None
                                ),
                                priority="polling",
                            )
                        )
                    )
                except Exception as e:
                    logger.warning(
                        "Radar alert: Nowcast fuer Zonenpunkt (%.4f, %.4f) des "
                        "Trips %s fehlgeschlagen (%s) — der Punkt faellt aus "
                        "der Ausdehnung heraus, der Alarm laeuft weiter.",
                        _p.lat, _p.lon, trip.id, e,
                    )
                    _zonen_ergebnisse.append(None)
            _rain_zones = tuple(
                derive_rain_zones(_punkte, _zonen_ergebnisse)
            )

            # Issue #2065: die gemessene Menge wird HIER festgehalten --
            # `result` traegt weiter unten die NotificationResult, die
            # Vergleichsbasis der naechsten Runde muss aber aus DIESEM Abruf
            # stammen.
            _menge_mm = result.window_precip_mm

            # Issue #2050 S3b: die Dringlichkeit dieses Abrufs entsteht HIER,
            # vor beiden Ausnahme-Entscheidungen — bis dahin wurde sie erst
            # kurz vor dem Versand gebildet (`_radar_request`, weiter unten),
            # also NACH der Tages-Obergrenzen-Nachpruefung, die sie braucht.
            # Ableitung und Werte sind unveraendert: `_radar_request` traegt
            # dieselben zwei Groessen aus DIESEM `result`, und
            # `urgency_from_radar()` liest das Label case-insensitiv (dort
            # steht es nur mit kleinem Anfangsbuchstaben).
            _radar_urgency = alert_urgency.urgency_from_radar(
                is_convective=result.is_convective,
                intensity_label=result.intensity_label,
            )
            # Traegt der Budget-Durchbruch diesen Lauf? Entscheidet unten
            # ueber die Buchung (`escalation_breakthroughs`) und bleibt False,
            # solange das Budget gar nicht im Weg stand.
            _budget_durchbruch = False

            # Issue #2065: Ueberholungs-Entscheidung gegen die zuletzt
            # gemeldete Menge. Bewusst VOR dem Ausloese-Guard
            # (`radar_alert_due`): so bekommt jeder Lauf, der AN DER SPERRZEIT
            # haengenbleibt, weiterhin seinen Protokoll-Eintrag mit Grund
            # `cooldown` — unabhaengig davon, ob die Lage alarmwuerdig waere.
            #
            # 🔴 Nach einem erfolgreichen Durchbruch gilt das NICHT mehr, und
            # das ist Absicht: der Durchgang ist dann nicht mehr gesperrt und
            # verhaelt sich ab hier wie ein freier Lauf. Scheitert er
            # anschliessend am Ausloese-Guard (`radar_alert_due`) oder am
            # Doppel-Alarm-Guard, bleibt er genauso still wie ein freier Lauf
            # in derselben Lage — „nicht alarmwuerdig" ist in diesem System
            # kein Unterdrueckungs-Ereignis und bekommt keinen `alert_log`-
            # Eintrag. Ein `cooldown`-Eintrag waere dort schlicht falsch: die
            # Sperrzeit hat diesen Lauf ja gerade NICHT unterdrueckt. Die
            # Entscheidung selbst bleibt ueber die `logger.info`-Zeile weiter
            # unten nachvollziehbar (AC-13, beide Ausgaenge). Festgenagelt in
            # `tests/tdd/test_radar_cooldown_overtake.py`
            # (`test_f001_durchbruch_ohne_ausloeser_verhaelt_sich_wie_ein_freier_lauf`).
            _ueberholt_sperrzeit = False
            if _sperrzeit_offen:
                _basis_mm = last_nowcast_precip_mm(
                    user_id=self._user_id, throttle_scope=_RADAR_THROTTLE_SCOPE,
                    throttle_key=trip.id, throttle_store=self._throttle_store,
                )
                _ueberholt_sperrzeit = radar_overtakes_cooldown(
                    basis_mm=_basis_mm, menge_mm=_menge_mm,
                )
                # Beide Zahlen in EINER Zeile, damit im Nachhinein
                # nachvollziehbar ist, GEGEN WAS entschieden wurde -- fuer
                # beide Ausgaenge (Durchbruch und Stille).
                logger.info(
                    "Radar alert: Sperrzeit-Ueberholung fuer Trip %s geprueft — "
                    "Vergleichsbasis %s mm, gemessene Menge %.1f mm: %s",
                    trip.id,
                    "unbekannt" if _basis_mm is None else f"{_basis_mm:.1f}",
                    _menge_mm,
                    "Durchbruch" if _ueberholt_sperrzeit else "Sperrzeit bleibt",
                )
                if not _ueberholt_sperrzeit:
                    # Issue #2050 S4a (AC-9): ab hier liegt ein Abruf vor, also
                    # reist auch die Frage mit, ob seine Gewitterpruefung lief.
                    self._protokolliere_radar_unterdrueckung(
                        trip, gate.reason, effective_channels,
                        convective_checked=result.convective_checked,
                    )
                    continue
                # Die Tages-Obergrenze wurde wegen des Abbruchs an der
                # Sperrzeit nie geprueft (feste Reihenfolge, ADR-0021) -- der
                # Durchbruch darf sie nicht stillschweigend mit-ueberspringen.
                # Rein lesend; gebucht wird weiterhin erst nach Zustellung.
                if not alert_daily_limit.is_allowed(
                    self._user_id, now_utc, anchor_tz(trip, now_utc),
                    reason="nowcast",
                ):
                    # Issue #2050 S3b (AC-22): auch DIESE Nachpruefung kennt
                    # die Eskalations-Ausnahme. Beide Ausnahmen wirken
                    # unabhaengig — ein Lauf kann an der Sperrzeit UND am
                    # Budget haengen und beide durchbrechen; ohne die Pruefung
                    # hier stoppte das erschoepfte Budget den Fall, bevor die
                    # Ausnahme unten ueberhaupt erreichbar waere.
                    _budget_durchbruch = self._eskalation_bricht_budget(
                        trip, now_utc, _radar_urgency,
                    )
                    if not _budget_durchbruch:
                        logger.debug(
                            "Radar alert suppressed (Tages-Obergrenze nach "
                            "Sperrzeit-Durchbruch) for trip %s", trip.id,
                        )
                        self._protokolliere_radar_unterdrueckung(
                            trip, alert_log.REASON_DAILY_LIMIT, effective_channels,
                            convective_checked=result.convective_checked,
                        )
                        continue
            elif _budget_erschoepft:
                # Issue #2050 S3b (Szenario 7, AC-15 bis AC-17): das Gate hat
                # an der Tages-Obergrenze gehalten. Jetzt — und erst jetzt,
                # mit der Dringlichkeit dieses Abrufs in der Hand — entscheidet
                # der Aufrufer, ob die Lage sie durchbricht.
                _budget_durchbruch = self._eskalation_bricht_budget(
                    trip, now_utc, _radar_urgency,
                )
                if not _budget_durchbruch:
                    logger.debug(
                        "Radar alert suppressed (Tages-Obergrenze, keine "
                        "Eskalation) for trip %s", trip.id,
                    )
                    self._protokolliere_radar_unterdrueckung(
                        trip, gate.reason, effective_channels,
                        convective_checked=result.convective_checked,
                    )
                    continue

            # Issue #2009: EINE geteilte Schwelle statt zweier Literale
            # (ADR-0021). Bewusst ueber die Modul-Referenz gelesen, nicht als
            # `from ... import RADAR_ONSET_THRESHOLD_MIN` gebunden — eine
            # gebundene Kopie waere eine stille Kopie und wuerde beim
            # Nachziehen der Quelle auseinanderlaufen.
            from services import radar_service as radar_service_mod

            # Issue #2050 S4a (AC-1, Anforderung B-4): ein Fremdausfall der
            # Quelle ist NIE eine Entwarnung. Ohne Frames gibt es keinen
            # Beginn, und der Lauf faellt heute in denselben stummen Ausstieg
            # wie eine ruhige Viertelstunde — im Protokoll ununterscheidbar von
            # "geprueft, alles ruhig". Geprueft wird deshalb VOR dem
            # Ausloese-Guard: `radar_alert_due()` bleibt unveraendert eine
            # reine Aussage ueber die LAGE, nicht ueber die Datenlage.
            if result.data_unavailable:
                logger.warning(
                    "Radar alert: Quellenausfall fuer Trip %s (keine Frames aus "
                    "der Quelle) — kein Alarm; der Ausfall wird als solcher "
                    "protokolliert statt als ruhige Viertelstunde.", trip.id,
                )
                self._protokolliere_radar_unterdrueckung(
                    trip, alert_log.REASON_DATA_UNAVAILABLE, effective_channels,
                    convective_checked=result.convective_checked,
                )
                continue

            if not radar_alert_due(result, radar_service_mod.RADAR_ONSET_THRESHOLD_MIN):
                continue

            # Issue #2050 S2b: ohne kuenftigen Beginn (laufendes Ereignis, das
            # in der laufenden Viertelstunde endet) waere `timedelta(
            # minutes=None)` ein Absturz. Bezugszeitpunkt ist dann JETZT --
            # dieser Wert traegt die Ereignis-Identitaet (Entdopplung) und den
            # Briefing-Vergleich, beide brauchen einen Zeitpunkt (Bruchstelle 3).
            _onset_dt = now_utc + timedelta(minutes=result.onset_minutes or 0)


            # Briefing-Vergleich (Issue #818 AC-1/AC-2/AC-3)
            # Issue #1667 S3: gelesen wird unter dem Datum, dem das GEWAEHLTE
            # Segment entstammt — nicht unter `today`. Stammt es vom Vortag
            # (Nacht-Ankunft), liegt sein Briefing-Schnappschuss auch unter
            # dem Vortag; mit `today` fiele der Vergleich ins Leere und ein
            # gerade gewonnener Alarm bliebe unbegruendet unterdrueckt bzw.
            # der angekuendigte Regen unerkannt.
            from services.weather_snapshot import WeatherSnapshotService
            # Issue #2050 S6 (E-1): `segment_fetched_at=True` -- die
            # Vergleichsbasis im Protokoll soll den Abruf benennen, auf den
            # sich der Briefing-Vergleich wirklich beruft. Nur HIER opt-in
            # (s. `load_dated()`): der Alarm-Footer #1916 laeuft ueber
            # `_get_cached_weather()` und bleibt beim Schreibzeitpunkt.
            _snapshot = WeatherSnapshotService(self._user_id).load_dated(
                trip.id, segment_date, segment_fetched_at=True,
            )
            _briefing_precip = self._briefing_precip_for_onset(_snapshot, active.segment_id, _onset_dt)
            _briefing_announced = (_briefing_precip is not None and _briefing_precip >= 0.5)
            # Issue #2050 S6 (E-1): die an DIESEM Zweig bekannten Groessen --
            # EINMAL abgeleitet und an allen drei Protokollstellen dieses
            # Zweigs identisch (Briefing-Gate, Ereignis-Identitaet, Versand).
            # Issue #2050 S4b: `_punkte`/`_zonen_ergebnisse` sind die ROHFORM
            # der Ausdehnungs-Messung, positionsgleich — aus ihnen entsteht die
            # Buchfuehrung ueber die ausgefallenen Messpunkte. Die verdichteten
            # Zonen taugen dafuer nicht: `derive_rain_zones` uebergeht eine
            # Luecke kommentarlos, danach ist sie nicht mehr rekonstruierbar.
            _e1 = _radar_e1_fields(
                entity_id=trip.id, result=result, now_utc=now_utc,
                onset_dt=_onset_dt, active=active, snapshot=_snapshot,
                punkte=_punkte, zonen_ergebnisse=_zonen_ergebnisse,
            )
            # Sicherheits-Override (Slice 4, #883): konvektive Gefahr (Gewitter/Hagel)
            # durchbricht die Briefing-Unterdrückung. Normaler (nicht-konvektiver)
            # angekündigter Regen bleibt unterdrückt (reines Δ-Modell).
            #
            # #2020 A3: Ueberholungs-Pruefung statt binaerer Sperre. Menge gegen
            # Menge (window_precip_mm vs. _briefing_precip), Relevanz-Untergrenze
            # ebenfalls ueber die Menge (F008, PO-Entscheid 2026-08-21) --
            # NICHT mehr ueber die Spitzenrate: anhaltender, nicht-spitzer Regen
            # ist per Definition nicht spitz und fiel durch die alte
            # Ratenschwelle durch, obwohl er die Ankuendigung real ueberholte
            # (belegt: 3,9 mm/h ueber 50 Min = 3,575 mm gegen 1,0 mm Ankuendigung,
            # 3,6-fach -- alte Regel: kein Alarm). UND-Verknuepfung (nicht ODER)
            # haelt die Regel fuer festen _briefing_precip monoton in beiden
            # Groessen (AC-3).
            _overtaking = (
                _briefing_announced
                and result.window_precip_mm >= _briefing_precip * _BRIEFING_OVERTAKE_FACTOR
                and result.window_precip_mm >= _OVERTAKE_MIN_ABSOLUTE_MM
            )
            # Issue #2050 S4a (AC-7, Anforderung B-4): die Unterdrueckung setzt
            # jetzt voraus, dass die Gewitterpruefung STATTGEFUNDEN hat.
            # `is_convective` ist per Vorgabe `False` und wird ohne den
            # Gewitter-Beiabruf nie gesetzt — aus "nicht geprueft" wurde still
            # "kein Gewitter", und der Sicherheits-Override aus #883 liess sich
            # damit durch eine NIE STATTGEFUNDENE Pruefung aushebeln. Eine
            # durchgefuehrte, negative Pruefung traegt die Unterdrueckung
            # unveraendert (Δ-Modell, Gegenprobe AC-8).
            if (
                _briefing_announced and result.convective_checked
                and not result.is_convective and not _overtaking
            ):
                logger.debug(
                    f"Radar alert suppressed: briefing had {_briefing_precip} mm for {trip.id}"
                )
                try:
                    alert_log.append_suppressed_entry(
                        self._user_id, entity_id=trip.id, entity_type="trip",
                        reason=alert_log.REASON_NOWCAST,
                        gate_reason=f"briefing_announced:{_briefing_precip}mm",
                        effective_channels=effective_channels,
                        **_e1,
                    )
                except Exception as e:
                    logger.error(
                        "Radar alert: Unterdrueckungs-Protokoll (Briefing-Ankuendigung) "
                        "fuer Trip %s fehlgeschlagen (%s) — der Alarm blieb aus, nur der "
                        "Protokoll-Eintrag fehlt.", trip.id, e,
                    )
                continue

            # Issue #2050 S4c (Entscheidung 2): der Doppel-Alert-Guard (#818)
            # ist HIER entfernt, nicht repariert -- er las `precip:<segment>`,
            # geschrieben wird das Melde-Gedaechtnis aber als
            # `<change.metric>:<segment_id>` (der reale Schluessel heisst
            # `precip_sum_mm:<segment>`); der Niederschlags-Teil war seit #818
            # toter Code, ohne Eskalations-Ausnahme. Die Paarung "Δ meldete,
            # Radar zieht nach" laeuft ab jetzt ausschliesslich ueber
            # `check_event_identity_gate()` weiter unten -- der Δ-Zweig
            # registriert seine nassen Alarme jetzt dort (`check_and_send_alerts`),
            # der Grund heisst fuer diese Paarung `event_duplicate` statt
            # `double_alert_guard` (AC-14/AC-15). Der Grund-Code selbst bleibt
            # in `alert_log.py`/`undelivered_hint.py` fuer historische
            # Eintraege erhalten.

            # Kein Kanal konfiguriert → kein Alert (nichts zu recorden).
            # Spec-Nachtrag 2026-08-11 (#1701, "die achte Stelle"): bewusst
            # gegen das effektive Kanal-Set gefuehrt statt gegen eine vierte
            # can_send_*()-Bereitschaftsfrage -- ein Trip mit ausschliesslich
            # Premium-SMS hat kein `sms_to`, `can_send_sms()` waere False,
            # obwohl ein funktionsfaehiger Kanal konfiguriert ist.
            if not effective_channels:
                logger.warning(f"No channel configured; skipping radar alert for {trip.id}")
                continue

            # Cooldown-Anzeige
            if cooldown_min % 60 == 0:
                n = cooldown_min // 60
                cooldown_display = f"{n} Stunde" if n == 1 else f"{n} Stunden"
            else:
                cooldown_display = f"{cooldown_min} Minuten"

            # Issue #952 (reopened): kurzes Intensitäts-Label (kein format_now_text-Satz
            # mehr — der Renderer haengt selbst "ab {onset_time}" an). Briefing-Kontext
            # wandert in ein eigenes Feld (4. Datenblock-Zeile, nur E-Mail).
            # Issue #1310 (AC-4 aus #883 Slice 4): der Override-Fall braucht einen
            # eigenen dritten Zustand. "bereits angekündigt" allein ist zwar wahr,
            # verschweigt aber die Zuspitzung, wegen der überhaupt gesendet wurde --
            # angekündigter Regen, der laut Radar konvektiv (Gewitter/Hagel) wird.
            # Ohne Konvektion kommt der Zweig hier gar nicht an (oben `continue`);
            # die Fallunterscheidung bleibt trotzdem explizit, damit die Aussage
            # auch dann richtig ist, wenn die Unterdrückung oben je gelockert wird.
            if _briefing_announced and result.is_convective:
                _briefing_context = "bereits angekündigt — jetzt akut"
            elif _briefing_announced:
                _briefing_context = "bereits angekündigt"
            else:
                _briefing_context = "nicht angekündigt"
            # F002: Anzeige-Kontext mitten im Satz ("leichter Regen") -- erstes
            # Zeichen kleinschreiben; intensity_to_text() selbst bleibt Title-Case
            # (andere Caller nutzen es am Satzanfang). Alle Labels beginnen mit
            # Adjektiv, daher ist [:1].lower() hier immer korrekt.
            _label = result.intensity_label
            _label = _label[:1].lower() + _label[1:]
            # Issue #2009: Uhrzeit und Tagesbezug aus DEMSELBEN Zeitpunkt
            # (`_onset_dt`, oben berechnet) und
            # DERSELBEN Zone — eine zweite Herleitung koennte auseinander-
            # laufen und "00:23" wieder mehrdeutig machen.
            _onset_time_str = local_fmt(_onset_dt, tz)
            # Issue #2051 S1: Ende-Uhrzeit, ihr EIGENER Tagesbezug und der
            # R4-Waechter ueber die geteilte Fassung, die auch das
            # Ortsvergleich-Buendel benutzt (ADR-0021). Der Waechter reist
            # ausdruecklich MIT: er waehlt im Renderer die Textform
            # (Untergrenze vs. bekanntes Ende, Spec v1.1). Lazy importiert wie
            # die uebrigen Renderer-Bausteine dieses Pfads.
            from output.renderers.alert.official_alerts import (
                _de_weekday_short,  # Issue #2054: EIN Kuerzel-Erzeuger
            )
            from output.renderers.alert.project import (
                event_end_display, location_sharpness_display, source_reach_display,
            )

            _end_time_str, _end_day_offset, _end_ongoing, _end_weekday = (
                event_end_display(now_utc, result, tz)
            )
            # Issue #2054: Versatz und Wochentagskuerzel des BEGINNS aus
            # DEMSELBEN Zeitpunkt und DERSELBEN Zone -- eine zweite Herleitung
            # koennte auseinanderlaufen (Muster #2009 o.).
            _onset_day_offset = day_offset(now_utc, _onset_dt, tz)
            # Issue #2051 S3: Reichweite und Guete-Grenzzeit ueber dieselben
            # geteilten Fassungen, die auch der Ortsvergleich-Pfad benutzt
            # (ADR-0021).
            _reach_time_str, _reach_day_offset = source_reach_display(
                now_utc, result, tz,
            )
            _sharp_time_str, _sharp_day_offset = location_sharpness_display(
                now_utc, result.onset_minutes,
                getattr(result, "event_end_minutes", None), tz,
            )
            _radar_request = RadarAlertRequest(
                onset_minutes=result.onset_minutes,
                already_running=result.already_running,  # Issue #2050 S2b
                onset_time=_onset_time_str,
                onset_day_offset=_onset_day_offset,
                onset_weekday=(
                    _de_weekday_short(local_dt(_onset_dt, tz))
                    if _onset_day_offset else None
                ),
                km_from=active.start_point.distance_from_start_km,
                km_to=active.end_point.distance_from_start_km,
                # Issue #2036/#2051 S2a: stammen diese km-Zahlen aus echter
                # GPX-Wegstrecke? Die Etappe weiss es (`distance_measured`),
                # der Onset-Pfad hat sie bis hierher nie gefragt — ohne die
                # Antwort bliebe die Ausdehnung unten auf jeder Etappe stumm.
                km_measured=getattr(active, "distance_measured", False),
                # Issue #2051 S2a: die Nass-Zonen der Reststrecke.
                rain_zones=_rain_zones,
                # Issue #2050 S4b-2: die Kennzeichnung im Text speist sich aus
                # DENSELBEN beiden Groessen, die schon Ausloeseentscheidung
                # (S4a) und Alarmprotokoll (S4b) fuehren -- die Messluecken
                # ueber `_e1`, also ueber die eine bestehende Ableitung
                # `_messluecken_felder`. Eine zweite Herleitung koennte
                # auseinanderlaufen und Text und Protokoll verschiedene
                # Wahrheiten erzaehlen lassen.
                convective_checked=result.convective_checked,
                gap_km=tuple(
                    _e1.get("measurement_gaps", {}).get("gap_km", ())
                ),
                # Issue #1744 A1: dieselbe Etappe, die schon die km-Spanne
                # liefert — nur zusaetzlich mit ihrer Kennung, damit der
                # Nowcast denselben Ort benennt wie die amtliche Warnung.
                segment_id=normalize_segment_id(active.segment_id),
                is_convective=result.is_convective,
                intensity_label=_label,
                source_label=radar_svc.source_label(result.source),
                briefing_context=_briefing_context,
                # Issue #2122: das Datum, dem das gewaehlte Segment ENTSTAMMT
                # (kann der Vortag sein, s. `_resolve_alert_segment`-Docstring)
                # -- NICHT `today` (`notification_service.send_radar_alert`
                # leitet daraus die Etappen-Nummer ab, AC-6).
                segment_date=segment_date,
                # Issue #2046: die Menge der Stunde AB DEM BEGINN aus DEMSELBEN
                # NowcastResult, das schon onset_minutes/intensity_label
                # liefert (analog `is_convective=result.is_convective`) -- rein
                # beschreibend, ohne Einfluss auf die Ausloeseregel.
                onset_precip_mm=result.onset_precip_mm,
                # Issue #2051 S1: Ende desselben Ereignisses -- beschreibend,
                # ohne Einfluss auf die Ausloeseregel (wie onset_precip_mm).
                event_end_time=_end_time_str,
                event_end_day_offset=_end_day_offset,
                event_end_weekday=_end_weekday,  # Issue #2054
                event_ongoing_beyond_horizon=_end_ongoing,
                # Issue #2051 S3: additiv.
                source_reach_time=_reach_time_str,
                source_reach_day_offset=_reach_day_offset,
                location_sharpness_limit_time=_sharp_time_str,
                location_sharpness_limit_day_offset=_sharp_day_offset,
                tz=tz,
            )

            # Kanal-Schwelle (ADR-0046) auf dem oben einmalig berechneten,
            # geteilten Kanal-Set. Bis #1752 stand hier ein dritter Aufruf der
            # eigenen Radar-Ableitung samt zweitem Leer-Check — beides
            # entfallen: die Aufloesung ist rein, `trip` bleibt zwischen dem
            # Leer-Check oben (`if not effective_channels`) und dieser Stelle
            # unveraendert.
            # Issue #2050 S3b: `_radar_urgency` steht bereits — es wird jetzt
            # direkt nach dem Nowcast-Abruf gebildet, weil die
            # Eskalations-Ausnahme am Tagesbudget es dort schon braucht. Eine
            # zweite Ableitung hier waere eine stille Kopie derselben Groesse.
            _radar_allowed, _radar_suppressed = alert_channel_threshold.split_by_threshold(
                effective_channels, _radar_urgency, trip.alert_channel_thresholds,
            )

            # Issue #1467 S4b-1: quellenuebergreifende Ereignis-Identitaet --
            # LETZTE Stufe vor dem Versand (AC-12), kanaluebergreifend (V3,
            # daher NACH der Kanal-Schwelle oben berechnet, aber VOR dem
            # eigentlichen Versand geprueft). Ein Nowcast ist immer Klasse
            # 'wet' (T2, AC-4b) -- `resolve_hazard_class` bekommt hier NIE
            # `None`.
            _identity_gate = check_event_identity_gate(
                user_id=self._user_id, entity_id=trip.id,
                hazard_class=resolve_hazard_class(is_convective=_radar_request.is_convective),
                segment_ids=(
                    [_radar_request.segment_id] if _radar_request.segment_id else []
                ),
                severity=_radar_urgency, now=now_utc, point_at=_onset_dt,
                # Issue #2065: dieselbe Mengen-Feststellung, die schon die
                # Sperrzeit ueberholt hat -- die Stufenskala saettigt bei
                # 4 mm/h und kann die Verschaerfung nicht sehen. Ohne diese
                # Haelfte bliebe der Alarm aus, nur mit anderem Grund.
                quantitative_escalation=_ueberholt_sperrzeit,
            )
            if not _identity_gate.allowed:
                logger.debug(
                    f"Radar alert suppressed ({_identity_gate.reason}) for trip {trip.id}"
                )
                try:
                    alert_log.append_suppressed_entry(
                        self._user_id, entity_id=trip.id, entity_type="trip",
                        reason=alert_log.REASON_NOWCAST, gate_reason=_identity_gate.reason,
                        effective_channels=effective_channels,
                        # Issue #2050 S4a (AC-9): reist an JEDER Radar-
                        # Unterdrueckungsstelle mit, auch hier -- diese Stufe
                        # liegt NACH dem Abruf, die Angabe ist also bekannt.
                        # Ohne sie waere ein Δ-Registereintrag, der einen Lauf
                        # mit ausgefallener Gewitterpruefung unterdrueckt, vom
                        # Eintrag eines mit durchgefuehrter Pruefung nicht
                        # mehr unterscheidbar.
                        convective_checked=result.convective_checked,
                        **_e1,
                    )
                except Exception as e:
                    logger.error(
                        "Radar alert: Unterdrueckungs-Protokoll (Ereignis-"
                        "Identitaet) fuer Trip %s fehlgeschlagen (%s) — der "
                        "Alarm blieb aus, nur der Protokoll-Eintrag fehlt.",
                        trip.id, e,
                    )
                continue

            # Issue #2018: das Gate hat diese Meldung als NACHTRAG zu einer
            # bereits zugestellten Meldung eingestuft — dieselbe Zustellung
            # wie bisher, nur in anderer FORM. Fehlt der Meldezeitpunkt
            # (fail-soft aus dem Register), entfaellt die Uhrzeit ersatzlos
            # statt eines erfundenen Platzhalters.
            # Issue #2050 S4c (AC-13): die Formulierung wird quellenabhaengig
            # -- ein Δ-Vorgaenger ist KEINE amtliche Warnung, die alte,
            # hartkodierte Formulierung waere fuer ihn falsch.
            if _identity_gate.is_addendum:
                _bezug = (
                    "Ergänzung zur gemeldeten Wetterabweichung"
                    if _identity_gate.addendum_source == "deviation"
                    else "Ergänzung zur amtlichen Warnung"
                )
                if _identity_gate.addendum_reported_at is not None:
                    _bezug += (
                        f" von {local_fmt(_identity_gate.addendum_reported_at, tz)}"
                    )
                _radar_request = replace(_radar_request, addendum_reference=_bezug)

            # Best-Effort-Zustellung über NotificationService (Issue #1023)
            result = self._notification_service.send_radar_alert(
                trip=trip,
                request=_radar_request,
                source=radar_svc.source_label(result.source),
                cooldown_display=cooldown_display,
                effective_channels=_radar_allowed,
                mail_sink=self._mail_sink,
                telegram_style=_trip_telegram_style(trip),
            )
            # Issue #1459: Protokoll VOR dem Zustellbarkeits-Guard; die
            # Ziel-Liste (`entries` vs. `not_delivered`) entscheidet
            # `append_entry()` selbst (D4). `result` traegt hier bereits die
            # NotificationResult — die Nowcast-Auswertung steckt im Request.
            # `effective_channels` bleibt ROH (rote Linie #638).
            # Issue #1948 (S1, AC-4): Korrelation ueber denselben
            # Koordinaten-Schluessel wie get_nowcast() (Zeitfenster =
            # Radar-Cache-TTL, 300s Default).
            from services.radar_service import _nowcast_source_key
            _nowcast_capture_id = alert_input_capture.latest_capture_id(
                "nowcast", _nowcast_source_key(lat, lon), max_age=300.0,
            )
            alert_log.append_entry(
                self._user_id, entity_id=trip.id, entity_type="trip",
                changes_count=1,
                severity=_radar_urgency,
                metrics=alert_log.register_pairs_for_nowcast(
                    _radar_request.is_convective
                ),
                reason=alert_log.REASON_NOWCAST,
                effective_channels=effective_channels,
                sent_channels=result.delivered_channels,
                reachable_channels=result.sent_channels,
                below_threshold_channels=_radar_suppressed,
                blocked_reason_codes=result.blocked_reason_codes,
                capture_id=_nowcast_capture_id,
                # Issue #2018: Nachtraege bleiben im Protokoll auswertbar;
                # ohne Nachtrag entstehen die Felder gar nicht erst.
                is_addendum=_identity_gate.is_addendum,
                addendum_reported_at=(
                    _identity_gate.addendum_reported_at.isoformat()
                    if _identity_gate.addendum_reported_at is not None else None
                ),
                **_e1,
            )
            delivered = result.sent
            if not delivered:
                logger.info(f"Radar alert: kein zustellbarer Kanal für {trip.id}")
                continue

            # Recording nach Best-Effort-Zustellung (F001-Semantik)
            # Issue #1070: nur bei tatsaechlichem Versand zaehlen (F001-Symmetrie)
            # Issue #1213: alleinige Radar-Throttle-Quelle ist der Store — der
            # alert_state-Key `radar_throttle` und die Legacy-Datei
            # `radar_alert_throttle.json` werden nicht mehr geschrieben (nur
            # noch als Migrationsquellen gelesen).
            # Issue #1467 S3: beide Buchungen buendelt jetzt der geteilte
            # Baustein — unveraendert erst NACH der Zustellung.
            record_nowcast_sent(
                user_id=self._user_id, throttle_scope=_RADAR_THROTTLE_SCOPE,
                throttle_key=trip.id, now=datetime.now(timezone.utc),
                zone=anchor_tz(trip, now_utc),
                throttle_store=self._throttle_store,
                # Issue #2065: Vergleichsbasis der naechsten Runde --
                # Selbstbremsung, die naechste Verschaerfung muss den vollen
                # Faktor gegen DIESE Menge erreichen.
                precip_mm=_menge_mm,
                # Issue #2050 S3b: die hoechste heute in dieser Zone
                # ZUGESTELLTE Stufe waechst bei JEDEM Versand mit (nicht nur
                # beim Durchbruch) — sie ist die Vergleichsbasis der naechsten
                # Eskalationspruefung. Der verbrauchte Durchbruch wird nur
                # gebucht, wenn er diesen Lauf auch getragen hat.
                urgency=_radar_urgency,
                is_escalation_breakthrough=_budget_durchbruch,
            )
            # Issue #1467 S4b-1 (AC-2/AC-3, F001-Symmetrie): NUR nach
            # erfolgreicher Zustellung -- ein spaeterer amtlicher Alarm
            # fuer dasselbe Ereignis findet diesen Eintrag ueber
            # `check_event_identity_gate()`.
            record_event_identity(
                user_id=self._user_id, entity_id=trip.id,
                hazard_class=resolve_hazard_class(is_convective=_radar_request.is_convective),
                segment_ids=(
                    [_radar_request.segment_id] if _radar_request.segment_id else []
                ),
                severity=_radar_urgency, point_at=_onset_dt,
                now=datetime.now(timezone.utc),
            )
            sent += 1

        return sent

    def _fetch_fresh_weather(
        self,
        cached_weather: List[SegmentWeatherData],
    ) -> List[SegmentWeatherData]:
        """
        Fetch fresh weather for the same segments.

        Args:
            cached_weather: Cached weather with segment info

        Returns:
            Fresh weather data
        """
        from providers.base import get_provider
        from services.segment_weather import SegmentWeatherService

        # OpenMeteo with automatic regional model selection
        provider = get_provider("openmeteo")

        service = SegmentWeatherService(provider)

        now_utc = datetime.now(timezone.utc)

        fresh_weather = []
        for cached in cached_weather:
            today_utc = now_utc.date()
            if cached.segment.end_time < now_utc:
                continue  # Bereits absolviert — überspringen
            if cached.segment.start_time.date() > today_utc:
                continue  # Beginnt erst morgen oder später — überspringen
            try:
                # Issue #1329: der frühere `service._cache.clear()` erzwang
                # bei JEDEM Alarm-Check einen Upstream-Fetch. Mit dem
                # geteilten Cache (10-Minuten-TTL) ist das nicht mehr nötig
                # -- die maximale Datenalterung ist bereits durch den TTL auf
                # ≤ 10 Minuten begrenzt (AC-6), unabhängig davon, ob ein
                # anderer Aufrufer (z.B. das letzte Briefing) denselben Ort
                # kurz zuvor gefüllt hat. Bewusste Verhaltensänderung:
                # vorher "garantiert taufrisch pro Check", nachher
                # "garantiert ≤ 10 Min alt".
                # Bug #288: Alert-Checks must NOT trigger ensemble-API calls
                # (would consume the daily free-tier quota in ~30 minutes).
                fresh = service.fetch_segment_weather(
                    cached.segment,
                    enrich_ensemble=False,
                    enrich_snow=False,
                    priority="alert_check",
                )
                fresh_weather.append(fresh)
            except Exception as e:
                logger.error(
                    f"Failed to fetch fresh weather for segment "
                    f"{cached.segment.segment_id}: {e}"
                )

        return fresh_weather

    def _send_alert(
        self,
        trip: "Trip",
        weather: List[SegmentWeatherData],
        changes: List[WeatherChange],
        official_notices: Optional[list] = None,
        corridor_hits: Optional[List[CorridorHit]] = None,
        reference_at: Optional[str] = None,
    ) -> "NotificationResult":
        """
        Format and send alert via all configured effective channels.

        Issue #1023: Rendering und Versand werden an den NotificationService
        delegiert; TripAlertService kennt keine Renderer-/Transport-Details mehr.
        Issue #1088: liegen `official_notices` vor, werden sie in dieselbe
        Nachricht gebündelt (kein zweiter Versand). Issue #1444 S1: dasselbe
        gilt fuer `corridor_hits` (Schwellen-Treffer, Muster #1088).

        Returns:
            Die volle `NotificationResult`. `result.sent` ist True, sobald
            mindestens ein konfigurierter Kanal erreichbar war; Sendefehler auf
            einem konfigurierten Kanal werden geloggt, unterdruecken das
            Recording aber NICHT (Best-Effort, Anti-Pattern #656). Issue #1459:
            der Aufrufer braucht zusaetzlich `sent_channels`/`failed_channels`
            fuers Alarm-Protokoll, deshalb die volle Ruecksage statt nur `bool`.
        """
        # Issue #638: Effective channels — per-alert override beats briefing channels.
        effective_channels = self._effective_alert_channels(trip)

        # Issue #1461 S3b-2a: die Kanal-Schwelle filtert NUR den tatsaechlichen
        # Versand (allowed), nie das rohe Opt-in -- das bleibt fuer den
        # Aufrufer (check_and_send_alerts -> alert_log.append_entry) unveraendert
        # ueber `effective_channels` erreichbar (rote Linie #638).
        urgency = alert_urgency.highest_urgency(
            alert_urgency.urgency_from_changes(changes),
            *[
                alert_urgency.urgency_from_official_level(a.level)
                for a, _segment_ids in (official_notices or [])
            ],
        )
        allowed, suppressed = alert_channel_threshold.split_by_threshold(
            effective_channels, urgency, trip.alert_channel_thresholds,
        )
        self._last_below_threshold_channels = suppressed

        result = self._notification_service.send_deviation_alert(
            trip=trip,
            weather=weather,
            changes=changes,
            effective_channels=allowed,
            official_notices=official_notices or [],
            mail_sink=self._mail_sink,
            telegram_style=_trip_telegram_style(trip),
            corridor_hits=corridor_hits or [],
            reference_at=reference_at,
        )

        if result.sent:
            logger.info(
                f"Alert sent for trip {trip.name}: {len(changes)} changes detected "
                f"via channels={sorted(result.sent_channels)}"
            )
            self._record_official_alert_state(trip.id, official_notices or [])

        return result

    def check_official_alert_triggers(
        self, trip: "Trip", now_utc: Optional[datetime] = None,
    ) -> list:
        """Issue #1088/#1200: liefert amtliche Warnungen, die NEU sind oder deren

        Level gestiegen ist ggü. dem letzten gemeldeten Stand (alert_state),
        getaggt mit den betroffenen Segment-IDs als
        `list[tuple[OfficialAlert, list[str]]]` (Issue #1200 — Segment-Bezug
        in der Standalone-Alert-Mail).
        Fail-soft: Toggle-Gate zuerst, Quellenfehler werden bereits von
        get_official_alerts_for_location() pro Quelle abgefangen. Schreibt
        nach erfolgreichem Versand KEINEN alert_state selbst — das übernimmt
        der Aufrufer (Konsistenz mit dem Wetter-Delta-Pfad). Ausnahme (Issue
        #1685): bei einer stillen Fenster-Revision (Warnung derselben
        Identität+Gefahr, echte Überlappung, keine Eskalation/Vorverlegung
        ≥2h) schreibt diese Methode das Melde-Gedächtnis SOFORT fort — sonst
        vergleicht ein drittes Kettenglied gegen das veraltete, erste Fenster
        und meldet fälschlich erneut.

        Issue #1697: `now_utc` reicht die "Jetzt"-Sekunde des Laufs an
        `_get_cached_weather` durch (Default: echte Wanduhr, s. dortiger
        Docstring).
        """
        # Issue #1258: official_warnings.enabled loest das Legacy-Feld ab.
        # official_warnings is None -> Trip noch nicht migriert -> Fallback auf
        # das bisherige Ist-Verhalten (kein Bestandsnutzer verliert Alarme).
        # Fix-Loop F003: ein leeres {} (kein "enabled"-Schluessel, z.B.
        # Datenmuell/nicht abgeschlossene Migration) zaehlt NICHT als
        # migriert -> ebenfalls Legacy-Fallback statt stillem Default True.
        if isinstance(trip.official_warnings, dict) and "enabled" in trip.official_warnings:
            if not trip.official_warnings.get("enabled", True):
                return []
        elif trip.official_alert_triggers_enabled is False:
            return []
        from services.alert_state import AlertStateService
        from services.official_alerts import get_official_alerts_for_location

        # #1661 Spec-Korrektur 2026-08-10: KEINE Tages-Pruefung auf diesem Pfad.
        # `cached` dient hier nur als Routen-Geometrie mit absoluten Zeiten; der
        # feinere Zeitfilter pro Etappe steht unten (`end_time < now_utc`).
        # Begruendung ausfuehrlich im Docstring von `_get_cached_weather`.
        cached = self._get_cached_weather(
            trip, tagesgleicher_anker_noetig=False, now_utc=now_utc,
        )
        if not cached:
            return []

        # Issue #1460 (P4): Ort UND Zeit gehoeren zusammen. Jedes Segment der
        # Restroute bekommt sein EIGENES Zeitfenster `[max(jetzt, Start), Ende]`
        # -- eine Warnung, die erst in drei Tagen gilt, gehoert nicht zur
        # heutigen Etappe, sondern zu der, auf der der Nutzer dann steht.
        # Bereits vollstaendig vergangene Segmente werden nicht mehr abgefragt.
        #
        # Die Pruefreichweite bleibt bewusst die GESAMTE Restroute (anders als
        # der Nowcast-Pfad `check_radar_alerts()`, der nur ein Segment waehlt):
        # amtliche Warnungen haben Tage Vorlauf, eine Verengung auf ein Segment
        # wuerde genau die Vorwarnung fuer spaetere Etappen verschlucken.
        #
        # Issue #1200: Segment-Zuordnung VOR dem Dedup aufbauen. Der
        # Dedup-Schluessel ist seit #1460 `(Koordinate, Fenster)` statt der
        # blossen Koordinate -- sonst fallen zwei Etappen an DERSELBEN
        # Koordinate zu VERSCHIEDENEN Zeiten zusammen und eine der beiden
        # verliert ihre Warnzeit still.
        now_utc = datetime.now(timezone.utc)
        group_segments: dict[tuple, list[str]] = {}
        group_order: list[tuple] = []
        for sw in cached:
            if sw.has_error:
                continue
            segment = sw.segment
            end_time = _as_aware_utc(segment.end_time)
            start_time = _as_aware_utc(segment.start_time)
            if end_time is None or end_time < now_utc:
                continue  # Etappe vorbei -- ihre Warnzeit ist um
            coord = (round(segment.start_point.lat, 3), round(segment.start_point.lon, 3))
            window_start = max(now_utc, start_time) if start_time else now_utc
            key = (coord, window_start, end_time)
            if key not in group_segments:
                group_segments[key] = []
                group_order.append(key)
            group_segments[key].append(str(segment.segment_id))

        tagged_alerts: list[tuple] = []
        for key in group_order:
            coord, window_start, window_end = key
            segment_ids = group_segments[key]
            try:
                for alert in get_official_alerts_for_location(
                    *coord, window_start=window_start, window_end=window_end, now=now_utc,
                ):
                    tagged_alerts.append((alert, segment_ids))
            except Exception as e:
                logger.warning(f"official_alert_triggers: Quelle fehlgeschlagen fuer {trip.id}: {e}")

        from output.renderers.alert.official_alerts import (
            dedupe_official_alerts,
            official_alert_state_key,
            official_alert_revision_verdict,
        )
        tagged_alerts = dedupe_official_alerts(tagged_alerts)

        state_svc = AlertStateService(user_id=self._user_id)
        state = state_svc.load(trip.id)
        new_or_escalated = []
        state_changed = False
        for a, segment_ids in tagged_alerts:
            should_report, stale_key, merged_entry = official_alert_revision_verdict(a, state)
            if should_report:
                new_or_escalated.append((a, segment_ids))
            elif merged_entry is not None:
                # Issue #1685: stille Fenster-Revision -- Fortschreibung sofort,
                # sonst vergleicht ein drittes Kettenglied gegen das veraltete,
                # erste Fenster und meldet faelschlich erneut.
                del state[stale_key]
                state[official_alert_state_key(a)] = merged_entry
                state_changed = True
        if state_changed:
            state_svc.save(trip.id, state)
        return new_or_escalated

    def _record_official_alert_state(self, trip_id: str, official_notices: list) -> None:
        """Issue #1088/#1200: alert_state nach erfolgreichem Versand fortschreiben
        (Dedupe). `official_notices` sind `(OfficialAlert, segment_ids)`-Tupel.

        Issue #1614 Teil 1: dünner Wrapper um die geteilte Schreib-Logik in
        `services.alert_briefing_anchor.record_official_alerts_reported` —
        Verhalten unverändert (AC-5), Segment-IDs werden hier nicht gebraucht.
        """
        if not official_notices:
            return
        from services.alert_briefing_anchor import record_official_alerts_reported

        record_official_alerts_reported(
            user_id=self._user_id, entity_id=trip_id,
            alerts=[a for a, _segment_ids in official_notices],
        )

    def _send_official_alert_only(
        self, trip: "Trip", official_notices: list, segments: Optional[list] = None,
    ) -> bool:
        """Issue #1088: Standalone-Versand einer amtlichen Warnung ohne Wetter-Delta.

        Reproduziert nur die generischen Sicherheits-Gates (QuietHours,
        Tageslimit) — NICHT die weather-delta-spezifischen Gates
        (has_active_rules, _filter_significant_changes), da ein eigenständiger
        amtlicher Trigger laut PO-Entscheidung unabhängig vom Wetter-Delta feuern soll.

        Issue #1467 S4a: die beiden verbliebenen Stufen stehen im geteilten
        Baustein `check_official_alert_gate` — derselbe, den auch der amtliche
        Ortsvergleich-Pfad ruft. Die Sperrzeit ist dabei ersatzlos ENTFALLEN
        (E1): sie las den Topf `"trip"`, den der Änderungsalarm befüllt, und
        verschluckte damit bis zu 120 Minuten lang jede amtliche Eskalation.
        Geschrieben wird der Topf weiterhin (s. unten) — nur gelesen nicht mehr.
        """
        now_utc = datetime.now(timezone.utc)
        # Issue #2050 S3b (Szenario 10, AC-5, Luecke E3): `check_official_alert_gate`
        # liefert den passenden Grund seit jeher mit — bis dahin verwarf ihn
        # der Aufrufer. Jetzt wird er weitergereicht statt verschluckt.
        _gate = check_official_alert_gate(
            user_id=self._user_id,
            quiet_from=trip.alert_quiet_from, quiet_to=trip.alert_quiet_to,
            context_label=trip.id, now=now_utc, zone=anchor_tz(trip, now_utc),
        )
        if not _gate.allowed:
            self._protokolliere_unterdrueckung(
                trip, reason=alert_log.REASON_OFFICIAL_ALERT,
                gate_reason=_gate.reason,
            )
            return False
        # Issue #1594: dieselbe Stufe wie im Aenderungspfad, gleiche Position
        # (nach der Ruhezeit) — die Warnung erscheint im Briefing, das
        # unmittelbar folgt (AC-16), statt zusaetzlich als eigene Nachricht.
        # Bleibt ein EIGENER Aufruf nach dem Gate (#1467 S4a AC-12), nicht in
        # den Baustein verschmolzen.
        if self._is_briefing_imminent(trip, now_utc):
            logger.debug(f"Official alert suppressed: briefing imminent for trip {trip.id}")
            return False

        effective_channels = self._effective_alert_channels(trip)

        # Issue #1467 S4b-1: Ereignis-Identitaet PRO Alert (Batch-Filterung,
        # AC-17) -- ein Gate-Aufruf ueber die GANZE Liste waere in beide
        # Richtungen falsch: alles durchlassen liesse die Nowcast-Dublette
        # bestehen, alles sperren wuerde eine zweite, eigenstaendige Warnung
        # im selben Lauf mit verschlucken (Fehlerrichtung "Alarm bleibt
        # aus"). `_official_urgency` wird deshalb ERST NACH dem Filtern aus
        # der verbleibenden Liste neu berechnet. Letzte Stufe vor dem Versand
        # (AC-12), kanaluebergreifend (V3: VOR `split_by_threshold`, AC-11).
        _filtered_notices = []
        for _alert, _segment_ids in official_notices:
            _hazard_class = resolve_hazard_class(hazard=_alert.hazard)
            _severity = alert_urgency.urgency_from_official_level(_alert.level)
            _identity_gate = check_event_identity_gate(
                user_id=self._user_id, entity_id=trip.id,
                hazard_class=_hazard_class, segment_ids=_segment_ids,
                severity=_severity, now=now_utc,
                window_start=_alert.valid_from, window_end=_alert.valid_to,
            )
            if _identity_gate.allowed:
                _filtered_notices.append((_alert, _segment_ids))
                continue
            logger.debug(
                f"Official alert suppressed ({_identity_gate.reason}) for trip {trip.id}"
            )
            try:
                # Issue #2050 S6 (E-1): hier liegt GENAU EINE Warnung vor --
                # Ereigniszeit und Quelle sind bekannt, der Messpunkt nur,
                # wenn ihre Segmentliste eindeutig ist. Vorwarnzeit und
                # Vergleichsbasis kennt der amtliche Zweig strukturell nicht.
                _e1_segment_id = alert_log.unique_or_none(_segment_ids)
                alert_log.append_suppressed_entry(
                    self._user_id, entity_id=trip.id, entity_type="trip",
                    reason=alert_log.REASON_OFFICIAL_ALERT,
                    gate_reason=_identity_gate.reason,
                    effective_channels=effective_channels,
                    event_at=(
                        _alert.valid_from.isoformat() if _alert.valid_from else None
                    ),
                    event_end_at=(
                        _alert.valid_to.isoformat() if _alert.valid_to else None
                    ),
                    measurement_point=(
                        {"segment_id": _e1_segment_id}
                        if _e1_segment_id is not None else None
                    ),
                    source=_alert.source,
                )
            except Exception as e:
                logger.error(
                    "Official alert: Unterdrueckungs-Protokoll (Ereignis-"
                    "Identitaet) fuer Trip %s fehlgeschlagen (%s) — der "
                    "Alarm blieb aus, nur der Protokoll-Eintrag fehlt.",
                    trip.id, e,
                )
        if not _filtered_notices:
            return False
        official_notices = _filtered_notices

        # Issue #1461 S3b-2a: dieselbe Naht wie in `_send_alert()` -- die
        # Schwelle filtert nur den Versand, `effective_channels` bleibt ROH
        # fuers Protokoll (rote Linie #638).
        _official_urgency = alert_urgency.highest_urgency(*[
            alert_urgency.urgency_from_official_level(a.level)
            for a, _segment_ids in official_notices
        ])
        _official_allowed, _official_suppressed = alert_channel_threshold.split_by_threshold(
            effective_channels, _official_urgency, trip.alert_channel_thresholds,
        )
        result = self._notification_service.send_official_alert(
            trip=trip,
            notices=official_notices,
            effective_channels=_official_allowed,
            mail_sink=self._mail_sink,
            telegram_style=_trip_telegram_style(trip),
            # Issue #2036 (AC-3): dieselbe Ortsquelle wie Nowcast- und
            # Abweichungsalarm. Ohne Segmente (kein Anker) bleibt die Karte
            # leer und die Warnung bei der Segment-Sprache (AC-10).
            segment_km=measured_segment_km(segments),
        )
        # Issue #2050 S6 (E-1): Ereigniszeit, Messpunkt und Quelle nur, wenn
        # ALLE Warnungen dieses EINEN Eintrags darin uebereinstimmen
        # (`unique_or_none`) -- sonst behauptete der Eintrag willkuerlich eine
        # von mehreren. Vorwarnzeit und Vergleichsbasis kennt dieser Zweig
        # strukturell nicht.
        _e1_valid_from = alert_log.unique_or_none(
            a.valid_from for a, _segment_ids in official_notices
        )
        _e1_valid_to = alert_log.unique_or_none(
            a.valid_to for a, _segment_ids in official_notices
        )
        _e1_segment_id = alert_log.unique_or_none(
            sid for _a, _segment_ids in official_notices for sid in (_segment_ids or [])
        )
        # Issue #1459: amtliche Warnungen tragen ihre Gefahrenart in `hazards`,
        # NICHT als Register-Kennung in `metrics` (eigenes Vokabular, O1).
        alert_log.append_entry(
            self._user_id, entity_id=trip.id, entity_type="trip",
            changes_count=len(official_notices),
            severity=_official_urgency,
            hazards=alert_log.hazards_from_official_alerts(
                [a for a, _segment_ids in official_notices]
            ),
            reason=alert_log.REASON_OFFICIAL_ALERT,
            effective_channels=effective_channels,
            sent_channels=result.delivered_channels,
            reachable_channels=result.sent_channels,
            below_threshold_channels=_official_suppressed,
            blocked_reason_codes=result.blocked_reason_codes,
            event_at=_e1_valid_from.isoformat() if _e1_valid_from else None,
            event_end_at=_e1_valid_to.isoformat() if _e1_valid_to else None,
            measurement_point=(
                {"segment_id": _e1_segment_id} if _e1_segment_id is not None else None
            ),
            source=alert_log.unique_or_none(
                a.source for a, _segment_ids in official_notices
            ),
            # Issue #1944: Herkunft der versendeten Warnungen (ein Mitschnitt
            # -> `capture_id`, mehrere -> `capture_ids`).
            **alert_log.capture_kwargs_from_alerts(
                [a for a, _segment_ids in official_notices]
            ),
        )
        if result.sent:
            self._record_official_alert_state(trip.id, official_notices)
            self._throttle_store.record("trip", trip.id, datetime.now(timezone.utc))
            alert_daily_limit.increment(
                self._user_id, now_utc, anchor_tz(trip, now_utc),
            )
            # Issue #1467 S4b-1 (AC-2/AC-3, F001-Symmetrie): NUR nach
            # erfolgreicher Zustellung -- ein spaeterer Nowcast fuer dasselbe
            # Ereignis findet diesen Eintrag ueber
            # `check_event_identity_gate()`. Hazards ausserhalb des
            # `wet`-Kanons (hazard_class=None) werden bewusst NICHT
            # registriert -- ein Registereintrag ohne Klasse kaeme nie zum
            # Zuge (kein Praefix-Match moeglich).
            for _alert, _segment_ids in official_notices:
                _hazard_class = resolve_hazard_class(hazard=_alert.hazard)
                if _hazard_class is None:
                    continue
                record_event_identity(
                    user_id=self._user_id, entity_id=trip.id,
                    hazard_class=_hazard_class, segment_ids=_segment_ids,
                    severity=alert_urgency.urgency_from_official_level(_alert.level),
                    window_start=_alert.valid_from, window_end=_alert.valid_to,
                    now=datetime.now(timezone.utc),
                )
        return result.sent

    def _effective_alert_channels(self, trip: "Trip") -> set[str]:
        """Issue #638: Compute effective alert channels for a trip.

        Semantik: Union über jede aktive Regel ihrer individuell effektiven Kanäle.
        Pro Regel: rule.channels falls nicht leer, SONST geerbte Briefing-Kanäle aus
        report_config. Kein globaler Override-Shortcut — sonst verschluckt ein Trip mit
        [Regel-A: telegram, Regel-B: []/briefing-email] den E-Mail-Kanal von Regel-B.

        Legacy-Pfad (keine aktiven alert_rules): erbt die Briefing-Kanäle aus
        report_config; falls report_config None ist → Default {"email"} (altes Verhalten:
        "not report_config or report_config.send_email" → E-Mail-Default nur bei
        report_config=None; existiert report_config mit allen Kanälen aus, wird nichts
        versendet — der Nutzer hat explizit alle Kanäle abgeschaltet).

        Issue #1258 S3 (D2): ist `trip.alert_channels` gesetzt (dict mit
        email/telegram/sms bool-Keys), ersetzt es NUR den geerbten
        Briefing-Anteil (an beiden Stellen unten, Legacy-Pfad UND
        per-Regel-Fallback) — nicht-leere `rule.channels`-Overrides (#638)
        gewinnen unverändert weiter, das SMS-Tier-Gate bleibt aktiv.
        `alert_channels=None` liefert exakt das bisherige Verhalten.

        Returns:
            Set of channel names ("email", "telegram", "sms") to use for alert dispatch.
        """
        active_rules = [r for r in (trip.alert_rules or []) if r.enabled]
        briefing = self._briefing_channels(trip.report_config)

        if trip.alert_channels is not None:
            # Scharfes Kanal-Set ersetzt den geerbten Briefing-Anteil vollständig
            # (auch wenn alle drei Kanäle aus sind — bewusst kein {"email"}-Default,
            # der Nutzer hat explizit konfiguriert).
            inherited = {
                ch for ch in ("email", "telegram", "sms", "premium_sms")
                if trip.alert_channels.get(ch)
            }
        else:
            # Legacy-Pfad: E-Mail-Default gilt NUR wenn report_config None ist
            # (kein explizites Ausschalten).
            inherited = briefing if (briefing or trip.report_config is not None) else {"email"}

        # Legacy-Pfad: keine aktiven alert_rules → erbe die (ggf. ersetzten) Kanäle.
        if not active_rules:
            channels = inherited
        else:
            channels = set()
            for rule in active_rules:
                if rule.channels:
                    channels.update(rule.channels)
                else:
                    channels.update(inherited)

        if "sms" in channels and not sms_allowed(self._user_id):
            channels = channels - {"sms"}
        if "premium_sms" in channels and not premium_sms_allowed(self._user_id):
            channels = channels - {"premium_sms"}
        return channels

    @staticmethod
    def _briefing_channels(config) -> set[str]:
        """Return the set of active briefing channels from report_config (or empty set)."""
        channels: set[str] = set()
        if config is None:
            return channels
        if config.send_email:
            channels.add("email")
        if config.send_telegram:
            channels.add("telegram")
        if getattr(config, "send_sms", False):
            channels.add("sms")
        if getattr(config, "send_premium_sms", False):
            channels.add("premium_sms")
        return channels
