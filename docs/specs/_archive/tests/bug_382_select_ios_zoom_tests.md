---
entity_id: bug_382_select_ios_zoom_tests
type: tests
created: 2026-05-25
updated: 2026-05-26
status: done
version: "1.0"
tags: [tests, bugfix, ios, safari, mobile, font-size, zoom, frontend, issue-382]
parent: bug_382_select_ios_zoom
phase: phase5_tdd_red
---

# Bug #382 — Select.svelte iOS-Auto-Zoom: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/bug_382_select_ios_zoom.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/bug_382_select_ios_zoom.md` v1.0

## Source

- **File:** `tests/tdd/test_bug_382_select_ios_zoom.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_select_svelte_exists` | Struktur | `Select.svelte` existiert im Repo |
| `test_ac3_select_svelte_has_mobile_media_query` | AC-3 | `Select.svelte` enthält `@media (max-width: 767px)` |
| `test_ac3_select_svelte_mobile_query_sets_font_size_16px` | AC-3 | `@media (max-width: 767px) { .gz-select select { font-size: 16px } }` in `Select.svelte` |
| `test_ac2_base_font_size_preserved` | AC-2 | `font-size: var(--g-text-sm)` (Desktop) bleibt in der Basisregel erhalten |
| `test_ac1_mobile_override_comes_after_base_rule` | AC-1 | `@media`-Block steht nach der Basisregel im Quelltext (gleiche Spezifität → Reihenfolge entscheidet) |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — ac3/ac1 müssen FAIL sein)
uv run pytest tests/tdd/test_bug_382_select_ios_zoom.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_bug_382_select_ios_zoom.py -v
```

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartetes Ergebnis | Grund |
|------|---------------------|-------|
| `test_select_svelte_exists` | PASS | Datei existiert bereits |
| `test_ac3_select_svelte_has_mobile_media_query` | FAIL | Kein `@media`-Block in `Select.svelte` |
| `test_ac3_select_svelte_mobile_query_sets_font_size_16px` | FAIL | Kein scoped Override vorhanden |
| `test_ac2_base_font_size_preserved` | PASS | Basisregel mit `--g-text-sm` existiert bereits |
| `test_ac1_mobile_override_comes_after_base_rule` | FAIL | `@media`-Block fehlt → `media_pos == -1` |

Mindestens 3 von 5 Tests müssen FAIL liefern — das ist der RED-Beweis.

## Changelog

- 2026-05-25: Initial test manifest erstellt für Bug #382 (Select.svelte iOS-Zoom-Regression).
