---
entity_id: e2e_verify_en_mailweg_2813
type: module
created: 2026-11-04
updated: 2026-11-04
status: draft
version: "1.0"
tags: [bugfix, tooling, e2e-verify, mail-validator, telegram-live, i18n]
---

# E2E-Verify: EN-Mailweg-Werkzeuge, Alarm-Validator-Betreff-Filter, Telegram-Live-Hygiene (#2813)

## Approval

- [ ] Approved

## Purpose

Der Befund aus `/e2e-verify` zu #2681 zeigt vier Luecken im Pruefwerkzeug, durch die ein "OK" nicht beweist, was es verspricht (falsche oder aeltere Mail geprueft, Wachter rot, "0 selected" als bestanden). Diese Spec schliesst drei davon (Teile 2, 3, 4); Teil 1 (`--lang en` ueber den Staging-Kern) ist bewusst ausgeklammert (siehe Known Limitations).

Reine Werkzeug-/Test-Aenderung: kein Produktcode, keine Nutzerdaten-Endpoints, daher keine neue Mandantenpruefung noetig. Kanalparitaet: betroffen ist nur die Hygiene der Telegram-Live-Tests, nicht der Inhalt der vier Kanaele.

## Source

- **File:** `scripts/send_gate_test_mails.py` (Teil 2, `main`)
- **File:** `.claude/hooks/official_alert_mail_validator.py`, `.claude/hooks/radar_alert_mail_validator.py`, `.claude/hooks/_e2e_paths.py` (Teil 3)
- **File:** `tests/tdd/_telegram_live_fixture.py`, `tests/tdd/test_issue_686_telegram_functional_live.py`, `tests/tdd/test_telegram_live_zweisprachig.py` (Teil 4)
- **File:** `.claude/commands/e2e-verify.md` (Doku)
- **Identifier:** `main`, `fetch_latest_message`, `_message_matches`, Fixture `tg_live_datenwurzel_zuruecksetzen` (neu)
- **Schicht:** ausschliesslich Tooling (`.claude/hooks`, `scripts`, `tests`); kein Frontend, kein Go, kein Python-Core (`src/` bleibt unveraendert, `src/app/origin_guard.py` und `src/output/channels/email.py:731` werden nur gelesen).

## Estimated Scope

