---
entity_id: bug_256_thunder_color_tests
type: tests
created: 2026-05-18
updated: 2026-05-18
status: draft
version: "1.0"
tags: [tests, email, design-tokens, thunder, bug-256]
parent: bug_256_thunder_color
phase: phase5_tdd_red
---

# Bug #256 — Thunder-Farbkonflikt: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/bug_256_thunder_color.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/bug_256_thunder_color.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_256_thunder_color.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_app_css_thunder_is_red` | AC-1 | `app.css` enthält `--g-wx-thunder: #c43a2a`, kein `#5a3a7a` |
| `test_ac2_design_tokens_py_constant` | AC-2 | `G_WX_THUNDER == "#c43a2a"` importierbar |
| `test_ac3_no_old_value_in_tokens_py` | AC-3 | `design_tokens.py` enthält kein `#5a3a7a` |
| `test_ac4_design_system_md_updated` | AC-4 | `design_system.md` zeigt Konflikt als gelöst (#256), kein `#5a3a7a` mehr aktiv |
| `test_ac5_design_system_tokens_css` | AC-5 | `design_system_tokens.css` hat `#c43a2a` + Issue-#256-Referenz im Kommentar |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests sollen FAIL sein)
uv run pytest tests/tdd/test_issue_256_thunder_color.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_issue_256_thunder_color.py \
             tests/tdd/test_issue_254_email_template_vorarbeit.py -v
```

## Changelog

- 2026-05-18: Initial test manifest erstellt für Bug #256 (Thunder-Farbkonflikt).
