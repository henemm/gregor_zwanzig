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

---

TDD RED — Issue #2302 Scheibe B: derselbe Baustein fuer `dwd.py` (ICON-D2)
und `dwd_eu.py` (ICON-EU).

SPEC: docs/specs/modules/fix_2302_s2_dwd_zeitbudget.md (AC-1..AC-9)

Gemeinsame RED-Ursache aller Waechter unten: beide `_request`-Methoden
(`dwd.py:323`, `dwd_eu.py:312`) kennen weder einen `deadline_at`-Parameter
noch die Fristkonstanten ihres Moduls. Geprueft wird das Budget heute nur
ZWISCHEN zwei Aufrufen (`dwd.py:341`, `dwd.py:486`, `dwd_eu.py:408`).

`_HangingServer` (`:105`), `_antwortender_server` (`:193`) und die
Normalfall-Bauform (`:351`) werden GETEILT, nicht kopiert (Spec Test Plan,
"Heimat und Teilung").

AC-Test-Mapping Scheibe B (parametrisierte IDs einzeln gelistet):
| AC   | Testfunktion (ID)                                                   | Heute |
|------|---------------------------------------------------------------------|-------|
| AC-1 | test_dwd_grundpfad_bricht_bei_haengender_gegenstelle_ab[dwd]        | RED   |
| AC-2 | test_dwd_grundpfad_bricht_bei_haengender_gegenstelle_ab[dwd_eu]     | RED   |
| AC-3 | test_dwd_normalfall_liefert_unveraendert_daten[dwd]                 | KONTR.|
| AC-3 | test_dwd_normalfall_liefert_unveraendert_daten[dwd_eu]              | KONTR.|
| AC-4 | test_dwd_gewitterpfad_haelt_die_gewitterfrist_nicht_die_grundfrist  | RED   |
| AC-5 | test_dwd_eu_gewitterpfad_haelt_seine_frist_und_bleibt_fail_soft     | RED   |
| AC-6 | test_hook_vorgabewert_ist_die_weitere_frist[dwd]                    | RED   |
| AC-6 | test_hook_vorgabewert_ist_die_weitere_frist[dwd_eu]                 | RED   |
| AC-7 | test_laufzeit_patch_der_fristdauer_wirkt_dwd[dwd]                   | RED   |
| AC-7 | test_laufzeit_patch_der_fristdauer_wirkt_dwd[dwd_eu]                | RED   |
| AC-8 | test_retry_konfiguration_ist_je_dwd_provider_unabhaengig            | RED   |
| AC-9 | test_thunder_zeitbudget_waechter_laeuft_im_normallauf_mit           | RED   |
| AC-10| keine Testfunktion — Regressionslauf der sechs M3-Dateien im QA-Artefakt |   |
| F-ADV1| test_dwd_frist_deckelt_auch_die_retry_wartepausen[dwd]/[dwd_eu]    | Adversary-Fix-Loop |
| F-ADV2| test_dwd_serienfrist_gilt_gemeinsam_ueber_mehrere_abrufe           | Adversary-Fix-Loop |

