# Context: rework-3331-validatoren-tempo

## Request Summary
Issue #3331 (Scheibe B zu #3317, Teil von #1196): die Testdatei der Mail-Validatoren (455 s auf dem Mac, 147 Tests) beschleunigen, ohne eine Zusicherung zu schwächen. Zuerst Messversuch mit vorgewärmtem Fork-Server in `validator_lauf`; unter ca. 25 % Gewinn begründet belassen.

## Intake
Summe 4 (Scope 1, Blast Radius 1, Unsicherheit 2), voller Prozess. Branch `rework-3331-validatoren-tempo` von `origin/main` (61ae0e9fb), Worktree-Ordner heißt weiter `rework-3279-testsuite-tempo`. #3317 ist geschlossen, PR gemergt.

## Related Files
| Datei | Rolle |
|---|---|
| `tests/helpers/mail_lang_fixture.py:151-176` | `validator_lauf`: Hook-Kopie nach `tmp_path/repo`, `src` als Symlink, `git init`, dann `subprocess.run([sys.executable, <validator>.py, --eml, …], timeout=180, cwd=kopie)`; Rückgabe (CompletedProcess, Log-Ordner) |
| `tests/tdd/test_einstellung_gleich_mail_validatoren.py` | 2164 Zeilen; lokaler `_lauf` (Z. 239) ist die einzige `validator_lauf`-Aufrufstelle der Datei; nutzt returncode, stdout, stderr |
| `.claude/hooks/email_spec_validator.py`, `briefing_mail_validator.py` | unverändert lassen. Modulebene: `sys.path.insert`, `app.*`/`i18n`/`output.*`-Importe (nur email_spec), Hilfsmodule `_e2e_paths`, `_validator_log`, `_mail_trust`, dazu lazy `_mail_lang` und `_soll_aus_konfiguration` |
| `.claude/hooks/briefing_mail_validator.py:488` | `_check_rendered`: echter Chromium, zwei Breiten; `browser.close()`/`ctx.stop()` im finally |

## Dependents (weitere Nutzer von `validator_lauf`, per grep)
`tests/test_{alarm,vergleichs_mail,amtliche_warnungen}_validator_zweisprachig.py`, `tests/unit/test_{briefing_mail_validator,alarm_mail_validatoren,compare_mail_validator,briefing_html,briefing_compact_plain}_sprache.py`, `tests/tdd/test_{gate_testmails_zweisprachig,validatoren_lang_pflicht,einstellung_gleich_mail_soll_placements}.py`. Sie rufen auch `official_alert_mail_validator` und `radar_alert_mail_validator`; einige nutzen `log_dir`. Nur andere Helfer der Datei importiert `tests/helpers/amtliche_warnungen_fixture.py`; `test_validatoren_lang_verdrahtung.py` nennt `validator_lauf` nur im Text.

## Existing Patterns
- Kein fork/forkserver in `tests/`/`src/` (grep); `multiprocessing.Process` nur in `tests/tdd/test_file_lock_timeout.py`, `runpy` nur in `tests/unit/test_secret_output_gate.py`.
- pytest: `timeout = 30` global je Test. CI laut Context von #3317: `-n 4 --dist loadgroup`. Python 3.12.15, Mac mit 10 Kernen.

## Existing Specs
- `docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md` §6 (laut Testdatei-Kopf: Validatoren laufen als Prozess mit `--eml`)
- `docs/specs/modules/rework_3317_wartezeiten_tempo_s1.md` (Scheibe A)
- Messwerte und Fallen: `docs/context/rework-3317-wartezeiten.md` (Abschnitt Gegenprüfung, Punkt 5)

## Risks & Considerations
- Geschwächte Isolation: Modulzustand, `os.environ`, cwd, `src` aus dem Original statt aus der Kopie (die Kopie ist ein Symlink darauf; ob `__file__`-Pfade abweichen, ist zu prüfen).
- macOS-fork mit Threads; je xdist-Worker ein Server; Aufräumen bei Abbruch.
- `briefing_mail_validator` verbringt die Zeit laut Profil überwiegend im Browser; dort ist der Gewinn voraussichtlich klein. Der Anteil von Trip- und Orte-Läufen an den 455 s ist NICHT gezählt.
- Die Zeit für den Mailaufbau in den Tests selbst ist NICHT getrennt gemessen.

