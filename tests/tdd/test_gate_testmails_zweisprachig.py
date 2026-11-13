"""Issue #2681 (A2): ``send_gate_test_mails.py --lang`` (AC-1, Kern-Teil).

Spec: docs/specs/modules/i18n_a2_e2e_zweisprachig_2681.md

Kern-Schicht, kein Netz: das Skript laeuft ECHT bis zum Draht (Renderer,
``NotificationService``, ``EmailOutput`` samt Guards). Ersetzt ist nur
``smtplib.SMTP`` durch eine aufzeichnende Gegenstelle (Muster
tests/tdd/test_mail_message_id_traceability.py). Die eingelieferten Mails werden
anschliessend vom jeweils zustaendigen ECHTEN Validator geprueft (``--eml``,
``--lang``, ``--to-contains``) -- dieselbe Pruefung wie in ``/e2e-verify``.
"""
from __future__ import annotations

import email
import importlib.util
import re
from pathlib import Path

import pytest

from tests.helpers.mail_lang_fixture import validator_lauf

ROOT = Path(__file__).resolve().parents[2]
SKRIPT = ROOT / "scripts" / "send_gate_test_mails.py"
BASIS = "gregor-test@henemm.com"
SUB_EN = "gregor-test+en@henemm.com"
PFADE = {  # --only -> (X-GZ-Mail-Type, Validator)
    "official": ("official-alert", "official_alert_mail_validator"),
    "briefing": ("trip-briefing", "briefing_mail_validator"),
    "compare": ("compare", "email_spec_validator"),
    "radar": ("radar-alert", "radar_alert_mail_validator"),
}


def _skript():
    spec = importlib.util.spec_from_file_location("send_gate_test_mails_2681", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def draht(monkeypatch):
    """Aufzeichnende SMTP-Gegenstelle: Liste (empfaenger, roh)."""
    from output.channels import email as email_module

    eingeliefert: list[tuple[list, str]] = []

    class _Socket:
        def settimeout(self, _t):
            pass

    class _Smtp:
        def __init__(self, host, port, timeout=None):
            self.sock = _Socket()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self, context=None):
            pass

        def login(self, user, password):
            pass

        def sendmail(self, from_addr, to_addrs, msg):
            eingeliefert.append((list(to_addrs), msg))

    monkeypatch.setattr(email_module.smtplib, "SMTP", _Smtp)
    monkeypatch.setattr(email_module.time, "sleep", lambda _s: None)
    monkeypatch.setattr(email_module, "running_origin", lambda _f: "production")
    monkeypatch.setenv("GZ_TEST_SMTP_USER", "gregor-test")
    monkeypatch.setenv("GZ_TEST_SMTP_PASS", "pruefstand")
    # Konfigurierter Profil-Empfaenger der Umgebung; das Skript ueberschreibt ihn.
    monkeypatch.setenv("GZ_MAIL_TO", "gregor-staging@henemm.com")
    return eingeliefert


def _sende(draht, capsys, *argv, herkunft=None) -> tuple[list, str]:
    """``herkunft``: Test-Seam des Skripts (#2813); --lang en geht nur aus Staging."""
    vorher = len(draht)
    kw = {} if herkunft is None else {"herkunft": herkunft}
    assert _skript().main(list(argv), **kw) == 0
    token = re.search(r"Token fuer diesen Lauf: (\w+)", capsys.readouterr().out).group(1)
    return draht[vorher:], token


@pytest.mark.parametrize("pfad", list(PFADE))
def test_lang_en_an_subadresse_und_validator_besteht(draht, capsys, tmp_path, pfad):
    # #2813: aus einem Worktree bricht --lang en ab; hier die Staging-Herkunft.
    mails, _ = _sende(draht, capsys, "--lang", "en", "--only", pfad,
                      herkunft=lambda _root: "staging")
    assert len(mails) == 1
    empfaenger, roh = mails[0]
    msg = email.message_from_string(roh)
    assert empfaenger == [SUB_EN] and msg["To"] == SUB_EN
    assert msg["X-GZ-Mail-Type"] == PFADE[pfad][0]
    assert msg["X-GZ-Lang"] == "en"
    lauf, _ = validator_lauf(tmp_path, PFADE[pfad][1], roh.encode(), "--lang", "en",
                             "--to-contains", "+en@")
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr


@pytest.mark.parametrize("pfad", list(PFADE))
def test_lang_de_bleibt_basispostfach_und_validator_besteht(draht, capsys, tmp_path, pfad):
    mails, _ = _sende(draht, capsys, "--lang", "de", "--only", pfad)
    empfaenger, roh = mails[0]
    msg = email.message_from_string(roh)
    assert empfaenger == [BASIS] and msg["X-GZ-Lang"] == "de"
    lauf, _ = validator_lauf(tmp_path, PFADE[pfad][1], roh.encode(), "--lang", "de")
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr


def _normiert(roh: str, token: str) -> list:
    """Kopfzeilen (ohne Date/Message-ID) und dekodierte Teile, Lauf-Token neutral."""
    msg = email.message_from_string(roh)
    kopf = [(k, v.replace(token, "TOKEN")) for k, v in msg.items()
            if k not in ("Date", "Message-ID", "Content-Type")]
    teile = [(t.get_content_type(), t.get_payload(decode=True).decode().replace(token, "TOKEN"))
             for t in msg.walk() if not t.is_multipart()]
    return kopf + teile


@pytest.mark.parametrize("pfad", ["official", "compare", "radar"])
def test_lang_de_byte_gleich_zum_bisherigen_verhalten(draht, capsys, pfad):
    ohne, t1 = _sende(draht, capsys, "--only", pfad)
    mit_de, t2 = _sende(draht, capsys, "--lang", "de", "--only", pfad)
    assert _normiert(ohne[0][1], t1) == _normiert(mit_de[0][1], t2)
    assert ohne[0][0] == mit_de[0][0] == [BASIS]


def test_unbekannte_sprache_wird_abgelehnt(draht):
    with pytest.raises(SystemExit) as exc:
        _skript().main(["--lang", "fr"])
    assert exc.value.code == 2
    assert draht == []
