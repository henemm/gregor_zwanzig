# Adversary Dialog — rework-3331-validatoren-tempo
Spec: docs/specs/modules/rework_3331_validatoren_tempo.md
Datum: 2026-11-24 21:00

## Checkliste
- [x] **Input:** Lauf von `tests/tdd/test_einstellung_gleich_mail_validatoren.py` (seriell oder `-n 4 --dist loadgroup`).
- [x] **Output:** dieselben Ergebnisse (returncode, stdout, stderr, Log) wie über den Prozess, in kürzerer Zeit; je Validator mindestens ein echter Prozesslauf.
- [x] **Side effects:** je Worker ein Hintergrundprozess während des Laufs, danach keiner. Keine Produktdatei, kein angehobenes Timeout, `data/users/` bleibt unberührt.
- [x] **AC-1:** Given je ein grüner und ein roter Fall für `email_spec_validator` und `briefing_mail_validator` / When derselbe Fall über den echten Prozess und über den Server läuft / Then sind returncode, stdout und stderr gleich UND der Log-Inhalt gleich (bis auf Zeitangaben).
- [x] **AC-2:** Given der Server verdeckt durch vorgeladene Module einen fehlenden Pfad / When die Zieldatei je Validator einen unveränderten Prozesslauf mit `--konfig` fährt / Then wird ein fehlender Pfad zu `src` in diesem Prozesslauf rot, unabhängig davon, ob der Serverlauf ihn bemerkt.
- [x] **AC-3:** Given ein Serverlauf / When das Kind startet / Then ist `os.environ` vollständig ersetzt (kein Rest der Server-Umgebung), `TZ` ist per `time.tzset()` wirksam, das Arbeitsverzeichnis ist die Kopie und `sys.argv` stimmt.
- [x] **AC-4:** Given ein Lauf überschreitet die Frist / When der Klient die Frist erreicht / Then wird das Kind samt Enkelprozess per `killpg` beendet, es entsteht `subprocess.TimeoutExpired`, und der Folgelauf liefert das richtige Ergebnis.
- [x] **AC-5:** Given der Test wird während des Wartens abgebrochen (z. B. pytest-timeout) / When der nächste Lauf startet / Then bekommt er nie die Antwort des abgebrochenen Laufs, und das Kind des abgebrochenen Laufs ist samt Enkeln beendet.
- [x] **AC-6:** Given der Server stirbt oder `os.fork` fehlt / When ein Lauf angefragt wird / Then scheitert er laut (kein stiller Rückfall auf den Prozess), und der nächste Lauf startet den Server neu und gelingt.
- [x] **AC-7:** Given zwei Läufe nacheinander im selben Server / When der erste Umgebung, Sprache und Module verändert / Then sieht der zweite keinen Zustand des ersten (`sys.modules`, `os.environ`, Sprache).
- [x] **AC-8:** Given ein Validator, der `SystemExit` mit Zahl, `None` oder Text auslöst oder eine Ausnahme wirft / When er über den Server läuft / Then entsprechen returncode und Ausgabe dem echten Prozess (Zahl, 0, Text auf stderr mit 1; Ausnahme mit Traceback und 1).
- [x] **AC-9:** Given `validator_lauf` ohne Opt-in / When die übrigen Nutzer (alle in Dependencies genannten Dateien) laufen / Then nutzen sie weiter den echten Prozess und bleiben grün.
- [x] **AC-10:** Given ein Lauf mit Server und Browser ist beendet oder der Worker wurde hart beendet / When danach nach Prozessen gesucht wird / Then ist kein Server- und kein Browserprozess übrig.
- [x] **AC-11:** Given je Validator mindestens eine Verfälschung, die heute ein Test der Zieldatei fängt / When sie über den Server läuft / Then wird sie auch dort gefangen, im Stand vorher wie nachher.
- [x] **AC-12:** Given die Zieldatei vorher (Prozess) und nachher (Server) / When sie im selben Zeitfenster am selben Rechner seriell und unter `-n 4 --dist loadgroup` gemessen wird / Then liegt der Gewinn auf dem Mac bei mindestens 25 %, sonst wird der Umbau zurückgenommen.

## Dialog

### Runde 1
**Adversary:** (2026-11-24, Stand unmutiert, Mac, Worktree `rework-3279-testsuite-tempo`)

