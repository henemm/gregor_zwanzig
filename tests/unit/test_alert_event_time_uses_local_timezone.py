"""Abweichungs-Alarm: Ereigniszeit steht in ORTSZEIT, nicht in Weltzeit (#1386).

Der Alarm nennt je Ereignis eine Uhrzeit ("Wo & wann: … · HH:MM") und im
SMS-Kürzel `@HH`. Diese kam roh aus dem UTC-Zeitstempel des Spitzen-Datenpunkts
— für Mitteleuropa 1–2 h daneben, für Neuseeland ~12 h.

Testort ist Wellington/NZ (UTC+12 im Juli): Ortszeit und Weltzeit sind dort
unverwechselbar verschieden, ein zufälliges Grün durch gleiche Offsets ist
ausgeschlossen. Geprüft werden Trip- UND Ortsvergleich-Pfad, das SMS-Token,
der Bündel-`tz`-Fallback und naive Provider-Zeitstempel.

Kern-Schicht: kein Netz, keine Mocks, echte Katalog-/Detektor-Funktionen.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NZ_LAT, NZ_LON = -41.29, 174.78  # Wellington → Pacific/Auckland, im Juli UTC+12
PEAK_UTC_HOUR = 3      # 03:00 UTC …
PEAK_LOCAL = "15:00"   # … = 15:00 Ortszeit


def _build_data(*, aware: bool = True):
    """(old_data, new_data) für EINE Etappe in Neuseeland mit Wind-Peak 03:00 UTC.

    `aware` steuert die tzinfo des ETAPPEN-Fensters. Die Datenpunkte sind IMMER
    naiv-UTC — `ForecastDataPoint.__post_init__` strippt tzinfo als Hausnorm
    (#1345). Genau deshalb braucht die Peak-Zeit den UTC-Guard.
    """
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    start = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc if aware else None)
    segment = TripSegment(
        segment_id="1",
        start_point=GPXPoint(lat=NZ_LAT, lon=NZ_LON, elevation_m=10.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=NZ_LAT + 0.1, lon=NZ_LON + 0.1, elevation_m=120.0,
                           distance_from_start_km=9.0),
        start_time=start, end_time=start + timedelta(hours=6), duration_hours=6.0,
        distance_km=9.0, ascent_m=110.0, descent_m=0.0,
    )
    ts = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", run=start,
                          grid_res_km=1.0, interp="point_grid"),
        # Wind-Spitze exakt bei PEAK_UTC_HOUR, davor/danach niedriger.
        data=[ForecastDataPoint(ts=start + timedelta(hours=h), t2m_c=12.0,
                                wind10m_kmh=60.0 if h == PEAK_UTC_HOUR else 20.0 + h)
              for h in range(7)],
    )
    def _data(wind_max):
        return SegmentWeatherData(
            segment=segment, timeseries=ts, provider="openmeteo",
            aggregated=SegmentWeatherSummary(temp_max_c=12.0, wind_max_kmh=wind_max),
            fetched_at=datetime.now(timezone.utc),
        )
    return _data(10.0), _data(60.0)


def _wind_change(*, aware: bool = True):
    """Echten Detektor-Lauf fahren und den Wind-Change herausgreifen."""
    from services.weather_change_detection import WeatherChangeDetectionService
    old, new = _build_data(aware=aware)
    changes = WeatherChangeDetectionService().detect_changes(
        old, new, include_absolute=False
    )
    wind = [c for c in changes if c.metric == "wind_max_kmh"]
    assert wind, f"Wind-Change erwartet, bekam {[c.metric for c in changes]}"
    return wind[0], new


class _Point:
    """Vergleichs-Ort mit Koordinaten (Form wie PointWeatherData/Waypoint)."""

    def __init__(self, lat, lon):
        self.lat, self.lon = lat, lon


def test_trip_alert_event_time_and_sms_token_are_local():
    """Trip-Alarm: `occurred_at` UND SMS-`@HH` tragen die Ortszeit der Etappe."""
    from output.renderers.alert.project import to_alert_message
    from output.renderers.alert.render import render_sms

    change, new_data = _wind_change()
    # tz=UTC absichtlich: die Ortszeit MUSS aus den Etappen-Koordinaten kommen,
    # nicht aus dem mitgegebenen Bündel-tz.
    msg = to_alert_message([change], [new_data], "NZ-Trip",
                           tz=ZoneInfo("UTC"), stand_at="12:00")
    assert msg.events[0].occurred_at == PEAK_LOCAL, (
        f"Ereigniszeit muss Ortszeit {PEAK_LOCAL} sein (Peak {PEAK_UTC_HOUR:02d}:00 "
        f"UTC, Pacific/Auckland = UTC+12); bekam {msg.events[0].occurred_at!r}"
    )
    sms = render_sms(msg)
    assert f"@{PEAK_LOCAL[:2]}" in sms, (
        f"SMS muss die lokale Stunde @{PEAK_LOCAL[:2]} tragen; bekam {sms!r}"
    )
    assert f"@{PEAK_UTC_HOUR:02d}" not in sms, (
        f"SMS darf die Weltzeit-Stunde @{PEAK_UTC_HOUR:02d} nicht tragen: {sms!r}"
    )


def test_compare_alert_event_time_is_local_per_location():
    """Ortsvergleich (Einzel- und Mehr-Ort-Bündel): Ortszeit je Ort."""
    from output.renderers.alert.project import (
        to_multi_point_alert_message, to_point_alert_message,
    )

    change, _new_data = _wind_change()
    single = to_point_alert_message([change], [_Point(NZ_LAT, NZ_LON)], "Wellington",
                                    tz=ZoneInfo("UTC"), stand_at="12:00")
    assert single.events[0].occurred_at == PEAK_LOCAL, (
        f"Einzel-Ort: erwartet {PEAK_LOCAL}, bekam {single.events[0].occurred_at!r}"
    )
    bundle = to_multi_point_alert_message(
        [("Wellington", [change], _Point(NZ_LAT, NZ_LON)),
         ("Berlin", [change], _Point(52.52, 13.40))],
        tz=ZoneInfo("UTC"), stand_at="12:00",
    )
    by_loc = {e.location_label: e.occurred_at for e in bundle.events}
    assert by_loc == {"Wellington": PEAK_LOCAL, "Berlin": "05:00"}, (
        f"Je Ort eigene Ortszeit erwartet (Berlin UTC+2 im Juli); bekam {by_loc!r}"
    )


def test_compare_alert_falls_back_to_bundle_tz_without_coordinates():
    """Ohne Ortskoordinaten greift der `tz`-Parameter — er ist wirksam, nicht Zierde."""
    from output.renderers.alert.project import to_multi_point_alert_message

    change, _new_data = _wind_change()
    msg = to_multi_point_alert_message(
        [("Ohne Koordinaten", [change], _Point(None, None))],
        tz=ZoneInfo("Pacific/Auckland"), stand_at="12:00",
    )
    assert msg.events[0].occurred_at == PEAK_LOCAL, (
        f"Fallback-tz muss wirken; erwartet {PEAK_LOCAL}, "
        f"bekam {msg.events[0].occurred_at!r}"
    )


def test_naive_timestamp_yields_same_local_time_as_aware():
    """Naives Etappenfenster = derselbe Zeitpunkt wie der aware Zwilling.

    Provider-Zeitstempel sind naiv-UTC (Hausnorm #1345); das Etappenfenster ist
    je nach Aufrufer naiv ODER aware. Ohne UTC-Guard deutet `astimezone()` den
    naiven Wert als System-Lokalzeit (auf einem UTC-Server zufällig richtig,
    sonst falsch), und der naiv/aware-Fenstervergleich verstummt per TypeError
    zu `None`.
    """
    from output.renderers.alert.project import to_alert_message

    results = []
    for aware in (True, False):
        change, data = _wind_change(aware=aware)
        assert change.occurred_at is not None, (
            f"aware={aware}: Peak-Erkennung darf nicht verstummen"
        )
        msg = to_alert_message([change], [data], "NZ-Trip",
                               tz=ZoneInfo("UTC"), stand_at="12:00")
        results.append(msg.events[0].occurred_at)
    assert results == [PEAK_LOCAL, PEAK_LOCAL], (
        f"[aware, naiv] = {results!r}, erwartet beide {PEAK_LOCAL}"
    )
