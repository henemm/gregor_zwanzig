# Context: issue-1130-expected-commit-gate

## Request Summary
`staging_gate.py` soll gegen einen **übergebenen Ziel-Commit** prüfen können (`--expected-commit <sha>`) statt nur gegen den aktuellen `HEAD`. Das ist die Voraussetzung, damit `deploy-gregor-prod.sh` (henemm-infra#107) das Gate **vor** `git reset --hard` / `systemctl stop` aufrufen kann — Fail-fast gegen die Parallel-Session-Drift.

## Root Cause (Vorfall 2026-07-08)
`deploy-gregor-prod.sh` prüft heute erst NACH `stop gregor-python` (Z.84) + `reset --hard origin/main` (Z.89) — Gate-Check auf Z.104. Grund: `gate_check` vergleicht `verified_commit == _head_sha()` (Z.329–331), also MUSS erst resettet werden, damit `HEAD == Deploy-Commit`. Blockt eine Parallel-Merge das Gate, ist der Dienst schon unten → Drift.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/staging_gate.py` | **Zu ändern.** `gate_check()` (Z.294), `_detect_committed_scope()` (Z.133), `_head_sha()` (Z.87), `main()`-argparse (Z.371) |
| `.claude/hooks/_e2e_paths.py` | Shared-Helper: `head_sha`, `read/write_last_gate_scope`, `cached_scope_for_sha`, Repo-Auflösung |
| `deploy-gregor-prod.sh` (henemm-infra) | Aufrufer — wird in #107 umgestellt, NICHT in diesem Workflow |
| `tests/tdd/test_staging_gate.py` | Haupt-Testdatei (Muster für REPO_DIR/e2e_path) |
| `tests/tdd/test_issue_1096_gate_scope_selfpoison.py`, `test_issue_1084_gate_scope_cache.py`, `test_issue_784_staging_gate_worktree_head.py` | Regressions-Muster für Scope/HEAD/Cache |

## Existing Patterns
- **Reference-Commit** wird überall über `_head_sha()` bezogen (Z.87 → `_e2e_paths.head_sha`). 8 Nutzungsstellen (Z.93,106,123,145,254,307,309,329,367).
- **Scope-Detection** (`_detect_committed_scope`, Z.133) difft `_scope_diff_base()..HEAD` → docs-only-Skip. Cache pro HEAD via `write_last_gate_scope` (Z.309/367).
- **Rückwärtskompatible Flags:** neue argparse-Option + optionaler Funktionsparameter, `None` = altes Verhalten (vgl. `--e2e-path`, `--scope`).
- Tests nutzen **echtes git** (REPO_DIR-Monkeypatch auf tmp-Repo), keine Mocks.

## Dependencies
- **Upstream:** `_e2e_paths.py` (git-Helper), echtes git-Repo.
- **Downstream:** `deploy-gregor-prod.sh` (henemm-infra#107) ruft `--check`; `prod_selftest.py` teilt Scope-Cache; `/e2e-verify` schreibt Verdict (`--write-verdict`, unberührt).

## Design-Kernfrage (für Analyse/Spec zu klären)
Im Preflight (vor Reset) ist `HEAD` = alter Prod-Commit, `EXP` = origin/main. Damit muss `--expected-commit EXP` **konsistent** auf EXP referenzieren:
1. **Attestations-Vergleich:** `verified_commit == EXP` (statt HEAD).
2. **Scope-Skip:** Was der Deploy ändert = Diff `HEAD..EXP` (nicht `base..HEAD`). docs-only → Exit 0 auch ohne Attestation.
3. **Scope-Cache:** im Preflight-Modus **nicht** schreiben (HEAD≠EXP würde falschen Key cachen; der reguläre `--check` nach Reset schreibt korrekt).
Verdict-VERIFIED-Prüfung + Staleness bleiben unverändert.

## Risks & Considerations
- **Blast-Radius:** Gate-Datei — jeder Fehler blockt/öffnet Prod-Deploys projektweit. Änderung muss minimal + rückwärtskompatibel sein (bestehende HEAD-Aufrufer 1:1 unverändert).
- **Gate-Workflow:** `.claude/hooks/` ist schreibgeschützt → Edit braucht vom USER getipptes `override`/`go` (edit_gate-Token). Keine eigenmächtige Lockerung.
- **Kein Mock:** RED-Tests gegen echtes tmp-git-Repo, wie bestehende `test_staging_gate.py`.
- Keine Änderung am `--write-verdict`- oder `--detect-scope`-Pfad nötig.
