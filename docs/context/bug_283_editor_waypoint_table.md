# Context: Bug #283 — Trip-Editor Wegpunkt-Tabelle

## Request Summary

Die Wegpunkt-Zeilen im Trip-Editor (Etappen-Accordion) sollen als echte Tabelle mit Spaltenköpfen, JetBrains Mono Koordinaten, Höheneinheit "m" und einem gepflegten AccordionSection-Header dargestellt werden.

## Related Files

| Datei | Relevanz |
|-------|---------|
| `frontend/src/lib/components/edit/EditStagesSection.svelte` | Hauptkomponente — Wegpunkt-Grid, Inputs, Stage-Header |
| `frontend/src/lib/components/edit/AccordionSection.svelte` | Accordion-Wrapper — Header-Styling muss gefixt werden |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Verwendet beide obigen Komponenten — kein Änderungsbedarf |
| `frontend/src/app.css` | Globale Utility-Klassen — `.g-num-input` und `.g-th` werden neu hinzugefügt |

## Existing Patterns

- `--g-font-data` ist bereits definiert (JetBrains Mono, Zeile 94 in app.css)
- `--g-surface-2`, `--g-ink-faint`, `--g-ink-muted`, `--g-text-sm`, `--g-text-md`, `--g-radius-md` sind alle als Token vorhanden
- iOS-Safari-Fix: `@media (max-width: 767px)` erzwingt `font-size: 16px` auf Inputs — muss für `g-num-input` erhalten bleiben
- Bestehende data-testids die NICHT verändert werden dürfen: `waypoint-{wi}`, `wp-name`, `wp-lat`, `wp-lon`, `wp-ele`, `wp-trash-mobile`, `stage-card-{si}`, `stage-move-up-{si}`, `stage-move-down-{si}`, `edit-section-{id}`, `edit-section-{id}-header`

## Änderungsumfang

### 1. `app.css` — 2 neue Utility-Klassen

```css
.g-num-input {
  font-family: var(--g-font-data);
  font-variant-numeric: tabular-nums;
  font-size: var(--g-text-sm);
}
.g-th {
  font-family: var(--g-font-data);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--g-ink-faint);
}
```

### 2. `EditStagesSection.svelte`

- Spaltenköpfe-Zeile (Name / Lat / Lon / Höhe) vor dem `{#each stage.waypoints}` — nur Desktop (`hidden sm:grid`)
- Lat/Lon/Ele-Inputs: Klasse zu `g-num-input text-right sm:w-[88px]`
- Ele-Input: Wrapped in `.g-num-with-unit` Label mit `m`-Suffix-Span
- Datum-Input des Stage-Headers: `g-num-input` hinzufügen
- Grid-Spalten für Desktop: `grid-cols-[1fr_88px_88px_88px_32px]` in Spaltenköpfe

### 3. `AccordionSection.svelte`

- Header-bg: `bg-muted/50` → explizit `var(--g-surface-2)`
- Text: `text-primary` (beim offenen Zustand) → `var(--g-ink)`, kein Primary-Blau
- Offener Border: `border-primary` → `border-[var(--g-ink-faint)]`
- Chevron-Icon statt `+`/`-` ASCII-Zeichen, 14px, `color: var(--g-ink-muted)`
- `rounded-lg` → `rounded-[var(--g-radius-md)]`

## Risks & Considerations

- iOS-Safari-Fix (Zeile 361–365 in app.css) muss erhalten bleiben — `g-num-input` setzt `font-size: var(--g-text-sm)` = 13px, aber der Media-Query überschreibt das auf Mobile auf 16px (korrekt!)
- Playwright-Tests in `e2e/waypoints-editor.spec.ts` testen den Detail-Tab (`#stages`), NICHT den Edit-View — kein Konflikt
- AccordionSection wird auch für Route/Wetter/Alerts/Reports genutzt — Styling-Änderung wirkt sich auf alle aus (gewollt laut Issue)
- Desktop-Grid-Layout der Waypoint-Rows ist fragil (laut Issue) — `sm:contents` bleibt; Spaltenbreiten werden durch `sm:w-[88px]` fixiert
