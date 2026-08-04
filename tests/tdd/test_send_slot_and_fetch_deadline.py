"""RED — Fix #1448 Scheibe S3: Telegram-Drosselbremse und open-meteo
bekommen eine Obergrenze.

Spec: docs/specs/modules/fix_1448_s3_telegram_openmeteo.md (AC-1..AC-6)
Kontext: docs/context/fix-1448-s3-telegram-openmeteo.md

Zwei unabhaengige Mechanismen, ein Testmodul (Vorbild: die gebuendelte
Zeitgrenzen-Testdatei aus Scheibe S1, tests/tdd/test_mail_send_deadline.py):

- Telegram (A): `TelegramOutput._reserve_send_slot()` (`telegram.py:210-250`)
  wartet heute unbegrenzt, wenn die Drossel-Buchfuehrung voll ist. Reine
  In-Memory-Buchfuehrung -- KEIN Netz, KEIN Live-Versand (Test-Politik).
  Die prozessweite Buchfuehrung (`TelegramOutput._rate_limit_stamps`,
  Klassenattribut) wird bereits von einer GLOBALEN autouse-Fixture
  (`tests/conftest.py:221-232`, `_reset_telegram_rate_limit`) vor UND nach
  JEDEM Testfall im gesamten Suite-Lauf geleert -- ein lokaler Reset-Helfer
  in dieser Datei waere redundant und wurde bewusst NICHT gebaut.
- open-meteo (B): `OpenMeteoProvider.fetch_forecast()`/`_request()`
  (`openmeteo.py:512-552`, `:787-1052`) haben kein Gesamt-Zeitbudget. Echte
  lokale HTTP-/TCP-Server (Vorbild `test_meteofrance_direct_fallback.py:
  476-517` und `test_issue_1115_model_fallback.py`), kein Mock, kein
  Mock-Theater.

Fuer die beiden noch nicht existierenden Konstanten
(`SEND_SLOT_MAX_WAIT_SECONDS`, `FETCH_DEADLINE_SECONDS`) wird
`monkeypatch.setattr(..., raising=False)` verwendet, damit die Tests HEUTE
am tatsaechlichen (Nicht-)Verhalten scheitern statt an einem AttributeError.

Team-Lead-Korrektur (2026-08-01, nach erster RED-Runde): der urspruengliche
AC-6-Test rief `_request(..., deadline_at=...)` explizit auf und war dadurch
NUR wegen des fehlenden Parameters rot (TypeError) -- das beweist nichts
ueber echtes Haenge-Verhalten. AC-6 hat jetzt ZWEI Tests: der zeitbasierte
(`test_single_hanging_request_aborts_within_deadline_without_candidate_switch`)
ruft `_request()` OHNE `deadline_at` auf und ist der eigentliche
AC-6-Nachweis -- rot, weil die Laufzeit heute weit ueber
`FETCH_DEADLINE_SECONDS` liegt (kein "DID NOT RAISE", ausschliesslich die
gemessene Zeit). Der ergaenzende
`test_request_explicit_deadline_at_overrides_default_fetch_deadline` prueft
zusaetzlich, dass ein explizit uebergebenes `deadline_at` den aus
`FETCH_DEADLINE_SECONDS` abgeleiteten Default UEBERSTIMMT (Grundlage fuer
AC-3: `fetch_forecast()` reicht EIN gemeinsames `deadline_at` ueber die
gesamte Kandidaten-Schleife weiter) -- dieser bleibt heute aus
Signatur-Gruenden (TypeError) rot und ERSETZT den zeitbasierten Test nicht.
Implikation fuer die Implementierung (Team-Lead-Vorgabe, staerker als der
Spec-Wortlaut "Default None erhaelt das bestehende Verhalten fuer alle
anderen Aufrufer"): `_request()` muss bei `deadline_at=None` intern
`time.monotonic() + FETCH_DEADLINE_SECONDS` als Ersatzwert bilden, statt bei
fehlendem Parameter unbegrenzt weiterzulaufen -- sonst haengt der gesamte
Schutz daran, dass JEDE Aufrufstelle (`_fetch_uv_data`,
`probe_model_availability`, WEATHER-05b-Fallback) den Parameter auch
tatsaechlich durchreicht, und genau solche Luecken haben S1/S2 je einen
Befund gekostet.

AC-Test-Mapping (Pflicht, aus Spec):
| AC   | Testfunktion                                                          | Heute |
|------|------------------------------------------------------------------------|-------|
| AC-1 | test_reserve_send_slot_raises_output_error_after_max_wait              | RED   |
| AC-2 | test_reserve_send_slot_logs_chat_key_and_waited_time_on_timeout        | RED   |
| AC-3 | test_fetch_forecast_raises_provider_request_error_after_deadline       | RED   |
| AC-4 | test_normal_case_unaffected_by_new_deadlines                           | GRUEN |
| AC-5 | test_429_retry_skips_new_slot_reservation_and_stays_capped             | GRUEN |
| AC-6 | test_single_hanging_request_aborts_within_deadline_without_candidate_switch (primaer) | RED |
| AC-6 | test_request_explicit_deadline_at_overrides_default_fetch_deadline (ergaenzend) | RED |
"""
from __future__ import annotations

