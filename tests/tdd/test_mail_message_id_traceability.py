"""TDD RED -- jede ausgehende Mail traegt eine Message-ID, und die Erfolgs-
Logzeile nennt genau diese ID (Beobachtbarkeit, Eintrag C5-53).

SPEC: docs/specs/modules/fix_2218_scheibe_c_observability.md (AC-1 bis AC-5;
AC-6/AC-7 sind Staging-Nachweise ohne Kern-Test).

Gemessen wird an der Stelle, an der die Zusicherung WIRKT: an der
Rohnachricht, die der Postausgang tatsaechlich eingeliefert bekommt (der
String, den ``smtplib.SMTP.sendmail`` erhaelt), und am Log -- nicht an einem
Zwischenwert in ``send()``.

Systemgrenze: ``smtplib.SMTP`` wird durch eine aufzeichnende Attrappe ersetzt
(Muster tests/tdd/test_mail_transport_dial_behaviour.py). Die Attrappe fuehrt
ein Skript ``(host, empfaenger, versuch_nr) -> Ausnahme | None`` aus und
zeichnet die Rohnachricht JEDES Einlieferungsversuchs auf, auch eines
abgelehnten. Ein echter TLS-faehiger Loopback-SMTP-Server entfaellt: smtplib
erzwingt STARTTLS + Login, und unter ``--disable-socket`` waere er nicht
bindbar; die Rohnachricht ist byte-identisch zu dem, was ueber den Draht ginge.

Kein Versand, kein Netz. Nicht als ``email``-Test markiert (Kernschicht).
"""
from __future__ import annotations

import email as email_pkg
import logging
import re
import smtplib
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from output.channels import email as email_module  # noqa: E402

PRIMAER = "mail.henemm.com"
ERSATZ = "ersatz.henemm.com"
ABSENDER = "gregor_zwanzig@henemm.com"
# Die beiden Betriebs-Postfaecher bleiben im Log unmaskiert (pii_masking),
# darueber lassen sich Log-Zeilen eindeutig einem Empfaenger zuordnen.
TEST_BOX = "gregor-test@henemm.com"
STAGING_BOX = "gregor-staging@henemm.com"
NUTZER_BOX = "ute@henemm.com"  # wird im Log zu ***@henemm.com maskiert

_ID_FORM = re.compile(r"^<[^<>\s]+@henemm\.com>$")


class _Draht:
    """Aufzeichnung aller Einlieferungsversuche: (host, empfaenger, roh)."""

    def __init__(self, skript=None):
        self.versuche: list[tuple[str, str, str]] = []
        self.skript = skript or (lambda host, empfaenger, nr: None)
        self._nr: dict[tuple[str, str], int] = {}


def _installiere(monkeypatch, skript=None, starttls_skript=None) -> _Draht:
    """``starttls_skript(host) -> Ausnahme | None`` laesst die Verbindung schon
    vor der Einlieferung scheitern (z. B. 421 beim STARTTLS)."""
    draht = _Draht(skript)

    class _Socket:
        def settimeout(self, _t):
            pass

    class _Smtp:
        def __init__(self, host, port, timeout=None):
            self._host = host
            self.sock = _Socket()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            if starttls_skript is not None:
                fehler = starttls_skript(self._host)
                if fehler is not None:
                    raise fehler

        def login(self, user, password):
            pass

        def sendmail(self, from_addr, to_addrs, msg):
            for empfaenger in to_addrs:
                schluessel = (self._host, empfaenger)
                draht._nr[schluessel] = draht._nr.get(schluessel, 0) + 1
                draht.versuche.append((self._host, empfaenger, msg))
                fehler = draht.skript(self._host, empfaenger, draht._nr[schluessel])
                if fehler is not None:
                    raise fehler

    monkeypatch.setattr(email_module.smtplib, "SMTP", _Smtp)
    monkeypatch.setattr(email_module.time, "sleep", lambda _s: None)
    monkeypatch.setattr(email_module, "running_origin", lambda _f: "production")
    return draht


def _postausgang(fallback_host: str | None = None):
    ausgang = email_module.EmailOutput.__new__(email_module.EmailOutput)
    ausgang._host = PRIMAER
    ausgang._port = 2525
    ausgang._user = "u"
    ausgang._password = "p"
    ausgang._to = NUTZER_BOX
    ausgang._from = ABSENDER
    ausgang._reply_to = "antwort@henemm.com"
    ausgang._fallback_host = fallback_host
    ausgang._fallback_user = "fu"
    ausgang._fallback_pass = "fp"
    return ausgang


def _sende(ausgang, empfaenger: list[str]) -> None:
    ausgang.send(
        "Wetter-Briefing Testlauf", "<p>Kurzer Testkoerper</p>", html=True,
        to=list(empfaenger), mail_type="trip-briefing", mail_format="compact",
    )


