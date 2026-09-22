"""TDD RED — Issue #1761: Korsika im Radar-Nowcast auf AROME-FR statt ARPAE,
Gewitter-/Hagel-Erkennung per ARPAE-Sidecar-Merge.

Spec: docs/specs/modules/fix_1761_korsika_arome_sidecar.md

Bisher liegt Korsika komplett innerhalb der (groesseren) Italien-Radar-Box, die
in `_fetch_frames_with_fallback`/`_region_bucket` VOR der Frankreich-Box gefragt
wird -- eine reine Reihenfolge-Nebenwirkung, keine fachliche Entscheidung
(#1648). AROME-FR liefert an Korsika-Koordinaten strukturell KEINEN
`weather_code` (Live-Befund 2026-09-20) -- die Gewitter-/Hagel-Erkennung wird
deshalb per Sidecar-Merge aus ARPAE ICON-2I ergaenzt (PO-Entscheidung
2026-09-20, analog zum bestehenden INCA+Sidecar-Muster `_merge_convective`).

KEINE MOCKS. DI erfolgt ausschliesslich durch Ersetzen von Instanzmethoden mit
echten Python-Funktionen, die reale `RadarFrame`-Objekte zurueckgeben — kein
`Mock()`/`patch()`/`MagicMock` (Muster aus test_issue_1161_inca_convective.py).

In der RED-Phase schlagen alle Tests fehl, weil:
- `_within_corsica` noch nicht existiert (AttributeError),
- `_region_bucket` "corsica" noch nicht kennt (liefert "italy_radar"),
- `RadarNowcastService._fetch_corsica_arome_fr` noch nicht existiert (AttributeError),
- `_fetch_frames_with_fallback` fuer Korsika-Koordinaten direkt in den
  Italien-Zweig geht, OHNE `_fetch_arome_france_hd` ueberhaupt aufzurufen.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# sys.path absichern: sowohl `services.*` als auch `src.services.*` Importpfade.
_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Vizzavona (GR20, Korsika) -- liegt in BEIDEN Boxen (Italien UND AROME-FR).
_VIZZAVONA_LAT, _VIZZAVONA_LON = 42.1244, 9.1339
# Conca (GR20-Ostkueste, Korsika-Endpunkt) -- eigener Geometrie-Testfall
# (Analyse-Risiko: fehlende Bbox im Vorgaengerprojekt an genau diesem Punkt).
_CONCA_LAT, _CONCA_LON = 41.7481, 9.3548
# Straße von Bonifacio: knapp NOERDLICH der Trennlinie = Korsika (inklusiv).
_BONIFACIO_NORTH_LAT, _BONIFACIO_LON = 41.30, 9.00
# Knapp SUEDLICH der Trennlinie = Sardinien (Italien), AUSSERHALB der Korsika-Box.
_BONIFACIO_SOUTH_LAT = 41.29


# ===========================================================================
# AC-4: _region_bucket und _within_corsica muessen synchron "Korsika" liefern
# ===========================================================================

@pytest.mark.parametrize(
    "lat,lon,label",
    [
        (_VIZZAVONA_LAT, _VIZZAVONA_LON, "Vizzavona"),
        (_CONCA_LAT, _CONCA_LON, "Conca (GR20-Ostkueste)"),
    ],
)
def test_ac4_region_bucket_matches_within_corsica(lat, lon, label):
    """AC-4: fuer dieselbe Korsika-Koordinate liefern `_region_bucket` UND
    `_within_corsica` konsistent "Korsika" -- Cache-Schluessel und tatsaechlich
    abgerufene Quelle duerfen nicht divergieren (Adversary-Risiko: nur eine
    der beiden Stellen geaendert)."""
    import services.radar_service as rs

    within_corsica = getattr(rs, "_within_corsica", None)
    assert callable(within_corsica), "_within_corsica muss existieren"
    assert within_corsica(lat, lon) is True, f"{label} muss innerhalb der Korsika-Box liegen"

    assert rs._region_bucket(lat, lon) == "corsica", (
        f"{label}: _region_bucket muss 'corsica' liefern (war: {rs._region_bucket(lat, lon)!r})"
    )


# ===========================================================================
# AC-5: Grenzlinie Straße von Bonifacio -- Sardinien wird NICHT mitgenommen
# ===========================================================================

def test_ac5_sardinia_boundary_excluded():
    """AC-5: unmittelbar nördlich der Straße von Bonifacio (41,30 N) liegt
    Korsika (inklusiv), unmittelbar südlich (41,29 N) liegt Sardinien/Italien
    -- nur die nördliche Koordinate wird als Korsika geroutet."""
    import services.radar_service as rs

    within_corsica = getattr(rs, "_within_corsica", None)
    assert callable(within_corsica), "_within_corsica muss existieren"

    assert within_corsica(_BONIFACIO_NORTH_LAT, _BONIFACIO_LON) is True, (
        "41,30 N muss noch als Korsika gelten (Grenze inklusiv)"
    )
    assert rs._region_bucket(_BONIFACIO_NORTH_LAT, _BONIFACIO_LON) == "corsica"

    assert within_corsica(_BONIFACIO_SOUTH_LAT, _BONIFACIO_LON) is False, (
        "41,29 N (Sardinien) darf NICHT als Korsika gelten"
    )
    assert rs._region_bucket(_BONIFACIO_SOUTH_LAT, _BONIFACIO_LON) == "italy_radar", (
        "Sardinien muss unveraendert im Italien-Bucket bleiben"
    )


# ===========================================================================
# AC-2: Sidecar-Merge -- AROME-Frame ohne weather_code uebernimmt
#       is_convective/hail vom ARPAE-Sidecar
# ===========================================================================

def test_ac2_sidecar_merges_convective_from_arpae():
    """AC-2: ein AROME-FR-Frame ohne weather_code (strukturell, echter
    Live-Fall) uebernimmt is_convective/hail vom zeitlich naechsten
    ARPAE-Sidecar-Frame (Toleranz 5 Min, wiederverwendet aus
    `_merge_convective`)."""
    from providers.brightsky import RadarFrame
    from services.radar_service import RadarNowcastService

    ts = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)

    def fake_arome(self, lat, lon, elevation_m=None):
        # AROME-FR liefert Niederschlag, aber KEIN Konvektions-Signal
        # (strukturell fehlender weather_code an Korsika-Koordinaten).
        return [RadarFrame(timestamp=ts, precip_mm_h=3.0, is_convective=False, hail=False)]

    def fake_arpae(self, lat, lon, elevation_m=None):
        # ARPAE fuehrt weather_code nativ -- hier WMO 96 (Gewitter mit Hagel).
        return [RadarFrame(timestamp=ts + timedelta(minutes=2), precip_mm_h=5.0, is_convective=True, hail=True)]

    svc = RadarNowcastService()
    fetch_corsica = getattr(svc, "_fetch_corsica_arome_fr", None)
    assert callable(fetch_corsica), "_fetch_corsica_arome_fr muss existieren"

    orig_arome = RadarNowcastService._fetch_arome_france_hd
    orig_arpae = RadarNowcastService._fetch_italy_arpae
    RadarNowcastService._fetch_arome_france_hd = fake_arome
    RadarNowcastService._fetch_italy_arpae = fake_arpae
    try:
        frames = svc._fetch_corsica_arome_fr(_VIZZAVONA_LAT, _VIZZAVONA_LON)
        assert len(frames) == 1
        assert frames[0].precip_mm_h == pytest.approx(3.0), (
            "Niederschlag muss aus AROME-FR stammen, nicht aus dem Sidecar"
        )
        assert frames[0].is_convective is True, (
            "is_convective muss aus dem ARPAE-Sidecar uebernommen werden"
        )
        assert frames[0].hail is True, (
            "hail muss aus dem ARPAE-Sidecar uebernommen werden"
        )
    finally:
        RadarNowcastService._fetch_arome_france_hd = orig_arome
        RadarNowcastService._fetch_italy_arpae = orig_arpae


# ===========================================================================
# AC-3: Sidecar-Ausfall -> convective_checked=False (ADR-0018), kein
#       stilles "kein Gewitter"
# ===========================================================================

def test_ac3_sidecar_failure_sets_convective_checked_false():
    """AC-3: liefert AROME-FR Niederschlags-Frames, aber der ARPAE-Sidecar-
    Fetch liefert [] (simulierter Ausfall), bleiben die AROME-Frames
    erhalten, aber `_convective_checked` wird False -- kein stilles
    "kein Gewitter" (ADR-0018 Nicht-Kaschieren-Invariante)."""
    from providers.brightsky import RadarFrame
    from services.radar_service import RadarNowcastService

    ts = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)

    def fake_arome(self, lat, lon, elevation_m=None):
        return [RadarFrame(timestamp=ts, precip_mm_h=1.5, is_convective=False)]

    def failing_arpae(self, lat, lon, elevation_m=None):
        # Realer Fail-Soft-Vertrag: leere Liste bei Fehler.
        return []

    svc = RadarNowcastService()
    fetch_corsica = getattr(svc, "_fetch_corsica_arome_fr", None)
    assert callable(fetch_corsica), "_fetch_corsica_arome_fr muss existieren"

    orig_arome = RadarNowcastService._fetch_arome_france_hd
    orig_arpae = RadarNowcastService._fetch_italy_arpae
    RadarNowcastService._fetch_arome_france_hd = fake_arome
    RadarNowcastService._fetch_italy_arpae = failing_arpae
    try:
        frames = svc._fetch_corsica_arome_fr(_VIZZAVONA_LAT, _VIZZAVONA_LON)
        assert len(frames) == 1, "AROME-Niederschlags-Frames bleiben trotz Sidecar-Fail erhalten"
        assert frames[0].precip_mm_h == pytest.approx(1.5)
        assert svc._convective_checked is False, (
            "Ein gescheiterter Sidecar-Call darf NICHT lautlos als 'kein Gewitter' gelten"
        )
    finally:
        RadarNowcastService._fetch_arome_france_hd = orig_arome
        RadarNowcastService._fetch_italy_arpae = orig_arpae


# ===========================================================================
# AC-6: AROME-FR-Ausfall -> Kette faellt auf den vollen Italien-Zweig zurueck
# ===========================================================================

def test_ac6_arome_failure_falls_back_to_arpae():
    """AC-6: schlaegt AROME-FR fuer eine Korsika-Koordinate fehl (leere
    Antwort), faellt `_fetch_frames_with_fallback` auf den vollen
    Italien-Zweig zurueck (`source == "ARPAE-2I"`), NICHT direkt auf
    `minutely_15` -- dieselbe Ausfalltiefe wie vor der Aenderung. Zusaetzlich
    belegt, dass `_fetch_arome_france_hd` fuer Korsika ueberhaupt zuerst
    versucht wird (heute: 0 Aufrufe, weil der Italien-Zweig zuerst greift)."""
    from providers.brightsky import RadarFrame
    from services.radar_service import RadarNowcastService

    ts = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
    arome_calls: list[tuple[float, float]] = []
    arpae_calls: list[tuple[float, float]] = []

    def failing_arome(self, lat, lon, elevation_m=None):
        arome_calls.append((lat, lon))
        return []

    def fake_arpae(self, lat, lon, elevation_m=None):
        arpae_calls.append((lat, lon))
        return [RadarFrame(timestamp=ts, precip_mm_h=2.0, is_convective=False)]

    svc = RadarNowcastService()
    orig_arome = RadarNowcastService._fetch_arome_france_hd
    orig_arpae = RadarNowcastService._fetch_italy_arpae
    RadarNowcastService._fetch_arome_france_hd = failing_arome
    RadarNowcastService._fetch_italy_arpae = fake_arpae
    try:
        frames, source = svc._fetch_frames_with_fallback(_VIZZAVONA_LAT, _VIZZAVONA_LON)

        assert len(arome_calls) == 1, (
            "AROME-FR muss fuer eine Korsika-Koordinate ZUERST versucht werden "
            f"(war: {len(arome_calls)} Aufrufe -- heute greift der Italien-Zweig zuerst)"
        )
        assert source == "ARPAE-2I", f"Bei AROME-FR-Ausfall muss die Kette auf ARPAE zurueckfallen (war: {source!r})"
        assert len(frames) == 1
    finally:
        RadarNowcastService._fetch_arome_france_hd = orig_arome
        RadarNowcastService._fetch_italy_arpae = orig_arpae
