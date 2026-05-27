---
entity_id: epic_404_phase2_ist_screenshots_tests
type: tests
created: 2026-05-27
updated: 2026-05-27
status: active
version: "1.0"
tags: [tests, playwright, screenshots, audit, staging, epic-404]
parent: epic_404_phase2_ist_screenshots
phase: phase5_tdd_red
---

# Epic #404 Phase 2 — IST-Screenshots: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/epic_404_phase2_ist_screenshots.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/epic_404_phase2_ist_screenshots.md` v1.0

## Source

- **File:** `tests/tdd/test_epic_404_phase2_ist_screenshots.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `soll_screenshots_vorhanden` | Voraussetzung | SOLL-Verzeichnis + mind. 20 PNGs vorhanden |
| `soll_naming_deckt_expected_desktop_ab` | Voraussetzung | Alle geplanten Desktop-IST-Namen haben SOLL-Pendant |
| `soll_naming_deckt_expected_mobile_ab` | Voraussetzung | Alle geplanten Mobile-IST-Namen haben SOLL-Pendant |
| `gpx_fixture_vorhanden` | Voraussetzung | `frontend/e2e/fixtures/test-trip.gpx` existiert |
| `env_playwright_vorhanden` | Voraussetzung | `.env.playwright` mit E2E_USER/E2E_PASS vorhanden |
| `script_existiert` | AC-1 | Script-Datei am erwarteten Pfad vorhanden |
| `script_definiert_staging_url` | AC-2 | BASE_URL zeigt auf Staging |
| `script_definiert_trip_id` | AC-3 | TRIP_ID = 'e2e-cockpit-test' enthalten |
| `script_definiert_login_funktion` | AC-2 | login() mit waitForURL definiert |
| `script_definiert_seed_trip_funktion` | AC-3 | seedTrip() definiert |
| `script_definiert_wizard_steps_funktion` | AC-6 | wizardSteps() mit setInputFiles definiert |
| `script_enthaelt_gpx_upload_referenz` | AC-6 | test-trip.gpx referenziert |
| `script_referenziert_alle_desktop_screenshots` | AC-4 | Alle 15 desktop-*.png Namen im Script |
| `script_referenziert_alle_mobile_screenshots` | AC-5 | Alle 11 mobile-m-*.png Namen im Script |
| `script_verwendet_desktop_viewport` | AC-4 | 1440 px Desktop-Viewport definiert |
| `script_verwendet_mobile_viewport` | AC-5 | 390 px Mobile-Viewport definiert |
| `script_enthaelt_zusammenfassung` | AC-7 | Abschluss-Zusammenfassung mit "fertig" |
| `script_setzt_exit_code_bei_fehler` | AC-7 | process.exit(1) bei Fehlern |
| `ist_screenshots_count_gesamt` | AC-4+AC-5 | Gesamtzahl 26 = 15 Desktop + 11 Mobile |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation -- alle Script-Tests sollen FAIL sein)
uv run pytest tests/tdd/test_epic_404_phase2_ist_screenshots.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_epic_404_phase2_ist_screenshots.py -v
```

## Changelog

- 2026-05-27: Initial test manifest erstellt für Epic #404 Phase 2 (IST-Screenshots).
