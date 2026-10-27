# Context: feat-1539-s1b-s2-abruf-baustein

## Request Summary
Zweiter Workflow zu #1539 (nach S0+S1a, live 2026-10-08, Prod `2dffd1e1d`, PR #2537):
**S1b** — Warn-Feed-Cache und Abruf-Kontingente gegen parallele Zugriffe absichern (inkl. C4-64);
**S2** — ein gemeinsamer, begrenzter Abruf-Baustein `src/services/parallel_fetch.py` plus Single-flight
im Wetter-Cache. Noch **keine** Schleife wird umgestellt (das ist S3/S4) — dieser Workflow schafft die
sicheren Bausteine. Gesamtplan und Vorher-Messung: `docs/context/feat-1539-parallele-abrufe.md`.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/official_alerts/warn_egress.py:389-404` | `cached_fetch` — Check (:443-460) → Fetch-Schleife (:468-537) → `_store_entry` (:177-189) / Exception-Zweig (:478). **Kein Lock, kein Dedupe.** TTL 1800/60/86400 s (:40/:41/:46); 429-Retry schläft vor dem Schreiben (:534) |
| `official_alerts/dpc.py:51-52,164`, `vigilance.py:57-58,93` | Nationale Feste Schlüssel `"national"` → Thundering Herd (C4-64), dpc 4,6-MB-ZIP |
| `massif_closure.py:43/120`, `geosphere_warn.py:53/99`, `meteo_forets.py:53/91`, `meteoalarm_feed.py:65/266`, `meteoalarm.py:488-490,771,966,983` | Weitere `cached_fetch`-Aufrufer mit eigenen Modul-dicts — profitieren automatisch von einem Lock/Single-flight in `cached_fetch` |
| `src/services/forecast_budget.py` | `allow()` :100-139 liest ohne Lock; `record_call()` :141-156 getrennt ⇒ nicht atomar; kein `reserve()`; `_update_datei` :362-403 bei Lock-Timeout WARNING + `return`, sonst `except: pass` ⇒ Buchung verloren, **kein Zähler** |
| `src/services/official_alerts/meteoalarm_budget.py` | `allow()` :102-117, `record_call()` :119-124, `_safe_update` :228-263 — identisches Muster; Default 100/Tag (`GZ_METEOALARM_DAILY_BUDGET`) |
| `meteoalarm.py:76-77,88-101,700-707,734-740,826` | Seiten-Drossel 4 s nur funktionslokal (je `_get_cached_index`-Aufruf), **nicht threadübergreifend**; Gate-Aufruf in `_do_request` |
| `src/services/segment_weather.py:138-237` | Check-then-Fetch: :152 cache.get → :166 allow → :204 record_call → :205 `fetch_forecast` → :237 put; Single-flight-Einbaustelle |
| `src/services/weather_cache.py:92,96-198,258-270,305-316` | Lock je get/put getrennt; Bucket-Key `round(lat,4)`/`round(lon,4)`/elev/model/enrich-Flags (~11 m, **keine Kachelrundung** — 2–4 km entfernte Etappen teilen nichts); Storage-Key `bucket|start|end`; Covers-Regel; Singleton TTL 600, LRU 100 |
| `src/services/radar_service.py:559-576,997-1018` | Weitere Gate-Call-Sites (allow + record_call getrennt) |
| `api/routers/internal.py:148-164` | `/api/_internal/forecast-budget/reserve`: allow → cache_miss → 2× record_call — ebenfalls nicht atomar; natürlicher Nutzer eines atomaren `reserve()` |
| `src/services/file_lock.py:28,34-53,78-96,99,124` | `LOCK_TIMEOUT_SECONDS=2.0`, `acquire_exclusive` (True/False), `exclusive_lock` (wirft `LockTimeout`), `atomic_write_json`, `locked_json_rmw` |
| `src/services/alert_log.py:51-53` | Vorbild für Verlustzähler: `alert_log_lost_entries` + `_lost_lock` (S1a) |
| `src/providers/call_log.py:66-104` | ContextVar `_call_source_override`, `override_call_source()` mit Pflicht-Reset |
| `warn_egress.py:57,98-110,120-174` | ContextVars `_fetch_failure_sink`, `_capture_id_sink` (mutable dicts/Listen — kopierter Kontext teilt die Referenz) |
| `src/services/comparison_parallel.py:42,53,71-74,115-157` | Bestehendes Parallelmuster: Executor je Aufruf, `MAX_PARALLEL_LOCATIONS=4`, `call_source` explizit neu gesetzt (kein `copy_context`), Index-Vorbelegung, Teilausfall als `LocationResult(error=…)`, alle aus ⇒ erste Exception |
| `src/services/stage_weather.py:170-187` | Pool `min(len,8)`, ohne Kontext/Zeitgrenze; Kommentar :170-174 zum Cache-Key veraltet |
| `src/providers/openmeteo.py:68,80,116-122,309-321,656-664,1080,1151-1157` | Retry 5×, 2–60 s exp., `{502,503,504}`, `stop_at_deadline`, `FETCH_DEADLINE_SECONDS=60`; kein 429-Retry; ruft das Budget-Gate **nicht** selbst |
| `src/providers/geosphere.py:56-67,145,303-333` | Timeout 30 s, 5 Retries, Deadline 180 s; Gewitter 3 s ohne Retry |

## Existing Patterns
- **Double-Checked-Locking** unter Dateisperre: `openmeteo.py:369-388` (`_auto_probe_single`, S1a) — Vorbild für Single-flight über Prozessgrenzen; prozessintern genügt `threading.Lock` + Event/Future.
- **Verlustzähler laut statt still:** `alert_log_lost_entries` (S1a, AC-11) — Muster für „Buchung bei Lock-Timeout verloren".
- **Index-geordnete Parallelergebnisse mit Teilausfall:** `comparison_parallel.py`.
- Repo-weit **kein** `copy_context`, **keine** generische Single-flight-Hilfe.

## Dependencies
- Upstream: `file_lock.py` (fcntl), `threading`, `concurrent.futures`, `contextvars`, tenacity-Retry in Providern.
- Downstream: alle Warn-Provider (7 Module über `cached_fetch`), `segment_weather` (Trip-Alarm, Briefing, Vorschau), `radar_service`, `internal.py`-Reserve-Endpoint (Go-Scheduler-Budget #2149), Go liest Budget-JSON direkt (Feldnamen über `TestForecastBudgetConstantsMatchPython` gekoppelt, `forecast_budget.py:233-235`).

## Existing Specs
- `fix_1329_forecast_cache_budget.md` — gleiche Koordinate/Stunde ⇒ genau 1 Upstream-Call; kein Stale-Serve > 10 min; `user_briefing` nie gedrosselt; fail-open; Identität/Aggregat entstehen beim Aufrufer, nie im Cache.
- `forecast_budget_je_nutzer.md` — globaler + Nutzer-Topf (Sidecar-Lock), Lock-Timeout ⇒ `allow=True` ohne Exception, ab 100 % harter Kontoschutz, UTC-Reset; Go-Kopplung der Feldnamen.
- `fix_1448_s2_dateisperren.md` — Sperre mit Frist ⇒ False + WARNING, kein Werfen; Reload→Mutate→Write; Zählerverlust als Known Limitation hingenommen (S1b macht ihn messbar).
- `feat_1539_s0_s1a_beobachtbarkeit_atomare_schreiber.md` — Folgeplan :324-336; Cache-Rundung ausdrücklich an S2 verschoben (:318-319).
- ADR-0038 — harte Laufzeitgrenze je Lauf, sichtbarer Teilerfolg statt still weiterlaufen; muss im Baustein (`deadline_at`) erhalten bleiben.

## Tests (Bestand)
- Concurrency-Vorbilder: `tests/tdd/test_alert_log_concurrent_append.py`, `tests/tdd/test_openmeteo_availability_probe_single.py` (Barrier, Thread-Fehler gesammelt), `tests/unit/test_weather_cache.py:257`, `tests/unit/test_call_source_ueber_threadgrenze.py`, `tests/unit/test_comparison_parallel.py`.
- Budget (ohne Thread-Tests): `tests/unit/test_forecast_budget_gate.py`, `test_forecast_budget_fairness_je_nutzer.py`, `test_meteoalarm_budget_gate.py`, `tests/tdd/test_internal_forecast_budget_reserve.py`.
- Cache/Egress: `tests/integration/test_segment_weather_cache.py`, `tests/tdd/test_warn_service_egress.py`, `tests/unit/test_warn_egress_*.py`, `test_dpc_*`.
- pytest: keine `filterwarnings` ⇒ Thread-Ausnahmen nur Warnung (C4-62) — neue Concurrency-Tests müssen Thread-Fehler selbst einsammeln und prüfen.

## Risks & Considerations
1. **Single-flight in `cached_fetch` darf Seiteneffekte nicht verdoppeln/verlieren:** `log_warn_service_call`, `_record_fetch_failure`, `_record_capture_id`, `capture_system` laufen beim Abrufer. Wartende Threads müssen die Sinks ihres **eigenen** Kontexts korrekt bedienen (Fehlschlag/capture_id), sonst stille Signalverluste in `base.py:180-181`.
2. **Lock nicht über den Netzabruf halten**, der andere Schlüssel blockiert — Sperre je `(id(cache), cache_key)`, nicht global; 429-Schlaf (:534) darf keine fremden Dienste aufhalten.
3. **Atomares `reserve()`** muss die Go-gekoppelten Feldnamen und fail-open-Semantik (AC-4 je-Nutzer-Spec) erhalten; Verlustzähler statt `except: pass`. Zwei Töpfe (global + Nutzer-Sidecar) ⇒ Lock-Reihenfolge fest, sonst Deadlock.
4. **ContextVars:** `copy_context().run` je Aufgabe nötig; Sinks sind geteilte mutable Objekte ⇒ Zugriff aus Workern braucht Thread-Sicherheit (append/dict-set in CPython atomar, aber prüfen).
5. **Provider-Semaphore + Retries:** 503-Retries laufen unter der Semaphore, sonst vervielfachen parallele Threads die Last auf Open-Meteo. Tageszahl der Calls darf nicht steigen.
6. **Zeitgrenze (ADR-0038):** nicht gestartete Aufgaben fallen bei `deadline_at` weg und werden als ausgelassen gemeldet; laufende Threads lassen sich nicht abbrechen.
7. **Executor-Lebensdauer:** modulweiter Executor statt anyio-Pool (Threadpool ~40 ist schon durch `def`-Handler belegt); verschachteltes Submit (Baustein ruft Baustein) kann deadlocken.
8. **Cache-Key-Rundung** (~11 m): Single-flight wirkt nur bei identischem Bucket+Fenster; eine Kachelrundung würde Fachaussagen ändern (fix_1329 AC-2) ⇒ ausdrücklich nicht Teil dieses Workflows, sofern die Analyse nichts anderes belegt.
9. **Multi-User:** Budget-Töpfe sind je Nutzer; Single-flight im geteilten Cache darf keine nutzerbezogenen Daten (Identität/Aggregat) mischen (fix_1329 AC-9).

## Analysis

### Type
Feature (Skalierungs-Bausteine für #1539). Behebt nebenbei zwei heute schon reale Nebenläufigkeitsfehler:
C4-64 (Warn-Feed-Cache ohne Sperre ⇒ parallele Doppelabrufe der nationalen Feeds) und nicht-atomare
Budget-Buchung (`allow` + `record_call` getrennt; der Go-Reserve-Endpoint wird parallel gerufen).
Keine Schleife wird parallel umgestellt — das ist S3/S4. Basis: `origin/main` `25b514327` (inkl. #2218).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/single_flight.py` | CREATE | Gemeinsame Single-flight-Hilfe: Flug je Schlüssel, kurzer `threading.Lock` nur für Registrieren/Entfernen (nie über den Netzabruf), Leader setzt Ergebnis im `finally`, Wartende mit begrenzter Wartezeit, Reentranz desselben Threads ohne Warten |
| `src/services/official_alerts/warn_egress.py` | MODIFY | `cached_fetch`: Hit-Zweig als `_serve_entry(entry, …)` herausziehen; Leader läuft den bisherigen Fetch-Zweig, Wartende bekommen das Entry **aus dem Flug** (nicht per erneutem `cache.get` — TTL-Falle beim 429-Schlaf) und bedienen über `_serve_entry` ihre **eigenen** Sinks (Journal `cache_hit=True`, Fehler-Senke, `mark_not_covered`, capture_id). Schlüssel `(id(cache), cache_key)` |
| `src/services/forecast_budget.py` | MODIFY | `reserve(priority, units=1, now=None) -> bool`: Entscheidung aus `allow()` als reine Funktion herausziehen, Prüfen+Buchen im globalen Topf in **einer** RMW, danach Nutzer-Topf in eigenem, nicht verschachteltem Lock (feste Reihenfolge global→Nutzer, nie beide gehalten). `_update_datei` meldet Erfolg zurück; `except: pass`/stilles `return` ⇒ Prozesszähler `forecast_budget_lost_bookings` + WARNING. `allow()`/`record_call()`/JSON-Feldnamen unverändert (Go-Kopplung) |
| `src/services/official_alerts/meteoalarm_budget.py` | MODIFY | `reserve()` analog (Reset-Prüfung + `calls < daily_budget` + Erhöhung im selben `_safe_update`), Verlustzähler |
| `src/services/official_alerts/meteoalarm.py` | MODIFY | `_do_request` (:734-741): `allow`+`record_call` ⇒ `reserve()` |
| `api/routers/internal.py` | MODIFY | Reserve-Endpoint (:148-164): `allow` + 2× `record_call` ⇒ `reserve(units=EINHEITEN_JE_FORECAST_ABRUF)`; `record_cache_miss` bleibt (Hit-Quote) |
| `src/services/parallel_fetch.py` | CREATE | `fetch_ordered(items, fn, *, provider, deadline_at, max_parallel=None) -> list[FetchOutcome]` (index, item, value, error, skipped); modulweiter, lazy Executor (8); `BoundedSemaphore` je Provider, Slot umspannt den ganzen Task inkl. Tenacity-Retries; `copy_context()` je Aufgabe; Ausnahmen im Outcome (Aufrufer wirft neu); nicht gestartete Aufgaben bei Frist ⇒ `skipped="deadline"`, laufende ⇒ `skipped="timeout"`, Ergebnis verworfen; Aufruf aus einem Worker läuft inline seriell |
| `src/services/weather_cache.py` | MODIFY | Öffentliche `flight_key(segment, enrich_ensemble, enrich_snow, model_id)` aus `_bucket_key` + Fenster (keine duplizierte Rundung) |
| `src/services/segment_weather.py` | MODIFY | Single-flight um Miss→Fetch→Put (:152-237). Leader: Validierung → `reserve` → Fetch → `put`, Rohzeitreihe in den Flug; Wartender aggregiert **selbst** für sein Segment und bucht `record_cache_hit` auf seinem eigenen Gate. Leader gedrosselt ⇒ Wartender versucht selbst (andere Priorität möglich); Leader `ProviderRequestError` ⇒ Wartender bekommt denselben Fehler ohne eigenen Retry |
| `tests/…` (nach Verhalten benannt) | CREATE | Concurrency-Tests mit Barrier und eingesammelten Thread-Fehlern (C4-62) |

