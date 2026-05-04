# External Validator Report

**Spec:** docs/specs/modules/weather_config_endpoints.md
**Datum:** 2026-04-14T12:57:00Z
**Server:** https://gregor20.henemm.com (Go API :8090)

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | GET /api/trips/{id}/weather-config: 200 + `null` wenn config nicht gesetzt | `curl GET gr221-mallorca` -> `null`, HTTP 200 | **PASS** |
| 2 | GET /api/trips/{id}/weather-config: 404 bei nicht existierendem Trip | `curl GET nonexistent` -> `{"error":"not_found"}`, HTTP 404 | **PASS** |
| 3 | PUT /api/trips/{id}/weather-config: 200 + gespeichertes Objekt zurueck | `curl PUT gr221-mallorca` -> `{"show_precipitation":true,"show_wind":false,"validator_test":42}`, HTTP 200 | **PASS** |
| 4 | GET nach PUT: Round-Trip liefert identisches Objekt | `curl GET gr221-mallorca` nach PUT -> identische Daten | **PASS** |
| 5 | PUT /api/trips/{id}/weather-config: 400 bei invalidem JSON | `curl PUT "NOT VALID JSON"` -> `{"error":"bad_request"}`, HTTP 400 | **PASS** |
| 6 | PUT /api/trips/{id}/weather-config: 404 bei nicht existierendem Trip | `curl PUT nonexistent` -> `{"error":"not_found"}`, HTTP 404 | **PASS** |
| 7 | GET /api/locations/{id}/weather-config: 200 + `null` | `curl GET geisbergalm-zillertal-arena` -> `null`, HTTP 200 | **PASS** |
| 8 | GET /api/locations/{id}/weather-config: 404 | `curl GET nonexistent` -> `{"error":"not_found"}`, HTTP 404 | **PASS** |
| 9 | PUT /api/locations/{id}/weather-config: 200 + Objekt | `curl PUT geisbergalm-zillertal-arena` -> gespeichertes Objekt, HTTP 200 | **PASS** |
| 10 | GET nach PUT Location: Round-Trip | `curl GET` nach PUT -> identische Daten | **PASS** |
| 11 | PUT /api/locations/{id}/weather-config: 400 | `curl PUT "{broken"` -> `{"error":"bad_request"}`, HTTP 400 | **PASS** |
| 12 | PUT /api/locations/{id}/weather-config: 404 | `curl PUT nonexistent` -> `{"error":"not_found"}`, HTTP 404 | **PASS** |
| 13 | GET /api/subscriptions/{id}/weather-config: 200 + existierendes config-Objekt | `curl GET zillertal-t-glich` -> volles display_config mit metrics-Array, HTTP 200 | **PASS** |
| 14 | GET /api/subscriptions/{id}/weather-config: 404 | `curl GET nonexistent` -> `{"error":"not_found"}`, HTTP 404 | **PASS** |
| 15 | PUT /api/subscriptions/{id}/weather-config: 200 + Objekt | `curl PUT zillertal-t-glich` -> `{"show_hourly":true,"sub_validator":"evidence"}`, HTTP 200 | **PASS** |
| 16 | GET nach PUT Subscription: Round-Trip | `curl GET` nach PUT -> identische Daten | **PASS** |
| 17 | PUT /api/subscriptions/{id}/weather-config: 400 | `curl PUT "<<<invalid>>>"` -> `{"error":"bad_request"}`, HTTP 400 | **PASS** |
| 18 | PUT /api/subscriptions/{id}/weather-config: 404 | `curl PUT nonexistent` -> `{"error":"not_found"}`, HTTP 404 | **PASS** |
| 19 | HTTPS via Nginx erreichbar | `curl GET https://gregor20.henemm.com/api/trips/gr221-mallorca/weather-config` -> HTTP 200 | **PASS** |
| 20 | HTTPS PUT via Nginx erreichbar | `curl PUT https://gregor20.henemm.com/api/subscriptions/...` -> HTTP 200 | **PASS** |
| 21 | Content-Type: application/json auf allen Responses | GET 200, GET 404, PUT 200 alle mit `Content-Type: application/json` | **PASS** |

## Findings

Keine Findings. Alle 6 Endpoints verhalten sich exakt wie in der Spec beschrieben.

### Beobachtungen (nicht-kritisch)

- **Opaque JSON Round-Trip funktioniert:** Beliebige JSON-Objekte werden ohne Schema-Validierung gespeichert und 1:1 zurueckgegeben (spec-konform: "opaque JSON round-getrippt")
- **Subscription display_config ueberschrieben:** PUT ersetzt das gesamte `display_config`-Feld, nicht nur einzelne Keys (spec-konform: "ersetzen", nicht "mergen")
- **Error-Bodies korrekt:** `{"error":"not_found"}` und `{"error":"bad_request"}` entsprechen exakt dem Spec-Format

## Verdict: VERIFIED

### Begruendung

Alle 6 Endpoints (GET/PUT fuer Trip, Location, Subscription) sind implementiert und verhalten sich exakt wie in der Spec definiert:

1. **Routing:** Alle 6 Routen sind registriert und erreichbar (localhost und HTTPS)
2. **GET-Verhalten:** Gibt `null` (HTTP 200) zurueck wenn kein display_config gesetzt, existierendes config als JSON-Objekt, 404 bei nicht existierender Parent-Entitaet
3. **PUT-Verhalten:** Speichert opaque JSON, gibt gespeichertes Objekt zurueck (200), 400 bei invalidem JSON, 404 bei nicht existierender Parent-Entitaet
4. **Round-Trip:** GET nach PUT liefert identische Daten
5. **Content-Type:** Alle Responses korrekt als `application/json`
6. **Error-Format:** Entspricht exakt der Spec (`{"error":"not_found"}`, `{"error":"bad_request"}`)