## Offen für die Analyse
1. Laufzahl je Validator und Zeitanteil (Validator gegen Mailaufbau) in der Testdatei messen.
2. Wegwerf-Prototyp Fork-Server im Scratchpad, Vorher/Nachher auf demselben Rechner, seriell und `-n 4`.
3. Entscheidung an der 25-%-Schwelle.

## Analysis (24.11.2026)

### Type
Feature/Rework (nur Testinfrastruktur, keine Produktdateien, Validatoren unverändert).

### Gemessen (Mac, 10 Kerne, Last 3,5 bis 8,5, Wanduhr je Lauf aus den Zeitstempeln des Messskripts, ganze Datei, 147 grün in JEDEM Lauf)
| Variante | Prozess (heute) | Fork-Server (Prototyp) | Gewinn |
|---|---|---|---|
| seriell, Lauf 1 | 392 s | 222 s | 43 % |
| seriell, Lauf 2 | 411 s | 242 s | 41 % |
| `-n 4 --dist loadgroup`, Lauf 1 | 180 s | 107 s | 41 % |
| `-n 4 --dist loadgroup`, Lauf 2 | 182 s | 108 s | 41 % |

- Reihenfolge abwechselnd Prozess/Fork; zu Beginn lief evtl. noch ein fremder Testlauf. Der Altwert 455 s ist NICHT als Vorher-Wert verwendet. Im Abschluss Vorher/Nachher im selben Zeitfenster neu messen.
- 241 Validator-Läufe: 120 `briefing_mail_validator`, 121 `email_spec_validator`. Anteil an der Testzeit (seriell, Lauf 1, Summe 390 s): Validatoren 246 + 119 = 365 s (93 %); der Rest (Mailaufbau, Kopie, Testrahmen) zusammen rund 25 s.
- Median je Lauf: email_spec 0,97 -> 0,22 s; briefing 2,14 -> 1,59 s (Rest ist echter Chromium). Server-Start 0,7 bis 1,3 s je Worker.
- Gepaart (jeder Lauf auf beiden Wegen nacheinander): 241 von 241 gleich in returncode, stdout, stderr. NICHT verglichen: Log-Dateien, `official_alert_`/`radar_alert_mail_validator`, Linux/CI. Gleichheit gilt für den heutigen Stand, sie belegt nicht, dass künftige Fehler gleich auffallen.
- Nach den Läufen keine Server- oder Browserprozesse übrig (pgrep auf `vfork_server`, `chrome-headless`, `headless_shell`).

**Entscheidung an der 25-%-Schwelle: umsetzen** (41 bis 43 %).

### Geprüfter Importzustand des Servers (124 src-Module)
- `output/renderers/email/helpers.py`: `_DEPLOYED_COMMIT` läuft beim Import als git-Aufruf im Arbeitsordner; im Server eingefroren (heute ebenfalls je Prozess einmal). Andere Umgebungszugriffe liegen in Funktionen (`app/config.py:33,305`, `loader.py:1406`, `parallel_fetch._env_int`, `base.py:253`, `radar_service.py`) oder sind `__file__`-Pfade. `parallel_fetch` hält Thread-Pool/Semaphore erst bei Gebrauch.
- Der Server nimmt die Umgebung des ersten Aufrufs für Importe an; je Lauf wird sie im Kind ersetzt.

### Prototyp (Wegwerf, Vorlage für die Umsetzung)
Server: Importe, Prüfung „nur ein Thread", dann je Anfrage eine JSON-Zeile; `os.fork`, stdin von `/dev/null`, stdout/stderr in Dateien, `os.environ` ersetzt, `chdir`, `sys.argv`, `sys.path` = Skriptordner + Grundpfad (src muss der Validator selbst ergänzen), `runpy.run_path(..., "__main__")`, SystemExit-Regeln, `os._exit`; Elternteil wartet mit Frist und sendet SIGKILL. Vorab geladen: argparse, email, imaplib, json, re, tempfile, subprocess, html, dataclasses, math, `app.metric_catalog`, `app.loader`, `app.ampel_templates`, `i18n`, `i18n.catalog`, `output.renderers.{compare_hourly_metric_ids,channel_layout,compare_metric_catalog,email.helpers}`, `playwright.sync_api` (nur Import, Browser startet erst im Kind).
NICHT vorgeladen: Hook-Module (`_soll_aus_konfiguration`, `_mail_lang`, ...): kommen je Lauf frisch aus der Kopie.

