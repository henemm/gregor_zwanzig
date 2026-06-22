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
from utils.timezone import tz_for_coords

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
        self._RADAR_THROTTLE_FILE = Path(f"data/users/{user_id}/radar_alert_throttle.json")
        self._radar_throttle_times: dict[str, datetime] = self._load_radar_throttle()
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
        has_active_rules = any(r.enabled for r in (trip.alert_rules or []))
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
        """Return detector with priority alert_rules > display_config > report_config > defaults.

        Issue #222 Workflow 1: alert_rules (enabled=True) is now the highest-priority
        source for change-detection thresholds. Pure helper — directly unit-testable
        without SMTP setup.
        """
        active_rules = [r for r in (trip.alert_rules or []) if r.enabled]
        if active_rules:
            return WeatherChangeDetectionService.from_alert_rules(active_rules)
        if trip.display_config and trip.display_config.get_enabled_metrics():
            return WeatherChangeDetectionService.from_display_config(trip.display_config)
        if trip.report_config:
            return WeatherChangeDetectionService.from_trip_config(trip.report_config)
        return WeatherChangeDetectionService()

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
            has_active_rules = any(r.enabled for r in (trip.alert_rules or []))
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

    def _load_radar_throttle(self) -> dict[str, datetime]:
        """Load radar throttle times from file."""
        if not self._RADAR_THROTTLE_FILE.exists():
            return {}
        try:
            data = json.loads(self._RADAR_THROTTLE_FILE.read_text())
            return {k: datetime.fromisoformat(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.warning(f"Failed to load radar throttle file: {e}")
            return {}

    def _save_radar_throttle(self) -> None:
        """Persist radar throttle times to file."""
        try:
            self._RADAR_THROTTLE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {k: v.isoformat() for k, v in self._radar_throttle_times.items()}
            self._RADAR_THROTTLE_FILE.write_text(json.dumps(data, indent=2))
        except OSError as e:
            logger.error(f"Failed to save radar throttle file: {e}")

    def _is_radar_throttled(self, trip_id: str, cooldown_min: int = 120) -> bool:
        """Return True if radar alert was sent within cooldown window."""
        last = self._radar_throttle_times.get(trip_id)
        if last is None:
            return False
        return datetime.now(timezone.utc) - last < timedelta(minutes=cooldown_min)

    def clear_radar_throttle(self, trip_id: str) -> None:
        """Clear radar throttle for a trip (test helper / manual override)."""
        self._radar_throttle_times.pop(trip_id, None)
        self._save_radar_throttle()

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
            from outputs.radar_alert import build_radar_alert_body, build_radar_alert_subject
            onset_text = radar_svc.format_now_text(result, tz=tz, include_source=False)
            full_body = build_radar_alert_body(
                onset_text=onset_text,
                segment_label=segment_label,
                cooldown_display=cooldown_display,
                source=radar_svc.source_label(result.source),
            )
            subject = build_radar_alert_subject(trip.name, result, segment_label)

            config = trip.report_config

            # Best-Effort-Zustellung; delivered=True wenn mindestens ein Kanal betreten (Issue #827)
            delivered = False
            if can_email and (not config or getattr(config, "send_email", True)):
                delivered = True
                try:
                    if self._mail_sink is not None:
                        self._mail_sink(subject=subject, body=full_body)
                    else:
                        EmailOutput(self._settings).send(
                            subject=subject,
                            body=full_body,
                            plain_text_body=full_body,
                            mail_type="radar-alert",
                        )
                except Exception as e:
                    logger.error(f"Radar alert email failed for {trip.id}: {e}")

            if can_telegram and config and getattr(config, "send_telegram", False):
                delivered = True
                try:
                    from outputs.telegram import TelegramOutput
                    TelegramOutput(self._settings).send(subject=subject, body=onset_text)
                except Exception as e:
                    logger.error(f"Radar alert telegram failed for {trip.id}: {e}")

            if not delivered:
                logger.info(f"Radar alert: alle Kanäle auf Trip-Ebene deaktiviert, kein Recording für {trip.id}")
                continue

            # Recording nach Best-Effort-Zustellung (F001-Semantik)
            self._append_alert_log(trip.id, 1, "HIGH")
            self._radar_throttle_times[trip.id] = datetime.now(timezone.utc)
            self._save_radar_throttle()
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

        # Issue #816 (D): Knapper Abweichungs-Alert (kein volles Briefing).
        from output.renderers.email.alert_compact import render_deviation_alert
        html, plain = render_deviation_alert(
            changes=changes,
            segments=weather,
            trip_name=trip.name,
            tz=alert_tz,
            stage_label=stage_name,
        )
        subject = f"[{trip.name}] Wetter ändert sich seit dem Briefing"

        # Issue #638: Effective channels — per-alert override beats briefing channels.
        effective_channels = self._effective_alert_channels(trip)
        send_email = "email" in effective_channels
        send_telegram = "telegram" in effective_channels

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
                    body=plain,
                )
            except Exception as e:
                logger.error(f"Telegram alert failed for {trip.name}: {e}")

        # F003: Nicht-zustellbare Kanäle (sms, unbekannte) still protokollieren.
        known_channels = {"email", "telegram"}
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
