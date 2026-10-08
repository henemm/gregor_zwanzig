---
entity_id: feat_1539_s1b_s2_abruf_baustein
type: feature
created: 2026-10-08
updated: 2026-10-08
status: draft
version: "1.0"
tags: [scheduler, nebenlaeufigkeit, single-flight, budget, parallel-fetch, multi-user, epic-2138, issue-1539]
---

# Feature #1539 Workflow 2 — S1b Cache/Budget gegen Parallelzugriff + S2 Abruf-Baustein

Issue #1539, Epic #2138, Workflow `feat-1539-s1b-s2-abruf-baustein`. Dieser Workflow liefert nur die
Scheiben **S1b** und **S2**. Keine Schleife wird auf Parallelbetrieb umgestellt (das sind S3/S4). #1539
bleibt danach offen (PR-Text „Refs #1539", nie „Closes").

## Approval

- [ ] Approved

## Purpose

Trip-Alarmläufe brechen heute an der Zeitobergrenze ab, weil Etappen strikt nacheinander abgerufen werden.
Die spätere Parallelisierung (S3 Trip-Alarm, S4 Radar) ist nur sicher, wenn die geteilten Bausteine
Nebenläufigkeit vertragen. Dieser Workflow legt diese Bausteine an und beseitigt dabei zwei Fehler, die
schon heute real sind, weil die `def`-Handler im Threadpool nebenläufig laufen:

1. **C4-64:** Der Warn-Feed-Cache (`cached_fetch`) hat weder Sperre noch Dedupe. Parallele Zugriffe rufen
   die nationalen Feeds (z. B. das 4,6-MB-ZIP des italienischen Zivilschutzes) mehrfach gleichzeitig ab.
2. **Nicht-atomare Budget-Buchung:** `allow()` und `record_call()` sind getrennt. Der vom Go-Scheduler
   parallel gerufene Reserve-Endpoint kann dadurch das Tageskontingent überschreiten, und bei Lock-Timeout
   geht eine Buchung ohne jede Spur verloren.

Neu entstehen ein atomares `reserve()` mit sichtbarem Verlustzähler, eine Single-flight-Hilfe
(`single_flight.py`), ein gemeinsamer begrenzter Abruf-Baustein (`parallel_fetch.py`) und eine
Single-flight-Absicherung im Wetter-Cache. **Ehrlich vorweg:** Dieser Workflow senkt die Alarm-Abbrüche
nicht. Kein Produktivpfad nutzt `parallel_fetch` bereits; die Senkung wird erst mit S3 gemessen.

## Source

- **Python-Dienste (Cache/Warnungen):** `src/services/official_alerts/warn_egress.py` (`cached_fetch`,
  `:389-404`, Check `:443-460`, Fetch-Schleife `:468-537`, `_store_entry :177-189`)
- **Python-Dienste (Budget):** `src/services/forecast_budget.py` (`allow :100-139`, `record_call :141-156`,
  `_update_datei :362-403`, Go-gekoppelte Konstanten `:233-235`),
  `src/services/official_alerts/meteoalarm_budget.py` (`allow :102-117`, `record_call :119-124`,
  `_safe_update :228-263`), `src/services/official_alerts/meteoalarm.py` (`_do_request :734-741`)
- **Python-Dienste (Wetter-Cache):** `src/services/weather_cache.py` (`_bucket_key`, Storage-Key
  `bucket|start|end`), `src/services/segment_weather.py` (`:138-237`)
- **Python-Router:** `api/routers/internal.py` (`/api/_internal/forecast-budget/reserve`, `:148-164`)
- **Neu:** `src/services/single_flight.py`, `src/services/parallel_fetch.py`
- **Vorbilder/Helfer:** `src/services/file_lock.py`, `src/services/alert_log.py:51-53`
  (`alert_log_lost_entries`), `src/services/comparison_parallel.py`, `src/providers/call_log.py:66-104`

> **Schicht-Hinweis:** Ausschließlich Python-Core (`api/`, `src/services/`). Die Go-API liest die
> Budget-JSON-Dateien direkt; deren Feldnamen bleiben unverändert (`TestForecastBudgetConstantsMatchPython`).
> Kein Frontend, kein Go-Code.

## Estimated Scope

- **LoC:** ca. +370/-40 Produktivcode (Plan-Schätzung, nicht gemessen) plus Tests.
  `loc_limit_override 500` ist gesetzt; S1b und S2 bleiben bewusst ein Workflow (Zuschnitt aus dem Gesamtplan).
- **Files:** 7 produktiv MODIFY, 2 CREATE, ca. 8 Testdateien
- **Effort:** high — zentrale Abruf- und Budgetpfade, aber kein Produktivpfad läuft schon parallel
- **Risk Level:** MITTEL

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/feat-1539-s1b-s2-abruf-baustein.md` | Analyse | Verbindliche Analyse, Entscheidungen, Risiken |
| `docs/context/feat-1539-parallele-abrufe.md` | Gesamtplan | Einordnung S1b/S2 gegenüber S3/S4 |
| `feat_1539_s0_s1a_beobachtbarkeit_atomare_schreiber.md` | Spec (live) | Vorgänger; Verlustzähler-Muster `alert_log_lost_entries`; Double-Checked-Locking `openmeteo.py:369-388` |
| `fix_1329_forecast_cache_budget.md` | Spec (live) | Gleiche Koordinate/Stunde ⇒ ein Upstream-Call; kein Stale-Serve > 10 min; `user_briefing` nie gedrosselt; AC-9 Identität/Aggregat entstehen beim Aufrufer |
| `forecast_budget_je_nutzer.md` | Spec (live) | Globaler + Nutzer-Topf; Lock-Timeout ⇒ `allow=True`; ab 100 % harter Kontoschutz; UTC-Reset; Go-Kopplung der Feldnamen |
| `fix_1448_s2_dateisperren.md` | Spec (live) | Sperre mit Frist ⇒ False + WARNING, kein Werfen; Reload→Mutate→Write |
| ADR-0038 | ADR | Harte Laufzeitgrenze je Lauf, sichtbarer Teilerfolg statt stilles Weiterlaufen |
| `src/services/file_lock.py` | Helfer | `acquire_exclusive`, `exclusive_lock`, `LockTimeout`, `locked_json_rmw` |

## Scope

**In Scope**

- S1b: `cached_fetch` mit Single-flight je Schlüssel (C4-64); `ForecastBudgetGate.reserve()` und
  `MeteoAlarmBudgetGate.reserve()` atomar; Verlustzähler statt stillem Buchungsverlust; Reserve-Endpoint und
  `meteoalarm._do_request` auf `reserve()`.
- S2: `single_flight.py`, `parallel_fetch.py`, `weather_cache.flight_key`, Single-flight in
  `segment_weather` (Miss→Fetch→Put).

**Out of Scope**

- Umstellung irgendeiner Schleife auf `parallel_fetch` (Trip-Alarm S3, Radar S4, Briefing S5, Compare S6,
  Go-Nutzer-Fan-out S7).
- `radar_service.py` (`:559-576,997-1018`) bleibt bei `allow` + `record_call` bis S4 (Zeitgrenzen-Logik dort).
- Cache-Kachelrundung (Schlüssel bleibt `round(lat,4)`/`round(lon,4)`, ca. 11 m): Sie würde Fachaussagen
  ändern (fix_1329 AC-2) und gehört nicht hierher.
- Neue JSON-Felder in den Budget-Dateien, neues Status-Konzept, Persistenz der Verlustzähler.
- Messung der Semaphorenzahlen (erst mit dem ersten echten Nutzer in S3).

## Betroffene Dateien

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/single_flight.py` | CREATE | Flug je Schlüssel; kurzer `threading.Lock` nur für Registrieren/Entfernen (nie über den Netzabruf); Leader setzt Ergebnis im `finally`; Wartende mit begrenzter Wartezeit; Reentranz desselben Threads ohne Warten |
| `src/services/official_alerts/warn_egress.py` | MODIFY | `cached_fetch`: Hit-Zweig als `_serve_entry(entry, …)` herausziehen; Leader läuft den bisherigen Fetch-Zweig; Wartende bekommen das Entry aus dem Flug (nicht per erneutem `cache.get`) und bedienen über `_serve_entry` ihre **eigenen** Sinks. Schlüssel `(id(cache), cache_key)` |
| `src/services/forecast_budget.py` | MODIFY | `reserve(priority, units=1, now=None) -> bool`; Entscheidung aus `allow()` als reine Funktion; `_update_datei` meldet Erfolg; Zähler `forecast_budget_lost_bookings` + WARNING. `allow()`, `record_call()`, JSON-Feldnamen unverändert |
| `src/services/official_alerts/meteoalarm_budget.py` | MODIFY | `reserve()` analog (Reset-Prüfung + `calls < daily_budget` + Erhöhung im selben `_safe_update`), Verlustzähler |
| `src/services/official_alerts/meteoalarm.py` | MODIFY | `_do_request` (`:734-741`): `allow` + `record_call` ⇒ `reserve()` |
| `api/routers/internal.py` | MODIFY | Reserve-Endpoint (`:148-164`): `allow` + 2× `record_call` ⇒ `reserve(units=EINHEITEN_JE_FORECAST_ABRUF)`; `record_cache_miss` bleibt (Hit-Quote) |
| `src/services/parallel_fetch.py` | CREATE | `fetch_ordered(...)`, `FetchOutcome`, modulweiter lazy Executor (8), `BoundedSemaphore` je Provider, `copy_context()` je Aufgabe |
| `src/services/weather_cache.py` | MODIFY | Öffentliche `flight_key(segment, enrich_ensemble, enrich_snow, model_id)` aus `_bucket_key` + Fenster, keine duplizierte Rundung |
| `src/services/segment_weather.py` | MODIFY | Single-flight um Miss→Fetch→Put (`:152-237`); `_validate_segment` vor `reserve` |
| `tests/…` (nach Verhalten benannt) | CREATE | siehe „Geplante Tests" |

## Implementation Details

### Reihenfolge

1. `single_flight.py` + `cached_fetch` (C4-64)
2. `ForecastBudgetGate.reserve()` + Verlustzähler → `internal.py`
3. `MeteoAlarmBudgetGate.reserve()` + Verlustzähler → `meteoalarm._do_request`
4. `parallel_fetch.py`
5. `weather_cache.flight_key` + `segment_weather` (reserve + Single-flight)

### A. `single_flight.py`

```python
class SingleFlight:
    def run(self, key, leader_fn, *, wait_timeout_s) -> FlightResult: ...
```

- Ein Flug je Schlüssel. Wer als Erster kommt, ist **Leader** und führt `leader_fn` aus; wer danach mit
  demselben Schlüssel kommt, ist **Wartender**.
- Der interne `threading.Lock` schützt nur das Anlegen und Entfernen des Flugs. Er wird **nie** über
  `leader_fn` (Netzabruf) gehalten. Jeder Schlüssel hat einen eigenen Flug; ein hängender Flug A blockiert
  Schlüssel B nicht.
- Der Leader setzt Ergebnis **oder** Ausnahme im `finally` und entfernt den Flug, auch bei Fehler.
- Wartende warten höchstens `wait_timeout_s` (Providerfrist + Puffer). Bei Ablauf liefert die Hilfe
  „kein Ergebnis"; der Aufrufer holt dann selbst ab (fail-open).
- Ruft derselbe Thread für denselben Schlüssel erneut auf (Reentranz), läuft er ohne Warten selbst durch.
- Die Hilfe kennt keine Nutzerdaten; sie transportiert nur, was der Leader hineinlegt.

### B. `cached_fetch` (Warn-Feed-Cache)

- Schlüssel des Flugs: `(id(cache), cache_key)`. Fremde Cache-Instanzen und fremde Schlüssel teilen nichts.
- Der Hit-Zweig wird zu `_serve_entry(entry, …)`. Leader und Wartende bedienen darüber **ihre eigenen**
  ContextVar-Sinks (`_fetch_failure_sink`, `_capture_id_sink`), das Journal (`cache_hit=True` bei
  Wartenden), `mark_not_covered` und `capture_id`.
- Wartende nehmen das Entry **aus dem Flug**, nicht per erneutem `cache.get`: Schläft der Leader bei
  429-Retry (`:534`) länger als die TTL, wäre ein erneutes `get` ein falscher Miss.
- Schlägt der Leader fehl, erhält jeder Wartende den Fehlschlag und meldet ihn in **seiner** Fehler-Senke
  (sonst stille Signalverluste in `base.py:180-181`).
- capture_id-Reihenfolge ist irrelevant (`base.py:106` bildet `set`, `alert_log.py:269` sortiert).
- TTLs (1800/60/86400 s) bleiben unverändert. Die sieben Aufrufermodule (neun Aufrufstellen) profitieren
  ohne eigene Änderung.

### C. `reserve()` im Forecast-Budget

```python
def reserve(self, priority, units=1, now=None) -> bool: ...
```

- Die Entscheidungslogik aus `allow()` wird als reine Funktion herausgezogen; `allow()` ruft sie weiter
  unverändert (nur lesend, Verhalten gleich).
- **Globaler Topf:** Prüfen und Buchen in **einer** Read-Modify-Write-Sequenz unter der Dateisperre.
- **Nutzer-Topf:** danach in eigenem, **nicht verschachteltem** Lock (feste Reihenfolge global → Nutzer,
  nie beide gleichzeitig gehalten ⇒ kein Deadlock). Der Nutzer-Topf wird nur für Prioritäten gebucht, für die
  die Je-Nutzer-Spec das vorsieht (unverändert).
- `user_briefing` wird nie gedrosselt (fix_1329); ab 100 % gilt der harte Kontoschutz exakt.
- `_update_datei` meldet Erfolg zurück. Bei Lock-Timeout oder Fehler gilt fail-open: `reserve()` liefert
  `True`, ein Prozesszähler `forecast_budget_lost_bookings` steigt um 1, `logger.warning` wird geschrieben.
  Das stille `except: pass` und das stille `return` entfallen.
- JSON-Feldnamen der Budget-Dateien bleiben byte-kompatibel (Go liest direkt).

### D. `reserve()` im MeteoAlarm-Budget

Gleiches Muster: Reset-Prüfung, `calls < daily_budget` und Erhöhung im selben `_safe_update`;
Lock-Timeout ⇒ `True`, Verlustzähler, WARNING. Default 100/Tag (`GZ_METEOALARM_DAILY_BUDGET`) unverändert.

### E. `fetch_ordered` (`parallel_fetch.py`)

```python
@dataclass
class FetchOutcome:
    index: int
    item: Any
    value: Any = None
    error: BaseException | None = None
    skipped: str | None = None   # None | "deadline" | "timeout"

def fetch_ordered(items, fn, *, provider, deadline_at, max_parallel=None) -> list[FetchOutcome]: ...
```

- **Reihenfolge:** Das Ergebnis hat genau `len(items)` Einträge in Eingabereihenfolge, unabhängig von der
  Fertigstellungsreihenfolge (Index-Vorbelegung wie `comparison_parallel.py`).
- **Teilausfall:** Eine Ausnahme in `fn` landet im `FetchOutcome.error` der betroffenen Aufgabe; die
  übrigen laufen weiter. Der Aufrufer entscheidet, ob er neu wirft.
- **Executor:** modulweit, lazy, 8 Worker (kein anyio-Pool, dessen ca. 40 Threads durch `def`-Handler
  belegt sind). `max_parallel` begrenzt zusätzlich je Aufruf.
- **Semaphore je Provider:** `BoundedSemaphore`; Defaults Open-Meteo 3, MeteoAlarm 1, Météo-France 4
  (per Env überschreibbar). Der Slot umspannt die **ganze** Aufgabe inklusive Tenacity-Retries, damit 503-Retries
  die Last nicht vervielfachen.
- **Semaphore-Erwerb mit Frist (ADR-0038):** Der Erwerb ist `acquire(timeout=Restzeit bis deadline_at)`.
  Läuft die Frist ab, wird die Aufgabe nicht gestartet und mit `skipped="deadline"` gemeldet. Verwaiste
  Worker eines früheren Aufrufs (nach Deadline weiterlaufend) halten Slots; ein Folgeaufruf darf deshalb nie
  unbegrenzt auf einen Slot warten.
- **Zeitgrenze:** Nicht gestartete Aufgaben bei Fristablauf ⇒ `skipped="deadline"`. Bereits laufende
  Aufgaben, die die Frist überschreiten ⇒ `skipped="timeout"`, ihr späteres Ergebnis wird verworfen.
- **Kontext:** Jede Aufgabe läuft in `copy_context().run(...)`. `override_call_source` (Set und Reset)
  liegen im selben `ctx.run`. Die Sinks sind geteilte mutable Objekte; der Zugriff aus Workern ist
  thread-sicher (append/dict-set).
- **Verschachtelung:** Ruft ein Worker `fetch_ordered` auf, läuft der innere Aufruf **inline seriell** im
  selben Thread; er reiht nichts im Executor ein und kann nicht verklemmen.

### F. `flight_key` und Single-flight in `segment_weather`

- `weather_cache.flight_key(segment, enrich_ensemble, enrich_snow, model_id)` liefert Bucket-Schlüssel
  plus Fenster aus der bestehenden `_bucket_key`-Logik (keine zweite Rundung).
- `segment_weather` legt Miss→Fetch→Put in einen Flug. Reihenfolge im **Leader**: `_validate_segment` →
  `reserve` → `fetch_forecast` → `put`. `_validate_segment` (heute `:178`, nach `allow`) rückt vor `reserve`;
  ein Validierungsfehler bucht keinen Call.
- Der Leader legt die **Rohzeitreihe** in den Flug, nie ein Aggregat oder eine Segmentidentität.
- Jeder Wartende aggregiert für **sein** Segment (eigene `segment_id`/`duration_hours`) und bucht
  `record_cache_hit` auf **seinem eigenen** Gate.
- Wurde der Leader gedrosselt (kein Call erfolgt), versucht der Wartende selbst, mit seiner eigenen Priorität.
- Wirft der Leader `ProviderRequestError`, erhält der Wartende denselben Fehler ohne eigenen Retry-Zyklus.
- Läuft die Wartezeit ab, holt der Wartende selbst ab (fail-open).

## Expected Behavior

- **Input:** unverändert; parallele Zugriffe aus dem Threadpool (Warn-Feeds, Reserve-Endpoint,
  künftig `fetch_ordered` aus S3/S4).
- **Output:** Je Warn-Feed-Schlüssel genau ein Upstream-Abruf; je Wetter-Bucket und Fenster genau ein
  `fetch_forecast`; Budget-Buchungen ohne Überschreitung; Verlustzähler `forecast_budget_lost_bookings`
  und das Pendant im MeteoAlarm-Budget steigen laut statt still.
- **Side effects:** Mehr `cache_hit=True`-Zeilen im Journal (Hit-Quote steigt). Echte Upstream-Calls pro
  Tag sinken oder bleiben gleich, steigen nie. Kein Produktivpfad nutzt `fetch_ordered` in diesem Workflow.

## Acceptance Criteria

- **AC-1:** Given N Threads (z. B. 12), die über eine `threading.Barrier` gleichzeitig `cached_fetch` für
  denselben Warn-Schlüssel und denselben Cache aufrufen / When alle fertig sind / Then wurde `request_fn`
  genau einmal aufgerufen, alle N Aufrufer erhalten dasselbe Ergebnis, und das Journal enthält genau N−1
  Zeilen mit `cache_hit=True`.
  - Test: `tests/tdd/test_warn_feed_single_flight.py`; Gegenprobe: ohne Flug ruft `request_fn` mehrfach auf, Test rot.

- **AC-2:** Given der Leader für Schlüssel A hängt im Abruf (blockiert) / When ein anderer Thread
  `cached_fetch` für Schlüssel B aufruft / Then kehrt B mit seinem Ergebnis zurück, ohne auf A zu warten,
  und der interne Registrier-Lock wird zu keinem Zeitpunkt über den Netzabruf gehalten.
  - Test: `tests/tdd/test_single_flight_keys_independent.py`; Leader A wartet auf ein Event, B muss vorher fertig sein.

- **AC-3:** Given der Leader eines Warn-Abrufs scheitert und N−1 Wartende hängen am Flug, jeder mit eigener
  Fehler-Senke / When der Fehlschlag eintritt / Then meldet die Fehler-Senke **jedes** Wartenden den
  Fehlschlag (nicht nur die des Leaders), und jeder Wartende bedient seine eigene capture-id-Senke.
  - Test: `tests/tdd/test_warn_feed_single_flight.py` mit je Thread eigenem Kontext und Senken.

- **AC-4:** Given der Leader eines Warn-Abrufs schläft wegen 429-Retry länger als die Cache-TTL, bevor er
  schreibt / When die Wartenden ihr Ergebnis übernehmen / Then erhalten sie das Entry aus dem Flug (kein
  erneuter Miss, kein zweiter Upstream-Abruf).
  - Test: `tests/tdd/test_warn_feed_single_flight.py` mit kurzer TTL und verzögerndem `request_fn`.

- **AC-5:** Given der Leader eines Flugs hängt länger als die begrenzte Wartezeit / When ein Wartender die
  Frist erreicht / Then holt der Wartende selbst ab und kehrt fristgerecht zurück (fail-open), statt
  unbegrenzt zu warten.
  - Test: `tests/tdd/test_single_flight_wait_is_bounded.py` mit verkürzter Wartefrist und blockiertem Leader.

- **AC-6:** Given N parallele `ForecastBudgetGate.reserve()`-Aufrufe bei einem Restbudget von M < N /
  When alle fertig sind / Then liefern genau M Aufrufe `True`, der Zähler `calls` in der Budget-Datei steht
  bei genau M (Tageslimit nie überschritten), und der Globaler-Kontoschutz ab 100 % bleibt exakt.
  - Test: `tests/tdd/test_forecast_budget_reserve_atomic.py` mit `Barrier`; Gegenprobe: mit getrenntem `allow`+`record_call` überschreitet das Limit, Test rot.

- **AC-7:** Given N parallele `MeteoAlarmBudgetGate.reserve()`-Aufrufe bei einem Restbudget von M /
  When alle fertig sind / Then liefern genau M Aufrufe `True` und `calls` in der Datei steht bei genau M;
  nach dem UTC-Tageswechsel beginnt der Zähler wieder bei 0.
  - Test: `tests/tdd/test_meteoalarm_budget_reserve_atomic.py` mit `Barrier`.

- **AC-8:** Given zwei verschiedene Nutzer A und B buchen parallel über `reserve()` auf ihre Nutzer-Töpfe /
  When alle Buchungen abgeschlossen sind / Then enthält der Topf von A genau die Buchungen von A und der Topf
  von B genau die von B, ohne Übersprechen und ohne Deadlock durch die feste Reihenfolge global → Nutzer.
  - Test: `tests/tdd/test_forecast_budget_reserve_atomic.py`, zwei `user_id`, Thread-Fehler gesammelt.

- **AC-9:** Given ein Sperrhalter, der die Budget-Dateisperre über die Wartefrist hinaus hält (Frist im Test
  verkürzt) / When `reserve()` aufgerufen wird / Then liefert es `True` ohne Ausnahme (fail-open), der
  Verlustzähler (`forecast_budget_lost_bookings` bzw. das MeteoAlarm-Pendant) steigt um genau 1, und es steht
  eine WARNING im Log.
  - Test: `tests/tdd/test_budget_reserve_lock_timeout_is_loud.py`, für beide Töpfe; Gegenprobe: stilles `except: pass` ⇒ Zähler bleibt 0, Test rot.

- **AC-10:** Given die Budget-Dateien nach beliebigen `reserve()`-, `allow()`- und `record_call()`-Aufrufen /
  When Go-Scheduler und der bestehende Vertragstest sie lesen / Then sind alle JSON-Feldnamen und Konstanten
  unverändert (`TestForecastBudgetConstantsMatchPython` bleibt grün), und es ist kein neues Feld
  hinzugekommen.
  - Test: bestehender Go-Test `TestForecastBudgetConstantsMatchPython` plus Python-Test, der die Schlüsselmenge der geschriebenen Datei mit der Menge vor der Änderung vergleicht (`tests/tdd/test_forecast_budget_reserve_atomic.py`).

- **AC-11:** Given ein Segment, das die Validierung nicht besteht (`_validate_segment` wirft) / When
  `segment_weather` es abruft / Then ist der Budgetzähler danach unverändert (kein gebuchter Call), und es
  geht kein Upstream-Aufruf raus.
  - Test: `tests/integration/test_segment_weather_single_flight.py`; Zähler vor/nach verglichen.

- **AC-12:** Given der Reserve-Endpoint `/api/_internal/forecast-budget/reserve` wird von N parallelen
  Anfragen gerufen / When das Restbudget kleiner als N ist / Then antwortet er höchstens so oft mit „erlaubt",
  wie Budget vorhanden war, die Antwortform ist unverändert, und `record_cache_miss` wird weiter gebucht.
  - Test: `tests/tdd/test_internal_forecast_budget_reserve.py` erweitert um Parallelfall (FastAPI-Testclient, Threads).

- **AC-13:** Given N parallele Abrufe für dasselbe Segment (gleicher Bucket, gleiches Fenster) / When alle
  `segment_weather` aufrufen / Then läuft genau ein `fetch_forecast` (am Provider-Rand gezählt), und alle N
  Aufrufer erhalten ein Ergebnis.
  - Test: `tests/integration/test_segment_weather_single_flight.py`, `Barrier`, Zähler an der HTTP-Grenze.

- **AC-14:** Given zwei verschiedene Nutzer rufen parallel dasselbe Segment ab / When einer Leader und der
  andere Wartender ist / Then wird der Call auf dem Gate des Leaders gebucht, der Wartende bucht einen
  Cache-Hit auf seinem **eigenen** Gate, und der Wartende erhält seine eigene `segment_id` und sein über das
  eigene Fenster berechnetes Aggregat.
  - Test: `tests/integration/test_segment_weather_single_flight.py`, zwei `user_id`, Gates je Nutzer geprüft.

- **AC-15:** Given ein Wetter-Cache nach Single-flight-Läufen mit zwei Nutzern / When der Cache-Inhalt
  inspiziert wird / Then enthält er ausschließlich Rohzeitreihen, weder Nutzerkennung noch Segmentidentität
  noch Aggregat (fix_1329 AC-9), und ein Aufrufer mit abweichender Fensterdauer erhält nie Identität oder
  Aggregat des ersten Aufrufers.
  - Test: `tests/integration/test_segment_weather_single_flight.py`; ergänzt den bestehenden fix_1329-AC-9-Test.

- **AC-16:** Given der Leader wurde gedrosselt (kein Call erfolgt, keine Zeitreihe im Flug) / When ein
  Wartender daraufhin verarbeitet wird / Then versucht der Wartende selbst `reserve` mit seiner eigenen
  Priorität und ruft bei Erfolg selbst ab.
  - Test: `tests/integration/test_segment_weather_single_flight.py` mit Leader auf niedriger, Wartendem auf höherer Priorität.

- **AC-17:** Given der Leader wirft `ProviderRequestError` / When Wartende am Flug hängen / Then erhalten
  alle Wartenden denselben Fehler, und es läuft kein zweiter Abruf-Retry-Zyklus (`fetch_forecast` wurde genau
  einmal aufgerufen).
  - Test: `tests/integration/test_segment_weather_single_flight.py`, Zähler am Provider-Rand.

- **AC-18:** Given drei feste Abruffolgen — (a) N gleiche Segmente, (b) N paarweise verschiedene Segmente,
  (c) eine Mischung aus gleichen und verschiedenen Segmenten mit zwei Nutzern — / When jede Folge einmal
  seriell und einmal parallel (Barrier) über `segment_weather` läuft und die echten Upstream-Calls gezählt
  werden / Then ist die Zahl parallel je Folge kleiner oder gleich der seriellen Zahl, und bei global
  ausgeschöpftem Budget (Anteil ≥ 100 %) wird ein Abruf mit Priorität `user_briefing` über `reserve()`
  trotzdem durchgelassen und gebucht.
  - Test: `tests/integration/test_segment_weather_single_flight.py` parametrisiert über die Folgen (a)–(c), zählt Provider-Calls seriell vs. parallel; zusätzlicher Fall: Budgetdatei auf `calls == DAILY_BUDGET`, `user_briefing`-Abruf erreicht den Provider.

- **AC-19:** Given `fetch_ordered` über eine Eingabeliste, deren Aufgaben in umgekehrter Reihenfolge fertig
  werden / When alle Aufgaben abgeschlossen sind / Then ist die Ergebnisliste in Eingabereihenfolge mit
  `index` gleich Position, und bei zwei Aufrufen derselben Eingabe sind die Ergebnisse identisch geordnet.
  - Test: `tests/unit/test_parallel_fetch_ordered.py`, Aufgaben mit absteigender Verzögerung.

- **AC-20:** Given eine Aufgabe wirft eine Ausnahme, die übrigen sind erfolgreich / When `fetch_ordered`
  endet / Then trägt nur das Outcome dieser Aufgabe `error`, die übrigen tragen `value`, und es gibt keine
  nicht eingesammelte Thread-Ausnahme.
  - Test: `tests/unit/test_parallel_fetch_ordered.py`; Thread-Fehler werden selbst eingesammelt (C4-62).

- **AC-21:** Given eine Semaphore der Größe S und mehr als S Aufgaben / When `fetch_ordered` läuft / Then
  sind nie mehr als S Aufgaben gleichzeitig im Abruf (per Spitzenzähler gemessen), und der Slot wird auch
  während Wiederholungsversuchen innerhalb einer Aufgabe gehalten.
  - Test: `tests/unit/test_parallel_fetch_ordered.py` mit gleichzeitigem Zähler und einer Aufgabe, die intern wiederholt.

- **AC-22:** Given die `deadline_at` läuft ab, während Aufgaben noch nicht gestartet sind / When
  `fetch_ordered` endet / Then tragen die nicht gestarteten Aufgaben `skipped="deadline"`, bereits laufende,
  aber zu späte Aufgaben tragen `skipped="timeout"` mit verworfenem Ergebnis, und die beiden Gründe sind
  unterscheidbar.
  - Test: `tests/unit/test_parallel_fetch_deadline.py` mit Semaphore 1, einer langsamen und mehreren wartenden Aufgaben.

- **AC-23:** Given ein verwaister Worker aus einem früheren Aufruf hält über die Frist hinaus den einzigen
  Semaphore-Slot (absichtlich hängend) / When ein Folgeaufruf von `fetch_ordered` mit eigener, kurzer
  `deadline_at` startet / Then kehrt der Folgeaufruf trotzdem fristgerecht (Frist plus kleine Toleranz) mit
  `skipped="deadline"` zurück, statt unbegrenzt auf den Slot zu warten (ADR-0038).
  - Test: `tests/unit/test_parallel_fetch_deadline.py`; Gegenprobe: `acquire()` ohne Timeout ⇒ Test hängt bzw. verfehlt die Frist, rot.

- **AC-24:** Given ein Worker von `fetch_ordered` ruft selbst wieder `fetch_ordered` auf (verschachtelt) /
  When der Executor voll ausgelastet ist / Then endet der Gesamtaufruf ohne Deadlock innerhalb einer
  Testfrist, und der innere Aufruf läuft inline seriell im selben Thread.
  - Test: `tests/unit/test_parallel_fetch_nested.py` mit Executor-Größe 1 und Zeitgrenze für den Test.

- **AC-25:** Given der aufrufende Kontext hat `call_source` gesetzt und trägt Fehler-/capture-Senken /
  When `fetch_ordered` die Aufgaben in Workern ausführt / Then sehen die Worker denselben `call_source`-Wert
  und schreiben in die Senken des Aufrufers, und nach der Aufgabe ist `call_source` im Worker
  zurückgesetzt (Set und Reset im selben Kontext).
  - Test: `tests/unit/test_parallel_fetch_context.py`, erweitert das Muster aus `test_call_source_ueber_threadgrenze.py`.

- **AC-26:** Given zwei Nutzer rufen `fetch_ordered` gleichzeitig mit je eigenem `call_source` und eigenen
  Senken auf / When beide fertig sind / Then landen Fehler und capture-Ids ausschließlich in den Senken des
  jeweiligen Aufrufers, ohne Übersprechen zwischen den Nutzern.
  - Test: `tests/unit/test_parallel_fetch_context.py`, zwei Nutzerkontexte, Thread-Fehler gesammelt.

## Geplante Tests

Deterministisch, ohne Netz, kein Mock-Theater (Zähler sitzen am Provider-/HTTP-Rand, nicht in der
Prüflingslogik), keine Dateiinhalt-Checks. Testdateien nach Verhalten benannt; jeder Test löst seinen
Prüfling relativ zur eigenen Datei auf (Worktree-sicher). **Concurrency-Tests sammeln Thread-Fehler selbst
ein und prüfen sie** (pytest hat keine `filterwarnings`, Thread-Ausnahmen wären sonst nur eine Warnung, C4-62).
Vorbilder: `tests/tdd/test_alert_log_concurrent_append.py`, `tests/tdd/test_openmeteo_availability_probe_single.py`,
`tests/unit/test_weather_cache.py:257`, `tests/unit/test_call_source_ueber_threadgrenze.py`,
`tests/unit/test_comparison_parallel.py`.

| Datei | Prüft |
|---|---|
| `tests/tdd/test_warn_feed_single_flight.py` | AC-1, AC-3, AC-4 |
| `tests/tdd/test_single_flight_keys_independent.py` | AC-2 |
| `tests/tdd/test_single_flight_wait_is_bounded.py` | AC-5 |
| `tests/tdd/test_forecast_budget_reserve_atomic.py` | AC-6, AC-8, AC-10 |
| `tests/tdd/test_meteoalarm_budget_reserve_atomic.py` | AC-7 |
| `tests/tdd/test_budget_reserve_lock_timeout_is_loud.py` | AC-9 |
| `tests/tdd/test_internal_forecast_budget_reserve.py` (erweitert) | AC-12 |
| `tests/integration/test_segment_weather_single_flight.py` | AC-11, AC-13 bis AC-18 |
| `tests/unit/test_parallel_fetch_ordered.py` | AC-19 bis AC-21 |
| `tests/unit/test_parallel_fetch_deadline.py` | AC-22, AC-23 |
| `tests/unit/test_parallel_fetch_nested.py` | AC-24 |
| `tests/unit/test_parallel_fetch_context.py` | AC-25, AC-26 |
| `TestForecastBudgetConstantsMatchPython` (Go, bestehend) | AC-10 (Feldnamen-Kopplung) |

**Mutations-Gegenprobe (Pflicht für den Adversary):** (1) Flug in `cached_fetch` entfernen ⇒ AC-1 rot;
(2) Wartende per erneutem `cache.get` statt aus dem Flug bedienen ⇒ AC-4 rot; (3) Fehler-Senke der
Wartenden nicht bedienen ⇒ AC-3 rot; (4) `reserve()` als `allow`+`record_call` getrennt ⇒ AC-6/AC-7 rot;
(5) Lock-Timeout still schlucken ⇒ AC-9 rot; (6) `_validate_segment` wieder hinter `reserve` ⇒ AC-11 rot;
(7) `acquire()` ohne Timeout ⇒ AC-23 rot; (8) `copy_context` weglassen ⇒ AC-25 rot; (9) Aggregat in den Flug
statt Rohzeitreihe ⇒ AC-14/AC-15 rot; (10) Registrier-Lock über den Netzabruf halten ⇒ AC-2 rot. Mutationen
nur per String-Ersetzung mit externer Sicherungskopie. Zu klären ist jeweils, **welcher** Test rot wird.

## Known Limitations

- **Nutzer-Fairness-Überschuss ≤ N−1:** Der Nutzer-Topf wird nach dem globalen Topf in eigenem Lock gebucht.
  Bei N parallelen Threads desselben Nutzers kann dessen Fairness-Grenze um höchstens N−1 Calls überschießen
  (heute ohne Lock ebenso). Der globale Kontoschutz ab 100 % bleibt exakt.
- **Laufende Threads sind nicht abbrechbar:** `fetch_ordered` verwirft das Ergebnis zu später Aufgaben
  (`skipped="timeout"`), der Thread selbst läuft bis zum Ende und hält seinen Slot bis dahin. Die Frist beim
  Erwerb (AC-23) begrenzt nur die Wirkung auf Folgeaufrufe.
- **Semaphorenzahlen nicht gemessen:** Open-Meteo 3, MeteoAlarm 1, Météo-France 4 sind begründete
  Env-Defaults. Gemessen werden sie erst in S3 mit dem ersten echten Nutzer des Bausteins.
- **Keine Kachelrundung:** Single-flight greift nur bei identischem Bucket (ca. 11 m) und Fenster; 2–4 km
  entfernte Etappen teilen weiterhin nichts.
- **Verlustzähler nur im Prozess:** Sie stehen auf 0 nach jedem Neustart und sind nicht im Status-JSON; die
  Sichtbarkeit liegt im Log (WARNING) und im Zähler wie bei `alert_log_lost_entries`.
- **Wartezeit bei hängendem Leader:** Ein 429-Schlaf oder Hänger des Leaders lässt Wartende bis zur
  begrenzten Wartezeit mitwarten, danach holen sie selbst ab (kurzzeitig mehr Calls auf einen Schlüssel
  möglich, nie unbegrenzt).
- `radar_service.py` bleibt bis S4 bei `allow` + `record_call` und ist damit weiter nicht atomar.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue ADR in diesem Workflow; ADR-0038 bleibt gültig und wird im Baustein
  (`deadline_at`, AC-22/AC-23) erhalten.
- **Rationale:** Die Bausteine ändern keine Grundsatzfläche (Kanäle, Provider, Datenmodell, Auth). Die
  Entscheidung zur Parallelisierung selbst (ein Baustein, Trips/Nutzer seriell) wird, wie im Vorgänger
  angekündigt, mit dem ersten echten Nutzer des Bausteins (S3) als ADR festgehalten.

## Changelog

- 2026-10-08: Initial spec created (Workflow feat-1539-s1b-s2-abruf-baustein, S1b + S2)
