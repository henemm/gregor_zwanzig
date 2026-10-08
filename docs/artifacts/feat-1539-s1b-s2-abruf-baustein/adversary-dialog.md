# Adversary Dialog — feat-1539-s1b-s2-abruf-baustein
Spec: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md
Datum: 2026-10-08 17:27

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
**Adversary:** Neue Vollpruefung nach dem Fix in /60-validate (Delta: forecast_budget.py reserve(), `calls + units <= DAILY_BUDGET` im _global-Callback). Frischer Testlauf der 14 Dateien: 67 passed, 0 failed (docs/artifacts/feat-1539-s1b-s2-abruf-baustein/adversary-test-output.txt, Flags --disable-socket --allow-unix-socket -v -rA). Mutationen: Sicherungskopie im Scratchpad, String-Ersetzung, nach der Mutationsserie `diff` gegen die Kopie IDENTISCH, `git diff --stat -- src` zeigt weiter nur forecast_budget.py (+5/-1).

Belege je AC gegen den aktuellen Stand (Code reference, Tests frisch gruen):
- AC-6/AC-12 (Fix): Code reference: src/services/forecast_budget.py:168 - Bedingung `calls + units <= DAILY_BUDGET` UND-verknuepft mit der Stufenentscheidung; Aufrufer Code reference: api/routers/internal.py:153 (units=2, EINHEITEN_JE_FORECAST_ABRUF=2). Tests: test_reserve_mehrere_einheiten_ueberbucht_restbudget_nicht[polling|alert_check], test_reservierung_ueberbucht_restbudget_von_einer_einheit_nicht[...] (Endpoint), test_..._schoepft_..._exakt_aus (Grenze Restbudget 2, units=2 erlaubt, calls==Limit), test_parallele_anfragen_ueberbuchen_das_restbudget_nicht.
- AC-7: Code reference: src/services/official_alerts/meteoalarm_budget.py:134 - MeteoAlarmBudgetGate.reserve() hat KEINEN units-Parameter, bucht immer +1 und prueft `calls < daily_budget` (Zeile 132) - dasselbe units-Problem besteht dort strukturell nicht. Aufrufer meteoalarm.py:737 Code reference: src/services/official_alerts/meteoalarm.py:737.
- AC-9/AC-10: fail-open bei Sperr-Timeout unveraendert (Code reference: src/services/forecast_budget.py:468, acquire_exclusive-Timeout -> Verlustzaehler Zeile 48/53); test_budget_reserve_lock_timeout_is_loud + test_forecast_budget_reserve_waechter gruen. Kein neues JSON-Feld (Diff beruehrt nur die Bedingung).
- AC-8: Nutzer-Topf wird weiter in eigener, nicht verschachtelter Sperre nach der globalen gebucht; bei Ablehnung `return False` vor `_safe_update_user` (forecast_budget.py:183-186) - kein Nutzer-Topf-Eintrag, kein active_users-Eintrag (test_abgelehnte_reservierung_bucht_nichts).
- AC-18 user_briefing: schwelle is None -> Kurzschluss, die neue Bedingung wird nicht ausgewertet; test_user_briefing_mehrere_einheiten_bei_restbudget_eins_erlaubt belegt Durchlass ueber Limit samt Buchung.
- units=1-Pfad: bei Stufe 0/1 gilt calls < Budget, also calls+1 <= Budget; bei Stufe 2 (ratio >= 1) ohnehin abgelehnt - Verhalten fuer units=1 identisch (bestehende AC-6-Tests test_parallel_reserve_* unveraendert gruen). Stufe-1-Fairness unberuehrt (UND-Verknuepfung, _erlaubt_laut_daten unveraendert, Zeile 280ff).
- AC-1..AC-5: Code reference: src/services/single_flight.py:37 und src/services/official_alerts/warn_egress.py:396 (cached_fetch); tests test_warn_feed_single_flight.py, test_single_flight_keys_independent.py, test_single_flight_wait_is_bounded.py gruen.
- AC-11, AC-13..AC-17: Code reference: src/services/segment_weather.py:229 (reserve nach Validierung, ein Aufruf je Flug-Leader), Schluessel Code reference: src/services/weather_cache.py:268 (flight_key inkl. Fenster); test_segment_weather_single_flight.py gruen.
- AC-19..AC-26: Code reference: src/services/parallel_fetch.py:129 (fetch_ordered); test_parallel_fetch_* gruen (Reihenfolge, Teilausfall, Spitzenzaehler, deadline/timeout, verwaister Slot, verschachtelt inline, Kontext/Senken).
Mutations-Gegenprobe auf dem Fix (je Mutante: WELCHER Test rot):
- M1 `<=` -> `<`: rot (9 Tests) u.a. test_reserve_mehrere_einheiten_schoepft_grenze_exakt_aus[polling|alert_check], test_parallel_reserve_kontoschutz_ab_100_prozent_exakt, test_reservierung_schoepft_restbudget_von_zwei_einheiten_exakt_aus.
- M2 Bedingung entfernt (`and True`): rot 4 Tests, test_reserve_mehrere_einheiten_ueberbucht_restbudget_nicht[polling|alert_check] (Klasse) + test_reservierung_ueberbucht_restbudget_von_einer_einheit_nicht[...] (Endpoint).
- M3 `units` -> `1` in der Bedingung: rot, dieselben 4 Tests.
- M4 Limit + 1: rot, dieselben 4 Tests.
- M5 Bedingung auch fuer user_briefing/unbekannte Prioritaet: rot test_user_briefing_mehrere_einheiten_bei_restbudget_eins_erlaubt.
- M6 Nutzer-Topf wird trotz Ablehnung gebucht (return False entfernt): rot, 11 Tests, u.a. test_abgelehnte_reservierung_bucht_nichts.
- M7 active_users-Eintrag trotz Ablehnung: rot test_abgelehnte_reservierung_bucht_nichts + test_reservierung_ueberbucht_restbudget_von_einer_einheit_nicht[...].
Keine ueberlebende Mutante. Testqualitaet: die Tests rufen Klasse und Endpoint echt (TestClient/Datei), patchen nur die Klassenkonstante DAILY_BUDGET, die reserve() zur Aufrufzeit liest (self.DAILY_BUDGET) - der Patch wirkt im Pruefling. Der Endpoint-Test prueft an der Stelle, die der Go-Scheduler erreicht (AC-12), nicht nur an der Klasse.
**Implementierer:** (nicht anwesend; Kontext-Isolationsmodus)

