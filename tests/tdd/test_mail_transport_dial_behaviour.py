"""Charakterisierung des E-Mail-Transports (#1412 Scheibe S3a).

Spec: docs/specs/modules/fix_1412_s3a_transport_kapselung_mail.md
      (AC-1, AC-2, AC-3, AC-9)

S3a ist verhaltensneutral: die drei abgeschriebenen Verbindungsbloecke in
`EmailOutput.send()` (email.py:589 Primaerweg, :638/:682 Ersatzwege) werden zu
EINER Methode `_dial_and_send` zusammengezogen. Diese Datei haelt das HEUTIGE
Verhalten am Transportrand fest, damit der Umbau beweisbar nichts verschiebt --
sie ist deshalb schon VOR dem Umbau gruen und wuerde rot, wenn er etwas
veraendert. Das ist ihr ganzer Zweck.

Ausdruecklich mitgeschrieben wird die ASYMMETRIE (Analyse, Befund 1): nur der
Primaerweg fasst jeden Empfaenger einzeln ein (`isolate_per_recipient=True`),
beide Ersatzwege brechen beim ersten abgelehnten Empfaenger ab. Der
zusammengesetzte Defekt dahinter ist als #1426 erfasst und wird NACH S3a
behoben -- diese Datei schreibt bis dahin den Ist-Zustand fest, nicht den
Wunschzustand.

Nachweisform: echte Attrappe am Transportrand (kein Mock, kein MagicMock), die
jeden Schritt in der Reihenfolge aufzeichnet und gezielt ablehnen kann.
Vorbilder: tests/tdd/test_telegram_test_mode_guard.py:278-303 (Fake-SMTP),
tests/test_mail_recipient_parity.py:185-194 (Sentinel am Transport).
Es entsteht KEINE echte Verbindung und es wird KEINE Mail verschickt.
"""
from __future__ import annotations

import smtplib
from typing import Callable

import pytest

from output.channels import email as email_module
from output.channels.base import OutputError

# Live-Schicht (Test-Politik, CLAUDE.md): braucht echtes Netz/echte Dienste --
# lief im Kern nie gruen (CI-Vermessung 2026-08-04, #1196) und gehoert per
# Marker in den /e2e-verify-Lauf, nicht auf eine Ausnahmeliste.
pytestmark = pytest.mark.email

PRIMAER_HOST = "mail.henemm.com"
# Bewusst NICHT 587: der Primaerweg muss nachweislich `self._port` benutzen und
# nicht den im Ersatzweg fest verdrahteten Port.
PRIMAER_PORT = 2525
PRIMAER_NUTZER = "primaer-nutzer"
PRIMAER_GEHEIM = "primaer-geheim"

ERSATZ_HOST = "ersatz.henemm.com"
ERSATZ_PORT = 587
ERSATZ_NUTZER = "ersatz-nutzer"
ERSATZ_GEHEIM = "ersatz-geheim"

ABSENDER = "gregor_zwanzig@henemm.com"
# Lokale @henemm.com-Empfaenger: der Empfaenger-Guard (email.py:529-567,
# Nicht-Resend-Pfad) laesst sie durch -- gemessen wird hier der Transport,
# nicht der Guard (dafuer gibt es tests/test_mail_recipient_parity.py).
EMPFAENGER = ["ute@henemm.com", "vera@henemm.com", "wim@henemm.com"]


def _postausgang(fallback_host: str | None = None):
    """Baut EmailOutput unter Umgehung von Settings (__new__ + Attribute
    direkt) -- `_resend_default_deny` (config.py) wuerde unter pytest sonst
    Hosts umlenken und den falschen Zweig messen (Vorbild:
    tests/test_mail_recipient_parity.py:197-223)."""
    ausgang = email_module.EmailOutput.__new__(email_module.EmailOutput)
    ausgang._host = PRIMAER_HOST
    ausgang._port = PRIMAER_PORT
    ausgang._user = PRIMAER_NUTZER
    ausgang._password = PRIMAER_GEHEIM
    ausgang._to = EMPFAENGER[0]
    ausgang._from = ABSENDER
    ausgang._reply_to = None
    ausgang._fallback_host = fallback_host
    ausgang._fallback_user = ERSATZ_NUTZER
    ausgang._fallback_pass = ERSATZ_GEHEIM
    return ausgang


