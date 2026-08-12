"""
RED-Tests fuer 3 Formatierungsfehler im kanonischen Alert-Renderer (render.py).

Bug 1: _km_str() produziert "km 0 km-11 km" statt "km 0-11 km"
Bug 2: SMS-Tripname <= 16 Zeichen schneidet mid-char (offene Klammer)
Bug 3: Telegram-Zeilen haben mehrfache Leerzeichen als Trennzeichen
"""
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, ".")
sys.path.insert(0, "src")


from app.models import WeatherChange, ChangeSeverity, SegmentWeatherData, SegmentWeatherSummary, TripSegment, GPXPoint
from output.renderers.alert.project import to_alert_message
from output.renderers.alert.render import render_subject, render_telegram, render_sms


def _local(h: int, m: int, now: datetime) -> datetime:
    """Ortszeit (Mallorca) → UTC-Zeitpunkt. Issue #1386: `WeatherChange.
    occurred_at` traegt den rohen UTC-Zeitpunkt, die Ortszeit entsteht erst in
    der Projektion aus den Etappen-Koordinaten."""
    return datetime(
        now.year, now.month, now.day, h, m, tzinfo=ZoneInfo("Europe/Madrid"),
    ).astimezone(timezone.utc)


def _make_msg(trip_name: str = "GR221 Mallorca", segment_id: str | None = "1"):
    """Issue #1744 A1: `segment_id=None` erzwingt den km-Rueckfall (Altdaten
    ohne Etappen-Kennung) — nur dort ist das km-Format ueberhaupt noch im
    Betreff/Telegram sichtbar, und nur dort kann Bug 1 also noch auftreten."""
    tz = ZoneInfo("Europe/Madrid")
    now = datetime.now(timezone.utc)
    seg_start = datetime(now.year, now.month, now.day, 8, 0, tzinfo=timezone.utc)
    seg_end   = datetime(now.year, now.month, now.day, 13, 30, tzinfo=timezone.utc)
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=39.710564, lon=2.62293, elevation_m=410, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=39.747657, lon=2.648606, elevation_m=149, distance_from_start_km=11.2),
        start_time=seg_start, end_time=seg_end,
        duration_hours=5.5, distance_km=11.2, ascent_m=385.0, descent_m=646.0,
    )
    weather_data = SegmentWeatherData(
        segment=segment, timeseries=None,
        aggregated=SegmentWeatherSummary(wind_max_kmh=55.0, precip_sum_mm=8.5),
        fetched_at=now, provider="openmeteo",
    )
    changes = [
        WeatherChange(
            metric="wind_max_kmh", old_value=25.0, new_value=55.0, delta=30.0,
            threshold=20.0, severity=ChangeSeverity.MAJOR, direction="increase",
            segment_id="1", occurred_at=_local(11, 0, now),
        ),
        WeatherChange(
            metric="precip_sum_mm", old_value=1.0, new_value=8.5, delta=7.5,
            threshold=5.0, severity=ChangeSeverity.MODERATE, direction="increase",
            segment_id="1", occurred_at=_local(10, 30, now),
        ),
    ]
    return to_alert_message(changes, [weather_data], trip_name, tz=tz, stand_at="10:00")


class TestKmStrNoDuplicatedUnit:
    """Bug 1: km_span darf km nicht doppelt im String haben.

    Issue #1744 A1: Betreff und Telegram nennen den Ort seither als
    Etappen-Kennung ("Segment 1"); die km-Spanne ist der RUECKFALL fuer Alarme
    ohne Kennung. Alle drei Faelle laufen deshalb ueber `segment_id=None` —
    sonst pruefte diese Klasse ein Format, das gar nicht mehr gerendert wird
    (die beiden "kein doppeltes km"-Zusicherungen waeren trivial erfuellt).
    """

    def test_subject_no_km_km(self):
        msg = _make_msg(segment_id=None)
        subj = render_subject(msg)
        assert "0 km-" not in subj and "0 km–" not in subj, f"Doppeltes km im Betreff: {subj!r}"

    def test_subject_contains_km_range(self):
        msg = _make_msg(segment_id=None)
        subj = render_subject(msg)
        assert "km 0–11" in subj, f"Km-Bereich fehlt im Betreff: {subj!r}"

    def test_telegram_no_km_km(self):
        msg = _make_msg(segment_id=None)
        tg = render_telegram(msg)
        assert "0 km–" not in tg, f"Doppeltes km in Telegram: {tg!r}"

    def test_subject_names_the_segment_when_known(self):
        """Issue #1744 A1: mit Kennung nennt der Betreff die Etappe statt km —
        die Gegenprobe zum Rueckfall oben."""
        subj = render_subject(_make_msg())
        assert "Segment 1" in subj, f"Ortsangabe fehlt im Betreff: {subj!r}"
        assert "km 0–11" not in subj, f"km-Spanne trotz Kennung: {subj!r}"


class TestSmsTripNameTruncation:
    """Bug 2: SMS-Tripname darf nicht mit offener Klammer enden."""

    def test_sms_no_dangling_paren(self):
        msg = _make_msg("GR221 Mallorca (Test-Tour)")
        sms = render_sms(msg)
        # Trip-Teil endet vor dem " km"-Spann-Abschnitt
        trip_part = sms.split(" km")[0].rstrip()
        assert not trip_part.endswith("("), f"Offene Klammer in SMS: {sms!r}"


class TestTelegramNoMultipleSpaces:
    """Bug 3: Telegram-Zeilen sollen keine Mehrfach-Leerzeichen enthalten."""

    def test_no_triple_space(self):
        msg = _make_msg()
        tg = render_telegram(msg)
        assert "   " not in tg, f"Dreifach-Leerzeichen in Telegram: {tg!r}"

    def test_no_double_space(self):
        msg = _make_msg()
        tg = render_telegram(msg)
        assert "  " not in tg, f"Doppel-Leerzeichen in Telegram: {tg!r}"
