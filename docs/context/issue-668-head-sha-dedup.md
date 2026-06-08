# Context: Issue #668 — staging_gate.write_verdict ruft _head_sha() doppelt auf

## Request Summary
`write_verdict()` in `.claude/hooks/staging_gate.py` ruft `_head_sha()` zweimal auf
(zwei `git rev-parse HEAD`-Subprozesse pro Aufruf). SHA einmal erfassen und
wiederverwenden. Vorbestehend seit #662, Nebenbefund aus #665 (Adversary F002).

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/staging_gate.py` | `write_verdict()` (Z.142–177) — Fix hier |
| `.claude/hooks/_e2e_paths.py` | `head_sha()`/`commit_e2e_path()` — Quelle der Subprozesse (#665) |
| `tests/tdd/test_staging_gate.py` | Bestehende write_verdict-Tests (Z.203 ff.) |

## Befund im Detail
`write_verdict()` ruft `_head_sha()` an zwei Stellen:
- Z.144–145: `e2e_path = _commit_e2e_path()` → intern `_head_sha()` (nur wenn kein `--e2e-path`-Override)
- Z.160: `payload["verified_commit"] = _head_sha()` (immer)

Beide liefern denselben SHA → kein Korrektheitsproblem, nur ein überflüssiger Subprozess.

## Fix
```python
sha = _head_sha()
if e2e_path is None:
    e2e_path = _commit_e2e_path(sha)
...
payload["verified_commit"] = sha
```

## Existing Patterns
- `_commit_e2e_path(sha)` akzeptiert bereits einen optionalen SHA-Parameter (Z.57–59) — kein Signatur-Eingriff nötig.
- `gate_check()` ruft `_head_sha()` ebenfalls auf (Z.208), aber nur einmal — nicht betroffen.

## Dependencies
- Upstream: `_e2e_paths.head_sha(REPO_DIR)` (echtes `git rev-parse HEAD`)
- Downstream: `/e2e-verify`-Skill + `staging-validator` rufen `write_verdict` auf; Output-Format unverändert.

## Risks & Considerations
- **Kein Verhaltensänderung am Output:** geschriebene Datei bleibt bit-identisch (gleicher SHA).
- TDD-Beweis ist Subprozess-Zählung (Refactor-RED, vgl. #649): mock-freier PATH-Shim-`git`,
  der `rev-parse HEAD`-Aufrufe in eine Zählerdatei schreibt → vor Fix 2, nach Fix 1.
- **Scope:** tooling-only (`.claude/hooks/`), kein `src/`/`api/`/`internal/`/`frontend/` →
  kein Prod-Deploy nötig (Doku-/Tooling-Ausnahme, analog #665/#666).
