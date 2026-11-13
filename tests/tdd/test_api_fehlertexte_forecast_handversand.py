"""Forecast- und Handversand-Endpunkt geben keine rohen Ausnahmetexte heraus (#2961, AC-5).

Die Stoerung wird an der Dienstgrenze eingespeist (Wetterdienst bzw.
Vergleichsversand werfen eine Ausnahme mit internem Text); geprueft wird die
echte Antwort des Routers ueber die ASGI-App.
"""
from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from api.main import app
from i18n import t

INTERNA = "Verbindung zu http://10.0.0.7:8443/intern fehlgeschlagen, Pfad /srv/gregor/data"


def test_forecast_502_ohne_ausnahmetext(monkeypatch, caplog):
    from services import forecast as forecast_mod

    def _kaputt(self, *a, **kw):
        raise RuntimeError(INTERNA)

    monkeypatch.setattr(forecast_mod.ForecastService, "get_forecast", _kaputt)
    with caplog.at_level(logging.WARNING):
        resp = TestClient(app).get("/forecast", params={"lat": 47.0, "lon": 11.0})
    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert detail["error"] == "provider_error"
    assert detail["detail"] == t("api.fehler.wetterdienst_fehler", "de")
    assert "10.0.0.7" not in resp.text and "/srv" not in resp.text
    assert any("10.0.0.7" in r.getMessage() for r in caplog.records)


def test_handversand_vergleich_valueerror_ohne_ausnahmetext(monkeypatch, caplog):
    from api.routers import briefings_send

    def _kaputt(user_id, entity_id):
        raise ValueError(INTERNA)

    monkeypatch.setattr(briefings_send, "send_compare_preset", _kaputt)
    with caplog.at_level(logging.WARNING):
        resp = TestClient(app).post(
            "/api/briefings/cp-x/send", params={"kind": "vergleich", "user_id": "fehlertext-hv"},
        )
    assert resp.json()["code"] == "invalid_preset", resp.text
    assert "10.0.0.7" not in resp.text and "/srv" not in resp.text
    assert t("api.fehler.unbekannt", "de") in resp.json()["detail"]
    assert any("10.0.0.7" in r.getMessage() for r in caplog.records)


def test_ortsfehler_im_vergleich_ist_katalogtext(caplog):
    """Ortsfehler erscheinen in Vergleichs-Mail, Telegram und /api/compare."""
    from services.comparison_engine import _abruf_fehlertext

    with caplog.at_level(logging.WARNING):
        text = _abruf_fehlertext(INTERNA, "fehlertext-vergleich")
    assert text == t("vergleich.ort.abruf_fehlgeschlagen", "de")
    assert any("10.0.0.7" in r.getMessage() for r in caplog.records)
