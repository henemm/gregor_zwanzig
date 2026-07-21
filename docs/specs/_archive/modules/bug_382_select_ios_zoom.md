---
entity_id: bug_382_select_ios_zoom
type: bugfix
created: 2026-05-25
updated: 2026-05-26
status: done
version: "1.0"
tags: [frontend, ios, accessibility, css]
---

# Bug #382 — Select.svelte iOS-Auto-Zoom (latente #272-Regression)

## Approval

- [x] Approved (2026-05-26)

## Purpose

`Select.svelte` setzt `font-size: var(--g-text-sm)` (= 13 px) auf `.gz-select select` mit CSS-Spezifität (0,1,1). Der globale iOS-Safari-Auto-Zoom-Guard in `app.css` (Bug #272) hat nur Spezifität (0,0,1) und verliert den Spezifitätswettbewerb — alle 14 Einsatzorte der Komponente lösen beim Fokus auf iOS den ungewollten Viewport-Zoom aus.

## Source

- **File:** `frontend/src/lib/components/ui/select/Select.svelte`
- **Identifier:** `.gz-select select` (CSS-Regel, Zeile 39)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | Referenz | Globaler iOS-Guard Z. 457–462; Kommentar-Warnung Z. 440–441 |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | Muster | Referenz-Implementierung des scoped `@media`-Override (Z. 337–342) |

## Implementation Details

In `Select.svelte` wird innerhalb des `<style>`-Blocks ein scoped Media-Query-Block ergänzt — identisches Muster wie `SavePresetDialog.svelte`:

```css
/* Vorher — Bug: (0,1,1) schlägt den globalen Guard (0,0,1) */
.gz-select select {
  font-size: var(--g-text-sm);   /* 13px, verliert auf Mobile */
}

/* Nachher — Fix: gleiche Spezifität (0,1,1), aber später im Quelltext → gewinnt */
.gz-select select {
  font-size: var(--g-text-sm);
}
@media (max-width: 767px) {
  .gz-select select {
    font-size: 16px; /* iOS zoom guard (#272, #382) */
  }
}
```

Svelte's Scoping-Hash erhöht die effektive Spezifität beider Regeln gleichmäßig — kein neues Spezifitätsproblem. Desktop bleibt unverändert (Guard greift nur ≤ 767 px).

## Expected Behavior

- **Desktop (≥ 768 px):** `Select.svelte`-Dropdowns rendern mit `font-size: 13px` — unverändert
- **Mobile (≤ 767 px):** `Select.svelte`-Dropdowns rendern mit `font-size: 16px` — kein iOS-Auto-Zoom beim Fokus
- **Betroffene Einsatzorte (14):** alle verwenden dieselbe Komponente und werden durch den Fix in einem Schritt korrigiert

## Acceptance Criteria

**AC-1:** Given ein `<Select>`-Dropdown auf einem Viewport ≤ 767 px / When das Element den Fokus erhält / Then ist die berechnete `font-size` des `<select>`-Elements ≥ 16 px (kein iOS-Auto-Zoom).
- Test: (populated after /tdd-red)

**AC-2:** Given ein `<Select>`-Dropdown auf einem Viewport ≥ 768 px / When das Element gerendert wird / Then ist die berechnete `font-size` des `<select>`-Elements 13 px (kein Desktop-Rückschritt).
- Test: (populated after /tdd-red)

**AC-3:** Given die Datei `Select.svelte` nach dem Fix / When der CSS-Block analysiert wird / Then enthält `<style>` einen `@media (max-width: 767px)`-Block mit `.gz-select select { font-size: 16px }`.
- Test: (populated after /tdd-red)

## Known Limitations

- Der globale Guard in `app.css` bleibt unverändert (Spezifität 0,0,1); er reicht für native `<select>`-Elemente ohne Wrapper-Klasse, ist aber nicht geeignet für Komponenten mit scoped Stilen.

## Changelog

- 2026-05-26: Implementiert & Doku aktualisiert
- 2026-05-25: Spec erstellt (Bug #382)
