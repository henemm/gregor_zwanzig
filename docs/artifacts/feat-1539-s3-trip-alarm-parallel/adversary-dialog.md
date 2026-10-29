# Adversary Dialog — feat-1539-s3-trip-alarm-parallel
Spec: docs/specs/modules/feat_1539_s3_trip_alarm_parallel.md
Datum: 2026-10-28 13:40

## Checkliste
- [x] **Input:** Liste zwischengespeicherter Etappen-Wetterdaten eines Trips (unverändert).
- [x] **Output:** Liste frischer Etappen-Wetterdaten in Eingabereihenfolge; gescheiterte oder übersprungene Etappen
- [x] **Side effects:** Kürzere Wartezeit je Trip bei mehreren fälligen Etappen. Journal bucht weiter „alarm" bzw.
- [x] **AC-1:** Given ein Trip mit fünf fälligen Etappen, deren Abrufe in umgekehrter Reihenfolge fertig werden / When `_fetch_fresh_weather` läuft / Then enthält die Ergebnisliste die Etappen in der ursprünglichen Reihenfolge des Trips, unabhängig davon, welcher Abruf zuerst zurückkam.
- [x] **AC-2:** Given ein Trip mit vier fälligen Etappen, bei denen der Abruf der zweiten Etappe scheitert / When `_fetch_fresh_weather` läuft / Then werden die übrigen drei Etappen trotzdem geliefert, die zweite fehlt, `_fetch_stats` steht auf (4, 1), und der Fehler steht mit Etappe im Log.
- [x] **AC-3:** Given die Lauf-Frist läuft ab, bevor alle Etappen abgerufen sind (Frist im Test verkürzt, Open-Meteo auf einen Slot begrenzt) / When `_fetch_fresh_weather` endet / Then zählt jede übersprungene Etappe (nicht gestartet oder zu spät) als gescheitert in `_fetch_stats`, fehlt in der Ergebnisliste, und für jede steht eine Fehlerzeile mit Grund (Frist bzw. Zeitüberschreitung) im Log, nichts wird still weggelassen.
- [x] **AC-4:** Given ein Alarmlauf (Aufruf aus dem Alarm-Pfad) / When die Etappen in Worker-Threads abgerufen werden / Then bucht das Open-Meteo-Journal jeden dieser Abrufe mit der Herkunft „alarm", keinen mit „unbekannt". Der Bestandstest `test_bug_338_openmeteo_call_counter.py` bleibt grün.
- [x] **AC-5:** Given die Vorschau (`trip_preview_series`) ruft `_fetch_fresh_weather` über ihren Hilfsfaden / When die Etappen in Worker-Threads abgerufen werden / Then bucht das Journal diese Abrufe mit der Herkunft „vorschau" und nicht mit „alarm".
- [x] **AC-6:** Given `check_all_trips` hat die Lauf-Frist gesetzt / When `_fetch_fresh_weather` den Baustein aufruft / Then erhält der Baustein genau diese Frist (`_run_deadline_at`); nach dem Lauf, auch nach einer Ausnahme, ist das Feld zurückgesetzt. Ein Aufruf ohne gesetztes Feld (Vorschau, Einzelaufruf) bekommt eine endliche Frist von etwa 60 s ab Aufruf, niemals eine unbegrenzte. Fall mit gesetztem Feld, ohne Feld und nach Ausnahme im Lauf.
- [x] **AC-7:** Given Worker, die parallel Ergebnisse liefern / When `_fetch_fresh_weather` endet / Then sind `_fetch_stats` und die Ergebnisliste ausschließlich vom Hauptfaden geschrieben worden (kein Schreibzugriff aus einem Worker-Thread), und `_fetch_stats` stimmt nach vielen Wiederholungen immer mit der Zahl der fälligen und der gescheiterten Etappen überein. Hauptfaden verglichen, plus Wiederholungslauf mit gemischtem Erfolg/Fehler; Thread-Fehler werden selbst eingesammelt (C4-62).
- [x] **AC-8:** Given zwei verschiedene Nutzer mit je einem Trip führen gleichzeitig den Alarm-Abruf aus / When die Worker laufen / Then trägt jeder Abruf die `user_id` seines Nutzers (am Provider-Rand erfasst), das Journal und das Budget je Nutzer werden nicht vermischt, und keine Etappe des einen Nutzers erscheint im Ergebnis des anderen.
- [x] **AC-9:** Given dieselben Trips mit mehreren fälligen Etappen, einmal im bisherigen seriellen Ablauf und einmal mit dem neuen parallelen Ablauf (auch mit Etappen am gleichen Ort) / When die echten Upstream-Calls am Provider-Rand gezählt werden / Then ist die Zahl der Open-Meteo-Calls im parallelen Ablauf kleiner oder gleich der im seriellen, es entstehen keine zusätzlichen Calls pro Tag.
- [x] **AC-10:** Given Etappen, die bereits beendet sind oder erst morgen oder später beginnen, und Aufrufer, die `_fetch_fresh_weather` ersetzen / When der Alarm-Pfad läuft / Then werden beendete und künftige Etappen weiter nicht abgerufen und nicht in `versucht` gezählt, ein Trip ganz ohne fällige Etappe meldet (0, 0), und die Bestandstests bleiben grün: `tests/tdd/test_bundle_791_847_844_alerts.py`, `tests/tdd/test_bug_338_openmeteo_call_counter.py`, `tests/tdd/test_briefing_anchor_survives_dispatch_failure.py`, `tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py`. Bestandstests unverändert.
- [x] **AC-11:** Given ein Trip mit mehreren fälligen Etappen, parallel abgerufen / When der Lauf ins Log schreibt / Then steht für jede Etappe genau eine Zeile „Etappe X: Abruf in N s", auch für gescheiterte und übersprungene Etappen, nie zwei und nie keine. `tests/tdd/test_trip_alert_parallel_fetch.py`.
- [x] **AC-12:** Given der Abruf-Code mit der Slotzahl für Open-Meteo / When ADR-0103 gelesen wird / Then nennt er die Semaphorenzahl Open-Meteo (Startwert 3), die Messmethode (503/429-Anteil und Abrufdauer p50/p95 vor und nach der Umstellung, Quelle Prod-Journal), die Stellschraube `GZ_PARALLEL_FETCH_SLOTS_OPEN_METEO` und das Prüfdatum 2027-01-26; die Zeile steht in `docs/adr/README.md`. markierter Test prüft, dass ADR-0103 die vier Angaben und das Prüfdatum enthält.