def _parse(roh: str):
    return email_pkg.message_from_string(roh)


def _ids(msg) -> list[str]:
    return msg.get_all("Message-ID") or []


def _info_zeilen(caplog) -> list[str]:
    return [
        r.getMessage() for r in caplog.records
        if r.levelno == logging.INFO and r.name == email_module.logger.name
    ]


def _roh_id(msg) -> str:
    ids = _ids(msg)
    assert len(ids) == 1, f"genau eine Message-ID erwartet, gefunden: {ids}"
    return ids[0]


# ---------------------------------------------------------------------------
# AC-1 -- genau eine Message-ID, alle bisherigen Kopfzeilen unveraendert
# ---------------------------------------------------------------------------

def test_eingelieferte_mail_traegt_genau_eine_message_id_und_unveraenderte_kopfzeilen(
    monkeypatch,
):
    """AC-1: die eingelieferte Rohnachricht hat genau eine Kopfzeile
    ``Message-ID`` der Form ``<...@henemm.com>``; Subject/From/To/Date/
    Reply-To/X-GZ-* bleiben wie bisher."""
    draht = _installiere(monkeypatch)

    _sende(_postausgang(), [NUTZER_BOX])

    assert len(draht.versuche) == 1, draht.versuche
    msg = _parse(draht.versuche[0][2])
    assert len(_ids(msg)) == 1, f"Message-ID-Kopfzeilen: {_ids(msg)}"
    assert _ID_FORM.match(_ids(msg)[0]), f"Form <...@henemm.com> verletzt: {_ids(msg)}"
    assert msg["Subject"] == "Wetter-Briefing Testlauf"
    # Bestandsverhalten (email.py send(): ``from_addr = self._reply_to or
    # self._from``): ist eine Inbound-Adresse gesetzt, steht SIE im From --
    # das bleibt unveraendert (Korrektur der RED-Erwartung in /50).
    assert msg["From"] == "antwort@henemm.com"
    assert NUTZER_BOX in msg["To"]
    assert msg["Date"], "Date-Kopfzeile fehlt"
    assert msg["Reply-To"] == "antwort@henemm.com"
    assert msg["X-GZ-Mail-Type"] == "trip-briefing"
    assert msg["X-GZ-Format"] == "compact"


def test_build_mime_message_setzt_uebergebene_id_und_erzeugt_sonst_selbst_eine():
    """AC-1 (Baustein): ``build_mime_message(message_id=...)`` setzt genau diese
    ID; ohne Angabe erzeugt der Baustein selbst eine (Form <...@henemm.com>)."""
    gegeben = email_module.build_mime_message(
        "S", "Text", ABSENDER, NUTZER_BOX, None, False, None,
        message_id="<fest-vergeben@henemm.com>",
    )
    assert _ids(gegeben) == ["<fest-vergeben@henemm.com>"]

    selbst = email_module.build_mime_message(
        "S", "Text", ABSENDER, NUTZER_BOX, None, False, None,
    )
    assert len(_ids(selbst)) == 1 and _ID_FORM.match(_ids(selbst)[0]), _ids(selbst)


# ---------------------------------------------------------------------------
# AC-2 -- Erfolgszeile beim Erstversuch, maskierte Adresse
# ---------------------------------------------------------------------------

def test_erstversuch_schreibt_je_empfaenger_eine_erfolgszeile_mit_id_und_maskierter_adresse(
    monkeypatch, caplog,
):
    """AC-2: ohne Retry steht genau eine Info-Zeile mit der Message-ID der
    eingelieferten Nachricht und der MASKIERTEN Adresse; die Klartextadresse
    kommt im Log nirgends vor."""
    draht = _installiere(monkeypatch)

    with caplog.at_level(logging.INFO, logger=email_module.logger.name):
        _sende(_postausgang(), [NUTZER_BOX])

    assert len(draht.versuche) == 1, "Aufbau: ein Versuch, kein Retry"
    nachweis = _roh_id(_parse(draht.versuche[0][2])).strip("<>")
    treffer = [z for z in _info_zeilen(caplog) if nachweis in z]
    assert len(treffer) == 1, (
        f"genau eine Erfolgszeile mit der ID {nachweis!r} erwartet: {_info_zeilen(caplog)}"
    )
    assert "***@henemm.com" in treffer[0], f"maskierte Adresse fehlt: {treffer[0]}"
    alles = " ".join(r.getMessage() for r in caplog.records)
    assert NUTZER_BOX not in alles, "Klartext-Empfaenger im Log (PII)"


# ---------------------------------------------------------------------------
# AC-3 -- Retry und Ersatzweg tragen dieselbe ID
# ---------------------------------------------------------------------------