SPEC-ABWEICHUNG (AC-4, ausdruecklich gemeldet statt still gekapselt):
AC-4 verlangt "liefert fail-soft `None`/eine unvollstaendige Reihe statt eine
propagierte Ausnahme". Fuer `dwd.py` ist das faktisch falsch —
`fetch_thunder_signals_named` wirft `ThunderSourceUnavailableError`, sobald
JEDER Versuch fehlgeschlagen ist (`dwd.py:508-511`, #1492 S2a), und genau das
ist gegen eine haengende Gegenstelle immer der Fall. Der AC-4-Waechter faengt
deshalb ausschliesslich `ThunderSourceUnavailableError`; ein
`ProviderRequestError` aus dem Fristabbruch, der bis zum Test durchschluege,
laesst ihn scheitern. Fuer `dwd_eu.py` (AC-5) stimmt die AC-Formulierung — dort
gibt es diesen Zaehlweg nicht.

---

TDD RED — Issue #2302 Scheibe C: derselbe Baustein fuer `geosphere.py`
(AROME/NWP + SNOWGRID).

SPEC: docs/specs/modules/fix_2302_s3_geosphere_zeitbudget.md (AC-1..AC-8)

Gemeinsame RED-Ursache: `GeoSphereProvider._request` (`geosphere.py:293`)
kennt weder `deadline_at` noch eine Fristkonstante und reicht `timeout=`
nicht an `self._client.get()` durch (Client-Default 30s). Anders als bei
Scheibe B laufen die meisten Waechter unten NICHT am `TypeError` vorbei --
`_request` und `fetch_combined` werden ohne `deadline_at` aufgerufen (ihre
heutige Signatur), RED entsteht ausschliesslich ueber die WANDUHR.

Ruest-Helfer `_geo_ruesten` ruehrt `wait` NIE implizit an (F-ADV1-Lehre aus
Scheibe B) -- nur bei explizit uebergebenem `wait`. Fuer die reinen
Deckel-Waechter (AC-1/AC-4/AC-6/AC-7, nicht wartepausen-kritisch) wird
`stop` sichtbar im jeweiligen Testkoerper auf `stop_after_attempt(1)`
gesetzt, um die RED-Laufzeit auf `TIMEOUT` zu begrenzen, statt auf die volle
Retry-Kette samt Produktions-Backoff (2-60s) -- das ruehrt ausdruecklich
nicht an `wait` und ist damit von der F-ADV1-Klasse unberuehrt.

AC-Test-Mapping Scheibe C:
| AC   | Testfunktion                                                        | Heute |
|------|----------------------------------------------------------------------|-------|
| AC-1 | test_geosphere_grundpfad_bricht_bei_haengender_gegenstelle_ab       | RED   |
| AC-2 | test_geosphere_frist_deckelt_auch_die_retry_wartepausen             | RED   |
| AC-3 | test_geosphere_fetch_combined_haelt_die_gemeinsame_serienfrist      | RED   |
| AC-4 | test_geosphere_fetch_combined_nwp_frist_bricht_ab_ohne_leeres_ergebnis | RED |
| AC-5 | test_geosphere_normalfall_liefert_unveraendert_daten                | KONTR.|
| AC-6 | test_geosphere_hook_vorgabewert_ist_die_weitere_frist                | RED   |
| AC-7 | test_geosphere_fetch_snowgrid_bleibt_fail_soft_und_journalisiert    | RED   |
| AC-8 | keine Testfunktion — Regressionslauf der fuenf Dateien im QA-Artefakt|       |
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest
import tenacity

import providers.dwd as dwd_module
import providers.dwd_eu as dwd_eu_module
import providers.geosphere as geosphere_module
import providers.meteofrance as mf_module
import providers.openmeteo as om_module
from app.config import Location
from providers.base import ProviderRequestError, ThunderSourceUnavailableError
from providers.dwd import DwdDirectProvider
from providers.dwd_eu import DwdEuDirectProvider
from providers.geosphere import GeoSphereProvider
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


# ===========================================================================
# Scheibe B (#2302) — dwd.py (ICON-D2) und dwd_eu.py (ICON-EU)
# ===========================================================================

# (Modul, Providerklasse, Name der Fristkonstante). `dwd_eu.py` hat NUR das
# Gewitterbudget (kein `fetch_forecast`), `dwd.py` hat zwei Konstanten — die
# hier genannte ist die WEITERE Huelle (180s), nie die Gewitterfrist (150s).
_DWD = (dwd_module, DwdDirectProvider, "FETCH_DEADLINE_SECONDS")
_DWD_EU = (dwd_eu_module, DwdEuDirectProvider, "THUNDER_FETCH_DEADLINE_SECONDS")
_BEIDE = [pytest.param(_DWD, id="dwd"), pytest.param(_DWD_EU, id="dwd_eu")]


def _dwd_ruesten(monkeypatch, modul, klasse, host, port, *, timeout, fristen, wait=None):
    """BASE_URL auf den lokalen Server, `TIMEOUT` und die Fristkonstanten
    klein, Wartepausen per `wait_none()` neutralisiert (die Pausen selbst sind
    Gegenstand von AC-2 in Scheibe A, nicht der meisten Waechter hier).

    `wait` ist optional und bleibt fuer alle bisherigen Aufrufer beim
    Vorgabewert `wait_none()` -- nur
    `test_dwd_frist_deckelt_auch_die_retry_wartepausen` setzt ihn bewusst auf
    eine SPUERBARE Pause, weil genau diese Neutralisierung Adversary-Finding
    F-ADV1 erst ermoeglicht hat.

    `TIMEOUT` wird VOR dem Erzeugen des Providers gepatcht: der Client
    uebernimmt ihn als Vorgabe-Timeout im Konstruktor (`dwd.py:310`).
    """
    monkeypatch.setattr(modul, "BASE_URL", f"http://{host}:{port}/")
    monkeypatch.setattr(modul, "TIMEOUT", timeout)
    for name, wert in fristen.items():
        monkeypatch.setattr(modul, name, wert)
    monkeypatch.setattr(
        klasse._request.retry, "wait", wait if wait is not None else tenacity.wait_none()
    )
    return klasse()


def _dwd_url(modul) -> str:
    """Eine URL im Bestandsformat des jeweiligen Moduls — erst NACH dem
    BASE_URL-Patch aufrufen, `_build_url` liest das Modul-Global zur
    Aufrufzeit (`dwd.py:194`, `dwd_eu.py:210`)."""
    return modul._build_url(datetime.now(timezone.utc), 1, modul.THUNDER_PARAMS[0])


# ---------------------------------------------------------------------------
# AC-1 / AC-2 — Grundpfad-`_request` bricht an der Frist ab
# ---------------------------------------------------------------------------


@pytest.mark.timeout(30)
@pytest.mark.parametrize("fall", _BEIDE)
def test_dwd_grundpfad_bricht_bei_haengender_gegenstelle_ab(monkeypatch, fall):
    """RED (muss heute scheitern).

    AC-1 (`dwd`) / AC-2 (`dwd_eu`): Given `_request` laeuft direkt gegen eine
    Gegenstelle, die annimmt und nie antwortet, mit auf 0,45s gepatchter
    Frist, When `_request(url, deadline_at=...)` aufgerufen wird, Then bricht
    der Aufruf mit einer Ausnahme aus `(ProviderRequestError, httpx.HTTPError)`
    ab und die verstrichene WANDUHRZEIT bleibt unter 0,9s.

    RED-Grund heute: `_request` nimmt gar kein `deadline_at` an
    (`dwd.py:323`, `dwd_eu.py:312`) — der Aufruf stirbt am `TypeError`, die
    Wanduhr-Zusicherung wird in RED also noch nicht ausgeuebt.

    TRAGENDE Groessenwahl: `TIMEOUT` (5,0s) liegt DEUTLICH OBERHALB der Frist
    (0,45s). Nur so misst der Test den Timeout-DECKEL mit: reicht die
    Implementierung den Rueckgabewert von `capped_timeout_or_raise` nicht als
    `timeout=` an den Client durch, laeuft schon Versuch 1 volle 5,0s und der
    Test wird rot. Mit einem `TIMEOUT` unterhalb der Frist bliebe genau diese
    Verfaelschung gruen — `dwd.py` hat, anders als
    `meteofrance._request_once:521`, keinen zweiten providereigenen Deckel.
    Die Untergrenze 0,2s ist Positivkontrolle: sie faengt eine Mutation, die
    den Deckel auf ~0 zusammenfallen laesst oder gar keinen Versuch hinausgehen
    laesst.
    """
    modul, klasse, frist = fall
    with _HangingServer() as server:
        provider = _dwd_ruesten(
            monkeypatch, modul, klasse, server.host, server.port,
            timeout=5.0, fristen={frist: 0.45},
        )
        url = _dwd_url(modul)
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._request(url, deadline_at=time.monotonic() + 0.45)
        elapsed = time.monotonic() - start

    assert 0.2 <= elapsed < 0.9, (
        f"_request() brauchte {elapsed:.2f}s -- die Frist (0.45s) muss den "
        "Abbruch INNERHALB der Retry-Kette EINES Aufrufs erzwingen, und der "
        "Einzelversuch muss auf die Restzeit gedeckelt sein. Ein Wert um "
        "~5.0s bedeutet: der gedeckelte Timeout wird nicht an den "
        "httpx-Client durchgereicht."
    )


# ---------------------------------------------------------------------------
# F-ADV1 — die Frist deckelt AUCH bei dwd.py/dwd_eu.py die Retry-Wartepausen
# ---------------------------------------------------------------------------


@pytest.mark.timeout(30)
@pytest.mark.parametrize("fall", _BEIDE)
def test_dwd_frist_deckelt_auch_die_retry_wartepausen(monkeypatch, fall):
    """Waechter fuer Adversary-Finding F-ADV1 (#2302 Scheibe B, MEDIUM).

    Scheibe-B-Gegenstueck zu `test_frist_deckelt_auch_die_retry_wartepausen`
    (:333-382, Scheibe A/AC-2). Entfernt man `| stop_at_deadline` aus dem
    `stop=`-Ausdruck in `dwd.py:335` bzw. seinem Gegenstueck in `dwd_eu.py`,
    blieben bis zu diesem Test ALLE elf dwd-bezogenen Tests gruen: der
    Ruest-Helfer `_dwd_ruesten` setzt `wait` standardmaessig auf
    `tenacity.wait_none()` und neutralisiert damit ueber die GESAMTE
    Scheibe-B-Suite genau den Anteil, den diese Mutation sichtbar machen
    wuerde. Ausserhalb von pytest nachgemessen: mit echter Wartepause ergibt
    die Mutation ~1.45s statt ~0.45s (wie beim Scheibe-A-Vorbild).

    AC-1 (`dwd`) / AC-2 (`dwd_eu`): Given dieselbe haengende Gegenstelle wie
    im Grundpfad-Test oben, aber die Wartepausen werden NICHT neutralisiert,
    sondern bleiben mit `wait_fixed(1.0)` spuerbar stehen, When der
    Grundpfad mehrfach retryt, Then deckelt die Frist die KETTE AUS
    VERSUCHEN UND WARTEPAUSEN gemeinsam.

    TRAGENDE Groessenwahl (Vorbild :348-365, woertlich auf dwd uebertragen):
    `TIMEOUT` (0.5s) liegt OBERHALB der Frist (0.45s). Nur so ist
    `min(TIMEOUT, restzeit)` = restzeit, der erste Versuch scheitert also
    GENAU an der Frist und die Stop-Bedingung greift VOR der ersten
    Wartepause. Kehrt man die beiden Werte um, laeuft eine volle 1.0s-Pause
    an und der Test wird falsch-rot.

    Auch die Obergrenze 0.9s ist tragend, nicht grosszuegig geraten: eine
    korrekte Umsetzung landet bei ~0.46s; faellt `stop_at_deadline` aus der
    `stop`-Komposition, landet derselbe Aufruf bei ~1.45s (Versuch 1
    scheitert an der Frist, kein Stop, volle 1.0s-Pause, dann greift erst
    der Kopf-Check am Beginn von Versuch 2). 0.9s liegt zwischen beiden. Wer
    die Schwelle hebt ODER senkt, nimmt diesem Test genau die Mutations-
    Empfindlichkeit, fuer die es ihn gibt. Die Untergrenze 0.2s ist
    Positivkontrolle (Muster der uebrigen Waechter in dieser Datei).
    """
    modul, klasse, frist = fall
    with _HangingServer() as server:
        provider = _dwd_ruesten(
            monkeypatch, modul, klasse, server.host, server.port,
            timeout=0.5, fristen={frist: 0.45}, wait=tenacity.wait_fixed(1.0),
        )
        url = _dwd_url(modul)
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._request(url, deadline_at=time.monotonic() + 0.45)
        elapsed = time.monotonic() - start

    assert 0.2 <= elapsed < 0.9, (
        f"_request() brauchte {elapsed:.2f}s -- die Frist (0.45s) muss die "
        "Kette aus Versuchen UND den absichtlich NICHT neutralisierten "
        "Wartepausen (1.0s je Pause) gemeinsam deckeln. Ein Wert um ~1.45s "
        "bedeutet: `stop_at_deadline` fehlt in der stop-Komposition, die "
        "volle 1.0s-Pause nach dem ersten Versuch laeuft ungebremst an."
    )


# ---------------------------------------------------------------------------
# F-ADV2 — die Serienfrist gilt GEMEINSAM ueber mehrere `_fetch_series`-Abrufe
# ---------------------------------------------------------------------------


@pytest.mark.timeout(20)
def test_dwd_serienfrist_gilt_gemeinsam_ueber_mehrere_abrufe(monkeypatch):
    """Waechter fuer Adversary-Finding F-ADV2 (`dwd.py:387`, MEDIUM).

    Pendant zu `test_serienfrist_gilt_gemeinsam_ueber_mehrere_abrufe` (:729,
    Scheibe A/F002), uebertragen auf `DwdDirectProvider._fetch_series` — NUR
    `dwd.py` hat diese Methode, `dwd_eu.py` kennt keinen `fetch_forecast`-
    Grundpfad (s. Modul-Docstring oben), darum hier unparametrisiert.

    Warum kein Test, der `_request` direkt aufruft, diese Luecke schliesst:
    die Zusicherung entsteht erst im ZUSAMMENSPIEL zweier Abrufe innerhalb
    EINER Schleife. `_fetch_series` hat zwar eine Zwischenpruefung
    (`dwd.py:380-385`), die weiter begrenzt -- die reicht aber nur, wenn der
    EINZELNE `_request`-Aufruf die Restzeit der Serie kennt. Entfernt man
    `deadline_at=deadline_at` aus dem Aufruf (`dwd.py:387`), bildet der
    geteilte `before`-Hook (`providers/http.py:50-54`) fuer JEDEN Abruf ein
    FRISCHES Fenster aus `FETCH_DEADLINE_SECONDS` statt der Restzeit -- direkte
    `_request`-Tests uebergeben `deadline_at` immer explizit und sehen das
    nie.

    Given `_fetch_series` laeuft gegen einen ERREICHBAREN, aber spuerbar
    langsamen Server, When der erste Abruf den groessten Teil der Serienfrist
    verbraucht hat, Then bricht die Serie an der GEMEINSAMEN Frist ab -- der
    zweite Abruf bekommt die RESTZEIT, keine frische volle Frist.

    TRAGENDE Groessenwahl, WOERTLICH vom Vorbild uebernommen (dieselbe
    Mechanik, derselbe Baustein): Frist 2,1s, Serverantwort nach 1,5s,
    `TIMEOUT` (10,0s) bleibt deutlich oberhalb der Frist, Wartepausen per
    `wait_none()` neutralisiert.
    - KORREKT: Abruf 1 gelingt bei ~1,5s; Abruf 2 bekommt die Restzeit 0,6s
      als Timeout, laeuft in den Lesetimeout -- Abbruch bei ~2,1s.
    - VERFAELSCHT: Abruf 2 bekommt eine frische 2,1s-Frist, gelingt darum
      bei ~3,0s; die Zwischenpruefung (Kopf von Abruf 3) schlaegt erst
      danach an -- Abbruch bei ~3,0s.
    Die Schwelle 2,6s liegt mittig zwischen beiden, s. Vorbild-Rechnung
    (:745-763) fuer die volle Begruendung -- hier nicht wiederholt, um den
    Test knapp zu halten.
    """
    with _zaehlender_server(delay=1.5) as (server, zaehler):
        host, port = server.server_address
        provider = _dwd_ruesten(
            monkeypatch, dwd_module, DwdDirectProvider, host, port,
            timeout=10.0, fristen={"FETCH_DEADLINE_SECONDS": 2.1},
        )
        deadline_at = time.monotonic() + dwd_module.FETCH_DEADLINE_SECONDS
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._fetch_series(
                dwd_module.PARAMS[0], _ORT.latitude, _ORT.longitude,
                datetime.now(timezone.utc), deadline_at,
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
        "bedeutet: jeder `_request`-Aufruf hat eine frische volle Frist "
        "bekommen, statt der Restzeit -- das Zeitbudget waere damit wieder "
        "nur eine Pruefung ZWISCHEN den Abrufen."
    )


# ---------------------------------------------------------------------------
# AC-3 — Normalfall bleibt unveraendert (Pflicht-Gegenprobe)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
@pytest.mark.parametrize("fall", _BEIDE)
def test_dwd_normalfall_liefert_unveraendert_daten(monkeypatch, fall):
    """KONTROLLE (heute gruen, muss gruen bleiben).

    AC-3: Given ein normal, also sofort antwortender lokaler Server, When
    `_request` aufgerufen wird, Then liefert er unveraendert die Bytes der
    Antwort und bricht nicht vorzeitig ab (< 2,0s).

    Pflichtbestandteil laut Spec: ohne diese Gegenprobe waere ein Fix, der
    schlicht ALLES sofort abbricht, ebenfalls gruen. `TIMEOUT` und die
    Fristkonstanten bleiben hier absichtlich auf den Produktionswerten.
    """
    modul, klasse, _ = fall
    with _antwortender_server() as server:
        host, port = server.server_address
        monkeypatch.setattr(modul, "BASE_URL", f"http://{host}:{port}/")
        provider = klasse()
        start = time.monotonic()
        roh = provider._request(_dwd_url(modul))
        elapsed = time.monotonic() - start

    assert json.loads(roh)["hourly"]["time"], (
        "`_request` lieferte nicht die unveraenderten Bytes der Server-"
        f"Antwort zurueck: {roh[:120]!r}"
    )
    assert elapsed < 2.0, (
        f"Normalfall verzoegert ({elapsed:.2f}s) -- die Fristpruefung darf "
        "einen sofort antwortenden Server nicht ausbremsen."
    )


# ---------------------------------------------------------------------------
# AC-4 — der Dual-Fall: der Gewitterpfad haelt die GEWITTER-Frist
# ---------------------------------------------------------------------------


@pytest.mark.timeout(25)
def test_dwd_gewitterpfad_haelt_die_gewitterfrist_nicht_die_grundfrist(monkeypatch):
    """RED (muss heute scheitern).

    AC-4: Given `THUNDER_FETCH_DEADLINE_SECONDS` ist auf 0,45s gepatcht und
    `FETCH_DEADLINE_SECONDS` DEUTLICH GROESSER auf 5,0s, When
    `fetch_thunder_signals_named` gegen die haengende Gegenstelle laeuft, Then
    haelt die verstrichene Zeit die GEWITTER-Frist ein (< 0,9s), nicht die
    weitere Grundpfad-Grenze.

    Der Kern ist der KONTRAST der beiden Werte: patchte man beide auf
    denselben kleinen Wert, bliebe der gefaehrliche Fehler "still die falsche
    Frist" unbewacht. Faellt das Durchreichen von `deadline_at` an der
    Gewitter-Aufrufstelle weg (Mutations-Gegenprobe, Spec Test Plan), setzt
    der `before`-Hook seinen Vorgabewert aus `FETCH_DEADLINE_SECONDS` — die
    Zeit laeuft dann gegen 5,0s und dieser Waechter wird rot.

    Zusicherung ist die WANDUHR, kein Ausnahmetyp aus dem Fristabbruch:
    `_thunder_point` faengt jede Ausnahme seines `_request`-Aufrufs selbst ab
    (`dwd.py:392-397`). Gefangen wird hier ausschliesslich der
    VORBESTEHENDE Zaehlweg-Vertrag `ThunderSourceUnavailableError`
    (`dwd.py:508-511`) — schluege ein `ProviderRequestError` bis hierher
    durch, waere der fail-soft-Vertrag gebrochen und der Test rot (s.
    SPEC-ABWEICHUNG im Modul-Docstring).

    TRAGENDE Groessenwahl: `TIMEOUT` (2,0s) liegt ueber der Gewitterfrist
    (0,45s), damit ein verworfener Timeout-Deckel sichtbar wird, und weit
    unter der gepatchten Grundpfad-Frist (5,0s), damit der heutige Fehlschlag
    (5 Versuche x 2,0s ~ 10s) eine lesbare Assertion liefert statt eines
    Timeout-Kills. Untergrenze 0,2s als Positivkontrolle.
    """
    with _HangingServer() as server:
        provider = _dwd_ruesten(
            monkeypatch, dwd_module, DwdDirectProvider, server.host, server.port,
            timeout=2.0,
            fristen={
                "THUNDER_FETCH_DEADLINE_SECONDS": 0.45,
                "FETCH_DEADLINE_SECONDS": 5.0,
            },
        )
        start = time.monotonic()
        with pytest.raises(ThunderSourceUnavailableError):
            provider.fetch_thunder_signals_named(_ORT)
        elapsed = time.monotonic() - start

    assert 0.2 <= elapsed < 0.9, (
        f"fetch_thunder_signals_named() brauchte {elapsed:.2f}s -- die "
        "GEWITTER-Frist (0.45s) muss gelten, nicht die weitere Grundpfad-"
        "Frist (5.0s). Ein Wert um ~5.0s bedeutet: die Gewitter-Aufrufstelle "
        "reicht ihr deadline_at nicht durch und der before-Hook setzt "
        "FETCH_DEADLINE_SECONDS als Vorgabewert. Ein Wert um ~10s bedeutet: "
        "es gibt im _request ueberhaupt keine Frist."
    )


# ---------------------------------------------------------------------------
# AC-5 — derselbe Weg am einfachen Fall (ICON-EU, ein Budget)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(25)
def test_dwd_eu_gewitterpfad_haelt_seine_frist_und_bleibt_fail_soft(monkeypatch):
    """RED (muss heute scheitern).

    AC-5: Given `THUNDER_FETCH_DEADLINE_SECONDS` (ICON-EUs einziges Budget)
    ist auf 0,45s gepatcht, When `fetch_thunder_signals_named` gegen die
    haengende Gegenstelle laeuft, Then haelt die verstrichene Zeit diese Frist
    ein (< 0,9s) und der Aufruf liefert fail-soft eine unvollstaendige Reihe
    statt einer propagierten Ausnahme.

    Hier stimmt die AC-Formulierung woertlich: `dwd_eu.py` hat den
    Zaehlweg-Vertrag aus `dwd.py:508-511` nicht, der Rueckgabewert ist also
    tatsaechlich pruefbar. Zusicherung bleibt die Wanduhr plus dieser
    Rueckgabewert — nie ein Ausnahmetyp (`dwd_eu.py:359-363` faengt jede
    Ausnahme im `_thunder_point` ab).

    RED-Grund heute: `_request` kennt keine Frist; der erste `_thunder_point`
    laeuft seine fuenf Versuche x `TIMEOUT` (2,0s) ~ 10s durch, erst danach
    greift die Budgetpruefung ZWISCHEN den Aufrufen (`dwd_eu.py:408`).
    """
    with _HangingServer() as server:
        provider = _dwd_ruesten(
            monkeypatch, dwd_eu_module, DwdEuDirectProvider, server.host, server.port,
            timeout=2.0, fristen={"THUNDER_FETCH_DEADLINE_SECONDS": 0.45},
        )
        start = time.monotonic()
        ergebnis = provider.fetch_thunder_signals_named(_ORT)
        elapsed = time.monotonic() - start

    assert all(
        wert is None for reihe in ergebnis.values() for wert in reihe.values()
    ), (
        "Gegen eine nie antwortende Gegenstelle darf kein Wert entstehen, "
        f"fail-soft bleibt None (Spec AC-2): {ergebnis!r}"
    )
    # Positivkontrolle gegen das leere Ergebnis: `all(...)` oben ist auch fuer
    # eine LEERE Reihe wahr. Der erste Zeitschritt MUSS versucht worden sein
    # und steht dann als None in der Reihe -- das trennt "Budget griff nach
    # dem ersten Abruf" von "es lief gar kein Abruf".
    assert 1 in ergebnis["lpi"], (
        f"Der erste Zeitschritt fehlt ganz ({ergebnis['lpi']!r}) -- der "
        "Gewitterpfad darf nicht VOR dem ersten Abruf abbrechen."
    )
    assert len(ergebnis["lpi"]) < len(dwd_eu_module.FORECAST_HOURS), (
        f"Die Reihe ist vollstaendig ({len(ergebnis['lpi'])} Zeitschritte) -- "
        "bei erschoepftem Budget muss sie ABBRECHEN, also unvollstaendig sein."
    )
    assert 0.2 <= elapsed < 0.9, (
        f"fetch_thunder_signals_named() brauchte {elapsed:.2f}s -- die Frist "
        "(0.45s) muss INNERHALB des ersten Abrufs greifen. Ein Wert um ~10s "
        "bedeutet: gepruefft wird erst ZWISCHEN zwei Abrufen, der einzelne "
        "haengende Abruf laeuft seine volle Retry-Kette durch."
    )


# ---------------------------------------------------------------------------
# AC-6 — der Hook-Vorgabewert kommt aus der WEITEREN Frist
# ---------------------------------------------------------------------------


_HOOK_FAELLE = [
    # `dwd`: BEIDE Konstanten gepatcht, und zwar auf deutlich verschiedene
    # Werte -- nur so ist an der Wanduhr ablesbar, WELCHE gewirkt hat.
    pytest.param(
        dwd_module, DwdDirectProvider,
        {"FETCH_DEADLINE_SECONDS": 0.45, "THUNDER_FETCH_DEADLINE_SECONDS": 0.05},
        id="dwd",
    ),
    # `dwd_eu`: nur eine Konstante vorhanden, kein Kontrast moeglich.
    pytest.param(
        dwd_eu_module, DwdEuDirectProvider,
        {"THUNDER_FETCH_DEADLINE_SECONDS": 0.45},
        id="dwd_eu",
    ),
]


@pytest.mark.timeout(15)
@pytest.mark.parametrize("modul, klasse, fristen", _HOOK_FAELLE)
def test_hook_vorgabewert_ist_die_weitere_frist(monkeypatch, modul, klasse, fristen):
    """RED (muss heute scheitern).

    AC-6: Given `_request` wird OHNE `deadline_at` aufgerufen, When der
    geteilte `before`-Hook feuert, Then setzt er die Frist selbst aus der
    providereigenen `_fetch_deadline_seconds()`-Methode — und fuer
    `DwdDirectProvider` ist dieser Vorgabewert `FETCH_DEADLINE_SECONDS`
    (180s), nie `THUNDER_FETCH_DEADLINE_SECONDS` (150s).

    Nachweisform des "nie 150s" ist die UNTERGRENZE: im `dwd`-Fall ist die
    Gewitterkonstante auf 0,05s gepatcht, die Grundpfadkonstante auf 0,45s.
    Loest der Accessor die falsche Konstante auf, endet der Aufruf nach ~0,05s
    — neunfach unterhalb der 0,2s-Grenze, der Test wird rot. Im `dwd_eu`-Fall
    gibt es nur eine Konstante; dort ist dieselbe Untergrenze die
    Positivkontrolle "es ging ein echter Versuch hinaus".

    Warum das eine eigene AC ist: eine Absicherung, die man vergessen kann
    einzuschalten, ist im Ernstfall keine — und `_thunder_point` reicht heute
    an KEINER Stelle ein `deadline_at` durch.

    RED-Grund heute: `_request` liest die Konstanten ueberhaupt nicht, der
    Aufruf laeuft seine fuenf Versuche x 0,3s ~ 1,5s durch.
    """
    with _HangingServer() as server:
        provider = _dwd_ruesten(
            monkeypatch, modul, klasse, server.host, server.port,
            timeout=0.3, fristen=fristen,
        )
        url = _dwd_url(modul)
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._request(url)  # BEWUSST ohne deadline_at
        elapsed = time.monotonic() - start

    assert 0.2 <= elapsed < 0.9, (
        f"_request() OHNE deadline_at brauchte {elapsed:.2f}s -- erwartet ist "
        "die Frist 0.45s. Ein Wert um ~0.05s bedeutet: der Accessor liefert "
        "die GEWITTER-Frist als Vorgabewert statt der weiteren Grundpfad-"
        "Frist. Ein Wert um ~1.5s bedeutet: der before-Hook setzt gar keine "
        "Frist."
    )


# ---------------------------------------------------------------------------
# AC-7 — ein LAUFZEIT-Patch der Fristdauer wirkt (Accessor statt Closure)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
@pytest.mark.parametrize("fall", _BEIDE)
def test_laufzeit_patch_der_fristdauer_wirkt_dwd(monkeypatch, fall):
    """RED (muss heute scheitern).

    AC-7: Given die Fristkonstante des Moduls wird ZUR LAUFZEIT auf 0,05s
    gepatcht, When `_request` gegen einen ERREICHBAREN, nur langsamen Server
    (0,6s Antwortzeit) laeuft, Then gilt der gepatchte Wert und der Aufruf
    bricht ab, statt die Antwort abzuwarten (< 0,4s).

    Das ist der Test, der eine Closure-Bauform ausschliesst: friert der
    Baustein die Fristdauer beim Dekorieren ein, liefe der Patch ins Leere und
    der Aufruf kaeme nach 0,6s mit Daten zurueck. Der ERREICHBARE Server ist
    bewusst gewaehlt — gegen eine haengende Gegenstelle waere "bricht schnell
    ab" auch ohne wirksamen Patch erklaerbar.

    RED-Grund heute: `_request` liest die Konstante nicht, der Abruf gelingt
    nach 0,6s und wirft gar nichts ("DID NOT RAISE").
    """
    modul, klasse, frist = fall
    with _antwortender_server(delay=0.6) as server:
        host, port = server.server_address
        provider = _dwd_ruesten(
            monkeypatch, modul, klasse, host, port,
            timeout=30.0, fristen={frist: 0.05},
        )
        url = _dwd_url(modul)
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._request(url)
        elapsed = time.monotonic() - start

    assert elapsed < 0.4, (
        f"_request() brauchte {elapsed:.2f}s -- der zur Laufzeit auf 0.05s "
        "gepatchte Wert haette vor der 0.6s-Antwort des erreichbaren Servers "
        "greifen muessen. Ein Wert um ~0.6s bedeutet: die Fristdauer wurde "
        "nicht zur Aufrufzeit gelesen (Closure statt Accessor)."
    )


# ---------------------------------------------------------------------------
# AC-8 — kein geteiltes Retrying-Objekt zwischen ICON-D2 und ICON-EU
# ---------------------------------------------------------------------------


@pytest.mark.timeout(25)
def test_retry_konfiguration_ist_je_dwd_provider_unabhaengig(monkeypatch):
    """RED (muss heute scheitern).

    AC-8: Given der geteilte Baustein ist in beiden Providern verdrahtet, When
    die Retry-Konfiguration des EINEN veraendert wird (hier
    `DwdDirectProvider._request.retry.wait` auf spuerbare 3,0s), Then bleibt
    das Verhalten von `DwdEuDirectProvider._request` unveraendert.

    VERHALTENSBASIERT, und die Reihenfolge der Patches ist tragend: erst
    ICON-EU auf `wait_none()`, DANACH ICON-D2 auf `wait_fixed(3.0)`. Teilten
    sich beide ein `Retrying`, ueberschriebe der zweite Patch den ersten;
    Versuch 1 scheitert dann bei 0,3s (Frist 0,45s noch nicht erreicht, also
    kein Stop), es folgt die volle 3,0s-Pause und der Aufruf braucht ~3,3s.
    Der `is not`-Vergleich steht ERGAENZEND am Ende -- stuende er vorn,
    brauchte eine Mutation mit geteiltem Objekt den Test strukturell ab, bevor
    die Wirkung gemessen ist.

    RED-Grund heute: ohne Frist laufen fuenf volle Versuche x 0,3s ~ 1,5s.
    """
    with _HangingServer() as server:
        provider = _dwd_ruesten(
            monkeypatch, dwd_eu_module, DwdEuDirectProvider, server.host, server.port,
            timeout=0.3, fristen={"THUNDER_FETCH_DEADLINE_SECONDS": 0.45},
        )
        # Reihenfolge tragend: dieser Patch kommt NACH dem ICON-EU-Patch.
        monkeypatch.setattr(
            DwdDirectProvider._request.retry, "wait", tenacity.wait_fixed(3.0)
        )
        url = _dwd_url(dwd_eu_module)
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._request(url)
        elapsed = time.monotonic() - start

    assert elapsed < 1.0, (
        f"ICON-EUs _request brauchte {elapsed:.2f}s, obwohl nur die "
        "Wartepause von ICON-D2 auf 3.0s gesetzt wurde -- die "
        "Retry-Konfiguration wirkt offenbar providerUEBERGREIFEND. Ein Wert "
        "um ~1.5s bedeutet dagegen: es gibt noch gar keine Frist."
    )
    assert (
        DwdDirectProvider._request.retry is not DwdEuDirectProvider._request.retry
    ), (
        "de_direct und eu_direct teilen sich EIN Retrying-Objekt -- eine "
        "Aenderung an der Retry-Konfiguration des einen wirkt damit still auf "
        "den anderen."
    )


# ---------------------------------------------------------------------------
# AC-9 — der bestehende Zaehl-Waechter wird im Normallauf ueberhaupt gesammelt
# ---------------------------------------------------------------------------


@pytest.mark.timeout(120)
def test_thunder_zeitbudget_waechter_laeuft_im_normallauf_mit():
    """RED (muss heute scheitern).

    AC-9: Given `tests/tdd/test_dwd_eu_thunder_time_budget.py` traegt keinen
    `live`/`email`/`staging`-Marker mehr, When ein normaler
    `pytest --collect-only`-Lauf MIT den Vorgabe-`addopts`
    (`pyproject.toml:65`, inkl. `-m 'not email and not live and not staging'`)
    laeuft, Then sammelt er die vorhandenen Tests (N > 0).

    Der Unterprozess ist der Kern der Beweisform: nur ein Lauf mit den echten
    `addopts` sieht den Marker-Filter, den ein `-m ''`-Override im Elternlauf
    ausschaltet. Pruefling und Arbeitsverzeichnis werden RELATIV ZU DIESER
    DATEI aufgeloest, damit der Test im Worktree nicht versehentlich den
    Hauptcheckout vermisst.

    RED-Grund heute: `pytestmark = pytest.mark.live` (`:31`) laesst den Lauf
    mit "no tests collected (2 deselected)" enden — der Waechter ist im
    Normallauf unsichtbar.
    """
    ziel = Path(__file__).resolve().parent / "test_dwd_eu_thunder_time_budget.py"
    wurzel = Path(__file__).resolve().parents[2]
    lauf = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", str(ziel)],
        cwd=str(wurzel), capture_output=True, text=True, timeout=100,
    )
    gesammelt = lauf.stdout.count("::")

    assert gesammelt > 0, (
        f"--collect-only sammelte {gesammelt} Tests aus {ziel.name} "
        f"(Exit {lauf.returncode}). Ein Waechter, den der Normallauf "
        "verwirft, bewacht nichts.\n--- stdout ---\n"
        f"{lauf.stdout[-800:]}\n--- stderr ---\n{lauf.stderr[-400:]}"
    )


