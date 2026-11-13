"""Testluecken aus der Gegenpruefung von #2961: je ein Test, der die genannte
Verfaelschung der Implementierung faengt. Echte Funktionen, echte Dateien;
ersetzt sind nur Transportgrenzen (SMTP-Socket, IMAP-Verbindung).
"""
from __future__ import annotations

import email
import json
import socket
import threading
import time

import pytest

from app.config import Settings
from app.loader import get_data_dir
from services.inbound_email_reader import InboundEmailReader
from tests.tdd._befehl_e2e_fixtures import (
    _FakeImap,
    _mime_plain,
    basis_settings,
    install_transport_fakes,
    lege_lage_an,
    user_ids,
)

__all__ = ["user_ids"]

NAME = "<img src=x onerror=1>"
ID_MIT_ZEILENENDE = "trip-zeilenende\n"


# ─────────────── HTML-Escaping: Starkregen-Hinweis, Segmentbezug ─────────────

def test_starkregen_hinweis_wird_escaped():
    from output.renderers.email.starkregen_hint import render_starkregen_hint_html

    html = render_starkregen_hint_html(f"Regen bei {NAME}")
    assert "<img" not in html and "&lt;img src=x onerror=1&gt;" in html


def test_segmentbezug_amtlicher_warnung_wird_escaped():
    from services.official_alerts.models import OfficialAlert
    from output.renderers.alert.official_alerts import render_official_alerts_html

    alarm = OfficialAlert(source="dwd", hazard="thunderstorm", level=3, label="Gewitter")
    html = render_official_alerts_html([(f"Region {NAME}", [alarm])],
                                       segment_refs={id(alarm): f"Etappe {NAME}"})
    assert "<img" not in html
    assert html.count("&lt;img src=x onerror=1&gt;") == 2


# ─────────────── Mail-Eingang: Drossel und eigene Adressen ──────────────────

def test_drossel_greift_auch_bei_unbekanntem_trip(monkeypatch, user_ids):
    rec = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    reader = InboundEmailReader()
    for _ in range(7):
        roh = _mime_plain(nutzer.mail_to, "Re: [Gibt es nicht] Etappe", "Hilfe")
        reader._process_single(_FakeImap(roh), b"1", basis_settings())
    assert len([m for m in rec.emails if nutzer.mail_to in m["to"]]) == 5


@pytest.mark.parametrize("feld", ["mail_from", "inbound_address", "smtp_user"])
def test_jede_eigene_adresse_einzeln_ist_kein_befehlsgeber(feld):
    adressen = {
        "mail_from": "absender@henemm.com",
        "inbound_address": "eingang@henemm.com",
        "smtp_user": "postfach@henemm.com",
    }
    eigene = adressen[feld]
    settings = basis_settings(email_verified_at="2026-01-01T00:00:00Z",
                              mail_to="nutzer@example.org", **adressen)
    msg = email.message_from_bytes(_mime_plain(eigene, "Re: [T] x", "Hilfe"))
    assert InboundEmailReader()._authorize(eigene, settings, msg) is False
    # Gegenprobe: die echte Nutzeradresse bleibt Befehlsgeber
    nutzer = email.message_from_bytes(_mime_plain("nutzer@example.org", "Re: [T] x", "Hilfe"))
    assert InboundEmailReader()._authorize("nutzer@example.org", settings, nutzer) is True


# ─────────────── IMAP: Zeitgrenze wirkt ──────────────────────────────────────

def test_imap_zeitgrenze_beendet_stummen_server(monkeypatch):
    from services import inbound_email_reader as mod

    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    verbindungen: list = []

    def _annehmen():
        try:
            conn, _ = srv.accept()
            verbindungen.append(conn)  # nimmt an, sagt aber nie etwas
        except OSError:
            pass

    threading.Thread(target=_annehmen, daemon=True).start()
    monkeypatch.setattr(mod, "IMAP_TIMEOUT_SECONDS", 0.5)
    s = Settings(imap_host="127.0.0.1", imap_port=srv.getsockname()[1],
                 smtp_host="127.0.0.1", smtp_user="u@example.org", smtp_pass="x")
    start = time.monotonic()
    ergebnis = InboundEmailReader()._poll_inbox(s, "u@example.org", "x")
    dauer = time.monotonic() - start
    srv.close()
    for c in verbindungen:
        c.close()
    assert ergebnis == (0, 1)
    assert dauer < 5, f"ohne Zeitgrenze haengt der Abruf ({dauer:.1f}s)"


