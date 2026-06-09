---
entity_id: issue_648_scope_tests_neutral
type: module
created: 2026-06-08
updated: 2026-06-08
status: draft
version: "1.0"
tags: [tooling, hooks, scope-detection]
---

# Scope-Erkennung: `tests/` neutral behandeln (#648)

## Approval

- [ ] Approved

## Purpose

Die Scope-Klassifikation der E2E-/Deploy-Gates soll Dateien unter `tests/` als
**neutral** behandeln (wie `docs/`), statt sie konservativ als Backend-Änderung
zu werten. Tests werden nie in Produktion ausgeliefert; ein reiner Test-Commit
darf kein Staging-/Deploy-Gate erzwingen.

## Source

- **File:** `.claude/hooks/e2e_commit_gate.py`
- **Identifier:** `detect_scope`
- **File:** `.claude/hooks/staging_gate.py`
- **Identifier:** `_detect_committed_scope`

(Tooling-Schicht — keine Frontend-/Go-/Python-Produktiv-Schicht betroffen.)

## Estimated Scope

- **LoC:** ~4 (je eine `elif`-Bedingung pro Funktion)
- **Files:** 2 Hook-Dateien + 1 neue mock-freie Testdatei
- **Effort:** low

## Dependencies

- `git diff --name-only` Output (gestaged bzw. HEAD~1..HEAD).
- Downstream: `staging_gate.gate_check()` (Deploy-Hard-Gate überspringt bei
  `docs-only`), `write_verdict()` (Scope-Feld in `e2e_verified.json`).

## Acceptance Criteria

**AC-1:** Given ein Commit/Staging-Stand, der **ausschließlich** Dateien unter
`tests/` ändert (z.B. `tests/tdd/test_foo.py`), When `detect_scope()` bzw.
`_detect_committed_scope()` aufgerufen wird, Then ist das Ergebnis `"docs-only"`
(zuvor fälschlich `"backend"`).

**AC-2:** Given ein Commit, der sowohl `src/`- als auch `tests/`-Dateien ändert,
When die Scope-Erkennung läuft, Then ist das Ergebnis `"backend"` — `src/`
triggert, `tests/` bleibt neutral und verändert das Ergebnis nicht.

**AC-3:** Given ein Commit, der `frontend/`- und `tests/`-Dateien ändert, When
die Scope-Erkennung läuft, Then ist das Ergebnis `"frontend-only"` (tests/
neutral, kein fälschliches `"full-stack"`).

**AC-4:** Given ein wirklich unbekannter Pfad (z.B. `config.ini`, `.env`), When
die Scope-Erkennung läuft, Then bleibt das Ergebnis weiterhin `"backend"` — die
konservative Behandlung unbekannter Pfade ist unverändert (nur `tests/` wird
explizit neutralisiert, keine pauschale Aufweichung).

**AC-5:** Given die Korrektur ist in beiden Hooks identisch umgesetzt, When man
denselben Datei-Mix durch `detect_scope()` und `_detect_committed_scope()`
schickt, Then liefern beide Funktionen denselben Scope (Konsistenz zwischen
informationellem Hook und Deploy-Gate).

## Test Strategy

Mock-frei: Pro Testfall ein echtes Temp-Git-Repo (`git init`, Dateien anlegen,
`git add`/`commit`), dann die Funktion mit `cwd`/Arbeitsverzeichnis auf das
Temp-Repo aufrufen und den zurückgegebenen Scope prüfen. Keine
`monkeypatch.setattr(subprocess, "run", …)`-Mocks (anders als die bestehende
`test_e2e_scope_detection.py`).

## Out of Scope

- Keine Änderung am Verhalten unbekannter Pfade (bleiben `backend`).
- Keine Migration der bestehenden gemockten `test_e2e_scope_detection.py`.
- Keine Änderung an `gate_check()`/`write_verdict()`-Logik selbst.
