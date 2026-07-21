---
entity_id: issue_276_mobile_gmaps_link
type: bugfix
created: 2026-05-20
updated: 2026-05-20
status: complete
version: "1.0"
tags: [resolver, google-maps, geocoding, nominatim, backend, bugfix]
---

# Issue #276 — Mobiler Google Maps Link wird nicht erkannt

## Approval

- [ ] Approved

## Purpose

Behebt drei Defekte im URL-Resolver (`internal/resolver/`), durch die mobile Google Maps Sharing-Links (Format `maps.google.com?q=...&ftid=...`) und Desktop Place-Links (`www.google.com/maps/place/...`) nicht aufgelöst werden und stattdessen „Format nicht erkannt" liefern. Die Lösung erweitert das Switch-Routing um beide URL-Formate, lässt die vollständige Redirect-Kette durchlaufen und fügt einen gestaffelten Nominatim-Fallback (OSM Geocoding) ein, wenn kein `@lat,lon`-Muster in der finalen URL gefunden wird.

## Source

- **Files:**
  - `internal/resolver/resolver.go` (geändert — Switch-Routing)
  - `internal/resolver/googlemaps.go` (geändert — Redirect-Kette + Nominatim-Fallback)
  - `internal/resolver/resolver_test.go` (geändert — 2 neue Tests)

## Dependencies

| Abhängigkeit | Art | Zweck |
|---|---|---|
| `internal/resolver/coords.go` | Go-Paket (vorhanden) | `inRange()`, `parseLatLonString()` — wird weiterhin genutzt für Koordinaten-Extraktion |
| `reGoogleAt` regexp | Bestehende Variable in `googlemaps.go` | `@(-?\d+\.\d+),(-?\d+\.\d+)` — matcht Koordinaten in finaler Redirect-URL |
| `https://nominatim.openstreetmap.org/search` | Externe REST-API (kostenlos) | Geocoding von Ortsnamen aus dem `q=`-Parameter; kein API-Key nötig; Rate-Limit 1 Req/s |
| `internal/handler/location_resolve.go` | Go-HTTP-Handler | Konsument von `Resolve()` — keine Änderung nötig |

## Scope

Nur Backend, 3 Dateien:

- **Geändert:** `internal/resolver/resolver.go` — Switch-Case
- **Geändert:** `internal/resolver/googlemaps.go` — Redirect-Logik + Nominatim-Fallback
- **Geändert:** `internal/resolver/resolver_test.go` — 2 neue echte HTTP-Tests

Keine Änderungen an:
- `internal/handler/location_resolve.go` — HTTP-Handler bleibt unverändert
- `frontend/src/lib/components/compare/NewLocationWizard.svelte` — Frontend unverändert

## Implementation Details

### Defekt 1 — `resolver.go`: Switch-Routing erweitern

Die `Resolve()`-Funktion enthält einen `switch`-Block, der die URL-Domain prüft. Zwei neue Cases ergänzen:

```go
case strings.Contains(rawURL, "maps.google.com"):
    return resolveGoogleMaps(rawURL)
case strings.Contains(rawURL, "www.google.com/maps"):
    return resolveGoogleMaps(rawURL)
```

Diese Cases werden **vor** dem `default`-Zweig eingefügt, sodass mobile Sharing-URLs und Desktop Place-Links dieselbe `resolveGoogleMaps`-Funktion durchlaufen wie bestehende `goo.gl/maps`-URLs.

### Defekt 2 — `googlemaps.go`: Vollständige Redirect-Kette + Nominatim-Fallback

**Schritt 1 — Redirect-Kette vollständig folgen:**

Das bestehende `followGoogleMapsRedirect` setzt `CheckRedirect: http.ErrUseLastResponse`, was nur einen Hop folgt. Dieses Override wird entfernt, sodass Go's `http.Client` standardmäßig bis zu 10 Redirects folgt. Die finale URL wird aus `resp.Request.URL.String()` gelesen.

```go
client := &http.Client{Timeout: 10 * time.Second}
resp, err := client.Get(rawURL)
if err != nil { return ResolveResult{}, err }
defer resp.Body.Close()
finalURL := resp.Request.URL.String()
```

Danach wie bisher `reGoogleAt.FindStringSubmatch(finalURL)` auf die finale URL anwenden.

**Schritt 2 — `q=`-Parameter auf Koordinaten prüfen:**

Falls `@lat,lon` nicht gefunden: `q=`-Parameter aus der Original-URL parsen und via `parseLatLonString()` auf ein Koordinatenpaar prüfen. Liefert das ein valides Ergebnis, direkt zurückgeben.

**Schritt 3 — Nominatim-Fallback (gestaffelt):**

Falls `q=` keinen Koordinaten-String enthält, den Ortsnamen via OSM Nominatim geocodieren. Gestaffelte Strategie:

1. Vollständigen `q=`-Wert URL-dekodieren und an Nominatim schicken
2. Wenn kein Treffer (leere Antwort): letztes Komma-Segment des `q=`-Werts extrahieren (z.B. `"23758 Wangels"` aus `"...Begräbniswald in Ostholstein,..., 23758 Wangels"`) und erneut anfragen
3. Wenn immer noch kein Treffer: `ResolveResult{Code: "resolve_failed", Message: "Ort nicht gefunden"}` zurückgeben

Nominatim-Request-Format:
```
GET https://nominatim.openstreetmap.org/search?q=<encoded>&format=json&limit=1
Header: User-Agent: gregor-zwanzig/1.0
```

