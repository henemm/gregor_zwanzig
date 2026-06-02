# Context: Wegpunkt-Editor vollständiger Umbau (Handoff)

## Request Summary
Implementierung des Claude Design Handoffs für den Wegpunkt-Editor im Tab "Etappen & Wegpunkte". Desktop ist zu ~90% fertig; die fehlenden Teile sind primär die Mobile-Ansicht (Vollbild-Karte + MapControl-Cluster + ProfileSheetEmbedded) und kleine Desktop-Label-Fixes.

## Design-Referenzen
| Datei | Inhalt |
|-------|--------|
| `docs/design-requests/Gregor 20 - Wegpunkt-Editor im Etappen-Tab.html` | Primäres Handoff-HTML |
| `docs/design-requests/screen-waypoint-editor.jsx` | Desktop JSX-Spec |
| `docs/design-requests/screen-waypoint-editor-mobile.jsx` | Mobile JSX-Spec |
| `docs/design-requests/issue_503_ANTWORT.md` | AC + Implementierungsplan von Claude Design |

## Status: Was bereits existiert (NICHT neu bauen)

| Komponente | Datei | Status |
|-----------|-------|--------|
| `EtappenStrip` | `waypoints/EtappenStrip.svelte` | ✅ 100% — DnD + Pause-Insert |
| `StageCard` | `waypoints/StageCard.svelte` | ✅ 100% |
| `MapCanvas` | `waypoints/MapCanvas.svelte` | ✅ 100% — Leaflet/OpenTopoMap, 440px |
| `ProfileEditor` | `waypoints/ProfileEditor.svelte` | ✅ 95% — SVG, klickbar |
| `WaypointCard` | `waypoints/WaypointCard.svelte` | ✅ 100% — Redesign #522 |
| `PauseStageView` | `waypoints/PauseStageView.svelte` | ✅ 100% |
| `StageDateField` | `edit/StageDateField.svelte` | ✅ 100% |
| `EditStagesPanelNew` | `edit/EditStagesPanelNew.svelte` | ✅ 85% — Desktop fertig |
| `TripEditView` | `edit/TripEditView.svelte` | ✅ 100% — Tab-Label korrekt |
| `Sheet` (Bottom-Sheet) | `mobile/Sheet.svelte` | ✅ 100% — snap: full/half/peek |
| `MTab` | `mobile/MTab.svelte` | ✅ 100% |

## Was noch gebaut werden muss

### Desktop-Fixes (klein, <1h)
1. **Stage-Code-Label** in `EditStagesPanelNew`: Eyebrow zeigt `stage.name`, Design fordert `Etappe · {stage.code}`
2. **Beschreibungstext** "Wegpunkte sind Wetterscheiden…" als Sidebar-Hinweis
3. **StageCascadeNotice** aus `.cascade-prompt`-Inline-CSS als eigene Komponente extrahieren

### Mobile (neu, ~4-6h)
4. **`MapControl.svelte`** — Neu (AP-012-Ausnahme, dokumentiert)
   - 3 Buttons vertikal: `add-waypoint` / `map-style` / `search`
   - Position: `top: 12px; right: 12px`
   - 44×44px, `--g-card` Hintergrund, `--g-rule` Border, `--g-shadow-2`
   - Icons 20px, `--g-ink` Farbe — KEIN Akzent
5. **`ProfileSheetEmbedded.svelte`** — Neu
   - Nutzt: `Sheet.svelte` (bestehend)
   - Snaps: peek 92px / half 320px / full 540px
   - Enthält: Drag-Handle + Eyebrow + `EditorProfileSVG` (343×70px) + WaypointCard-Liste
6. **`StageSelectSheet.svelte`** — Neu
   - Modal-Sheet mit Etappen-Auswahl (wird bei Mobile-Stage-Switcher-Click geöffnet)
7. **`EditorProfileSVG.svelte`** — Neu (vereinfachtes Profil für Mobile-Sheet, 343×70px)
8. **Mobile-Branch in `EditStagesPanelNew`** (oder separate `MobileWaypointEditor.svelte`)
   - Unter `@media (max-width: 899px)`: Vollbild-Karte + MapControl + EtappenSwitcher-Pill + ProfileSheetEmbedded

## Verwandte offene Issues
| Issue | Titel | Überschneidung |
|-------|-------|---------------|
| #542 | MapCanvas: Wegpunkt per Klick auf Karte hinzufügen | Klick-Event auf Karte — Teil dieses Redesigns |
| #524 | WaypointSidebar: '+ auf Route' Button disabled | Button-Aktivierung — Teil dieses Redesigns |
| #500 | Etappen-Kacheln anklickbar machen | EtappenStrip-Navigation |

## Props-Referenz (wichtigste Komponenten)

```typescript
// MapCanvas
{ stage: Stage, activeWaypointId: string|null, onWaypointActivate: (id: string) => void }

// ProfileEditor
{ stage: Stage, activeWaypointId: string|null, onWaypointActivate: (id) => void, onProfileAdd?: (fraction: 0..1) => void }

// EtappenStrip
{ stages: Stage[], activeStageId: string, onStagesReorder, onStageActivate, onPauseInsert? }

// WaypointCard
{ waypoint: Waypoint, index: number, active?: boolean, arrival?: string|null, onActivate, onRename, onDelete }

// Sheet (Mobile)
{ open?: boolean, snap?: 'full'|'half'|'peek', title?, eyebrow?, onClose? }
```

## Architektur-Entscheidung (Claude Design, issue_503_ANTWORT)
- Desktop und Mobile teilen NICHT dieselbe Komponente
- Desktop: Grid-Layout `1fr / 360px` (nebeneinander)
- Mobile: Vollbild-Karte + überlagerndes Bottom-Sheet
- `EditStagesPanelNew` bleibt **Desktop-only**
- Mobile: Neuer Branch (responsive CSS oder eigenständige Mobile-Komponente)
- **Kein FAB** — MapControl ist die AP-012-Ausnahme (neutral, oben, card-farbig)
- **Keine Lat/Lon-Inputs** — nur Karte-Click + Profil-Click

## Risiken
- Leaflet auf Mobile: `height: 100vh` im Tab-Kontext kann problematisch sein (TripEditView hat eigene Höhe)
- Sheet-Snap-Logik: `Sheet.svelte` hat `full/half/peek` als String-Enum, Design fordert px-Werte (92/320/540) → Mapping nötig
- Issue #542 + #524 haben Überschneidung — Commits müssen sauber voneinander getrennt sein
