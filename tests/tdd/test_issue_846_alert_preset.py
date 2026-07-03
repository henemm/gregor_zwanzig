"""TDD RED — Issue #846: Alert-Preset-Dropdown + 4 neue Alert-Metriken
(Epic #813 Slice 3).

Diese Tests beweisen die **Python-Backend**-Acceptance-Criteria der Spec
`docs/specs/modules/issue_846_alert_preset.md` aus Nutzersicht — KEINE Mocks
(CLAUDE.md). Sie verwenden echte Python-Objekte und echten Dateisystem-Zugriff
unter `data/users/<user_id>/` (eindeutige tdd-846-* IDs, Cleanup in Fixture).

Heute schlagen sie fehl (RED), weil:
- `src/services/alert_preset.py::expand_preset` existiert noch nicht (ImportError).
- `AlertMetric.FRESH_SNOW/CAPE/VISIBILITY/HUMIDITY` sind noch nicht im Enum
  (AttributeError).
- Die Threshold-Crossing-Logik für Sichtweite in `detect_changes`
  (`src/services/weather_change_detection.py`) existiert noch nicht.

Geprüfte ACs (nur Python):
- AC-3: `expand_preset("deaktiviert")` → leere Liste; Service ohne Thresholds
  liefert leere Change-Liste.
- AC-4: Threshold-Crossing für `visibility_min_m` (genau bei Unterschreiten).
- AC-6: `expand_preset("entspannt")` → exakt 13 Regeln, neue Metriken korrekt.
- AC-7: Mandantentrennung zweier User über echtes Dateisystem.
- AC-8: Preset hat Vorrang vor altem `alert_rules`-Array.

SPEC: docs/specs/modules/issue_846_alert_preset.md
"""
from __future__ import annotations