# ===========================================================================
# Scheibe C (#2302) — geosphere.py (AROME/NWP + SNOWGRID)
# ===========================================================================

_GEO_LAT, _GEO_LON = 46.40, 12.52  # innerhalb SNOWGRID_BOUNDS (Alpen)


def _geo_ruesten(monkeypatch, host, port, *, timeout, frist, wait=None):
    """BASE_URL auf den lokalen Server, `TIMEOUT` und `FETCH_DEADLINE_SECONDS`
    patchen. `wait` bleibt UNVERAENDERT (Produktions-`wait_exponential`),
    wenn nicht EXPLIZIT uebergeben -- dieser Helfer darf die Wartepause NIE
    implizit neutralisieren (F-ADV1-Lehre aus Scheibe B, Spec-Vorgabe fuer
    Scheibe C). `FETCH_DEADLINE_SECONDS` existiert im heutigen Modul noch
    nicht, darum `raising=False`. `TIMEOUT` wird VOR dem Erzeugen des
    Providers gepatcht, der Client uebernimmt ihn als Konstruktor-Default.
    """
    monkeypatch.setattr(geosphere_module, "BASE_URL", f"http://{host}:{port}")
    monkeypatch.setattr(geosphere_module, "TIMEOUT", timeout)
    monkeypatch.setattr(
        geosphere_module, "FETCH_DEADLINE_SECONDS", frist, raising=False
    )
    if wait is not None:
        monkeypatch.setattr(GeoSphereProvider._request.retry, "wait", wait)
    return GeoSphereProvider()