def test_retry_traegt_dieselbe_message_id_und_log_nennt_sie(monkeypatch, caplog):
    """AC-3 (Retry): Versuch 1 wird vom Postausgang mit 4xx abgelehnt, Versuch 2
    angenommen -- beide Rohnachrichten tragen dieselbe ID, die Erfolgszeile
    nennt genau diese."""
    draht = _installiere(
        monkeypatch,
        lambda host, empf, nr: smtplib.SMTPResponseException(452, "zu viele") if nr == 1 else None,
    )

    with caplog.at_level(logging.INFO, logger=email_module.logger.name):
        _sende(_postausgang(), [NUTZER_BOX])

    assert len(draht.versuche) == 2, f"Aufbau: ein Retry erwartet: {len(draht.versuche)}"
    ids = {_roh_id(_parse(roh)) for _, _, roh in draht.versuche}
    assert len(ids) == 1, f"Retry hat die Message-ID gewechselt: {ids}"
    nachweis = next(iter(ids)).strip("<>")
    assert [z for z in _info_zeilen(caplog) if nachweis in z], (
        f"keine Erfolgszeile mit der ID {nachweis!r}: {_info_zeilen(caplog)}"
    )


def test_ersatzweg_traegt_dieselbe_message_id_und_log_nennt_sie(monkeypatch, caplog):
    """AC-3 (Ersatzweg): der Primaerweg lehnt dauerhaft mit 4xx ab, der
    ``[SMTP-FALLBACK]`` nimmt an -- alle Einlieferungen tragen dieselbe ID,
    die Erfolgszeile nennt sie."""
    draht = _installiere(
        monkeypatch,
        lambda host, empf, nr: (
            smtplib.SMTPResponseException(452, "zu viele") if host == PRIMAER else None
        ),
    )

    with caplog.at_level(logging.INFO, logger=email_module.logger.name):
        _sende(_postausgang(fallback_host=ERSATZ), [NUTZER_BOX])

    hosts = [h for h, _, _ in draht.versuche]
    assert ERSATZ in hosts and hosts.count(PRIMAER) >= 2, f"Aufbau: Ersatzweg genutzt? {hosts}"
    ids = {_roh_id(_parse(roh)) for _, _, roh in draht.versuche}
    assert len(ids) == 1, f"Primaer- und Ersatzweg tragen verschiedene IDs: {ids}"
    nachweis = next(iter(ids)).strip("<>")
    assert [z for z in _info_zeilen(caplog) if nachweis in z], (
        f"keine Erfolgszeile mit der ID {nachweis!r}: {_info_zeilen(caplog)}"
    )


# ---------------------------------------------------------------------------
# AC-4 -- je Empfaenger eine eigene ID, nie doppelte Kopfzeile
# ---------------------------------------------------------------------------

def test_drei_empfaenger_erhalten_je_eine_eigene_message_id(monkeypatch, caplog):
    """AC-4: bei Einlieferung je Empfaenger traegt jede Zustellung eine EIGENE
    ID, jede Nachricht hat genau EINE Message-ID-Kopfzeile, das Log nennt je
    Empfaenger die ID seiner Einlieferung."""
    draht = _installiere(monkeypatch)
    empfaenger = [TEST_BOX, STAGING_BOX, NUTZER_BOX]

    with caplog.at_level(logging.INFO, logger=email_module.logger.name):
        _sende(_postausgang(), empfaenger)

    assert [e for _, e, _ in draht.versuche] == empfaenger, "Aufbau: je Empfaenger einzeln"
    je_empfaenger = {e: _roh_id(_parse(roh)) for _, e, roh in draht.versuche}
    assert len(set(je_empfaenger.values())) == 3, (
        f"Message-IDs nicht paarweise verschieden: {je_empfaenger}"
    )
    zeilen = _info_zeilen(caplog)
    for adresse, mid in je_empfaenger.items():
        treffer = [z for z in zeilen if mid.strip("<>") in z]
        assert len(treffer) == 1, f"{adresse}: genau eine Zeile erwartet: {zeilen}"
        if adresse in (TEST_BOX, STAGING_BOX):  # unmaskierte Betriebspostfaecher
            assert adresse in treffer[0], (
                f"Zeile mit der ID von {adresse} nennt eine andere Adresse: {treffer[0]}"
            )


# ---------------------------------------------------------------------------
# AC-5 -- Erfolg nie ohne Annahme
# ---------------------------------------------------------------------------

