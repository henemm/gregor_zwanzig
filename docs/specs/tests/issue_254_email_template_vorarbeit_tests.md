---
entity_id: issue_254_email_template_vorarbeit_tests
type: tests
created: 2026-05-17
updated: 2026-05-17
status: draft
version: "1.0"
tags: [tests, email, design-system, issue-254, epic9]
parent: issue_254_email_template_vorarbeit
phase: phase5_tdd_red
---

# Issue #254 — Email-Template Vorarbeit (Test-Manifest)

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_254_email_template_vorarbeit.md`. Jeder
pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_254_email_template_vorarbeit.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_254_email_template_vorarbeit.py` (NEU)

## Test Inventory (`tests/tdd/test_issue_254_email_template_vorarbeit.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_design_system_md_has_mail_tokens_section` | AC-1 | `design_system.md` enthält §12-Abschnitt |
| `test_ac1_design_system_md_names_app_css_as_source` | AC-1 | §12 benennt `app.css` als verbindliche Mail-Token-Quelle |
| `test_ac1_design_system_md_lists_naming_deviations` | AC-1 | §12 listet `--g-success/danger`, `--g-ink-muted/faint` als Mapping |
| `test_ac1_design_system_md_references_thunder_bug` | AC-1 | §12 verweist auf `--g-weather-thunder`-Farbkonflikt |
| `test_ac1_tokens_css_comment_references_decision` | AC-1 | `design_system_tokens.css` Header verweist auf §12 oder Entscheidung |
| `test_ac2_inventory_dark_footer_assessed` | AC-2 | Dunkel-Footer (`#1a1a18`) als FEHLT bewertet in §12 |
| `test_ac2_inventory_daylight_svg_assessed` | AC-2 | Daylight-Bar (SVG) als FEHLT bewertet in §12 |
| `test_ac2_inventory_tag_system_assessed` | AC-2 | Tag-System ok/warn/risk/info bewertet in §12 |
| `test_ac2_inventory_all_six_components_present` | AC-2 | ActivityProfile, Inline-CSS, Fonts in §12 dokumentiert |
| `test_ac3_preview_script_exists` | AC-3 | `scripts/preview_email.py` existiert |
| `test_ac3_preview_script_runs_without_error` | AC-3 | Script läuft mit Exit 0, erzeugt HTML-Datei |
| `test_ac3_preview_output_is_valid_html` | AC-3 | Output enthält `<!DOCTYPE html>` und `<table` |
| `test_ac3_preview_script_no_network_calls` | AC-3 | Keine Netzwerk-Bibliotheken im Script importiert |

## Changelog

- 2026-05-17: Initial test manifest created (Issue #254)
