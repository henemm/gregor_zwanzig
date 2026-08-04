"""RED — Fix #1448 Scheibe S1: E-Mail-Versand bekommt Verbindungs-Timeout +
Gesamtbudget ueber die Wiederhol-Schleife.

Spec: docs/specs/modules/fix_1448_s1_mail_zeitgrenze.md (AC-1, AC-2, AC-3,
AC-4, AC-5)

Kein Mock-Theater am Transport: alle Server sind echte lokale TCP-Sockets
(Vorbild tests/tdd/test_meteofrance_direct_fallback.py:476-517 -- ein echter,
absichtlich haengender/schnell-scheiternder lokaler Server statt einer
Attrappe). Einzige Ausnahme -- wie in
tests/tdd/test_mail_transport_dial_behaviour.py:132 vorgemacht -- ist
`time.sleep`, das als Spion (`list.append`/No-Op) ersetzt wird: das misst
echtes Verhalten (die tatsaechlich angeforderte Wartedauer bzw. entkoppelt
die Testlaufzeit vom Backoff), es faelscht nichts vor.

Die vier neuen Modulkonstanten (`SMTP_OP_TIMEOUT_SECONDS`,
`SEND_BUDGET_SECONDS`, `FALLBACK_RESERVE_SECONDS`, `FALLBACK_SMTP_PORT` --
Team-Lead-Entscheidung 2026-08-01, ersetzt die bisher an zwei Stellen nackte
Zahl 587) existieren heute noch nicht -- sie werden per
`monkeypatch.setattr(..., raising=False)` gesetzt, damit ein Test HEUTE am
echten Haengen scheitert (RED) statt an einem AttributeError.

AC-3 baut absichtlich KEINEN echten SMTP-Erfolgspfad nach (das braeuchte
ein vertrauenswuerdiges TLS-Zertifikat fuer `server.starttls()` -- selbst
eine Attrappe, die wir vermeiden wollen). Geprueft wird stattdessen die
eigentliche Aussage von AC-3: die Reserve traegt -- bei haengendem
Primaerhost wird der Ersatzweg innerhalb des Budgets ueberhaupt noch
angewaehlt (der Ersatz-Server bekommt nachweislich eine Verbindung),
statt dass die Zeit vorher komplett in Primaer-Wiederholversuchen
verbrennt. Ob danach wirklich zugestellt wird, deckt bereits
tests/tdd/test_927_smtp_fallback.py gegen den echten Stalwart-Server ab
(S1 aendert daran nichts) -- hier bewusst nicht dupliziert, keine echte
Mail wird verschickt.
"""
from __future__ import annotations

import socket
import threading
import time

import pytest

import app.egress_guard as egress_guard
from output.channels import email as email_module
from output.channels.base import OutputError

# Live-Schicht (Test-Politik, CLAUDE.md): braucht echtes Netz/echte Dienste --
# lief im Kern nie gruen (CI-Vermessung 2026-08-04, #1196) und gehoert per
# Marker in den /e2e-verify-Lauf, nicht auf eine Ausnahmeliste.
pytestmark = pytest.mark.email

ABSENDER = "gregor_zwanzig@henemm.com"
# Lokaler Empfaenger: der Nicht-Resend-Guard in send() (email.py:581-607)
# laesst auf einem Nicht-Resend-Host nur @henemm.com-Adressen durch.
EMPFAENGER = "s1-zeitgrenze@henemm.com"

# RFC-5737 TEST-NET-1 -- garantiert nicht geroutet. Ein TCP-Connect dorthin
# haengt dadurch ECHT (SYN bleibt unbeantwortet, keine sofortige Ablehnung
# -- manuell verifiziert), ohne dass ein lokaler Bind noetig ist.
UNROUTABLE_HOST = "192.0.2.1"


class _HangingServer:
    """Echter lokaler TCP-Server: nimmt Verbindungen an, schreibt aber NIE
    etwas zurueck. `smtplib.SMTP(host, port)` haengt dadurch bereits beim
    Warten auf die 220-Begruessung in `connect()` (Teil von
    `smtplib.SMTP.__init__`) -- exakt das Szenario aus AC-1 ("der Socket
    nimmt die Verbindung an, sendet aber nie eine Antwort").

    Zaehlt jede angenommene Verbindung -- AC-2 weist daran die tatsaechliche
    Anzahl der Primaerversuche nach.
    """

    def __init__(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self.host, self.port = self._sock.getsockname()
        self.connection_count = 0
        self._conns: list[socket.socket] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self) -> None:
        self._sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self.connection_count += 1
            self._conns.append(conn)

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        for conn in self._conns:
            try:
                conn.close()
            except OSError:
                pass
        try:
            self._sock.close()
        except OSError:
            pass

    def __enter__(self) -> "_HangingServer":
        return self

    def __exit__(self, *exc_info) -> bool:
        self.close()
        return False