def test_abgelehnter_empfaenger_bekommt_keine_erfolgszeile(monkeypatch, caplog):
    """AC-5: von drei Empfaengern lehnt der Postausgang einen mit 550 ab -- nur
    die zwei angenommenen bekommen eine Erfolgszeile mit ihrer ID; fuer den
    abgelehnten steht keine, die bestehende Fehlerzeile bleibt."""
    draht = _installiere(
        monkeypatch,
        lambda host, empf, nr: (
            smtplib.SMTPRecipientsRefused({empf: (550, b"Mailbox unavailable")})
            if empf == STAGING_BOX else None
        ),
    )

    with caplog.at_level(logging.INFO, logger=email_module.logger.name):
        _sende(_postausgang(), [TEST_BOX, STAGING_BOX, NUTZER_BOX])

    je_empfaenger = {e: _roh_id(_parse(roh)) for _, e, roh in draht.versuche}
    zeilen = _info_zeilen(caplog)
    for angenommen in (TEST_BOX, NUTZER_BOX):
        treffer = [z for z in zeilen if je_empfaenger[angenommen].strip("<>") in z]
        assert len(treffer) == 1, f"{angenommen}: Erfolgszeile fehlt: {zeilen}"
    abgelehnt_id = je_empfaenger[STAGING_BOX].strip("<>")
    alle = [r.getMessage() for r in caplog.records]
    assert not [z for z in alle if abgelehnt_id in z], (
        f"Erfolg behauptet fuer abgelehnten Empfaenger: {alle}"
    )
    assert [r for r in caplog.records if r.levelno == logging.ERROR and STAGING_BOX in r.getMessage()], (
        "die bestehende Fehlerzeile fuer den abgelehnten Empfaenger fehlt"
    )


# ---------------------------------------------------------------------------
# Adversary F004 -- Ersatzweg bei mehreren Empfaengern: je Empfaenger die
# eigene ID auch dort, Logzeile nennt sie
# ---------------------------------------------------------------------------

def _pruefe_ersatzweg_je_empfaenger(draht, caplog, empfaenger):
    ersatz = [(e, _roh_id(_parse(roh))) for h, e, roh in draht.versuche if h == ERSATZ]
    assert [e for e, _ in ersatz] == empfaenger, f"Aufbau: Ersatzweg je Empfaenger: {ersatz}"
    ids = [mid for _, mid in ersatz]
    assert len(set(ids)) == len(empfaenger), (
        f"Ersatzweg: Message-IDs nicht je Empfaenger verschieden: {ersatz}"
    )
    primaer_ids = {
        e: _roh_id(_parse(roh)) for h, e, roh in draht.versuche if h == PRIMAER
    }
    zeilen = _info_zeilen(caplog)
    for adresse, mid in ersatz:
        if adresse in primaer_ids:
            assert primaer_ids[adresse] == mid, (
                f"{adresse}: Primaer- und Ersatzweg tragen verschiedene IDs"
            )
        treffer = [z for z in zeilen if mid.strip("<>") in z]
        assert len(treffer) == 1 and "route=fallback" in treffer[0], (
            f"{adresse}: genau eine Ersatzweg-Erfolgszeile mit seiner ID erwartet: {zeilen}"
        )
        if adresse in (TEST_BOX, STAGING_BOX):
            assert adresse in treffer[0], treffer[0]


def test_ersatzweg_nach_verbindungsabbruch_je_empfaenger_eigene_id(monkeypatch, caplog):
    """F004 (Weg ueber ``_handle_transient_dial_failure``): der Primaerweg bricht
    die Verbindung ab, der Ersatzweg nimmt alle drei an -- jede Einlieferung
    auf dem Ersatzweg traegt die ID IHRES Empfaengers."""
    empfaenger = [TEST_BOX, STAGING_BOX, NUTZER_BOX]
    draht = _installiere(
        monkeypatch,
        lambda host, empf, nr: (
            smtplib.SMTPServerDisconnected("weg") if host == PRIMAER else None
        ),
    )

    with caplog.at_level(logging.INFO, logger=email_module.logger.name):
        _sende(_postausgang(fallback_host=ERSATZ), empfaenger)

    _pruefe_ersatzweg_je_empfaenger(draht, caplog, empfaenger)


def test_ersatzweg_nach_4xx_beim_verbindungsaufbau_je_empfaenger_eigene_id(
    monkeypatch, caplog,
):
    """F004 (Weg ueber den 4xx-Zweig in ``send()``): der Primaerweg antwortet
    schon beim STARTTLS mit 421, der Ersatzweg nimmt alle drei an -- jede
    Einlieferung traegt die ID IHRES Empfaengers."""
    empfaenger = [TEST_BOX, STAGING_BOX, NUTZER_BOX]
    draht = _installiere(
        monkeypatch,
        starttls_skript=lambda host: (
            smtplib.SMTPResponseException(421, "busy") if host == PRIMAER else None
        ),
    )

    with caplog.at_level(logging.INFO, logger=email_module.logger.name):
        _sende(_postausgang(fallback_host=ERSATZ), empfaenger)

    _pruefe_ersatzweg_je_empfaenger(draht, caplog, empfaenger)
