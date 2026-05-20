# Context: Issue #289 — Fix undefined --g-surface / --g-surface-alt tokens

## Request Summary

8 CSS-Stellen in 5 Svelte-Komponenten verwenden `--g-surface` und `--g-surface-alt`, die in `app.css` nicht existieren. Stattdessen fallen sie auf Hex-Fallbacks (`#fff`, `#f5f5f5`, `#fafafa`) zurück. Die korrekten Token heißen `--g-surface-0` und `--g-surface-1`.

## Token-Mapping

| Verwendet | Status | Fallback (alt) | Korrekter Ersatz |
|---|---|---|---|
| `--g-surface` | ❌ undefiniert | `#fff` | `--g-surface-0` (Hintergrund) oder `--g-paper` (Textfarbe = versteckter Checkmark) |
| `--g-surface-alt` | ❌ undefiniert | `#f5f5f5` / `#fafafa` | `--g-surface-1` |

## Definierte Tokens in app.css

```css
--g-paper:      #f6f4ee;   /* = surface-0, Basis-Hintergrund */
--g-surface-0:  #f6f4ee;   /* Warm-Cream, hellste Fläche */
--g-surface-1:  #edeae1;   /* Etwas dunkler, Alt-Flächen */
--g-surface-2:  #e3dfd4;   /* Dunkelste Fläche */
```

## Betroffene Dateien

| Datei | Zeile | Token | Kontext | Ersatz |
|---|---|---|---|---|
| `trip-detail/SavePresetDialog.svelte` | 225 | `--g-surface` | background Dialog-Bereich | `--g-surface-0` |
| `trip-detail/SavePresetDialog.svelte` | 201 | `--g-surface-alt` | background Alt-Fläche | `--g-surface-1` |
| `trip-detail/MetricCheckbox.svelte` | 123 | `--g-surface` | background Checkbox | `--g-paper` |
| `trip-detail/MetricCheckbox.svelte` | 124 | `--g-surface` | color (Checkmark verstecken) | `--g-paper` |
| `trip-detail/WeatherMetricsTab.svelte` | 376 | `--g-surface` | background Tabellen-Bereich | `--g-surface-0` |
| `trip-detail/PresetRow.svelte` | 43 | `--g-surface` | background Zeile | `--g-surface-0` |
| `trip-detail/PresetRow.svelte` | 50 | `--g-surface` in `color-mix()` | active-state Hintergrund | `--g-surface-0` |
| `trip-detail/TablePreview.svelte` | 103 | `--g-surface-alt` | background Tabellen-Alt-Zeilen | `--g-surface-1` |

## Hinweis MetricCheckbox Zeile 124

`color: var(--g-surface, #fff)` dient dazu, den SVG-Checkmark in unkontrolliertem Zustand unsichtbar zu machen (Farbe = Hintergrundfarbe). Da `--g-paper` = `#f6f4ee` (nicht reines Weiß), muss hier `--g-paper` verwendet werden — passt zum `background: var(--g-paper)` auf Zeile 123.

## Ansatz

**Direkte Ersetzung** in den 5 Komponenten (kein Alias in app.css). Der Issue-Text schlägt alternativ Aliases vor, aber direkte Ersetzung ist expliziter und zieht keine versteckten Abhängigkeiten ein.

Fallbacks werden entfernt, da die Ziel-Token in app.css definiert sind.

## Akzeptanzkriterien (aus Issue)

- `grep -rn "var(--g-surface[^-0-9]" frontend/src/lib/` → 0 Treffer
- `grep -rn "var(--g-surface-alt" frontend/src/lib/` → 0 Treffer
- Visuell: Keine unbeabsichtigte Farbänderung (Fallback war #fff ≈ --g-surface-0, konservativ)

## Dependencies

- **app.css** → Definiert alle Ziel-Token (keine Änderung nötig)
- **5 Svelte-Komponenten** → Erhalten die Ersetzungen

## Risiken

- `MetricCheckbox` Zeile 124: `color`-Eigenschaft muss exakt die Hintergrundfarbe treffen → `--g-paper` (nicht `--g-surface-0`, da beide gleich sind, aber `--g-paper` semantisch richtiger für Texte)
- Visuelle Änderung: `#fff` (reines Weiß) → `#f6f4ee` (warmes Creme). Kleine, konservative Änderung im Sinne des Design-Systems.
