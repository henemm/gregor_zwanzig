# Spec: Wegpunkt-Editor Mobile-Ansicht + MapCanvas-Klick

**Workflow:** wegpunkt-editor-handoff  
**Status:** draft  
**Datum:** 2026-06-02  
**Design-Referenz:** `docs/design-requests/Gregor 20 - Wegpunkt-Editor im Etappen-Tab.html`

---

## Hintergrund

Der Wegpunkt-Editor (Tab „Etappen & Wegpunkte" in `TripEditView`) ist auf dem Desktop vollständig implementiert. Die Mobile-Ansicht fehlt komplett: Statt Vollbild-Karte mit ausklappbarem Panel erscheint das Desktop-Grid auf kleinen Bildschirmen. Zusätzlich fehlt die Möglichkeit, Wegpunkte direkt per Klick auf die Karte zu setzen.

---

## Scope

**In Scope:**

- `MapCanvas.svelte`: optionaler `onMapClick`-Handler (Prerequisite für Mobile)
- `MapControl.svelte`: neuer neutraler Karten-Werkzeug-Cluster (AP-012-Ausnahme)
- `EditorProfileSVG.svelte`: vereinfachtes Höhenprofil 343×70px für Mobile
- `ProfileSheetEmbedded.svelte`: Bottom-Sheet mit Profil + Wegpunktliste
- `StageSelectSheet.svelte`: Modal-Sheet zur Etappen-Auswahl auf Mobile
- `EditStagesPanelNew.svelte`: Mobile-Branch `@media (max-width: 899px)`

**Out of Scope:**

- Geometrisches Snap-to-Route (Klick-Wegpunkt ans Segment anpassen) — Folge-Issue
- Drag-to-Move von Wegpunkten auf der Karte
- Tile-Caching / Leaflet-Backend
- Desktop-Änderungen (bereits vollständig)

---

## Acceptance Criteria

**AC-1:** Given `MapCanvas.svelte`, When ein optionaler Prop `onMapClick?: (lat: number, lon: number) => void` übergeben wird und der User auf die Karte klickt, Then wird `onMapClick` mit den Koordinaten des Klick-Punktes aufgerufen.

**AC-2:** Given `MapControl.svelte`, When es in einem Karten-Container gerendert wird, Then zeigt es drei vertikal gestapelte Buttons (44×44px, `--g-card` Hintergrund, `--g-rule` Border, `--g-shadow-2`) mit Icons `plus` / `map` / `search` in `--g-ink` Farbe, positioniert `top: 12px; right: 12px`, ohne Akzent-Farbe.

**AC-3:** Given `EditStagesPanelNew.svelte` bei Viewport ≤ 899px, When eine Etappe mit Wegpunkten aktiv ist, Then ist das Desktop-Grid ausgeblendet und stattdessen erscheint: Vollbild-MapCanvas (100% Breite, `calc(100dvh - 56px)` Höhe), MapControl oben rechts, EtappenSwitcher-Pill oben links.

**AC-4:** Given `StageSelectSheet.svelte`, When der User auf die EtappenSwitcher-Pill klickt, Then öffnet sich ein Bottom-Sheet (snap: half) mit der scrollbaren Etappen-Liste; Klick auf eine Etappe wählt sie aus und schließt das Sheet.

**AC-5:** Given `ProfileSheetEmbedded.svelte` bei Viewport ≤ 899px, When die Mobile-Ansicht aktiv ist, Then erscheint ein Bottom-Sheet mit drei Snap-Positionen (peek ≈ 92px / half ≈ 320px / full ≈ 540px), das `EditorProfileSVG` (343×70px) und die scrollbare `WaypointCard`-Liste enthält.

**AC-6:** Given `EditorProfileSVG.svelte`, When ein `stage`-Objekt übergeben wird, Then rendert es eine SVG (343×70px) mit Polyline, Wegpunkt-Pins und einer klickbaren Fläche, die `onProfileAdd(fraction)` aufruft — identische Signatur wie `ProfileEditor.svelte`.

**AC-7:** Given `EditStagesPanelNew.svelte` bei Viewport ≤ 899px mit einer Pausentag-Etappe, When die Etappe aktiv ist, Then ist MapControl nicht sichtbar, und `PauseStageView` erscheint statt der Karte.

**AC-8:** Given die Gesamtimplementierung, When `MapCanvas.svelte` das `onMapClick`-Event auslöst, Then fügt `EditStagesPanelNew` den neuen Wegpunkt am Ende der aktuellen Wegpunktliste ein (MVP: kein geometrisches Snap-to-Route).

---

## Technische Entscheidungen

### Sheet-Höhen (px vs. %)
`Sheet.svelte` arbeitet mit %-Werten (`full: 84%`, `half: 55%`, `peek: 32%`). `ProfileSheetEmbedded` umschließt `Sheet` in einem Container mit `position: relative; height: calc(100dvh - 56px)`. Die %-Werte von Sheet werden relativ zu diesem Container berechnet und ergeben so annähernd die Design-Zielwerte (peek≈92px, half≈320px). `Sheet.svelte` bleibt unverändert.

### MapCanvas-Größenänderung bei Sheet-Snap
Nach jedem Sheet-Snap-Wechsel muss Leaflet `map.invalidateSize()` aufgerufen werden. `MapCanvas` bekommt ein optionales `sizeKey`-Prop; sobald es sich ändert, triggert ein `$effect` die Invalidierung. (+3 LOC)

### Waypoint-Einfügelogik bei Karten-Klick
MVP: neuer Wegpunkt wird am Ende der Wegpunktliste der aktiven Etappe eingefügt. Koordinaten kommen aus dem Leaflet-Klick-Event (lat/lon direkt). Elevation = 0 als Fallback (identisch zu `interpolateWaypoint` bei n=0).

### Dateiablage neue Komponenten
- `MapControl.svelte` → `frontend/src/lib/components/edit/`
- `ProfileSheetEmbedded.svelte` → `frontend/src/lib/components/edit/`
- `StageSelectSheet.svelte` → `frontend/src/lib/components/edit/`
- `EditorProfileSVG.svelte` → `frontend/src/lib/components/trip-detail/waypoints/`

---

## Betroffene Dateien

| Datei | Änderung | ~LoC |
|-------|----------|------|
| `waypoints/MapCanvas.svelte` | `onMapClick` + `sizeKey` Prop | +18 |
| `edit/EditStagesPanelNew.svelte` | Mobile-Branch + Handler | +85 |
| `edit/MapControl.svelte` | NEU | +55 |
| `edit/ProfileSheetEmbedded.svelte` | NEU | +90 |
| `edit/StageSelectSheet.svelte` | NEU | +70 |
| `waypoints/EditorProfileSVG.svelte` | NEU | +60 |
| Tests: `issue_542_mobile_editor.test.ts` | NEU | +100 |
| **Gesamt** | | **~478** |

**LoC-Override erforderlich:** 500

---

## Risiken

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Sheet %-Höhen stimmen nicht genau (dvh vs. vh, Adressleiste) | Mittel | `dvh` statt `vh`; Sheet-Container-Höhe explizit setzen |
| Leaflet rendert falsch nach Sheet-Resize | Mittel | `sizeKey`-Prop + `map.invalidateSize()` im `$effect` |
| DnD-Strip auf Touch problematisch | Niedrig | EtappenStrip auf Mobile `display: none`; StageSelectSheet ersetzt Navigation |
