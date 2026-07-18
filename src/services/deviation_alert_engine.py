"""Location-generischer Deviation-Alert-Auswertungskern.

Issue #1168 — Scheibe 1/3, Epic #1095.

`DeviationAlertEngine` enthält die bereits trip-unabhängigen Bausteine, die
bisher inline in `TripAlertService.check_and_send_alerts()` liefen:
Detektor-Wahl, Change-Detection, Filter significant, Filter-gegen-Alert-State,
Severity-Bestimmung, Quiet-Hours (inkl. Mitternachts-Wrap) und Cooldown als
reine, wiederverwendbare Bausteine. Die Engine kennt kein `Trip` — sie
operiert ausschließlich auf `PointWeatherData` + `AlertEvaluationConfig` +
einem Melde-Gedächtnis-Dict (`alert_state`).

Reihenfolge und Bedingungen sind 1:1 aus `TripAlertService` übernommen
(keine Logikänderung) — `TripAlertService` wird zum dünnen Adapter, siehe
`docs/specs/modules/issue_1168_alert_engine_extract.md`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time as time_type, timedelta, timezone
from typing import List, Optional, Set
from zoneinfo import ZoneInfo

from app.models import ChangeSeverity, WeatherChange
from services.point_weather import AlertEvaluationConfig, PointWeatherData
from services.weather_change_detection import WeatherChangeDetectionService

VIENNA = ZoneInfo("Europe/Vienna")  # Vorbild alert_daily_limit.py:21


@dataclass
class EvaluationResult:
    """Ergebnis einer Engine-Auswertung — location-generisch, kein Trip-Bezug."""

    triggered: bool
    changes: List[WeatherChange] = field(default_factory=list)
    severity: str = "LOW"
    channels: Set[str] = field(default_factory=set)
    suppressed_reason: Optional[str] = None


class _SegmentIdShim:
    """Interner Adapter: gibt `WeatherChangeDetectionService.detect_changes()`
    (unverändert, liest `.segment.segment_id`/`.start_time`/`.end_time` für
    `_peak_occurred_at()`) etwas mit diesem Attribut-Shape, ohne
    `PointWeatherData` selbst an `TripSegment` zu koppeln. `start_time`/
    `end_time` werden aus der Zeitreihe selbst abgeleitet (erster/letzter
    Zeitstempel) — das reproduziert den bestehenden Peak-Zeit-Fensterfilter
    ohne echtes `TripSegment`."""

    __slots__ = ("segment_id", "start_time", "end_time")

    def __init__(self, point: PointWeatherData) -> None:
        self.segment_id = point.id
        ts_values = [dp.ts for dp in point.timeseries.data] if point.timeseries else []
        self.start_time = ts_values[0] if ts_values else None
        self.end_time = ts_values[-1] if ts_values else None


class _PointShim:
    """Interner Adapter: `PointWeatherData` → das Attribut-Shape, das
    `WeatherChangeDetectionService.detect_changes()` erwartet (`.segment.segment_id`,
    `.aggregated`, `.timeseries`). Nur Engine-intern, kein öffentliches DTO."""

    def __init__(self, point: PointWeatherData) -> None:
        self.segment = _SegmentIdShim(point)
        self.aggregated = point.aggregated
        self.timeseries = point.timeseries


class DeviationAlertEngine:
    """Location-generischer Auswertungskern für Wetter-Abweichungs-Alarme."""

    @staticmethod
    def is_quiet_hours(
        now: datetime, quiet_from: Optional[str], quiet_to: Optional[str]
    ) -> bool:
        """Prüft, ob `now` (in Europe/Vienna-Lokalzeit) innerhalb des
        konfigurierten Ruhezeit-Fensters liegt — inkl. Mitternachts-Wrap.

        Issue #1312 (Scheibe D1): `now` wird VOR dem Vergleich nach
        Europe/Vienna konvertiert, weil Nutzer die Uhrzeiten in gefühlter
        Lokalzeit eingeben. Naive datetimes (kein tzinfo) werden als UTC
        interpretiert (konservativ, deckungsgleich mit dem bisherigen
        De-facto-Verhalten aller sechs Aufrufer). DST wird durch ZoneInfo
        automatisch korrekt behandelt (Sommer +2h, Winter +1h). Vorbild:
        `alert_daily_limit.py` (dieselbe Konvention für den
        Tageszähler-Reset). Mitternachts-Wrap-Logik unverändert aus
        `TripAlertService._is_quiet_hours()` übernommen.
        """
        if not quiet_from or not quiet_to:
            return False
        aware_now = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        local_now = aware_now.astimezone(VIENNA)
        from_time = time_type.fromisoformat(quiet_from)
        to_time = time_type.fromisoformat(quiet_to)
        current = local_now.time()
        if from_time > to_time:
            return current >= from_time or current < to_time
        return from_time <= current < to_time

    @staticmethod
    def is_cooldown_active(
        now: datetime,
        last_alert_at: Optional[datetime],
        cooldown_minutes: Optional[int],
    ) -> bool:
        """1:1 aus `TripAlertService._is_throttled_with_cooldown()` (generisch:
        nimmt den letzten Alarm-Zeitpunkt direkt entgegen statt trip-keyed dict)."""
        if not cooldown_minutes:
            return False
        if last_alert_at is None:
            return False
        return now - last_alert_at < timedelta(minutes=cooldown_minutes)

    @staticmethod
    def _has_active_alert_metric(display_config: object) -> bool:
        """1:1 aus `TripAlertService._has_active_alert_metric()` (Issue #961
        F002): True, wenn mindestens eine auf dem Weather-Tab GENUIN aktive
        Metrik (echter `enabled=True`-Eintrag in `metrics[]`) auf einen
        bekannten AlertMetric gemappt ist — dann lohnt der
        Aktivieren-Lücke-Backfill in `expand_per_metric_levels()`."""
        from services.weather_change_detection import _ALERT_METRIC_TO_CATALOG_ID

        if not getattr(display_config, "metrics", None):
            return False
        alert_catalog_ids: set[str] = set()
        for catalog_ids in _ALERT_METRIC_TO_CATALOG_ID.values():
            alert_catalog_ids.update(catalog_ids)
        return any(
            mc.enabled and mc.metric_id in alert_catalog_ids
            for mc in display_config.metrics
        )

    @staticmethod
    def _select_detector(
        config: AlertEvaluationConfig,
    ) -> WeatherChangeDetectionService:
        """Detektor-Wahl inkl. #961-„Aktivieren-Lücke"-Backfill — jetzt
        location-generisch in der Engine (Issue #1168 F001-Fix), gespeist aus
        `config.metric_alert_levels` + `config.display_config`-Auszug statt
        über einen `detector=`-Override-Parameter. 1:1 aus
        `TripAlertService._select_change_detector()` übernommen; ohne
        `display_config` (None, z. B. reiner Compare-Aufruf ohne Weather-Tab)
        bleibt das alte, levels-only Verhalten erhalten (Abwärtskompatibilität)."""
        from services.alert_preset import expand_per_metric_levels

        display_config = config.display_config
        if display_config is not None:
            if not (
                config.metric_alert_levels
                or DeviationAlertEngine._has_active_alert_metric(display_config)
            ):
                return WeatherChangeDetectionService.from_alert_rules([])
            rules = expand_per_metric_levels(
                config.metric_alert_levels or {}, display_config=display_config
            )
            return WeatherChangeDetectionService.from_alert_rules(rules)

        rules = expand_per_metric_levels(config.metric_alert_levels or {}, display_config=None)
        return WeatherChangeDetectionService.from_alert_rules(rules)

    @staticmethod
    def _detect_all_changes(
        detector: WeatherChangeDetectionService,
        cached: List[PointWeatherData],
        fresh: List[PointWeatherData],
    ) -> List[WeatherChange]:
        """1:1 aus `TripAlertService._detect_all_changes()` — Matching per id
        statt segment_id, sonst identisch (inkl. `include_absolute=False`)."""
        all_changes: List[WeatherChange] = []
        cached_by_id = {p.id: p for p in cached}
        fresh_by_id = {p.id: p for p in fresh}
        for point_id, cached_point in cached_by_id.items():
            fresh_point = fresh_by_id.get(point_id)
            if fresh_point is None:
                continue
            changes = detector.detect_changes(
                _PointShim(cached_point), _PointShim(fresh_point), include_absolute=False
            )
            all_changes.extend(changes)
        return all_changes

    @staticmethod
    def _filter_significant_changes(changes: List[WeatherChange]) -> List[WeatherChange]:
        """1:1 aus `TripAlertService._filter_significant_changes()` (Issue #638:
        alle Changes einer aktiven Regel sind signifikant)."""
        return list(changes)

    @staticmethod
    def _filter_against_alert_state(
        changes: List[WeatherChange], alert_state: dict
    ) -> List[WeatherChange]:
        """1:1 aus `TripAlertService._filter_against_alert_state()` (Issue #816)."""
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

    @staticmethod
    def _highest_severity(changes: List[WeatherChange]) -> str:
        """1:1 aus `TripAlertService._highest_severity()` (Issue #393)."""
        rank = {ChangeSeverity.MINOR: 0, ChangeSeverity.MODERATE: 1, ChangeSeverity.MAJOR: 2}
        token = {
            ChangeSeverity.MINOR: "LOW",
            ChangeSeverity.MODERATE: "MODERATE",
            ChangeSeverity.MAJOR: "HIGH",
        }
        if not changes:
            return "LOW"
        top = max(changes, key=lambda c: rank.get(c.severity, 0)).severity
        return token.get(top, "LOW")

    def evaluate(
        self,
        cached: List[PointWeatherData],
        fresh: List[PointWeatherData],
        config: AlertEvaluationConfig,
        alert_state: dict,
        *,
        now: Optional[datetime] = None,
    ) -> EvaluationResult:
        """Wertet Abweichungen zwischen `cached` und `fresh` aus.

        Reihenfolge (1:1 aus `TripAlertService.check_and_send_alerts()`):
        Quiet-Hours → Detektor-Wahl → Change-Detection → Filter significant →
        Filter-gegen-State → Severity → Kanalwahl. Cooldown bleibt Trip-seitig
        im Adapter (zustandsbehaftete Datei, nicht Teil dieser Scheibe) —
        `is_cooldown_active()` steht als extrahierter, reiner Baustein bereit.
        Detektor-Wahl (inkl. #961-Backfill) läuft vollständig über
        `config.metric_alert_levels`/`config.display_config` — kein
        `detector=`-Override mehr (Issue #1168 F001-Fix).
        """
        now = now or datetime.now(timezone.utc)

        if self.is_quiet_hours(now, config.quiet_from, config.quiet_to):
            return EvaluationResult(triggered=False, suppressed_reason="quiet_hours")

        active_detector = self._select_detector(config)
        all_changes = self._detect_all_changes(active_detector, cached, fresh)
        significant = self._filter_significant_changes(all_changes)
        if not significant:
            return EvaluationResult(triggered=False, suppressed_reason="no_significant_changes")

        to_report = self._filter_against_alert_state(significant, alert_state)
        if not to_report:
            return EvaluationResult(triggered=False, suppressed_reason="alert_state_dedup")

        severity = self._highest_severity(to_report)
        return EvaluationResult(
            triggered=True,
            changes=to_report,
            severity=severity,
            channels=set(config.channels),
        )