### Scope Assessment
- Dateien: 7 produktiv MODIFY, 2 CREATE + Tests
- Geschätzte produktive LoC: ~+370/-40 (Plan-Schätzung, nicht gemessen) ⇒ `loc_limit_override 500` gesetzt
- Risk Level: **MITTEL** — zentrale Abruf- und Budgetpfade; aber kein Produktivpfad läuft schon parallel, die Bausteine wirken heute nur dort, wo `def`-Handler bereits parallel laufen (Warn-Cache, Reserve-Endpoint), und dort beseitigen sie Races.

### Technical Approach (Entscheidung Tech Lead)
**S1b und S2 bleiben in diesem einen Workflow** (Zuschnitt aus dem Gesamtplan; LoC-Druck ⇒ offizieller Override, nicht Verengung). Reihenfolge:
1. `single_flight.py` + `cached_fetch` (C4-64)
2. `ForecastBudgetGate.reserve()` + Verlustzähler → `internal.py`
3. `MeteoAlarmBudgetGate.reserve()` + Verlustzähler → `meteoalarm._do_request`
4. `parallel_fetch.py`
5. `weather_cache.flight_key` + `segment_weather` (reserve + Single-flight)

### Entschiedene technische Fragen (keine PO-Fragen)
1. **Verlustzähler-Sichtbarkeit:** wie S1a (`alert_log_lost_entries`, `alert_log.py:52/540`): int-Prozesszähler + WARNING/ERROR-Log. Kein neues JSON-Feld (Go-Kopplung), kein neues Status-Konzept.
2. **Nutzer-Fairness:** Nutzer-Topf wird nach dem globalen Topf in eigenem Lock gebucht ⇒ Fairness je Nutzer kann bei N parallelen Threads desselben Nutzers um ≤ N−1 Calls überschießen (heute ohne Lock ebenso). Globaler Kontoschutz (ab 100 %) bleibt **exakt**. Als Known Limitation in die Spec.
3. **`reserve` in `segment_weather`:** `_validate_segment` (heute :178, NACH `allow`) wird vor `reserve` gezogen ⇒ ein Validierungsfehler bucht keinen Call.
4. **capture_id-Reihenfolge:** irrelevant — `base.py:106` bildet `set(capture_ids)`, `alert_log.py:269` sortiert. Keine eigene Senke je Aufgabe nötig.
5. **Wartezeit im Single-flight:** begrenzt (Providerfrist + Puffer); bei Ablauf holt der Wartende selbst ab (fail-open, wie Lock-Timeout-Semantik der Budgets).
6. **Semaphorenzahlen:** Open-Meteo 3, MeteoAlarm 1, Météo-France 4 als Env-Defaults. Messung erst in S3 mit dem ersten echten Nutzer des Bausteins (in diesem Workflow nutzt kein Produktivpfad `parallel_fetch`).
7. **`radar_service`** bleibt bei `allow`+`record_call` bis S4 (Zeitgrenzen-Logik dort).

