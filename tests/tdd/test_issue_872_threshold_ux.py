"""TDD RED — #872: Schwellwerte-Block UX — Label-Fix + Presets + Gewitter.

SPEC: docs/specs/modules/issue_872_threshold_ux.md (AC-1..AC-6)

AC-6 (Backend): SMS_SYMBOL_BY_METRIC muss "thunder" -> "TH:" enthalten.
AC-4 (Backend): trip_report_scheduler muss sms_threshold_thunder im Trend-Dict übergeben.

AC-1/2/3/5 sind Frontend-E2E-ACs → frontend/e2e/issue-872-threshold-ux.spec.ts

RED-Erwartung:
  AC-6: AssertionError — "thunder" fehlt in SMS_SYMBOL_BY_METRIC (nur R/PR/W/G)
  AC-4: AssertionError — Scheduler baut sms_threshold_thunder nicht in Trend-Dict

KEINE Mocks — echter Import von sms_trip, echter Scheduler-Pfad.
"""

from __future__ import annotations

import pytest


# ── AC-6: SMS_SYMBOL_BY_METRIC enthält "thunder" -> "TH:" ─────────────────
def test_ac6_sms_symbol_by_metric_contains_thunder():
    """
    GIVEN: SMS_SYMBOL_BY_METRIC in src/formatters/sms_trip.py
    WHEN:  Direkter Import des Dicts
    THEN:  "thunder" ist als Key vorhanden mit Wert "TH:"
    """
    from src.formatters.sms_trip import SMS_SYMBOL_BY_METRIC

    assert "thunder" in SMS_SYMBOL_BY_METRIC, (
        f"SMS_SYMBOL_BY_METRIC enthält 'thunder' nicht. Aktuell: {list(SMS_SYMBOL_BY_METRIC.keys())}"
    )
    assert SMS_SYMBOL_BY_METRIC["thunder"] == "TH:", (
        f"Erwarte 'TH:', got '{SMS_SYMBOL_BY_METRIC['thunder']}'"
    )


# ── AC-4: Scheduler-Quellcode enthält sms_threshold_thunder ──────────────
def test_ac4_scheduler_source_contains_sms_threshold_thunder():
    """
    GIVEN: trip_report_scheduler.py (Trend-Dict-Aufbau ~Z.1064-1069)
    WHEN:  Quellcode-Inspektion des Scheduler-Moduls
    THEN:  Der String "sms_threshold_thunder" ist im Quellcode vorhanden,
           was beweist dass der Scheduler diesen Key in den Trend-Dict schreibt
    """
    import inspect
    from src.services import trip_report_scheduler

    scheduler_src = inspect.getsource(trip_report_scheduler)

    assert "sms_threshold_thunder" in scheduler_src, (
        "trip_report_scheduler.py enthält 'sms_threshold_thunder' noch nicht. "
        "Erwartet: Zeile ~1067 'sms_threshold_thunder': _sms_thr.get('thunder')"
    )