Testlaeufe (Vollausgabe `adversary-test-output.txt`): `tests/test_validator_server.py` 25 passed (`-n 4` und seriell), Zieldatei 149 passed (`-n 4` 96 s, seriell 289 s), `_lauf`-Importeure (`soll_placements`, `test_3047_r8py_luecken`, `test_validatoren_ausblick_3155`) 57 passed, weitere `validator_lauf`-Nutzer (11 Dateien, darunter `test_validatoren_lang_verdrahtung.py`, in der Spec nicht genannt) 174 passed. Kein Server-/Browserprozess uebrig nach unmutiertem Lauf.
Mutationen: 91 Eintraege in `mutationen-runde1.md` (4 davon als UNGUELTIG gekennzeichnet: Treiberfehler bei zwei Ersetzungen in derselben Datei, wiederholt). Hash vorher/nachher nach jedem Rueckspielen identisch, Arbeitsbaum-Status am Ende wie am Anfang.

**Findings**

- **F001 | HIGH | edge_case (flackernder Test) | `tests/helpers/validator_server.py:174-178` (Stand Runde 1: 172-174)**: `_lies` liest beim EOF sofort `self._stderr`, ohne den toten Server abzuwarten. Beim Absturz im Start kommt das EOF auf stdout teils VOR der Server-Meldung auf stderr; die Meldung lautet dann nur `Server tot: `. Spec AC-6: "scheitert laut ... mit klarer Meldung". Belege: Probe mit dem Ersatz-Server aus `test_ac6_ungeeigneter_server_scheitert_laut[zusatz-thread]` unter CPU-Last: 8 von 60 Laeufen leere stderr-Meldung (nach `wait()` steht sie da); `pytest -k "zusatz-thread or ohne-fork or fremde_kennung"` unter 14 Last-Prozessen: 3 von 28 Laeufen rot (`Regex pattern did not match ... Actual message: 'Server tot: '`); ein einzelner Fehlschlag auch ohne Last in der Mutation S25 (mit der Mutation nicht reproduzierbar). Folge: der Pflicht-Check `test` (CI, `-n 4`) kann zufaellig rot werden. Abhilfe: nach EOF `self._proc.wait(timeout=5)` (oder kurz pollen), dann stderr lesen.
- **F002 | MEDIUM | edge_case (unbewachte Schutzmassnahme) | `validator_server.py:62-63, 74-76, 105-106, 190-192`**: Die Absicherung des Starts bei Abbruch oder Server-Tod ist von keinem Test bewacht. Je einzeln mutiert, kein Test rot: Handschlag-Gate des Kindes `if sync.recv(1):` -> `if True:` (S24a), Server-Handschlag `assert hier.recv(1)` entfernt (S24b), fremde fds im Kind nicht schliessen (S25, nach Klaerung des Flackerns GRUEN), Nachlesen der Startzeile in `verwerfen` (S36). Spec AC-5: Kind des abgebrochenen Laufs "samt Enkeln beendet"; ein Abbruch VOR Eingang der Startzeile laesst bei Wegfall dieser Zweige ein laufendes Kind zurueck (bis 180 s Chromium). Abhilfe: deterministischer Test mit Ersatz-Server, der die Startzeile verzoegert, plus Abbruch in diesem Fenster.
- **F003 | LOW | edge_case (unbewacht) | `validator_server.py:89, 100-102, 68, 71, 116, 117, 136, 144, 164, 22`**: weitere Verfaelschungen ohne roten Test: Signaltod -> negativer returncode (`os.waitstatus_to_exitcode` -> `WEXITSTATUS`, S33; Probe: heute gleich dem Prozess), stdin des Servers nicht auf `/dev/null` (S22, Kind erbt Anfrage-Pipe), `dup2(2, 1)` (S23), `tempfile.tempdir = None` (S26), Kind-`sys.path` aus Server-Pfad (S31/S32), `PIPE_BUF`-Stuecke (S30), `_kennung/_kind` nach Erfolg nicht zuruecksetzen (S35; `killpg` auf wiederverwendete pid beim spaeteren `verwerfen`), Setup-Fehler im Kind still oder Exit 0 (S43/S44), konstante Kennung (S49; nur der Ersatz-Server prueft Kennungen), `START_FRIST` 60 -> 3600 (S27b). Gleichwertig und begruendet: S13 (`hasattr(os,"fork")`: ohne ihn stirbt der Server am `os.fork()` mit AttributeError "fork"), S20b (atexit allein, EOF genuegt; S20a und S20c ROT), S34 (`& 0xFF`, `os._exit` kuerzt), H4 (`_mail_trust`-Pfad allein).
- **F004 | LOW | spec_violation (Gleichheit Prozess/Server) | `validator_server.py:65-67`**: Interpreter-Startparameter des Laufs wirken im Kind nicht, weil der Server schon laeuft: `PYTHONIOENCODING`, `PYTHONUTF8`, `PYTHONWARNINGS`, `PYTHONHASHSEED`, `locale.getpreferredencoding` (Probe: je UNTERSCHIED), `__loader__` (None statt SourceFileLoader), Schliessen von `sys.stdout` im Validator (Server: Traceback, Prozess: 0), nicht-daemon-Threads (Server beendet sofort per `os._exit`), `atexit` (in den Known Limitations genannt). Heute ohne Wirkung auf die 241 Laeufe (die Zieldatei setzt keine solchen Variablen), aber nicht dokumentiert und von AC-1/AC-3 nicht erfasst. Abhilfe: in `gates_und_ratschen.md` und den Known Limitations nennen.
- **F005 | LOW | spec_violation (Prozess) | Spec "Estimated Scope", `docs/specs/modules/rework_3331_validatoren_tempo.md`**: Spec nennt Obergrenze 400 Zeilen und 5 Dateien; real 602 hinzugefuegte Zeilen (600 in `tests/`, 2 Doku) und 6 Dateien. Die PO-Anhebung auf 600 steht nur in `docs/context/rework-3331-validatoren-tempo.md`, nicht in der Spec (Frontmatter `status: draft` trotz Freigabe). Die Spec-Abhaengigkeiten nennen weder `tests/tdd/test_validatoren_lang_verdrahtung.py` (validator_lauf-Nutzer) noch `test_3047_r8py_luecken.py` und `test_validatoren_ausblick_3155.py` (laufen jetzt ueber den Server); alle drei sind gruen.
- **F006 | LOW | edge_case (bekannt, nicht testbar) | `validator_server.py:171-175`**: Signal-Ausnahme zwischen `read()` und `self._puffer += stueck` verliert eine gelesene Startzeile; `verwerfen` kann das Kind dann nicht per pid beenden. Fenster Mikrosekunden; vom Implementierer genannt, nicht nachgestellt.

