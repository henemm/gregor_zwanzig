"""MCP „Gregor Wetter“ vollstaendig, Scheibe S2: Core-Endpunkt Nowcast (Issue #3398).

SPEC: docs/specs/modules/mcp_wetter_vollstaendig.md — AC-6 bis AC-9 (Datenebene).

Echter ASGI-Aufruf von ``GET /api/_internal/mcp/nowcast``. Quelle ist der
Offline-Radarpfad des Dienstes (``GZ_TEST_FIXTURE_DIR``; Radar-Frames aus dem
Geschwisterordner ``radar/minutely_15.json``, relativ zu *jetzt* gestempelt).
Jeder Test schreibt seine eigene Frame-Datei und nutzt eigene Koordinaten
(der Radar-Cache ist je Kachel gemeinsam). Offline liefert jede Open-Meteo-Stufe
der Kette die Fixture (in der AROME-HD-Box ``AROME-FR``, ausserhalb aller Boxen
``minutely_15``); ``radar``/``INCA`` und Drosselung sind hier nicht
erreichbar (siehe Bericht).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from api.main import app
from utils.timezone import tz_for_coords

PFAD = "/api/_internal/mcp/nowcast"
TOKEN = {"trocken", "leicht", "maessig", "stark", "gewitter", "hagel_gewitter"}
PFLICHT = {
    "beginn_min", "ende_min", "laeuft_bereits", "intensitaet", "konvektiv", "hagel",
    "max_mm_h_erste_stunde", "summe_erste_stunde_mm", "quelle", "reichweite_min",
    "ueber_horizont_hinaus", "gedrosselt", "nicht_verfuegbar", "trocken", "frames",
}


def _setze_frames(monkeypatch, tmp_path, frames: list[dict] | None):
    """Legt ``<tmp>/openmeteo`` (Env) und das Geschwister ``<tmp>/radar`` an."""
    (tmp_path / "openmeteo").mkdir()
    if frames is not None:
        (tmp_path / "radar").mkdir()
        (tmp_path / "radar" / "minutely_15.json").write_text(json.dumps({"frames": frames}))
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(tmp_path / "openmeteo"))


def _raster(nass: dict[int, tuple[float, int]], bis: int = 210) -> list[dict]:
    """15-Minuten-Raster 0..bis; ``nass``: offset -> (mm_h, wmo_code)."""
    return [{"offset_min": m, "precip_mm_h": nass.get(m, (0.0, 0))[0],
             "weather_code": nass.get(m, (0.0, 0))[1]} for m in range(0, bis + 1, 15)]


def _abruf(lat: float, lon: float):
    return TestClient(app).get(PFAD, params={"lat": lat, "lon": lon})


def test_ac6_regen_in_30_minuten_alle_felder(monkeypatch, tmp_path):
    _setze_frames(monkeypatch, tmp_path, _raster(
        {30: (2.0, 61), 45: (4.0, 63), 60: (0.0, 0), 75: (8.0, 65)}))
    lat, lon = 50.11, 8.68
    jetzt = datetime.now(tz_for_coords(lat, lon))
    resp = _abruf(lat, lon)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert PFLICHT <= set(body), PFLICHT - set(body)
    assert 28 <= body["beginn_min"] <= 30
    assert body["laeuft_bereits"] is False
    assert body["ende_min"] is not None and body["ende_min"] > body["beginn_min"]
    assert body["intensitaet"] in TOKEN and body["intensitaet"] != "trocken"
    assert body["trocken"] is False
    assert body["gedrosselt"] is False and body["nicht_verfuegbar"] is False
    assert body["konvektiv"] is False and body["hagel"] is False
    # Erste Stunde ab jetzt: Frames bei +30 (2 mm/h) und +45 (4 mm/h), je 15 min.
    assert body["max_mm_h_erste_stunde"] == pytest.approx(4.0)
    assert body["summe_erste_stunde_mm"] == pytest.approx(1.5, abs=0.1)
    # Frankfurt liegt in der AROME-HD-Box; offline liefert jede Open-Meteo-Stufe
    # der Kette die Fixture, die Quelle wird ehrlich durchgereicht.
    assert body["quelle"] == "AROME-FR"
    assert 0 < body["reichweite_min"] <= 180
    assert isinstance(body["ueber_horizont_hinaus"], bool)
    # Frames: Ortszeit mit Offset, hoechstens 180 Minuten.
    frames = body["frames"]
    assert frames and set(frames[0]) == {"zeit", "mm_h", "konvektiv", "hagel"}
    erwarteter_offset = jetzt.utcoffset()
    for frame in frames:
        zeit = datetime.fromisoformat(frame["zeit"])
        assert zeit.utcoffset() == erwarteter_offset, frame
        assert (zeit - jetzt) <= timedelta(minutes=181), frame
    assert any(f["mm_h"] == 4.0 for f in frames)


def test_ac6_gewitter_mit_hagel_token_und_flags(monkeypatch, tmp_path):
    _setze_frames(monkeypatch, tmp_path, _raster({30: (6.0, 96), 45: (5.0, 96)}))
    body = _abruf(52.52, 13.40).json()
    assert body["intensitaet"] == "hagel_gewitter"
    assert body["konvektiv"] is True and body["hagel"] is True
    assert any(f["hagel"] and f["konvektiv"] for f in body["frames"])


def test_ac6_laufender_regen(monkeypatch, tmp_path):
    _setze_frames(monkeypatch, tmp_path, _raster({0: (1.0, 61), 15: (1.0, 61), 30: (1.0, 61)}))
    body = _abruf(53.55, 10.00).json()
    assert body["laeuft_bereits"] is True
    assert body["ende_min"] is not None
    assert body["trocken"] is False


def test_ac6_frames_hoechstens_180_minuten(monkeypatch, tmp_path):
    _setze_frames(monkeypatch, tmp_path, _raster({195: (3.0, 63), 210: (3.0, 63)}, bis=210))
    lat, lon = 48.14, 11.58
    jetzt = datetime.now(tz_for_coords(lat, lon))
    body = _abruf(lat, lon).json()
    assert body["frames"]
    assert all((datetime.fromisoformat(f["zeit"]) - jetzt) <= timedelta(minutes=181)
               for f in body["frames"])
    assert all(f["mm_h"] == 0.0 for f in body["frames"])
    assert body["beginn_min"] is None


def test_ac7_trocken_ausdruecklich(monkeypatch, tmp_path):
    _setze_frames(monkeypatch, tmp_path, _raster({}))
    body = _abruf(51.34, 12.37).json()
    assert PFLICHT <= set(body)
    assert body["trocken"] is True
    assert body["intensitaet"] == "trocken"
    assert body["beginn_min"] is None and body["laeuft_bereits"] is False
    assert body["nicht_verfuegbar"] is False and body["gedrosselt"] is False
    assert body["frames"], "trocken heisst Frames ohne Niederschlag, nicht leer"


def test_ac8_ausserhalb_radar_minutely_15(monkeypatch, tmp_path):
    _setze_frames(monkeypatch, tmp_path, _raster({30: (1.5, 61)}))
    body = _abruf(64.14, -21.90).json()  # Reykjavik, ausserhalb aller Radar-Boxen
    assert body["quelle"] == "minutely_15"
    assert body["frames"]


def test_ac9_quelle_ausgefallen_keine_erfundenen_werte(monkeypatch, tmp_path):
    _setze_frames(monkeypatch, tmp_path, None)  # Radar-Fixture fehlt = Upstream-Ausfall
    resp = _abruf(40.42, -3.70)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["nicht_verfuegbar"] is True
    assert body["trocken"] is False
    assert body["beginn_min"] is None and body["intensitaet"] != "gewitter"
    # F001 (Adversary): ohne Daten keine erfundenen Werte, auch kein "trocken"-Token.
    assert body["intensitaet"] is None
    assert body["max_mm_h_erste_stunde"] is None
    assert body["summe_erste_stunde_mm"] is None
    assert body["reichweite_min"] is None


@pytest.mark.parametrize("params", [
    {"lat": 95, "lon": 8.0}, {"lat": 50.0, "lon": 190}, {"lat": "x", "lon": 8.0}, {"lon": 8.0},
])
def test_ungueltige_koordinaten_422(params):
    resp = TestClient(app).get(PFAD, params=params)
    assert resp.status_code == 422, resp.text


def test_ohne_core_auth_abgelehnt():
    client = TestClient(app)
    client.headers.pop("X-GZ-Core-Auth", None)
    resp = client.get(PFAD, params={"lat": 50.0, "lon": 8.0})
    assert resp.status_code == 401
    assert "frames" not in resp.text


class _Aufzeichnend:
    """Aufzeichnender Wrapper um den echten RadarNowcastService (kein Mock):
    haelt Aufrufparameter und das echte Ergebnis fest."""

    aufrufe: list[dict] = []
    ergebnisse: list = []


def _aufzeichnen(monkeypatch):
    import services.radar_service as radar

    _Aufzeichnend.aufrufe, _Aufzeichnend.ergebnisse = [], []

    class _Dienst(radar.RadarNowcastService):
        def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing",
                        user_id=None, deadline_at=None):
            _Aufzeichnend.aufrufe.append({"priority": priority, "user_id": user_id})
            ergebnis = super().get_nowcast(lat, lon, elevation_m, priority=priority,
                                           user_id=user_id, deadline_at=deadline_at)
            _Aufzeichnend.ergebnisse.append(ergebnis)
            return ergebnis

    monkeypatch.setattr(radar, "RadarNowcastService", _Dienst)


def test_f006_core_ruft_nutzerfrei_und_reicht_reichweite_und_horizont_durch(monkeypatch, tmp_path):
    """F006: user_id=None (Mandantenfreiheit), Reichweite und Horizont aus dem Dienst."""
    _setze_frames(monkeypatch, tmp_path, _raster({60: (2.0, 61), 75: (2.0, 61), 90: (2.0, 61)}, bis=90))
    _aufzeichnen(monkeypatch)
    body = _abruf(47.80, 13.04).json()
    assert _Aufzeichnend.aufrufe == [{"priority": "user_briefing", "user_id": None}]
    ergebnis = _Aufzeichnend.ergebnisse[0]
    assert body["reichweite_min"] == ergebnis.source_reach_minutes
    assert body["reichweite_min"] is not None and body["reichweite_min"] < 180
    assert body["ueber_horizont_hinaus"] is True
    assert body["ueber_horizont_hinaus"] == ergebnis.event_ongoing_beyond_horizon
    assert body["gedrosselt"] is ergebnis.throttled is False


def test_f006_hagel_nur_bei_nassem_frame_und_keine_frames_vor_jetzt(monkeypatch, tmp_path):
    """Hagel-Code ohne Niederschlag ist kein Hagel; Frames vor jetzt fallen heraus."""
    frames = [{"offset_min": -30, "precip_mm_h": 0.0, "weather_code": 0}]
    frames += _raster({30: (0.0, 96)})
    _setze_frames(monkeypatch, tmp_path, frames)
    lat, lon = 49.45, 11.08
    jetzt = datetime.now(tz_for_coords(lat, lon))
    body = _abruf(lat, lon).json()
    assert body["hagel"] is False
    assert all(datetime.fromisoformat(f["zeit"]) >= jetzt - timedelta(seconds=5)
               for f in body["frames"]), body["frames"][:2]
