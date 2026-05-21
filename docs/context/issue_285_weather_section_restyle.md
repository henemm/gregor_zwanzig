# Context: Issue #285 — EditWeatherSection Brand-Token Restyle

## Request Summary

Die Wetter-Sektion im Trip-Editor soll vollständig auf Brand-Tokens umgestellt werden: Das Roh/Indikator-Toggle als echten Segmented Control (neue Komponente), Kategorie-Überschriften mit Hairline-Underline und Brand-Farbe, Row-Hover mit Brand-Token statt Tailwind-Klassen.

## Ist-Zustand (was zu ändern ist)

### EditWeatherSection.svelte — bereits erledigt
- `<Checkbox>` (gz-Komponente mit Brand-Tokens) wird bereits korrekt verwendet — ✅ done
- `<Select>` (gz-Komponente mit Brand-Tokens) wird bereits korrekt verwendet — ✅ done

### EditWeatherSection.svelte — noch offen

**Roh/Indikator Toggle (Zeilen ca. 183–196):**
```html
<span class="inline-flex border rounded overflow-hidden text-xs flex-shrink-0">
  <button ... class="px-1.5 py-0.5 {!(friendlyMap[metric.id] ?? true) ? 'bg-primary text-primary-foreground' : ...}">Roh</button>
  <button ... class="px-1.5 py-0.5 {(friendlyMap[metric.id] ?? true) ? 'bg-primary text-primary-foreground' : ...}">Indikator</button>
</span>
```
Problem: `bg-primary text-primary-foreground` sind Tailwind-Klassen, die gegen Brand-Tokens kämpfen.

**Kategorie-Überschriften (Zeile ca. 172):**
```html
<h4 class="text-sm font-semibold">{CATEGORY_LABELS[cat] ?? cat}</h4>
```
Problem: kein `--g-ink`, kein Hairline-Underline.

**Row-Hover (Zeile ca. 175):**
```html
<div class="flex items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-muted/50">
```
Problem: `hover:bg-muted/50` statt `--g-surface-2`, kein `min-h`.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/edit/EditWeatherSection.svelte` | Hauptdatei — alle Änderungen hier |
| `frontend/src/lib/components/ui/segmented/` | **Neu** — Segmented.svelte + index.ts |
| `frontend/src/app.css` | Brand-Tokens: `--g-ink`, `--g-ink-faint`, `--g-ink-muted`, `--g-paper`, `--g-surface-2`, `--g-radius-sm`, `--g-font-data` |

## Neue Komponente: Segmented Control

Neues Verzeichnis `frontend/src/lib/components/ui/segmented/` mit:
- `Segmented.svelte` — Outer-Wrapper mit `role="radiogroup"`, Brand-Token-Styles
- `index.ts` — Re-Export

Begründung: Die Komponente wird laut Issue auch in `ModeCard.svelte` (AlertRulesEditor) benötigt.

## Design Tokens (relevant)

```css
--g-ink:        #1a1a18   /* aktives Segment BG */
--g-paper:      #f6f4ee   /* aktives Segment Text */
--g-ink-muted:  #5c5a52   /* inaktiver Text */
--g-ink-faint:  #9c9a90   /* Outer-Border */
--g-surface-2:  #e3dfd4   /* Hover-BG */
--g-radius-sm:  0.25rem   /* Outer-Radius */
--g-font-data:  JetBrains Mono  /* Segment-Labels */
```

## Acceptance Criteria (aus Issue)

- [ ] Kein `bg-primary`/`text-primary-foreground` in dieser Datei
- [ ] Roh/Indikator rendert als Single Segmented Control (ein äußerer Border, zwei Zellen)
- [ ] Aktives Segment: `--g-ink` BG, `--g-paper` Text
- [ ] Inaktive Segmente: `--g-ink-muted` Text, transparent BG
- [ ] Kategorie-Überschriften haben Hairline-Underline (`--g-ink-faint`)
- [ ] `metric-checkbox-{id}` und `weather-template-select` testids bleiben erhalten

## Risiken

- Kein E2E-Test prüft derzeit Roh/Indikator — rein visuell
- `Segmented.svelte` muss auch zukünftig für ModeCard nutzbar sein (interface-stabil halten)