**Confirmations** (alle mit Mutationsnachweis in `mutationen-runde1.md`)

- AC-1 CONFIRMED | `tests/test_validator_server.py:113-122` + `validator_server.py:108-110`: gepaarter Vergleich returncode/stdout/stderr/Log (ohne `validated_at`), vier Faelle (je Validator gruen/rot); S01 (stderr leer), S02 (returncode), S03 (stdout), S39 (stdout/stderr vertauscht) je ROT.
- AC-2 CONFIRMED | `test_validator_server.py:130-146`, Zieldatei `test_*_echter_prozess_mit_konfig` (Z. 280, 359), `mail_lang_fixture.py:177-182`: Entfernen von `-S` (Z3), `ohne_installiertes_src` (Z2), src-Pfade von email_spec (H1), `_soll` (H2), `_mail_lang` (H3, nur Selbstpruefung des Tests), briefing (H7) sowie ORTE-alle/TRIP-alle (H5, H6, H8, H9) machen den Prozesslauf rot; derselbe Eingriff bleibt im Serverlauf GRUEN (H5s, H6s), wie die Spec es nur protokolliert.
- AC-3 CONFIRMED | `test_validator_server.py:152-165`, `validator_server.py:65-70`: S04 (`environ.clear`), S05 (`chdir`), S06 (`tzset`), S07 (`argv`), S07b (`environ.update`) je ROT.
- AC-4 CONFIRMED | `test_validator_server.py:171-176`, `validator_server.py:33-35`: S08 (`killpg` -> `kill`), S21 (`setsid`), S40 (TimeoutExpired), S11 ROT.
- AC-5 CONFIRMED | `test_validator_server.py:187-227`, `validator_server.py:146-150, 177-178, 193-194`: S09 (nicht verwerfen), S10 (Kennung nicht pruefen), S11 (`killpg` beim Verwerfen) je ROT. Offene Luecken: F002, F003 (S35, S36, S49), F006.
- AC-6 teilweise: Verhalten CONFIRMED (`validator_server.py:114, 122-123`; S12 Rueckfall, S14 Thread, S37 Tot-Meldung ROT; `os.fork`-Pruefung gleichwertig), aber der Absicherungstest flackert (F001), deshalb nicht abgehakt.
- AC-7 CONFIRMED | `test_validator_server.py:262-271`, `validator_server.py:100-102`: S15 (Direktaufruf statt fork) ROT.
- AC-8 CONFIRMED | `test_validator_server.py:274-284`, `validator_server.py:38-55`: S16 (None als 1), S17 (Text), S18 (Traceback), S45 (flush), S46 (Traceback-Rahmen), S47-voll ROT. Luecke: Signaltod (F003).
- AC-9 CONFIRMED | `mail_lang_fixture.py:151`, `test_validator_server.py:297-307`: S19 (Standard ein) ROT, Z1 ROT; alle genannten Nutzerdateien gruen (57 + 174 passed).
- AC-10 CONFIRMED | `test_validator_server.py:313-362`, `validator_server.py:124, 131-132`: S20a (EOF-Ende) ROT, S20c (beides) ROT, S28/S28b (Serverfrist) ROT, S38 ROT; nach den unmutierten Laeufen kein Server, kein Chromium, kein `sleep` (Abschnitt 8 in `adversary-test-output.txt`); Probe: Browser ohne `close()` am Laufende ist im Prozess und im Server gleich weg.
- AC-11 CONFIRMED | Zieldatei: je Validator mindestens zwei Verfaelschungen, die die Zieldatei ueber den Server UND ueber den echten Prozess faengt: briefing (V1 Format-Pruefung, V3 Render-Pruefung `_check_rendered`), email_spec (V2 Ortsfolge, V6 "Ortsfolge nicht pruefbar"), gemeinsam (V5 "Spalte zu viel"); Stand vorher gruen.
- AC-12 CONFIRMED mit Vorbehalt | `messung-ac12.txt`: `-n 4` 153 -> 101 s (34 %) und 157 -> 99 s (37 %), seriell 460 -> 232 s (50 %) und 482 -> 287 s (41 %), alle Laeufe Exit 0, 149 passed, Wegzaehler 243/0 gegen 2/241; alle Werte klar ueber 25 %. Vorbehalt: der Serverlauf folgt stets direkt auf den Prozesslauf (Reihenfolge nie vertauscht), "Prozess" ist der neue Stand mit erzwungenem Prozessweg (inkl. `-S`), Last 2 bis 8,5 notiert. Linux/CI ungemessen.
- Side effects CONFIRMED: kein Produktcode (Diff gegen HEAD fuer `src` und `.claude/hooks` leer), Timeout bleibt 180 s, ein Server je Worker und danach keiner. Nicht gelaufen: Linux/CI (gedanklich: `PIPE_BUF` 4096, EPERM/ESRCH-Behandlung, `killpg` auf Zombie, Hauptthread des xdist-Workers fuer `signal.signal` in `test_ac5`; unter 14 Last-Prozessen lief die Absicherungsdatei dreimal gruen in 58 s).

