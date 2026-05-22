---
entity_id: bug_274_safe_area_insets
type: bug-fix
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [frontend, mobile, css, ios]
---

# Bug #274 — Safe-Area-Insets

## Approval

- [ ] Approved

## Purpose

Zwei fehlende Safe-Area-Fixes schließen, damit die Sticky-Bottom-Bar im Trip-Edit auf iPhones mit Home-Indikator (iPhone X und neuer) nicht durch den Home-Indikator verdeckt wird.

## Source

- **Datei 1:** `frontend/src/app.html`
- **Datei 2:** `frontend/src/lib/components/edit/TripEditView.svelte`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `BottomNav.svelte` | Referenz | Hat safe-area-Padding korrekt — als Vorbild |
| `TripWizardShell.svelte` | Referenz | Hat safe-area-Padding korrekt — als Vorbild |

## Implementation Details

### Fix 1 — `frontend/src/app.html` Zeile 6

```html
<!-- Vorher -->
<meta name="viewport" content="width=device-width, initial-scale=1" />

<!-- Nachher -->
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
```

`viewport-fit=cover` ist Pflicht damit `env(safe-area-inset-bottom)` auf iOS Safari überhaupt wirkt. Ohne dieses Flag ignoriert der Browser alle safe-area-env()-Aufrufe.

### Fix 2 — `frontend/src/lib/components/edit/TripEditView.svelte` Zeile 138–139

```html
<!-- Vorher -->
<div class="fixed bottom-0 left-0 right-0 bg-background border-t p-3
            flex gap-2 justify-end">

<!-- Nachher -->
<div class="fixed bottom-0 left-0 right-0 bg-background border-t p-3
            flex gap-2 justify-end"
     style="padding-bottom: calc(0.75rem + env(safe-area-inset-bottom, 0px));">
```

Das bestehende `p-3` (= 0.75rem, entspricht 12px) bleibt erhalten; der Safe-Area-Wert wird addiert. Auf Geräten ohne Home-Indikator ist `env(safe-area-inset-bottom, 0px)` = 0, d.h. kein visueller Unterschied.

## Expected Behavior

- **Ohne Änderung:** `env(safe-area-inset-bottom)` hat auf iOS Safari keinen Effekt (fehlendes `viewport-fit=cover`); Action-Bar im Trip-Edit kann Home-Indikator überlappen
- **Mit Änderung:** Auf iPhones mit Home-Indikator hat die Action-Bar ausreichend Abstand zum Bildschirmrand; auf anderen Geräten kein sichtbarer Unterschied

## Acceptance Criteria

**AC-1:** Given `app.html` wird im Browser geladen / When der Viewport-Meta-Tag geprüft wird / Then enthält er `viewport-fit=cover` als Teil des content-Attributs.
- Test: (populated after /tdd-red)

**AC-2:** Given die Trip-Edit-Seite ist geöffnet / When die Action-Bar (`[data-testid="edit-save-btn"]`) im DOM geprüft wird / Then hat ihr Container-Element einen `style`-Attribut mit `padding-bottom` und `env(safe-area-inset-bottom`.
- Test: (populated after /tdd-red)

**AC-3:** Given ein Gerät ohne Home-Indikator / When die Action-Bar gerendert wird / Then beträgt das padding-bottom mindestens 0.75rem (= 12px, entspricht dem bisherigen `p-3`).
- Test: (populated after /tdd-red)

## Known Limitations

- Testbarkeit: `env(safe-area-inset-bottom)` ergibt im Playwright-/Browser-Test-Kontext immer 0px (kein echter iOS-Viewport). Akzeptanz-Nachweis erfolgt über DOM-Attribut-Prüfung (AC-1, AC-2), nicht über gemessenen Pixel-Abstand.

## Changelog

- 2026-05-22: Initial spec erstellt (Bug #274)