def _installiere_transport(
    monkeypatch,
    verbindungsfehler: dict[str, Callable[[], BaseException]] | None = None,
    sendefehler: dict[str, Callable[[], BaseException]] | None = None,
) -> list[tuple]:
    """Ersetzt den Draht durch eine aufzeichnende Attrappe und liefert den
    Verlauf: ("dial", host, port) / ("starttls", host) / ("login", host, user,
    pass) / ("sendmail", host, empfaenger, ergebnis) / ("close", host).

    `verbindungsfehler` wirft beim Verbindungsaufbau zum jeweiligen Host,
    `sendefehler` bei der Zustellung an den jeweiligen Empfaenger -- jeweils
    eine FRISCHE Ausnahme je Versuch (die Retry-Schleife laeuft bis zu 4x).
    """
    verlauf: list[tuple] = []
    verbindungsfehler = dict(verbindungsfehler or {})
    sendefehler = dict(sendefehler or {})

    class _FakeSocket:
        """Issue #1448 S1: `_dial_and_send()` ruft `server.sock.settimeout(...)`
        vor jeder Phase -- die Attrappe braucht dafuer ein Attribut mit einer
        No-Op-Methode (kein echter Socket, keine echte Verbindung)."""

        def settimeout(self, timeout: float) -> None:
            pass

    class _SMTPAttrappe:
        def __init__(self, host, port, timeout=None):
            # `timeout` (Issue #1448 S1: Verbindungs-Timeout) wird von der
            # Attrappe entgegengenommen, aber bewusst NICHT aufgezeichnet --
            # `verlauf` bleibt unverändert nur ("dial", host, port), die
            # bestehenden Tupel-Assertions messen weiterhin Host/Port/
            # Reihenfolge, nicht den Timeout-Wert.
            verlauf.append(("dial", host, port))
            self._host = host
            self.sock = _FakeSocket()
            fehler = verbindungsfehler.get(host)
            if fehler is not None:
                raise fehler()

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            verlauf.append(("close", self._host))
            return False

        def starttls(self):
            verlauf.append(("starttls", self._host))

        def login(self, user, password):
            verlauf.append(("login", self._host, user, password))

        def sendmail(self, from_addr, to_addrs, msg):
            empfaenger = tuple(to_addrs)
            abgelehnt = next(
                (sendefehler[a] for a in empfaenger if a in sendefehler), None
            )
            verlauf.append(
                (
                    "sendmail",
                    self._host,
                    empfaenger,
                    "abgelehnt" if abgelehnt else "zugestellt",
                )
            )
            if abgelehnt:
                raise abgelehnt()

    monkeypatch.setattr(email_module.smtplib, "SMTP", _SMTPAttrappe)
    # Wartezeiten der Retry-Schleife (5s/15s/30s) aufzeichnen statt absitzen --
    # es wird nichts weggeprueft, nur die Wanduhr.
    wartezeiten: list[float] = []
    monkeypatch.setattr(email_module.time, "sleep", wartezeiten.append)
    return verlauf


def _sende(ausgang, empfaenger: list[str]) -> None:
    ausgang.send(
        "Wetter-Briefing Testlauf",
        "Kurzer Testkoerper",
        html=False,
        to=list(empfaenger),
    )


def _zustellungen(verlauf: list[tuple], host: str) -> list[tuple[str, ...]]:
    return [e[2] for e in verlauf if e[0] == "sendmail" and e[1] == host]


# -----------------------------------------------------------------------
# AC-1 -- Primaerweg: Host, Port und Reihenfolge
# -----------------------------------------------------------------------


def test_ac1_primaerweg_verbindet_mit_konfiguriertem_ziel_in_fester_reihenfolge(
    monkeypatch,
):
    """AC-1: ein Empfaenger, Primaerweg, erfolgreich -- die Verbindung
    entsteht mit dem konfigurierten Host und Port, Reihenfolge STARTTLS ->
    Anmeldung -> Versand."""
    verlauf = _installiere_transport(monkeypatch)

    _sende(_postausgang(), [EMPFAENGER[0]])

    assert verlauf == [
        ("dial", PRIMAER_HOST, PRIMAER_PORT),
        ("starttls", PRIMAER_HOST),
        ("login", PRIMAER_HOST, PRIMAER_NUTZER, PRIMAER_GEHEIM),
        ("sendmail", PRIMAER_HOST, (EMPFAENGER[0],), "zugestellt"),
        ("close", PRIMAER_HOST),
    ]


# -----------------------------------------------------------------------
# AC-2 -- Primaerweg duldet einen abgelehnten Empfaenger
# -----------------------------------------------------------------------


