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
from tests.helpers.ampel_allgemein import AMPEL_ALLGEMEIN

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

    # Issue #2792 S1c-4b (E1, AC-19 e) -- umgekehrt: die SMS-Schwelle wirkt
    # im Ausblick nicht mehr; ``build_outlook_row`` nimmt sie nicht mehr an
    # und die Zeile traegt keinen ``sms_threshold_*``-Schluessel.
    import pytest
    with pytest.raises(TypeError):
        build_outlook_row(
            summary, [], "Mo", tz, sms_thresholds={"thunder": 3.0},
            context="vergleich", ampel=AMPEL_ALLGEMEIN,
        )
    row = build_outlook_row(summary, [], "Mo", tz, context="vergleich", ampel=AMPEL_ALLGEMEIN)
    assert not [k for k in row if k.startswith("sms_threshold")], (
        f"Die Ausblick-Zeile darf keine SMS-Schwelle mehr tragen, erhalten: {row}"
    )