class _ImmediateTempFailServer:
    """Echter lokaler TCP-Server: antwortet auf jede Verbindung SOFORT mit
    einer 4xx-Begruessung (`421`). `smtplib.SMTP.__init__` wertet eine
    Begruessung != 220 als `SMTPConnectError` (Unterklasse von
    `SMTPResponseException`, `smtp_code=421 < 500`) -- die temporaere
    Retry-Behandlung in `send()` greift also real, ohne dass irgendetwas
    haengen muss. Reicht fuer AC-5 (Backoff-Kappung), das keinen Hang
    braucht, sondern nur einen echten, wiederholten Fehlschlag.
    """

    def __init__(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self.host, self.port = self._sock.getsockname()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self) -> None:
        self._sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            try:
                conn.sendall(b"421 Immer ausgelastet\r\n")
            except OSError:
                pass
            finally:
                conn.close()

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        try:
            self._sock.close()
        except OSError:
            pass

    def __enter__(self) -> "_ImmediateTempFailServer":
        return self

    def __exit__(self, *exc_info) -> bool:
        self.close()
        return False


def _postausgang(
    host: str, port: int, fallback_host: str | None = None
) -> email_module.EmailOutput:
    """Baut EmailOutput unter Umgehung von Settings (Vorbild:
    tests/tdd/test_mail_transport_dial_behaviour.py:55-71) -- vermeidet die
    Settings-/Resend-Default-Deny-Validierung, die unter pytest sonst den
    falschen Zweig messen wuerde."""
    ausgang = email_module.EmailOutput.__new__(email_module.EmailOutput)
    ausgang._host = host
    ausgang._port = port
    ausgang._user = "primaer-nutzer"
    ausgang._password = "primaer-geheim"
    ausgang._to = EMPFAENGER
    ausgang._from = ABSENDER
    ausgang._reply_to = None
    ausgang._fallback_host = fallback_host
    ausgang._fallback_user = "ersatz-nutzer"
    ausgang._fallback_pass = "ersatz-geheim"
    return ausgang


def _sende(ausgang: email_module.EmailOutput) -> None:
    ausgang.send("Zeitgrenzen-Testlauf", "Kurzer Testkoerper", html=False)


# ---------------------------------------------------------------------------
# AC-1 -- Grenze je Socket-Operation
# ---------------------------------------------------------------------------


@pytest.mark.timeout(10)
def test_dial_and_send_times_out_when_socket_hangs(monkeypatch):
    """AC-1: Given der Primaer-Postausgang nimmt die Verbindung an und
    antwortet nie, When `_dial_and_send()` eine ihrer Phasen ausfuehrt (hier
    bereits das Warten auf die SMTP-Begruessung waehrend des initialen
    Verbindungsaufbaus), Then wird der Aufruf spaetestens nach
    `SMTP_OP_TIMEOUT_SECONDS` mit einem Fehler abgebrochen statt unbegrenzt
    zu blockieren.

    Kein Ersatzweg konfiguriert, `SEND_BUDGET_SECONDS`/
    `FALLBACK_RESERVE_SECONDS` bleiben unveraendert (grosszuegig) -- so
    koennen alle vier Versuche stattfinden, und es wird ausschliesslich
    gemessen, ob JEDER einzelne Versuch durch `SMTP_OP_TIMEOUT_SECONDS`
    begrenzt wird (die Budget-/Reserve-Interaktion ist AC-2/AC-4).
    """
    with _HangingServer() as primaer:
        monkeypatch.setattr(
            email_module, "SMTP_OP_TIMEOUT_SECONDS", 0.3, raising=False
        )
        monkeypatch.setattr(email_module.time, "sleep", lambda s: None)

        ausgang = _postausgang(primaer.host, primaer.port)

        start = time.monotonic()
        with pytest.raises(OutputError):
            _sende(ausgang)
        elapsed = time.monotonic() - start

    assert elapsed < 5.0, (
        f"send() brauchte {elapsed:.1f}s -- SMTP_OP_TIMEOUT_SECONDS "
        "begrenzt die haengende Verbindung nicht (RED erwartet: die "
        "Konstante existiert heute nur als per monkeypatch gesetztes "
        "Modulattribut, wird von _dial_and_send()/smtplib.SMTP() aber noch "
        "nicht als timeout= verwendet -- der Aufruf haengt daher bis zum "
        "@pytest.mark.timeout(10) dieses Tests)."
    )