### Gegenprüfung (Plan-Agent, nur Codelesen) und maßgeblicher Ansatz
Geht bei Widerspruch dem Prototyp vor. Explore-Teilagenten ausgelassen (Context lag vor).
1. **Opt-in:** `validator_lauf` bleibt im Standard der echte Prozess; nur `_lauf` der Zieldatei schaltet den Server ein (Argument, keine Umgebungsvariable). Die anderen Aufrufer bleiben unverändert; die 241/241-Gleichheit gilt nur für `email_spec_` und `briefing_mail_validator`.
2. **Schwächung und Ausgleich:** Vorgeladene Module verdecken einen fehlenden/falschen `sys.path`-Eintrag im Validator. Daher je Validator mindestens ein unveränderter Prozesslauf MIT `--konfig` (nur dann wird `_soll_aus_konfiguration` geladen). Die übrigen `briefing`-Aufrufer, die ich per grep gesehen habe, rufen ohne `--konfig` (nicht jede Zeile einzeln gelesen): der Lauf muss ausdrücklich angelegt werden.
3. **Desynchronisation (wichtigster Fehler des Prototyps):** bricht pytest-timeout (30 s) den Test während des Wartens ab, liest der nächste Lauf die alte Antwort. Server nach JEDER Ausnahme/Frist verwerfen und neu starten; zusätzlich Anfrage-Kennung in der Antwort. Antwort-Lesen mit Frist. Frist überschritten = `subprocess.TimeoutExpired` wie heute.
4. **Server tot (EOF):** laut scheitern und beim nächsten Lauf neu starten; KEIN stiller Rückfall auf den Prozess.
5. **Enkel:** Kind per `os.setsid`, bei Frist `os.killpg` (Chromium/Node-Treiber). Server endet bei EOF auf stdin, auch bei hart beendetem xdist-Worker (Ende durch `atexit`, sonst EOF).
6. **Umgebung:** Server startet mit der Umgebung des ersten Aufrufs; im Kind vollständig ersetzt. Der Agent vermutet Env-Zugriffe beim Import; meine Suche fand in den 124 src-Modulen nur `_DEPLOYED_COMMIT` (git im Arbeitsordner). Fremdpakete nicht durchsucht. Hash-Seed ist je Server fest statt je Lauf zufällig (hingenommen). `TZ`: ob ein Test sie je Lauf setzt, NICHT geprüft; falls ja, `time.tzset()` im Kind.
7. **Socket-Sperre:** wirkt auch heute nicht im Unterprozess, also unverändert.
8. **Nachgerechnet:** Der Gewinn verteilt sich seriell (Lauf 1) etwa zur Hälfte: briefing 246 -> 165 s, email_spec 119 -> 30 s. Die Aussage des Agenten, fast alles komme aus email_spec, ist falsch. Geteilter Chromium ist ohne Änderung am Validator nicht möglich.

9. **Nachtrag RED (gemessen 24.11.2026), geht der Spec bei AC-2 vor:** `src` liegt ueber die editierbare Installation (`__editable__.gregor_zwanzig-0.2.0.pth`) in jedem Prozess im Suchpfad. Mit allen fuenf entfernten `src`-Ergaenzungen blieb der normale Prozesslauf von `email_spec_validator` ohne Importfehler; erst `python -S` mit `PYTHONPATH=<site-packages>` gab `ModuleNotFoundError: app`. `briefing` war mit der Messkonfiguration nicht aussagekraeftig (Exit 2 in allen Faellen). Der Prozesslauf fuer AC-2 muss deshalb das installierte `src` ausblenden (`-S` + site-packages im `PYTHONPATH`); der Validator bleibt unveraendert.

