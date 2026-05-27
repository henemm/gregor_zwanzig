---
entity_id: bug_405_sms_preview_screenshot_tests
type: tests
created: 2026-05-27
updated: 2026-05-27
status: active
version: "1.0"
tags: [tests, bugfix, screenshot, audit, tooling, issue-405]
parent: bug_405_sms_preview_screenshot
phase: phase5_tdd_red
---

# Bug #405 — SMS-Preview-Screenshot: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/bug_405_sms_preview_screenshot.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/bug_405_sms_preview_screenshot.md` v1.0

## Source

- **File:** `tests/tdd/test_bug_405_sms_preview_screenshot.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `script_exists` | Struktur | Script-Datei am erwarteten Pfad vorhanden |
| `ac1_broken_radio_selector_absent` | AC-1 | `input[type="radio"][value="sms"]` nicht mehr im Script |
| `ac1_preview_channel_sms_testid_absent` | AC-1 | `preview-channel-sms` Selektor nicht mehr im Script |
| `ac1_element_screenshot_used_for_sms` | AC-1 | `sms-phone-wrapper` + `.screenshot(` im Script vorhanden |
| `ac2_no_silent_catch_after_sms_wrapper` | AC-2 | Kein `.catch(() => {})` nach `sms-phone-wrapper` |
| `ac2_errors_incremented_in_sms_block` | AC-2 | `ERRORS++` nach `sms-phone-wrapper` vorhanden |

## Test-Ausführung

```bash
# RED-Phase (vor Fix — ac1/ac2 Tests müssen FAIL sein)
uv run pytest tests/tdd/test_bug_405_sms_preview_screenshot.py -v

# GREEN-Phase (nach Fix)
uv run pytest tests/tdd/test_bug_405_sms_preview_screenshot.py -v
```

## Expected RED-State

- `test_script_exists` → PASS (Script existiert bereits)
- `test_ac1_broken_radio_selector_absent` → FAIL (kaputte Selektoren noch vorhanden)
- `test_ac1_preview_channel_sms_testid_absent` → FAIL (kaputte Selektoren noch vorhanden)
- `test_ac1_element_screenshot_used_for_sms` → FAIL (`sms-phone-wrapper` noch nicht im Script)
- `test_ac2_no_silent_catch_after_sms_wrapper` → PASS (sms-phone-wrapper nicht im Script → test gibt early return)
- `test_ac2_errors_incremented_in_sms_block` → PASS (sms-phone-wrapper nicht im Script → test gibt early return)
