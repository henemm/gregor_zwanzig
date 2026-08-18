"""TDD RED — Issue #1945: Nowcast-Horizont auf 180 Minuten anheben.

Spec: docs/specs/modules/fix_1945_nowcast_horizon.md

KEINE MOCKS: echte `RadarFrame`-Objekte gegen den echten
`RadarNowcastService._derive_result()` mit injiziertem `now`.

In der RED-Phase schlagen die Tests fehl, weil `_NOWCAST_HORIZON_MIN` noch 60
ist: ein nasser Frame in 90 Minuten liegt ausserhalb des Fensters, der Alarm
bleibt aus (`onset_minutes is None`) — genau das Nutzersymptom aus #1945.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _frames(now: datetime, wet_offsets: tuple[int, ...]):
    """Trockene 15-Min-Raster-Frames ueber 4 Stunden, nass nur bei wet_offsets."""
    from providers.brightsky import RadarFrame  # noqa: PLC0415

    return [
        RadarFrame(
            timestamp=now + timedelta(minutes=offset),
            precip_mm_h=(2.0 if offset in wet_offsets else 0.0),
            is_convective=False,
        )
        for offset in range(0, 241, 5)
    ]


def test_ac1_nowcast_horizon_is_180_minutes():
    """AC-1: Der oeffentliche Horizont-Wert ist 180, nicht mehr 60."""
    from services import radar_service

    assert radar_service.NOWCAST_HORIZON_MIN == 180


def test_ac2_onset_at_90_minutes_is_detected():
    """AC-2: Nasser Frame in 90 Minuten -> onset_minutes == 90 statt None."""
    from services.radar_service import RadarNowcastService

    now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
    result = RadarNowcastService()._derive_result(
        _frames(now, wet_offsets=(90,)), "test-source", now=now
    )

    assert result.onset_minutes == 90


def test_ac3_frame_beyond_180_minutes_stays_outside_window():
    """AC-3: Frame bei 200 Min bleibt draussen, onset bleibt der 90-Min-Frame."""
    from services.radar_service import RadarNowcastService

    now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
    result = RadarNowcastService()._derive_result(
        _frames(now, wet_offsets=(90, 200)), "test-source", now=now
    )

    assert result.onset_minutes == 90

    only_far = RadarNowcastService()._derive_result(
        _frames(now, wet_offsets=(200,)), "test-source", now=now
    )
    assert only_far.onset_minutes is None
