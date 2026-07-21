---
entity_id: issue_641_remove_dead_sms_trend_tests
type: tests
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [sms, cleanup, tests]
---

# Tests: #641 Toten SMS-Trend-Pfad entfernen

Test-Spec zu `docs/specs/modules/issue_641_remove_dead_sms_trend.md`.
Mock-frei, Laufzeit-Introspektion (kein Datei-Text-Scan).

## Test-Fälle

- **test_format_sms_has_no_multi_day_trend_param** — `inspect.signature(SMSTripFormatter.format_sms)`
  enthält keinen `multi_day_trend`-Parameter mehr (toter SMS-Trend-Pfad entfernt, AC-1).
  RED vor Rückbau (Param vorhanden), GRÜN danach.
- **test_sms_peak_only_helper_removed** — `hasattr(sms_trip, "_sms_peak_only")` ist False
  (Helfer nur vom toten Trend-Block genutzt, AC-1). RED vor Rückbau, GRÜN danach.

## Behavior-Preservation (AC-2)

Die echte SMS-Vorschau-Ausgabe bleibt bit-identisch (der entfernte Pfad lief nie).
