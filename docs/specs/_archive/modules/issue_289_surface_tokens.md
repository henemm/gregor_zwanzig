---
entity_id: issue_289_surface_tokens
type: module
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [frontend, design-system, tokens, bug]
---

# Fix: Undefinierte CSS-Token --g-surface / --g-surface-alt

## Approval

- [ ] Approved

## Purpose

5 Svelte-Komponenten verwenden `--g-surface` und `--g-surface-alt`, die in `app.css` nicht definiert sind. Browser fällt auf Hex-Fallbacks (`#fff`, `#f5f5f5`, `#fafafa`) zurück. Diese werden durch die korrekten Design-System-Token `--g-surface-0`, `--g-paper` und `--g-surface-1` ersetzt.

## Source

- **Schicht:** Frontend / User-UI (`frontend/src/lib/components/trip-detail/`)
- **Dateien:** 5 Svelte-Komponenten (8 Stellen)

## Token-Mapping

| Undefinierter Token | Fallback (alt) | Korrekter Ersatz | Wert |
|---|---|---|---|
| `--g-surface` (background) | `#fff` | `--g-surface-0` | `#f6f4ee` |
| `--g-surface` (color/Checkmark) | `#fff` | `--g-paper` | `#f6f4ee` |
| `--g-surface-alt` | `#f5f5f5` / `#fafafa` | `--g-surface-1` | `#edeae1` |

## Betroffene Dateien

| Datei | Zeile | Alt | Neu |
|---|---|---|---|
| `trip-detail/MetricCheckbox.svelte` | 123 | `background: var(--g-surface, #fff)` | `background: var(--g-paper)` |
| `trip-detail/MetricCheckbox.svelte` | 124 | `color: var(--g-surface, #fff)` | `color: var(--g-paper)` |
| `trip-detail/SavePresetDialog.svelte` | 225 | `background: var(--g-surface, #fff)` | `background: var(--g-surface-0)` |
| `trip-detail/SavePresetDialog.svelte` | 201 | `background: var(--g-surface-alt, #f5f5f5)` | `background: var(--g-surface-1)` |
| `trip-detail/PresetRow.svelte` | 43 | `background: var(--g-surface, #fff)` | `background: var(--g-surface-0)` |
| `trip-detail/PresetRow.svelte` | 50 | `color-mix(..., var(--g-surface, #fff))` | `color-mix(..., var(--g-surface-0))` |
| `trip-detail/WeatherMetricsTab.svelte` | 376 | `background: var(--g-surface, #fff)` | `background: var(--g-surface-0)` |
| `trip-detail/TablePreview.svelte` | 103 | `background: var(--g-surface-alt, #fafafa)` | `background: var(--g-surface-1)` |

## Hinweis MetricCheckbox (Zeilen 123–124)

`color: var(--g-surface, #fff)` dient dazu, den SVG-Checkmark im unkontrollierten Zustand unsichtbar zu machen (Farbe entspricht Hintergrundfarbe). Da Hintergrund `--g-paper` wird, muss auch `color` auf `--g-paper` gesetzt werden. Im `:checked`-Zustand (Zeile 131) ist `color: #fff` explizit gesetzt — das bleibt unverändert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | Definition | Definiert `--g-surface-0`, `--g-surface-1`, `--g-paper` (keine Änderung nötig) |

## Implementation Details

Keine neuen Funktionen, keine Architekturänderung. Reine Token-Substitution in 5 Svelte-Komponenten. Hex-Fallbacks werden vollständig entfernt, da alle Ziel-Token in `app.css` definiert sind.

## Expected Behavior

- **Vorher:** `--g-surface` nicht gefunden → Browser nutzt `#fff` (reines Weiß)
- **Nachher:** `--g-surface-0` / `--g-paper` → `#f6f4ee` (warmes Creme, Design-System-konform)
- **Visuelle Änderung:** Minimal — Hintergründe wechseln von reinem Weiß zu warmem Creme (~6 Punkte Helligkeitsunterschied)

## Acceptance Criteria

**AC-1:** Given das Frontend gebaut und `frontend/src/lib/` durchsucht / When `grep -rn "var(--g-surface[^-0-9]" frontend/src/lib/` ausgeführt / Then 0 Treffer (kein undefinierter `--g-surface`-Token mehr)
- Test: (populated after /tdd-red)

**AC-2:** Given das Frontend gebaut und `frontend/src/lib/` durchsucht / When `grep -rn "var(--g-surface-alt" frontend/src/lib/` ausgeführt / Then 0 Treffer (kein `--g-surface-alt`-Token mehr)
- Test: (populated after /tdd-red)

**AC-3:** Given `MetricCheckbox.svelte` / When Komponente im Browser gerendert (unkontrollierter Zustand) / Then Checkbox-Hintergrund und Checkmark-Farbe stimmen überein (`--g-paper` = `#f6f4ee`), Checkmark nicht sichtbar
- Test: (populated after /tdd-red)

**AC-4:** Given `PresetRow.svelte` / When Zeile im `active`-Zustand / Then `color-mix`-Basis ist `--g-surface-0`, kein Hex-Fallback
- Test: (populated after /tdd-red)

## Known Limitations

Keine.

## Changelog

- 2026-05-20: Initial spec created (Issue #289)