**Implementierer:** (offen, Antwort ausstehend)

**Nachfragen fuer Runde 2 (an den Implementierer)**
1. F001: Behebung (Warten auf den toten Server vor dem Lesen von stderr) und Nachweis unter Last (mindestens 50 Laeufe von `-k "zusatz-thread or ohne-fork or fremde_kennung"` mit CPU-Last, null rot).
2. F002: Test fuer die Start-Absicherung (verzoegerte Startzeile, Abbruch im Fenster, Server-Tod vor Handschlag) oder begruendete Streichung der Zweige (S24a, S24b, S25, S36).
3. F003: je Punkt Test oder begruendeter Verzicht, mindestens Signaltod (negativer returncode) und stdin-Verhalten.
4. F004/F005: Doku (Known Limitations, gates_und_ratschen) um die nicht uebernommenen Startparameter ergaenzen; Spec-Obergrenze 600 und die zusaetzlichen Nutzer nachtragen.
5. Linux: gibt es einen Weg (Container), den Server dort einmal laufen zu lassen, oder bleibt es beim CI-Nachweis im PR?

### Runde 2
**Implementierer (Antworten, uebernommen):** (1) F001: `_lies` wartet bei EOF hoechstens 5 s auf das Serverende, Frist vorher geprueft, neuer Fall `meldung-nach-eof`; Flackernachweis 60 Laeufe unter Last, 0 rot. (2) F002: Vorspann STIRBT (S24a, S25), fehlendes cwd (S24b), Abbruch vor der Startzeile (S36); S25-Teile ein_fd/aus nicht einzeln mutiert. (3) F003: S22, S26, S31, S32, S33, S35, S43 rot; Verzicht auf S44, S23, S27b, S30, S49. (4) F004-F006: Spec-Known-Limitations, Changelog und `gates_und_ratschen.md` ergaenzt. (5) Linux: kein Container, Nachweis ist der CI-Lauf im PR.

