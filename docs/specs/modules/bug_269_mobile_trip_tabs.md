---
entity_id: bug_269_mobile_trip_tabs
type: bugfix
created: 2026-05-20
updated: 2026-05-20
status: completed
version: "1.0"
tags: [bugfix, mobile, tabs, svelte, frontend, pill-scroller, issue-269]
---

<!-- Issue #269 — Bug: Trip-Detail-Tabs überläuft und clippt auf Mobile -->

# Issue #269 — Bug-Fix: Mobile Trip-Detail-Tabs als Pill-Scroller

## Approval

- [x] Approved (2026-05-20)

## Zweck

Auf Viewports < 900 px (z.B. iPhone 375 × 667 px) werden die 6 Tabs in der Trip-Detail-Ansicht abgeschnitten — der Tab-Label „Etappen & Wegpunkte" bricht auf 2 Zeilen um, die rechten Tabs „Alerts" und „Vorschau" sind nicht erreichbar. Ursache: `.trip-tabs-list` hat kein horizontales Scrolling und kein `white-space: nowrap`.

Der Fix aktiviert auf Mobile (< 900 px) einen Pill-Scroller: alle Tabs bleiben einzeilig, die Liste scrollt horizontal, der aktive Tab wird als gefülltes Pill mit `--g-accent` dargestellt. Desktop (≥ 900 px) bleibt unverändert.

## Quelle / Source

**Geänderte Datei:**
- `frontend/src/lib/components/trip-detail/TripTabs.svelte` — `<style>`-Block wird um einen `@media (max-width: 899px)`-Block ergänzt

**NICHT ändern:**
- Kein Go-API-Code, kein Python-Backend-Code
- Keine anderen Svelte-Komponenten
- Desktop-Styles (`.trip-tabs-list`, `.trip-tab-trigger`, `[data-state='active']`) bleiben unverändert

> **Schicht-Hinweis:** Ausschließlich Frontend-Layer (`frontend/src/`). Reine CSS-Änderung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Svelte-Komponente | Einzige betroffene Datei; enthält `:global(.trip-tabs-list)` und `:global(.trip-tab-trigger)` |
| `frontend/src/app.css` | CSS | Definiert `@custom-variant mobile { @media (max-width: 899px) }` — Breakpoint-Referenz; `--g-accent: #c45a2a` und `--g-radius-pill: 99rem` als Token |
| `bits-ui` `Tabs`-Primitive | Dependency | Rendert `role="tablist"`; CSS-Klassen werden per `:global()` gesetzt. `data-state='active'` ist der aktive-Tab-Selektor |

## Implementation Details

Im `<style>`-Block von `TripTabs.svelte` wird am Ende (vor `</style>`) folgender Block eingefügt:

```css
@media (max-width: 899px) {
  /* Scrollbares Tab-Band */
  :global(.trip-tabs-list) {
    overflow-x: auto;
    white-space: nowrap;
    scrollbar-width: none;          /* Firefox */
    -ms-overflow-style: none;       /* IE/Edge legacy */
    scroll-snap-type: x mandatory;
  }
  :global(.trip-tabs-list)::-webkit-scrollbar {
    display: none;                  /* Chrome/Safari/WebKit */
  }

  /* Pill-Trigger: einzeilig, nicht schrumpfbar */
  :global(.trip-tab-trigger) {
    white-space: nowrap;
    flex-shrink: 0;
    scroll-snap-align: start;
    border-bottom: none;            /* Desktop-Underline deaktivieren */
    border-radius: var(--g-radius-pill, 99rem);
    padding: 0.375rem 0.875rem;
  }

  /* Aktiver Pill: gefüllt mit Akzentfarbe */
  :global(.trip-tab-trigger[data-state='active']) {
    background: var(--g-accent);
    color: var(--g-paper, #f6f4ee);
    border-bottom-color: transparent;
  }
}
```

**Klassennamen-Sicherheit:** `trip-tabs-list`, `trip-tab-trigger` und `trip-tab-badge` werden ausschließlich in `TripTabs.svelte` vergeben — keine Kollisionsgefahr durch `:global()`.

**Scrollbar-Hiding:** Dreifach abgedeckt (Firefox, IE/Edge, WebKit) ohne Deaktivierung der Scroll-Funktion.

### LoC-Budget

| Datei | Δ LoC |
|-------|--------|
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | +22 |
| **Gesamt** | **+22 (< 250 LoC-Limit)** |

## Expected Behavior

- **Input:** Viewport-Breite < 900 px (mobiles Gerät oder schmales Browser-Fenster)
- **Output:**
  - Tab-Band scrollt horizontal; alle 6 Tabs erreichbar
  - Tab-Labels brechen nicht um (einzeilig durch `white-space: nowrap`)
  - Aktiver Tab: gefülltes Burnt-Orange Pill (`--g-accent`)
  - Inaktive Tabs: transparenter Hintergrund, normaler Ink
  - Scrollbar unsichtbar (Scrollfunktion aktiv)
  - `scroll-snap` verbessert Touch-Scrolling auf exakt einen Tab
- **Desktop (≥ 900 px):** Unverändert — orangene Underline, keine Pill-Optik
- **Side effects:** Keine — reine CSS-Ergänzung ohne Logik-Änderung

## Acceptance Criteria

**AC-1:** Given ein 375 × 667 px Viewport (Mobile), When die Trip-Detail-Seite geladen wird, Then scrollt die Tab-Leiste horizontal und alle 6 Tabs sind per Scroll erreichbar (kein Clipping)

**AC-2:** Given ein 375 × 667 px Viewport (Mobile), When kein Tab aktiv ist außer dem ersten, Then sind alle Tab-Labels einzeilig (kein Zeilenumbruch bei „Etappen & Wegpunkte")

**AC-3:** Given ein 375 × 667 px Viewport (Mobile), When der aktive Tab gewechselt wird, Then ist der aktive Tab als gefülltes Pill mit `--g-accent`-Hintergrund und hellem Text sichtbar

**AC-4:** Given ein Desktop-Viewport (≥ 900 px), When die Trip-Detail-Seite angezeigt wird, Then zeigt der aktive Tab die orangene Underline (`border-bottom-color: var(--g-accent)`) — identisch zum Ist-Zustand

## Known Limitations

- `scroll-snap-type: x mandatory` auf Touch-Geräten kann aggressiv wirken (Snap auf Tab-Grenzen). Falls in Praxis störend: auf `x proximity` abmildern (kein Spec-Change nötig).
- Der bestehende E2E-Test `trip-detail-tabs.spec.ts` AC-5 (prüft `borderBottomColor` auf aktiven Tab) läuft im Default-Desktop-Viewport (1280 × 720) und schlägt daher nicht fehl — Desktop-Underline bleibt.

## Changelog

- 2026-05-20: Initial spec created
