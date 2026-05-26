---
entity_id: issue_377_contrast_audit_tests
type: tests
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [tests, frontend, design-system, wcag, accessibility, tokens, issue-377]
parent: issue_377_contrast_audit
phase: phase5_tdd_red
---

# Issue #377 — Contrast-Audit der Ink-Skala: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_377_contrast_audit.md`.
Jeder Test mappt auf ein Acceptance Criterion der Parent-Spec. Keine Mocks —
Python-Tests rechnen echte WCAG-Kontraste, node:test-Tests lesen die echten
`.svelte`/`.css`-Quelldateien (Pattern wie `tokens-bridge.test.ts`).

Parent-Spec: `docs/specs/modules/issue_377_contrast_audit.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_377_contrast_audit.py` (NEU) — Mess-Script-Tests
- **File:** `frontend/src/lib/contrast-audit.test.ts` (NEU) — Source-Inspection-Tests (node:test)

## Test Inventory (Python — `scripts/contrast_audit.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_contrast_ratio_black_on_white` | AC-1 | schwarz auf weiß = 21.0:1 (±0.05), Referenzwert |
| `test_contrast_ratio_white_on_white` | AC-1 | weiß auf weiß = 1.0:1 (kein Kontrast) |
| `test_ink_faint_fails_on_card` | AC-2 | `--g-ink-faint #9c9a90` auf `#ffffff` < 3.0:1 (FAIL) |
| `test_ink_4_fails_on_card` | AC-2 | `--g-ink-4 #9a958a` auf `#ffffff` < 3.0:1 (FAIL) |
| `test_ink_muted_passes_on_card` | AC-3 | `--g-ink-muted #5c5a52` auf `#ffffff` >= 4.5:1 (AA) |
| `test_accent_fails_body_text` | AC-2 | `--g-accent #c45a2a` auf `#ffffff` < 4.5:1 (nur AA-large) |
| `test_accent_deep_passes` | AC-3 | `--g-accent-deep #8c3e1a` auf `#ffffff` >= 4.5:1 (AAA) |
| `test_classify_thresholds` | AC-1 | `classify()` ordnet Ratios den WCAG-Klassen korrekt zu |

## Test Inventory (node:test — Source-Inspection `frontend/src/`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `no --g-ink-faint as color anywhere` | AC-6/AC-9 | kein `color: var(--g-ink-faint)` in `.svelte`/`.css` |
| `no --g-ink-4 as color anywhere` | AC-6/AC-9 | kein `color: var(--g-ink-4)` in `.svelte`/`.css` |
| `no naked --g-accent body text in fix files` | AC-7 | TablePreview/TripHeader/ActiveMetricRow: `color: var(--g-accent)` nur mit Underline/Bold |
| `contrast-section exists in _design route` | AC-8 | `_design/+page.svelte` enthält `data-testid="contrast-section"` |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests sollen FAIL sein)
uv run pytest tests/tdd/test_issue_377_contrast_audit.py -v
cd frontend && node --experimental-strip-types --test src/lib/contrast-audit.test.ts

# GREEN-Phase (nach Implementation — alle grün)
uv run pytest tests/tdd/test_issue_377_contrast_audit.py -v
cd frontend && node --experimental-strip-types --test src/lib/contrast-audit.test.ts
```

## Changelog

- 2026-05-25: Initial test manifest erstellt für Issue #377 (Contrast-Audit Ink-Skala).
