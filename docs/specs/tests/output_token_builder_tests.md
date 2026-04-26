---
entity_id: output_token_builder_tests
type: tests
created: 2026-04-26
updated: 2026-04-26
status: active
version: "1.0"
tags: [tests, sms, token-builder]
parent: output_token_builder
---

# Output Token Builder Tests

## Approval

- [x] Approved

## Purpose

Test entity manifest for the β1 token builder. Each entry maps a pytest
function name (without the `test_` prefix) to the behaviour it asserts.

## Source

- **File:** `tests/unit/test_token_builder.py`, `tests/golden/test_sms_golden.py`
- **Spec:** `docs/specs/modules/output_token_builder.md` v1.1

## Test Inventory

### Unit (`tests/unit/test_token_builder.py`)

| Test | Asserts |
|---|---|
| build_token_line_returns_tokenline | Returns `TokenLine` instance |
| token_order_positional_per_sms_format_v2 | §2 POSITIONAL order N D R PR W G TH: TH+: |
| friendly_format_uses_friendly_label | `use_friendly_format=True` -> friendly label |
| threshold_peak_format | `R0.2@6(1.4@16)` rendering |
| morning_filter_excludes_evening_only | `morning_enabled=False` drops token |
| wintersport_profile_adds_sn_token | `profile=wintersport` injects `SN` |
| render_max_length_truncates | `len(render(160)) <= 160` + `truncated=True` |
| render_truncation_priority | §6 order: DBG -> Wintersport -> Fire -> Peaks -> PR -> D/N |
| empty_forecast_raises | empty forecast -> `ValueError` |
| determinism | identical inputs -> identical render |
| stage_name_umlauts_replaced | Umlauts ersetzt VOR Truncate; `Übergangsjoch` -> `Uebergangsjoch`[:10] -> `Uebergangs` |
| stage_name_truncated_to_ten_chars | Stage-Name max 10 Chars; `VeryLongStageName` -> `VeryLongSt` |

### Golden / Conformance (`tests/golden/test_sms_golden.py`)

| Test | Asserts |
|---|---|
| golden_gr20_summer_evening | render() == frozen golden gr20-summer-evening.txt |
| golden_gr20_spring_morning | render() == frozen golden gr20-spring-morning.txt |
| golden_gr221_mallorca_evening | render() == frozen golden gr221-mallorca-evening.txt |
| golden_arlberg_winter_morning | render() == frozen golden arlberg-winter-morning.txt |
| golden_corsica_vigilance | render() == frozen golden corsica-vigilance.txt |
| render_conforms_to_sms_format_v2 | Structural §2 / §3 conformance for all 5 goldens |

## Expected Behavior

- **Input:** Synthetic NormalizedForecast + MetricSpec list per test fixture.
- **Output:** Test passes / fails based on assertions in spec.
- **Side effects:** None (pure tests).

## Known Limitations

- Property-tests (Hypothesis) are optional in β1 and not part of this manifest.

## Changelog

- 2026-04-26: Initial test manifest for β1 token builder.
