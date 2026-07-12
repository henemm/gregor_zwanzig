# Kontext: fix-1191-compare-alert-deactivated-metric

**Issue:** #1191 (Nebenbefund F006 aus #1170). Compare-Δ-Alarm ignoriert deaktivierte Metriken.

## Ursache (Analyse bestätigt)
`compare_alert.py:207` → `display_config=None` → #961-Filter in `deviation_alert_engine._select_detector` greift nicht.

## Komplikation
Metrik-Aktivierung liegt in `display_config.active_metrics` (Summary-Keys: temp_max_c, wind_max_kmh, …), NICHT in `display_config.metrics`. Der Alarm-Filter prüft aber Katalog-IDs (temperature, wind, …) via `is_metric_enabled`. → Mapper Summary→Katalog nötig. Leeres `metrics[]` filtert nicht (is_alert_metric_active → True). Kein bestehender Compare→DisplayConfig-Builder.

## Fix
`_build_eval_config`: bei vorhandenem `active_metrics` UnifiedWeatherDisplayConfig mit `metrics=[MetricConfig(metric_id=<katalog>, enabled=True)]` bauen (via Mapper) + schalter-lose Alarm-Metriken (gust/cape/freezing_level/temp_min) immer enabled; durchreichen. Ohne active_metrics: None beibehalten (backward-compat).

## Betroffen
- src/services/compare_alert.py (Fix)
- Mapper (loader.py:617 erweitern oder Helfer)
- tests/tdd/ (Repro, analog test_issue_1169/1170)

## Vorbild
trip_alert.py:191 (display_config=trip.display_config).