**Adversary (Gegenpruefung, eigene Laeufe, Protokoll `mutationen-runde2.md`, 43 Mutationen, sha256 nach jedem Rueckspielen identisch, Arbeitsbaum-Status wie vor Runde 2):**

- **F001 behoben.** Code reference `tests/helpers/validator_server.py:174-178` (Warten, `wait(5)` in Z. 176) und `tests/test_validator_server.py:244-258` (Fall `meldung-nach-eof`). Eigene Messung unter 14 Last-Prozessen: 50 Laeufe `-k "ac6 or ac5_fremde"` seriell, 0 rot; dazu 30 Laeufe `-k "ac3 or ac4 or ac5 or ac6 or ac8"` mit `-n 4`, 0 rot (Runde 1 desselben Aufbaus: 3 von 28 rot). Warten entfernt (R-F001): `meldung-nach-eof` ROT, also deterministisch bewacht. Nicht gelaufen: Kontrollserie ohne Warten unter Last (der Fall ist ohnehin deterministisch rot). Die 5 s liegen unter dem pytest-Timeout von 30 s und enden sofort, wenn der Server tot ist.
- **F002 behoben bis auf Reste.** Selbst nachgestellt, je ROT: S24a `if sync.recv(1):` -> `if True:` (`validator_server.py:75`, Test `ac6[stirbt-vor-startzeile]`), S24b `assert hier.recv(1)` (`:104`, Test `ac6_gescheiterte_einrichtung...`), S25 alle fds (`:62-63`, `ac6[stirbt-vor-startzeile]`), S25 nur `hier` (ROT), S36 Nachlesen der Startzeile (`:190-192`, `ac5[vor-startzeile]`). Reste ohne roten Test: S25 nur `ein_fd` (gleichwertig: das Lesende der Anfrage-Pipe haelt kein EOF) und S25 nur `aus` (nicht gleichwertig: das Kind haelt dann das Schreibende der Antwort-Pipe; stirbt der Server bei laufendem Kind, meldet der Klient erst nach dem Ende des Kindes oder der Frist "Server tot" statt sofort). Siehe F007.
- **F003 behoben bis auf begruendete Verzichte.** Selbst nachgestellt, je ROT: S22 (stdin), S26 (tempdir), S31, S32 (sys.path), S33 (Signaltod, Test `ac8[signal]`), S35 (`_kind` zuruecksetzen, Test `ac3`), S43 (Setup-Fehler still). Verzichte bewertet: S44 (Exit-Code des Kindes nach gescheitertem Handschlag) gleichwertig, weil der Server am `assert` abbricht und der Code nie gelesen wird; S23 (`dup2(2, 1)`) bleibt unbewacht, die Begruendung (Fremdausgabe scheitert laut in `json.loads`) ist schluessig, ein Vorab-Modul druckt heute nichts; S49 (konstante Kennung) bewacht der Ersatz-Server-Fall; S27b (START_FRIST) und S30 (PIPE_BUF) bleiben ungetestete Zeitgrenze bzw. Grenzfall, beide ohne Folge fuer die ACs (LOW, hingenommen).
- **F004, F005, F006 behoben (Doku).** `docs/reference/gates_und_ratschen.md` und Spec Known Limitations nennen Startparameter, Threads, Abbruchfenster, sechste Datei und weitere Nutzer. Zeilen gegen 742c42c22: in `tests/` genau 600 hinzugefuegte Zeilen (17 + 206 + 1 + 18 + 358) = PO-Obergrenze, keine Reserve; Spec-Frontmatter steht weiter auf `draft` (kosmetisch).
- **Neu: Umstrukturierung der Tests geprueft** (Vergleich mit dem Commit-Stand der RED-Tests). Entfernte try/finally werden durch die Fixture `klient` ersetzt (`test_validator_server.py:42-45`, `k.verwerfen()` im Abbau), `_vs()` durch Modulimport (Z. 22), Banner sind reine Kommentare. Keine Zusicherung geschwaecht: die Runde-1-Stichproben S08, S09, S10, S11, S12, S14, S15, S16, S18, S19, S20a, S20c (als R-S20c), S21 bleiben ROT; S13, S20b, S34 gleichwertig GRUEN wie zuvor; R-S47, R-S28, R-S29, R-S37 ROT. Der Fall `ac8` vergleicht jetzt auch `sys.path` und Signaltod, `ac3` stdin, tmp und `_kind`; `ac5` hat zwei Abbruchstellen. Der Fall `ac5[vor-startzeile]` ersetzt `klient._lies` per Instanzattribut und schlaeft 20 s, bis das Signal kommt; das ist deterministisch, weil das Signal erst nach dem Pid-Dateieintrag des Kindes ausloest.
- **F007 | LOW | edge_case | `validator_server.py:62-63` (`aus.fileno()` in der Liste Z. 102)**: das Schliessen des Schreibendes der Antwort-Pipe im Kind ist unbewacht (R-S25aus GRUEN). Abhilfe: Test, der den Server bei laufendem Kind hart beendet und `ServerFehler` binnen weniger Sekunden erwartet. Nicht blockierend.
- **F008 | LOW | edge_case | `validator_server.py:174-178`**: das Warten laeuft nach der Fristpruefung; die Fristpruefung selbst (R-F001b entfernt) ist unbewacht. Folge nur: bis zu 5 s ueber die Frist, nie ueber den pytest-Timeout. Nicht blockierend.

