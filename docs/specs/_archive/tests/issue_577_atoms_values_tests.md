---
entity_id: issue_577_atoms_values_tests
type: tests
created: 2026-06-05
status: draft
version: "1.0"
tags: [tests, design-fidelity, issue-577, epic-575, foundation]
parent: issue_577_atoms_sync_v2
phase: phase5_tdd_red
---

# Issue #577 — Atom-Werte computed-style-Tests (Playwright)

## Approval

- [x] Approved

## Purpose

Verhaltensbasierte Tests der 10 driftenden Atom-Werte. Injiziert auf einer
authentifizierten Staging-Seite Atom-DOM-Elemente (Btn / Pill / Card mit den
zugehörigen `data-slot`/`data-size`/`data-variant`-Attributen), liest den
computed style und prüft gegen JSX-Vorgaben. Token-Vergleich für Eyebrow als
Bonus-AC.

Parent-Spec: `docs/specs/modules/issue_577_atoms_sync_v2.md`.

## Source

- **File:** `tests/tdd/test_issue_577_atoms_values.py`

## Test → AC Mapping

| Test-Funktion-Entity | AC | Was wird geprüft |
|---|---|---|
| `issue_577_btn_border_radius_4px` | AC-1 | `[data-slot="btn"]` → `border-radius` = `4px` |
| `issue_577_btn_md_padding_9_14` | AC-2 | `[data-slot="btn"][data-size="md"]` → `padding-top` und `padding-bottom` = `9px` |
| `issue_577_btn_lg_padding_and_fs` | AC-3 | `[data-slot="btn"][data-size="lg"]` → padding `12px 20px`, font-size `14px` |
| `issue_577_btn_sm_fs_12px` | AC-4 | `[data-slot="btn"][data-size="sm"]` → `font-size` = `12px` |
| `issue_577_btn_accent_color_white` | AC-5 | `[data-slot="btn"][data-variant="accent"]` → `color` = `rgb(255, 255, 255)` |
| `issue_577_pill_padding_3_9` | AC-6 | `[data-slot="pill"]` → `padding-top`/`-bottom` = `3px`, `padding-left`/`-right` = `9px` |
| `issue_577_gcard_border_radius_6px` | AC-7 | `[data-slot="g-card"]` → `border-radius` = `6px` |
| `issue_577_gcard_padding_20px` | AC-8 | `[data-slot="g-card"]` → `padding` = `20px` |
| `issue_577_gcard_border_1px` | AC-9 | `[data-slot="g-card"]` → `border-width` = `1px`, `border-style` = `solid` |
| `issue_577_eyebrow_color_same_as_ink_3` | AC-10 | `[data-slot="eyebrow"]` computed `color` = `rgb(107, 103, 92)` (JSX `--g-ink-3` = #6b675c) |

## Test-Strategie

- Echter Browser via Playwright (Chromium headless).
- Login mit Validator-Credentials auf Staging.
- Navigate auf `/archiv` (lädt `app.css`).
- Pro Test: dynamisch DOM-Element mit Atom-Selectors injizieren, computed style lesen.
- Keine Mocks, keine Dateiinhalt-Checks.

## TDD-RED-Erwartung

Aktueller Staging-Stand (HEAD nach #576) hat:
- Btn: border-radius 8 px (statt 4), md padY 8 (statt 9), lg padding 10/18 (statt 12/20), sm/lg fs 13/15 (statt 12/14), accent color #f6f4ee (statt #fff)
- Pill: padding 2 px 8 px (statt 3 px 9 px)
- g-card: border-radius 12 px (statt 6), padding 16 px (statt 20), kein expliziter Border (statt 1 px solid)

10/10 Tests schlagen fehl bis `frontend/src/app.css` die JSX-Werte setzt.
