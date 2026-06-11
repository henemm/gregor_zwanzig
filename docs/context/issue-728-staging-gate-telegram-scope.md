# Context: Issue #728 — staging_gate Telegram-Scope flaggt docs-only `.md` fälschlich

## Request Summary
`_scope_touches_telegram()` matcht den Substring `telegram` über alle geänderten Dateinamen — auch über Doku-`.md`-Dateien. Eine reine `docs/`-`.md`-Änderung (z.B. `issue_692_telegram_disabled_unconfigured.md`) löst dadurch fälschlich den Telegram-Live-Gate aus und blockt `write_verdict` ohne `GZ_TELEGRAM_TEST_CHAT_ID`.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/e2e_telegram_live.py:47` | `_scope_touches_telegram()` — der fehlerhafte Substring-Match (Fix-Ort) |
| `.claude/hooks/staging_gate.py:73` | `_detect_committed_scope()` — Vorbild-Neutral-Liste (Z.98–106: `docs/`, `.claude/`, `.md`, `README`, `.gitignore`, `tests/`) |
| `.claude/hooks/staging_gate.py:143` | `_telegram_live_gate()` — Aufrufer, reicht `git diff`-Liste an `_scope_touches_telegram()` |
| `tests/tdd/test_issue_686_telegram_functional_live.py:258` | Bestehender mock-freier Gate-Test (echtes git-Repo) — Vorbild für Wächter-Test |

## Existing Patterns
- **Neutral-Liste** in `_detect_committed_scope()` filtert `docs/`-Prefix und `.md`-Suffix bereits korrekt als nicht-Code.
- **Mock-freie Gate-Tests**: echtes `git init` + Commits in `tmp_path`, dann Funktion gegen reale `git diff`-Ausgabe (kein Mock).

## Dependencies
- Upstream: `git diff --name-only HEAD~1..HEAD` (Dateiliste)
- Downstream: `_telegram_live_gate()` → `write_verdict()` → Close-Gate / `deploy-gregor-prod.sh`

## Existing Specs
- `docs/specs/modules/issue_686_telegram_functional_live_tests.md` — Ursprungs-Spec des Gates

## Risks & Considerations
- Fix muss eng sein: nur **echte Code-Pfade** dürfen den Telegram-Gate auslösen. `docs/`-Prefix + `.md`-Suffix herausfiltern, BEVOR der Substring-Match läuft.
- `.claude/`-Pfade: dieser Hook selbst (`e2e_telegram_live.py`) enthält `telegram` im Namen — eine reine Tooling-Edit an `.claude/` sollte ebenfalls keinen Live-Gate triggern (analog Neutral-Liste). Abwägung in Spec.
- Regression: gemischter Commit (`outputs/telegram.py` + docs) MUSS weiterhin `True` liefern.
- Tooling-only Change (`.claude/hooks/`) → kein Staging-Deploy nötig, wirkt beim nächsten Deploy-Lauf.
