"""TDD RED — Issue #2302 Scheibe A: geteilter Zeitbudget-Baustein fuer
Provider-HTTP-Aufrufe (`src/providers/http.py`).

SPEC: docs/specs/modules/fix_2302_s1_provider_zeitbudget_baustein.md (AC-1..AC-7)

Zwei Provider, EIN Baustein:

- **Meteo-France-Grundpfad** (`meteofrance.py`, `_request`/`_request_once`) ist
  heute OHNE Zeitbudget. `_request` kennt keinen `deadline_at`-Parameter und
  reicht `_request_once` kein `timeout=` durch — die Retry-Kette EINES
  `_request`-Aufrufs laeuft darum bis `RETRY_ATTEMPTS x TIMEOUT` plus vier
  Wartepausen (2-60s) durch. Geprueft wird heute nur ZWISCHEN zwei
  `_request`-Aufrufen (`_fetch_series:501`). Das ist die gemeinsame
  RED-Ursache aller vier RED-Tests unten.
- **Open-Meteo** (`openmeteo.py`) hat dieses Budget seit #1448 S3 bereits. Die
  Open-Meteo-Haelften von AC-4/AC-5 sowie AC-6 sind deshalb KONTROLLEN: sie
  sind heute gruen und bilden das Regressionsnetz der Migration in einem
  UNGEMARKERTEN Waechter — der bestehende Nachweis
  (`test_send_slot_and_fetch_deadline.py`) traegt `pytest.mark.live` (`:91`)
  und wird vom Normallauf komplett verworfen.

AC-7 (ausdruecklicher Spec-Bestandteil): diese Datei traegt BEWUSST KEINEN
`live`/`email`/`staging`-Marker (Vorbild `tests/tdd/test_alert_run_deadline.py`)
und wird darum im Normallauf gesammelt. Jeder Test gegen eine haengende
Gegenstelle traegt stattdessen ein eigenes `@pytest.mark.timeout(N)`, weil
`pyproject.toml:69` global `timeout = 30` setzt. Die Werte liegen jeweils
OBERHALB der heute erwarteten FEHLSCHLAG-Laufzeit — ein Timeout-Kill statt
einer lesbaren Assertion waere ein schlechteres RED-Artefakt.

Kein Mock-Theater: echte lokale TCP-/HTTP-Server, echter httpx, echtes
tenacity. Der Egress-Waechter (`app.egress_guard`, autouse in
`tests/conftest.py:318`) laesst `127.0.0.1`/`localhost` ausdruecklich durch
(`egress_guard.py:72`), deshalb traegt diese Datei den `live`-Marker NICHT.

Abbruch-TYP (Spec-Luecke, bewusst so gefasst): AC-1 fordert
`ProviderRequestError`. Das ist am Grundpfad-Eingang (`fetch_forecast`)
erfuellt und wird dort auch strikt geprueft. Ein DIREKTER `_request`-Aufruf
endet bei Meteo-France dagegen im rohen httpx-Fehler: `stop_at_deadline`
schlaegt erst NACH einem gescheiterten Versuch an, `reraise=True` reicht
darum den letzten httpx-Fehler durch, und `_request_once` uebersetzt
httpx-Fehler nicht (das tut erst `fetch_forecast:741-747`). Die
Spec-`Implementation Details` listen KEINE Uebersetzungsschicht in
`_request`; die direkten `_request`-Tests fordern deshalb
`(ProviderRequestError, httpx.HTTPError)` — ihre Zusicherung ist die
WANDUHR, nicht der Ausnahmetyp.

AC-Test-Mapping:
| AC   | Testfunktion                                                        | Heute     |
|------|---------------------------------------------------------------------|-----------|
| AC-1 | test_meteofrance_grundpfad_bricht_bei_haengender_gegenstelle_rechtzeitig_ab | RED       |
| AC-2 | test_frist_deckelt_auch_die_retry_wartepausen                       | RED       |
| AC-3 | test_normalfall_liefert_unveraendert_daten                          | KONTROLLE |
| AC-4 | test_frist_haelt_ohne_durchgereichtes_deadline_at_meteofrance       | RED       |
| AC-4 | test_frist_haelt_ohne_durchgereichtes_deadline_at_openmeteo         | KONTROLLE |
| AC-5 | test_laufzeit_patch_der_fristdauer_wirkt_meteofrance                | RED       |
| AC-5 | test_laufzeit_patch_der_fristdauer_wirkt_openmeteo                  | KONTROLLE |
| AC-6 | test_retry_konfiguration_ist_je_provider_unabhaengig                 | KONTROLLE |
| AC-7 | keine Testfunktion — bewiesen durch das FEHLEN eines Markers plus    | —         |
|      | den `--collect-only`-Normallauf im QA-Artefakt                       |           |

Fix-Loop (Adversary-Verdict BROKEN, Findings F001/F002): zwei Waechter fuer
Stellen, an denen der Produktivcode KORREKT, aber UNBEWACHT war — je eine
gezielte Verfaelschung liess alle acht Tests oben gruen.

| Finding | Testfunktion                                                     |
|---------|------------------------------------------------------------------|
| F002    | test_serienfrist_gilt_gemeinsam_ueber_mehrere_abrufe             |
| F001    | test_aufgebrauchte_frist_bricht_am_kopf_des_naechsten_versuchs_ab |
| F004    | test_einzelversuch_bleibt_auf_timeout_gedeckelt_wenn_frist_groesser_ist |
"""
from __future__ import annotations

import json
import socket
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
import tenacity

