"""TDD RED -- #1758 AC-9: die zwei neuen GeoSphere-Rohwerte aendern KEINE
Ausgabe.

Spec: docs/specs/modules/feat_1758_geosphere_cape_cin.md (AC-9, Invariante 4)

Diese Scheibe liefert AUSSCHLIESSLICH Rohwerte ins Datenmodell (Scope-
Abgrenzung: "keine Einstufung, keine Fusion, keine Ausgabeaenderung").
Faengt schon hier eine bestehende Rendering- oder Einstufungsfunktion an,
`cape_geosphere_jkg`/`convective_inhibition_geosphere_jkg` mitzulesen,
entstuende eine zweite, konkurrierende Gewitteraussage -- Verstoss gegen
ADR-0025.

Bauart des Nachweises (Muster `test_thunder_output_invariance_new_signals.py`,
#1531 AC-9): dieselbe Vorhersage/derselbe Ortsvergleich wird zweimal
gerendert -- einmal ohne die zwei neuen Felder, einmal mit ABSICHTLICH
EXTREMEN Werten. Wuerde irgendeine bestehende Funktion sie mitlesen, muesste
sich die Ausgabe unterscheiden.

Vier Kanaele geprueft (SMS, Gewitterstufen-Aggregation, Compare-Mail,
Trip-Briefing-Mail) -- wie im #1531-Vorbild, die Spec nennt hier explizit
dieselben vier Kanaele.

RED-GRUND (heute, unveraenderter Code): `ForecastDataPoint` kennt weder
`cape_geosphere_jkg` noch `convective_inhibition_geosphere_jkg` -> TypeError
beim Bauen des Vergleichsfalls (unerwartetes Keyword-Argument).

Testart: Kern-Schicht, keine Netzzugriffe, keine Mocks.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
)
from app.user import ComparisonResult, LocationResult, SavedLocation  # noqa: E402
from output.renderers.sms_trip import SMSTripFormatter  # noqa: E402
from output.renderers.trip_report import TripReportFormatter  # noqa: E402
from services.weather_metrics import WeatherMetricsService  # noqa: E402

_JAHR, _MONAT, _TAG = 2026, 8, 18
_TZ = ZoneInfo("UTC")
_START_H, _ENDE_H = 7, 17

# Absichtlich extrem -- deutlich ausserhalb jedes real gemessenen Bereichs
# (Aufzeichnung: cape 0,5..713,5, cin 0,0..-0,1).
_EXTREME_NEUE_FELDER = {
    "cape_geosphere_jkg": 6000.0,
    "convective_inhibition_geosphere_jkg": 900.0,
}


def _dp(stunde: int, thunder: ThunderLevel, mit_neuen_feldern: bool) -> ForecastDataPoint:
    neu = _EXTREME_NEUE_FELDER if mit_neuen_feldern else {}
    return ForecastDataPoint(
        ts=datetime(_JAHR, _MONAT, _TAG, stunde, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.0,
        cloud_total_pct=50, thunder_level=thunder, humidity_pct=55,
        **neu,
    )


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.GEOSPHERE, model="AROME",
        run=datetime(_JAHR, _MONAT, _TAG, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.5, interp="bilinear",
    )


def _reihe(mit_neuen_feldern: bool) -> NormalizedTimeseries:
    """24 Stunden mit einem MED-Gewitter um 09:00 und HIGH um 14:00 -- so
    tragen die Ausgaben ueberhaupt eine Gewitteraussage, an der eine
    Verfaelschung sichtbar wuerde."""
    stufen = {9: ThunderLevel.MED, 14: ThunderLevel.HIGH}
    daten = [
        _dp(h, stufen.get(h, ThunderLevel.NONE), mit_neuen_feldern) for h in range(24)
    ]
    return NormalizedTimeseries(meta=_meta(), data=daten)


def _segment(mit_neuen_feldern: bool) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=46.66, lon=12.74, elevation_m=1800.0),
        end_point=GPXPoint(lat=46.70, lon=12.80, elevation_m=2100.0),
        start_time=datetime(_JAHR, _MONAT, _TAG, _START_H, 0, tzinfo=timezone.utc),
        end_time=datetime(_JAHR, _MONAT, _TAG, _ENDE_H, 0, tzinfo=timezone.utc),
        duration_hours=float(_ENDE_H - _START_H),
        distance_km=14.0, ascent_m=600.0, descent_m=300.0,
    )
    ts = _reihe(mit_neuen_feldern)
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0, temp_max_c=20.0, wind_max_kmh=15.0,
            gust_max_kmh=25.0, precip_sum_mm=0.0,
            thunder_level_max=ThunderLevel.HIGH,
        ),
        fetched_at=datetime(_JAHR, _MONAT, _TAG, 6, 0, tzinfo=timezone.utc),
        provider="geosphere",
    )


def _sms(mit_neuen_feldern: bool) -> str:
    return SMSTripFormatter().format_sms(
        [_segment(mit_neuen_feldern)],
        stage_name="Karnisch-1", report_type="morning", tz=_TZ,
    )


def _briefing_mail(mit_neuen_feldern: bool):
    return TripReportFormatter().format_email(
        [_segment(mit_neuen_feldern)],
        trip_name="Test-Trip", report_type="morning", tz=_TZ,
    )


def _compare_result(mit_neuen_feldern: bool) -> ComparisonResult:
    loc = SavedLocation(id="loc-1", name="Karnischer Hoehenweg", lat=46.66, lon=12.74, elevation_m=1800)
    ts = _reihe(mit_neuen_feldern)
    lr = LocationResult(
        location=loc, score=50, temp_max=20.0, temp_min=10.0, wind_max=15.0,
        gust_max=25.0, cloud_avg=50, sunny_hours=3, official_alerts=[],
        hourly_data=ts.data,
    )
    return ComparisonResult(
        locations=[lr], time_window=(_START_H, _ENDE_H),
        target_date=date(_JAHR, _MONAT, _TAG),
        created_at=datetime(_JAHR, _MONAT, _TAG, 4, 0),
    )


def test_ac9_sms_bleibt_mit_und_ohne_die_neuen_geosphere_rohwerte_identisch():
    """AC-9 (Kanal 1/4, SMS): Given dieselbe Vorhersage einmal mit und einmal
    ohne gesetzte GeoSphere-Rohwerte, When die SMS gerendert wird, Then ist
    der Text zeichengleich."""
    ohne = _sms(False)
    mit = _sms(True)
    assert "TH:" in ohne, f"SMS traegt keine Gewitteraussage -- Vergleich pruefte nichts.\nSMS: {ohne}"
    assert mit == ohne, (
        f"SMS aendert sich, sobald die GeoSphere-Rohwerte gesetzt sind.\nohne: {ohne}\nmit : {mit}"
    )


def test_ac9_gewitterstufe_bleibt_mit_und_ohne_die_neuen_geosphere_rohwerte_identisch():
    """AC-9 (Kanal 2/4, Aggregation): Given dieselbe Zeitreihe mit und ohne
    die GeoSphere-Rohwerte, When die Gewitterstufe aggregiert wird, Then ist
    sie identisch -- ADR-0025 verbietet eine zweite, konkurrierende
    Gewitter-Quelle im selben Briefing."""
    dienst = WeatherMetricsService()
    ohne = dienst._compute_thunder_level(_reihe(False))
    mit = dienst._compute_thunder_level(_reihe(True))
    assert ohne is not None, "Ohne die neuen Felder kommt gar keine Stufe heraus"
    assert mit == ohne, f"Gewitterstufe aendert sich von {ohne} auf {mit}"


def test_ac9_compare_mail_bleibt_mit_und_ohne_die_neuen_geosphere_rohwerte_identisch():
    """AC-9 (Kanal 3/4, Compare-Mail): Given denselben Ortsvergleich einmal
    mit und einmal ohne die GeoSphere-Rohwerte, When die Compare-Mail (HTML +
    Klartext) gerendert wird, Then sind beide Teile zeichengleich."""
    from output.renderers.comparison import render_compare_email

    html_ohne, text_ohne = render_compare_email(_compare_result(False))
    html_mit, text_mit = render_compare_email(_compare_result(True))
    assert text_ohne.strip(), "Compare-Klartext ist leer -- Vergleich pruefte nichts"
    assert html_mit == html_ohne, "Compare-Mail-HTML aendert sich durch die GeoSphere-Rohwerte"
    assert text_mit == text_ohne, "Compare-Mail-Klartext aendert sich durch die GeoSphere-Rohwerte"


def test_ac9_briefing_mail_bleibt_mit_und_ohne_die_neuen_geosphere_rohwerte_identisch():
    """AC-9 (Kanal 4/4, Trip-Briefing-Mail): Given dasselbe Segment einmal mit
    und einmal ohne die GeoSphere-Rohwerte, When das Trip-Briefing (HTML +
    Klartext + Betreff) gerendert wird, Then sind alle drei Teile
    zeichengleich."""
    ohne = _briefing_mail(False)
    mit = _briefing_mail(True)
    assert ohne.email_html.strip(), "Briefing-HTML ist leer -- Vergleich pruefte nichts"
    assert mit.email_subject == ohne.email_subject, "Briefing-Betreff aendert sich durch die GeoSphere-Rohwerte"
    assert mit.email_html == ohne.email_html, "Briefing-HTML aendert sich durch die GeoSphere-Rohwerte"
    assert mit.email_plain == ohne.email_plain, "Briefing-Klartext aendert sich durch die GeoSphere-Rohwerte"
