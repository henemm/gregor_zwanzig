---
entity_id: output_channel_renderers_tests
type: tests
created: 2026-04-27
updated: 2026-04-27
status: draft
version: "1.0"
tags: [tests, output, pipeline, refactor, epic-render-pipeline]
parent: output_channel_renderers
phase: β3
---

# Output Channel Renderers Tests

## Approval

- [x] Approved

## Purpose

Test entity manifest for the β3 channel-renderer split. Each entry maps a
pytest function name (without the `test_` prefix) to the behaviour it asserts.

Parent module spec: `docs/specs/modules/output_channel_renderers.md`.

## Source

- **Files:**
  - `tests/golden/email/test_email_plain_golden.py` (Plain-Text-Goldens, §A7)
  - `tests/unit/test_renderers_email.py` (Direktaufruf-Tests `render_email`)
  - `tests/unit/test_renderers_sms.py` (Direktaufruf-Tests `render_sms`)
  - `tests/unit/test_sms_trip.py` (Adapter-Migration auf v2.0, §A3)
- **Spec:** `docs/specs/modules/output_channel_renderers.md` v1.0

## Test Inventory

### Plain-Text Goldens (`tests/golden/email/test_email_plain_golden.py`)

Spec §A7 Pflicht-Gate. Eine parametrisierte Test-Funktion pro Profil:

| Test | Asserts |
|---|---|
| email_plain_golden_gr20_summer_evening | `report.email_plain == tests/golden/email/gr20-summer-evening-plain.txt` |
| email_plain_golden_gr20_spring_morning | `report.email_plain == tests/golden/email/gr20-spring-morning-plain.txt` |
| email_plain_golden_gr221_mallorca_evening | `report.email_plain == tests/golden/email/gr221-mallorca-evening-plain.txt` |
| email_plain_golden_arlberg_winter_morning | `report.email_plain == tests/golden/email/arlberg-winter-morning-plain.txt` |
| email_plain_golden_corsica_vigilance | `report.email_plain == tests/golden/email/corsica-vigilance-plain.txt` |

### Direktaufruf-Tests `render_email()` (`tests/unit/test_renderers_email.py`)

| Test | Asserts |
|---|---|
| render_email_returns_html_and_plain_tuple | Rückgabe ist `tuple[str, str]` |
| render_email_html_contains_segment_table | HTML enthält `<table>` mit Etappen-Header |
| render_email_plain_matches_html_data | Plain enthält dieselben Stage-Daten und Highlights wie HTML |
| render_email_with_changes_renders_alert_block | `changes!=None` → HTML+Plain enthalten Alert-Sektion |
| render_email_no_night_rows_when_morning | `report_type=morning, night_rows=None` → kein 'Nacht'-Block |
| render_email_pure_function | Zwei Aufrufe mit identischen Inputs → outputs `==` (Determinismus) |

### Direktaufruf-Tests `render_sms()` (`tests/unit/test_renderers_sms.py`)

| Test | Asserts |
|---|---|
| render_sms_delegates_to_tokenline | `render_sms(line) == render_line(line, 160)` (β1-Authority) |
| render_sms_respects_max_length | `len(render_sms(line, 160)) <= 160` für lange TokenLines |
| render_sms_v2_format | Output enthält `N12 D18`, NICHT Legacy `T12/18` |

### SMS-Adapter-Migration auf v2.0 (`tests/unit/test_sms_trip.py`, §A3)

Bestehende Tests werden auf v2.0-Erwartungen umgeschrieben (kein neuer Test-Datei-Pfad).

| Test | Asserts |
|---|---|
| sms_formatter_exists | `SMSTripFormatter` bleibt importierbar (Adapter, A3) |
| format_sms_single_segment_v2 | Output enthält `N12 D18`, kein Legacy `E1:T12/18`, kein `\|`-Trenner |
| format_sms_validates_length | `len(sms) <= 160` (sms_format.md §1) — bleibt unverändert |
| format_sms_v2_wire_format | Stage-Prefix `{Name}: ` am Anfang; genau eine Zeile (kein `\n`/`\|`) |

## Expected Behavior

- **Phase 5 RED:** Alle 17 oben gelisteten Tests müssen fehlschlagen, weil
  `src/output/renderers/` und die migrierten Adapter noch nicht existieren.
  - 5 Plain-Text-Goldens: `pytest.fail` (Golden-Datei fehlt).
  - 6 `render_email`-Tests: `ModuleNotFoundError` für `src.output.renderers.email`.
  - 3 `render_sms`-Tests: `ModuleNotFoundError` für `src.output.renderers.sms`.
  - 3 SMS-Migrationstests: Format-Assertions schlagen fehl (Legacy `E1:T12/18`).
- **Phase 6 GREEN:** Alle 17 Tests grün; bestehende ~87 Trip-Report-Formatter-
  Tests bleiben unverändert grün; β1-SMS-Goldens und β2-Subject-Goldens bleiben
  unverändert grün.

## Known Limitations

- HTML-Volltext-Goldens werden bewusst NICHT geschrieben (Spec §A7,
  Wartungsalbtraum). Strukturtests in den 87+ bestehenden Tests sind das
  HTML-Drift-Netz.
- Property-Tests (Hypothesis) sind kein Bestandteil von β3.

## Changelog

- 2026-04-27: Initial test manifest for β3 channel renderers (TDD RED).
