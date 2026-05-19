# Context: Issue #249 — Locations-Verwaltung: Rail + Modal "Ort anlegen"

## Request Summary

Die bestehende Locations-Sidebar im Compare-Screen soll zur vollständigen **Locations-Rail** (240px, Suche, Chip-Filter, kollabierbare Gruppen, "+ NEU"-Button) ausgebaut werden. Der "Neuer Ort"-Dialog wird durch ein **3-stufiges Modal** ersetzt: Schritt 1 nutzt Smart-Import (Issue #248 Resolve-Endpoint), Schritt 2 vergibt Name + Gruppe, Schritt 3 wählt das Aktivitätsprofil.

## Related Files

| Datei | Relevanz |
|-------|---------|
| `frontend/src/routes/compare/+page.svelte:282–345` | Bestehende Sidebar (Aside) — hier wird die Rail integriert |
| `frontend/src/routes/compare/+page.svelte:704–720` | Bestehender Dialog mit `LocationForm` — wird durch Wizard-Modal ersetzt |
| `frontend/src/lib/components/LocationForm.svelte` | Bestehende flat Form — wird für den Wizard-Modal-Schritt 2+3 umgebaut oder ersetzt |
| `frontend/src/lib/types.ts:1–20` | `Location`-Interface — fehlen `timezone`, `data_source`, `created_at` aus Issue #247 |
| `frontend/src/lib/components/trip-wizard/Stepper.svelte` | Muster-Stepper (4 Steps) — anpassbar für 3-Step-Modal |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | Muster für Step-basiertes UI mit Zurück/Weiter-Footer |
| `frontend/src/lib/components/ui/dialog/` | Dialog-Infrastruktur (Overlay, Content, Header, Footer) |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Chip-Komponente für Gruppen-Filter in der Rail |
| `frontend/src/lib/components/ui/badge/badge.svelte` | Badge-Komponente (Gruppen-Zähler) |
| `frontend/src/lib/api.ts` | API-Helper `api.get/post/put/del` — Pattern für Resolve-Call |
| `internal/model/location.go` | Go-Struct mit allen Feldern inkl. Timezone, DataSource, CreatedAt |
| `internal/handler/location.go` | POST /api/locations Handler — produziert gespeicherte Location |
| `docs/context/issue_248_smart_import.md` | Kontext für Resolve-Endpoint `POST /api/locations/resolve` |

## Existing Patterns

- **Dialog-Pattern:** `Dialog.Root open={bool} onOpenChange={fn}` + `Dialog.Content` — konsistent in `compare/+page.svelte` und `locations/+page.svelte`
- **Stepper:** `Stepper.svelte` mit `current: 1|2|3|4` + Labels-Array — wiederverwendbar für 3 Schritte (current: 1|2|3)
- **Gruppen-Logik:** `groupedLocations` $derived in `compare/+page.svelte` (Zeilen 240–253) — bereits fertig implementiert
- **Gruppen-Toggle:** `openGroups: Set<string>` + `toggleGroup()` — bereits in compare vorhanden
- **Pill-Filter:** `Pill.svelte` aus `$lib/components/ui/pill` — existiert, bereit zum Einsatz
- **API-Resolve-Call:** `api.post('/api/locations/resolve', { input })` → ResolvePreview (wenn #248 fertig)
- **Location-Speichern:** `api.post('/api/locations', loc)` → Location — gleich bleibend

## Abhängigkeit: Issue #248 (Smart-Import)

Schritt 1 des Modals (URL/Koordinaten-Eingabe + Vorschau) hängt vom Resolve-Endpoint ab:
- `POST /api/locations/resolve` mit `{ input: string }` → `{ lat, lon, elevation_m, timezone, name, region }`
- Issue #248 ist in Phase "Context Generation" — **noch nicht implementiert**
- **Handlungsoption:** Schritt 1 mit minimalem Fallback bauen (nur Dezimalkoordinaten, kein Resolve-Call), sobald #248 fertig → URL-Felder aktivieren

## Dependencies

- **Upstream:** Issue #248 Resolve-Endpoint (Phase Context Generation → nicht abgeschlossen)
- **Downstream:** Issue #250 Compare-Engine nutzt `selectedIds` aus der Rail
- **Typ-Sync:** `types.ts` `Location`-Interface um `timezone?`, `data_source?`, `created_at?` ergänzen (aus Go-Struct `compare_247_location_model.md`)

## Existing Specs

- `docs/specs/modules/compare_247_location_model.md` — Location-Struct mit Timezone/DataSource/CreatedAt (implementiert)
- `docs/specs/modules/generic_locations_ui.md` — Ältere NiceGUI-Spec (veraltet, nicht mehr maßgeblich)
- `docs/context/issue_248_smart_import.md` — Kontext für den Resolve-Endpoint

## Was bereits existiert (NICHT neu bauen)

1. `groupedLocations` Derived-State mit Gruppen-Map + ungrouped (Zeilen 240–253)
2. `openGroups` State + `toggleGroup()` / `toggleGroupSelection()` (Zeilen 255–279)
3. Dialog-Infrastruktur für New Location
4. `handleNewLocSave()` mit `api.post('/api/locations', ...)` (Zeilen 110–120)

## Was NEU gebaut werden muss

1. **`LocationsRail.svelte`** — eigenständige Komponente (extrahiert aus `compare/+page.svelte`)
   - Suchfeld (filtert Name + Gruppe)
   - Chip-Filter für aktive Gruppen
   - Gruppen-Header mit Gruppen-Zähler (z.B. "Zillertal (5)")
   - "+ NEU"-Button

2. **`NewLocationWizard.svelte`** — 3-stufiger Dialog-Inhalt
   - Schritt 1: Smart-Import (URL/Koordinaten-Eingabe, Format-Chips, Auflösungs-Vorschau) — abhängig von #248
   - Schritt 2: Benennung (Name Pflicht, Gruppe optional, neue Gruppe inline anlegen)
   - Schritt 3: Aktivitätsprofil (3-spaltige Profilkarten)

3. **Typ-Ergänzung** in `types.ts`: `timezone?`, `data_source?`, `created_at?` in `Location`-Interface

## Risiken & Offene Fragen

1. **#248-Abhängigkeit:** Wenn #248 nicht fertig ist, muss Schritt 1 ohne Resolve-Preview auskommen. Fallback: manuelle Koordinateneingabe (wie jetzt in `LocationForm.svelte`).
2. **Mini-Map mit Topo:** Issue-Beschreibung erwähnt eine Topo-Karte im Modal. `TopoBg`-Komponente existiert, ist aber ein SVG-Hintergrund — kein interaktiver Karten-Pin. Echte Karte (Leaflet/Mapbox) würde neue Dependency erfordern. **Empfehlung:** In Phase-1-Spec als "nice to have" markieren, nicht blocken.
3. **`LocationForm.svelte` Weiterverwendung:** Die bestehende Form kann für Schritt 2+3 als Basis dienen, aber das 3-Step-Layout erfordert Aufspaltung der Felder.
