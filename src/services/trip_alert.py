"""
Trip alert service - sends immediate alerts on significant weather changes.

Feature 3.4: Alert bei Änderungen (Story 3)
Detects significant weather changes and sends alert emails with throttling.

SPEC: docs/specs/modules/trip_alert.md v2.0
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, List, Optional

from app.config import Settings
from app.models import SegmentWeatherData, WeatherChange
from services import alert_channel_threshold, alert_daily_limit, alert_log
import services.alert_urgency as alert_urgency
from services.deviation_alert_engine import DeviationAlertEngine
from services.notification_service import (
    NotificationResult,
    NotificationService,
    RadarAlertRequest,
)
from services.point_weather import AlertEvaluationConfig, TripSegmentWeatherAdapter
from services.corridor_threshold import CorridorHit
from services.throttle_store import ThrottleStore
from services.user_tier import sms_allowed
from services.weather_change_detection import WeatherChangeDetectionService
from utils.timezone import tz_for_coords

if TYPE_CHECKING:
    from app.trip import Trip

logger = logging.getLogger("trip_alert")

# Gesamt-Zeitbudget je check_all_trips()-Lauf (Issue #1447): der
# Go-Scheduler wartet pro Nutzer maximal 120s (scheduler.go:82) und bricht
# danach die HTTP-Verbindung ab, ohne dass der Python-Lauf davon erfaehrt.
# 90s Reserve gegenueber diesen 120s, analog FETCH_DEADLINE_SECONDS in
# providers/meteofrance.py und providers/dwd.py.
ALERT_RUN_DEADLINE_SECONDS = 90.0

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
    """Return True when rain onset is within threshold_min minutes."""
    onset = getattr(result, "onset_minutes", None)
    return onset is not None and onset <= threshold_min


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
        if self._is_quiet_hours(trip, datetime.now(timezone.utc)):
            logger.debug(f"Alert suppressed: quiet hours active for trip {trip.id}")
            return False

        # 1b. Throttle-Check mit per-trip Cooldown (AC-2/3)
        if self._is_throttled_with_cooldown(trip):
            logger.debug(f"Alert throttled for trip {trip.id}")
            return False

        # 1c. Issue #1070: Tages-Obergrenze nach Nutzerlevel (Free/Standard/Premium)
        if not alert_daily_limit.is_allowed(self._user_id, datetime.now(timezone.utc)):
            logger.debug(f"Alert suppressed: daily limit reached for trip {trip.id}")
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
            return False

        logger.info(
            f"Detected {len(to_report)} significant changes for trip {trip.id}"
        )

        # 5. Send alert; guard: only record throttle/log when at least one
        # configured channel was reachable (AC-1 symmetry with Telegram/Radar).
        notif_result = self._send_alert(
            trip, fresh_weather, to_report, official_notices=official_notices,
        )
        # Issue #1459: Alarm-Protokoll VOR dem Zustellbarkeits-Guard — die
        # Funktion entscheidet selbst, ob der Eintrag nach `entries` (mindestens
        # ein Kanal kam an, Ist-Verhalten) oder nach `not_delivered` geht (D4).
        alert_log.append_entry(
            self._user_id,
            entity_id=trip.id,
            entity_type="trip",
            changes_count=len(to_report),
            severity=alert_urgency.highest_urgency(
                alert_urgency.urgency_from_changes(to_report),
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

        # 7. Update throttle (only on success) + persist
        self._throttle_store.record("trip", trip.id, datetime.now(timezone.utc))
        # Issue #1070: nur bei tatsaechlichem Versand zaehlen (F001-Symmetrie)
        alert_daily_limit.increment(self._user_id, datetime.now(timezone.utc))

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
        from datetime import date as date_type

        from app.loader import load_all_trips

        today = date_type.today()
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

            # Skip if no cached weather available
            cached = self._get_cached_weather(trip)
            if not cached:
                continue

            # Issue #1088: amtliche Warnungen zusätzlich zum Wetter-Delta prüfen —
            # fail-soft, darf den Zyklus für andere Trips nicht abbrechen.
            official_notices: list = []
            try:
                official_notices = self.check_official_alert_triggers(trip)
            except Exception as e:
                logger.error(f"Official alert trigger check failed for trip {trip.id}: {e}")

            try:
                weather_sent = self.check_and_send_alerts(
                    trip, cached, official_notices=official_notices,
                )
                if weather_sent:
                    alerts_sent += 1
                elif official_notices:
                    # Kein Wetter-Delta-Alert gefeuert, aber neue/gestiegene amtliche
                    # Warnung(en) — eigenständiger Versand (PO-Entscheidung).
                    if self._send_official_alert_only(trip, official_notices):
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

    def _get_cached_weather(self, trip: "Trip") -> Optional[List[SegmentWeatherData]]:
        """
        Get cached weather data for a trip from the weather snapshot.

        Loads the dated snapshot for today first (written by morning briefing with
        target_date=today). Falls back to the undated snapshot only when no dated
        file exists yet (first-run / migration). This prevents alerts from using the
        evening briefing snapshot, which has target_date=tomorrow and would cause the
        alert to compare today's nowcast against tomorrow's stage. (Issue #823)

        Args:
            trip: Trip to get cached weather for

        Returns:
            Cached weather data or None if not available
        """
        try:
            from services.weather_snapshot import WeatherSnapshotService

            svc = WeatherSnapshotService(user_id=self._user_id)
            today = date.today()
            dated = svc.load_dated(trip.id, today)
            if dated is not None:
                return dated
            # Fallback: undated snapshot (may be stale after evening briefing)
            return svc.load(trip.id)
        except Exception as e:
            logger.debug(f"No cached weather for trip {trip.id}: {e}")
            return None

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
        """
        return DeviationAlertEngine.is_quiet_hours(
            now, trip.alert_quiet_from, trip.alert_quiet_to,
            context_label=trip.id,
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

    def _is_radar_throttled(self, trip_id: str, cooldown_min: int = 120) -> bool:
        """Return True if radar alert was sent within cooldown window (Issue #818 AC-6).

        Issue #1213: liest jetzt aus dem gemeinsamen ThrottleStore statt aus
        dem alert_state-Key `radar_throttle` (nur noch Migrationsquelle).
        """
        return self._throttle_store.is_throttled(
            "radar", trip_id, cooldown_min, datetime.now(timezone.utc)
        )

    def clear_radar_throttle(self, trip_id: str) -> None:
        """Clear radar throttle for a trip (test helper)."""
        self._throttle_store.clear("radar", trip_id)

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
        onset_hour = onset_dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
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
        from datetime import date as date_type
        from app.loader import load_all_trips
        from services.trip_segments import convert_trip_to_segments

        today = date_type.today()
        now_utc = datetime.now(timezone.utc)
        sent = 0

        for trip in load_all_trips(user_id=self._user_id):
            # Segment-Auswahl (Issue #822 — ersetzt stage.waypoints[0])
            segments = convert_trip_to_segments(trip, today)
            if not segments:
                continue

            # Aktives Segment: erstes mit start_time <= now_utc <= end_time
            active = None
            for seg in segments:
                if seg.start_time <= now_utc <= seg.end_time:
                    active = seg
                    break

            if active is None:
                if now_utc < segments[0].start_time:
                    active = segments[0]   # vor allen Segmenten → erstes
                else:
                    # Alle Segmente zeitlich vorbei → kein Alert (Option Y der Spec)
                    logger.debug(
                        f"Radar alert skipped: alle Segmente vorbei fuer {trip.id}"
                    )
                    continue

            # QuietHours check (reuse existing)
            if self._is_quiet_hours(trip, now_utc):
                logger.debug(f"Radar alert suppressed (quiet hours) for trip {trip.id}")
                continue

            cooldown_min = (
                trip.alert_cooldown_minutes
                if trip.alert_cooldown_minutes is not None
                else self._throttle_hours * 60
            )
            if self._is_radar_throttled(trip.id, cooldown_min=cooldown_min):
                logger.debug(f"Radar alert throttled for trip {trip.id}")
                continue

            # Issue #1070: Tages-Obergrenze nach Nutzerlevel (Free/Standard/Premium)
            if not alert_daily_limit.is_allowed(self._user_id, datetime.now(timezone.utc)):
                logger.debug(f"Radar alert suppressed: daily limit reached for trip {trip.id}")
                continue

            # Genau EIN get_nowcast-Call pro Trip an Segment-Startpunkt
            lat = active.start_point.lat
            lon = active.start_point.lon
            tz = tz_for_coords(lat, lon)
            try:
                radar_svc = self._get_radar_service()
                # Issue #1329 C2: Scheduler-Radar ist ein polling-Check
                # (drosselbar bei Budget-Druck) -- kein Nutzer-Briefing.
                result = radar_svc.get_nowcast(lat, lon, priority="polling")
            except Exception as e:
                logger.error(f"Radar nowcast failed for trip {trip.id}: {e}")
                continue

            if not radar_alert_due(result, threshold_min=20):
                continue

            # Briefing-Vergleich (Issue #818 AC-1/AC-2/AC-3)
            from services.weather_snapshot import WeatherSnapshotService
            _snapshot = WeatherSnapshotService(self._user_id).load_dated(trip.id, today)
            _onset_dt = now_utc + timedelta(minutes=result.onset_minutes)
            _briefing_precip = self._briefing_precip_for_onset(_snapshot, active.segment_id, _onset_dt)
            _briefing_announced = (_briefing_precip is not None and _briefing_precip >= 0.5)
            # Sicherheits-Override (Slice 4, #883): konvektive Gefahr (Gewitter/Hagel)
            # durchbricht die Briefing-Unterdrückung. Normaler (nicht-konvektiver)
            # angekündigter Regen bleibt unterdrückt (reines Δ-Modell).
            if _briefing_announced and not result.is_convective:
                logger.debug(
                    f"Radar alert suppressed: briefing had {_briefing_precip} mm for {trip.id}"
                )
                continue

            # Doppel-Alert-Guard (Issue #818 AC-4)
            from services.alert_state import AlertStateService
            _guard_state = AlertStateService(self._user_id).load(trip.id)
            _double_suppressed = False
            for _gkey in [f"precip:{active.segment_id}", f"thunder_level_max:{active.segment_id}"]:
                _gentry = _guard_state.get(_gkey)
                if _gentry:
                    try:
                        _glast = datetime.fromisoformat(_gentry["reported_at"])
                        if _glast.tzinfo is None:
                            _glast = _glast.replace(tzinfo=timezone.utc)
                        if datetime.now(timezone.utc) - _glast < timedelta(minutes=cooldown_min):
                            _double_suppressed = True
                            break
                    except (KeyError, ValueError):
                        pass
            if _double_suppressed:
                logger.debug(f"Radar alert suppressed by double-alert guard for {trip.id}")
                continue

            # Kein Kanal konfiguriert → kein Alert (nichts zu recorden)
            can_email = self._settings.can_send_email()
            can_telegram = self._settings.can_send_telegram()
            can_sms = self._settings.can_send_sms()
            if not can_email and not can_telegram and not can_sms:
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
            _onset_time_str = (now_utc + timedelta(minutes=result.onset_minutes)).astimezone(tz).strftime("%H:%M")
            _radar_request = RadarAlertRequest(
                onset_minutes=result.onset_minutes,
                onset_time=_onset_time_str,
                km_from=active.start_point.distance_from_start_km,
                km_to=active.end_point.distance_from_start_km,
                is_convective=result.is_convective,
                intensity_label=_label,
                source_label=radar_svc.source_label(result.source),
                briefing_context=_briefing_context,
                tz=tz,
            )

            config = trip.report_config

            # Issue #1023: Kanal-Set für NotificationService bauen; der Service prüft
            # selbst can_send_*(). Trip-Ebene darf Kanäle explizit deaktivieren.
            effective_channels: set[str] = set()
            if can_email and (not config or getattr(config, "send_email", True)):
                effective_channels.add("email")
            if can_telegram and config and getattr(config, "send_telegram", False):
                effective_channels.add("telegram")
            if can_sms and config and getattr(config, "send_sms", False) and sms_allowed(self._user_id):
                effective_channels.add("sms")

            if not effective_channels:
                logger.info(f"Radar alert: alle Kanäle auf Trip-Ebene deaktiviert, kein Recording für {trip.id}")
                continue

            # Issue #1461 S3b-2a: eigenstaendige Inline-Ableitung (Kontext-
            # Risiko 5) -- ruft `_effective_alert_channels()` bewusst NICHT
            # auf, muss die Kanal-Schwelle deshalb hier ERNEUT anwenden, sonst
            # bleibt der Regenradar-Pfad dauerhaft ungefiltert.
            _radar_urgency = alert_urgency.urgency_from_radar(
                is_convective=_radar_request.is_convective,
                intensity_label=_radar_request.intensity_label,
            )
            _radar_allowed, _radar_suppressed = alert_channel_threshold.split_by_threshold(
                effective_channels, _radar_urgency, trip.alert_channel_thresholds,
            )

            # Best-Effort-Zustellung über NotificationService (Issue #1023)
            result = self._notification_service.send_radar_alert(
                trip=trip,
                request=_radar_request,
                source=radar_svc.source_label(result.source),
                cooldown_display=cooldown_display,
                effective_channels=_radar_allowed,
                mail_sink=self._mail_sink,
            )
            # Issue #1459: Protokoll VOR dem Zustellbarkeits-Guard; die
            # Ziel-Liste (`entries` vs. `not_delivered`) entscheidet
            # `append_entry()` selbst (D4). `result` traegt hier bereits die
            # NotificationResult — die Nowcast-Auswertung steckt im Request.
            # `effective_channels` bleibt ROH (rote Linie #638).
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
            )
            delivered = result.sent
            if not delivered:
                logger.info(f"Radar alert: kein zustellbarer Kanal für {trip.id}")
                continue

            # Recording nach Best-Effort-Zustellung (F001-Semantik)
            # Issue #1070: nur bei tatsaechlichem Versand zaehlen (F001-Symmetrie)
            alert_daily_limit.increment(self._user_id, datetime.now(timezone.utc))
            # Issue #1213: alleinige Radar-Throttle-Quelle ist jetzt der Store —
            # der alert_state-Key `radar_throttle` und die Legacy-Datei
            # `radar_alert_throttle.json` werden nicht mehr geschrieben (nur
            # noch als Migrationsquellen gelesen).
            self._throttle_store.record("radar", trip.id, datetime.now(timezone.utc))
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
        )

        if result.sent:
            logger.info(
                f"Alert sent for trip {trip.name}: {len(changes)} changes detected "
                f"via channels={sorted(result.sent_channels)}"
            )
            self._record_official_alert_state(trip.id, official_notices or [])

        return result

    def check_official_alert_triggers(self, trip: "Trip") -> list:
        """Issue #1088/#1200: liefert amtliche Warnungen, die NEU sind oder deren

        Level gestiegen ist ggü. dem letzten gemeldeten Stand (alert_state),
        getaggt mit den betroffenen Segment-IDs als
        `list[tuple[OfficialAlert, list[str]]]` (Issue #1200 — Segment-Bezug
        in der Standalone-Alert-Mail).
        Fail-soft: Toggle-Gate zuerst, Quellenfehler werden bereits von
        get_official_alerts_for_location() pro Quelle abgefangen. Schreibt
        KEINEN alert_state — das übernimmt der Aufrufer erst nach
        erfolgreichem Versand (Konsistenz mit dem Wetter-Delta-Pfad).
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

        cached = self._get_cached_weather(trip)
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
        )
        tagged_alerts = dedupe_official_alerts(tagged_alerts)

        state = AlertStateService(user_id=self._user_id).load(trip.id)
        new_or_escalated = []
        for a, segment_ids in tagged_alerts:
            key = official_alert_state_key(a)
            prev = state.get(key)
            if prev is None or a.level > prev.get("last_reported_value", 0):
                new_or_escalated.append((a, segment_ids))
        return new_or_escalated

    def _record_official_alert_state(self, trip_id: str, official_notices: list) -> None:
        """Issue #1088/#1200: alert_state nach erfolgreichem Versand fortschreiben
        (Dedupe). `official_notices` sind `(OfficialAlert, segment_ids)`-Tupel."""
        if not official_notices:
            return
        from output.renderers.alert.official_alerts import official_alert_state_key
        from services.alert_state import AlertStateService

        state_svc = AlertStateService(user_id=self._user_id)
        state = state_svc.load(trip_id)
        now_iso = datetime.now(timezone.utc).isoformat()
        for a, _segment_ids in official_notices:
            key = official_alert_state_key(a)
            state[key] = {"last_reported_value": float(a.level), "reported_at": now_iso}
        state_svc.save(trip_id, state)

    def _send_official_alert_only(self, trip: "Trip", official_notices: list) -> bool:
        """Issue #1088: Standalone-Versand einer amtlichen Warnung ohne Wetter-Delta.

        Reproduziert nur die generischen Sicherheits-Gates (QuietHours, Throttle/
        Cooldown, Tageslimit) — NICHT die weather-delta-spezifischen Gates
        (has_active_rules, _filter_significant_changes), da ein eigenständiger
        amtlicher Trigger laut PO-Entscheidung unabhängig vom Wetter-Delta feuern soll.
        """
        if self._is_quiet_hours(trip, datetime.now(timezone.utc)):
            logger.debug(f"Official alert suppressed: quiet hours active for trip {trip.id}")
            return False
        if self._is_throttled_with_cooldown(trip):
            logger.debug(f"Official alert throttled for trip {trip.id}")
            return False
        if not alert_daily_limit.is_allowed(self._user_id, datetime.now(timezone.utc)):
            logger.debug(f"Official alert suppressed: daily limit reached for trip {trip.id}")
            return False

        effective_channels = self._effective_alert_channels(trip)
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
        )
        if result.sent:
            self._record_official_alert_state(trip.id, official_notices)
            self._throttle_store.record("trip", trip.id, datetime.now(timezone.utc))
            alert_daily_limit.increment(self._user_id, datetime.now(timezone.utc))
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
                ch for ch in ("email", "telegram", "sms") if trip.alert_channels.get(ch)
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
        return channels