### Pflicht-Zusicherung aus der Analyse (muss AC werden)
**Semaphore-Erwerb mit Frist (ADR-0038):** Verwaiste Worker eines Vorlaufs (nach Deadline weiterlaufend) halten Slots. Der Erwerb im Aufrufer muss `acquire(timeout=Restzeit bis deadline_at)` sein; bei Ablauf ⇒ `skipped="deadline"`. Test: absichtlich hängender Worker aus einem Vorlauf, Folgeaufruf kehrt trotzdem fristgerecht zurück.

### Messbare Zusicherungen (Testkandidaten)
- N Threads, gleicher Warn-Schlüssel ⇒ genau 1 `request_fn`-Aufruf, N−1 Journalzeilen `cache_hit=True`
- Zwei verschiedene Schlüssel blockieren sich nicht (Leader A hängt, B kehrt zurück)
- Leader-Fehlschlag ⇒ die Fehler-Senke **jedes** Wartenden meldet Fehlschlag
- N parallele `reserve()` bei Restbudget M ⇒ genau M `True`, `calls == M` in der Datei (global und MeteoAlarm)
- Zwei Nutzer parallel ⇒ kein Übersprechen der Nutzer-Töpfe
- Lock-Timeout ⇒ `reserve()` liefert `True`, Verlustzähler +1, WARNING
- `fetch_ordered`: Index-Reihenfolge trotz umgekehrter Fertigstellung; ≤ Semaphore gleichzeitig; Deadline ⇒ `skipped`; verschachtelter Aufruf ohne Hänger; ContextVar `call_source` + Sinks im Worker sichtbar
- `segment_weather`: N parallele gleiche Segmente ⇒ 1 `fetch_forecast`; zwei Nutzer ⇒ Call auf Leader-Gate, Cache-Hit je Wartendem auf eigenem Gate; keine Nutzerdaten im Cache (fix_1329 AC-9)

