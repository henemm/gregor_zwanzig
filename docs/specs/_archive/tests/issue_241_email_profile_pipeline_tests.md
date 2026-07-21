---
entity_id: issue_241_email_profile_pipeline_tests
type: tests
created: 2026-05-17
updated: 2026-05-17
status: draft
version: "1.0"
tags: [tests, email, activity-profile, issue-241]
parent: issue_241_email_profile_pipeline
phase: phase5_tdd_red
---

# Issue #241 — ActivityProfile durch Mail-Pipeline (Test-Manifest)

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_241_email_profile_pipeline.md`.
Jeder pytest-Test mappt 1:1 auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_241_email_profile_pipeline.md` v1.0.0

## Source

- **File:** `tests/tdd/test_email_profile_pipeline.py` (NEU)

## Test Inventory (`tests/tdd/test_email_profile_pipeline.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_signature_wintersport` | AC-1 | `profile_signature(ActivityProfile.WINTERSPORT)` liefert `accent_hex='#4a7fb5'`, `icon='❄'`, `eyebrow='Wintersport'` |
| `test_ac1_signature_wandern` | AC-1 | `profile_signature(ActivityProfile.WANDERN)` liefert `accent_hex='#3a7d44'`, `icon='🥾'`, `eyebrow='Wandern'` |
| `test_ac1_signature_summer_trekking` | AC-1 | `profile_signature(ActivityProfile.SUMMER_TREKKING)` liefert `accent_hex='#c45a2a'`, `icon='🏔'`, `eyebrow='Sommer-Trekking'` (ö + Bindestrich) |
| `test_ac1_signature_allgemein` | AC-1 | `profile_signature(ActivityProfile.ALLGEMEIN)` liefert `accent_hex='#6b675c'`, `icon='◯'`, `eyebrow='Allgemein'` |
| `test_ac2_render_html_with_profile` | AC-2 | Parametrisierter Test: für jedes der 4 Profile rendert `render_html(profile=...)` HTML mit dem korrekten `accent_hex` als Background-Inline-Style **und** mit Eyebrow-Block `{icon} {eyebrow}` |
| `test_ac3_render_email_passes_profile_through` | AC-3 | `render_email(profile=ActivityProfile.WINTERSPORT)` liefert (html, plain) — beide enthalten Wintersport-Marker (`#4a7fb5` im HTML, `❄ Wintersport` im Plain) |
| `test_ac4_format_email_passes_profile_through` | AC-4 | `TripReportFormatter().format_email(profile=ActivityProfile.SUMMER_TREKKING, ...)` liefert TripReport, dessen html_body `#c45a2a` und `Sommer-Trekking` enthält |
| `test_ac5_scheduler_passes_profile_to_formatter` | AC-5 | Source-Inspection: `src/services/trip_report_scheduler.py` ruft `format_email(..., profile=trip.aggregation.profile, ...)` auf (Substring-Check im Quelltext, kein Mock) |
| `test_ac6_header_eyebrow_before_h1` | AC-6 | Für jedes Profil: im HTML-Body steht `<div class="eyebrow"` **vor** `<h1>` im Header-Block — Reihenfolge im DOM ist eyebrow → h1 |
| `test_ac7_render_plain_prefix_line` | AC-7 | Parametrisierter Test: für jedes der 4 Profile beginnt der Plain-Body mit Prefix-Zeile `{icon} {eyebrow}` vor Trip-Namen |
| `test_ac8_render_email_without_profile_kwarg_backward_compat` | AC-8 | `render_email(...)` ohne `profile`-kwarg crasht nicht, rendert mit ALLGEMEIN-Fallback (`#6b675c`, `Allgemein`) |
| `test_ac9_preview_service_passes_profile_through` | AC-9 | Source-Inspection: `src/services/preview_service.py` reicht `profile` an `render_email` / `format_email` durch (Substring-Check im Quelltext) |
| `test_ac10_signature_none_fallback` | AC-10 | `profile_signature(None)` liefert ALLGEMEIN-Signatur ohne Exception |
| `test_ac10_signature_unknown_value_fallback` | AC-10 | `profile_signature("nicht_im_enum")` liefert ALLGEMEIN-Signatur ohne Exception |

## Test-Ausführung

```bash
# Pure-Function-Tests (default, ohne SMTP)
uv run pytest tests/tdd/test_email_profile_pipeline.py -v

# Mit Real-Gmail (deferred — wartet auf Infra-Fix MQ 20834)
uv run pytest tests/tdd/test_email_profile_pipeline.py -v -m email
```

## Erwartetes RED-Verhalten (vor Implementation)

- AC-1 + AC-10-Tests: `ModuleNotFoundError: src.output.renderers.email.profile_signature`
- AC-2-Tests: `render_html` kennt `profile`-kwarg noch nicht → `TypeError: render_html() got an unexpected keyword argument 'profile'`
- AC-3/AC-4-Tests: Aufrufer-Funktionen kennen `profile`-kwarg noch nicht → `TypeError`
- AC-5/AC-9-Tests: Source-Inspection findet `profile=trip.aggregation.profile` nicht → `AssertionError`
- AC-6 + AC-7-Tests: HTML/Plain enthält noch keinen Eyebrow-Block → `AssertionError`
- AC-8-Test: bereits grün, weil `render_email` heute ohne profile-kwarg läuft

## Erwartetes GREEN-Verhalten (nach Implementation)

Alle 13 Tests grün ohne `-m email`. AC-5-Real-Gmail bleibt deferred.

## Changelog

- 2026-05-17: Test-Manifest für #241 (Sub-Issue 3b von Epic #236)
