# Spec: e2e_commit_gate.detect_scope — post-commit-Fallback statt False docs-only

- **Issue:** #1197 (Sammel-Gate-Audit), Scheibe „e2e_commit_gate detect_scope post-commit" (#1137)
- **Created:** 2026-07-16
- **Typ:** Gate-Fix (false-durchlassend, kompensiert; Legacy-Helfer)
- **ADR-Nr.:** keine
- **Datei:** `.claude/hooks/e2e_commit_gate.py` (`detect_scope`, ~Z.48)
- **Prüfdatum (Regel-Budget):** 2026-10-14

## Problem

`detect_scope` klassifiziert über `git diff --cached` (gestagte Dateien). Post-commit
(Aufruf durch /e2e-verify) ist die Staging-Area leer → fälschlich "docs-only" auch
für Code-Commits → zu niedrige Verifikations-Tiefe.

## Lösung

Ist `git diff --cached` leer, auf `HEAD~1..HEAD` zurückfallen. git-Fehler im Fallback
→ konservativ "backend". Klassifikations-Logik unverändert.

## Acceptance Criteria

**AC-1:** Given es gibt gestagte Dateien (`git diff --cached` nicht leer) mit einer
`frontend/`-Datei, When `detect_scope` läuft, Then ist das Ergebnis wie bisher
(z.B. "frontend-only") — unveränderte Pre-Commit-Klassifikation.

**AC-2:** Given die Staging-Area ist leer, aber der letzte Commit (`HEAD~1..HEAD`)
enthält eine `frontend/`-Datei, When `detect_scope` läuft, Then ist das Ergebnis
aus dem Commit-Bereich abgeleitet (NICHT fälschlich "docs-only", sondern z.B.
"frontend-only").

**AC-3:** Given die Staging-Area ist leer, aber der letzte Commit enthält eine
`src/`-Datei, When `detect_scope` läuft, Then ist das Ergebnis "backend".

**AC-4:** Given die Staging-Area ist leer und der letzte Commit enthält
ausschließlich Doku/Tooling/Tests (`docs/`, `.claude/`, `*.md`, `tests/`), When
`detect_scope` läuft, Then ist das Ergebnis "docs-only" (korrekt, nicht
über-klassifiziert).

**AC-5:** Given die Staging-Area ist leer und der Fallback-Diff scheitert
(git-Fehler, z.B. kein Parent-Commit / `HEAD~1` nicht auflösbar), When
`detect_scope` läuft, Then ist das Ergebnis konservativ "backend" (über-verifizieren
statt unter-verifizieren) und es tritt kein Crash auf.

## Known Limitations

- Keine vollständige Konsolidierung mit `_e2e_paths._detect_scope_from_git_diff`
  (leicht abweichende Klassifikations-Nuancen; würde die issue_648-Scope-Tests
  berühren). Nur die post-commit-Datenquelle wird robust gemacht.

## Test-Politik

Kern-Schicht, deterministisch: echtes temporäres Git-Repo (`git init`, echte Commits,
echtes/leeres Staging), `detect_scope` gegen dieses Repo (Location-Seam auf `cwd`/
`find_project_root`, Git-Logik echt, kein Mock, kein Netz). Neue Datei
`tests/tdd/test_e2e_commit_gate_postcommit_scope.py`.
