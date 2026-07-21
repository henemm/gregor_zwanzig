---
entity_id: issue_248_smart_import
type: module
created: 2026-05-19
updated: 2026-05-19
status: draft
version: "1.0"
issue: 248
tags: [compare, go, location, import, resolver, endpoint]
---

# Issue #248 — Smart-Import: URL/Koordinaten-Parser + Resolve-Endpoint (EPIC 2 #246)

## Approval

- [ ] Approved

## Purpose

Implementiert einen neuen API-Endpoint `POST /api/locations/resolve`, der eine URL oder Koordinateneingabe entgegennimmt, das Format automatisch erkennt, die Koordinaten auflöst und eine Location-Vorschau zurückgibt — ohne zu speichern. Das Frontend zeigt die Vorschau zur Bestätigung, bevor der Nutzer via `POST /api/locations` speichert. Unterstützte Formate: Komoot Highlight-URLs, Google Maps-URLs, Dezimalkoordinaten, DMS-Koordinaten, UTM, GPX-Wegpunkt-Text.

## Source

- **NEU:** `internal/handler/location_resolve.go` — `ResolveLocationHandler` (HTTP-Handler)
- **NEU:** `internal/resolver/resolver.go` — `Resolve(input string) (ResolveResult, error)` — Haupt-Dispatcher
- **NEU:** `internal/resolver/komoot.go` — Komoot-Highlight-URL-Parser + API-Call
- **NEU:** `internal/resolver/googlemaps.go` — Google-Maps-URL-Parser (kein API-Key, Redirect+Regex)
- **NEU:** `internal/resolver/coords.go` — Dezimal, DMS, UTM, GPX-Parsing
- **NEU:** `internal/resolver/elevation.go` — Elevation-Lookup via Open-Elevation API
- **NEU:** `internal/handler/location_resolve_test.go` — HTTP-Handler-Tests
- **NEU:** `internal/resolver/resolver_test.go` — Parser-Tests für alle Formate
- **EDIT:** `cmd/server/main.go` — Route `POST /api/locations/resolve` vor `POST /api/locations` registrieren

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TimezoneForCoords(lat, lon float64) string` (`internal/provider/openmeteo/timezone.go`) | intern | Timezone-Lookup aus Koordinaten — existiert bereits, direkt nutzbar |
| `AuthMiddleware` (`internal/middleware/`) | intern | Alle `/api/`-Routen sind auth-geschützt; kein gesondertes Handling nötig |
| Chi-Router (`github.com/go-chi/chi/v5`) | extern | Route-Registrierung — bereits in `go.mod` |
| Komoot Public API | extern | `GET https://www.komoot.com/api/v007/highlights/{id}` — kein API-Key, liefert lat/lon/elevation/name |
| Open-Elevation API | extern | `GET https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}` — kein API-Key, Fallback bei nicht ermittelbarer Elevation |
| `net/http`, `net/url`, `encoding/xml`, `regexp`, `strconv`, `math` | Go-Stdlib | URL-Parsing, HTTP-Calls, XML-Decode für GPX, Regex für DMS/UTM |

## Implementation Details

### §1 Response-Struct (`internal/resolver/resolver.go`)

```go
type ResolveResult struct {
    Lat           float64  `json:"lat"`
    Lon           float64  `json:"lon"`
    ElevationM    *int     `json:"elevation_m,omitempty"`
    Timezone      string   `json:"timezone"`
    SuggestedName string   `json:"suggested_name,omitempty"`
    Region        string   `json:"region,omitempty"`
    SourceType    string   `json:"source_type"` // "komoot"|"google_maps"|"decimal"|"dms"|"utm"|"gpx"
}

type ResolveError struct {
    Code    string `json:"code"`    // "unknown_format"|"unsupported_url"|"resolve_failed"
    Message string `json:"message"` // menschenlesbar
}
```

