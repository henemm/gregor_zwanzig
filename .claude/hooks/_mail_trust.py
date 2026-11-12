"""Vertrauenspruefung fuer Mails im geteilten Test-Postfach (#2961).

Die Mail-Validatoren lesen ein Postfach, in das auch Fremde schreiben koennen.
Eine Mail zaehlt nur, wenn

1. sie genau einen ``From``-Kopf mit genau einer Adresse traegt und diese
   Adresse ein konfigurierter Dienst-Absender ist (``aus_settings``), und
2. soweit vorhanden, der ERSTE ``Authentication-Results``-Kopf des eigenen
   Mailservers (authserv-id = ``GZ_MAIL_SERVER_HOSTNAME``) DKIM oder SPF
   ``pass`` ausweist und keines der beiden ``fail``/``softfail``/``permerror``.
   Stalwart stellt seinen Kopf vor alle anderen; fehlt ein Kopf des eigenen
   Servers (lokal eingelieferte Mail), entfaellt Punkt 2.

Fehlt jede Absender-Konfiguration, wird keine Mail akzeptiert (fail-closed).
Ueberschreiben (kommagetrennt): ``GZ_VALIDATOR_MAIL_FROM``.
"""
from __future__ import annotations

import email.utils
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ENV_ABSENDER = "GZ_VALIDATOR_MAIL_FROM"
_FAIL = {"fail", "softfail", "permerror"}


@dataclass(frozen=True)
class Vertrauen:
    """Erwartete Dienst-Absender (klein geschrieben) und authserv-id."""

    absender: frozenset
    authserv_id: str | None = None


def _norm(adresse: str) -> str:
    return adresse.strip().lower()


def aus_settings(settings) -> Vertrauen:
    """Dienst-Absender aus der Konfiguration, die der Versand selbst nutzt:
    Test-Routing (``for_testing``: ``mail_from``/``inbound_address``) und
    Normalbetrieb (``mail_from``/``inbound_address``/``smtp_user``)."""
    roh = os.environ.get(ENV_ABSENDER, "")
    if roh.strip():
        kandidaten = roh.split(",")
    else:
        test = settings.for_testing()
        kandidaten = [test.mail_from, test.inbound_address, settings.mail_from,
                      settings.inbound_address, settings.smtp_user]
    absender = frozenset(_norm(a) for a in kandidaten if a and "@" in a)
    host = (getattr(settings, "mail_server_hostname", None) or "").strip() or None
    return Vertrauen(absender, host)


def aus_konfiguration() -> Vertrauen:
    """``aus_settings`` mit den Settings der Umgebung (wie ``_open_test_imap``)."""
    src_dir = Path(__file__).resolve().parents[2] / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from app.config import Settings

    return aus_settings(Settings())


def _auth_results(wert: str) -> tuple[str | None, dict] | None:
    """(authserv-id, {methode: ergebnis}) oder None, wenn unlesbar.
    Kommentare in Klammern fallen weg; Anfuehrungszeichen gelten als unlesbar
    (wie im Inbound-Leser, #2252)."""
    if '"' in wert:
        return None
    vorher = None
    while vorher != wert:
        vorher, wert = wert, re.sub(r"\([^()]*\)", " ", wert)
    if "(" in wert or ")" in wert:
        return None
    teile = wert.split(";")
    kopf = teile[0].split()
    if not kopf:
        return None
    ergebnisse: dict = {}
    for teil in teile[1:]:
        woerter = teil.split()
        if woerter and "=" in woerter[0]:
            methode, _, ergebnis = woerter[0].partition("=")
            ergebnisse.setdefault(methode.lower(), set()).add(ergebnis.lower())
    return kopf[0].lower(), ergebnisse


def _auth_fehler(headers, authserv_id: str | None) -> str | None:
    if not authserv_id:
        return None
    roh = headers.get("Authentication-Results")
    if roh is None:
        return None
    geparst = _auth_results(str(roh))
    if geparst is None:
        return "AUTHENTISIERUNG: Authentication-Results-Kopf unlesbar"
    server, ergebnisse = geparst
    if server != authserv_id.lower():
        return None  # kein Kopf des eigenen Servers: Pruefung nicht verfuegbar
    werte = ergebnisse.get("dkim", set()) | ergebnisse.get("spf", set())
    if werte & _FAIL:
        return f"AUTHENTISIERUNG: DKIM/SPF des eigenen Servers nicht bestanden ({sorted(werte)})"
    if "pass" not in werte:
        return "AUTHENTISIERUNG: weder DKIM noch SPF des eigenen Servers ist pass"
    return None


def fehler(headers, vertrauen: Vertrauen) -> str | None:
    """None, wenn die Mail vertrauenswuerdig ist, sonst ein Grund (ohne Inhalte)."""
    froms = headers.get_all("From") or []
    if len(froms) != 1:
        return f"ABSENDER: genau ein From-Kopf erwartet, gefunden {len(froms)}"
    adressen = email.utils.getaddresses([str(froms[0])])
    if len(adressen) != 1 or not adressen[0][1]:
        return "ABSENDER: From-Kopf ohne genau eine Adresse"
    if not vertrauen.absender:
        return (f"ABSENDER: kein Dienst-Absender konfiguriert (GZ_TEST_SMTP_USER, "
                f"GZ_MAIL_FROM oder {ENV_ABSENDER})")
    adresse = _norm(adressen[0][1])
    if adresse not in vertrauen.absender:
        return (f"ABSENDER: {adresse} ist kein erwarteter Dienst-Absender "
                f"({', '.join(sorted(vertrauen.absender))})")
    return _auth_fehler(headers, vertrauen.authserv_id)


def hinweis(gruende: list) -> str:
    """Zusatz fuer die "keine passende Mail"-Meldung."""
    if not gruende:
        return ""
    return (f" {len(gruende)} sonst passende Mail(s) wegen Absender/Authentisierung "
            f"verworfen, die neueste: {gruende[0]}")