def test_ac2_primaerweg_stellt_trotz_einer_ablehnung_an_die_uebrigen_zu(
    monkeypatch,
):
    """AC-2: drei Empfaenger, genau einer wird abgelehnt -- die anderen zwei
    bekommen die Mail trotzdem, und send() wirft nicht.

    Traegt seit Issue #1196 S1 (AC-6) zugleich die Verhaltensabdeckung von
    #457 (Per-Empfaenger-Fehlerbehandlung): die zwei frueheren Quelltext-
    Textprueferstests in test_issue_457_email_per_recipient.py wurden
    geloescht, weil dieser Test dieselbe Aussage bereits verhaltensbasiert
    beweist (kein Verlust an Abdeckung)."""
    verlauf = _installiere_transport(
        monkeypatch,
        sendefehler={
            EMPFAENGER[1]: lambda: smtplib.SMTPException("Empfaenger abgelehnt")
        },
    )

    _sende(_postausgang(), EMPFAENGER)

    assert _zustellungen(verlauf, PRIMAER_HOST) == [
        (EMPFAENGER[0],),
        (EMPFAENGER[1],),
        (EMPFAENGER[2],),
    ], "der Primaerweg versucht jeden Empfaenger einzeln"
    zugestellt = [
        e[2][0] for e in verlauf if e[0] == "sendmail" and e[3] == "zugestellt"
    ]
    assert zugestellt == [EMPFAENGER[0], EMPFAENGER[2]]
    assert [e for e in verlauf if e[0] == "dial"] == [
        ("dial", PRIMAER_HOST, PRIMAER_PORT)
    ], "eine abgelehnte Zustellung darf keinen Neuversuch ausloesen"


# -----------------------------------------------------------------------
# AC-3 -- Ersatzwege brechen beim ersten abgelehnten Empfaenger ab
# -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "weg, primaerfehler",
    [
        ("ersatzweg-1-4xx", lambda: smtplib.SMTPResponseException(452, "Zu viele Nachrichten")),
        ("ersatzweg-2-netzfehler", lambda: OSError("Namensaufloesung fehlgeschlagen")),
    ],
)
def test_ac3_ersatzweg_bricht_beim_ersten_abgelehnten_empfaenger_ab(
    monkeypatch, weg, primaerfehler
):
    """AC-3: drei Empfaenger auf dem Ersatzweg, genau einer wird abgelehnt --
    kein Zustellversuch nach dem gescheiterten, und send() wirft. Beide
    Ersatzwege (nach 4xx bzw. nach Netzfehler) sind getrennter Code und werden
    getrennt geprueft."""
    verlauf = _installiere_transport(
        monkeypatch,
        verbindungsfehler={PRIMAER_HOST: primaerfehler},
        sendefehler={
            EMPFAENGER[1]: lambda: smtplib.SMTPException("Ersatzweg lehnt ab")
        },
    )

    with pytest.raises(OutputError):
        _sende(_postausgang(fallback_host=ERSATZ_HOST), EMPFAENGER)

    assert _zustellungen(verlauf, ERSATZ_HOST) == [
        (EMPFAENGER[0],),
        (EMPFAENGER[1],),
    ], f"{weg}: nach dem abgelehnten Empfaenger darf kein weiterer folgen"
    assert ("dial", ERSATZ_HOST, ERSATZ_PORT) in verlauf
    assert len([e for e in verlauf if e[0] == "dial" and e[1] == PRIMAER_HOST]) == 4, (
        f"{weg}: der Ersatzweg ist erst nach vier gescheiterten Versuchen dran"
    )


# -----------------------------------------------------------------------
# F001 (#1448 S1 Adversary) -- Transportabbruch darf NICHT wie eine
# Empfaenger-Ablehnung verschluckt werden
# -----------------------------------------------------------------------


def test_f001_primaerweg_reicht_transportabbruch_durch_statt_ihn_zu_verschlucken(
    monkeypatch,
):
    """F001 (Adversary-Fund zu #1448 S1): bricht der Transport WAEHREND der
    Empfaenger-Schleife mit `SMTPServerDisconnected` ab (z.B. weil die neue
    Zeitgrenze aus S1 waehrend eines `sendmail()`-Aufrufs zuschlaegt --
    CPython wandelt einen Timeout dort in genau diese, rein von
    `SMTPException` abgeleitete Ausnahme um, s. email.py `_dial_and_send()`),
    darf die Empfaenger-Isolierung (`isolate_per_recipient=True`, #1412 S3a)
    sie NICHT wie eine normale Empfaenger-Ablehnung (z.B.
    `SMTPRecipientsRefused`) schlucken und mit dem naechsten Empfaenger
    weitermachen -- der Socket ist tot, ein weiterer Versuch darauf ist
    sinnlos, und `send()` wuerde sonst nach aussen stillschweigend Erfolg
    melden, obwohl ab dem Abbruch niemand mehr die Mail bekommen hat.

    Erwartung NACH dem Fix: der Abbruch verlaesst die Empfaenger-Schleife
    sofort (kein Zustellversuch fuer den DRITTEN Empfaenger auf DERSELBEN
    Verbindung) und landet in `send()`s eigenem
    `SMTPServerDisconnected`-Zweig, der wiederholt und am Ende (hier: kein
    Ersatzweg konfiguriert) `OutputError` wirft -- `send()` darf NICHT
    normal zurueckkehren.
    """
    verlauf = _installiere_transport(
        monkeypatch,
        sendefehler={
            EMPFAENGER[1]: lambda: smtplib.SMTPServerDisconnected(
                "Verbindung waehrend sendmail() verloren"
            )
        },
    )

    with pytest.raises(OutputError):
        _sende(_postausgang(), EMPFAENGER)

    dial_indices = [i for i, e in enumerate(verlauf) if e[0] == "dial"]
    assert len(dial_indices) >= 2, (
        "der Transportabbruch haette send()s eigene "
        "SMTPServerDisconnected-Behandlung (Retry) ausloesen muessen -- "
        f"nur {len(dial_indices)} Verbindungsversuch(e) im Verlauf"
    )
    erster_versuch = verlauf[dial_indices[0]:dial_indices[1]]
    zustellungen_erster_versuch = [
        e[2] for e in erster_versuch if e[0] == "sendmail"
    ]
    assert zustellungen_erster_versuch == [
        (EMPFAENGER[0],),
        (EMPFAENGER[1],),
    ], (
        "nach dem Transportabbruch bei EMPFAENGER[1] darf auf DERSELBEN "
        "Verbindung kein weiterer Zustellversuch (EMPFAENGER[2]) mehr "
        f"folgen -- tatsaechlich: {zustellungen_erster_versuch}"
    )


