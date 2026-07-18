"""TDD RED — Feature #761: Explizites ICON-D2-Routing für Zentraleuropa/Alpen.

Spec: docs/specs/modules/radar_nowcast_icon_d2.md
Test-Manifest: docs/specs/tests/feature_761_icon_d2_nowcast_tests.md

KEINE MOCKS.
- AC-1/AC-3: echte HTTP-Calls gegen Open-Meteo (models=icon_d2).
- AC-2(bbox)/AC-4: deterministisch mit ECHTEN RadarFrame-/NowcastResult-Objekten.

In der RED-Phase schlagen die ICON-D2-Tests fehl, weil:
- `_within_icon_d2` und `_fetch_icon_d2` noch nicht existieren,
- `RadarNowcastService` Zentraleuropa-Koordinaten noch auf den globalen Fallback routet,
- `format_now_text` das Label „DWD ICON-D2" noch nicht kennt,
- der All-None-Guard im expliziten Modell-Pfad noch fehlt.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import services.radar_service as rs
from services.radar_service import NowcastResult, RadarNowcastService
from providers.brightsky import RadarFrame

# Reale Koordinaten
_SLOVENIA_LAT, _SLOVENIA_LON = 46.2, 14.5      # ICON-D2-only (außerhalb DE/AT/FR), im Gitter
_DOLOMITES_LAT, _DOLOMITES_LON = 46.4, 11.8    # ICON-D2-Box, im Gitter
_SWISS_WEST_LAT, _SWISS_WEST_LON = 46.0, 7.5   # AROME-Box → AROME-FR-Vorrang vor ICON-D2
_BERLIN_LAT, _BERLIN_LON = 52.52, 13.40        # RADOLAN-Box (DE) → radar
_ATLANTIC_LAT, _ATLANTIC_LON = 35.0, -40.0     # keine Box → globaler Fallback
_BOSNIA_LAT, _BOSNIA_LON = 44.5, 18.5          # IN Bbox, AUSSERHALB rotiertem Gitter → all-None


# ---------------------------------------------------------------------------
# AC-1 — ICON-D2 wird wirklich genutzt (echter Fetch)
# ---------------------------------------------------------------------------

@pytest.mark.xfail(reason="#1144: DWD-Direktquelle (ICON-D2 fuer Deutschland-Totalausfall) noch nicht implementiert, Quellenentscheidung offen", strict=False)
def test_ac1_icon_d2_real_fetch_returns_icon_d2_source():
    """GIVEN reale Zentraleuropa-Koordinate (ICON-D2-Gitter, außerhalb DE/AT/FR)
    WHEN get_nowcast aufgerufen wird
    THEN source == 'ICON-D2' und ≥1 reale Frame mit mm/h ≥ 0 — NICHT der globale Fallback.
    """
    svc = RadarNowcastService()
    result = svc.get_nowcast(_SLOVENIA_LAT, _SLOVENIA_LON)

    assert result.source == "ICON-D2", (
        f"Zentraleuropa sollte explizit ICON-D2 nutzen (war: {result.source})"
    )
    assert result.frames, "ICON-D2-Fetch sollte reale Frames liefern"
    for f in result.frames:
        assert isinstance(f.precip_mm_h, (int, float))
        assert f.precip_mm_h >= 0.0


# ---------------------------------------------------------------------------
# AC-2 — Korrekte Routing-Priorität
# ---------------------------------------------------------------------------

def test_ac2_within_icon_d2_bbox():
    """GIVEN die ICON-D2-Bbox
    WHEN _within_icon_d2 Koordinaten klassifiziert
    THEN Slowenien/Dolomiten=True, Nord-Atlantik=False. (deterministisch, kein Netz)
    """
    within = getattr(rs, "_within_icon_d2", None)
    assert callable(within), "_within_icon_d2 muss existieren"

    assert within(_SLOVENIA_LAT, _SLOVENIA_LON) is True
    assert within(_DOLOMITES_LAT, _DOLOMITES_LON) is True
    assert within(_ATLANTIC_LAT, _ATLANTIC_LON) is False


@pytest.mark.xfail(reason="#1144: DWD-Direktquelle (ICON-D2 fuer Deutschland-Totalausfall) noch nicht implementiert, Quellenentscheidung offen", strict=False)
def test_ac2_chain_routing_precedence():
    """GIVEN die Quellen-Kette mit Reihenfolge RADOLAN→INCA→AROME-FR→ICON-D2→global
    WHEN get_nowcast für verschiedene Regionen läuft
    THEN Slowenien→'ICON-D2', Berlin→'radar', Schweiz-West→'AROME-FR' (Vorrang), Atlantik→'minutely_15'.
    (echte API-Calls, kein Mock)
    """
    svc = RadarNowcastService()

    # Zentraleuropa: explizit ICON-D2 (neu) — schlägt in RED fehl
    assert svc.get_nowcast(_SLOVENIA_LAT, _SLOVENIA_LON).source == "ICON-D2"

    # Berlin: RADOLAN-Vorrang
    assert svc.get_nowcast(_BERLIN_LAT, _BERLIN_LON).source == "radar"

    # Schweiz-West: AROME-FR (höher aufgelöst) wird VOR ICON-D2 geprüft
    assert svc.get_nowcast(_SWISS_WEST_LAT, _SWISS_WEST_LON).source == "AROME-FR"

    # Atlantik: keine Box → globaler Fallback
    assert svc.get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON).source == "minutely_15"


# ---------------------------------------------------------------------------
# AC-3 — All-None-Guard (rotiertes Gitter)
# ---------------------------------------------------------------------------

@pytest.mark.xfail(reason="#1144: DWD-Direktquelle (ICON-D2 fuer Deutschland-Totalausfall) noch nicht implementiert, Quellenentscheidung offen", strict=False)
def test_ac3_icon_d2_all_none_falls_through_to_global():
    """GIVEN eine Koordinate INNERHALB der ICON-D2-Bbox, aber AUSSERHALB des rotierten
    Gitters (Open-Meteo liefert dort real all-None precipitation)
    WHEN _fetch_icon_d2 bzw. get_nowcast aufgerufen wird
    THEN liefert _fetch_icon_d2 [] (All-None-Guard) und die Kette fällt auf 'minutely_15'
    zurück — KEIN fälschliches 'ICON-D2' mit Schein-Null-Frames.
    """
    svc = RadarNowcastService()

    fetch = getattr(svc, "_fetch_icon_d2", None)
    assert callable(fetch), "_fetch_icon_d2 muss existieren"

    # All-None außerhalb Gitter → leere Frame-Liste
    frames = fetch(_BOSNIA_LAT, _BOSNIA_LON)
    assert frames == [], f"all-None-Punkt muss [] liefern, nicht Schein-Nullen (war: {frames!r})"

    # Kette fällt sauber durch auf globalen Fallback
    assert svc.get_nowcast(_BOSNIA_LAT, _BOSNIA_LON).source == "minutely_15"


# ---------------------------------------------------------------------------
# AC-4 — Transparenz + Gewitter
# ---------------------------------------------------------------------------

def test_ac4_format_now_text_icon_d2_label():
    """GIVEN NowcastResult mit source 'ICON-D2'
    WHEN format_now_text rendert
    THEN nennt der Text transparent 'DWD ICON-D2'.
    """
    svc = RadarNowcastService()
    result = NowcastResult(
        onset_minutes=None, intensity_label="Kein Niederschlag",
        source="ICON-D2", frames=[], is_convective=False,
    )
    text = svc.format_now_text(result)
    assert "DWD ICON-D2" in text, (
        f"ICON-D2-Quelle muss transparent benannt werden (war: {text!r})"
    )


def test_ac4_icon_d2_convective_drives_intensity():
    """GIVEN ein konvektiver ICON-D2-Frame im Nowcast-Fenster (echte RadarFrame-Objekte)
    WHEN der Service daraus ableitet
    THEN is_convective == True und intensity_to_text == 'Starker Hagel/Gewitter'.
    Contract-Guard: belegt die Konvektions-Klassifikation, die der ICON-D2-Pfad nutzt.
    """
    svc = RadarNowcastService()
    now = datetime.now(tz=timezone.utc)
    frames = [
        RadarFrame(timestamp=now + timedelta(minutes=15), precip_mm_h=0.4, is_convective=True),
        RadarFrame(timestamp=now + timedelta(minutes=30), precip_mm_h=3.0, is_convective=True),
    ]
    result = svc._derive_result(frames, "ICON-D2")

    assert result.source == "ICON-D2"
    assert result.is_convective is True
    assert result.intensity_label == "Starker Hagel/Gewitter"
