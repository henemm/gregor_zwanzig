# Spec: Issue #503 — Wegpunkt-Editor vollständiger Fix

## Überblick

**Issue:** #503 — Zwei verschiedene Edit-Seiten + Kartenbreite falsch  
**Scope:** Navigation-Fix + vollständige Design-Angleichung des WaypointEditors (Desktop + Mobile) an das Claude-Design-Spec (`screen-waypoint-editor.jsx`, `screen-waypoint-editor-mobile.jsx`)  
**Nicht in scope:** StageDateField + StageCascadeNotice (Issue #498)

---

## Acceptance Criteria

**AC-1:** Given der User öffnet einen Trip (`/trips/[id]`), When er auf „Etappen öffnen" klickt, Then landet er auf `/trips/[id]/edit` — nicht mehr auf `#stages`.

**AC-2:** Given der User ist auf `/trips/[id]` im `#stages`-Tab, When er ihn öffnet, Then sieht er KEINE editierbare WaypointsPanel-Oberfläche — stattdessen wird er zu `/trips/[id]/edit` weitergeleitet oder der Tab zeigt eine Leseanzeige.

**AC-3:** Given der User öffnet `/trips/[id]/edit` auf Desktop (≥900px), When er die Seite lädt, Then sieht er einen Breadcrumb-Header (`Tripname / Etappe-Code / Wegpunkte`) mit Save-Button rechts.

**AC-4:** Given Desktop-Editor, When eine normale Etappe aktiv ist, Then ist die Leaflet-Karte in eine Card eingebettet (border, shadow) mit Header-Zeile: Eyebrow „Karte · OpenTopoMap (OSM + SRTM)" + Pill „Topo" oben.

**AC-5:** Given Desktop-Editor, When eine normale Etappe aktiv ist, Then füllt die Karte die volle Breite ihrer Card (100%, kein hartes 400px), Höhe 440px.

**AC-6:** Given Desktop-Editor, When eine normale Etappe aktiv ist, Then ist das Höhenprofil in eine Card eingebettet mit Header: Eyebrow „Höhenprofil · synchron mit Karte" + rechts mono km/ascent/descent-Stats.

**AC-7:** Given Desktop-Editor, When eine normale Etappe aktiv ist, Then ist die Wegpunkt-Sidebar eine Card mit Header (Eyebrow „Wegpunkte" + `N insgesamt` + `[+ auf Route]`-Button) und einem Hinweis-Footer über KI-Vorschläge.

**AC-8:** Given Desktop-Editor, When der EtappenStrip sichtbar ist, Then hat er einen semi-transparenten Hintergrund (`rgba(255,255,255,0.4)` + blur), eine Eyebrow-Zeile mit Text „Etappen" sowie einen `[+ Etappe]`-Button am Ende.

**AC-9:** Given Mobile-Editor (≤899px), When der User die Seite öffnet, Then zeigt die TopAppBar den Trip-Namen als Eyebrow über dem Titel „Wegpunkt-Editor".

**AC-10:** Given Mobile-Editor, When die Karte sichtbar ist, Then gibt es 3 FAB-Buttons rechts (Plus, Map, Search) und einen Profil-Strip floating links oben mit Etappenname + km/ascent-Stats.

**AC-11:** Given Mobile-Editor, When der User das Bottom-Sheet hochzieht, Then gibt es drei Snap-Positionen: peek (92px), half (320px), full (540px) — animiert.

**AC-12:** Given Mobile-Editor Bottom-Sheet bei snap ≠ peek, When ein KI-Vorschlag aktiv ist, Then erscheinen `[KI-Vorschlag übernehmen]` (accent, full-width) und `[Verwerfen]` (ghost) als prominente Zeile oben im Sheet vor der Wegpunktliste.

---

## Technische Analyse

### Betroffene Dateien

| Datei | Art der Änderung |
|-------|-----------------|
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | #stages-Tab: WaypointsPanel raus, redirect zu /edit |
| `frontend/src/lib/components/trip-detail/TripOverview.svelte` | actionHref="#stages" → actionHref="/trips/{trip.id}/edit" (benötigt trip-Prop) |
| `frontend/src/lib/components/trip-detail/TripOverview.issue487.test.ts` | Test anpassen: #stages → /edit |
| `frontend/src/lib/components/edit/WaypointEditorPage.svelte` | Alle Desktop- und Mobile-Design-Anpassungen |
| `frontend/src/lib/components/trip-detail/waypoints/MapCanvas.svelte` | width: 400px → width: 100%; height: 300px → height: 440px |
| `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte` | Hintergrund, Eyebrow, GPX/Pause-Zähler, PauseInsertGap, "+ Etappe"-Button |

### TripOverview — trip-Prop

`TripOverview.svelte` erhält `trip` bereits als Prop (für `stats.stages`, `alertItems`, etc.). Der `actionHref` kann direkt auf `/trips/${trip.id}/edit` gesetzt werden — kein neues Prop nötig.

### #stages-Tab Fix

Einfachste Lösung: Der `#stages`-Tab in `TripTabs.svelte` zeigt statt `<WaypointsPanel>` einen Redirect-Hinweis mit Link zu `/trips/[id]/edit`. Dies ist konsistent mit dem Design (Trip-Detail = Leseansicht, /edit = Editor).

Alternativ: Tab-Klick auf „Etappen" navigiert direkt zu `/trips/${trip.id}/edit`. Empfehlung: **Redirect-Banner** im Tab-Content ist weniger invasiv und bewahrt die Tab-Navigation.

### MapCanvas

`MapCanvas.svelte:94` — `style="width:400px;height:300px;"` → `style="width:100%;height:440px;"`. Leaflet initialisiert sich in einem `$effect`, der nach dem Rendern läuft — 100%-Breite funktioniert, wenn der Container-Parent eine definierte Breite hat (`.wp-editor-left` im Grid ist `1fr`).

### WaypointEditorPage Desktop-Struktur (SOLL)

```
[Breadcrumb-Header: Tripname / Code / Wegpunkte | KI-Vorschläge | Speichern]
[EtappenStrip: rgba bg + blur, Eyebrow, Cards, PauseGaps, +Etappe]
[Stage-Header: Eyebrow + Titel 32px + Beschreibung | (StageDateField = #498)]
[Grid 1fr / 360px, gap 24px, padding 20px 40px]
  LEFT:
    [Card: Header "Karte · OpenTopoMap" + Pill "Topo"]
      [MapCanvas 100% × 440px]
    [Card: Header "Höhenprofil · synchron" + km-Stats]
      [ProfileEditor]
  RIGHT (360px):
    [Card: Eyebrow "Wegpunkte" + N insgesamt + [+ auf Route]]
      [WaypointCard list]
      [Hinweis-Footer: KI-Erklärung]
[Footer: Speichern | Abbrechen]
```

### WaypointEditorPage Mobile-Struktur (SOLL)

```
[TopAppBar: ← | Eyebrow: Tripname · N Etappen | Titel: Wegpunkt-Editor | ⋮]
[StageNavDropdown: Nr-Badge + Name + Chevron + Prev/Next]
[(StageDateField-Zeile = #498)]
[Karten-Bereich flex:1]
  [MapMock/Leaflet absolute inset:0]
  [FABs: + / map / search rechts oben, 44×44]
  [Profil-Strip: links oben float, Etappenname + Risk + Stats]
  [Bottom-Sheet: peek/half/full snap, animiert]
    [Grip]
    [Sheet-Header: Eyebrow + aktiver WP-Name + Stats + Collapse-Button]
    [ProfileEditor mini]
    [bei snap≠peek + KI aktiv: KI-Vorschlag-Buttons]
    [Wegpunktliste]
[Footer: Speichern | Abbrechen]
```

---

## Constraints

- **C1** Kein Breaking-Change am WaypointsPanel (bleibt in `trip-detail/waypoints/` für eventuelle spätere Wiederverwendung)
- **C2** StageDateField und StageCascadeNotice sind **out of scope** (Issue #498)
- **C3** Leaflet-Karte bleibt: echte OpenTopoMap (keine SVG-Attrappe)
- **C4** Die bestehenden `data-testid`s in WaypointEditorPage müssen erhalten bleiben
- **C5** Trip-Name für Breadcrumb kommt aus `trip.name`, Stage-Code aus `activeStage?.name`

---

## Out of Scope

- StageDateField + StageCascadeNotice → Issue #498
- TopoBg-Textur → kosmetisch, separates Issue
- StageCard-Größe (160→200px): nur marginale Anpassung, nach PO-Rückfrage
