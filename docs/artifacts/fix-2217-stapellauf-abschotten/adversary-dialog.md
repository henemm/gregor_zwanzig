# Adversary-Protokoll #2217 (fix-2217-stapellauf-abschotten)

## Runde 1

Tests: 61 passed (Python, 4 Dateien, -v -rA), Go ./internal/scheduler/... ok (inkl. 4 neue Panic-/failed-Tests).
Testausgabe: scratchpad/adversary_test_output.txt. Arbeitsbaum nach allen Mutationen identisch (diff gegen Sicherung, git status unveraendert).

## Mutationstabelle (rot gewordener Test)
| Mutation | Ergebnis |
|---|---|
| M5 recover in recordRun weg | rot: TestPanicInRecordRun_RecordedAsErrorAndLockReleased |
| M6 recover in Nutzer-Goroutine weg | Testbinary stuerzt ab (Panic) -> Suite rot, kein einzelner FAIL-Name |
| M7 Stack in lastRuns Error | rot: TestPanicInRecordRun_... |
| M7b cron.Recover weg | NICHT gefangen (F002) |
| M1 Stempel Radar weg / M1b nur bei Erfolg | rot: test_kaputter_trip_rueckt_in_der_reihenfolge_nach_hinten + 3 Fairness-Tests |
| M1c Stempel in check_all_trips weg | NICHT gefangen (F003) |
| M1d Stempel compare_radar weg | rot: Fairness-Tests |
| M2 / M2b `except RadarDeadlineExceeded: raise` weg (Trip-Radar / check_all_trips) | NICHT gefangen (F001) |
| M2c Compare-Radar: Deadline-Handler hinter except Exception | rot: AC-4 Compare + 2 Fairness-Tests |
| M3a-d failed nicht in Router-Antwort (je Endpunkt) | rot je Endpunkt eigener Test |
| M4 failed>0 -> partial (Python) | rot: test_unwetterlauf_... ; Go: TestTriggerResponseBody_FailedIsHardErrorNotPartial |
| M8a-e Schutz je Lauf weg (5 Laeufe) | rot je Lauf eigener Test |
| M9/M9b/M9c collect_failed / due.failed_ids / auto_pause nicht auf _failed | rot AC-11/12/13, AC-14, AC-14 |
| M10 skip_next vor Pruefung | rot: test_ac13 |
| M18 Vermerk bei Ausnahme | rot: test_ac11, test_ac13 |
| M11/M12 try in presets_due_for_hour / _auto_pause | rot AC-14 (+AC-10) |
| M13 kein Log / M13b Log ohne Stack | rot (13 bzw. 10 Tests) |
| M14/M14b try in _collect_due_trips / _get_active_trips | rot AC-11,13 / AC-12 |
| M15 collect_failed nicht zurueckgesetzt | NICHT gefangen (F004) |
| M16/M17 failed nicht gezaehlt / nicht ins Result | rot |
| R9 Rueckdreh B9-B11c in KNOWN_VIOLATIONS / SPEC_LISTED | rot: test_known_violations_only_shrink, test_scanner_finds_every_spec_listed_finding (nicht vakuum-gruen) |

## Findings
F001 MEDIUM edge_case: src/services/trip_alert.py:2804 und :1171 (`except RadarDeadlineExceeded: raise`). Spec-Tabelle verlangt: Entfernen macht AC-4 rot. Tut es nicht: im Trip-Radar faengt jede Nowcast-Stelle (trip_alert.py:2146, :2189) die Ausnahme selbst, check_all_trips ruft keinen Radar-Dienst. Der Wächter ist heute nicht erreichbar -> Schutz ungeprueft/toter Defensivcode. Remediation: Test, der RadarDeadlineExceeded aus einer Stelle ausserhalb der inneren Handler wirft (z. B. trip_local_today), oder Handler streichen und in Spec so festhalten.
F002 LOW: scheduler.go:213 cron.Recover nicht testbar (Zusatznetz hinter recordRun-recover); Mutation unbemerkt.
F003 LOW: trip_alert.py:~1070 Stempel in check_all_trips (Fairness-Stempel, AC-5 spricht nur Radar) ohne Test.
F004 LOW: trip_report_scheduler.py:596 `collect_failed = 0` Reset ungeprueft (Service wird je Request neu gebaut -> praktisch folgenlos).
F005 LOW: compare_alert.py:306 / compare_official_alert.py:203 nutzen presets_due_for_hour([preset]) als Briefing-imminent-Pruefung; Ausnahmen dort werden jetzt je Preset verschluckt (nur geloggt, nicht in failed) -> Alarm laeuft dann ohne Briefing-Sperre weiter. Verhaltensaenderung gegenueber vorher (Abbruch), geringes Risiko (Doppelnachricht).
F006 LOW: AC-1 "Go-Status error" ist in zwei Haelften bewiesen (Python-Body mit failed; Go-Test nutzt Pfad /trip-reports mit gleichem Parser). Kein Ende-zu-Ende-Test mit echter Alarm-Antwortform, aber Parser ist pfadunabhaengig (scheduler.go triggerEndpointForUser).