### Schnittstelle, die die RED-Tests festlegen
- `tests/helpers/validator_server.py`: `SERVER_SKRIPT`, `ServerFehler`, `GEMEINSAM` (ein `Klient` je Worker), `Klient(server_skript=SERVER_SKRIPT)` mit `lauf(skript, args, *, env, cwd, timeout=180)` -> `CompletedProcess`, `pid`, `verwerfen()`.
- Zeilen je Anfrage: Anfrage `{"kennung", ...}`; Antwort 1 `{"kennung", "pid"}` (Prozessgruppe, VOR dem Warten; Kind muss `setsid` schon ausgefuehrt haben), Antwort 2 `{"kennung", "returncode", "stdout", "stderr"}`. Fremde Kennung in beiden Zeilen = `ServerFehler`; `killpg` nie auf eine pid aus einer fremden Zeile, `ProcessLookupError` dulden.
- Frist auch im Server durchsetzen (hart beendeter Worker, Kind haengt: Server, Kind und Enkel enden spaetestens kurz nach der Frist).
- `ServerFehler` enthaelt die stderr-Ausgabe des Servers (Meldungen mit "fork" bzw. "Thread"). Traceback ohne runpy-Rahmen, gleich dem echten Prozess.
- Playwright startet Chromium unter POSIX vermutlich in eigener Prozessgruppe (nicht geprueft); `test_ac10_browser_weg_nach_frist` entscheidet, ob `killpg` reicht.
- `validator_lauf(..., im_server=False)`; `_lauf(..., prozess=False)` der Zieldatei: Standard Server, `prozess=True` = echter Prozess ohne installiertes `src`.

- **Umfang:** PO hat die Obergrenze am 24.11.2026 von 400 auf 600 Zeilen angehoben (376 davon stehen mit den RED-Tests schon im Commit, zaehlen also mit).

### Affected Files
| File | Change | Beschreibung |
|---|---|---|
| `tests/helpers/validator_server.py` | CREATE | Server (als Skript startbar) und Klient; Kind-Ablauf, Start, Anfrage, Ende je eigene Funktion |
| `tests/helpers/mail_lang_fixture.py` | MODIFY | `validator_lauf`: Opt-in-Argument, sonst unverändert |
| `tests/tdd/test_einstellung_gleich_mail_validatoren.py` | MODIFY | `_lauf` schaltet ein; je Validator ein echter Prozesslauf mit `--konfig` |
| `tests/test_validator_server.py` (Name offen) | CREATE | Absicherung des Servers |
| `docs/reference/gates_und_ratschen.md` | MODIFY (falls dort beschrieben) | Hinweis |

### Pflicht-Absicherung des Servers (Grundlage der ACs)
1. Prozess und Server liefern je Validator in einem grünen und einem roten Fall dasselbe (returncode, stdout, stderr) UND denselben Log-Inhalt (bis auf Zeitangaben): Logs sind bisher NICHT verglichen.
2. Umgebung vollständig ersetzt (Mutation: `environ.clear()` weg), `chdir` (Mutation: weg), `sys.argv` richtig.
3. Frist tötet Kind samt Enkel; der nächste Lauf ist korrekt. Mutation: `killpg` auf `kill`.
4. Abbruch während des Wartens führt nie zu vertauschter Antwort.
5. Server-Tod: lautes Scheitern, danach Neustart.
6. Kein Überspringen von Zustand zwischen zwei Läufen (`sys.modules`, `os.environ`, Sprache).
7. `SystemExit` mit Zahl, None, Text wie im echten Prozess; ungefangene Ausnahme gibt 1 und Traceback.
8. Mutations-Gegenprobe an der Zieldatei: eine Verfälschung eines Validators, die heute ein Test fängt, wird auch über den Server gefangen; je Validator mindestens eine, gegen den Stand vorher und nachher.

### Scope Assessment
- Dateien: 4 bis 5. Geschätzt 230 bis 345 neue Zeilen (Agent: 120 + 60 + 15 + 150), Grenze 250 voraussichtlich knapp oder überschritten: in der Spec benennen, Absicherung nicht kürzen.
- Risiko: mittel (geteilter Helfer, durch Opt-in begrenzt; keine Produktdateien).

### Open Questions
- [ ] Linux/CI-Laufzeit ungemessen: im PR belegen (Laufzeit der Datei im CI-Job `test` vorher/nachher, soweit die Ausgabe sie zeigt).
- [ ] Nur eine Einzelperson-Messreihe auf dem Mac; Vorher/Nachher nach der Umsetzung neu messen.

