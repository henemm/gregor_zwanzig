---
entity_id: bug_554_556_test_fixes
type: bugfix
created: 2026-06-02
updated: 2026-06-02
status: completed
version: "1.0"
tags: [test, bugfix]
---

# Bug #554 + #556: Test-Fixes (playwright-skip + Issue-Close)

## Approval

- [x] Approved — implemented and validated

## Purpose

Zwei veraltete/fehlerhafte Tests bereinigen: `test_env_playwright_vorhanden` bricht dauerhaft ab weil `.env.playwright` nicht im Repo liegt; `test_sidebar_uses_trips_label` ist bereits grün (Issue schließen).

## Source

- **File:** `tests/tdd/test_epic_404_phase2_ist_screenshots.py:84`
- **Identifier:** `test_env_playwright_vorhanden`

## Estimated Scope

- **LoC:** ~4
- **Files:** 1
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/.env.playwright` | external file | Staging-Credentials — nicht im Repo |

## Implementation Details

```python
# Vor dem assert: skip wenn Datei fehlt
def test_env_playwright_vorhanden():
    env = REPO_ROOT / "frontend/.env.playwright"
    if not env.exists():
        pytest.skip(".env.playwright fehlt — E2E-Screenshot-Tests übersprungen")
    content = env.read_text()
    assert "E2E_USER" in content
    assert "E2E_PASS" in content
```

## Expected Behavior

- **Input:** pytest läuft ohne `frontend/.env.playwright` im Repo
- **Output:** `test_env_playwright_vorhanden` beendet mit Status `SKIPPED`
- **Side effects:** Keine — andere Tests im selben File laufen unverändert durch

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-06-02 | Initial spec — pytest.skip statt hard assert (Bug #554); Issue #556 schließen |

## Acceptance Criteria

**AC-1:** Given `.env.playwright` existiert nicht / When pytest `test_env_playwright_vorhanden` läuft / Then wird der Test mit Status `SKIPPED` beendet, nicht `FAILED`.

**AC-2:** Given `.env.playwright` existiert mit `E2E_USER` und `E2E_PASS` / When pytest `test_env_playwright_vorhanden` läuft / Then wird der Test mit Status `PASSED` beendet.

**AC-3:** Given Issue #556 / When überprüft / Then ist das Issue auf GitHub als `closed` markiert (Test läuft bereits grün).