# ─────────────── GPX-Parser: kein Ablagepfad im Meldungstext ────────────────

def test_gpx_parser_meldung_ohne_ablagepfad(tmp_path):
    from core.gpx_parser import GPXParseError, parse_gpx

    ordner = tmp_path / "geheimer-ablageordner"
    ordner.mkdir()
    leer = ordner / "leer.gpx"
    leer.write_text("")
    with pytest.raises(GPXParseError) as fehler:
        parse_gpx(leer)
    assert "geheimer-ablageordner" not in str(fehler.value)
    with pytest.raises(GPXParseError) as fehler:
        parse_gpx(ordner / "fehlt.gpx")
    assert "geheimer-ablageordner" not in str(fehler.value)


# ─────────────── Kennung mit Zeilenende an den Aufrufstellen ────────────────

def _briefing_mit_zeilenende(user_id: str, inhalt: dict):
    d = get_data_dir(user_id) / "briefings"
    d.mkdir(parents=True, exist_ok=True)
    pfad = d / f"{ID_MIT_ZEILENENDE}.json"
    pfad.write_text(json.dumps(inhalt))
    return pfad


def test_validator_laedt_keine_kennung_mit_zeilenende():
    from api.routers.validator import _load_trip_raw

    _briefing_mit_zeilenende("id-zeile-a", {"id": "x", "name": "x", "stages": []})
    assert _load_trip_raw("id-zeile-a", ID_MIT_ZEILENENDE) is None


def test_vorschau_lehnt_kennung_mit_zeilenende_ab():
    from services.preview_service import PreviewService

    _briefing_mit_zeilenende("id-zeile-b", {"id": "x", "name": "x", "stages": []})
    with pytest.raises(ValueError, match="invalid trip_id"):
        PreviewService(settings=Settings(_env_file=None))._load_trip(ID_MIT_ZEILENENDE, "id-zeile-b")


def test_vergleichsstatus_schreibt_keine_kennung_mit_zeilenende():
    from services.scheduler_dispatch_service import (
        resume_compare_preset, save_compare_preset_pause, save_compare_preset_status,
    )

    inhalt = {"id": "x", "kind": "vergleich", "name": "v", "schedule": "manual"}
    pfad = _briefing_mit_zeilenende("id-zeile-c", inhalt)
    assert save_compare_preset_status("id-zeile-c", ID_MIT_ZEILENENDE, "Ort") is None
    assert save_compare_preset_pause("id-zeile-c", ID_MIT_ZEILENENDE) is None
    assert resume_compare_preset("id-zeile-c", ID_MIT_ZEILENENDE) == "not_found"
    assert json.loads(pfad.read_text()) == inhalt


# ─────────────── Profil: kein Telegram-Rueckfall, Profil kein dict ──────────

def test_ohne_profil_kein_telegram_chat_ausserhalb_testmodus():
    s = Settings(_env_file=None, env="production", telegram_chat_id="betreiber-chat",
                 mail_to="betreiber@example.org").with_user_profile("ohne-profil-tg")
    assert s.telegram_chat_id is None and s.mail_to is None


@pytest.mark.parametrize("inhalt", ["[1, 2]", '"text"', "42"])
def test_profil_das_kein_objekt_ist_gibt_keinen_empfaenger(inhalt):
    user_id = "profil-kein-objekt"
    d = get_data_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(inhalt)
    s = Settings(_env_file=None, env="production", telegram_chat_id="betreiber-chat",
                 mail_to="betreiber@example.org").with_user_profile(user_id)
    assert s.mail_to is None and s.telegram_chat_id is None