**Hinweis:** `source_type` im Response ist die Import-Quelle (komoot, google_maps, …). Das ist bewusst verschieden von `Location.DataSource`, das den Wetter-Provider (icon_d2, openmeteo) bezeichnet.

### §2 Format-Erkennung (`internal/resolver/resolver.go`)

Dispatcher prüft in dieser Reihenfolge — erste Übereinstimmung gewinnt:

1. Enthält `komoot.com` → Komoot-Parser
2. Enthält `goo.gl/maps` oder `maps.app.goo.gl` → Google-Maps-Parser
3. Enthält `<trkpt` → GPX-Parser
4. Passt auf UTM-Regex (`\d+[A-Z]\s+\d+\s+\d+`) → UTM-Parser
5. Passt auf DMS-Regex (enthält `°`) → DMS-Parser
6. Passt auf Dezimal-Regex (`-?\d+\.\d+,\s*-?\d+\.\d+`) → Dezimal-Parser
7. Sonst → `ResolveError{Code: "unknown_format"}`

### §3 Komoot-Parser (`internal/resolver/komoot.go`)

URL-Erkennung via Regex: `komoot\.com/[^/]+/(highlight)/(\d+)` → extrahiert Highlight-ID.

Falls URL `tour` oder `collection` enthält statt `highlight`: sofortige `ResolveError{Code: "unsupported_url", Message: "Komoot-Touren und Sammlungen werden nicht unterstützt. Bitte einen Komoot Highlight-Link verwenden."}`.

Für Highlights: HTTP-GET `https://www.komoot.com/api/v007/highlights/{id}` mit `Accept: application/json`. Response-JSON hat die Felder:
- `._embedded.coordinates.items[0]` → lat, lng (als `lng`, nicht `lon`)
- `.elevation` → Höhe in Metern (float → int)
- `.name` → `suggested_name`

HTTP-Timeout: 10 Sekunden. Bei Statuscode ≠ 200 oder ungültigem JSON: `ResolveError{Code: "resolve_failed"}`.

### §4 Google-Maps-Parser (`internal/resolver/googlemaps.go`)

Kurz-URLs (`goo.gl/maps/...`, `maps.app.goo.gl/...`) enthalten die Koordinaten nach einem HTTP-Redirect in der finalen URL. Vorgehen:

1. HTTP-GET mit `CheckRedirect: func(...) error { return http.ErrUseLastResponse }` — nur 1 Redirect-Level.
2. Aus dem `Location`-Header der Response die finale URL extrahieren.
3. Aus der finalen URL per Regex `@(-?\d+\.\d+),(-?\d+\.\d+)` die Koordinaten extrahieren (Google Maps Standard-Muster für Kartenlinks).
4. Alternativ URL-Parameter `ll=lat,lon` oder `q=lat,lon` prüfen (für direkte maps.google.com-Links).
5. HTTP-Timeout: 10 Sekunden. `suggested_name` bleibt leer (Google Maps gibt keinen Ortsnamen ohne API-Key).

### §5 Koordinaten-Parser (`internal/resolver/coords.go`)

**Dezimal:** Regex `(-?\d{1,3}\.\d+)[,\s]+(-?\d{1,3}\.\d+)` → `strconv.ParseFloat`. Bereichsprüfung: lat ∈ [-90, 90], lon ∈ [-180, 180], sonst `ResolveError`.

**DMS:** Regex für Format `47°04'44.0"N 11°41'08.2"E` — extrahiert Grad/Minuten/Sekunden + Himmelsrichtung. Formel: `dd = d + m/60 + s/3600`, S/W negieren.

**UTM:** Regex `(\d{1,2})([A-Z])\s+(\d{4,7})\s+(\d{4,7})` → Zone, Band, Easting, Northing. Konvertierung via Standardformel (Karney/WGS84, ca. 30 Zeilen — keine externe Dep nötig). Nur UTM-Zonen 1–60 + Nordhalbkugel-Bänder (C–X ohne I/O) werden unterstützt; Südzone-Handling per Falsenorthing (10.000.000 m für negative Northings).