### Runde 2
**Adversary:** Angrenzende Flaechen und Grenzfaelle, ohne Produktivcode-Aenderung:
- Restbudget 0 mit units=2 / Restbudget 1 mit units=1: durch Stufe 2 bzw. Bedingung abgelehnt bzw. erlaubt - M1 (`<`) macht den Fall Restbudget==units rot, M2/M3/M4 den Fall Restbudget<units rot; beide Raender sind je ein namentlicher Test.
- Fail-open bei Sperr-Timeout: `entscheidung` bleibt leer, Rueckgabe True (Code reference: src/services/forecast_budget.py:183-187) - bewusste AC-9-Semantik, die neue Bedingung wird bei nicht erhaltener Sperre nicht erreicht; unveraendert, Tests test_budget_reserve_lock_timeout_is_loud gruen.
- Reserve-Endpoint ohne Datei/mit kaputter Datei: _safe_update schluckt, fail-open - unveraendert.
- Zusammenspiel mit ``allow()``: allow() prueft weiter ratio >= 1.0; reserve() ist strenger (units-bewusst). Das ist gewollt, weil nur reserve() Mehr-Einheiten-Buchungen macht; record_call() (Provider-Schicht, +1 nach dem Fakt) kann das Limit weiter um 1 je Aufruf ueberschreiten - bekannte, spec-konforme Nachbuchungsgrenze, nicht Teil von AC-6/AC-12 (die verlangen Atomaritaet von reserve()).
- MeteoAlarm: Code reference: src/services/official_alerts/meteoalarm_budget.py:142 - _op bucht +1 nur bei erlaubt; keine Mehr-Einheiten-Schnittstelle, daher kein analoger Defekt. Test test_meteoalarm_budget_reserve_atomic gruen.
Weitere Wirkstellen-Mutationen aus dem Vorlauf (Runde 2 der Vorpruefung: P1-P12) betreffen unveraenderten Code; die zugehoerigen Tests liefen frisch gruen (67/67), die Code-Referenzen wurden gegen den aktuellen Stand bestaetigt: Code reference: src/services/single_flight.py:37, src/services/parallel_fetch.py:129, src/services/weather_cache.py:268, src/services/official_alerts/warn_egress.py:396, src/services/segment_weather.py:229, src/services/official_alerts/meteoalarm.py:737, api/routers/internal.py:153.

