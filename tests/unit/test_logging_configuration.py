"""TDD RED — Issue #1447 Scheibe S1 Teil B: Root-Logger-Konfiguration (AC-6).

SPEC: docs/specs/modules/fix_1447_s1_alarm_lauf_zeitgrenze.md

Verhaltenstests -- kein Mock-Theater. Ruft ``api.main.configure_logging()``
direkt auf und prueft echtes Verhalten des installierten Root-Logger-Handlers/
-Formatters (Level, formatierte Ausgabe), nicht bloss eine String-Suche im
Quelltext.

RED-Ursache (heute): ``api.main`` hat keine Funktion ``configure_logging`` ->
``AttributeError: module 'api.main' has no attribute 'configure_logging'``
bei jedem Test dieser Datei.

Adversary-Nachbefund F001 (#1447): ``configure_logging()`` schaltet den
Root-Logger auf INFO -- damit werden auch die INFO-Zeilen von httpx/httpcore
sichtbar, die vorher verworfen wurden. httpx protokolliert bei jedem Request
die volle URL, und die Telegram-Bot-API kodiert den Zugangsschluessel als
URL-Pfadsegment (".../bot{token}/sendMessage") -- der echte Bot-Token wuerde
sonst bei jedem Alarm/Briefing im Prozess-Log landen. Der Test unten baut
denselben echten lokalen Bot-API-Socket wie
tests/tdd/test_issue_671_bot_menu_autoset.py nach und beweist am Verhalten
(nicht an der Einstellung), dass ein Platzhalter-Token in der gesamten
aufgefangenen Log-Ausgabe NICHT auftaucht -- auch nicht bei GZ_LOG_LEVEL=DEBUG.
"""
from __future__ import annotations

import http.server
import json
import logging
import re
import socketserver
import threading
from contextlib import contextmanager

import pytest


@pytest.fixture(autouse=True)
def _restore_root_logger_state():
    """Verhindert, dass ``configure_logging()``-Aufrufe aus diesen Tests den
    Root-Logger fuer den Rest der Testsuite dauerhaft veraendern (analog dem
    Save/Redirect/Restore-Muster von ``_isolate_data_root`` in
    tests/conftest.py)."""
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.setLevel(original_level)


def test_configure_logging_default_level_is_info_and_installs_formatter(monkeypatch):
    """AC-6: Given der Python-Core-Prozess startet (Default, kein
    GZ_LOG_LEVEL gesetzt) / When ``configure_logging()`` laeuft / Then ist
    die Mindeststufe INFO und der installierte Formatter zeigt Zeitstempel,
    Log-Stufe und Modulname in der formatierten Ausgabe.
    """
    import api.main as main_module

    monkeypatch.delenv("GZ_LOG_LEVEL", raising=False)
    main_module.configure_logging()

    root = logging.getLogger()
    assert root.level == logging.INFO, (
        f"Default-Mindeststufe muss INFO sein, tatsaechlich: "
        f"{logging.getLevelName(root.level)}"
    )
    assert root.handlers, "configure_logging() muss mindestens einen Handler installieren"
    formatter = root.handlers[0].formatter
    assert formatter is not None, "Root-Handler hat keinen Formatter"

    record = logging.LogRecord(
        name="src.services.trip_alert", level=logging.INFO, pathname=__file__,
        lineno=1, msg="Testzeile fuer Format-Pruefung (#1447 AC-6)", args=(), exc_info=None,
    )
    formatted = formatter.format(record)
    assert re.search(r"\d{4}-\d{2}-\d{2}", formatted) or re.search(r"\d{2}:\d{2}:\d{2}", formatted), (
        f"Formatierte Zeile enthaelt keinen erkennbaren Zeitstempel: {formatted!r}"
    )
    assert "INFO" in formatted, f"Formatierte Zeile enthaelt keine Log-Stufe: {formatted!r}"
    assert "src.services.trip_alert" in formatted, (
        f"Formatierte Zeile enthaelt keinen Modulnamen: {formatted!r}"
    )


