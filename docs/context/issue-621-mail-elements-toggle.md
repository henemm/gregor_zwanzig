# Context: Issue #621 — Mail-Elemente abschaltbar (Konfig + Render-Gating, Backend)

## Request Summary
Jedes (vom PO freigegebene) Element der Briefing-Mail soll an-/abschaltbar sein.
Dieses Issue liefert die **Backend-Felder auf `TripReportConfig`** + die **Render-Gating-Logik**
(HTML + Plain-Text). Die Anzeige selbst kommt aus #613 (bereits live), die Bedien-Oberfläche
aus #619 (Frontend, separat).

## Schaltbare Sektionen (PO-Vorgabe)
| Feld (neu) | Default | Gating-Ziel HTML | Gating-Ziel Plain |
|---|---|---|---|
| `show_stage_stats: bool` | True | `stats_grid_html` (Kennzahlen-Raster) | stage_stats-Zeile |
| `show_quick_take_tags: bool` | True | `quick_take_html` (Chips) | — (nur HTML) |
| `show_stability: bool` | True | `stability_html` (Großwetterlage) | Stabilitäts-Block |
| `show_highlights: bool` | True | `highlights_html` (Zusammenfassung) | Highlights-Block |
| `daily_summary_metrics: list[str]` | `["precipitation","wind","visibility","thunder"]` | `daily_summary_html` Zellen-Filter | „Tages-Summe"-Zeilen-Filter |

**Immer an, KEIN Schalter** (PO): Kopf, Fußzeile, Unsicherheits-Hinweis (`confidence_hint_html`).
**Aggregation fest pro Kennzahl:** Regen Σ · Wind/Böen/Gewitter max · Sicht min · Temp min/max.

## Related Files
| File | Relevance |
|------|-----------|
| `src/app/models.py:676` | `TripReportConfig` — hier kommen die 5 additiven Felder hin |
| `src/app/loader.py:338-367` | parst `report_config` JSON → `TripReportConfig` (Default-Fallbacks) |
| `src/output/renderers/email/html.py:267` | `render_html` baut alle Blöcke; daily_summary + quick_take aktuell IMMER gerendert |
| `src/output/renderers/email/plain.py:106` | `render_plain` — Plain-Parität (stage_stats/stability/highlights/daily-summary) |
| `src/output/renderers/email/__init__.py:30` | `render_email` dispatcht zu html+plain (Param-Durchreichung) |
| `src/formatters/trip_report.py:51` | `format_email` — zentrale Render-Pipeline; reicht Werte an `render_email` |
| `src/services/trip_report_scheduler.py:419-464` | liest `trip.report_config.*` Toggles, ruft `format_email` |
| `src/services/preview_service.py:120-136` | Vorschau-Pipeline, identische Verkabelung |
| `internal/model/trip.go:81` | Go: `report_config` als opaque `map[string]interface{}` → kein Go-Change nötig |
| `internal/handler/trip.go:201` | Go-Merge auf Top-Level (Issue #99) → unbekannte Felder bleiben erhalten |

## Existing Patterns (Vorbild = `show_daylight`, `show_compact_summary`)
1. **Feld auf `TripReportConfig`** (models.py) additiv mit sicherem Default.
2. **Loader parst** aus `rc_data.get(..., default)` (loader.py) — fehlendes Feld = alter Zustand.
3. **Scheduler/Preview liest** `trip.report_config.show_X` und gated:
   - *Daten-Gating* (daylight, multi_day_trend): Daten gar nicht erst berechnen/übergeben.
   - *dc-Patch* (show_compact_summary): `display_config.show_compact_summary` patchen.
4. **Renderer gated** über `if <wert>:` (stage_stats/highlights bereits so; stability via `render_stability_label_html(None)→""`).

## Architektur-Entscheidung (für Phase 2/3)
`quick_take_html` und `daily_summary_html` werden in `render_html` aktuell **bedingungslos**
gerendert → reines Daten-Gating reicht NICHT. Sauberster Weg: die 5 Toggles als explizite
kwargs (backward-kompatible Defaults) durch `format_email → render_email → render_html/render_plain`
durchreichen. `format_email` erhält dazu die Toggles aus `trip.report_config`.

## Dependencies
- **Upstream:** `TripReportConfig`, `UnifiedWeatherDisplayConfig`, `build_daily_aggregates`, `build_quick_take_chips`.
- **Downstream:** Scheduler-Versand, Preview-Service, #619-Frontend (schreibt die Felder später).

## Existing Specs
- `docs/specs/modules/email_redesign_613.md` — die zu schaltenden Sektionen (AC-1..AC-7).

## Risks & Considerations
- **Datenverlust-Regel (CLAUDE.md):** rein additiv, keine Migration; Loader-Default = alter Zustand. Go-Backend merged ohnehin opaque.
- **Plain-Parität:** quick_take hat keine Plain-Entsprechung (Chips sind HTML-visuell) — bewusst kein Plain-Gate dafür.
- **`daily_summary_metrics` leer** → ganzer Tages-Summe-Block fehlt (HTML + Plain).
- **email_spec_validator:** muss bei allen Defaults (alles an) weiter Exit 0 liefern.
- **LoC-Limit 250:** Felder + Loader + 2 Renderer + Pipeline-Durchreichung — eng kalkulieren.
