# Context: Issue #407 — Dedizierter Wegpunkt-Editor-Screen

## Request Summary

Die Route `/trips/[id]/edit` soll von einer generischen Akkordeon-Bearbeitungsmaske (Route / Etappen / Wetter / Alarmregeln / Reports) in einen **dedizierten Vollbild-Wegpunkt-Editor** umgebaut werden mit: SVG-Topo-Karte + Route-Overlay, interaktivem Höhenprofil, nummerierter Wegpunkt-Sidebar und KI-Vorschlag-Interface.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | Einstiegspunkt — minimal, lädt TripEditView |
| `frontend/src/routes/trips/[id]/edit/+page.server.ts` | Loader — lädt Trip via `/api/trips/{id}` |
| `frontend/src/lib/components/edit/TripEditView.svelte` | IST: Akkordeon-Wrapper (Route/Etappen/Wetter/Alarmregeln/Reports) |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Aktueller Editor im Etappen-Akkordeon (ProfileEditor + EtappenStrip + WaypointCard) |
| `frontend/src/lib/components/trip-detail/WaypointsPanel.svelte` | REFERENZ: State-Owner im Detail-View (Map+Profil+WaypointList) — fast identisch mit SOLL |
| `frontend/src/lib/components/trip-detail/waypoints/MapCanvas.svelte` | SVG-Pseudo-Topo-Karte mit Route-Overlay + WaypointPins (TopoBg) |
| `frontend/src/lib/components/trip-detail/waypoints/ProfileEditor.svelte` | Interaktives SVG-Höhenprofil, klickbare Pins, onProfileAdd |
| `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte` | Horizontaler DnD-Strip aus StageCards |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte` | Listenzeile: Name + Höhe + Ankunft + Confirm/Reject/Rename/Delete |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointPin.svelte` | Pin-SVG (suggested/bestätigt/aktiv) |
| `frontend/src/lib/components/trip-detail/waypoints/PauseStageView.svelte` | Pausentag-Ansicht |
| `frontend/src/lib/components/ui/topo/TopoBg.svelte` | Topo-Hintergrundmuster (SVG) |
| `frontend/src/lib/types.ts` | Waypoint, Stage Interfaces |
| `frontend/src/lib/utils/waypointEditor.ts` | stripSuggested, buildMapPositions, interpolateWaypoint |
| `frontend/src/lib/utils/naismith.ts` | computeArrivalTimes |
| `frontend/src/lib/api.ts` | API-Client (put/get) |
| `docs/specs/modules/trip_edit_view.md` | Aktuelle Spec (draft, Akkordeon-Layout) |
| `docs/specs/modules/issue_296_fe_profile_editor.md` | Vorgänger-Spec (draft, kein Approve) |
| `docs/specs/modules/epic_137_wegpunkt_editor.md` | Epic-137-Spec (MapCanvas + ProfileEditor + WaypointCard) |

## Existing Patterns

- **WaypointsPanel.svelte** (Detail-View) macht fast alles, was das SOLL zeigt: MapCanvas + ProfileEditor + WaypointCard + EtappenStrip + Speichern. Der neue Edit-Screen ist im Wesentlichen `WaypointsPanel` in einer eigenen Full-Page-Route.
- **Factory-Pattern** für Callbacks überall (Safari-Closure-Schutz — `function makeXHandler()`)
- **Kein direktes Edit auf die API** — lokaler State (`localStages`), dann expliziter Save-Button → `PUT /api/trips/{id}`
- **stripSuggested** vor dem Save (transiente `suggested`-Flags nicht persistieren)
- **computeArrivalTimes** für Naismith-Ankunftszeiten pro Wegpunkt

## SOLL vs. IST

### Desktop SOLL
- Horizontaler Etappen-Strip oben (StageCards, aktuell: aktiv = orange)
- Links: SVG-Topo-Karte (400×300px, TopoBg, Route-Polyline, nummerierte WaypointPins)
- Unten: Höhenprofil-Panel (ProfileEditor, klickbare Pins)
- Rechts: Sidebar „N Wegpunkte" mit nummerierten Einträgen (Name + km/ETA)

### Mobile SOLL
- Page-Title „Wegpunkt-Editor" + Back-Button
- **Etappen-Navigator: Dropdown + Prev/Next-Pfeile** (≠ EtappenStrip)
- Stage-Info-Card (Name + Schwierigkeits-Pill + Stats + Add/Map/Search-Buttons)
- Karte (Vollbreite, TopoBg)
- Bottom-Sheet (ziehbar): Höhenprofil + KI-Vorschlag-Bar + Wegpunkt-Liste

### KI-Vorschlag-Bar (neu)
- Erscheint, wenn aktive Stage hat `waypoints.some(w => w.suggested)`
- "✓ KI-Vorschlag übernehmen" (Primary-Button) + "Verwerfen" (Ghost-Button)
- Wirkt auf den ersten noch-vorgeschlagenen Wegpunkt der aktiven Etappe

## Dependencies

- **Upstream:** Go-API `GET /api/trips/{id}` (existiert), `PUT /api/trips/{id}` (existiert, Read-Modify-Write)
- **Downstream:** `/trips` (Trips-Liste), `/trips/[id]` (Detail-View) — keine Auswirkung auf diese

## Karten-Entscheidung (PO bestätigt 2026-05-27)

- **SVG-Pseudo-Karte (`MapCanvas.svelte`) in Issue #407** — PO hat bestätigt
- Echte OSM-Karte (Leaflet) als separates Folge-Issue anlegen
- Die alte #296-Entscheidung "keine Karte" bezog sich auf MapLibre (echte Tile-Karte, schwere Dep.) — nicht auf die SVG-Variante

## Scope-Entscheidung: Was wird aus Wetter/Alarmregeln/Reports?

Die aktuelle `TripEditView` hat 5 Akkordeon-Sektionen. Die neuen SOLL-Screenshots für den Edit-Screen zeigen nur den Wegpunkt-Editor (keine Wetter/Alarmregeln-Akkordeons).

Wetter, Alarmregeln und Reports sind in der Trip-Detail-Seite (`/trips/[id]`) als eigene Tabs erreichbar. Die Edit-Route kann daher **auf Wegpunkt-Bearbeitung fokussiert** werden — die anderen Konfigurationen bleiben in den Trip-Detail-Tabs.

## Existierende Specs

- `docs/specs/modules/trip_edit_view.md` — draft, beschreibt Akkordeon-Layout (wird durch #407 überstimmt)
- `docs/specs/modules/issue_296_fe_profile_editor.md` — draft (nie approved), beschreibt Profil-only (kein Approve → kein Blocking)
- `docs/specs/modules/epic_137_wegpunkt_editor.md` — approved & deployed, Basis-Komponenten

## Risks & Considerations

1. **Karten-Konflikt** (s.o.) — vor Spec-Approval klären
2. **Fehlende Mobile-Komponenten:** Etappen-Navigator (Dropdown + Prev/Next) und KI-Vorschlag-Bar existieren noch nicht als Atomic-Komponenten
3. **LoC-Budget:** Die Kombination aller Teile ist komplex — LoC-Limit ggf. erhöhen
4. **Bestehende Tests:** `issue_402.test.ts` unter `trips/[id]/` — prüfen ob Regression möglich
5. **Keine Backend-Änderungen nötig:** `PUT /api/trips/{id}` existiert und unterstützt Read-Modify-Write
