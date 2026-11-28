---
entity_id: fix_3503_compare_mail_gate_imac
type: bugfix
created: 2026-11-28
updated: 2026-11-28
status: draft
version: "1.0"
workflow: fix-3503-mail-gate-imac
tags: [gate, tooling, renderer-mail-gate, compare]
---

# Compare-Mail-Gate: Herkunft des Nachweises und iMac-Weg (#3503)

## Approval

- [ ] Approved

## Purpose

Das Renderer-Commit-Gate (#811, Compare-Teil #1282) soll für Commits an der Compare-Mail nur einen echten Nachweis akzeptieren. Heute erfüllen auch Testläufe mit Fixture-Mails (`--eml`) das Gate, und auf dem iMac kann ohne Test-Postfach gar kein Nachweis entstehen. Diese Änderung markiert die Herkunft des Validator-Logs und führt einen lokalen, an den gestagten Stand gebundenen Render-Nachweis ein.

## Source

- **File:** `.claude/hooks/renderer_mail_gate.py`
- **Identifier:** `_compare_validator_log_ok`, neuer Modus `record-compare-lokal`, Gate-Prüfung in `_do_hook`
- **Weitere Datei:** `.claude/hooks/email_spec_validator.py` (`_write_validation_log`, `main`)

Schicht: reines Tooling (Hooks unter `.claude/hooks/`), kein Frontend, keine Go-API, kein Python-Core der Produktion. Kein Trip/Compare-Pendant betroffen, keine Nutzerdaten bewegt (keine Zwei-Nutzer-Tests nötig), keine Kanal-Inhalte geändert.

## Estimated Scope

- **LoC:** ~240
- **Files:** 5-6 (Kern 3)
- **Effort:** medium (Risiko hoch, da Gate-Code; Adversary 2 Runden)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `hook_utils.get_active_workflow_name` | modul | aktiver Workflow |
| `_e2e_paths.shared_repo_dir` | modul | Ablage von Workflow-Zustand und `_log` |
| `scripts/send_gate_test_mails.build_compare_mail` | funktion | Gate-Fixture, lazy importiert, keine Kopie |
| `src/output/channels/email.py::build_mime_message` | funktion | MIME-Bau ohne SMTP (`mail_type="compare"`, `mail_format="full"`, `lang`, `html=True`) |
| `email_spec_validator.validate_message` | funktion | Prüfung der gebauten Mail |
| `renderer_mail_gate.record-matrix` | modus | Vorbild und gleicher Hash (`_staged_mail_hash`) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/renderer_mail_gate.py` | MODIFY | Whitelist `quelle: imap`, `continue` statt Abbruch, Modus `record-compare-lokal`, Gate-Logik, Block-Meldung (~90 LoC) |
| `.claude/hooks/email_spec_validator.py` | MODIFY | Log-Feld `quelle` (`imap`/`eml`) (~8 LoC) |
| `tests/tdd/test_issue_3503_compare_nachweis.py` | CREATE | neue Tests mit echten Wegwerf-Git-Repos (~110 LoC) |
| `tests/tdd/test_issue_811_renderer_gate.py`, `tests/tdd/test_renderer_gate_compare_dispatch.py` (ggf. weitere) | MODIFY | Fixture-Logs bekommen `quelle: imap` (~15 LoC) |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Abschnitt Renderer-Commit-Gate: neuer Nachweis, Restrisiko (~15 LoC) |

## Implementation Details

1. **Herkunftsfeld:** `email_spec_validator` schreibt in das Gate-Log ein Feld `quelle`: `imap` im IMAP-Zweig, `eml` im `--eml`-Zweig.
2. **Whitelist im Gate:** `_compare_validator_log_ok` wertet nur Logs mit `quelle: imap`. Fehlendes Feld gilt als nicht akzeptiert. Logs anderer Herkunft (oder anderer Workflow) werden mit `continue` übersprungen statt abzubrechen, sodass ein Fixture-Fehlerlauf einen echten Erfolg nicht mehr verdeckt. `passed: false` eines imap-Logs blockt weiterhin, die Frische-Prüfung (`validated_at` jünger als mtime der gestagten Dateien) bleibt.
3. **Neuer Modus `renderer_mail_gate.py record-compare-lokal`:** rendert mit dem aktuellen (gestagten) Code die Gate-Fixture `build_compare_mail` (lazy import, keine Kopie) für `de` und `en`, baut je Sprache die Mail über `build_mime_message` und prüft mit `email_spec_validator.validate_message`. Nur wenn beide Sprachen bestehen, schreibt er in den Workflow-Zustand `gates.renderer_mail.compare_lokal = {passed: true, mail_files_hash, langs: ["de","en"], recorded_at}` (Hash identisch zu `record-matrix`). Bei Befund Exit 1 mit Fehlerliste und ohne Eintrag; ohne aktiven Workflow Exit 2. Er schreibt nichts nach `.claude/workflows/_log`, damit Tests ihn nicht nebenbei erzeugen.
4. **Gate:** Der Compare-Nachweis ist erfüllt bei frischem imap-Log ODER `compare_lokal` mit `passed: true`, `langs` enthält `de` und `en` und Hash gleich dem aktuellen gestagten Mail-Stand (Anti-Stale). Die Block-Meldung nennt beide Wege: Server mit Test-Postfach (Validator gegen zugestellte Mail), ohne Test-Postfach z. B. iMac `record-compare-lokal`.
5. **Transport und Live-Daten** bleiben Aufgabe von `/e2e-verify` (`mail-pruefen compare de|en`) nach dem Deploy; dies wird in `docs/reference/gates_und_ratschen.md` (Abschnitt Renderer-Commit-Gate) dokumentiert.
6. **Reihenfolge:** Herkunftsfeld, Whitelist und Recorder in EINEM Commit, sonst wäre der iMac sofort komplett blockiert.
7. **Bestandstests:** Fixture-Logs der bestehenden Gate-Tests erhalten `quelle: imap`.

## Expected Behavior

- **Input:** gestagte Compare-/Helfer-Dateien, Validator-Logs in `_log`, Workflow-Zustand.
- **Output:** Gate lässt den Commit nur mit imap-Log oder hash-gebundenem lokalem Nachweis (de+en) durch.
- **Side effects:** `record-compare-lokal` ändert nur den Workflow-Zustand des aktiven Workflows.

## Acceptance Criteria

- **AC-1:** Given der Validator läuft einmal gegen eine zugestellte Mail (IMAP) und einmal mit `--eml` / When beide Läufe ihr Gate-Log schreiben / Then enthält das IMAP-Log `quelle: imap` und das `--eml`-Log `quelle: eml`.
  - Test: Validator als Subprozess in Wegwerf-Umgebung ausführen, Log-Feld lesen.

- **AC-2:** Given im Log-Ordner liegt nur ein frisches, passendes Log mit `quelle: eml` oder ohne `quelle`-Feld / When ein Compare-Mail-Commit gestagt und das Gate geprüft wird / Then blockiert das Gate den Commit.
  - Test: echtes Wegwerf-Git-Repo, Gate per Subprozess, Exit 2 erwartet.

- **AC-3:** Given ein passendes frisches Log mit `quelle: imap` liegt vor einem neueren Log mit `quelle: eml` und `passed: false` / When das Gate den Commit prüft / Then lässt es den Commit durch, weil das Fixture-Log übersprungen wird.
  - Test: Wegwerf-Repo mit zwei Logs, Exit 0 erwartet.

- **AC-4:** Given das jüngste passende Log hat `quelle: imap` und `passed: false` / When das Gate prüft / Then blockiert es weiterhin den Commit.
  - Test: Wegwerf-Repo, Exit 2 erwartet.

- **AC-5:** Given ein aktiver Workflow und gestagte Compare-Änderungen mit intaktem Renderer / When `record-compare-lokal` läuft / Then endet es mit Exit 0 und der Workflow-Zustand enthält `compare_lokal` mit `passed: true`, `langs` de und en sowie dem Hash des gestagten Stands, und `_log` bleibt unverändert.
  - Test: Subprozess im Wegwerf-Repo, Zustand und `_log` danach vergleichen.

- **AC-6:** Given `compare_lokal` ist für den gestagten Stand aufgezeichnet und kein imap-Log existiert / When das Gate den Commit prüft / Then lässt es den Commit durch.
  - Test: Wegwerf-Repo, Exit 0 erwartet.

- **AC-7:** Given `compare_lokal` wurde aufgezeichnet und danach wird eine Mail-Datei erneut geändert und gestagt / When das Gate prüft / Then blockiert es, weil der Hash nicht mehr zum gestagten Stand passt, und die Meldung nennt beide Nachweiswege.
  - Test: Wegwerf-Repo, Datei nach Aufzeichnung ändern, Exit 2 und Meldungstext prüfen.

- **AC-8:** Given die Compare-Ausgabe verletzt die Mail-Spezifikation in einer Sprache (z. B. durch einen defekten Renderer im Wegwerf-Repo) / When `record-compare-lokal` läuft / Then endet es mit Exit 1, nennt die Fehler und schreibt keinen Eintrag; ohne aktiven Workflow endet es mit Exit 2.
  - Test: Subprozess im Wegwerf-Repo mit manipuliertem Renderer, Zustand unverändert prüfen; zweiter Lauf ohne Workflow-Variable.

- **AC-9:** Given die bestehenden Gate-Tests mit Fixture-Logs / When sie nach der Änderung laufen / Then sind sie weiterhin grün, weil ihre Fixture-Logs `quelle: imap` tragen.
  - Test: `test_issue_811_renderer_gate.py` und `test_renderer_gate_compare_dispatch.py` ausführen.

## Test Plan

- `tests/tdd/test_issue_3503_compare_nachweis.py` (Kern-Schicht, ohne Netz): echte Wegwerf-Git-Repos (Vorbild `tests/tdd/test_issue_811_renderer_gate.py`), Gate und Recorder per Subprozess mit eigener Workflow-Variable, Validator `--eml` per Subprozess mit isoliertem Log-Ordner (AC-1 bis AC-8). Der IMAP-Zweig von AC-1 wird über `_write_validation_log(..., quelle="imap")` bzw. den Aufruf im IMAP-Zweig von `main()` belegt, ohne Netz.
- AC-9: `tests/tdd/test_issue_811_renderer_gate.py`, `tests/tdd/test_renderer_gate_compare_dispatch.py` und die weiteren Testdateien mit Fixture-Logs laufen grün.
- RED-Nachweis: vor der Änderung fehlt `quelle`, das Gate lässt ein `eml`-Log durch (AC-2 rot), `record-compare-lokal` existiert nicht (AC-5/6/8 rot).
- Kein Mock-Theater: kein `patch()`/`Mock()`; Renderer und Validator laufen echt.

## Definition of Done

- Alle ACs durch die Testdatei grün belegt, vorher rot nachgewiesen.
- Bestehende Gate- und Validator-Tests grün.
- Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe (Risiko hoch → 2 Dialog-Runden).
- `docs/reference/gates_und_ratschen.md` beschreibt beide Nachweiswege und das Restrisiko.
- PR mit allen CI-Checks grün gemergt; Folge-Issue für Briefing/Radar/Official angelegt; Issue #3503 mit Ergebnis-Kommentar geschlossen; danach #2923 per `record-compare-lokal` committbar.

## Known Limitations

- Restrisiko: Der Zustand `compare_lokal` ist wie der Matrix-Nachweis handschreibbar (Absicht, nicht Versehen); dokumentiert in `gates_und_ratschen.md`.
- Der lokale Nachweis prüft den Renderer mit Fixture-Daten, nicht den Transport; das übernimmt `/e2e-verify` (`mail-pruefen compare de|en`) nach dem Deploy.
- Out of scope: Briefing-, Radar- und Official-Validator haben dieselbe `--eml`-Lücke (Folge-Issue, zentral in `_validator_log.py`); der Briefing-Nachweis bei geteilten Helfern bleibt unverändert.
- Keine Änderung an Gate-Konfiguration oder override-Sperre.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Ändert nur die Nachweis-Mechanik eines bestehenden Tooling-Gates im Rahmen von #811, ohne Kanal-, Provider-, Datenmodell-, Auth- oder Deploy-Entscheidung.

## Changelog

- 2026-11-28: Initial spec created (Variante V1, Issue #3503)
