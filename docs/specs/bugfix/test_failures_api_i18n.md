---
entity_id: test_failures_api_i18n
type: bugfix
created: 2026-02-11
status: draft
version: "1.0"
tags: [bugfix, api, i18n, tests]
workflow: test-failures-api-i18n
---

# Bugfix: Test Failures - API Mismatch & i18n

- [ ] Approved for implementation

## Purpose

Fix 3 bugs causing 5 test failures (excl. 5 expected RED tests for Feature 2.6):
1. Wrong keyword argument in trip_report_scheduler email send call
2. Missing temp directory in Gmail E2E test
3. English text where spec requires German in plain-text email header

## Scope

- Files: 3
- Estimated: +3/-2 LoC
- Risk Level: LOW

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_report_scheduler.py` | MODIFY | Fix kwarg `html_body` → `body` (line 209) |
| `tests/tdd/test_html_email.py` | MODIFY | Add `os.makedirs()` before file write (line 495) |
| `src/web/pages/compare.py` | MODIFY | Restore German header text (line 726) |

## Bug Details

### Bug 1: EmailOutput.send() API Mismatch

**Source:** `src/services/trip_report_scheduler.py:207-211`

```python
# CURRENT (broken):
email_output.send(
    subject=report.email_subject,
    html_body=report.email_html,       # <-- WRONG: kwarg doesn't exist
    plain_text_body=report.email_plain,
)

# FIX:
email_output.send(
    subject=report.email_subject,
    body=report.email_html,            # <-- CORRECT: matches signature
    plain_text_body=report.email_plain,
)
```

**EmailOutput.send() signature:** `send(subject, body, html=True, plain_text_body=None)`

### Bug 2: Missing Temp Directory

**Source:** `tests/tdd/test_html_email.py:495`

```python
# CURRENT (broken):
with open("/tmp/gregor_email_test/imap_retrieved.eml", "wb") as f:

# FIX: Add before the open() call:
os.makedirs("/tmp/gregor_email_test", exist_ok=True)
```

### Bug 3: English vs German Text (HTML + Plain-Text)

**Source:** `src/web/pages/compare.py` (multiple lines)
**Spec Reference:** `docs/specs/compare_email.md` lines 341-366

The entire email renderer was changed from German to English, violating the spec.

**Affected labels in `render_comparison_html()`:**

| Current (English) | Spec (German) | Line |
|-------------------|---------------|------|
| `Ski Resort Comparison` | `Skigebiete-Vergleich` | 521 |
| `Recommendation:` | `Empfehlung:` | 541 |
| `snow` / `new snow` / `sun` | `Schnee` / `Neuschnee` / `Sonne` | 533-537 |
| `Comparison` | `Vergleich` | 555 |
| `Metric` | `Metrik` | 558 |
| `Snow Depth` | `Schneehöhe` | 571 |
| `New Snow` | `Neuschnee` | 577 |
| `Wind/Gusts` | `Wind/Böen` | 584 |
| `Temperature (felt)` | `Temperatur (gefühlt)` | 599 |
| `Sunny Hours` | `Sonnenstunden` | 605 |
| `Cloud Cover` | `Bewölkung` | 614 |
| `Green = best value...` | `Grün = bester Wert...` | 621 |
| `Hourly Overview` | `Stunden-Übersicht` | 649 |

**Affected labels in `render_comparison_text()`:**

| Current (English) | Spec (German) | Line |
|-------------------|---------------|------|
| `SKI RESORT COMPARISON` | `SKIGEBIETE-VERGLEICH` | 726 |
| `RECOMMENDATION:` | `EMPFEHLUNG:` | 735 |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `outputs.email.EmailOutput` | Module | Email send API (unchanged) |
| `docs/specs/compare_email.md` | Spec | Defines German plain-text format |

## Test Plan

### Existing Tests (should PASS after fix)

- [ ] `tests/e2e/test_e2e_story3_reports.py::TestSchedulerIntegration::test_scheduler_send_reports` — Bug 1
- [ ] `tests/tdd/test_html_email.py::TestRealGmailE2E::test_real_gmail_e2e_html_email` — Bug 2
- [ ] `tests/tdd/test_html_email.py::TestSubscriptionEmailGeneration::test_subscription_generates_html_email_with_real_data` — Bug 3
- [ ] `tests/tdd/test_html_email.py::TestEndToEndEmailSending::test_e2e_email_contains_all_data` — Bug 3
- [ ] `tests/tdd/test_html_email.py::TestEndToEndEmailSending::test_e2e_plain_text_does_not_contain_css` — Bug 3

### Regression

- [ ] Full test suite passes (`uv run pytest`) — no regressions

## Acceptance Criteria

- [ ] `email_output.send()` called with correct `body=` kwarg
- [ ] Gmail E2E test creates temp directory before writing
- [ ] Plain-text email header uses German `"⛷️ SKIGEBIETE-VERGLEICH"`
- [ ] All 5 previously failing tests pass
- [ ] No new test failures introduced

## Changelog

- 2026-02-11: Initial spec created
