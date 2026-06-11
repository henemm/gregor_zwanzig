# Context: issue-763-step5-select

## Request Summary
Das native `<select>` für den "Horizont" (forecastHours) in `compare/steps/Step5Versand.svelte`
soll auf die Design-System-Komponente `ui/select/Select.svelte` umgestellt werden
(Konsistenz + iOS-Zoom-Guard, vgl. #278/#382). Datenerhaltend, gleiche Optionen/Binding.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte` | Enthält das native `<select data-testid="compare-step5-forecast-hours">` (Sektion "Horizont"), das migriert wird |
| `frontend/src/lib/components/ui/select/Select.svelte` | Ziel-Komponente: `value=$bindable()`, `onchange`, `children`, restProps (testid wird durchgereicht); enthält iOS-Zoom-Guard (font-size:16px @max-width:767px) |
| `frontend/src/lib/components/ui/select/index.ts` | Export: `export { Select }` |
| `frontend/src/lib/components/compare/PresetHeader.svelte` | **Exakte Vorbild-Nutzung** (Z.84-93): identischer forecastHours-Select über `<Select bind:value={forecastHours}>` mit `<option value={24/48/72}>` |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | `forecastHours = $state(48)` — **Number**-Typ; muss erhalten bleiben |

## Existing Patterns
- `import { Select } from '$lib/components/ui/select';`
- `<Select bind:value={state.forecastHours}><option value={24}>...</option></Select>`
- Svelte-`bind:value` auf `<select>` mit numerischen `<option value={n}>` erhält den Number-Typ — bestätigt durch PresetHeader (gleiches Feld).
- `data-testid` wird via restProps an das innere `<select>` durchgereicht → Test-Selektor bleibt stabil.

## Dependencies
- Upstream: `state.forecastHours` (Number) aus CompareWizardState; wird im save-Payload als `forecast_hours` gesendet (Z.70/113).
- Downstream: E2E-Selektor `compare-step5-forecast-hours`; save-Payload `forecast_hours`.

## Existing Specs
- `docs/specs/modules/issue_443_compare_wizard_step5_versand.md` — Spec von Step 5

## Risks & Considerations
- **Number-Typ-Erhalt:** Wenn die Migration den Number-Typ in String wandelt, bricht `forecast_hours` im Payload. PresetHeader beweist, dass `bind:value` über die Wrapper-Komponente den Typ erhält → Risiko gering, aber im E2E zu verifizieren (Payload-Wert).
- **Styling:** Native Klassen (`w-full border rounded...`) entfallen; `Select.svelte` bringt eigenes Styling + Chevron mit. `class="w-full"` für volle Breite mitgeben.
- Frontend-only, ~3 Zeilen netto.
