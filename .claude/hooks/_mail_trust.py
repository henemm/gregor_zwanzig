"""Vertrauenspruefung fuer Mails im geteilten Test-Postfach (#2961).

Die Mail-Validatoren lesen ein Postfach, in das auch Fremde schreiben koennen.

1. **Absender:** genau ein ``From``-Kopf mit genau einer Adresse.
   - Adresse ist ein erwarteter Dienst-Absender (``aus_settings``) -> ok.
   - Adresse liegt in der Domain eines erwarteten Absenders, ist aber nicht
     selbst gelistet -> Warnzeile, kein Abbruch (die Domain-Pruefung unten
     bleibt wirksam).
   - Adresse in einer fremden Domain -> verworfen.
   - Kein erwarteter Absender ermittelbar -> Warnzeile statt Ablehnung, damit
     diese Haertung den Deploy-Nachweis nie faelschlich blockiert.
2. **Authentisierung:** dieselbe Auswertung wie der Produktions-Eingang
   (``services.inbound_email_reader``: RFC-8601-Parser, Quote-Sperre, nur der
   ERSTE ``Authentication-Results``-Kopf, authserv-id = ``GZ_MAIL_SERVER_HOSTNAME``,
   Annahmeregel V3 mit Ausrichtung zur From-Domain; SPF zaehlt nur im Scope
   ``smtp.mailfrom``, HELO-Ergebnisse werden ignoriert). Kein Kopf (Einlieferung
   ueber Port 587) oder ein Kopf eines fremden Servers -> Teilpruefung entfaellt.
   Ein unlesbarer Kopf des eigenen Servers oder eine nicht ausgerichtete
   Annahme -> verworfen.

Warnungen gehen nach stderr. Absender ueberschreiben (kommagetrennt):
``GZ_VALIDATOR_MAIL_FROM``.
"""
from __future__ import annotations

import email.utils
import imaplib
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ENV_ABSENDER = "GZ_VALIDATOR_MAIL_FROM"
_SRC = Path(__file__).resolve().parents[2] / "src"


@dataclass(frozen=True)
class Vertrauen:
    """Erwartete Dienst-Absender (klein geschrieben) und authserv-id."""

    absender: frozenset
    authserv_id: str | None = None


def _norm(adresse: str) -> str:
    return adresse.strip().lower()


def _src_pfad() -> None:
    if str(_SRC) not in sys.path:
        sys.path.insert(0, str(_SRC))


def _konto_adresse(konto: str | None) -> str | None:
    """Kontoname des Test-Postfachs -> Adresse (Konten liegen auf henemm.com)."""
    if not konto:
        return None
    return konto if "@" in konto else f"{konto}@henemm.com"


def aus_settings(settings) -> Vertrauen:
    """Dienst-Absender aus der Konfiguration, die der Versand selbst nutzt.

    Auf Staging laufen alle Nutzer ueber ``for_testing()``: From ist
    ``GZ_TEST_MAIL_FROM`` bzw. ``<GZ_TEST_SMTP_USER>@henemm.com`` -- dasselbe
    Konto, dessen Postfach der Validator liest (``GZ_TEST_IMAP_USER``,
    docs/context/fix-2542-staging-befehl-pruefweg.md). Darum zaehlt auch die
    Adresse des Test-Postfachs. Dazu der Normalbetrieb (``mail_from``,
    ``inbound_address``, ``smtp_user``)."""
    roh = os.environ.get(ENV_ABSENDER, "")
    if roh.strip():
        kandidaten = roh.split(",")
    else:
        test = settings.for_testing()
        kandidaten = [test.mail_from, test.inbound_address, settings.mail_from,
                      settings.inbound_address, settings.smtp_user,
                      _konto_adresse(settings.test_imap_user),
                      _konto_adresse(settings.test_smtp_user)]
    absender = frozenset(_norm(a) for a in kandidaten if a and "@" in a)
    host = (getattr(settings, "mail_server_hostname", None) or "").strip() or None
    return Vertrauen(absender, host)


