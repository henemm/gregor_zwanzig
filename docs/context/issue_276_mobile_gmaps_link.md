# Context: Issue #276 — Mobiler Google Maps Link wird nicht erkannt

## Request Summary

Im NewLocationWizard (Schritt 1 — Verortung) scheitert das Auflösen von mobilen Google Maps Sharing-Links. Die URL-Form `https://maps.google.com?q=ORTSNAME&ftid=PLACE_ID&entry=gps` wird nicht erkannt und liefert „Format nicht erkannt" statt Koordinaten.

Beispiel-URL aus dem Issue:
```
https://maps.google.com?q=Freden%20op'n%20Kliff%20-%20Der%20Begr%C3%A4bniswald%20in%20Ostholstein,%20Sebastian%20Graf%20Platen%20Eitz,%2023758%20Wangels&ftid=0x47b287f8362cffa1:0x43d19fdda3876e3f&entry=gps&shh=CAE&lucs=,...&g_st=ic
```

## Root Causes

### 1. Routing-Miss (`internal/resolver/resolver.go`, Zeile ~22)

Der `switch` in `Resolve()` prüft nur:
- `goo.gl/maps`
- `maps.app.goo.gl`

Aber NICHT:
- `maps.google.com` ← mobiles Sharing-Format
- `www.google.com/maps` ← Desktop-URL-Format

→ Die URL fällt durch zum `default`-Zweig und liefert `code: "unknown_format"`.

### 2. Format-Mismatch (`internal/resolver/googlemaps.go`)

Selbst wenn das Routing greift, kann `resolveGoogleMaps` die Koordinaten nicht extrahieren, weil die mobile Sharing-URL:
- kein `@lat,lon`-Muster enthält
- im `q=`-Parameter nur den Ortsnamen (kein Koordinatenpaar) hat
- `ftid=` ein opakes Google-Places-ID ist (kein öffentlicher Decoder ohne Google API Key)

Die aktuelle Funktion `followGoogleMapsRedirect` folgt nur **einem** Redirect-Hop. Bei `maps.google.com?q=...&ftid=...` ist das unzureichend — es sind mehrere Redirects nötig, bevor eine URL mit `@lat,lon` erreicht wird (falls überhaupt eine).

## Related Files

| Datei | Relevanz |
|-------|---------|
| `internal/resolver/resolver.go` | `Resolve()` switch — hier fehlt `maps.google.com`-Match |
| `internal/resolver/googlemaps.go` | `resolveGoogleMaps()` + `followGoogleMapsRedirect()` — muss mobile URLs handhaben |
| `internal/resolver/resolver_test.go` | Tests für Resolver — neuer Test für mobilen Link nötig |
| `internal/resolver/coords.go` | `inRange()`, `parseLatLonString()` — wird weiter genutzt |
| `internal/handler/location_resolve.go` | HTTP-Handler — keine Änderung nötig |
| `frontend/src/lib/components/compare/NewLocationWizard.svelte` | Konsument von `/api/locations/resolve` — keine Änderung nötig |

## Lösungsansätze

### Ansatz A: Vollständige Redirect-Kette (empfohlen)

`maps.google.com?q=...&ftid=...` leitet nach Google-intern weiter. Die Kette endet typischerweise bei einer URL der Form `https://www.google.com/maps/place/NAME/@lat,lon,zoom`. Das bestehende `@`-Regex würde dann greifen.

**Änderung:** `followGoogleMapsRedirect` so umbauen, dass es die **vollständige Redirect-Kette** folgt (nicht nur einen Hop). Go's `http.Client` folgt standardmäßig bis zu 10 Redirects — das `CheckRedirect`-Override muss entfernt werden, und die finale URL wird aus `resp.Request.URL.String()` gelesen.

**Vorteil:** Keine externe Geocoding-API, koordinaten-autoritativ von Google selbst.  
**Risiko:** Google könnte die Route ohne Redirect (als 200-HTML) ausliefern → kein `@lat,lon`.

### Ansatz B: Nominatim-Geocoding als Fallback

