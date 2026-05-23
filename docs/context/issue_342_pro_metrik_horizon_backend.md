---
issue: 342
parent_epic: 304
workflow: issue_342_pro_metrik_horizon_backend
created: 2026-05-23
status: phase2_analyse
---

# Context: Issue #342 — Pro-Metrik-Horizont Backend + Datenmodell

> Sub-Issue 1 von #304 (Klammer-Epic). Voller Vorab-Kontext: `docs/context/issue_304_pro_metrik_horizon_template_save.md`.

## Request Summary

Backend-Voraussetzung für Pro-Metrik-Zeithorizont: Schema-Erweiterung von `MetricPreset` und `Trip.display_config.metrics[]` um `horizons` (today/tomorrow/day_after); neuer PATCH-Endpoint; Renderer-Filter pro Etappe.

## Scope dieses Sub-Issues

Alles Backend (Python `src/output/renderers/email/`, Go `internal/model/`, `internal/handler/`, `internal/store/`, `cmd/server/main.go`).

UI- und Account-Karte-Themen sind in **#343** und **#344** ausgelagert. Diese Spec deckt nur:

1. **`MetricPreset` Modell** (`internal/model/metric_preset.go`): von `Metrics []string` + `FriendlyIDs []string` auf `Metrics []DisplayMetric` umstellen mit Feldern `metric_id`, `enabled`, `use_friendly_format`, `horizons` (`today/tomorrow/day_after` bool).
2. **`Trip.DisplayConfig.metrics[]`** analog erweitern (additiv via `map[string]interface{}` — bestehende Trips bleiben lesbar).
3. **PATCH `/api/metric-presets/{id}`** ergänzen (Read-Modify-Write).
4. **GET-Backward-Compat**: Bestehende Presets/Trips ohne `horizons` werden beim Laden mit `{today:true, tomorrow:true, day_after:true}` defaultet.
5. **Renderer-Filter** in `src/output/renderers/email/helpers.py` `dp_to_row()` + `visible_cols()`: pro Etappe wird aus dem Etappen-Startdatum heute/morgen/übermorgen abgeleitet; Metriken mit `horizons.today=false` werden in heutigen Etappen-Tabellen weggelassen. Etappen ab Tag 4 ignorieren den Horizont (Default-Verhalten beibehalten).
6. **Datenmigration**: Hook `data_schema_backup.py` macht Backup vor Edit; Roundtrip-Test (load alt → save → load → diff).
7. **Tests**: Unit-Tests für Modell, Handler, Renderer-Filter. Keine Mocks.

## Related Files

| Datei | Was passiert |
|---|---|
| `internal/model/metric_preset.go` | Struct erweitern. |
| `internal/handler/metric_preset.go` | PATCH-Handler ergänzen. |
| `internal/store/store.go` (L323+) | `LoadMetricPresets` mit Default-Migration. |
| `cmd/server/main.go` (L128–131) | PATCH-Route registrieren. |
| `src/output/renderers/email/helpers.py` | `dp_to_row()` + `visible_cols()` mit Horizon-Auswertung. |
| `src/output/renderers/email/html.py` (L140+) | `render_html()` ggf. um Horizon-Parameter erweitern (oder über `dc.metrics[].horizons` direkt). |
| `internal/handler/metric_preset_test.go` | Tests für neue PATCH-Route. |
| Python Test-Datei (neu) `tests/tdd/test_horizon_filter.py` | Renderer-Filter-Tests. |

## Etappen-zu-Horizon-Mapping

```
heute   = Etappe-Startdatum == report-Datum
morgen  = Etappe-Startdatum == report-Datum + 1 Tag
übermorgen = Etappe-Startdatum == report-Datum + 2 Tage
sonst   = ignoriere Horizont (zeige Metrik immer)
```

Report-Datum = `segments[0].segment.start_time` (siehe `html.py:160`).

## Risks

1. **Schema-Migration** — PFLICHT-Workflow (Backup + Roundtrip-Test).
2. **Renderer-Architektur** ist heute pro-Etappe, nicht pro-Tag. Etappen-zu-Horizon-Mapping muss klar getestet werden.
3. **Daten-Bestand** ist klein (0 Trips mit display_config.metrics, 1 leeres Preset), Migration aber trotzdem mit Backup/Test absichern.
4. **`use_friendly_format` umzieht** aus paralleler `FriendlyIDs []string` Liste in den strukturierten Eintrag — Migration muss diese Liste konsumieren.

## LoC-Schätzung

| Block | LoC |
|---|---|
| Go-Modell + Store + Handler + Route | ~80 |
| Go-Tests | ~80 |
| Python-Renderer-Filter (helpers.py) | ~40 |
| Python-Tests | ~60 |
| **Summe** | **~260** |

LoC-Limit 250 wird grenzwertig überschritten — Override mit Begründung „Schema-Migration + Tests" planen.
