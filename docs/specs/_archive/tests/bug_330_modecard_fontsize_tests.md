---
entity_id: bug_330_modecard_fontsize_tests
type: tests
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [tests, bugfix, design-system, css-tokens, font-size, ap-017, frontend, issue-330]
parent: bug_330_modecard_fontsize
phase: phase5_tdd_red
---

# Bug #330 — ModeCard font-sizes → --g-text-* Tokens: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/bug_330_modecard_fontsize.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/bug_330_modecard_fontsize.md` v1.0

## Source

- **File:** `tests/tdd/test_bug_330_modecard_fontsize.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_no_hardcoded_font_sizes` | AC-1 | `<style>`-Block von `ModeCard.svelte` enthält kein numerisches `font-size: [0-9]`-Literal mehr (Kommentarzeilen ausgenommen) |
| `test_font_sizes_use_correct_tokens` | AC-2 | Genau 5 `font-size: var(--g-text-*)`-Referenzen mit Verteilung `--g-text-xs`×3, `--g-text-sm`×1, `--g-text-md`×1 |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests sollen FAIL sein)
uv run pytest tests/tdd/test_bug_330_modecard_fontsize.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_bug_330_modecard_fontsize.py -v
```

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartetes Ergebnis | Grund |
|------|---------------------|-------|
| `test_no_hardcoded_font_sizes` | FAIL | 5 hardcodierte `font-size`-Werte noch vorhanden |
| `test_font_sizes_use_correct_tokens` | FAIL | 0 statt 5 `--g-text-*`-Token-Referenzen vorhanden |

Beide Tests müssen FAIL liefern — das ist der RED-Beweis.

## Changelog

- 2026-05-22: Initial test manifest erstellt für Bug #330 (AP-017 Schrift-Skala-Drift in ModeCard).