- **LoC:** ca. +180 / -20
- **Files:** ca. 8 (Skript, 2 Validatoren, `_e2e_paths.py`, Telegram-Fixture, `e2e-verify.md`, 3 neue Tests unter `tests/tdd/`)
- **Effort:** medium (Risiko mittel: Teil 4 beruehrt die Testinfrastruktur rund um den Waechter #2226)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/origin_guard.py` `classify_origin` | Modul (nur lesen) | liefert `"test"` fuer jeden Worktree; Herkunftssperre #1476 bleibt unveraendert |
| `src/output/channels/email.py:731` | Modul (nur lesen) | schreibt bei Herkunft `test` das To auf die Basisadresse um |
| `.claude/hooks/briefing_mail_validator.py` | Vorbild | `fetch_latest_message(..., subject_contains)`, `_message_matches` |
| `.claude/hooks/_e2e_paths.py` | Hook-Helfer | `mail_waehlbar`, `sprach_argumente`; Ort fuer gemeinsamen Betreff-Filter |
| `tests/conftest.py` Session-Waechter #2226 | Test-Infrastruktur (UNVERAENDERT) | meldet Aenderungen am echten `data/users`-Baum |
| `pyproject.toml` `addopts` | Konfiguration (UNVERAENDERT) | `-m 'not email and not live and not staging'` |

## Implementation Details

**Teil 2 - Versandskript bricht im Worktree mit `--lang en` laut ab (`scripts/send_gate_test_mails.py`)**

- In `main()` direkt nach dem Parsen, VOR `_test_settings` und vor jedem Versand: ist `lang == "en"` und `classify_origin(...) == "test"` (Worktree, jede Nicht-Prod/Staging-Herkunft), dann Fehlermeldung auf stderr und Rueckgabe eines Exit-Codes != 0 (z. B. 3). Die Meldung nennt den Grund (Herkunftssperre #1476 schreibt das To auf die Basisadresse um, `+en@` kann hier nicht ankommen) und die Abhilfe (aus `/home/hem/gregor_zwanzig_staging` senden).
- Die Herkunftsklassifikation wird ueber eine kleine, injizierbare Funktion (Test-Seam, z. B. `main(argv, herkunft=classify_origin)`) aufgerufen, damit der Test beide Herkuenfte ohne Mock-Theater durchspielt; im echten Worktree liefert `classify_origin` ohnehin `"test"`.
- `--lang de` aus dem Worktree funktioniert unveraendert (Basisadresse, keine Umschreibung noetig).
- Es wird nie "gesendet" oder "An: ...+en@" gedruckt, wenn das To umgeschrieben wuerde: der Abbruch erfolgt vor allen Ausgaben ("Token fuer diesen Lauf" inklusive).

**Teil 3 - `--subject-contains` fuer die Alarm-Validatoren**

- `official_alert_mail_validator.py` und `radar_alert_mail_validator.py`: neues Argument `--subject-contains <text>`; `_message_matches` und `fetch_latest_message` bekommen den Parameter `subject_contains` (Vorbild `briefing_mail_validator.py`). Das dekodierte Subject muss das Fragment enthalten; Sprach- und Empfaengerauswahl (`mail_waehlbar`) bleiben UND-verknuepft. Ein gemeinsamer Helfer `betreff_enthaelt(headers, fragment)` in `_e2e_paths.py` wird verwendet, wenn dadurch Code gespart wird (Dekodierung nicht doppelt bauen).
- Kein Treffer unter den gescannten Mails: Fehlertext "Keine passende ... Mail gefunden (subject_contains=...)" und technischer Fehler (Exit 2). Kein stilles Ausweichen auf eine aeltere Mail. Ein leeres Fragment (`""`) wird abgelehnt (Vorbild `email_spec_validator._check_selection_arguments`).
- Lauf-Token im Betreff: Die Gate-Mails tragen ihn laut Quelltext (official: Trip-Name `GATE1233 <token>`, radar: `trip_short=GATE1241 <token>`). Ob dieser Name im tatsaechlichen Betreff steht (`render_alert_subject`), wird im Test am ECHTEN Betreffaufbau (Mail ueber den Renderer bauen, Betreff lesen) belegt, nicht angenommen. Steht der Token nicht im Betreff, ergaenzt die Implementierung ihn im Betreff der Gate-Mail (nur im Sendeskript, nie im Produktcode) und der Test haelt das fest.
- `e2e-verify.md`: Aufrufe der beiden Alarm-Validatoren zeigen `--subject-contains <token>` (Token aus der Ausgabe von `send_gate_test_mails.py`).

**Teil 4 - Telegram-Live-Tests hinterlassen keine Spur mehr**

- In `tests/tdd/_telegram_live_fixture.py` eine Fixture/ein Kontextmanager `tg_live_datenwurzel_zuruecksetzen(data_dir)`: vor dem Test Zustand von `data/users/tg-live-e2e` sichern (Verzeichnis vorhanden ja/nein; wenn ja, Dateien samt Inhalt), nach dem Test wiederherstellen: war es nicht vorhanden, wird das Verzeichnis vollstaendig entfernt; war es vorhanden, werden Dateien auf den gesicherten Inhalt zurueckgesetzt und Neues entfernt (Read-Modify-Write-Gedanke: Vorbestand bleibt erhalten).
- Beide Live-Testdateien binden die Fixture ein (autouse in der Datei oder Mixin). Der Waechter #2226 in `tests/conftest.py` bleibt UNVERAENDERT; der Teardown-Error verschwindet, weil die Spur tatsaechlich entfernt wird.
- `e2e-verify.md`: Telegram-Live-Tests werden ausdruecklich mit `-m live` aufgerufen; Warnhinweis, dass "0 selected" (wegen `addopts`) KEIN Bestanden ist.

**Teststrategie (je Teil ein Verhaltenstest unter `tests/tdd/`, kein Mock-Theater)**

- Teil 2: `main(["--lang","en"])` aus dem Worktree mit Test-Seam fuer die Herkunft ⇒ Exit != 0, nichts gesendet (Versandfunktion zaehlt Aufrufe ueber echten Test-Transport/Seam), stderr nennt Grund und Abhilfe, stdout enthaelt weder "gesendet" noch "+en@"; Gegenprobe `--lang de` laeuft durch.
- Teil 3: je Validator ein Test-IMAP/EML-Seam (`imap=`-Parameter existiert bereits) mit zwei Mails: eine aeltere ohne Token, eine frische mit Token ⇒ mit `--subject-contains <token>` wird die frische gewaehlt; mit einem Token ohne Treffer ⇒ Exit 2. Der Betreff der Test-Mails kommt vom echten Renderer/Gate-Mail-Aufbau.
- Teil 4: Fixture-Lauf in einer tmp-Datenwurzel: (a) Verzeichnis nicht vorhanden, Test legt es an ⇒ nach der Fixture Fingerprint unveraendert, Verzeichnis weg; (b) Vorbestand mit Datei ⇒ nach einer Veraenderung wird der Vorbestand wiederhergestellt.

## Expected Behavior

- **Input:** `send_gate_test_mails.py --lang en` aus Worktree; Validator-Aufruf mit `--subject-contains <token>`; Lauf der Telegram-Live-Tests mit `-m live`.
- **Output:** Teil 2: Abbruch mit klarer Meldung, Exit != 0; Teil 3: Validator prueft nachweislich die frische Mail oder meldet Exit 2; Teil 4: Live-Tests enden ohne Wachter-Teardown-Error.
- **Side effects:** keine im Produktivbetrieb; nur Werkzeug, Tests und Doku.

## Acceptance Criteria

- **AC-1:** Given das Versandskript wird aus einem Worktree (Herkunft "test") gestartet / When es mit `--lang en` aufgerufen wird / Then bricht es VOR jedem Versand mit Exit-Code ungleich 0 ab, und die Meldung nennt Grund (Herkunftssperre) und Abhilfe (aus `/home/hem/gregor_zwanzig_staging` senden).
  - Test: Skript-`main()` im Worktree mit `--lang en` aufrufen; Exit != 0, kein Versand ausgeloest, stderr enthaelt Grund und Abhilfe.

- **AC-2:** Given das Versandskript bricht wegen Herkunft ab / When die Ausgabe betrachtet wird / Then erscheint weder "gesendet" noch eine Zeile "An: ...+en@", damit niemand eine umgeschriebene Mail fuer eine EN-Mail haelt.
  - Test: stdout/stderr des Abbruch-Laufs enthalten kein "gesendet" und kein "+en@" als Zieladresse.

- **AC-3:** Given dieselbe Worktree-Herkunft / When das Skript mit `--lang de` laeuft / Then funktioniert der Versand wie bisher (Basisadresse, Exit 0), und die Herkunftssperre in `email.py` bleibt unveraendert.
  - Test: `main(["--lang","de"])` im Worktree sendet ueber den Test-Seam und liefert Exit 0; Gegenprobe zu AC-1.

- **AC-4:** Given im Test-Postfach liegen eine aeltere amtliche-Warnung-Mail ohne Lauf-Token und eine frische mit Token im Betreff / When `official_alert_mail_validator` mit `--subject-contains <token>` laeuft / Then wird die frische Mail geprueft und nicht die aeltere.
  - Test: Validator gegen Test-IMAP/EML-Seam mit zwei Mails; ausgewaehlt wird die Mail mit Token im dekodierten Betreff.

- **AC-5:** Given dieselbe Konstellation fuer Radar-/Regen-Alarm / When `radar_alert_mail_validator` mit `--subject-contains <token>` laeuft / Then wird die frische Mail mit Token geprueft und die aeltere ignoriert.
  - Test: wie AC-4 fuer den Radar-Validator.

- **AC-6:** Given kein Postfach-Eintrag enthaelt das angegebene Betreffs-Fragment / When einer der beiden Alarm-Validatoren mit `--subject-contains` laeuft / Then endet er mit technischem Fehler (Exit 2) und weicht nicht auf eine aeltere Mail aus; ein leeres Fragment wird abgelehnt.
  - Test: Seam-Postfach nur mit alter Mail, Aufruf mit fremdem Token ⇒ Exit 2, keine Pruefung der alten Mail.

- **AC-7:** Given die Gate-Mails werden mit dem echten Betreffaufbau gebaut / When ihr Betreff gelesen wird / Then enthaelt er den Lauf-Token (official `GATE1233 <token>`, radar `GATE1241 <token>`), sodass `--subject-contains <token>` die frisch gesendete Mail trifft.
  - Test: Gate-Mail ueber den echten Renderer/Gate-Aufbau erzeugen, Betreff dekodieren und Token pruefen; zusammen mit dem Validator-Filter ein Durchlauf ohne Annahme.

- **AC-8:** Given die Telegram-Live-Tests mit `real_data_root` laufen mit `-m live` / When die Session endet / Then hinterlassen sie `data/users/tg-live-e2e` nicht, und der Waechter #2226 meldet keinen Teardown-Error.
  - Test: Fixture-Lauf in einer tmp-Datenwurzel ohne Vorbestand: Fingerprint nach dem Test gleich dem vorher, Verzeichnis entfernt.

- **AC-9:** Given `data/users/tg-live-e2e` existiert schon mit Dateien / When ein Live-Test sie veraendert / Then stellt die Fixture den urspruenglichen Inhalt wieder her und entfernt Neues; der Waechter #2226 in `tests/conftest.py` ist unveraendert.
  - Test: Fixture-Lauf mit Vorbestand; Dateiinhalt nach dem Test identisch zum Zustand davor.

- **AC-10:** Given ein Mensch folgt `e2e-verify.md` fuer die Telegram-Live-Tests / When er den Befehl ausfuehrt / Then nennt die Doku `-m live` ausdruecklich und warnt, dass "0 selected" kein Bestanden ist; die Alarm-Validatoren werden dort mit `--subject-contains <token>` aufgerufen.
  - Test: `# doc-compliance-test` (reine Doku): `e2e-verify.md` enthaelt `-m live`, die "0 selected"-Warnung und den `--subject-contains`-Aufruf fuer beide Validatoren.

## Known Limitations

- **Teil 1 ausserhalb des Umfangs:** `--lang en` in `.claude/tools/staging_mail_pruefen.py` (Staging-Kern, Nutzer `en`, Scheduler, Validator mit `--lang en --to-contains +en@`) ist live-abhaengig vom Blocker #2774 (Wegwerf-Konten, Plus-Adresse, Helfer-Konto) und kommt als Folge-Ticket nach dem Merge; Issue #2813 bleibt dafuer offen, bis das Folge-Ticket angelegt ist. Bis dahin wird EN weiter nur mit Gate-Mails aus dem Staging-Checkout belegt (kein Beleg ueber den Staging-Kern).
- Die Herkunftssperre #1476 wird nicht gelockert; EN-Gate-Mails entstehen weiter nur aus `/home/hem/gregor_zwanzig_staging`.
- Der Token im Betreff ist nur fuer die Gate-Mails gesichert, nicht fuer produktive Alarm-Mails.
- Die Telegram-Live-Tests brauchen weiterhin echte Telegram-Zugangsdaten und `-m live`; ohne beide bleibt "0 selected".

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Werkzeug-/Test-Bugfix ohne Aenderung an Kanaelen, Providern, Datenmodell, Auth oder Deploy-Strategie; bestehende Entscheidungen (Herkunftssperre #1476, Waechter #2226, ADR-0104) bleiben unangetastet.

## Changelog

- 2026-11-04: Initial spec created (Teile 2-4 von #2813; Teil 1 als Folge-Ticket wegen #2774)