# -----------------------------------------------------------------------
# AC-9 -- die Meldungstexte, wortgleich
# -----------------------------------------------------------------------

# Woertlich aus dem heutigen Code abgelesen (email.py:612, :618-621,
# :649-652, :653-657, :661, :693, :694); das Praefix "[email] " setzt
# OutputError.__init__ (output/channels/base.py:55).
_ERSATZ_UNERREICHBAR = "Ersatz-Postausgang unerreichbar"

FEHLERFAELLE = [
    (
        "anmeldefehler",
        lambda: smtplib.SMTPAuthenticationError(535, "Zugang verweigert"),
        None,
        "[email] SMTP authentication error: (535, 'Zugang verweigert')",
    ),
    (
        "dauerhafte-ablehnung-5xx",
        lambda: smtplib.SMTPResponseException(550, "Postfach unbekannt"),
        None,
        "[email] SMTP permanent error 550: Postfach unbekannt",
    ),
    (
        "voruebergehende-ablehnung-4xx-ohne-ersatzweg",
        lambda: smtplib.SMTPResponseException(452, "Zu viele Nachrichten"),
        None,
        "[email] SMTP temporary error 452 after 4 attempts: Zu viele Nachrichten",
    ),
    (
        "voruebergehende-ablehnung-4xx-mit-gescheitertem-ersatzweg",
        lambda: smtplib.SMTPResponseException(452, "Zu viele Nachrichten"),
        ERSATZ_HOST,
        "[email] SMTP temporary error 452 after 4 attempts "
        f"(fallback also failed: {_ERSATZ_UNERREICHBAR})",
    ),
    (
        "sonstiger-smtp-fehler",
        lambda: smtplib.SMTPException("Begruessung fehlgeschlagen"),
        None,
        "[email] SMTP error: Begruessung fehlgeschlagen",
    ),
    (
        "netzfehler-ohne-ersatzweg",
        lambda: OSError("Namensaufloesung fehlgeschlagen"),
        None,
        "[email] Connection error: Namensaufloesung fehlgeschlagen",
    ),
    (
        "netzfehler-mit-gescheitertem-ersatzweg",
        lambda: OSError("Namensaufloesung fehlgeschlagen"),
        ERSATZ_HOST,
        "[email] Connection error: Namensaufloesung fehlgeschlagen "
        f"(fallback also failed: {_ERSATZ_UNERREICHBAR})",
    ),
]


@pytest.mark.parametrize(
    "fall, primaerfehler, fallback_host, erwartete_meldung",
    FEHLERFAELLE,
    ids=[f[0] for f in FEHLERFAELLE],
)
def test_ac9_fehlermeldungen_bleiben_wortgleich(
    monkeypatch, fall, primaerfehler, fallback_host, erwartete_meldung
):
    """AC-9: je Fehlerart der wortgleiche Meldungstext. Kein bestehender Test
    prueft diese Texte (S1, repo-weite Suche) -- eine versehentliche
    Umformulierung beim Umbau bliebe sonst unbemerkt, obwohl die Meldung das
    ist, was im Betrieb gelesen wird."""
    _installiere_transport(
        monkeypatch,
        verbindungsfehler={
            PRIMAER_HOST: primaerfehler,
            ERSATZ_HOST: lambda: OSError(_ERSATZ_UNERREICHBAR),
        },
    )

    with pytest.raises(OutputError) as fehler:
        _sende(_postausgang(fallback_host=fallback_host), [EMPFAENGER[0]])

    assert str(fehler.value) == erwartete_meldung
