---
entity_id: fix_go_rmw_merge_1082_1103
type: module
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
tags: [bug, data-loss, go, persistence, read-modify-write]
---

# Fix: Go-Persistenz — Blind-Replace verhindert Datenverlust (#1082 + #1103)

## Approval

- [ ] Approved

## Purpose

Zwei vorbestehende Datenverlust-Bugs derselben Fehlerklasse in der Go-API beheben:
Teil-Schreibvorgänge ersetzen Bestehendes blind, statt feldweise zu mergen bzw.
Kollisionen sichtbar abzulehnen. Fehlerklasse wie BUG-DATALOSS-GR221 (#102).

## Source

- **File:** `internal/handler/location.go` (`CreateLocationHandler`, ab Zeile 55)
- **File:** `internal/handler/trip.go` (`UpdateTripHandler`, `report_config`-Zweig ~Zeile 203)
- **Identifier:** `CreateLocationHandler`, `UpdateTripHandler`

Schicht: **Go-API** (`internal/`), Production-API Port 8090.

## Estimated Scope

- **LoC:** ~20 (Produktivcode), + Tests
- **Files:** 2 Produktivdateien (`internal/handler/location.go`, `internal/handler/trip.go`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/location.go` (`LoadLocation`, `SaveLocation`) | store | Existenzprüfung + Persistenz |
| `internal/store/trip.go` (`LoadTrip`, `SaveTrip`) | store | RMW-Basis für Trip-Update |
| `internal/model/trip.go` (`ReportConfig map[string]interface{}`) | model | Ziel-Map des Feld-Merges |

## Implementation Details

### Bug A — #1082: POST /api/locations überschreibt bei ID-Kollision still

`CreateLocationHandler` leitet die ID deterministisch aus dem Namen ab (`toKebab`)
und ruft `SaveLocation` **ohne Existenzprüfung** → bestehende (ggf. Bibliotheks-)
Location wird still überschrieben, fehlende Payload-Felder gehen verloren.

**Fix (409 Conflict):** Vor dem Speichern prüfen, ob unter der (Auto-)ID bereits
eine Location existiert. Falls ja → **HTTP 409** mit sprechendem Detail, kein Write.
Prüfung ist user-scoped (`s.WithUser(...)` ist bereits gesetzt) — keine
Cross-User-Kollision. Für gewollte Änderungen existiert bereits PUT/PATCH.

```
existing, err := s.LoadLocation(loc.ID)   // nach ID-Ableitung, vor SaveLocation
if err != nil { -> 500 store_error }
if existing != nil {
    -> 409 {"error":"conflict","detail":"Ort mit dieser ID existiert bereits"}
}
```

### Bug B — #1103: PUT /api/trips/{id} ersetzt report_config komplett

`existing.ReportConfig = *req.ReportConfig` ersetzt die ganze Map, sobald der Body
den Key `report_config` enthält → Teil-Update löscht übrige Keys (`enabled`,
`send_email`, ...). Andere Trip-Felder sind bereits korrekt RMW-gemergt.

**Fix (Feld-Level-Merge):** Nur die im Request vorhandenen Keys überschreiben,
bestehende Map beibehalten.

```
if req.ReportConfig != nil {
    if existing.ReportConfig == nil {
        existing.ReportConfig = map[string]interface{}{}
    }
    for k, v := range *req.ReportConfig {
        existing.ReportConfig[k] = v
    }
}
```

## Expected Behavior

- **Input A:** POST /api/locations mit Name/ID, die eine bestehende Location trifft.
- **Output A:** HTTP 409, bestehende Datei **unverändert**.
- **Input B:** PUT /api/trips/{id} mit `report_config` nur teilweise (z.B. `{"email_format":"compact"}`).
- **Output B:** Nur `email_format` geändert; `enabled`/`send_email`/übrige Keys bleiben.
- **Side effects:** keine über die Ziel-Datei hinaus.

## Acceptance Criteria

- **AC-1:** Given eine bereits gespeicherte Location `chamonix` (userA) mit Feld `region` /
  When userA `POST /api/locations` mit `{"name":"Chamonix", ...}` (kebab-ID = `chamonix`) sendet /
  Then antwortet die API mit **409** und die bestehende Datei bleibt byte-identisch (kein Feldverlust).
  - Test: Go-Handler-Test gegen echten Store (Tempdir): Location anlegen → zweiter POST → Code 409 + Datei-Inhalt vor/nach identisch.

- **AC-2:** Given kein Ort unter der abgeleiteten ID existiert /
  When userA `POST /api/locations` mit gültigem neuen Ort sendet /
  Then antwortet die API weiterhin mit **201** und legt die Location an (Regression-Schutz).
  - Test: Go-Handler-Test gegen echten Store: frischer POST → 201, Datei existiert.

- **AC-3:** Given ein Trip mit `report_config = {"enabled":true,"email_format":"full","send_email":true}` /
  When `PUT /api/trips/{id}` mit Body `{"report_config":{"email_format":"compact"}}` gesendet wird /
  Then enthält der gespeicherte Trip `report_config` = `{"enabled":true,"email_format":"compact","send_email":true}` (nur `email_format` geändert, `enabled`/`send_email` erhalten).
  - Test: Go-Handler-Test gegen echten Store: Trip anlegen → PUT mit Teil-report_config → GET/Load → alle drei Keys prüfen.

- **AC-4:** Given zwei verschiedene Nutzer (userA, userB) /
  When userB `POST /api/locations` mit einer ID sendet, die nur in userAs Store existiert /
  Then antwortet die API mit **201** (kein 409), denn die Existenzprüfung ist user-scoped — keine Cross-User-Kollision und kein Cross-User-Datenleck.
  - Test: Go-Handler-Test mit zwei user-scoped Stores: gleiche ID in userA vorhanden, userB-POST → 201, userAs Datei unberührt.

## Was NICHT Teil dieses Workflows ist (Known Consideration)

`UpdateTripHandler` ersetzt auch `aggregation`, `weather_config`, `display_config`
als ganze Maps (gleiche Blind-Replace-Mechanik wie report_config). Diese sind
**nicht** durch einen Live-Bug belegt und werden hier bewusst nicht angefasst
(Replace-Semantik dieser Clients unbekannt → Regressionsrisiko). Bei Bestätigung
in der Validierung → separates Folge-Issue, nicht in diesem Scope fixen.

## Test-Plan

4 automatisierte Go-Handler-Tests gegen echten Store (Tempdir, keine Mocks) —
konsistent mit `internal/handler/location_write_test.go` / `trip_write_test.go`.
