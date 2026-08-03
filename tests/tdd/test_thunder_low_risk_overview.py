"""TDD RED — Issue #1474 (S3 zu #1419), AC-12.

SPEC: docs/specs/modules/feat_1474_gewitter_befund_stufen.md v2.3 Abschnitt 4

`RiskEngine._check_thunder()` kennt heute nur HIGH->RiskLevel.HIGH und
MED->RiskLevel.MODERATE; LOW kommt in keinem Zweig vor. Ohne Erweiterung ist
"leicht" in der fertigen Risiko-Uebersicht nicht bloss abwesend, sondern
FALSCH beschriftet: `trip_report.py::_determine_risk` und
`sms_trip.py::_detect_risk` lesen `assessment.risks` DIREKT und fallen bei
einem unbekannten (type, level)-Paar auf einen generischen Fallback zurueck
(`top.type.value.title()` = "Thunderstorm", englisch, kein "leicht").

Diese ACs pruefen die WIRKUNG an der FERTIGEN Risiko-Uebersicht, nicht an der
Beschriftungstabelle (Lehre aus #1457, dreimal an genau diesem Punkt
gescheitert).

RED-Ursache (heute): `ThunderLevel.LOW` existiert nicht -> AttributeError.

Keine Mocks: echte SegmentWeatherData-/SegmentWeatherSummary-Fixturen, echte
RiskEngine.assess_segment()-Kette, echte Renderer-Methoden.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import (
    GPXPoint,
    NormalizedTimeseries,
    ForecastMeta,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)


def _segment_data(thunder_level_max) -> SegmentWeatherData:
    """Fixture (a)/(b): NUR das Gewitter-Feld variiert, alle anderen
    Risikofelder bleiben unauffaellig (keine weiteren Risiken)."""
    now = datetime.now(timezone.utc)
    seg = TripSegment(
        segment_id="seg-1",
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500, distance_from_start_km=8.0),
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=3),
        duration_hours=4.0, distance_km=8.0, ascent_m=500, descent_m=0,
    )
    agg = SegmentWeatherSummary(
        temp_min_c=10.0, temp_max_c=16.0, temp_avg_c=13.0,
        wind_max_kmh=15.0, gust_max_kmh=25.0, precip_sum_mm=0.0,
        cloud_avg_pct=40, humidity_avg_pct=50,
        thunder_level_max=thunder_level_max,
        wind_chill_min_c=8.0, pop_max_pct=10, cape_max_jkg=None,
        visibility_min_m=15000,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=agg,
        fetched_at=now,
        provider="openmeteo",
    )


# ─────────────────────── RiskEngine (Kern der Kette) ──────────────────────

def test_ac12_risk_engine_erzeugt_low_risiko():
    """Vorstufe: RiskEngine._check_thunder() erzeugt bei LOW ueberhaupt einen
    Risk-Eintrag (RiskLevel.LOW, RiskType.THUNDERSTORM)."""
    from app.models import RiskLevel, RiskType
    from services.risk_engine import RiskEngine

    data_low = _segment_data(ThunderLevel.LOW)
    assessment = RiskEngine().assess_segment(data_low)
    thunder_risks = [r for r in assessment.risks if r.type == RiskType.THUNDERSTORM]
    assert thunder_risks, (
        "RiskEngine erzeugt bei ThunderLevel.LOW keinen THUNDERSTORM-Risk-"
        "Eintrag -- der dritte Zweig (LOW -> RiskLevel.LOW) fehlt in "
        "_check_thunder()"
    )
    assert thunder_risks[0].level == RiskLevel.LOW


def test_ac12_kein_risiko_ohne_gewitter_und_ohne_low():
    """Gegenprobe-Vorbedingung: die (b)-Fixture (kein Risiko ueberhaupt)
    erzeugt tatsaechlich KEINE Risiken -- sonst waere der spaetere
    Unterschieds-Test wertlos."""
    from services.risk_engine import RiskEngine

    data_none = _segment_data(None)
    assessment = RiskEngine().assess_segment(data_none)
    assert assessment.risks == [], (
        f"Die 'kein Risiko'-Fixture darf keine Risiken erzeugen, erhalten "
        f"{assessment.risks!r}"
    )


# ────────────── AC-12: fertige Uebersicht, Trip-Pfad ──────────────────────

def test_ac12_trip_report_determine_risk_zeigt_leicht():
    """(a) LOW liefert einen von '✓ OK' verschiedenen Eintrag mit dem
    deutschen Wort fuer 'leicht'."""
    from output.renderers.trip_report import TripReportFormatter

    formatter = TripReportFormatter()
    level, label = formatter._determine_risk(_segment_data(ThunderLevel.LOW))
    assert (level, label) != ("none", "✓ OK"), (
        "Ein leichtes Gewitter darf nicht als 'kein Risiko' erscheinen"
    )
    assert "leicht" in label.lower(), (
        f"Die Risiko-Uebersicht muss bei LOW das deutsche Wort 'leicht' "
        f"zeigen (nicht den generischen englischen Fallback), erhalten "
        f"level={level!r} label={label!r}"
    )


def test_ac12_trip_report_determine_risk_kein_risiko_bleibt_ok():
    """(b) Kein Risiko (auch kein leichtes Gewitter) liefert weiterhin
    ('none', '✓ OK')."""
    from output.renderers.trip_report import TripReportFormatter

    formatter = TripReportFormatter()
    level, label = formatter._determine_risk(_segment_data(None))
    assert (level, label) == ("none", "✓ OK")


def test_ac12_trip_report_low_und_kein_risiko_unterscheiden_sich():
    """Beide Faelle muessen sich unterscheiden -- sonst ist die Kette blind
    fuer 'leicht' (dieselbe Kette wird als 'kein Risiko' behandelt)."""
    from output.renderers.trip_report import TripReportFormatter

    formatter = TripReportFormatter()
    ergebnis_low = formatter._determine_risk(_segment_data(ThunderLevel.LOW))
    ergebnis_kein = formatter._determine_risk(_segment_data(None))
    assert ergebnis_low != ergebnis_kein, (
        f"LOW und 'kein Risiko' liefern dasselbe Ergebnis {ergebnis_low!r} -- "
        "die Risiko-Kette ist blind fuer 'leicht'"
    )


# ────────────── AC-12: fertige Uebersicht, SMS-Pfad ────────────────────────

def _sms_formatter_with_tz():
    """`_detect_risk()` liest `self._tz` (Issue #1402: kein stiller
    UTC-Rueckfall); der einzige produktive Aufrufer `format_sms()` setzt ihn
    vorher. Ein Direktaufruf muss das nachbilden, sonst scheitert der
    GREEN-Zustand an einer AttributeError statt an der eigentlichen
    Zusicherung."""
    from zoneinfo import ZoneInfo

    from output.renderers.sms_trip import SMSTripFormatter

    formatter = SMSTripFormatter()
    formatter._tz = ZoneInfo("Europe/Berlin")
    return formatter


def test_ac12_sms_detect_risk_zeigt_leicht():
    """(a) LOW liefert im SMS-Pfad ebenfalls einen von None verschiedenen
    Eintrag mit dem deutschen Wort fuer 'leicht'."""
    formatter = _sms_formatter_with_tz()
    label, _hour = formatter._detect_risk(_segment_data(ThunderLevel.LOW))
    assert label is not None, "SMS-Pfad liefert kein Label fuer ein leichtes Gewitter"
    assert "leicht" in label.lower(), (
        f"Das SMS-Risiko-Label muss bei LOW das deutsche Wort 'leicht' "
        f"enthalten, erhalten {label!r}"
    )


def test_ac12_sms_detect_risk_kein_risiko_bleibt_none():
    """(b) Kein Risiko liefert weiterhin (None, None)."""
    formatter = _sms_formatter_with_tz()
    label, hour = formatter._detect_risk(_segment_data(None))
    assert (label, hour) == (None, None)


def test_ac12_sms_low_und_kein_risiko_unterscheiden_sich():
    formatter = _sms_formatter_with_tz()
    ergebnis_low = formatter._detect_risk(_segment_data(ThunderLevel.LOW))
    ergebnis_kein = formatter._detect_risk(_segment_data(None))
    assert ergebnis_low != ergebnis_kein, (
        f"LOW und 'kein Risiko' liefern im SMS-Pfad dasselbe Ergebnis "
        f"{ergebnis_low!r} -- die Kette ist blind fuer 'leicht'"
    )


# ─────────────── Regressionsschutz: MED/HIGH unveraendert ─────────────────

def test_ac12_regressionsschutz_med_und_high_labels_unveraendert():
    """Derselbe Testaufbau mit MED/HIGH muss weiterhin die BISHERIGEN Labels
    liefern -- die LOW-Erweiterung darf MED/HIGH nicht veraendern."""
    from output.renderers.trip_report import TripReportFormatter

    trip_formatter = TripReportFormatter()
    sms_formatter = _sms_formatter_with_tz()

    level_med, label_med = trip_formatter._determine_risk(_segment_data(ThunderLevel.MED))
    assert level_med == "moderate"
    assert label_med == "⚠️ Thunder Risk"

    level_high, label_high = trip_formatter._determine_risk(_segment_data(ThunderLevel.HIGH))
    assert level_high == "high"
    assert label_high == "⚠️ Thunder"

    sms_label_med, _ = sms_formatter._detect_risk(_segment_data(ThunderLevel.MED))
    assert sms_label_med == "Gewitter"

    sms_label_high, _ = sms_formatter._detect_risk(_segment_data(ThunderLevel.HIGH))
    assert sms_label_high == "Gewitter"
