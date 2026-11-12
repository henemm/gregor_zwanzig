"""Fehlerantworten nach aussen nennen keine internen Details (#2961, AC-5).

Ausnahmetexte (Pfade, Hostnamen, Konfigurationsnamen) gehoeren ins Log; der
Client bekommt einen Katalogtext in seiner Sprache.
"""
from __future__ import annotations

import json
import logging

import pytest

from app.config import Settings
from app.loader import get_data_dir
from i18n import t


def test_api_fehler_ohne_code_liefert_katalogtext():
    from api.fehler import UNBEKANNT, api_fehler_aus, meldung_aus

    exc = ValueError("Datei /srv/geheim/data/users/x/trip.json kaputt")
    fehler = api_fehler_aus(exc, 422, None)
    assert fehler.detail == t("api.fehler.unbekannt", "de")
    assert fehler.code == UNBEKANNT
    assert "/srv" not in meldung_aus(exc, None)


def test_api_fehler_mit_code_bleibt_lokalisiert():
    from api.fehler import api_fehler_aus
    from services.fehler_code import fehler_mit_code

    exc = fehler_mit_code(ValueError, "gpx_nur_gpx", filename="a.txt")
    assert api_fehler_aus(exc, 400, None).detail == t("api.fehler.gpx_nur_gpx", "de", filename="a.txt")


@pytest.fixture
def ohne_postausgang(monkeypatch):
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for key in ("GZ_SMTP_HOST", "GZ_SMTP_USER", "GZ_SMTP_PASS", "GZ_IS_TEST_MODE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GZ_ENV", "production")


def test_kanaltest_meldet_generischen_text_und_loggt_details(ohne_postausgang, caplog):
    from services.channel_test_service import send_test_message

    user_id = "fehlertext-nutzer"
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({
        "id": user_id, "mail_to": "a@example.org", "email": "a@example.org",
        "email_verified_at": "2026-10-01T08:00:00Z",
    }))
    with caplog.at_level(logging.WARNING):
        ergebnis = send_test_message("email", user_id)
    assert ergebnis == {"error": t("versand.test.fehlgeschlagen", "de")}
    assert "smtp" not in ergebnis["error"].lower()
    assert any("smtp" in r.getMessage().lower() for r in caplog.records)


def test_gpx_fehlertext_nennt_keinen_pfad():
    from fastapi.testclient import TestClient

    from api.main import app

    resp = TestClient(app).post(
        "/api/gpx/parse", params={"user_id": "fehlertext-nutzer"},
        files={"file": ("kaputt.gpx", b"<gpx", "application/gpx+xml")},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "gpx_ungueltig"
    assert "data/users" not in body["detail"] and "/" not in body["detail"]