## Dialog

### Runde 1
**Adversary:** Tests selbst gefahren: 17/17 gruen (adversary-test-output.txt); Regression 97 passed (adversary-regression-output.txt, inkl. tests/unit/test_alert_data_freshness.py und tests/unit/test_forecast_cache_sharing.py mit `TripAlertService.__new__` -- gruen, Klassenattribut `_run_deadline_at = None` harmlos: Code reference: src/services/trip_alert.py:534).
Code reference: src/services/trip_alert.py:2984-3010 (_fetch_fresh_weather: Zeitfilter seriell im Hauptfaden, Herkunft vor dem Worker aufgeloest, Frist aus _run_deadline_at sonst 60 s), :3012-3039 (_segment_fetcher: Worker schreibt keinen geteilten Zustand), :3041-3072 (_collect_fresh_weather: Auswertung im Hauptfaden, eine Dauerzeile je Etappe), :1157 und :1286 (Frist gesetzt / im finally zurueckgenommen).
Mutations-Gegenprobe (Spec-Mutationen 1-10 plus eigene): jede Mutation per String-Ersetzung, Sicherungskopie extern, nach jeder Mutation zurueckkopiert.
| Mutation | roter Test |
|---|---|
| M1 Herkunfts-Setzung im Worker weg | test_ac4_alarmabrufe_in_workern_werden_als_alarm_gebucht |
| M2 feste Herkunft "alarm" | test_ac5_vorschauabrufe_in_workern_bleiben_vorschau |
| M3 Ergebnisse umsortiert | test_ac1_..._eingabereihenfolge (+ ac2, ac5, ac7, ac8, ac10) |
| M4 skipped nicht gezaehlt | test_ac3_fristablauf_zaehlt_uebersprungene_als_gescheitert_mit_grund |
| M5 Frist unbegrenzt | 14 Tests, u.a. test_ac6_gesetzte_laufgrenze_erreicht_den_baustein_unveraendert, test_ac6_ohne_laufgrenze_gilt_eine_endliche_frist |
| M6 Frist nach Lauf nicht zurueckgenommen | test_ac6_check_all_trips_setzt_die_frist_und_setzt_sie_danach_zurueck, test_ac6_laufgrenze_wird_auch_nach_einer_ausnahme_im_lauf_zurueckgesetzt |
| M7 Worker schreibt _fetch_stats | test_ac7_stand_und_ergebnis_entstehen_nur_im_hauptfaden |
| M8a/b user_id 'default' bzw. None im Worker | test_ac8_zwei_nutzer_gleichzeitig_bleiben_getrennt |
| M9b Endfilter entfernt | test_ac10_beendete_und_kuenftige_..., test_ac10_trip_ohne_faellige_etappe_meldet_null_null |
| M9c Startfilter entfernt | test_ac10_beendete_und_kuenftige_etappen_werden_nicht_abgerufen |
| M9d Start `>=` statt `>` | 11 Tests (u.a. test_ac10_beendete_...) |
| M10 doppelte Dauerzeile | test_ac11_..._bei_ausfall, test_ac11_..._bei_uebersprungenen |
| M11 Default-Frist 600 s | test_ac6_ohne_laufgrenze_gilt_eine_endliche_frist_von_etwa_60_sekunden |
| M12 Stats zaehlt alle statt faellige | test_ac10_beendete_..., test_ac10_trip_ohne_faellige_... |
| M13 gescheitert immer 0 | test_ac2, test_ac3, test_ac7 |
| M14 Fehler im Worker verschluckt | test_ac2, test_ac7 |
| M15 Fehlerzeile nur debug | test_ac2, test_ac3 |
| M16 max_parallel=1 (seriell) | test_ac1, test_ac2, test_ac9 |
| M17 falscher Provider-Schluessel | test_ac3 |
| M18 Frist nie gesetzt | die beiden check_all_trips-AC-6-Tests |
| M19 enrich_ensemble=True | NICHT von der neuen Datei; rot in test_alarm_path_reuses_fresh_entry_and_refetches_stale_entry_without_clear und test_end_to_end_real_call_paths_trip_alert_and_compare_share_cache_with_own_identity (Bestand, Bug #288 bewacht) |
| M9a Endfilter `<=` statt `<` | KEIN Test rot (Finding F002, LOW) |
| M20 priority "alert_check" -> "normal" | KEIN Test rot, weder neue Datei noch Regression (Finding F001, MEDIUM) |
**Implementierer:** (nicht anwesend, Kontext-Isolation)

### Runde 2
**Adversary:** Freies Brechen.
- Leere Liste / alle Etappen gescheitert: `_collect_fresh_weather` liefert ([], n), `_fetch_stats=(n,n)` (Code reference: src/services/trip_alert.py:3041-3072); durch M12/M13 mitbewacht.
- Worker-Ausnahme, die keine `Exception` ist: der Baustein faengt `BaseException` (src/services/parallel_fetch.py `_run_task`), landet als `out.error` und wird gezaehlt -- kein Verlust.
- Worker ruft `fetch_ordered` selbst (Inline-Pfad): `_fetch_inline` liefert dieselbe Outcome-Form, Auswertung identisch.
- `_run_deadline_at` aus vorherigem Lauf: wird im `finally` (src/services/trip_alert.py:1286) auf None gesetzt, Test AC-6 bewacht (M6, M18). Einziger Rest: zwei gleichzeitige `check_all_trips` auf derselben Instanz wuerden sich gegenseitig die Frist loeschen -> Rueckfall auf 60 s Default (endlich, sicher) -- Beobachtung, kein Fehler.
- Frist im spaeten Teil eines 180-s-Laufs: uebersprungene Etappen zaehlen als gescheitert (gewollt, AC-3).
- Mutationslauf der Bestandstests: erste Fassung ohne `--allow-unix-socket` lieferte falsches Rot (test_alert_run_deadline braucht den Unix-Socket); mit Flag korrekt wiederholt, Ergebnisse oben stammen aus dem korrekten Lauf.
- Wirkt die Zusicherung dort, wo der Nutzer sie erreicht? Ja: M16 (seriell erzwingen) und M17 (falscher Provider) werden rot; die Parallelitaet ist wirklich im Produktivpfad `_fetch_fresh_weather` aktiv.
**Implementierer:** (nicht anwesend)

### Runde 3
**Adversary:** Delta-Pruefung des UNCOMMITTETEN Fixes (Verzweigung in `_collect_fresh_weather` umgedreht: `if err is None: fresh_weather += [fresh]` / `else: gescheitert += 1; logger.error(...)`), ausgeloest durch den Waechter `tests/test_success_status_guard.py` (partial_success_blind).
- Verhaltensgleichheit (Code reference: src/services/trip_alert.py:3046-3076): Reihenfolge = Schleife ueber `outcomes` (Eingabereihenfolge), `+= [fresh]` haengt hinten an wie `append`; (4,1)-Zaehlung: ein Fehler -> `gescheitert == 1`, `_fetch_stats == (len(faellig), 1)` (Zeile 3016); uebersprungene (`out.skipped` "deadline"/"timeout", Zeile 3057-3059) und `out.error` (Zeile 3060-3061) laufen in den selben `else`-Zweig; die Dauerzeile (Zeile 3074) steht ausserhalb der Verzweigung, also genau einmal je Etappe.
- Testlauf: 84 passed, 0 failed (Ausgabe: docs/artifacts/feat-1539-s3-trip-alarm-parallel/adversary-test-output.txt), inkl. `tests/test_success_status_guard.py` (Waechter jetzt gruen).
- Keine Umgehung des Waechters: `gescheitert` wird vom Aufrufer verwendet. `_fetch_fresh_weather` setzt `self._fetch_stats = (len(faellig), gescheitert)` (src/services/trip_alert.py:3016); der Aufrufer (src/services/trip_alert.py:757-769) loggt `OUTCOME_UNAVAILABLE` wenn `_gescheitert`, `OUTCOME_OK` nur wenn `_versucht and fresh_weather` und nichts gescheitert. Die Erfolgsmeldung ist aus dem Ergebnis abgeleitet. Mutationen M2/M9/M10 (Zaehler weg / Rueckgabe 0 / `_fetch_stats` 0) werden rot -> die Ableitung ist bewacht.
- Mutations-Gegenprobe (String-Ersetzung, Sicherungskopie im Scratchpad, am Ende `cmp` identisch), Zielsuite = 8 Dateien, 84 Tests:
  - M1 `+= [fresh]` -> `insert(0, fresh)`: ROT (7; u. a. test_ac1_ergebnis_folgt_der_eingabereihenfolge..., test_ac2, test_ac5, test_ac7)
  - M2 `gescheitert += 1` entfernt: ROT (test_ac2, test_ac3, test_ac7)
  - M3 Fehlerlog `error` -> `debug`: ROT (test_ac2, test_ac3)
  - M4 `err is None` -> `err is not None`: ROT (7; test_ac1, ac2, ac3, ac5 ...)
  - M5 doppelte Dauerzeile: ROT (test_ac11 x2, test_trip_alarmlauf_loggt_dauerzeile_je_etappe)
  - M6 `out.skipped` ignoriert (err=None): ROT (test_ac3)
  - M7 `out.error` ignoriert (err=None; None landet im Ergebnis): KEIN Test rot (84 gruen) -> F003
  - M8 `gescheitert += 2`: ROT (test_ac2, ac3, ac7)
  - M9 Rueckgabe `gescheitert` -> 0: ROT (test_ac2, ac3, ac7)
  - M10 `_fetch_stats` gescheitert -> 0: ROT (test_ac2, ac3, ac7)
  - M11 Etappen-ID aus Fehlerlog entfernt: nur test_ac3 rot (test_ac2 bleibt gruen) -> F004 (LOW)
  - M12 Dauerzeile nur im Erfolg: ROT (test_ac11 x2)
  - M13 `{err}` aus Fehlerlog entfernt: ROT (test_ac2, test_ac3)
  - M14 Fehler zusaetzlich im Ergebnis: ROT (test_ac2, ac3, ac7)
- Wirkt die Zusicherung dort, wo der Nutzer sie erreicht? Ja fuer Reihenfolge/Zaehlung/Status (M9, M10 rot ueber den Produktivpfad `_fetch_fresh_weather`). Nicht fuer den `out.error`-Zweig (M7): nur bei einer `BaseException` im Worker erreichbar (Worker faengt nur `Exception`, src/services/trip_alert.py:3052-3056; Baustein faengt `BaseException`, src/services/parallel_fetch.py:92).
**Implementierer:** (nicht anwesend)

## Findings
- F001 MEDIUM edge_case, Code reference: src/services/trip_alert.py:3037 -- `priority="alert_check"` (Budget-Drosselung der Alarm-Abrufe, services/forecast_budget.py:278) wird von keinem Test bewacht; Mutation auf "normal" bleibt gruen. Zeile wurde in den Worker verschoben, die Neuverdrahtung ist ungeprueft. Remediation: Test, der `fetch_segment_weather` mit priority=="alert_check" im Worker-Aufruf prueft. Vorbestehende Luecke (auch im seriellen Altcode nicht bewacht), daher kein Blocker.
- F002 LOW edge_case, Code reference: src/services/trip_alert.py:3000 -- Grenzfall end_time == now (`<` vs `<=`) ungeprueft; praktisch nicht beobachtbar. Sammel-Eintrag #1199.
- F003 MEDIUM edge_case, Code reference: src/services/trip_alert.py:3060 -- der Zweig `elif out.error is not None` (BaseException aus dem Worker) ist von keinem Test bewacht; Mutation `err = None` laesst alle 84 Tests gruen, ein `None` wuerde still in `fresh_weather` landen. Spec requirement: AC-2 -- Ausfall einer Etappe zaehlt als gescheitert und fehlt im Ergebnis. Remediation: Test mit Worker, der eine BaseException-Unterklasse wirft; erwartet `gescheitert == 1`, kein `None` im Ergebnis. Nicht durch den Fix verursacht (Zweig unveraendert), aber erst jetzt gemessen.
- F004 LOW edge_case, Code reference: src/services/trip_alert.py:3068 -- Fehlerlog-Test fuer Worker-Ausnahme (AC-2) prueft die Etappen-ID nicht; nur AC-3 tut es. Sammel-Eintrag #1199.
## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict
**VERIFIED**

Begruendung (Runde 3, Delta): Der Fix ist verhaltensgleich und keine Waechter-Umgehung (Ergebnis wird ueber `_fetch_stats` fuer den Status genutzt, src/services/trip_alert.py:3016 und :757). 84/84 Tests gruen. 12 von 14 Mutationen rot; M7 (F003, MEDIUM) und M11 (F004, LOW) nicht voll bewacht, kein Spec-Bruch, F003 sollte per Test geschlossen werden. Datei per cmp identisch zur Sicherungskopie. (Runde 1+2: 18/18 neue und 97 Regressionstests gruen; 22 von 24 Mutationen rot.)

## Nachtrag Orchestrator
F001 (MEDIUM, src/services/trip_alert.py:3037) behoben: Test test_worker_ruft_mit_alarm_prioritaet_ohne_anreicherung_und_mit_echter_user_id; Mutation priority=normal macht ihn rot. F002 (LOW) -> Sammel-Issue #1199.

## Geprüfte Dateien

- sha256:c7f384303258917810e335e0cea353cac0edb2efd80a736bf6e827dba1c899bf  src/services/trip_alert.py

## Prüfbasis

- base: c8bb30d56dcec0b25d4993cd9f7ba4ec94b121b0
- blob:46c3d367edefd0a6ea51ec2161b7c6e2a7d1d2f9  src/services/trip_alert.py

## Geprüfte Dateien

- sha256:c7f384303258917810e335e0cea353cac0edb2efd80a736bf6e827dba1c899bf  src/services/trip_alert.py

## Prüfbasis

- base: c8bb30d56dcec0b25d4993cd9f7ba4ec94b121b0
- blob:46c3d367edefd0a6ea51ec2161b7c6e2a7d1d2f9  src/services/trip_alert.py

## Geprüfte Dateien

- sha256:c7f384303258917810e335e0cea353cac0edb2efd80a736bf6e827dba1c899bf  src/services/trip_alert.py

## Prüfbasis

- base: c8bb30d56dcec0b25d4993cd9f7ba4ec94b121b0
- blob:46c3d367edefd0a6ea51ec2161b7c6e2a7d1d2f9  src/services/trip_alert.py

## Geprüfte Dateien

- sha256:c7f384303258917810e335e0cea353cac0edb2efd80a736bf6e827dba1c899bf  src/services/trip_alert.py

## Prüfbasis

- base: c8bb30d56dcec0b25d4993cd9f7ba4ec94b121b0
- blob:46c3d367edefd0a6ea51ec2161b7c6e2a7d1d2f9  src/services/trip_alert.py

## Geprüfte Dateien

- sha256:c840357454e7789bb24baffc419b880f4d239c9d8cd301b1c3c17996e4fb98e0  src/services/trip_alert.py

## Prüfbasis

- base: ce4e76be06474c4186eee63a268964f121cef9ba
- blob:3e5062fe912506ff156399e0724722b8d5282c8a  src/services/trip_alert.py