**Schlusslaeufe, unmutiert** (`adversary-test-output.txt`, Schlusszeilen enthalten, keine Mutationslaeufe darin): `tests/test_validator_server.py` 30 passed (`-n 4` 25 s, seriell 62 s); Zieldatei 149 passed (`-n 4` 85 s, seriell 281 s); `_lauf`-Importeure 57 passed; weitere `validator_lauf`-Nutzer 174 passed. Danach Server 0, `sleep 60` 0, Chromium 0.

**Code references (aktuell)**
- AC-1: `tests/test_validator_server.py:121`, `tests/helpers/validator_server.py:108-110`
- AC-2: `tests/test_validator_server.py:135`, `tests/helpers/mail_lang_fixture.py:176-186`, `tests/tdd/test_einstellung_gleich_mail_validatoren.py:283, 362`
- AC-3: `tests/test_validator_server.py:154`, `validator_server.py:64-70`
- AC-4: `tests/test_validator_server.py:172`, `validator_server.py:33-35`
- AC-5: `tests/test_validator_server.py:185, 219`, `validator_server.py:146-150, 177-182, 185-198`
- AC-6: `tests/test_validator_server.py:233, 250, 260`, `validator_server.py:113-123, 166-181`
- AC-7: `tests/test_validator_server.py:265`, `validator_server.py:99-101`
- AC-8: `tests/test_validator_server.py:281`, `validator_server.py:38-55, 89`
- AC-9: `tests/helpers/mail_lang_fixture.py:152`, `tests/test_validator_server.py:297, 304`, `tests/tdd/test_einstellung_gleich_mail_validatoren.py:239`, `tests/tdd/test_einstellung_gleich_mail_soll_placements.py:490`
- AC-10: `tests/test_validator_server.py:311, 339`, `validator_server.py:124, 128-132`
- AC-11: `tests/tdd/test_einstellung_gleich_mail_validatoren.py:239` (`_lauf`; Mutationen V1 bis V6 in `mutationen-runde1.md`)
- AC-12: `docs/artifacts/rework-3331-validatoren-tempo/messung-ac12.txt`

**Nicht gelaufen:** Linux/CI; Neumessung AC-12; Kontrollserie ohne Warten unter Last; Test zu F007/F008.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict
**VERIFIED** (Runde 2): kein HIGH oder MEDIUM offen; F007 und F008 sind LOW. Vorbehalt: Linux/CI ist nicht gelaufen und bleibt der Nachweis im PR (Pflicht-Check `test`).

Nachtrag F001: Stuetze ist die eigene Messung (Serie A 30 x 17 Tests, Serie B 50 x 8 Tests, 0 rot, siehe mutationen-runde2.md); der Implementierer-Nachweis flacker-nachweis.txt ("1 gruen" je Lauf, Testzahl unklar) wird nicht herangezogen.

