# Context: Issue #248 — Smart-Import Endpoint

## Request Summary

Neuer API-Endpoint `POST /api/locations/resolve` der URL oder Koordinaten entgegennimmt, das Format automatisch erkennt, und eine Location-Preview (lat/lon/elevation/timezone/name) zurückgibt — ohne zu speichern. Das Frontend nutzt die Preview zur Benutzer-Bestätigung, bevor via `POST /api/locations` gespeichert wird.

## Unterstützte Eingabe-Formate

| Format | Beispiel |
|--------|---------|
| Komoot Highlight | `komoot.com/de-de/highlight/2049832` |
| Komoot Tour | `komoot.com/de-de/tour/…` |
| Google Maps Share-URL | `goo.gl/maps/…` |
| Google Maps App-URL | `maps.app.goo.gl/…` |
| Dezimal-Koordinaten | `47.0789, 11.6856` |
| DMS-Koordinaten | `47°04'44.0"N 11°41'08.2"E` |
| UTM | `33T 296000 5215000` |
| GPX-Wegpunkt | einzelner `<trkpt>`-Eintrag als Text |

## Related Files

| Datei | Relevanz |
|-------|---------|
| `internal/handler/location.go:1-164` | Alle bestehenden Location-Handler — Muster für neuen Handler |
| `internal/handler/location.go:42-53` | `validateLocation()` — Validierungs-Pattern |
| `internal/handler/location.go:17-24` | `toKebab()` + `nonAlphaNum` regexp — schon importiert |
| `internal/model/location.go:1-20` | Location-Struct mit allen Feldern inkl. Spec #247 |
| `internal/provider/openmeteo/timezone.go:1-28` | `TimezoneForCoords(lat, lon float64) string` — direkt nutzbar |
| `internal/store/store.go:34-225` | Store-CRUD (für Resolve-Handler irrelevant — kein Speichern) |
| `cmd/server/main.go:82-85` | Route-Registrierung — hier neue Route eintragen |
| `go.mod` | Dependencies: chi, tzf (Timezone), paulmach/orb |
| `internal/handler/forecast.go` | HTTP-Handler-Pattern + `strconv`-Koordinaten-Parsing |
| `internal/handler/proxy.go` | HTTP-Client-Pattern für externe API-Calls |
| `internal/handler/location_write_test.go` | Test-Helper `newTestStore`, `httptest`-Pattern |

## Existing Patterns

- **Handler-Pattern:** `func XxxHandler(s *store.Store) http.HandlerFunc { return func(w http.ResponseWriter, r *http.Request) {...} }`
- **JSON Decode/Encode:** `json.NewDecoder(r.Body).Decode(&req)` / `json.NewEncoder(w).Encode(resp)`
- **Fehler-Response:** `w.WriteHeader(400); w.Write([]byte(`{"error":"bad_request"}`))`
- **Timezone-Lookup:** `openmeteo.TimezoneForCoords(lat, lon)` — liefert IANA-String oder "UTC"
- **ID-Generierung:** `toKebab(name)` — bereits in location.go
- **Regexp-Nutzung:** `regexp.MustCompile(...)` als Package-Var, nicht pro Request

## Dependencies

- **Upstream (was Resolve nutzt):**
  - `internal/provider/openmeteo/timezone.go` für Timezone-Lookup
  - Komoot API (öffentlich, kein Auth) für Name+Elevation aus Highlights
  - Open-Elevation API oder `api.open-elevation.com` für Höhe bei reinen Koordinaten
- **Downstream (was Resolve nicht berührt):**
  - Store-Layer — Resolve speichert nichts
  - Frontend Sub-Issue #249 (noch offen) nutzt diesen Endpoint

## Existing Specs

- `docs/specs/modules/compare_247_location_model.md` — Location-Struct mit Timezone/DataSource/CreatedAt

## Offene Fragen / Risiken

1. **Elevation-Quelle:** Noch kein Elevation-Lookup im Codebase. Optionen:
   - Open-Elevation API (`api.open-elevation.com/api/v1/lookup?locations=lat,lon`) — kostenlos, kein Key
   - Komoot-Highlight liefert Elevation direkt in der JSON-Response
   - Bei reinen Koordinaten ohne Komoot: HTTP-Call nötig

2. **Komoot-URL-Auflösung:** Komoot hat eine öffentliche JSON-API für Highlights:
   - `https://www.komoot.com/api/v007/highlights/{id}` — kein Auth nötig für öffentliche Highlights
   - Liefert: `lat`, `lon`, `elevation`, `display.name`
   - Für Touren: `https://www.komoot.com/api/v007/tours/{id}` — Start-Waypoint

3. **Google Maps URL-Parsing:** Keine API nötig — URL enthält Koordinaten direkt:
   - `goo.gl/maps/...` → HTTP-Redirect folgen → URL-Parameter `@lat,lon,z` extrahieren
   - `maps.app.goo.gl/...` → selbes Muster nach Redirect

4. **UTM-Konvertierung:** Stdlib hat kein UTM-Modul. Optionen:
   - Eigene Formel (ca. 20 Zeilen) — hinreichend für Issue-Scope
   - `github.com/golang/geo` oder `github.com/twpayne/go-proj` — neue Dep

5. **GPX `<trkpt>`-Parsing:** Einfaches XML-Unmarshal mit `encoding/xml` (stdlib)

6. **AC-3 (HTTP 422 bei unbekannt):** Chi antwortet mit 404 wenn Route nicht matched — 422 muss im Handler kommen, nicht im Router

7. **Komoot-Tour vs Highlight:** Tour hat keinen einzelnen Punkt — Sinnvollstes: erster oder markantester Waypoint? Spec sagt nur "Tour" — unklar ob Start/End/Highlight. **Frage an User vor Spec.**

## Route-Positionierung

Route muss **vor** `r.Post("/api/locations", ...)` registriert werden, sonst würde Chi `/resolve` als `{id}`-Parameter interpretieren:

```go
// RICHTIG:
r.Post("/api/locations/resolve", handler.ResolveLocationHandler())
r.Post("/api/locations", handler.CreateLocationHandler(s))
```

## Response-Schema (aus Issue)

```json
{
  "lat": 47.0789,
  "lon": 11.6856,
  "elevation_m": 3250,
  "timezone": "Europe/Vienna",
  "data_source": "icon_d2",
  "region": "Tirol · Tuxer Alpen",
  "suggested_name": "Hintertuxer Gletscher",
  "source_type": "komoot"
}
```

**Hinweis:** `data_source` im Response kommt aus Issue-Spec, ist aber irreführend — `data_source` im Location-Modell bedeutet Wetter-Provider (openmeteo/icon_d2), nicht Import-Quelle. `source_type` ist besser für Import-Quelle. Klären in Spec.
