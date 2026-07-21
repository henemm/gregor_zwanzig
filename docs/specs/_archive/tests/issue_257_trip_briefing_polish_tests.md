---
entity_id: issue_257_trip_briefing_polish_tests
type: tests
created: 2026-05-18
updated: 2026-05-18
status: draft
version: "1.0"
tags: [tests, email, dark-footer, pill, mobile, issue-257, epic-236]
parent: issue_257_trip_briefing_mail_polish
phase: phase5_tdd_red
---

# Issue #257 — Trip-Briefing-Mail Polish: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_257_trip_briefing_mail_polish.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_257_trip_briefing_mail_polish.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_257_trip_briefing_polish.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_footer_has_ink_background` | AC-1 | Footer-CSS enthält `background:#1a1a18` (G_INK) |
| `test_ac1_footer_text_is_white` | AC-1 | Footer-CSS enthält `color:#ffffff` |
| `test_ac1_footer_no_border_top` | AC-1 | Footer-CSS enthält kein `border-top` |
| `test_ac2_color_scheme_meta_present` | AC-2 | `<meta name="color-scheme" content="light">` im `<head>` |
| `test_ac3_pill_html_good_tone` | AC-3 | `pill_html("OK", "good")` → `#3a7d44` BG, `#ffffff` Text, `<span>`, kein `var(--)` |
| `test_ac3_pill_html_is_inline_span` | AC-3 | `pill_html`-Ergebnis hat `border-radius` und `padding` |
| `test_ac4_pill_html_tones` | AC-4 | Parametrisiert: warn→`#c8882a`, bad→`#b33a2a`, info→`#2a6cb3` |
| `test_ac4_pill_html_neutral_fallback` | AC-4 | Unbekannter Tone → `#edeae1` BG, `#1a1a18` Text |
| `test_ac5_mobile_media_query_present` | AC-5 | `@media (max-width: 480px)` im `<style>`-Block |
| `test_ac5_mobile_table_resp_rule` | AC-5 | `table.resp` und `td::before`/`td:before` im `@media`-Block |
| `test_ac6_table_has_resp_class` | AC-6 | `_render_html_table()` gibt `<table class="resp">` zurück |
| `test_ac6_table_td_has_data_label` | AC-6 | Jede `<td>` hat `data-label=...`-Attribut |
| `test_ac7_no_hardcoded_eee` | AC-7 | Gerendertes HTML enthält kein `#eee` |
| `test_ac7_no_eee_in_source` | AC-7 | Quelltext `html.py` enthält kein `#eee` |
| `test_ac8_preview_script_profile_argument` | AC-8 | `preview_email.py --profile wintersport` → Eyebrow `WINTERSPORT · PISTE`, Exit 0 |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests sollen FAIL sein)
uv run pytest tests/tdd/test_issue_257_trip_briefing_polish.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_issue_257_trip_briefing_polish.py \
             tests/tdd/test_email_design_tokens.py \
             tests/tdd/test_email_profile_pipeline.py \
             tests/tdd/test_issue_255_profil_signaturen.py \
             tests/integration/test_units_legend.py -v
```

## Erwartetes RED-Verhalten (vor Implementation)

- `test_ac1_*`: `AssertionError` — Footer hat noch `G_PAPER`-Background
- `test_ac2_*`: `AssertionError` — kein `color-scheme`-Meta im HTML
- `test_ac3_*`, `test_ac4_*`: `ImportError` — `pill_html` existiert nicht in `helpers.py`
- `test_ac5_*`, `test_ac6_*`: `AssertionError` — kein `@media`, kein `class="resp"`, kein `data-label`
- `test_ac7_*`: `AssertionError` — `#eee` noch in html.py (Zeile 283)
- `test_ac8_*`: Prozess-Fehler — `--profile`-Argument existiert nicht in preview_email.py

## Changelog

- 2026-05-18: Initial test manifest erstellt für Issue #257 (Epic #9, Sub-Issue 3).