import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.models import (
    AlertMetric,
    AlertRuleKind,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint


# ───────────────────────── Builder (kein Mock) ──────────────────────────────


def _segment(segment_id: int | str = 1) -> TripSegment:
    start = datetime(2026, 4, 5, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(
            lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=12.0
        ),
        end_point=GPXPoint(
            lat=47.1, lon=11.1, elevation_m=1500, distance_from_start_km=18.0
        ),
        start_time=start,
        end_time=end,
        duration_hours=4.0,
        distance_km=6.0,
        ascent_m=500,
        descent_m=0,
    )


def _data(segment_id: int | str = 1, **summary_kwargs) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(segment_id),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(
                provider=Provider.OPENMETEO, model="test", grid_res_km=1.0
            ),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


@pytest.fixture()
def clean_user_dirs():
    """Räumt die echten data/users/tdd-846-*-Verzeichnisse vor und nach dem Test."""
    created: list[str] = []

    def _register(user_id: str) -> str:
        created.append(user_id)
        path = Path(f"data/users/{user_id}")
        if path.exists():
            shutil.rmtree(path)
        return user_id

    yield _register

    for user_id in created:
        path = Path(f"data/users/{user_id}")
        if path.exists():
            shutil.rmtree(path)


# ═════════════════════════════ AC-3 ═════════════════════════════════════════
# Preset "deaktiviert" → leere Regel-Liste → keine Changes.


def test_ac3_deaktiviert_expands_to_empty_list():
    """AC-3: `expand_preset("deaktiviert")` liefert eine leere Liste."""
    from services.alert_preset import expand_preset  # RED: Modul fehlt

    rules = expand_preset("deaktiviert")
    assert rules == [], (
        "Preset 'deaktiviert' muss zu einer leeren AlertRule-Liste expandieren "
        "(kein Alert-Versand)"
    )


def test_ac3_empty_service_yields_no_changes():
    """AC-3: Preset 'deaktiviert' → `expand_preset` liefert leere Liste →
    `from_alert_rules([])` → Service ohne Thresholds → leere Change-Liste
    unabhängig vom Wetter-Zustand. Geht durch den NEUEN Expansions-Pfad,
    damit der Nachweis nicht nur bestehendes Verhalten testet."""
    from services.alert_preset import expand_preset  # RED: Modul fehlt
    from services.weather_change_detection import WeatherChangeDetectionService

    rules = expand_preset("deaktiviert")
    service = WeatherChangeDetectionService.from_alert_rules(rules)

    # Drastische Abweichung im Wetter — darf trotzdem KEINEN Change geben.
    old = _data(precip_sum_mm=0.0, gust_max_kmh=10.0)
    new = _data(precip_sum_mm=99.0, gust_max_kmh=120.0)

    changes = service.detect_changes(old, new)
    assert changes == [], (
        "Leerer Service (Preset 'deaktiviert') darf keine Changes liefern, "
        f"erhielt: {changes}"
    )


# ═════════════════════════════ AC-4 ═════════════════════════════════════════
# Threshold-Crossing für Sichtweite: feuert nur beim erstmaligen Unterschreiten.


def _visibility_service(threshold: int):
    """Baut einen Service, der NUR die Sichtweiten-Regel (Threshold-Crossing)
    kennt — über die Preset-/Regel-Expansion des neuen `visibility`-Metrik."""
    from app.models import AlertRule, AlertSeverity
    from services.weather_change_detection import WeatherChangeDetectionService

    rule = AlertRule(
        id="vis-1",
        kind=AlertRuleKind.DELTA,  # in der Spec als threshold_crossing markiert
        metric=AlertMetric.VISIBILITY,  # RED: Enum-Wert fehlt heute
        threshold=float(threshold),
        severity=AlertSeverity.WARNING,
        enabled=True,
    )
    return WeatherChangeDetectionService.from_alert_rules([rule])


def test_ac4_visibility_crossing_below_threshold_fires_once():
    """AC-4: old=2500, new=800, threshold=1000 → genau 1 Change für
    `visibility_min_m` (erstmaliges Unterschreiten)."""
    service = _visibility_service(threshold=1000)

    old = _data(visibility_min_m=2500)
    new = _data(visibility_min_m=800)

    changes = service.detect_changes(old, new, include_absolute=False)
    vis_changes = [c for c in changes if c.metric == "visibility_min_m"]
    assert len(vis_changes) == 1, (
        "Sichtweite fällt erstmals unter 1000 m (2500→800) → genau ein "
        f"Change-Eintrag erwartet, erhielt: {changes}"
    )


def test_ac4_visibility_already_below_threshold_no_realert():
    """AC-4 Kontrollfall: old=800, new=600 (beide < threshold=1000) →
    KEIN erneuter Alert (Threshold-Crossing-Semantik, kein Delta)."""
    service = _visibility_service(threshold=1000)

    old = _data(visibility_min_m=800)
    new = _data(visibility_min_m=600)

    changes = service.detect_changes(old, new, include_absolute=False)
    vis_changes = [c for c in changes if c.metric == "visibility_min_m"]
    assert vis_changes == [], (
        "Beide Werte bereits unter Threshold (800→600) → kein erneuter "
        f"Sichtweite-Alert erwartet, erhielt: {vis_changes}"
    )


# ═════════════════════════════ AC-6 ═════════════════════════════════════════
# Preset "entspannt" → exakt 12 Regeln inkl. der neuen Metriken.
# Issue #889 / ADR-0010: HUMIDITY als Vorboten-Metrik aus dem Preset entfernt
# (war zuvor 13 Regeln inkl. humidity).


def test_ac6_entspannt_has_exactly_12_rules():
    """AC-6: `expand_preset("entspannt")` liefert exakt 12 Regeln.

    Issue #889: humidity entfernt → 12.
    Issue #946: freezing_level ergänzt → 13.
    Issue #959: snow_line + freezing_level zu EINER Nullgradgrenze-Zeile
    konsolidiert (snow_line-Zeile entfernt) → 12.
    """
    from services.alert_preset import expand_preset

    rules = expand_preset("entspannt")
    assert len(rules) == 12, (
        f"Preset 'entspannt' muss exakt 12 Regeln liefern, erhielt: {len(rules)}"
    )


def _rule_for(rules, metric: AlertMetric):
    matches = [r for r in rules if r.metric == metric]
    assert matches, f"Keine Regel für Metrik {metric} im Preset gefunden"
    assert len(matches) == 1, f"Mehrere Regeln für {metric}: {matches}"
    return matches[0]


def test_ac6_entspannt_fresh_snow_threshold_20_delta():
    """AC-6: Neuschnee — threshold=20, kind=delta."""
    from services.alert_preset import expand_preset

    rule = _rule_for(expand_preset("entspannt"), AlertMetric.FRESH_SNOW)
    assert rule.threshold == 20, f"fresh_snow threshold erwartet 20, war {rule.threshold}"
    assert rule.kind == AlertRuleKind.DELTA, (
        f"fresh_snow kind erwartet delta, war {rule.kind}"
    )


def test_ac6_entspannt_cape_threshold_1200_delta():
    """AC-6: CAPE — threshold=1200, kind=delta."""
    from services.alert_preset import expand_preset

    rule = _rule_for(expand_preset("entspannt"), AlertMetric.CAPE)
    assert rule.threshold == 1200, f"cape threshold erwartet 1200, war {rule.threshold}"
    assert rule.kind == AlertRuleKind.DELTA, f"cape kind erwartet delta, war {rule.kind}"


def test_ac6_entspannt_visibility_threshold_500_crossing():
    """AC-6: Sichtweite — threshold=500, kind=threshold_crossing
    (oder äquivalenter Marker, NICHT delta)."""
    from services.alert_preset import expand_preset

    rule = _rule_for(expand_preset("entspannt"), AlertMetric.VISIBILITY)
    assert rule.threshold == 500, (
        f"visibility threshold erwartet 500, war {rule.threshold}"
    )
    kind_value = getattr(rule.kind, "value", rule.kind)
    assert kind_value == "threshold_crossing", (
        "visibility muss als Threshold-Crossing markiert sein (nicht delta), "
        f"war: {kind_value}"
    )


def test_ac6_entspannt_has_no_humidity_rule():
    """Issue #889 / ADR-0010: Luftfeuchtigkeit ist Vorboten-Metrik —
    das Preset darf keine HUMIDITY-Regel mehr liefern (ersetzt den vormaligen
    #846-Vertrag threshold=25/delta)."""
    from services.alert_preset import expand_preset

    rules = expand_preset("entspannt")
    humidity_rules = [r for r in rules if r.metric == AlertMetric.HUMIDITY]
    assert humidity_rules == [], (
        "Preset 'entspannt' darf keine HUMIDITY-Regel mehr enthalten, "
        f"enthielt aber {len(humidity_rules)}."
    )


# ═════════════════════════════ AC-7 ═════════════════════════════════════════
# Mandantentrennung: zwei User, Standard-Preset, Böen-Δ unter Schwelle.


def _trip(trip_id: str) -> Trip:
    stage = Stage(
        id="T1",
        name="Tag 1",
        date=date(2026, 4, 5),
        waypoints=[
            Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)
        ],
    )
    trip = Trip(id=trip_id, name="Mandanten-Trip", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id,
        send_email=False,
        send_telegram=True,
        alert_on_changes=True,
    )
    return trip


