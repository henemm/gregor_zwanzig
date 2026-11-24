---
entity_id: rework_3331_validatoren_tempo
type: refactor
created: 2026-11-24
updated: 2026-11-24
status: draft
version: "1.0"
workflow: rework-3331-validatoren-tempo
tags: [testsuite, performance, mail-validatoren, epic-1196]
---

# Testsuite: Mail-Validatoren-Datei beschleunigen (vorgewärmter Fork-Server), Scheibe B

## Approval

- [x] Approved (PO, 2026-11-24)

## Purpose

Die Testdatei der Mail-Validatoren startet 241 Mal einen frischen Python-Prozess, der jedes Mal dieselben `src`-Module importiert; das ist der Hauptteil ihrer Laufzeit. Diese Scheibe lässt die Datei die Validatoren aus einem vorgewärmten Fork-Server aufrufen, ohne eine Zusicherung zu schwächen und ohne die Validatoren (`.claude/hooks/`) zu ändern. Issue #3331 (Scheibe B zu #3317, Teil von Epic #1196). Der Messversuch liegt vor und lag über der 25-%-Schwelle des Issues (41 bis 43 %), deshalb wird umgesetzt.

## Source

- **File:** `tests/helpers/mail_lang_fixture.py`, `tests/tdd/test_einstellung_gleich_mail_validatoren.py`, neu `tests/helpers/validator_server.py`, `tests/test_validator_server.py`
- **Identifier:** `validator_lauf` (Opt-in-Argument), `_lauf` (Z. 239 der Zieldatei, einzige `validator_lauf`-Aufrufstelle der Datei), Server/Klient in `validator_server.py`

> **Schicht-Hinweis:** Reine Testinfrastruktur (`tests/`, Doku). Keine Produktdatei (`src/`, `.claude/hooks/`, Go, Frontend), keine neue Abhängigkeit (`os.fork`, `runpy`, `playwright` sind vorhanden). Querschnitts-Prüfpunkte entfallen: Kanäle, Mandantentrennung und Trip/Ortsvergleich-Teilung sind nicht berührt, Nutzerdaten werden nicht bewegt.

## Estimated Scope

- **LoC:** geschätzt +230 bis +345 neu (Server und Klient rund 120, `validator_lauf` und `_lauf` rund 15 bis 20, Absicherung rund 150, Prozesslauf je Validator rund 20). Das überschreitet die 250er-Grenze der Projektregeln möglicherweise. **Obergrenze für diesen Workflow: 400 Zeilen**; die Spec bittet mit der Freigabe ausdrücklich darum. Die Absicherung wird nicht gekürzt, weil sie die Zusicherungen der Validator-Tests schützt.
- **Files:** 5 (zwei neu, drei geändert)
- **Effort:** high (Risiko: still geschwächte Isolation und vertauschte Antworten; Schutz sind Opt-in, Absicherung des Servers und Mutations-Gegenprobe)

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/helpers/validator_server.py` | CREATE | Server (als Skript startbar) und Klient; Kind-Ablauf, Start, Anfrage, Ende je eigene Funktion |
| `tests/helpers/mail_lang_fixture.py` | MODIFY | `validator_lauf`: Opt-in-Argument (Standard aus); sonst unverändert |
| `tests/tdd/test_einstellung_gleich_mail_validatoren.py` | MODIFY | `_lauf` schaltet den Server ein; je Validator ein unveränderter Prozesslauf mit `--konfig` |
| `tests/test_validator_server.py` | CREATE | Absicherung des Servers (AC-1 bis AC-10) |
| `docs/reference/gates_und_ratschen.md` | MODIFY | kurzer Hinweis (Abschnitt Test-Politik): Server-Läufe sind opt-in, der echte Prozesslauf je Validator bleibt, Begründung. Keine neue Pflichtregel |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/helpers/mail_lang_fixture.py::validator_lauf` | bestehend, erweitert | Aufrufschnittstelle; Rückgabe (CompletedProcess-artiges Objekt, Log-Ordner) bleibt |
| `.claude/hooks/email_spec_validator.py`, `briefing_mail_validator.py` | bestehend, **unverändert** | Prüflinge; sie ergänzen `sys.path` selbst und importieren `_e2e_paths`, `_validator_log`, `_mail_trust`, lazy `_mail_lang`, `_soll_aus_konfiguration` |
| `briefing_mail_validator._check_rendered` | bestehend | echter Chromium (zwei Breiten), im Kind gestartet, nie im Elternprozess |
| pytest, `pytest-xdist` (`-n 4 --dist loadgroup` in CI), `pytest-timeout` (`timeout = 30` je Test) | bestehend | je Worker ein Server; Abbruch während des Wartens ist ein Normalfall |
| weitere Nutzer von `validator_lauf` (`tests/test_{alarm,vergleichs_mail,amtliche_warnungen}_validator_zweisprachig.py`, `tests/unit/test_{briefing_mail_validator,alarm_mail_validatoren,compare_mail_validator,briefing_html,briefing_compact_plain}_sprache.py`, `tests/tdd/test_{gate_testmails_zweisprachig,validatoren_lang_pflicht,einstellung_gleich_mail_soll_placements}.py`) | bestehend | bleiben im Standardweg (Prozess), müssen grün bleiben; einige nutzen `log_dir` und `official_alert_`/`radar_alert_mail_validator` |
| `docs/specs/modules/rework_3317_wartezeiten_tempo_s1.md`, `docs/context/rework-3331-validatoren-tempo.md` | Vorbild/Analyse | Muster und Messwerte |

