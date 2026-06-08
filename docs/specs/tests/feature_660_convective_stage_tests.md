---
entity_id: feature_660_convective_stage_tests
type: tests
created: 2026-06-07
updated: 2026-06-08
status: draft
version: "1.0"
tags: [tests, feature, radar, nowcast, convective, issue-660]
parent: radar_convective_stage
phase: phase5_tdd_red
---

# Feature #660 — Gewitter/Hagel-Stufe (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für Feature #660 (Konvektions-Stufe im Radar-Nowcast). Jeder Eintrag
mappt einen pytest-Funktionsnamen auf das in der Parent-Spec definierte
Acceptance-Criterion.

Parent-Spec: `docs/specs/modules/radar_convective_stage.md`.

## Source

- **Files:**
  - `tests/tdd/test_feature_660_convective_stage.py` (NEU — mock-frei)
- **Spec:** `docs/specs/modules/radar_convective_stage.md` v1.0

## Test Inventory

Die Test-Funktionsnamen tragen die AC-Bezeichner, damit der Spec-Enforcement-Hook
sie auflösen kann.

| Test-Funktion | AC | Was geprüft wird |
|---------------|----|------------------|
| `ac1_intensity_convective_overrides_rate` | AC-1 | `intensity_to_text(mm, is_convective=True)` liefert „Starker Hagel/Gewitter" unabhängig von der Rate. |
| `ac1_intensity_non_convective_unchanged` | AC-1 | Ohne Konvektion bleibt das 4-Stufen-Verhalten (inkl. Default-Argument) exakt erhalten. |
| `ac2_openmeteo_frames_have_convective_flag` | AC-2 | Echter Open-Meteo-`minutely_15`-Abruf → jeder RadarFrame trägt ein bool `is_convective`. |
| `ac2_weathercode_maps_to_convective` | AC-2 | WMO-Codes 95/96/99 → konvektiv; alle anderen (inkl. None) → nicht konvektiv. |
| `ac3_derive_result_convective_label_and_text` | AC-3 | Konvektiver nasser Frame → `NowcastResult.is_convective`, Label und `format_now_text` nennen Gewitter. |
| `ac4_radar_alert_convective_marked_once_then_throttles` | AC-4 | Genau 1 Radar-Alert mit Gewitter-Kennzeichnung + alert_log HIGH; zweiter Lauf throttelt. |

## Anti-Mock-Nachweis

- AC-1/AC-3: pure Funktionen mit echten `RadarFrame`/`NowcastResult`-Objekten.
- AC-2: echter HTTP-Call gegen Open-Meteo + deterministischer Mapping-Test.
- AC-4: echte DI-Frame-Quelle + Aufzeichnung der real gebauten `EmailOutput.send`-Argumente
  (kein Mock-Objekt, nur Recorder-Funktion — Muster #612).

## Changelog

- 2026-06-07: Initial test manifest (Issue #660)
- 2026-06-08: Implementation complete — all AC tests passing, mock-free verification confirmed
