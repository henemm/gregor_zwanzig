---
entity_id: issue_323_hex_fallbacks_tests
type: tests
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [tests, design-system, css-tokens, ap-007, hex-fallbacks, bug-323]
parent: issue_323_hex_fallbacks_cleanup
phase: phase5_tdd_red
---

# Issue #323 — Hex-Fallbacks Cleanup: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_323_hex_fallbacks_cleanup.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_323_hex_fallbacks_cleanup.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_323_hex_fallbacks.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_smsphoneframe_no_hex_literals` | AC-1 | SmsPhoneFrame.svelte enthält 0 Hex-Literale nach dem Fix |
| `test_profile_signature_no_hex_literals` | AC-2 | profileSignature.ts enthält 0 Hex-Literale nach dem Fix |
| `test_accent_fallback_field_removed_from_type` | AC-4 | `accentFallback` nicht mehr in profileSignature.ts |
| `test_accent_fallback_not_used_in_design_page` | AC-4 | `accentFallback` nicht mehr in _design/+page.svelte |
| `test_accent_fallback_not_used_in_any_productive_component` | AC-4 | `accentFallback` in keiner produktiven .svelte-Datei |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests sollen FAIL sein)
uv run pytest tests/tdd/test_issue_323_hex_fallbacks.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_issue_323_hex_fallbacks.py -v
```

## Changelog

- 2026-05-22: Test-Manifest erstellt für Issue #323 (AP-007 Restdrift: Hex-Fallbacks)