## Implementation Details

Maßgeblich ist der Abschnitt „Gegenprüfung" in `docs/context/rework-3331-validatoren-tempo.md`; bei Widerspruch geht er dem dort beschriebenen Prototyp vor.

**Entscheidungen des Tech Leads.**

- **Opt-in:** `validator_lauf` bekommt ein Argument (Standard aus, keine Umgebungsvariable). Nur `_lauf` der Zieldatei schaltet ein. Alle anderen Aufrufer laufen unverändert als echter Prozess.
- **Linux-Fork, kein stiller Rückfall:** der Server muss in CI (Linux, `-n 4 --dist loadgroup`) laufen. Ohne `os.fork` gibt es keinen Rückfall auf den Prozess; die Prüfung „im Server läuft nur ein Thread" scheitert laut.
- **TZ:** `tests/helpers/trip_outlook_selection.py` setzt `os.environ["TZ"]` zeitweise. Die Zieldatei selbst setzt weder `TZ` noch ruft sie `tzset` auf (nur `fx.TZ`-Zonenobjekte). Ob der Helfer in einem Validator-Lauf der Zieldatei berührt wird, ist nicht geprüft. Deshalb im Kind nach dem Ersetzen der Umgebung immer `time.tzset()` (ein Aufruf, durch Test belegt).
- **Testdatei der Absicherung:** `tests/test_validator_server.py`.

**Server (Ablauf, Vorlage ist der Wegwerf-Prototyp).** Importe vorab, Prüfung „nur ein Thread", dann je Anfrage eine JSON-Zeile mit Anfrage-Kennung. Je Anfrage `os.fork`; im Kind: `os.setsid`, stdin von `/dev/null`, stdout/stderr in Dateien, `os.environ` vollständig ersetzt (`clear()`, dann Umgebung des Aufrufs), `time.tzset()`, `chdir` in die Kopie, `sys.argv`, `sys.path` = Skriptordner plus Grundpfad (`src` ergänzt der Validator selbst, sonst verdeckten vorgeladene Module einen fehlenden Eintrag), `runpy.run_path(<validator>, run_name="__main__")`, `SystemExit` wie im echten Prozess (Zahl, `None` = 0, Text auf stderr und 1; ungefangene Ausnahme = Traceback auf stderr und 1), `os._exit`. Vorab geladen sind nur schwere Fremd- und `src`-Module (argparse, email, imaplib, json, re, tempfile, subprocess, html, dataclasses, math, `app.metric_catalog`, `app.loader`, `app.ampel_templates`, `i18n`, `i18n.catalog`, `output.renderers.*`, `playwright.sync_api` nur als Import; der Browser startet erst im Kind). Hook-Module (`_soll_aus_konfiguration`, `_mail_lang`, …) werden nie vorgeladen und kommen je Lauf frisch aus der Kopie.