import providers.meteofrance as mf_module
import providers.openmeteo as om_module
from app.config import Location
from providers.base import ProviderRequestError
from providers.http import capped_timeout_or_raise
from providers.meteofrance import MeteoFranceDirectProvider
from providers.openmeteo import OpenMeteoProvider

# Der Abbruch-Typ eines DIREKTEN `_request`-Aufrufs ist nicht Gegenstand der
# Spec (s. Modul-Docstring). Die Zusicherung dieser Tests ist die Wanduhr.
_ABBRUCH = (ProviderRequestError, httpx.HTTPError)

_ORT = Location(latitude=42.3, longitude=9.0, name="Korsika")


# ---------------------------------------------------------------------------
# Server-Bausteine — echte lokale Sockets, kein Mock
# ---------------------------------------------------------------------------


class _HangingServer:
    """Echter lokaler TCP-Server: nimmt Verbindungen an, antwortet aber NIE.

    WOERTLICH uebernommen aus
    `tests/tdd/test_send_slot_and_fetch_deadline.py:140-188` (httpx-Kopie des
    Originals `tests/tdd/test_mail_send_deadline.py:63-116`, #1448 S1) — die
    Spec-Abhaengigkeitstabelle verlangt ausdruecklich "uebernehmen, nicht
    nachbauen". httpx blockiert dadurch beim Warten auf die HTTP-Antwort
    (Read-Phase), begrenzt einzig durch den httpx-Client-eigenen `timeout=`.
    """

    def __init__(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self.host, self.port = self._sock.getsockname()
        self._stop = threading.Event()
        self._conns: list[socket.socket] = []
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


def _valid_openmeteo_body() -> dict:
    """Minimale, aber gueltige rohe Open-Meteo-JSON-Antwort (Vorbild
    `test_send_slot_and_fetch_deadline.py:191-198`). Meteo-France bekommt
    dieselben Bytes: `_request` reicht `response.content` unveraendert
    durch, der Inhalt ist dort nur Traeger des "unveraendert"-Nachweises."""
    base = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    times = [(base + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(3)]
    return {"hourly": {"time": times, "temperature_2m": [10.0, 10.5, 11.0]}}


def _make_ok_handler(delay: float):
    """Handler-Klasse, die nach `delay` Sekunden mit 200 + gueltiger Antwort
    kommt. `delay=0.0` ist der Normalfall (AC-3), ein spuerbares `delay` der
    ERREICHBARE, nur langsame Server aus AC-5."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server API)
            if delay:
                time.sleep(delay)
            payload = json.dumps(_valid_openmeteo_body()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):  # Ruhe im pytest-Output
            pass

    return _Handler


@contextmanager
def _antwortender_server(delay: float = 0.0):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_ok_handler(delay))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _mf_base_url(host: str, port: int) -> str:
    """`_request_once:480` haengt `GetCoverage` direkt an `BASE_URL` an —
    der abschliessende Schraegstrich ist Teil des Bestandsformats
    (`meteofrance.py:74-77`)."""
    return f"http://{host}:{port}/"


def _mf_zeitstempel() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


# ---------------------------------------------------------------------------
# AC-1 — Meteo-France-Grundpfad bricht rechtzeitig ab
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
def test_meteofrance_grundpfad_bricht_bei_haengender_gegenstelle_rechtzeitig_ab(
    monkeypatch,
):
    """RED (muss heute scheitern).

    AC-1: Given der Meteo-France-GRUNDPFAD ruft gegen eine Gegenstelle, die
    die Verbindung annimmt und nie antwortet (`_HangingServer`), mit auf
    Millisekunden geschrumpftem `FETCH_DEADLINE_SECONDS`, When
    `fetch_forecast()` aufgerufen wird, Then bricht der Aufruf mit
    `ProviderRequestError` ab und die tatsaechlich verstrichene WANDUHRZEIT
    bleibt unter einer grosszuegig bemessenen Obergrenze.

    Eingang `fetch_forecast` gewaehlt, weil AC-1 den Typ `ProviderRequestError`
    verlangt und die httpx-Uebersetzung dort sitzt (`meteofrance.py:741-747`).
    Die Zusicherung ist trotzdem die Wanduhr, NICHT eine Aufrufzaehlung und
    NICHT "`timeout=` wurde durchgereicht".

    RED-Grund heute: `_request` (`:428`) liest `FETCH_DEADLINE_SECONDS` an
    keiner Stelle. Geprueft wird das Budget nur ZWISCHEN zwei Aufrufen
    (`_fetch_series:501`) — der erste haengende Aufruf laeuft darum seine
    vollen `RETRY_ATTEMPTS=5` Versuche x `TIMEOUT` (hier 5 x 0,3s = ~1,5s)
    durch, weit jenseits der auf 0,4s geschrumpften Frist. Die Ausnahme
    selbst kommt schon heute (kein "DID NOT RAISE") — rot ist
    AUSSCHLIESSLICH die gemessene Zeit.

    Nach dem Fix: der erste Versuch ist auf `min(TIMEOUT, restzeit)` = 0,3s
    gedeckelt, der zweite auf die Restzeit 0,1s, dann greift die Frist —
    ~0,4s statt ~1,5s.
    """
    with _HangingServer() as server:
        monkeypatch.setattr(mf_module, "BASE_URL", _mf_base_url(server.host, server.port))
        monkeypatch.setattr(mf_module, "TIMEOUT", 0.3)
        monkeypatch.setattr(mf_module, "FETCH_DEADLINE_SECONDS", 0.4)
        monkeypatch.setattr(
            MeteoFranceDirectProvider._request.retry, "wait", tenacity.wait_none()
        )

        provider = MeteoFranceDirectProvider()
        start = time.monotonic()
        with pytest.raises(ProviderRequestError):
            provider.fetch_forecast(_ORT, enrich_thunder=False)
        elapsed = time.monotonic() - start

    assert elapsed < 0.9, (
        f"fetch_forecast() brauchte {elapsed:.2f}s bis zur ProviderRequestError "
        "-- FETCH_DEADLINE_SECONDS (0.4s) haette den Abbruch INNERHALB der "
        "Retry-Kette des ersten _request-Aufrufs erzwingen muessen, statt "
        "dessen vollen RETRY_ATTEMPTS x TIMEOUT-Zyklus (5 x 0.3s) abzuwarten."
    )


# ---------------------------------------------------------------------------
# AC-2 — die Frist deckelt Versuche UND Wartepausen gemeinsam
# ---------------------------------------------------------------------------


@pytest.mark.timeout(25)
def test_frist_deckelt_auch_die_retry_wartepausen(monkeypatch):
    """RED (muss heute scheitern).

    AC-2: Given dieselbe haengende Gegenstelle, aber die Wartepausen zwischen
    den Versuchen werden NICHT per `wait_none()` neutralisiert, sondern
    bleiben mit `wait_fixed(1.0)` spuerbar stehen (Muster
    `test_send_slot_and_fetch_deadline.py:673-729`), When der Grundpfad
    mehrfach retryt, Then deckelt die Frist die KETTE AUS VERSUCHEN UND
    WARTEPAUSEN gemeinsam.

    Warum diese AC nicht in AC-1 aufgeht: in der 390-Sekunden-Rechnung des
    Tickets sind die vier Pausen (bis 60s) der groessere Anteil gegenueber
    fuenf Versuchen (30s). Ein Test, der die Pausen neutralisiert, liesse
    genau diesen Anteil unbewacht — das war Adversary-Befund F001 in #1448 S3.

    TRAGENDE Groessenwahl (bitte in Phase 6 NICHT "aufraeumen"):
    `TIMEOUT` (0.5s) liegt OBERHALB von `FETCH_DEADLINE_SECONDS` (0.45s).
    Nur so ist nach dem Fix `min(TIMEOUT, restzeit)` = restzeit, der erste
    Versuch scheitert also GENAU an der Frist und die Stop-Bedingung greift
    VOR der ersten Wartepause. Kehrt man die beiden Werte um, laeuft eine
    volle 1,0s-Pause an und der Test wird falsch-rot. `TIMEOUT` bleibt hier
    bewusst gepatcht (nicht wie im Open-Meteo-Vorbild auf dem Produktionswert
    30s), weil der heutige Fehlschlag sonst 5 x 30s braeuchte und von
    pytest-timeout abgeschossen wuerde, statt eine lesbare Assertion zu
    liefern.

    Auch die Obergrenze 0,9s ist tragend, nicht grosszuegig geraten: eine
    korrekte Umsetzung landet bei ~0,46s; faellt `stop_at_deadline` aus der
    `stop`-Komposition, landet derselbe Aufruf bei ~1,45s (Versuch 1
    scheitert an der Frist, kein Stop, volle 1,0s-Pause, dann greift erst
    `capped_timeout_or_raise` am Kopf von Versuch 2). 0,9s liegt zwischen
    beiden. Wer die Schwelle hebt ODER senkt, nimmt diesem Test genau die
    Mutations-Empfindlichkeit, fuer die es ihn gibt.

    RED-Grund heute: ohne Zeitbudget laufen fuenf volle Versuche (je 0,5s)
    und vier volle Pausen (je 1,0s) — ~6,5s statt ~0,45s.
    """
    with _HangingServer() as server:
        monkeypatch.setattr(mf_module, "BASE_URL", _mf_base_url(server.host, server.port))
        monkeypatch.setattr(mf_module, "TIMEOUT", 0.5)
        monkeypatch.setattr(mf_module, "FETCH_DEADLINE_SECONDS", 0.45)
        monkeypatch.setattr(
            MeteoFranceDirectProvider._request.retry, "wait", tenacity.wait_fixed(1.0)
        )

        provider = MeteoFranceDirectProvider()
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._request(
                mf_module.TEMPERATURE_COVERAGE, _ORT.latitude, _ORT.longitude,
                2, _mf_zeitstempel(),
            )
        elapsed = time.monotonic() - start

    assert elapsed < 0.9, (
        f"_request() brauchte {elapsed:.2f}s -- die Frist (0.45s) muss die "
        "Kette aus Versuchen UND den absichtlich NICHT neutralisierten "
        "Wartepausen (1.0s je Pause) gemeinsam deckeln. Ein Wert um ~6.5s "
        "bedeutet: fuenf volle Versuche plus vier volle Pausen sind "
        "durchgelaufen."
    )


# ---------------------------------------------------------------------------
# AC-3 — Normalfall bleibt unveraendert (Gegenprobe gegen "bricht immer ab")
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
def test_normalfall_liefert_unveraendert_daten(monkeypatch):
    """KONTROLLE (heute gruen, muss gruen bleiben).

    AC-3: Given ein normal, also sofort antwortender lokaler Server, When
    derselbe neu geschuetzte (Meteo-France) bzw. migrierte (Open-Meteo) Pfad
    aufgerufen wird, Then liefert er unveraendert Daten und bricht NICHT
    vorzeitig ab.

    Pflichtbestandteil laut Spec: ohne diese Gegenprobe waere ein Fix, der
    schlicht ALLES sofort abbricht, ebenfalls gruen. Produktionswerte fuer
    `TIMEOUT`/`FETCH_DEADLINE_SECONDS` bleiben hier absichtlich unangetastet.
    """
    with _antwortender_server() as server:
        host, port = server.server_address

        # --- Meteo-France: `_request` reicht `response.content` durch ---
        monkeypatch.setattr(mf_module, "BASE_URL", _mf_base_url(host, port))
        mf = MeteoFranceDirectProvider()
        start = time.monotonic()
        roh = mf._request(
            mf_module.TEMPERATURE_COVERAGE, _ORT.latitude, _ORT.longitude,
            2, _mf_zeitstempel(),
        )
        mf_elapsed = time.monotonic() - start

        # --- Open-Meteo: `_request` liefert die geparste Antwort ---
        om = OpenMeteoProvider()
        start = time.monotonic()
        antwort = om._request(
            "/v1/ecmwf", {"latitude": _ORT.latitude, "longitude": _ORT.longitude},
            base_host=f"http://{host}:{port}",
        )
        om_elapsed = time.monotonic() - start

    assert json.loads(roh)["hourly"]["time"], (
        "Meteo-France `_request` lieferte nicht die unveraenderten Bytes der "
        f"Server-Antwort zurueck: {roh[:120]!r}"
    )
    assert antwort["hourly"]["time"], (
        f"Open-Meteo `_request` lieferte keine Nutzdaten: {antwort!r}"
    )
    assert mf_elapsed < 2.0 and om_elapsed < 2.0, (
        f"Normalfall verzoegert (fr_direct {mf_elapsed:.2f}s / openmeteo "
        f"{om_elapsed:.2f}s) -- die Fristpruefung darf einen sofort "
        "antwortenden Server nicht ausbremsen."
    )


# ---------------------------------------------------------------------------
# AC-4 — die Frist haelt AUCH OHNE durchgereichtes `deadline_at`
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
def test_frist_haelt_ohne_durchgereichtes_deadline_at_meteofrance(monkeypatch):
    """RED (muss heute scheitern).

    AC-4 (Meteo-France-Haelfte): Given `_request` wird OHNE den Parameter
    `deadline_at` aufgerufen -- genau so, wie es der Produktivaufrufer
    `_fetch_series:508` heute tut --, When der geteilte `before`-Hook feuert,
    Then setzt er die Frist selbst aus der providereigenen
    `_fetch_deadline_seconds()`-Accessor-Methode, und die Frist haelt.

    Woertliche Begruendung aus `fix_1448_s3_telegram_openmeteo.md:157-176`:
    "eine Absicherung, die man vergessen kann einzuschalten, ist im Ernstfall
    keine." Genau diese Lueckenklasse hat S1/S2 je einen Befund gekostet.

    RED-Grund heute: `_request` kennt weder den Parameter noch die Frist; der
    Aufruf laeuft seine vollen fuenf Versuche (5 x 0,3s = ~1,5s) durch.
    """
    with _HangingServer() as server:
        monkeypatch.setattr(mf_module, "BASE_URL", _mf_base_url(server.host, server.port))
        monkeypatch.setattr(mf_module, "TIMEOUT", 0.3)
        monkeypatch.setattr(mf_module, "FETCH_DEADLINE_SECONDS", 0.4)
        monkeypatch.setattr(
            MeteoFranceDirectProvider._request.retry, "wait", tenacity.wait_none()
        )

        provider = MeteoFranceDirectProvider()
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._request(
                mf_module.TEMPERATURE_COVERAGE, _ORT.latitude, _ORT.longitude,
                2, _mf_zeitstempel(),
            )
        elapsed = time.monotonic() - start

    assert elapsed < 0.9, (
        f"_request() OHNE deadline_at brauchte {elapsed:.2f}s -- die Frist "
        "(0.4s) muss auch dann greifen, wenn die Aufrufstelle gar kein "
        "deadline_at durchreicht (der Produktivaufrufer _fetch_series tut "
        "das nicht)."
    )


@pytest.mark.timeout(15)
def test_frist_haelt_ohne_durchgereichtes_deadline_at_openmeteo(monkeypatch):
    """KONTROLLE (heute gruen, muss gruen bleiben).

    AC-4 (Open-Meteo-Haelfte): dieselbe Zusicherung gegen
    `OpenMeteoProvider._request`. Seit #1448 S3 erfuellt
    (`_resolve_request_deadline`, `openmeteo.py:286-301`) — steht hier als
    Regressionsnetz der Migration auf `src/providers/http.py`, und zwar im
    UNGEMARKERTEN Waechter: der bestehende Nachweis liegt hinter
    `pytest.mark.live` und laeuft im Normallauf nie mit.
    """
    with _HangingServer() as server:
        monkeypatch.setattr(om_module, "TIMEOUT", 0.2)
        monkeypatch.setattr(om_module, "FETCH_DEADLINE_SECONDS", 0.3)
        monkeypatch.setattr(
            OpenMeteoProvider._request.retry, "wait", tenacity.wait_none()
        )

        provider = OpenMeteoProvider()
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._request(
                "/v1/ecmwf", {"latitude": _ORT.latitude, "longitude": _ORT.longitude},
                base_host=f"http://{server.host}:{server.port}",
            )
        elapsed = time.monotonic() - start

    assert elapsed < 0.9, (
        f"_request() OHNE deadline_at brauchte {elapsed:.2f}s -- die Frist "
        "(0.3s) muss auch ohne durchgereichtes deadline_at greifen. Nach der "
        "Migration auf src/providers/http.py darf dieser Wert nicht steigen."
    )


# ---------------------------------------------------------------------------
# AC-5 — ein LAUFZEIT-Patch der Fristdauer wirkt (schliesst Closure-Bauform aus)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
def test_laufzeit_patch_der_fristdauer_wirkt_meteofrance(monkeypatch):
    """RED (muss heute scheitern).

    AC-5 (Meteo-France-Haelfte): Given das Modul-Global
    `FETCH_DEADLINE_SECONDS` wird ZUR LAUFZEIT auf einen sehr kleinen Wert
    gepatcht, When `_request` gegen einen ERREICHBAREN, nur langsamen Server
    (0,6s Antwortzeit) laeuft, Then gilt der gepatchte Wert: der Aufruf
    bricht nach ~0,05s ab, statt die Antwort abzuwarten.

    Diese AC ist der Test, der eine Closure-Bauform ausschliesst: friert der
    Baustein die Fristdauer beim Dekorieren ein (z. B.
    `make_deadline_before_hook(180.0)` statt
    `make_deadline_before_hook("_fetch_deadline_seconds")`), liefe der Patch
    ins Leere und der Aufruf kaeme nach 0,6s mit Daten zurueck. Der
    erreichbare Server ist bewusst gewaehlt: gegen eine haengende
    Gegenstelle waere "bricht schnell ab" auch ohne wirksamen Patch erklaerbar.

    RED-Grund heute: `_request` liest die Konstante ueberhaupt nicht -- der
    Abruf gelingt nach 0,6s und wirft gar nichts ("DID NOT RAISE").
    """
    with _antwortender_server(delay=0.6) as server:
        host, port = server.server_address
        monkeypatch.setattr(mf_module, "BASE_URL", _mf_base_url(host, port))
        monkeypatch.setattr(mf_module, "FETCH_DEADLINE_SECONDS", 0.05)
        monkeypatch.setattr(
            MeteoFranceDirectProvider._request.retry, "wait", tenacity.wait_none()
        )

        provider = MeteoFranceDirectProvider()
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._request(
                mf_module.TEMPERATURE_COVERAGE, _ORT.latitude, _ORT.longitude,
                2, _mf_zeitstempel(),
            )
        elapsed = time.monotonic() - start

    assert elapsed < 0.4, (
        f"_request() brauchte {elapsed:.2f}s -- der zur Laufzeit auf 0.05s "
        "gepatchte FETCH_DEADLINE_SECONDS-Wert haette vor der 0.6s-Antwort "
        "des erreichbaren Servers greifen muessen. Ein Wert um ~0.6s "
        "bedeutet: die Fristdauer wurde nicht zur Aufrufzeit gelesen."
    )


@pytest.mark.timeout(15)
def test_laufzeit_patch_der_fristdauer_wirkt_openmeteo(monkeypatch):
    """KONTROLLE (heute gruen, muss gruen bleiben).

    AC-5 (Open-Meteo-Haelfte): dieselbe Zusicherung gegen
    `OpenMeteoProvider._request`. Heute erfuellt, weil
    `_resolve_request_deadline` das Modul-Global zur AUFRUFZEIT liest
    (`openmeteo.py:301`). Nach der Migration muss der geteilte Baustein
    dasselbe tun -- er schliesst ueber den METHODENNAMEN des Accessors, nie
    ueber den Wert.
    """
    with _antwortender_server(delay=0.6) as server:
        host, port = server.server_address
        monkeypatch.setattr(om_module, "FETCH_DEADLINE_SECONDS", 0.05)
        monkeypatch.setattr(
            OpenMeteoProvider._request.retry, "wait", tenacity.wait_none()
        )

        provider = OpenMeteoProvider()
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._request(
                "/v1/ecmwf", {"latitude": _ORT.latitude, "longitude": _ORT.longitude},
                base_host=f"http://{host}:{port}",
            )
        elapsed = time.monotonic() - start

    assert elapsed < 0.4, (
        f"_request() brauchte {elapsed:.2f}s -- der zur Laufzeit auf 0.05s "
        "gepatchte FETCH_DEADLINE_SECONDS-Wert muss vor der 0.6s-Antwort des "
        "erreichbaren Servers greifen. Steigt dieser Wert nach der Migration, "
        "ist die Fristdauer in eine Closure eingefroren worden."
    )


# ---------------------------------------------------------------------------
# AC-6 — kein geteiltes Retrying-Objekt: die Provider bleiben unabhaengig
# ---------------------------------------------------------------------------


@pytest.mark.timeout(20)
def test_retry_konfiguration_ist_je_provider_unabhaengig(monkeypatch):
    """KONTROLLE (heute gruen, muss gruen bleiben).

    AC-6: Given der geteilte Baustein ist in beiden Providern verdrahtet,
    When die Retry-Konfiguration des EINEN Providers veraendert wird (hier:
    `MeteoFranceDirectProvider._request.retry.wait` auf spuerbare 3,0s), Then
    bleibt das Verhalten von `OpenMeteoProvider._request` unveraendert -- es
    entsteht KEIN gemeinsames `Retrying`-Objekt.

    VERHALTENSBASIERT, nicht nur `is`-Vergleich: die Reihenfolge der beiden
    Patches ist tragend. Erst wird Open-Meteo auf `wait_none()` gesetzt,
    DANACH Meteo-France auf `wait_fixed(3.0)`. Teilten sich beide ein
    Objekt, ueberschriebe der zweite Patch den ersten und der Open-Meteo-Lauf
    zoege sich ueber mindestens eine 3,0s-Pause hin statt ~0,3s zu brauchen.
    Der `is not`-Vergleich steht ergaenzend dabei -- allein genuegt er nicht,
    weil er nur den Draht prueft, nicht die Wirkung. Er steht deshalb am ENDE:
    stuende er vorn, brauchte eine Mutation mit geteiltem `Retrying`-Objekt
    den Test strukturell ab, und die Wirkungs-Messung liefe nie -- genau die
    Beweisform, die die Spec fuer sich allein als unzureichend bezeichnet.
    """
    with _HangingServer() as server:
        monkeypatch.setattr(om_module, "TIMEOUT", 0.2)
        monkeypatch.setattr(om_module, "FETCH_DEADLINE_SECONDS", 0.3)
        monkeypatch.setattr(
            OpenMeteoProvider._request.retry, "wait", tenacity.wait_none()
        )
        # Reihenfolge tragend: dieser Patch kommt NACH dem Open-Meteo-Patch.
        monkeypatch.setattr(
            MeteoFranceDirectProvider._request.retry, "wait", tenacity.wait_fixed(3.0)
        )

        provider = OpenMeteoProvider()
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._request(
                "/v1/ecmwf", {"latitude": _ORT.latitude, "longitude": _ORT.longitude},
                base_host=f"http://{server.host}:{server.port}",
            )
        elapsed = time.monotonic() - start

    assert elapsed < 1.0, (
        f"Open-Meteos _request brauchte {elapsed:.2f}s, obwohl nur die "
        "Wartepause von fr_direct auf 3.0s gesetzt wurde -- die "
        "Retry-Konfiguration wirkt offenbar providerUEBERGREIFEND."
    )
    assert (
        MeteoFranceDirectProvider._request.retry
        is not OpenMeteoProvider._request.retry
    ), (
        "fr_direct und openmeteo teilen sich EIN Retrying-Objekt -- eine "
        "Aenderung an der Retry-Konfiguration des einen Providers wirkt "
        "damit still auf den anderen."
    )


# ---------------------------------------------------------------------------
# Fix-Loop F001/F002 — Server-Baustein mit Anfragen-ZAEHLER
# ---------------------------------------------------------------------------


@contextmanager
def _zaehlender_server(delay: float = 0.0, status: int = 200):
    """Wie `_antwortender_server`, zaehlt aber die tatsaechlich eingegangenen
    Anfragen und kann statt 200 einen retryablen Fehlercode liefern.

    Der Zaehler ist keine Zierde: beide Fix-Loop-Tests haengen daran, dass
    eine BESTIMMTE Anzahl Abrufe die Gegenstelle wirklich erreicht hat.
    Yieldet `(server, zaehler)`; `zaehler[0]` ist die Anfragenzahl.
    """
    zaehler = [0]
    sperre = threading.Lock()

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server API)
            with sperre:
                zaehler[0] += 1
            if delay:
                time.sleep(delay)
            payload = json.dumps(_valid_openmeteo_body()).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):  # Ruhe im pytest-Output
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, zaehler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Fix-Loop F002 — die Serienfrist gilt GEMEINSAM ueber alle Abrufe der Serie
# ---------------------------------------------------------------------------


@pytest.mark.timeout(20)
def test_serienfrist_gilt_gemeinsam_ueber_mehrere_abrufe(monkeypatch):
    """Waechter fuer Adversary-Finding F002 (`meteofrance.py:555-557`).

    Given `_fetch_series` laeuft gegen einen ERREICHBAREN, aber spuerbar
    langsamen Server, When der erste Abruf den groessten Teil der Serienfrist
    verbraucht hat, Then bricht die Serie an der GEMEINSAMEN Frist ab —
    der zweite Abruf bekommt die RESTZEIT, keine frische volle Frist.

    Warum nicht ueber `_request` pruefbar: die Zusicherung entsteht erst im
    Zusammenspiel ZWEIER Abrufe. Genau deshalb blieb die Verfaelschung
    (`deadline_at=deadline_at` beim `_request`-Aufruf entfernt) unbemerkt —
    pro Einzelaufruf ist der `before`-Hook, der die Frist dann selbst bildet,
    voellig korrekt. Fuer eine Serie aus bis zu 24 Abrufen je Groesse ist es
    eine stille Ruecknahme des Zeitbudgets: aus EINER 180s-Frist wuerden
    96 eigene.

    TRAGENDE Groessenwahl (bitte NICHT "aufraeumen"), gerechnet:
    Frist 2,1s, Serverantwort nach 1,5s, `TIMEOUT` bleibt auf dem
    Produktionswert (30s), Wartepausen per `wait_none()` neutralisiert
    (sie sind Gegenstand von AC-2, nicht dieses Tests).
    - KORREKT: Abruf 1 gelingt bei ~1,5s; Abruf 2 bekommt die Restzeit 0,6s
      als Timeout, laeuft in den Lesetimeout, `stop_at_deadline` greift —
      Abbruch bei **~2,1s**.
    - VERFAELSCHT: Abruf 2 bekommt eine frische 2,1s-Frist, gelingt darum
      bei ~3,0s; erst die Zwischenpruefung in `_fetch_series:543` schlaegt
      danach an — Abbruch bei **~3,0s**.
    Die Schwelle 2,6s liegt mittig zwischen beiden (0,5s Luft nach jeder
    Seite). Wer sie hebt ODER senkt, nimmt dem Test seine Trennschaerfe.
    Der Abstand Frist-zu-Antwortzeit (0,6s) ist ebenfalls tragend: er muss
    den Rueckweg durch die Schleife (GRIB-Parse-Fehlpfad, gemessen ~4ms)
    deutlich ueberdecken, sonst greift schon die Zwischenpruefung nach
    Abruf 1 und ein zweiter Abruf findet gar nicht mehr statt. Die
    Sekundenwerte sind bewusst grosszuegiger als lokal noetig (lokal gemessen:
    3 Laeufe, Streuung < 0,01s) — auf geteilten CI-Runnern ist eine
    schlafbasierte Verzoegerung die unsicherste Groesse im Test.
    """
    with _zaehlender_server(delay=1.5) as (server, zaehler):
        host, port = server.server_address
        monkeypatch.setattr(mf_module, "BASE_URL", _mf_base_url(host, port))
        monkeypatch.setattr(mf_module, "FETCH_DEADLINE_SECONDS", 2.1)
        monkeypatch.setattr(
            MeteoFranceDirectProvider._request.retry, "wait", tenacity.wait_none()
        )

        provider = MeteoFranceDirectProvider()
        # Woertlich wie der Produktivaufrufer `fetch_forecast:783`.
        deadline_at = time.monotonic() + mf_module.FETCH_DEADLINE_SECONDS
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._fetch_series(
                mf_module.TEMPERATURE_COVERAGE, _ORT.latitude, _ORT.longitude,
                datetime.now(timezone.utc), 2, deadline_at,
            )
        elapsed = time.monotonic() - start

    assert zaehler[0] >= 2, (
        f"Die Gegenstelle sah nur {zaehler[0]} Anfrage(n) -- dieser Test misst "
        "die GEMEINSAME Frist ueber MEHRERE Abrufe und braucht dafuer einen "
        "zweiten Abruf. Passiert das nicht, passen die Testgroessen nicht mehr "
        "zueinander (Frist 2.1s / Antwortzeit 1.5s)."
    )
    assert elapsed < 2.6, (
        f"_fetch_series() brauchte {elapsed:.2f}s -- die Frist der SERIE "
        "(2.1s) muss ueber ALLE Abrufe gemeinsam gelten. Ein Wert um ~3.0s "
        "bedeutet: der zweite Abruf hat eine frische volle Frist bekommen, "
        "statt der Restzeit -- das Zeitbudget waere damit wieder nur eine "
        "Pruefung ZWISCHEN den Abrufen."
    )


# ---------------------------------------------------------------------------
# Fix-Loop F001 — aufgebrauchte Frist bricht am KOPF des naechsten Versuchs ab
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
def test_aufgebrauchte_frist_bricht_am_kopf_des_naechsten_versuchs_ab(monkeypatch):
    """Waechter fuer Adversary-Finding F001 (`http.py:102-107`).

    Given eine Wartepause zwischen zwei Versuchen endet JENSEITS der Frist,
    When der Folgeversuch mit NEGATIVER Restzeit auf
    `capped_timeout_or_raise` trifft, Then endet der Abruf mit einem
    `ProviderRequestError` — der Fristabbruch bleibt als solcher erkennbar
    (ADR-0018), statt als roher Fehler aus den Tiefen des HTTP-Stacks
    herauszufallen.

    Warum der Zweig ueberhaupt erreichbar ist (und die acht Tests oben ihn
    trotzdem nie treffen): tenacity wertet `stop` VOR dem Schlafen aus. Sagt
    `stop_at_deadline` "noch nicht abgelaufen", wird die volle Pause
    abgewartet — und erst der NAECHSTE Versuch sieht die verbrauchte Frist.
    In allen bisherigen Tests greift `stop_at_deadline` schon vorher, weil
    dort der VERSUCH selbst die Frist reisst, nicht die Pause.

    TRAGENDE Groessenwahl: die Pause (0,6s) muss LAENGER sein als die Frist
    (0,3s) — sonst greift wieder die Stop-Bedingung und der Kopf-Check
    bleibt unerreicht. Der Server antwortet sofort mit einem retryablen 503,
    damit Versuch 1 in Millisekunden scheitert und die Frist praktisch
    vollstaendig fuer die Pause zur Verfuegung steht. `TIMEOUT` bleibt auf
    dem Produktionswert: `min(30, 0.3)` deckelt ohnehin auf die Restzeit.

    Ohne den Raise-Zweig ginge die negative Restzeit als `timeout=` an httpx
    weiter; der daraus entstehende Fehler ist WEDER ein
    `ProviderRequestError` noch etwas, das `fetch_forecast:741-747`
    uebersetzen wuerde.
    """
    with _zaehlender_server(status=503) as (server, zaehler):
        host, port = server.server_address
        monkeypatch.setattr(mf_module, "BASE_URL", _mf_base_url(host, port))
        monkeypatch.setattr(mf_module, "FETCH_DEADLINE_SECONDS", 0.3)
        monkeypatch.setattr(
            MeteoFranceDirectProvider._request.retry, "wait", tenacity.wait_fixed(0.6)
        )

        provider = MeteoFranceDirectProvider()
        with pytest.raises(ProviderRequestError) as excinfo:
            provider._request(
                mf_module.TEMPERATURE_COVERAGE, _ORT.latitude, _ORT.longitude,
                2, _mf_zeitstempel(),
            )

    assert "vor diesem Versuch" in str(excinfo.value), (
        f"Die Ausnahme kam nicht aus dem Kopf-Check: {excinfo.value!r}. "
        "Erwartet wird der Fristabbruch VOR dem Versuch, nicht irgendein "
        "anderer ProviderRequestError."
    )
    assert zaehler[0] == 1, (
        f"Die Gegenstelle sah {zaehler[0]} Anfragen -- nach abgelaufener Frist "
        "darf gar kein zweiter HTTP-Versuch mehr hinausgehen."
    )

    # Ergaenzend (NICHT allein tragend, steht deshalb am ENDE): derselbe
    # Kopf-Check direkt, mit bereits verstrichener Frist.
    with pytest.raises(ProviderRequestError):
        capped_timeout_or_raise(
            provider_name="fr_direct", base_timeout=30.0,
            deadline_at=time.monotonic() - 0.1,
            budget_label="FETCH_DEADLINE_SECONDS", budget_seconds=180.0,
        )


# ---------------------------------------------------------------------------
# Fix-Loop F004 — der TIMEOUT-Deckel haelt, wenn die Frist GROESSER ist
# ---------------------------------------------------------------------------


@pytest.mark.timeout(20)
def test_einzelversuch_bleibt_auf_timeout_gedeckelt_wenn_frist_groesser_ist(
    monkeypatch,
):
    """Waechter fuer Adversary-Finding F004 (`http.py:108`).

    Given die PRODUKTIONSRELATION — die Frist ist deutlich GROESSER als der
    Einzel-Timeout (real: 60s gegen 30s bei Open-Meteo, 180s gegen 30s bei
    Meteo-France) —, When ein einzelner Versuch gegen eine haengende
    Gegenstelle laeuft, Then richtet sich seine tatsaechliche Dauer nach
    `TIMEOUT`, nicht nach der viel groesseren Restzeit.

    WARUM OPEN-METEO und nicht Meteo-France (gemessen, nicht vermutet):
    `meteofrance._request_once:521` deckelt ein ZWEITES Mal selbst
    (`request_timeout = TIMEOUT if timeout is None else min(TIMEOUT, timeout)`)
    — dort maskiert der providereigene Deckel die Verfaelschung im geteilten
    Baustein, ein Test an diesem Pfad bliebe gruen und bewiese nichts.
    `openmeteo._request:661` reicht `request_timeout` dagegen unveraendert an
    `httpx` weiter; die Zusicherung des geteilten Bausteins WIRKT dort, also
    wird sie dort gemessen.

    Warum das der wichtigere Zweig von `min(base_timeout, restzeit)` ist:
    bei jedem frisch gestarteten Aufruf ist die Restzeit fast das ganze
    Budget, also groesser als `TIMEOUT` — der Deckel greift im Normalbetrieb
    also auf der `base_timeout`-SEITE. Faellt er weg (`return restzeit`),
    bekaeme der erste Versuch jeder Kette einen httpx-Timeout von bis zu 180s
    statt 30s: genau die Fehlerklasse "einzelner, in sich unbegrenzt
    blockierender Schritt", die #2302 beseitigen soll, kehrt zurueck. Alle
    uebrigen Tests hier waehlen die Frist KLEINER als `TIMEOUT` und
    exerzieren damit ausschliesslich die `restzeit`-Seite.

    TRAGENDE Groessenwahl (bitte NICHT "aufraeumen"), gerechnet:
    - `stop_after_attempt(1)` auf der `stop`-Bedingung ist der Kern des
      Tests, nicht Bequemlichkeit. Ueber die VOLLE Kette gemessen liegen
      beide Varianten weit weg von 0,3s — und ausgerechnet die verfaelschte
      waere die schnellere: ungedeckelt scheitert Versuch 1 nach 5,0s und
      `stop_at_deadline` beendet die Kette (~5,0s), gedeckelt laufen
      0,3s-Versuche bis ueber die Frist hinaus (~5s+). Nur der EINZELVERSUCH
      trennt die beiden Faelle.
    - `deadline_at` wird ausdruecklich uebergeben (woertlich wie der
      Produktivaufrufer `openmeteo.py:994`) statt dem `before`-Hook
      ueberlassen: kaeme
      `None` am Kopf-Check an, liefe der Fruehausstieg `http.py:99-100` und
      der Test waere vakuum-gruen, ohne Zeile 108 je zu erreichen.
    - Schwelle 2,0s liegt grosszuegig zwischen 0,3s (mit Deckel) und 5,0s
      (ohne). Die UNTERGRENZE 0,2s ist Positivkontrolle: ohne sie waere auch
      eine Mutation gruen, die den Deckel auf ~0 zusammenfallen laesst oder
      den Versuch gar nicht erst hinausgehen laesst.
    """
    with _HangingServer() as server:
        monkeypatch.setattr(om_module, "TIMEOUT", 0.3)
        monkeypatch.setattr(om_module, "FETCH_DEADLINE_SECONDS", 5.0)
        # Ein einziger Versuch — die Kette wuerde die beiden Faelle verwischen.
        monkeypatch.setattr(
            OpenMeteoProvider._request.retry,
            "stop",
            tenacity.stop_after_attempt(1),
        )

        provider = OpenMeteoProvider()
        deadline_at = time.monotonic() + om_module.FETCH_DEADLINE_SECONDS
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._request(
                "/v1/ecmwf", {"latitude": _ORT.latitude, "longitude": _ORT.longitude},
                base_host=f"http://{server.host}:{server.port}",
                deadline_at=deadline_at,
            )
        elapsed = time.monotonic() - start

    assert elapsed >= 0.2, (
        f"Der Versuch endete schon nach {elapsed:.2f}s -- bei TIMEOUT 0.3s "
        "gegen eine haengende Gegenstelle muss er rund 0.3s lang laufen. Ein "
        "deutlich kleinerer Wert heisst: es ging gar kein echter Versuch "
        "hinaus oder der Timeout ist auf ~0 zusammengefallen."
    )
    assert elapsed < 2.0, (
        f"Der EINE Versuch brauchte {elapsed:.2f}s -- gedeckelt werden muss "
        "er auf TIMEOUT (0.3s), obwohl die Restzeit der Frist (5.0s) viel "
        "groesser ist. Ein Wert um ~5.0s bedeutet: der min()-Deckel fehlt, "
        "der Einzelversuch laeuft ueber das gesamte Budget."
    )
