---
entity_id: issue_833_gate_tests
type: tests
created: 2026-06-22
updated: 2026-06-22
status: approved
version: "1.0"
tags: [tests, mail, qa-gate, playwright, hooks, issue-833]
parent: issue_833_mail_gate_structural
phase: phase5_tdd_red
---

# Issue #833 — Mail-Acceptance-Gate Härtung: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_833_mail_gate_structural.md`.
Jeder Test mappt auf ein Acceptance Criterion. Mock-frei: echte konstruierte
MIME-/HTML-Artefakte mit den realen Renderer-Markern, echtes Gate-Verhalten.

Parent-Spec: `docs/specs/modules/issue_833_mail_gate_structural.md`

## Source

- **File:** `tests/tdd/test_issue_833_gate.py` (NEU) — AC-1, AC-3, AC-4, AC-5, AC-6.
- **File:** `tests/tdd/test_issue_811_mode_matrix.py` (ERWEITERT) — AC-2, Mobile-Viewport.

## Test Inventory — test_issue_811_mode_matrix.py (module-level Funktionen)

| Test-Funktion | AC | Phase | Was geprüft wird |
|---|---|---|---|
| `mobile_block_data_cells_roh` | AC-2 | RED→GREEN | Roh+full → `.mobile-compact`-Block liefert Datenzellen ohne Ampel (über `_data_cells_mobile()`) |
| `mobile_block_data_cells_einfach` | AC-2 | RED→GREEN | Einfach+full → `.mobile-compact`-Block zeigt Ampel/Symbole mobil (#831-Regressionsschutz) |

## Test Inventory — test_issue_833_gate.py (Klassenmethoden)

| Test-Methode | AC | Phase | Was geprüft wird |
|---|---|---|---|
| `TestAC5Localization::test_english_header_gust_rain_sun_detected` | AC-5 | RED | EN-Spaltenköpfe Gust/Rain/Sun → `_check_localization()` meldet rot |
| `TestAC5Localization::test_homograph_wind_not_flagged` | AC-5 | RED-Anker | Homograph „Wind" (DE=EN) wird NICHT gemeldet |
| `TestAC3LayerConsistency::test_pill_peak_contradicts_table_max` | AC-3 | RED | Pill-Spitze 84 ≠ Tabellen-Max 30 → `_check_layer_consistency()` rot (#807-Klasse) |
| `TestAC3LayerConsistency::test_pill_peak_within_tolerance_passes` | AC-3 | RED-Anker | Übereinstimmende Spitzen → kein Fehler |
| `TestAC4MetricPlausibility::test_sonne_pill_contradicts_zero_sun_table` | AC-4 | RED | „Sonne 120 min" bei 0 h Tabelle → `_check_metric_plausibility()` rot (#808-Klasse) |
| `TestAC4MetricPlausibility::test_kein_regen_pill_contradicts_rain_table` | AC-4 | RED | „kein Regen" bei 0.5 mm Tabellensumme → rot |
| `TestAC4MetricPlausibility::test_sonne_pill_matches_table_passes` | AC-4 | RED-Anker | Übereinstimmende Sonne-Angabe → kein Fehler |
| `TestAC1RenderViewport::test_missing_mobile_block_rejected` | AC-1 | RED | full-Mail ohne `.mobile-compact` → `validate_message()` rot (Render-Check) |
| `TestAC6GateSelfVerification::test_deliberately_broken_mail_is_rejected` | AC-6 | RED | Vier konstruierte defekte Mails → `validate_message()` liefert je Exit-1 |

## Verhaltensnachweis (kein Dateiinhalt-Check)

- AC-3/AC-4/AC-5 prüfen das Rückgabeverhalten neuer Check-Funktionen an konstruierten
  HTML-Artefakten mit echten Renderer-Markern (`<table class="resp">`, `data-label`,
  Pill-`<span>`, `<th>`).
- AC-1/AC-6 prüfen das öffentliche `validate_message()`-Urteil über echt serialisierte
  und reparste MIME-Nachrichten (Wire-Format).
- AC-2 prüft den Roh/Einfach-Vertrag über die ECHT gerenderte Mail (`render_email`) im
  Mobile-Block — beide Auflösungen, kein Mock.

## Changelog

- 2026-06-22: Initial Test-Manifest — Issue #833.
