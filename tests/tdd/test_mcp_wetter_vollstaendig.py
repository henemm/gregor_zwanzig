"""MCP „Gregor Wetter“ vollstaendig, Scheibe S1: alle Katalog-Metriken + ``felder`` (Issue #3398).

SPEC: docs/specs/modules/mcp_wetter_vollstaendig.md — AC-1 bis AC-5 (Datenebene).

Geprueft wird die echte Antwort von ``GET /api/_internal/mcp/wetter`` gegen den
offline ``FixtureProvider`` (``tests/fixtures/mcp_wetter/innsbruck.json``, fuer
#3398 um alle uebrigen waehlbaren Katalogfelder ergaenzt). Die erwartete
Feldmenge wird zur Laufzeit aus ``get_all_metrics()`` berechnet (kein
Patchen des Katalogs): jede heute oder kuenftig waehlbare Metrik muss
automatisch in der Antwort erscheinen.

Bekannte Luecke der Offline-Schicht: ``FixtureProvider`` ignoriert
``enrich_snow`` und liest nur einen Teil der Fixture-Schluessel. Die
Umsetzung muss ihn (Testinfrastruktur) um die neuen Felder erweitern.

Fehlercode bei unbekanntem Feld: ``mcp_feld_unbekannt`` (HTTP 422), Katalogtext
``api.fehler.mcp_feld_unbekannt`` mit den Platzhaltern ``feld`` und ``gueltig``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from app.metric_catalog import get_all_metrics
from i18n import t

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "mcp_wetter"
PFAD = "/api/_internal/mcp/wetter"
FRANKFURT = {"lat": 50.1106444, "lon": 8.6820917}
INNSBRUCK = {"lat": 47.2692, "lon": 11.4041}
NIE = {"confidence_pct", "cape_jkg"}


@pytest.fixture(autouse=True)
def _tagesgang_fixture(monkeypatch):
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(FIXTURE_DIR))


def _erwartete_felder() -> set[str]:
    """Aus dem Katalog: dedupliziert, Strahlung nur als sonnenminuten, plus wmo_code."""
    felder = {m.dp_field for m in get_all_metrics()} - {"dni_wm2"}
    return (felder | {"sonnenminuten", "wmo_code"}) - NIE


def _abruf(**params):
    jetzt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    basis = {**FRANKFURT, "von": jetzt.isoformat(),
             "bis": (jetzt + timedelta(hours=6)).isoformat()}
    return TestClient(app).get(PFAD, params={**basis, **params})


def _stundenfelder(body: dict) -> set[str]:
    return {k for s in body["stunden"] for k in s} - {"zeit"}


def test_ac1_stundenfelder_entsprechen_dem_katalog():
    """AC-1: Feldmenge ueber alle Stunden == aus dem Katalog abgeleitete Menge."""
    resp = _abruf()
    assert resp.status_code == 200, resp.text
    body = resp.json()
    erwartet = _erwartete_felder()
    assert _stundenfelder(body) == erwartet, (
        f"fehlt: {sorted(erwartet - _stundenfelder(body))}, "
        f"zu viel: {sorted(_stundenfelder(body) - erwartet)}")


def test_ac1_jedes_feld_hat_eine_katalogeinheit():
    body = _abruf().json()
    katalog: dict[str, str] = {}
    for m in get_all_metrics():
        katalog.setdefault(m.dp_field, m.unit)
    einheiten = body["einheiten"]
    for feld in _stundenfelder(body):
        assert feld in einheiten, f"{feld} ohne Einheit"
    for feld, einheit in katalog.items():
        if feld == "dni_wm2":
            continue
        assert einheiten.get(feld) == einheit, (feld, einheiten.get(feld), einheit)
    assert einheiten["sonnenminuten"] == "min"


def test_ac2_nie_confidence_und_cape_auch_nicht_mit_felder():
    body = _abruf().json()
    assert not (_stundenfelder(body) & NIE)
    assert not (set(body["einheiten"]) & NIE)
    resp = _abruf(felder="t2m_c")
    assert resp.status_code == 200, resp.text
    assert not (set(resp.json()["einheiten"]) & NIE)


def test_ac3_gefuehlte_temperatur_in_jeder_stunde_mit_einheit():
    body = _abruf().json()
    assert body["stunden"], body
    for stunde in body["stunden"]:
        assert "wind_chill_c" in stunde, stunde
    assert body["einheiten"]["wind_chill_c"] == "°C"


def test_ac4_enrich_snow_wird_wie_im_briefing_angefordert(monkeypatch):
    """AC-4 (Offline-Naeherung): Der Abruf fordert die SNOWGRID-Anreicherung an.

    Die Alpen-Abgrenzung selbst macht ``_should_enrich_snow`` im Provider
    (bestehende Tests); hier zaehlt, dass der Endpunkt sie nicht abschaltet.
    Aufzeichnender Wrapper um den echten FixtureProvider, keine erfundenen Werte.
    """
    import providers.base as base
    from providers.fixture import FixtureProvider

    aufrufe: list[bool] = []

    class _Aufzeichnend(FixtureProvider):
        def fetch_forecast(self, location, start=None, end=None,
                           enrich_ensemble=True, enrich_snow=True):
            aufrufe.append(enrich_snow)
            return super().fetch_forecast(location, start, end,
                                          enrich_ensemble, enrich_snow)

    monkeypatch.setattr(base, "get_provider",
                        lambda name, *a, **kw: _Aufzeichnend(str(FIXTURE_DIR)))
    resp = _abruf(**INNSBRUCK)
    assert resp.status_code == 200, resp.text
    assert aufrufe == [True]


def test_ac4_schneefelder_im_alpenort_gefuellt():
    body = _abruf(**INNSBRUCK).json()
    assert body["stunden"][0]["snow_depth_cm"] == 35.0
    assert body["stunden"][0]["snow_new_24h_cm"] == 2.5
    assert body["einheiten"]["snow_depth_cm"] == "cm"


def test_ac5_felder_beschraenkt_stunden_und_einheiten():
    resp = _abruf(felder="wind_chill_c,t2m_c")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert _stundenfelder(body) == {"wind_chill_c", "t2m_c"}
    assert set(body["einheiten"]) == {"wind_chill_c", "t2m_c"}
    assert all("zeit" in s for s in body["stunden"])


def test_ac5_felder_mehrfach_parameter_wird_akzeptiert():
    resp = _abruf(felder=["wind_chill_c", "sonnenminuten"])
    assert resp.status_code == 200, resp.text
    assert _stundenfelder(resp.json()) == {"wind_chill_c", "sonnenminuten"}


def test_ac5_ohne_felder_alle_felder():
    assert _stundenfelder(_abruf().json()) == _erwartete_felder()


def test_ac5_unbekanntes_feld_422_mit_katalogtext():
    resp = _abruf(felder="t2m_c,gibt_es_nicht")
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["code"] == "mcp_feld_unbekannt"
    assert body["detail"] == t("api.fehler.mcp_feld_unbekannt", "de",
                               feld="gibt_es_nicht",
                               gueltig=", ".join(sorted(_erwartete_felder())))
    assert "wind_chill_c" in body["detail"]


def test_ac5_confidence_als_feld_ist_unbekannt():
    resp = _abruf(felder="confidence_pct")
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "mcp_feld_unbekannt"
