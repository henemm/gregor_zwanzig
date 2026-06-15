---
entity_id: issue_830_radar_alert_validator_tests
type: tests
created: 2026-06-15
updated: 2026-06-15
status: draft
version: "1.0"
tags: [tests, radar, alert, validator, gate, staging, debug-endpoint, issue-830]
parent: issue_830_radar_alert_validator
phase: phase5_tdd_red
---

# Issue #830 — Radar-Alert-Mail testbar machen (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für Issue #830. Jeder pytest-Test mappt auf ein Acceptance Criterion
der Parent-Spec `docs/specs/modules/issue_830_radar_alert_validator.md`.

Mock-frei: Frame-Seam via `frame_source`-DI erlaubt (dokumentierter Seam). IMAP-Calls
gegen echtes Stalwart-Postfach. Gate-Tests gegen echtes Temp-Git-Repo.

## Source

- **File:** `tests/tdd/test_issue_830_radar_alert_validator.py` (NEU)

## Test Inventory

### Python (`tests/tdd/test_issue_830_radar_alert_validator.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_trigger_endpoint_exists_on_staging` | AC-1 | POST /api/debug/trigger-radar-alert → HTTP 200 (nicht 404) auf Staging |
| `test_ac1_trigger_response_contains_trip_info` | AC-1 | Response enthält status=sent + trip_id + segment |
| `test_ac2_validator_file_exists` | AC-2 | radar_alert_mail_validator.py ist im hooks-Verzeichnis vorhanden |
| `test_ac2_validator_loadable_as_module` | AC-2 | Validator kann als Python-Modul geladen werden, exportiert validate_message() |
| `test_ac2_validator_exit2_for_wrong_mail_type` | AC-2 | Mail mit X-GZ-Mail-Type: trip-briefing → No-Op (ok=True) |
| `test_ac2_validator_exit1_for_missing_segment_label` | AC-2 | Mail ohne Segment-Label → ok=False mit Fehlerdetail |
| `test_ac2_validator_exit0_for_valid_radar_alert_mail` | AC-2 | Vollständige Radar-Alert-Mail → ok=True |
| `test_ac3_gate_blocks_radar_alert_py_without_nachweis` | AC-3 | Gate Exit 2 wenn src/outputs/radar_alert.py gestaged, kein Nachweis |
| `test_ac3_gate_allows_commit_after_radar_nachweis` | AC-3 | Gate Exit 0 wenn Nachweis hinterlegt (skip in RED-Phase) |
| `test_bonus_radar_alert_module_exports_build_functions` | AC-1/AC-2 | src/outputs/radar_alert.py exportiert build_radar_alert_body + build_radar_alert_subject |
| `test_bonus_settings_has_env_field` | AC-4 | Settings.env == "production" als Default (GZ_ENV-Feld vorhanden) |
| `test_ac4_production_endpoint_returns_404` | AC-4 | POST /api/debug/trigger-radar-alert auf gregor20.henemm.com → 404 |
