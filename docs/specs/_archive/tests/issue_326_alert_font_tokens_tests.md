---
entity_id: issue_326_alert_font_tokens_tests
type: tests
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [tests, bugfix, design-system, css-tokens, font-size, ap-017, ap-008, frontend, issue-326]
parent: issue_326_alert_font_tokens
phase: phase5_tdd_red
---

# Bug #326 — Alert-Karten font-sizes + Spacing → Tokens: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_326_alert_font_tokens.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_326_alert_font_tokens.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_326_alert_font_tokens.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_quiet_hours_no_hardcoded_font_size` | AC-1 | `<style>`-Block von `AlertQuietHoursCard.svelte` enthält kein `font-size` mit Zahl+Einheit mehr (Kommentarzeilen ausgenommen) |
| `test_cooldown_no_hardcoded_font_size` | AC-2 | `<style>`-Block von `AlertCooldownCard.svelte` enthält kein `font-size` mit Zahl+Einheit mehr |
| `test_quiet_hours_no_hardcoded_spacing` | AC-3 | Kein `padding`/`margin`/`gap`/`border-radius` mit Zahl+Einheit in `AlertQuietHoursCard.svelte` (min-height/width/border bleiben) |
| `test_cooldown_no_hardcoded_spacing` | AC-3 | Kein `padding`/`margin`/`gap`/`border-radius` mit Zahl+Einheit in `AlertCooldownCard.svelte` |
| `test_quiet_hours_dead_toggle_label_removed` | AC-4 | Tote, ungenutzte `.toggle-label`-Regel ist vollständig entfernt (0 Vorkommen) |
| `test_quiet_hours_uses_text_tokens` | AC-1/AC-5 | `var(--g-text-sm)` UND `var(--g-text-xs)` vorhanden — font-size wurde ersetzt, nicht gelöscht |
| `test_cooldown_uses_text_tokens` | AC-2/AC-5 | `var(--g-text-sm)` UND `var(--g-text-xs)` vorhanden — font-size wurde ersetzt, nicht gelöscht |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests sollen FAIL sein)
uv run pytest tests/tdd/test_issue_326_alert_font_tokens.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_issue_326_alert_font_tokens.py -v
```

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartetes Ergebnis | Grund |
|------|---------------------|-------|
| `test_quiet_hours_no_hardcoded_font_size` | FAIL | 3 hardcodierte `font-size` (0.875/0.8125rem) noch vorhanden |
| `test_cooldown_no_hardcoded_font_size` | FAIL | 3 hardcodierte `font-size` noch vorhanden |
| `test_quiet_hours_no_hardcoded_spacing` | FAIL | `1rem`/`0.5rem`/`0.25rem` Spacing + Radius noch vorhanden |
| `test_cooldown_no_hardcoded_spacing` | FAIL | `1rem`/`0.5rem`/`0.25rem` Spacing + Radius noch vorhanden |
| `test_quiet_hours_dead_toggle_label_removed` | FAIL | `.toggle-label`-Regel noch in Datei |
| `test_quiet_hours_uses_text_tokens` | FAIL | Noch keine `--g-text-*`-Referenz vorhanden |
| `test_cooldown_uses_text_tokens` | FAIL | Noch keine `--g-text-*`-Referenz vorhanden |

Alle sieben Tests müssen FAIL liefern — das ist der RED-Beweis.

## Changelog

- 2026-05-22: Initial test manifest erstellt für Bug #326 (AP-017 Schrift-Skala + AP-008 Spacing in Alert-Karten).
