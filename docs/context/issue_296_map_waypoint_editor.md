# Context: Issue #296 — Trip-Editor Wegpunkte visuell (Edit-View)

## ✅ PO-Entscheidung (2026-05-22)

1. **Keine Landkarte — nur Höhenprofil.** Weder MapLibre (echte Tile-Karte) noch die SVG-Pseudo-Topokarte aus epic_137. Zitat PO: *„Landkarten sind nicht das von Gregor Zwanzig. Es soll nur ein Höhenprofil geben."* → Die einzige visuelle Editier-Fläche für Wegpunkte ist das **Höhenprofil**. `MapCanvas.svelte` wird NICHT verwendet; Basis ist epic_137s `ProfileEditor.svelte`.
2. **Naismith „alles in einem Zug":** Backend-Berechnung der Ankunftszeiten (Go-Modell + Anbindung der Python-Naismith-Logik) UND die neue Oberfläche zusammen, nicht aufteilen.

**Konsequenz für den weiteren Verlauf:** Das SOLL-Mockup `soll-flow2B` (zeigt Karte + Profil) ist durch die PO-Entscheidung überstimmt — nur der Profil-Teil + Wegpunkt-Sidebar + EtappenStrip sind relevant. Offene Folge-Frage: Die bestehende Landkarte im **Detail-View** (epic_137 `MapCanvas`) widerspricht diesem Prinzip → separat mit PO klären, nicht in #296 eigenmächtig anfassen.

## Request Summary

Der Trip-Editor unter `/trips/[id]/edit` zeigt Wegpunkte als Stack von Lat/Lon/Höhen-Number-Inputs (`EditStagesSection.svelte`). Issue #296 will das durch einen **visuellen Karten-Editor** ersetzen: Etappen-Strip → Klick auf Etappe → Karte + Höhenprofil + Wegpunkt-Sidebar mit Naismith-Ankunftszeiten. Lat/Lon-Felder sollen vollständig verschwinden.

## ⚠️ Kritischer Befund: Vieles existiert bereits + Issue-Text widerspricht eigenem SOLL

### 1. Es gibt schon einen visuellen Wegpunkt-Editor (epic_137)

