---
entity_id: bug_397_segment_timezone_display_tests
type: tests
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
tags: [tests, timezone, email, sms, segment, cest, utc, bug-397]
parent: bug_397_segment_timezone_display
phase: phase5_tdd_red
---

# Bug #397 — Segment-Zeitangaben UTC vs. lokal: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/bug_397_segment_timezone_display.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/bug_397_segment_timezone_display.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_397_segment_timezone.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `build_segment_label_local_time_cest` | AC-2 | `build_segment_label(change, segments, tz)` gibt "10:00" (CEST) statt "08:00" (UTC) zurück |
| `render_plain_segment_header_local_time_cest` | AC-1 | `render_plain` Segment-Kopfzeile enthält lokale CEST-Zeit, nicht UTC |
| `render_narrow_segment_header_local_time_cest` | AC-3 | `render_narrow` (Signal/Telegram) Segment-Kopfzeile enthält lokale CEST-Zeit |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests sollen FAIL sein)
uv run pytest tests/tdd/test_issue_397_segment_timezone.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_issue_397_segment_timezone.py -v
```

## Changelog

- 2026-05-26: Initial test manifest erstellt für Bug #397 (Zeitzonen-Versatz Segment-Header).
