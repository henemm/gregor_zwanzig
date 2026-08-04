"""TDD RED — #1457 S2b AC-8: die neuen Rohwerte aendern KEINE Ausgabe.

Spec: docs/specs/modules/feat_1457_s2b_gewitter_dwd_alpen.md (AC-8)

Diese Scheibe liefert ausschliesslich ROHWERTE ins Datenmodell. Die
Stufenbildung (Schwellenwerte fuer das Blitzpotenzial) baut eine andere
Scheibe (#1474, parallele Session). Faengt schon hier eine bestehende
Einstufungs- oder Renderfunktion an, die neuen Felder mitzulesen, entstehen
zwei konkurrierende Gewitter-Aussagen — und der Nutzer bekaeme unter
Umstaenden fuer denselben Tag zwei verschiedene Warnungen.

Bauart des Nachweises: dieselbe Vorhersage wird zweimal gerendert — einmal
ohne die neuen Felder, einmal mit ABSICHTLICH EXTREMEN Werten
(Blitzpotenzial 250 J/kg, das ist oberhalb des hoechsten am 2026-08-03 im
ganzen ICON-D2-Gebiet gemessenen Wertes von 225). Wuerde irgendeine
bestehende Funktion sie mitlesen, muesste sich die Ausgabe unterscheiden.
Ein unauffaelliger Wert wuerde diesen Beweis nicht tragen.

RED-GRUND (heute, unveraenderter Code): `ForecastDataPoint` kennt weder
`lightning_potential_lpi_jkg` noch `hail_potential_grau_gsp` -> TypeError
beim Bauen des Vergleichsfalls.

Testart: Kern-Schicht, keine Netzzugriffe, keine Mocks.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.app.models import (  # noqa: E402
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from src.output.renderers.sms_trip import SMSTripFormatter  # noqa: E402
from src.services.weather_metrics import WeatherMetricsService  # noqa: E402

_JAHR, _MONAT, _TAG = 2026, 8, 4
_TZ = ZoneInfo("UTC")
_START_H, _ENDE_H = 7, 17

# Absichtlich extrem: hoeher als der hoechste am 2026-08-03 im gesamten
# ICON-D2-Gebiet gemessene Wert (225,2 J/kg). Wuerde eine bestehende
# Einstufung diesen Wert lesen, schluege sie mit Sicherheit an.
_EXTREMES_BLITZPOTENZIAL = 250.0
_EXTREMER_HAGELWERT = 12.0


def _dp(stunde: int, thunder: ThunderLevel, **neue_felder) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(_JAHR, _MONAT, _TAG, stunde, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.0,
        cloud_total_pct=50, thunder_level=thunder, humidity_pct=55,
        **neue_felder,
    )


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(_JAHR, _MONAT, _TAG, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )


def _reihe(mit_neuen_feldern: bool) -> NormalizedTimeseries:
    """24 Stunden mit einem MED-Gewitter um 09:00 und HIGH um 14:00 — so
    tragen die Ausgaben ueberhaupt eine Gewitteraussage, an der eine
    Verfaelschung sichtbar wuerde."""
    stufen = {9: ThunderLevel.MED, 14: ThunderLevel.HIGH}
    neu = (
        {"lightning_potential_lpi_jkg": _EXTREMES_BLITZPOTENZIAL,
         "hail_potential_grau_gsp": _EXTREMER_HAGELWERT}
        if mit_neuen_feldern else {}
    )
    daten = [_dp(h, stufen.get(h, ThunderLevel.NONE), **neu) for h in range(24)]
    return NormalizedTimeseries(meta=_meta(), data=daten)


def _segment(mit_neuen_feldern: bool) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=46.40, lon=12.52, elevation_m=1800.0),
        end_point=GPXPoint(lat=46.45, lon=12.60, elevation_m=2100.0),
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
        provider="openmeteo",
    )


def _sms(mit_neuen_feldern: bool) -> str:
    return SMSTripFormatter().format_sms(
        [_segment(mit_neuen_feldern)],
        stage_name="Karnisch-1", report_type="morning", tz=_TZ,
    )


def test_ac8_sms_text_bleibt_mit_und_ohne_die_neuen_rohwerte_identisch():
    """AC-8: Given dieselbe Vorhersage einmal mit und einmal ohne gesetzte
    Blitzpotenzial-/Hagel-Rohwerte, When die SMS gerendert wird, Then ist der
    Text zeichengleich.

    Gegenprobe: Fliesst eines der neuen Felder in die SMS-Gewitteraussage ein,
    muss dieser Test rot werden.
    """
    ohne = _sms(False)
    mit = _sms(True)

    assert "TH:" in ohne, (
        f"Die SMS traegt gar keine Gewitteraussage — der Vergleich wuerde "
        f"nichts pruefen.\nSMS: {ohne}"
    )
    assert mit == ohne, (
        "Die SMS aendert sich, sobald Blitzpotenzial/Hagel gesetzt sind. Diese "
        "Scheibe liefert nur Rohwerte; die Stufenbildung baut #1474.\n"
        f"ohne: {ohne}\nmit : {mit}"
    )


def test_ac8_gewitterstufe_bleibt_mit_und_ohne_die_neuen_rohwerte_identisch():
    """AC-8: Given dieselbe Zeitreihe mit und ohne die neuen Rohwerte, When
    die Gewitterstufe aggregiert wird, Then ist sie identisch.

    Die Gewitterstufe kommt heute allein aus `weather_code` (openmeteo.py:821).
    Wuerde das Blitzpotenzial hier mitgerechnet, entstuende eine zweite,
    konkurrierende Gewitter-Quelle im selben Briefing — genau das verbietet
    ADR-0025 ("eine Gewitter-Quelle fuer alle Briefing-Kanaele").
    """
    dienst = WeatherMetricsService()
    ohne = dienst._compute_thunder_level(_reihe(False))
    mit = dienst._compute_thunder_level(_reihe(True))

    assert ohne is not None, "Ohne die neuen Felder kommt gar keine Stufe heraus"
    assert mit == ohne, (
        f"Die Gewitterstufe aendert sich von {ohne} auf {mit}, sobald das "
        "Blitzpotenzial gesetzt ist — es fliesst in eine bestehende "
        "Einstufung ein"
    )


def test_ac8_datenpunkt_gewitterstufe_bleibt_unberuehrt():
    """AC-8, feinste Ebene: Given einen Datenpunkt mit extremem
    Blitzpotenzial, aber `thunder_level = NONE`, When die Reihe gebaut wird,
    Then bleibt seine Gewitterstufe NONE.

    Faengt irgendeine Stelle an, aus dem Rohwert eine Stufe abzuleiten,
    widerspraeche sie dem `weather_code` derselben Stunde.
    """
    reihe = _reihe(True)
    stille_stunden = [
        dp for dp in reihe.data
        if dp.ts.hour not in (9, 14)
    ]
    assert stille_stunden, "Keine Vergleichsstunde vorhanden"
    assert all(dp.thunder_level == ThunderLevel.NONE for dp in stille_stunden), (
        "Eine Stunde ohne Gewitter im `weather_code` traegt trotzdem eine "
        "Gewitterstufe — der Rohwert wurde in eine Stufe uebersetzt: "
        f"{[(dp.ts.hour, dp.thunder_level) for dp in stille_stunden if dp.thunder_level != ThunderLevel.NONE]}"
    )
    assert all(
        dp.lightning_potential_lpi_jkg == _EXTREMES_BLITZPOTENZIAL
        for dp in stille_stunden
    ), "Der Rohwert steht gar nicht am Datenpunkt — der Test prueft nichts"
