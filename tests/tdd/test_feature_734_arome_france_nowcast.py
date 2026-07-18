"""TDD RED — Feature #734: Explizites AROME-HD-Routing für Frankreich.

Spec: docs/specs/modules/radar_nowcast_france.md
Test-Manifest: docs/specs/tests/feature_734_arome_france_nowcast_tests.md

KEINE MOCKS.
- AC-1/AC-4(real): echte HTTP-Calls gegen Open-Meteo (models=arome_france_hd).
- AC-2(bbox)/AC-3/AC-4(konvektiv): deterministisch mit ECHTEN RadarFrame-/
  NowcastResult-Objekten (keine Mock-Objekte, kein patch).

In der RED-Phase schlagen die AROME-Tests fehl, weil:
- `RadarNowcastService` Korsika-Koordinaten noch auf den globalen `minutely_15`-Fallback
  routet (statt `source == "AROME-FR"`),
- der Bbox-Helper `_within_arome_france` noch nicht existiert,
- `_fetch_arome_france_hd` noch nicht existiert,
- `format_now_text` die transparenten Labels ("Météo-France …", "Open-Meteo (global)")
  noch nicht kennt.
"""
from __future__ import annotations

import pytest

import services.radar_service as rs
from services.radar_service import NowcastResult, RadarNowcastService
from providers.brightsky import RadarFrame

# Reale Koordinaten
_CORSICA_LAT, _CORSICA_LON = 42.18, 9.0      # GR20-Region, in AROME-Box, außerhalb DE/AT
_PARIS_LAT, _PARIS_LON = 48.85, 2.35         # AROME-Box
_PYRENEES_LAT, _PYRENEES_LON = 42.6, 1.0     # AROME-Box
_BERLIN_LAT, _BERLIN_LON = 52.52, 13.40      # RADOLAN-Box (DE)
_ATLANTIC_LAT, _ATLANTIC_LON = 35.0, -40.0   # keine explizite Box → globaler Fallback


# ---------------------------------------------------------------------------
# AC-1 — AROME wird wirklich genutzt (echter Fetch)
# ---------------------------------------------------------------------------

# Dialt real Open-Meteo/AROME (#1211-2b) -- nur via -m live
@pytest.mark.live
def test_ac1_arome_france_real_fetch_returns_arome_source():
    """GIVEN reale Korsika-Koordinate (GR20-Region, DPC-Box, außerhalb DE/AT)
    WHEN get_nowcast aufgerufen wird
    THEN source == 'DPC' (Issue #1162: reale Radarbeobachtung schlägt AROME-Modell-
    Downscaling) und ≥1 reale Frame mit mm/h ≥ 0 — NICHT der globale Fallback.
    """
    svc = RadarNowcastService()
    result = svc.get_nowcast(_CORSICA_LAT, _CORSICA_LON)

    assert result.source == "DPC", (
        f"Korsika sollte Radar-DPC nutzen (echte Radarbeobachtung vor AROME-"
        f"Downscaling, Issue #1162), nicht den Fallback (war: {result.source})"
    )
    assert result.frames, "DPC-Fetch sollte reale Frames liefern"
    for f in result.frames:
        assert isinstance(f.precip_mm_h, (int, float))
        assert f.precip_mm_h >= 0.0


# ---------------------------------------------------------------------------
# AC-2 — Korrektes Routing pro Region
# ---------------------------------------------------------------------------

def test_ac2_within_arome_france_bbox():
    """GIVEN die AROME-HD-Domäne
    WHEN _within_arome_france Koordinaten klassifiziert
    THEN Korsika/Paris/Pyrenäen=True, Nord-Atlantik=False. (deterministisch, kein Netz)
    """
    within = getattr(rs, "_within_arome_france", None)
    assert callable(within), "_within_arome_france muss existieren"

    assert within(_CORSICA_LAT, _CORSICA_LON) is True
    assert within(_PARIS_LAT, _PARIS_LON) is True
    assert within(_PYRENEES_LAT, _PYRENEES_LON) is True
    assert within(_ATLANTIC_LAT, _ATLANTIC_LON) is False


