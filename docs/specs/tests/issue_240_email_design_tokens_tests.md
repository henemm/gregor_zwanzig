---
entity_id: issue_240_email_design_tokens_tests
type: tests
created: 2026-05-16
updated: 2026-05-16
status: draft
version: "1.0"
tags: [tests, email, design-system, issue-240]
parent: issue_240_email_design_tokens
phase: phase5_tdd_red
---

# Issue #240 — Trip-Briefing-Mail auf Design-Tokens (Test-Manifest)

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_240_email_design_tokens.md`. Jeder
pytest-Test mappt 1:1 auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_240_email_design_tokens.md` v1.0

## Source

- **File:** `tests/tdd/test_email_design_tokens.py` (NEU)

## Test Inventory (`tests/tdd/test_email_design_tokens.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_design_tokens_surfaces` | AC-1 | `G_PAPER='#f6f4ee'`, `G_SURFACE_1='#edeae1'`, `G_SURFACE_2='#e3dfd4'` exportiert |
| `test_ac1_design_tokens_ink` | AC-1 | `G_INK='#1a1a18'`, `G_INK_MUTED='#5c5a52'`, `G_INK_FAINT='#9c9a90'` exportiert |
| `test_ac1_design_tokens_brand_semantic` | AC-1 | `G_ACCENT='#c45a2a'`, `G_SUCCESS='#3a7d44'`, `G_WARNING='#c8882a'`, `G_DANGER='#b33a2a'`, `G_INFO='#2a6cb3'` exportiert |
| `test_ac1_design_tokens_box_tints` | AC-1 | Mail-only Box-Tints `G_BOX_WARNING_BG`, `G_BOX_DANGER_BG`, `G_BOX_INFO_BG` exportiert (helle Hex-Werte, kein Alpha) |
| `test_ac1_design_tokens_fonts` | AC-1, AC-4 | `FONT_UI` enthält 'Inter Tight' + Fallback-Stack, `FONT_DATA` enthält 'JetBrains Mono' + monospace-Fallback, `WEB_FONT_LINK` enthält `fonts.googleapis.com` mit Inter+Tight + JetBrains+Mono |
| `test_ac2_no_old_hex_in_html_source` | AC-2 | Parameterisierter Test: 12 alte Hex-Literale (`#1976d2`, `#42a5f5`, `#fffde7`, `#f9a825`, `#fff3e0`, `#e65100`, `#f0f7ff`, `#fff8e1`, `#fbc02d`, `#f5f5f5`, `#e3f2fd`, `#90caf9`) sind aus `src/output/renderers/email/html.py` entfernt |
| `test_ac3_render_html_contains_accent` | AC-3 | Gerenderter HTML-Body enthält `#c45a2a` mindestens 2x (Header + h3-Border) |
| `test_ac3_render_html_paper_background` | AC-3 | `#f6f4ee` im HTML, `#f5f5f5` nicht mehr |
| `test_ac3_render_html_no_old_gradient` | AC-3 | Weder `#1976d2` noch `#42a5f5` im gerenderten HTML |
| `test_ac4_render_html_inter_tight` | AC-4 | 'Inter Tight' im HTML-`<style>`-Block |
| `test_ac4_render_html_jetbrains_mono` | AC-4 | 'JetBrains Mono' im HTML (für `.metric-value`/`code`) |
| `test_ac4_render_html_web_font_link` | AC-4 | `fonts.googleapis.com` + `Inter+Tight` im `<head>` |
| `test_ac5_real_gmail_briefing_tokens` | AC-5 | `@pytest.mark.email` — Real-Gmail-Versand, IMAP-Abruf, Body-Asserts: `#c45a2a` + 'Inter Tight' vorhanden, `#1976d2` nicht; default deselected |

## Test-Ausführung

```bash
# Pure-Function-Tests (default, ohne SMTP)
uv run pytest tests/tdd/test_email_design_tokens.py -v

# Mit Real-Gmail-Test (langsam, braucht Google-SMTP-Credentials)
uv run pytest tests/tdd/test_email_design_tokens.py -v -m email
```

## Erwartetes RED-Verhalten (vor Implementation)

- AC-1-Tests: `ModuleNotFoundError: src.output.renderers.email.design_tokens`
- AC-2-Tests: alte Hex-Werte sind noch in `html.py` → Assertion-Fail
- AC-3/AC-4-Tests: gerenderte Mail enthält noch alte Tokens → Assertion-Fail
- AC-5-Test: deselected (`-m email` nicht gesetzt)

## Erwartetes GREEN-Verhalten (nach Implementation)

Alle 12 non-email-Tests grün. AC-5 grün wenn mit `-m email` und gültigen
Google-SMTP-Credentials gestartet.

## Changelog

- 2026-05-16: Test-Manifest für #240 (Sub-Issue 3a von Epic #236)
