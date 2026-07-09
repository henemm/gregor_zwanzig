# Context: fix-1151-weather-config-merge

## Request Summary

Issue #1151 (Nebenbefund aus #1129): `PutTripWeatherConfigHandler` (`internal/handler/weather_config.go:37-74`,
Endpoint `PUT /api/trips/{id}/weather-config`) schreibt trotz seines Namens auf `trip.DisplayConfig` und ersetzt
dort blind die ganze Map (`trip.DisplayConfig = cfg`, Zeile 61). Gleiche Fehlerklasse wie BUG-DATALOSS-GR221
(#102/#1082/#1103/#1129). Aufgabe: prüfen, ob Merge (analog #1129) sinnvoll ist, und ggf. umsetzen.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/handler/weather_config.go` (Zeilen 37-74) | `PutTripWeatherConfigHandler` — der zu fixende Blind-Replace-Zweig (Zeile 61: `trip.DisplayConfig = cfg`) |
| `internal/handler/trip.go` (Zeilen 194-217, seit `bc1aa391`) | Bereits gefixtes Vorbild — identisches Merge-Pattern für `Aggregation`/`WeatherConfig`/`DisplayConfig`/`ReportConfig` im Haupt-Trip-PUT-Handler |
| `internal/model/trip.go` (Zeilen 93-96) | `Trip.DisplayConfig` vom Typ `map[string]interface{}` — gleicher Typ wie in #1129 |
| `internal/handler/weather_config_test.go` | Bestehende Tests: `TestPutTripWeatherConfig` (prüft nur `DisplayConfig != nil`), `TestPutTripWeatherConfigNotFound`, `TestPutTripWeatherConfigBadJSON`. Analoge Tests existieren auch für Location/Subscription-Varianten im selben File. |
| `internal/handler/weather_config_701_test.go` | Tests für die `extractActiveMetricIDs`/`SyncAlertRules`-Kopplung (Issue #701/#817) — arbeitet auf dem **rohen Decoded-Body `cfg`**, nicht auf `trip.DisplayConfig`, daher vom Merge-Fix unberührt. `TestPutTripWeatherConfig_PreservesExistingThreshold` seedet `DisplayConfig` mit genau 1 Key (`metrics`) → Merge-Verhalten bei diesem Test identisch zu Replace, keine Anpassung nötig. |
| `docs/specs/modules/fix_1129_config_map_merge.md` | Vorgänger-Spec — hält #1151 bereits explizit als "Known Limitations" / Folge-Issue fest, inkl. Formulierung "zweiter, unabhängiger Blind-Replace-Pfad derselben Fehlerklasse" |
| `docs/context/fix-1129-config-map-merge.md` | Vorgänger-Context — Abschnitt "Risks & Considerations" beschreibt #1151 bereits vollständig vorab |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` (Zeilen 392-409, 419, 443) | Einziger bekannter Trip-Client: `buildWeatherPayload()` spreadet `...(trip.display_config ?? {})` und sendet die volle Map — kein Partial-Send-Client bekannt (bestätigt Aussage aus Issue) |
| `CLAUDE.md` Abschnitt "Daten-Schema-Reworks (PFLICHT!)" | Projektregel: Read-Modify-Write mit Merge, niemals Replace |

## Existing Patterns

- **Feldweiser Merge bereits etabliert** (trip.go, seit #1103/#1129) — exaktes Muster:
  ```go
  if existing.DisplayConfig == nil {
      existing.DisplayConfig = map[string]interface{}{}
  }
  for k, v := range cfg {
      existing.DisplayConfig[k] = v
  }
  ```
  In `weather_config.go` entfällt der `req.DisplayConfig != nil`-Guard, da `cfg` hier bereits die gesamte
  Top-Level-Map des Requests ist (kein DTO mit Pointer-Feldern wie in `trip.go`).
- **Alert-Rule-Sync bleibt unverändert:** `extractActiveMetricIDs(cfg)` (Zeile 63) liest weiterhin aus dem
  rohen `cfg` (Request-Body), nicht aus dem gemergten `trip.DisplayConfig` — unabhängig vom Merge-Fix korrekt,
  keine Anpassung nötig.

## Dependencies

- **Upstream:** `store.LoadTrip` / `store.SaveTrip` (Datei-Persistenz pro Nutzer, `data/users/<user_id>/`)
- **Downstream:** `WeatherMetricsTab.svelte` liest/schreibt `trip.display_config` über diesen Endpoint;
  Server-Response (`json.NewEncoder(w).Encode(trip.DisplayConfig)`, Zeile 72) gibt nach Merge die **volle**
  gemergte Map zurück statt nur der gesendeten Teilmenge — Frontend erwartet bereits die volle Map als
  Response (siehe `onTripUpdate?.()`-Aufrufe im selben File), daher unkritisch.

## Existing Specs

- `docs/specs/modules/fix_1129_config_map_merge.md` — Vorgänger-Fix, exaktes Pattern-Vorbild

## Risks & Considerations

- **Kein Live-Bug belegt** — Frontend sendet aktuell stets die volle Map (Spread-Pattern in
  `buildWeatherPayload()`). Fix ist defensiv/präventiv wie schon bei #1129.
- **Kein Client bekannt, der bewusst Keys per PUT löschen will** — Merge ist konsequent, kein Trade-off.
- **Response-Verhalten:** Handler gibt nach dem Fix die gemergte (volle) Map zurück, nicht mehr nur den
  gesendeten Payload. Bei vollständigen Client-Payloads (aktueller Stand) identisch zum bisherigen Verhalten.
- **Nebenbefund (neuer Fund, noch kein Issue):** `PutLocationWeatherConfigHandler` (Zeile 100-134) und
  `PutSubscriptionWeatherConfigHandler` (Zeile 188-222) im selben File haben exakt dasselbe
  Blind-Replace-Muster (`loc.DisplayConfig = cfg` / `sub.DisplayConfig = cfg`) für Location- bzw.
  Subscription-Objekte. Nicht Teil von Issue #1151 (das ist explizit auf den Trip-Endpoint verengt) —
  wird als eigenständiges Folge-Issue gemeldet, analog dazu, wie #1129 zu #1151 geführt hat.

## Analysis (Plan/Sonnet, Step 3)

### Type
Bug (Fehlerklasse BUG-DATALOSS-GR221), Entscheidung fällt zugunsten Merge (siehe Empfehlung unten).

### Technischer Ansatz
`cfg` in `PutTripWeatherConfigHandler` ist bereits die vollständige, aus dem Request-Body decodierte
`map[string]interface{}` (kein DTO mit optionalen Pointer-Feldern wie bei `trip.go`). Der Fix ersetzt
Zeile 61 (`trip.DisplayConfig = cfg`) durch eine Merge-Schleife über `cfg`, analog zum bereits verifizierten
Pattern aus #1129. `extractActiveMetricIDs(cfg)` bleibt unverändert, da es unabhängig vom Ziel-Feld auf dem
rohen `cfg` operiert.

### Risiko-Bewertung
Identisch zu #1129: kein belegter Use-Case für gezieltes Key-Löschen, Frontend sendet volle Maps. Merge ist
strikt sicherer (verhält sich bei vollständigen Payloads identisch zu Replace, schützt zusätzlich vor
künftigen Teil-Update-Clients).

### Scope Assessment
- Produktivcode: `internal/handler/weather_config.go`, ~6-10 Zeilen (ein Merge-Block statt Zeile 61)
- Tests: `internal/handler/weather_config_test.go` (oder neue Datei), ~40-60 Zeilen — Merge-Beweis-Test mit
  Multi-Key-Seed + Teil-Update, analog `TestUpdateTripHandlerMergesDisplayConfig` aus #1129
- Risk Level: LOW — identisches, bereits zweimal bewährtes Pattern

### Empfehlung
Fix umsetzen — konsistent mit #1103/#1129, schließt eine durch CLAUDE.md explizit verbotene
Datenverlust-Klasse. Location/Subscription-Pendants als separates Folge-Issue melden, nicht in diesem Scope.

### Open Questions
- Keine — Ansatz eindeutig, zweifaches Vorbild vorhanden (#1103, #1129).