def test_ac7_standard_gust_below_threshold_no_alert_and_user_isolation(
    clean_user_dirs,
):
    """AC-7: Beide User mit Preset "standard" (Böen-Δ-Schwelle 20). Böen-Delta
    von 18 km/h erreicht die Schwelle NICHT → kein Alert für user_a; user_b
    bleibt komplett unberührt (Mandantentrennung, echtes Dateisystem)."""
    from app.config import Settings
    from services.alert_preset import expand_preset  # RED: Modul fehlt
    from services.trip_alert import TripAlertService
    from services.weather_change_detection import WeatherChangeDetectionService

    user_a = clean_user_dirs("tdd-846-usera")
    user_b = clean_user_dirs("tdd-846-userb")

    # Standard-Preset → wind_gust Δ-Schwelle 20.
    rules = expand_preset("standard")
    service_rules = WeatherChangeDetectionService.from_alert_rules(rules)

    # Böen-Delta 18 km/h (60→78) — unter Standard-Schwelle 20 → kein Change.
    old = _data(gust_max_kmh=60.0)
    new = _data(gust_max_kmh=78.0)
    changes = service_rules.detect_changes(old, new, include_absolute=False)
    gust_changes = [c for c in changes if c.metric == "gust_max_kmh"]
    assert gust_changes == [], (
        "Böen-Δ 18 < Standard-Schwelle 20 → kein Change erwartet, "
        f"erhielt: {gust_changes}"
    )

    # Echter Alert-Lauf unter user_a — darf keinen alert_log-Eintrag erzeugen.
    settings = Settings(telegram_bot_token="test-token", telegram_chat_id="test-chat")
    trip_a = _trip("trip-usera")
    trip_a.alert_cooldown_minutes = 0
    trip_a.alert_rules = rules
    svc_a = TripAlertService(settings=settings, user_id=user_a)
    svc_a.check_and_send_alerts(trip_a, [old], fresh_weather=[new])

    alert_log_a = Path(f"data/users/{user_a}/alert_log.json")
    assert not alert_log_a.exists(), (
        "user_a darf bei Δ unter Schwelle keinen Alert-Log-Eintrag bekommen — "
        f"{alert_log_a} existiert unerwartet"
    )

    # user_b wurde nie angefasst → kein Verzeichnis/keine Daten.
    user_b_dir = Path(f"data/users/{user_b}")
    assert not user_b_dir.exists() or not any(user_b_dir.iterdir()), (
        "user_b-Daten wurden durch den user_a-Lauf berührt — "
        "Mandantentrennung verletzt"
    )


# ═════════════════════════════ AC-8 ═════════════════════════════════════════
# Preset hat Vorrang vor altem alert_rules-Array.


def test_ac8_standard_preset_gust_threshold_is_20():
    """`expand_preset("standard")` liefert wind_gust mit Standard-Wert threshold=20.

    Issue #946: Der frühere Integrations-Teil dieses Tests (alert_preset überschreibt
    Legacy-alert_rules über _select_change_detector) wurde entfernt — dieser
    Routing-Pfad existiert nach #946 nicht mehr (metric_alert_levels ist einzige
    Quelle). Die reine expand_preset-Zusicherung bleibt gültig.
    """
    from services.alert_preset import expand_preset

    rules = expand_preset("standard")
    gust = _rule_for(rules, AlertMetric.WIND_GUST)
    assert gust.threshold == 20, (
        f"Preset 'standard' muss Böen-Schwelle 20 liefern, war: {gust.threshold}"
    )