**Klient.** Ein Server je xdist-Worker, beim ersten Gebrauch gestartet. Antwort-Lesen mit Frist (Standard wie heute `timeout=180`). Frist überschritten oder Abbruch während des Wartens: `os.killpg` auf die Prozessgruppe des Kindes (samt Chromium/Node-Treiber; die Gruppenkennung muss der Klient dafür vor dem Warten kennen), bei Frist danach `subprocess.TimeoutExpired` wie heute. Antwort trägt die Anfrage-Kennung; eine Antwort mit fremder Kennung zählt als Fehler. Nach JEDER Ausnahme oder Frist (auch pytest-timeout während des Wartens) wird der Server verworfen und beim nächsten Lauf neu gestartet, damit nie die Antwort eines früheren Laufs gelesen wird. Server tot (EOF): laut scheitern, nächster Lauf startet neu, kein Rückfall. Der Server endet bei EOF auf stdin (auch bei hart beendetem Worker) und per `atexit`.

**Unveränderter Prozesslauf je Validator.** Je Validator mindestens ein Lauf der Zieldatei über den echten Prozess MIT `--konfig` (nur dann wird `_soll_aus_konfiguration` geladen). Er fängt einen fehlenden Pfad zu `src`, den der Server durch vorgeladene Module verdecken kann. Die übrigen `briefing`-Aufrufer ohne `--konfig` decken das nicht ab (per grep gesehen, nicht jede Zeile einzeln gelesen).

**Verworfen:** den Validator im Testprozess ausführen (Zustand, Browser im Elternprozess), die Render-Prüfung abschalten (schwächt die Zusicherung), geteilter Chromium (ohne Änderung am Validator nicht möglich).

**Gemessene Ausgangslage (Prototyp, Mac, 10 Kerne, 147 grün in jedem Lauf).** Seriell Prozess 392 und 411 s gegen Fork-Server 222 und 242 s (43 und 41 %); `-n 4 --dist loadgroup` 180 und 182 s gegen 107 und 108 s (41 %). 241 Validator-Läufe, davon 120 `briefing_mail_validator` und 121 `email_spec_validator`. Median `email_spec` 0,97 auf 0,22 s, `briefing` 2,14 auf 1,59 s (Rest ist echter Chromium). Gepaart waren 241 von 241 Läufen gleich in returncode, stdout, stderr. Der Altwert 455 s ist kein Vorher-Wert.

## Expected Behavior

- **Input:** Lauf von `tests/tdd/test_einstellung_gleich_mail_validatoren.py` (seriell oder `-n 4 --dist loadgroup`).
- **Output:** dieselben Ergebnisse (returncode, stdout, stderr, Log) wie über den Prozess, in kürzerer Zeit; je Validator mindestens ein echter Prozesslauf.
- **Side effects:** je Worker ein Hintergrundprozess während des Laufs, danach keiner. Keine Produktdatei, kein angehobenes Timeout, `data/users/` bleibt unberührt.

## Acceptance Criteria

- **AC-1:** Given je ein grüner und ein roter Fall für `email_spec_validator` und `briefing_mail_validator` / When derselbe Fall über den echten Prozess und über den Server läuft / Then sind returncode, stdout und stderr gleich UND der Log-Inhalt gleich (bis auf Zeitangaben).
  - Test: gepaarter Vergleich in `tests/test_validator_server.py`; Mutation (der Server liefert einen anderen returncode oder lässt eine Logzeile weg, z. B. stderr nicht in die Antwort übernehmen) macht den Vergleich rot.

- **AC-2:** Given der Server verdeckt durch vorgeladene Module einen fehlenden Pfad / When die Zieldatei je Validator einen unveränderten Prozesslauf mit `--konfig` fährt / Then wird ein fehlender Pfad zu `src` in diesem Prozesslauf rot, unabhängig davon, ob der Serverlauf ihn bemerkt.
  - Test: je Validator ein Lauf; Mutation: ALLE `sys.path`-Ergänzungen für `src` entfernen, die dieser Lauf erreicht (`email_spec_validator` selbst, `_soll_aus_konfiguration`, `_mail_lang`; eine einzelne genügt nicht zwingend, weil die anderen sie ersetzen können), macht den Prozesslauf rot. Ob der Serverlauf dabei grün bleibt, wird protokolliert, nicht zugesichert.

