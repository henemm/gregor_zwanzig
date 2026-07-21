---
entity_id: issue_728_telegram_scope_neutral_tests
type: tests
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [tests, telegram, staging-gate, deploy-gate, issue-728]
parent: issue_728_telegram_scope_neutral_paths
phase: phase5_tdd_red
---

# Issue #728 — Telegram-Scope-Erkennung filtert Doku-Pfade (Tests v1.0)

## Approval

- [x] Approved (2026-06-11, PO — „go")

## Purpose

Test-Manifest für #728. Beweist mock-frei (echte git-Repos, echte `git diff`-Ausgabe,
echtes Close-Gate `staging_gate.write_verdict`): Eine reine Doku-`.md` mit „telegram" im
Pfad löst KEINEN Telegram-Live-Gate aus, ein echter Code-Pfad weiterhin schon, und das
Close-Gate blockt eine docs-only-Änderung nicht (der #724-Blocker ist behoben).

Parent-Spec: `docs/specs/modules/issue_728_telegram_scope_neutral_paths.md` v1.0

## Source

- **Files:**
  - `tests/tdd/test_issue_728_telegram_scope_neutral.py` (NEU — mock-frei)
- **Spec:** `docs/specs/modules/issue_728_telegram_scope_neutral_paths.md` v1.0

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---------------|----|------------------|
| `ac1_docs_only_telegram_md_is_not_telegram_scope` | AC-1 | Echtes tmp-git-Repo, Commit ändert NUR `docs/specs/modules/issue_692_telegram_disabled_unconfigured.md`; `_scope_touches_telegram()` gegen die reale `git diff`-Liste → `False`. |
| `ac2_real_code_plus_docs_still_telegram_scope` | AC-2 | Commit ändert `src/outputs/telegram.py` UND eine Doku-`.md`; `_scope_touches_telegram()` → weiterhin `True` (echter Code wird nicht maskiert). |
| `ac3_write_verdict_not_blocked_by_docs_only_telegram_md` | AC-3 | Echtes Close-Gate: `staging_gate.write_verdict` gegen tmp-git-Repo mit docs-only-Telegram-`.md`-Commit, OHNE `GZ_TELEGRAM_TEST_CHAT_ID` → Rückgabe `0` UND `out.json` geschrieben (Verdict NICHT verweigert). Reproduziert den #724-Blocker. Mock-frei (echtes git, monkeypatch nur ENV + REPO_DIR). |

## Expected RED-State (vor GREEN-Phase)

- **AC-1** rot: `_scope_touches_telegram()` matcht aktuell `telegram` im `.md`-Pfad → liefert
  fälschlich `True` statt `False`.
- **AC-3** rot: dadurch verweigert `write_verdict` das Verdict (Rückgabe `1`, kein `out.json`)
  obwohl der Scope eine reine Doku-`.md` ist.
- **AC-2** grün-stabil: dient als Regressions-Wächter (echter Code-Pfad muss `True` bleiben).

## Changelog

- 2026-06-11: Initial test manifest (Issue #728).
