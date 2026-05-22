# Context: Bug #324 — Magic-Pixel-Spacing → --g-s-* Tokens

## Request Summary
AP-008 verbietet freie Pixel-Werte bei `padding`, `margin`, `gap` — ausschließlich `--g-s-*` Spacing-Tokens sind erlaubt. 17 Verstöße in 6 Produktiv-Komponenten müssen auf die Token-Skala gemappt werden.

## Token-Skala (app.css)
| Token | Wert |
|-------|------|
| `--g-s-1` | 4px |
| `--g-s-2` | 8px |
| `--g-s-3` | 12px |
| `--g-s-4` | 16px |
| `--g-s-5` | 20px |

Kein Token für 2px — kleinster Token ist `--g-s-1` (4px).

## Mapping-Tabelle (per Issue #324)
| Pixelwert | Token | Anmerkung |
|-----------|-------|-----------|
| 2px | `0` | Kein Token; nur als y-Padding mit min-height 28px → 0 vertretbar |
| 4px | `--g-s-1` | exakt |
| 5px | `--g-s-1` | nächster (diff 1px) |
| 6px | `--g-s-2` | per Issue-Mapping (diff 2px, größeren Token gewählt) |
| 8px | `--g-s-2` | exakt |
| 10px | `--g-s-3` | nächster (diff 2px) |
| 12px | `--g-s-3` | exakt |
| 14px | `--g-s-4` | nächster (diff 2px) |
| 16px | `--g-s-4` | exakt |

## Vollständige Verstoß-Liste (grep-AC-Scope)
*Nur Eigenschaften der Form `padding:`, `margin:`, `gap:` — shorthand-Properties mit Doppelpunkt direkt nach dem Token-Namen.*

| Datei | Zeile | Ist | Soll |
|-------|-------|-----|------|
| `EditWeatherSection.svelte` | 240 | `gap: 8px` | `var(--g-s-2)` |
| `EditWeatherSection.svelte` | 241 | `padding: 2px 4px` | `0 var(--g-s-1)` |
| `StageCard.svelte` | 123 | `gap: 4px` | `var(--g-s-1)` |
| `StageCard.svelte` | 126 | `padding: 8px` | `var(--g-s-2)` |
| `StageCard.svelte` | 171 | `gap: 6px` | `var(--g-s-2)` |
| `AlertRuleRow.svelte` | 360 | `gap: 12px` | `var(--g-s-3)` |
| `AlertRuleRow.svelte` | 361 | `padding: 10px 14px` | `var(--g-s-3) var(--g-s-4)` |
| `AlertRuleRow.svelte` | 441 | `padding: 4px 0` | `var(--g-s-1) 0` |
| `AlertRuleRow.svelte` | 446 | `padding: 8px 14px` | `var(--g-s-2) var(--g-s-4)` |
| `AlertRulesEditor.svelte` | 85 | `padding: 12px 14px` | `var(--g-s-3) var(--g-s-4)` |
| `AlertRulesEditor.svelte` | 93 | `padding: 8px 12px` | `var(--g-s-2) var(--g-s-3)` |
| `TripKachel.svelte` | 55 | `gap: 6px` | `var(--g-s-2)` |
| `TripKachel.svelte` | 56 | `padding: 14px 16px` | `var(--g-s-4)` (beide Seiten 16px) |
| `TripKachel.svelte` | 83 | `gap: 5px` | `var(--g-s-1)` |
| `CompareKachel.svelte` | 46 | `gap: 6px` | `var(--g-s-2)` |
| `CompareKachel.svelte` | 47 | `padding: 14px 16px` | `var(--g-s-4)` (beide Seiten 16px) |
| `CompareKachel.svelte` | 74 | `gap: 5px` | `var(--g-s-1)` |

## Außerhalb grep-AC-Scope (padding-left/padding-bottom etc.)
- `EditWeatherSection.svelte` Z.234: `padding-bottom: 4px` — nicht im AC-grep, nicht in Scope
- `EditWeatherSection.svelte` Z.235: `margin-bottom: 4px` — nicht im AC-grep, nicht in Scope  
- `AlertRuleRow.svelte` Z.460: `padding-left: 12px` — nicht im AC-grep, nicht in Scope

## Risiken
- Visuelle Regression: Spacing-Änderungen können Layout minimal verschieben. Mapping-Werte sind nah genug (max ±4px Differenz).
- `padding: 14px 16px` → `var(--g-s-4)` gibt `16px 16px` statt `14px 16px` — minimale Änderung (~1.4%).
- `padding: 2px 4px` → `0 var(--g-s-1)`: Vertikaler Padding entfällt; min-height 28px ist Anker.

## Referenzen
- `docs/design-system/ANTI-PATTERNS.md` → AP-008
- `docs/design-system/TOKENS.md` → `--g-s-*` Spacing-Skala
- `frontend/src/app.css` Z. 126–136 — Token-Definitionen