`epic_137_wegpunkt_editor` (Issues #166–#172, Spec: `docs/specs/modules/epic_137_wegpunkt_editor.md`, **aktiv & deployed**) hat im **Detail-View** (`/trips/[id]`, Tab „Etappen") bereits gebaut:
- `WaypointsPanel.svelte` (State-Owner, expliziter Save)
- `MapCanvas.svelte` — SVG-Pseudo-Topokarte mit Routenlinie, Zoom, Topo/Sat-Layer-Toggle
- `ProfileEditor.svelte` — SVG-Höhenprofil mit klickbaren Pins
- `EtappenStrip.svelte` — horizontaler Drag-Drop-Strip aus `StageCard`s
- `WaypointCard.svelte` — Wegpunkt-Liste mit Vorschlag-Bestätigen/Verwerfen
- `WaypointPin.svelte` (orange-gestrichelt = Vorschlag, solid = bestätigt/manuell)
- `PauseStageView.svelte` (Pausentag)
- `waypointEditor.ts` — `stripSuggested`, `buildMapPositions`, `boundingBox`

epic_137 listet in „Not In Scope" **explizit**: *„Echter Tile-Kartendienst (Leaflet, Mapbox) — Folge-Epic"*, *„Waypoint hinzufügen per Klick auf Karte — Folge-Issue"*. **#296 ist genau dieser geplante Folge-Schritt** — aber für eine andere Route (Edit statt Detail).

### 2. Das SOLL-Mockup des Issues zeigt SVG, nicht MapLibre

`claude-code-handoff/screenshots/soll-flow2B-map-editor.png` zeigt eine **SVG-Pseudo-Topokarte** (Höhenlinien-Stil, Topo/Satellit-Toggle, GPX-Spur, Manuell/Vorschlag-Pins, Legende) plus Höhenprofil unten und Wegpunkt-Sidebar mit Naismith-Zeiten. **Das ist optisch identisch mit dem, was epic_137s `MapCanvas` + `ProfileEditor` + `WaypointCard` bereits rendern.** Die im Issue-Text empfohlene `maplibre-gl`-Bibliothek (neue schwere Dependency, kein API-Key, OSM-Tiles) ist im SOLL **nicht abgebildet** — der Issue-Text widerspricht hier seinem eigenen Screenshot.

`soll-flow2A-trip-editor-overview.png` zeigt den **Edit-View** („TRIP BEARBEITEN", Tabs Route/Etappen/Wetter/Reports/Alarmregeln) mit Summary-Strip (GESAMT km/↑hm, ZEITRAUM) + EtappenStrip aus StageCards. Klick auf Etappe → flow2B.

### 3. Konsequenz

Eine wörtliche #296-Umsetzung (neuer MapLibre-Editor in der Edit-Route) würde einen **dritten** Wegpunkt-Editor neben epic_137 (Detail) und EditStagesSection (Edit) schaffen — Code-Duplikat + schwere neue Abhängigkeit, beides ohne SOLL-Deckung. Memory-Regeln „Code-Duplikate konsolidieren statt parallel fixen" und „Sorgsam bei Änderungen — vieles ist schon gut" greifen direkt.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/edit/EditStagesSection.svelte` | DIE zu ersetzende Komponente (Lat/Lon-Tabelle, `wp-lat`/`wp-lon`/`wp-ele` Inputs) |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Edit-View Container, bindet EditStagesSection in „Etappen"-Accordion ein |
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | Edit-Route, rendert TripEditView |
| `frontend/src/lib/components/trip-detail/WaypointsPanel.svelte` | **Bereits existierender visueller Editor** (epic_137) — Konsolidierungs-Kandidat |
| `frontend/src/lib/components/trip-detail/waypoints/*.svelte` | MapCanvas, ProfileEditor, EtappenStrip, StageCard, WaypointCard, WaypointPin, PauseStageView |
| `frontend/src/lib/utils/waypointEditor.ts` | Pure Functions (stripSuggested, buildMapPositions, boundingBox) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Detail-View „Etappen"-Tab → rendert `<WaypointsPanel>` (live) |
| `frontend/src/lib/types.ts` | `Waypoint` = {id,name,lat,lon,elevation_m,suggested?}; `Stage` = {id,name,date,waypoints,...} |
| `internal/model/trip.go` | Go-Backend-Modell: Waypoint{ID,Name,Lat,Lon,ElevationM,TimeWindow,Suggested}, Stage{...,StartTime} |
| `src/core/segment_builder.py` | **Naismith existiert hier** (`compute_hiking_time`, adapted Naismith's Rule) — aber in Python-Core, nicht im Go-Trip-API verdrahtet |

## Existing Patterns

- **Visueller Editor = SVG, nicht Tiles.** epic_137 bewusst SVG-Pseudokarte (`TopoBg` + normierte Koordinaten via Cos-Korrektur). Kein Kartendienst im Stack.
- **Explizites Save-Pattern.** WaypointsPanel: tiefer Klon (`structuredClone`), Mutation lokal, `stripSuggested()` vor `PUT /api/trips/:id`. TripEditView nutzt dasselbe Muster (JSON-Klon, PUT, dann goto).
- **suggested-Flag** ist transient im Frontend, wird vor PUT gestrippt. Marker: orange-gestrichelt (`--g-warning`) = Vorschlag, solid (`--g-ink-strong`) = bestätigt/manuell.
- **svelte-dnd-action** ist Dependency (EtappenStrip Drag-Drop).
- **Design-System:** `docs/design-system/` ist Autorität. Brand-Tokens (`--g-accent`, `--g-ink`, `--g-warning`, `--g-info`).

## Dependencies

- **Upstream (was wir nutzen):** `Trip`/`Stage`/`Waypoint` Typen, `api.put`, epic_137-Komponenten, `waypointEditor.ts`, Brand-CSS-Tokens, `svelte-dnd-action`, `@lucide/svelte`.
- **Downstream (was uns nutzt):** Trip-Persistenz `PUT /api/trips/:id` (Go), Save-Pipeline. E2E-Tests (siehe unten).
- **MapLibre:** aktuell **KEINE** Kartenbibliothek im `package.json`. Issue-Text empfiehlt `maplibre-gl` neu — nicht durch SOLL gedeckt.

## Existing Specs

- `docs/specs/modules/epic_137_wegpunkt_editor.md` — der bereits gebaute visuelle Editor (Detail-View)
- `docs/specs/modules/bug_283_editor_waypoint_table.md` — **kürzlich** poliertes Lat/Lon-Tabellen-Layout (genau das, was #296 löschen will)
- `docs/specs/modules/epic_136_trip_wizard.md` — Master-Spec (Trip/Stage/Waypoint, wizardHelpers, isPauseStage)
- `docs/specs/user_stories_foundation.md` — US-1 (Quelle des „Kein Lat/Lon"-Prinzips); benennt offene Naismith-Backend-Frage explizit

## Datenmodell-Lücke (Naismith / Ankunftszeiten)

Issue will `origin`, `confirmed`, `arrival_calculated`, `arrival_override` auf Waypoint. **Keines existiert** — weder in `types.ts` noch in `internal/model/trip.go`.
- Heute: nur `TimeWindow *string` (manuell) + `Stage.StartTime`. Kein berechnetes Ankunftsfeld.
- Naismith-Logik existiert in `src/core/segment_builder.py` (`compute_hiking_time`), ist aber **nicht** an die Go-Trip-API angebunden.
- Issue-Text sagt selbst: „Vor Implementierung muss ein separates Backend-Issue erstellt werden: Compute Naismith arrival times on save." → Naismith ist ein **eigenes Backend-Thema**, vom Frontend-Redesign trennbar (Frontend kann mit Platzhalter/`arrival_calculated` arbeiten bis Backend liefert).

## Betroffene E2E-Tests (würden bei Lat/Lon-Entfernung brechen)

- `frontend/e2e/bug-283-waypoint-table.spec.ts` — prüft Lat/Lon-Tabelle (`.g-th`, `wp-lat`…)
- `frontend/e2e/bug-273-coordinate-inputmode.spec.ts` — prüft `inputmode` der Koordinaten-Inputs
- `frontend/e2e/trip-edit.spec.ts` — Edit-View-Flow
- `frontend/e2e/trips.spec.ts` — referenziert Edit-Wegpunkte
- `frontend/e2e/waypoints-editor.spec.ts` — epic_137 Detail-View-Editor (Referenz für neue Tests)

→ Tests, die Lat/Lon-DOM-Inputs asserten, müssen auf State/Marker-basierte Assertions umgeschrieben werden.

## Risks & Considerations

1. **Architektur-Entscheidung nötig (PO):** Konsolidieren (Edit-View nutzt/teilt epic_137-Editor) vs. dritter Parallel-Editor. Empfehlung-Richtung: Konsolidierung, SVG beibehalten, MapLibre verwerfen.
2. **MapLibre = unnötige Schwergewichts-Dependency** laut SOLL — Risiko von Bundle-Größe, Tile-Hosting, Offline-Eignung ohne Mehrwert ggü. bestehender SVG-Lösung.
3. **Breaking-Change-Label:** Lat/Lon-Editor wurde gerade erst (bug-283/#283) poliert — vor Löschen klar bestätigen.
4. **Naismith-Backend** ist ein separater Workstream (Go-Modell-Felder + Verdrahtung der Python-Naismith-Logik); nicht im Frontend-Scope von #296 erzwingen.
5. **Datenverlust-Regel:** `types.ts`/`trip.go`-Änderungen sind schema-relevant → additiv (`omitempty`), Read-Modify-Write, Pre-Snapshot-Hook (CLAUDE.md „Daten-Schema-Reworks").
6. **Mobile:** Frontend ist Desktop-Planungstool (Memory) — Issue-AC „Sidebar → Bottom-Sheet" ist nice-to-have, nicht Pflicht.

## Analyse-Ergebnis (Phase 2, 2026-05-22)

### Architektur-Entscheidung (Tech-Lead)

1. **Frontend-Editor:** Neue schlanke Komponente `frontend/src/lib/components/edit/EditStagesPanelNew.svelte`, die `ProfileEditor` + `WaypointCard` + `EtappenStrip` (alle aus epic_137, alle MapCanvas-unabhängig) direkt komponiert. **WaypointsPanel NICHT umbauen** (kein `showMap`-Prop) — der Detail-View (epic_137, grün) bleibt unangetastet. Ersetzt `EditStagesSection.svelte` im „Etappen"-Accordion von `TripEditView.svelte`.
2. **Klick aufs Höhenprofil = Wegpunkt hinzufügen:** optionales Prop `onProfileClick` an `ProfileEditor` (SVG-Background-onClick nur wenn Prop gesetzt → Detail-View unverändert). Neuer Punkt: lat/lon/elevation linear zwischen Nachbar-Wegpunkten interpoliert (`interpolateWaypoint` in `waypointEditor.ts`), startet als `suggested: true`.
3. **Datenmodell — minimal-additiv:**
   - **NEU:** `arrival_calculated` (Waypoint) — in `types.ts`, `internal/model/trip.go` (`*string, omitempty`), Python `src/app/trip.py` (Loader muss Feld erhalten — Datenverlust-Regel!).
   - **NICHT NEU:** `origin`/`confirmed` aus dem Issue sind redundant zum existierenden `suggested`-Flag → `suggested` wiederverwenden (suggested:true ≈ algorithm+unconfirmed). `arrival_override` vorerst weglassen (Folge-Issue falls Override-Bedarf).
4. **Naismith — Berechnungsort (Korrektur am Plan-Agent):** Die Naismith-Formel ist trivial (`dist/4 + ascent/300 + descent/500`, kumulativ ab `start_time`/Default 08:00).
   - **Live-Vorschau im Editor:** clientseitig (`frontend/src/lib/utils/naismith.ts`, nutzt `haversineKm` aus `headerStats.ts`) für sofortiges Feedback beim Editieren.
   - **Authoritative + persistiert:** Go berechnet `arrival_calculated` beim Speichern (PUT-Handler) und persistiert es → Single Source. Formel-Konstanten in Go gespiegelt mit Querverweis-Kommentar auf Python `EtappenConfig` (`src/app/models.py`).
   - **Python-Pipeline:** `trip_report_scheduler._convert_trip_to_segments` bevorzugt persistiertes `arrival_calculated`, statt selbst zu interpolieren → Editor-Anzeige == reale Wetterabruf-Zeiten. **Wichtig:** `_interpolate_arrival_time` nutzt heute `max()` statt Summe (divergent/Bug) — durch Bevorzugung des persistierten Werts wird diese Divergenz für bearbeitete Trips umgangen (risikoarm, ohne die Live-Formel umzuschreiben).

### Begründung „alles in einem Zug" ernst genommen

PO wählte explizit Backend+UI zusammen (nicht Platzhalter+später). Rein-clientseitige Berechnung (Plan-Agent-Vorschlag) würde Editor-Zeiten zeigen, die NICHT den Zeiten entsprechen, zu denen das System real Wetter abruft (Python-Divergenz). Deshalb: Backend rechnet & persistiert, Pipeline konsumiert denselben Wert.

### Scope (überschreitet 250-LoC-Einzel-Workflow → Aufteilung empfohlen)

| Datei | Aktion | ~LoC |
|-------|--------|------|
| `frontend/src/lib/types.ts` | +arrival_calculated | +1 |
| `internal/model/trip.go` | +ArrivalCalculated | +1 |
| `internal/handler/trip.go` (+ ggf. `internal/.../naismith.go`) | Naismith-Compute-on-save | ~50 |
| `src/app/trip.py` / loader | arrival_calculated erhalten | ~6 |
| `src/services/trip_report_scheduler.py` | persistierten Wert bevorzugen | ~15 |
| `frontend/src/lib/utils/naismith.ts` (+test) | Live-Berechnung | ~70 |
| `frontend/src/lib/components/trip-detail/waypoints/ProfileEditor.svelte` | +onProfileClick | ~35 |
| `frontend/src/lib/utils/waypointEditor.ts` | interpolateWaypoint | ~20 |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | NEU (Kern) | ~160 |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Komponenten-Tausch | ~3 |
| e2e: bug-283 umschreiben, bug-273 löschen, issue-296 neu | Test-Migration | (Tests) |

**Empfohlene Aufteilung in 2 koordinierte Sub-Workflows (ein PR):**
- **296-BE (Backend/Daten):** Modell-Felder (types.ts/trip.go/Python) + Go-Compute-on-save + Python-Konsum + Roundtrip-Migrationstest. ~120 LoC.
- **296-FE (Editor):** naismith.ts + ProfileEditor-onProfileClick + interpolateWaypoint + EditStagesPanelNew + TripEditView-Tausch + Test-Migration. ~250 LoC (ggf. eigener Split oder `loc_limit_override`).

### Risiken

1. **Interpolierte Koordinaten** für rein manuell aufs Profil gesetzte Punkte sind lineare Schätzwerte (kein echter Geländebezug, da keine Karte). Akzeptabel, da Algorithmus die relevanten Punkte (Wetterscheiden) vorschlägt; UI sollte „interpolierter Punkt" kommunizieren.
2. **Python-Pipeline ist Live-System** (versendet echte Briefings). Konsum des persistierten Werts ist risikoarm, MUSS aber getestet werden (Roundtrip + Scheduler-Pfad).
3. **Test-Migration:** bug-283 (4/6) + bug-273 (1/1) sind dedizierte Regressionstests der zu löschenden Lat/Lon-Tabelle → umschreiben/löschen.
4. **Schema-Felder** additiv + Read-Modify-Write-Merge (Go-PUT-Handler merged bereits) + Pre-Snapshot-Hook → Datenverlust-Regel eingehalten.

### Nächster Schritt

`/3-write-spec` — Spec(s) für 296-BE + 296-FE mit AC-N-Format. Vorher PO-Bestätigung der 2-Schritt-Aufteilung.
