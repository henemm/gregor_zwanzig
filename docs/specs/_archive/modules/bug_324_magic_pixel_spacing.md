---
entity_id: bug_324_magic_pixel_spacing
type: bugfix
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [frontend, design-system, css, ap-008]
---

# Bug #324: Magic-Pixel-Spacing → --g-s-* Tokens

## Approval

- [ ] Approved

## Purpose

AP-008 verbietet freie Pixel-Werte bei `padding`, `margin` und `gap` — ausschließlich `--g-s-*` Spacing-Tokens sind erlaubt. 17 Verstöße in 6 Svelte-Komponenten werden auf die definierte Token-Skala gemappt. Keine Logik-Änderungen.

## Source

- **File:** `frontend/src/lib/components/edit/EditWeatherSection.svelte`, `frontend/src/lib/components/trip-detail/waypoints/StageCard.svelte`, `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte`, `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte`, `frontend/src/routes/_home/TripKachel.svelte`, `frontend/src/routes/_home/CompareKachel.svelte`
- **Identifier:** `<style>` — CSS-Spacing-Eigenschaften in den jeweiligen Scoped-Styles

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | CSS-Token-Quelle | Definiert `--g-s-*` Spacing-Skala (Z. 126–136) |

## Affected Files

| Datei | Schicht |
|-------|---------|
| `frontend/src/lib/components/edit/EditWeatherSection.svelte` | Frontend / User-UI |
| `frontend/src/lib/components/trip-detail/waypoints/StageCard.svelte` | Frontend / User-UI |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | Frontend / User-UI |
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | Frontend / User-UI |
| `frontend/src/routes/_home/TripKachel.svelte` | Frontend / User-UI |
| `frontend/src/routes/_home/CompareKachel.svelte` | Frontend / User-UI |

## Token-Referenz (app.css Z. 126–136)

| Token | Wert |
|-------|------|
| `--g-s-1` | 4px |
| `--g-s-2` | 8px |
| `--g-s-3` | 12px |
| `--g-s-4` | 16px |

## Implementation Details

Jede Ersetzung folgt der Mapping-Tabelle aus dem Issue:

| Pixel | Ersatz | Begründung |
|-------|--------|-----------|
| 2px | `0` | Kein Token < 4px; nur y-Padding bei `min-height: 28px` |
| 4px | `var(--g-s-1)` | exakt |
| 5px | `var(--g-s-1)` | nächster (diff 1px) |
| 6px | `var(--g-s-2)` | per Issue-Mapping |
| 8px | `var(--g-s-2)` | exakt |
| 10px | `var(--g-s-3)` | nächster (diff 2px) |
| 12px | `var(--g-s-3)` | exakt |
| 14px | `var(--g-s-4)` | nächster (diff 2px) |
| 16px | `var(--g-s-4)` | exakt |

### Vollständige Ersetzungsliste

| Datei | Eigenschaft (Ist) | Eigenschaft (Soll) |
|-------|-------------------|---------------------|
| EditWeatherSection.svelte:240 | `gap: 8px` | `gap: var(--g-s-2)` |
| EditWeatherSection.svelte:241 | `padding: 2px 4px` | `padding: 0 var(--g-s-1)` |
| StageCard.svelte:123 | `gap: 4px` | `gap: var(--g-s-1)` |
| StageCard.svelte:126 | `padding: 8px` | `padding: var(--g-s-2)` |
| StageCard.svelte:171 | `gap: 6px` | `gap: var(--g-s-2)` |
| AlertRuleRow.svelte:360 | `gap: 12px` | `gap: var(--g-s-3)` |
| AlertRuleRow.svelte:361 | `padding: 10px 14px` | `padding: var(--g-s-3) var(--g-s-4)` |
| AlertRuleRow.svelte:441 | `padding: 4px 0` | `padding: var(--g-s-1) 0` |
| AlertRuleRow.svelte:446 | `padding: 8px 14px` | `padding: var(--g-s-2) var(--g-s-4)` |
| AlertRulesEditor.svelte:85 | `padding: 12px 14px` | `padding: var(--g-s-3) var(--g-s-4)` |
| AlertRulesEditor.svelte:93 | `padding: 8px 12px` | `padding: var(--g-s-2) var(--g-s-3)` |
| TripKachel.svelte:55 | `gap: 6px` | `gap: var(--g-s-2)` |
| TripKachel.svelte:56 | `padding: 14px 16px` | `padding: var(--g-s-4)` |
| TripKachel.svelte:83 | `gap: 5px` | `gap: var(--g-s-1)` |
| CompareKachel.svelte:46 | `gap: 6px` | `gap: var(--g-s-2)` |
| CompareKachel.svelte:47 | `padding: 14px 16px` | `padding: var(--g-s-4)` |
| CompareKachel.svelte:74 | `gap: 5px` | `gap: var(--g-s-1)` |

## Expected Behavior

- **Input:** 6 Svelte-Komponenten mit freien Pixel-Werten in `padding`/`margin`/`gap`-Eigenschaften
- **Output:** Dieselben Eigenschaften mit `--g-s-*` CSS-Custom-Properties; visuell gleichwertiges Ergebnis
- **Side effects:** Keine — reine CSS-Änderungen ohne Logik- oder Props-Anpassungen

## Acceptance Criteria

**AC-1:** Given die 6 betroffenen Svelte-Dateien / When man `grep -rnE '(padding|margin|gap):\s*[0-9]+px'` dagegen ausführt / Then liefert der Befehl keine Treffer mehr in diesen Dateien.

**AC-2:** Given die geänderten Komponenten werden im Browser gerendert / When man TripKachel, CompareKachel, StageCard, AlertRuleRow, AlertRulesEditor und EditWeatherSection aufruft / Then sehen alle Layouts visuell identisch oder gleichwertig aus (max ±4px Spacing-Delta, keine Überlappungen, kein Layout-Bruch).

**AC-3:** Given `padding: 14px 16px` wird zu `padding: var(--g-s-4)` / When das Token ausgewertet wird / Then ergibt sich `16px` auf allen vier Seiten — symmetrisch statt asymmetrisch; akzeptable Abweichung (+2px oben/unten).

## Changelog

| Version | Datum | Änderung |
|---------|-------|----------|
| 1.0 | 2026-05-22 | Initiale Spec für Bug #324 — 17 Magic-Pixel-Verstöße in 6 Komponenten |

## Known Limitations

- `2px`-Vertikalpadding bei `.metric-row` wird zu `0` (kein Token < 4px). Die `min-height: 28px` bleibt Höhenanker.
- Longhand-Properties (`padding-left`, `padding-bottom`) mit Pixelwerten in denselben Dateien sind außerhalb des AP-008-grep-Scope und werden in diesem Issue nicht geändert.
