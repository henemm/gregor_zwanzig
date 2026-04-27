---
entity_id: output_subject_filter_tests
type: tests
created: 2026-04-26
updated: 2026-04-26
status: active
version: "1.0"
tags: [tests, subject, output, epic-render-pipeline]
parent: output_subject_filter
phase: β2
---

# Output Subject Filter Tests

## Approval

- [x] Approved

## Purpose

Test entity manifest for the β2 subject filter. Each entry maps a pytest
function name (without the `test_` prefix) to the behaviour it asserts.

## Source

- **File:** `tests/unit/test_subject_filter.py`, `tests/golden/test_subject_golden.py`
- **Spec:** `docs/specs/modules/output_subject_filter.md` v1.0

## Test Inventory

### Unit (`tests/unit/test_subject_filter.py`)

| Test | Asserts |
|---|---|
| subject_basic_format | Skelett `[GR221] Tag 1 — Morgen — Gewitter` ohne Wetter-Tokens |
| subject_german_report_type_labels | `morning → Morgen`, `evening → Abend`, `update → Update` |
| subject_main_risk_german | `main_risk="Thunder"` → Subject enthält `Gewitter`, nicht `Thunder` |
| subject_with_weather_tokens | Whitelist-Reihenfolge `D → W → G`, Space-getrennt |
| subject_drops_non_whitelisted_tokens | `N`, `R`, `PR`, `TH+` dürfen NICHT im Subject erscheinen |
| subject_hr_th_vigilance_fusion | HR/TH-Vigilance-Paar gefused ohne Space (`HR:M@13TH:H@14`) |
| subject_truncation_to_78_drops_weather_first | Wetter-Tokens fallen vor Etappe/Trip; ≤78 Zeichen |
| subject_truncation_keeps_stage_name_intact | Etappen-Name niemals gekürzt; ggf. Trip-Präfix gestrichen |
| subject_no_trip_prefix_when_trip_name_none | `trip_name=None` → kein `[…]`-Präfix |
| subject_no_trailing_dash_when_no_risk_and_no_tokens | `main_risk=None` + `tokens=()` → kein dangling ` — ` am Subject-Ende (Validator-Finding 2026-04-27) |
| trip_report_subject_includes_dwg_tokens | TripReportFormatter.format_email mit aggregierten Wetter-Daten → Subject enthält `D{temp_max} W{wind_max} G{gust_max}` (Validator-Finding 2026-04-27) |

### Golden (`tests/golden/test_subject_golden.py`)

| Test | Asserts |
|---|---|
| golden_gr221_summer_morning | `[GR221] Tag 3: Valldemossa → Sóller — Morgen — Hitze D32 W12 G20` |
| golden_gr20_spring_evening_vigilance | `[GR20] Étape 7: Vizzavona — Abend — Sturm D18 W30@14 G55@15 HR:M@13TH:H@14` |
| golden_arlberg_wintersport_update | `[Arlberg] Tag 2: Lech — Update — Schnee D-4 W45 G70` |
| golden_corsica_fr_vigilance_morning | `[Corsica] E5: Vizzavona — Morgen — Gewitter D32 W30 G45 HR:M@14TH:H@17` |
| golden_gr221_short_update | `[GR221] Tag 1: Port d'Andratx → Esporles — Update — D26 W08 G15` (kein MainRisk) |

## Expected Behavior

- **Phase:** TDD RED — alle Tests müssen fehlschlagen, weil `src/output/subject.py` und die DTO-Felder `main_risk`/`trip_name` noch nicht existieren.
- **Erwartung nach β2-Implementierung:** Alle 14 Tests grün.

## Changelog

- 2026-04-26: Initial test manifest (TDD RED for β2)
