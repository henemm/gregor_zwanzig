# Adversary Dialog — feat-1539-s1b-s2-abruf-baustein
Spec: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md
Datum: 2026-10-08 14:51

## Checkliste
- [x] **Input:** unverändert; parallele Zugriffe aus dem Threadpool (Warn-Feeds, Reserve-Endpoint,
- [ ] **Output:** Je Warn-Feed-Schlüssel genau ein Upstream-Abruf; je Wetter-Bucket und Fenster genau ein
- [x] **Side effects:** Mehr `cache_hit=True`-Zeilen im Journal (Hit-Quote steigt). Echte Upstream-Calls pro
- [x] **AC-1:** Given N Threads (z. B. 12), die über eine `threading.Barrier` gleichzeitig `cached_fetch` für denselben Warn-Schlüssel und denselben Cache aufrufen / When alle fertig sind / Then wurde `request_fn` genau einmal aufgerufen, alle N Aufrufer erhalten dasselbe Ergebnis, und das Journal enthält genau N−1 Zeilen mit `cache_hit=True`.
- [x] **AC-2:** Given der Leader für Schlüssel A hängt im Abruf (blockiert) / When ein anderer Thread `cached_fetch` für Schlüssel B aufruft / Then kehrt B mit seinem Ergebnis zurück, ohne auf A zu warten, und der interne Registrier-Lock wird zu keinem Zeitpunkt über den Netzabruf gehalten.
- [x] **AC-3:** Given der Leader eines Warn-Abrufs scheitert und N−1 Wartende hängen am Flug, jeder mit eigener Fehler-Senke / When der Fehlschlag eintritt / Then meldet die Fehler-Senke **jedes** Wartenden den Fehlschlag (nicht nur die des Leaders), und jeder Wartende bedient seine eigene capture-id-Senke.
- [x] **AC-4:** Given der Leader eines Warn-Abrufs schläft wegen 429-Retry länger als die Cache-TTL, bevor er schreibt / When die Wartenden ihr Ergebnis übernehmen / Then erhalten sie das Entry aus dem Flug (kein erneuter Miss, kein zweiter Upstream-Abruf).
- [x] **AC-5:** Given der Leader eines Flugs hängt länger als die begrenzte Wartezeit / When ein Wartender die Frist erreicht / Then holt der Wartende selbst ab und kehrt fristgerecht zurück (fail-open), statt unbegrenzt zu warten.
- [x] **AC-6:** Given N parallele `ForecastBudgetGate.reserve()`-Aufrufe bei einem Restbudget von M < N / When alle fertig sind / Then liefern genau M Aufrufe `True`, der Zähler `calls` in der Budget-Datei steht bei genau M (Tageslimit nie überschritten), und der Globaler-Kontoschutz ab 100 % bleibt exakt.
- [x] **AC-7:** Given N parallele `MeteoAlarmBudgetGate.reserve()`-Aufrufe bei einem Restbudget von M / When alle fertig sind / Then liefern genau M Aufrufe `True` und `calls` in der Datei steht bei genau M; nach dem UTC-Tageswechsel beginnt der Zähler wieder bei 0.
- [x] **AC-8:** Given zwei verschiedene Nutzer A und B buchen parallel über `reserve()` auf ihre Nutzer-Töpfe / When alle Buchungen abgeschlossen sind / Then enthält der Topf von A genau die Buchungen von A und der Topf von B genau die von B, ohne Übersprechen und ohne Deadlock durch die feste Reihenfolge global → Nutzer.
- [x] **AC-9:** Given ein Sperrhalter, der die Budget-Dateisperre über die Wartefrist hinaus hält (Frist im Test verkürzt) / When `reserve()` aufgerufen wird / Then liefert es `True` ohne Ausnahme (fail-open), der Verlustzähler (`forecast_budget_lost_bookings` bzw. das MeteoAlarm-Pendant) steigt um genau 1, und es steht eine WARNING im Log.
- [x] **AC-10:** Given die Budget-Dateien nach beliebigen `reserve()`-, `allow()`- und `record_call()`-Aufrufen / When Go-Scheduler und der bestehende Vertragstest sie lesen / Then sind alle JSON-Feldnamen und Konstanten unverändert (`TestForecastBudgetConstantsMatchPython` bleibt grün), und es ist kein neues Feld hinzugekommen.
- [x] **AC-11:** Given ein Segment, das die Validierung nicht besteht (`_validate_segment` wirft) / When `segment_weather` es abruft / Then ist der Budgetzähler danach unverändert (kein gebuchter Call), und es geht kein Upstream-Aufruf raus.
- [x] **AC-12:** Given der Reserve-Endpoint `/api/_internal/forecast-budget/reserve` wird von N parallelen Anfragen gerufen / When das Restbudget kleiner als N ist / Then antwortet er höchstens so oft mit „erlaubt", wie Budget vorhanden war, die Antwortform ist unverändert, und `record_cache_miss` wird weiter gebucht.
- [x] **AC-13:** Given N parallele Abrufe für dasselbe Segment (gleicher Bucket, gleiches Fenster) / When alle `segment_weather` aufrufen / Then läuft genau ein `fetch_forecast` (am Provider-Rand gezählt), und alle N Aufrufer erhalten ein Ergebnis.
- [x] **AC-14:** Given zwei verschiedene Nutzer rufen parallel dasselbe Segment ab / When einer Leader und der andere Wartender ist / Then wird der Call auf dem Gate des Leaders gebucht, der Wartende bucht einen Cache-Hit auf seinem **eigenen** Gate, und der Wartende erhält seine eigene `segment_id` und sein über das eigene Fenster berechnetes Aggregat.
- [x] **AC-15:** Given ein Wetter-Cache nach Single-flight-Läufen mit zwei Nutzern / When der Cache-Inhalt inspiziert wird / Then enthält er ausschließlich Rohzeitreihen, weder Nutzerkennung noch Segmentidentität noch Aggregat (fix_1329 AC-9), und ein Aufrufer mit abweichender Fensterdauer erhält nie Identität oder Aggregat des ersten Aufrufers.
- [ ] **AC-16:** Given der Leader wurde gedrosselt (kein Call erfolgt, keine Zeitreihe im Flug) / When ein Wartender daraufhin verarbeitet wird / Then versucht der Wartende selbst `reserve` mit seiner eigenen Priorität und ruft bei Erfolg selbst ab.
- [x] **AC-17:** Given der Leader wirft `ProviderRequestError` / When Wartende am Flug hängen / Then erhalten alle Wartenden denselben Fehler, und es läuft kein zweiter Abruf-Retry-Zyklus (`fetch_forecast` wurde genau einmal aufgerufen).
- [x] **AC-18:** Given drei feste Abruffolgen — (a) N gleiche Segmente, (b) N paarweise verschiedene Segmente, (c) eine Mischung aus gleichen und verschiedenen Segmenten mit zwei Nutzern — / When jede Folge einmal seriell und einmal parallel (Barrier) über `segment_weather` läuft und die echten Upstream-Calls gezählt werden / Then ist die Zahl parallel je Folge kleiner oder gleich der seriellen Zahl, und bei global ausgeschöpftem Budget (Anteil ≥ 100 %) wird ein Abruf mit Priorität `user_briefing` über `reserve()` trotzdem durchgelassen und gebucht.
- [x] **AC-19:** Given `fetch_ordered` über eine Eingabeliste, deren Aufgaben in umgekehrter Reihenfolge fertig werden / When alle Aufgaben abgeschlossen sind / Then ist die Ergebnisliste in Eingabereihenfolge mit `index` gleich Position, und bei zwei Aufrufen derselben Eingabe sind die Ergebnisse identisch geordnet.
- [x] **AC-20:** Given eine Aufgabe wirft eine Ausnahme, die übrigen sind erfolgreich / When `fetch_ordered` endet / Then trägt nur das Outcome dieser Aufgabe `error`, die übrigen tragen `value`, und es gibt keine nicht eingesammelte Thread-Ausnahme.
- [x] **AC-21:** Given eine Semaphore der Größe S und mehr als S Aufgaben / When `fetch_ordered` läuft / Then sind nie mehr als S Aufgaben gleichzeitig im Abruf (per Spitzenzähler gemessen), und der Slot wird auch während Wiederholungsversuchen innerhalb einer Aufgabe gehalten.
- [x] **AC-22:** Given die `deadline_at` läuft ab, während Aufgaben noch nicht gestartet sind / When `fetch_ordered` endet / Then tragen die nicht gestarteten Aufgaben `skipped="deadline"`, bereits laufende, aber zu späte Aufgaben tragen `skipped="timeout"` mit verworfenem Ergebnis, und die beiden Gründe sind unterscheidbar.
- [x] **AC-23:** Given ein verwaister Worker aus einem früheren Aufruf hält über die Frist hinaus den einzigen Semaphore-Slot (absichtlich hängend) / When ein Folgeaufruf von `fetch_ordered` mit eigener, kurzer `deadline_at` startet / Then kehrt der Folgeaufruf trotzdem fristgerecht (Frist plus kleine Toleranz) mit `skipped="deadline"` zurück, statt unbegrenzt auf den Slot zu warten (ADR-0038).
- [x] **AC-24:** Given ein Worker von `fetch_ordered` ruft selbst wieder `fetch_ordered` auf (verschachtelt) / When der Executor voll ausgelastet ist / Then endet der Gesamtaufruf ohne Deadlock innerhalb einer Testfrist, und der innere Aufruf läuft inline seriell im selben Thread.
- [x] **AC-25:** Given der aufrufende Kontext hat `call_source` gesetzt und trägt Fehler-/capture-Senken / When `fetch_ordered` die Aufgaben in Workern ausführt / Then sehen die Worker denselben `call_source`-Wert und schreiben in die Senken des Aufrufers, und nach der Aufgabe ist `call_source` im Worker zurückgesetzt (Set und Reset im selben Kontext).
- [x] **AC-26:** Given zwei Nutzer rufen `fetch_ordered` gleichzeitig mit je eigenem `call_source` und eigenen Senken auf / When beide fertig sind / Then landen Fehler und capture-Ids ausschließlich in den Senken des jeweiligen Aufrufers, ohne Übersprechen zwischen den Nutzern.

## Dialog

### Runde 1
**Adversary:** Testlauf: 38 passed (ohne Internal-Datei, mit --disable-socket) + 8 passed (Internal-Datei, ohne --disable-socket); Go-Vertragstest `TestForecastBudgetConstantsMatchPython` ok. Volltext: `docs/artifacts/feat-1539-s1b-s2-abruf-baustein/adversary-test-output.txt`. Danach rund 40 Einzel-Mutationen per String-Ersetzung (Sicherungskopie im Scratchpad, nach jeder Mutation per `filecmp` identisch zurueckgestellt). Ergebnis: die meisten Mutationen rot (jeweils benannter bewachender Test, siehe Liste unten), 1 aequivalent (N19: Einsammel-Reihenfolge, Ausgabe ist indiziert), 1 unerreichbar (N20: `_fetch_and_store` wirft nicht), 12 UEBERLEBEN ohne roten Test.

Finding:
  ID: F001
  Severity: HIGH
  Category: spec_violation
  Code reference: src/services/segment_weather.py:204
  Description: Zweig "Leader gedrosselt => Wartender reserviert selbst" (`res.value.kind != "throttled"`). Mutation M1 (Bedingung entfernt, Wartender erhaelt `budget_throttled` des Leaders) laesst alle 46 Tests gruen. Der einzige AC-16-Test (tests/integration/test_segment_weather_single_flight.py:362) gibt im Docstring selbst zu, die Ueberlappung nicht zu erzwingen: der Leader ist nach Mikrosekunden fertig, der Wartende kommt 0.1 s spaeter und startet einen eigenen Flug, der Zweig wird nie betreten.
  Spec requirement: AC-16 — gedrosselter Leader => Wartender versucht selbst `reserve` mit eigener Prioritaet.
  Conflict: Die Zusicherung ist nur dort "geprueft", wo der Code steht, nicht dort, wo sie wirkt. Das Verhalten selbst ist KORREKT: ein Ad-hoc-Test (Leader `polling` haelt `reserve()` 0.8 s offen, Wartender `user_briefing` haengt am Flug, Budget erschoepft) war gruen auf dem Original und rot unter M1 (Wartender bekam `has_error=True`). Der Ad-hoc-Test wurde danach wieder entfernt.
  Remediation: AC-16-Test mit echter Ueberlappung (Leader haelt `reserve()` per Event offen, bis der Wartende am Flug haengt).

Finding:
  ID: F002
  Severity: HIGH
  Category: regression
  Code reference: src/services/official_alerts/meteoalarm.py:737
  Description: Der produktive Aufrufer `_get_cached_index` ruft `gate.reserve()`. Mutation N1 (`gate.reserve()` -> `gate.allow()`, also gar keine Buchung, das Tagesbudget zaehlt nie hoch) laesst alle 46 Tests gruen. tests/tdd/test_meteoalarm_budget_reserve_atomic.py prueft nur die Gate-Methode, nicht den Weg, ueber den der Nutzer sie erreicht. (Das Endpoint-Gegenstueck ist bewacht: Rueckmutation M9 faengt `test_internal_forecast_budget_reserve.py`.)
  Spec requirement: AC-7 — Tagesbudget wird unter parallelen Abrufen exakt gebucht (Wirkung am Aufrufer, nicht nur am Gate).
  Conflict: Entfaellt die Buchung im Aufrufer, laeuft MeteoAlarm ohne Tageslimit und kein Test merkt es (Leitfrage aus #1457).
  Remediation: Test, der `_get_cached_index` mit am Rand ersetztem httpx aufruft und danach `calls` in der Budgetdatei prueft.

Finding:
  ID: F003
  Severity: MEDIUM
  Category: edge_case
  Code reference: src/services/segment_weather.py:188
  Description: Doppelpruefung des Caches im Leader (`leader_fn`) entfernt (M2a) => alle Tests gruen. Gleiches fuer die Doppelpruefung in warn_egress (M2b, src/services/official_alerts/warn_egress.py:467). Ohne sie loest ein Vorgaenger-Flug, der zwischen Erstpruefung und Flugstart geschrieben hat, einen zweiten Upstream-Abruf aus.
  Spec requirement: Output — je Schluessel/Bucket genau ein Upstream-Abruf.
  Conflict: Kein Test erzeugt das Rennen "Erstpruefung Miss, Vorgaenger-Flug endet, neuer Flug startet".
  Remediation: Deterministischer Test mit Hook zwischen Erstpruefung und `run()`.

Finding:
  ID: F004
  Severity: MEDIUM
  Category: edge_case
  Code reference: src/services/weather_cache.py:268
  Description: `flight_key` ohne Fenster (Mutation N4: nur Bucket) laesst alle Tests gruen, obwohl AC-15 "Aufrufer mit abweichender Fensterdauer erhaelt nie Identitaet/Aggregat des ersten" behauptet. Auch `id(cache)` im Schluessel (src/services/segment_weather.py:192 und src/services/official_alerts/warn_egress.py:471; Mutationen N7/N8) ist ungeschuetzt.
  Spec requirement: AC-15, AC-13 (Schluessel = Bucket + Fenster).
  Conflict: AC-15-Test prueft nur sequenziell, nie bei gleichzeitigem Lauf mit abweichendem Fenster; kein Test mit zwei Caches/Dicts und gleichem Schluessel.
  Remediation: Barrier-Test: gleicher Bucket, abweichende Fensterdauer, langsamer Leader, erwarte zwei Provider-Calls; analog zwei Caches.

Finding:
  ID: F005
  Severity: MEDIUM
  Category: edge_case
  Code reference: src/services/single_flight.py:65
  Description: Das Entfernen des Flugs (`self._flights.pop(key, None)`) kann ersatzlos entfallen (Mutation N16) ohne roten Test. Ohne Entfernen bekaeme jeder spaetere Aufrufer desselben Schluessels fuer immer das alte Ergebnis (auch nach TTL-Ablauf).
  Spec requirement: AC-2 (Registratur bleibt sauber nach Lauf und Fehler).
  Conflict: `test_ac2_registrier_lock_frei_nach_lauf_und_nach_fehler` prueft den Lock, nicht dass ein zweiter Lauf wieder eigener Leader ist.
  Remediation: Zwei serielle `run()` mit gleichem Schluessel, beide `is_leader=True`, `leader_fn` zweimal gerufen.

Finding:
  ID: F006
  Severity: MEDIUM
  Category: edge_case
  Code reference: src/services/segment_weather.py:204
  Description: Fail-open bei Wartefrist im Segment-Pfad (`not res.timed_out` entfernt, Mutation N22b) => 12 Tests gruen. Mit der Mutation liefe ein Wartender nach `timed_out` auf `res.value.kind` mit `res.value=None` (AttributeError). AC-5 ist nur an SingleFlight und cached_fetch getestet, nicht an segment_weather.
  Spec requirement: AC-5 — Wartender holt nach Fristablauf selbst ab.
  Conflict: Gleiches Muster wie F001: Zusicherung am Baustein, nicht an der Wirkstelle.
  Remediation: Test mit verkuerztem `SEGMENT_FLIGHT_WAIT_TIMEOUT_S`, haengendem Leader, Wartender liefert Ergebnis.

Finding:
  ID: F007
  Severity: LOW
  Category: edge_case
  Code reference: src/services/forecast_budget.py:454
  Description: (a) Im `except Exception`-Zweig von `_update_datei` entfaellt `_count_lost_booking()` (M5e) ohne roten Test: AC-9 ist nur fuer Sperr-Timeout belegt, nicht fuer IO-/JSON-Fehler. (b) `_load_for_today(now)` im globalen Update (src/services/forecast_budget.py:418, Mutation N14: `now` ignoriert) ist ungeschuetzt; der UTC-Tageswechsel ist nur fuer MeteoAlarm getestet. (c) Nutzer-Topf-Buchung verschachtelt unter dem globalen Lock (M10b, src/services/forecast_budget.py:182) bleibt unbemerkt; reine Verklemmung ist aktuell nicht erreichbar (kein Pfad haelt den Nutzer-Lock und fordert danach den globalen), ein Test fuer die feste Reihenfolge fehlt.
  Spec requirement: AC-9, AC-7, AC-8.
  Conflict: Teilbereiche der ACs ungeschuetzt.
  Remediation: Je ein gezielter Test.

Finding:
  ID: F008
  Severity: LOW
  Category: edge_case
  Code reference: src/services/segment_weather.py:206
  Description: Wirft der Leader eine Ausnahme, die NICHT `ProviderRequestError` ist (Ad-hoc, `RuntimeError`), holen alle N-1 Wartenden selbst ab (4 Provider-Calls bei N=4 statt 1) und werfen dieselbe Ausnahme: kein Haengen, kein Deadlock, aber keine Ersparnis. Spec schweigt; fail-open ist vertretbar.
  Spec requirement: Spec ohne Aussage (AC-17 nennt nur ProviderRequestError).
  Conflict: keiner, Hinweis.
  Remediation: Optional dokumentieren.

Rot gewordene Mutationen (WELCHER Test): M3a/M3b/M3c Wartende ohne Senken: test_warn_feed_single_flight.py::test_ac1_wartende_bedienen_eigene_capture_id_senke, ::test_ac3_fehlschlag_erreicht_fehler_senke_jedes_wartenden, ::test_ac4_wartende_bekommen_entry_aus_dem_flug_nicht_per_cache_get. M4a/M4b Pruefen+Buchen getrennt: test_forecast_budget_reserve_atomic.py::test_parallel_reserve_kontoschutz_ab_100_prozent_exakt, ::test_parallel_reserve_schwelle_ohne_nutzer_exakt, test_meteoalarm_budget_reserve_atomic.py::test_parallel_reserve_genau_restbudget_mal_true, test_internal_forecast_budget_reserve.py::test_parallele_anfragen_ueberbuchen_das_restbudget_nicht. M5a-M5d Verlustzaehler/WARNING: test_budget_reserve_lock_timeout_is_loud.py (Forecast global+Nutzer, MeteoAlarm); N9/N10 fail-closed ebenfalls dort. M6 `_validate_segment` hinter reserve: test_ac11_validierungsfehler_bucht_keinen_call_und_ruft_keinen_provider. M7a: test_parallel_fetch_deadline.py (2 Tests); M7b: test_parallel_fetch_context.py (2 Tests); M7c: test_parallel_fetch_nested.py; M7d: test_parallel_fetch_ordered.py::test_spitzenzaehler_nie_ueber_slotzahl_und_retry_haelt_slot. M8 Lock ueber leader_fn: 7 Tests (keys_independent, wait_is_bounded, AC-17, AC-4). M9 Endpoint zurueck auf allow+record_call: test_parallele_anfragen_ueberbuchen_das_restbudget_nicht. M10a Nutzer-Topf nicht gebucht: 12 Tests (u. a. AC-14). N2, N3, N5, N6, N11, N12, N13, N15, N17, N18, N21: jeweils mindestens ein benannter Test rot.
**Implementierer:** (nicht anwesend; Adversary-Lauf im Kontext-Isolationsmodus)

### Runde 2
**Adversary:** Zweite Pruefrunde, Fokus auf Randfaelle und Querschnitt.
- Leader-Ausnahme, die nicht ProviderRequestError ist: kein Haengen (Ad-hoc, 4 Threads) => F008.
- Reentranz: `_run_reentrant` laeuft ohne Warten, Code reference: src/services/single_flight.py:52. Kein Befund.
- Wartezeit begrenzt: Code reference: src/services/single_flight.py:54 (N5 rot durch test_ac5_*).
- Multi-User-Isolation: `_Raw` transportiert nur Rohzeitreihe und fetched_at, Code reference: src/services/segment_weather.py:35; der Wartende aggregiert ueber sein eigenes Segment, Hit auf eigenem Gate (N3 rot durch AC-14). Kein Uebersprechen gefunden.
- Fail-open bei haengender Nutzer-Topf-Sperre: Code reference: src/services/forecast_budget.py:151 liefert `True`, Verlustzaehler +1 und WARNING (rot unter M5a und N9).
- Atomares reserve MeteoAlarm: Code reference: src/services/official_alerts/meteoalarm_budget.py:134 (M4b rot).
- Fail-open Warn-Feed bei Fehler/Frist: Code reference: src/services/official_alerts/warn_egress.py:480.
- Endpoint: Code reference: api/routers/internal.py:153 (M9 rot).
- Parallelbaustein: Code reference: src/services/parallel_fetch.py:105 (acquire mit Frist, M7a rot) und Code reference: src/services/parallel_fetch.py:139 (Inline-Erkennung, M7c rot).
- Go-Feldnamen: `TestForecastBudgetConstantsMatchPython` ok; keine neuen JSON-Felder (Verlustzaehler nur im Prozess, Code reference: src/services/forecast_budget.py:46).
- Gesamteindruck: Implementierung verhaltensrichtig; die Hauptluecken sind Zusicherungen, die am Baustein statt an der Wirkstelle (F001, F002, F006) oder ohne Gleichzeitigkeit (F003, F004, F005) geprueft werden.
**Implementierer:** (nicht anwesend)

Confirmation:
  AC: AC-1
  Code reference: src/services/official_alerts/warn_egress.py:471
  Evidence: test_ac1_n_parallele_aufrufer_ein_upstream_abruf gruen, rot unter M3a.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: src/services/forecast_budget.py:151
  Evidence: reserve() entscheidet und bucht in einem Lock; M4a rot (3 Tests).
  Status: CONFIRMED

Confirmation:
  AC: AC-11
  Code reference: src/services/segment_weather.py:225
  Evidence: Validierung vor reserve; M6 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-12
  Code reference: api/routers/internal.py:153
  Evidence: M9 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-23
  Code reference: src/services/parallel_fetch.py:105
  Evidence: M7a rot (test_verwaister_worker_haelt_slot_folgeaufruf_kehrt_fristgerecht_zurueck).
  Status: CONFIRMED

## Herkunft der Vorbedingungen
kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict: BROKEN
Produktivcode verhaltensrichtig (Ad-hoc-Beweis AC-16, Go-Vertrag, 46 Tests gruen), aber 12 Mutationen ueberleben, darunter zwei HIGH-Wirkstellen-Luecken (F001 AC-16-Zweig, F002 meteoalarm.py reserve-Aufruf) und vier MEDIUM (F003-F006). Behebung nur durch zusaetzliche Tests; LOW: F007, F008.
