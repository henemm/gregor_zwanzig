---
entity_id: bug_328_savepreset_tokens
type: bugfix
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [frontend, design-system, css, ap-007, ap-010, font-size, hex-color, issue-328]
---

# Bug #328: Hardcodierte font-sizes + Hex-Farben in SavePresetDialog.svelte → Tokens

## Approval

- [x] Approved (2026-05-22)

## Purpose

`SavePresetDialog.svelte` enthält im `<style>`-Block 7 hardcodierte `font-size`-Werte (AP-010)
und 2 Inline-Hex-Farben (AP-007). Diese werden auf die Design-System-Tokens `--g-text-*`,
`--g-danger` und `--g-paper` gemappt. Reine CSS-Änderung, keine Logik-Anpassung.

**Bewusste Ausnahme:** Die `font-size: 16px`-Regel im `@media (max-width: 767px)`-Block
(Z. 230) bleibt unverändert. Sie ist der Scoped-Override aus Bug #272 gegen iOS-Safari-Auto-Zoom
und benötigt **exakt 16px** — `--g-text-md` ist nur 15px und würde den Zoom-Schutz reaktivieren.
Diese Zeile erhält stattdessen einen erklärenden Kommentar (AC-1-konform).

## Source

- **File:** `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte`
- **Identifier:** `<style>` — Scoped-CSS-Regeln (Z. 175–230)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | CSS-Token-Quelle | Definiert `--g-text-*` (Z. 109–117), `--g-paper` (Z. 58), `--g-danger` (Z. 75) |
| `docs/specs/modules/bug_272_ios_input_font_size.md` | Vorgänger-Spec | Hat die 16px-`@media`-Regel eingefügt (iOS-Zoom-Schutz) — darf nicht gebrochen werden |

## Affected Files

| Datei | Schicht |
|-------|---------|
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | Frontend / User-UI |

## Token-Referenz (app.css)

| Token | Wert | Verwendung |
|-------|------|-----------|
| `--g-text-xs` | 11px | Captions, Meta-Info |
| `--g-text-sm` | 13px | Body-Text, Inputs, Buttons |
| `--g-text-md` | 15px | Default Body (**nicht** für iOS-Guard geeignet) |
| `--g-danger` | #b33a2a | Fehler-/Gefahren-Farbe |
| `--g-paper` | #f6f4ee | Helle Schrift auf farbigem Grund / App-Hintergrund |

## Implementation Details

Token-Ersetzung ohne Hex-Fallback (folgt etabliertem Muster: `Select.svelte`, `Checkbox.svelte`,
`StageCard.svelte` nutzen `font-size: var(--g-text-sm)` ohne Fallback).

### Vollständige Ersetzungsliste

| Zeile | Selektor | Ist | Soll |
|-------|----------|-----|------|
| 175 | `.field-label` | `font-size: 0.8125rem` | `font-size: var(--g-text-xs)` |
| 187 | `.field input/textarea` | `font-size: 0.875rem` | `font-size: var(--g-text-sm)` |
| 193 | `.field-inline` | `font-size: 0.875rem` | `font-size: var(--g-text-sm)` |
| 197 | `.summary` | `font-size: 0.8125rem` | `font-size: var(--g-text-xs)` |
| 204 | `.error` | `font-size: 0.8125rem` | `font-size: var(--g-text-xs)` |
| 205 | `.error` | `color: #dc2626` | `color: var(--g-danger)` |
| 210 | `.btn-primary/.btn-secondary` | `font-size: 0.875rem` | `font-size: var(--g-text-sm)` |
| 217 | `.btn-primary` | `color: #fff` | `color: var(--g-paper)` |
| 230 | `@media .field input/textarea` | `font-size: 16px` | **unverändert** + Kommentar `/* iOS zoom guard (#272): exakt 16px, --g-text-md (15px) wuerde Auto-Zoom reaktivieren */` |

## Expected Behavior

- **Input:** `SavePresetDialog.svelte` mit 7 hardcodierten font-sizes + 2 Inline-Hex-Farben.
- **Output:** Dieselben Regeln über Design-Tokens; die 16px-iOS-Guard-Regel bleibt erhalten + kommentiert.
- **Side effects:** Keine Logik-/Props-Änderung. Geringfügige, gewollte visuelle Verschiebung:
  Schrift minimal kleiner (13→11px, 14→13px), Fehler-Rot → System-Danger, Button-Text → warmes Off-White.

## Acceptance Criteria

**AC-1:** Given `SavePresetDialog.svelte` / When man `grep -nE 'font-size:\s*[0-9]'` ausführt / Then liefert der Befehl genau einen Treffer — die `@media`-Zeile (Z. 230) mit `16px` und vorangestelltem iOS-zoom-guard-Kommentar; alle übrigen font-size-Regeln nutzen `var(--g-text-*)`.

**AC-2:** Given `SavePresetDialog.svelte` / When man `grep -nE 'color:\s*#'` ausführt / Then liefert der Befehl keine Treffer mehr; beide Farben nutzen `var(--g-danger)` bzw. `var(--g-paper)`.

**AC-3:** Given der Dialog wird im Browser geöffnet / When man Fehlermeldung und Buttons rendert / Then erscheint das Fehler-Rot als System-Danger (#b33a2a) und der Primary-Button-Text in `--g-paper`, ohne Layout-Bruch oder unleserlichen Kontrast; auf Mobile-Viewport (≤767px) bleiben Eingabefelder bei 16px (kein iOS-Auto-Zoom).

## Changelog

| Version | Datum | Änderung |
|---------|-------|----------|
| 1.0 | 2026-05-22 | Initiale Spec für Bug #328 — 7 font-size + 2 Hex-Farben, iOS-Guard als Ausnahme |

## Known Limitations

- `#fff → --g-paper` ist semantisch grenzwertig (`--g-paper` heißt „App-Hintergrund"). Es gibt
  keinen dedizierten „Schrift-auf-Accent"-Token; der Codebase nutzt teils weiterhin `#fff`. Ein
  systemweiter `--g-on-accent`-Token wäre sauberer — separates Backlog-Thema, nicht Teil von #328.
- Schriftgrößen verkleinern sich minimal (rem-Werte gingen von Browser-Default 16px aus, Tokens
  sind 1px kleiner). Gewollt und vom Issue akzeptiert (keine font-size in den Farb-Akzeptanzkriterien).
