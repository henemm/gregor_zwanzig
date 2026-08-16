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


def test_wind_chill_erzeugt_kein_wc_token_mehr():
    """Fix #1887 E6 Scheibe A (PO-Entscheid, docs/specs/modules/
    fix_1887_e6a_sms_kuerzel_register.md, AC-4): 'WC' entfaellt ERSATZLOS --
    es verdoppelte nachweislich den Wert von 'FK' (identisches Feld, Fenster,
    Aggregation). Diese Testfassung loest den urspruenglichen Bug-#1450-
    Nachweis ab (der bewies, dass WC bei aktiver Metrik erscheint) mit dem
    umgekehrten Positivnachweis: 'wind_chill' aktiv + gefuehlte Temperatur
    vorhanden -> KEIN 'WC'-Token im SMS-Text, unabhaengig von der
    Metrik-Auswahl (die Zahl selbst bleibt ueber FK/FD sichtbar, s.
    test_felt_night_own_metric_selection.py)."""
    from output.renderers.sms_trip import SMSTripFormatter

    segments = [_felt_temp_segment()]
    formatter = SMSTripFormatter()

    sms = formatter.format_sms(segments, stage_name="Etappe 1")

    assert "WC" not in sms, (
        f"'WC'-Token erscheint weiterhin trotz PO-Entscheid, das Kuerzel "
        f"ersatzlos zu entfernen (verdoppelte 'FK'): {sms!r}"
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