## Checkliste
AC-1 PROVEN (test_trip_radar_kaputter_trip..., M3b/M8d/M16 rot; Go failed->error). AC-2 PROVEN (test_unwetterlauf...). AC-3 PROVEN (drei Tests, M8a/b/c je einzeln rot). AC-4 PARTIAL: Partial+failed getrennt PROVEN (M2c rot, test_..._grenzabbruch_nach_gescheitertem_trip), aber raise-Guard im Trip-Pfad unbewacht (F001). AC-5 PROVEN Radar/Compare (M1/M1b/M1d). AC-6 PROVEN (M13/M13b). AC-7 PROVEN (M5, M7). AC-8 PROVEN (M6 Absturz; Tests Rueckkehrzeit + andere Nutzer). AC-9 PROVEN (R9). AC-10 PROVEN (test_zwei_nutzer_*, test_ac10_*; M3d/M9b rot). AC-11 PROVEN (M9, M14, M18). AC-12 PROVEN (M14b, M19). AC-13 PROVEN (M10). AC-14 PROVEN (M9b/M9c/M11/M12).
Paritaet: report_unit_failure als geteilter Baustein in allen 5 Laeufen + Briefing-Pfaden genutzt, kein Duplikat. compare_alert._check_one_preset: nur continue->return False auf Funktionsebene, innere continue (Z.383) unveraendert. DueList ist list-Unterklasse; die Aufrufer compare_alert.py:306, compare_official_alert.py:203, dispatch_orchestrator.py:152 funktionieren.

VERDICT: AMBIGUOUS (kein Spec-Verstoss im Verhalten; eine Mutation der Spec-Tabelle, F001, wird von keinem Test gefangen)

## Runde 2 (nach Fix-Loop 1)

Tests: 93 passed (6 Python-Dateien inkl. test_compare_alert_briefing_imminent.py, test_compare_official_alert.py; -v -rA), Go scheduler ok. Ausgabe: scratchpad/adversary_test_output.txt. Arbeitsbaum nach den Mutationen identisch (Sicherung per diff je Mutation "identical").

## Mutationen Runde 2
| Mutation | rot |
|---|---|
| N1a Handler trip_alert.py:2804 entfernt | test_trip_radar_deadline_ausserhalb_der_nowcast_handler_ist_partial_nicht_failed |
| N1b Handler hinter except Exception | derselbe Test |
| N1c Handler nur `raise` (alte Form) | derselbe Test |
| N1d Handler ohne _abort_radar_unit | derselbe Test |
| N3 Stempel check_all_trips (trip_alert.py:~1070) weg | test_unwetterlauf_kaputter_trip_rueckt_in_der_reihenfolge_nach_hinten |
| N5a due_or_raise->bool in compare_alert.py:305 | test_ortsvergleich_abweichung_unlesbare_faelligkeit_sperrt_alarm_und_zaehlt_failed |
| N5b dito compare_official_alert.py:202 | test_ortsvergleich_amtlich_unlesbare_faelligkeit_sperrt_alarm_und_zaehlt_failed |
| N5c due_or_raise wirft nie (compare_slot_scheduler.py:116) | beide N5-Tests |

