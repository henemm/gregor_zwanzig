"""MCP-Konnektor „Gregor Wetter“, Scheibe 1: Core-Endpunkt fuer Stundenwerte (Issue #3281).

SPEC: docs/specs/modules/mcp_wetter_konnektor.md — AC-1/AC-2 (Datenebene), AC-14.

Geprueft wird die echte Antwort von ``GET /api/_internal/mcp/wetter`` ueber die
ASGI-App. Wetterdaten kommen aus dem offline ``FixtureProvider`` mit einem
eigenen Tagesgang (``tests/fixtures/mcp_wetter/innsbruck.json``: 192 Stunden ab
00 UTC des Testtags; Direktstrahlung je UTC-Stunde 6..17 =
60/90/120/150/180/600/600/600/180/150/120/90 W/m², sonst 0; Stunde 47 ohne
Strahlungswert und ohne Nullgradgrenze). Die erwarteten Sonnenminuten sind von Hand aus dem
DNI-Band 60..180 W/m² (Standard-Settings, linear) abgeschrieben:
60 -> 0, 90 -> 15, 120 -> 30, 150 -> 45, >=180 -> 60.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from freezegun import freeze_time

from api.main import app
from i18n import t

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "mcp_wetter"
PFAD = "/api/_internal/mcp/wetter"
CORE_AUTH_HEADER = "X-GZ-Core-Auth"
FRANKFURT = {"lat": 50.1106444, "lon": 8.6820917}
MUENSTER = {"lat": 51.9625101, "lon": 7.6251879}
BERLIN = ZoneInfo("Europe/Berlin")

#: Sonnenminuten je UTC-Stunde des Fixture-Tagesgangs (von Hand, s. Kopf).
SONNENMINUTEN_JE_UTC_STUNDE = {
    5: 0, 6: 0, 7: 15, 8: 30, 9: 45, 10: 60, 11: 60, 12: 60, 13: 60,
    14: 60, 15: 45, 16: 30, 17: 15, 18: 0,
}


@pytest.fixture(autouse=True)
def _tagesgang_fixture(monkeypatch):
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(FIXTURE_DIR))


def _basis() -> datetime:
    """00 UTC des Testtags — Anker des FixtureProvider."""
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _rohdaten() -> list[dict]:
    return json.loads((FIXTURE_DIR / "innsbruck.json").read_text())["data"]


def _abruf(params: dict):
    return TestClient(app).get(PFAD, params=params)


def _ortszeit(utc: datetime) -> str:
    return utc.astimezone(BERLIN).isoformat()


def test_naechste_zwei_stunden_in_ortszeit_mit_einheiten():
    """AC-1 (Datenebene): zwei Stundeneintraege mit Offset der Ortszeit und Einheiten."""
    jetzt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    resp = _abruf({**FRANKFURT, "von": _ortszeit(jetzt),
                   "bis": _ortszeit(jetzt + timedelta(hours=2))})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["zeitzone"] == "Europe/Berlin"
    stunden = body["stunden"]
    assert [s["zeit"] for s in stunden] == [
        _ortszeit(jetzt + timedelta(hours=i)) for i in range(2)]

    roh = _rohdaten()
    index = int((jetzt - _basis()) / timedelta(hours=1))
    for i, stunde in enumerate(stunden):
        assert stunde["precip_1h_mm"] == roh[index + i]["precip_1h_mm"]
        assert stunde["pop_pct"] == roh[index + i]["pop_pct"]
        assert stunde["t2m_c"] == roh[index + i]["t2m_c"]
        assert "confidence_pct" not in stunde

    einheiten = body["einheiten"]
    assert einheiten["precip_1h_mm"] == "mm"
    assert einheiten["pop_pct"] == "%"
    assert einheiten["t2m_c"] == "°C"
    assert einheiten["wind10m_kmh"] == "km/h"
    assert einheiten["gust_kmh"] == "km/h"
    assert einheiten["sonnenminuten"] == "min"
    for stunde in stunden:
        assert set(stunde) - {"zeit"} <= set(einheiten), stunde
    # Nur Wetter, keinerlei Nutzer- oder Trip-Angaben.
    assert set(body) == {"lat", "lon", "zeitzone", "von", "bis", "begrenzt",
                         "einheiten", "stunden"}


def test_zeit_ohne_offset_gilt_als_ortszeit():
    jetzt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    naiv = jetzt.astimezone(BERLIN).replace(tzinfo=None)
    resp = _abruf({**FRANKFURT, "von": naiv.isoformat(),
                   "bis": (naiv + timedelta(hours=1)).isoformat()})
    assert resp.status_code == 200, resp.text
    assert [s["zeit"] for s in resp.json()["stunden"]] == [_ortszeit(jetzt)]


def test_sonnenminuten_je_stunde_ergeben_sonnenstunden_je_tag():
    """AC-2: Muenster, 72 Stunden, je Stunde Sonnenminuten 0..60, Tagessumme ableitbar."""
    basis = _basis()
    resp = _abruf({**MUENSTER, "von": basis.isoformat(),
                   "bis": (basis + timedelta(hours=72)).isoformat()})
    assert resp.status_code == 200, resp.text
    stunden = resp.json()["stunden"]
    assert len(stunden) == 72

    je_tag: dict[str, int] = defaultdict(int)
    for i, stunde in enumerate(stunden):
        if i == 47:
            # Kein Strahlungswert beim Anbieter -> kein erfundener Wert, und
            # ein fehlendes Rohfeld entfaellt (kein null).
            assert "sonnenminuten" not in stunde
            assert "freezing_level_m" not in stunde
            assert stunde["snowfall_limit_m"] == _rohdaten()[47]["snowfall_limit_m"]
            continue
        minuten = stunde["sonnenminuten"]
        assert isinstance(minuten, int) and 0 <= minuten <= 60
        if i % 24 in SONNENMINUTEN_JE_UTC_STUNDE:
            assert minuten == SONNENMINUTEN_JE_UTC_STUNDE[i % 24], (i, minuten)
        je_tag[stunde["zeit"][:10]] += minuten

    # Je Ortstag 8 Sonnenstunden (480 min): 0+15+30+45+60*5+45+30+15.
    tage = [(basis + timedelta(days=d)).astimezone(BERLIN).date().isoformat() for d in range(3)]
    assert [je_tag[tag] for tag in tage] == [480, 480, 480]


def test_zeitraum_ueber_sieben_tage_wird_begrenzt():
    """AC-14: 10 Tage angefragt -> begrenzt, tatsaechliches Ende = von + 7 Tage."""
    basis = _basis()
    resp = _abruf({**MUENSTER, "von": basis.isoformat(),
                   "bis": (basis + timedelta(days=10)).isoformat()})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["begrenzt"] is True
    assert body["von"] == _ortszeit(basis)
    assert body["bis"] == _ortszeit(basis + timedelta(days=7))
    # Entscheidung: hoechstens 168 Stundeneintraege (7 x 24 h absolut).
    assert len(body["stunden"]) == 168


@freeze_time("2026-10-20T12:00:00Z")
def test_begrenzung_ueber_die_zeitumstellung_168_stunden():
    """F004: 21.10.-31.10.2026 in Berlin, Umstellung am 25.10. -> 168 Stunden absolut."""
    resp = _abruf({**MUENSTER, "von": "2026-10-21T00:00", "bis": "2026-10-31T00:00"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["begrenzt"] is True
    assert body["von"] == "2026-10-21T00:00:00+02:00"
    # 7 x 24 Stunden nach Mitternacht (Sommerzeit) enden um 23:00 Winterzeit.
    assert body["bis"] == "2026-10-27T23:00:00+01:00"
    zeiten = [s["zeit"] for s in body["stunden"]]
    assert len(zeiten) == 168
    assert zeiten[0].endswith("+02:00") and zeiten[-1].endswith("+01:00")
    assert "2026-10-25T01:00:00+02:00" in zeiten and "2026-10-25T03:00:00+01:00" in zeiten
    # Die doppelte Stunde 02:00 (+02:00, dann +01:00) ist hier nicht pruefbar:
    # freezegun ersetzt datetime durch FakeDatetime, dessen astimezone() das
    # fold-Bit verliert. Ausserhalb von freezegun liefert local_dt() beide.


def test_bis_wird_auf_die_volle_stunde_aufgerundet():
    jetzt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    resp = _abruf({**FRANKFURT, "von": _ortszeit(jetzt),
                   "bis": _ortszeit(jetzt + timedelta(minutes=90))})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["bis"] == _ortszeit(jetzt + timedelta(hours=2))
    assert len(body["stunden"]) == 2


def test_zeitraum_ausserhalb_der_vorhersage_422_mit_katalogtext():
    """F001: kein leeres 200, sondern ein Hinweis."""
    basis = _basis()
    resp = _abruf({**FRANKFURT, "von": (basis - timedelta(days=10)).isoformat(),
                   "bis": (basis - timedelta(days=9)).isoformat()})
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["code"] == "mcp_zeitraum_ausserhalb"
    assert body["detail"] == t("api.fehler.mcp_zeitraum_ausserhalb", "de")


def test_ueberlange_zeitangabe_wird_abgewiesen():
    """Parametergrenze 40 Zeichen, auch wenn der Text sonst gueltiges ISO 8601 waere."""
    jetzt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    lokal = jetzt.astimezone(BERLIN)
    stunden = int(lokal.utcoffset() / timedelta(hours=1))
    lang = lokal.strftime("%Y-%m-%dT%H:%M:%S.000000") + f"+{stunden:02d}:00:00.000000"
    assert len(lang) == 42 and datetime.fromisoformat(lang) == jetzt
    resp = _abruf({**FRANKFURT, "von": lang})
    assert resp.status_code == 422, resp.text


def test_zeitraum_bis_sieben_tage_bleibt_unbegrenzt():
    basis = _basis()
    resp = _abruf({**MUENSTER, "von": basis.isoformat(),
                   "bis": (basis + timedelta(days=7)).isoformat()})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["begrenzt"] is False
    assert body["bis"] == _ortszeit(basis + timedelta(days=7))


def test_ohne_zeitraum_die_naechsten_24_stunden():
    jetzt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    resp = _abruf(FRANKFURT)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["von"] == _ortszeit(jetzt)
    assert body["bis"] == _ortszeit(jetzt + timedelta(hours=24))
    assert body["stunden"][0]["zeit"] == _ortszeit(jetzt)


@pytest.mark.parametrize(("params", "code", "text"), [
    ({"von": "morgen frueh"}, "mcp_zeitpunkt_ungueltig",
     t("api.fehler.mcp_zeitpunkt_ungueltig", "de", parameter="von")),
    ({"von": "2026-11-22T14:00:00+01:00", "bis": "2026-11-22T13:00:00+01:00"},
     "mcp_bis_vor_von", t("api.fehler.mcp_bis_vor_von", "de")),
    # F003: von == bis ist kein Zeitraum, auch nicht innerhalb einer Stunde.
    ({"von": "2026-11-22T14:30:00+01:00", "bis": "2026-11-22T14:30:00+01:00"},
     "mcp_bis_vor_von", t("api.fehler.mcp_bis_vor_von", "de")),
])
def test_ungueltiger_zeitraum_wird_abgewiesen(params, code, text):
    resp = _abruf({**FRANKFURT, **params})
    assert resp.status_code == 422, resp.text
    assert resp.json() == {"code": code, "detail": text}


def test_ohne_core_auth_abgelehnt():
    client = TestClient(app)
    client.headers.pop(CORE_AUTH_HEADER, None)
    assert CORE_AUTH_HEADER not in client.headers
    resp = client.get(PFAD, params=FRANKFURT)
    assert resp.status_code == 401
    assert "stunden" not in resp.text


def test_wetterdienst_stoerung_liefert_502_mit_katalogtext(monkeypatch, tmp_path):
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(tmp_path))  # leer: Anbieter wirft
    resp = _abruf(FRANKFURT)
    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert detail["error"] == "provider_error"
    assert detail["detail"] == t("api.fehler.wetterdienst_fehler", "de")
    assert str(tmp_path) not in resp.text