- **AC-3:** Given ein Serverlauf / When das Kind startet / Then ist `os.environ` vollständig ersetzt (kein Rest der Server-Umgebung), `TZ` ist per `time.tzset()` wirksam, das Arbeitsverzeichnis ist die Kopie und `sys.argv` stimmt.
  - Test: Hilfs-Skript im Kind meldet Umgebung, Zeitzonenversatz, `cwd` und `argv`; Mutation (`environ.clear()` weg, `chdir` weg, `tzset` weg) wird je einzeln rot.

- **AC-4:** Given ein Lauf überschreitet die Frist / When der Klient die Frist erreicht / Then wird das Kind samt Enkelprozess per `killpg` beendet, es entsteht `subprocess.TimeoutExpired`, und der Folgelauf liefert das richtige Ergebnis.
  - Test: Kind startet einen schlafenden Enkel; danach lebt keiner von beiden und der nächste Lauf stimmt; Mutation (`killpg` durch `kill` auf das Kind) lässt den Enkel leben und wird rot.

- **AC-5:** Given der Test wird während des Wartens abgebrochen (z. B. pytest-timeout) / When der nächste Lauf startet / Then bekommt er nie die Antwort des abgebrochenen Laufs, und das Kind des abgebrochenen Laufs ist samt Enkeln beendet.
  - Test: Abbruch per Ausnahme mitten im Warten, danach Folgelauf mit anderem Ergebnis und Prüfung, dass Kind und Enkel nicht mehr laufen. Jede Sicherung ist einzeln geprüft: nach der Ausnahme läuft ein neuer Server (Mutation: nicht verwerfen), eine Antwort mit fremder Kennung scheitert laut (Mutation: Kennung nicht prüfen), die Kindgruppe ist beendet (Mutation: `killpg` beim Verwerfen weg); jede Mutation wird rot.

- **AC-6:** Given der Server stirbt oder `os.fork` fehlt / When ein Lauf angefragt wird / Then scheitert er laut (kein stiller Rückfall auf den Prozess), und der nächste Lauf startet den Server neu und gelingt.
  - Test: Server hart beenden, Lauf scheitert mit klarer Meldung, Folgelauf grün; Mutation (Rückfall auf `subprocess.run` einbauen) wird rot; fehlendes `os.fork` (im Server-Skript simuliert) und ein zusätzlicher Thread beim Start scheitern je laut.

- **AC-7:** Given zwei Läufe nacheinander im selben Server / When der erste Umgebung, Sprache und Module verändert / Then sieht der zweite keinen Zustand des ersten (`sys.modules`, `os.environ`, Sprache).
  - Test: erster Lauf setzt Marker in Umgebung und `sys.modules`; zweiter meldet sie nicht; Mutation (Kind-Zustand in den Server zurückschreiben bzw. `os.fork` durch direkten Aufruf im Server ersetzen) wird rot.

- **AC-8:** Given ein Validator, der `SystemExit` mit Zahl, `None` oder Text auslöst oder eine Ausnahme wirft / When er über den Server läuft / Then entsprechen returncode und Ausgabe dem echten Prozess (Zahl, 0, Text auf stderr mit 1; Ausnahme mit Traceback und 1).
  - Test: vier Hilfs-Skripte, je gepaart gegen den Prozess; Mutation (`SystemExit(None)` als 1 werten oder Traceback nicht schreiben) wird rot.

