---
entity_id: issue_236_epic9_remaining_templates_tests
type: tests
created: 2026-05-18
updated: 2026-05-18
status: draft
version: "1.0"
tags: [tests, email, design-system, epic-236, service-error-mail, comparison-mail]
parent: issue_236_epic9_remaining_templates
phase: phase5_tdd_red
---

# Issue #236 EPIC 9 — Verbleibende Templates: Test-Manifest

## Approval

- [x] Approved

## Purpose

Test-Manifest für die verbleibenden E-Mail-Templates in EPIC 9 (Issue #236).
Mappt pytest-Funktionsnamen auf die Acceptance-Criteria der Parent-Spec
`docs/specs/modules/issue_236_epic9_remaining_templates.md`.

Zwei Bereiche:
1. **Service-Error-Mail** — `build_service_error_email_html()` (neue Hilfsfunktion)
2. **Comparison-Mail** — `render_comparison_html()` / `render_comparison_text()` Token-Migration + Profil-Parameter

## Source

- **Test-Datei:** `tests/tdd/test_issue_236_remaining_templates.py`
- **Parent-Spec:** `docs/specs/modules/issue_236_epic9_remaining_templates.md` v1.0

## Test Inventory

### Service-Error-Mail

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `ac1_service_error_mail_structure` | AC-1 | `build_service_error_email_html()` importierbar; HTML enthält G_PAPER, G_ACCENT, G_DANGER, G_INK-Footer, WEB_FONT_LINK, "Gregor Zwanzig", #ffffff |
| `ac2_service_error_mail_no_hardcoded_colors` | AC-2 | Verbotene Farben #f5f5f5, #1976d2, #42a5f5 fehlen im generierten HTML |

### Comparison-Mail

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `ac3_comparison_html_profile_eyebrow` | AC-3 | `render_comparison_html(..., profile=WANDERN)` liefert Eyebrow mit eyebrow-Text + accent_hex; ohne Profil ALLGEMEIN-Fallback |
| `ac4_comparison_html_no_material_colors` | AC-4 | Keine Material-Farben (#1976d2, #42a5f5, #4caf50, #e8f5e9, #2e7d32); G_PAPER, G_ACCENT, G_SUCCESS, WEB_FONT_LINK vorhanden |
| `ac5_comparison_text_profile_param_ignored` | AC-5 | `render_comparison_text(..., profile=WINTERSPORT)` liefert String, identisch mit ohne Profil |

### compare_subscription.py Weitergabe

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `ac6_warning_banner_tokens` | AC-6 | compare_subscription.py enthält weder #fff3cd noch #ffc107; G_BOX_WARNING_BG referenziert |
| `ac6_compare_subscription_profile_forwarding` | AC-6 | compare_subscription.py enthält `profile=` beim render_comparison_html-Aufruf |

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartung in Phase 5 (RED) | Begründung |
|---|---|---|
| `ac1_service_error_mail_structure` | FAIL (ImportError) | `build_service_error_email_html` existiert noch nicht |
| `ac2_service_error_mail_no_hardcoded_colors` | FAIL (ImportError) | `build_service_error_email_html` existiert noch nicht |
| `ac3_comparison_html_profile_eyebrow` | FAIL (TypeError) | `render_comparison_html` akzeptiert kein `profile`-Argument |
| `ac4_comparison_html_no_material_colors` | FAIL (AssertionError) | #1976d2 ist noch im CSS-Block |
| `ac5_comparison_text_profile_param_ignored` | FAIL (TypeError) | `render_comparison_text` akzeptiert kein `profile`-Argument |
| `ac6_warning_banner_tokens` | FAIL (AssertionError) | #fff3cd und #ffc107 sind noch im Code |
| `ac6_compare_subscription_profile_forwarding` | FAIL (AssertionError) | `profile=` fehlt beim Aufruf |

Alle 7 Tests müssen rot sein — das ist der RED-Beweis.

## Verification

- **Scoped Run:** `uv run pytest tests/tdd/test_issue_236_remaining_templates.py -v`
- **Phase 5 RED:** Alle 7 Tests rot.
- **Phase 6 GREEN:** Alle 7 Tests grün nach Implementierung.

## Out of Scope

- Echte E-Mail-Versandtests (werden durch bestehende Tests in `test_html_email.py` abgedeckt)
- Visueller Regressions-Check (separater Schritt nach Implementierung)

## Changelog

- 2026-05-18: Initial test manifest für EPIC 9 verbleibende Templates.