**Confirmation-Bloecke (Schema)**

Confirmation:
  AC: AC-1
  Code reference: tests/test_validator_server.py:121
  Evidence: gepaarter Vergleich returncode/stdout/stderr/Log; Mutationen S01, S02, S03, S39 rot
  Status: CONFIRMED

Confirmation:
  AC: AC-1
  Code reference: tests/helpers/validator_server.py:108
  Evidence: Antwort mit returncode, stdout, stderr aus dem Kind
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: tests/test_validator_server.py:135
  Evidence: Prozesslauf bemerkt fehlenden src-Pfad; Z2, Z3, H1-H9 rot
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: tests/helpers/mail_lang_fixture.py:181
  Evidence: ohne_installiertes_src: Prozess mit -S und purelib
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: tests/tdd/test_einstellung_gleich_mail_validatoren.py:283
  Evidence: echter Prozesslauf mit --konfig (Trip)
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: tests/tdd/test_einstellung_gleich_mail_validatoren.py:362
  Evidence: echter Prozesslauf mit --konfig (Orte)
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: tests/helpers/validator_server.py:65
  Evidence: environ.clear/update, tzset, chdir, argv; S04-S07b, S22, S26, S31, S32 rot
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: tests/test_validator_server.py:154
  Evidence: Kind meldet Umgebung, Zeitzone, cwd, argv, stdin, tmp
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: tests/helpers/validator_server.py:35
  Evidence: killpg auf die Kindgruppe; S08, S21, S40 rot
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: tests/test_validator_server.py:172
  Evidence: Frist beendet Kind und Enkel, Folgelauf stimmt
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: tests/helpers/validator_server.py:146
  Evidence: verwerfen nach jeder Ausnahme; S09, S10, S11, S36 rot
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: tests/test_validator_server.py:185
  Evidence: Abbruch vor Startzeile und vor Ergebnis
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: tests/helpers/validator_server.py:113
  Evidence: fork- und Thread-Pruefung beim Start; S12, S14, S37 rot
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: tests/test_validator_server.py:250
  Evidence: ungeeigneter Server scheitert laut, auch meldung-nach-eof und stirbt-vor-startzeile
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: tests/helpers/validator_server.py:99
  Evidence: je Anfrage os.fork; S15 rot
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: tests/test_validator_server.py:265
  Evidence: zweiter Lauf sieht keinen Zustand des ersten
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: tests/helpers/validator_server.py:38
  Evidence: Exit-Regeln Zahl, None, Text, Ausnahme, Signal; S16, S17, S18, S33, S45, S46 rot
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: tests/test_validator_server.py:281
  Evidence: gepaarter Vergleich gegen den echten Prozess
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: tests/helpers/mail_lang_fixture.py:152
  Evidence: im_server Standard False; S19 rot
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: tests/tdd/test_einstellung_gleich_mail_validatoren.py:239
  Evidence: _lauf schaltet den Server ein, prozess=True bleibt Prozess
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: tests/tdd/test_einstellung_gleich_mail_soll_placements.py:490
  Evidence: prozess=True in der Abnahme (Mutation Z4 gleichwertig gruen)
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: tests/test_validator_server.py:297
  Evidence: Opt-in-Zaehler; alle Nutzerdateien gruen
  Status: CONFIRMED

Confirmation:
  AC: AC-10
  Code reference: tests/helpers/validator_server.py:124
  Evidence: EOF-Ende des Servers; S20a, S20c, S28 rot
  Status: CONFIRMED

Confirmation:
  AC: AC-10
  Code reference: tests/test_validator_server.py:311
  Evidence: Server verschwindet mit dem Worker, auch bei SIGKILL
  Status: CONFIRMED

Confirmation:
  AC: AC-11
  Code reference: tests/tdd/test_einstellung_gleich_mail_validatoren.py:239
  Evidence: je Validator Verfaelschungen V1-V6 ueber Server und Prozess rot
  Status: CONFIRMED

Confirmation:
  AC: AC-12
  Code reference: tests/test_validator_server.py:1
  Evidence: Messnachweis liegt in docs/artifacts/rework-3331-validatoren-tempo/messung-ac12.txt, 34-50 Prozent
  Status: CONFIRMED

**Finding-Bloecke (offen, LOW)**

