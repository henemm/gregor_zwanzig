# Mobile-Audit — gregor_zwanzig Frontend
**Datum:** 2026-05-20  
**Branch:** mobile-audit/2026-05-20  
**Viewports:** 375×667 · 390×844 · 414×896 · 768×1024  
**Design-Referenz:** `docs/design/mobile/` (Handoff aus Claude Design, chat5 „Mobile-Erweiterung 375px")

---

## Issue-Übersicht

### Nach Priorität

| Priorität | Anzahl | Issues |
|-----------|--------|--------|
| critical  | 1      | #267   |
| high      | 3      | #268, #269, #270 |
| medium    | 3      | #271, #272, #273 |
| low       | 1      | #274   |
| **Gesamt** | **8** | |

### Nach Viewport-Relevanz

| Viewport | Betroffene Issues |
|----------|-------------------|
| 375×667 (iPhone SE) | alle 8 |
| 390×844 (iPhone 14) | alle 8 |
| 414×896 (iPhone 11 Pro Max) | alle 8 |
| 768×1024 (iPad mini) | #267, #269, #270, #272 |

---

## Top-5 Hotspot-Routes

| Rang | Route | Issues | Begründung |
|------|-------|--------|-----------|
| 1 | `/` + alle Auth-Screens | #267 | Navigation komplett ohne BottomNav |
| 2 | `/trips` | #267, #268 | Tabellen-Layout + keine BottomNav |
| 3 | `/trips/[id]` | #267, #269 | Tabs clippen + keine BottomNav |
| 4 | `/compare` | #267, #270 | Locations nicht erreichbar + keine BottomNav |
| 5 | `/trips/new` | #267, #271, #272 | Wizard + Stepper + Font-Size |

---

## Empfohlene Bearbeitungsreihenfolge

1. **#267 – BottomNav** (critical): Fundament für alle anderen Navigation-Issues. Ohne dieses fix ist jede Route betroffen. Implementierung: `TopAppBar.svelte` + `BottomNav.svelte` + `Drawer.svelte` + Layout-Breakpoint.

2. **#268 – Trips-Liste Card-Stack** (high): Hochfrequenz-Screen, Touch-Targets kritisch. Nach #267 angehen (BottomNav schafft den nötigen Platz unten).

3. **#269 – Trip-Detail-Tabs** (high): Quick-Win — nur CSS `overflow-x: auto` + `white-space: nowrap`. Kann parallel zu #267 gemacht werden.

4. **#270 – Compare Locations-Rail** (high): Größerer Aufwand (Bottom-Sheet + H-Scroll-Matrix). Nach #267.

5. **#272 – Input Font-Size** (medium): Quick-Win — eine globale CSS-Regel in `app.css`. Kann jederzeit, kein Abhängigkeit.

6. **#271 – Wizard Stepper** (medium): Nach #267, da Wizard auch BottomNav braucht.

7. **#273 – Trip-Edit Koordinaten** (medium): Unabhängig, nach den high-Prio-Issues.

8. **#274 – Safe-Area-Insets** (low): Beim Anlegen der BottomNav (#267) direkt mitberücksichtigen.

---

## Alle erstellten Issues

| # | Titel | Priorität |
|---|-------|-----------|
| [#267](https://github.com/henemm/gregor_zwanzig/issues/267) | Bug: App-Shell – Keine Bottom-Navigation auf Mobile | critical |
| [#268](https://github.com/henemm/gregor_zwanzig/issues/268) | Bug: Trips-Liste auf /trips ohne Mobile-Strategie | high |
| [#269](https://github.com/henemm/gregor_zwanzig/issues/269) | Bug: Trip-Detail-Tabs überläuft und clippt auf Mobile | high |
| [#270](https://github.com/henemm/gregor_zwanzig/issues/270) | Bug: Orts-Vergleich auf /compare ohne Locations-Rail auf Mobile | high |
| [#271](https://github.com/henemm/gregor_zwanzig/issues/271) | Bug: Trip-Wizard – Stepper und Labels klippen auf Mobile | medium |
| [#272](https://github.com/henemm/gregor_zwanzig/issues/272) | Bug: Eingabefelder – Font-Size < 16 px löst iOS-Auto-Zoom aus | medium |
| [#273](https://github.com/henemm/gregor_zwanzig/issues/273) | Bug: Trip-Edit – Koordinaten-Eingabe ohne Mobile-Strategie | medium |
| [#274](https://github.com/henemm/gregor_zwanzig/issues/274) | Bug: Safe-Area-Insets fehlen in Sticky-Bereichen | low |

---

## Hinweise für Implementierung

- Design-Referenz: `docs/design/mobile/mobile-shell.jsx` → Pattern-Primitives für `TopAppBar`, `BottomNav`, `Drawer`, `BottomSheet`
- Breakpoint: `≤ 899 px` = Mobile, `≥ 900 px` = Desktop (lt. `docs/design/mobile/README.md` §H)
- Tokens: `docs/design/mobile/tokens-reference.css` (identisch mit `frontend/src/app.css`)
- Screenshots: `audit/screenshots/<viewport>/`
