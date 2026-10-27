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
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import scheduler
from app.loader import get_data_root
from tests.tdd._befehl_e2e_fixtures import (
    _mime_plain,
    install_transport_fakes,
    lege_lage_an,
    user_ids,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

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
    monkeypatch.setattr(
        inbound_email_reader.InboundEmailReader, "poll_and_process", _mit_laufzaehler(rec),
    )
    return rec


def _mit_laufzaehler(aufzeichner):
    """#1405 S4b AC-23: der Router liest ``reader.last_failed_count`` direkt
    (kein ``getattr(..., 0)``-Rueckfall im Produkt) -- der Fake des Mail-Lesers
    setzt den Laufzaehler deshalb selbst, wie es ``poll_and_process`` tut."""
    def _poll(self, *a, **kw):
        self.last_failed_count = 0
        return aufzeichner(*a, **kw)

    return _poll


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


# ---------------------------------------------------------------------------
# Adversary-Luecke F001: /inbound-commands meldet ``processed`` (AC-7 Mail)
# ---------------------------------------------------------------------------
#
# Echter Endpunkt, echter ``InboundEmailReader.poll_and_process`` und echter
# ``_process_single`` -- ersetzt ist NUR die IMAP-Verbindung (Transportgrenze).
# Zwei Befehlsmails bekannter Absender + eine Mail eines unbekannten Absenders
# -> ``processed`` muss genau 2 sein.

class _FakeImapPostfach:
    """Double NUR fuer ``imaplib.IMAP4_SSL``: liefert feste Rohmails je UID."""

    def __init__(self, mails: dict[bytes, bytes]):
        self._mails = mails
        self.gesehen: list[bytes] = []

    def __call__(self, *_a, **_kw):  # Konstruktor-Ersatz: IMAP4_SSL(host, port)
        return self

    def login(self, *_a):
        return "OK", [b"logged in"]

    def select(self, *_a):
        return "OK", [str(len(self._mails)).encode()]

    def search(self, *_a):
        return "OK", [b" ".join(self._mails)]

    def fetch(self, uid, _spec):
        return "OK", [(b"1 (RFC822)", self._mails[uid])]

    def store(self, uid, _flags, _value):
        self.gesehen.append(uid)
        return "OK", []

    def logout(self):
        return "BYE", []


def test_f001_inbound_commands_meldet_processed_gleich_anzahl_befehle_bekannter_absender(
    client, monkeypatch, user_ids
):
    from services import inbound_email_reader

    install_transport_fakes(monkeypatch)
    nutzer_a = lege_lage_an(user_ids, "L2")
    nutzer_b = lege_lage_an(user_ids, "L2")
    betreff = "Re: [Solo-Trip] Etappe"
    postfach = _FakeImapPostfach({
        b"1": _mime_plain(nutzer_a.mail_to, betreff, "Hilfe"),
        b"2": _mime_plain("unbekannt-2439@henemm.com", betreff, "Hilfe"),
        b"3": _mime_plain(nutzer_b.mail_to, betreff, "Hilfe"),
    })
    monkeypatch.setattr(inbound_email_reader.imaplib, "IMAP4_SSL", postfach)

    antwort = client.post("/api/scheduler/inbound-commands")

    assert antwort.status_code == 200, antwort.text
    body = antwort.json()
    assert body.get("status") == "ok", body
    assert "processed" in body, f"Antwort muss 'processed' tragen (Go steuert damit den Nachversuch): {body}"
    assert isinstance(body["processed"], int) and not isinstance(body["processed"], bool), body
    assert body["processed"] == 2, (
        f"genau die 2 Befehle bekannter Absender sind verarbeitet, der unbekannte nicht: {body}"
    )
    assert sorted(postfach.gesehen) == [b"1", b"2", b"3"], "alle drei Mails muessen gelesen sein"


# ---------------------------------------------------------------------------
# Adversary-Luecke F002: der Lock ist EXKLUSIV -- zwei echte, gleichzeitige
# Endpunkt-Aufrufe: der zweite meldet busy, verarbeitet wird genau einmal.
# ---------------------------------------------------------------------------

class _BlockierenderReader:
    """Nur der ERSTE Aufruf blockiert bis ``freigabe``; spaetere kehren sofort
    zurueck (sonst haengt der Test unter einem geteilten Lock)."""

    def __init__(self):
        self.aufrufe = 0
        self.betreten = threading.Event()
        self.freigabe = threading.Event()
        self._mu = threading.Lock()

    def __call__(self, *_a, **_kw):
        with self._mu:
            self.aufrufe += 1
            erster = self.aufrufe == 1
        if erster:
            self.betreten.set()
            self.freigabe.wait(10)
        return 1


def _zwei_gleichzeitige_aufrufe(endpunkt, reader: _BlockierenderReader):
    ergebnis: dict = {}

    def _erster():
        ergebnis["erster"] = endpunkt()

    t = threading.Thread(target=_erster, daemon=True)
    t.start()
    try:
        assert reader.betreten.wait(5), "der erste Aufruf hat den Reader nicht erreicht"
        ergebnis["zweiter"] = endpunkt()
    finally:
        reader.freigabe.set()
        t.join(10)
    assert not t.is_alive(), "der erste Aufruf ist nicht zurueckgekehrt"
    return ergebnis["erster"], ergebnis["zweiter"]


def test_f002_inbound_sms_zwei_gleichzeitige_aufrufe_zweiter_ist_busy(monkeypatch):
    from services import inbound_sms_reader

    install_transport_fakes(monkeypatch)
    reader = _BlockierenderReader()
    monkeypatch.setattr(inbound_sms_reader.InboundSmsReader, "poll_and_process", reader)

    erster, zweiter = _zwei_gleichzeitige_aufrufe(scheduler.trigger_inbound_sms, reader)

    assert zweiter == {"status": "busy"}, f"zweiter gleichzeitiger Aufruf muss busy melden: {zweiter}"
    assert erster.get("status") != "busy" and erster.get("processed") == 1, erster
    assert reader.aufrufe == 1, f"der Journal-Poll darf nur EINMAL laufen, lief {reader.aufrufe}x"
    assert (_diagnostics() / SMS_LOCK).exists(), "Lock-Datei muss unter get_data_root()/diagnostics liegen"


def test_f002_inbound_commands_zwei_gleichzeitige_aufrufe_zweiter_ist_busy(monkeypatch):
    from services import inbound_email_reader

    install_transport_fakes(monkeypatch)
    reader = _BlockierenderReader()
    monkeypatch.setattr(
        inbound_email_reader.InboundEmailReader, "poll_and_process", _mit_laufzaehler(reader),
    )

    erster, zweiter = _zwei_gleichzeitige_aufrufe(scheduler.trigger_inbound, reader)

    assert zweiter == {"status": "busy"}, f"zweiter gleichzeitiger Aufruf muss busy melden: {zweiter}"
    assert erster.get("status") == "ok" and erster.get("processed") == 1, erster
    assert reader.aufrufe == 1, f"der IMAP-Poll darf nur EINMAL laufen, lief {reader.aufrufe}x"
    assert (_diagnostics() / MAIL_LOCK).exists(), "Lock-Datei muss unter get_data_root()/diagnostics liegen"
