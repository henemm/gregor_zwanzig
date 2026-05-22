---
entity_id: issue_326_alert_font_tokens
type: bugfix
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [frontend, design-system, css, ap-017, ap-008]
---

# Bug #326: Hardcodierte font-sizes in Alert-Karten → Design-Tokens

## Approval

- [ ] Approved

## Purpose

AP-017 (Drift in der Schrift-Skala) verbietet `font-size`-Werte außerhalb der `--g-text-*`
Tokens. Zwei Karten im `alerts-tab/`-Verzeichnis verstoßen aktiv dagegen. Begleitend werden —
analog #324 — auch freie Spacing- (`--g-s-*`, AP-008) und Radius-Werte (`--g-radius-*`)
tokenisiert sowie eine tote CSS-Regel entfernt, damit beide Dateien vollständig Design-konform
sind. Reiner CSS-Refactor, keine Logik-, Props- oder Markup-Änderung.

## Source

- **File:** `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte`, `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte`
- **Identifier:** `<style>` — Scoped-CSS beider Komponenten

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | CSS-Token-Quelle | Definiert `--g-text-*` (Z. 109–117), `--g-s-*` und `--g-radius-*` |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Konsument | Rendert beide Karten (Alarme-Tab der Trip-Detail-Ansicht) — Render-Pfad für den visuellen Check |

## Affected Files

| Datei | Schicht |
|-------|---------|
| `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte` | Frontend / User-UI |
| `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte` | Frontend / User-UI |

## Token-Referenz (app.css)

| Token | Wert | | Token | Wert |
|-------|------|-|-------|------|
| `--g-text-xs` | 11px | | `--g-s-1` | 4px (0.25rem) |
| `--g-text-sm` | 13px | | `--g-s-2` | 8px (0.5rem) |
| | | | `--g-s-4` | 16px (1rem) |
| `--g-radius-sm` | 0.25rem | | `--g-radius-md` | 0.5rem |

## Implementation Details

### Font-Size-Mapping (AP-017)

| Ist | Soll | Delta | Begründung |
|-----|------|-------|-----------|
| `0.875rem` (14px) | `var(--g-text-sm)` (13px) | −1px | Nächster Token; per Issue gewünschtes Mapping |
| `0.8125rem` (13px) | `var(--g-text-xs)` (11px) | −2px | Per Issue-Mapping; erhält Hierarchie (Hint kleiner als Titel) |

> **Hinweis:** Die Pixel-Tabelle im Issue ist faktisch falsch (behauptet `sm`=14px, `xs`=12px;
> `app.css` sagt `sm`=13px, `xs`=11px). Maßgeblich sind die im Issue gemeinten **Token-Namen**,
> nicht dessen Pixel-Angaben. Die 1–2px-Abweichung liegt auf sekundärem Meta-Text und ist nicht
> wahrnehmbar — genau der Sinn von AP-017 (Snap auf die kanonische Skala).

### Spacing-/Radius-Mapping (alle exakt)

| Ist | Soll |
|-----|------|
| `1rem` | `var(--g-s-4)` (exakt 16px) |
| `0.5rem` (padding/margin/gap) | `var(--g-s-2)` (exakt 8px) |
| `0.25rem` (padding) | `var(--g-s-1)` (exakt 4px) |
| `border-radius: 0.5rem` | `var(--g-radius-md)` (exakt) |
| `border-radius: 0.25rem` | `var(--g-radius-sm)` (exakt) |

### Vollständige Ersetzungsliste

