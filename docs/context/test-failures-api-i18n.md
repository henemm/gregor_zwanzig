# Context: Test Failures - API Mismatch & i18n

## Request Summary

Fix 3 bugs causing test failures (10 tests failing, 274 passing):

1. **EmailOutput.send() API mismatch** - trip_report_scheduler uses wrong kwarg
2. **Missing temp directory** - test tries to write without creating dir
3. **German vs English text** - code outputs English but spec requires German

## Analysis

### Bug 1: EmailOutput.send() API Mismatch

**Location:** `src/services/trip_report_scheduler.py:207-211`

**Problem:**
```python
# Current (WRONG):
email_output.send(
    subject=report.email_subject,
    html_body=report.email_html,      # <-- WRONG kwarg
    plain_text_body=report.email_plain,
)

# Expected signature:
def send(self, subject: str, body: str, html: bool = True, plain_text_body: str | None = None)
```

**Root Cause:** Developer used `html_body` instead of `body` as the second positional argument.

**Fix:** Change `html_body=` to `body=` (or use positional arg).

### Bug 2: Missing /tmp/gregor_email_test/ Directory

**Location:** `tests/tdd/test_html_email.py:495`

**Problem:**
```python
with open("/tmp/gregor_email_test/imap_retrieved.eml", "wb") as f:
    f.write(raw_email)
```

**Root Cause:** Directory `/tmp/gregor_email_test/` doesn't exist, causing FileNotFoundError.

**Fix:** Add `os.makedirs("/tmp/gregor_email_test", exist_ok=True)` before file write.

### Bug 3: German vs English Text Mismatch

**Location:** `src/web/pages/compare.py:726`

**Problem:**
```python
# Current (WRONG - English):
lines.append("⛷️ SKI RESORT COMPARISON")

# Expected (German - per spec):
lines.append("⛷️ SKIGEBIETE-VERGLEICH")
```

**Spec Reference:** `docs/specs/compare_email.md:285` defines German text.

**Root Cause:** Code was changed to English, breaking spec compliance.

**Fix:** Change back to German `"⛷️ SKIGEBIETE-VERGLEICH"`.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| src/services/trip_report_scheduler.py | MODIFY | Fix kwarg `html_body` → `body` |
| tests/tdd/test_html_email.py | MODIFY | Add `os.makedirs()` before file write |
| src/web/pages/compare.py | MODIFY | Change English → German header |

### Scope Assessment

- Files: 3
- Estimated LoC: +2/-2
- Risk Level: LOW (isolated fixes, no architectural changes)

### Technical Approach

1. Fix API mismatch in trip_report_scheduler.py (1 line)
2. Add directory creation in test_html_email.py (2 lines)
3. Restore German text in compare.py (1 line)

### Open Questions

None - all fixes are straightforward with clear root causes.

## Verification

After fixes, run:
```bash
uv run pytest tests/e2e/test_e2e_story3_reports.py::TestSchedulerIntegration::test_scheduler_send_reports
uv run pytest tests/tdd/test_html_email.py::TestRealGmailE2E
uv run pytest tests/tdd/test_html_email.py::TestSubscriptionEmailGeneration
uv run pytest tests/tdd/test_html_email.py::TestEndToEndEmailSending
```
