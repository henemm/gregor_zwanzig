# Context: feat-1329-ac8-budget-sichtbar

## Request Summary

Letzter offener Rest von Issue #1329: der Go-Status-Endpoint `/api/scheduler/status` soll
einen `forecast_budget`-Block mit `calls_today`, `cache_hit_ratio` und `throttle_level`
liefern, damit ein leerlaufendes open-meteo-Tageskontingent auffällt, **bevor** Briefings
ausbleiben. AC-8 ist in `docs/specs/modules/fix_1329_forecast_cache_budget.md:351`
bereits freigegeben spezifiziert — dies ist reine Umsetzung, keine neue Spec.

Vorbedingung für #1439 (Starkregen-Kurzfrist): dessen `minutely_15`-Abrufe ziehen
zusätzliches Kontingent, das ohne Verbrauchssicht unbeobachtbar wäre.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/forecast_budget.py:93` | `snapshot()` — beim Bau von Scheibe C **ausdrücklich für AC-8 vorbereitet**; liefert `date`, `calls_today`, `daily_budget`, `usage_ratio`, `cache_hits`, `cache_misses`, `status`. Wird bisher nur in Tests verwendet, von keinem Endpoint. |
| `src/services/forecast_budget.py:40-42` | Die drei zu spiegelnden Zahlen: `DAILY_BUDGET = 9000`, `POLLING_THRESHOLD = 0.80`, `BRIEFING_ONLY_THRESHOLD = 0.95`. |
| `data/diagnostics/forecast_budget.json` | Persistierter Zählerstand, Format `{"date", "calls": {"openmeteo": N}, "cache_hits", "cache_misses"}`. Pfad prod/staging getrennt über `app.loader.get_data_root()`. |
| `internal/scheduler/scheduler.go:611-679` | `Scheduler.Status() map[string]any` — hier wird der neue Top-Level-Key eingehängt (`:676-677` zeigen `briefing_health` und `warn_service_health` als Vorbild). |
| `internal/scheduler/warn_service_health.go:189-237` | **Das direkte Vorbild:** `meteoalarmBudgetFile`-Struct + `meteoalarmBudgetSnapshot(path)` mit fail-soft `unavailable`-Default. Gleiche Aufgabe, gleiche Bauform. |
| `internal/handler/scheduler_status.go:11-16` | HTTP-Handler, reines `Encode(sched.Status())` — braucht keine Änderung. |
| `internal/router/router.go:198` | Route `/api/scheduler/status` — unverändert. |
| `internal/scheduler/warn_service_health_test.go:107-146` | Test-Vorbild: JSON-Fixture per `os.WriteFile` in `t.TempDir()/diagnostics/`, Scheduler über `store.New(tmpDir, "default")`, Felder per Type-Assertion auf `map[string]any`. |
| `docs/specs/modules/fix_1329_forecast_cache_budget.md:280-309,351,450-452` | AC-8 im Wortlaut, das Ziel-JSON, die Stufennamen und die Test-Vorgabe. |

## Existing Patterns

- **Budget-JSON von Go direkt lesen, fail-soft:** `meteoalarmBudgetSnapshot` liefert bei
  leerem Pfad, Lesefehler **und** kaputtem JSON denselben Default-Block mit
  `status: "unavailable"` — nie ein Panic, nie ein halb gefüllter Block. Erfolgsfall setzt
  `status: "ok"`. Genau diese Semantik fordert AC-8 auch.
- **Status-Antwort ist eine `map[string]any`**, kein benanntes Struct — neuer Block wird als
  ein Literal-Key ergänzt.
- **Python bleibt Entscheidungslogik, Go zeigt nur an** (Spec `:303-309`): Go leitet
  `throttle_level` aus `usage_ratio` ab, trifft aber keine eigene Drossel-Entscheidung.
- **Fail-open des Zählers:** `ForecastBudgetGate._safe_update` verschluckt jeden Fehler
  (`:214-215`). Ein kaputter Zähler darf nie einen Versand blockieren — und folglich auch
  die Anzeige nie einen Statusabruf.

## Dependencies

- **Upstream (was wir lesen):** die von `ForecastBudgetGate` geschriebene Zählerdatei unter
  `<store.DataDir>/diagnostics/forecast_budget.json`. Kein Netz, kein Python-Prozess nötig —
  der Statusabruf funktioniert auch, wenn `gregor-python` hängt.
- **Downstream (was uns nutzt):** `check-gregor20.sh` in `henemm-infra` liest den
  Status-Endpoint; ein neuer Top-Level-Key ist additiv und bricht dort nichts. Eine
  Auswertung des neuen Blocks (Alarm bei hoher Auslastung) wäre eine eigene, spätere
  Arbeit im Infra-Repo.

## Existing Specs

- `docs/specs/modules/fix_1329_forecast_cache_budget.md` — AC-8 (dieser Workflow),
  AC-1 bis AC-7 und AC-9 sind live.
- `docs/specs/modules/fix_1329_c2_radar_nowcast_cache.md` — Radar-Pfad zählt gegen dasselbe
  Budget (dortiges AC-8), erklärt, warum `record_cache_hit/miss` zwei Aufrufer hat.
- `docs/specs/modules/fix_1397_meteoalarm_coverage_budget.md` — das gespiegelte Vorbild.

## Risks & Considerations

1. **Die gespiegelten Zahlen driften unbewacht.** Das Vorbild trägt den Kommentar
   „mirrors MeteoAlarmBudgetGate.DEFAULT_DAILY_BUDGET" (`warn_service_health.go:170`),
   aber `grep -rn "DEFAULT_DAILY_BUDGET" --include=*_test.go` findet **keinen** Test. Wird
   die Python-Zahl geändert, zeigt der Status still eine falsche Auslastung. Gegenmittel in
   diesem Workflow: ein Paritäts-Test, der die drei Zahlen aus `forecast_budget.py` liest
   und gegen die Go-Konstanten prüft (Muster: Paritäts-Test gegen `passkey.go` aus #1364).
   Ein Kommentar ist eine Bitte, ein Test ist eine Zusicherung.
2. **`cache_hit_ratio` existiert nirgends fertig.** Weder `weather_cache.stats()`
   (`src/services/weather_cache.py:208` — nur `total_entries`/`max_entries`/`ttl_seconds`)
   noch `radar_cache.py` (kein Zähler) noch ein HTTP-Endpoint liefern es. Es muss aus
   `cache_hits / (cache_hits + cache_misses)` abgeleitet werden. **Division durch Null bei
   frisch zurückgesetztem Tageszähler ist der naheliegende Fehler** — beide Zähler sind
   dann 0.
3. **Go-Tests liegen co-located** (`internal/scheduler/*_test.go`), lassen sich in Phase
   `phase5_tdd_red` also nicht anlegen (`edit_gate` blockt `.go` außerhalb von
   `test`/`tests`-Verzeichnissen). Dokumentierter Ausweg ohne Gate-Eingriff:
   `go test -overlay` mit der Testdatei außerhalb des Repos, RED-Artefakt registrieren,
   danach wandert die Datei an ihren co-located Platz.
4. **`go` ist nicht im PATH** — `/usr/local/go/bin/go` explizit aufrufen.
5. **Der Zähler ist pro Datenraum getrennt.** Prod, Staging und der Entwicklungs-Datenraum
   haben eigene Dateien mit stark abweichenden Werten. Ein Test darf niemals gegen den
   echten Datenraum prüfen, immer gegen `t.TempDir()`.
6. **Beobachtung, ausdrücklich NICHT Teil dieser Arbeit:** Prod meldet heute 164 Calls bei
   **0** Cache-Treffern, während der Entwicklungs-Datenraum 483 Treffer zeigt. Der Zähler
   funktioniert also grundsätzlich. Ob der Cache auf Prod wirklich nie trifft (plausibel:
   Dienst-Neustarts durch die heutigen Deploys, der Cache lebt nur im Arbeitsspeicher) oder
   etwas anderes vorliegt, ist **unbewiesen**. Genau das soll diese Anzeige messbar machen —
   erst bauen, dann über Tage beobachten, dann entscheiden. Vorher wäre es Spekulation.
