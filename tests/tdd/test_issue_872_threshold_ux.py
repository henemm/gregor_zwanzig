"""TDD RED — #872: Schwellwerte-Block UX — Label-Fix + Presets + Gewitter.

SPEC: docs/specs/modules/issue_872_threshold_ux.md (AC-1..AC-6)

AC-6 (Backend): SMS_SYMBOL_BY_METRIC muss "thunder" -> "TH:" enthalten.
AC-4 (Backend): eine gesetzte Gewitterschwelle muss tatsaechlich als
  row["sms_threshold_thunder"] ankommen -- geprueft am geteilten
  Ausblick-Renderer build_outlook_row() (src/output/renderers/email/outlook.py),
  wo der Schlüssel seit #1301 gesetzt wird (Issue #1196 S1 AC-7: der alte
  Quelltext-Textprüfer zeigte auf einen laengst umgezogenen Ort im Scheduler).

AC-1/2/3/5 sind Frontend-E2E-ACs → frontend/e2e/issue-872-threshold-ux.spec.ts

KEINE Mocks — echter Import von sms_trip, echter Aufruf von build_outlook_row.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo



# ── AC-6: SMS_SYMBOL_BY_METRIC enthält "thunder" -> "TH:" ─────────────────
def test_ac6_sms_symbol_by_metric_contains_thunder():
    """
    GIVEN: SMS_SYMBOL_BY_METRIC in src/formatters/sms_trip.py
    WHEN:  Direkter Import des Dicts
    THEN:  "thunder" ist als Key vorhanden mit Wert "TH:"
    """
    from src.output.renderers.sms_trip import SMS_SYMBOL_BY_METRIC

    assert "thunder" in SMS_SYMBOL_BY_METRIC, (
        f"SMS_SYMBOL_BY_METRIC enthält 'thunder' nicht. Aktuell: {list(SMS_SYMBOL_BY_METRIC.keys())}"
    )
    assert SMS_SYMBOL_BY_METRIC["thunder"] == "TH:", (
        f"Erwarte 'TH:', got '{SMS_SYMBOL_BY_METRIC['thunder']}'"
    )


# ── AC-4: gesetzte Gewitterschwelle kommt in build_outlook_row() an ──────
def test_ac4_gesetzte_sms_schwelle_thunder_kommt_in_row_an():
    """
    GIVEN: build_outlook_row(..., sms_thresholds={"thunder": X})
    WHEN:  die Zeile gebaut wird
    THEN:  row["sms_threshold_thunder"] == X (Positivfall -- die Negation
           bei None/leerem Dict prüft bereits test_shared_outlook_renderer.py
           test_build_outlook_row_pure_function, Zeile 260)
    """
    from app.models import SegmentWeatherSummary, ThunderLevel
    from output.renderers.email.outlook import build_outlook_row

    summary = SegmentWeatherSummary(
        temp_min_c=9.0, temp_max_c=21.0, precip_sum_mm=3.5,
        wind_max_kmh=28.0, thunder_level_max=ThunderLevel.MED,
        pop_max_pct=60,
    )
    tz = ZoneInfo("Europe/Vienna")

    row = build_outlook_row(
        summary, [], "Mo", tz, sms_thresholds={"thunder": 3.0},
    )
    assert row["sms_threshold_thunder"] == 3.0, (
        f"Gesetzte Gewitterschwelle muss ankommen, erhalten: {row.get('sms_threshold_thunder')!r}"
    )

    row_empty = build_outlook_row(summary, [], "Mo", tz, sms_thresholds={})
    assert "sms_threshold_thunder" not in row_empty, (
        f"Ohne gesetzte Schwelle darf der Schlüssel nicht auftauchen, erhalten: {row_empty}"
    )

    row_none = build_outlook_row(summary, [], "Mo", tz, sms_thresholds={"thunder": None})
    assert "sms_threshold_thunder" not in row_none, (
        f"None-Schwelle muss gefiltert werden, erhalten: {row_none}"
    )