### Dependencies
Upstream: `file_lock.py`, `threading`, `concurrent.futures`, `contextvars`. Downstream: 7 Warn-Module über `cached_fetch` (9 Aufrufstellen), Go-Scheduler über Reserve-Endpoint (Feldnamen via `TestForecastBudgetConstantsMatchPython`), `segment_weather` (Trip-Alarm, Briefing, Vorschau), künftig S3/S4 über `parallel_fetch`.

### Risiken
- 429-Schlaf des Leaders lässt Wartende mitwarten ⇒ begrenzte Wartezeit
- Lock-Contention (2 s Dateisperre) ⇒ jeder Timeout fail-open + gezählt
- `override_call_source`-Reset muss im selben Kontext wie das Set laufen (`ctx.run` umschließt beides)
- Journal-Hit-Quote steigt durch Wartende; echte Calls/Tag sinken oder bleiben gleich, nie mehr

### Open Questions
- keine offenen PO-Fragen

## Schnittstellen-Festlegungen für TDD RED (2026-10-08, Phase 5)

Die Spec lässt diese Nahtstellen offen; die RED-Tests legen sie fest, `/50-implement` muss sie exakt so bauen.

- **`services.single_flight`:** `class SingleFlight` mit `run(key, leader_fn, *, wait_timeout_s) -> FlightResult`.
  `FlightResult` ist eine Dataclass mit `value: Any = None`, `error: BaseException | None = None`,
  `is_leader: bool = False`, `timed_out: bool = False`. `run()` wirft **nie** — weder für Leader noch für
  Wartende; eine Ausnahme aus `leader_fn` steht in `error` (beim Leader und bei allen Wartenden dasselbe
  Objekt). Wartefrist abgelaufen ⇒ `FlightResult(timed_out=True)`, der Aufrufer holt selbst ab.
  Der Registrier-Lock heißt `self._lock` (`threading.Lock`); Tests prüfen `sf._lock.locked() is False`
  innerhalb von `leader_fn`.
