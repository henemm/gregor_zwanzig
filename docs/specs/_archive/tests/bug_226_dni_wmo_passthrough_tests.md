---
entity_id: bug_226_dni_wmo_passthrough_tests
type: tests
created: 2026-05-20
updated: 2026-05-20
status: complete
version: "1.0"
tags: [tests, weather-metrics, segment-summary, dni, wmo-code, bug-226]
parent: bug_226_dni_wmo_passthrough
phase: phase5_tdd_red
---

# Bug #226 — DNI/WMO Passthrough: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/bug_226_dni_wmo_passthrough.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/bug_226_dni_wmo_passthrough.md` v1.0

## Source

- **File:** `tests/tdd/test_bug_226_dni_wmo_passthrough.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_dominant_wmo_code_passthrough` | AC-1 | `dominant_wmo_code=80` aus basis_summary kommt in extended result durch |
| `test_ac2_dni_avg_wm2_passthrough` | AC-2 | `dni_avg_wm2=250.0` aus basis_summary kommt in extended result durch |
| `test_ac3_none_fields_remain_none` | AC-3 | Felder mit `None` im basis_summary bleiben `None` — kein Regression |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests sollen FAIL sein)
uv run pytest tests/tdd/test_bug_226_dni_wmo_passthrough.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_bug_226_dni_wmo_passthrough.py \
             tests/unit/test_weather_metrics.py -v
```

## Changelog

- 2026-05-20: Initial test manifest erstellt für Bug #226.
