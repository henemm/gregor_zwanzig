# Context: Bug #359 — Go-Handler-Tests auf Fixtures umstellen

## Request Summary
10 Tests in 5 Dateien nutzen `store.New("../../data", "default")` — echte Produktionsdaten.
Tests schlagen fehl wenn bestimmte Datensätze (z.B. Trip `e2e-test-story3`, Abo `zillertal-t-glich`)
nicht existieren oder wenn die Tests außerhalb des Produktionsservers laufen.

## Betroffene Tests

| Datei | Test | Problem | Fix-Typ |
|-------|------|---------|---------|
| `trip_test.go:13` | `TestTripsHandler` | Braucht mind. 1 Trip | seed |
| `trip_test.go:39` | `TestTripHandlerFound` | Braucht Trip `e2e-test-story3` | seed |
| `trip_test.go:62` | `TestTripHandlerNotFound` | Leerer Store reicht | replace only |
| `handler_test.go:147` | `TestLocationsHandler` | Braucht mind. 1 Location | seed |
| `stage_weather_test.go:43` | `TestStagesWeatherHandler_TripNotFound` | Leerer Store reicht | replace only |
| `subscription_test.go:21` | `TestSubscriptionsHandler` | Braucht mind. 1 Abo | seed |
| `subscription_test.go:47` | `TestSubscriptionHandlerFound` | Braucht Abo `zillertal-t-glich` | seed |
| `subscription_test.go:70` | `TestSubscriptionHandlerNotFound` | Leerer Store reicht | replace only |
| `weather_config_test.go:36` | `TestGetTripWeatherConfigNotFound` | Leerer Store reicht | replace only |
| `weather_config_test.go:109` | `TestGetLocationWeatherConfigNotFound` | Leerer Store reicht | replace only |

## Existierendes Pattern (korrekt)

In `trip_write_test.go`:
```go
func newTestStore(t *testing.T) *store.Store {
    return store.New(t.TempDir(), "test")
}
func seedTrip(t *testing.T, s *store.Store, id, name string) { ... }
```

Viele Tests nutzen dieses Pattern bereits korrekt (z.B. `TestGetTripWeatherConfigFound`).

## Abhängigkeiten

- `internal/store/store.go`: `Store.SaveSubscription(CompareSubscription)`, `Store.SaveLocation(Location)`, `Store.SaveTrip(Trip)` — alle vorhanden
- `internal/model/subscription.go`: `CompareSubscription` Struct mit Pflichtfeldern `ID`, `Name`, `Enabled`, `Locations`
- `trip_write_test.go`: Definiert `newTestStore`, `seedTrip`, `seedTripWithConfigs` — im selben Package

## Fehlender Helper

`seedSubscription` existiert noch nicht — muss analog zu `seedTrip` in `trip_write_test.go` ergänzt werden.

## Risiken

- Keines: reine Test-Umgebungs-Änderung, kein Produktionscode berührt
- `t.TempDir()` wird von Go automatisch nach dem Test aufgeräumt
