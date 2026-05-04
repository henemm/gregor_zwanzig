# Context: M3b Locations (SvelteKit)

## Request Summary
Locations CRUD als SvelteKit-Page portieren. Ersetzt NiceGUI `locations.py` (259 LOC). Folgt dem M3a-Pattern (Trips).

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/location.go` | Go API CRUD Endpoints (GET/POST/PUT/DELETE) |
| `internal/model/location.go` | Location struct (id, name, lat, lon, elevation_m, region, bergfex_slug, activity_profile, display_config) |
| `internal/store/store.go` | LoadLocations, SaveLocation, DeleteLocation |
| `src/web/pages/locations.py` | NiceGUI Page (259 LOC) — zu ersetzen |
| `frontend/src/lib/types.ts` | Location TypeScript interface bereits definiert |
| `frontend/src/routes/trips/+page.svelte` | M3a CRUD Pattern (Dialog, Table, State) |
| `frontend/src/lib/components/TripForm.svelte` | Form-Komponenten-Pattern |
| `frontend/src/routes/+page.server.ts` | Fetcht bereits locationCount |

## Existing Patterns (M3a)
- Dialog-basierte Create/Edit Forms mit `dialogMode` State
- Delete-Bestaetigungsdialog (separates Modal)
- Server-side Load via +page.server.ts mit Cookie-Forwarding
- API-Proxy Route fuer Client-side Mutations
- shadcn-svelte Komponenten: Button, Card, Dialog, Input, Label, Badge, Table

## Dependencies
- **Upstream:** Go API Location CRUD, shadcn-svelte UI Components
- **Downstream:** Dashboard locationCount, spaeter Weather Config Dialog

## Existing Specs
- `docs/specs/modules/generic_locations.md` — Python Location Model + ActivityProfile
- `docs/specs/modules/generic_locations_ui.md` — NiceGUI UI Spec
- `docs/specs/modules/go_location_write.md` — Go CRUD Spec

## Scope Comparison (NiceGUI vs SvelteKit)

### In Scope M3b
- Locations-Tabelle (Name, Koordinaten, Hoehe, Profil-Badge)
- Create/Edit Dialog (Name, Lat, Lon, Elevation, Region, Bergfex Slug, Activity Profile)
- Delete mit Bestaetigung
- Activity Profile Dropdown (wintersport/wandern/allgemein)
- ID auto-generiert aus Name

### Out of Scope M3b
- Weather-Metriken Dialog (eigenes Feature)
- DMS-Koordinaten-Parser (nice-to-have, spaeter)
- Karten-Integration (spaeter)

## Data: 15 Locations in Production
