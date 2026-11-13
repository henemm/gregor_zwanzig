"""Premium-SMS-Rueckkanal, Sicherheits-Haertung (Issue #2961 Welle 2, ADR-0116).

SPEC: docs/specs/modules/security_haertung_2026_11_premium_sms_rueckkanal.md

Gemessen an den echten Funktionen auf der isolierten Datenwurzel
(autouse-Fixture aus tests/conftest.py, #1133). Ersetzt ist nur die
Aussengrenze zum seven.io-Journal (``httpx`` im Reader-Modul) durch eine
Aufzeichner-Klasse; kein ``Mock()``/``patch()``.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest

import services.inbound_sms_reader as reader_mod
from app.loader import get_data_dir
from output.channels.base import ChannelBlockedError
from output.channels.recipient import PremiumSmsRecipient
from services.inbound_sms_reader import split_link_code


def _uid(praefix: str) -> str:
    return f"psh-{praefix}-{uuid.uuid4().hex[:6]}"


def _profil(user_id: str, **felder) -> None:
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    daten = {"id": user_id, "tier": "premium", **felder}
    (ordner / "user.json").write_text(json.dumps(daten))


# ---------------------------------------------------------------------------
# Verknuepfungscode: neues und altes Format werden im Eingang erkannt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text, erwartet", [
    # neues Format: XX + 5 Buchstaben + 3 Ziffern
    ("xxabcde234 status inreachlink.com/x (1.0, 2.0)", ("XXABCDE234", "status")),
    ("XXQRSTU789 inreachlink.com/x", ("XXQRSTU789", "")),
    # Bestandsformat: XX + 3 Buchstaben + 3 Ziffern
    ("XXCJD224 Heute inreachlink.com/x", ("XXCJD224", "Heute")),
    # weder alt noch neu: 4 Buchstaben, verwechselbares I, zu kurz
    ("XXABCD234 status inreachlink.com/x", ("", "XXABCD234 status")),
    ("XXABIDE234 status inreachlink.com/x", ("", "XXABIDE234 status")),
    ("XXAB234 status inreachlink.com/x", ("", "XXAB234 status")),
])
def test_verknuepfungscode_beide_laengen_werden_erkannt(text, erwartet):
    assert split_link_code(text) == erwartet


# ---------------------------------------------------------------------------
# Ausgehend: Rueckadresse nur, wenn sie genau einem Konto gehoert
# ---------------------------------------------------------------------------


class _Settings:
    is_test_mode = False


def test_rueckadresse_zweier_konten_wird_nicht_bedient():
    """AC-5: tragen (Bestandsdaten) zwei Konten dieselbe Rueckadresse, geht an
    keines der beiden etwas hinaus; ein Konto mit eigener Nummer bleibt
    bedienbar."""
    jetzt = datetime.now(timezone.utc).isoformat()
    anna, bert, carl = _uid("anna"), _uid("bert"), _uid("carl")
    _profil(anna, premium_sms_reply_to="+4917000000031", premium_sms_reply_at=jetzt)
    _profil(bert, premium_sms_reply_to="+4917000000031", premium_sms_reply_at=jetzt)
    _profil(carl, premium_sms_reply_to="+4917000000032", premium_sms_reply_at=jetzt)

    for uid in (anna, bert):
        with pytest.raises(ChannelBlockedError) as e:
            PremiumSmsRecipient.for_user(uid, _Settings())
        assert e.value.reason_code == "premium_sms_no_reply_address"

    assert PremiumSmsRecipient.for_user(carl, _Settings()).number == "+4917000000032"


def test_rueckadresse_eines_einzigen_kontos_wird_bedient():
    jetzt = datetime.now(timezone.utc).isoformat()
    anna, bert = _uid("anna"), _uid("bert")
    _profil(anna, premium_sms_reply_to="+4917000000033", premium_sms_reply_at=jetzt)
    _profil(bert)  # ohne Rueckadresse
    empfaenger = PremiumSmsRecipient.for_user(anna, _Settings())
    assert empfaenger.number == "+4917000000033"
    assert empfaenger.user_id == anna


# ---------------------------------------------------------------------------
# Journal: genau 100 Eintraege ohne Ueberlappung -> Warnung "abgeschnitten"
# ---------------------------------------------------------------------------


class _Journal:
    def __init__(self, eintraege: list[dict]) -> None:
        self._eintraege = eintraege
        self.params: list[dict] = []

    def get(self, url, headers=None, params=None, timeout=None, **kw):
        self.params.append(dict(params or {}))
        return httpx.Response(200, json=self._eintraege)


def _eintraege(von: int, anzahl: int) -> list[dict]:
    # An eine fremde Nummer: der Reader rueckt nur den Zeiger vor.
    return [{"id": str(von + i), "from": "4917000000040", "to": "4900000000000",
             "text": "x"} for i in range(anzahl)]


def _zeiger_setzen(wert: int) -> None:
    from app.loader import get_data_root

    ordner = get_data_root() / "diagnostics"
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "premium_sms_inbound.json").write_text(json.dumps({"last_seen_id": wert}))


def _poll(monkeypatch, journal: _Journal):
    from app.config import Settings

    monkeypatch.setattr(reader_mod, "classify_origin", lambda root: "production")
    monkeypatch.setattr(reader_mod, "httpx", journal)
    monkeypatch.delenv(reader_mod.DRYRUN_ENV_VAR, raising=False)
    monkeypatch.setenv("GZ_SEVEN_API_KEY", "unbrauchbar")
    return reader_mod.InboundSmsReader().poll_and_process(Settings(_env_file=None))


def test_journal_volle_seite_ohne_ueberlappung_warnt(monkeypatch, caplog):
    _zeiger_setzen(1000)
    journal = _Journal(_eintraege(2000, reader_mod.JOURNAL_LIMIT))
    with caplog.at_level(logging.WARNING, logger=reader_mod.logger.name):
        _poll(monkeypatch, journal)
    assert journal.params == [{"limit": 100}]
    assert any("abgeschnitten" in r.getMessage() for r in caplog.records), caplog.text


def test_journal_volle_seite_mit_ueberlappung_warnt_nicht(monkeypatch, caplog):
    _zeiger_setzen(2050)
    journal = _Journal(_eintraege(2000, reader_mod.JOURNAL_LIMIT))
    with caplog.at_level(logging.WARNING, logger=reader_mod.logger.name):
        _poll(monkeypatch, journal)
    assert not any("abgeschnitten" in r.getMessage() for r in caplog.records), caplog.text


def test_journal_unvolle_seite_warnt_nicht(monkeypatch, caplog):
    _zeiger_setzen(1000)
    journal = _Journal(_eintraege(2000, 99))
    with caplog.at_level(logging.WARNING, logger=reader_mod.logger.name):
        _poll(monkeypatch, journal)
    assert not any("abgeschnitten" in r.getMessage() for r in caplog.records), caplog.text