## Bewertung
- F001 GESCHLOSSEN: trip_alert.py:2804-2809 ist semantisch identisch zum inneren Handler (trip_alert.py:2146-2149, :2201-2202): beide rufen _abort_radar_unit (Stempel entfernt, checked-1, hit_deadline) und break -> Einheit nicht erreicht, Fairness unveraendert, partial/deadline, failed 0. Die Abweichung vom Spec-Wortlaut "raise" ist durch AC-4 gedeckt ("bestehende Deadline-Behandlung unveraendert", partial); blosses raise haette HTTP 500 ergeben (N1c rot belegt, dass der Test genau das unterscheidet). Empfehlung: Spec-Text "raise" auf "wie innere Handler" nachziehen (rein redaktionell).
- check_all_trips-Handler (trip_alert.py:1171): strukturell unerreichbar (kein Radar-Aufruf), vom Orchestrator als begruendet entschieden; kein Finding.
- F003 GESCHLOSSEN (N3). F005 GESCHLOSSEN (N5a-c); Nachbarregression: briefing_imminent- und official-Alert-Tests gruen.
- F002/F004/F006 LOW: als akzeptiert mit Begruendung gefuehrt (Zusatznetz nicht testbar; Service je Request neu; Parser pfadunabhaengig).

VERDICT: VERIFIED (Runde 2) - keine ungefangene Mutation ausser den begruendet akzeptierten LOW-Punkten.

## Code-Referenzen (Findings und Bestätigungen)

F001 geschlossen: äußerer Deadline-Handler Trip-Radar:
Code reference: src/services/trip_alert.py:2804

F001 Vergleich: innerer Nowcast-Handler:
Code reference: src/services/trip_alert.py:2146

F001 begründet unerreichbar: Handler check_all_trips (Spec-Reihenfolge):
Code reference: src/services/trip_alert.py:1171

F002 LOW akzeptiert: Zusatznetz cron.Recover:
Code reference: internal/scheduler/scheduler.go:213

F004 LOW akzeptiert: Reset collect_failed:
Code reference: src/services/trip_report_scheduler.py:596

F005 geschlossen: due_or_raise wirft bei failed_ids:
Code reference: src/services/compare_slot_scheduler.py:116

F005 Aufrufer Abweichungs-Alarm:
Code reference: src/services/compare_alert.py:305

F005 Aufrufer amtliche Warnungen:
Code reference: src/services/compare_official_alert.py:202

F006 LOW akzeptiert: pfadunabhängiger Aufruf/Parser:
Code reference: internal/scheduler/scheduler.go:478

AC-7: safeCall mit recover:
Code reference: internal/scheduler/scheduler.go:873

AC-8: recover in Nutzer-Goroutine:
Code reference: internal/scheduler/scheduler.go:489

AC-6/Parität: geteilter Baustein report_unit_failure:
Code reference: src/services/alert_check_state.py:114

AC-4: Compare-Radar Deadline vor except Exception:
Code reference: src/services/compare_radar_alert.py:580

AC-11/12: collect_failed auf _failed:
Code reference: src/services/dispatch_orchestrator.py:62

AC-14: Auto-Pause je Preset geschützt:
Code reference: src/services/scheduler_dispatch_service.py:66

AC-1/2/3: failed in Router-Antworten:
Code reference: api/routers/scheduler.py:81

## Checkliste (Beweise siehe oben)

- [x] AC-1 Trip-Radar: Folge-Trip alarmiert, failed==1, Go error (M3b/M8d/M16, M4 Go-Test rot)
- [x] AC-2 Unwetterlauf: Folge-Trip gewarnt, failed==1 (test_unwetterlauf_..., M8 rot)
- [x] AC-3 drei Compare-Läufe je eigener Test (M8a/b/c einzeln rot)
- [x] AC-4 Deadline bleibt partial, failed getrennt (M2c; Runde 2 N1a-d rot)
- [x] AC-5 Fairness-Stempel vor try, Radar + Unwetter (M1/M1b/M1d; Runde 2 N3 rot)
- [x] AC-6 ERROR-Log mit ID + Stacktrace (M13/M13b rot)
- [x] AC-7 Go-Panic in recordRun: error 'panic in <jobID>', Sperre frei (M5/M7 rot)
- [x] AC-8 Panic in Nutzer-Goroutine: sofortiger Fehler, andere Nutzer bedient (M6 rot)
- [x] AC-9 Ratsche ohne B9-B11c, Rückdreh-Gegenprobe rot (R9)
- [x] AC-10 Zwei-Nutzer-Trennung, kein default (M3d/M9b rot)
- [x] AC-11 Briefing: Folge-Trip bedient, kein Vermerk (M9/M14/M18 rot)
- [x] AC-12 _get_active_trips je Trip geschützt (M14b/M19 rot)
- [x] AC-13 skip_next unverbraucht (M10 rot)
- [x] AC-14 Compare-Fälligkeit/Auto-Pause je Preset (M9b/M9c/M11/M12 rot)
- [x] F005 Vorlauf-Sperre bei unlesbarer Fälligkeit (Runde 2 N5a-c rot)