def test_configure_logging_level_controllable_via_env_debug(monkeypatch):
    """AC-6: Given GZ_LOG_LEVEL=DEBUG gesetzt / When ``configure_logging()``
    laeuft / Then ist die sichtbare Mindeststufe DEBUG.
    """
    import api.main as main_module

    monkeypatch.setenv("GZ_LOG_LEVEL", "DEBUG")
    main_module.configure_logging()

    root = logging.getLogger()
    assert root.level == logging.DEBUG, (
        f"GZ_LOG_LEVEL=DEBUG muss root.level auf DEBUG setzen, tatsaechlich: "
        f"{logging.getLevelName(root.level)}"
    )


@pytest.mark.parametrize("bogus_value", ["VOELLIGER_UNSINN", ""])
def test_configure_logging_bogus_level_falls_back_to_info_without_raising(monkeypatch, bogus_value):
    """Fail-soft-Nachbefund #1447: Given GZ_LOG_LEVEL ist unbekannt/leer /
    When ``configure_logging()`` laeuft / Then wirft es NICHT und die
    wirksame Stufe ist INFO -- eine INFO-Zeile kommt tatsaechlich durch.

    Vorher: ``logging.getLevelName("VOELLIGER_UNSINN")`` liefert den String
    ``"Level VOELLIGER_UNSINN"`` zurueck, den ``basicConfig()`` dann mit
    ``ValueError: Unknown level`` quittiert hat -- Absturz beim Modulimport.
    """
    import io

    import api.main as main_module

    monkeypatch.setenv("GZ_LOG_LEVEL", bogus_value)
    main_module.configure_logging()  # darf NICHT werfen

    root = logging.getLogger()
    assert root.level == logging.INFO, (
        f"Bogus/leerer GZ_LOG_LEVEL muss auf INFO zurueckfallen, tatsaechlich: "
        f"{logging.getLevelName(root.level)}"
    )
    assert root.handlers, "configure_logging() muss trotzdem einen Handler installieren"

    buffer = io.StringIO()
    root.handlers[0].stream = buffer
    test_logger = logging.getLogger("src.services.trip_alert")
    test_logger.info("INFO-Zeile muss bei Fallback-auf-INFO durchkommen (#1447)")

    output = buffer.getvalue()
    assert "INFO-Zeile muss bei Fallback-auf-INFO durchkommen" in output, (
        f"Effektive Stufe ist nicht wirklich INFO -- INFO-Zeile fehlt im Ausgang: {output!r}"
    )


def test_configure_logging_warning_level_suppresses_info_line(monkeypatch):
    """AC-6 Gegenrichtung: Given GZ_LOG_LEVEL=WARNING gesetzt / When ein
    Modul unter src/ eine INFO-Zeile protokolliert / Then erscheint diese
    Zeile NICHT im konfigurierten Root-Logger-Ausgang, eine WARNING-Zeile
    hingegen schon.
    """
    import io

    import api.main as main_module

    monkeypatch.setenv("GZ_LOG_LEVEL", "WARNING")
    main_module.configure_logging()

    root = logging.getLogger()
    assert root.handlers, "configure_logging() muss mindestens einen Handler installieren"
    buffer = io.StringIO()
    root.handlers[0].stream = buffer

    test_logger = logging.getLogger("src.services.trip_alert")
    test_logger.info("Diese INFO-Zeile darf bei GZ_LOG_LEVEL=WARNING nicht sichtbar werden (#1447 AC-6)")
    test_logger.warning("Diese WARNING-Zeile MUSS sichtbar werden (#1447 AC-6)")

    output = buffer.getvalue()
    assert "MUSS sichtbar werden" in output, (
        f"WARNING-Zeile fehlt im Root-Logger-Ausgang trotz GZ_LOG_LEVEL=WARNING: {output!r}"
    )
    assert "darf bei GZ_LOG_LEVEL=WARNING nicht sichtbar werden" not in output, (
        f"INFO-Zeile erschien trotz GZ_LOG_LEVEL=WARNING im Root-Logger-Ausgang: {output!r}"
    )