**GPX-Wegpunkt:** `encoding/xml`-Unmarshal der `<trkpt lat="..." lon="...">...</trkpt>`-Struktur. Falls `<ele>` vorhanden → als Elevation setzen. Optionaler `<name>` → `suggested_name`.

### §6 Elevation-Lookup (`internal/resolver/elevation.go`)

Wird aufgerufen wenn nach Format-Parsing noch kein Elevation-Wert vorliegt (d.h. für Dezimal, DMS, UTM, Google Maps — Komoot und GPX liefern Elevation direkt).

HTTP-GET: `https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}` — kein API-Key. Response-JSON: `{"results": [{"elevation": N}]}`. HTTP-Timeout: 8 Sekunden.

Fehler beim Elevation-Lookup sind **nicht kritisch** — `ElevationM` bleibt dann `nil` (`omitempty` im JSON), der Endpoint gibt trotzdem 200 zurück.

### §7 Timezone-Lookup

Nach erfolgreicher Koordinaten-Auflösung: `openmeteo.TimezoneForCoords(lat, lon)` — liefert IANA-String oder `"UTC"` als Fallback. Kein gesondertes Error-Handling nötig.

### §8 HTTP-Handler (`internal/handler/location_resolve.go`)

```go
func ResolveLocationHandler() http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        var req struct {
            Input string `json:"input"`
        }
        if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Input == "" {
            w.Header().Set("Content-Type", "application/json")
            w.WriteHeader(400)
            w.Write([]byte(`{"error":"bad_request","message":"Feld 'input' fehlt"}`))
            return
        }

        result, resolveErr := resolver.Resolve(strings.TrimSpace(req.Input))
        if resolveErr != nil {
            w.Header().Set("Content-Type", "application/json")
            w.WriteHeader(422)
            json.NewEncoder(w).Encode(resolveErr)
            return
        }

        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(result)
    }
}
```

Der Handler braucht keinen `*store.Store` (kein Speichern) — vereinfachte Signatur.

### §9 Route-Registrierung (`cmd/server/main.go`)

```go
// MUSS vor POST /api/locations stehen — sonst matcht Chi "resolve" als {id}-Parameter
r.Post("/api/locations/resolve", handler.ResolveLocationHandler())
r.Post("/api/locations", handler.CreateLocationHandler(s))
```

### §10 LoC-Schätzung

| Datei | Inhalt | LoC |
|-------|--------|-----|
| `internal/resolver/resolver.go` | Structs + Dispatcher | ~40 |
| `internal/resolver/komoot.go` | HTTP-Call + JSON-Parse | ~50 |
| `internal/resolver/googlemaps.go` | Redirect-Follow + Regex | ~45 |
| `internal/resolver/coords.go` | Dezimal + DMS + UTM + GPX | ~100 |
| `internal/resolver/elevation.go` | Open-Elevation HTTP-Call | ~35 |
| `internal/handler/location_resolve.go` | HTTP-Handler | ~25 |
| `cmd/server/main.go` | 1 neue Route | +1 |
| Tests (2 Dateien) | Handler + Parser-Tests | ~120 |
| **Summe** | | **~416 LoC** |

LoC-Limit 250 → `workflow.py set-field loc_limit_override 500` vor Implementation.

## Expected Behavior

- **Input:** POST `/api/locations/resolve` mit JSON-Body `{"input": "<url-oder-koordinaten>"}`. Auth-Cookie erforderlich (Standard-Middleware).
- **Output (Erfolg, HTTP 200):**
  ```json
  {
    "lat": 47.0789,
    "lon": 11.6856,
    "elevation_m": 3250,
    "timezone": "Europe/Vienna",
    "suggested_name": "Hintertuxer Gletscher",
    "source_type": "komoot"
  }
  ```
