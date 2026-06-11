---
entity_id: issue_728_telegram_scope_neutral_paths
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [staging-gate, telegram, deploy-gate, tooling]
---

# Issue #728 — Telegram-Scope-Erkennung filtert Doku-/Tooling-Pfade

## Approval

- [x] Approved

## Purpose

`_scope_touches_telegram()` darf reine Doku-/Tooling-Pfade (`docs/`, `.md`, `.claude/`, `tests/`, `README`, `.gitignore`) NICHT als Telegram-Code-Berührung werten. Nur echte Code-Pfade (z.B. `outputs/telegram.py`) dürfen den Telegram-Live-Gate auslösen. Behebt einen False-Positive, der reine Doku-`.md`-Commits fälschlich die Deploy-Freigabe blockieren ließ (#724).

## Source

- **File:** `.claude/hooks/e2e_telegram_live.py`
- **Identifier:** `_scope_touches_telegram()`

## Estimated Scope

- **LoC:** ~12
- **Files:** 2 (1 Hook + 1 Test)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `staging_gate._detect_committed_scope` | reference | Vorbild für Neutral-Liste (Z.98–106) — gleiche Pfad-Klassen |
| `staging_gate._telegram_live_gate` | downstream | Aufrufer, reicht `git diff`-Liste an die Funktion |

## Implementation Details

In `_scope_touches_telegram()` jede geänderte Datei zuerst gegen eine Neutral-Liste prüfen
und überspringen, BEVOR der `telegram`-Substring-Match läuft. Neutral = identisch zur Liste
in `_detect_committed_scope()`:

```python
def _is_neutral_path(path: str) -> bool:
    """Doku-/Tooling-Pfade, die NIE den Telegram-Code-Pfad bilden (analog
    staging_gate._detect_committed_scope Neutral-Liste, Issue #728)."""
    return (
        path.startswith("docs/")
        or path.startswith(".claude/")
        or path.endswith(".md")
        or path.startswith("README")
        or path == ".gitignore"
        or path.startswith("tests/")
    )

# in _scope_touches_telegram, in der Schleife:
for f in changed_files:
    if _is_neutral_path(f):
        continue
    f_lower = f.lower()
    if any(p in f_lower for p in telegram_patterns):
        return True
return False
```

Hinweis: Der Hook bleibt dependency-arm (nur stdlib, kein App-Import — #685-Lehre).
Die Neutral-Liste wird inline dupliziert, NICHT aus `staging_gate` importiert, um die
Standalone-Lauffähigkeit unter System-python3 zu erhalten.

## Expected Behavior

- **Input:** Liste geänderter Dateipfade (aus `git diff --name-only`)
- **Output:** `True` nur wenn mind. eine NICHT-neutrale Datei den `telegram`-Substring trägt
- **Side effects:** keine

## Acceptance Criteria

- **AC-1:** Given ein echtes git-Repo, dessen letzter Commit ausschließlich eine Doku-Datei
  `docs/specs/modules/issue_692_telegram_disabled_unconfigured.md` ändert / When
  `_scope_touches_telegram()` gegen die reale `git diff`-Liste läuft / Then liefert sie
  `False` (Doku-`.md` löst keinen Telegram-Scope aus).
  - Test: Mini-Git-Repo in tmp_path, Commit nur mit der `.md`, Funktion gegen echte
    `git diff --name-only HEAD~1 HEAD`-Ausgabe — mock-frei.

- **AC-2:** Given derselbe Aufbau, aber der Commit ändert `src/outputs/telegram.py` (echter
  Code-Pfad) zusätzlich zu einer Doku-`.md` / When `_scope_touches_telegram()` läuft / Then
  liefert sie weiterhin `True` (echter Telegram-Code wird nicht maskiert).
  - Test: Mini-Git-Repo mit gemischtem Commit, Funktion gegen echte `git diff`-Liste.

- **AC-3:** Given ein echtes git-Repo, dessen letzter Commit nur eine Doku-`.md` mit
  „telegram" im Pfad ändert, und ein `staging_gate` mit `REPO_DIR` auf dieses Repo, OHNE
  gesetzte `GZ_TELEGRAM_TEST_CHAT_ID` / When `write_verdict("VERIFIED: ...")` aufgerufen
  wird / Then liefert es `0` UND das Verdict-Artefakt (`out.json`) wird geschrieben — der
  Telegram-Live-Gate blockt eine reine Doku-Änderung NICHT.
  - Test: End-to-End über `staging_gate.write_verdict` (das echte Close-Gate), mock-frei,
    reproduziert exakt den #724-Blocker.

## Test Manifest

Tests in `tests/tdd/test_issue_728_telegram_scope_neutral.py` (mock-frei, echte git-Repos):

- `ac1_docs_only_telegram_md_is_not_telegram_scope` — AC-1: Doku-`.md` → `_scope_touches_telegram()` False
- `ac2_real_code_plus_docs_still_telegram_scope` — AC-2: `telegram.py` + docs → True
- `ac3_write_verdict_not_blocked_by_docs_only_telegram_md` — AC-3: echtes Close-Gate blockt docs-only nicht

## Changelog

- 2026-06-11: Initial (Issue #728).
