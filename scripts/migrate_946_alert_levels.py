"""Issue #946 — Migration: alert_preset → metric_alert_levels.

metric_alert_levels ist ab Issue #946 die einzige Alert-Datenquelle. Alt-Trips, die
nur ein globales alert_preset gesetzt hatten, werden auf pro-Metrik-Stufen umgestellt:
jede der 13 alertfähigen Metriken bekommt das Preset-Level.

migrate_trip() ist eine reine Funktion (transformiert nur das dict, schreibt keine Datei).
"""
from __future__ import annotations

# 13 alertfähige Metriken (ALERTABLE_METRICS).
ALERTABLE_METRICS = [
    "wind_gust",
    "precipitation_sum",
    "thunder_level",
    "snow_line",
    "temperature_min",
    "temperature_max",
    "temperature_change",
    "wind_change",
    "precipitation_change",
    "fresh_snow",
    "cape",
    "visibility",
    "humidity",
]


def migrate_trip(trip_json: dict) -> dict:
    """Konvertiert alert_preset → metric_alert_levels (reine Funktion).

    - metric_alert_levels bereits gesetzt (nicht-leer)  → unverändert zurück.
    - alert_preset gesetzt, metric_alert_levels fehlt/None → alle 13 Metriken
      mit dem Preset-Level befüllen.
    - weder preset noch levels → unverändert.
    """
    config = trip_json.get("display_config")
    if not isinstance(config, dict):
        return trip_json

    existing = config.get("metric_alert_levels")
    if existing:
        return trip_json

    preset = config.get("alert_preset")
    if not preset:
        return trip_json

    config["metric_alert_levels"] = {metric: preset for metric in ALERTABLE_METRICS}
    return trip_json