- **Output (Fehler, HTTP 422):**
  ```json
  {
    "code": "unknown_format",
    "message": "Das Format wurde nicht erkannt. Bitte eine Komoot-Highlight-URL, Google-Maps-Link oder Koordinaten eingeben."
  }
  ```
- **Output (Fehler, HTTP 400):** Fehlendes/leeres `input`-Feld.
- **Side effects:** Keine — der Endpoint speichert nichts.

## Acceptance Criteria

- **AC-1:** Given eine Komoot-Highlight-URL (`komoot.com/de-de/highlight/2049832`) / When POST `/api/locations/resolve` aufgerufen wird / Then antwortet der Endpoint mit HTTP 200 und enthält `lat`, `lon`, `elevation_m` und `timezone` mit plausiblen Werten (lat ∈ [-90,90], lon ∈ [-180,180], timezone ist IANA-String).
  - Test: (populated after /tdd-red)

- **AC-2:** Given Dezimalkoordinaten als String (`"47.0789, 11.6856"`) / When aufgelöst / Then stimmt `lat` auf 4 Nachkommastellen, `lon` auf 4 Nachkommastellen, `source_type` ist `"decimal"`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein unbekanntes Format (`"Gasthof Zum Löwen"`) / When aufgelöst / Then antwortet der Endpoint mit HTTP 422 und `code: "unknown_format"`.
  - Test: (populated after /tdd-red)

- **AC-4:** Given eine Komoot-Tour-URL (`komoot.com/de-de/tour/12345`) / When aufgelöst / Then antwortet der Endpoint mit HTTP 422 und `code: "unsupported_url"` mit einer Nachricht die erklärt, dass nur Highlights unterstützt werden.
  - Test: (populated after /tdd-red)

- **AC-5:** Given DMS-Koordinaten (`"47°04'44.0\"N 11°41'08.2\"E"`) / When aufgelöst / Then gibt der Endpoint HTTP 200 zurück mit lat ≈ 47.0789 und lon ≈ 11.6856 (Toleranz ±0.001), `source_type: "dms"`.
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein fehlendes `input`-Feld im Request-Body / When der Endpoint aufgerufen wird / Then antwortet er mit HTTP 400.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Google Maps App-Links:** `maps.app.goo.gl`-Links gehen über mehrere Redirects. Nur 1 Redirect-Level wird verfolgt — falls Google die Redirect-Kette ändert, kann der Parse fehlschlagen. In diesem Fall antwortet der Endpoint mit 422 (kein Absturz).
- **Open-Elevation API:** Externer Service ohne SLA — bei Ausfall bleibt `elevation_m` leer (`null` im JSON). Das ist kein Fehler, nur unvollständige Vorschau. Der User kann die Location trotzdem speichern.
- **Komoot API-Stabilität:** Die `/api/v007/highlights/{id}`-URL ist nicht offiziell dokumentiert und kann sich ändern. Bei strukturellen Änderungen der Komoot-Response schlägt der Parser fehl (422).
- **UTM-Abdeckung:** Nur WGS84/UTM-Zonen 1–60 ohne Polarregionen (unter 80°S / über 84°N). Militärisches MGRS-Format wird nicht unterstützt.
- **Keine Speicherung im Resolve-Endpoint:** Das Speichern erfolgt separat via `POST /api/locations`. Der Resolve-Endpoint ist rein lesend — er ist idempotent und kann ohne Konsequenzen mehrfach aufgerufen werden.

## Changelog

- 2026-05-19: Initial spec — Issue #248 / EPIC 2 #246. Smart-Import-Endpoint mit 6 Eingabe-Formaten (Komoot Highlight, Google Maps, Dezimal, DMS, UTM, GPX). Komoot Tours/Etappen bewusst ausgeschlossen (→ 422). Elevation via Open-Elevation-API als Fallback (soft-fail). ~416 LoC, LoC-Override 500 nötig.
