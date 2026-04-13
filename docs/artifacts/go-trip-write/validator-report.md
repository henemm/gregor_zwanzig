# External Validator Report

**Spec:** docs/specs/modules/go_trip_write.md
**Datum:** 2026-04-13T17:50:00+02:00
**Server:** https://gregor20.henemm.com

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | POST /api/trips — gueltiger Trip → 201 mit Trip-JSON | HTTP 201, Body: `{"id":"validator-test-trip","name":"Validator Test Trip",...}` | **PASS** |
| 2 | POST /api/trips — fehlender Body → 400 bad_request | HTTP 400, Body: `{"error":"bad_request"}` | **PASS** |
| 3 | POST /api/trips — name leer → 400 validation_error | HTTP 400, Body: `{"detail":"name required","error":"validation_error"}` | **PASS** |
| 4 | PUT /api/trips/{id} — existierender Trip → 200 mit Trip-JSON | HTTP 200, Body: `{"id":"validator-test-trip","name":"Updated Validator Trip",...}` | **PASS** |
| 5 | PUT /api/trips/{id} — nicht vorhanden → 404 not_found | HTTP 404, Body: `{"error":"not_found"}` | **PASS** |
| 6 | PUT — URL-ID ueberschreibt Body-ID | Body-ID: `different-body-id`, Response-ID: `validator-test-trip` (URL-ID gewann) | **PASS** |
| 7 | DELETE /api/trips/{id} — existierender Trip → 204 No Content | HTTP 204, leerer Body | **PASS** |
| 8 | DELETE /api/trips/{id} — nicht vorhanden → 204 (idempotent) | HTTP 204 bei zweitem DELETE auf selben Trip | **PASS** |

### Validierungsregeln (Detail)

| # | Regel | Beweis | Verdict |
|---|-------|--------|---------|
| 9 | id leer → "id required" | HTTP 400, `{"detail":"id required","error":"validation_error"}` | **PASS** |
| 10 | stages leer → "at least one stage required" | HTTP 400, `{"detail":"at least one stage required","error":"validation_error"}` | **PASS** |
| 11 | stage ohne waypoints → "stage {id}: at least one waypoint required" | HTTP 400, `{"detail":"stage s1: at least one waypoint required","error":"validation_error"}` | **PASS** |
| 12 | waypoint lat/lon = 0 → "waypoint {id}: coordinates required" | HTTP 400, `{"detail":"waypoint w1: coordinates required","error":"validation_error"}` | **PASS** |

### Integritaet

| # | Test | Beweis | Verdict |
|---|------|--------|---------|
| 13 | Geloeschter Trip nicht mehr per GET abrufbar | HTTP 404, `{"error":"not_found"}` | **PASS** |
| 14 | Kaputter JSON-Body → bad_request | HTTP 400, `{"error":"bad_request"}` | **PASS** |

## Findings

Keine Findings. Alle Expected-Behavior-Punkte aus der Spec sind korrekt implementiert.

**Hinweis:** Ein frueherer Validator-Lauf (gleicher Tag) hatte die Waypoint-Koordinaten-Validierung als BROKEN markiert. Diese wurde offensichtlich zwischenzeitlich gefixt — Test 12 zeigt jetzt korrektes Verhalten.

## Verdict: VERIFIED

### Begruendung

Alle 8 Expected-Behavior-Punkte plus 5 Validierungsregeln aus der Spec wurden gegen den laufenden Server getestet und bestanden. Im Einzelnen:

- **POST** erstellt Trips korrekt (201) mit vollstaendigem Response-Body
- **Fehlerbehandlung** liefert korrekte HTTP-Codes und Error-Formate (400 bad_request, 400 validation_error mit detail)
- **PUT** aktualisiert existierende Trips (200) und gibt 404 bei nicht-existierenden
- **URL-ID Vorrang** vor Body-ID bewiesen
- **DELETE** ist idempotent (204 in beiden Faellen)
- **Alle 5 Validierungsregeln** (id, name, stages, waypoints, coordinates) funktionieren mit exakten Fehlermeldungen laut Spec
- **Kein Test-Artefakt** auf dem Server hinterlassen (Trip wurde geloescht und Loeschung per GET verifiziert)