def aus_konfiguration() -> Vertrauen:
    """``aus_settings`` mit den Settings der Umgebung (wie ``_open_test_imap``)."""
    _src_pfad()
    from app.config import Settings

    return aus_settings(Settings())


def _auth_fehler(headers, authserv_id: str | None, from_domain: str) -> str | None:
    """Auswertung des Produktions-Eingangs (keine eigene Kopie)."""
    if not authserv_id:
        return None
    roh = headers.get("Authentication-Results")
    if roh is None:
        return None  # Port 587: strukturell kein Kopf
    _src_pfad()
    from services.inbound_email_reader import (
        _alignment_accepts,
        _norm_domain,
        parse_authentication_results_segments,
    )

    wert = str(roh)
    geparst = None if '"' in wert else parse_authentication_results_segments(wert)
    if geparst is None:
        # authserv-id grob bestimmen: nur ein Kopf des EIGENEN Servers ist ein Fehler
        if wert.split(";", 1)[0].strip().lower() != authserv_id.lower():
            return None
        return "AUTHENTISIERUNG: Authentication-Results-Kopf des eigenen Servers unlesbar"
    server, segmente = geparst
    if (server or "").lower() != authserv_id.lower():
        return None  # Kopf eines fremden Servers: Pruefung nicht verfuegbar
    if not _alignment_accepts(segmente, _norm_domain(from_domain)):
        return ("AUTHENTISIERUNG: weder DMARC, SPF (smtp.mailfrom) noch DKIM des "
                f"eigenen Servers bestaetigen die Absender-Domain {from_domain}")
    return None


def pruefen(headers, vertrauen: Vertrauen) -> tuple[str | None, str | None]:
    """(Ablehnungsgrund | None, Warnung | None) -- ohne Mail-Inhalte."""
    froms = headers.get_all("From") or []
    if len(froms) != 1:
        return f"ABSENDER: genau ein From-Kopf erwartet, gefunden {len(froms)}", None
    adressen = email.utils.getaddresses([str(froms[0])])
    if len(adressen) != 1 or "@" not in adressen[0][1]:
        return "ABSENDER: From-Kopf ohne genau eine Adresse", None
    adresse = _norm(adressen[0][1])
    domain = adresse.rpartition("@")[2]
    warnung = None
    if not vertrauen.absender:
        warnung = (f"ABSENDER: kein Dienst-Absender ermittelbar (GZ_TEST_SMTP_USER, "
                   f"GZ_MAIL_FROM oder {ENV_ABSENDER}) -- {adresse} nicht geprueft")
    elif adresse not in vertrauen.absender:
        domains = {a.rpartition("@")[2] for a in vertrauen.absender}
        if domain not in domains:
            return (f"ABSENDER: {adresse} ist kein erwarteter Dienst-Absender "
                    f"({', '.join(sorted(vertrauen.absender))})"), None
        warnung = (f"ABSENDER: {adresse} ist nicht als Dienst-Absender gelistet, "
                   f"aber in der eigenen Domain {domain}")
    return _auth_fehler(headers, vertrauen.authserv_id, domain), warnung


def fehler(headers, vertrauen: Vertrauen) -> str | None:
    """Ablehnungsgrund oder None; eine Warnung geht als Zeile nach stderr."""
    grund, warnung = pruefen(headers, vertrauen)
    if warnung and not grund:
        print(f"WARNUNG: {warnung}", file=sys.stderr)
    return grund


def hinweis(gruende: list) -> str:
    """Zusatz fuer die "keine passende Mail"-Meldung."""
    if not gruende:
        return ""
    return (f" {len(gruende)} sonst passende Mail(s) wegen Absender/Authentisierung "
            f"verworfen, die neueste: {gruende[0]}")