def _minimaler_nwp_body() -> bytes:
    """Minimales, aber gueltiges GeoJSON: `timestamps` + `t2m.data`, damit
    `_parse_nwp_response` mindestens einen Datenpunkt liefert (Spec Test
    Plan, Zwei-Pfad-Testserver)."""
    jetzt = datetime.now(timezone.utc)
    ts = [(jetzt + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M+00:00") for h in range(1, 4)]
    body = {
        "timestamps": ts,
        "features": [{"properties": {"parameters": {"t2m": {"data": [10.0, 10.5, 11.0]}}}}],
    }
    return json.dumps(body).encode("utf-8")


def _geo_zwei_pfad_handler(nwp_body: bytes, nwp_delay: float):
    """EIN Handler fuer beide GeoSphere-Endpunkte, unterschieden ueber den
    Datensatz-Teilstring in `self.path` (Spec Test Plan). Der SNOWGRID-Pfad
    haengt (30s Schlaf -- laenger als jede hier gemessene Frist), der
    NWP-Pfad antwortet nach `nwp_delay` mit gueltigem GeoJSON."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server API)
            if "nwp-v1-1h-2500m" in self.path:
                if nwp_delay:
                    time.sleep(nwp_delay)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(nwp_body)))
                self.end_headers()
                self.wfile.write(nwp_body)
            elif "snowgrid_cl-v2-1d-1km" in self.path:
                time.sleep(30)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):  # Ruhe im pytest-Output
            pass

    return _Handler


@contextmanager
def _geo_server(nwp_delay: float = 0.6):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), _geo_zwei_pfad_handler(_minimaler_nwp_body(), nwp_delay)
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _snowgrid_journal_zeilen() -> list:
    """Lokale Kopie des Journal-Lesers (Testplumbing, kein geteilter
    Prueflingsbaustein), Muster `test_snowgrid_enrichment_health.py`."""
    from app.loader import get_data_root

    pfad = get_data_root().joinpath("diagnostics", "enrichment_calls.jsonl")
    if not pfad.is_file():
        return []
    zeilen = [json.loads(z) for z in pfad.read_text().splitlines() if z.strip()]
    return [z for z in zeilen if z.get("path") == "snowgrid"]


def _snowgrid_unavailable_vorhanden() -> bool:
    return any(z.get("outcome") == "unavailable" for z in _snowgrid_journal_zeilen())


# ---------------------------------------------------------------------------
# AC-1 — Grundpfad-`_request` bricht an der Frist ab
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
def test_geosphere_grundpfad_bricht_bei_haengender_gegenstelle_ab(monkeypatch):
    """RED (muss heute scheitern -- als Timeout-Kill, s.u.).

    AC-1: Given `_request` laeuft direkt gegen `_HangingServer`,
    `FETCH_DEADLINE_SECONDS` auf 0,45s gepatcht, `TIMEOUT` auf 5,0s (DEUTLICH
    OBERHALB der Frist -- nur so misst der Test den Timeout-DECKEL mit),
    When `_request(endpoint, lat, lon, parameters)` OHNE `deadline_at`
    laeuft, Then bricht der Aufruf mit `(ProviderRequestError,
    httpx.HTTPError)` ab, Wanduhr < 0,9s.

    KEIN Ueberschreiben von `.retry.stop`: der Produktionsausdruck
    `stop_after_attempt(RETRY_ATTEMPTS) | stop_at_deadline` bleibt VOLLSTAENDIG
    verdrahtet -- ein `stop_after_attempt(1)`-Patch wuerde denselben Ausdruck
    ERSETZEN, also auch `| stop_at_deadline` entfernen, und damit dieselbe
    Mutationsfamilie unbewacht lassen, die F-ADV1 in Scheibe B aufgedeckt
    hat (Adversary-Korrektur, s. Modul-Docstring Scheibe C).

    RED-Grund heute: `_request` kennt keine Frist, `stop_after_attempt(5)`
    ist die einzige Stop-Bedingung -- gegen die haengende Gegenstelle laeuft
    das volle 5-Versuche-Backoff (~5x5,0s TIMEOUT + Produktions-Wartepausen,
    Groessenordnung 40s+) weit ueber die hier gesetzte
    `@pytest.mark.timeout(15)` hinaus. Der Test wird dadurch als
    Timeout-Kill rot, nicht als lesbare Assertion -- bewusst in Kauf
    genommen (PO-Korrektur K1), weil nur so die volle Produktions-`stop`-
    Komposition gemessen wird. Nach GREEN liegt `elapsed` bei ~0,45s und die
    Assertion unten greift normal.
    """
    with _HangingServer() as server:
        provider = _geo_ruesten(monkeypatch, server.host, server.port, timeout=5.0, frist=0.45)
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._request(
                geosphere_module.ENDPOINTS["nwp"], _GEO_LAT, _GEO_LON,
                geosphere_module.NWP_PARAMS,
            )
        elapsed = time.monotonic() - start

    assert 0.2 <= elapsed < 0.9, (
        f"_request() brauchte {elapsed:.2f}s -- die Frist (0.45s) muss den "
        "Einzelversuch deckeln. Ein Wert um ~5.0s bedeutet: der gedeckelte "
        "Timeout wird nicht an den httpx-Client durchgereicht."
    )


# ---------------------------------------------------------------------------
# AC-2 — die Frist deckelt AUCH die Retry-Wartepausen (F-ADV1-Klasse)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
def test_geosphere_frist_deckelt_auch_die_retry_wartepausen(monkeypatch):
    """RED (muss heute scheitern). Mutations-relevanter Waechter
    (F-ADV1-Klasse) -- `wait` wird EXPLIZIT IM TEST gepatcht, nicht im
    Ruest-Helfer.

    AC-2: Given `TIMEOUT` 0,5s, `FETCH_DEADLINE_SECONDS` 0,45s, `wait`
    EXPLIZIT auf `wait_fixed(1.0)`, When `_request` gegen `_HangingServer`
    laeuft, Then liegt die verstrichene Zeit zwischen 0,2 und unter 0,9s --
    die Wartepause selbst wird von der Frist gedeckelt, nicht nur die
    HTTP-Versuche.

    RED-Grund heute: ohne `stop_at_deadline` laufen bis zu 5 Versuche x 0,5s
    TIMEOUT plus 4 volle 1,0s-Wartepausen durch (~6,5s).
    """
    with _HangingServer() as server:
        provider = _geo_ruesten(
            monkeypatch, server.host, server.port, timeout=0.5, frist=0.45,
            wait=tenacity.wait_fixed(1.0),
        )
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._request(
                geosphere_module.ENDPOINTS["nwp"], _GEO_LAT, _GEO_LON,
                geosphere_module.NWP_PARAMS,
            )
        elapsed = time.monotonic() - start

    assert 0.2 <= elapsed < 0.9, (
        f"_request() brauchte {elapsed:.2f}s -- die Frist (0.45s) muss die "
        "Kette aus Versuchen UND Wartepausen (1.0s je Pause) gemeinsam "
        "deckeln. Ein Wert um ~6.5s bedeutet: `stop_at_deadline` fehlt."
    )


# ---------------------------------------------------------------------------
# AC-3 — `fetch_combined` haelt die gemeinsame Serienfrist (Mutations-Pflicht)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(90)
def test_geosphere_fetch_combined_haelt_die_gemeinsame_serienfrist(monkeypatch):
    """RED (muss heute scheitern). Mutations-Pflicht-Waechter (Spec Test
    Plan): korrekt ~1,0-1,1s, Mutation "deadline_at nicht an SNOWGRID
    durchgereicht" ~1,6s, Mutation "stop_at_deadline entfernt" ~3s.

    AC-3: Given `fetch_combined(lat, lon, include_cloud_layers=False)` laeuft
    gegen den Zwei-Pfad-Server (NWP antwortet nach 0,6s, SNOWGRID haengt),
    `FETCH_DEADLINE_SECONDS` 1,0s, `TIMEOUT` 10,0s, `wait` EXPLIZIT auf
    `wait_fixed(1.0)` (wie AC-2 -- NICHT neutralisiert), When der Aufruf
    durchlaeuft, Then liegt die GESAMTE Wanduhrzeit unter 1,35s, `ts.data`
    ist nicht leer, alle Datenpunkte tragen `snow_depth_cm is None`, und das
    Journal enthaelt einen `snowgrid`/`unavailable`-Eintrag.

    RED-Grund heute: ohne Frist laeuft der SNOWGRID-Abruf seine volle
    Retry-Kette (bis zu 5 Versuche x TIMEOUT=10s + 4 x 1,0s Wartepause,
    ~54s) durch, bevor der bestehende `except Exception`-Fang in
    `fetch_combined` (`geosphere.py:622-631`) greift -- weit jenseits 1,35s.
    """
    with _geo_server(nwp_delay=0.6) as server:
        host, port = server.server_address
        provider = _geo_ruesten(
            monkeypatch, host, port, timeout=10.0, frist=1.0,
            wait=tenacity.wait_fixed(1.0),
        )
        start = time.monotonic()
        ts = provider.fetch_combined(_GEO_LAT, _GEO_LON, include_cloud_layers=False)
        elapsed = time.monotonic() - start

    assert ts.data, (
        "fetch_combined() lieferte keine Datenpunkte -- der NWP-Abruf muss "
        "gelingen, sonst wird der SNOWGRID-Pfad gar nicht erst versucht "
        "(geosphere.py:621)."
    )
    assert all(dp.snow_depth_cm is None for dp in ts.data), (
        "Datenpunkte tragen eine Schneehoehe -- SNOWGRID haette an der "
        "haengenden Gegenstelle abbrechen muessen."
    )
    assert _snowgrid_unavailable_vorhanden(), (
        "Kein Journal-Eintrag path='snowgrid' outcome='unavailable' -- ohne "
        "Frist bricht der SNOWGRID-Pfad heute nicht rechtzeitig ab, um in "
        "den bestehenden except-Zweig zu laufen."
    )
    assert elapsed < 1.35, (
        f"fetch_combined() brauchte {elapsed:.2f}s -- die GEMEINSAME Frist "
        "(1.0s) muss NWP- und SNOWGRID-Abruf zusammen deckeln. Werte um "
        "~1.6s/~3s deuten auf die in der Spec benannten Mutationen hin."
    )


# ---------------------------------------------------------------------------
# AC-4 — der NWP-Pfad bricht ab statt ein leeres Ergebnis zu liefern (D2)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
def test_geosphere_fetch_combined_nwp_frist_bricht_ab_ohne_leeres_ergebnis(monkeypatch):
    """RED (muss heute scheitern -- als Timeout-Kill, s.u.).

    AC-4: Given `FETCH_DEADLINE_SECONDS` 0,45s, der Server fuer den
    NWP-Endpunkt ist ein `_HangingServer`, When `fetch_combined` aufgerufen
    wird -- derselbe Pfad wie `at_direct` (`regional_stubs.py:88-95`) --,
    Then wirft der Aufruf `(ProviderRequestError, httpx.HTTPError)`, liefert
    KEIN leeres/unvollstaendiges Ergebnis, Wanduhr < 0,9s. Bewusst
    `fetch_combined`, nicht `fetch_forecast` (uebersetzt jeden httpx-Fehler
    und zeigte den Ausnahmetyp der Frist allein nicht mehr).

    KEIN Ueberschreiben von `.retry.stop` (PO-Korrektur K1, s.
    AC-1-Begruendung): ein `stop_after_attempt(1)`-Patch wuerde
    `| stop_at_deadline` aus dem Produktionsausdruck entfernen und damit
    genau die Mutationsfamilie unbewacht lassen, die dieser Test eigentlich
    absichern soll.

    RED-Grund heute: ohne Frist laeuft das volle 5-Versuche-Backoff gegen
    die haengende Gegenstelle (Groessenordnung 40s+), weit ueber
    `@pytest.mark.timeout(15)` -- der Test wird als Timeout-Kill rot. Nach
    GREEN liegt `elapsed` bei ~0,45s.
    """
    with _HangingServer() as server:
        provider = _geo_ruesten(monkeypatch, server.host, server.port, timeout=5.0, frist=0.45)
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider.fetch_combined(_GEO_LAT, _GEO_LON, include_cloud_layers=False)
        elapsed = time.monotonic() - start

    assert 0.2 <= elapsed < 0.9, (
        f"fetch_combined() brauchte {elapsed:.2f}s -- erwartet < 0.9s. Ein "
        "Wert um ~5.0s bedeutet: der NWP-Abruf ist nicht auf die Frist "
        "gedeckelt."
    )


# ---------------------------------------------------------------------------
# AC-5 — Normalfall bleibt unveraendert (Pflicht-Gegenprobe, KONTROLLE)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(10)
def test_geosphere_normalfall_liefert_unveraendert_daten(monkeypatch):
    """KONTROLLE (heute gruen, muss gruen bleiben) -- Pflicht-Gegenprobe.

    AC-5: Given ein normal (sofort) antwortender lokaler GeoJSON-Server,
    Standardfrist unveraendert (kein Patch von `FETCH_DEADLINE_SECONDS`),
    When `fetch_nwp_forecast` aufgerufen wird, Then liefert er unveraendert
    Daten, bricht nicht vorzeitig ab, Wanduhr < 2,0s.

    Ohne diese AC waere ein Fix, der ALLES sofort abbricht, ebenfalls gruen.
    """
    with _geo_server(nwp_delay=0.0) as server:
        host, port = server.server_address
        monkeypatch.setattr(geosphere_module, "BASE_URL", f"http://{host}:{port}")
        provider = GeoSphereProvider()
        start = time.monotonic()
        ts = provider.fetch_nwp_forecast(_GEO_LAT, _GEO_LON)
        elapsed = time.monotonic() - start

    assert ts.data, "fetch_nwp_forecast() lieferte keine Datenpunkte."
    assert elapsed < 2.0, (
        f"Normalfall verzoegert ({elapsed:.2f}s) -- die Fristpruefung darf "
        "einen sofort antwortenden Server nicht ausbremsen."
    )


# ---------------------------------------------------------------------------
# AC-6 — der Hook-Vorgabewert kommt aus `_fetch_deadline_seconds()`
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
def test_geosphere_hook_vorgabewert_ist_die_weitere_frist(monkeypatch):
    """RED (muss heute scheitern).

    AC-6: Given `_request` OHNE `deadline_at` aufgerufen wird,
    `FETCH_DEADLINE_SECONDS` zur LAUFZEIT auf einen sehr kleinen Wert
    gepatcht, When der geteilte `before`-Hook feuert, Then setzt er die
    Frist selbst aus `_fetch_deadline_seconds()` -- der gepatchte Wert wirkt
    SOFORT. Zusaetzlich gilt im unveraenderten Modul:
    `FETCH_DEADLINE_SECONDS == 180.0`.

    `stop_after_attempt(1)` bleibt hier EXPLIZIT gesetzt (PO-Korrektur K1
    erlaubt das ausdruecklich fuer AC-6): dieser Test bewacht NICHT die
    `stop`-Komposition (das tun AC-1/AC-2/AC-3/AC-4), sondern ausschliesslich
    WELCHEN Wert der `before`-Hook als `deadline_at` einsetzt, wenn keiner
    uebergeben wurde. Diese Zusicherung ist nach dem ERSTEN Versuch bereits
    vollstaendig geprueft (der Versuch faellt entweder bei ~0,05s oder bei
    TIMEOUT); ein zweiter, dritter... Versuch mit vollem Produktions-Backoff
    liefe nur denselben Beweis nochmal, kostete aber ~40s RED-Laufzeit ohne
    zusaetzliche Mutations-Abdeckung. Ruehrt NICHT an `wait`.

    RED-Grund heute (Wertpruefung): die Konstante existiert im Modul noch
    gar nicht -- `AttributeError` statt 180.0.
    RED-Grund heute (Hang-Teil): ohne Frist-Auswertung laeuft der eine
    Versuch bis TIMEOUT (2,0s) statt bei ~0,05s abzubrechen.
    """
    assert geosphere_module.FETCH_DEADLINE_SECONDS == 180.0, (
        "Modul-Konstante FETCH_DEADLINE_SECONDS fehlt oder weicht vom "
        "dokumentierten Vorgabewert (180.0s) ab."
    )
    with _HangingServer() as server:
        provider = _geo_ruesten(monkeypatch, server.host, server.port, timeout=2.0, frist=0.05)
        monkeypatch.setattr(
            GeoSphereProvider._request.retry, "stop", tenacity.stop_after_attempt(1)
        )
        start = time.monotonic()
        with pytest.raises(_ABBRUCH):
            provider._request(
                geosphere_module.ENDPOINTS["nwp"], _GEO_LAT, _GEO_LON,
                geosphere_module.NWP_PARAMS,
            )  # BEWUSST ohne deadline_at
        elapsed = time.monotonic() - start

    assert elapsed < 0.9, (
        f"_request() OHNE deadline_at brauchte {elapsed:.2f}s -- erwartet "
        "ist die gepatchte Frist (0.05s). Ein Wert um ~2.0s bedeutet: der "
        "before-Hook setzt gar keine Frist."
    )


# ---------------------------------------------------------------------------
# AC-7 — `fetch_snowgrid` bleibt fail-soft und journalisiert den Frist-Fehler
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
def test_geosphere_fetch_snowgrid_bleibt_fail_soft_und_journalisiert(monkeypatch):
    """RED (muss heute scheitern -- am Journal-`detail`, NICHT an der
    Wanduhr; PO-Korrektur K2).

    AC-7 (freigegebener Wortlaut, KEINE Wanduhr-Schwelle darin): Given
    `fetch_snowgrid` direkt aufgerufen wird (Pfad, den
    `openmeteo._enrich_snow` nutzt), `FETCH_DEADLINE_SECONDS` 0,45s, der
    SNOWGRID-Endpunkt haengt, When der Aufruf durchlaeuft, Then liefert
    `fetch_snowgrid` `(None, None)` ohne Ausnahme, und das Journal traegt
    einen `snowgrid`/`unavailable`-Eintrag.

    TIMEOUT (0,2s) liegt bewusst UNTER der Frist (0,45s) -- Gegenteil von
    AC-1/AC-4/AC-6. Grund (am Code verifiziert, `providers/http.py:73-108`
    und `tenacity/__init__.py:359-401,374-436`):
    1. Versuch 1 scheitert nach ~0,2s an `TIMEOUT` (ReadTimeout, retryable).
    2. `_run_wait` berechnet die Pause (hier `wait_fixed(1.0)`, EXPLIZIT
       gesetzt -- kein Ruest-Default), `_run_stop` prueft DANACH, ob
       abgebrochen wird: bei t~0,2s ist weder `stop_after_attempt(5)` noch
       `stop_at_deadline` (Frist bei t=0,45s) erfuellt -- also wird
       geschlafen (1,0s), t liegt danach bei ~1,2s, ueber der Frist.
    3. Versuch 2: der Kopf-Check `capped_timeout_or_raise` (im
       Funktionskoerper von `_request`, VOR dem HTTP-Aufruf) sieht eine
       NEGATIVE Restzeit und wirft `ProviderRequestError` -- BEVOR ueberhaupt
       ein zweiter HTTP-Versuch hinausgeht.
    4. `_is_retryable_error(ProviderRequestError)` ist `False` ->
       `retry_if_exception` liefert `False` -> tenacity ruft laut
       `_post_retry_check_actions:398-401` sofort `rs.outcome.result()` auf
       und reraised den `ProviderRequestError` UNGEDROSSELT (kein
       `RetryError`-Wrapper, `wait`/`stop` werden fuer diesen Versuch gar
       nicht mehr ausgewertet).
    Damit dieser `ProviderRequestError` `fetch_snowgrid` NICHT verlaesst,
    braucht `fetch_snowgrid` den in der Spec geforderten zusaetzlichen
    Fang von `ProviderRequestError` (Implementation Details, Punkt
    "fetch_snowgrid ... faengt zusaetzlich ProviderRequestError").

    RED-Grund heute: dieser zusaetzliche Fang fehlt NICHT direkt sichtbar,
    denn `fetch_snowgrid` faengt schon heute `httpx.TimeoutException` (der
    `ReadTimeout` aus dem HEUTIGEN, frist-losen Code, der alle 5 Versuche
    durchlaeuft) -- der Test bleibt also FUNKTIONAL gruen ((None,None) +
    ein Journal-Eintrag entsteht so oder so). Die einzige Stelle, an der
    heute UND nach GREEN unterschiedliches Verhalten sichtbar wird, ist der
    Inhalt von `detail`: heute traegt er den rohen `ReadTimeout`-Text, nach
    GREEN die `ProviderRequestError`-Meldung aus `capped_timeout_or_raise`
    ("Zeitbudget (...) vor diesem Versuch bereits aufgebraucht",
    `http.py:104-106`, verpackt in `[geosphere] ...` durch
    `ProviderError.__init__`, `base.py:135`). Die `detail`-Assertion unten
    ist damit der einzige Beleg, dass der NEUE Fangzweig griff -- eine
    Mutation "`fetch_snowgrid` faengt `ProviderRequestError` nicht" laesst
    den `ProviderRequestError` bis zu diesem Test durchschlagen und macht
    ihn dadurch rot (keine Wanduhr-Schwelle noetig).
    """
    with _HangingServer() as server:
        provider = _geo_ruesten(
            monkeypatch, server.host, server.port, timeout=0.2, frist=0.45,
            wait=tenacity.wait_fixed(1.0),
        )
        ergebnis = provider.fetch_snowgrid(_GEO_LAT, _GEO_LON)

    assert ergebnis == (None, None), (
        f"fetch_snowgrid() muss fail-soft (None, None) liefern, bekommen "
        f"{ergebnis!r}."
    )
    zeilen = _snowgrid_journal_zeilen()
    assert zeilen, "Kein Journal-Eintrag path='snowgrid'."
    zeile = zeilen[-1]
    assert zeile.get("outcome") == "unavailable", (
        f"Erwartet outcome='unavailable', bekommen {zeile.get('outcome')!r}."
    )
    assert "Zeitbudget" in (zeile.get("detail") or ""), (
        f"detail enthaelt nicht 'Zeitbudget' (bekommen: {zeile.get('detail')!r}) "
        "-- das ist die Meldung von capped_timeout_or_raise() und der Beleg, "
        "dass der NEUE ProviderRequestError-Fangzweig griff, nicht der "
        "bestehende httpx.TimeoutException-Fang."
    )