- **Wartefristen als Modulkonstanten (monkeypatchbar, zur Aufrufzeit gelesen):**
  `services.official_alerts.warn_egress.WARN_FLIGHT_WAIT_TIMEOUT_S`,
  `services.segment_weather.SEGMENT_FLIGHT_WAIT_TIMEOUT_S`.
- **Verlustzähler (Muster `alert_log_lost_entries`, Modul-int + eigener `threading.Lock`):**
  `services.forecast_budget.forecast_budget_lost_bookings`,
  `services.official_alerts.meteoalarm_budget.meteoalarm_budget_lost_bookings`.
- **Sperrfrist im Test verkürzen:** `monkeypatch.setattr` auf `services.forecast_budget.LOCK_TIMEOUT_SECONDS`
  bzw. `services.official_alerts.meteoalarm_budget.LOCK_TIMEOUT_SECONDS` (Modulname, zur Aufrufzeit gelesen).
- **Signaturen:** `ForecastBudgetGate.reserve(priority, units=1, now=None) -> bool`,
  `MeteoAlarmBudgetGate.reserve(now=None) -> bool`.
- **`services.parallel_fetch`:** `fetch_ordered(items, fn, *, provider, deadline_at, max_parallel=None)`;
  `fn(item)` liefert den Wert; `deadline_at` ist ein absoluter `time.monotonic()`-Wert.
  Executorgröße per Env `GZ_PARALLEL_FETCH_WORKERS` (Default 8), Slots je Provider per Env
  `GZ_PARALLEL_FETCH_SLOTS_<PROVIDER_UPPER>` (Provider-Schlüssel `open_meteo`=3, `meteoalarm`=1,
  `meteo_france`=4; unbekannter Provider ⇒ 3). Beides lazy beim ersten Gebrauch gelesen;
  `parallel_fetch._reset_for_tests()` verwirft Executor und Semaphoren, damit Tests neue Env-Werte setzen können.

