# Adversary Dialog — feat-1539-s1b-s2-abruf-baustein
Spec: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md
Datum: 2026-10-08 15:22

## Checkliste
- [x] **Input:** unverändert; parallele Zugriffe aus dem Threadpool (Warn-Feeds, Reserve-Endpoint,
- [x] **Output:** Je Warn-Feed-Schlüssel genau ein Upstream-Abruf; je Wetter-Bucket und Fenster genau ein
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
- [x] **AC-16:** Given der Leader wurde gedrosselt (kein Call erfolgt, keine Zeitreihe im Flug) / When ein Wartender daraufhin verarbeitet wird / Then versucht der Wartende selbst `reserve` mit seiner eigenen Priorität und ruft bei Erfolg selbst ab.
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
**Adversary:** Neuer Dialog nach Fix-Loop 1. Testlauf: 50 passed (13 Dateien, --disable-socket) + 8 passed (test_internal_forecast_budget_reserve.py, ohne --disable-socket); Volltext docs/artifacts/feat-1539-s1b-s2-abruf-baustein/adversary-test-output.txt. Produktivcode gegenueber Runde 1 unveraendert (nur Tests ergaenzt). Alle in Runde 1 ueberlebenden Mutationen erneut angewendet (String-Ersetzung, Sicherungskopie, nach jeder Mutation filecmp identisch): ALLE jetzt rot, jeweils durch einen neuen, namentlichen Test:
- F001/M1 (kind != "throttled" entfernt, segment_weather.py:204): rot durch test_segment_weather_single_flight.py::test_ac16_gedrosselter_leader_wartender_mit_hoeherer_prioritaet_ruft_selbst_ab. Der Test erzwingt die Ueberlappung echt (_HakenCache, echter Cache, haelt den Leader bei seinem zweiten get im Flug an, Wartender nachweislich registriert, dann Freigabe) -- kein Mock-Theater, kein vakuum-gruen.
- F002/N1 (gate.reserve() -> gate.allow(), meteoalarm.py:737): rot durch test_meteoalarm_budget_buchung_im_abrufpfad.py::test_restbudget_abruf_bucht_genau_einen_call_in_der_budgetdatei. Weg ist der echte Abrufpfad _get_cached_index; gefakt nur httpx.get (Netzrand), Datei/Gate/Cache echt.
- F003/M2a (segment_weather.py:188) rot: test_f003_vorgaenger_flug_schreibt_..._kein_zweiter_abruf (integration); M2b (warn_egress.py:467) rot: gleichnamiger Test in test_warn_feed_single_flight.py.
- F004/N4 (weather_cache.py:268, Schluessel ohne Fenster) rot: test_f004_gleicher_bucket_verschiedene_fenster_parallel_zwei_fetches_je_eigenes_fenster; N7 (id(cache), segment_weather.py:192) rot: test_f004_zwei_cache_instanzen_gleicher_schluessel_parallel_je_ein_abruf; N8 (warn_egress.py:471) rot: test_f004_zwei_cache_dicts_gleicher_schluessel_parallel_je_ein_abruf.
- F005/N16 (single_flight.py:65, pop entfernt) rot: test_single_flight_keys_independent.py::test_f005_zwei_aufeinanderfolgende_laeufe_gleicher_schluessel_je_eigener_leader_frisches_ergebnis. Der Folgelauf kommt bewusst aus anderem Thread (sonst Reentranz-Abkuerzung, falsches Gruen) -- der Test misst, was er behauptet.
- F006/N22b (not res.timed_out entfernt, segment_weather.py:204) rot: test_f006_wartefrist_abgelaufen_wartender_holt_selbst_ab_und_kehrt_fristgerecht_zurueck.
- F007a/M5e (_count_lost_booking() im except, forecast_budget.py:454) rot: test_forecast_budget_reserve_waechter.py::test_a_schreibfehler_statt_sperr_timeout_zaehlt_als_verlorene_buchung; F007b/N14 (now ignoriert, forecast_budget.py:418) rot: test_b_utc_tageswechsel_gilt_auch_fuer_reserve; F007c/M10b (Nutzer-Topf verschachtelt unter globaler Sperre, forecast_budget.py:182) rot: test_c_nutzer_topf_wird_nicht_unter_der_globalen_sperre_gebucht (echte fcntl.flock-Halter, keine Mocks).
Test-Qualitaet geprueft: keine Dateiinhalt-Checks, kein patch/Mock auf Eigenannahmen; die Patches (meteoalarm.httpx.get, sw.SEGMENT_FLIGHT_WAIT_TIMEOUT_S, fb.LOCK_TIMEOUT_SECONDS) greifen im verbrauchenden Modul. Der Pruefling wird per __file__-Assert im Quellbaum des Worktrees abgesichert.
**Implementierer:** (nicht anwesend; Kontext-Isolationsmodus)

### Runde 2
**Adversary:** 12 NEUE eigene Mutationen ueber die neuen Tests hinaus, an Wirkstellen (Aufrufer, Endpoint, Baustein):
- P1 Wartezeit effektiv unbegrenzt (single_flight.py:54): rot (3 Tests: test_ac5_wartender_bekommt_timed_out_nach_frist, test_ac5_cached_fetch_wartender_holt_selbst_ab, test_f006_...).
- P2 Wartender bucht keinen Cache-Hit (segment_weather.py:290): rot test_ac14_zwei_nutzer_call_auf_leader_gate_hit_auf_eigenem_gate_des_wartenden.
- P3 Endpoint ohne record_cache_miss (internal.py:153ff): rot test_erlaubte_reservierung_bucht_genau_einen_cache_miss.
- P4 MeteoAlarm-Rueckgabe von reserve() ignoriert (meteoalarm.py:737): rot test_ausgeschoepftes_budget_abruf_erreicht_den_upstream_nicht.
- P6 Endpoint units=1 statt 2 (internal.py:153): rot (6 Tests). P7 active_users nicht eingetragen (forecast_budget.py:151ff): rot (5 Tests). P8 Nutzer-Topf units->1: rot (5 Tests).
- P9 Warn-Fail-open bei timed_out entfernt (warn_egress.py:480): rot test_ac5_cached_fetch_wartender_holt_selbst_ab.
- P10 Leader-Fehler verschluckt (segment_weather.py:201): rot test_ac11_validierungsfehler_bucht_keinen_call_und_ruft_keinen_provider.
- P11 timeout->deadline vertauscht (parallel_fetch.py:176): rot test_deadline_und_timeout_sind_unterscheidbar.
- P12 _count_lost_booking() im Lock-Timeout-Zweig entfernt (forecast_budget.py:451): rot (test_forecast_reserve_bei_globalem_lock_timeout_ist_laut, ..._nutzer_lock_timeout_ist_laut).
- P5 beobachteter Reset in _erlaubt_laut_state entfernt (meteoalarm_budget.py:130): UEBERLEBT (kein Test rot). Ad-hoc belegt das Produktivverhalten als korrekt (reserve() und allow() liefern False nach record_observed_reset(+3000s)), aber kein Test bewacht die Reset-Sperre -> F009.
F008 (Nicht-ProviderRequestError des Leaders) unveraendert, Spec schweigt, LOW. Arbeitsbaum nach allen Mutationen: Statusliste identisch zum Start, src/services und api/routers/internal.py per diff -rq identisch zur Sicherungskopie.
**Implementierer:** (nicht anwesend)

Finding:
  ID: F009
  Severity: LOW
  Category: edge_case
  Code reference: src/services/official_alerts/meteoalarm_budget.py:130
  Description: Die Sperre "beobachteter Reset-Zeitpunkt" in _erlaubt_laut_state (jetzt auch Teil des atomaren reserve(), Zeile 134) wird von keinem Test bewacht; Entfernen laesst alle 58 Tests gruen. Verhalten selbst ist korrekt (Ad-hoc).
  Spec requirement: AC-7 (reserve: Reset-Pruefung + Budget in einer Sequenz); die Spec nennt den Reset nicht ausdruecklich.
  Conflict: Zusicherung nur dort vorhanden, wo der Code steht. Vor-#1539-Luecke (allow() war ebenfalls ungetestet), daher kein Blocker.
  Remediation: Sammel-Issue #1199: Test record_observed_reset(+X) => reserve() False, calls unveraendert.

Finding:
  ID: F008
  Severity: LOW
  Category: edge_case
  Code reference: src/services/segment_weather.py:199
  Description: Leader-Ausnahme, die nicht ProviderRequestError ist: Wartende holen selbst ab (keine Ersparnis), kein Haengen. Bewusst unveraendert.
  Spec requirement: Spec schweigt (AC-17 nennt nur ProviderRequestError).
  Conflict: keiner, fail-open vertretbar.
  Remediation: Sammel-Issue #1199.

Confirmation:
  AC: AC-1
  Code reference: src/services/official_alerts/warn_egress.py:467
  Evidence: Leader-Flug je (id(cache), key); N-1 Wartende bedienen das Journal aus dem Flug; test_warn_feed_single_flight ac1 gruen.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: src/services/single_flight.py:45
  Evidence: Registrier-Lock nur um Anlegen/Entfernen, nie um leader_fn; keys_independent gruen, Lock ueber leader_fn war in Runde 1 rot (M8).
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: src/services/official_alerts/warn_egress.py:480
  Evidence: Wartende bedienen eigene Senken via _serve_entry; ac3-Test gruen.
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: src/services/official_alerts/warn_egress.py:483
  Evidence: Wartender nimmt res.value[0] aus dem Flug, nicht cache.get; ac4-Test gruen.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: src/services/single_flight.py:54
  Evidence: Wartezeit begrenzt; P1 rot (3 Tests, u.a. test_f006 an der Wirkstelle segment_weather), P9 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: src/services/forecast_budget.py:151
  Evidence: reserve entscheidet und bucht in einem Lock; Runde-1-Mutation M4a rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: src/services/official_alerts/meteoalarm_budget.py:134
  Evidence: Atomares reserve; N1 rot durch test_restbudget_abruf_bucht_genau_einen_call_in_der_budgetdatei; N14 rot (Tageswechsel Forecast).
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: src/services/forecast_budget.py:182
  Evidence: Nutzer-Topf nach der globalen Sperre in eigener Sperre; M10b rot durch test_c_nutzer_topf_wird_nicht_unter_der_globalen_sperre_gebucht.
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: src/services/forecast_budget.py:454
  Evidence: Fail-open + Verlustzaehler + WARNING; M5e rot durch test_a_schreibfehler_statt_sperr_timeout_zaehlt_als_verlorene_buchung; P12 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-10
  Code reference: src/services/forecast_budget.py:52
  Evidence: Verlustzaehler nur im Prozess, keine neuen JSON-Felder; Go-Vertragstest laut Runde 1 ok, JSON-Konstanten unveraendert.
  Status: CONFIRMED

Confirmation:
  AC: AC-11
  Code reference: src/services/segment_weather.py:225
  Evidence: Validierung vor reserve; P10 rot durch test_ac11.
  Status: CONFIRMED

Confirmation:
  AC: AC-12
  Code reference: api/routers/internal.py:153
  Evidence: reserve statt allow+record_call; P3 und P6 rot (test_internal_forecast_budget_reserve).
  Status: CONFIRMED

Confirmation:
  AC: AC-13
  Code reference: src/services/segment_weather.py:192
  Evidence: Flug-Schluessel (id(cache), Bucket+Fenster); N7 rot durch test_f004_zwei_cache_instanzen.
  Status: CONFIRMED

Confirmation:
  AC: AC-14
  Code reference: src/services/segment_weather.py:290
  Evidence: Wartender bucht Hit auf eigenem Gate; P2 rot durch test_ac14.
  Status: CONFIRMED

Confirmation:
  AC: AC-15
  Code reference: src/services/weather_cache.py:268
  Evidence: flight_key = Bucket+Fenster; N4 rot durch test_f004_gleicher_bucket_verschiedene_fenster; Cache haelt nur Rohzeitreihen.
  Status: CONFIRMED

Confirmation:
  AC: AC-16
  Code reference: src/services/segment_weather.py:204
  Evidence: Gedrosselter Leader: Wartender reserviert selbst; M1 rot durch test_ac16 (echte Ueberlappung per _HakenCache).
  Status: CONFIRMED

Confirmation:
  AC: AC-17
  Code reference: src/services/segment_weather.py:199
  Evidence: ProviderRequestError gilt fuer alle, ein Retry-Zyklus; ac17-Test gruen.
  Status: CONFIRMED

Confirmation:
  AC: AC-18
  Code reference: src/services/segment_weather.py:229
  Evidence: Parallel <= seriell; user_briefing wird bei >=100 % durchgelassen und gebucht; ac18-Tests gruen.
  Status: CONFIRMED

Confirmation:
  AC: AC-19
  Code reference: src/services/parallel_fetch.py:149
  Evidence: Outcomes nach Eingabeposition indiziert; ordered-Tests gruen.
  Status: CONFIRMED

Confirmation:
  AC: AC-20
  Code reference: src/services/parallel_fetch.py:87
  Evidence: _run_task faengt Ausnahmen ins Outcome; Test gruen.
  Status: CONFIRMED

Confirmation:
  AC: AC-21
  Code reference: src/services/parallel_fetch.py:100
  Evidence: Semaphore-Slot bis Aufgabenende gehalten; Spitzenzaehler-Test gruen (M7d rot in Runde 1).
  Status: CONFIRMED

Confirmation:
  AC: AC-22
  Code reference: src/services/parallel_fetch.py:176
  Evidence: deadline vs timeout; P11 rot durch test_deadline_und_timeout_sind_unterscheidbar.
  Status: CONFIRMED

Confirmation:
  AC: AC-23
  Code reference: src/services/parallel_fetch.py:100
  Evidence: acquire mit Frist; Runde-1-Mutation M7a rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-24
  Code reference: src/services/parallel_fetch.py:139
  Evidence: Inline-Erkennung im Worker; M7c rot (Runde 1).
  Status: CONFIRMED

Confirmation:
  AC: AC-25
  Code reference: src/services/parallel_fetch.py:153
  Evidence: copy_context + ctx.run; M7b rot (Runde 1).
  Status: CONFIRMED

Confirmation:
  AC: AC-26
  Code reference: src/services/parallel_fetch.py:153
  Evidence: Je Aufrufer eigener Kontext; context-Tests gruen.
  Status: CONFIRMED

Confirmation:
  AC: Input/Output/Side effects
  Code reference: src/services/weather_cache.py:268
  Evidence: Je Schluessel/Bucket+Fenster ein Upstream-Abruf (AC-1/AC-13), Hit-Zeilen fuer Wartende (AC-1/AC-14), Budgetdatei-Felder unveraendert. Weitere zitierte Dateien: api/routers/internal.py:153, src/services/forecast_budget.py:151, src/services/official_alerts/meteoalarm.py:737, src/services/official_alerts/meteoalarm_budget.py:134, src/services/official_alerts/warn_egress.py:467, src/services/segment_weather.py:204, src/services/single_flight.py:54, src/services/parallel_fetch.py:149.
  Status: CONFIRMED

Confirmation:
  AC: AC-7 (Abrufpfad, F002)
  Code reference: src/services/official_alerts/meteoalarm.py:737
  Evidence: _do_request ruft gate.reserve() (atomar Pruefen+Buchen); N1 (reserve zu allow) rot durch test_restbudget_abruf_bucht_genau_einen_call_in_der_budgetdatei, P4 rot durch test_ausgeschoepftes_budget_abruf_erreicht_den_upstream_nicht.
  Status: CONFIRMED

## Herkunft der Vorbedingungen
kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict: VERIFIED
Alle Runde-1-Mutationen sind jetzt durch namentliche, an der Wirkstelle messende Tests rot; 11 von 12 neuen Mutationen rot, die eine ueberlebende (F009, Reset-Sperre) ist LOW und eine Vor-#1539-Luecke. Tests: 58 passed, 0 failed. F008/F009 LOW -> Sammel-Issue #1199.

## Geprüfte Dateien

- sha256:799ff849489b2a3a167f09434d6f9e5254aabdf6d1112c770fb35246f88a0b18  api/routers/internal.py
- sha256:0e03b796b41b153aa6ddd335ae3287d20befd56023e06feaa3480851bb7cc007  src/services/forecast_budget.py
- sha256:e73d052a30e6f9ce6135735797d2fd4df9fe053e94ed4a8547b44c1e172f7fcf  src/services/official_alerts/meteoalarm.py
- sha256:2c6f83d6058b333290b7dd49ce07009c95c4314e79547d750f6a955351a2c7e1  src/services/official_alerts/meteoalarm_budget.py
- sha256:3860e141c91a20774312d49da1ceeaf1c9d742619316c80abb179e4898818bf1  src/services/official_alerts/warn_egress.py
- sha256:c25fc4dd7ac2aa45f1db468df9c50b12b98711329a84e61823a3ade81768f77e  src/services/parallel_fetch.py
- sha256:dd3a8741ff2062684c9433ead89f05e24b8d749d2002e1bce05a19fb03ebd14a  src/services/segment_weather.py
- sha256:22baf7dd86f1d1bc74018275b3d0ce3ff385a0b18b09d4cb64025182297acf90  src/services/single_flight.py
- sha256:c03db00d69e93f31ecfd6ede632c75c418f855df75cf27b5b4432daeecb5cc03  src/services/weather_cache.py

## Prüfbasis

- base: 25b514327bf4094453b02cb88328e4205889bb57
- blob:2e43f5fc3f2aaaa4bbe90732664ce3037c3708de  api/routers/internal.py
- blob:abb69a43de81f81ed907dd44cac6a8b148a0875c  src/services/forecast_budget.py
- blob:ffb4899eb5ce8891961231cfc4567b2acd1d4b51  src/services/official_alerts/meteoalarm.py
- blob:4fca21f258fc39876e0335d58285417559b7a83e  src/services/official_alerts/meteoalarm_budget.py
- blob:6232e3eb129e03cf76579cad2ab4efd1e3b350a7  src/services/official_alerts/warn_egress.py
- blob:1afa6e15e2277a45f1cf99298c32682b41432f24  src/services/parallel_fetch.py
- blob:13f729253a03b6ac6c563723c014cdafd07d34ce  src/services/segment_weather.py
- blob:c861b227ff93cfedefbdf488761a6ec935e14540  src/services/single_flight.py
- blob:df4108e2c96c68377dafbee52bc24c02e88faa13  src/services/weather_cache.py
