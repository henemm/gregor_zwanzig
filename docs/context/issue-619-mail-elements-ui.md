# Context: Issue #619 — Auswahl-/Schalter-UI für E-Mail-Elemente in Trip-Einstellungen

## Request Summary
Frontend-UI zu den bereits live deployten Backend-Konfig-Feldern aus #621: Pro Trip
auswählen, welche E-Mail-Elemente erscheinen (4 An/Aus-Schalter) und welche Kennzahlen
in der Tages-Summe stehen (Mehrfachauswahl). Reines Anbinden — Backend + Render-Gating
existieren schon.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/molecules/ReportConfigDialog.svelte` | Report-Konfig-Dialog — hier kommen die neuen Bedienelemente rein (Interface Zeile 17-32, UI ab Zeile 80) |
| `frontend/src/routes/trips/+page.svelte` | `reportConfig`-State (Z. 46-61), `openReportConfig` Load-Mapping (Z. 183-230), `saveReportConfig` (Z. 232-251) |
| `src/app/models.py:676-731` | `TripReportConfig` mit den 5 Feldern aus #621 (Defaults) |
| `src/app/loader.py:344-375` | Python liest die 5 Felder aus `report_config`-JSON |
| `src/output/renderers/email/html.py:558-579` | Metrik-Katalog `_METRIC_ORDER` + Labels (precipitation/wind/visibility/thunder/temperature) |
| `internal/handler/trip.go:155-248` | PUT /api/trips/{id} — REPLACE von `report_config` (opaque map) |
| `internal/model/trip.go:81` | `ReportConfig map[string]interface{}` — opaque, alle Felder durchgereicht |

## Datenfluss (Save)
Frontend `reportConfig`-State → PUT /api/trips/{id} → Go ersetzt `report_config` komplett
durch das gesendete Objekt (opaque map → alle Felder persistiert) → Python-Loader liest
beim Render. **Konsequenz:** Da Go die ganze Map ersetzt, müssen die 5 neuen Felder im
Frontend-State liegen, sonst gehen sie beim Speichern auf Default zurück (genau das
read-modify-write-Risiko aus dem Issue).

## Die 5 Felder aus #621
- `show_stage_stats` (bool, default true) — Etappen-Kennzahlen-Raster
- `show_quick_take_tags` (bool, default true) — Quick-Take-Chips (nur HTML)
- `show_stability` (bool, default true) — Großwetterlage
- `show_highlights` (bool, default true) — Zusammenfassung/Highlights
- `daily_summary_metrics` (list, default `[precipitation, wind, visibility, thunder]`) —
  Tages-Summe; wählbar zusätzlich `temperature`. Render-Reihenfolge ist FEST (Katalog),
  Nutzer wählt nur ob eine Kennzahl dabei ist.

## Existing Patterns
- Bestehende Checkboxen im Dialog (`<Checkbox bind:checked={config.x}>`), z.B. Kanäle/Optionen.
- Felder die nur durchgereicht (nicht editiert) werden, liegen bereits im State ohne UI:
  `wind_exposition_min_elevation_m`, `multi_day_trend_reports` → gleiches Muster für die neuen.

## Risks & Considerations
- **Datenverlust-Risiko:** Go macht REPLACE. Die 5 Felder MÜSSEN in State + Load-Mapping +
  Save-Objekt, sonst Reset auf Default beim Speichern.
- Latente Lücke (außerhalb #619-Scope): `loader.py:_trip_to_dict()` serialisiert die 5 Felder
  nicht — betrifft nur einen Python-Schreibpfad, nicht den aktiven Go-Save. Nicht anfassen.
- E2E-Abnahme: Playwright gegen Staging — Auswahl ändern, speichern, in Test-Mail prüfen.
