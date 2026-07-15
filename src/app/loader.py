"""
JSON loaders and savers for Trip and User configurations.

Provides functions to load and save Trip and User objects from/to JSON files
with validation and error handling.
"""
from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.models import (
    AlertMetric,
    AlertRule,
    AlertRuleKind,
    AlertSeverity,
    ComparePreset,
    Corridor,
)
from app.trip import (
    ActivityProfile,
    AggregationConfig,
    AggregationFunc,
    Stage,
    TimeWindow,
    Trip,
    Waypoint,
)
from app.user import (
    LocationSubscription,
    SavedLocation,
    Schedule,
    TriggerTiming,
    TripSubscription,
    User,
    UserPreferences,
)

logger = logging.getLogger(__name__)

# Mapping Legacy report_config -> AlertMetric + Unit (Issue #205)
_LEGACY_DELTA_MAPPING: list[tuple[str, AlertMetric, str]] = [
    ("change_threshold_temp_c", AlertMetric.TEMPERATURE_CHANGE, "°C"),
    ("change_threshold_wind_kmh", AlertMetric.WIND_CHANGE, "km/h"),
    ("change_threshold_precip_mm", AlertMetric.PRECIPITATION_CHANGE, "mm"),
]


def _resolve_format_mode(mc_data: dict, metric_id: str) -> str:
    """
    Issue #435: Resolve format_mode from persisted MetricConfig dict.

    Precedence:
        1. Explicit `format_mode` field wins (new write path).
        2. Legacy `use_friendly_format=False` -> "raw".
        3. Legacy `use_friendly_format=True` (or missing) ->
           Catalog `default_format_mode` of the metric.

    For unknown metric_ids (not in catalog) falls back to "raw".
    """
    raw = mc_data.get("format_mode")
    if raw is not None:
        try:
            from app.metric_catalog import get_metric
            metric_def = get_metric(metric_id)
            if raw not in metric_def.format_modes:
                logger.warning(
                    "Unknown format_mode %r for metric %r; "
                    "falling back to default %r",
                    raw, metric_id, metric_def.default_format_mode,
                )
                return metric_def.default_format_mode
        except KeyError:
            pass  # unbekannte metric_id → weiter mit raw
        return raw
    if not mc_data.get("use_friendly_format", True):
        return "raw"
    try:
        from app.metric_catalog import get_metric
        return get_metric(metric_id).default_format_mode
    except KeyError:
        return "raw"


def _friendly_from_mode(mode: str) -> bool:
    """Issue #435: Map new format_mode back to legacy use_friendly_format bool.

    "raw" -> False, every other mode -> True (backward-compat for older readers).
    """
    return mode != "raw"


def _deep_merge_preserve_unknown(base: dict, overlay: dict) -> dict:
    """Merge overlay into base. overlay wins on key conflicts; unknown keys in base are preserved.

    Used in save_trip to preserve Go-written or legacy fields Python doesn't model (Issue #805).
    Lists are replaced wholesale (not element-merged) — overlay wins.
    """
    result = dict(base)
    for k, v in overlay.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge_preserve_unknown(result[k], v)
        else:
            result[k] = v
    return result


def _metric_to_dict(mc) -> dict:
    """Issue #435: Serialize a MetricConfig to dict, writing format_mode and
    use_friendly_format in parallel (Backward-Compat for older readers).

    Precedence:
      - If `format_mode` is explicit on the MetricConfig, write it as-is and
        derive `use_friendly_format` from it (raw -> False, other -> True).
      - Else write the existing `use_friendly_format` bool; `format_mode`
        gets resolved via the catalog default (so reading the file later
        produces the same effective mode).
    """
    if mc.format_mode is not None:
        mode = mc.format_mode
        friendly = _friendly_from_mode(mode)
    else:
        mode = None
        friendly = mc.use_friendly_format
    out = {
        "metric_id": mc.metric_id,
        "enabled": mc.enabled,
        "aggregations": mc.aggregations,
        "morning_enabled": mc.morning_enabled,
        "evening_enabled": mc.evening_enabled,
        "use_friendly_format": friendly,
        "alert_enabled": mc.alert_enabled,
        "alert_threshold": mc.alert_threshold,
        "bucket": mc.bucket,
        "order": mc.order,
    }
    if mode is not None:
        out["format_mode"] = mode
    # Issue #624: sms_threshold nur schreiben wenn gesetzt (additiv, kein Datenverlust).
    if mc.sms_threshold is not None:
        out["sms_threshold"] = mc.sms_threshold
    # Issue #805: horizons roundtrip-erhalten
    if mc.horizons is not None:
        out["horizons"] = mc.horizons
    return out


def _alert_rule_from_dict(d: Dict[str, Any]) -> AlertRule:
    """Parse a single AlertRule from a JSON dict.

    Issue #638: channels parsed with empty-list default for Bestands-Daten (BUG-DATALOSS-GR221).
    """
    return AlertRule(
        id=d["id"],
        kind=AlertRuleKind(d["kind"]),
        metric=AlertMetric(d["metric"]),
        threshold=float(d["threshold"]),
        unit=d.get("unit", ""),
        severity=AlertSeverity(d.get("severity", "warning")),
        enabled=bool(d["enabled"]),
        # Issue #1244: "channels": null (explizites JSON-null) faellt bei
        # .get(default) NICHT auf den Default zurueck -> or []
        channels=list(d.get("channels") or []),
    )