## Hinweise aus TDD RED für /50 (2026-10-08)

- `tests/tdd/test_internal_forecast_budget_reserve.py` läuft **ohne** `--disable-socket` (TestClient braucht lokalen Socket); alle übrigen RED-Dateien mit.
- Grüne Wächtertests (heute schon erfüllt, bewachen Mutationen): AC-2 über `cached_fetch` mit zwei Schlüsseln, AC-11 (Mutation 6: `_validate_segment` hinter `reserve`), AC-16, AC-18(b), AC-18 `user_briefing` bei vollem Budget.
- **AC-16 ist schwach:** Der gedrosselte Leader ist sofort fertig, deshalb lässt sich die Überlappung mit dem Wartenden ohne Eingriff in `src/` nicht erzwingen. Der Adversary muss den Zweig „Leader gedrosselt ⇒ Wartender reserviert selbst" eigens per Mutation prüfen.
- AC-14: Beide Nutzer nutzen dasselbe Fenster, weil `flight_key` das Fenster enthält. Die abweichende Fensterdauer prüft AC-15 über einen dritten Aufrufer.
- AC-9, Nutzer-Topf: Nur die Nutzer-Sperre wird gehalten, und der Verlustzähler steigt um genau 1. Grund: Die globale Buchung gelingt, nur die Nutzer-Buchung geht verloren.
- Öffentliche Methode ist `SegmentWeatherService.fetch_segment_weather`.
- Dieser Abschnitt ist nach dem RED-Commit `0bfb69d66` entstanden und noch nicht committet (Commit-Sperre in Phase 6 bis zum Adversary-Verdict). Er geht mit dem GREEN-Commit hinein.