# ---------------------------------------------------------------------------
# AC-2 -- Schleife ueberspringt restliche Primaerversuche bei knapper Reserve
# ---------------------------------------------------------------------------


@pytest.mark.timeout(10)
def test_retry_loop_skips_remaining_primary_attempts_when_reserve_at_risk(
    monkeypatch,
):
    """AC-2: Given die Restzeit bis `SEND_BUDGET_SECONDS` reicht nach einem
    gescheiterten Versuch nicht mehr fuer einen weiteren Versuch plus die
    garantierte `FALLBACK_RESERVE_SECONDS`, When die Wiederhol-Schleife nach
    diesem Versuch prueft, ob sich ein weiterer Primaerversuch noch lohnt,
    Then wird kein weiterer Primaerversuch mehr gestartet -- die gezaehlte
    Anzahl tatsaechlicher Verbindungsversuche gegen den Primaer-Host bleibt
    nachweislich unter `max_attempts=4`.

    Werte proportional zur Beleg-Rechnung der Spec herunterskaliert (dort:
    SMTP_OP=10s/BUDGET=50s/RESERVE=12s fuehrt zu 3 statt 4 Versuchen).
    """
    with _HangingServer() as primaer:
        monkeypatch.setattr(
            email_module, "SMTP_OP_TIMEOUT_SECONDS", 0.3, raising=False
        )
        monkeypatch.setattr(
            email_module, "SEND_BUDGET_SECONDS", 1.5, raising=False
        )
        monkeypatch.setattr(
            email_module, "FALLBACK_RESERVE_SECONDS", 0.35, raising=False
        )
        monkeypatch.setattr(email_module.time, "sleep", lambda s: None)

        ausgang = _postausgang(primaer.host, primaer.port)

        with pytest.raises(OutputError):
            _sende(ausgang)

    assert primaer.connection_count >= 1
    assert primaer.connection_count < 4, (
        f"{primaer.connection_count} Verbindungsversuche gegen den "
        "Primaer-Host -- die Schleife haette vor max_attempts=4 abbrechen "
        "muessen, weil die Restzeit fuer einen weiteren Versuch plus "
        "Reserve nicht mehr gereicht haette (RED erwartet: "
        "SEND_BUDGET_SECONDS/FALLBACK_RESERVE_SECONDS existieren heute nur "
        "als monkeypatch-Attribute, die Schleife kennt kein Gesamtbudget "
        "und haengt am ersten Versuch bis zum @pytest.mark.timeout(10) "
        "dieses Tests)."
    )


# ---------------------------------------------------------------------------
# AC-3 -- die Reserve traegt: der Ersatzweg wird rechtzeitig angewaehlt
# ---------------------------------------------------------------------------


