# Context: Issue #784 — staging_gate write-verdict taggt Worktree-HEAD statt Hauptrepo-HEAD

## Request Summary
`staging_gate.py --write-verdict` löst HEAD-SHA und Scope immer im hartkodierten
Hauptrepo (`REPO_DIR = /home/hem/gregor_zwanzig`) auf. Läuft die eigentliche Arbeit
in einem Worktree (Standard im OpenSpec-Workflow), und steht das Hauptrepo auf einem
anderen Commit, wird die Attestation `.claude/e2e_verified/<sha>.json` auf den **falschen**
Commit getaggt → Deploy-Gate `--check` schlägt fehl → manuelles `git merge --ff-only`
als Krücke (dokumentiert in #733, #744, #760, #770, #777).

## Root Cause
Zwei orthogonale Fragen sind in einem hartkodierten Pfad vermischt:
1. **Welcher Commit wird bescheinigt?** → muss Worktree-HEAD sein (das verifizierte; cwd).
2. **Wo liegt die Attestation-Datei?** → muss im geteilten Hauptrepo liegen
   (gitignored, überlebt `reset --hard` beim Deploy).

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/staging_gate.py` | Trägt `REPO_DIR`-Konstante; `_head_sha`, `_commit_e2e_path`, `_default_e2e_path`, `_detect_committed_scope`, `_telegram_live_gate` hängen daran |
| `.claude/hooks/_e2e_paths.py` | Geteiltes Pfad-Helfer-Modul (Issue #665). Hier MUSS die Git-Auflösung landen (siehe AC-5-Constraint unten) |
| `.claude/hooks/prod_selftest.py` | Nutzt dasselbe Pattern, läuft aber im Hauptrepo post-deploy → **nicht** vom Bug betroffen, out-of-scope |

## Existing Patterns
- `_e2e_paths.py` ist die SSoT für Pfad-/SHA-Logik (Issue #665). Hooks delegieren dahin.
- Tests laufen **mock-frei** gegen echte temporäre Git-Repos und monkeypatchen `REPO_DIR`
  auf das Temp-Repo (kein Mock — realer Pfad auf echtes Repo).

## Constraints (kritisch fürs Design)
- **AC-5 doc-compliance (`test_e2e_path_helper.py`)** verbietet den String `rev-parse`
  in `staging_gate.py` und `prod_selftest.py` — die neue Git-Auflösung MUSS in
  `_e2e_paths.py` stehen.
- **7 Tests monkeypatchen `staging_gate.REPO_DIR`** (test_e2e_commit_namespacing,
  test_e2e_verified_retention, test_e2e_path_helper, test_issue_668_head_sha_dedup,
  test_scope_tests_neutral, test_issue_728_telegram_scope_neutral,
  test_issue_686_telegram_functional_live) und erwarten, dass dieser EINE Knopf sowohl
  SHA als auch Datei-Ort steuert. Das Design muss diesen Seam erhalten, sonst brechen
  alle 7 Tests ohne fachlichen Grund.

## Lösungsskizze (sentinel-basierter Seam, null Test-Churn)
- `_e2e_paths.py`: zwei neue mock-freie Helfer
  - `shared_repo_dir(cwd=None)` → `git rev-parse --git-common-dir` (relativ→absolut), `.parent` = Hauptrepo-Arbeitsbaum (Datei-Ort).
  - `worktree_repo_dir(cwd=None)` → `git rev-parse --show-toplevel` = aktueller Worktree (Commit-/Scope-Quelle).
- `staging_gate.py`: `REPO_DIR` bleibt als Sentinel-Default-Konstante.
  - `_shared_repo_dir()` / `_verified_repo_dir()`: ist `REPO_DIR` **explizit umgebogen**
    (Test-Monkeypatch ≠ Default) → diesen Wert für BEIDE verwenden (Alt-Verhalten, alle
    7 Tests grün). Sonst (Produktion) dynamisch via `_e2e_paths` auflösen, Fallback = `REPO_DIR`.
  - SHA + Scope (`_head_sha`, `_detect_committed_scope` cwd, `_telegram_live_gate` cwd)
    → `_verified_repo_dir()`.
  - Datei-Ort (`_commit_e2e_path`, `_default_e2e_path`, `CANONICAL_E2E_PATH`)
    → `_shared_repo_dir()`.

## Dependencies
- Upstream: `git` CLI, `_e2e_paths`.
- Downstream: `deploy-gregor-prod.sh` (ruft `--check`), Staging-Validator-Agent (ruft `--write-verdict`).

## Risks & Considerations
- **Schärfer, nicht schwächer:** Bescheinigt man aus einem nicht-gepushten Worktree-HEAD,
  blockt der Deploy-`--check` den Mismatch weiterhin korrekt.
- prod_selftest.py bleibt unangetastet (kein Bug dort) — bewusst out-of-scope.
- `--git-common-dir` liefert aus Hauptrepo-Top `.git` (relativ) → gegen cwd auflösen.
