# Context: Trip-Wizard W1 (Route + Etappen)

## Request Summary

4-Schritt-Wizard fuer Trip-Anlage. Phase W1 baut den Wizard-Container (Stepper-UI, State-Management) und die ersten zwei Schritte: Route (GPX oder manuell) und Etappen (editieren, Daten zuweisen). Schritte 3+4 (Wetter-Templates, Reports) folgen in W2/W3.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/routes/trips/+page.svelte` | Aktuelle Trips-Seite, Create/Edit-Dialoge — Wizard wird hier verlinkt |
| `frontend/src/routes/trips/+page.server.ts` | Server-Load fuer Trips-Liste |
| `frontend/src/lib/components/TripForm.svelte` | Bestehendes Trip-Formular (Stages/Waypoints) — wird in Wizard-Schritt 2 wiederverwendet |
| `frontend/src/routes/gpx-upload/+page.svelte` | GPX Upload Flow — wird in Wizard-Schritt 1 integriert |
| `frontend/src/lib/components/WeatherConfigDialog.svelte` | Wetter-Config — spaeter Schritt 3 (W2) |
| `frontend/src/lib/types.ts` | Trip, Stage, Waypoint Typen |
| `frontend/src/lib/api.ts` | API Client (fetch-basiert) |
| `frontend/src/routes/+layout.svelte` | Layout mit Sidebar-Navigation |
| `frontend/src/lib/components/ui/` | shadcn-svelte Komponenten (Button, Card, Dialog, Input, Label, Badge, Table) |
| `internal/handler/trip.go` | Go API: POST/PUT /api/trips |
| `internal/handler/trip_write_test.go` | Go API Tests |
| `api/routers/gpx.py` | FastAPI: POST /api/gpx/parse |
| `docs/specs/ux_redesign_navigation.md` | Approved Spec mit Wizard-Design |

## Existing Patterns

- **Dialog-basierte UX:** Alle Formulare sind Modals (Dialog.Root), keine separaten Seiten
- **Card-basierte Sektionen:** Daten-Bereiche in Card-Komponenten
- **Svelte 5 $state/$derived:** Reaktive State-Verwaltung
- **ID-Generierung:** `crypto.randomUUID().slice(0, 8)`
- **Factory Pattern:** Safari-Kompatibilitaet (NiceGUI-seitig, nicht SvelteKit)
- **API-Pattern:** `api.get/post/put/del` mit JSON error/detail Response

## Dependencies

### Upstream (was der Wizard nutzt)
- Go API: `POST /api/trips`, `PUT /api/trips/{id}` — Trip CRUD
- FastAPI: `POST /api/gpx/parse` — GPX-Parsing
- shadcn-svelte UI-Komponenten (Button, Card, Input, Label, Dialog)
- bits-ui (Tabs vorhanden aber noch nicht gewrappt)

### Downstream (was vom Wizard abhaengt)
- W2 (Wetter-Templates): Baut auf Wizard-Container auf, fuegt Schritt 3 hinzu
- W3 (Reports): Baut auf W2 auf, fuegt Schritt 4 hinzu
- Startseite: "Neue Tour" Button soll zum Wizard fuehren

## Existing Specs

- `docs/specs/ux_redesign_navigation.md` — Approved, enthaelt Wizard-Design (4 Schritte)
- `docs/specs/modules/gpx_import_in_trip_dialog.md` — GPX Import Spec
- `docs/specs/trip_edit.md` — Trip Edit Spec

## Risiken & Ueberlegungen

1. **Wizard als Seite vs. Dialog:** Bisherige Formulare sind Dialoge. Ein 4-Schritt-Wizard passt besser als eigene Route (`/trips/new`, `/trips/{id}/edit`)
2. **Kein Stepper in shadcn-svelte:** Muss als Custom-Komponente gebaut werden
3. **GPX Upload Integration:** Aktuell separate Seite mit eigenem Flow — muss in Wizard-Schritt 1 eingebettet werden
4. **State ueber Schritte:** Wizard-State muss ueber alle 4 Schritte konsistent bleiben
5. **Edit-Modus:** Wizard muss auch fuer Bearbeitung bestehender Trips funktionieren
6. **Schritte 3+4 als Placeholder:** W1 baut Container mit 4 Schritten, aber 3+4 zeigen nur Placeholder (kommen in W2/W3)