Wenn kein `@lat,lon` gefunden wird, den `q=`-Parameter extrahieren und via OSM Nominatim kostenlos geocodieren:
```
https://nominatim.openstreetmap.org/search?q=ORTSNAME&format=json&limit=1
```

**Vorteil:** Funktioniert für beliebige Ortsnamen, kein API-Key nötig.  
**Risiko:** Nominatim-Ergebnis kann ungenau sein (Ortsnamen aus Sharing-URLs sind oft lang mit Adressen — das verbessert die Treffsicherheit).

### Empfehlung: A + B kombiniert

1. `maps.google.com` und `www.google.com/maps` zum Router hinzufügen
2. In `resolveGoogleMaps`: vollständige Redirect-Kette folgen, dann `@lat,lon` suchen
3. Fallback: `q=`-Parameter auf Koordinaten prüfen (bestehende `parseLatLonString`)
4. Letzter Fallback: Nominatim mit dem `q=`-Wert

## Existing Patterns

- `resolveKomoot()` — greift via echter HTTP-API auf externe Daten zu (gleicher Ansatz für Nominatim)
- `parseLatLonString()` — bereits vorhanden, parst Koordinaten aus Strings
- `reGoogleAt = regexp.MustCompile(`@(-?\d+\.\d+),(-?\d+\.\d+)`)` — bereits vorhanden

## Scope

Nur Backend: `internal/resolver/resolver.go` + `internal/resolver/googlemaps.go` + `internal/resolver/resolver_test.go`.  
Frontend (`NewLocationWizard.svelte`) und HTTP-Handler (`location_resolve.go`) brauchen **keine Änderungen**.

## Risiken

- Kein echter HTTP-Call-Test im TDD-Stil möglich (gemockte Tests verboten, aber echter Netzwerk-Call auf eine externe URL ist in Ordnung — wie bei `TestResolveKomootHighlight`)
- Google ändert gelegentlich die Redirect-Struktur → der Resolver kann in Zukunft wieder brechen (niedrige Priorität)
- Nominatim Rate-Limit: 1 Request/Sekunde (kein Problem bei Einzel-Requests im Wizard)

## Analyse-Ergebnis (Phase 2)

### 3 Defekte — 2 kritisch, 1 minor

**Defekt 1 (kritisch):** `resolver.go:44` — `switch` matcht nur `goo.gl/maps` und `maps.app.goo.gl`, nicht `maps.google.com`. Die mobile Sharing-URL landet im `unknown_format`-Zweig.

**Defekt 2 (kritisch):** `googlemaps.go:55–77` — `followGoogleMapsRedirect` folgt nur einem Redirect-Hop. Die Kette `maps.google.com?q=...&ftid=...` → `maps.google.com/maps?q=...` → `200 OK (HTML)` endet nie bei einer URL mit `@lat,lon`. Danach kein Fallback für Ortsnamen im `q=`-Parameter.

**Defekt 3 (minor):** `www.google.com/maps/place/...` ebenfalls nicht im Switch — strukturell dieselbe Lücke, noch kein gemeldetes Issue.

### Nominatim-Fallback: Gestaffelt nötig

Vollstring `q=` → Nominatim schlägt oft fehl (zu spezifische POI-Namen). Funktioniert: letztes Komma-Segment aus `q=` (= PLZ + Ort, z.B. "23758 Wangels"). Strategie:
1. Vollstring → Nominatim
2. Wenn kein Treffer: letztes Komma-Segment → Nominatim
3. Wenn immer noch kein Treffer: `resolve_failed` mit klarer Fehlermeldung

### Implementierungsplan

| Datei | Änderung | ~LoC |
|-------|----------|------|
| `internal/resolver/resolver.go` | Switch-Case um `maps.google.com` + `www.google.com/maps` erweitern | +2 |
| `internal/resolver/googlemaps.go` | Volle Redirect-Kette, Nominatim-Fallback-Funktion | +30 |
| `internal/resolver/resolver_test.go` | 2 neue Tests (echter HTTP-Call, Nominatim) | +35 |

**Gesamt: ~67 LoC — weit unter dem 250er-Limit.**

## Changelog

- 2026-05-20: Initial context + Phase-2-Analyse (Issue #276)
