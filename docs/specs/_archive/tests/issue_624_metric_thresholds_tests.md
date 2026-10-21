---
entity_id: issue_624_metric_thresholds_tests
type: tests
created: 2026-06-06
updated: 2026-06-06
status: implemented
version: "1.0"
tags: [output, sms, telegram, threshold, tdd]
---

# Test-Manifest: Konfigurierbare Schwellwerte pro Metrik (#624)

## Approval

- [x] Approved (PO „go", 2026-06-06)

MODUL-SPEC: `docs/specs/_archive/modules/issue_624_metric_thresholds.md`

Test-Datei: `tests/tdd/test_issue_624_metric_thresholds.py`. KEINE Mocks —
echte `SegmentWeatherData`, echter `SMSTripFormatter.format_sms()`-Render,
echter `loader._parse_display_config`-Parse.

## Test → AC Mapping

| Test-Funktion | AC | Was bewiesen wird | RED-Grund |
|---------------|----|-------------------|-----------|
| `def test_metricconfig_sms_threshold_default_none` | Model | `MetricConfig.sms_threshold` existiert, Default `None` (additiv) | Feld fehlt → TypeError/AttributeError |
| `def test_ac1_metric_id_to_sms_symbol_mapping` | AC-1 | `SMS_SYMBOL_BY_METRIC` mappt precipitation→R, rain_probability→PR, wind→W, gust→G | Mapping existiert nicht → ImportError |
| `def test_ac1_configured_threshold_shifts_first_crossing` | AC-1 | Konfigurierter Schwellwert (W=25) verschiebt erste-Überschreitung von 10 Uhr (Default) auf 14 Uhr | `format_sms` kennt kein `thresholds`-Kwarg → TypeError |
| `def test_ac2_default_baseline_unchanged` | AC-2 | Ohne Konfiguration bleibt Output = Default (`W18@10(40@16)`) — GREEN-Guard | bleibt grün vor/nach Fix |
| `def test_ac3_loader_roundtrip_preserves_sms_threshold` | AC-3 | Loader parst `sms_threshold=5.0` und erhält übrige MetricConfig-Felder (kein Datenverlust) | Loader liest Feld nicht |

AC-4 (kein Eingabefeld bei Nicht-Threshold-Metriken) und AC-5 (Persistenz im Editor nach
Reload) sind FRONTEND-ACs → werden in der E2E-Phase via `staging-validator` (Playwright)
bewiesen, nicht im pytest (analog #614 AC-5).

## Erwartete RED-Evidenz

- Model/AC-1/AC-3: `TypeError`/`ImportError`/`AttributeError`, weil Feld, Mapping und
  `thresholds`-Param noch nicht existieren.
- AC-2: grün (Regressions-Guard, darf durch das Feature nicht brechen).
