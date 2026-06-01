# Design-Request: Wegpunkt-Editor — Wo gehört die Karte hin?

**Status:** new  
**Priorität:** Hoch — Issue #503 teilweise offen, Design-ACs noch nicht user-sichtbar  
**Issue:** #503 / #506

## Hintergrund

Der Wegpunkt-Editor (`/trips/[id]/edit`) wurde in Issue #494 auf ein Tab-Design umgestellt.
Die aktive Struktur ist jetzt:

```
TripEditView.svelte
  Tab "Route"       → EditRouteSection.svelte
  Tab "Etappen"     → EditStagesPanelNew.svelte  (Höhenprofil + Wegpunkt-Liste, KEINE Karte)
  Tab "Wetter"      → WeatherSummaryCard.svelte
  Tab "Reports"     → EditReportConfigSection.svelte
  Tab "Alarmregeln" → AlertRulesEditor
```

`EditStagesPanelNew` hat bewusst **keine Leaflet-Karte** (Issue #296 — visuelle
Wegpunkt-Bearbeitung nur via Höhenprofil). Die Karte war früher in `WaypointEditorPage`
(jetzt toter Code).

## Die Design-Frage

Die Claude-Design-Specs für Desktop und Mobile zeigen den Wegpunkt-Editor **mit Karte**:

- Desktop: Grid 1fr / 360px — links Karte (OpenTopoMap, 100% Breite, 440px Höhe) +
  Höhenprofil; rechts Wegpunkt-Sidebar
- Mobile: Karte fullscreen, Bottom-Sheet mit Wegpunktliste, 3 FAB-Buttons

Diese Specs wurden gegen den alten `WaypointEditorPage` entwickelt, bevor #494 das
Tab-Design einführte.

**Jetzt gibt es drei mögliche Wege:**

### Option A — Karte weglassen
`EditStagesPanelNew` bleibt wie es ist (Höhenprofil + Wegpunkt-Liste ohne Karte).
`WaypointEditorPage` wird gelöscht. Design-Spec wird auf den Ist-Zustand angepasst.

### Option B — Karte in Tab „Etappen"
`EditStagesPanelNew` bekommt zusätzlich den MapCanvas (Leaflet OpenTopoMap).
Das Grid wäre dann: links Karte + Höhenprofil, rechts Wegpunkt-Liste (wie früher).
Issue #296 wird damit revidiert.

### Option C — Eigener Tab „Wegpunkte"
Ein neuer 6. Tab „Wegpunkte" in `TripEditView`. Darin läuft `WaypointEditorPage`
(bereits implementiert mit Karte + Höhenprofil + Sidebar + Mobile Bottom-Sheet).
Tab „Etappen" bleibt unverändert (nur Höhenprofil).

## Kontext: Was ist bereits implementiert

`WaypointEditorPage.svelte` enthält einen **vollständigen Desktop- und Mobile-Editor**
gemäß der Design-Spec (Commit `3ce6419`):

Desktop:
- Breadcrumb-Header (Tripname / Etappencode / Wegpunkte) + KI-Vorschläge + Speichern
- EtappenStrip mit Eyebrow + GPX/Pause-Zähler + „+ Etappe"-Button
- Karte in Card (Eyebrow „Karte · OpenTopoMap (OSM + SRTM)" + Pill „Topo"), 100% × 440px
- Höhenprofil in Card (Eyebrow + km/ascent/descent-Stats)
- Wegpunkt-Sidebar Card (360px, Eyebrow + „+ auf Route"-Button + KI-Hinweis-Footer)

Mobile:
- TopAppBar mit Tripname als Eyebrow über „Wegpunkt-Editor"
- Floating Profil-Strip mit Etappenname + Stats
- 3 FAB-Buttons (Plus, Map, Search)
- Bottom-Sheet mit 3 Snap-Positionen (peek 92px / half 320px / full 540px)

Diese Komponente ist fertig — sie wird nur aktuell nicht gerendert.

## Fragen an Claude Design

1. **Architektur:** Welche Option (A / B / C) ist aus Design-Sicht die richtige?
   Soll die Karte Teil des Etappen-Tabs sein oder einen eigenen Tab bekommen?

2. **Falls Option C:** Wie soll der neue Tab heißen und wo in der Tab-Reihenfolge
   soll er erscheinen? (Vorschlag: zwischen „Etappen" und „Wetter")

3. **Falls Option B:** Wie soll das Layout von `EditStagesPanelNew` mit Karte aussehen?
   Gleich wie der frühere Wegpunkt-Editor (Grid 1fr / 360px)? Oder anders?

4. **Tab-Streifen:** Braucht der neue/erweiterte Editor einen eigenen `EtappenStrip`
   (horizontale Etappen-Navigation oben), oder reicht die Tab-Navigation von `TripEditView`?

## Referenz-Screens (Ist)

Live: `https://gregor20.henemm.com/trips/gr221-mallorca/edit`  
Tab „Etappen" zeigt aktuell: EtappenStrip + Höhenprofil + Wegpunktliste (ohne Karte)

## Design-System

Token-Referenz: `docs/design-system/TOKENS.md`  
Atom-Referenz: `docs/design-system/COMPONENTS.md`  
Screens-Referenz: `docs/design-system/SCREENS.json`

Bestehende Desktop-Spec: `claude-code-handoff/screenshots/soll-flow2B-waypoint-editor-desktop.png` (falls vorhanden)  
Bestehende Mobile-Spec: `claude-code-handoff/screenshots/soll-flow2B-waypoint-editor-mobile.png` (falls vorhanden)

## Erwarteter Output

- Klare Empfehlung: Option A / B / C (mit Begründung)
- Bei B oder C: Mockup des veränderten Editors (Desktop 1440px + Mobile 390px)
- Tab-Label und Position des neuen/erweiterten Editors
- Ggf. Anpassung der EtappenStrip-Positionierung
