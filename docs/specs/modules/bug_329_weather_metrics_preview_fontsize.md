---
entity_id: bug_329_weather_metrics_preview_fontsize
type: bugfix
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [frontend, design-system, css, ap-010]
---

# Bug #329: Hardcodierte font-sizes in WeatherMetricsPreviewCard.svelte → --g-text-* Tokens

## Approval

- [ ] Approved

## Purpose

AP-010 verbietet freie `font-size`-Werte — ausschließlich die `--g-text-*` Typografie-Tokens sind erlaubt. Die Wetter-Metriken-Vorschau-Karte (Epic #135 Step 5, rechte Spalte im Trip-Detail Overview-Tab) nutzt 4 feste rem-Werte. Diese werden auf die definierte Token-Skala gemappt. Keine Logik-Änderungen.

## Source

- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte`
- **Identifier:** `<style>` — `font-size`-Eigenschaften der Selektoren `.card-title`, `.empty-state`, `:global(.chips .chip)`, `.edit-link`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | CSS-Token-Quelle | Definiert `--g-text-*` Typografie-Skala (Z. 109–117) |

## Affected Files

| Datei | Schicht |
|-------|---------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` | Frontend / User-UI |

## Token-Referenz (app.css Z. 109–117)

| Token | Wert |
|-------|------|
| `--g-text-xs` | 11px |
| `--g-text-sm` | 13px |
| `--g-text-md` | 15px |

## Implementation Details

Fallbacks werden **weggelassen** (`var(--g-text-md)`, nicht `var(--g-text-md, 15px)`): Die Tokens sind in `app.css` garantiert definiert, und die Design-System-Linie (#277, #323) hat Fallbacks bei definierten Tokens konsequent entfernt (AP-007).

### Vollständige Ersetzungsliste

| Zeile | Selektor | font-size (Ist) | font-size (Soll) | Begründung |
|-------|----------|-----------------|-------------------|-----------|
| 55 | `.card-title` | `1rem` | `var(--g-text-md)` | Default Body (15px) |
| 60 | `.empty-state` | `0.875rem` | `var(--g-text-sm)` | Meta-Info in Cards (13px) |
| 74 | `:global(.chips .chip)` | `0.75rem` | `var(--g-text-xs)` | Caption/Chip, kleinste Stufe (11px) |
| 79 | `.edit-link` | `0.875rem` | `var(--g-text-sm)` | Meta-Info in Cards (13px) |

## Expected Behavior

- **Input:** `WeatherMetricsPreviewCard.svelte` mit 4 freien rem-`font-size`-Werten.
- **Output:** Dieselben Selektoren mit `--g-text-*` CSS-Custom-Properties; visuell gleichwertiges Karten-Layout.
- **Side effects:** Keine — reine CSS-Änderung ohne Logik-, Props- oder Markup-Anpassung. Custom Properties sind global verfügbar, auch im `:global()`-Selektor.

## Acceptance Criteria

**AC-1:** Given `WeatherMetricsPreviewCard.svelte` / When man `grep -nE 'font-size:\s*[0-9]'` dagegen ausführt / Then liefert der Befehl keine Treffer mehr.

**AC-2:** Given die Karte wird im Wetter-Metriken-/Overview-Tab gerendert / When man sie vor und nach der Änderung visuell vergleicht / Then bleibt das Karten-Layout unverändert (kein Layout-Bruch, keine Überlappung; lediglich beabsichtigter 1px-Feinschliff durch die Token-Skala).

**AC-3:** Given die ersetzten Werte / When die Tokens ausgewertet werden / Then ergeben sich 15px (`.card-title`), 13px (`.empty-state`, `.edit-link`) und 11px (`.chip`) — je 1px kleiner als die rem-Äquivalente, was die beabsichtigte Vereinheitlichung auf die Skala ist.

## Changelog

| Version | Datum | Änderung |
|---------|-------|----------|
| 1.0 | 2026-05-22 | Initiale Spec für Bug #329 — 4 hardcodierte font-sizes in WeatherMetricsPreviewCard.svelte |

## Known Limitations

- Die Token-Werte (11/13/15px) liegen je 1px unter den rem-Äquivalenten (12/14/16px). Dieser minimale Feinschliff ist beabsichtigt und Teil der Vereinheitlichung auf die Typografie-Skala (siehe AC-3).