### Stand Phase 6b (24.11.2026, Wiedereinstieg nach /clear)
- Implementierung fertig, **noch nicht committet** (Commit-Gate verlangt VERIFIED): `tests/helpers/validator_server.py` (neu, untracked), `mail_lang_fixture.py`, Zieldatei, `test_einstellung_gleich_mail_soll_placements.py:489` (`prozess=True`, AC-9), Doku. Umfang 600 neue + 9 entfernte Zeilen in `tests`, Obergrenze 600: kein Spielraum mehr. GREEN automatisch freigegeben.
- Gruen gelaufen (Developer Agent): Server-Tests 25 (mehrfach), Gesamtlauf 376, Zusatz 29; nach der Nacharbeit nur Server-Tests + soll_placements (53). Linux ungetestet.
- `test_3047_r8py_luecken.py`, `test_validatoren_ausblick_3155.py` importieren `_lauf` und laufen bewusst im Server (in der Spec nicht genannt).
- Offen fuer den Adversary: Rest-Luecke Signal-Ausnahme zwischen read und Pufferspeichern in `_lies`; Server-cwd/-env = Testprozess; `timeout` zaehlt ab Startzeile; Serverfrist = timeout + 1 s. Nach dem Adversary-Lauf: `required-files` listete nichts, `risk` = hoch (2 Runden) wegen `.claude/gate-events.jsonl`; untracked Datei vor dem `stamp` pruefen. `adversary-dialog.md` ist als Geruest angelegt.
- AC-12: erste Messung UNGUELTIG (`messung-ac12-UNGUELTIG-nur-server.txt`): Patch traf `tests.tdd....` statt des pytest-Moduls ohne Paketnamen, alle 8 Laeufe waren Server-Laeufe. Wiederholung mit Wegzaehler: `messung-ac12.txt` (je Zeile exit, wand, laeufe prozess/server).
- **AC-12 erfuellt (gemessen, alle Laeufe Exit 0, 149 gruen, Wegzaehler 243/0 gegen 2/241):** `-n 4` 152 -> 99 s (35 %) und 156 -> 98 s (37 %); seriell 458 -> 231 s (50 %) und 481 -> 285 s (41 %). Last schwankte (2,0 bis 8,5), Serverlaeufe liefen je direkt nach dem Prozesslauf. "Prozess" ist nicht der alte Commit, sondern der neue Stand mit erzwungenem Prozessweg. Danach kein Server-/Chromium-Prozess uebrig. Die Zieldatei lief dabei viermal ueber den Server, jedes Mal gruen.
- **Naechster Schritt:** `implementation-validator` starten (2 Runden, AC-11-Mutationen je Validator und je Absicherungstest, String-Ersetzung mit externer Kopie), Protokoll `docs/artifacts/rework-3331-validatoren-tempo/adversary-dialog.md` befuellen, registrieren, `git add` der neuen Datei VOR `stamp`, dann `qa_gate.py --infra --no-visual`, dann Phase 7. Messhilfe lag nur im Sitzungs-Scratchpad.

### Stand nach Adversary (25.11.2026)
- **VERIFIED nach 2 Runden** (Runde 1 BROKEN: F001 flackernder Test, F002 unbewachte Start-Absicherung; behoben). Server-Tests 30, Zieldatei 149, `_lauf`-Importeure 57, weitere Nutzer 174, alle gruen. Offen nur LOW: F007 (`aus`-fd im Kind), F008 (Fristpruefung vor dem 5-s-Warten).
- `flacker-nachweis.txt` zaehlt unklar ("1 gruen") und gilt nicht als Beleg; massgeblich ist die Messung in `mutationen-runde2.md` (80 Laeufe unter Last, 0 rot).
- AC-12 stammt von vor der Nacharbeit und wurde nicht neu gemessen (Nacharbeit betrifft nur den Fehlerpfad). Linux/CI offen: Laufzeit der Datei im Job `test` im PR nennen.
- Umfang 600 von 600 Zeilen, kein Spielraum. `.claude/gate-events.jsonl` und `herdr_*` nie committen.
