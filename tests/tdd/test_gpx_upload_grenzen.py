"""GPX-Upload hat Grenzen je Datei und je Nutzer (#2961, AC-6).

Echte Anfragen an ``POST /api/gpx/parse`` ueber die ASGI-App; geprueft wird
Antwort UND Dateiablage unter ``data/users/<id>/gpx/``.
"""
from __future__ import annotations

import os

from fastapi.testclient import TestClient

from api.main import app
from app.loader import get_data_dir

_PUNKTE = b"".join(
    b'<trkpt lat="%.3f" lon="%.3f"><ele>%d</ele></trkpt>' % (47.27 + i * 0.004, 11.40 - i * 0.002, 574 + i * 140)
    for i in range(12)
)
_GPX = (b'<?xml version="1.0"?><gpx version="1.1" creator="t"><trk><name>T</name><trkseg>'
        + _PUNKTE + b'</trkseg></trk></gpx>')

NUTZER_A = "gpx-grenze-a"
NUTZER_B = "gpx-grenze-b"


def _post(user_id: str, name: str, inhalt: bytes):
    return TestClient(app).post(
        "/api/gpx/parse", params={"user_id": user_id},
        files={"file": (name, inhalt, "application/gpx+xml")},
    )


def _ablage(user_id: str):
    d = get_data_dir(user_id) / "gpx"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_datei_ueber_10_mb_wird_mit_413_abgewiesen_und_nicht_gespeichert():
    d = _ablage(NUTZER_A)
    zu_gross = _GPX[:-6] + b" " * (10 * 1024 * 1024) + b"</gpx>"
    resp = _post(NUTZER_A, "gross.gpx", zu_gross)
    assert resp.status_code == 413, resp.text
    assert resp.json()["code"] == "gpx_zu_gross"
    assert "10" in resp.json()["detail"]
    assert not (d / "gross.gpx").exists()


def test_gleichnamige_datei_ersetzt_statt_dupliziert():
    d = _ablage(NUTZER_A)
    assert _post(NUTZER_A, "tour.gpx", _GPX).status_code == 200
    assert _post(NUTZER_A, "tour.gpx", _GPX.replace(b"<name>T</name>", b"<name>U</name>")).status_code == 200
    assert sorted(p.name for p in d.iterdir() if p.name.startswith("tour")) == ["tour.gpx"]
    assert b"<name>U</name>" in (d / "tour.gpx").read_bytes()


def test_kaputte_gleichnamige_datei_zerstoert_vorhandene_nicht():
    d = _ablage(NUTZER_A)
    assert _post(NUTZER_A, "heil.gpx", _GPX).status_code == 200
    resp = _post(NUTZER_A, "heil.gpx", b"<kein gpx")
    assert resp.status_code == 400
    assert (d / "heil.gpx").read_bytes() == _GPX


def test_hoechstens_200_dateien_je_nutzer_anderer_nutzer_unberuehrt():
    d = _ablage(NUTZER_A)
    for i in range(200 - len(list(d.glob("*.gpx")))):
        (d / f"alt-{i:03d}.gpx").write_bytes(_GPX)
    resp = _post(NUTZER_A, "neu.gpx", _GPX)
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "gpx_speicher_voll"
    assert not (d / "neu.gpx").exists()
    # Ersetzen einer vorhandenen Datei bleibt moeglich
    assert _post(NUTZER_A, "alt-000.gpx", _GPX).status_code == 200
    # Grenze gilt je Nutzer
    assert _post(NUTZER_B, "neu.gpx", _GPX).status_code == 200


def test_hoechstens_200_mb_gesamt_je_nutzer():
    d = _ablage(NUTZER_B)
    gross = d / "riesig.gpx"
    with open(gross, "wb") as f:
        f.truncate(200 * 1024 * 1024)  # duenn belegte Datei, logische Groesse zaehlt
    try:
        resp = _post(NUTZER_B, "noch-eine.gpx", _GPX)
        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == "gpx_speicher_voll"
        assert not (d / "noch-eine.gpx").exists()
    finally:
        os.remove(gross)


def test_grenze_zaehlt_jede_schreibweise_der_endung():
    """F001: Dateien mit ``.GPX``/``.Gpx`` zaehlen genauso -- getrennt je Nutzer."""
    d = _ablage("gpx-grenze-c")
    for i in range(199):
        (d / f"alt-{i:03d}.{('GPX', 'Gpx', 'gpx')[i % 3]}").write_bytes(_GPX)
    assert _post("gpx-grenze-c", "nummer-200.GPX", _GPX).status_code == 200
    resp = _post("gpx-grenze-c", "nummer-201.Gpx", _GPX)
    assert resp.status_code == 409, resp.text
    assert not (d / "nummer-201.Gpx").exists()
    assert _post("gpx-grenze-d", "erste.GPX", _GPX).status_code == 200


def test_liegengebliebene_zwischendateien_zaehlen_und_werden_aufgeraeumt():
    d = _ablage("gpx-grenze-e")
    alt = d / ".upload-deadbeef.tmp"
    alt.write_bytes(b"x" * 1000)
    os.utime(alt, (0, 0))  # sehr alt
    assert _post("gpx-grenze-e", "tour.gpx", _GPX).status_code == 200
    assert not alt.exists()
    assert sorted(p.name for p in d.iterdir()) == ["tour.gpx"]


def test_sehr_langer_dateiname_wird_gekuerzt_statt_500():
    """F004: bisher wurden Namen bis 255 Bytes gespeichert; jetzt gekuerzt auf
    hoechstens 200 Bytes, Endung bleibt."""
    d = _ablage("gpx-grenze-f")
    name = "ä" * 120 + ".gpx"  # 244 Bytes UTF-8
    resp = _post("gpx-grenze-f", name, _GPX)
    assert resp.status_code == 200, resp.text
    namen = [p.name for p in d.iterdir()]
    assert len(namen) == 1 and namen[0].endswith(".gpx")
    assert len(namen[0].encode()) <= 200
    lang = "x" * 251 + ".gpx"  # 255 Bytes
    assert _post("gpx-grenze-f", lang, _GPX).status_code == 200
