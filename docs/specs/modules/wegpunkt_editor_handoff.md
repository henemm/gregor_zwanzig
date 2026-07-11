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

**AC-3:** Given `EditStagesPanelNew.svelte` bei Viewport ≤ 899px, When eine Etappe mit Wegpunkten aktiv ist, Then ist das Desktop-Grid ausgeblendet und stattdessen erscheint: Vollbild-MapCanvas (100% Breite, `calc(100dvh - {gemessene Tab-Unterkante}px)` Höhe — dynamisch per `getBoundingClientRect()` gemessen, siehe Update unten), MapControl oben rechts, EtappenSwitcher-Pill oben links.
>
> **Update (Issue #963, 2026-07-11 — Map-First-Reorder):** Die ursprüngliche Annahme `calc(100dvh - 56px)` ging fälschlich davon aus, `.mobile-map-wrap` sitze direkt unter der 56px-TopAppBar. Tatsächlich lag davor variabler Chrome-Content (Breadcrumb, TripHeader, Tab-Leiste, EtappenStrip, Etappen-Header) — bei RED-Test-Messung lag die reale Oberkante bei y≈1453px (Viewport 390×844), die Steuerelemente (`stage-switcher-pill`, `add-waypoint`) lagen damit weit außerhalb des Viewports (Issue #963). Fix: `.mobile-editor` wird auf Mobil per CSS `order:-1` innerhalb des flex-col-Containers direkt unter die Tab-Leiste vorgezogen (vor EtappenStrip/Etappen-Header/Cascade-Strip); seine tatsächliche Oberkante wird per `getBoundingClientRect().top` bei Mount + `resize`/`orientationchange` gemessen (Bezugspunkt = Tab-Unterkante, nicht mehr ein hartcodierter 56px-Wert) und reaktiv als `calc(100dvh - {gemessener Wert}px)` gesetzt. Details: `docs/specs/modules/issue_963_mobile_editor_controls.md`.

**AC-4:** Given `StageSelectSheet.svelte`, When der User auf die EtappenSwitcher-Pill klickt, Then öffnet sich ein Bottom-Sheet (snap: half) mit der scrollbaren Etappen-Liste; Klick auf eine Etappe wählt sie aus und schließt das Sheet.

**AC-5:** Given `ProfileSheetEmbedded.svelte` bei Viewport ≤ 899px, When die Mobile-Ansicht aktiv ist, Then erscheint ein Bottom-Sheet mit vier Snap-Positionen (collapsed ≤64px feste Höhe / peek ≈ 92px / half ≈ 320px / full ≈ 540px), das `EditorProfileSVG` (343×70px) und die scrollbare `WaypointCard`-Liste enthält.

> **Update (Issue #1158, 2026-07-09):** `collapsed` wurde als vierte Snap-Stufe ergänzt, um die Schublade auf Mobile schließbar zu machen. Details: `docs/specs/modules/issue_1158_mobile_sheet_close.md`.

**AC-6:** Given `EditorProfileSVG.svelte`, When ein `stage`-Objekt übergeben wird, Then rendert es eine SVG (343×70px) mit Polyline, Wegpunkt-Pins und einer klickbaren Fläche, die `onProfileAdd(fraction)` aufruft — identische Signatur wie `ProfileEditor.svelte`.

**AC-7:** Given `EditStagesPanelNew.svelte` bei Viewport ≤ 899px mit einer Pausentag-Etappe, When die Etappe aktiv ist, Then ist MapControl nicht sichtbar, und `PauseStageView` erscheint statt der Karte.

**AC-8:** Given die Gesamtimplementierung, When `MapCanvas.svelte` das `onMapClick`-Event auslöst, Then fügt `EditStagesPanelNew` den neuen Wegpunkt am Ende der aktuellen Wegpunktliste ein (MVP: kein geometrisches Snap-to-Route).

---

## Technische Entscheidungen

### Sheet-Höhen (px vs. %)
`Sheet.svelte` arbeitet mit %-Werten (`full: 84%`, `half: 55%`, `peek: 32%`) sowie seit Issue #1158 einer festen Pixel-Höhe für `collapsed` (`56px`) — bewusst kein %-Wert, sonst wäre "eingeklappt" auf großen Displays immer noch zu hoch. `ProfileSheetEmbedded` umschließt `Sheet` in einem Container mit `position: relative`; die Höhe dieses Containers (`.mobile-editor`) wird seit Issue #963 (Map-First-Reorder) **dynamisch zur Laufzeit** gemessen statt hartcodiert `calc(100dvh - 56px)` gesetzt (s. AC-3-Update oben) — die %-Werte von Sheet werden relativ zu dieser echten, gemessenen Container-Höhe berechnet. Design-Zielwerte (peek≈92px, half≈320px) gingen von der vollen Viewport-Höhe als Näherung aus; nach dem Map-First-Reorder ist die reale Container-Höhe deutlich kleiner (Standard-Viewport 390×844: real gemessen ≈254px unclamped, da Höhenformel Chrome-Offset UND reservierte BottomNav-Zone abzieht, s. F004/Fix-Loop 3; Extremfälle wie schmales Querformat oder sehr kurzer Portrait-Viewport greifen auf den 200px-Mindesthöhen-Floor zurück, `MOBILE_EDITOR_MIN_HEIGHT_PX` in `EditStagesPanelNew.svelte`), statt fast voller `dvh` wie ursprünglich angenommen. Die Ziel-px-Werte (peek/half) sind daher nur noch grobe Richtwerte — maßgeblich sind die %-Anteile selbst. `Sheet.svelte` bleibt in seiner Grundstruktur unverändert (siehe `docs/specs/modules/issue_1158_mobile_sheet_close.md` für den Collapsed-Zusatz und die Anker-Korrektur `fixed`→`absolute`).

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
