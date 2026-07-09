---
entity_id: fix_1151_weather_config_merge
type: module
created: 2026-07-09
updated: 2026-07-09
status: implemented
version: "1.0"
tags: [bug, data-loss, go, persistence, read-modify-write]
---

# Fix: Blind-Replace in PutTripWeatherConfigHandler (#1151)

## Approval

- [ ] Approved

## Purpose

`PUT /api/trips/{id}/weather-config` (`PutTripWeatherConfigHandler`) schreibt
trotz seines Namens auf `trip.DisplayConfig` und ersetzt dort blind die ganze
Map (`trip.DisplayConfig = cfg`), sobald ein Request eintrifft. Ein Teil-Update
(z.B. nur `metrics` gesendet) löscht dadurch alle anderen zuvor gespeicherten
Keys von `display_config` — gleiche Fehlerklasse wie BUG-DATALOSS-GR221 (#102)
und der bereits gefixte Zwilling in `internal/handler/trip.go` (#1129,
Commit `bc1aa391`). Ziel: den Blind-Replace in `PutTripWeatherConfigHandler`
auf das bereits etablierte, verifizierte Feld-Level-Merge-Pattern umstellen.

## Source

- **File:** `internal/handler/weather_config.go` (`PutTripWeatherConfigHandler`, Zeilen 37-74)
- **Identifier:** `PutTripWeatherConfigHandler`

Schicht: **Go-API** (`internal/`), Production-API Port 8090.

## Estimated Scope

- **LoC:** ~8-12 (Produktivcode, ein Merge-Block statt Zeile 61), + ~40-60 Zeilen Tests
- **Files:** 1 Produktivdatei (`internal/handler/weather_config.go`), 1 Testdatei (`internal/handler/weather_config_test.go` oder neue Datei `internal/handler/weather_config_1151_test.go`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/trip.go` (`LoadTrip`, `SaveTrip`) | store | RMW-Basis für Trip-Weather-Config-Update |
| `internal/model/trip.go` (`DisplayConfig map[string]interface{}`) | model | Ziel-Map des Feld-Merges |
| `internal/model` (`SyncAlertRules`, `extractActiveMetricIDs`) | logic | Alert-Rule-Sync liest weiterhin aus rohem `cfg`, bleibt unverändert korrekt (kein Merge-relevanter Pfad) |
| `docs/specs/modules/fix_1129_config_map_merge.md` | spec | Vorgänger-Fix, etabliert das identische Merge-Pattern für `aggregation`/`weather_config`/`display_config` in `trip.go` |

## Implementation Details

Aktueller Blind-Replace (`internal/handler/weather_config.go`, Zeile 54-64):

```go
var cfg map[string]interface{}
if err := json.NewDecoder(r.Body).Decode(&cfg); err != nil {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(400)
    w.Write([]byte(`{"error":"bad_request"}`))
    return
}
trip.DisplayConfig = cfg
// Sync alert_rules with active weather metrics (Issue #701)
activeIDs := extractActiveMetricIDs(cfg)
```

**Fix (Feld-Level-Merge, analog `trip.go`/#1129):**

```go
var cfg map[string]interface{}
if err := json.NewDecoder(r.Body).Decode(&cfg); err != nil {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(400)
    w.Write([]byte(`{"error":"bad_request"}`))
    return
}
if trip.DisplayConfig == nil {
    trip.DisplayConfig = map[string]interface{}{}
}
for k, v := range cfg {
    trip.DisplayConfig[k] = v
}
// Sync alert_rules with active weather metrics (Issue #701)
activeIDs := extractActiveMetricIDs(cfg)
```

Anders als in `trip.go` gibt es hier keinen `req.DisplayConfig != nil`-Guard,
da `cfg` bereits die gesamte, aus dem Request-Body decodierte Top-Level-Map
ist (kein DTO mit optionalen Pointer-Feldern). Der `nil`-Guard für
`trip.DisplayConfig` selbst bleibt erhalten (erster PUT auf einen frischen
Trip ohne vorherige `display_config`).

`extractActiveMetricIDs(cfg)` liest weiterhin aus dem rohen `cfg`
(Request-Body), nicht aus dem gemergten `trip.DisplayConfig` — dieser Aufruf
bleibt unverändert, da er unabhängig vom Ziel-Feld korrekt ist (Issue #701).

Die Response (`json.NewEncoder(w).Encode(trip.DisplayConfig)`, Zeile 72) gibt
nach dem Fix die gemergte (volle) Map zurück statt nur des gesendeten
Payloads. Bei vollständigen Client-Payloads (aktueller Stand des einzigen
bekannten Clients, `WeatherMetricsTab.svelte`) ist das Ergebnis identisch zum
bisherigen Verhalten.

## Expected Behavior

- **Input:** `PUT /api/trips/{id}/weather-config` mit einem JSON-Body, der nur
  eine Teilmenge der zuvor gespeicherten `display_config`-Keys enthält.
- **Output:** Nur die gesendeten Keys werden geändert/hinzugefügt; alle
  anderen zuvor gespeicherten Keys von `trip.display_config` bleiben
  unverändert erhalten. Response enthält die vollständige, gemergte Map.
- **Side effects:** `AlertRules` werden weiterhin per `SyncAlertRules`
  basierend auf `extractActiveMetricIDs(cfg)` (rohes `cfg`, unverändert)
  aktualisiert — keine Änderung an diesem Verhalten.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit `display_config = {"theme":"compact","metrics":[{"metric_id":"temperature","enabled":true}]}` /
  When `PUT /api/trips/{id}/weather-config` mit Body `{"metrics":[{"metric_id":"wind","enabled":true}]}` gesendet wird (nur `metrics`, kein `theme`) /
  Then enthält der gespeicherte Trip `display_config["theme"] == "compact"` weiterhin (unverändert) und `display_config["metrics"]` reflektiert den neuen Payload.
  - Test: Go-Handler-Test gegen echten Store (Tempdir, kein Mock) — `TestPutTripWeatherConfigMergesDisplayConfig`, Seed mit ≥2 Top-Level-Keys in `display_config`, Teil-PUT mit nur 1 Key, beide Keys nach `LoadTrip` geprüft. Analog `TestUpdateTripHandlerMergesDisplayConfig` aus #1129.

- **AC-2:** Given die bestehenden Tests `TestPutTripWeatherConfig`, `TestPutTripWeatherConfigNotFound`, `TestPutTripWeatherConfigBadJSON` (`internal/handler/weather_config_test.go`) sowie die `extractActiveMetricIDs`/`SyncAlertRules`-Tests in `internal/handler/weather_config_701_test.go` /
  When der Merge-Fix implementiert ist /
  Then bleiben alle diese Tests unverändert grün (Regressionsschutz) — insbesondere bleibt `TestPutTripWeatherConfig_PreservesExistingThreshold` grün, da `extractActiveMetricIDs(cfg)` weiterhin auf dem rohen Request-Body operiert, nicht auf der gemergten Map.
  - Test: `go test ./internal/handler/... -run TestPutTripWeatherConfig` und `go test ./internal/handler/... -run TestPutTripWeatherConfig_PreservesExistingThreshold` laufen ohne Anpassung grün durch.

- **AC-3:** Given ein neu erstellter Trip ohne vorheriges `display_config` (`nil`) /
  When `PUT /api/trips/{id}/weather-config` mit Body `{"metrics":[{"metric_id":"temperature","enabled":true}]}` gesendet wird (erster PUT) /
  Then wird `display_config` korrekt mit dem gesendeten Key initialisiert (kein Nil-Pointer-Panic, kein leeres Ergebnis) — Verhalten identisch zum bisherigen `TestPutTripWeatherConfig`.
  - Test: bestehender Test `TestPutTripWeatherConfig` bleibt unverändert grün und beweist diesen Fall bereits (Seed-Trip ohne `display_config`, erster PUT).

## Known Limitations

- **Kein Sentinel für gezieltes Key-Löschen:** Wie beim bereits etablierten
  Merge-Pattern (#1103, #1129) gibt es keinen Mechanismus, um einen Key
  gezielt aus `display_config` zu entfernen (z.B. `null`-Sentinel). Kein
  belegter Use-Case dafür bekannt — konsistentes, bereits akzeptiertes Risiko.
- **`PutLocationWeatherConfigHandler` und `PutSubscriptionWeatherConfigHandler`
  (`internal/handler/weather_config.go`, Zeilen 100-134 und 188-222) sind
  explizit außerhalb dieses Scopes.** Beide Handler haben dasselbe
  Blind-Replace-Muster (`loc.DisplayConfig = cfg` / `sub.DisplayConfig = cfg`)
  für Location- bzw. Subscription-Objekte — ein dritter und vierter,
  unabhängiger Blind-Replace-Pfad derselben Fehlerklasse. Bereits als
  eigenständiges Folge-Issue **#1159** gemeldet, wird hier **nicht**
  mitgefixt (Scope dieses Fixes ist ausschließlich `PutTripWeatherConfigHandler`).
- **Kein Live-Bug belegt:** Der einzige bekannte Client
  (`frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`,
  `buildWeatherPayload()`) sendet aktuell stets die volle
  `display_config`-Map (Spread-Pattern). Fix ist defensiv/präventiv, analog
  zu #1129.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Bugfix-Konsistenz — überträgt das bereits etablierte
  und verifizierte Merge-Pattern aus `trip.go` (#1103/#1129) unverändert auf
  einen strukturell identischen zweiten Handler im selben Modul. Keine neue
  Architektur- oder Datenmodell-Entscheidung, kein neuer Trade-off. Konsistent
  mit der Vorgänger-Spec `fix_1129_config_map_merge.md`, die ebenfalls keinen
  ADR-Abschnitt für dieses Pattern anlegt.

## Changelog

- 2026-07-09: Initial spec created
- 2026-07-09: Implementiert und durch Adversary verifiziert (VERIFIED)