# Dialt real Open-Meteo/AROME (#1211-2b) -- nur via -m live
@pytest.mark.live
def test_ac2_chain_routing_berlin_radar_atlantic_global():
    """GIVEN die Quellen-Kette mit korrekter Reihenfolge
    WHEN get_nowcast für verschiedene Regionen läuft
    THEN Korsika→'DPC', Berlin→'radar' (RADOLAN-Vorrang), Atlantik→'minutely_15'.
    (echte API-Calls, kein Mock)
    """
    svc = RadarNowcastService()

    # Korsika: Radar-DPC vor AROME-FR (Issue #1162 — reale Radarbeobachtung)
    assert svc.get_nowcast(_CORSICA_LAT, _CORSICA_LON).source == "DPC"

    # Berlin: RADOLAN wird VOR AROME geprüft → echtes Radar
    assert svc.get_nowcast(_BERLIN_LAT, _BERLIN_LON).source == "radar"

    # Atlantik: keine explizite Box → globaler Fallback
    assert svc.get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON).source == "minutely_15"


# ---------------------------------------------------------------------------
# AC-3 — Transparente Quellen-Angabe (Pure-Function)
# ---------------------------------------------------------------------------

def test_ac3_format_now_text_transparent_source_labels():
    """GIVEN NowcastResult mit source 'AROME-FR' bzw. 'minutely_15'
    WHEN format_now_text rendert
    THEN AROME-Text nennt 'Météo-France', Fallback-Text nennt 'Open-Meteo (global)'.
    """
    svc = RadarNowcastService()

    arome = NowcastResult(
        onset_minutes=None, intensity_label="Kein Niederschlag",
        source="AROME-FR", frames=[], is_convective=False,
    )
    arome_text = svc.format_now_text(arome)
    assert "Météo-France" in arome_text, (
        f"AROME-Quelle muss transparent benannt werden (war: {arome_text!r})"
    )
    assert "AROME" in arome_text

    fallback = NowcastResult(
        onset_minutes=None, intensity_label="Kein Niederschlag",
        source="minutely_15", frames=[], is_convective=False,
    )
    fallback_text = svc.format_now_text(fallback)
    assert "(global)" in fallback_text, (
        f"Fallback muss ehrlich als global beschriftet sein (war: {fallback_text!r})"
    )


# ---------------------------------------------------------------------------
# AC-4 — Gewitter-Signal aus AROME
# ---------------------------------------------------------------------------

def test_ac4_arome_convective_weathercode_drives_intensity():
    """GIVEN ein konvektiver AROME-Frame im Nowcast-Fenster (echte RadarFrame-Objekte)
    WHEN der Service daraus ableitet
    THEN is_convective == True und intensity_to_text == 'Starker Hagel/Gewitter'.
    Contract-Guard: belegt, dass die AROME-Konvektions-Klassifikation greift.
    """
    from datetime import datetime, timedelta, timezone

    svc = RadarNowcastService()
    now = datetime.now(tz=timezone.utc)
    frames = [
        RadarFrame(timestamp=now + timedelta(minutes=15), precip_mm_h=0.3, is_convective=True),
        RadarFrame(timestamp=now + timedelta(minutes=30), precip_mm_h=2.0, is_convective=True),
    ]
    result = svc._derive_result(frames, "AROME-FR")

    assert result.source == "AROME-FR"
    assert result.is_convective is True
    assert result.intensity_label == "Starker Hagel/Gewitter"


# Dialt real Open-Meteo/AROME (#1211-2b) -- nur via -m live
@pytest.mark.live
def test_ac4_arome_real_fetch_has_weather_code():
    """GIVEN reale AROME-Koordinate
    WHEN _fetch_arome_france_hd aufgerufen wird (existiert in RED noch nicht)
    THEN liefert es reale Frames mit numerischer Rate und parstem Konvektions-Flag.
    """
    fetch = getattr(RadarNowcastService(), "_fetch_arome_france_hd", None)
    assert callable(fetch), "_fetch_arome_france_hd muss existieren"

    frames = fetch(_CORSICA_LAT, _CORSICA_LON)
    assert isinstance(frames, list)
    assert frames, "AROME-Fetch sollte reale Frames liefern"
    for f in frames:
        assert isinstance(f.precip_mm_h, (int, float))
        assert f.precip_mm_h >= 0.0
        assert isinstance(f.is_convective, bool)
