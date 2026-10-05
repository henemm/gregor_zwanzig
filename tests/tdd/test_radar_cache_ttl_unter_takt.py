"""TDD RED — Epic #2261, Scheibe A-2 S2, AC-9: Radar-Cache-TTL 240 s.

SPEC: docs/specs/modules/feat_2261_a2s2_radar_takt.md AC-9, Abschnitt 5/7

Der Radar-Cache liest die Zeit NICHT selbst, sondern bekommt ``now`` als
Parameter (``RadarNowcastCacheService.get/put(..., now=...)``) — die Uhr ist
damit von Haus aus injizierbar, kein ``sleep`` und kein freezegun noetig.

Ein 239 s alter Eintrag ist ein Treffer, ein 241 s alter ein Fehltreffer
(TTL 240 s). Die Standard-TTL des geteilten Caches ist kleiner als der
5-Minuten-Takt (300 s), sonst bedient jeder zweite Lauf Altdaten.
RED heute: TTL 300 (Konstruktor ``:68`` und ``get_shared_radar_cache``
``:127``) ⇒ 241 s ist noch ein Treffer.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from providers.brightsky import RadarFrame
from services.radar_cache import (
    RadarNowcastCacheService,
    get_shared_radar_cache,
    reset_shared_radar_cache_for_tests,
)

LAT, LON, REGION = 47.3, 11.4, "inca"
T0 = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
TAKT_S = 300


def _frames() -> list:
    return [RadarFrame(timestamp=T0, precip_mm_h=1.0)]


def _treffer(cache, alter_s: float) -> bool:
    cache.put(LAT, LON, REGION, _frames(), "INCA", now=T0)
    return cache.get(LAT, LON, REGION, now=T0 + timedelta(seconds=alter_s)) is not None


def test_radar_cache_ttl_240_unter_takt():
    """AC-9: 239 s ⇒ Treffer, 241 s ⇒ Fehltreffer — am geteilten Cache, wie
    ihn ``RadarNowcastService`` im Alarmlauf benutzt (Singleton)."""
    reset_shared_radar_cache_for_tests()
    try:
        cache = get_shared_radar_cache()
        assert _treffer(cache, 239.0) is True, "239 s alter Eintrag muss ein Treffer sein"
        assert _treffer(cache, 241.0) is False, (
            "241 s alter Eintrag muss ein Fehltreffer sein (TTL 240 s)"
        )
    finally:
        reset_shared_radar_cache_for_tests()


def test_radar_cache_standard_ttl_des_konstruktors_ist_240():
    """AC-9: auch der Konstruktor-Default (nicht nur der Singleton) ist 240 s.
    Rueckmutation einer der beiden Stellen auf 300 wird rot."""
    cache = RadarNowcastCacheService()
    assert _treffer(cache, 239.0) is True
    assert _treffer(cache, 241.0) is False


def test_radar_cache_standard_ttl_kleiner_als_der_takt():
    """AC-9: Standard-TTL < Takt (300 s) — sonst bedient ein Folgelauf Altdaten."""
    reset_shared_radar_cache_for_tests()
    try:
        cache = get_shared_radar_cache()
        assert _treffer(cache, TAKT_S - 1.0) is False, (
            f"Ein {TAKT_S - 1} s alter Eintrag darf beim 5-Minuten-Takt nicht mehr bedient werden"
        )
    finally:
        reset_shared_radar_cache_for_tests()
