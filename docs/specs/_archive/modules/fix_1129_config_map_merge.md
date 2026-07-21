---
entity_id: fix_1129_config_map_merge
type: module
created: 2026-07-09
updated: 2026-07-09
status: implemented
version: "1.0"
tags: [bug, data-loss, go, persistence, read-modify-write]
---

# Fix: Blind-Replace bei aggregation/weather_config/display_config (#1129)

## Approval

- [ ] Approved

## Purpose

`PUT /api/trips/{id}` mergt `report_config` seit #1103 bereits feldweise, ersetzt
aber `aggregation`, `weather_config` und `display_config` weiterhin blind als
ganze Map, sobald der jeweilige Key im Request-Body vorhanden ist. Teil-Updates
löschen dadurch alle anderen Keys der jeweiligen Map — gleiche Fehlerklasse wie
BUG-DATALOSS-GR221 (#102). Ziel: die drei verbliebenen Blind-Replace-Zweige auf
das bereits etablierte Merge-Pattern von `report_config` umstellen.

## Source

- **File:** `internal/handler/trip.go` (`UpdateTripHandler`, Zeilen 194-202)
- **Identifier:** `UpdateTripHandler`

Schicht: **Go-API** (`internal/`), Production-API Port 8090.

## Estimated Scope

- **LoC:** ~15-20 (Produktivcode), + ~60-90 Zeilen Tests
- **Files:** 1 Produktivdatei (`internal/handler/trip.go`), 1 Testdatei (`internal/handler/trip_write_test.go`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/trip.go` (`LoadTrip`, `SaveTrip`) | store | RMW-Basis für Trip-Update |
| `internal/model/trip.go` (`Aggregation`, `WeatherConfig`, `DisplayConfig` je `map[string]interface{}`) | model | Ziel-Maps des Feld-Merges |
| `docs/specs/modules/fix_go_rmw_merge_1082_1103.md` | spec | Vorgänger-Fix, etabliert das identische Merge-Pattern für `report_config` |

## Implementation Details

Aktueller Blind-Replace (trip.go:194-202):

```go
if req.Aggregation != nil {
    existing.Aggregation = *req.Aggregation
}
if req.WeatherConfig != nil {
    existing.WeatherConfig = *req.WeatherConfig
}
if req.DisplayConfig != nil {
    existing.DisplayConfig = *req.DisplayConfig
}
```

**Fix (Feld-Level-Merge, analog `report_config` Zeile 203-212):**

```go
if req.Aggregation != nil {
    if existing.Aggregation == nil {
        existing.Aggregation = map[string]interface{}{}
    }
    for k, v := range *req.Aggregation {
        existing.Aggregation[k] = v
    }
}
if req.WeatherConfig != nil {
    if existing.WeatherConfig == nil {
        existing.WeatherConfig = map[string]interface{}{}
    }
    for k, v := range *req.WeatherConfig {
        existing.WeatherConfig[k] = v
    }
}
if req.DisplayConfig != nil {
    if existing.DisplayConfig == nil {
        existing.DisplayConfig = map[string]interface{}{}
    }
    for k, v := range *req.DisplayConfig {
        existing.DisplayConfig[k] = v
    }
}
```

Keine Sonderbehandlung nötig: alle drei Felder sind identisch typisiert
(`map[string]interface{}`, `internal/model/trip.go`), keine Arrays auf oberster
Ebene, keine abweichende Nil-Semantik gegenüber `report_config`.

## Expected Behavior

- **Input:** `PUT /api/trips/{id}` mit `aggregation`/`weather_config`/`display_config`
  jeweils nur teilweise gesendet (z.B. nur ein Key von zweien).
- **Output:** Nur der gesendete Key wird geändert; alle anderen zuvor gespeicherten
  Keys derselben Map bleiben unverändert erhalten.
- **Side effects:** keine über die Ziel-Trip-Datei hinaus.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit `aggregation = {"strategy":"max_per_stage","window_days":3}` /
  When `PUT /api/trips/{id}` mit Body `{"aggregation":{"strategy":"min_per_stage"}}` gesendet wird /
  Then enthält der gespeicherte Trip `aggregation` = `{"strategy":"min_per_stage","window_days":3}` (nur `strategy` geändert, `window_days` bleibt erhalten).
  - Test: Go-Handler-Test gegen echten Store (Tempdir, kein Mock) — `TestUpdateTripHandlerMergesAggregationWhenSent` (umbenannt/erweitert aus `TestUpdateTripHandlerReplacesAggregationWhenSent`), Seed mit 2 Keys, Teil-PUT, beide Keys nach Load geprüft.

- **AC-2:** Given ein Trip mit `weather_config = {"profile":"skitouren","provider":"geosphere"}` /
  When `PUT /api/trips/{id}` mit Body `{"weather_config":{"profile":"wandern"}}` gesendet wird /
  Then enthält der gespeicherte Trip `weather_config` = `{"profile":"wandern","provider":"geosphere"}` (nur `profile` geändert, `provider` bleibt erhalten).
  - Test: Go-Handler-Test gegen echten Store — neuer Test `TestUpdateTripHandlerMergesWeatherConfig`, Seed mit 2 Keys, Teil-PUT, beide Keys nach Load geprüft.

- **AC-3:** Given ein Trip mit `display_config = {"theme":"compact","channels":["email"]}` /
  When `PUT /api/trips/{id}` mit Body `{"display_config":{"theme":"full"}}` gesendet wird /
  Then enthält der gespeicherte Trip `display_config` = `{"theme":"full","channels":["email"]}` (nur `theme` geändert, `channels` bleibt erhalten).
  - Test: Go-Handler-Test gegen echten Store — neuer Test `TestUpdateTripHandlerMergesDisplayConfig`, Seed mit 2 Keys, Teil-PUT, beide Keys nach Load geprüft.

- **AC-4:** Given ein Trip mit vollständig befülltem `aggregation`/`weather_config`/`display_config`/`report_config` /
  When `PUT /api/trips/{id}` mit einem Body gesendet wird, der keinen dieser vier Keys enthält (nur `name`/`stages`) /
  Then bleiben alle vier Maps unverändert erhalten (Regressionsschutz — bestehendes Preserve-Verhalten darf durch den Merge-Fix nicht brechen).
  - Test: bestehende Tests `TestUpdateTripHandlerPreservesAggregation`/`PreservesWeatherConfig`/`PreservesDisplayConfig`/`PreservesReportConfig` sowie `TestUpdateTripHandlerKeepsAllConfigsOnNameOnlyUpdate` in `internal/handler/trip_write_test.go` bleiben unverändert und grün.

## Was NICHT Teil dieses Workflows ist (Known Limitations)

- **Kein Sentinel für gezieltes Key-Löschen:** Wie beim bereits etablierten
  `report_config`-Merge (#1103) gibt es keinen Mechanismus, um einen Key gezielt
  aus der Map zu entfernen (z.B. `null`-Sentinel). Kein belegter Use-Case dafür
  bekannt — konsistentes, bereits akzeptiertes Risiko.
- **`PUT /api/trips/{id}/weather-config` (`internal/handler/weather_config.go`,
  `PutTripWeatherConfigHandler`) ist explizit außerhalb dieses Scopes.** Dieser
  separate Endpoint schreibt (trotz seines Namens) auf `trip.DisplayConfig` und
  ersetzt dort ebenfalls blind die ganze Map (Zeile 61) — ein zweiter,
  unabhängiger Blind-Replace-Pfad derselben Fehlerklasse. Als eigener Nebenbefund
  bereits unter **Issue #1151** gemeldet, wird hier **nicht** mitgefixt (Scope
  dieses Fixes ist ausschließlich `internal/handler/trip.go`).

## Test-Plan

Alle Tests in `internal/handler/trip_write_test.go`, gegen echten Store
(Tempdir, keine Mocks) — konsistent mit `fix_go_rmw_merge_1082_1103_test.go`:

1. `TestUpdateTripHandlerReplacesAggregationWhenSent` → **umbenennen** zu
   `TestUpdateTripHandlerMergesAggregationWhenSent`; Seed-Daten (`seedTripWithConfigs`
   bzw. lokaler Seed) um einen zweiten Key erweitern (z.B.
   `{"strategy":"max_per_stage","window_days":3}`), Body sendet nur `strategy`,
   Assertion prüft zusätzlich, dass `window_days` erhalten bleibt (Merge-Beweis,
   nicht nur Replace-Zufallstreffer bei 1-Key-Map).
2. Neuer Test `TestUpdateTripHandlerMergesWeatherConfig` — analoges Muster mit
   ≥2 Keys in `weather_config`.
3. Neuer Test `TestUpdateTripHandlerMergesDisplayConfig` — analoges Muster mit
   ≥2 Keys in `display_config`.
4. Bestehende `TestUpdateTripHandlerPreserves*`-Tests (Zeilen 221-304) sowie
   `TestUpdateTripHandlerKeepsAllConfigsOnNameOnlyUpdate` (Zeilen 325-352) bleiben
   unverändert bestehen und müssen weiterhin grün sein (Regressionsschutz, AC-4).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Bugfix-Konsistenz — überträgt ein bereits etabliertes und
  akzeptiertes Muster (`report_config`-Merge aus #1103) unverändert auf drei
  strukturell identische Felder im selben Handler. Keine neue Architektur- oder
  Datenmodell-Entscheidung, kein neuer Trade-off. Die Vorgänger-Spec
  (`fix_go_rmw_merge_1082_1103.md`) enthält ebenfalls keinen ADR-Abschnitt für
  das identische Pattern — konsistent damit wird hier ebenfalls keiner angelegt.

## Changelog

- 2026-07-09: Initial spec created
- 2026-07-09: Implementiert und durch Adversary verifiziert (VERIFIED)
