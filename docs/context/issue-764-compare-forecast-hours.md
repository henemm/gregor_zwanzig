# Context: issue-764-compare-forecast-hours

## Request Summary
Der gewählte Vorhersage-Horizont (`forecast_hours`, 24/48/72 h) im Orts-Vergleich-Editor
geht verloren: Er ist kein Feld des `ComparePreset`-Modells, wird beim Speichern (POST/PUT)
nicht mitgesendet und beim Bearbeiten nicht zurückgemappt → Editor zeigt im Edit-Modus
immer „Morgen (48 h)".

## Related Files
| File | Relevance |
|------|-----------|
| `internal/model/compare_preset.go` | `ComparePreset`-Struct — **Feld `ForecastHours` fehlt** |
| `frontend/src/lib/types.ts` (Z. 466) | `interface ComparePreset` — **Feld `forecast_hours` fehlt** |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | `forecastHours = $state(48)`; `saveNewPreset()` (Z. 152) POST-Payload **ohne** `forecast_hours`; `saveComparePreset()` (Z. 189) via `buildComparePresetSavePayload` |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | `buildComparePresetSavePayload()` — Round-Trip-Spread `{...original}`, überschreibt `forecast_hours` **nicht** mit Edit-Wert |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | Hydration mappt schedule/weekday/hour_from/hour_to — **nicht** `forecast_hours` |
| `internal/handler/compare_preset.go` | Create (Z. 114) + Update (Z. 166) Handler; Update = Full-Replace mit selektivem Preserve (display_config, previous_schedule) |
| `internal/store/store.go` (Z. 466) | `LoadComparePresets`/`SaveComparePresets` = plain JSON Marshal → neues Feld auto-persistiert; Legacy-Default-Muster (Weekday) vorhanden |
| `api/routers/scheduler.py` (Z. 398) | `_send_one_compare_preset` **hardcodet `forecast_hours=48`** beim täglichen Versand — Konsum-Seite |

## Existing Patterns
- **Read-Modify-Write/Merge** (BUG-DATALOSS-GR221): Update-Handler erhält server-managed + nicht
  gesendete Felder aus `original` (display_config Z. 199, previous_schedule Z. 207).
- **Legacy-Default beim Load**: `LoadComparePresets` setzt `Weekday=4` wenn `nil` (Z. 481) —
  analoges Muster für `forecast_hours==0 → 48` möglich.
- **Round-Trip-Spread im Frontend-Save**: `buildComparePresetSavePayload` spreadet `...original`
  und überschreibt nur editierte Felder — neuer Edit-Wert muss **explizit** in den Body.
- **Versand-Felder im Subscription-Pfad** (`save()` Z. 95) senden `forecast_hours` bereits korrekt
  — das ist NICHT der Bug-Pfad (Subscriptions ≠ ComparePresets).

## Dependencies
- Upstream: Horizont-Select im Compare-Editor (Step „Versand"), schreibt `state.forecastHours`.
- Downstream: `ComparisonEngine.run(forecast_hours=...)` im täglichen Versand
  (`api/routers/scheduler.py`) — derzeit hartkodiert 48, ignoriert das Preset.

## Existing Specs
- `docs/specs/modules/issue_763_step5_forecast_select.md` — Out-of-Scope-Dokumentation des Befunds (Quelle).
- `docs/specs/modules/issue_458_compare_preset_backend.md` — ComparePreset-Modell.
- `docs/specs/modules/issue_679_compare_editor_edit.md` — Edit-Route + Round-Trip-Spread.

## Risks & Considerations
- **Legacy-Daten:** Bestehende `compare_presets.json` ohne `forecast_hours` → Go-Zero-Value 0
  (kein gültiger Horizont). Beim Load auf 48 defaulten, sonst zeigt Editor „0 h".
- **Persistenz ohne Konsum = totes Setting:** Wird nur der Round-Trip gefixt, aber
  `_send_one_compare_preset` bleibt bei `forecast_hours=48`, hat der gespeicherte Wert
  **keine** funktionale Wirkung. Das Issue framet `forecast_hours` als „funktional relevant,
  nicht kosmetisch" → Konsum-Wiring (Z. 398: `preset.get("forecast_hours", 48)`) gehört
  fachlich dazu. **PO-Entscheidung im Summary.**
- **Mandantentrennung:** Pfad ist bereits user-isoliert (`s.WithUser`, `data/users/<id>/`).
- **Full-Stack:** Go-Modell + TS-Typ + Frontend-Hydration/Save (+ optional Python-Konsum) →
  Deploy ist full-stack, kein frontend-only.