Finding:
  ID: F007
  Severity: LOW
  Category: edge_case
  Code reference: tests/helpers/validator_server.py:102
  Description: Das Kind schliesst das Schreibende der Antwort-Pipe (aus.fileno()), kein Test bewacht es (R-S25aus gruen).
  Spec requirement: AC-5/AC-6 - Server-Tod wird laut gemeldet
  Conflict: bei Server-Tod mit laufendem Kind kommt die Meldung erst nach dem Kind oder der Frist
  Remediation: Test mit hart beendetem Server bei laufendem Kind

Finding:
  ID: F008
  Severity: LOW
  Category: edge_case
  Code reference: tests/helpers/validator_server.py:174
  Description: Fristpruefung vor dem 5-s-Warten in _lies hat keinen roten Test (R-F001b gruen).
  Spec requirement: AC-4 - Frist wird eingehalten
  Conflict: Meldung kann bis zu 5 s nach der Frist kommen, nie ueber den pytest-Timeout
  Remediation: Test mit EOF kurz vor der Frist

## Geprüfte Dateien

- sha256:60d8a171ebbae048307a59078f8dd9008e0b674c3155d1e9db912af330d6a39e  tests/helpers/mail_lang_fixture.py
- sha256:564312edf3fec02b4a9e53c5d4666cf7ac749608a472af99dc795497ce6dd0bd  tests/helpers/validator_server.py
- sha256:8c61adf971e01e1fb4d852a8e34048724f69f4c4c39ff19b31d61b70877d668b  tests/tdd/test_einstellung_gleich_mail_soll_placements.py
- sha256:d8db1d2d810fabab0ab74fe4a71aa2a38eb6224a43e56059fea6aa8e1feb478d  tests/tdd/test_einstellung_gleich_mail_validatoren.py
- sha256:a89409f8a3a01129d108b33c7e25b0b4490db454483fea1b1aec90a0f9a39fb5  tests/test_validator_server.py

## Prüfbasis

- base: 742c42c22f06f7836e9f81de5428d4001eda9c27
- blob:ce7e2d9d23e4632fbbd31bb8e1ecb2f34b3056b8  tests/helpers/mail_lang_fixture.py
- blob:a9874fe1916a79fcddc867ce0bee8b155411d44c  tests/helpers/validator_server.py
- blob:864b10c5e665da71840232806a4b2aa1e665e963  tests/tdd/test_einstellung_gleich_mail_soll_placements.py
- blob:fea1bbeb3124ad357d64dbb91e675ab736bc21c9  tests/tdd/test_einstellung_gleich_mail_validatoren.py
- blob:1fc3f7ba97a46a6d0c73bda96182bc9647c2c8ef  tests/test_validator_server.py

## Geprüfte Dateien

- sha256:60d8a171ebbae048307a59078f8dd9008e0b674c3155d1e9db912af330d6a39e  tests/helpers/mail_lang_fixture.py
- sha256:564312edf3fec02b4a9e53c5d4666cf7ac749608a472af99dc795497ce6dd0bd  tests/helpers/validator_server.py
- sha256:8c61adf971e01e1fb4d852a8e34048724f69f4c4c39ff19b31d61b70877d668b  tests/tdd/test_einstellung_gleich_mail_soll_placements.py
- sha256:d8db1d2d810fabab0ab74fe4a71aa2a38eb6224a43e56059fea6aa8e1feb478d  tests/tdd/test_einstellung_gleich_mail_validatoren.py
- sha256:a89409f8a3a01129d108b33c7e25b0b4490db454483fea1b1aec90a0f9a39fb5  tests/test_validator_server.py

## Prüfbasis

- base: 742c42c22f06f7836e9f81de5428d4001eda9c27
- blob:ce7e2d9d23e4632fbbd31bb8e1ecb2f34b3056b8  tests/helpers/mail_lang_fixture.py
- blob:a9874fe1916a79fcddc867ce0bee8b155411d44c  tests/helpers/validator_server.py
- blob:864b10c5e665da71840232806a4b2aa1e665e963  tests/tdd/test_einstellung_gleich_mail_soll_placements.py
- blob:fea1bbeb3124ad357d64dbb91e675ab736bc21c9  tests/tdd/test_einstellung_gleich_mail_validatoren.py
- blob:1fc3f7ba97a46a6d0c73bda96182bc9647c2c8ef  tests/test_validator_server.py