VERDICT: VERIFIED (Runde 2) - keine ungefangene Mutation ausser den begruendet akzeptierten LOW-Punkten F002/F004/F006.

## Geprüfte Dateien

- sha256:e53477284434d9f37460b40aa01759038d55c661d08a1e0779430409d75b4e91  api/routers/scheduler.py
- sha256:f22020b0e41459afdc65fa814207ad049aaee19d2f828345485405e2166d3f8f  internal/scheduler/scheduler.go
- sha256:cc4d10d3625700d2df0cc657034698b4169bcd02becdf1ddf03045e762361ec2  src/services/alert_check_state.py
- sha256:74ea89104b243259832feb207e2c52986769905274ddaca5fcb7cd7906ce8ef8  src/services/compare_alert.py
- sha256:3c35ac2c63aadccca986549b1ba069f17dcd2741e183db3ad3b8e1f1ea5a36ef  src/services/compare_official_alert.py
- sha256:b98c20de077516a35af84613c5bb85db2c3bc183dc1c6e69dcf5d813ea8fdc1c  src/services/compare_radar_alert.py
- sha256:e8aa10720698c9b37ecd55a08133045f329c122aee45b42f9bdfb240bd5363d4  src/services/compare_slot_scheduler.py
- sha256:53ac86e534e357a8ab02fd30ccc47e185641a360d52910b0a0449da8cce5f1d9  src/services/dispatch_orchestrator.py
- sha256:429ee04e5b27c2cf53f3ebc8530cd8f3f149d910b7de02d1eac3cfe846c099a3  src/services/scheduler_dispatch_service.py
- sha256:685ad2a8053d70ca1b55e1f90e4f7c3b2d90d53f208896c11e151cc7620a3661  src/services/trip_alert.py
- sha256:f22d2ec69dfd98b2187324401bbfe62870b2859e79797a8a4c323759c6a25986  src/services/trip_report_scheduler.py

## Prüfbasis

- base: 416a8d027a0a91a59d5beaf045d2bba90d9c4cc6
- blob:8d08a2d53769aaa742c12584fdabb504b3945531  api/routers/scheduler.py
- blob:7cdde69298b5f23f02d86ce7c2c382d38d568abd  internal/scheduler/scheduler.go
- blob:3039bdd07a1fe301024d9de2d0de2e022a8021a6  src/services/alert_check_state.py
- blob:d352288608e2a42811de52ae3fe130a35cbc6430  src/services/compare_alert.py
- blob:fe9ca8cc2f3e354af472bb6a527426a243f1b323  src/services/compare_official_alert.py
- blob:52bd8c31b6e9618599117490c11b806060852f26  src/services/compare_radar_alert.py
- blob:01cfb02255fcfeb6e6d61fccd8136778b1b7398a  src/services/compare_slot_scheduler.py
- blob:e6ae623ff9d7d92490021696ec0dcbf39f302a31  src/services/dispatch_orchestrator.py
- blob:20b91eb38a8244be3aa2ff5c64ca2e124bac97d6  src/services/scheduler_dispatch_service.py
- blob:3d4472f240e3eebb076b1bb17d1a5118efeebe92  src/services/trip_alert.py
- blob:efacc97431577ebcbefc9d0e9516d54d5cf78c4f  src/services/trip_report_scheduler.py

## Runde 3 (Integration main #2526)