- **AC-9:** Given `validator_lauf` ohne Opt-in / When die übrigen Nutzer (alle in Dependencies genannten Dateien) laufen / Then nutzen sie weiter den echten Prozess und bleiben grün.
  - Test: Aufruf ohne Argument startet einen Prozess und keinen Server (Zähler); die genannten Testdateien laufen grün; Mutation (Standard auf „ein") macht den Zähler-Test rot.

- **AC-10:** Given ein Lauf mit Server und Browser ist beendet oder der Worker wurde hart beendet / When danach nach Prozessen gesucht wird / Then ist kein Server- und kein Browserprozess übrig.
  - Test: nach normalem Ende und nach `SIGKILL` auf den Eltern-Worker verschwindet der Server per EOF (läuft gerade ein Kind, spätestens nach dessen Ende oder Frist); Browser-Prozesse sind auch nach einem `TimeoutExpired`-Lauf weg; Mutation (EOF-Ende und `atexit` entfernen) wird rot.

- **AC-11:** Given je Validator mindestens eine Verfälschung, die heute ein Test der Zieldatei fängt / When sie über den Server läuft / Then wird sie auch dort gefangen, im Stand vorher wie nachher.
  - Test: Mutation nur per String-Ersetzung mit externer Sicherungskopie, nie `git checkout`, `git stash` oder `git reset`; je Validator mindestens eine Verfälschung am Validator oder an der Mail, Hash nach Rückspielen geprüft; Protokoll unter `docs/artifacts/rework-3331-validatoren-tempo/`.

- **AC-12:** Given die Zieldatei vorher (Prozess) und nachher (Server) / When sie im selben Zeitfenster am selben Rechner seriell und unter `-n 4 --dist loadgroup` gemessen wird / Then liegt der Gewinn auf dem Mac bei mindestens 25 %, sonst wird der Umbau zurückgenommen.
  - Test: Messnachweis im Artefakt-Ordner (Vorher/Nachher abwechselnd gemessen, Last notiert); CI-Laufzeit der Datei im Job `test` vorher/nachher, soweit die Ausgabe sie zeigt; kein Laufzeit-Assert als Dauertest.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Gleichheit: GIVEN grüner und roter Fall je Validator WHEN Prozess und Server laufen THEN returncode, stdout, stderr und Log gleich (AC-1).
- [ ] Prozesslauf: GIVEN Zieldatei WHEN je Validator ein Lauf mit `--konfig` über den Prozess läuft THEN ein fehlender Pfad zu `src` wird rot (AC-2).
- [ ] Kind-Zustand: GIVEN Hilfs-Skript WHEN es im Kind läuft THEN Umgebung, TZ, `cwd`, `argv` stimmen (AC-3).
- [ ] Frist und Enkel: GIVEN schlafender Enkel WHEN die Frist greift THEN `TimeoutExpired`, kein Prozess übrig, Folgelauf korrekt (AC-4).
- [ ] Abbruch und Server-Tod: GIVEN Abbruch im Warten bzw. toter Server WHEN der nächste Lauf startet THEN keine vertauschte Antwort, lautes Scheitern, Neustart (AC-5, AC-6).
- [ ] Zustandsfreiheit und Exit-Regeln: GIVEN zwei Läufe bzw. vier Exit-Arten WHEN sie laufen THEN kein Zustand übrig, Ergebnis wie im Prozess (AC-7, AC-8).
- [ ] Opt-in und Aufräumen: GIVEN Aufruf ohne Argument bzw. hart beendeter Worker THEN Prozess statt Server bzw. kein Prozess übrig (AC-9, AC-10).
- Einmalige Nachweise im Artefakt-Ordner (kein Dauertest): Mutations-Gegenprobe (AC-11), Vorher/Nachher-Zeit (AC-12).
- Die Zieldatei selbst (147 Tests) muss unter `-n 4 --dist loadgroup` und seriell vollständig grün bleiben.

## Scope

- **In Scope:** die fünf Dateien der Tabelle, Messnachweise und Mutationsprotokoll unter `docs/artifacts/rework-3331-validatoren-tempo/`.
- **Out of Scope:** jede Änderung an `.claude/hooks/` und `src/`, die übrigen Nutzer von `validator_lauf` (bleiben im Prozess), `official_alert_mail_validator` und `radar_alert_mail_validator` über den Server, geteilter Chromium, Config-Änderungen, lokale parallele Form (#3278).

## Definition of Done

- [ ] AC-1 bis AC-12 erfüllt; `tests/test_validator_server.py` und die Zieldatei grün (seriell und `-n 4 --dist loadgroup`); alle in Dependencies genannten `validator_lauf`-Nutzer grün.
- [ ] Gewinn auf dem Mac mindestens 25 % belegt, sonst Umbau zurückgenommen und Befund im Issue.
- [ ] Mutations-Gegenprobe je Validator und je Absicherungstest im Artefakt-Ordner protokolliert, Dateien nach Rückspielen per Hash geprüft.
- [ ] Keine Produktdatei, kein Validator geändert, kein Timeout angehoben, keine Zusicherung gesenkt.
- [ ] Alle CI-Pflicht-Checks grün (der Server läuft auf Linux).

## Known Limitations

- **Linux/CI ungemessen:** der Prototyp lief nur auf dem Mac (macOS-fork). Ob der Server unter Linux denselben Gewinn bringt und stabil läuft, ist erst im CI-Lauf belegbar; die Laufzeit der Datei im Job `test` wird im PR benannt, soweit die Ausgabe sie zeigt.
- **Log-Gleichheit:** bisher NICHT verglichen (nur returncode, stdout, stderr: 241 von 241 gleich). AC-1 holt das nach; das Ergebnis ist vorher offen.
- **`official_alert_`/`radar_alert_mail_validator`:** über den Server nie gelaufen, bleiben außerhalb.
- **Fremdpakete:** nur die 124 `src`-Module wurden auf Umgebungszugriffe beim Import durchsucht (Befund: `_DEPLOYED_COMMIT` in `output/renderers/email/helpers.py` läuft beim Import als git-Aufruf im Arbeitsordner und ist im Server eingefroren, heute je Prozess einmal). Fremdpakete sind nicht durchsucht.
- **Prozessende:** das Kind leert die Ausgaben und endet per `os._exit`; `atexit`-Aufräumfunktionen laufen dort nicht. In `.claude/hooks/*.py` kommt `atexit` heute nicht vor, Fremdpakete sind nicht geprüft.
- **Hash-Seed:** je Server fest statt je Lauf zufällig (hingenommen). Die Socket-Sperre wirkt im Unterprozess heute nicht und bleibt unverändert.
- **TZ:** ob ein Validator-Lauf der Zieldatei den Helfer `trip_outlook_selection` berührt, ist nicht geprüft; abgesichert über `time.tzset()` im Kind (AC-3).
- **Gleichheit gilt für den heutigen Stand:** sie belegt nicht, dass künftige Fehler im Server gleich auffallen; dafür gibt es je Validator den echten Prozesslauf (AC-2).
- **Gewinn verteilt sich ungleich:** seriell etwa je zur Hälfte, `briefing` 246 auf 165 s, `email_spec` 119 auf 30 s (Rest bei `briefing` ist echter Chromium).
- **Messung des Prototyps:** Einzelmessreihe auf einem Mac bei schwankender Last (3,5 bis 8,5); zu Beginn lief evtl. noch ein fremder Testlauf. Die Messung nach der Umsetzung ersetzt diese Werte.
- **LoC:** die 250er-Grenze wird überschritten. Der PO hat die Obergrenze am 24.11.2026 von 400 auf 600 Zeilen in `tests/` angehoben (die Absicherung wurde größer als geschätzt); das ersetzt die Zahl in Estimated Scope. Sechste Datei: `tests/tdd/test_einstellung_gleich_mail_soll_placements.py` (eine Zeile, `prozess=True`, damit sie nach AC-9 im Prozess bleibt).
- **Interpreter-Startparameter:** der Server läuft bereits, deshalb wirken im Kind nicht: `PYTHONIOENCODING`, `PYTHONUTF8`, `PYTHONWARNINGS`, `PYTHONHASHSEED`, `LANG`/`LC_*` für die Ausgabekodierung. Ferner abweichend: `__loader__`, ein Validator, der `sys.stdout` schließt, und Nicht-Daemon-Threads, die das Skriptende überleben (Ende per `os._exit`). Die Zieldatei nutzt heute nichts davon; wer es braucht, nimmt den echten Prozess.
- **Abbruchfenster:** eine Signalausnahme genau zwischen dem Lesen und dem Ablegen der Startzeile im Klienten verliert die Kind-Kennung (Mikrosekunden, nicht testbar); das Kind läuft dann bis zu seinem eigenen Ende weiter, ohne Frist durch den Server.
- **Weitere Nutzer (in Dependencies nicht genannt):** `tests/tdd/test_validatoren_lang_verdrahtung.py` ruft `validator_lauf` (Prozess); `test_3047_r8py_luecken.py` und `test_validatoren_ausblick_3155.py` importieren `_lauf` der Zieldatei und laufen daher im Server.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testinfrastruktur ohne Änderung an Kanälen, Providern, Datenmodell, Auth oder Test-Politik; die Zusicherungen bleiben, ein Teil der Validator-Läufe wird nur über einen vorgewärmten Prozess geführt.

## Changelog

- 2026-11-24: Initial spec created (Workflow rework-3331-validatoren-tempo, Issue #3331, Scheibe B)
- 2026-11-24: Nachtrag aus der Adversary-Runde 1 (Known Limitations: Startparameter, Umfang, weitere Nutzer); ACs unverändert