@pytest.mark.timeout(10)
def test_send_reaches_fallback_within_budget_when_primary_hangs(monkeypatch):
    """AC-3: Given der Primaer-Postausgang haengt bei jedem
    Verbindungsversuch UND ein Ersatz-Postausgang ist konfiguriert, When
    `send()` aufgerufen wird, Then wird der Ersatzweg innerhalb von
    `SEND_BUDGET_SECONDS + FALLBACK_RESERVE_SECONDS` tatsaechlich
    angewaehlt (der Ersatz-Server bekommt nachweislich eine Verbindung),
    statt dass die Zeit vollstaendig in Primaer-Wiederholversuchen
    verbrennt.

    Was dieser Test NICHT beweist (Team-Lead-Entscheidung 2026-08-01): dass
    die Mail danach ueber den Ersatzweg tatsaechlich ZUGESTELLT wird
    (STARTTLS/AUTH/DATA) -- `_dial_and_send()` ruft `server.starttls()`
    ohne eigenen Kontext auf, ein echter Erfolgsnachweis braeuchte also ein
    vertrauenswuerdiges TLS-Zertifikat fuer localhost, also selbst wieder
    eine Attrappe. Die Zustellung deckt bereits
    tests/tdd/test_927_smtp_fallback.py gegen den echten Stalwart-Server
    plus IMAP-Verifikation ab (S1 aendert daran nichts) -- hier bewusst
    nicht dupliziert, es wird keine echte Mail verschickt.

    Der Ersatz-Server laeuft auf einem freien lokalen Port.
    `FALLBACK_SMTP_PORT` (email.py, ersetzt die bisher an beiden
    Ersatzweg-Aufrufstellen nackte Zahl 587) wird per monkeypatch auf
    diesen Port geschrumpft. Ohne diese Konstante (heute) bleibt der
    Ersatzweg-Aufruf hart auf Port 587 verdrahtet -- der wird aber ohnehin
    nie erreicht, weil der Primaerweg bereits unbegrenzt haengt (derselbe
    Hang-Ort wie AC-1/AC-2/AC-4), also auch keine Gefahr fuer den echten,
    auf diesem Host laufenden Stalwart-Mailserver auf 127.0.0.1:587.
    """
    with _HangingServer() as primaer, _HangingServer() as ersatz:
        monkeypatch.setattr(
            email_module, "FALLBACK_SMTP_PORT", ersatz.port, raising=False
        )
        monkeypatch.setattr(
            email_module, "SMTP_OP_TIMEOUT_SECONDS", 0.3, raising=False
        )
        monkeypatch.setattr(
            email_module, "SEND_BUDGET_SECONDS", 1.5, raising=False
        )
        monkeypatch.setattr(
            email_module, "FALLBACK_RESERVE_SECONDS", 0.35, raising=False
        )
        monkeypatch.setattr(email_module.time, "sleep", lambda s: None)

        ausgang = _postausgang(
            primaer.host, primaer.port, fallback_host=ersatz.host
        )

        start = time.monotonic()
        with pytest.raises(Exception):
            # Der Ersatz-Server antwortet ebenfalls nie (er soll nur
            # beweisen, DASS/WANN er kontaktiert wird) -- send() endet
            # daher trotzdem mit einem Fehler. Welcher genau, ist fuer
            # AC-3 nicht die Aussage (das ist AC-4); daher hier bewusst
            # die breite `Exception`-Erwartung statt `OutputError`.
            _sende(ausgang)
        elapsed = time.monotonic() - start

    assert elapsed < 5.0, (
        f"send() brauchte {elapsed:.1f}s, bevor ueberhaupt ein Fehler kam "
        "-- das Budget wirkt nicht (RED erwartet: FALLBACK_SMTP_PORT "
        "existiert heute nicht, der Ersatzweg-Aufruf bleibt hart auf 587 "
        "verdrahtet und wird wegen des unbegrenzt haengenden Primaerwegs "
        "ohnehin nie erreicht -- der Aufruf haengt bis zum "
        "@pytest.mark.timeout(10) dieses Tests)."
    )
    assert ersatz.connection_count >= 1, (
        "der Ersatz-Server hat NIE eine Verbindung bekommen -- der "
        "Ersatzweg wurde innerhalb des Budgets nicht angewaehlt (RED "
        "erwartet: heute wird der Primaerweg nie verlassen, weil er "
        "unbegrenzt haengt)."
    )


# ---------------------------------------------------------------------------
# AC-4 -- Obergrenze, wenn Primaer- UND Ersatzweg haengen
# ---------------------------------------------------------------------------


