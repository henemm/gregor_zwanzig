# Context: Issue #284 — AlertRulesEditor + ModeCard Restyle

## Request Summary

Die Alarmregeln-Sektion im Trip-Edit-View soll vollständig auf Brand-Tokens umgestellt werden: Buttons via `<Btn>`, Severity-Pills als Outlined-Variante mit deutschen Labels, ModeCard-Beispieltext mono statt kursiv, Listenzeilen als Hairline-Trenner ohne Einzel-Karten.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | Container, Add-Button, List-Wrapper |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | View + Edit Mode; Buttons, Pills, Labels |
| `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte` | Modus-Karten; Example-Text-Styling |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Pill-Komponente; braucht `outlined`-Variante |
| `frontend/src/lib/components/ui/btn/Btn.svelte` | Btn-Komponente; Variants: primary, ghost |
| `frontend/src/lib/components/ui/select/Select.svelte` | Bereits gebrandet, wird schon benutzt |
| `frontend/src/lib/components/ui/checkbox/Checkbox.svelte` | Bereits gebrandet, wird schon benutzt |
| `frontend/src/lib/utils/alertMetricLabels.ts` | ALERT_SEVERITY_TONE + neue SEVERITY_LABEL_DE |
| `frontend/src/app.css` | Pill-Styles (outlined-Erweiterung), Btn-Variants |
| `frontend/e2e/alert-rules-editor.spec.ts` | E2E-Tests — must pass |

## Ist-Zustand (was zu ändern ist)

### AlertRulesEditor.svelte
- Add-Button: plain `<button class="add-button">` außerhalb der Liste → soll als `<Btn variant="ghost">` **innerhalb** einer Card am unteren Ende sitzen
- Liste hat keinen Card-Rahmen

### AlertRuleRow.svelte — View Mode
- Edit- und Löschen-Buttons: `.btn-secondary` mit Inline-Styles → `<Btn variant="ghost" size="sm">`
- Severity-Pill: `<Pill tone="warning">` = gefüllt braun/orange → soll **outlined** sein
- Severity-Label: Englisch (`"warning"`) → Deutsch (`"Warnung"`)
- Kind-Badge (`Abs`/`Δ`): `<Pill tone="default">` gefüllt → outlined oder inline-Style passend
- Threshold-Wert: kein Mono-Font definiert → soll `font-family: var(--g-font-data)` + tabular-nums

### AlertRuleRow.svelte — Edit Mode
- Speichern-Button: `class="btn-primary"` mit Inline-Style → `<Btn variant="primary" size="sm">`
- Abbrechen-Button: `class="btn-secondary"` → `<Btn variant="ghost" size="sm">`
- Lokale `.field`-, `.btn-primary`-, `.btn-secondary`-CSS-Blöcke → danach obsolet, entfernen

### ModeCard.svelte
- `.example` hat `font-style: italic` → muss `font-family: var(--g-font-data); font-style: normal; font-size: 11px; letter-spacing: 0;` sein

## Existing Patterns

- `<Btn variant="primary|ghost|outline" size="sm|md">` via `data-slot="btn"` aus `app.css`
- `<Pill tone="warning|danger|info|default|accent">` via `data-slot="pill"` aus `app.css`
- Outlined-Pills fehlen bisher in `app.css` — neue Styles nötig (`[data-slot="pill"][data-outlined]`)
- Alternativ: `data-variant="outlined"` auf Pill übergeben, dann CSS-Selector `[data-variant="outlined"]`
- Design-Tokens: `--g-font-data`, `--g-radius-pill`, `--g-info`, `--g-warning`, `--g-danger`, `--g-ink-faint`

## Critical Test Constraint

`frontend/e2e/alert-rules-editor.spec.ts` AC-2 prüft:
```js
row.first().locator('[data-slot="pill"][data-tone="warning"]')
```
→ **`data-slot="pill"` und `data-tone="warning"` MÜSSEN erhalten bleiben**, auch nach Restyle. Outlined-Variante muss über zusätzliches Attribut oder CSS-Klasse gelöst werden — nicht über Ersatz des Elements.

## Dependencies

- Issue #277 (CSS-Variable-Fallbacks) bereits implementiert — kein `--g-primary`, kein `--g-border` in den 3 Dateien vorhanden (verifiziert)
- Issue #277 hat `app.css` bereits bereinigt — `--g-ink` ist der korrekte Primär-Token
- `Select` und `Checkbox` aus der UI-Lib sind in AlertRuleRow **bereits importiert und benutzt** — kein Handlungsbedarf

## Risks & Considerations

- Pill-outlined Variante muss in `app.css` ergänzt werden (neue Selector-Regel) — einzige globale Änderung
- `SEVERITY_LABEL_DE` als neue Konstante in `alertMetricLabels.ts` → kein Breaking Change
- Die Add-Button-Verschiebung in die Card erfordert Restructuring in `AlertRulesEditor.svelte` (Card-Wrapper um Liste + Button)
- `ModeCard` ist unabhängig; Änderung unkritisch (nur `.example`-Styling)
