"""Mail-Posteingang: keine Schleifen, keine Flut, Rumpf erst nach Autorisierung (#2961).

AC-4: ausgehende Mails sind als automatisch markiert; automatische Mails im
Eingang werden verworfen; Mails von der eigenen Eingangsadresse sind keine
Befehle; Fehlerantworten auf unbekannte Befehle sind je Nutzer gedrosselt.
AC-10: der Abruf holt zuerst nur Kopfzeilen, den Rumpf nur fuer autorisierte
Absender, hoechstens 50 Mails je Lauf, Mails ueber 2 MB werden uebersprungen.

Ersetzt sind nur die Transportgrenzen (IMAP-Verbindung, SMTP-Socket); Reader,
Autorisierung, Befehlsverarbeitung und Antwortversand laufen echt.
"""
from __future__ import annotations

import email

import pytest

from output.channels.email import build_mime_message
from services import inbound_email_reader
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


def _mit_kopf(raw: bytes, kopf: bytes) -> bytes:
    return raw.replace(b"MIME-Version", kopf + b"\r\nMIME-Version", 1)


def _befehlsmail(nutzer, text: str = "Hilfe") -> bytes:
    return _mime_plain(nutzer.mail_to, f"Re: [{nutzer.trip.name}] Etappe", text)


# ─────────────────────────── ausgehend ──────────────────────────────────────

@pytest.mark.parametrize("html", [True, False])
def test_ausgehende_mail_traegt_auto_submitted(html):
    msg = build_mime_message("s", "<p>x</p>" if html else "x", "a@example.org",
                             "b@example.org", None, html, None)
    assert msg["Auto-Submitted"] == "auto-generated"


# ─────────────────────────── eingehend ──────────────────────────────────────

@pytest.mark.parametrize("kopf", [
    b"Auto-Submitted: auto-replied", b"Auto-Submitted: auto-generated",
    b"Precedence: bulk", b"Precedence: junk", b"Precedence: auto_reply",
    b"Precedence: list", b"X-Autoreply: yes",
])
def test_automatische_mail_wird_ohne_antwort_verworfen(monkeypatch, user_ids, kopf):
    rec = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    imap = _FakeImap(_mit_kopf(_befehlsmail(nutzer), kopf))
    assert InboundEmailReader()._process_single(imap, b"1", basis_settings()) == (0, 0)
    assert rec.emails == []
    assert any("Seen" in v for (_, _, v) in imap.stored)


def test_auto_submitted_no_ist_ein_normaler_befehl(monkeypatch, user_ids):
    rec = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    imap = _FakeImap(_mit_kopf(_befehlsmail(nutzer), b"Auto-Submitted: no"))
    assert InboundEmailReader()._process_single(imap, b"1", basis_settings()) == (1, 0)
    assert len(rec.emails) == 1


def test_auto_response_suppress_befehl_wird_ausgefuehrt_und_beantwortet(monkeypatch, user_ids):
    rec = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    imap = _FakeImap(_mit_kopf(_befehlsmail(nutzer, "Hilfe"), b"X-Auto-Response-Suppress: All"))
    assert InboundEmailReader()._process_single(imap, b"1", basis_settings()) == (1, 0)
    assert len(rec.emails) == 1


def test_auto_response_suppress_bekommt_keine_fehlerantwort(monkeypatch, user_ids):
    rec = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    kopf = b"X-Auto-Response-Suppress: All"
    unbekannt = _mit_kopf(_befehlsmail(nutzer, "xyzzy"), kopf)
    assert InboundEmailReader()._process_single(_FakeImap(unbekannt), b"1", basis_settings()) == (1, 0)
    fremder_trip = _mit_kopf(
        _mime_plain(nutzer.mail_to, "Re: [Gibt es nicht] Etappe", "Hilfe"), kopf)
    assert InboundEmailReader()._process_single(_FakeImap(fremder_trip), b"1", basis_settings()) == (0, 0)
    assert rec.emails == []


def _authorize_settings(**kw):
    return basis_settings(email_verified_at="2026-01-01T00:00:00Z", **kw)


@pytest.mark.parametrize("absender", ["gregor+befehle@henemm.com", "postfach@henemm.com"])
def test_mail_von_eigener_eingangsadresse_ist_kein_befehl(absender):
    settings = _authorize_settings(
        mail_to="nutzer@example.org", inbound_address="gregor+befehle@henemm.com",
        smtp_user="postfach@henemm.com",
    )
    msg = email.message_from_bytes(_mime_plain(absender, "Re: [T] x", "Hilfe"))
    assert InboundEmailReader()._authorize(absender, settings, msg) is False