| Datei:Zeile | Eigenschaft (Ist) | Eigenschaft (Soll) |
|-------------|-------------------|---------------------|
| AlertQuietHoursCard.svelte:64 | `padding: 1rem` | `padding: var(--g-s-4)` |
| AlertQuietHoursCard.svelte:66 | `border-radius: 0.5rem` | `border-radius: var(--g-radius-md)` |
| AlertQuietHoursCard.svelte:73 | `margin-bottom: 0.5rem` | `margin-bottom: var(--g-s-2)` |
| AlertQuietHoursCard.svelte:75 | `.card-title { font-size: 0.875rem }` | `font-size: var(--g-text-sm)` |
| AlertQuietHoursCard.svelte:76 | `.toggle-label { … }` (gesamte Regel) | **Regel entfernen** (tote CSS) |
| AlertQuietHoursCard.svelte:77 | `.time-row { gap: 1rem }` | `gap: var(--g-s-4)` |
| AlertQuietHoursCard.svelte:78 | `.time-row label { gap: 0.5rem; font-size: 0.875rem }` | `gap: var(--g-s-2); font-size: var(--g-text-sm)` |
| AlertQuietHoursCard.svelte:79 | `.time-input { padding: 0.25rem 0.5rem; border-radius: 0.25rem }` | `padding: var(--g-s-1) var(--g-s-2); border-radius: var(--g-radius-sm)` |
| AlertQuietHoursCard.svelte:80 | `.midnight-hint { margin: 0.5rem 0 0; font-size: 0.8125rem }` | `margin: var(--g-s-2) 0 0; font-size: var(--g-text-xs)` |
| AlertCooldownCard.svelte:36 | `padding: 1rem` | `padding: var(--g-s-4)` |
| AlertCooldownCard.svelte:38 | `border-radius: 0.5rem` | `border-radius: var(--g-radius-md)` |
| AlertCooldownCard.svelte:42 | `.card-title { font-size: 0.875rem }` | `font-size: var(--g-text-sm)` |
| AlertCooldownCard.svelte:44 | `margin: 0 0 0.5rem` | `margin: 0 0 var(--g-s-2)` |
| AlertCooldownCard.svelte:49 | `.input-row { gap: 0.5rem }` | `gap: var(--g-s-2)` |
| AlertCooldownCard.svelte:54 | `.cooldown-input { padding: 0.25rem 0.5rem }` | `padding: var(--g-s-1) var(--g-s-2)` |
| AlertCooldownCard.svelte:56 | `border-radius: 0.25rem` | `border-radius: var(--g-radius-sm)` |
| AlertCooldownCard.svelte:58 | `.unit { font-size: 0.875rem }` | `font-size: var(--g-text-sm)` |
| AlertCooldownCard.svelte:59 | `.hint { margin: 0.5rem 0 0; font-size: 0.8125rem }` | `margin: var(--g-s-2) 0 0; font-size: var(--g-text-xs)` |

### Bewusst unverändert (semantisch erlaubt, AP-008)

- `min-height: 36px` (`.time-input`, `.cooldown-input`) — deliberate Control-Höhe
- `width: 80px` (`.cooldown-input`) — deliberate Feldbreite
- `border: 1px solid var(--g-ink-faint)` — 1px-Trennlinie (AP-008-Ausnahme)
- `background: var(--g-surface-1, #fff)` — toter/falscher Hex-Fallback (AP-007); gehört zur
  Farb-Fallback-Bereinigung (#323/#277), nicht zu diesem Issue

## Expected Behavior

- **Input:** 2 Svelte-Karten mit hardcodierten `font-size`-, Spacing- und Radius-Werten
- **Output:** Dieselben Eigenschaften via `--g-text-*` / `--g-s-*` / `--g-radius-*` Tokens; tote
  `.toggle-label`-Regel entfernt; visuell gleichwertiges Ergebnis
- **Side effects:** Keine — reine CSS-Änderungen, kein Markup, keine Props, keine Logik

## Acceptance Criteria

**AC-1:** Given `AlertQuietHoursCard.svelte` / When man `grep -nE 'font-size:\s*[0-9]'` dagegen ausführt / Then liefert der Befehl keine Treffer mehr (alle `font-size` via `var(--g-text-*)`).

**AC-2:** Given `AlertCooldownCard.svelte` / When man `grep -nE 'font-size:\s*[0-9]'` dagegen ausführt / Then liefert der Befehl keine Treffer mehr (alle `font-size` via `var(--g-text-*)`).

**AC-3:** Given beide Karten / When man `grep -nE '(padding|margin|gap|border-radius):\s*[0-9]'` dagegen ausführt / Then liefert der Befehl keine Treffer mehr (alle Spacing-/Radius-Werte via Token; `min-height`/`width`/`1px`-Border bleiben semantisch).

**AC-4:** Given die tote `.toggle-label`-Regel in `AlertQuietHoursCard.svelte` / When man die Datei nach `toggle-label` durchsucht / Then existiert weder Markup noch Style-Regel dazu.

**AC-5:** Given beide Karten werden im Alarme-Tab (Trip-Detail) gerendert / When man den visuellen Vor/Nach-Vergleich gegen Staging zieht / Then ist das Layout unverändert (Spacing/Radius pixel-identisch, Schrift max. 2px kleiner auf Nebentext, keine Überlappungen, kein Layout-Bruch, Hierarchie Titel > Hint erhalten).

## Known Limitations

- Schrift-Mapping ist nicht pixel-identisch: `0.875rem`→13px (−1px), `0.8125rem`→11px (−2px).
  Bewusst akzeptiert (AP-017-Snap auf kanonische Skala, sekundärer Text).
- Der falsche Hex-Fallback `#fff` in `background: var(--g-surface-1, #fff)` bleibt — gehört zur
  AP-007-Farb-Aufräumung, nicht in dieses Issue.

## Changelog

| Version | Datum | Änderung |
|---------|-------|----------|
| 1.0 | 2026-05-22 | Initiale Spec für Bug #326 — font-size (AP-017) + Spacing/Radius (AP-008) + tote Regel in 2 Alert-Karten |
