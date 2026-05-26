---
entity_id: bug_359_handler_fixtures
type: bug
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
tags: [go, testing, handler]
---

# Bug #359 — Go-Handler-Tests auf Fixtures umstellen

## Approval

- [ ] Approved

## Purpose

10 Tests in 5 Go-Handler-Testdateien nutzen `store.New("../../data", "default")` — echte Produktionsdaten.
Tests schlagen fehl wenn bestimmte Named-Ressourcen nicht existieren. Fix: Alle Stellen auf das
bereits etablierte Pattern `newTestStore(t)` + Seeding umstellen.

## Source

- **Schicht:** Go-API — `internal/handler/`
- **Betroffene Test-Dateien:**
  - `internal/handler/trip_test.go`
  - `internal/handler/handler_test.go`
  - `internal/handler/stage_weather_test.go`
  - `internal/handler/subscription_test.go`
  - `internal/handler/weather_config_test.go`
- **Pattern-Quelle:** `internal/handler/trip_write_test.go` (`newTestStore`, `seedTrip`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store.Store` | Runtime | Filesystem-Store, unterstützt `t.TempDir()` als DataDir |
| `internal/model.CompareSubscription` | Data | Seed-Daten für Subscription-Tests |
| `internal/model.Location` | Data | Seed-Daten für Location-Tests |
| `trip_write_test.go::newTestStore` | Test-Helper | Erstellt isolierten TempDir-Store |
| `trip_write_test.go::seedTrip` | Test-Helper | Legt Minimal-Trip im Store an |

## Implementation Details

### Neuer Helper (in `trip_write_test.go`)

```go
func seedSubscription(t *testing.T, s *store.Store, id, name string) {
    sub := model.CompareSubscription{
        ID: id, Name: name, Enabled: true,
        Locations: []string{},
    }
    s.SaveSubscription(sub)
}
```

### Ersetzungsregel pro Test

| Test | Ersetzung |
|------|-----------|
| `TestTripsHandler` | `newTestStore(t)` + `seedTrip(t, s, "test-trip", "Test")` |
| `TestTripHandlerFound` | `newTestStore(t)` + `seedTrip(t, s, "e2e-test-story3", "Story 3")` |
| `TestTripHandlerNotFound` | `newTestStore(t)` (leerer Store → 404 korrekt) |
| `TestLocationsHandler` | `newTestStore(t)` + `s.SaveLocation(model.Location{...})` |
| `TestStagesWeatherHandler_TripNotFound` | `newTestStore(t)` (leerer Store → 404 korrekt) |
| `TestSubscriptionsHandler` | `newTestStore(t)` + `seedSubscription(t, s, "test-sub", "Test Sub")` |
| `TestSubscriptionHandlerFound` | `newTestStore(t)` + `seedSubscription(t, s, "zillertal-t-glich", "Zillertal")` |
| `TestSubscriptionHandlerNotFound` | `newTestStore(t)` (leerer Store → 404 korrekt) |
| `TestGetTripWeatherConfigNotFound` | `newTestStore(t)` (leerer Store → 404 korrekt) |
| `TestGetLocationWeatherConfigNotFound` | `newTestStore(t)` (leerer Store → 404 korrekt) |

## Expected Behavior

- **Input:** Go-Test-Runner ohne Zugriff auf `../../data` (leeres oder nicht-existentes Datenverzeichnis)
- **Output:** Alle 10 migrierten Tests bestehen; Handler-Suite komplett grün (0 Failures)
- **Side effects:** Keine — `t.TempDir()` wird von Go automatisch nach dem Test aufgeräumt

## Acceptance Criteria

**AC-1:** Given keine Produktionsdaten vorhanden / When `go test ./internal/handler/...` ausgeführt wird / Then alle 10 migrierten Tests bestehen ohne Zugriff auf `../../data`

**AC-2:** Given leerer TempDir-Store / When Test für "nicht gefunden"-Verhalten läuft / Then HTTP 404 mit `{"error":"not_found"}` geliefert

**AC-3:** Given `newTestStore(t)` mit geseedeten Daten / When Test für "gefunden"-Verhalten läuft (z.B. `TestTripHandlerFound`) / Then HTTP 200 mit korrekter ID zurückgegeben

**AC-4:** Given alle Handler-Tests / When `go test ./internal/handler/...` ohne Server und ohne `../../data` ausgeführt wird / Then 0 Failures, Laufzeit unter 10 Sekunden

## Known Limitations

- Keine: reine Test-Isolation, kein Produktionscode berührt

## Changelog

- 2026-05-26: Spec erstellt für Bug #359
