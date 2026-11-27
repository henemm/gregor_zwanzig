"""Issue #2035 (Gate-Audit #1197): Mail-Validatoren akzeptieren keine tagealte Fremd-Mail.

Echter ``fetch_latest_message`` der drei Hook-Validatoren (Radar-Alarm,
Amtliche Warnung, Briefing) gegen ein IMAP-Double (Test-Seam ``imap=``). Das
Double liefert wie ein echter Server die INTERNALDATE im Praefix der
Fetch-Antwort. Eine fuenf Tage alte Mail muss abgelehnt werden, eine frische
besteht; ohne Server-Zeit gibt es keinen Rueckfall auf den Date-Kopf.
"""
from __future__ import annotations

import imaplib
import importlib.util
import sys
import time
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"

TYPEN = {
    "radar_alert_mail_validator": "radar-alert",
    "official_alert_mail_validator": "official-alert",
    "briefing_mail_validator": "trip-briefing",
}


def _modul(name: str):
    sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location(f"{name}_2035", HOOKS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mail(typ: str) -> bytes:
    return (f"From: gregor@henemm.com\nTo: nutzer@henemm.com\nSubject: Test Beleg\n"
            f"X-GZ-Mail-Type: {typ}\nX-GZ-Lang: de\n\nKoerper\n").encode()


class _Postfach:
    def __init__(self, roh: bytes, alter_s: float | None):
        self.roh, self.alter_s = roh, alter_s

    def select(self, _box):
        return "OK", [b""]

    def search(self, _c, _k):
        return "OK", [b"1"]

    def fetch(self, _mid, teil):
        if "HEADER" in teil:
            prefix = b"1 (BODY[HEADER] {1}"
            if self.alter_s is not None:
                zeit = imaplib.Time2Internaldate(time.time() - self.alter_s).encode()
                prefix = b"1 (INTERNALDATE " + zeit + b" BODY[HEADER] {1}"
            return "OK", [(prefix, self.roh.split(b"\n\n", 1)[0] + b"\n\n"), b")"]
        return "OK", [(b"1", self.roh)]

    def close(self):
        pass

    def logout(self):
        pass


@pytest.fixture(params=sorted(TYPEN))
def val(request):
    return _modul(request.param), TYPEN[request.param]


def _hole(val_typ, alter_s, **kw):
    mod, typ = val_typ
    return mod.fetch_latest_message(imap=_Postfach(_mail(typ), alter_s), **kw)


def test_frische_mail_besteht(val):
    assert _hole(val, 120)["Subject"] == "Test Beleg"


def test_fuenf_tage_alte_fremdmail_wird_abgelehnt(val):
    with pytest.raises(ValueError, match="Minuten alt"):
        _hole(val, 5 * 86400)


def test_ohne_server_zeit_kein_rueckfall_auf_date_kopf(val):
    with pytest.raises(ValueError, match="INTERNALDATE"):
        _hole(val, None)


def test_abschalten_nur_mit_begruendung(val):
    assert _hole(val, 5 * 86400, ignore_mail_age_reason="Altfall manuell geprueft")
    with pytest.raises(ValueError, match="Grund"):
        _hole(val, 5 * 86400, ignore_mail_age_reason="  ")


def test_grenze_ueber_24h_wird_abgelehnt(val):
    with pytest.raises(ValueError, match="Maximum"):
        _hole(val, 60, max_age_minutes=99999)


def test_eigene_grenze_wirkt(val):
    with pytest.raises(ValueError, match="Minuten alt"):
        _hole(val, 600, max_age_minutes=5)
