"""
Weather change detection service - detects significant weather changes.

Feature 2.5: Change-Detection
Compares cached vs fresh weather data and identifies changes exceeding thresholds.

SPEC: docs/specs/modules/weather_change_detection.md v2.0
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.models import (
        AlertRule,
        SegmentWeatherData,
        TripReportConfig,
        UnifiedWeatherDisplayConfig,
    )

from enum import Enum

from app.models import (
    AlertMetric,
    AlertRuleKind,
    AlertSeverity,
    ChangeSeverity,
    ThunderLevel,
    WeatherChange,
)

# Ordinal mapping for enum-type metrics (used for delta calculation)
_THUNDER_ORDINAL = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}

# --- Issue #222 Workflow 1: AlertRule → SegmentWeatherSummary field mappings ---

# Absolute-Rule metrics → summary field name (one field per metric)
_ALERT_METRIC_TO_SUMMARY_FIELD: dict[AlertMetric, str] = {
    AlertMetric.WIND_GUST: "gust_max_kmh",
    AlertMetric.PRECIPITATION_SUM: "precip_sum_mm",
    AlertMetric.TEMPERATURE_MIN: "temp_min_c",
    AlertMetric.TEMPERATURE_MAX: "temp_max_c",
    AlertMetric.THUNDER_LEVEL: "thunder_level_max",
    # Issue #959: Nullgradgrenze konsolidiert auf freezing_level. SNOW_LINE bleibt
    # als Übergangs-Mapping auf denselben Summary-Field (Backward-Compat für
    # alt-persistierte Regeln während des Deploys).
    AlertMetric.FREEZING_LEVEL: "freezing_level_m",
    AlertMetric.SNOW_LINE: "freezing_level_m",
    # Issue #846: 4 neue Metriken
    AlertMetric.FRESH_SNOW: "snow_new_sum_cm",
    AlertMetric.CAPE: "cape_max_jkg",
    AlertMetric.VISIBILITY: "visibility_min_m",
    # Issue #889 / ADR-0010: HUMIDITY ist Vorboten-Metrik — kein Field-Mapping mehr,
    # damit auch alt-persistierte humidity-AlertRules keinen Change-Eintrag erzeugen.
}

# Delta-Rule metrics → tuple of summary fields (metric-aggregating)
_ALERT_DELTA_METRIC_TO_FIELDS: dict[AlertMetric, tuple[str, ...]] = {
    AlertMetric.TEMPERATURE_CHANGE: ("temp_min_c", "temp_max_c"),
    AlertMetric.WIND_CHANGE: ("wind_max_kmh", "gust_max_kmh"),
    AlertMetric.PRECIPITATION_CHANGE: ("precip_sum_mm",),
}

# Issue #914 / AC-2: Explicit AlertMetric → catalog metric_id bridge.
# The catalog `cmp` ("über"/"unter") is the SINGLE SOURCE for comparison direction.
# TEMPERATURE_MIN maps to "temperature_cold" (cmp="unter") because cold alarms fire
# when temp_min_c FALLS BELOW threshold — a separate catalog entry is required since
# the "temperature" entry carries cmp="über" for the warm direction.
#
# Issue #961: Value is now a TUPLE of catalog metric_ids (was a single str). Two
# distinct concerns share this map:
#   1. Comparison direction (_build_alert_metric_comparison) — derived from the
#      FIRST catalog_id ONLY (cmp is unique per AlertMetric).
#   2. Weather-Tab activation (is_alert_metric_active) — OR over ALL catalog_ids.
# For TEMPERATURE_MIN the FIRST id ("temperature_cold", cmp="unter") drives the cold
# comparison direction, while the second id ("temperature") is the Weather-Tab metric
# the user actually toggles (there is no separate "temperature_cold" toggle).
# SNOW_LINE hangs on two Weather-Tab metrics ("snowfall_limit", "freezing_level") —
# OR-policy per Issue #961 (Übergangslösung, see spec / Issue #959). The FIRST id
# ("freezing_level", cmp="unter") drives the comparison direction.
# VISIBILITY uses Threshold-Crossing logic, no cmp entry (excluded below).
_ALERT_METRIC_TO_CATALOG_ID: dict[AlertMetric, tuple[str, ...]] = {
    AlertMetric.WIND_GUST: ("gust",),
    AlertMetric.PRECIPITATION_SUM: ("precipitation",),
    AlertMetric.TEMPERATURE_MIN: ("temperature_cold", "temperature"),  # cmp="unter" (Kältealarm); Weather-Tab: temperature
    AlertMetric.TEMPERATURE_MAX: ("temperature",),        # cmp="über"
    AlertMetric.THUNDER_LEVEL: ("thunder",),
    AlertMetric.SNOW_LINE: ("snowfall_limit", "freezing_level"),  # Issue #961: OR-Policy; cmp aus "snowfall_limit" (unter)
    AlertMetric.FREEZING_LEVEL: ("freezing_level",),  # Issue #959: cmp="unter" aus Katalog
    AlertMetric.FRESH_SNOW: ("fresh_snow",),
    AlertMetric.CAPE: ("cape",),
    # Issue #961: Delta-Change-Metriken + Sichtweite ergänzt (nur für Weather-Tab-
    # Aktivierungs-Check via is_alert_metric_active; cmp wird für Delta-Metriken
    # nicht genutzt, ist aber wohldefiniert, da die catalog_ids existieren).
    AlertMetric.TEMPERATURE_CHANGE: ("temperature",),
    AlertMetric.WIND_CHANGE: ("wind",),
    AlertMetric.PRECIPITATION_CHANGE: ("precipitation",),
    AlertMetric.VISIBILITY: ("visibility",),
}

# Issue #961: VISIBILITY nutzt Threshold-Crossing (cmp="unter"), soll aber NICHT im
# Absolut-/Delta-Comparison-Map landen (Issue #917 Test-Vertrag: VISIBILITY nicht in
# _ALERT_METRIC_COMPARISON). Comparison wird nur für diese Metriken abgeleitet.
_COMPARISON_EXCLUDED_METRICS: frozenset = frozenset({AlertMetric.VISIBILITY})


def _build_alert_metric_comparison() -> dict[AlertMetric, str]:
    """Derive comparison direction from catalog cmp at module load.

    Maps 'über' → 'above', 'unter' → 'below'. Uses only the FIRST catalog_id per
    AlertMetric (Issue #961: value is now a tuple; cmp is unique per metric).
    This replaces the former hand-coded _ALERT_METRIC_COMPARISON dict
    (Issue #914/AC-2: catalog is the single source).
    """
    from app.metric_catalog import get_cmp as _catalog_get_cmp
    _cmp_map = {"über": "above", "unter": "below"}
    result: dict[AlertMetric, str] = {}
    for metric, catalog_ids in _ALERT_METRIC_TO_CATALOG_ID.items():
        if metric in _COMPARISON_EXCLUDED_METRICS:
            continue
        catalog_id = catalog_ids[0]
        catalog_cmp = _catalog_get_cmp(catalog_id)
        direction = _cmp_map.get(catalog_cmp)
        if direction is None:
            raise ValueError(
                f"AlertMetric.{metric.name} → catalog '{catalog_id}' has "
                f"unexpected cmp={catalog_cmp!r}; expected 'über' or 'unter'"
            )
        result[metric] = direction
    return result


# Comparison direction per absolute-rule metric ("above" or "below").
# Derived from catalog at module load — DO NOT hand-edit this dict.
# To change a direction, update the catalog entry or _ALERT_METRIC_TO_CATALOG_ID.
_ALERT_METRIC_COMPARISON: dict[AlertMetric, str] = _build_alert_metric_comparison()


def is_alert_metric_active(
    alert_metric: AlertMetric,
    display_config: "UnifiedWeatherDisplayConfig | None",
) -> bool:
    """True, wenn die auf `alert_metric` gemappte(n) Weather-Tab-Metrik(en) als
    aktiv für Alarm-Zwecke gelten.

    Issue #961: Schließt die Lücke zwischen Weather-Tab (`display_config.metrics[]`)
    und Alarm-Regeln (`metric_alert_levels`). OR-Verknüpfung bei Mehrfach-Mapping
    (aktuell SNOW_LINE → snowfall_limit/freezing_level; Übergangslösung, siehe Spec
    fix_961 und Issue #959).

    Finding F002 (Regression-Fix): Ein Trip, der Alarm-Level gesetzt bekam, OHNE je
    den Wetter-Tab zu berühren, hat ein KOMPLETT LEERES `metrics[]`-Array (der
    Loader backfillt es NICHT, wenn `display_config` bereits existiert). In diesem
    Zustand liegt gar keine bewusste Wetter-Tab-Auswahl vor — jede Alarm-Metrik gilt
    konservativ als AKTIV (Backward-Compat, kein stiller Alarmverlust für Alt-Trips).

    Sobald `metrics[]` MINDESTENS EINEN Eintrag hat, hat der Nutzer den Wetter-Tab
    bewusst konfiguriert: Dann zählt nur die tatsächliche Aktivierung. Ein fehlender
    Eintrag gilt hier als NICHT aktiv (identisch zur `is_metric_enabled()`-Semantik) —
    das ist wichtig für synthetische Katalog-IDs wie "temperature_cold", die keinen
    eigenen Wetter-Tab-Toggle haben und immer fehlen würden.

    Semantik (OR über alle gemappten Catalog-IDs):
      - metrics[] leer                       → aktiv (nie konfiguriert, konservativ)
      - mindestens eine gemappte ID enabled=True → aktiv
      - sonst                                → inaktiv

    None-safe: fehlende display_config oder unbekannter AlertMetric → False.
    """
    if display_config is None:
        return False
    catalog_ids = _ALERT_METRIC_TO_CATALOG_ID.get(alert_metric)
    if not catalog_ids:
        return False
    # Finding F002: komplett leeres metrics[] = Trip hat den Wetter-Tab nie
    # angefasst → konservativ aktiv (kein stiller Alarmverlust für Alt-Trips).
    if not display_config.metrics:
        return True
    return any(display_config.is_metric_enabled(cid) for cid in catalog_ids)


# AlertSeverity (Issue #205) → ChangeSeverity (DTO for mail filter)
_RULE_SEVERITY_TO_CHANGE_SEVERITY: dict[AlertSeverity, ChangeSeverity] = {
    AlertSeverity.INFO: ChangeSeverity.MINOR,
    AlertSeverity.WARNING: ChangeSeverity.MODERATE,
    AlertSeverity.CRITICAL: ChangeSeverity.MAJOR,
}


def _peak_occurred_at(
    summary_field: str,
    new_data: "SegmentWeatherData",
) -> "str | None":
    """Best-effort: find 'HH:MM' of the peak value for the given summary field.

    Looks up the metric's dp_field and aggregation type from the catalog,
    then scans the timeseries for the peak point within the segment window.
    Returns None on any error — never raises.
    """
    try:
        from app.metric_catalog import _METRICS
        dp_field: str | None = None
        agg: str | None = None
        for m in _METRICS:
            for a, sf in m.summary_fields.items():
                if sf == summary_field:
                    dp_field = m.dp_field
                    agg = a
                    break
            if dp_field:
                break
        if not dp_field or not agg:
            return None

        seg = new_data.segment
        points = new_data.timeseries.data
        if not points:
            return None

        seg_start = seg.start_time
        seg_end = seg.end_time

        # Filter to points within the segment window
        window = [
            p for p in points
            if p.ts is not None and seg_start <= p.ts <= seg_end
        ]
        if not window:
            window = points  # fallback: use all points

        # Find peak point based on aggregation type
        best = None
        best_val: float | None = None
        for p in window:
            raw = getattr(p, dp_field, None)
            if raw is None:
                continue
            try:
                val = float(raw)
            except (TypeError, ValueError):
                continue
            if best_val is None:
                best, best_val = p, val
            elif agg in ("max", "sum") and val > best_val:
                best, best_val = p, val
            elif agg == "min" and val < best_val:
                best, best_val = p, val
            # avg: use last point as proxy (no running mean needed here)
            elif agg == "avg":
                best, best_val = p, val

        if best is None or best.ts is None:
            return None

        ts = best.ts
        if hasattr(ts, "hour"):
            return f"{ts.hour:02d}:{ts.minute:02d}"
        return None
    except Exception:
        return None


class WeatherChangeDetectionService:
    """
    Service for detecting significant weather changes.

    Compares two SegmentWeatherSummary objects and identifies changes
    that exceed configured thresholds.

    v2.0: Thresholds derived from MetricCatalog via get_change_detection_map().
    User-configured overrides from TripReportConfig applied via from_trip_config().

    Example:
        >>> service = WeatherChangeDetectionService()
        >>> changes = service.detect_changes(old_data, new_data)
        >>> for change in changes:
        ...     print(f"{change.metric}: {change.delta:+.1f} ({change.severity})")
        temp_max_c: +7.0 (moderate)
        wind_max_kmh: +25.0 (major)
    """

    # Issue #846: Metriken mit Threshold-Crossing-Semantik (feuert nur beim erstmaligen Unterschreiten)
    _THRESHOLD_CROSSING_METRICS: frozenset = frozenset({AlertMetric.VISIBILITY})

    def __init__(
        self,
        thresholds: Optional[dict[str, float]] = None,
        absolute_rules: Optional[list["AlertRule"]] = None,
        severity_overrides: Optional[dict[str, AlertSeverity]] = None,
        absolute_seeded_fields: Optional[set[str]] = None,
        threshold_crossing_rules: Optional[list["AlertRule"]] = None,
    ):
        """
        Initialize with thresholds.

        Args:
            thresholds: Custom {field: threshold} dict.
                        If None, uses get_change_detection_map() defaults from MetricCatalog.
            absolute_rules: Issue #222 — Absolute AlertRules (kind=absolute, enabled=True).
                            Detected via comparison-direction (above/below) per metric.
            severity_overrides: Issue #222 — Maps summary-field → AlertSeverity for delta
                                detection, so rule.severity wins over ratio-based classify.
            absolute_seeded_fields: Issue #821 — Felder, deren Δ-Threshold ausschließlich
                                    durch den #816-setdefault-Seed einer ABSOLUTE-Regel
                                    entstanden ist (kein expliziter DELTA-Eintrag). Bei
                                    include_absolute=True übernimmt der Absolut-Pfad das
                                    Feld → Δ-Pfad wird übersprungen (kein Doppel-Change).
        """
        if thresholds is None:
            from app.metric_catalog import get_change_detection_map
            self._thresholds = get_change_detection_map()
        else:
            self._thresholds = dict(thresholds)
        self._absolute_rules: list["AlertRule"] = list(absolute_rules) if absolute_rules else []
        self._severity_overrides: dict[str, AlertSeverity] = (
            dict(severity_overrides) if severity_overrides else {}
        )
        # Issue #821: rein-geseedete Felder (ABSOLUTE-Seed ohne explizite DELTA-Regel)
        self._absolute_seeded_fields: set[str] = set(absolute_seeded_fields or set())
        # Issue #846: Threshold-Crossing-Regeln (Sichtweite: feuert nur beim erstmaligen Unterschreiten)
        self._threshold_crossing_rules: list["AlertRule"] = list(threshold_crossing_rules) if threshold_crossing_rules else []

    @classmethod
    def from_trip_config(cls, config: "TripReportConfig") -> "WeatherChangeDetectionService":
        """
        Factory: Create service with user-configured thresholds.

        Starts with MetricCatalog defaults, then overrides
        temp/wind/precip thresholds from TripReportConfig.

        Args:
            config: User's trip report configuration

        Returns:
            WeatherChangeDetectionService with merged thresholds
        """
        from app.metric_catalog import get_change_detection_map
        thresholds = get_change_detection_map()

        # Override temp-related fields
        for field_name in ("temp_min_c", "temp_max_c", "temp_avg_c",
                           "wind_chill_min_c", "dewpoint_avg_c"):
            if field_name in thresholds:
                thresholds[field_name] = config.change_threshold_temp_c

        # Override wind-related fields
        for field_name in ("wind_max_kmh", "gust_max_kmh"):
            if field_name in thresholds:
                thresholds[field_name] = config.change_threshold_wind_kmh

        # Override precip-related fields
        for field_name in ("precip_sum_mm",):
            if field_name in thresholds:
                thresholds[field_name] = config.change_threshold_precip_mm

        return cls(thresholds=thresholds)

    @classmethod
    def from_display_config(cls, display_config: "UnifiedWeatherDisplayConfig") -> "WeatherChangeDetectionService":
        """
        Factory: Create service from per-metric display settings.

        Only metrics with enabled=True are included in detection (display flag;
        bewusst so seit Issue #131 — NICHT alert_enabled). User-set
        alert_threshold overrides MetricCatalog default.

        Args:
            display_config: Unified weather display config with per-metric alert settings

        Returns:
            WeatherChangeDetectionService with filtered thresholds
        """
        from app.metric_catalog import get_metric
        thresholds: dict[str, float] = {}
        for mc in display_config.metrics:
            if not mc.enabled:
                continue
            try:
                metric_def = get_metric(mc.metric_id)
            except KeyError:
                continue
            if metric_def.default_change_threshold is None:
                continue  # Enum metrics (thunder, precip_type) — skip
            # Issue #889 / #914: Vorboten-Metriken (is_precursor=True) lösen
            # keinen Abweichungs-Alert aus — auch wenn aktiviert im Display-Config.
            if metric_def.is_precursor:
                continue
            threshold = mc.alert_threshold if mc.alert_threshold is not None else metric_def.default_change_threshold
            for field in metric_def.summary_fields.values():
                thresholds[field] = threshold
        return cls(thresholds=thresholds)

    @classmethod
    def from_alert_rules(cls, rules: list["AlertRule"]) -> "WeatherChangeDetectionService":
        """Factory: Build a service from Issue-#205 AlertRule list (Issue #222 W1).

        Only rules with enabled=True contribute. Delta-rules fill _thresholds
        (compatible with existing detect_changes logic). Absolute-rules go to
        a separate _absolute_rules list (consumed by detect_changes). The rule
        severity overrides the ratio-based classification for both paths.

        Args:
            rules: List of AlertRule objects (typically from Trip.alert_rules).

        Returns:
            WeatherChangeDetectionService with only rule-driven thresholds
            (no MetricCatalog defaults — explicit opt-in via rules).
        """
        from app.metric_catalog import get_change_detection_map
        catalog_defaults = get_change_detection_map()

        thresholds: dict[str, float] = {}
        absolute_rules: list["AlertRule"] = []
        severity_overrides: dict[str, AlertSeverity] = {}
        # Issue #821: Set der rein-geseedeten Felder — gesetzt vom ABSOLUTE-Zweig,
        # entfernt wenn eine explizite DELTA-Regel dasselbe Feld belegt.
        absolute_seeded: set[str] = set()
        # Issue #846: Threshold-Crossing-Regeln (Sichtweite: feuert nur beim erstmaligen Unterschreiten)
        threshold_crossing_rules: list["AlertRule"] = []

        for rule in rules:
            if not rule.enabled:
                continue
            # Issue #961 (Finding F004): feld-granulare Backfill-Unterdrückung.
            # Felder, die bereits von einer explizit gesetzten (Weather-Tab-aktiven)
            # Metrik belegt sind, dürfen durch diese Backfill-Regel NICHT scharf
            # gestellt werden — der Rest der Metrik-Felder wird aber weiterhin armiert.
            suppressed = getattr(rule, "suppressed_fields", None) or set()
            # Issue #846: Threshold-Crossing-Semantik für VISIBILITY-Metrik und
            # explizit als THRESHOLD_CROSSING markierte Regeln.
            if (rule.kind == AlertRuleKind.THRESHOLD_CROSSING
                    or rule.metric in cls._THRESHOLD_CROSSING_METRICS):
                threshold_crossing_rules.append(rule)
                continue
            if rule.kind == AlertRuleKind.ABSOLUTE:
                absolute_rules.append(rule)
                # Issue #816 (C): ABSOLUTE-Regeln liefern keine Δ-Schwellen; damit
                # der Alert-Pfad (`include_absolute=False`) für Trips mit reinen
                # absolute-rules trotzdem symmetrische Δ-Alerts produziert, tragen
                # wir die MetricCatalog-Defaults für das betroffene Summary-Field ein.
                # Invariante: ein Trip mit SyncAlertRules (#809 — nur ABSOLUTE) bekommt
                # Δ-Alerts mit denselben Schwellen wie der MetricCatalog-Default.
                field_name = _ALERT_METRIC_TO_SUMMARY_FIELD.get(rule.metric)
                # Issue #961 (F004): unterdrücktes Feld nicht seeden.
                if field_name and field_name in suppressed:
                    field_name = None
                if field_name and field_name in catalog_defaults:
                    # Issue #821: Nur wenn das Feld wirklich NEU geseedet wird (nicht
                    # bereits durch eine frühere Regel belegt), als rein-geseedet merken.
                    if field_name not in thresholds:
                        absolute_seeded.add(field_name)
                    thresholds.setdefault(field_name, catalog_defaults[field_name])
            elif rule.kind == AlertRuleKind.DELTA:
                fields = _ALERT_DELTA_METRIC_TO_FIELDS.get(rule.metric)
                if not fields:
                    # Issue #817: Basis-Metrik-Delta-Regeln (WIND_GUST, TEMPERATURE_MIN/MAX,
                    # PRECIPITATION_SUM, THUNDER_LEVEL, SNOW_LINE) — seit #817 erzeugt
                    # SyncAlertRules diese als kind="delta". Auf das einzelne Summary-Feld
                    # aufloesen, sonst wuerde der Nutzer-Schwellenwert verworfen.
                    base_field = _ALERT_METRIC_TO_SUMMARY_FIELD.get(rule.metric)
                    fields = (base_field,) if base_field else ()
                if not fields:
                    logger.warning(
                        "AlertRule kind=delta with unsupported metric %s (id=%s) — dropped",
                        rule.metric, rule.id,
                    )
                    continue
                # Issue #961 (F004): kollidierende Felder aus der Backfill-Regel
                # entfernen — nur die verbleibenden Felder werden scharf gestellt.
                if suppressed:
                    fields = tuple(f for f in fields if f not in suppressed)
                    if not fields:
                        continue
                for field_name in fields:
                    thresholds[field_name] = rule.threshold
                    severity_overrides[field_name] = rule.severity
                    # Issue #821: Explizite DELTA-Regel überschreibt Seed — das Feld
                    # ist nicht mehr rein-geseedet, darf nicht unterdrückt werden.
                    absolute_seeded.discard(field_name)

        return cls(
            thresholds=thresholds,
            absolute_rules=absolute_rules,
            severity_overrides=severity_overrides,
            absolute_seeded_fields=absolute_seeded,
            threshold_crossing_rules=threshold_crossing_rules,
        )

    def detect_changes(
        self,
        old_data: "SegmentWeatherData",
        new_data: "SegmentWeatherData",
        *,
        include_absolute: bool = True,
    ) -> list[WeatherChange]:
        """
        Detect significant changes between old and new weather data.

        Args:
            old_data: Cached weather data
            new_data: Fresh weather data
            include_absolute: Issue #816 — wenn False, werden die absoluten
                Regeln (`_detect_absolute_changes`) NICHT ausgewertet (nur die
                symmetrische Δ-Erkennung). Der Forecast-Alert-Pfad nutzt False;
                Default True bewahrt das Verhalten bestehender Aufrufer.

        Returns:
            List of WeatherChange objects for metrics exceeding thresholds.
            Empty list if no significant changes detected.

        Algorithm:
            1. Extract old and new summaries
            2. For each metric:
               a. Skip if either value is None
               b. Calculate delta (new - old)
               c. Check if |delta| > threshold
               d. If yes: classify severity, create WeatherChange
            3. Return all detected changes
        """
        old_summary = old_data.aggregated
        new_summary = new_data.aggregated
        changes = []

        # Compare all numeric metrics
        for metric, threshold in self._thresholds.items():
            # Issue #821: Rein-geseedetes Feld (ABSOLUTE-Seed via #816-setdefault) bei
            # include_absolute=True überspringen — der Absolut-Pfad deckt es ab.
            # Bei include_absolute=False ist der Δ-Pfad die einzige Quelle → nicht skippen.
            if include_absolute and metric in self._absolute_seeded_fields:
                continue

            # Get old and new values
            old_value = getattr(old_summary, metric, None)
            new_value = getattr(new_summary, metric, None)

            # Skip if either is None
            if old_value is None or new_value is None:
                continue

            # Convert enum values to ordinals for delta calculation
            if isinstance(old_value, Enum):
                old_value = _THUNDER_ORDINAL.get(old_value, 0)
                new_value = _THUNDER_ORDINAL.get(new_value, 0)

            # Calculate delta
            delta = new_value - old_value

            # Check if exceeds threshold
            if abs(delta) > threshold:
                # Issue #222: Rule-driven severity override (delta-rules from from_alert_rules)
                if metric in self._severity_overrides:
                    severity = _RULE_SEVERITY_TO_CHANGE_SEVERITY[
                        self._severity_overrides[metric]
                    ]
                else:
                    severity = self._classify_severity(abs(delta), threshold)
                direction = "increase" if delta > 0 else "decrease"

                change = WeatherChange(
                    metric=metric,
                    old_value=float(old_value),
                    new_value=float(new_value),
                    delta=float(delta),
                    threshold=float(threshold),
                    severity=severity,
                    direction=direction,
                    segment_id=str(new_data.segment.segment_id),
                    occurred_at=_peak_occurred_at(metric, new_data),
                )
                changes.append(change)

        # Issue #222 Workflow 1: Absolute-rule detection (new_value vs threshold)
        # Issue #816: Im Δ-only-Alert-Pfad (include_absolute=False) ausgeschlossen.
        if include_absolute:
            changes.extend(self._detect_absolute_changes(new_summary, new_data))

        # Issue #846: Threshold-Crossing-Erkennung (z.B. Sichtweite).
        # Feuert genau dann wenn new_value erstmals unter den Schwellwert fällt
        # (old_value >= threshold AND new_value < threshold). Läuft immer (unabhängig
        # von include_absolute), da es weder Absolut- noch Delta-Logik ist.
        changes.extend(self._detect_threshold_crossing_changes(old_summary, new_summary, new_data))

        return changes

    def _detect_absolute_changes(
        self,
        new_summary,
        new_data: "SegmentWeatherData",
    ) -> list[WeatherChange]:
        """Detect absolute-rule violations (Issue #222 W1).

        For each absolute rule:
        - Resolve summary field via _ALERT_METRIC_TO_SUMMARY_FIELD
        - Look up comparison direction (above/below)
        - Emit WeatherChange if threshold violated, using rule-severity
        """
        results: list[WeatherChange] = []
        for rule in self._absolute_rules:
            field_name = _ALERT_METRIC_TO_SUMMARY_FIELD.get(rule.metric)
            if not field_name:
                continue
            new_value = getattr(new_summary, field_name, None)
            if new_value is None:
                continue
            # Convert enum values (e.g., ThunderLevel) to ordinals
            if isinstance(new_value, Enum):
                new_value = _THUNDER_ORDINAL.get(new_value, 0)
            comparison = _ALERT_METRIC_COMPARISON[rule.metric]
            # Issue #222 F003: THUNDER_LEVEL uses >= for above (user intent
            # "ab Stufe MED alarmieren" — threshold=1.0 must match MED=1).
            # Other numeric metrics keep strict > to avoid spurious noise.
            if rule.metric == AlertMetric.THUNDER_LEVEL:
                triggered = (
                    (comparison == "above" and new_value >= rule.threshold)
                    or (comparison == "below" and new_value <= rule.threshold)
                )
            else:
                triggered = (
                    (comparison == "above" and new_value > rule.threshold)
                    or (comparison == "below" and new_value < rule.threshold)
                )
            if not triggered:
                continue
            severity = _RULE_SEVERITY_TO_CHANGE_SEVERITY[rule.severity]
            results.append(
                WeatherChange(
                    metric=field_name,
                    old_value=0.0,  # Absolute rules have no "old" comparison
                    new_value=float(new_value),
                    delta=float(new_value) - float(rule.threshold),
                    threshold=float(rule.threshold),
                    severity=severity,
                    direction=comparison,  # "above" or "below"
                    segment_id=str(new_data.segment.segment_id),
                )
            )
        return results

    def _detect_threshold_crossing_changes(
        self,
        old_summary,
        new_summary,
        new_data: "SegmentWeatherData",
    ) -> list[WeatherChange]:
        """Issue #846: Threshold-Crossing-Erkennung.

        Feuert genau dann, wenn new_value erstmals unter den Schwellwert fällt:
            old_value >= threshold AND new_value < threshold

        Kein erneutes Feuern wenn beide Werte bereits unter dem Schwellwert liegen.
        """
        results: list[WeatherChange] = []
        for rule in self._threshold_crossing_rules:
            field_name = _ALERT_METRIC_TO_SUMMARY_FIELD.get(rule.metric)
            if not field_name:
                continue
            old_value = getattr(old_summary, field_name, None)
            new_value = getattr(new_summary, field_name, None)
            if old_value is None or new_value is None:
                continue
            old_f = float(old_value)
            new_f = float(new_value)
            threshold = float(rule.threshold)
            # Threshold-Crossing: erstmaliges Unterschreiten
            if old_f >= threshold and new_f < threshold:
                severity = _RULE_SEVERITY_TO_CHANGE_SEVERITY[rule.severity]
                results.append(WeatherChange(
                    metric=field_name,
                    old_value=old_f,
                    new_value=new_f,
                    delta=new_f - old_f,
                    threshold=threshold,
                    severity=severity,
                    direction="below_threshold",
                    segment_id=str(new_data.segment.segment_id),
                ))
        return results

    def _classify_severity(self, delta: float, threshold: float) -> ChangeSeverity:
        """
        Classify change severity based on delta/threshold ratio.

        Thresholds:
        - MINOR: 10-50% over threshold (1.0x - <1.5x)
        - MODERATE: 50-100% over threshold (1.5x - <2.0x)
        - MAJOR: >100% over threshold (>=2.0x)

        Args:
            delta: Absolute delta value
            threshold: Configured threshold

        Returns:
            ChangeSeverity enum value
        """
        ratio = abs(delta) / threshold

        if ratio >= 2.0:
            return ChangeSeverity.MAJOR
        elif ratio >= 1.5:
            return ChangeSeverity.MODERATE
        else:
            return ChangeSeverity.MINOR