import json
import logging
import socket
import threading
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import tenacity

import output.channels.telegram as tg_module
import providers.openmeteo as om_module
from app.config import Location, Settings
from output.channels.base import OutputError
from output.channels.telegram import TelegramOutput
from providers.base import ProviderRequestError
from providers.openmeteo import OpenMeteoProvider

# Live-Schicht (Test-Politik, CLAUDE.md): braucht echtes Netz/echte Dienste --
# lief im Kern nie gruen (CI-Vermessung 2026-08-04, #1196) und gehoert per
# Marker in den /e2e-verify-Lauf, nicht auf eine Ausnahmeliste.
pytestmark = pytest.mark.live

_SUEDBADEN = Location(latitude=48.0, longitude=7.0, name="Suedbaden")
# AC-3 braucht MEHRERE Open-Meteo-Kandidaten, aber AUSSERHALB der
# AT/DE/FR-Rechtecke aus `region_routing.py` -- sonst greift bei
# vollstaendigem Ausfall aller Kandidaten die Cross-Provider-Weiche (#1141)
# und ruft einen ECHTEN Direktprovider (z. B. DWD) auf, den der
# Egress-Guard fuer diesen Test zu Recht blockt (Verwechslungsgefahr mit
# einem echten Fund). Nordschweden liegt in metno_nordic/icon_eu/ecmwf,
# aber in keiner der drei Regionen.
_NORDSCHWEDEN = Location(latitude=65.0, longitude=20.0, name="Nordschweden")
_ALL_MODEL_IDS = (
    "meteofrance_arome", "icon_d2", "metno_nordic", "icon_eu", "ecmwf_ifs04",
)


# ---------------------------------------------------------------------------
# Telegram-Helfer (kein Netz)
# ---------------------------------------------------------------------------


def _settings(chat_id: str, **overrides) -> Settings:
    return Settings(
        telegram_bot_token="stub-bot-token", telegram_chat_id=chat_id,
        telegram_test_chat_id="", is_test_mode=False,
        **overrides, _env_file=None,
    )


def _chat(tag: str) -> str:
    """Eigene Chat-ID je Test -- auch wenn die globale Fixture die
    Buchfuehrung schon zwischen Tests leert, schuetzt das zusaetzlich gegen
    Verwechslung innerhalb desselben Testlaufs."""
    return f"9{abs(hash((tag, time.monotonic_ns()))) % 10**8:08d}"


def _fill_window(chat_key: str, count: int) -> None:
    """Seed die Klassen-Buchfuehrung DIREKT mit `count` frischen
    Zeitstempeln -- reine In-Memory-Manipulation, kein `httpx.post` noetig,
    da die Bremse ausschliesslich die eigene Buchfuehrung zaehlt."""
    now = time.monotonic()
    TelegramOutput._rate_limit_stamps[chat_key] = [now] * count


# ---------------------------------------------------------------------------
# open-meteo-Helfer: echte lokale Server
# ---------------------------------------------------------------------------


