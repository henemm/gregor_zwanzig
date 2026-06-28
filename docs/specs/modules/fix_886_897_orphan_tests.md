# Spec: fix-886-897-orphan-tests

- **Created:** 2026-06-28
- **Issues:** #886, #897
- **ADR:** [no-adr] — reine Test-Hygiene, keine Richtungsentscheidung
- **Scope:** Test-/Tooling-Ebene (kein `src/`, `api/`, `internal/`, `frontend/`, `cmd/`)

## Zusammenfassung
Bereinigung zweier Test-Altlasten aus der Plugin-Migration (33da201c). #886 ist bereits durch #894 behoben (verifiziert grün) und wird ohne Code geschlossen. #897 ist ein verwaister Test, der eine gelöschte Hook-Datei aufruft — er wird entfernt; der von ihm geprüfte Schutz (Bug-380) ist heute strukturell über das UserPromptSubmit-Hook-Event garantiert.

## Acceptance Criteria

**AC-1:** Given Issue #886 fordert explizite Subprozess-Env-Übergabe, When die beiden Tests `test_pass_with_both_evidences` und `test_record_matrix_writes_hash` gegen den aktuellen `origin/main`-Stand laufen, Then bestehen beide grün (Fix bereits via #894/`4c2de0a3` vorhanden) und #886 wird ohne weitere Code-Änderung als erledigt geschlossen.

**AC-2:** Given der verwaiste Test `tests/tdd/test_bug_380_approval_injection.py` ruft die in 33da201c gelöschte `workflow_state_updater.py` auf, When die Bereinigung durchgeführt ist, Then ist diese Testdatei entfernt und ein voller TDD-Suite-Lauf enthält keine 14 Orphan-Fehler „No such file or directory" mehr.

**AC-3:** Given die Bug-380-Sorge (injizierter Agent-/Task-Text darf keine Freigabe auslösen), When der heutige Freigabepfad geprüft wird, Then ist dokumentiert und belegt, dass Freigabe-Stichworte ausschließlich aus dem `prompt`-Feld echter UserPromptSubmit-Ereignisse und nur phasengebunden ausgewertet werden, sodass injizierter Text den Hook strukturell nicht erreicht — kein Ersatztest erforderlich.

**AC-4:** Given die Änderung betrifft nur Testdateien, When der Workflow validiert und ausgeliefert wird, Then bleibt das Produktverhalten unverändert (keine `src/`-Änderung) und die Issues #886 und #897 werden geschlossen.

## Out of Scope
- Inhaltliche Änderungen an `phase_listener.py` oder am Freigabe-Mechanismus.
- Neuer Behavior-Test gegen `phase_listener` (Schutz ist strukturell, nicht inhaltlich).
