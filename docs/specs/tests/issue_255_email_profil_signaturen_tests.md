---
entity_id: issue_255_email_profil_signaturen_tests
type: tests
created: 2026-05-18
updated: 2026-05-18
status: draft
version: "1.0"
tags: [tests, email, activity-profile, issue-255, epic-236]
parent: issue_255_email_profil_signaturen
phase: phase5_tdd_red
---

# Issue #255 — Profil-Signaturen: CAPS-Eyebrows, SVG-Icons, Paper-Header (Test-Manifest)

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_255_email_profil_signaturen.md`.
Jeder pytest-Test mappt 1:1 auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_255_email_profil_signaturen.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_255_profil_signaturen.py` (NEU)

## Test Inventory (`tests/tdd/test_issue_255_profil_signaturen.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_255_icon_html_is_valid_svg` | AC-1 | `ProfileSignature` hat `icon_html`-Feld mit validem inline SVG — beginnt mit `<svg`, endet mit `</svg>`, enthält `xmlns` und Profil-Akzentfarbe |
| `test_ac1_255_eyebrow_caps_format` | AC-1 | Eyebrow-Texte im neuen CAPS-Format: `WINTERSPORT · PISTE`, `WANDERN`, `ALPINE TOUR`, `WETTER-BRIEFING` |
| `test_ac2_255_summer_trekking_vs_allgemein_distinguishable` | AC-2 | `SUMMER_TREKKING.icon_html != ALLGEMEIN.icon_html` und unterschiedliche Fill-Farben (`#c45a2a` vs `#6b675c`) |
| `test_ac3_255_render_html_paper_header_and_accent_eyebrow` | AC-3 | `render_html(profile=WINTERSPORT)` enthält `#f6f4ee` im Header, `#c45a2a` im Eyebrow, und `<svg`-Tag |
| `test_ac4_255_accent_not_as_header_background` | AC-4 | `render_html(profile=ALLGEMEIN)` — `#6b675c` erscheint nicht als `background` des Header-Divs |
| `test_ac5_255_render_plain_uses_emoji_not_svg` | AC-5 | `render_plain(profile=WANDERN)` enthält kein `<svg>`, aber `WANDERN` (CAPS) und Emoji `🥾` |
| `test_ac6_255_fallback_none_returns_wetter_briefing` | AC-6 | `profile_signature(None)` liefert `eyebrow='WETTER-BRIEFING'` und valides SVG in `icon_html` |

## Test-Ausführung

```bash
# Neue RED-Tests (sollen alle FAIL sein vor Implementation)
uv run pytest tests/tdd/test_issue_255_profil_signaturen.py -v

# Nach Implementation: beide Test-Suites grün
uv run pytest tests/tdd/test_issue_255_profil_signaturen.py tests/tdd/test_email_profile_pipeline.py -v
```

## Erwartetes RED-Verhalten (vor Implementation)

Alle Tests in `test_issue_255_profil_signaturen.py` schlagen fehl, weil:
- `ProfileSignature` hat noch kein `icon_html`-Feld → `AttributeError`
- `eyebrow`-Werte sind noch alt (`Wintersport` statt `WINTERSPORT · PISTE`) → `AssertionError`
- `html.py` setzt Header-BG noch auf `sig.accent_hex`, nicht `G_PAPER` → `AssertionError`

## Changelog

- 2026-05-18: Initial test manifest für Issue #255
