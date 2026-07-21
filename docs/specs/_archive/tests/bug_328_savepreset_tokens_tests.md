---
entity_id: bug_328_savepreset_tokens_tests
type: tests
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [tests, bugfix, design-system, css-tokens, font-size, hex-color, ap-007, ap-010, frontend, issue-328]
parent: bug_328_savepreset_tokens
phase: phase5_tdd_red
---

# Bug #328 — SavePresetDialog font-sizes + Hex-Farben → Tokens: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/bug_328_savepreset_tokens.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec. Die Tests lesen die
echte Datei `SavePresetDialog.svelte` (keine Mocks).

Parent-Spec: `docs/specs/modules/bug_328_savepreset_tokens.md` v1.0

## Source

- **File:** `tests/tdd/test_bug_328_savepreset_tokens.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_file_exists` | — | Zieldatei `SavePresetDialog.svelte` existiert |
| `test_ac1_only_ios_guard_font_size_remains` | AC-1 | Genau eine hardcodierte `font-size` bleibt — die iOS-Guard-Regel mit `16px` |
| `test_ac1_ios_guard_has_explanatory_comment` | AC-1 | Erklärender iOS-Zoom-Guard-Kommentar (Verweis auf iOS-Zoom / #272) vorhanden |
| `test_ac1_uses_text_size_tokens` | AC-1 | `var(--g-text-xs)` und `var(--g-text-sm)` werden verwendet |
| `test_ac2_no_inline_hex_colors` | AC-2 | Keine `color: #...`-Hex-Literale mehr |
| `test_ac2_uses_color_tokens` | AC-2 | `var(--g-danger)` und `var(--g-paper)` werden verwendet |
| `test_ios_zoom_guard_media_query_intact` | AC-3 | Regressions-Guard: `@media (max-width: 767px)` setzt `.field`-Inputs weiterhin auf `16px` (Bug #272 intakt) |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — Token-/Hex-Tests sollen FAIL sein)
uv run pytest tests/tdd/test_bug_328_savepreset_tokens.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_bug_328_savepreset_tokens.py -v
```

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartetes Ergebnis | Grund |
|------|---------------------|-------|
| `test_file_exists` | PASS | Datei existiert bereits |
| `test_ac1_only_ios_guard_font_size_remains` | FAIL | Noch 7 hardcodierte font-sizes vorhanden (statt nur 16px) |
| `test_ac1_ios_guard_has_explanatory_comment` | FAIL | iOS-Guard-Kommentar fehlt noch |
| `test_ac1_uses_text_size_tokens` | FAIL | Keine `--g-text-*`-Token-Referenzen vorhanden |
| `test_ac2_no_inline_hex_colors` | FAIL | `#dc2626` und `#fff` noch vorhanden |
| `test_ac2_uses_color_tokens` | FAIL | `--g-danger`/`--g-paper` noch nicht verwendet |
| `test_ios_zoom_guard_media_query_intact` | PASS | iOS-Guard ist bereits da — Regressions-Absicherung, muss intakt bleiben |

Die fünf Kern-Tests (AC-1/AC-2-Tokenisierung) müssen FAIL liefern — das ist der RED-Beweis.
`test_file_exists` und der iOS-Regressions-Guard sind bereits grün (sichern Bestehendes ab).

## Changelog

- 2026-05-22: Initial test manifest erstellt für Bug #328 (AP-007 Hex + AP-010 font-size in SavePresetDialog).
