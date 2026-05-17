# Context: Epic 5 — Wegpunkt-Editor (Issues #166–#172)

## Request Summary
Neuer Tab „Etappen & Wegpunkte" in der Trip-Detailansicht: visueller Editor mit Etappen-Strip oben, SVG-Karte links, Höhenprofil und Waypoint-Liste rechts. Keine rohen Lat/Lon-Felder.

## Issues in Scope
| Issue | Komponente | Beschreibung |
|-------|-----------|-------------|
| #166 | `EtappenStrip` | Horizontaler Strip, drag-to-reorder, Pause einfügen |
| #167 | `StageCard` | Kachel für GPX-Etappe (Sparkline, km, Aufstieg) + Pause-Etappe |
| #168 | `MapCanvas` | SVG-Pseudo-Topokarte, Route-Linie, WaypointPins, Zoom, Layer-Toggle |
| #169 | `WaypointPin` | SVG-Pin (Nummer, aktiv/inaktiv, vorgeschlagen=gestrichelt) |
| #170 | `ProfileEditor` | SVG-Höhenprofil mit Gridlines + klickbaren Pins, synchron mit Karte |
| #171 | `WaypointCard` | Listenitem rechts mit Aktionen (Bestätigen/Verwerfen/Umbenennen/Löschen) |
| #172 | `PauseStageView` | Pausentag-Ansicht: Standort-Info statt Karte |

## Einstiegspunkt
- Route: `/trips/[id]` → Tab `stages` in `TripTabs.svelte`
- Derzeit: Platzhalter `<p>Inhalt folgt mit Epic #137 (Wegpunkt-Editor)</p>`
- Tab-Label: „Etappen & Wegpunkte" (bereits definiert in TABS-Array)

## Related Files
| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Einstiegspunkt — tab `stages` befüllen |
| `frontend/src/lib/types.ts` | `Trip`, `Stage`, `Waypoint` — Datenmodell |
| `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte` | Ähnliches Layout (Etappen-Liste links, rechts Waypoint-UI) — Vorbild |
| `frontend/src/lib/components/trip-wizard/steps/ProfileChart.svelte` | Bestehender SVG-Höhenprofil-Chart — erweitern zu ProfileEditor |
| `frontend/src/lib/components/trip-wizard/steps/StageRow.svelte` | Referenz für Etappen-Kacheln mit Drag-Handle |
| `frontend/src/lib/components/trip-wizard/steps/WaypointRow.svelte` | Referenz für Waypoint-Listenitem (Bestätigen/Verwerfen) |
| `frontend/src/lib/components/ui/elev-sparkline/ElevSparkline.svelte` | Sparkline-SVG → in StageCard verwenden |
| `frontend/src/lib/components/ui/topo/TopoBg.svelte` | Topo-Hintergrundmuster → in MapCanvas verwenden |
| `frontend/src/lib/components/ui/btn/Btn.svelte` | Standard-Button für Aktionen |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | T01-Pill für Etappennummer |
| `frontend/src/lib/api.ts` | API-Calls für Trip-Updates (PATCH /trips/:id) |
| `docs/reference/design_system.md` | Tokens, Farben, Typografie |

## Existing Patterns
- **Etappen-Liste links / Aktions-UI rechts:** identisches Layout wie Step3Waypoints — `flex-row gap-6`, linke Spalte `w-48`, rechte Spalte `flex-1`
- **SVG-Profil:** ProfileChart.svelte — bewährt, Padding 8px, Polyline + Circles
- **Drag-Handle:** StageRow.svelte — `GripVertical`-Icon, `cursor-grab`, `aria-label="Etappe verschieben"`
- **Pause-Heuristik:** `isPauseStage()` in wizardHelpers — `waypoints.length === 0`
- **Factory-Pattern für Handler:** benannte Funktionen (kein inline `() =>`) — CLAUDE.md Safari-Konvention
- **Topo-Stil:** `TopoBg.svelte` für Hintergrundmuster; Route-Linie in `--g-accent` (Burnt Orange)
- **SVG-Pin-Stil:** vorgeschlagen = `stroke="--g-warning"`, dasharray, weiß; bestätigt = `fill="--g-ink-strong"`

## Datenmodell (relevant)
```ts
interface Stage { id, name, date, waypoints: Waypoint[] }
interface Waypoint { id, name, lat, lon, elevation_m, suggested?: boolean }
// isPauseStage: waypoints.length === 0
```

## Abhängigkeiten
- **Upstream:** `Trip`-Objekt kommt von `+page.server.ts` (bereits vorhanden)
- **Downstream:** Änderungen an Waypoints → PATCH `/api/trips/:id` via `api.ts`
- **Kein Backend-Umbau nötig** — Trip-Datenmodell trägt `stages[].waypoints` bereits

## Keine bestehende Spec für Epic 5
Kein `docs/specs/modules/epic_137_*.md` vorhanden — Spec muss in Phase 3 neu erstellt werden.

## Drag & Drop — Technologie
SvelteKit-Frontend nutzt aktuell kein Drag-Library. Im Wizard (Step2) gibt es einen Drag-Handle, aber kein echtes DnD. Für den EtappenStrip (#166) muss eine Entscheidung getroffen werden: nativer HTML5 DnD (kein extra Package) oder `@dnd-kit` / `svelte-dnd-action`.

## Risiken
- **SVG-Karte (#168):** Pseudo-Topokarte aus SVG (keine echte Kartenlib) — Koordinaten müssen auf SVG-Viewport normiert werden (ähnlich ProfileChart)
- **Drag & Drop (#166):** Kein DnD-Framework bisher — Entscheidung in Phase 3
- **Synchronisation Karte ↔ Profil (#170):** Shared State für `activeWaypointId` nötig — in Editor-Level-State halten, nicht im globalen Store
- **API-Write-Back:** Waypoint-Änderungen (Löschen, Umbenennen) müssen persistiert werden; Wizard-Step3 persistiert nicht (nur lokaler State) — Wegpunkt-Editor muss PATCH aufrufen
