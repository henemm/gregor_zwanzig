# Context: fix-1129-config-map-merge

## Request Summary

Issue #1129: `PUT /api/trips/{id}` mergt `report_config` bereits feldweise (Fix #1103),
ersetzt aber `aggregation`, `weather_config` und `display_config` weiterhin blind als
ganze Map. Gleiche Fehlerklasse wie BUG-DATALOSS-GR221 (#102). Aufgabe: pro Feld
entscheiden — feldweiser Merge (konsistent mit #1103) oder bewusste Replace-Semantik
(dokumentiert) — und umsetzen.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/handler/trip.go` (Zeilen 140-212) | `tripUpdateRequest`-DTO + `UpdateTripHandler` — die drei betroffenen Blind-Replace-Zweige (Z. 194-202) direkt neben dem bereits gefixten `report_config`-Merge-Block (Z. 203-212) |
| `internal/model/trip.go` | `Trip.Aggregation`, `Trip.WeatherConfig`, `Trip.DisplayConfig`, `Trip.ReportConfig` — alle vom Typ `map[string]interface{}` |
| `internal/handler/trip_write_test.go` (Zeilen 176-352) | Bestehende RMW-Tests aus #1103/#99: `seedTripWithConfigs`, `putUpdate`, `loadTripOrFail` Helper bereits vorhanden. `TestUpdateTripHandlerPreservesAggregation/WeatherConfig/DisplayConfig` (Feld komplett fehlt im Body → bleibt erhalten) und `TestUpdateTripHandlerReplacesAggregationWhenSent` (Feld wird gesendet → wird ersetzt) — Letztere dokumentiert aktuell explizit das **Blind-Replace**-Verhalten als Ist-Zustand. Test bleibt nach Fix grün (Seed hat nur 1 Key in `aggregation`), muss aber um einen echten Merge-Beweis (mehrere Keys, nur einer gesendet) ergänzt werden. |
| `internal/handler/fix_go_rmw_merge_1082_1103_test.go` | Referenz-Testmuster für Merge-Nachweis: Trip mit Multi-Key-Map anlegen → Teil-Update senden → alle Keys prüfen |
| `docs/specs/modules/fix_go_rmw_merge_1082_1103.md` | Vorgänger-Spec. Abschnitt "Was NICHT Teil dieses Workflows ist" hält explizit fest, dass `aggregation`/`weather_config`/`display_config` bewusst außerhalb des #1103-Scopes blieben — genau das ist jetzt der Auftrag von #1129. |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` (Z. 79-94) | Baut `display_config` clientseitig per Spread (`...trip.display_config, channels: ...`) zusammen, bevor es per PUT gesendet wird — sendet also volle Maps, kein Partial-Send-Client bekannt |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` (Z. 404, 419-445) | Gleiches Spread-Muster für `display_config`; `weather_config` läuft primär über einen **eigenen** Endpoint `PUT /api/trips/{id}/weather-config` (`internal/handler/weather_config.go`), nicht über den Haupt-Trip-PUT |
| `CLAUDE.md` Abschnitt "Daten-Schema-Reworks (PFLICHT!)" | Projektregel: Read-Modify-Write mit Merge, **niemals Replace**, bei Persistenz-Änderungen — gilt generell für Trip/Model-Felder |

## Existing Patterns

- **Feldweiser Merge für Maps** bereits etabliert für `report_config` (trip.go:203-212):
  ```go
  if existing.ReportConfig == nil {
      existing.ReportConfig = map[string]interface{}{}
  }
  for k, v := range *req.ReportConfig {
      existing.ReportConfig[k] = v
  }
  ```
  Dieses exakte Muster lässt sich unverändert auf `Aggregation`, `WeatherConfig`, `DisplayConfig` übertragen.
- **Test-Helper wiederverwendbar:** `seedTripWithConfigs`, `putUpdate`, `loadTripOrFail` in `trip_write_test.go` decken bereits alle vier Maps ab — nur die Seed-Daten brauchen zusätzliche Keys pro Map, um einen echten Merge-Beweis (mehrere Keys, Teil-Update) zu ermöglichen.

## Dependencies

- **Upstream:** `store.LoadTrip` / `store.SaveTrip` (Datei-Persistenz pro Nutzer, `data/users/<user_id>/`)
- **Downstream:** Frontend liest `trip.aggregation` / `trip.weather_config` / `trip.display_config` u. a. in `WeatherMetricsTab.svelte`, `BriefingScheduleTab.svelte`, `MetricsPreview.svelte`, `PresetRow.svelte`; Risk-Engine/Reporting nutzt vermutlich `aggregation`/`weather_config` serverseitig (nicht Teil dieses Scopes, nur lesend betroffen)

## Existing Specs

- `docs/specs/modules/fix_go_rmw_merge_1082_1103.md` — Vorgänger-Fix, hält #1129 explizit als "Known Consideration" / Folge-Issue fest

## Risks & Considerations

- **Kein Live-Bug belegt** (lt. Issue) — Frontend sendet aktuell alle drei Maps vollständig (Spread-Pattern). Fix ist defensiv/präventiv, nicht Reaktion auf einen beobachteten Datenverlust.
- **Kein Client bekannt, der bewusst Keys per PUT löschen will** — daher spricht nichts für Replace-Semantik; Merge ist die konsistente, projektweit vorgeschriebene Wahl (CLAUDE.md).
- Bestehender Test `TestUpdateTripHandlerReplacesAggregationWhenSent` muss ggf. umbenannt/erweitert werden, da der Name nach dem Fix irreführend ist (Verhalten ist Merge, nicht Replace — nur bei diesem speziellen Testdatensatz mit nur einem Key ist das Ergebnis identisch).
- **Nebenbefund (eigenes Folge-Issue nötig):** `PUT /api/trips/{id}/weather-config` (`internal/handler/weather_config.go:37-74`, `PutTripWeatherConfigHandler`) schreibt trotz des Namens auf `trip.DisplayConfig` (nicht `WeatherConfig`!) und ersetzt dort **ebenfalls blind** die ganze Map (`trip.DisplayConfig = cfg`, Zeile 61) — ein zweiter, unabhängiger Blind-Replace-Pfad für `display_config`, der von #1129 (Scope: nur `trip.go`) nicht erfasst wird. Die Frontend-Clients dieses Endpoints (`WeatherMetricsTab.svelte`, `BriefingScheduleTab.svelte`) bauen zwar clientseitig per Spread die volle Map zusammen, aber serverseitig bleibt die Lücke bestehen (gleiche Fehlerklasse wie #1082/#1103, falls je ein Client nur ein Teil-Objekt sendet). **Nicht** Teil dieses Workflows — als Issue #1151 gemeldet.

## Analysis (Plan/Sonnet, Step 3)

### Type
Bug (Fehlerklasse BUG-DATALOSS-GR221), gleichzeitig Design-Entscheidung (Merge vs. bewusster Replace) — Entscheidung fällt zugunsten Merge (siehe unten).

### Technischer Ansatz
Bestätigt: Alle vier Felder (`Aggregation`, `WeatherConfig`, `DisplayConfig`, `ReportConfig`) sind identisch typisiert (`map[string]interface{}`, `internal/model/trip.go:93-96`). Keines enthält Arrays auf oberster Ebene, keine abweichende Nil-Semantik. Das `report_config`-Merge-Pattern ist 1:1 auf alle drei Felder übertragbar — keine Sonderbehandlung nötig. Einzige Ausnahme: `PutTripWeatherConfigHandler` (weather_config.go:61) ersetzt `DisplayConfig` separat blind — das ist #1151, nicht hier zu fixen.

### Risiko-Bewertung
Kein legitimer/belegter Use-Case für gezieltes Key-Löschen gefunden. Frontend sendet stets vollständige Maps (Spread-Pattern). Sollte künftig gezieltes Löschen gebraucht werden, bräuchte es ein explizites Sentinel — das unterstützt der bestehende `report_config`-Merge ebenfalls nicht, also konsistentes, bereits akzeptiertes Risiko.

### Scope Assessment
- Produktivcode: `internal/handler/trip.go`, ~15-20 Zeilen (drei Merge-Blöcke analog Zeile 203-212)
- Tests: `internal/handler/trip_write_test.go`, ~60-90 Zeilen (Multi-Key-Seeds + 3 neue Merge-Beweis-Tests + Umbau des Replace-Tests)
- Risk Level: LOW (bekanntes, bereits bewährtes Pattern im selben File)

### Test-Empfehlung
- `TestUpdateTripHandlerReplacesAggregationWhenSent` → umbenennen zu `TestUpdateTripHandlerMergesAggregationWhenSent`; Seed auf ≥2 Keys erweitern (z.B. `{"strategy":"max_per_stage","window_days":3}`), Body sendet nur `strategy`, Assertion prüft `window_days` bleibt erhalten.
- Analog neue Tests `TestUpdateTripHandlerMergesWeatherConfig` / `TestUpdateTripHandlerMergesDisplayConfig` mit je ≥2 Keys pro Map.
- Bestehende `TestUpdateTripHandlerPreserves*`-Tests bleiben unverändert gültig (Feld fehlt im Body → bleibt erhalten, unabhängig von Merge/Replace).

### Empfehlung
Fix umsetzen — identisches, bereits bewährtes Merge-Pattern, geringer Aufwand, schließt eine durch Projektregel explizit verbotene Datenverlust-Klasse (CLAUDE.md "Daten-Schema-Reworks").

### Open Questions
- Keine offenen Fragen — Ansatz ist eindeutig, Vorbild existiert im selben File.