def test_fehlerantworten_auf_unbekannte_befehle_hoechstens_fuenf_je_stunde(monkeypatch, user_ids):
    rec = install_transport_fakes(monkeypatch)
    a = lege_lage_an(user_ids, "L2")
    b = lege_lage_an(user_ids, "L2")
    reader = InboundEmailReader()
    for _ in range(7):
        reader._process_single(_FakeImap(_befehlsmail(a, "xyzzy")), b"1", basis_settings())
    an_a = [m for m in rec.emails if a.mail_to in m["to"]]
    assert len(an_a) == 5
    reader._process_single(_FakeImap(_befehlsmail(b, "xyzzy")), b"1", basis_settings())
    assert len([m for m in rec.emails if b.mail_to in m["to"]]) == 1
    # ein gueltiger Befehl wird weiterhin beantwortet
    reader._process_single(_FakeImap(_befehlsmail(a, "Hilfe")), b"1", basis_settings())
    assert len([m for m in rec.emails if a.mail_to in m["to"]]) == 6


# ─────────────────────────── Abruf (AC-10) ──────────────────────────────────

class _Postfach:
    """IMAP-Gegenstelle: beantwortet Kopf- und Vollabruf getrennt, wie ein Server."""

    def __init__(self, mails: dict[bytes, bytes], groessen: dict[bytes, int] | None = None):
        self.mails = mails
        self.groessen = groessen or {}
        self.abrufe: list[tuple[bytes, str]] = []
        self.gelesen: set[bytes] = set()

    def __call__(self, *_a, **_kw):
        return self

    def login(self, *_a):
        return "OK", [b""]

    def select(self, *_a):
        return "OK", [b"1"]

    def search(self, *_a):
        return "OK", [b" ".join(self.mails)]

    def fetch(self, uid, spec):
        self.abrufe.append((uid, spec))
        raw = self.mails[uid]
        size = self.groessen.get(uid, len(raw))
        if "HEADER" in spec.upper():
            kopf = raw.split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n"
            return "OK", [(b"%s (RFC822.SIZE %d BODY[HEADER] {%d}" % (uid, size, len(kopf)), kopf), b")"]
        return "OK", [(b"%s (RFC822 {%d}" % (uid, len(raw)), raw), b")"]

    def store(self, uid, _flags, value):
        if "Seen" in value:
            self.gelesen.add(uid)
        return "OK", [b""]

    def logout(self):
        return "BYE", [b""]

    def voll_abgerufen(self) -> set[bytes]:
        return {uid for uid, spec in self.abrufe if "HEADER" not in spec.upper()}


def _poll(monkeypatch, postfach) -> int:
    monkeypatch.setattr(inbound_email_reader.imaplib, "IMAP4_SSL", postfach)
    return InboundEmailReader().poll_and_process(basis_settings())


def test_rumpf_nur_fuer_autorisierte_absender(monkeypatch, user_ids):
    install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    fremd = _mime_plain("fremd@example.org", f"Re: [{nutzer.trip.name}] x", "Hilfe")
    postfach = _Postfach({b"1": fremd, b"2": _befehlsmail(nutzer)})
    assert _poll(monkeypatch, postfach) == 1
    assert postfach.voll_abgerufen() == {b"2"}
    assert postfach.gelesen == {b"1", b"2"}


def test_hoechstens_50_mails_je_lauf(monkeypatch, user_ids):
    install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    fremd = _mime_plain("fremd@example.org", f"Re: [{nutzer.trip.name}] x", "Hilfe")
    postfach = _Postfach({str(i).encode(): fremd for i in range(1, 61)})
    _poll(monkeypatch, postfach)
    assert len({uid for uid, _ in postfach.abrufe}) == 50
    assert len(postfach.gelesen) == 50


def test_mail_ueber_2_mb_wird_uebersprungen(monkeypatch, user_ids):
    rec = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    postfach = _Postfach({b"1": _befehlsmail(nutzer)}, groessen={b"1": 2 * 1024 * 1024 + 1})
    assert _poll(monkeypatch, postfach) == 0
    assert postfach.voll_abgerufen() == set()
    assert postfach.gelesen == {b"1"}
    assert rec.emails == []

