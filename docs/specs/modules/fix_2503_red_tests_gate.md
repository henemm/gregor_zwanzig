---
entity_id: fix_2503_red_tests_gate
type: bugfix
created: 2026-11-12
updated: 2026-11-12
status: draft
workflow: fix-2503-red-tests-gate
version: "1.0"
tags: [gate, tooling, tdd]
---

# Commit-Gate: neu angelegte RED-Tests in Phase TDD-RED durchlassen

## Approval

- [ ] Approved

## Purpose

Das Commit-Gate `touched_tests_gate.py` blockiert in der TDD-RED-Phase den Commit neu angelegter, erwartungsgemaess roter Tests, weil es sie wie eine Regression behandelt (Issue #2503). Diese Spec erweitert `feat_1481a_touched_tests_gate` um eine eng begrenzte Ausnahme: Ein Test, der im letzten Commit nachweislich nicht existierte, darf in Phase `phase5_tdd_red` rot committet werden. Alles andere bleibt unveraendert streng.

## Source

- **File:** `.claude/hooks/touched_tests_gate.py`
- **Identifier:** `main`, `_lauf_python`, `_lauf_go`, `_lauf_frontend`, `_vorzustand_messen`
- **Ursprungs-Spec:** `docs/specs/modules/feat_1481a_touched_tests_gate.md` (deren ACs, insbesondere AC-7 "Stoerung blockiert nie", bleiben gueltig)
- **Kontext und Analyse:** `docs/context/fix-2503-red-tests-gate.md`

> **Schicht-Hinweis:** Reines Tooling (Claude-Hook), keine Frontend-/Go-API-/Python-Core-Produktivcode-Aenderung. Keine Nutzerdaten, keine Kanaele, kein Trip/Vergleich-Pendant.

## Estimated Scope

- **LoC:** Gate +50/-10, Tests +130
- **Files:** 3 (Hook, Test, diese Spec)
- **Effort:** medium (Risiko mittel: Gate-Code, mindestens zwei Adversary-Runden)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `feat_1481a_touched_tests_gate` | Spec | Ursprung, ACs bleiben gueltig |
| `hook_utils` (Projekt-Shim in `.claude/hooks/`) | module | aktiver Workflow-Name (`get_active_workflow_name()`) |
| `.claude/workflows/<name>.json` | state | Phase in `current_phase` (`phase5_tdd_red`) |
| `git` (`diff --cached`, `worktree add`) | tool | Vorzustand am Wegwerf-Abzug messen |
| `go test -v`, `pytest -rA`, `node --test` (TAP) | tool | Liste der gelaufenen Tests im Vorzustand |
| `tests/tdd/test_touched_tests_gate.py` | test | Verhaltensnachweis ueber Wegwerf-Repos |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/touched_tests_gate.py` | MODIFY | Laeufer liefern zusaetzlich die Menge der GELAUFENEN Tests; Klassifikation vorbestehend / neu angelegt rot / neu_rot; Phasenabfrage |
| `tests/tdd/test_touched_tests_gate.py` | MODIFY | Neue Verhaltensfaelle mit Wegwerf-Repos (Python, Go inkl. Subtest, Frontend), Workflow-State im Wegwerf-Repo |
| `docs/specs/modules/fix_2503_red_tests_gate.md` | CREATE | diese Spec |

## Implementation Details

1. **Existenz im Vorzustand wird gemessen, nicht geraten.** Jeder Laeufer gibt `(fehlgeschlagen, gelaufen, stoerung)` zurueck. Der Vorzustandslauf am Wegwerf-Abzug von `HEAD` liefert die Menge aller dort gelaufenen Tests:
   - Go: `go test -v`, Zeilen `=== RUN <Name>` (inkl. `Eltern/sub`).
   - Python: `-rA`, Zeilen `PASSED|FAILED|ERROR|SKIPPED|XFAIL <id>`. Fehlt eine Testdatei im Vorzustand komplett, bleibt es beim bisherigen Stoerungspfad (pytest Exit 4, durchlassen).
   - Frontend: TAP `ok N - name` / `not ok N - name`.
   Eine Namenssuche per `git grep` ist verworfen, weil Namensgleichheit in Kommentaren oder anderen Paketen Existenz vortaeuscht.
2. **Klassifikation je Fehlschlag `f`:** in vorher-rot: vorbestehend (unveraendert); nicht im Vorzustand gelaufen: neu angelegt rot; sonst: `neu_rot` (blockiert, unveraendert).
3. **Go-Elternfunktion:** `--- FAIL: TestA` gilt nur dann als entschuldigt, wenn alle fehlschlagenden Subtests neu angelegt sind. Ist auch nur ein vorbestehender Subtest betroffen, ist die Elternfunktion `neu_rot`. Das Fehlschlag-Muster muss eingerueckte Zeilen (`^\s*--- FAIL:`) erkennen, weil `go test -v` Subtests einrueckt.
4. **Phasenbindung:** "neu angelegt rot" laesst den Commit nur durch, wenn der aktive Workflow (worktree-bewusst) in `phase5_tdd_red` steht. Ausgabe als Hinweis "neu angelegt rot (TDD-RED, blockiert nicht)" mit Testnamen. In jeder anderen Phase, ohne aktiven Workflow oder bei unlesbarem State: keine Ausnahme, Block mit eigener Meldung ("neu angelegter Test ist rot — nur in Phase TDD-RED erlaubt"). Eine nicht lesbare Phase ist fehlende Erlaubnis, kein Stoerungsfall des Gates.
5. Der zweite Lauf entsteht weiterhin nur, wenn etwas rot ist (Kosten unveraendert).
6. **Befund aus TDD-RED (Voraussetzung fuer AC-7):** Im Wegwerf-Abzug fehlt `frontend/node_modules` (nicht eingecheckt). Die Frontend-Vorzustandsmessung scheitert deshalb heute IMMER ("Frontend-Abhaengigkeiten fehlen") und jeder Frontend-Fehlschlag gilt als "Vorzustand unbekannt" (durchgelassen). Der Vorzustandslauf muss die Abhaengigkeiten des Arbeitsstands mitbenutzen (z. B. Verweis `abzug/frontend/node_modules` -> `wurzel/frontend/node_modules`, vor dem Aufraeumen wieder entfernt), sonst ist AC-7 (Block ausserhalb Phase RED) nicht erfuellbar.

## Expected Behavior

- **Input:** `git commit` mit gestagten Quelldateien; mindestens ein zugehoeriger Test ist rot.
- **Output:** Exit 0 mit Hinweis bei vorbestehend rot oder (Phase RED) neu angelegt rot; Exit 2 bei `neu_rot` oder neu angelegt rot ausserhalb der Phase RED.
- **Side effects:** keine; Wegwerf-Abzug wird wie bisher aufgeraeumt.

## Test Plan

### Automated Tests (TDD RED)

Alle in `tests/tdd/test_touched_tests_gate.py`, mit Wegwerf-Repo, echtem `git commit` und echtem Hook-Aufruf, ohne Netz; Phase ueber eine State-Datei `.claude/workflows/<name>.json` im Wegwerf-Repo.

- [ ] GIVEN Phase RED und neue Go-Testfunktion per Assertion rot WHEN Hook THEN Exit 0, Hinweis nennt Testnamen
- [ ] GIVEN Phase RED und neue Python-Testfunktion in bestehender Datei rot WHEN Hook THEN Exit 0
- [ ] GIVEN neuer roter Go-Subtest in bestehender Funktion WHEN Hook THEN Exit 0; mit zusaetzlich vorbestehendem, jetzt rotem Subtest THEN Exit 2
- [ ] GIVEN Phase `phase6_implement` / kein Workflow / unlesbarer State und neuer roter Test WHEN Hook THEN Exit 2 mit "nur in Phase TDD-RED erlaubt"
- [ ] GIVEN Phase RED und vorher gruener Test wird rot WHEN Hook THEN Exit 2
- [ ] GIVEN vorbestehend roter Test WHEN Hook THEN Exit 0 wie bisher
- [ ] GIVEN Phase RED und neuer roter Frontend-Test WHEN Hook THEN Exit 0
- [ ] GIVEN Go-Uebersetzungsfehler / fehlendes Werkzeug WHEN Hook THEN Exit 0 mit Stoerungshinweis

## Acceptance Criteria

- **AC-1:** Given der aktive Workflow steht in Phase `phase5_tdd_red` und eine neu angelegte Go-Testfunktion schlaegt per Assertion fehl / When `git commit` mit gestagter Go-Quelldatei ausgefuehrt wird / Then wird der Commit durchgelassen (Exit 0), und der Hinweis nennt den neuen Test namentlich als "neu angelegt rot (TDD-RED, blockiert nicht)".
  - Test: Wegwerf-Repo mit Go-Paket, State-Datei Phase RED, neue Funktion `TestNeu` mit falscher Erwartung; echter Hook-Aufruf liefert Exit 0, stderr enthaelt `TestNeu`.

- **AC-2:** Given Phase `phase5_tdd_red` und eine neue Python-Testfunktion in einer bestehenden Testdatei unter `tests/unit/` schlaegt fehl / When `git commit` mit zugehoeriger gestagter Quelldatei ausgefuehrt wird / Then wird der Commit durchgelassen und der neue Test im Hinweis genannt.
  - Test: Wegwerf-Repo mit gruener Testdatei, im Arbeitsstand eine zweite, rote Funktion ergaenzt; Hook liefert Exit 0 mit Funktionsnamen im Hinweis.

- **AC-3:** Given Phase `phase5_tdd_red` und ein neuer, fehlschlagender Subtest in einer bestehenden Go-Funktion / When `git commit` ausgefuehrt wird / Then wird der Commit durchgelassen; hat die Elternfunktion zusaetzlich einen vorbestehenden Subtest, der jetzt rot wird, dann wird der Commit blockiert (Exit 2).
  - Test: Zwei Wegwerf-Repos; im ersten nur neuer roter Subtest (Exit 0), im zweiten zusaetzlich ein vorher gruener Subtest derselben Funktion rot gemacht (Exit 2, eingerueckte `--- FAIL:`-Zeilen werden erkannt).

- **AC-4:** Given ein neu angelegter, roter Test, aber der aktive Workflow steht in einer anderen Phase (z. B. `phase6_implement`), es gibt keinen aktiven Workflow oder der Workflow-State ist nicht lesbar / When `git commit` ausgefuehrt wird / Then wird der Commit blockiert (Exit 2), und die Meldung sagt ausdruecklich, dass ein neu angelegter roter Test "nur in Phase TDD-RED erlaubt" ist.
  - Test: Drei Wegwerf-Repos mit demselben neuen roten Test (Phase `phase6_implement`, keine State-Datei, defekte State-Datei); jedes liefert Exit 2 und enthaelt den Meldungstext.

- **AC-5:** Given Phase `phase5_tdd_red` und ein bestehender, im letzten Commit gruener Test wird durch die Aenderung rot / When `git commit` ausgefuehrt wird / Then wird der Commit weiterhin blockiert (Exit 2) und der Test als "macht Tests rot" genannt.
  - Test: Wegwerf-Repo mit gruenem Test, Quelldatei wird kaputt geaendert, State-Datei Phase RED; Hook liefert Exit 2 (Gegenprobe, sonst waere die Ausnahme beliebig weit).

- **AC-6:** Given ein Test, der schon im letzten Commit rot war / When `git commit` ohne neue Fehlschlaege ausgefuehrt wird / Then laeuft der Commit wie bisher durch und meldet den Test als "vorbestehend rot", unabhaengig von der Phase.
  - Test: Bestehender Verhaltenstest `test_ac3_vorbestehend_roter_test_blockiert_nicht` bleibt gruen, zusaetzlich einmal mit Phase RED und einmal ohne Workflow.

- **AC-7:** Given Phase `phase5_tdd_red` und ein neu angelegter, fehlschlagender Frontend-Test (`node --test`, TAP-Ausgabe) / When `git commit` mit gestagter Frontend-Quelldatei ausgefuehrt wird / Then wird der Commit durchgelassen und der Test im Hinweis genannt; ausserhalb der Phase RED wird er blockiert.
  - Test: Wegwerf-Repo mit `frontend/`-Testlauf (ohne Netz), neuer roter Test; Hook liefert Exit 0 in Phase RED und Exit 2 in Phase `phase6_implement`. Fehlt die Frontend-Umgebung, wird der Test uebersprungen und das Fehlen benannt.

- **AC-8:** Given eine Stoerung des Gates selbst (Go-Uebersetzungsfehler, fehlendes Werkzeug, gescheiterte Vorzustandsmessung, unerwartete Ausnahme) / When `git commit` ausgefuehrt wird / Then wird der Commit nicht blockiert (Exit 0) und die Stoerung sichtbar gemeldet, in jeder Phase.
  - Test: Bestehende AC-7-Tests der Ursprungs-Spec bleiben gruen; zusaetzlich ein Wegwerf-Repo mit nicht kompilierendem Go-Test in Phase RED und in Phase `phase6_implement`: beide Exit 0 mit Stoerungshinweis.

## Definition of Done

- AC-1 bis AC-8 durch Verhaltenstests mit Wegwerf-Repos in `tests/tdd/test_touched_tests_gate.py` grün; alle bestehenden Tests der Ursprungs-Spec `feat_1481a` bleiben grün.
- Adversary VERIFIED in mindestens zwei Runden; Pflicht-Mutationen (Phasenbindung entfernt, Existenzmessung durch „immer neu“ ersetzt, Subtest-Elternregel gelockert, eingerücktes `--- FAIL:` übersehen) werden jeweils von einem Test gefangen.
- Lieferung per PR mit allen 6 CI-Checks grün; Issue #2503 mit Verweis auf die Lieferung geschlossen.

## Known Limitations

- **Umbenennungs-Umgehung in Phase RED:** Wird ein bestehender Test umbenannt und rot gemacht, gilt er als neu angelegt. Begrenzt durch die Phasenbindung; jeder so durchgelassene Test wird namentlich gemeldet; Gegenprobe im Adversary.
- Ein geaenderter bestehender Test (z. B. verschaerfte Assertion), der dadurch rot wird, bleibt blockiert; bewusst ausserhalb des Umfangs.
- Ein Go-Uebersetzungsfehler bleibt eine Stoerung (durchlassen, AC-7 der Ursprungs-Spec); der Fehlanreiz zu absichtlich nicht kompilierenden RED-Tests entfaellt, weil kompilierbare rote Tests jetzt committbar sind.
- Neue Python-Testdatei: Vorzustand liefert pytest Exit 4, bleibt Stoerungspfad (durchlassen) wie bisher.
- **Elternfunktion mit eigenem Fehlschlag:** Eine bestehende Go-Elternfunktion (bzw. Frontend-Suite), die selbst per `t.Error` rot wird und zugleich nur neu angelegte rote Subtests hat, wird in Phase RED mitentschuldigt. Die Ausgabe von `go test -v` trennt den eigenen Fehlschlag der Eltern nicht von dem ihrer Kinder; die neuen Subtests werden namentlich gemeldet.
- **Testnamen ohne Paket-/Dateikontext (Adversary F005):** Vorzustand und Arbeitsstand werden ueber den Testnamen verglichen (Go `TestX`, Frontend `suite > test`). Gleichnamige Tests in verschiedenen Paketen bzw. Dateien derselben Schicht koennen sich vermischen: Ein neuer Test, dessen Name anderswo schon lief, gilt als bestehend (blockiert strenger), und umgekehrt kann ein dort gelaufener Name einen roten Test nicht als neu ausweisen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Tooling-Gate, Erweiterung des bestehenden Gates aus #1481; keine Entscheidungsflaeche (Kanaele, Provider, Datenmodell, Auth, Deploy) beruehrt.

## Changelog

- 2026-11-12: Initial spec created (Issue #2503)
- 2026-11-12: TDD-RED-Befund ergaenzt (Implementation Details Punkt 6: node_modules im Vorzustands-Abzug)
- 2026-11-12: Adversary-Runde 1: describe-Verschachtelung, Limitations ergänzt