@pytest.mark.timeout(12)
def test_send_raises_bounded_error_when_primary_and_fallback_both_hang(
    monkeypatch,
):
    """AC-4: Given weder Primaer- noch Ersatz-Postausgang antworten (beide
    haengen), When `send()` aufgerufen wird, Then wirft der Aufruf
    spaetestens nach `SEND_BUDGET_SECONDS + FALLBACK_RESERVE_SECONDS` eine
    `OutputError`, statt unbegrenzt zu blockieren.

    Ersatzweg = `UNROUTABLE_HOST` (RFC-5737 TEST-NET-1) auf dem in
    `email.py` fest verdrahteten Port 587 (`:677`/`:723`) -- der Connect
    dorthin haengt echt (manuell verifiziert), ohne dass ein lokaler Bind
    auf 587 noetig waere (auf diesem Host bereits vom echten Stalwart-
    Mailserver belegt, s. Moduldocstring).

    `UNROUTABLE_HOST` muss zusaetzlich am produktiven Egress-Waechter
    (`src/app/egress_guard.py`, Issue #1337) vorbeikommen -- der patcht
    `smtplib.SMTP.connect` bereits fuer die gesamte Testsession und blockt
    jeden nicht deklarierten Host sofort mit `EgressBlockedError` (kein
    Haengen!). Ohne diese Freigabe wuerde der Test faelschlich "gruen"
    aussehen, weil die Ausnahme sofort statt erst nach der Budget-Grenze
    kaeme.
    """
    monkeypatch.setattr(
        egress_guard,
        "_dynamic_test_hosts",
        egress_guard._dynamic_test_hosts | {UNROUTABLE_HOST},
    )
    with _HangingServer() as primaer:
        monkeypatch.setattr(
            email_module, "SMTP_OP_TIMEOUT_SECONDS", 0.3, raising=False
        )
        monkeypatch.setattr(
            email_module, "SEND_BUDGET_SECONDS", 1.5, raising=False
        )
        monkeypatch.setattr(
            email_module, "FALLBACK_RESERVE_SECONDS", 0.35, raising=False
        )
        monkeypatch.setattr(email_module.time, "sleep", lambda s: None)

        ausgang = _postausgang(
            primaer.host, primaer.port, fallback_host=UNROUTABLE_HOST
        )

        start = time.monotonic()
        with pytest.raises(OutputError):
            _sende(ausgang)
        elapsed = time.monotonic() - start

    assert elapsed < 8.0, (
        f"send() brauchte {elapsed:.1f}s trotz beidseitig haengendem "
        "Postausgang -- keine Obergrenze aus SEND_BUDGET_SECONDS + "
        "FALLBACK_RESERVE_SECONDS wirksam (RED erwartet: heute unbegrenzt, "
        "der Aufruf haengt bis zum @pytest.mark.timeout(12) dieses Tests)."
    )


# ---------------------------------------------------------------------------
# AC-5 -- Wartepause wird durch die verbleibende Reserve gekappt
# ---------------------------------------------------------------------------


@pytest.mark.timeout(10)
def test_backoff_wait_is_capped_by_remaining_reserve(monkeypatch):
    """AC-5: Given ein Primaerversuch schlaegt fehl (hier: sofortige
    4xx-Antwort, kein Haengen noetig), waehrend das geschrumpfte
    Gesamtbudget kaum noch Puffer ueber die garantierte
    `FALLBACK_RESERVE_SECONDS` hinaus laesst, When die Wartepause vor dem
    naechsten Versuch berechnet wird, Then wird sie zusaetzlich auf die
    verbleibende Zeit minus `FALLBACK_RESERVE_SECONDS` gekappt -- die
    tatsaechlich angeforderte Schlafdauer bleibt nachweislich weit unter der
    nominalen (ungekappten) Wartepause der neuen Backoff-Tabelle (Spec:
    mindestens 2s fuer den ersten Neuversuch).

    `time.sleep` wird als Spion belauscht (Vorbild
    test_mail_transport_dial_behaviour.py:132) -- misst die tatsaechlich
    angeforderte Dauer, ohne sie vorzuspiegeln.
    """
    angeforderte_wartezeiten: list[float] = []
    monkeypatch.setattr(
        email_module.time, "sleep", angeforderte_wartezeiten.append
    )

    with _ImmediateTempFailServer() as primaer:
        monkeypatch.setattr(
            email_module, "SEND_BUDGET_SECONDS", 0.3, raising=False
        )
        monkeypatch.setattr(
            email_module, "FALLBACK_RESERVE_SECONDS", 0.1, raising=False
        )

        ausgang = _postausgang(primaer.host, primaer.port)

        with pytest.raises(OutputError):
            _sende(ausgang)

    assert angeforderte_wartezeiten, (
        "kein Neuversuch wurde ueberhaupt unternommen -- Testaufbau pruefen"
    )
    assert max(angeforderte_wartezeiten) < 1.0, (
        f"angeforderte Wartezeiten {angeforderte_wartezeiten} -- die "
        "nominale (ungekappte) Backoff-Tabelle beginnt beim ersten "
        "Neuversuch bei mindestens 2s; die Wartepause haette auf "
        "restzeit - FALLBACK_RESERVE_SECONDS gekappt werden muessen (RED "
        "erwartet: send() nutzt heute die feste 5/15/30s-Tabelle ohne jede "
        "Kappung durch das -- heute nicht existierende -- Gesamtbudget)."
    )
