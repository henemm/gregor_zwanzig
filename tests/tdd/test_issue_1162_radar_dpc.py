"""TDD RED — Issue #1162: Radar-DPC (Protezione Civile) als Regen-Nowcast-Quelle
fuer Italien.

Spec: docs/specs/modules/issue_1162_radar_dpc.md

Bisher durchlaufen italienische Orte in `_fetch_frames_with_fallback` entweder
AROME-FR (nur NW-Italien, Modell-Downscaling) oder direkt den globalen
`minutely_15`-Fallback. Diese Tests belegen die geplante Radar-DPC-Integration:
ein neuer Provider `RadarDPCProvider` (3-Schritt-REST-Ablauf gegen
radar-api.protezionecivile.it, GeoTIFF-Punktextraktion via `rasterio`), eine neue
IT-Bounding-Box `_within_dpc` VOR dem AROME-FR-Check in der Fallback-Kette, und
ein Konvektions-Sidecar-Merge analog zum GeoSphere-INCA-Pfad (#1161, ADR-0018
Nicht-Kaschieren-Invariante).

KEINE MOCKS. DI erfolgt ausschliesslich durch Ersetzen von Instanz-/Klassenmethoden
mit echten Python-Funktionen, die reale Objekte (RadarFrame) zurueckgeben — kein
`Mock()`/`patch()`/`MagicMock` (Muster aus test_issue_1161_inca_convective.py).

In der RED-Phase schlagen ALLE Tests fehl, weil:
- `providers.radar_dpc` (Modul mit `RadarDPCProvider`) noch nicht existiert (ImportError),
- `services.radar_service._within_dpc` noch nicht existiert (ImportError),
- `RadarNowcastService._fetch_radar_dpc` noch nicht existiert (AttributeError),
- `rasterio` noch keine Projekt-Dependency ist.
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

# Rom — eindeutig innerhalb der geplanten DPC-Box (lat 36.0-47.5 / lon 6.5-19.0).
_ROME_LAT, _ROME_LON = 41.9028, 12.4964

# Marseille — ausserhalb der geplanten DPC-Box (lon 5.37 < 6.5), aber innerhalb
# der bestehenden AROME-FR-Box (lat 41.0-51.5 / lon -5.5-10.0).
_MARSEILLE_LAT, _MARSEILLE_LON = 43.2965, 5.3698


# ===========================================================================
# AC-1: Realer Rasterwert an einer echten IT-Koordinate (Live, kein Mock)
# ===========================================================================

@pytest.mark.live
def test_ac1_dpc_provider_returns_real_frame_at_it_coordinate():
    """AC-1: der volle 3-Schritt-REST-Ablauf gegen die echte DPC-API liefert ein
    nicht-leeres RadarFrame mit plausiblem Zeitstempel und precip_mm_h."""
    from providers.radar_dpc import RadarDPCProvider

    frames = RadarDPCProvider().fetch_nowcast(_ROME_LAT, _ROME_LON)

    assert frames, "DPC-Provider muss mindestens ein RadarFrame liefern"
    frame = frames[0]

    now = datetime.now(tz=timezone.utc)
    ts = frame.timestamp if frame.timestamp.tzinfo else frame.timestamp.replace(tzinfo=timezone.utc)
    age_min = (now - ts).total_seconds() / 60.0
    assert 0 <= age_min <= 20, (
        f"SRI-Update-Intervall ist 5 Min — Zeitstempel sollte nicht aelter als ~20 Min "
        f"sein (war: {age_min:.1f} Min)"
    )
    assert isinstance(frame.precip_mm_h, (int, float))
    assert 0.0 <= frame.precip_mm_h < 500.0, (
        f"precip_mm_h ausserhalb des Plausibilitaetsbereichs: {frame.precip_mm_h}"
    )


# ===========================================================================
# AC-2: End-to-End gegen die echte Source-Chain (reale IT-Koordinate)
# ===========================================================================

@pytest.mark.live
def test_ac2_dpc_live_get_nowcast_uses_dpc_source_for_it_coordinate():
    """AC-2: echter Aufruf ohne DI gegen die produktive Source-Chain (Rom) liefert
    source=='DPC'. Skip nur, wenn eine direkte Probe den Provider selbst als
    unerreichbar bestaetigt (Muster aus test_issue_1161_inca_convective.py::AC-4) —
    andernfalls harter Assert, kein stilles Wegfallen bei falscher Quelle."""
    from providers.radar_dpc import RadarDPCProvider
    from services.radar_service import RadarNowcastService

    if not RadarDPCProvider().fetch_nowcast(_ROME_LAT, _ROME_LON):
        pytest.skip("Radar-DPC API nicht erreichbar (fetch_nowcast liefert leere Liste)")

    result = RadarNowcastService().get_nowcast(_ROME_LAT, _ROME_LON)
    assert result.source == "DPC", (
        f"Rom sollte explizit DPC nutzen, nicht den Fallback (war: {result.source})"
    )


# ===========================================================================
# AC-3: DPC-Ausfall -> Fail-Soft-Fallback auf die naechste Quelle in der Kette
# ===========================================================================

def test_ac3_dpc_failure_falls_back_to_next_source():
    """AC-3: schlaegt der DPC-Ablauf REAL fehl (echter httpx-Request gegen eine
    ungueltige Endpoint-Adresse — kein Mock, kein Wegstubben der Methode), laeuft
    der reale `except Exception -> []`-Pfad im 3-Schritt-Flow durch: `_fetch_radar_dpc`
    liefert [] und `get_nowcast` faellt auf die naechste Quelle in der Kette zurueck
    — kein Absturz."""
    import providers.radar_dpc as radar_dpc
    from services.radar_service import RadarNowcastService

    # BASE_URL auf eine schema-lose (nicht auflösbare) Adresse setzen: der echte
    # client.get()/post() in _find_last_product wirft httpx.UnsupportedProtocol, die
    # der reale Provider-except-Zweig zu [] verarbeitet (kein Methoden-Stub).
    orig_base = radar_dpc.BASE_URL
    radar_dpc.BASE_URL = "not-a-valid-url-scheme"
    try:
        svc = RadarNowcastService()
        frames = svc._fetch_radar_dpc(_ROME_LAT, _ROME_LON)
        assert frames == [], "_fetch_radar_dpc muss bei realem Endpoint-Fehler [] liefern, nicht crashen"

        result = svc.get_nowcast(_ROME_LAT, _ROME_LON)
        # Issue #1186: nach Einfuehrung des ARPAE-ICON-2I-Rueckfalls ist "ARPAE-2I"
        # der korrekte naechste Schritt fuer Rom bei DPC-Ausfall (bewusste,
        # spec-gedeckte Erweiterung der erlaubten Ergebnismenge, keine Verwaesserung).
        assert result.source in ("ARPAE-2I", "AROME-FR", "ICON-D2", "minutely_15"), (
            f"Bei DPC-Ausfall muss die Fallback-Kette greifen (war: {result.source})"
        )
    finally:
        radar_dpc.BASE_URL = orig_base


# ===========================================================================
# AC-4a: Convective-Sidecar-Match innerhalb Toleranz -> is_convective gemerged
# ===========================================================================

def test_ac4_dpc_merges_convective_flag_from_sidecar(monkeypatch):
    """AC-4a: ein konvektives Sidecar-Frame (WMO 95/96/99) innerhalb +-5 Min wird
    auf das zeitlich passende DPC-Frame gemerged; precip_mm_h bleibt DPC-Quelle."""
    from providers.brightsky import RadarFrame
    from providers.radar_dpc import RadarDPCProvider
    from services.radar_service import RadarNowcastService

    # Issue #1329 C2 / AC-11: der globale Offline-Guard (GZ_TEST_FIXTURE_DIR,
    # von tests/conftest.py autouse gesetzt) wuerde _fetch_radar_dpc VOR der
    # Provider-Konstruktion kurzschliessen. Dieser Test prueft aber genau
    # die reale DPC-Provider-Konstruktion (mit eigenem Methoden-Patch als
    # Netz-Schutz) -- der globale Schalter ist hier kontraproduktiv, nicht
    # sein Sicherheitsnetz.
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)

    dpc_ts = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)

    def fake_dpc_fetch(self, lat, lon):
        return [RadarFrame(timestamp=dpc_ts, precip_mm_h=3.5, is_convective=False)]

    def fake_openmeteo_15(self, lat, lon, models=None):
        return [RadarFrame(timestamp=dpc_ts + timedelta(minutes=2), precip_mm_h=2.0, is_convective=True)]

    orig_dpc = RadarDPCProvider.fetch_nowcast
    orig_sidecar = RadarNowcastService._fetch_openmeteo_15
    RadarDPCProvider.fetch_nowcast = fake_dpc_fetch
    RadarNowcastService._fetch_openmeteo_15 = fake_openmeteo_15
    try:
        svc = RadarNowcastService()
        frames = svc._fetch_radar_dpc(_ROME_LAT, _ROME_LON)
        assert len(frames) == 1
        assert frames[0].is_convective is True, (
            "Konvektives Sidecar-Frame innerhalb +-5 Min muss auf das DPC-Frame gemerged werden"
        )
        assert frames[0].precip_mm_h == pytest.approx(3.5), (
            "Regen-Rate muss weiterhin aus der DPC-Quelle stammen, nicht aus dem Sidecar"
        )
    finally:
        RadarDPCProvider.fetch_nowcast = orig_dpc
        RadarNowcastService._fetch_openmeteo_15 = orig_sidecar


# ===========================================================================
# AC-4b: Sidecar-Fail-Soft-Fall -> convective_checked=False (ADR-0018)
# ===========================================================================

def test_ac4_dpc_sidecar_failure_sets_convective_checked_false(monkeypatch):
    """AC-4b: schlaegt der Open-Meteo-Sidecar fehl (liefert [], realer Fail-Soft-
    Vertrag), bleibt die DPC-Regen-Nowcast nutzbar, aber `convective_checked` wird
    False und `format_now_text` weist das sichtbar aus statt es zu kaschieren."""
    from providers.brightsky import RadarFrame
    from providers.radar_dpc import RadarDPCProvider
    from services.radar_service import RadarNowcastService

    # Issue #1329 C2 / AC-11: siehe test_ac4_dpc_merges_convective_flag_from_sidecar
    # -- der globale Offline-Guard wuerde die Provider-Konstruktion, die
    # dieser Test gerade prueft, kurzschliessen. Eigener Methoden-Patch ist
    # der Netz-Schutz dieses Tests.
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)

    dpc_ts = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)

    def fake_dpc_fetch(self, lat, lon):
        return [RadarFrame(timestamp=dpc_ts, precip_mm_h=1.5, is_convective=False)]

    def failing_openmeteo_15(self, lat, lon, models=None):
        return []

    orig_dpc = RadarDPCProvider.fetch_nowcast
    orig_sidecar = RadarNowcastService._fetch_openmeteo_15
    RadarDPCProvider.fetch_nowcast = fake_dpc_fetch
    RadarNowcastService._fetch_openmeteo_15 = failing_openmeteo_15
    try:
        svc = RadarNowcastService()
        result = svc.get_nowcast(_ROME_LAT, _ROME_LON)

        assert result.source == "DPC", "Regen-Nowcast muss trotz Sidecar-Fail DPC nutzen"
        assert len(result.frames) >= 1, "DPC-Regen-Frames bleiben trotz Sidecar-Fail erhalten"
        assert result.convective_checked is False, (
            "Sidecar-Fail darf NICHT stillschweigend als 'geprueft, kein Gewitter' behandelt "
            "werden (ADR-0018 Nicht-Kaschieren-Invariante)"
        )

        text = svc.format_now_text(result)
        assert "Gewitter-Check nicht verfügbar." in text
    finally:
        RadarDPCProvider.fetch_nowcast = orig_dpc
        RadarNowcastService._fetch_openmeteo_15 = orig_sidecar


# ===========================================================================
# AC-5: BBox-Grenzfall — Koordinate ausserhalb DPC, aber innerhalb AROME-FR
# ===========================================================================

@pytest.mark.live
def test_ac5_dpc_bbox_boundary_defers_to_arome_fr():
    """AC-5: eine Koordinate knapp ausserhalb der DPC-Box (aber innerhalb AROME-FR)
    nutzt weiterhin AROME-FR — die neue DPC-Pruefung verdraengt die bestehende
    AROME-FR-Abdeckung nicht."""
    from services.radar_service import RadarNowcastService, _within_arome_france, _within_dpc

    assert _within_dpc(_MARSEILLE_LAT, _MARSEILLE_LON) is False, (
        "Marseille liegt ausserhalb der geplanten DPC-Box (lon < 6.5)"
    )
    assert _within_arome_france(_MARSEILLE_LAT, _MARSEILLE_LON) is True, (
        "Marseille muss weiterhin innerhalb der bestehenden AROME-FR-Box liegen"
    )

    result = RadarNowcastService().get_nowcast(_MARSEILLE_LAT, _MARSEILLE_LON)
    assert result.source == "AROME-FR", (
        f"Marseille sollte AROME-FR nutzen, nicht von der neuen DPC-Pruefung verdraengt "
        f"werden (war: {result.source})"
    )
