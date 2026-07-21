---
entity_id: issue_831_mobile_einfach_tests
type: tests
created: 2026-06-15
updated: 2026-06-15
status: implemented
version: "1.0"
tags: [tests, email, mobile, ampel, einfach-modus, bug-831]
parent: issue_831_mobile_einfach_stundenraster
phase: phase6_green
---

# Issue #831 — Mobile Stundenraster Einfach-Modus: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_831_mobile_einfach_stundenraster.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_831_mobile_einfach_stundenraster.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_831_mobile_einfach.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_mobile_compact_einfach_shows_ampel` | AC-1 | `.mobile-compact`-Div zeigt Ampel-Emojis im Einfach-Modus (parametrisiert: wind/gust/precip/pop) |
| `test_mobile_compact_roh_keeps_pre_block` | AC-2 | `.mobile-compact`-Div enthält `<pre>`-Block ohne Ampel im Roh-Modus (unverändertes #636-Verhalten) |
| `test_no_viewport_mismatch_einfach` | AC-3 | Desktop-Div (.desktop-only) UND Mobile-Div (.mobile-compact) zeigen beide Ampel im Einfach-Modus |
| `test_no_viewport_mismatch_roh` | AC-3 | Roh-Modus: weder Desktop noch Mobile zeigen Ampel |

**Normalisierte Entity-IDs (für Spec-Enforcement):**
- `mobile_compact_einfach_shows_ampel`
- `mobile_compact_roh_keeps_pre_block`
- `no_viewport_mismatch_einfach`
- `no_viewport_mismatch_roh`

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — AC-1 + AC-3 sollen FAIL sein)
uv run pytest tests/tdd/test_issue_831_mobile_einfach.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_issue_831_mobile_einfach.py \
             tests/tdd/test_issue_811_mode_matrix.py -v
```

## Changelog

- 2026-06-15: Tests implementiert und grün — alle ACs verifiziert
- 2026-06-15: Initial test manifest erstellt für Issue #831 (Mobile Einfach-Modus).
