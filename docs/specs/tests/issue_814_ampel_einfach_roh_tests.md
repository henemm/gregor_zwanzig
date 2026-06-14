---
entity_id: issue_814_ampel_einfach_roh_tests
type: tests
created: 2026-06-14
updated: 2026-06-14
status: approved
version: "1.0"
tags: [tests, email, renderer, ampel, format-mode, briefing, frontend, issue-814]
parent: issue_814_ampel_einfach_roh
phase: phase5_tdd_red
---

# Issue #814 — Ampel Einfach/Roh vollständiger Vertrag: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_814_ampel_einfach_roh.md` v2.0.
Jeder pytest-/vitest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_814_ampel_einfach_roh.md` v2.0

## Source

- **File:** `tests/tdd/test_issue_811_mode_matrix.py` (ERWEITERT) — metrik-spezifische Prüfungen, AC-10 (_XFAIL_810 entfernt)
- **File:** `tests/tdd/test_issue_759_email_ampel.py` (ANGEGLICHEN) — neue Quelle use_friendly_format
- **File:** `frontend/src/lib/components/trip-detail/metricsEditor.test.ts` (ERWEITERT) — AC-11/AC-12

## Test Inventory — test_issue_811_mode_matrix.py

| Test-Funktion | AC | Phase | Was geprüft wird |
|---|---|---|---|
| `raw_full_html_metric_no_ampel` | AC-2 | GREEN-Sicherung | Roh+full → einzelne Metrik-Zelle ist KEINE Ampel (wind/gust/precip/pop) |
| `plain_numeric_in_both_modes` | AC-3 | GREEN-Sicherung | Plain numerisch in beiden Modi für die vier Metriken |
| `einfach_full_html_metric_has_ampel` | AC-1 | RED | Einfach+full → Metrik-Zelle ist Ampel-Emoji (heute: Zahl, Bug) |
| `cape_plain_einfach_is_number_not_emoji` | AC-4 | RED | CAPE Plain-Einfach = Zahl, kein Emoji (heute: Emoji im Plain) |
| `cape_roh_html_no_yellow_span` | AC-4 | RED | CAPE Roh-HTML = nackte Zahl ohne Gelb-Span (heute: Span vorhanden) |
| `cape_einfach_html_has_ampel` | AC-4 | GREEN-Sicherung | CAPE Einfach-HTML zeigt Ampel-Emoji (cape_jkg=1500 >= yellow=1000) |
| `visibility_numeric_km_no_english_word` | AC-5 | RED | Sicht = km-Zahl, kein englisches Wort good/fair/poor/fog |
| `visibility_roh_html_no_inline_style` | AC-5/AC-8 | RED | Sicht Roh-HTML hat keinen Orange-Highlight-Span |
| `thunder_einfach_med_has_lightning_symbol` | AC-6 | GREEN-Sicherung | Gewitter Einfach MED zeigt Blitz-Symbol |
| `thunder_einfach_high_has_double_lightning` | AC-6 | GREEN-Sicherung | Gewitter Einfach HIGH zeigt doppeltes Blitzsymbol |
| `thunder_roh_med_german_word_no_lightning` | AC-6 | RED | Gewitter Roh MED = deutsches Wort ohne Blitzsymbol (heute: Blitz-Symbol) |
| `thunder_roh_high_german_word_no_lightning` | AC-6 | RED | Gewitter Roh HIGH = deutsches Wort ohne Blitzsymbol (heute: doppeltes Blitzsymbol) |
| `thunder_roh_none_german_word_kein` | AC-6 | GREEN | Gewitter Roh NONE = 'kein' (Adversary F001); Einfach NONE bleibt '–' |
| `raw_full_html_no_inline_style_any_metric` | AC-8 | RED | Roh-HTML hat KEIN inline background:/color:-Style |
| `compact_ascii_no_emoji_no_hourly_table` | AC-1 | GREEN-Sicherung | compact bleibt ASCII, kein Emoji, keine Stundentabelle |

## Test Inventory — test_issue_759_email_ampel.py

| Test-Funktion | AC | Phase | Was geprüft wird |
|---|---|---|---|
| `issue759_wind_ampel_roh_is_number` | AC-10 | RED | Wind Roh (use_friendly=False) = Zahl, kein Ampel-Emoji |
| `issue759_wind_ampel_einfach_html_is_emoji` | AC-10 | RED | Wind Einfach (use_friendly=True) HTML = Ampel-Emoji |

## Test Inventory — metricsEditor.test.ts (Frontend)

| Test-Funktion | AC | Phase | Was geprüft wird |
|---|---|---|---|
| `indicator_capable_visibility_is_false` | AC-11 | RED | indicatorCapable('visibility') === false (heute: true) |
| `indicator_capable_precipitation_is_true` | AC-12 | RED | indicatorCapable('precipitation') === true (heute: false) |

## Test-Ausführung

```bash
# Backend RED-Phase
uv run pytest tests/tdd/test_issue_811_mode_matrix.py \
             tests/tdd/test_issue_759_email_ampel.py -v

# Frontend RED-Phase
cd frontend && npx vitest run src/lib/components/trip-detail/metricsEditor.test.ts
```

## Changelog

- 2026-06-14: Initial test manifest für Issue #814 RED-Phase erstellt.
