# Context: feat-880-autosave-overlay

## Request Summary
Der Autospeicher-Indikator soll (1) den Zeitstempel des letzten Speichervorgangs anzeigen und (2) als fixes Overlay am unteren Bildschirmrand erscheinen — immer sichtbar, scrollunabhängig, ohne Viewport-Verkleinerung, auf Desktop und Mobile.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | SaveStatus-Klasse — braucht `savedAt: Date \| null` Feld |
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | Haupt-Änderung: fixed-overlay + Timestamp-Anzeige |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Nutzt SaveIndicator inline in status-line — muss entfernt werden |
| `frontend/src/routes/trips/[id]/+page.svelte` | Übergibt `saveController` an TripHeader und TripTabs |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | Nutzt SaveIndicator in sticky header (Zeile 269) — muss entfernt werden |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` | Referenz: `height: 64px`, `z-index: 50`, `desktop:hidden`, `padding-bottom: env(safe-area-inset-bottom)` |
| `frontend/src/lib/components/mobile/Sheet.svelte` | Referenz: `env(safe-area-inset-bottom)` Pattern (Zeile 116) |
| `frontend/src/app.css` | Referenz: `.mobile-scroll-pad` mit `calc(64px + env(safe-area-inset-bottom))` |

## Existing Patterns

- **safe-area-inset-bottom**: `Sheet.svelte` nutzt `calc(12px + env(safe-area-inset-bottom))` als padding. `BottomNav` selbst nutzt `padding-bottom: env(safe-area-inset-bottom)`.
- **Fixed-bottom Overlays**: `BottomNav` = `fixed bottom-0 z-50`; `Sheet` = `fixed bottom: 0 z-index: 61`; `Toast` = `z-index: 30`
- **Content-Clearance ohne Viewport-Shrink**: `mobile-scroll-pad` in app.css gibt dem Body `padding-bottom: calc(64px + env(safe-area-inset-bottom))` — Inhalt scrollt über fixed Elemente hinweg, kein Viewport-Resize
- **Debounce-Scheduling**: SaveStatus hat 700ms Debounce mit sofortigem `setSaving()` → Indikator lügt nie

## Z-Index-Landschaft

| Element | Z-Index | Position |
|---------|---------|----------|
| TopAppBar (mobile) | 60 | fixed top |
| Sheet | 60/61 | fixed bottom |
| AlertPresetSelector | 100 | absolute |
| Drawer | 50/51 | fixed |
| BottomNav (mobile) | 50 | fixed bottom |
| Sidebar overlay | 50 | fixed |
| Dialog | 50 | fixed center |
| Toast | 30 | fixed |

→ SaveIndicator-Overlay: **z-index 40** — über normalem Content (z-20), unter Modals/Sheets/BottomNav (z-50+). Auf Mobile sitzt es physisch ÜBER der BottomNav durch `bottom`-Offset, nicht durch z-index-Übertrumpfen.

## Mobile-Positionierung

- BottomNav: `height: 64px` + `padding-bottom: env(safe-area-inset-bottom)`, `desktop:hidden`
- Mobile-Breakpoint: ≤899px
- Overlay auf Mobile: `bottom: calc(64px + env(safe-area-inset-bottom) + 8px)` — sitzt 8px über BottomNav
- Overlay auf Desktop (≥900px): `bottom: 16px` + kein BottomNav-Offset nötig

## Abhängigkeiten

- **Upstream**: SaveStatus (Store), TripDetail-Route (+page.svelte), CompareEditor
- **Downstream**: Nichts weiteres nutzt SaveIndicator

## Analysis

### Type
Feature (UI-Verbesserung)

### Betroffene Dateien

| Datei | Änderungstyp | Beschreibung |
|-------|--------------|--------------|
| `saveStatusStore.svelte.ts` | MODIFY | `savedAt: Date \| null = $state(null)`, gesetzt in `setSaved()` |
| `SaveIndicator.svelte` | MODIFY | `position: fixed`, Breakpoint-CSS, Timestamp-Anzeige, Idle-Fade-Animation |
| `TripHeader.svelte` | MODIFY | `<SaveIndicator>` aus status-line entfernen (3 Zeilen) |
| `CompareEditor.svelte` | MODIFY | `<SaveIndicator>` aus Edit-Toolbar entfernen (1 Zeile) |

### Scope Assessment
- Dateien: 4
- Geschätztes LoC-Delta: +24 netto (~+30/-6)
- Risiko: **Niedrig**

### Technischer Ansatz
- **DOM-Position**: SaveIndicator bleibt in TripHeader/CompareEditor — `position: fixed` ist viewport-relativ, keine Eltern-Transforms vorhanden → kein DOM-Umbau nötig (Option A)
- **Idle-Dimming**: CSS `animation-delay: 3s` + `fill-mode: forwards` → `opacity: 0.5` ohne JS-Timer
- **Timestamp-Format**: `String(h).padStart(2,'0') + ':' + String(m).padStart(2,'0')` — SSR-sicher, keine externe Library
- **Mobile-Offset**: `bottom: calc(64px + env(safe-area-inset-bottom) + 8px)` bei ≤899px; `bottom: 16px` auf Desktop

### Implementierungsreihenfolge
1. `saveStatusStore.svelte.ts`: `savedAt`-Feld + `setSaved()`-Zuweisung
2. `SaveIndicator.svelte`: fixed-Positioning + Breakpoints + Timestamp + Idle-Animation
3. `TripHeader.svelte` + `CompareEditor.svelte`: inline `<SaveIndicator>` entfernen

## Risiken

- TripHeader und CompareEditor müssen den inline-SaveIndicator entfernen — leere `saveController`-Prop bleibt optional für Backward-Compat
- Das Overlay muss als Svelte-Komponente an der richtigen Stelle im DOM stehen (body-level oder per Svelte portal), damit `position: fixed` korrekt funktioniert — prüfen ob Eltern-Transform/Contain das verhindert
- Opacity-Transition bei idle: muss barrierefrei bleiben (nicht unter ~0.5 Opacity, kein `display: none`)