Tests: 97 passed (7 Python-Dateien, -v -rA, Ausgabe docs/artifacts/fix-2217-stapellauf-abschotten/adversary-test-output.txt), Go ./internal/... ok. Mutationen per String-Ersetzung mit Sicherungskopie, je per diff identisch zurueck; git diff --cached --stat unveraendert (23 files, +12253/-1330); ungestagte Aenderung nur das ueberschriebene Testausgabe-Artefakt.

| Mutation | rot |
|---|---|
| P1 recover in runRecovered weg | TestRecordRun_PanicInJob_RecordedAsErrorAndLockReleased |
| P2 Panic-Wert in lastRuns Error | TestRecordRun_PanicInJob_... und TestPanicInRecordRun_RecordedAsErrorAndLockReleased |
| P2b Panic-Wert im Fehler der Nutzer-Goroutine | NICHT gefangen (F007) |
| P3 recover in Nutzer-Goroutine weg | Testbinary stuerzt ab (Suite rot) |
| P4 cron.Recover weg | Testbinary stuerzt ab bei TestNew_CronChainRecoversPanicOutsideRecordRun (Suite rot) |
| P5 innerer Handler um trip_local_today | test_radar_run_skips_broken_trip_and_still_checks_next_trip[ortstag], test_radar_run_counts_broken_trip_as_failed_with_stacktrace[ortstag] |
| P5b innerer Handler um _resolve_alert_segment | dieselben Tests [segment] |

- [x] Go: runRecovered (scheduler.go:932), cron.Recover (scheduler.go:216) und Goroutinen-recover (scheduler.go:493) genau je einmal vorhanden, kein doppelter Schutz, kein toter safeCall mehr; Text in recordRun-Pfad exakt "panic in <jobID>" (Test prueft exakt, P2 rot).
- [x] F002 geschlossen: cron.Recover ist jetzt ueber TestNew_CronChainRecoversPanicOutsideRecordRun bewacht (P4 rot).
- [x] Python trip_alert.py: nur der aeussere Wrapper (trip_alert.py:2804-2811); innere Handler von main weg; Wiedereinsetzen (P5/P5b) wird von main's Isolationstest und dem neuen failed/Stacktrace-Test gefangen.
- [x] main's Isolationszusicherungen erhalten (tests/unit/test_radar_alert_trip_isolation.py: Eintrag nur von Trip B im alert_log, checked == 2, Stempel fuer A und B, ERROR-Log mit Trip-ID).
- [x] Go-Testpaket kompiliert und laeuft ohne Namenskollision (job_panic_isolation_test.go und scheduler_panic_test.go haben verschiedene Funktionsnamen).
Code reference: internal/scheduler/scheduler.go:496 — F007 (LOW): der Fehlertext der Nutzer-Goroutine ("panic in <jobID>") wird von keinem Test exakt geprueft (P2b gruen); der Text kann den Panic-Wert tragen, ohne dass ein Test rot wird. Abhilfe: in TestPanicInUserCall_* exakten Text pruefen. Fliesst nur in Nutzer-Fehlerflanke/Logs, nicht direkt in lastRuns -> kein Blocker.
Code reference: internal/scheduler/job_panic_isolation_test.go:19 — F008 (LOW, Redundanz): drei Tests duplizieren inhaltlich scheduler_panic_test.go:44/:113 (recordRun-Panic, Nutzer-Panic); keine Kollision, nur doppelte Pflege.
Code reference: internal/scheduler/scheduler.go:932 — Bestaetigung AC-7: Panic -> error "panic in <jobID>", Stack nur im Log, Sperre danach frei.
Code reference: src/services/trip_alert.py:2804 — Bestaetigung AC-1/AC-4/AC-6: aeusserer Schutz zaehlt failed, Deadline -> partial.
VERDICT: VERIFIED (Runde 3) - alle Pflicht-Mutationen ausser P2b gefangen; F007/F008 LOW, kein Blocker.

### Nachtrag Runde 3: F007 geschlossen

Orchestrator-Nachweis (Entwickler-Gegenprobe): TestPanicInUserCall_ReturnsErrorImmediatelyAndReleasesMarker prüft den Fehler jetzt exakt auf "panic in "+jobID (PO-Entscheid 2026-10-07). Mutation P2b (Panic-Wert in den Fehlertext der Nutzer-Goroutine) macht diesen Test rot; Original per diff identisch wiederhergestellt. F008 (Redundanz) LOW akzeptiert.
Code reference: internal/scheduler/scheduler_panic_test.go:113
- [x] F007 geschlossen: Fehlertext der Nutzer-Goroutine exakt bewacht (P2b rot)

