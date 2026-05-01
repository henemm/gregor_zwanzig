---
bug_id: 99
title: "Backend UpdateTripHandler: Replace statt Merge (Defense-in-Depth)"
created: 2026-04-30
status: analyzed
---

# Context: Bug #99 — UpdateTripHandler überschreibt optionale Felder

## Symptom (reproduziert in Issue #99)

PUT auf `/api/trips/{id}` mit Minimal-Body (`{id, name, stages}`) liefert HTTP 200, löscht aber stillschweigend `aggregation`, `report_config`, `weather_config`, `display_config`, `avalanche_regions` aus der Persistenz.

Aktuell maskiert durch Frontend-Spread (`TripWizard.svelte:62-66`), das die Felder bewahrt. Bricht bei jedem 3rd-Party-Client (CLI, Tests, MCP-Tools) und bei Frontend-Refactors, die das Spread vergessen.

## Root Cause (verifiziert)

`internal/handler/trip.go:131-159`:

```go
existing, err := s.LoadTrip(id)        // 117 — geladen, aber nur für 404-Check
// ...
var trip model.Trip                    // 131 — fresh empty struct
if err := json.NewDecoder(r.Body).Decode(&trip); err != nil { ... }
// trip ist jetzt das, was im Body stand — alles andere ist Zero-Value (nil maps)
trip.ID = id
// validateTrip prüft nur required fields
s.SaveTrip(trip)                       // 151 — bit-identisches Replace auf Disk
```

`SaveTrip` (`internal/store/store.go:144-156`) macht `json.MarshalIndent(trip)` + `os.WriteFile` — kein Merge. `omitempty` bei nil-Maps führt dazu, dass die Felder im JSON komplett verschwinden.

## Codebase-Messung: Wer liest die Felder?

`grep` über `internal/**/*.go` für `Aggregation|ReportConfig|WeatherConfig|DisplayConfig|AvalancheRegions`:

| Datei | Zugriffe | Bedeutung |
|-------|----------|-----------|
| `internal/model/trip.go` | Definitionen | — |
| `internal/model/location.go` | DisplayConfig (eigenes Feld auf Location) | nicht betroffen |
| `internal/model/subscription.go` | DisplayConfig (eigenes Feld) | nicht betroffen |
| `internal/handler/weather_config.go` | 6× `trip.DisplayConfig` Read/Write | dedizierte Endpoints |
| `internal/handler/weather_config_test.go` | 3× DisplayConfig | Tests |

**Befund:** Die Felder werden im Backend-Code als Pass-Through behandelt — sie werden nicht von der Wetter-Engine, der Aggregation oder Reports im Go-Backend gelesen. Das Domain-Modell `model.Trip` bleibt für den Bugfix unverändert.

## Strategie: DTO-Variante (vom PO genehmigt)

Im Handler einen Update-Request-Typ mit Pointer-Feldern einführen. Decoder kann damit "fehlt im Body" von "explizit gesetzt" unterscheiden. Merge auf `existing`, dann `SaveTrip`.

```go
// In internal/handler/trip.go
type tripUpdateRequest struct {
    Name             *string                 `json:"name"`
    Stages           *[]model.Stage          `json:"stages"`
    AvalancheRegions *[]string               `json:"avalanche_regions,omitempty"`
    Aggregation      *map[string]interface{} `json:"aggregation,omitempty"`
    WeatherConfig    *map[string]interface{} `json:"weather_config,omitempty"`
    DisplayConfig    *map[string]interface{} `json:"display_config,omitempty"`
    ReportConfig     *map[string]interface{} `json:"report_config,omitempty"`
}
```

Im Handler: Decode → für jedes nicht-nil Pointer-Feld Feld in `existing` überschreiben → `validateTrip(*existing)` → `SaveTrip(*existing)`.

**Was diese Variante NICHT verändert:**
- `model.Trip` Struktur
- `internal/handler/weather_config.go` (eigenständige Sub-Endpoints, anderer Zugriffspfad)
- Alle Lesepfade auf `trip.*` im Codebase
- Frontend-API-Kontrakt (gleiche Akzeptanz von Minimal- und Voll-Body)

## Scope

| Datei | Änderung | Geschätzte LoC |
|-------|----------|----------------|
| `internal/handler/trip.go` | `UpdateTripHandler` umbauen + DTO definieren | ~40 LoC neu, ~20 ersetzt |
| `internal/handler/trip_write_test.go` | 5-6 neue Test-Cases (Merge pro Feld + Minimal-Body) | ~80 LoC neu |

**Insgesamt:** 2 Dateien, ~120 LoC. Innerhalb des "Klein"-Scopes.

## Risiken

- **Niedrig:** Bestehende Tests (`TestUpdateTripHandler`, `TestUpdateTripHandlerNotFound`) verwenden Voll-Body und müssen weiter grün bleiben → Regressionsschutz vorhanden.
- **Mittel:** Bei `Stages` muss klar sein, dass `null`/`[]` ≠ "nicht gesendet". Aktuelle Validierung (`validateTrip`) verlangt `len(stages) >= 1` — der Merge muss deshalb `stages` nur ersetzen, wenn der Pointer non-nil ist. Wird in Spec festgehalten.
- **Niedrig:** Frontend sendet immer `name` und `stages` mit. Ein PUT, der nur `aggregation` ändert, ist heute nicht im Use-Case — sollte aber durch den Merge konsequent unterstützt werden.

## Akzeptanzkriterien (aus Issue #99)

- [x] Backend mergt fehlende `omitempty`-Felder aus `existing`, statt sie zu löschen.
- [x] PUT mit Minimal-Body (nur `id`, `name`, `stages`) lässt Configs aus `existing` unberührt.
- [x] Test deckt Merge-Verhalten ab (pro Feld + kombiniert).
