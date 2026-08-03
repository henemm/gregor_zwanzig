"""Touren-SMS: Wintersport-Metriken folgen der normalen Metrik-Sichtbarkeit.

SPEC: docs/specs/fast/fix-1450-sms-wintersport-tokens.md (#1450)

Bug: `build_token_line()` erzeugte den Wintersport-Token-Block (SD/NS24+/SL/
AV/WC) nur wenn `profile == "wintersport"`. Der einzige Produktiv-Aufrufer
(`SMSTripFormatter.format_sms()` -> `trip_report.py`) hat `profile` nie
übergeben -> der Block lief NIE, egal was im Trip-Editor aktiviert war.

PO-Entscheidung: keine Sonderbehandlung nach Trip-Typ. Diese Werte verhalten
sich wie jede andere Metrik -- Sichtbarkeit steuert allein `_visible()`
(enabled/threshold), kein Profil-Flag.

Bug-Nachweis: Trip/Segment mit Schneedaten (snow_depth_cm > 0), Metrik SD
aktiviert (kein disabled_specs-Eintrag) -> das SD-Token MUSS im gerenderten
SMS-Text erscheinen.

KEIN Mock — echte SegmentWeatherData, echter SMSTripFormatter, echter
Aufrufpfad über format_sms() (NICHT direkt _wintersport()).
"""
from datetime import datetime, timezone

import pytest

from app.models import (
    GPXPoint,
    NormalizedTimeseries,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)


def _snow_segment(
    segment_id: int = 1,
    temp_min: float = -3.0,
    temp_max: float = 2.0,
    wind_max: float = 20.0,
    precip_sum: float = 4.0,
    snow_depth_cm: float = 45.0,
) -> SegmentWeatherData:
    """Echtes SegmentWeatherData mit Schneedaten (snow_depth_cm > 0)."""
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=2100),
        start_time=datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0,
        distance_km=6.0,
        ascent_m=600,
        descent_m=0,
    )

    summary = SegmentWeatherSummary(
        temp_min_c=temp_min,
        temp_max_c=temp_max,
        temp_avg_c=(temp_min + temp_max) / 2,
        wind_max_kmh=wind_max,
        precip_sum_mm=precip_sum,
        thunder_level_max=ThunderLevel.NONE,
        snow_depth_cm=snow_depth_cm,
    )

    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(data=[], meta=None),
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="test",
    )


def _felt_temp_segment(
    segment_id: int = 1,
    temp_min: float = -5.0,
    temp_max: float = 1.0,
    wind_max: float = 30.0,
    precip_sum: float = 0.0,
    wind_chill_min: float = -12.0,
    wind_chill_max: float = -4.0,
) -> SegmentWeatherData:
    """Echtes SegmentWeatherData mit gefuehlter Temperatur (wind_chill_min_c/
    wind_chill_max_c), aber leerer Stunden-Zeitreihe -- fail-soft-Pfad
    (`_agg("wind_chill_min_c", "wind_chill_max_c")`), analog `_snow_segment`."""
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=2100),
        start_time=datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0,
        distance_km=6.0,
        ascent_m=600,
        descent_m=0,
    )

    summary = SegmentWeatherSummary(
        temp_min_c=temp_min,
        temp_max_c=temp_max,
        temp_avg_c=(temp_min + temp_max) / 2,
        wind_max_kmh=wind_max,
        precip_sum_mm=precip_sum,
        thunder_level_max=ThunderLevel.NONE,
        wind_chill_min_c=wind_chill_min,
        wind_chill_max_c=wind_chill_max,
    )

    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(data=[], meta=None),
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="test",
    )


def test_enabled_wind_chill_appears_in_sms_as_wc():
    """Bug #1450 Nachweis (WC): Metrik `wind_chill` aktiviert (keine
    disabled_specs), Segment liefert eine gefuehlte Tiefst-/Hoechsttemperatur
    -> das WC-Token MUSS im SMS-Text erscheinen.

    Vor dem Fix: `DailyForecast.wind_chill_c` wurde in
    `_segments_to_normalized_forecast()` nie gesetzt (blieb None) ->
    `_wintersport()` liess WC IMMER aus, unabhaengig von der Metrik-Auswahl.
    Nach dem Fix: WC nutzt den bereits berechneten Gehzeit-Tiefstwert (FK-
    Quelle) als Tages-Einzelwert.
    """
    from output.renderers.sms_trip import SMSTripFormatter

    segments = [_felt_temp_segment()]
    formatter = SMSTripFormatter()

    sms = formatter.format_sms(segments, stage_name="Etappe 1")

    assert "WC" in sms, (
        f"Bug #1450: 'WC'-Token fehlt trotz aktivierter Metrik 'wind_chill' "
        f"und vorhandener gefuehlter Temperatur (day.wind_chill_c blieb "
        f"unbefuellt): {sms!r}"
    )


def test_enabled_snow_depth_appears_in_sms():
    """Bug #1450 Nachweis: SD-Metrik im Trip aktiviert (keine disabled_specs),
    Vorhersage hat Schneedaten -> das SD-Token MUSS im SMS-Text erscheinen.

    Vor dem Fix: kein TypeError, aber SD fehlt (Profil-Gate blockierte den
    Wintersport-Block, da `format_sms()` `profile` nie übergibt). Nach dem
    Fix: SD steht im Text, gesteuert allein durch die Metrik-Auswahl.
    """
    from output.renderers.sms_trip import SMSTripFormatter

    segments = [_snow_segment()]
    formatter = SMSTripFormatter()

    sms = formatter.format_sms(segments, stage_name="Etappe 1")

    assert "SD" in sms, (
        f"Bug #1450: 'SD'-Token fehlt trotz aktivierter Schneehoehe-Metrik "
        f"und vorhandener Schneedaten (kein Profil-Sonderweg mehr erlaubt): {sms!r}"
    )


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