# ---------------------------------------------------------------------------
# Adversary-Befund F001 — Telegram-Bot-Token darf NIE ins Log durchsickern
# ---------------------------------------------------------------------------

def _bot_api_handler():
    class _Handler(http.server.BaseHTTPRequestHandler):
        def _dispatch(self) -> None:
            n = int(self.headers.get("Content-Length", 0) or 0)
            if n:
                self.rfile.read(n)
            body = json.dumps({"ok": True, "result": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802
            self._dispatch()

        def log_message(self, *args):  # Stille -- kein http.server-Eigenrauschen
            return

    return _Handler


@contextmanager
def _bot_server():
    """Echter TCP-Socket, der Telegram-Bot-API-Calls beantwortet (kein Mock).

    Nachgebaut aus tests/tdd/test_issue_671_bot_menu_autoset.py."""
    srv = socketserver.TCPServer(("127.0.0.1", 0), _bot_api_handler())
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.shutdown()
        srv.server_close()


def _assert_placeholder_token_never_logged(monkeypatch, gz_log_level, placeholder_token):
    """Konfiguriert Logging auf ``gz_log_level``, feuert einen echten
    Telegram-API-Call gegen den lokalen Bot-Socket ab und prueft, dass der
    Platzhalter-Token in KEINER aufgefangenen Log-Zeile auftaucht -- weder
    ueber httpx' eigenen "HTTP Request"-Logger noch ueber irgendeinen
    anderen Root-Logger-Handler."""
    import api.main as main_module
    from app.config import Settings
    from output.channels.telegram import TelegramOutput

    if gz_log_level is None:
        monkeypatch.delenv("GZ_LOG_LEVEL", raising=False)
    else:
        monkeypatch.setenv("GZ_LOG_LEVEL", gz_log_level)
    main_module.configure_logging()

    root = logging.getLogger()
    assert root.handlers, "configure_logging() muss mindestens einen Handler installieren"
    import io

    buffer = io.StringIO()
    root.handlers[0].stream = buffer

    with _bot_server() as base:
        monkeypatch.setattr("output.channels.telegram.TELEGRAM_API_BASE", base)
        monkeypatch.setenv("GZ_TELEGRAM_BOT_TOKEN", placeholder_token)
        TelegramOutput(Settings()).set_my_commands()

    output = buffer.getvalue()
    assert placeholder_token not in output, (
        f"Platzhalter-Token {placeholder_token!r} erscheint im Log-Ausgang trotz "
        f"GZ_LOG_LEVEL={gz_log_level!r} — Zugangsschluessel-Leak (#1447 F001): {output!r}"
    )


def test_telegram_bot_token_never_appears_in_log_output_default_level(monkeypatch):
    """Adversary-Befund F001: Given Root-Logger auf Default-Stufe (INFO) /
    When ein echter Telegram-Bot-API-Call laeuft / Then taucht der
    Platzhalter-Token in keiner Log-Zeile auf (httpx protokolliert sonst die
    volle URL inkl. Token-Pfadsegment auf INFO)."""
    _assert_placeholder_token_never_logged(monkeypatch, None, "PLACEHOLDER-TOKEN-F001-DEFAULT")


def test_telegram_bot_token_never_appears_in_log_output_debug_level(monkeypatch):
    """Adversary-Befund F001, Gegenrichtung: Auch bei GZ_LOG_LEVEL=DEBUG
    (z.B. zur Fehlersuche) darf httpx/httpcore NICHT auf DEBUG/INFO
    hochspringen — sonst baut sich das Leck beim Debuggen wieder ein."""
    _assert_placeholder_token_never_logged(monkeypatch, "DEBUG", "PLACEHOLDER-TOKEN-F001-DEBUG")