Confirmations (alle ACs HOLD, Evidence siehe Runde 1):
Code reference: src/services/forecast_budget.py:168
Evidence: AC-6/AC-12/AC-18 - Mehr-Einheiten-Buchung ueberschreitet das Tageslimit nicht; user_briefing nie gedrosselt.
Code reference: api/routers/internal.py:153
Evidence: AC-12 - Endpoint bucht units=2 atomar ueber reserve(), Ablehnung bucht nichts.
Code reference: src/services/official_alerts/meteoalarm_budget.py:134
Evidence: AC-7/AC-9 - MeteoAlarm-reserve ohne units-Parameter, +1 atomar unter Sperre.
Code reference: src/services/official_alerts/meteoalarm.py:737
Evidence: AC-7 - Abrufpfad bucht ueber reserve() und beachtet die Rueckgabe.
Code reference: src/services/official_alerts/warn_egress.py:396
Evidence: AC-1..AC-5 - Warn-Feed cached_fetch ueber Single-flight, Wartefrist begrenzt.
Code reference: src/services/single_flight.py:37
Evidence: AC-1..AC-5, AC-17 - je Schluessel ein Leader, Fehler an alle Wartenden, Wartezeit begrenzt.
Code reference: src/services/segment_weather.py:229
Evidence: AC-11, AC-13, AC-14, AC-16, AC-18 - reserve erst nach Validierung, genau ein Abruf je Flug.
Code reference: src/services/weather_cache.py:268
Evidence: AC-13, AC-15 - Flugschluessel enthaelt Bucket und Fenster, Cache haelt nur Rohzeitreihen.
Code reference: src/services/parallel_fetch.py:129
Evidence: AC-19..AC-26 - fetch_ordered Reihenfolge, Teilausfall, Semaphore, Frist, inline verschachtelt, Kontext.
Findings: keine neuen. Frueher gebuchte LOW-Eintraege (F008/F009 in #1199) bleiben unveraendert.
**Implementierer:** (nicht anwesend; Kontext-Isolationsmodus)

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict: VERIFIED
Fix in forecast_budget.py reserve() (calls + units <= DAILY_BUDGET) belegt; 7 Mutationen auf Fix und Nachbarschaft alle durch namentliche Tests rot, keine ueberlebende Mutante. Tests: 67 passed, 0 failed. Keine neuen Findings.

## Geprüfte Dateien

- sha256:799ff849489b2a3a167f09434d6f9e5254aabdf6d1112c770fb35246f88a0b18  api/routers/internal.py
- sha256:33fc327f6c5bb1d283dc7c1d7d3721db21d0ffd2e11a9d6f94c68483e34351e2  src/services/forecast_budget.py
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
- blob:d8779db875688c42addcf6c6abe01ec14b2aa980  src/services/forecast_budget.py
- blob:ffb4899eb5ce8891961231cfc4567b2acd1d4b51  src/services/official_alerts/meteoalarm.py
- blob:4fca21f258fc39876e0335d58285417559b7a83e  src/services/official_alerts/meteoalarm_budget.py
- blob:6232e3eb129e03cf76579cad2ab4efd1e3b350a7  src/services/official_alerts/warn_egress.py
- blob:1afa6e15e2277a45f1cf99298c32682b41432f24  src/services/parallel_fetch.py
- blob:13f729253a03b6ac6c563723c014cdafd07d34ce  src/services/segment_weather.py
- blob:c861b227ff93cfedefbdf488761a6ec935e14540  src/services/single_flight.py
- blob:df4108e2c96c68377dafbee52bc24c02e88faa13  src/services/weather_cache.py
