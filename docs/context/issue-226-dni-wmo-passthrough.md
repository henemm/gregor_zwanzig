# Context: Issue #226 — compute_extended_metrics verliert dominant_wmo_code + dni_avg_wm2

## Request Summary

In `compute_extended_metrics()` werden zwei Felder aus dem Basis-Summary nicht in das Extended-Summary kopiert: `dominant_wmo_code` (dominantes Wetter-Symbol) und `dni_avg_wm2` (Tageshelligkeit). Bug ist seit Commit `d92af39` latent.

## Betroffene Dateien

| Datei | Relevanz |
|-------|---------|
| `src/services/weather_metrics.py` Z. 907–950 | `compute_extended_metrics()` — hier fehlen die zwei Felder im `SegmentWeatherSummary(...)` Konstruktor-Aufruf |
| `src/services/weather_metrics.py` Z. 610–636 | `compute_basis_metrics()` — setzt `dominant_wmo_code` + `dni_avg_wm2` korrekt |
| `tests/unit/test_weather_metrics.py` | Bestehende Regressions-Tests für Extended-Metrics — hier kommt der neue Test rein |

## Bug-Details

`compute_extended_metrics()` (Z. 907) baut ein neues `SegmentWeatherSummary` per Feldliste. Kopiert werden:
- Basis-Felder: `temp_min_c`, `temp_max_c`, `temp_avg_c`, `wind_max_kmh`, `gust_max_kmh`, `precip_sum_mm`, `cloud_avg_pct`, `humidity_avg_pct`, `thunder_level_max`, `visibility_min_m`
- **Fehlt: `dominant_wmo_code`, `dni_avg_wm2`**

Die `aggregation_config` für beide Felder wird korrekt via `**basis_summary.aggregation_config`-Spread übernommen (Z. 935), aber die Felder selbst sind `None`.

## Bestehende Test-Fixtures

`TestWeatherMetricsServiceExtendedKnownValues` (Z. 472):
- `basis_summary`-Fixture (Z. 481) setzt `dominant_wmo_code` und `dni_avg_wm2` **nicht** (beide `None` by default)
- Für den Regressions-Test müssen diese Werte explizit gesetzt werden

## Fix-Scope

- **2 Zeilen** Production-Code in `compute_extended_metrics()` (Z. 918 nach `visibility_min_m`)
- **1 Regressions-Test** in `TestWeatherMetricsServiceExtendedKnownValues`
- Keine Spec-Änderung nötig (Verhalten ist in `weather_emoji_dni.md` + `risk_engine.md` v2.0 bereits korrekt spezifiziert)

## Auswirkung heute

Gering — Renderer greifen meist direkt auf `timeseries.data` zu. Stage-Level-Aggregation (`aggregate_stage_summary()`) aggregiert jedoch `dominant_wmo_code` nicht, weil das Feld `None` ist.

## Risiken

- Minimal — reine Addition, keine bestehenden Felder betroffen
- Plausibilitätsprüfung `_validate_extended_plausibility()` prüft diese Felder nicht → kein Konflikt
