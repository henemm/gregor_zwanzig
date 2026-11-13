"""Strenge Pruefung von Kennungen und Konfiguration im Python-Core (#2961, AC-7).

- Der Bergfex-Kurzname besteht nur aus ``[a-z0-9-]``; Weiterleitungen werden
  nicht verfolgt.
- Geheimnis-Felder erscheinen nie in der Darstellung von ``Settings``.
- Ohne lesbares Nutzerprofil gibt es keinen Mail-Empfaenger.
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest

from app.config import Settings
from app.loader import get_data_dir

@pytest.mark.parametrize("slug", ["../konto", "a/b", "Hochfuegen", "a?x=1", "a#b", "", "hoch fuegen"])
def test_bergfex_kurzname_nur_kleinbuchstaben_ziffern_bindestrich(slug):
    from validation.ground_truth import BergfexScraper

    with pytest.raises(ValueError):
        BergfexScraper().get_snow_report(slug)


def test_bergfex_folgt_keiner_weiterleitung(monkeypatch):
    from validation.ground_truth import BergfexScraper

    aufrufe: list[str] = []

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *_a):
            pass

        def do_GET(self):  # noqa: N802
            aufrufe.append(self.path)
            if self.path == "/hochfuegen/":
                self.send_response(302)
                self.send_header("Location", "/anderswo/")
                self.end_headers()
                return
            body = b"Mountain:</span> <span>110 cm</span>"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(BergfexScraper, "BASE_URL", f"http://127.0.0.1:{srv.server_port}")
        with pytest.raises(httpx.HTTPStatusError):
            BergfexScraper().get_snow_report("hochfuegen")
    finally:
        srv.shutdown()
    assert aufrufe == ["/hochfuegen/"]


GEHEIMNISSE = {
    "smtp_pass": "geheim-smtp", "imap_pass": "geheim-imap", "test_smtp_pass": "geheim-test-smtp",
    "test_imap_pass": "geheim-test-imap", "telegram_bot_token": "1:geheim-bot",
    "telegram_test_bot_token": "2:geheim-testbot", "seven_api_key": "geheim-seven",
    "seven_sandbox_key": "geheim-sandbox", "core_shared_secret": "geheim-core-0123456789abcdef0123",
}


def test_settings_darstellung_zeigt_keine_geheimnisse():
    felder = {k: v for k, v in GEHEIMNISSE.items() if k in Settings.model_fields}
    s = Settings(_env_file=None, **felder)
    text = repr(s) + str(s)
    for wert in felder.values():
        assert wert not in text


def test_alle_geheimnisfelder_sind_als_sensibel_markiert():
    sensibel = set(Settings(_env_file=None)._SENSITIVE_FIELDS)
    verdaechtig = {
        name for name in Settings.model_fields
        if any(w in name for w in ("pass", "token", "secret", "api_key", "sandbox_key"))
    }
    assert verdaechtig <= sensibel, sorted(verdaechtig - sensibel)


@pytest.mark.parametrize("profil", [None, "{kaputt"])
def test_ohne_lesbares_profil_kein_mail_empfaenger(profil):
    user_id = "ohne-profil" if profil is None else "kaputtes-profil"
    d = get_data_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    if profil is not None:
        (d / "user.json").write_text(profil)
    s = Settings(_env_file=None, mail_to="betreiber@example.org").with_user_profile(user_id)
    assert s.mail_to is None
