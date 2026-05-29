# Context: Issue #452 — Smart-Import (URL-Parser + Geocoding + Preview)

## Request Summary

Nutzer soll im Compare-Wizard (Step 2) eine URL oder Koordinaten eingeben können — das System erkennt das Format, löst Koordinaten auf und zeigt eine vollständige Vorschau mit Höhe und Zeitzone. Nach Bestätigung wird der Ort gespeichert und zur Vergleichs-Auswahl hinzugefügt.

## Was bereits implementiert ist

### Backend — vollständig fertig (#248, deployed)

| Datei | Status | Inhalt |
|-------|--------|--------|
| `internal/handler/location_resolve.go` | ✅ deployed | `POST /api/locations/resolve` HTTP-Handler |
| `internal/resolver/resolver.go` | ✅ deployed | Format-Dispatcher (Reihenfolge: Komoot → Google Maps → GPX-Text → UTM → DMS → Dezimal) |
| `internal/resolver/komoot.go` | ✅ deployed | Komoot Highlight-URL → API-Call → lat/lon/alt/name |
| `internal/resolver/googlemaps.go` | ✅ deployed | Google Maps Share-URL → Redirect-Follow → @lat,lon + Nominatim-Fallback |
| `internal/resolver/coords.go` | ✅ deployed | Dezimal, DMS, UTM, inline-GPX (`<trkpt`) |
| `internal/resolver/elevation.go` | ✅ deployed | Open-Elevation API Fallback (soft-fail) |
| `cmd/server/main.go:103` | ✅ deployed | Route `POST /api/locations/resolve` registriert |

**Response-Struct:**
```go
type ResolveResult struct {
    Lat           float64 `json:"lat"`
    Lon           float64 `json:"lon"`
    ElevationM    *int    `json:"elevation_m,omitempty"`
    Timezone      string  `json:"timezone"`
    SuggestedName string  `json:"suggested_name,omitempty"`
    Region        string  `json:"region,omitempty"`
    SourceType    string  `json:"source_type"` // "komoot"|"google_maps"|"decimal"|"dms"|"utm"|"gpx"
}
```

### Frontend — teilweise fertig (#440)

`frontend/src/lib/components/compare/steps/Step2Orte.svelte`:
- ✅ Eingabefeld + "Auflösen"-Button (data-testid: `compare-step2-smart-import-input`, `compare-step2-resolve-btn`)
- ✅ Ruft `POST /api/locations/resolve` auf
- ✅ Fehleranzeige bei nicht erkanntem Format
- ✅ Vorschau mit Name, lat.toFixed(4), lon.toFixed(4)
- ✅ "Hinzufügen"-Button → `POST /api/locations` → `state.pickedIds`

## Lücken — Was noch fehlt

### Frontend-Lücken (Step2Orte.svelte)

| AC | Was fehlt | Aktuell |
|----|-----------|---------|
| AC-4 | Manuelles Koordinaten-Eingabefeld bei unbekanntem Format | Nur Fehlermeldung, kein Fallback-Input |
| AC-5 | Vorschau zeigt Höhe und Zeitzone | Vorschau zeigt nur Name + lat/lon |
| — | Debounce 400ms (Issue explizit erwähnt) | Nur Button-Click, kein Live-Trigger |

### Backend-Lücken

| Feature | Status | Aufwand |
|---------|--------|---------|
| Google Maps Place-ID (`ChIJ...`) | ❌ nicht implementiert | Medium — Nominatim kann Place-ID auflösen via `/lookup?osm_type=...` oder Google Geocoding API (kein Key nötig für Place-ID-Redirect) |
| GPX-Datei-Upload | ❌ nicht implementiert | Höherer Aufwand — `POST /api/locations/resolve` nimmt derzeit JSON body, kein multipart |

## Wichtige Dateien

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/compare/steps/Step2Orte.svelte` | Primäre Frontend-Datei für AC-4 und AC-5 |
| `internal/resolver/resolver.go` | Format-Dispatcher — für Place-ID Erweiterung |
| `internal/resolver/googlemaps.go` | Google Maps Resolver — Place-ID hier ergänzen |
| `internal/handler/location_resolve.go` | Handler — für GPX-Upload ggf. neue Route |
| `frontend/src/lib/api.ts` | API-Client (vorhanden, kein Änderungsbedarf) |
| `frontend/src/lib/types.ts` | Location-Interface |
| `src/utils/timezone.py` | Python timezone util (nicht relevant für Go-Backend) |
| `src/services/coordinates.py` | Python DMS-Parser (nicht relevant — Go hat eigene Impl) |

## Existing Patterns

- **Debounce in Svelte 5:** `$effect(() => { const t = setTimeout(fn, 400); return () => clearTimeout(t); })` — kein separates Utility nötig
- **Fehler-Extraktion:** `extractMsg(e)` Funktion bereits in Step2Orte vorhanden (Zeile 88–98)
- **Nominatim-Call:** `resolveViaNominatim()` in `googlemaps.go` — für Place-ID wiederverwendbar
- **Vorschau-Pattern:** `{#if preview} ... {/if}` Block bereits vorhanden (Zeile 131–146)
- **GPX multipart:** `api/routers/gpx.py` + `api.ts gpxUpload()` als Muster für File-Upload

## Scoping-Empfehlung

**Kern (#452):** Nur die Frontend-Lücken schließen (AC-4 + AC-5 + optional Debounce) — das ist rein `Step2Orte.svelte`, ~40 LoC.

**Separates Issue empfohlen für:**
- Google Maps Place-ID Backend-Support
- GPX-Datei-Upload (braucht eigene Route + Multipart-Handling)

Der Backend-Resolve-Endpoint ist produktionsreif. Das Frontend in Step2Orte.svelte muss Höhe + Zeitzone anzeigen und bei Fehler ein Koordinaten-Fallback-Feld zeigen.

## Risiken & Abhängigkeiten

- Abhängigkeit #451 (Location-CRUD-API) ist abgeschlossen ✅
- `POST /api/locations/resolve` funktioniert und ist auth-geschützt (Chi-Router Middleware)
- Open-Elevation API ist öffentlich und kostenlos, aber träge (~2–5s) → soft-fail bereits implementiert
- Google Maps Place-ID würde erfordern, dass Nominatim `/lookup?osm_type=W&osm_id=...` (OpenStreetMap) statt Place-ID unterstützt — Google-interne Place-IDs (`ChIJ...`) lassen sich nicht direkt über Nominatim auflösen (erfordert Google Places API Key)

## Bestehende Specs

- `docs/specs/modules/issue_248_smart_import.md` — Go-Backend-Spec (referenz, umgesetzt)
- `docs/specs/modules/issue_265_smart_import_frontend.md` — Frontend-Spec für NewLocationWizard (umgesetzt)
- `docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md` — §7 definiert Step2Orte Grundstruktur
- `frontend/e2e/issue-265-smart-import.spec.ts` — E2E-Tests für NewLocationWizard (AC-1 bis AC-5)
