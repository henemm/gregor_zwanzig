"""
TDD-Tests für #925 — SMS-Stunden-Token deckungsgleich mit E-Mail-Tabelle.

Root-Cause: sms_trip.build_forecast baut EIN Sample je Etappe
(Etappen-Summe @ Etappen-Start). Die E-Mail zeigt per-Stunde. Daher
SMS R…@10 (Start+Summe) vs. E-Mail erster Regen @11.

Fix (Option A): SMS füttert per-Stunde-Samples aus seg.timeseries → Onset@h(Peak@h),
deckungsgleich mit der E-Mail.

KEINE Mocks. Echte Domänen-Objekte; SMS UND E-Mail aus DENSELBEN Segment-Daten.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


from app.models import (
    GPXPoint, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
    TripSegment, NormalizedTimeseries, ForecastDataPoint,
)

BERLIN = ZoneInfo("Europe/Berlin")


def _dp(hour_utc: int, precip: float, wind: float = 5.0, gust: float = 10.0,
        pop: float = 0.0) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, hour_utc, 0, tzinfo=timezone.utc),
        t2m_c=16.0, wind10m_kmh=wind, gust_kmh=gust, precip_1h_mm=precip,
        pop_pct=pop, cloud_total_pct=80, thunder_level=ThunderLevel.NONE,
        wind_chill_c=15.0,
    )


def _segment_rain_from_11() -> SegmentWeatherData:
    """Etappe startet 10:00 Ortszeit (08:00 UTC). Regen erst ab 11:00 Ortszeit.

    Lokale Stunden (Berlin = UTC+2 im Juli):
      08 UTC → 10:00  precip 0.0
      09 UTC → 11:00  precip 1.0   ← Onset
      10 UTC → 12:00  precip 3.0   ← Peak
      11 UTC → 13:00  precip 0.0
    """
    dps = [
        _dp(8, 0.0, wind=8, gust=14, pop=10),
        _dp(9, 1.0, wind=20, gust=33, pop=60),   # Onset Regen + Wind/Böen-Peak hier
        _dp(10, 3.0, wind=15, gust=25, pop=80),  # Regen-Peak
        _dp(11, 0.0, wind=10, gust=18, pop=40),
    ]
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.16, lon=11.84, elevation_m=840),
        end_point=GPXPoint(lat=47.07, lon=11.75, elevation_m=2100),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),   # 10:00 Berlin
        end_time=datetime(2026, 7, 11, 11, 0, tzinfo=timezone.utc),    # 13:00 Berlin
        duration_hours=3.0, distance_km=6.0, ascent_m=900, descent_m=0,
    )
    summary = SegmentWeatherSummary(
        temp_min_c=12.0, temp_max_c=18.0, temp_avg_c=15.0,
        wind_max_kmh=20.0, gust_max_kmh=33.0, precip_sum_mm=4.0,  # Summe der Stunden
        pop_max_pct=80, thunder_level_max=ThunderLevel.NONE,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(data=dps, meta=None),
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="test",
    )


def _sms_token_onset_hour(sms: str, symbol: str) -> int | None:
    """Onset-Stunde aus einem SMS-Token '{symbol}{val}@{h}...' ziehen."""
    m = re.search(rf'(?<![A-Z]){symbol}[-\d.]+@(\d+)', sms)
    return int(m.group(1)) if m else None


def _email_first_rain_hour(seg: SegmentWeatherData, threshold: float) -> int | None:
    """Erste Stunde der E-Mail-Tabelle, deren precip >= threshold (Ortszeit)."""
    from output.renderers.email.helpers import extract_hourly_rows
    from app.metric_catalog import build_default_display_config
    dc = build_default_display_config()
    rows = extract_hourly_rows(seg, dc, tz=BERLIN)
    for r in sorted(rows, key=lambda r: r["time"]):
        val = r.get("precip")
        if val is not None and float(val) >= threshold:
            return int(r["time"])
    return None


# ---------------------------------------------------------------------------
# AC-1: SMS-Regen-Onset ist die echte erste Regen-Stunde (11), nicht Etappenstart (10)
# ---------------------------------------------------------------------------

class TestAC1RainOnsetHour:
    def test_sms_rain_token_anchors_at_onset_not_segment_start(self):
        from output.renderers.sms_trip import SMSTripFormatter
        seg = _segment_rain_from_11()
        sms = SMSTripFormatter().format_sms([seg], tz=BERLIN, thresholds={"R": 0.2})
        onset = _sms_token_onset_hour(sms, "R")
        assert onset == 11, (
            f"SMS-Regen-Onset muss 11 (echte erste Regen-Stunde) sein, "
            f"nicht 10 (Etappenstart). SMS={sms!r}, onset={onset}"
        )


# ---------------------------------------------------------------------------
# AC-2: SMS-Onset == erste Regen-Stunde der E-Mail (kein Widerspruch)
# ---------------------------------------------------------------------------

class TestAC2SmsEmailConsistent:
    def test_sms_onset_matches_email_first_rain_hour(self):
        from output.renderers.sms_trip import SMSTripFormatter
        seg = _segment_rain_from_11()
        sms = SMSTripFormatter().format_sms([seg], tz=BERLIN, thresholds={"R": 0.2})
        sms_onset = _sms_token_onset_hour(sms, "R")
        email_onset = _email_first_rain_hour(seg, threshold=0.2)
        assert email_onset == 11, f"E-Mail erste Regen-Stunde sollte 11 sein: {email_onset}"
        assert sms_onset == email_onset, (
            f"SMS-Onset ({sms_onset}) muss mit E-Mail-erster-Regen-Stunde "
            f"({email_onset}) übereinstimmen. SMS={sms!r}"
        )


# ---------------------------------------------------------------------------
# AC-3: Wert ist der Stundenwert (Peak 3.0), nicht die Etappen-Summe (4.0)
# ---------------------------------------------------------------------------

class TestAC3HourlyValueNotSegmentSum:
    def test_rain_token_uses_hourly_value_not_segment_sum(self):
        from output.renderers.sms_trip import SMSTripFormatter
        seg = _segment_rain_from_11()
        sms = SMSTripFormatter().format_sms([seg], tz=BERLIN, thresholds={"R": 0.2})
        m = re.search(r'R[-\d.]+@\d+(?:\(([-\d.]+)@\d+\))?', sms)
        assert m, f"Kein Regen-Token gefunden: {sms!r}"
        # Etappen-Summe 4.0 darf NICHT als Token-Wert auftauchen
        assert "R4.0@" not in sms, (
            f"SMS darf nicht die Etappen-Summe 4.0 als Stundenwert zeigen: {sms!r}"
        )
        # Peak-Stundenwert 3.0 muss vorkommen (entweder als Onset- oder Peak-Wert)
        assert "3.0" in sms, f"Peak-Stundenwert 3.0 erwartet: {sms!r}"


# ---------------------------------------------------------------------------
# AC-4: Auch Wind/Böen aus per-Stunde-Samples (Onset, nicht Etappenstart)
# ---------------------------------------------------------------------------

class TestAC4WindGustHourly:
    def test_gust_peak_anchored_at_real_hour_not_segment_start(self):
        from output.renderers.sms_trip import SMSTripFormatter
        seg = _segment_rain_from_11()
        # Böen-Peak (33) liegt bei 11:00 Ortszeit. Alt: G33@10 (Etappenstart).
        # Neu (per-Stunde): Peak-Wert 33 an echter Stunde 11 → '33@11' im Token.
        sms = SMSTripFormatter().format_sms([seg], tz=BERLIN)
        assert "33@11" in sms, (
            f"Böen-Peak 33 muss an der echten Spitzenstunde 11 verankert sein "
            f"(per-Stunde), nicht am Etappenstart. SMS={sms!r}"
        )
        assert "G33@10" not in sms, (
            f"Böen-Token darf den Peak nicht am Etappenstart (10) zeigen: {sms!r}"
        )
