---
entity_id: issue_496_channel_preview_layout_fix_tests
type: tests
created: 2026-06-01
updated: 2026-06-01
status: draft
version: "1.0"
tags: [tests, frontend, layout, overflow, channel-preview, issue-496]
parent: issue_496_channel_preview_layout_fix
phase: phase6_implement
---

# Issue #496 Layout-Fix — Test-Manifest

## Approval

- [x] Approved

## Test-Datei

`tests/tdd/test_issue_496_layout.py`

## Test-Funktionen

| Funktion | AC | Beschreibung |
|----------|----|-------------|
| `test_ac1_email_scroll_with_many_metrics` | AC-1 | Card.Root ist nicht mehr overflow:hidden; Scroll-Mechanismus funktioniert wenn nötig |
| `test_ac2_block_uses_full_tab_width` | AC-2 | ChannelPreviewBlock Breite >900px auf 1440px-Desktop |
| `test_ac3_five_metrics_all_columns_visible` | AC-3 | 5 Metriken passen ohne Scrollen (scrollWidth <= clientWidth) |
| `test_ac4_testids_present` | AC-4 | data-testids channel-preview-block und channel-fidelity-email vorhanden |

## RED-Ergebnisse (vor Fix)

| Funktion | Status | Befund |
|----------|--------|--------|
| `test_ac1_email_scroll_with_many_metrics` | FAIL | Card.Root hatte overflowX=hidden |
| `test_ac2_block_uses_full_tab_width` | FAIL | Block 628px ≤ 900px |
| `test_ac3_five_metrics_all_columns_visible` | FAIL | scrollWidth=276 > clientWidth=254 |
| `test_ac4_testids_present` | PASS | testids vorhanden |

## Ausführen

```bash
uv run pytest tests/tdd/test_issue_496_layout.py -v
```