def _corridor_range_side(v: Any) -> Optional[float]:
    """Eine range-Seite defensiv zu float|None normalisieren (Adversary F001):
    nicht-castbare Werte (z.B. nicht-numerische Strings) degradieren zu None
    statt einen spaeteren TypeError in corridor_inside() zu erzeugen.
    NaN/Infinity (json.load laesst beide durch) wuerden die Grenze sonst
    stillschweigend unwirksam machen -> nur endliche Werte werden akzeptiert."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _corridor_from_dict(d: Dict[str, Any]) -> Corridor:
    """Parse a single Corridor from a JSON dict (Issue #1231, Slice 1).

    `range` kommt als 2er-Liste [min, max] mit optional null-Seiten (C2).
    Adversary F002: `range` selbst kann fehlen/null/zu kurz/zu lang sein —
    normalisiert defensiv auf genau 2 Elemente statt per Index zu crashen
    (BUG-DATALOSS-GR221-Muster: ein malformter Corridor darf den gesamten
    Trip nie unladbar machen, analog zum fehlerfreien Go-Verhalten).
    Adversary F003: `range` als Skalar (kein list/tuple) ist ebenso
    nicht-iterierbar -> degradiert vor dem list()-Aufruf zu [None, None].
    """
    raw_range = d.get("range") or [None, None]
    if not isinstance(raw_range, (list, tuple)):
        raw_range = [None, None]
    padded = (list(raw_range) + [None, None])[:2]
    return Corridor(
        metric=d["metric"],
        range=[_corridor_range_side(padded[0]), _corridor_range_side(padded[1])],
        notify=bool(d.get("notify", False)),
        mark=bool(d.get("mark", False)),
        prio=d.get("prio"),
    )


def compare_preset_from_dict(data: Dict[str, Any]) -> ComparePreset:
    """Parse ein einzelnes ComparePreset aus einem rohen JSON-Dict (Issue
    #1250, Scheibe 1). Reiner Lese-Kontrakt: keine Normalisierung von
    Deprecated-Feldern (KL-3). `raw` traegt den unveraenderten Eingabe-Dict
    fuer bestehende Dict-Konsumenten, siehe `compare_preset_to_dict`.
    """
    corridors = [_corridor_from_dict(c) for c in (data.get("corridors") or [])]
    return ComparePreset(
        id=data.get("id", ""),
        name=data.get("name", ""),
        user_id=data.get("user_id", ""),
        location_ids=list(data.get("location_ids") or []),
        schedule=data.get("schedule", ""),
        previous_schedule=data.get("previous_schedule", ""),
        profil=data.get("profil", ""),
        hour_from=data.get("hour_from", 0),
        hour_to=data.get("hour_to", 0),
        forecast_hours=data.get("forecast_hours", 0),
        weekday=data.get("weekday"),
        empfaenger=list(data.get("empfaenger") or []),
        letzter_versand=data.get("letzter_versand"),
        top_ort_letzter_versand=data.get("top_ort_letzter_versand"),
        created_at=data.get("created_at", ""),
        archived_at=data.get("archived_at"),
        paused_at=data.get("paused_at"),
        display_config=data.get("display_config"),
        official_alerts_enabled=data.get("official_alerts_enabled"),
        radar_alert_enabled=data.get("radar_alert_enabled"),
        hourly_enabled=data.get("hourly_enabled"),
        alert_cooldown_minutes=data.get("alert_cooldown_minutes"),
        alert_quiet_from=data.get("alert_quiet_from"),
        alert_quiet_to=data.get("alert_quiet_to"),
        official_alert_triggers_enabled=data.get("official_alert_triggers_enabled"),
        # Issue #1258: explizit durchreichen (auch als None) — Parität zu _parse_trip.
        official_warnings=data.get("official_warnings"),
        send_telegram=data.get("send_telegram"),
        send_sms=data.get("send_sms"),
        morning_enabled=data.get("morning_enabled"),
        morning_time=data.get("morning_time"),
        evening_enabled=data.get("evening_enabled"),
        evening_time=data.get("evening_time"),
        end_date=data.get("end_date"),
        corridors=corridors,
        # Issue #1250 Scheibe 5: additiver Diskriminator, roundtrip-erhalten
        # (auch als None) — Parität zu _parse_trip.kind.
        kind=data.get("kind"),
        raw=dict(data),
    )


def load_compare_presets(
    user_id: str,
    data_root: Union[str, Path] = "data",
    strict: bool = False,
) -> List[ComparePreset]:
    """Zentraler Lade-Pfad fuer `compare_presets.json` (Issue #1250, Scheibe 1).

    Ersetzt die bisher 4-fach duplizierten rohen `json.loads`-Reads an den
    5 Lese-Call-Sites (AC-5). Default (`strict=False`) fail-soft identisch
    zum bisherigen Verhalten: fehlende Datei, korruptes JSON/OSError oder
    Nicht-Liste-JSON liefern `[]` (Korruption zusaetzlich mit Warning).
    Reiner Lese-Kontrakt — schreibt beim Laden nichts zurueck (AC-6); der
    RMW-Schreibpfad (`save_compare_preset_status`) bleibt unveraendert
    Dict-basiert.

    `strict=True` (Adversary-Fix F001/F002): korrupte Dateien werfen
    `LoaderError` mit der Original-Parse-Fehlermeldung statt fail-soft `[]`
    zu liefern. Noetig fuer `send_compare_preset` (Einzelversand, #627) und
    `run_compare_presets_daily`, die die urspruengliche Fehlerdiagnose
    (HTTP-404-Detail bzw. ERROR-Log) bewahren muessen; die 3 Alert-Services
    bleiben beim fail-soft-Default.
    """
    path = Path(data_root) / "users" / user_id / "compare_presets.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        if strict:
            raise LoaderError(str(e)) from e
        logger.warning("Corrupt compare_presets.json for %s: %s", user_id, e)
        return []
    if not isinstance(data, list):
        return []
    return [compare_preset_from_dict(d) for d in data]


def compare_preset_to_dict(preset: ComparePreset) -> Dict[str, Any]:
    """Rueckkonvertierung fuer bestehende Dict-Konsumenten (Issue #1250,
    Scheibe 1). Liefert den unveraenderten Roh-Dict (`preset.raw`) statt
    `dataclasses.asdict()`: ein asdict()-Roundtrip wuerde fehlende
    Pointer-Felder (z.B. `radar_alert_enabled`) durch explizites `None`
    ersetzen und `.get(key, default)`-Aufrufe an den Call-Sites
    verhaltensfremd machen (der Default griffe nicht mehr).
    """
    return preset.raw


def _migrate_legacy_alert_rules(data: Dict[str, Any]) -> List[AlertRule]:
    """Generate AlertRule list from legacy report_config fields.

    If `data["alert_rules"]` exists, parse it 1:1 (no re-migration).
    Otherwise, derive Delta-Rules from `report_config.change_threshold_*`.
    `alert_on_changes=False` keeps rules but marks them disabled (preserves
    user thresholds — Datenverlust-Prinzip BUG-DATALOSS-GR221).
    Legacy fields stay in `report_config` as fallback.
    """
    existing = data.get("alert_rules")
    if existing is not None:
        return [_alert_rule_from_dict(r) for r in existing]

    report_config = data.get("report_config", {}) or {}
    enabled = bool(report_config.get("alert_on_changes", False))

    rules: List[AlertRule] = []
    for legacy_field, metric, unit in _LEGACY_DELTA_MAPPING:
        threshold = report_config.get(legacy_field)
        if threshold is None:
            continue
        rules.append(AlertRule(
            id=str(uuid.uuid4()),
            kind=AlertRuleKind.DELTA,
            metric=metric,
            threshold=float(threshold),
            unit=unit,
            severity=AlertSeverity.WARNING,
            enabled=enabled,
        ))
    return rules


class LoaderError(Exception):
    """Error loading configuration."""
    pass


_DATA_ROOT: str | None = None


def load_trip(
    source: Union[str, Path, Dict[str, Any]],
    data_dir: Optional[Union[str, Path]] = None,
    user_id: str = "default",
) -> Optional[Trip]:
    """
    Load a Trip from a JSON file or a dict.

    Accepts either a filesystem path (str/Path) or a pre-parsed JSON dict
    (Issue #205 — Tests use the dict form directly).

    Issue #303: when ``data_dir`` is given, ``source`` is interpreted as a
    trip ID and resolved to ``{data_dir}/users/{user_id}/briefings/{id}.json``
    (Issue #1250 Scheibe 7a Cutover, ADR-0023 -- was ``trips/{id}.json``
    before). Returns ``None`` if that file does not exist (mirrors the Go
    store) or if it carries ``kind="vergleich"`` (a ComparePreset, not a Trip
    -- briefingsDir holds both since the Scheibe 5 migration, AC-30).

    Args:
        source: Path to the JSON file, a trip ID (with ``data_dir``), or a dict.
        data_dir: Optional base data directory; activates trip-ID resolution.
        user_id: User namespace under ``data_dir`` (default: "default").

    Returns:
        Trip object, or None if resolved via ``data_dir`` and not found.

    Raises:
        LoaderError: If the file cannot be loaded or is invalid
    """
    if data_dir is not None and not isinstance(source, dict):
        path = Path(data_dir) / "users" / user_id / "briefings" / f"{source}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("kind") == "vergleich":
            return None
        return _parse_trip(data.get("trip", data))

    if isinstance(source, dict):
        return _parse_trip(source.get("trip", source))

    path = Path(source)
    if not path.exists():
        raise LoaderError(f"Trip file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise LoaderError(f"Invalid JSON in {path}: {e}")

    return _parse_trip(data.get("trip", data))


def load_trip_from_dict(data: Dict[str, Any]) -> Trip:
    """Load a Trip from a dictionary."""
    return _parse_trip(data.get("trip", data))


def _parse_trip(data: Dict[str, Any]) -> Trip:
    """Parse trip data from dictionary."""
    stages = []
    # Issue #1244: explizites JSON-null bei "stages"/"waypoints" faellt bei
    # .get(default) NICHT auf den Default zurueck -> or []
    for stage_data in data.get("stages") or []:
        waypoints = []
        for wp_data in stage_data.get("waypoints") or []:
            time_window = None
            if "time_window" in wp_data:
                time_window = TimeWindow.from_string(wp_data["time_window"])

            waypoint = Waypoint(
                id=wp_data["id"],
                name=wp_data["name"],
                lat=wp_data["lat"],
                lon=wp_data["lon"],
                elevation_m=wp_data["elevation_m"],
                time_window=time_window,
                # Issue #296 — persistierte Naismith-Ankunftszeit erhalten (Datenverlust-Regel)
                arrival_calculated=wp_data.get("arrival_calculated"),
                # Issue #303 — Vorschlags-Metadaten + Override (Datenverlust-Regel)
                origin=wp_data.get("origin"),
                confirmed=wp_data.get("confirmed"),
                suggestion_reason=wp_data.get("suggestion_reason"),
                arrival_override=wp_data.get("arrival_override"),
            )
            waypoints.append(waypoint)

        # Parse start_time if present
        start_time_val = None
        if "start_time" in stage_data:
            from datetime import time as _time
            start_time_val = _time.fromisoformat(stage_data["start_time"])

        stage = Stage(
            id=stage_data["id"],
            name=stage_data["name"],
            date=date.fromisoformat(stage_data["date"]),
            waypoints=waypoints,
            start_time=start_time_val,
        )
        stages.append(stage)

    # Parse aggregation config if present.
    # Default (kein aggregation-Block im JSON) ist ALLGEMEIN — Spec
    # docs/specs/modules/loader_display_config_default.md. Wir nutzen NICHT
    # den DTO-Default `AggregationConfig()` (= WINTERSPORT), weil dann der
    # else-Branch fuer den display_config-Default unten faelschlicherweise
    # ein wintersport-Template waehlen wuerde.
    aggregation = AggregationConfig.for_profile(ActivityProfile.ALLGEMEIN)
    if "aggregation" in data:
        agg_data = data["aggregation"]
        # Issue #111 Validator-Finding: agg_data.get("profile") kann None sein
        # (Key vorhanden, aber Wert null). Defensiv auf ALLGEMEIN mappen.
        profile_str = agg_data.get("profile") or "allgemein"
        try:
            profile = ActivityProfile(profile_str)
        except ValueError:
            # Unbekannter Profile-String -> ALLGEMEIN-Fallback (kein Crash)
            profile = ActivityProfile.ALLGEMEIN
        aggregation = AggregationConfig.for_profile(profile)

        # Apply overrides
        if "overrides" in agg_data:
            overrides = agg_data["overrides"]
            for key, value in overrides.items():
                if hasattr(aggregation, key):
                    if isinstance(value, list):
                        setattr(aggregation, key, [AggregationFunc(v) for v in value])
                    else:
                        setattr(aggregation, key, AggregationFunc(value))

    # Parse weather config if present (Feature 2.6 legacy)
    weather_config = None
    if "weather_config" in data:
        from app.models import TripWeatherConfig
        from datetime import datetime
        wc_data = data["weather_config"]
        weather_config = TripWeatherConfig(
            trip_id=wc_data["trip_id"],
            enabled_metrics=wc_data["enabled_metrics"],
            updated_at=datetime.fromisoformat(wc_data["updated_at"])
        )

    # Parse unified display config (Feature 2.6 v2) or migrate from old weather_config
    display_config = None
    if "display_config" in data:
        # Issue #1244: "display_config": null (explizites JSON-null) darf
        # nicht crashen -- fail-soft heisst hier: valider Default statt
        # AttributeError in _parse_display_config.
        display_config = _parse_display_config(data["display_config"] or {})
    elif weather_config is not None:
        display_config = _migrate_weather_config(weather_config)
    else:
        # Issue #111: kein display_config + kein weather_config -> profil-abhaengiger Default
        from app.metric_catalog import build_default_display_config_for_profile
        profile = (
            aggregation.profile
            if aggregation is not None and getattr(aggregation, "profile", None) is not None
            else ActivityProfile.ALLGEMEIN
        )
        display_config = build_default_display_config_for_profile(data["id"], profile)

    # Parse report config if present (Feature 3.5)
    report_config = None
    if "report_config" in data:
        from app.models import TripReportConfig
        from datetime import datetime, time
        rc_data = data["report_config"]
        dc_data = data.get("display_config") or {}
        report_config = TripReportConfig(
            trip_id=rc_data.get("trip_id", data["id"]),
            enabled=rc_data.get("enabled", True),
            morning_time=time.fromisoformat(rc_data.get("morning_time", "07:00:00")),
            evening_time=time.fromisoformat(rc_data.get("evening_time", "18:00:00")),
            send_email=rc_data.get("send_email", True),
            send_sms=rc_data.get("send_sms", False),
            send_telegram=rc_data.get("send_telegram", False),
            alert_on_changes=rc_data.get("alert_on_changes", True),
            change_threshold_temp_c=rc_data.get("change_threshold_temp_c", 5.0),
            change_threshold_wind_kmh=rc_data.get("change_threshold_wind_kmh", 20.0),
            change_threshold_precip_mm=rc_data.get("change_threshold_precip_mm", 10.0),
            wind_exposition_min_elevation_m=rc_data.get("wind_exposition_min_elevation_m"),
            show_compact_summary=rc_data.get(
                "show_compact_summary",
                dc_data.get("show_compact_summary", True),
            ),
            show_daylight=rc_data.get("show_daylight", True),
            multi_day_trend_reports=rc_data.get(
                "multi_day_trend_reports",
                dc_data.get("multi_day_trend_reports", ["evening"]),
            ),
            show_stage_stats=rc_data.get("show_stage_stats", True),
            show_quick_take_tags=rc_data.get("show_quick_take_tags", True),
            show_stability=rc_data.get("show_stability", True),
            show_highlights=rc_data.get("show_highlights", True),
            daily_summary_metrics=rc_data.get(
                "daily_summary_metrics",
                ["precipitation", "wind", "visibility", "thunder"],
            ),
            show_metrics_summary=rc_data.get("show_metrics_summary", False),
            show_outlook=rc_data.get("show_outlook", True),
            email_format=rc_data.get("email_format", "full"),
            show_yesterday_comparison=rc_data.get("show_yesterday_comparison", True),
            paused_until=datetime.fromisoformat(rc_data["paused_until"]) if rc_data.get("paused_until") else None,
            skip_next=rc_data.get("skip_next", False),
            updated_at=datetime.fromisoformat(rc_data["updated_at"]) if "updated_at" in rc_data else datetime.now(),
        )

    # Issue #205: Alert Rules — either directly from JSON or migrated from legacy.
    alert_rules = _migrate_legacy_alert_rules(data)

    # Issue #1231 (Slice 1): Corridors — additiv neben alert_rules, kein
    # Legacy-Migrationspfad in Slice 1 (s. scripts/migrate_1231_corridors.py, Slice 2).
    corridors = [_corridor_from_dict(c) for c in (data.get("corridors") or [])]

    # Issue #1250 Scheibe 4: additive flache Slot-/Kanal-Felder aus dem bereits
    # geparsten `report_config` ABLEITEN (Dual-Read). `report_config.enabled`
    # ist der EINZIGE Schalter (kein getrenntes morning/evening-Flag) -> steuert
    # beide abgeleiteten *_enabled-Felder, verifiziert gegen
    # trip_report_scheduler._get_active_trips (rc.enabled gated dort ebenfalls
    # morning UND evening gleichermassen). report_config bleibt Single Source.
    morning_time = report_config.morning_time.isoformat() if report_config else None
    evening_time = report_config.evening_time.isoformat() if report_config else None
    morning_enabled = report_config.enabled if report_config else None
    evening_enabled = report_config.enabled if report_config else None
    send_email = report_config.send_email if report_config else None
    send_sms = report_config.send_sms if report_config else None
    send_telegram = report_config.send_telegram if report_config else None

    # Issue #991: unbekannte Top-Level-Keys generisch auffangen (roundtrip-erhalten),
    # statt pro Feld ein weiteres Einzelattribut anzubauen.
    KNOWN_TOP_LEVEL = {
        "id", "name", "stages", "avalanche_regions", "aggregation", "shortcode", "activity",
        "region", "archived_at", "paused_at", "official_alerts_enabled",
        "official_alert_triggers_enabled", "official_warnings", "weather_config",
        "display_config", "report_config", "alert_rules", "corridors", "alert_cooldown_minutes",
        "alert_quiet_from", "alert_quiet_to", "trip",
        # Issue #1258 S3: additives Trip-Kanal-Set (D2), None = Legacy.
        "alert_channels",
        # Issue #1250 Scheibe 4 Fix-Loop F002 (Adversary BROKEN): diese Top-
        # Level-Keys sind ABGELEITET (nicht autoritativ). Fehlten sie in
        # KNOWN_TOP_LEVEL, wuerde ein zuvor persistierter Alt-Wert ueber den
        # `extra`-Mechanismus (setdefault, s.u.) als "fremdes Feld" konserviert
        # und einen stalen Stand vortaeuschen, obwohl die Quelle (report_config/
        # Stages) laengst verschwunden ist.
        "end_date", "morning_time", "evening_time", "morning_enabled",
        "evening_enabled", "send_email", "send_sms", "send_telegram",
        # Issue #1250 Scheibe 5: additiver Diskriminator (roundtrip-erhalten,
        # nicht via extra) — s. Trip.kind.
        "kind",
    }
    extra = {k: v for k, v in data.items() if k not in KNOWN_TOP_LEVEL}

    trip = Trip(
        id=data["id"],
        name=data["name"],
        stages=stages,
        avalanche_regions=data.get("avalanche_regions") or [],
        aggregation=aggregation,
        weather_config=weather_config,
        display_config=display_config,
        report_config=report_config,
        alert_rules=alert_rules,
        corridors=corridors,  # Issue #1231, Slice 1
        alert_cooldown_minutes=data.get("alert_cooldown_minutes"),
        alert_quiet_from=data.get("alert_quiet_from"),
        alert_quiet_to=data.get("alert_quiet_to"),
        shortcode=data.get("shortcode", ""),
        activity=data.get("activity", ""),  # Issue #802
        region=data.get("region", ""),  # Issue #805
        archived_at=data.get("archived_at"),  # Issue #805
        paused_at=data.get("paused_at"),  # Issue #995: Go-Feld paused_at — roundtrip-erhalten
        official_alerts_enabled=data.get("official_alerts_enabled"),  # Issue #1087
        official_alert_triggers_enabled=data.get("official_alert_triggers_enabled"),  # Issue #1088
        # Issue #1258: explizit durchreichen (auch als None) -> unterscheidet
        # geladenen Bestandstrip (noch nicht migriert) von einer Neuanlage.
        official_warnings=data.get("official_warnings"),
        # Issue #1258 S3 (D2): explizit durchreichen (auch als None) -> None
        # bleibt Legacy-Verhalten (s. Trip.alert_channels Docstring).
        alert_channels=data.get("alert_channels"),
        extra=extra,  # Issue #991: unmodellierte Top-Level-Keys
        # Issue #1250 Scheibe 4: abgeleitete flache Slot-/Kanal-Felder (Dual-Read)
        morning_time=morning_time,
        evening_time=evening_time,
        morning_enabled=morning_enabled,
        evening_enabled=evening_enabled,
        send_email=send_email,
        send_sms=send_sms,
        send_telegram=send_telegram,
        # Issue #1250 Scheibe 5: explizit durchreichen (auch als None) —
        # Parität zu compare_preset_from_dict.kind.
        kind=data.get("kind"),
    )
    return trip


# Issue #629: Legacy-Modi scale/symbol verschwinden aus der UI. Beim Laden werden
# sie auf None normalisiert (Rückfall auf default_format_mode, der für diese
# Metriken GENAU scale/symbol ist) + use_friendly_format=True → bit-identische
# Briefing-Darstellung, aber keine wählbaren scale/symbol-Reste in der Persistenz.
_LEGACY_FORMAT_MODES = {"scale", "symbol"}


def _normalize_legacy_mode(mc_data: Dict[str, Any]) -> tuple[Optional[str], bool]:
    """(format_mode, use_friendly_format) mit scale/symbol→None+friendly-Migration."""
    mode = mc_data.get("format_mode")
    if mode in _LEGACY_FORMAT_MODES:
        return None, True
    return mode, mc_data.get("use_friendly_format", True)


def _migrate_metric_alert_levels(levels: Any) -> Any:
    """Issue #959: snow_line → freezing_level (Read-Modify-Write, kein Datenverlust).

    Nullgradgrenze ist zu EINER Alert-Metrik (freezing_level) konsolidiert. Alt-
    persistierte Trips mit `metric_alert_levels.snow_line` werden beim Laden
    umbenannt — bestehendes Dict kopieren, nur diesen Key verschieben, alle
    anderen Felder unangetastet lassen (BUG-DATALOSS-GR221-Lehre). Ein bereits
    vorhandener freezing_level-Eintrag gewinnt (kein Überschreiben).
    """
    if not isinstance(levels, dict) or "snow_line" not in levels:
        return levels
    migrated = dict(levels)
    value = migrated.pop("snow_line")
    migrated.setdefault("freezing_level", value)
    return migrated


def _parse_display_config(data: Dict[str, Any]) -> "UnifiedWeatherDisplayConfig":
    """Parse UnifiedWeatherDisplayConfig from dict."""
    from datetime import datetime as _dt
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig

    raw_metrics = data.get("metrics") or []
    # Issue #360 (F002): bucket/order pro Metrik aufloesen. auto_distribute wird
    # IMMER auf die aktiven Metrik-IDs angewandt, damit auch teil-migrierte
    # Configs (eine Metrik hat bucket/order, andere nicht) korrekt sind:
    # nicht-migrierte AKTIVE Metriken erben das auto_distribute-Ergebnis statt
    # stillschweigend auf ("secondary", 0) zu fallen.
    bucket_order_by_id: Dict[str, tuple] = {}
    if raw_metrics:
        from src.output.renderers.channel_layout import auto_distribute
        active_ids = [mc["metric_id"] for mc in raw_metrics if mc.get("enabled", True)]
        for dist in auto_distribute(active_ids):
            bucket_order_by_id[dist.metric_id] = (dist.bucket, dist.order)

    metrics = []
    for mc_data in raw_metrics:
        mid = mc_data["metric_id"]
        if "bucket" in mc_data or "order" in mc_data:
            # Explizit gesetzt (voll-/teil-migriert) → unveraendert uebernehmen.
            bucket = mc_data.get("bucket", "primary")
            order = mc_data.get("order", 0)
        else:
            # Nicht migriert: aktive Metrik erbt auto_distribute; wirklich
            # unbekannte/inaktive fallen auf secondary/0 (erscheinen nicht im
            # Layout).
            bucket, order = bucket_order_by_id.get(mid, ("secondary", 0))
        # Issue #435: nur explizite format_mode-Felder ins Modell übernehmen,
        # damit Roundtrip-Tests use_friendly_format bit-identisch erhalten.
        # Issue #629: scale/symbol → None + use_friendly_format=True normalisieren.
        explicit_mode, friendly = _normalize_legacy_mode(mc_data)
        metrics.append(MetricConfig(
            metric_id=mid,
            enabled=mc_data.get("enabled", True),
            aggregations=mc_data.get("aggregations", ["min", "max"]),
            morning_enabled=mc_data.get("morning_enabled"),
            evening_enabled=mc_data.get("evening_enabled"),
            use_friendly_format=friendly,
            format_mode=explicit_mode,
            alert_enabled=mc_data.get("alert_enabled", False),
            alert_threshold=mc_data.get("alert_threshold"),
            horizons=mc_data.get("horizons"),
            bucket=bucket,
            order=order,
            sms_threshold=mc_data.get("sms_threshold"),
        ))

    # Issue #429: kanal-spezifische Layouts laden (optional, backward-compat).
    # Wenn channel_layouts fehlt ODER alle Kanal-Listen leer sind → None,
    # damit get_metrics_for_channel auf die globale Liste zurückfällt.
    per_channel_layouts: Optional[Dict[str, List[MetricConfig]]] = None
    raw_channel_layouts = data.get("channel_layouts")
    if (
        raw_channel_layouts
        and isinstance(raw_channel_layouts, dict)
        and any(raw_channel_layouts.values())
    ):
        per_channel_layouts = {}
        for ch, ch_metrics in raw_channel_layouts.items():
            if not isinstance(ch_metrics, list):
                continue
            ch_parsed: List[MetricConfig] = []
            for mc_data in ch_metrics:
                ch_explicit_mode, ch_friendly = _normalize_legacy_mode(mc_data)
                ch_parsed.append(MetricConfig(
                    metric_id=mc_data["metric_id"],
                    enabled=mc_data.get("enabled", True),
                    aggregations=mc_data.get("aggregations", ["min", "max"]),
                    morning_enabled=mc_data.get("morning_enabled"),
                    evening_enabled=mc_data.get("evening_enabled"),
                    use_friendly_format=ch_friendly,
                    format_mode=ch_explicit_mode,
                    alert_enabled=mc_data.get("alert_enabled", False),
                    alert_threshold=mc_data.get("alert_threshold"),
                    horizons=mc_data.get("horizons"),
                    bucket=mc_data.get("bucket", "primary"),
                    order=mc_data.get("order", 0),
                    sms_threshold=mc_data.get("sms_threshold"),
                ))
            per_channel_layouts[ch] = ch_parsed

    # Issue #434: per-report-Overrides laden (optional, backward-compat).
    per_report_layouts: Optional[Dict[str, Dict[str, List[MetricConfig]]]] = None
    raw_per_report = data.get("channel_layouts_per_report")
    if raw_per_report and isinstance(raw_per_report, dict):
        per_report_layouts = {}
        for report_type, channels_dict in raw_per_report.items():
            if not isinstance(channels_dict, dict):
                continue
            per_report_layouts[report_type] = {}
            for ch, ch_metrics in channels_dict.items():
                if not isinstance(ch_metrics, list):
                    continue
                pr_parsed: List[MetricConfig] = []
                for mc_data in ch_metrics:
                    pr_mode, pr_friendly = _normalize_legacy_mode(mc_data)
                    pr_parsed.append(MetricConfig(
                        metric_id=mc_data["metric_id"],
                        enabled=mc_data.get("enabled", True),
                        aggregations=mc_data.get("aggregations", ["min", "max"]),
                        morning_enabled=mc_data.get("morning_enabled"),
                        evening_enabled=mc_data.get("evening_enabled"),
                        use_friendly_format=pr_friendly,
                        format_mode=pr_mode,
                        alert_enabled=mc_data.get("alert_enabled", False),
                        alert_threshold=mc_data.get("alert_threshold"),
                        horizons=mc_data.get("horizons"),
                        bucket=mc_data.get("bucket", "primary"),
                        order=mc_data.get("order", 0),
                        sms_threshold=mc_data.get("sms_threshold"),
                    ))
                per_report_layouts[report_type][ch] = pr_parsed
        if not per_report_layouts:
            per_report_layouts = None

    return UnifiedWeatherDisplayConfig(
        trip_id=data.get("trip_id", ""),
        metrics=metrics,
        preset_name=data.get("preset_name"),
        show_night_block=data.get("show_night_block", True),
        night_interval_hours=data.get("night_interval_hours", 2),
        thunder_forecast_days=data.get("thunder_forecast_days", 2),
        multi_day_trend_reports=data.get("multi_day_trend_reports", ["evening"] if data.get("show_multi_day_trend", True) else []),
        sms_metrics=data.get("sms_metrics") or [],
        per_channel_layouts=per_channel_layouts,
        per_report_layouts=per_report_layouts,
        telegram_kurzform=data.get("telegram_kurzform", False),
        alert_preset=data.get("alert_preset"),  # Issue #846
        metric_alert_levels=_migrate_metric_alert_levels(data.get("metric_alert_levels")),  # Issue #946/#959
        updated_at=_dt.fromisoformat(data["updated_at"]) if "updated_at" in data else _dt.now(),
    )


# Migration map: old metric name -> (new metric_id, aggregation)
_OLD_METRIC_MAP: Dict[str, tuple] = {
    "temp_min_c": ("temperature", "min"),
    "temp_max_c": ("temperature", "max"),
    "temp_avg_c": ("temperature", "avg"),
    "wind_max_kmh": ("wind", "max"),
    "gust_max_kmh": ("gust", "max"),
    "precip_sum_mm": ("precipitation", "sum"),
    "cloud_avg_pct": ("cloud_total", "avg"),
    "humidity_avg_pct": ("humidity", "avg"),
    "thunder_level_max": ("thunder", "max"),
    "dewpoint_avg_c": ("dewpoint", "avg"),
    "pressure_avg_hpa": ("pressure", "avg"),
    "wind_chill_min_c": ("wind_chill", "min"),
}


def _migrate_weather_config(old_config) -> "UnifiedWeatherDisplayConfig":
    """
    Migrate old TripWeatherConfig to UnifiedWeatherDisplayConfig.

    Groups old metric names by new metric_id and builds MetricConfig entries.
    Metrics not in old config are set to disabled.
    """
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    from app.metric_catalog import get_all_metrics

    # Collect enabled metric IDs with their aggregations from old config
    enabled_metrics: Dict[str, list] = {}
    for old_name in old_config.enabled_metrics:
        if old_name in _OLD_METRIC_MAP:
            metric_id, agg = _OLD_METRIC_MAP[old_name]
            if metric_id not in enabled_metrics:
                enabled_metrics[metric_id] = []
            enabled_metrics[metric_id].append(agg)

    # Build MetricConfig list for all catalog metrics
    metrics = []
    for m in get_all_metrics():
        if m.id in enabled_metrics:
            metrics.append(MetricConfig(
                metric_id=m.id,
                enabled=True,
                aggregations=enabled_metrics[m.id],
            ))
        else:
            metrics.append(MetricConfig(
                metric_id=m.id,
                enabled=False,
                aggregations=list(m.default_aggregations),
            ))

    return UnifiedWeatherDisplayConfig(
        trip_id=old_config.trip_id,
        metrics=metrics,
        updated_at=old_config.updated_at,
    )


def load_user(path: Union[str, Path]) -> User:
    """
    Load a User from a JSON file.

    Args:
        path: Path to the JSON file

    Returns:
        User object

    Raises:
        LoaderError: If the file cannot be loaded or is invalid
    """
    path = Path(path)
    if not path.exists():
        raise LoaderError(f"User file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise LoaderError(f"Invalid JSON in {path}: {e}")

    return _parse_user(data)


def load_user_from_dict(data: Dict[str, Any]) -> User:
    """Load a User from a dictionary."""
    return _parse_user(data)


def _parse_user(data: Dict[str, Any]) -> User:
    """Parse user data from dictionary."""
    user_data = data.get("user", data)

    # Parse preferences
    prefs_data = user_data.get("preferences", {})
    preferences = UserPreferences(
        units=prefs_data.get("units", "metric"),
        language=prefs_data.get("language", "de"),
        wind_chill_warning=prefs_data.get("wind_chill_warning", -20),
        avalanche_level_warning=prefs_data.get("avalanche_level_warning", 3),
        wind_warning=prefs_data.get("wind_warning", 50),
        gust_warning=prefs_data.get("gust_warning", 70),
        include_debug=prefs_data.get("include_debug", False),
        compact_format=prefs_data.get("compact_format", False),
    )

    # Parse saved locations
    locations: Dict[str, SavedLocation] = {}
    for loc_id, loc_data in data.get("locations", {}).items():
        locations[loc_id] = SavedLocation(
            id=loc_id,
            name=loc_data["name"],
            lat=loc_data["lat"],
            lon=loc_data["lon"],
            elevation_m=loc_data["elevation_m"],
            region=loc_data.get("region"),
        )

    # Parse subscriptions
    location_subs: List[LocationSubscription] = []
    trip_subs: List[TripSubscription] = []

    for sub_data in data.get("subscriptions", []):
        sub_type = sub_data.get("type", "location")

        if sub_type == "location":
            location_subs.append(LocationSubscription(
                id=sub_data.get("id", sub_data.get("name", "")),
                name=sub_data.get("name", ""),
                location_ref=sub_data["location_ref"],
                schedule=Schedule(sub_data.get("schedule", "daily_evening")),
                report_type=sub_data.get("report_type", "evening"),
                enabled=sub_data.get("enabled", True),
            ))
        elif sub_type == "trip":
            trip_subs.append(TripSubscription(
                id=sub_data.get("id", sub_data.get("name", "")),
                name=sub_data.get("name", ""),
                trip_file=sub_data["trip_file"],
                trigger=TriggerTiming(sub_data.get("trigger", "2_days_before")),
                enabled=sub_data.get("enabled", True),
            ))

    return User(
        id=user_data["id"],
        email=user_data["email"],
        preferences=preferences,
        locations=locations,
        location_subscriptions=location_subs,
        trip_subscriptions=trip_subs,
    )


# =============================================================================
# Data Directory Helpers
# =============================================================================

def get_data_root() -> Path:
    """Resolve the data ROOT directory (parent of ``users/``).

    Honors the module-level ``_DATA_ROOT`` override (used in tests, Issue
    #1133) and, as a fallback, the ``GZ_DATA_DIR`` environment variable.
    Priority: ``_DATA_ROOT`` > ``GZ_DATA_DIR`` > default ``data``.

    Any code that needs the data directory WITHOUT going through
    ``get_data_dir()``'s per-user ``users/<id>`` join (e.g. Issue #1219's
    Resend-Allowlist-Loader, which scans ALL user directories) MUST use this
    function rather than reading ``GZ_DATA_DIR`` directly — otherwise the
    autouse test-isolation fixture (``tests/conftest.py``, Issue #1133) is
    silently bypassed and the real ``data/users/`` tree could be read.
    """
    import os as _os
    import sys as _sys
    _root = getattr(_sys.modules[__name__], "_DATA_ROOT", None) or _os.environ.get(
        "GZ_DATA_DIR"
    )
    return Path(_root) if _root else Path("data")


def get_data_dir(user_id: str = "default") -> Path:
    """Get the data directory for a user.

    Honors the module-level ``_DATA_ROOT`` override (used in tests) and,
    as a fallback, the ``GZ_DATA_DIR`` environment variable (Issue #1133).
    Priority: ``_DATA_ROOT`` > ``GZ_DATA_DIR`` > default ``data/users``.
    """
    return get_data_root() / "users" / user_id


def get_locations_dir(user_id: str = "default") -> Path:
    """Get the locations directory for a user."""
    return get_data_dir(user_id) / "locations"


def get_trips_dir(user_id: str = "default") -> Path:
    """Get the (legacy, pre-Cutover) trips directory for a user.

    Issue #1250 Scheibe 7a: load_all_trips/load_trip/save_trip no longer
    read/write here (see get_briefings_dir) -- this stays as a reference to
    the old location (Rollback-Fähigkeit, AC-26) and for the historical
    per-user directory bootstrap.
    """
    return get_data_dir(user_id) / "trips"


def get_briefings_dir(user_id: str = "default") -> Path:
    """Get the briefings directory for a user (Issue #1250 Scheibe 7a
    Cutover, ADR-0023). route-Entitäten (Trips) leben seit dem Cutover hier;
    vergleich-Entitäten (ComparePresets) bleiben unberührt auf
    compare_presets.json (AC-30)."""
    return get_data_dir(user_id) / "briefings"


def get_snapshots_dir(user_id: str = "default") -> Path:
    """Get the weather snapshots directory for a user."""
    return get_data_dir(user_id) / "weather_snapshots"


def list_all_user_ids(data_dir: str = "data") -> list[str]:
    """Return all user IDs found under data/users/, real users first (Issue #1013).

    Args:
        data_dir: Root data directory (default: "data")

    Returns:
        Sorted list of user_id strings (excludes entries starting with 'test' or '_'),
        with real users sorted before remaining test-classified users
        (is_test_user_id, z.B. tg-live-e2e/tdd-*) — deterministischer Lookup-Vorrang
        unabhängig von der Dateisystem-Iterationsreihenfolge.
    """
    from app.config import is_test_user_id

    users_root = Path(data_dir) / "users"
    if not users_root.exists():
        return []
    names = sorted(
        d.name for d in users_root.iterdir()
        if d.is_dir()
        and not d.name.startswith("_")
        and not d.name.startswith("test")
    )
    real = [n for n in names if not is_test_user_id(n, data_dir=data_dir)]
    test = [n for n in names if is_test_user_id(n, data_dir=data_dir)]
    return real + test


def lookup_user_by_email(email: str, data_dir: str = "data") -> str | None:
    """Find user_id whose mail_to matches the given email address (case-insensitive).

    Args:
        email: Sender email address to match against user profiles
        data_dir: Root data directory (default: "data")

    Returns:
        Matching user_id or None if no match found
    """
    for uid in list_all_user_ids(data_dir):
        profile_path = Path(data_dir) / "users" / uid / "user.json"
        if profile_path.exists():
            try:
                profile = json.loads(profile_path.read_text(encoding="utf-8"))
                if profile.get("mail_to", "").lower() == email.lower():
                    return uid
            except Exception:
                continue
    return None


def lookup_user_by_telegram_chat_id(chat_id: str, data_dir: str = "data") -> str | None:
    """Find user_id whose telegram_chat_id matches the given chat_id (int/str-tolerant).

    Args:
        chat_id: Telegram chat ID to match (compared as strings)
        data_dir: Root data directory (default: "data")

    Returns:
        Matching user_id or None if no match found
    """
    for uid in list_all_user_ids(data_dir):
        profile_path = Path(data_dir) / "users" / uid / "user.json"
        if profile_path.exists():
            try:
                profile = json.loads(profile_path.read_text(encoding="utf-8"))
                if str(profile.get("telegram_chat_id", "")) == str(chat_id):
                    return uid
            except Exception:
                continue
    return None


# =============================================================================
# Location CRUD
# =============================================================================

def load_all_locations(user_id: str = "default") -> List[SavedLocation]:
    """
    Load all locations for a user.

    Args:
        user_id: User identifier (default: "default")

    Returns:
        List of SavedLocation objects
    """
    locations_dir = get_locations_dir(user_id)
    if not locations_dir.exists():
        return []

    locations = []
    for path in locations_dir.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            from app.profile import ActivityProfile
            activity_profile_str = data.get("activity_profile", "allgemein")
            display_config_data = data.get("display_config")
            display_config = _parse_display_config(display_config_data) if display_config_data else None
            elevation_m = data.get("elevation_m")
            if elevation_m is None:
                logger.warning(
                    "Location %s (%s) ohne elevation_m geladen — Go/Python-Vertragsbruch #1039",
                    data.get("id", path.stem),
                    path,
                )
            locations.append(SavedLocation(
                id=data.get("id", path.stem),
                name=data["name"],
                lat=data["lat"],
                lon=data["lon"],
                elevation_m=elevation_m,
                region=data.get("region"),
                bergfex_slug=data.get("bergfex_slug"),
                activity_profile=ActivityProfile(activity_profile_str),
                display_config=display_config,
            ))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return locations


def save_location(location: SavedLocation, user_id: str = "default") -> Path:
    """
    Save a location to JSON file.

    Args:
        location: SavedLocation object to save
        user_id: User identifier (default: "default")

    Returns:
        Path to the saved file
    """
    locations_dir = get_locations_dir(user_id)
    locations_dir.mkdir(parents=True, exist_ok=True)

    path = locations_dir / f"{location.id}.json"
    data = {
        "id": location.id,
        "name": location.name,
        "lat": location.lat,
        "lon": location.lon,
        "elevation_m": location.elevation_m,
        "region": location.region,
        "bergfex_slug": location.bergfex_slug,
        "activity_profile": location.activity_profile.value,
    }
    if location.display_config is not None:
        dc = location.display_config
        data["display_config"] = {
            "trip_id": dc.trip_id,
            "metrics": [_metric_to_dict(mc) for mc in dc.metrics],
            "show_night_block": dc.show_night_block,
            "night_interval_hours": dc.night_interval_hours,
            "thunder_forecast_days": dc.thunder_forecast_days,
            "multi_day_trend_reports": dc.multi_day_trend_reports,
            "sms_metrics": dc.sms_metrics,
            "telegram_kurzform": dc.telegram_kurzform,
            "updated_at": dc.updated_at.isoformat(),
        }
        # Issue #429: per_channel_layouts serialisieren (latenter Bug-Fix)
        if dc.per_channel_layouts is not None:
            data["display_config"]["channel_layouts"] = {
                ch: [_metric_to_dict(mc) for mc in metrics]
                for ch, metrics in dc.per_channel_layouts.items()
            }
        # Issue #434: per_report_layouts serialisieren
        if dc.per_report_layouts is not None:
            data["display_config"]["channel_layouts_per_report"] = {
                report_type: {
                    ch: [_metric_to_dict(mc) for mc in metrics]
                    for ch, metrics in channels_dict.items()
                }
                for report_type, channels_dict in dc.per_report_layouts.items()
            }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return path


def delete_location(location_id: str, user_id: str = "default") -> None:
    """
    Delete a location file.

    Args:
        location_id: ID of the location to delete
        user_id: User identifier (default: "default")
    """
    path = get_locations_dir(user_id) / f"{location_id}.json"
    if path.exists():
        path.unlink()


# =============================================================================
# Trip CRUD
# =============================================================================

def load_all_trips(
    user_id: str = "default",
    include_archived: bool = False,
) -> List[Trip]:
    """
    Load all trips for a user.

    Issue #1250 Scheibe 7a Cutover (ADR-0023): reads ``briefings/*.json``
    instead of ``trips/*.json``. ``briefings/`` also holds ComparePresets
    (``kind="vergleich"``, Scheibe 5 migration) -- those are skipped here,
    they stay reachable via ``load_compare_presets`` (AC-30).

    Args:
        user_id: User identifier (default: "default")
        include_archived: When False (default), trips with archived_at set are
            excluded. Set True for shortcode deduplication (Bug #824).

    Returns:
        List of Trip objects
    """
    briefings_dir = get_briefings_dir(user_id)
    if not briefings_dir.exists():
        return []

    trips = []
    for path in briefings_dir.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if raw.get("kind") == "vergleich":
                continue
            trip = load_trip(raw)
            if not include_archived and trip.archived_at is not None:
                continue
            trips.append(trip)
        except Exception as e:
            # Issue #111 Validator-Finding: ein einzelner kaputter Trip darf
            # NICHT den gesamten Load fuer alle anderen Trips desselben Users
            # blockieren. Frueher fing das `except LoaderError:` nur einen Teil
            # ab — generische Exceptions (z.B. ValueError aus
            # ActivityProfile(None)) propagierten als HTTP 500.
            # Issue #1244 (AC-6): ein unladbarer Trip ist ein Datenintegritaets-
            # problem, kein erwartbarer Nebeneffekt -- warning-Level hat
            # kaputte Trips monatelang unsichtbar gemacht.
            logger.error("Skipping corrupt trip %s: %s", path.name, e)
            continue
    return trips


def _trip_to_dict(trip: Trip) -> Dict[str, Any]:
    """Convert a Trip object to a dictionary for JSON serialization."""
    stages_data = []
    for stage in trip.stages:
        waypoints_data = []
        for wp in stage.waypoints:
            wp_dict: Dict[str, Any] = {
                "id": wp.id,
                "name": wp.name,
                "lat": wp.lat,
                "lon": wp.lon,
                "elevation_m": wp.elevation_m,
            }
            if wp.time_window:
                wp_dict["time_window"] = str(wp.time_window)
            # Issue #296 — persistierte Naismith-Ankunftszeit erhalten (omitempty-Äquivalent)
            if wp.arrival_calculated:
                wp_dict["arrival_calculated"] = wp.arrival_calculated
            # Issue #303 — Vorschlags-Metadaten + Override (omitempty-Äquivalent).
            # confirmed: `is not None` statt truthy — False muss persistiert werden.
            if wp.origin:
                wp_dict["origin"] = wp.origin
            if wp.confirmed is not None:
                wp_dict["confirmed"] = wp.confirmed
            if wp.suggestion_reason:
                wp_dict["suggestion_reason"] = wp.suggestion_reason
            if wp.arrival_override:
                wp_dict["arrival_override"] = wp.arrival_override
            waypoints_data.append(wp_dict)

        stage_dict = {
            "id": stage.id,
            "name": stage.name,
            "date": stage.date.isoformat(),
            "waypoints": waypoints_data,
        }
        if stage.start_time is not None:
            # #991 AC-5: kanonisches HH:MM (Go naismith.go:24, Frontend
            # DEFAULT_START_TIME) statt .isoformat() mit Sekunden.
            stage_dict["start_time"] = stage.start_time.strftime("%H:%M")
        stages_data.append(stage_dict)

    data = {
        "id": trip.id,
        "name": trip.name,
        "stages": stages_data,
        "avalanche_regions": trip.avalanche_regions,
        "aggregation": {
            "profile": trip.aggregation.profile.value,
        },
    }

    if trip.shortcode:
        data["shortcode"] = trip.shortcode

    if trip.activity:
        data["activity"] = trip.activity

    if trip.region:
        data["region"] = trip.region

    if trip.archived_at:
        data["archived_at"] = trip.archived_at

    if trip.paused_at:  # Issue #995: Go-Feld paused_at — roundtrip-erhalten
        data["paused_at"] = trip.paused_at

    # Issue #1087: nur schreiben wenn "is not None" — False muss persistieren
    # (Read-Modify-Write, BUG-DATALOSS-GR221), nicht wie ein falsy-Wert wegfallen.
    if trip.official_alerts_enabled is not None:
        data["official_alerts_enabled"] = trip.official_alerts_enabled

    # Issue #1088: analog #1087 — RMW, False muss persistieren.
    if trip.official_alert_triggers_enabled is not None:
        data["official_alert_triggers_enabled"] = trip.official_alert_triggers_enabled

    # Issue #1258: additiv, RMW — None (unmigrierter Bestand) bleibt ungeschrieben.
    if trip.official_warnings is not None:
        data["official_warnings"] = trip.official_warnings

    # Issue #1250 Scheibe 5: additiver Diskriminator, omitempty-guarded (RMW)
    # — None (unmigrierter Bestand) bleibt ungeschrieben, kein erzwungener
    # Default in den alten Schreibpfaden (ADR-0023, rein additiv).
    if trip.kind is not None:
        data["kind"] = trip.kind

    # Issue #1258 S3 (D2): additiv, RMW — None (Legacy) bleibt ungeschrieben.
    if trip.alert_channels is not None:
        data["alert_channels"] = trip.alert_channels

    # Serialize weather config (Feature 2.6 legacy, preserved for migration)
    if trip.weather_config:
        data["weather_config"] = {
            "trip_id": trip.weather_config.trip_id,
            "enabled_metrics": trip.weather_config.enabled_metrics,
            "updated_at": trip.weather_config.updated_at.isoformat()
        }

    # Serialize unified display config (Feature 2.6 v2)
    if trip.display_config:
        dc = trip.display_config
        data["display_config"] = {
            "trip_id": dc.trip_id,
            "metrics": [_metric_to_dict(mc) for mc in dc.metrics],
            "show_night_block": dc.show_night_block,
            "night_interval_hours": dc.night_interval_hours,
            "thunder_forecast_days": dc.thunder_forecast_days,
            "multi_day_trend_reports": dc.multi_day_trend_reports,
            "sms_metrics": dc.sms_metrics,
            "telegram_kurzform": dc.telegram_kurzform,
            "updated_at": dc.updated_at.isoformat(),
            **({"preset_name": dc.preset_name} if dc.preset_name is not None else {}),
            # Issue #946: metric_alert_levels ist die einzige Alert-Quelle — MUSS
            # persistiert werden, sonst verliert der Trip beim Reload seine Alert-
            # Konfiguration. alert_preset bleibt für Backward-Compat-Migration erhalten.
            **({"alert_preset": dc.alert_preset} if dc.alert_preset is not None else {}),
            **({"metric_alert_levels": dc.metric_alert_levels}
               if dc.metric_alert_levels is not None else {}),
        }
        # Issue #429: per_channel_layouts serialisieren (latenter Bug-Fix)
        if dc.per_channel_layouts is not None:
            data["display_config"]["channel_layouts"] = {
                ch: [_metric_to_dict(mc) for mc in metrics]
                for ch, metrics in dc.per_channel_layouts.items()
            }
        # Issue #434: per_report_layouts serialisieren
        if dc.per_report_layouts is not None:
            data["display_config"]["channel_layouts_per_report"] = {
                report_type: {
                    ch: [_metric_to_dict(mc) for mc in metrics]
                    for ch, metrics in channels_dict.items()
                }
                for report_type, channels_dict in dc.per_report_layouts.items()
            }

    # Serialize alert cooldown and quiet hours (Issue #181)
    if trip.alert_cooldown_minutes is not None:
        data["alert_cooldown_minutes"] = trip.alert_cooldown_minutes
    if trip.alert_quiet_from is not None:
        data["alert_quiet_from"] = trip.alert_quiet_from
    if trip.alert_quiet_to is not None:
        data["alert_quiet_to"] = trip.alert_quiet_to

    # Serialize alert_rules (Issue #205/#638) — always emit, even if empty
    data["alert_rules"] = [
        {
            "id": r.id,
            "kind": r.kind.value,
            "metric": r.metric.value,
            "threshold": r.threshold,
            "unit": r.unit,
            "severity": r.severity.value,
            "enabled": r.enabled,
            "channels": list(r.channels),
        }
        for r in trip.alert_rules
    ]

    # Serialize corridors (Issue #1231, Slice 1) — always emit, even if empty
    # (analog alert_rules), damit additiv immer sichtbar ist.
    data["corridors"] = [
        {
            "metric": c.metric,
            "range": list(c.range),
            "notify": c.notify,
            "mark": c.mark,
            **({"prio": c.prio} if c.prio is not None else {}),
        }
        for c in trip.corridors
    ]

    # Serialize report config (Feature 3.5)
    if trip.report_config:
        data["report_config"] = {
            "trip_id": trip.report_config.trip_id,
            "enabled": trip.report_config.enabled,
            "morning_time": trip.report_config.morning_time.isoformat(),
            "evening_time": trip.report_config.evening_time.isoformat(),
            "send_email": trip.report_config.send_email,
            "send_sms": trip.report_config.send_sms,
            "send_telegram": trip.report_config.send_telegram,
            "alert_on_changes": trip.report_config.alert_on_changes,
            "change_threshold_temp_c": trip.report_config.change_threshold_temp_c,
            "change_threshold_wind_kmh": trip.report_config.change_threshold_wind_kmh,
            "change_threshold_precip_mm": trip.report_config.change_threshold_precip_mm,
            "wind_exposition_min_elevation_m": trip.report_config.wind_exposition_min_elevation_m,
            "show_compact_summary": trip.report_config.show_compact_summary,
            "show_daylight": trip.report_config.show_daylight,
            "multi_day_trend_reports": trip.report_config.multi_day_trend_reports,
            "show_stage_stats": trip.report_config.show_stage_stats,
            "show_quick_take_tags": trip.report_config.show_quick_take_tags,
            "show_stability": trip.report_config.show_stability,
            "show_highlights": trip.report_config.show_highlights,
            "daily_summary_metrics": trip.report_config.daily_summary_metrics,
            "show_metrics_summary": trip.report_config.show_metrics_summary,
            "show_outlook": trip.report_config.show_outlook,
            "email_format": trip.report_config.email_format,
            "show_yesterday_comparison": trip.report_config.show_yesterday_comparison,
            "paused_until": trip.report_config.paused_until.isoformat() if trip.report_config.paused_until else None,
            "skip_next": trip.report_config.skip_next,
            "updated_at": trip.report_config.updated_at.isoformat(),
        }

    # Issue #1250 Scheibe 4 Fix-Loop F002 (Adversary BROKEN): flache Slot-/
    # Kanal-Felder + end_date werden IMMER emittiert (auch als None), NICHT
    # omitempty-guarded. Grund: save_trip() merged diesen Output per
    # _deep_merge_preserve_unknown gegen die Datei auf Platte — fehlt ein Key
    # im Overlay komplett, bleibt der ALTE Plattenwert stehen (stale), statt
    # ueberschrieben zu werden. report_config-Block (s.o.) bleibt UNVERAENDERT
    # die einzige Wahrheit fuer den Versand.
    data["morning_time"] = trip.morning_time
    data["evening_time"] = trip.evening_time
    data["morning_enabled"] = trip.morning_enabled
    data["evening_enabled"] = trip.evening_enabled
    data["send_email"] = trip.send_email
    data["send_sms"] = trip.send_sms
    data["send_telegram"] = trip.send_telegram
    # end_date: aus der @property (trip.py:216, max(stage.date), None-sicher
    # bei leeren Stages) materialisiert — KEIN Dataclass-Feld, die Property
    # bleibt Single Source (trip_alert.py:315).
    data["end_date"] = trip.end_date.isoformat() if trip.end_date is not None else None

    # Issue #991: unmodellierte Top-Level-Keys re-emittieren — modellierte
    # Felder haben Vorrang, extra füllt nur Lücken (setdefault).
    for k, v in trip.extra.items():
        data.setdefault(k, v)

    return data


def save_trip(
    trip: Trip,
    user_id: str = "default",
    data_dir: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Save a trip to JSON file.

    Issue #1250 Scheibe 7a Cutover (ADR-0023): writes to
    ``{data_dir or data_root}/users/{user_id}/briefings/{id}.json`` (was
    ``trips/{id}.json`` before). The legacy ``trips/{id}.json`` file is left
    UNTOUCHED (Rollback-Fähigkeit, AC-26, kein Löschen im Cutover). Every
    Python ``save_trip`` write is a route-Entität (this loader never writes
    ComparePresets) -- ``kind`` is unconditionally set to ``"route"``,
    analog Go ``store.SaveTrip``.

    Issue #303: when ``data_dir`` is given, resolves under that root
    (test-isolation), otherwise the configured data root is used.

    Issue #802: Compute-on-Save — arrival_calculated wird für jede Stage
    vor der Serialisierung berechnet (bit-genau zu Go store.SaveTrip).

    Args:
        trip: Trip object to save
        user_id: User identifier (default: "default")
        data_dir: Optional base data directory override.

    Returns:
        Path to the saved file
    """
    import dataclasses
    from core.naismith import compute_stage_arrivals

    # Issue #802: Compute-on-Save — arrival_calculated für jede Stage berechnen.
    trip = dataclasses.replace(
        trip,
        stages=[compute_stage_arrivals(s, trip.activity) for s in trip.stages],
    )

    if data_dir is not None:
        briefings_dir = Path(data_dir) / "users" / user_id / "briefings"
    else:
        briefings_dir = get_briefings_dir(user_id)
    briefings_dir.mkdir(parents=True, exist_ok=True)

    path = briefings_dir / f"{trip.id}.json"
    python_data = _trip_to_dict(trip)
    # Issue #1250 Scheibe 7a (AC-26): jede Python-save_trip-Schreiboperation
    # ist per Definition eine route-Entität -- kind wird unbedingt gesetzt,
    # unabhängig vom Vorzustand des Aufrufers (analog Go store.SaveTrip).
    python_data["kind"] = "route"

    # Issue #805: RMW-Merge — vorhandene JSON laden und Python-bekannte Felder überlagern.
    # Bewahrt Go-geschriebene und Legacy-Felder die Python nicht modelliert
    # (z.B. display_config.channels, report_config.send_signal, multi_day_trend_morning/evening).
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    data = _deep_merge_preserve_unknown(existing, python_data)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return path


def delete_trip(trip_id: str, user_id: str = "default") -> None:
    """
    Delete a trip file.

    Issue #1250 Scheibe 7a (Adversary F004): deletes
    `briefings/<trip_id>.json` (was `trips/<trip_id>.json` before the
    Cutover) -- write-path completeness alongside load_all_trips/load_trip/
    save_trip. briefingsDir also holds ComparePresets (`kind="vergleich"`,
    Scheibe 5 migration) -- a Trip delete must never remove one, even if a
    Preset happens to share the same id (analog Go DeleteTrip's kind guard,
    AC-30).

    Args:
        trip_id: ID of the trip to delete
        user_id: User identifier (default: "default")
    """
    path = get_briefings_dir(user_id) / f"{trip_id}.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = None
    if isinstance(data, dict) and data.get("kind") == "vergleich":
        return
    path.unlink()


# =============================================================================
# Activity Profile Parsing (bleibt — genutzt von scheduler_dispatch_service.py)
# =============================================================================
# Issue #1250 Scheibe 0: Compare-Subscription-CRUD (get/load/save/delete) hier
# entfernt — Legacy-Drittstack CompareSubscription stillgelegt (#1131).
# _parse_activity_profile bleibt: aktiver Import in scheduler_dispatch_service.py.

def _parse_activity_profile(value: str | None):
    """Parse activity_profile string to enum, returns None if missing/invalid."""
    if not value:
        return None
    from app.profile import ActivityProfile
    try:
        return ActivityProfile(value)
    except ValueError:
        return None

# Public alias for _trip_to_dict (Issue #664 — tests import this name)
dump_trip_to_dict = _trip_to_dict
