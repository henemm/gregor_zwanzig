---
entity_id: issue_205_followup_read_path
type: module
created: 2026-05-14
updated: 2026-05-14
status: draft
version: "1.0"
tags: [bug, go, alert-rules, read-path, follow-up-205]
---

<!-- Hot-Fix nach External-Validator-Befund von Issue #205 -->

# Issue #205 Follow-Up — Go-Read-Path alert_rules-Coercion

## Approval

- [x] Approved

## Purpose

Nach dem Live-Gang von Issue #205 hat der External Validator entdeckt:
Bestand-Trips kommen über die Go-API (`GET /api/trips`,
`GET /api/trips/<id>`) mit `alert_rules: null` zurück — die Nil-Coercion
ist nur im Write-Path (`SaveTrip`) eingebaut. Beim Lesen läuft Go
`json.Unmarshal` direkt vom File, hinterlässt `AlertRules` als nil,
und marshalled es ohne weitere Behandlung als `null` ins API-Response.

Konsequenz: Frontend muss `null` defensiv handhaben, und der spätere
`TripAlertService`-Umbau kann Alerts verlieren, wenn ein Trip nie über
einen Python-Save lief.

## Source

- **File:** `internal/store/store.go` — `LoadTrip()`/`LoadTrips()` müssen nil → `[]AlertRule{}` coercen, bevor die Trip-Objekte zurückgegeben werden
- **File:** `internal/store/store_trip_write_test.go` (oder neu `store_trip_read_test.go`) — Go-Test, der Legacy-JSON ohne `alert_rules` schreibt, dann `LoadTrip()` aufruft und prüft, dass `trip.AlertRules == []AlertRule{}` (nicht nil)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Trip.AlertRules` Go-Struct | intern | Wird vom Load-Pfad als nil zurückgegeben — soll als leeres Slice zurückgegeben werden |
| Bestehende `SaveTrip`-Coercion | intern | Symmetrische Logik im Read-Pfad — selbe Coercion wiederverwenden |

## Implementation Details

In `internal/store/store.go`, `LoadTrip()`-Funktion nach `json.Unmarshal`:

```go
if trip.AlertRules == nil {
    trip.AlertRules = []model.AlertRule{}
}
```

Wenn es eine `LoadTrips()`-Funktion gibt, die mehrere Trips zurückgibt:
selben Guard in der Schleife.

Alternative-Stelle (falls sauberer): Konstruktor-/Factory-Funktion oder
ein Hilfsfunktion `ensureDefaults(*Trip)` die in Load **und** Save
aufgerufen wird. Wenn das den bestehenden Code zu sehr umbaut: einfach
direkt in `LoadTrip` einbauen.

## Expected Behavior

- **Input:** Trip-JSON-File ohne `alert_rules`-Feld (Legacy-Format).
- **Output:** `LoadTrip()` liefert `trip.AlertRules = []model.AlertRule{}` —
  niemals nil.
- **Side effects:** Keine. JSON-File auf Disk unverändert (das ist Read-Path).

## Acceptance Criteria

- **AC-1:** Given ein Trip-JSON in einem tmp-Dir mit `{"id":"t1","name":"Legacy"}`
  (kein `alert_rules`-Feld) /
  When `store.LoadTrip("t1")` aufgerufen wird /
  Then ist `trip.AlertRules != nil` UND `len(trip.AlertRules) == 0` —
  also leeres Slice statt nil.

- **AC-2:** Given ein Trip-JSON mit drei existierenden `alert_rules` /
  When `store.LoadTrip("t1")` aufgerufen wird /
  Then bleibt `len(trip.AlertRules) == 3` und alle drei Rules sind intakt
  (Coercion hat existierende Daten NICHT überschrieben).

- **AC-3:** Given drei verschiedene Trip-Files (eines Legacy, eines mit
  vollen Rules, eines mit explizitem `"alert_rules":[]`) /
  When `GET /api/trips` über den Go-Server aufgerufen wird /
  Then sind alle drei Antworten konsistent: `alert_rules` ist immer ein
  Array (`[]` oder mit Inhalt), niemals `null` im JSON-Response.

## Known Limitations

- AC-3 wird im Test-Setup via direkter Go-Func-Calls geprüft, nicht via
  HTTP-Roundtrip — der Handler greift auf die gleiche `LoadTrip`-Funktion zu.

## Changelog

- 2026-05-14: Hot-Fix nach External-Validator AMBIGUOUS-Befund zu Issue #205.
