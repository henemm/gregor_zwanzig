"""
Trip alert service - sends immediate alerts on significant weather changes.

Feature 3.4: Alert bei Änderungen (Story 3)
Detects significant weather changes and sends alert emails with throttling.

SPEC: docs/specs/modules/trip_alert.md v2.0
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, time as time_type, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from app.config import Settings
from app.models import ChangeSeverity, SegmentWeatherData, WeatherChange
from formatters.trip_report import TripReportFormatter
from outputs.email import EmailOutput
from services.weather_change_detection import WeatherChangeDetectionService
from utils.timezone import local_fmt, tz_for_coords

if TYPE_CHECKING:
    from app.trip import Trip

logger = logging.getLogger("trip_alert")


def radar_alert_due(result: object, threshold_min: int) -> bool:
    """Return True when rain onset is within threshold_min minutes."""
    onset = getattr(result, "onset_minutes", None)
    return onset is not None and onset <= threshold_min


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
        self._formatter = TripReportFormatter()
        self._change_detector = WeatherChangeDetectionService()
        self._throttle_hours = throttle_hours
        self._user_id = user_id
        self.THROTTLE_FILE = Path(f"data/users/{user_id}/alert_throttle.json")
        self._last_alert_times: dict[str, datetime] = self._load_throttle_times()
        # Radar nowcast service (DI seam)
        self._radar_service = radar_service
        # Mail-body capture seam for AC-4/AC-6 testing (replaces SMTP when set)
        self._mail_sink = mail_sink

    def check_and_send_alerts(
        self,
        trip: "Trip",
        cached_weather: List[SegmentWeatherData],
        fresh_weather: Optional[List[SegmentWeatherData]] = None,
    ) -> bool:
        """
        Check for weather changes and send alert if significant.

        Args:
            trip: Trip to check
            cached_weather: Previously fetched weather data
            fresh_weather: Optional fresh weather (fetched if not provided)

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

        # 2. Fetch fresh weather if not provided
        if fresh_weather is None:
            fresh_weather = self._fetch_fresh_weather(cached_weather)

        if not fresh_weather:
            logger.warning(f"No fresh weather data for trip {trip.id}")
            return False

        # 3. Detect changes across all segments
        all_changes = self._detect_all_changes(cached_weather, fresh_weather)

        # 4. Issue #638: alle Changes durchreichen (kein Severity-Filter mehr)
        significant = self._filter_significant_changes(all_changes)

        if not significant:
            logger.debug(f"No significant changes for trip {trip.id}")
            return False

        logger.info(
            f"Detected {len(significant)} significant changes for trip {trip.id}"
        )

        # 4b. Issue #816 (B): Melde-Gedächtnis — Wiederholungs-Spam unterdrücken.
        # Durchlassen nur bei neuem metric:segment-Key ODER Eskalation
        # (|new_value − last_reported_value| ≥ threshold). Werden alle Changes
        # unterdrückt → kein Alert (kein Throttle/Log).
        from services.alert_state import AlertStateService
        state_svc = AlertStateService(user_id=self._user_id)
        alert_state = state_svc.load(trip.id)
        to_report = self._filter_against_alert_state(significant, alert_state)
        if not to_report:
            logger.debug(
                f"All changes suppressed by alert_state for trip {trip.id}"
            )
            return False

        # 5. Send alert; guard: only record throttle/log when at least one
        # configured channel was reachable (AC-1 symmetry with Telegram/Radar).
        delivered = self._send_alert(trip, fresh_weather, to_report)
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
        self._last_alert_times[trip.id] = datetime.now(timezone.utc)
        self._save_throttle_times()

        # 8. Issue #393: Alert-Log für Cockpit-Kachel "Alarme · letzte 24 h".
        # Nur nach erfolgreichem Versand; höchste Severity der gemeldeten Changes.
        severity = self._highest_severity(to_report)
        self._append_alert_log(trip.id, len(to_report), severity)

        return True

    @staticmethod
    def _filter_against_alert_state(
        changes: List[WeatherChange],
        alert_state: dict,
    ) -> List[WeatherChange]:
        """Issue #816 (B): Behalte nur Changes, die neu sind oder eskalieren.

        Durchlassen bei (a) kein Eintrag für `<metric>:<segment_id>` ODER
        (b) |new_value − last_reported_value| ≥ threshold der Metrik.
        """
        result: List[WeatherChange] = []
        for change in changes:
            key = f"{change.metric}:{change.segment_id}"
            prev = alert_state.get(key)
            if prev is None:
                result.append(change)
                continue
            last = prev.get("last_reported_value")
            if last is None or abs(change.new_value - last) >= change.threshold:
                result.append(change)
        return result

    def _select_change_detector(self, trip: "Trip") -> WeatherChangeDetectionService:
        """Return detector — metric_alert_levels is the SINGLE source of truth (Issue #946).

        Issue #946: metric_alert_levels ist die EINZIGE Alert-Datenquelle. Null oder leer
        = keine Alerts (NoOp-Detektor). Kein Fallback mehr auf alert_preset,
        from_display_config() oder from_trip_config() — ein unkonfigurierter Trip darf
        niemals Alerts für bloße Anzeige-Metriken feuern. Pure helper — direkt testbar.
        """
        # Issue #946: Per-Metrik-Stufen sind die einzige Quelle.
        if trip.display_config and getattr(trip.display_config, "metric_alert_levels", None):
            from services.alert_preset import expand_per_metric_levels
            rules = expand_per_metric_levels(trip.display_config.metric_alert_levels)
            return WeatherChangeDetectionService.from_alert_rules(rules)
        # Issue #946: kein Fallback — nicht konfiguriert = kein Alert (NoOp-Detektor
        # ohne MetricCatalog-Defaults, erzwungen über leere Regelliste).
        return WeatherChangeDetectionService.from_alert_rules([])

    def check_all_trips(self) -> int:
        """
        Check all active trips for weather changes and send alerts.

        Called by scheduler every 30 minutes.
        Only checks trips that have at least one stage today or in the future.

        Returns:
            Number of alerts sent
        """
        from datetime import date as date_type

        from app.loader import load_all_trips

        today = date_type.today()
        alerts_sent = 0
        for trip in load_all_trips(user_id=self._user_id):
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
            has_active_rules = (
                has_preset
                or has_metric_levels
                or any(r.enabled for r in (trip.alert_rules or []))
            )
            if not has_active_rules and (
                not trip.report_config or not trip.report_config.alert_on_changes
            ):
                continue

            # Skip expired trips (all stages in the past)
            if trip.end_date < today:
                logger.debug(f"Skipping expired trip {trip.id} (ended {trip.end_date})")
                continue

            # Skip if no cached weather available
            cached = self._get_cached_weather(trip)
            if not cached:
                continue

            try:
                if self.check_and_send_alerts(trip, cached):
                    alerts_sent += 1
            except Exception as e:
                logger.error(f"Alert check failed for trip {trip.id}: {e}")

        return alerts_sent

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

        Args:
            trip: Trip with optional alert_quiet_from / alert_quiet_to fields
            now: Current datetime (caller is responsible for correct timezone)

        Returns:
            True if alerts should be suppressed (quiet hours active)
        """
        if not trip.alert_quiet_from or not trip.alert_quiet_to:
            return False
        from_time = time_type.fromisoformat(trip.alert_quiet_from)
        to_time = time_type.fromisoformat(trip.alert_quiet_to)
        current = now.time()
        if from_time > to_time:
            # Midnight-wrap: e.g. 22:00 → 07:00
            return current >= from_time or current < to_time
        else:
            # Normal window: e.g. 08:00 → 22:00
            return from_time <= current < to_time

    def _is_throttled_with_cooldown(self, trip: "Trip") -> bool:
        """Check if alert is throttled using per-trip cooldown override.

        Issue #181: alert_cooldown_minutes=0 means no limit (always returns False).
        If None, falls back to global throttle_hours default.

        Args:
            trip: Trip with optional alert_cooldown_minutes field

        Returns:
            True if throttled (too soon since last alert)
        """
        if trip.alert_cooldown_minutes == 0:
            return False
        if trip.alert_cooldown_minutes is not None:
            cooldown_td = timedelta(minutes=trip.alert_cooldown_minutes)
        else:
            cooldown_td = timedelta(hours=self._throttle_hours)
        last_alert = self._last_alert_times.get(trip.id)
        if last_alert is None:
            return False
        return datetime.now(timezone.utc) - last_alert < cooldown_td

    def _is_throttled(self, trip_id: str) -> bool:
        """
        Check if alert is throttled for this trip.

        Args:
            trip_id: Trip identifier

        Returns:
            True if throttled (too soon since last alert)
        """
        last_alert = self._last_alert_times.get(trip_id)
        if last_alert is None:
            return False

        elapsed = datetime.now(timezone.utc) - last_alert
        return elapsed < timedelta(hours=self._throttle_hours)

    def get_time_until_next_alert(self, trip_id: str) -> Optional[timedelta]:
        """
        Get remaining throttle time for a trip.

        Args:
            trip_id: Trip identifier

        Returns:
            Time remaining until next alert allowed, or None if not throttled
        """
        last_alert = self._last_alert_times.get(trip_id)
        if last_alert is None:
            return None

        elapsed = datetime.now(timezone.utc) - last_alert
        remaining = timedelta(hours=self._throttle_hours) - elapsed

        if remaining.total_seconds() <= 0:
            return None

        return remaining

    def clear_throttle(self, trip_id: str) -> None:
        """
        Clear throttle for a trip (for testing or manual override).

        Args:
            trip_id: Trip identifier
        """
        if trip_id in self._last_alert_times:
            del self._last_alert_times[trip_id]
            self._save_throttle_times()
            logger.debug(f"Throttle cleared for trip {trip_id}")

    # --- Throttle Persistence ---

    def _load_throttle_times(self) -> dict[str, datetime]:
        """Load throttle times from JSON file."""
        if not self.THROTTLE_FILE.exists():
            return {}
        try:
            data = json.loads(self.THROTTLE_FILE.read_text())
            return {k: datetime.fromisoformat(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.warning(f"Failed to load throttle file: {e}")
            return {}

    def _save_throttle_times(self) -> None:
        """Save throttle times to JSON file."""
        try:
            self.THROTTLE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {k: v.isoformat() for k, v in self._last_alert_times.items()}
            self.THROTTLE_FILE.write_text(json.dumps(data, indent=2))
        except OSError as e:
            logger.error(f"Failed to save throttle file: {e}")

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

    @staticmethod
    def _highest_severity(changes: List[WeatherChange]) -> str:
        """Issue #393: Höchste Severity der Changes als Cockpit-Token (LOW/MODERATE/HIGH).

        ChangeSeverity (minor<moderate<major) wird auf das Frontend-Token-Set gemappt:
        MINOR→LOW, MODERATE→MODERATE, MAJOR→HIGH. Leere Liste → "LOW".
        """
        rank = {ChangeSeverity.MINOR: 0, ChangeSeverity.MODERATE: 1, ChangeSeverity.MAJOR: 2}
        token = {ChangeSeverity.MINOR: "LOW", ChangeSeverity.MODERATE: "MODERATE", ChangeSeverity.MAJOR: "HIGH"}
        if not changes:
            return "LOW"
        top = max(changes, key=lambda c: rank.get(c.severity, 0)).severity
        return token.get(top, "LOW")

    def _append_alert_log(self, trip_id: str, changes_count: int, severity: str) -> None:
        """Issue #393: Hängt einen Alert-Versand-Eintrag an alert_log.json an.

        Issue #396: Keine Retention mehr — Einträge bleiben dauerhaft erhalten,
        damit die Archiv-Statistik (Alarme pro Tour) alle historischen Alerts
        zählen kann. Der Cockpit-Endpoint filtert weiterhin Go-seitig auf 24 h.
        Wird von Go (GET /api/cockpit/status, GET /api/archive/stats) read-only gelesen.
        """
        path = Path(f"data/users/{self._user_id}/alert_log.json")
        data = json.loads(path.read_text()) if path.exists() else {"entries": []}
        data["entries"].append({
            "trip_id": trip_id,
            "sent_at": datetime.now(tz=timezone.utc).isoformat(),
            "changes_count": changes_count,
            "severity": severity,
        })
        path.write_text(json.dumps(data, indent=2))

    # --- Radar Nowcast ---

    def _get_radar_service(self):
        """Lazy-init radar service."""
        if self._radar_service is None:
            from services.radar_service import RadarNowcastService
            self._radar_service = RadarNowcastService()
        return self._radar_service

    def _is_radar_throttled(self, trip_id: str, cooldown_min: int = 120) -> bool:
        """Return True if radar alert was sent within cooldown window (Issue #818 AC-6)."""
        from services.alert_state import AlertStateService
        state = AlertStateService(self._user_id).load(trip_id)
        radar_entry = state.get("radar_throttle")
        if radar_entry:
            try:
                last = datetime.fromisoformat(radar_entry["reported_at"])
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                return datetime.now(timezone.utc) - last < timedelta(minutes=cooldown_min)
            except (KeyError, ValueError):
                pass
        return False

    def clear_radar_throttle(self, trip_id: str) -> None:
        """Clear radar throttle for a trip (test helper)."""
        from services.alert_state import AlertStateService
        svc = AlertStateService(self._user_id)
        state = svc.load(trip_id)
        if "radar_throttle" in state:
            state.pop("radar_throttle")
            svc.save(trip_id, state)

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
        from types import SimpleNamespace
        from app.loader import load_all_trips
        from services.trip_segments import convert_trip_to_segments
        from output.renderers.email.helpers import build_segment_label

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

            # Genau EIN get_nowcast-Call pro Trip an Segment-Startpunkt
            lat = active.start_point.lat
            lon = active.start_point.lon
            tz = tz_for_coords(lat, lon)
            try:
                radar_svc = self._get_radar_service()
                result = radar_svc.get_nowcast(lat, lon)
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
            if not can_email and not can_telegram:
                logger.warning(f"No channel configured; skipping radar alert for {trip.id}")
                continue

            # Ort-Label aus build_segment_label (braucht Wrapper-Objekte mit .segment)
            change_like = SimpleNamespace(segment_id=str(active.segment_id))
            seg_wrappers = [SimpleNamespace(segment=s) for s in segments]
            segment_label = build_segment_label(change_like, seg_wrappers, tz=tz)

            # Cooldown-Anzeige
            if cooldown_min % 60 == 0:
                n = cooldown_min // 60
                cooldown_display = f"{n} Stunde" if n == 1 else f"{n} Stunden"
            else:
                cooldown_display = f"{cooldown_min} Minuten"

            # Mail-Body + Betreff via pure functions (Issue #830 -- Extraktion)
            # include_source=False: format_now_text liefert nur den Onset-Satz
            # ohne eigene Quelle-Zeile, damit genau EINE Quelle-Zeile im Body steht.
            from output.renderers.alert.model import AlertMessage, OnsetEvent
            from output.renderers.alert.render import (
                render_email, render_subject, render_telegram,
            )

            _onset_time_str = (now_utc + timedelta(minutes=result.onset_minutes)).astimezone(tz).strftime("%H:%M")
            _intensity = radar_svc.format_now_text(result, tz=tz, include_source=False)
            if _briefing_announced:
                _intensity += ", jetzt akut"
            else:
                _intensity += ", im Briefing nicht angekündigt"
            _onset_ev = OnsetEvent(
                onset_minutes=result.onset_minutes,
                onset_time=_onset_time_str,
                km_from=active.start_point.distance_from_start_km,
                km_to=active.end_point.distance_from_start_km,
                is_convective=result.is_convective,
                intensity_label=_intensity,
                source_label=radar_svc.source_label(result.source),
            )
            _alert_msg = AlertMessage(
                trip_short=trip.name[:16],
                stand_at=now_utc.astimezone(tz).strftime("%H:%M"),
                events=(_onset_ev,),
                source=radar_svc.source_label(result.source),
                cooldown_display=cooldown_display,
            )
            subject = render_subject(_alert_msg)
            _html, _plain = render_email(_alert_msg)

            config = trip.report_config

            # Best-Effort-Zustellung; delivered=True wenn mindestens ein Kanal betreten (Issue #827)
            delivered = False
            if can_email and (not config or getattr(config, "send_email", True)):
                delivered = True
                try:
                    if self._mail_sink is not None:
                        self._mail_sink(subject=subject, body=_plain)
                    else:
                        EmailOutput(self._settings).send(
                            subject=subject,
                            body=_html,
                            plain_text_body=_plain,
                            mail_type="radar-alert",
                        )
                except Exception as e:
                    logger.error(f"Radar alert email failed for {trip.id}: {e}")

            if can_telegram and config and getattr(config, "send_telegram", False):
                delivered = True
                try:
                    from outputs.telegram import TelegramOutput
                    TelegramOutput(self._settings).send(subject=subject, body=render_telegram(_alert_msg))
                except Exception as e:
                    logger.error(f"Radar alert telegram failed for {trip.id}: {e}")

            if not delivered:
                logger.info(f"Radar alert: alle Kanäle auf Trip-Ebene deaktiviert, kein Recording für {trip.id}")
                continue

            # Recording nach Best-Effort-Zustellung (F001-Semantik)
            self._append_alert_log(trip.id, 1, "HIGH")
            _now = datetime.now(timezone.utc)
            from services.alert_state import AlertStateService
            _rec_svc = AlertStateService(self._user_id)
            _rec_state = _rec_svc.load(trip.id)
            _rec_state["radar_throttle"] = {"reported_at": _now.isoformat()}
            _rec_svc.save(trip.id, _rec_state)
            # Legacy-Datei für Regressions-Guard (test_827 AC-2): radar_alert_throttle.json
            _throttle_file = Path(f"data/users/{self._user_id}/radar_alert_throttle.json")
            try:
                _throttle_file.parent.mkdir(parents=True, exist_ok=True)
                _throttle_data = json.loads(_throttle_file.read_text()) if _throttle_file.exists() else {}
                _throttle_data[trip.id] = _now.isoformat()
                _throttle_file.write_text(json.dumps(_throttle_data, indent=2))
            except OSError as _e:
                logger.warning(f"Failed to write legacy radar throttle file: {_e}")
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
                # Clear cache to force fresh fetch
                service._cache.clear()
                # Bug #288: Alert-Checks must NOT trigger ensemble-API calls
                # (would consume the daily free-tier quota in ~30 minutes).
                fresh = service.fetch_segment_weather(cached.segment, enrich_ensemble=False)
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
    ) -> bool:
        """
        Format and send alert via all configured effective channels.

        Returns:
            True if at least one configured channel was reachable (deliverable),
            False if no effective channel has a working configuration.
            Send errors on a configured channel are logged but do NOT suppress
            recording (best-effort, Anti-Pattern #656).
        """
        alert_date = weather[0].segment.start_time.date()
        matched_stage = trip.get_stage_for_date(alert_date)
        stage_name = trip.numbered_stage_label(matched_stage) if matched_stage else None

        # Bug #400: ohne tz= würden Segment-Zeiten in UTC statt Lokalzeit erscheinen.
        # Zeitzone aus den Koordinaten des ersten Segments bestimmen.
        alert_tz = tz_for_coords(
            weather[0].segment.start_point.lat,
            weather[0].segment.start_point.lon,
        )

        # Issue #917 (Slice 2): kanonischer Alert-Renderer (dynamischer Betreff).
        from output.renderers.alert.project import to_alert_message
        from output.renderers.alert.render import (
            render_email, render_subject, render_telegram, render_sms,
        )

        stand_at = local_fmt(datetime.now(timezone.utc), alert_tz)
        msg = to_alert_message(
            changes, weather, trip.name, tz=alert_tz, stand_at=stand_at,
        )
        subject = render_subject(msg)
        html, plain = render_email(msg)
        telegram_body = render_telegram(msg)
        sms_body = render_sms(msg)

        # Issue #638: Effective channels — per-alert override beats briefing channels.
        effective_channels = self._effective_alert_channels(trip)
        send_email = "email" in effective_channels
        send_telegram = "telegram" in effective_channels
        send_sms = "sms" in effective_channels

        deliverable_any = False

        # Email: NEU mit can_send_email()-Guard (Symmetrie zu Telegram/Radar, Issue #684)
        if send_email and self._settings.can_send_email():
            deliverable_any = True
            try:
                EmailOutput(self._settings).send(
                    subject=subject,
                    body=html,
                    plain_text_body=plain,
                    mail_type="deviation-alert",
                )
            except Exception as e:
                logger.error(f"Email alert failed for {trip.name}: {e}")

        # Telegram (Issue #360: plain-Text, gleiche knappe Struktur)
        if send_telegram and self._settings.can_send_telegram():
            deliverable_any = True
            try:
                from outputs.telegram import TelegramOutput
                TelegramOutput(self._settings).send(
                    subject=subject,
                    body=telegram_body,
                )
            except Exception as e:
                logger.error(f"Telegram alert failed for {trip.name}: {e}")

        # SMS (Issue #914 Slice 4): kanonischer Alert-Renderer, seven.io-Versand.
        if send_sms and self._settings.can_send_sms():
            deliverable_any = True
            try:
                from outputs.sms import SMSOutput
                SMSOutput(self._settings).send(subject=subject, body=sms_body)
            except Exception as e:
                logger.error(f"SMS alert failed for {trip.name}: {e}")

        # F003: Nicht-zustellbare Kanäle (unbekannte) still protokollieren.
        known_channels = {"email", "telegram", "sms"}
        undeliverable = effective_channels - known_channels
        if undeliverable:
            logger.debug(
                f"Alert channels not yet deliverable (out-of-scope): {sorted(undeliverable)}"
            )

        if deliverable_any:
            logger.info(
                f"Alert sent for trip {trip.name}: {len(changes)} changes detected "
                f"via channels={sorted(effective_channels)}"
            )

        return deliverable_any

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

        Returns:
            Set of channel names ("email", "telegram", "sms") to use for alert dispatch.
        """
        active_rules = [r for r in (trip.alert_rules or []) if r.enabled]
        briefing = self._briefing_channels(trip.report_config)

        # Legacy-Pfad: keine aktiven alert_rules → erbe Briefing-Kanäle (oder E-Mail-Default)
        # E-Mail-Default gilt NUR wenn report_config None ist (kein explizites Ausschalten).
        if not active_rules:
            return briefing if (briefing or trip.report_config is not None) else {"email"}

        result: set[str] = set()
        for rule in active_rules:
            if rule.channels:
                result.update(rule.channels)
            else:
                result.update(briefing)
        return result

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