class _HangingServer:
    """Echter lokaler TCP-Server: nimmt Verbindungen an, antwortet aber NIE.

    Vorbild: `tests/tdd/test_mail_send_deadline.py::_HangingServer` (#1448
    S1) -- httpx blockiert dadurch beim Warten auf die HTTP-Antwort
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
    """Minimale, aber gueltige rohe Open-Meteo-JSON-Antwort (`_parse_response`
    verlangt nur `hourly.time`, alle weiteren Felder sind optional)."""
    base = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    times = [(base + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(3)]
    return {"hourly": {"time": times, "temperature_2m": [10.0, 10.5, 11.0]}}


class _ImmediateOkHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (http.server API)
        payload = json.dumps(_valid_openmeteo_body()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # Ruhe im pytest-Output
        pass


@contextmanager
def _immediate_ok_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ImmediateOkHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _write_all_available_cache(path: Path) -> None:
    """Availability-Cache ohne fehlende Metriken -- unterdrueckt den
    WEATHER-05b-Metrik-Fallback-Block (ein zusaetzlicher `_request`), der
    sonst AC-4b verfaelschen wuerde. Vorbild:
    `test_issue_1115_model_fallback.py::_write_all_available_cache`."""
    path.write_text(json.dumps({
        "probe_date": date.today().isoformat(),
        "models": {mid: {"available": [], "unavailable": []} for mid in _ALL_MODEL_IDS},
    }))


class _Http429Server(ThreadingHTTPServer):
    def __init__(self, address, handler, retry_after: float):
        super().__init__(address, handler)
        self.retry_after = retry_after
        self.request_count = 0
        self._lock = threading.Lock()

    def record(self) -> None:
        with self._lock:
            self.request_count += 1


class _Http429Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self.server.record()
        body = json.dumps({
            "ok": False, "error_code": 429,
            "parameters": {"retry_after": self.server.retry_after},
        }).encode("utf-8")
        self.send_response(429)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@contextmanager
def _http_429_server(retry_after: float):
    server = _Http429Server(("127.0.0.1", 0), _Http429Handler, retry_after)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# AC-1 -- Telegram-Bremse bricht nach SEND_SLOT_MAX_WAIT_SECONDS ab
# ---------------------------------------------------------------------------


@pytest.mark.timeout(6)
def test_reserve_send_slot_raises_output_error_after_max_wait(monkeypatch):
    """AC-1: Given die Drossel-Buchfuehrung fuer einen Chat enthaelt bereits
    >= `telegram_rate_limit_max_per_window` Zeitstempel im aktuellen Fenster,
    sodass `_reserve_send_slot()` in die Warteschleife eintritt, UND
    `SEND_SLOT_MAX_WAIT_SECONDS` ist per Test auf Millisekunden geschrumpft,
    When `_reserve_send_slot(chat_key)` aufgerufen wird, Then kehrt der
    Aufruf spaetestens nach `SEND_SLOT_MAX_WAIT_SECONDS` mit `OutputError`
    zurueck, statt unbegrenzt weiter zu schlafen.

    Das Fenster (1.0s) ist bewusst deutlich groesser als die geschrumpfte
    Deadline (0.15s) -- der Test misst NICHT den Normalfall (Fenster laeuft
    irgendwann natuerlich ab), sondern ob die Deadline VOR diesem
    natuerlichen Ablauf zuschlaegt.

    RED-Grund heute: `SEND_SLOT_MAX_WAIT_SECONDS` existiert nur als per
    `monkeypatch` gesetztes Modulattribut -- `_reserve_send_slot()` liest es
    nicht. Die Schleife wartet den vollen Fensterablauf (~1.0s) ab und kehrt
    danach ERFOLGREICH (ohne Fehler) zurueck -> `pytest.raises(OutputError)`
    schlaegt mit "DID NOT RAISE" fehl.
    """
    chat_key = _chat("ac1")
    settings = _settings(
        chat_key,
        telegram_rate_limit_max_per_window=3,
        telegram_rate_limit_window_seconds=1.0,
    )
    monkeypatch.setattr(tg_module, "SEND_SLOT_MAX_WAIT_SECONDS", 0.15, raising=False)
    _fill_window(chat_key, 3)

    ausgang = TelegramOutput(settings)
    start = time.monotonic()
    with pytest.raises(OutputError):
        ausgang._reserve_send_slot(chat_key)
    elapsed = time.monotonic() - start

    assert elapsed < 0.6, (
        f"_reserve_send_slot() brauchte {elapsed:.2f}s bis zum Fehler -- "
        "SEND_SLOT_MAX_WAIT_SECONDS (0.15s) haette den Abbruch weit vor dem "
        "1.0s-Fensterablauf erzwingen muessen."
    )


# ---------------------------------------------------------------------------
# AC-2 -- Log-Zeile mit chat_key und gewarteter Zeit VOR dem Abbruch
# ---------------------------------------------------------------------------


@pytest.mark.timeout(6)
def test_reserve_send_slot_logs_chat_key_and_waited_time_on_timeout(monkeypatch, caplog):
    """AC-2: Given dieselbe Ausgangslage wie AC-1, When `_reserve_send_slot()`
    die Frist ueberschreitet und abbricht, Then erscheint VORHER eine
    Log-Zeile (WARNING oder ERROR), die den `chat_key` und die insgesamt
    gewartete Zeit enthaelt.

    RED-Grund heute: derselbe Befund wie AC-1 -- kein Abbruch findet je
    statt (die Schleife wartet das Fenster natuerlich ab und kehrt ohne
    Fehler zurueck), folglich kann auch keine Logzeile VOR einem Abbruch
    erscheinen -> `pytest.raises(OutputError)` schlaegt mit "DID NOT RAISE"
    fehl, bevor die caplog-Pruefung ueberhaupt erreicht wird. Zusaetzlich:
    die bestehende Logzeile bei jeder Wartepause (`telegram.py:246-249`)
    liegt auf INFO (nicht WARNING/ERROR) und nennt keine insgesamt gewartete
    Zeit -- sie wuerde AC-2 inhaltlich auch nicht erfuellen, selbst wenn sie
    auf WARNING gehoben wuerde.
    """
    chat_key = _chat("ac2")
    settings = _settings(
        chat_key,
        telegram_rate_limit_max_per_window=3,
        telegram_rate_limit_window_seconds=1.0,
    )
    monkeypatch.setattr(tg_module, "SEND_SLOT_MAX_WAIT_SECONDS", 0.15, raising=False)
    _fill_window(chat_key, 3)

    ausgang = TelegramOutput(settings)
    with caplog.at_level(logging.WARNING, logger="output.channels.telegram"):
        with pytest.raises(OutputError):
            ausgang._reserve_send_slot(chat_key)

    warn_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warn_records, "keine WARNING/ERROR-Logzeile beim Abbruch gefunden"
    matching = [
        r for r in warn_records
        if chat_key in r.getMessage() and any(ch.isdigit() for ch in r.getMessage())
    ]
    assert matching, (
        f"keine Logzeile enthaelt sowohl chat_key={chat_key!r} als auch eine "
        f"Zeitangabe. Gefundene WARNING/ERROR-Zeilen: "
        f"{[r.getMessage() for r in warn_records]}"
    )


# ---------------------------------------------------------------------------
# AC-3 -- open-meteo bricht nach FETCH_DEADLINE_SECONDS ab (alle Kandidaten)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(10)
def test_fetch_forecast_raises_provider_request_error_after_deadline(monkeypatch):
    """AC-3: Given ein lokaler HTTP-Server, gegen den open-meteo aufgeloest
    ist, nimmt Verbindungen an, antwortet aber nie -- fuer ALLE erreichbaren
    Kandidaten (Nordschweden deckt drei Modelle ab: metno_nordic, icon_eu,
    ecmwf -- drei kontaktierte Endpoints `/v1/metno`, `/v1/dwd-icon`,
    `/v1/ecmwf`; bewusst AUSSERHALB der AT/DE/FR-Cross-Provider-Boxen aus
    `region_routing.py`, sonst griffe bei komplettem Ausfall die
    Cross-Provider-Weiche #1141 und riefe einen echten Direktprovider auf),
    When `fetch_forecast()` aufgerufen wird
    und die verstrichene Zeit `FETCH_DEADLINE_SECONDS` uebersteigt, Then
    wird `ProviderRequestError` geworfen, statt weitere Kandidaten
    unbegrenzt zu versuchen -- gemessene Gesamtlaufzeit liegt nahe
    `FETCH_DEADLINE_SECONDS`, nicht erst nach allen vollen
    Kandidaten-Retry-Zyklen.

    RED-Grund heute: `ProviderRequestError` wird bereits geworfen (jeder
    einzelne HTTP-Versuch ist durch das BESTEHENDE `TIMEOUT` begrenzt, haengt
    also nicht unendlich) -- aber erst nach dem VOLLEN Retry-Zyklus aller
    Kandidaten (5x TIMEOUT fuer den Primaerkandidaten + je 1x TIMEOUT fuer
    die beiden Fallback-Kandidaten, ~1.4s bei den hier geschrumpften Werten),
    weit jenseits von `FETCH_DEADLINE_SECONDS` (0.4s) -- `fetch_forecast()`
    liest diese Konstante heute an keiner Stelle.
    """
    with _HangingServer() as server:
        monkeypatch.setattr(om_module, "TIMEOUT", 0.2)
        monkeypatch.setattr(
            OpenMeteoProvider._request.retry, "wait", tenacity.wait_none()
        )
        monkeypatch.setattr(om_module, "FETCH_DEADLINE_SECONDS", 0.4, raising=False)
        monkeypatch.setattr(
            om_module, "BASE_HOST", f"http://{server.host}:{server.port}"
        )

        provider = OpenMeteoProvider()
        start = time.monotonic()
        with pytest.raises(ProviderRequestError):
            provider.fetch_forecast(
                _NORDSCHWEDEN, enrich_ensemble=False, enrich_snow=False
            )
        elapsed = time.monotonic() - start

    assert elapsed < 0.9, (
        f"fetch_forecast() brauchte {elapsed:.2f}s bis zur ProviderRequestError "
        "-- FETCH_DEADLINE_SECONDS (0.4s) haette den Abbruch weit vor dem "
        "vollen Retry-Zyklus aller Kandidaten erzwingen muessen."
    )


# ---------------------------------------------------------------------------
# AC-4 -- Normalfall bleibt in beiden Mechanismen unveraendert schnell
# ---------------------------------------------------------------------------


@pytest.mark.timeout(8)
def test_normal_case_unaffected_by_new_deadlines(monkeypatch, tmp_path):
    """AC-4: Given der Normalfall in beiden Mechanismen -- (a) weniger als
    `telegram_rate_limit_max_per_window` Zeitstempel liegen im Fenster, (b)
    der open-meteo-Server antwortet sofort mit einer gueltigen Antwort, When
    (a) `_reserve_send_slot()` bzw. (b) `fetch_forecast()` aufgerufen wird,
    Then bleibt das Verhalten in beiden Faellen unveraendert schnell: (a)
    kein `time.sleep`-Aufruf, sofortige Rueckkehr; (b) das gewohnte Ergebnis
    ohne zusaetzlichen Aufruf oder Verzoegerung durch die neue
    Deadline-Pruefung.

    GRUEN erwartet schon heute (Regressions-Waechter, Team-Lead-Brief): kein
    neuer Mechanismus greift im Normalfall ein.
    """
    # --- (a) Telegram-Teil: leeres Fenster -> kein Warten ---
    chat_key = _chat("ac4-tg")
    settings = _settings(chat_key)  # Produktiv-Defaults (max=18, window=60)
    sleep_calls: list[float] = []
    monkeypatch.setattr(tg_module.time, "sleep", lambda s: sleep_calls.append(s))

    ausgang = TelegramOutput(settings)
    ausgang._reserve_send_slot(chat_key)

    assert sleep_calls == [], (
        f"time.sleep() wurde im Normalfall aufgerufen ({sleep_calls}) -- unter "
        "der Drossel-Obergrenze darf ueberhaupt nicht gewartet werden."
    )

    # --- (b) open-meteo-Teil: sofortige gueltige Antwort ---
    cache_path = tmp_path / "model_availability.json"
    _write_all_available_cache(cache_path)
    monkeypatch.setattr(om_module, "AVAILABILITY_CACHE_PATH", cache_path)

    with _immediate_ok_server() as server:
        host, port = server.server_address
        monkeypatch.setattr(om_module, "BASE_HOST", f"http://{host}:{port}")

        provider = OpenMeteoProvider()
        start = time.monotonic()
        result = provider.fetch_forecast(
            _SUEDBADEN, enrich_ensemble=False, enrich_snow=False,
        )
        elapsed = time.monotonic() - start

    assert result.data, "kein Datenpunkt geparst -- gewohntes Ergebnis fehlt"
    assert elapsed < 2.0, (
        f"fetch_forecast() mit sofort antwortendem Server brauchte "
        f"{elapsed:.2f}s -- die neue Deadline-Pruefung darf den Normalfall "
        "nicht verzoegern."
    )


# ---------------------------------------------------------------------------
# AC-5 -- 429-Wiederholung bleibt von den neuen Konstanten unberuehrt
# ---------------------------------------------------------------------------


@pytest.mark.timeout(8)
def test_429_retry_skips_new_slot_reservation_and_stays_capped(monkeypatch):
    """AC-5: Given Telegram antwortet auf einen Sendeversuch mit HTTP 429 und
    einem `retry_after`-Wert oberhalb des bestehenden
    `telegram_retry_after_cap_seconds`-Deckels, When `_post()` die
    bestehende Wiederholung nach 429 durchlaeuft (`:290-304`), Then bleibt
    diese Wiederholung von den neuen Konstanten unberuehrt -- insbesondere
    wird nach dem 429 KEINE erneute Slot-Reservierung ausgeloest, und die
    Wartezeit bleibt weiterhin auf `telegram_retry_after_cap_seconds`
    gedeckelt.

    GRUEN erwartet schon heute (Regressions-Waechter, Team-Lead-Brief):
    dieses Verhalten ist bereits korrekt implementiert (`telegram.py:
    297-303`) und soll durch S3 NICHT veraendert werden.
    """
    chat_key = _chat("ac5")
    settings = _settings(chat_key, telegram_retry_after_cap_seconds=0.05)
    ausgang = TelegramOutput(settings)

    reserve_calls: list[str] = []
    original_reserve = TelegramOutput._reserve_send_slot

    def _spy(self, key):
        reserve_calls.append(key)
        return original_reserve(self, key)

    monkeypatch.setattr(TelegramOutput, "_reserve_send_slot", _spy)
    sleep_calls: list[float] = []
    monkeypatch.setattr(tg_module.time, "sleep", lambda s: sleep_calls.append(s))

    with _http_429_server(retry_after=5.0) as server:
        host, port = server.server_address
        url = f"http://{host}:{port}/bot-test/sendMessage"
        response = ausgang._post(url, {"chat_id": chat_key, "text": "s3-ac5"}, chat_id=chat_key)
        request_count = server.request_count

    assert response.status_code == 429
    assert request_count == 2, (
        f"{request_count} statt 2 POSTs -- erwartet: erster Versuch + genau "
        "EINE 429-Wiederholung."
    )
    assert reserve_calls == [chat_key], (
        f"_reserve_send_slot wurde {len(reserve_calls)}x statt 1x aufgerufen "
        f"({reserve_calls}) -- nach dem 429 darf KEINE zweite "
        "Slot-Reservierung ausgeloest werden (telegram.py:297-303)."
    )
    assert sleep_calls and sleep_calls[0] <= 0.05 + 1e-6, (
        f"tatsaechlich verwendete Wartezeit {sleep_calls} ueberschreitet den "
        "telegram_retry_after_cap_seconds-Deckel (0.05s)."
    )


# ---------------------------------------------------------------------------
# AC-6 -- EIN einzelner haengender _request-Aufruf bricht ab, KEIN
#         Kandidatenwechsel als Erklaerung (Kern des Tickets)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(6)
def test_single_hanging_request_aborts_within_deadline_without_candidate_switch(
    monkeypatch,
):
    """AC-6 (PO-Rueckmeldung 2026-08-01, Kern des Tickets; Team-Lead-Korrektur
    2026-08-01 -- primaerer, ZEITBASIERTER Nachweis): Given ein lokaler
    HTTP-Server nimmt die Verbindung fuer einen EINZELNEN `_request`-Aufruf
    an, antwortet aber nie -- OHNE dass ein Wechsel zum naechsten
    Modell-Kandidaten stattfindet, When `_request(endpoint, params)` OHNE
    explizites `deadline_at` aufgerufen wird, waehrend
    `FETCH_DEADLINE_SECONDS` per Test auf Millisekunden geschrumpft ist,
    Then bricht bereits DIESER EINE Aufruf spaetestens nach
    `FETCH_DEADLINE_SECONDS` mit `ProviderRequestError` ab -- nicht erst
    nach seinem eigenen `RETRY_ATTEMPTS x TIMEOUT`-Maximum.

    Team-Lead-Korrektur: die urspruengliche Fassung rief `_request(...,
    deadline_at=...)` explizit auf und war dadurch NUR wegen des fehlenden
    Parameters rot (`TypeError`) -- das beweist nichts ueber echtes
    Haenge-Verhalten. Diese Fassung ruft ABSICHTLICH OHNE `deadline_at` auf:
    die Zeitgrenze muss auch dann greifen, wenn eine Aufrufstelle den
    Parameter GAR NICHT durchreicht (abgeleitet aus
    `FETCH_DEADLINE_SECONDS` ab Aufrufbeginn), sonst haengt der gesamte
    Schutz an jeder einzelnen Aufrufstelle -- genau die Lueckenklasse, die
    S1/S2 je einen Befund gekostet hat. Implikation fuer die
    Implementierung: `_request()` muss bei `deadline_at=None` intern
    `time.monotonic() + FETCH_DEADLINE_SECONDS` als Ersatzwert bilden, statt
    unbegrenzt weiterzulaufen.

    Direkter Aufruf von `_request()` (nicht ueber `fetch_forecast()`), damit
    ein Kandidatenwechsel als Erklaerung fuer ein bestandenes Ergebnis
    ausgeschlossen ist -- exakt die PO-Vorgabe der Spec.

    RED-Grund heute: `_request()` liest `FETCH_DEADLINE_SECONDS` an keiner
    Stelle -- der Aufruf laeuft durch alle `RETRY_ATTEMPTS=5` Versuche
    (~5x TIMEOUT), weit jenseits der geschrumpften Deadline, bevor
    `ProviderRequestError` geworfen wird. Die Exception selbst kommt also
    schon heute (kein "DID NOT RAISE") -- rot ist AUSSCHLIESSLICH die
    gemessene Laufzeit.
    """
    with _HangingServer() as server:
        monkeypatch.setattr(om_module, "TIMEOUT", 0.2)
        monkeypatch.setattr(
            OpenMeteoProvider._request.retry, "wait", tenacity.wait_none()
        )
        monkeypatch.setattr(om_module, "FETCH_DEADLINE_SECONDS", 0.3, raising=False)
        provider = OpenMeteoProvider()

        start = time.monotonic()
        with pytest.raises(ProviderRequestError):
            provider._request(
                "/v1/ecmwf",
                {"latitude": 65.0, "longitude": 20.0},
                base_host=f"http://{server.host}:{server.port}",
            )
        elapsed = time.monotonic() - start

    assert elapsed < 0.65, (
        f"_request() OHNE deadline_at brauchte {elapsed:.2f}s -- "
        "FETCH_DEADLINE_SECONDS (0.3s) haette den Abbruch weit vor dem "
        "vollen RETRY_ATTEMPTS-Maximum (5x TIMEOUT) erzwingen muessen, AUCH "
        "OHNE dass die Aufrufstelle ein explizites deadline_at durchreicht."
    )


@pytest.mark.timeout(6)
def test_request_explicit_deadline_at_overrides_default_fetch_deadline(monkeypatch):
    """Ergaenzender Nachweis zu AC-6 (Team-Lead-Vorgabe, ERSETZT NICHT den
    zeitbasierten Test oben): ein explizit uebergebenes `deadline_at` muss
    VOR dem aus `FETCH_DEADLINE_SECONDS` abgeleiteten Default greifen --
    Grundlage dafuer, dass `fetch_forecast()` (AC-3) EIN gemeinsames
    `deadline_at` ueber die gesamte Kandidaten-Schleife weiterreichen kann,
    statt dass jeder einzelne `_request()`-Aufruf seinen eigenen vollen
    `FETCH_DEADLINE_SECONDS`-Default neu beginnt.

    Given `FETCH_DEADLINE_SECONDS` ist auf einen GROSSZUEGIGEN Wert
    geschrumpft (2.0s -- wuerde das Default-Verhalten allein binnen der
    Testlaufzeit NICHT greifen lassen) UND ein explizites `deadline_at` ist
    auf eine deutlich KUERZERE Restzeit (0.15s) gesetzt, When
    `_request(endpoint, params, deadline_at=...)` gegen den haengenden
    Server aufgerufen wird, Then bricht der Aufruf nahe der KUERZEREN
    expliziten Restzeit ab, nicht erst nach dem laengeren Default.

    RED-Grund heute (Signatur-Luecke, ergaenzend zum zeitbasierten Beweis
    oben): `_request()` kennt den Parameter `deadline_at` noch nicht ->
    `TypeError` ("unexpected keyword argument 'deadline_at'"), bevor
    irgendein Zeitverhalten beobachtet werden kann.
    """
    with _HangingServer() as server:
        monkeypatch.setattr(om_module, "TIMEOUT", 0.2)
        monkeypatch.setattr(
            OpenMeteoProvider._request.retry, "wait", tenacity.wait_none()
        )
        monkeypatch.setattr(om_module, "FETCH_DEADLINE_SECONDS", 2.0, raising=False)
        provider = OpenMeteoProvider()
        deadline_at = time.monotonic() + 0.15

        start = time.monotonic()
        with pytest.raises(ProviderRequestError):
            provider._request(
                "/v1/ecmwf",
                {"latitude": 65.0, "longitude": 20.0},
                base_host=f"http://{server.host}:{server.port}",
                deadline_at=deadline_at,
            )
        elapsed = time.monotonic() - start

    assert elapsed < 0.5, (
        f"_request() mit explizitem deadline_at brauchte {elapsed:.2f}s -- "
        "das explizite deadline_at (0.15s Restzeit) haette VOR dem "
        "grosszuegigen FETCH_DEADLINE_SECONDS-Default (2.0s) greifen muessen."
    )


# ---------------------------------------------------------------------------
# F001 (Adversary-Runde #1448 S3) -- Mutations-Luecke: die zeitbasierte
# Stop-Bedingung selbst war von keinem Test abgesichert
# ---------------------------------------------------------------------------


@pytest.mark.timeout(6)
def test_stop_condition_limits_retry_backoff_within_deadline(monkeypatch):
    """F001: entfernt man ``_stop_at_request_deadline`` aus der
    ``stop``-Komposition (``openmeteo.py:548``), blieben bislang ALLE Tests
    gruen -- beide einschlaegigen Tests oben neutralisieren die Wartepausen
    per ``monkeypatch.setattr(OpenMeteoProvider._request.retry, "wait",
    tenacity.wait_none())`` und schalten damit genau den Faktor aus, den die
    Bedingung begrenzen soll. Der Restzeit-Check am Kopf von ``_request()``
    (``restzeit <= 0``) faengt einen ueberzogenen Aufruf zwar ohnehin
    IRGENDWANN ab, aber erst am Beginn des NAECHSTEN Versuchs -- also erst
    NACH einer vollen, unnoetigen Wartepause, wenn diese Bedingung fehlt.

    Dieser Test laesst die Wartepause SPUERBAR und UNNEUTRALISIERT
    (``tenacity.wait_fixed(1.5)``): ``FETCH_DEADLINE_SECONDS`` ist auf 0.3s
    geschrumpft, ``TIMEOUT`` bleibt UNVERAENDERT (Produktionswert 30s) --
    dadurch deckelt ``request_timeout = min(TIMEOUT, restzeit)`` schon den
    ERSTEN Versuch exakt auf die Restzeit (~0.3s), er scheitert also GENAU
    an der Deadline. Mit ``_stop_at_request_deadline`` stoppt tenacity SOFORT
    danach (keine weitere Wartepause mehr, da der Stop-Check VOR dem
    tatsaechlichen Schlafen der berechneten Wartezeit ausgewertet wird).
    Fehlt die Bedingung, prueft tenacity nur noch
    ``stop_after_attempt(RETRY_ATTEMPTS)`` (Versuch 1 von 5) -- das haelt
    nicht an, der volle 1.5s-Wartezyklus laeuft unnoetig durch, ehe der
    Restzeit-Check am Kopf des zweiten Versuchs erst dort abbricht.

    Given ein haengender lokaler Server, ``FETCH_DEADLINE_SECONDS`` auf 0.3s
    geschrumpft und eine ECHTE (nicht neutralisierte) Wartepause von 1.5s,
    When ``_request()`` OHNE explizites ``deadline_at`` aufgerufen wird,
    Then bleibt die Gesamtlaufzeit deutlich unter dem, was ein zusaetzlicher
    Wartezyklus verursachen wuerde (< 1.0s statt ~1.8s).

    Selbstkontrolle (Ergebnis im Bericht, nicht Teil dieses Testlaufs): mit
    ``_stop_at_request_deadline`` testweise aus der ``stop``-Komposition
    entfernt wird dieser Test ROT (gemessene Laufzeit deutlich > 1.0s); mit
    wiederhergestellter Bedingung GRUEN.
    """
    with _HangingServer() as server:
        monkeypatch.setattr(om_module, "FETCH_DEADLINE_SECONDS", 0.3, raising=False)
        monkeypatch.setattr(
            OpenMeteoProvider._request.retry, "wait", tenacity.wait_fixed(1.5)
        )
        provider = OpenMeteoProvider()

        start = time.monotonic()
        with pytest.raises(ProviderRequestError):
            provider._request(
                "/v1/ecmwf",
                {"latitude": 65.0, "longitude": 20.0},
                base_host=f"http://{server.host}:{server.port}",
            )
        elapsed = time.monotonic() - start

    assert elapsed < 1.0, (
        f"_request() brauchte {elapsed:.2f}s -- das deutet darauf hin, dass "
        "die zeitbasierte Stop-Bedingung (_stop_at_request_deadline) NICHT "
        "griff und ein voller zusaetzlicher Wartezyklus (1.5s, absichtlich "
        "NICHT neutralisiert) durchlief, bevor der Restzeit-Check am Kopf "
        "des naechsten Versuchs erst abbrach."
    )
