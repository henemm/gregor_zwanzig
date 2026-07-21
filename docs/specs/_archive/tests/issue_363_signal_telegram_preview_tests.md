---
entity_id: issue_363_signal_telegram_preview_tests
type: tests
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [tests, output, preview, signal, telegram, issue-363, epic-331]
parent: issue_363_signal_telegram_preview
phase: phase5_tdd_red
---

# Issue #363 — Signal/Telegram-Vorschau-Endpoints (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für die Signal/Telegram-Vorschau aus
`docs/specs/modules/issue_363_signal_telegram_preview.md`. Jeder pytest-Test
mappt auf ein Acceptance Criterion (AC-1..AC-4 + Service-Ebene). AC-5 (Go-Proxy)
und AC-6 (`buildPreviewUrl`) werden in dieser RED-Phase NICHT getestet — der
Go-`PreviewProxyHandler` ist bereits channel-parametrisiert und `buildPreviewUrl`
ist eine reine Typ-Erweiterung; beide würden vorab grün testen und gehören in
die GREEN-Phase.

Parent-Spec: `docs/specs/modules/issue_363_signal_telegram_preview.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_363_signal_telegram_preview.py` (NEU — RED-Phase-
  Tests für die noch nicht existierenden Python-Endpoints
  `GET /api/preview/{trip}/signal|telegram` und die Service-Methoden
  `render_signal_preview()`/`render_telegram_preview()`).

## Test Inventory

### Python (`tests/tdd/test_issue_363_signal_telegram_preview.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_signal_endpoint_body_equals_signal_text_and_narrow` | AC-1 | `GET /signal?type=morning` → 200 (oder 503): JSON `body == report.signal_text`, jede Body-Zeile ≤26 Zeichen, `char_count`/`max_line_width` plausibel. |
| `test_ac2_telegram_endpoint_body_equals_telegram_text` | AC-2 | `GET /telegram?type=evening` → 200 (oder 503): JSON `body == report.telegram_text`, nicht leer. |
| `test_ac3_signal_body_differs_from_sms_and_email` | AC-3 | Für denselben Trip: Signal-`body` ≠ sms-`token_line` ≠ email-HTML (eigenständiges Kanal-Rendering). |
| `test_ac4_signal_invalid_type_returns_422` | AC-4 | Ungültiger `type` am signal-Endpoint → 422 (wie email/sms). |
| `test_ac4_telegram_invalid_type_returns_422` | AC-4 | Ungültiger `type` am telegram-Endpoint → 422. |
| `test_ac4_signal_unknown_trip_returns_404` | AC-4 | Unbekannte `trip_id` am signal-Endpoint → 404. |
| `test_ac4_telegram_unknown_trip_returns_404` | AC-4 | Unbekannte `trip_id` am telegram-Endpoint → 404. |
| `test_service_has_render_signal_preview` | Service | `PreviewService.render_signal_preview` existiert (RED: AttributeError, fehlt noch). |
| `test_service_has_render_telegram_preview` | Service | `PreviewService.render_telegram_preview` existiert (RED: AttributeError, fehlt noch). |

## Implementation Details

Tests folgen exakt dem No-Mocks-Setup aus
`tests/tdd/test_epic_140_preview_endpoints.py`:
- `TestClient` über den `preview.router`, echte Trip-Fixture
  `gr221-mallorca` aus `data/users/default`.
- `PreviewService(Settings())` für direkte Service-Aufrufe.
- Wetter-Provider-Calls erlaubt: HTTP 200 (Erfolg) oder 503 (API-Fehler) sind
  beide akzeptabel; inhaltliche Assertions nur bei 200.
- Keine `Mock()`, `patch()`, `MagicMock`.

In RED-Phase schlagen alle Tests fehl: die Endpoints `/signal` und `/telegram`
existieren noch nicht (404 statt 200/503/422) und die Service-Methoden
`render_signal_preview`/`render_telegram_preview` fehlen (AttributeError).

## Expected Behavior

- **Input:** `trip_id`, `user_id`, `type` (morning|evening), optional `date`.
- **Output:** Signal/Telegram → JSON `{subject, body, char_count, max_line_width}`,
  `body` = schmaler Monospace-Text aus `render_narrow` (#360).
- **Side effects:** keine (kein Versand, kein Persistieren).

## Acceptance Criteria

- **AC-T1:** Given die Test-Datei existiert und Implementierung fehlt /
  When `pytest tests/tdd/test_issue_363_signal_telegram_preview.py -v` läuft /
  Then schlagen alle Tests fehl (RED-Phase: 404 bzw. AttributeError).

- **AC-T2:** Given GREEN-Phase abgeschlossen /
  When dieselbe Suite läuft /
  Then alle grün, keine Mocks.

## Known Limitations

- AC-5 (Go-Proxy-Routen) und AC-6 (`buildPreviewUrl`-Typ) werden erst in der
  GREEN-Phase getestet/umgesetzt — in RED nicht erzwungen (würden vorab grün).
- Endpoint-Assertions tolerieren 503 bei Wetter-API-Ausfall (wie email/sms).

## Changelog

- 2026-05-25: Initial — Test-Manifest für Issue #363 (Signal/Telegram-Vorschau).
