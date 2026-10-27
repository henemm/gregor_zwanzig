"""TDD RED — Issue #1412 Scheibe S5, Python-Seite von C3-20 (AC-8, AC-9, AC-11).

SPEC: docs/specs/modules/fix_1412_s5_go_empfaengerschutz.md

Der Guard in `EmailOutput.send` bewertet die quote-bewusste Hauptliste
(`getaddresses([recipient])`): enthaelt sie einen nicht-leeren Eintrag OHNE
`@`, ist der gesamte Versand blockiert (Resend- UND Nicht-Resend-Zweig).
Gequotete Formen (`"Nachname, Vorname" <addr>`, `"Foo; Bar" <addr>`) erzeugen
keinen `@`-losen Eintrag und bleiben erlaubt.

Messweg wie `tests/test_mail_recipient_parity.py`: echtes `EmailOutput.send`
gegen den ECHTEN Guard, der SMTP-Transport wird durch eine Sentinel-Ausnahme
ersetzt (kein Netz, keine Mail). Prueflinge werden relativ zu dieser Datei
(per Import ueber `src`) aufgeloest, nie ueber den festen Hauptrepo-Pfad.

Klassifikation: Block-Faelle A/Z1 (beide Zweige) sind vor der Umsetzung ROT;
`a@henemm.com garbage` (B), gequotete Formen und Z2 sind PINNING.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from output.channels import email as email_module  # noqa: E402
from output.channels.base import OutputConfigError  # noqa: E402

RESEND_HOST = "smtp.resend-fixture.test"
STALWART_HOST = "mail.henemm.com"


class _TransportSentinel(Exception):
    """Transport erreicht == Guard hat NICHT geblockt. Erbt weder von
    SMTPException noch OSError, damit send() sie ohne Retry durchreicht."""


def _raise_sentinel(*_a, **_k):
    raise _TransportSentinel("Transport erreicht")


@pytest.fixture
def _datenwurzel(tmp_path, monkeypatch):
    """Verifiziertes Profil henning@henemm.com => Resend-Allowlist."""
    from app import loader

    user_dir = tmp_path / "data" / "users" / "henning"
    user_dir.mkdir(parents=True)
    (user_dir / "user.json").write_text(
        json.dumps({"mail_to": "henning@henemm.com", "email_verified_at": "2026-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path / "data"), raising=False)
    monkeypatch.setattr(email_module.smtplib, "SMTP", _raise_sentinel)
    monkeypatch.setattr(email_module, "running_origin", lambda _p: "prod")
    return tmp_path


def _entscheidung(host: str, to: str) -> str:
    out = email_module.EmailOutput.__new__(email_module.EmailOutput)
    out._host = host
    out._port = 587
    out._user = "guard-test-user"
    out._password = "guard-test-pass"
    out._to = "fallback@henemm.com"
    out._from = "fallback@henemm.com"
    out._reply_to = None
    out._fallback_host = None
    out._fallback_user = None
    out._fallback_pass = None
    try:
        out.send("Guard-Pruefung", "Testkoerper", html=False, to=[to])
    except _TransportSentinel:
        return "allow"
    except OutputConfigError:
        return "block"
    pytest.fail(f"send() kehrte ohne Sentinel und ohne Guard-Fehler zurueck (to={to!r})")


HOSTS = [pytest.param(RESEND_HOST, id="resend"), pytest.param(STALWART_HOST, id="stalwart")]


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize(
    "to",
    [
        "henning@henemm.com, garbage",  # AC-8 (Fall A)
        "Nachname, Vorname <henning@henemm.com>",  # AC-11 (Z1, ungequotet)
    ],
)
def test_atloser_hauptlisteneintrag_blockt_gesamtversand(_datenwurzel, host, to):
    """AC-8/AC-11: Hauptliste mit `@`-losem Eintrag => OutputConfigError."""
    assert _entscheidung(host, to) == "block", (
        f"to={to!r} host={host!r}: `@`-loser Hauptlisten-Eintrag muss den "
        "gesamten Versand blocken (fail-closed)"
    )


@pytest.mark.parametrize("host", HOSTS)
def test_leerzeichen_rest_blockt_schon_heute(_datenwurzel, host):
    """AC-9 (PINNING): `a@henemm.com garbage` (ohne Komma) wird von Python als
    `a@henemm.comgarbage` gelesen => block, beide Zweige. Muss so bleiben."""
    assert _entscheidung(host, "henning@henemm.com garbage") == "block"


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize(
    "to",
    [
        '"Nachname, Vorname" <henning@henemm.com>',  # AC-11 (Z2)
        '"Foo; Bar" <henning@henemm.com>',
    ],
)
def test_gequotete_anzeigenamen_bleiben_erlaubt(_datenwurzel, host, to):
    """AC-11 (PINNING): gequotete Formen erzeugen keinen `@`-losen Eintrag."""
    assert _entscheidung(host, to) == "allow", (
        f"to={to!r} host={host!r}: gequotete Form muss erlaubt bleiben"
    )
