"""Kern-Schicht: nicht-blockierender flock auf den Poll-Endpunkten
``/api/scheduler/inbound-sms`` und ``/api/scheduler/inbound-commands``
(Issue #2439 Scheibe a, "Webhook = Weckruf").

Spec: docs/specs/modules/feat_2439_befehle_push_eingang.md

AC-Zuordnung:
  AC-6  Belegter Lock -> ``{"status":"busy"}`` SOFORT, ohne Reader-Aufruf,
        Zeigerdatei ``premium_sms_inbound.json`` unveraendert; der Admin-Proxy-
        Pfad ``/inbound-commands`` laeuft in denselben Lock wie der Push-Pfad.
  AC-5  (Python-Seite) Der Lock wird nach jedem Lauf freigegeben, auch nach
        einem Reader-Fehler -- sonst bliebe der Kanal fuer immer "busy".
  AC-7  (Python-Seite) ``/inbound-sms`` meldet ``processed`` (int), damit Go den
        Nachversuch steuern kann.

Lock-Dateien (Vorgabe der Spec): ``get_data_root()/diagnostics/``
``inbound_sms_poll.lock`` bzw. ``inbound_command_poll.lock``.

Echter flock: der Test haelt den Lock ueber einen EIGENEN Dateideskriptor
(fcntl.flock LOCK_EX|LOCK_NB). flock-Sperren gelten je offener Dateibeschreibung,
konkurrieren also auch innerhalb desselben Prozesses mit dem Lock des Endpunkts.
Kein Mock der Sperre. Der Reader-Aufruf wird nur AUFGEZEICHNET (Recorder-Ersatz
fuer ``poll_and_process``), wo ein echter Lauf Netz braeuchte (IMAP).

Datenwurzel: ``tests/conftest.py::_isolate_data_root`` biegt sie auf ein
tmp-Verzeichnis um; der Test arbeitet nur ueber ``get_data_root()``.
"""
from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import scheduler
from app.loader import get_data_root
from tests.tdd._befehl_e2e_fixtures import install_transport_fakes

SMS_LOCK = "inbound_sms_poll.lock"
MAIL_LOCK = "inbound_command_poll.lock"
POINTER = "premium_sms_inbound.json"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(scheduler.router)
    # raise_server_exceptions=False: ein Reader-Fehler wird HTTP 500, der Test
    # prueft danach, dass der Lock trotzdem frei ist.
    return TestClient(app, raise_server_exceptions=False)


def _diagnostics() -> Path:
    d = get_data_root() / "diagnostics"
    d.mkdir(parents=True, exist_ok=True)
    return d


@contextmanager
def _lock_gehalten(name: str):
    """Haelt den echten flock auf der von der Spec vorgegebenen Lock-Datei."""
    pfad = _diagnostics() / name
    fd = open(pfad, "a+")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield pfad
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            fd.close()


class _ReaderAufrufe:
    """Zeichnet auf, ob der Reader laeuft (echter Ersatz, kein Rueckspiegeln)."""

    def __init__(self, ergebnis: int = 0, fehler: Exception | None = None):
        self.aufrufe = 0
        self._ergebnis = ergebnis
        self._fehler = fehler

    def __call__(self, *_a, **_kw):
        self.aufrufe += 1
        if self._fehler is not None:
            raise self._fehler
        return self._ergebnis


def _mail_reader_aufzeichnen(monkeypatch, **kw) -> _ReaderAufrufe:
    from services import inbound_email_reader

    rec = _ReaderAufrufe(**kw)
    monkeypatch.setattr(inbound_email_reader.InboundEmailReader, "poll_and_process", rec)
    return rec


def _sms_reader_aufzeichnen(monkeypatch, **kw) -> _ReaderAufrufe:
    from services import inbound_sms_reader

    rec = _ReaderAufrufe(**kw)
    monkeypatch.setattr(inbound_sms_reader.InboundSmsReader, "poll_and_process", rec)
    return rec


# ---------------------------------------------------------------------------
# AC-6: /inbound-sms
# ---------------------------------------------------------------------------

def test_ac6_inbound_sms_busy_bei_gehaltenem_lock_ohne_reader_und_zeigerdatei_unveraendert(
    client, monkeypatch
):
    install_transport_fakes(monkeypatch)
    zeiger = _diagnostics() / POINTER
    zeiger.write_text(json.dumps({"last_seen_id": "41"}), encoding="utf-8")
    vorher = zeiger.read_bytes()
    reader = _sms_reader_aufzeichnen(monkeypatch, ergebnis=1)

    with _lock_gehalten(SMS_LOCK):
        antwort = client.post("/api/scheduler/inbound-sms")

    assert antwort.status_code == 200, antwort.text
    assert antwort.json() == {"status": "busy"}, antwort.text
    assert reader.aufrufe == 0, "bei belegtem Lock darf der Reader NICHT laufen"
    assert zeiger.read_bytes() == vorher, "Zeigerdatei (last_seen_id) darf nicht angefasst werden"


