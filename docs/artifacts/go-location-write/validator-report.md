# External Validator Report

**Spec:** docs/specs/modules/go_location_write.md
**Datum:** 2026-04-13T14:30:00Z
**Server:** https://gregor20.henemm.com

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | POST /api/locations — 201 mit Location-JSON | `201 {"id":"validator-test-loc","name":"Validator Test","lat":47,"lon":11}` | PASS |
| 2 | POST /api/locations — leerer Body → 400 bad_request | `400 {"error":"bad_request"}` | PASS |
| 3 | POST /api/locations — fehlender Name → 400 validation_error | `400 {"detail":"name required","error":"validation_error"}` | PASS |
| 4 | POST /api/locations — fehlende ID → 400 validation_error | `400 {"detail":"id required","error":"validation_error"}` | PASS |
| 5 | POST /api/locations — Zero Coords → 400 validation_error | `400 {"detail":"coordinates required","error":"validation_error"}` | PASS |
| 6 | PUT /api/locations/{id} — 200 mit aktualisierter Location | `200 {"id":"validator-test-loc","name":"Updated Name","lat":48,"lon":12}` | PASS |
| 7 | PUT /api/locations/{id} — nicht vorhanden → 404 not_found | `404 {"error":"not_found"}` | PASS |
| 8 | PUT /api/locations/{id} — URL-ID ueberschreibt Body-ID | Response und GET zeigen URL-ID "url-id-test", nicht Body-ID "body-id-different" | PASS |
| 9 | PUT /api/locations/{id} — Validierungsfehler → 400 | `400 {"detail":"name required","error":"validation_error"}` | PASS |
| 10 | DELETE /api/locations/{id} — 204 No Content | `204` (leerer Body) | PASS |
| 11 | DELETE /api/locations/{id} — nicht vorhanden → 204 (idempotent) | `204` (leerer Body) | PASS |
| 12 | DELETE entfernt Location tatsaechlich | GET vor Delete: "Found", GET nach Delete: "Not found" | PASS |

## Adversarial Tests

| # | Test | Beweis | Verdict |
|---|------|--------|---------|
| A1 | POST ohne Content-Type Header | `201` — Server akzeptiert (Go net/http tolerant) | PASS |
| A2 | POST mit invalidem JSON | `400 {"error":"bad_request"}` | PASS |
| A3 | PUT mit leerem Body auf nicht-existente Location | `404 {"error":"not_found"}` (Existenzpruefung vor Body-Parse — korrekt) | PASS |

## Findings

Keine Findings. Alle Expected-Behavior-Punkte aus der Spec sind korrekt implementiert.

## Verdict: VERIFIED

### Begruendung

Alle 12 Spec-Punkte und 3 adversariale Tests bestanden. Die API verhaelt sich exakt wie in der Spec beschrieben:
- POST erstellt Locations mit korrekter Validierung (id, name, coords)
- PUT aktualisiert mit Existenzpruefung und URL-ID-Override
- DELETE ist idempotent (immer 204)
- Fehlerformate konsistent: `{"error":"..."}` bzw. `{"error":"...","detail":"..."}`
