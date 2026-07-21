---
entity_id: issue_784_staging_gate_worktree_head
type: module
created: 2026-06-12
updated: 2026-06-12
status: draft
version: "1.0"
tags: [infra, tooling, e2e-gate, worktree, deploy, bugfix]
---

# staging_gate: Attestation auf Worktree-HEAD taggen, Datei im geteilten Hauptrepo ablegen

## Approval

- [x] Approved

## Purpose

`staging_gate.py --write-verdict` löst HEAD-SHA und Scope über die hartkodierte
Konstante `REPO_DIR = /home/hem/gregor_zwanzig` immer im **Hauptrepo** auf. Im
worktree-isolierten OpenSpec-Workflow ist der zu bescheinigende Commit aber der
**Worktree-HEAD**. Steht das Hauptrepo (Parallel-Session / hinterherhängend) auf
einem anderen Commit, taggt die Attestation `.claude/e2e_verified/<sha>.json` den
**falschen** Commit → Deploy-Gate `--check` schlägt fehl → manuelles
`git merge --ff-only` als Krücke (dokumentiert in #733, #744, #760, #770, #777).

Diese Änderung trennt die zwei orthogonalen Fragen, die im hartkodierten Pfad
vermischt sind:
1. **Welcher Commit wird bescheinigt?** → Worktree-HEAD (das verifizierte, cwd).
2. **Wo liegt die Attestation-Datei?** → geteiltes Hauptrepo (gitignored, überlebt
   `reset --hard` beim Deploy).

Git liefert beides nativ aus jedem Worktree: `git rev-parse --show-toplevel`
(Worktree) und `git rev-parse --git-common-dir` (→ `<hauptrepo>/.git` → `.parent`).

## Source

- **File:** `.claude/hooks/_e2e_paths.py` — zwei neue pure, mock-freie Helfer
  `shared_repo_dir(cwd=None)` und `worktree_repo_dir(cwd=None)` (git-Auflösung;
  AC-5-doc-compliance verbietet `rev-parse` in den Hook-Dateien selbst).
- **File:** `.claude/hooks/staging_gate.py` — `REPO_DIR` wird Sentinel-Default;
  neue interne Helfer `_shared_repo_dir()` (Datei-Ort) und `_verified_repo_dir()`
  (Commit/Scope). SHA + Scope lesen aus Worktree, Datei-Ort aus geteiltem Repo.
- **File:** `tests/tdd/test_issue_784_staging_gate_worktree_head.py` — neue Tests.

Schicht-Hinweis: reine Tooling-Hooks (Python). Keine Frontend-/Go-/FastAPI-Schicht
betroffen. `prod_selftest.py` bleibt unverändert (läuft post-deploy im Hauptrepo →
kein Bug, bewusst out-of-scope).

## Estimated Scope

- **LoC:** ~40 (Hooks) + Test
- **Files:** 2 Source + 1 Test
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `git` CLI | tool | `rev-parse --show-toplevel` / `--git-common-dir` |
| `.claude/hooks/_e2e_paths.py` | module | Trägt die neue Git-Auflösung |
| `deploy-gregor-prod.sh` | consumer | ruft `--check` (cwd=Hauptrepo) — unverändert korrekt |

## Implementation Details

```
_e2e_paths.py (neu):
  shared_repo_dir(cwd=None) -> Path | None:
    out = git rev-parse --git-common-dir   (cwd=cwd or os.getcwd())
    fehler/leer -> None
    common = Path(out); relativ -> (base / common).resolve()
    return common.parent           # Hauptrepo-Arbeitsbaum

  worktree_repo_dir(cwd=None) -> Path | None:
    out = git rev-parse --show-toplevel    (cwd=cwd or os.getcwd())
    fehler/leer -> None
    return Path(out)               # aktueller Worktree

staging_gate.py:
  _DEFAULT_REPO_DIR = Path("/home/hem/gregor_zwanzig")
  REPO_DIR = _DEFAULT_REPO_DIR     # Sentinel + Fallback; weiter monkeypatchbar

  _shared_repo_dir():
    if REPO_DIR != _DEFAULT_REPO_DIR: return REPO_DIR   # Test-Override (Alt-Verhalten)
    return _e2e_paths.shared_repo_dir() or REPO_DIR

  _verified_repo_dir():
    if REPO_DIR != _DEFAULT_REPO_DIR: return REPO_DIR   # Test-Override (Alt-Verhalten)
    return _e2e_paths.worktree_repo_dir() or REPO_DIR

  _head_sha()            -> head_sha(_verified_repo_dir())
  _commit_e2e_path(sha)  -> commit_e2e_path(_shared_repo_dir(), sha or _head_sha())
  _default_e2e_path()    -> default_e2e_path(_shared_repo_dir(),
                                _shared_repo_dir()/".claude"/"e2e_verified.json",
                                _head_sha())
  _detect_committed_scope(): git diff ... cwd=_verified_repo_dir()
  _telegram_live_gate():     git diff ... cwd=_verified_repo_dir()
```

**Sentinel-Seam:** In Produktion bleibt `REPO_DIR == _DEFAULT_REPO_DIR` → dynamische
Git-Auflösung greift. Biegt ein Test `REPO_DIR` per monkeypatch um (≠ Default) →
beide Helfer geben diesen Wert zurück = bisheriges Ein-Repo-Verhalten. Damit bleiben
die 7 bestehenden REPO_DIR-monkeypatchenden Tests ohne Änderung grün.

## Expected Behavior

- **Input:** `staging_gate.py --write-verdict "VERIFIED: ..." --findings-json ...`,
  ausgeführt mit cwd im Worktree (HEAD = Commit B), während das Hauptrepo auf
  Commit A steht (A ≠ B).
- **Output:** Attestation-Datei `<hauptrepo>/.claude/e2e_verified/B.json` mit
  `verified_commit == B` (Worktree-HEAD).
- **Side effects:** Datei landet im geteilten Hauptrepo (nicht im Worktree).

## Acceptance Criteria

- **AC-1:** Given ein echtes temporäres Git-Repo (Hauptrepo) auf Commit A mit einem
  daran hängenden Worktree auf Commit B (B ≠ A) / When `staging_gate.py
  --write-verdict "VERIFIED: ..."` mit cwd = Worktree ausgeführt wird / Then wird die
  Attestation-Datei unter `<hauptrepo>/.claude/e2e_verified/<B>.json` geschrieben und
  ihr `verified_commit`-Feld ist **B** (Worktree-HEAD), nicht A.
  - Test: Echtes Temp-Repo + echter `git worktree add` + Subprozess-Aufruf des realen
    `staging_gate.py` mit `cwd=worktree`; danach JSON laden und `verified_commit == B`
    sowie Datei-Ablageort im Hauptrepo prüfen. Kein Mock.

- **AC-2:** Given dasselbe Setup wie AC-1 / When die Attestation geschrieben ist /
  Then liefert ein anschließender `staging_gate.py --check` mit cwd = Worktree
  (HEAD = B) Exit 0, weil `verified_commit (B) == HEAD (B)` — ohne jeden manuellen
  `git merge --ff-only`-Zwischenschritt.
  - Test: Subprozess `--check` mit `cwd=worktree`, Exit-Code 0 asserten. (Scope des
    Worktree-Commits berührt Backend, damit das Gate nicht docs-only-übersprungen wird.)

- **AC-3:** Given ein Worktree auf Commit B, dessen HEAD **nicht** dem Hauptrepo-Stand
  entspricht und der NICHT auf origin/main liegt / When nach `--write-verdict` aus dem
  Worktree ein `--check` mit cwd = Hauptrepo (HEAD = A) läuft / Then Exit 1 mit
  Mismatch-Meldung (`verified_commit (B) != HEAD (A)`) — das Gate bleibt **schärfer**,
  nicht schwächer.
  - Test: Subprozess `--check` mit `cwd=hauptrepo`, Exit 1 asserten. Kein Mock.

- **AC-4:** Given ein per monkeypatch auf ein Temp-Repo umgebogenes `REPO_DIR`
  (Bestands-Testmuster) / When `_head_sha()` und `_default_e2e_path()` aufgerufen
  werden / Then verhalten sie sich wie bisher (SHA + Datei-Ort folgen dem
  gepatchten `REPO_DIR`) — die 7 bestehenden REPO_DIR-Tests bleiben grün.
  - Test: Die bestehende Suite `tests/tdd/test_e2e_path_helper.py`,
    `test_e2e_commit_namespacing.py`, `test_e2e_verified_retention.py`,
    `test_issue_668_head_sha_dedup.py`, `test_scope_tests_neutral.py`,
    `test_issue_728_telegram_scope_neutral.py`, `test_issue_686_telegram_functional_live.py`
    läuft unverändert grün.

- **AC-5:** Given die geänderten Hook-Dateien / When `staging_gate.py` auf den String
  `rev-parse` geprüft wird / Then enthält sie ihn **nicht** (Git-Auflösung lebt
  ausschließlich in `_e2e_paths.py`) — die bestehende doc-compliance-Invariante
  (`test_e2e_path_helper.py::test_path_logic_only_in_shared_module`) bleibt erfüllt.
  - Test: bestehender doc-compliance-Test bleibt grün (markiert `# doc-compliance-test`).

## Known Limitations

- `prod_selftest.py` wird bewusst nicht angefasst: es läuft post-deploy im Hauptrepo
  (cwd = Hauptrepo, HEAD = origin/main) und ist vom Bug nicht betroffen.
- Bei git-Fehler (kaputtes/kein Repo) fällt die Auflösung fail-soft auf die
  hartkodierte `REPO_DIR`-Konstante zurück — identisch zum heutigen Verhalten.

## Changelog

- 2026-06-12: Initial spec created (Issue #784)
