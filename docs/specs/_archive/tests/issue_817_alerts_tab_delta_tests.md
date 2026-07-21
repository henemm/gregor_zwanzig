---
entity_id: issue_817_alerts_tab_delta_tests
type: test
created: 2026-06-14
updated: 2026-06-14
status: draft
version: "1.0"
tags: [alert, delta, alerts-tab, sync-alert-rules, cross-lang-contract]
---

# Issue #817 Alerts-Tab Delta-Schwellen — Tests

## Approval

- [x] Approved (PO, 2026-06-14)

## Test References

<!-- spec_enforcement entity lookup — maps test function names to this spec -->
- `817_ac4_cross_lang_contract_go_block_exists` — AC-4 (Teil 1: DefaultDeltaThreshold Map existiert + 6 Einträge via Go-subprocess)
- `817_ac4_cross_lang_contract_values` — AC-4 (Teil 2: Go-Laufzeitwerte stimmen mit Python metric_catalog überein)
- `817_ac5_delta_rule_threshold_flows_through` — AC-5 (Delta-Threshold fließt direkt durch from_alert_rules)
- `817_ac5_contrast_absolute_rule_ignores_threshold` — AC-5 Kontrast (Absolut-Threshold wird ignoriert — Kern-Erkenntnis #817)

## Purpose

Diese Tests decken den Cross-Lang-Wertekontrakt (AC-4) und den Regression-Guard
für from_alert_rules (AC-5) aus Issue #817 ab.

AC-4 nutzt einen Go-subprocess-Aufruf (`TestEmitDefaultDeltaThresholdJSON`) statt
Quelltext-Read — damit #765-konform (kein Produkt-Quelltext-Read via read_text).

## Changelog

- 2026-06-14: v1.0 Initial test spec (Issue #817, #765-konformes AC-4 via subprocess)