def test_ac6_inbound_sms_ohne_gehaltenen_lock_nicht_busy_und_meldet_processed(
    client, monkeypatch
):
    """Echter Reader, leeres Journal (aufgezeichneter Transport): Lauf geschieht,
    Ergebnis enthaelt ``processed`` als int (AC-7-Voraussetzung fuer Go)."""
    install_transport_fakes(monkeypatch)

    antwort = client.post("/api/scheduler/inbound-sms")

    assert antwort.status_code == 200, antwort.text
    body = antwort.json()
    assert body.get("status") != "busy", body
    assert "processed" in body, f"Antwort muss 'processed' (int) tragen: {body}"
    assert isinstance(body["processed"], int) and not isinstance(body["processed"], bool), body
    assert body["processed"] == 0, body


def test_ac5_inbound_sms_lock_wird_nach_lauf_und_nach_reader_fehler_freigegeben(
    client, monkeypatch
):
    install_transport_fakes(monkeypatch)
    # 1) normaler Lauf
    _sms_reader_aufzeichnen(monkeypatch, ergebnis=0)
    assert client.post("/api/scheduler/inbound-sms").json().get("status") != "busy"
    assert client.post("/api/scheduler/inbound-sms").json().get("status") != "busy", (
        "nach einem Lauf muss der Lock frei sein"
    )
    # 2) Reader wirft -> HTTP 500, Lock trotzdem frei
    _sms_reader_aufzeichnen(monkeypatch, fehler=RuntimeError("Journal kaputt"))
    assert client.post("/api/scheduler/inbound-sms").status_code == 500
    _sms_reader_aufzeichnen(monkeypatch, ergebnis=0)
    assert client.post("/api/scheduler/inbound-sms").json().get("status") != "busy", (
        "nach einem Reader-Fehler muss der Lock freigegeben sein (kein dauerhaftes busy)"
    )


# ---------------------------------------------------------------------------
# AC-6: /inbound-commands (Admin-Proxy-Pfad laeuft in denselben Lock)
# ---------------------------------------------------------------------------

def test_ac6_inbound_commands_busy_bei_gehaltenem_lock_ohne_reader(client, monkeypatch):
    install_transport_fakes(monkeypatch)
    reader = _mail_reader_aufzeichnen(monkeypatch, ergebnis=1)

    with _lock_gehalten(MAIL_LOCK):
        antwort = client.post("/api/scheduler/inbound-commands")

    assert antwort.status_code == 200, antwort.text
    assert antwort.json() == {"status": "busy"}, antwort.text
    assert reader.aufrufe == 0, "bei belegtem Lock darf der IMAP-Reader NICHT laufen"


def test_ac6_inbound_commands_ohne_gehaltenen_lock_laeuft_der_reader(client, monkeypatch):
    install_transport_fakes(monkeypatch)
    reader = _mail_reader_aufzeichnen(monkeypatch, ergebnis=0)

    antwort = client.post("/api/scheduler/inbound-commands")

    assert antwort.status_code == 200, antwort.text
    assert antwort.json().get("status") != "busy", antwort.text
    assert reader.aufrufe == 1, "ohne gehaltenen Lock muss der Reader genau einmal laufen"
    # und der Lock ist danach wieder frei
    assert client.post("/api/scheduler/inbound-commands").json().get("status") != "busy"
    assert reader.aufrufe == 2


def test_ac5_inbound_commands_lock_wird_nach_reader_fehler_freigegeben(client, monkeypatch):
    install_transport_fakes(monkeypatch)
    _mail_reader_aufzeichnen(monkeypatch, fehler=RuntimeError("IMAP kaputt"))
    assert client.post("/api/scheduler/inbound-commands").status_code == 500

    reader = _mail_reader_aufzeichnen(monkeypatch, ergebnis=0)
    antwort = client.post("/api/scheduler/inbound-commands")

    assert antwort.json().get("status") != "busy", antwort.text
    assert reader.aufrufe == 1


# ---------------------------------------------------------------------------
# Kanaltrennung: der SMS-Lock sperrt nicht den Mail-Pfad und umgekehrt
# ---------------------------------------------------------------------------

def test_sms_lock_sperrt_den_mail_pfad_nicht(client, monkeypatch):
    install_transport_fakes(monkeypatch)
    mail = _mail_reader_aufzeichnen(monkeypatch, ergebnis=0)

    with _lock_gehalten(SMS_LOCK):
        antwort = client.post("/api/scheduler/inbound-commands")

    assert antwort.json().get("status") != "busy", antwort.text
    assert mail.aufrufe == 1


def test_mail_lock_sperrt_den_sms_pfad_nicht(client, monkeypatch):
    install_transport_fakes(monkeypatch)
    sms = _sms_reader_aufzeichnen(monkeypatch, ergebnis=0)

    with _lock_gehalten(MAIL_LOCK):
        antwort = client.post("/api/scheduler/inbound-sms")

    assert antwort.json().get("status") != "busy", antwort.text
    assert sms.aufrufe == 1