VERDICT: VERIFIED (Runde 3 inkl. Nachtrag F007) - alle Pflicht-Mutationen gefangen; F004/F006/F008 LOW begruendet akzeptiert.

## Geprüfte Dateien

- sha256:e53477284434d9f37460b40aa01759038d55c661d08a1e0779430409d75b4e91  api/routers/scheduler.py
- sha256:000e6c3bf49f8352e0fa56a5b0f2f0c4037b3f399734974799d3a22cc14de224  internal/scheduler/job_panic_isolation_test.go
- sha256:96a48a3d194e494862924b0ccc5e1c69ef0b7465acd340212ea370cb4a73acf0  internal/scheduler/scheduler.go
- sha256:380c54cd7e028d11d892e6f19440b0a7a7b359987a53a35d15e1db71be45d385  internal/scheduler/scheduler_panic_test.go
- sha256:cc4d10d3625700d2df0cc657034698b4169bcd02becdf1ddf03045e762361ec2  src/services/alert_check_state.py
- sha256:74ea89104b243259832feb207e2c52986769905274ddaca5fcb7cd7906ce8ef8  src/services/compare_alert.py
- sha256:3c35ac2c63aadccca986549b1ba069f17dcd2741e183db3ad3b8e1f1ea5a36ef  src/services/compare_official_alert.py
- sha256:b98c20de077516a35af84613c5bb85db2c3bc183dc1c6e69dcf5d813ea8fdc1c  src/services/compare_radar_alert.py
- sha256:e8aa10720698c9b37ecd55a08133045f329c122aee45b42f9bdfb240bd5363d4  src/services/compare_slot_scheduler.py
- sha256:53ac86e534e357a8ab02fd30ccc47e185641a360d52910b0a0449da8cce5f1d9  src/services/dispatch_orchestrator.py
- sha256:429ee04e5b27c2cf53f3ebc8530cd8f3f149d910b7de02d1eac3cfe846c099a3  src/services/scheduler_dispatch_service.py
- sha256:685ad2a8053d70ca1b55e1f90e4f7c3b2d90d53f208896c11e151cc7620a3661  src/services/trip_alert.py
- sha256:f22d2ec69dfd98b2187324401bbfe62870b2859e79797a8a4c323759c6a25986  src/services/trip_report_scheduler.py

## Prüfbasis

- base: b8c799d05f9c7fee0a2fa0dcc183c1080add590e
- blob:8d08a2d53769aaa742c12584fdabb504b3945531  api/routers/scheduler.py
- blob:9cc81a6c3889caa1abdcf446a69e202e4d72343a  internal/scheduler/job_panic_isolation_test.go
- blob:1133e5896e70bc4a38504a270c53f4e9968355e5  internal/scheduler/scheduler.go
- blob:93c44099afec927ef8f80853aa9d95c43aa40cf0  internal/scheduler/scheduler_panic_test.go
- blob:3039bdd07a1fe301024d9de2d0de2e022a8021a6  src/services/alert_check_state.py
- blob:d352288608e2a42811de52ae3fe130a35cbc6430  src/services/compare_alert.py
- blob:fe9ca8cc2f3e354af472bb6a527426a243f1b323  src/services/compare_official_alert.py
- blob:52bd8c31b6e9618599117490c11b806060852f26  src/services/compare_radar_alert.py
- blob:01cfb02255fcfeb6e6d61fccd8136778b1b7398a  src/services/compare_slot_scheduler.py
- blob:e6ae623ff9d7d92490021696ec0dcbf39f302a31  src/services/dispatch_orchestrator.py
- blob:20b91eb38a8244be3aa2ff5c64ca2e124bac97d6  src/services/scheduler_dispatch_service.py
- blob:3d4472f240e3eebb076b1bb17d1a5118efeebe92  src/services/trip_alert.py
- blob:efacc97431577ebcbefc9d0e9516d54d5cf78c4f  src/services/trip_report_scheduler.py