Antwort-Parsing: JSON-Array, erstes Element enthält `lat` und `lon` als Strings — via `strconv.ParseFloat` konvertieren.

`source_type` im Rückgabe-Objekt: `"google_maps"` (da der Input-Typ Google Maps war, unabhängig vom Geocoding-Pfad).

### Defekt 3 — `www.google.com/maps/place/...` (minor)

Wird durch die beiden neuen Switch-Cases in `resolver.go` (Defekt 1) mitabgedeckt, da `www.google.com/maps` als Substring erkannt wird. Kein gesonderter Codepfad nötig — Desktop Place-Links enthalten `@lat,lon` in der URL, das bestehende `reGoogleAt`-Regex greift nach dem Redirect.

### `resolver_test.go` — 2 neue Tests

Beide Tests machen echte HTTP-Calls (Projektkonvention: keine Mocks):

**Test 1 — mobiler Sharing-Link:**
```go
func TestResolveMobileGoogleMapsLink(t *testing.T) {
    result, err := Resolve("https://maps.google.com?q=Freden%20op%27n%20Kliff%2C%2023758%20Wangels&ftid=0x47b287f8362cffa1:0x43d19fdda3876e3f&entry=gps")
    require.NoError(t, err)
    assert.Equal(t, "google_maps", result.SourceType)
    assert.InDelta(t, 54.3, result.Lat, 0.5)  // Wangels liegt bei ~54.3°N
    assert.InDelta(t, 10.8, result.Lon, 0.5)  // ~10.8°E
}
```

**Test 2 — Desktop Place-Link:**
```go
func TestResolveDesktopGoogleMapsPlaceLink(t *testing.T) {
    result, err := Resolve("https://www.google.com/maps/place/Innsbruck/@47.2692,11.4041,13z")
    require.NoError(t, err)
    assert.Equal(t, "google_maps", result.SourceType)
    assert.InDelta(t, 47.27, result.Lat, 0.1)
    assert.InDelta(t, 11.40, result.Lon, 0.1)
}
```

## Expected Behavior

- **Input:** Eine URL der Form `https://maps.google.com?q=ORTSNAME&ftid=...` oder `https://www.google.com/maps/place/NAME/@lat,lon,...`
- **Output:** `ResolveResult` mit gesetztem `Lat`, `Lon`, `SourceType: "google_maps"` und `Code: "ok"`
- **Fehlerfall (Ort nicht auflösbar):** `ResolveResult{Code: "resolve_failed", Message: "Ort nicht gefunden"}` — kein HTTP-500
- **Side effects:** Maximal 2 ausgehende HTTP-Requests pro Auflösung (1× Google Redirect-Kette + ggf. 1–2× Nominatim). Nominatim-User-Agent wird gesetzt (`gregor-zwanzig/1.0`).

## Acceptance Criteria

**AC-1:** Given eine mobile Google Maps Sharing-URL der Form `maps.google.com?q=ORTSNAME&ftid=PLACE_ID&entry=gps` / When `Resolve()` mit dieser URL aufgerufen wird / Then liefert das Ergebnis `SourceType: "google_maps"`, `Code: "ok"` und Koordinaten, die innerhalb von 0,5 Grad des tatsächlichen Orts liegen.

**AC-2:** Given eine Desktop Google Maps Place-URL der Form `www.google.com/maps/place/NAME/@lat,lon,zoom` / When `Resolve()` mit dieser URL aufgerufen wird / Then liefert das Ergebnis `SourceType: "google_maps"`, `Code: "ok"` und Koordinaten, die innerhalb von 0,1 Grad der in der URL enthaltenen `@lat,lon`-Werte liegen.

**AC-3:** Given eine mobile Google Maps Sharing-URL, bei der die vollständige Redirect-Kette keine URL mit `@lat,lon` liefert und der `q=`-Parameter einen Ortsnamen enthält / When der Nominatim-Fallback ausgeführt wird / Then wird zuerst der vollständige `q=`-Wert an Nominatim gesendet; nur wenn kein Treffer: das letzte Komma-Segment als zweiter Versuch.

**AC-4:** Given eine URL, die `maps.google.com` als Substring enthält / When `Resolve()` diese URL verarbeitet / Then wird sie nicht mehr im `unknown_format`-Zweig abgefangen, sondern via `resolveGoogleMaps()` verarbeitet.

**AC-5:** Given Nominatim liefert für beide gestaffelten Abfragen keine Ergebnisse / When der Fallback vollständig durchgelaufen ist / Then gibt `Resolve()` `Code: "resolve_failed"` zurück (kein Crash, kein HTTP-Fehler).

## Known Limitations

- Google kann die Redirect-Kette jederzeit ändern — der Resolver kann dann erneut brechen. Niedrige Priorität, da kein API-Vertrag.
- Nominatim Rate-Limit: 1 Request/Sekunde. Bei Einzel-Requests im Wizard kein Problem; sollte kein Batch-Resolver gebaut werden, muss ein Throttle ergänzt werden.
- `ftid=` (Google Places ID) wird nicht direkt decodiert — kein öffentlicher Decoder ohne Google Places API Key. Der Resolver verlässt sich auf Redirect-Kette + Nominatim.

## Changelog

- 2026-05-20: Initial spec erstellt (Issue #276 — Mobiler Google Maps Link wird nicht erkannt).
