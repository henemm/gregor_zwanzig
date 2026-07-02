"""TDD RED — Bug: Alert-Regeln ignorieren den Weather-Tab-Deaktivierungs-Status.

Hintergrund (Produktions-Vorfall "Lottis Abschiedfahrradtour", Trip 74de939c,
2026-07-01): Der Trip hat "Nullgradgrenze" (freezing_level) UND "Schneefallgrenze"
(snowfall_limit) auf dem Weather-Tab deaktiviert (enabled=False). Trotzdem enthält
`display_config.metric_alert_levels` noch einen Eintrag `"snow_line": "standard"` —
und dieser hat tatsächlich einen Alarm ausgelöst (Δ=430m), obwohl der Nutzer die
zugehörige Metrik gar nicht mehr sieht/gewählt hat.

Issue #864 (geschlossen, "11/11 ACs E2E-verifiziert") behauptet als Kernprinzip:
    "Die Alerts-Liste ist KEINE eigene Entität — sie ist eine Projektion der
    aktiven Trip-Metriken." (AC-1: Nutzer sieht im Alerts-Tab EXAKT die im
    Weather-Tab aktiven Metriken.)

Das stimmt nur für die FRONTEND-ANZEIGE (`activeAlertableMetrics()` in
`alertMetricTable.ts`, filtert Zeilen korrekt). Der tatsächliche Alarm-Versand
läuft aber über `TripAlertService._select_change_detector()`
(`src/services/trip_alert.py`) → `expand_per_metric_levels()`
(`src/services/alert_preset.py`) — und BEIDE lesen ausschließlich
`metric_alert_levels`, OHNE jemals `display_config.metrics` (den Weather-Tab-
Aktivierungsstatus) zu prüfen. `UnifiedWeatherDisplayConfig.is_metric_enabled()`
(`src/app/models.py`) existiert bereits als fertiger Baustein dafür — wird aber
in `_select_change_detector()` nirgends aufgerufen.

Konsequenz: Deaktiviert ein Nutzer eine Metrik auf dem Weather-Tab, nachdem er
dafür schon eine Alarm-Empfindlichkeit gesetzt hatte, bleibt die Alarm-Regel für
immer aktiv im Hintergrund — unsichtbar im Alerts-Tab, aber weiterhin scharf.

Diese Tests beweisen das Verhalten an ECHTEM Produktionscode (kein Mock):
`TripAlertService._select_change_detector()` wird mit echten `Trip`/
`UnifiedWeatherDisplayConfig`/`MetricConfig`-Objekten aufgerufen — exakt der
Pfad, den `check_all_trips()` im Scheduler nutzt.

Erwartetes RED-Bild heute:
- Alle "*_enabled=True*"-Fälle (Positiv-Kontrolle: Metrik ist auf dem Weather-Tab
  AN) laufen bereits GRÜN — das beweist, dass der Alarm-Pfad an sich funktioniert.
- Alle "*_enabled=False*"-Fälle (Metrik ist auf dem Weather-Tab AUS) schlagen FEHL —
  die Alarm-Regel feuert trotzdem, weil kein Code sie an den Weather-Tab-Status
  koppelt.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.models import MetricConfig, UnifiedWeatherDisplayConfig
from app.trip import Stage, Trip, Waypoint
from services.trip_alert import TripAlertService


# ───────────────────────── Helpers ──────────────────────────────────────────

def _stage() -> Stage:
    return Stage(
        id="stage-1",
        name="Etappe 1",
        date=date(2026, 7, 1),
        waypoints=[Waypoint(id="wp-1", name="Start", lat=46.0, lon=11.0, elevation_m=800)],
    )


def _trip(*, metric_alert_levels: dict, metrics: list[MetricConfig]) -> Trip:
    """Baut einen Trip mit expliziter Weather-Tab-Metrikliste (an/aus) und
    Alert-Konfiguration — bewusst getrennt, um genau die Lücke zwischen beiden
    zu prüfen."""
    config = UnifiedWeatherDisplayConfig(
        trip_id="tdd-bug-alert-gate",
        metrics=metrics,
        metric_alert_levels=metric_alert_levels,
    )
    return Trip(
        id="tdd-bug-alert-gate",
        name="TDD Bug: Alert ignoriert Weather-Tab-Status",
        stages=[_stage()],
        display_config=config,
    )


def _thresholds(detector) -> dict:
    return dict(getattr(detector, "_thresholds", {}) or {})


def _crossing_metrics(detector) -> set:
    rules = getattr(detector, "_threshold_crossing_rules", None) or []
    return {str(r.metric) for r in rules}


# ───────────────── Gruppe 1: Delta-Regeln (Böen, Gewitterenergie, Nullgradgrenze) ─

@pytest.mark.parametrize(
    "case_id, weather_tab_enabled, catalog_ids, alert_metric_key, threshold_field",
    [
        # Positiv-Kontrolle: Metrik ist auf dem Weather-Tab AN → Alarm MUSS feuern.
        ("cape_an",            True,  ["cape"],  "cape",      "cape_max_jkg"),
        ("boeen_an",           True,  ["gust"],  "wind_gust", "gust_max_kmh"),
        ("nullgradgrenze_an",  True,  ["snowfall_limit", "freezing_level"], "snow_line", "freezing_level_m"),
        # Bug-Fall: Metrik ist auf dem Weather-Tab AUS → Alarm darf NICHT feuern.
        ("cape_aus",           False, ["cape"],  "cape",      "cape_max_jkg"),
        ("boeen_aus",          False, ["gust"],  "wind_gust", "gust_max_kmh"),
        ("nullgradgrenze_aus", False, ["snowfall_limit", "freezing_level"], "snow_line", "freezing_level_m"),
    ],
)
def test_alert_threshold_respects_weather_tab_enabled_state(
    case_id, weather_tab_enabled, catalog_ids, alert_metric_key, threshold_field,
):
    metrics = [MetricConfig(metric_id=cid, enabled=weather_tab_enabled) for cid in catalog_ids]
    trip = _trip(metric_alert_levels={alert_metric_key: "standard"}, metrics=metrics)

    service = TripAlertService()
    detector = service._select_change_detector(trip)
    thresholds = _thresholds(detector)

    if weather_tab_enabled:
        assert threshold_field in thresholds, (
            f"[{case_id}] Metrik ist auf dem Weather-Tab AKTIV — Alarm-Schwelle "
            f"'{threshold_field}' MUSS gesetzt sein, fehlt aber: {thresholds!r}"
        )
    else:
        assert threshold_field not in thresholds, (
            f"[{case_id}] Metrik ist auf dem Weather-Tab DEAKTIVIERT ({catalog_ids!r} "
            f"enabled=False) — Alarm-Schwelle '{threshold_field}' darf NICHT gesetzt "
            f"sein. Der Nutzer sieht die Zeile im Alerts-Tab nicht mehr, bekommt aber "
            f"trotzdem einen Alarm dafür. Gefundene Schwellen: {thresholds!r}"
        )


# ───────────────── Gruppe 2: Threshold-Crossing-Regeln (Sichtweite) ─────────

@pytest.mark.parametrize(
    "case_id, weather_tab_enabled",
    [
        ("sichtweite_an", True),
        ("sichtweite_aus", False),
    ],
)
def test_visibility_crossing_rule_respects_weather_tab_enabled_state(case_id, weather_tab_enabled):
    metrics = [MetricConfig(metric_id="visibility", enabled=weather_tab_enabled)]
    trip = _trip(metric_alert_levels={"visibility": "standard"}, metrics=metrics)

    service = TripAlertService()
    detector = service._select_change_detector(trip)
    crossing = _crossing_metrics(detector)

    if weather_tab_enabled:
        assert "visibility" in crossing, (
            f"[{case_id}] Sichtweite ist auf dem Weather-Tab AKTIV — Threshold-"
            f"Crossing-Regel MUSS existieren, fehlt aber. Gefunden: {crossing!r}"
        )
    else:
        assert "visibility" not in crossing, (
            f"[{case_id}] Sichtweite ist auf dem Weather-Tab DEAKTIVIERT — "
            f"Threshold-Crossing-Regel darf NICHT existieren. Gefunden: {crossing!r}"
        )


# ───────────────── Gruppe 3: Produktions-Vorfall 1:1 nachgestellt ───────────

def test_reproduces_lottis_abschiedfahrradtour_incident():
    """Bildet die reale Konfiguration von Trip 74de939c nach (Böen an, Nullgrad-
    grenze/Schneefallgrenze aus, aber `metric_alert_levels.snow_line` noch gesetzt).

    Erwartung: kein Alarm für die Nullgradgrenze. Heute (Bug): der Alarm feuert
    trotzdem — exakt der Vorfall, der zur Falsch-Einordnung in Issue #959 führte.
    """
    metrics = [
        MetricConfig(metric_id="gust", enabled=True),
        MetricConfig(metric_id="snowfall_limit", enabled=False),
        MetricConfig(metric_id="freezing_level", enabled=False),
    ]
    trip = _trip(
        metric_alert_levels={"wind_gust": "standard", "snow_line": "standard"},
        metrics=metrics,
    )

    service = TripAlertService()
    detector = service._select_change_detector(trip)
    thresholds = _thresholds(detector)

    assert "gust_max_kmh" in thresholds, (
        "Böen sind aktiv konfiguriert — dieser Teil funktioniert bereits korrekt."
    )
    assert "freezing_level_m" not in thresholds, (
        "Nullgradgrenze/Schneefallgrenze sind auf dem Weather-Tab deaktiviert — "
        f"trotzdem liefert der Detektor eine scharfe Schwelle: {thresholds!r}. "
        "Das ist der reale Vorfall aus Trip 74de939c."
    )
