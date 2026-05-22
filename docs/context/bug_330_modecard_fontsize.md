# Context: Bug #330 — Hardcodierte font-sizes in ModeCard.svelte → --g-text-* Tokens

## Request Summary
`ModeCard.svelte` (Alert-Modus-Auswahl) enthält 5 hardcodierte `font-size`-Werte. Alle sollen auf die `--g-text-*` Design-System-Tokens umgestellt werden, ohne dass sich das sichtbare Layout ändert.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte` | Die zu ändernde Datei — 5 `font-size`-Treffer im `<style>`-Block |
| `frontend/src/app.css` (Z. 109–117) | Definition der `--g-text-*` Tokens (Single Source of Truth) |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | Geschwister-Komponente, nutzt bereits `font-size: var(--g-text-sm)` — Vorbild-Muster |
| `docs/design-system/ANTI-PATTERNS.md` (AP-017) | Regel "Drift in der Schrift-Skala" — verbietet font-sizes außerhalb der Token-Skala |
| `docs/design-system/TOKENS.md` (Z. 82–90) | Typografie-Skala-Tabelle |

## Konkretes Mapping (auf Basis der TATSÄCHLICHEN Werte)
Die Issue-Tabelle ist ungenau (nennt 0.75/0.875/1/1.125rem). Die echten Werte mappen **exakt** auf Pixel — kein Rundungsfehler, Layout bleibt pixelgenau identisch:

| Zeile | Selektor | Ist-Wert | = px | Ziel-Token |
|-------|----------|----------|------|-----------|
| 105 | `.eyebrow` | `0.6875rem` | 11px | `var(--g-text-xs)` |
| 112 | `.title` | `0.9375rem` | 15px | `var(--g-text-md)` |
| 115 | `.description` | `0.8125rem` | 13px | `var(--g-text-sm)` |
| 120 | `.example` | `11px` | 11px | `var(--g-text-xs)` |
| 131 | `.field-count-badge` | `0.6875rem` | 11px | `var(--g-text-xs)` |

## Existing Patterns
- `font-size: var(--g-text-sm);` — direkte Token-Referenz ohne Hex/px-Fallback (AlertRuleRow.svelte, StageCard.svelte, EditWeatherSection.svelte, Select/Checkbox)
- app.css definiert Tokens als feste px-Werte (`--g-text-xs: 11px;` …), Browser-`rem`-Basis ist 16px, daher 0.6875rem == 11px etc.

## Dependencies
- Upstream: nur `app.css` (Token-Definitionen) — bereits vorhanden
- Downstream: `AlertRulesEditor.svelte` rendert `ModeCard` 3× (Modi absolute/delta/both). Rein visuelle CSS-Änderung, keine API/Props betroffen.

## Existing Specs
- Keine Spec für ModeCard-Styling vorhanden. ModeCard stammt aus Issue #179 (`docs/specs/modules/issue_179_alert_konfigurator_modus_toggle.md`), zuletzt restyled in #284 (`issue_284_alert_rules_restyle`).

## Risks & Considerations
- **Niedriges Risiko:** Reiner CSS-Token-Swap, exakte px-Übereinstimmung garantiert identisches Layout (AC-2).
- **Naming-Diskrepanz:** Issue-Titel nennt "AP-010e", relevant ist tatsächlich **AP-017** in ANTI-PATTERNS.md. Substanz unverändert.
- **Keine Fallbacks hinzufügen:** Konsistent mit #277/#323 (Hex-Fallback-Cleanup) — Tokens ohne `, #hex`-Fallback referenzieren.
- AC-1 verlangt `grep 'font-size:\s*[0-9]'` ohne Treffer → alle 5 Werte müssen ersetzt sein.