# --- Frische der Mail (#2035) -------------------------------------------------
# Gleiche Regel wie ``email_spec_validator`` (#1408): Alter aus der
# serverseitigen INTERNALDATE (kein Rueckfall auf den manipulierbaren
# Date-Kopf), Standardgrenze 60 Minuten, Obergrenze 24 h, Abschalten nur mit
# Begruendung. Ohne sie erfuellt jede Altmail im geteilten Postfach den
# Validatorlauf (#2035: fuenf Tage alte Fremd-Mail als Nachweis).
#
# PRUEFDATUM (Regel-Budget, #1197): 2027-02-25. Bis dahin muss die Schranke
# einen echten Fang vorweisen oder sie wird zurueckgebaut.
DEFAULT_MAX_AGE_MINUTES = 60
MAX_AGE_CEILING_MINUTES = 1440
ALTER_FETCH = "(BODY.PEEK[HEADER] INTERNALDATE)"
_IGNORE_HINT = 'bewusstes Abschalten nur ueber --ignore-mail-age "<Grund>"'


def alter_argumente(parser) -> None:
    parser.add_argument("--max-age-minutes", type=float, default=None,
                        help=f"hoechstes Mail-Alter (Standard {DEFAULT_MAX_AGE_MINUTES}, "
                             f"max {MAX_AGE_CEILING_MINUTES}) (#2035)")
    parser.add_argument("--ignore-mail-age", metavar="GRUND", default=None,
                        help="Altersschranke bewusst abschalten, Grund Pflicht (#2035)")


def alter_pruefen_argumente(max_age_minutes, ignore_reason) -> None:
    """Werte, die still "keine Pruefung" bedeuten koennten, werden abgelehnt."""
    if ignore_reason is not None and not ignore_reason.strip():
        raise ValueError("Die Altersschranke laesst sich nur mit nicht-leerem Grund "
                         "abschalten (--ignore-mail-age \"<Grund>\").")
    if max_age_minutes is not None and not math.isfinite(max_age_minutes):
        raise ValueError(f"Altersgrenze muss endlich sein (bekommen: {max_age_minutes}); "
                         f"{_IGNORE_HINT}.")
    if max_age_minutes is not None and max_age_minutes > MAX_AGE_CEILING_MINUTES:
        raise ValueError(f"Altersgrenze {max_age_minutes} Minuten ueberschreitet das Maximum "
                         f"von {MAX_AGE_CEILING_MINUTES}; {_IGNORE_HINT}.")


def _internaldate_zeile(fetch_data) -> bytes:
    teile = []
    for item in fetch_data or []:
        if isinstance(item, tuple) and item:
            teile.append(bytes(item[0]))
        elif isinstance(item, (bytes, bytearray)):
            teile.append(bytes(item))
    return b" ".join(teile)


def alter_erzwingen(fetch_data, betreff: str, max_age_minutes, ignore_reason) -> None:
    """ValueError, wenn die gewaehlte Mail zu alt ist oder keine Server-Zeit hat."""
    if ignore_reason is not None:
        return
    grenze = DEFAULT_MAX_AGE_MINUTES if max_age_minutes is None else max_age_minutes
    geparst = imaplib.Internaldate2tuple(_internaldate_zeile(fetch_data))
    if geparst is None:
        raise ValueError(f"Kein auswertbarer Server-Zeitstempel (INTERNALDATE) fuer die Mail "
                         f"{betreff!r}; kein Rueckfall auf den Date-Kopf. {_IGNORE_HINT}.")
    alter = (time.time() - time.mktime(geparst)) / 60.0
    if alter > grenze:
        raise ValueError(f"Die gefundene Mail ({betreff!r}) ist {alter:.0f} Minuten alt, "
                         f"zulaessig sind {grenze:g} (--max-age-minutes). Sie stammt nicht aus "
                         f"diesem Lauf und taugt nicht als Nachweis: bitte frische Mail "
                         f"ausloesen. {_IGNORE_HINT}.")
