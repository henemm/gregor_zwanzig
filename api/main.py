"""
Gregor Zwanzig Core API — Python FastAPI Wrapper.

Exposes the Python core as HTTP endpoints for the Go API to proxy.
Runs on localhost:8000 (internal only).
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routers import config, compare, forecast, gpx, health, internal, notify, preview, scheduler, validator, webhook
from app.config import Settings
from app.egress_guard import install_egress_guard
from output.channels.telegram import TelegramOutput

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Root-Logger fuer den gesamten Python-Core (Issue #1447 Teil B):
    ohne das gibt es keine einzige sichtbare logger.info/.warning-Zeile aus
    src/, weder in Betrieb noch fuer die Fehlersuche. Stufe ueber
    GZ_LOG_LEVEL (Default INFO). `force=True` macht die Funktion
    deterministisch wiederholbar (Tests, mehrfacher Import) statt vom
    Zufall abzuhaengen, ob der Root-Logger bereits Handler traegt.

    Fail-soft (Issue #1447 Folgebefund): ``logging.getLevelName()`` wirft bei
    einem unbekannten Namen NICHT, sondern liefert den String
    ``"Level <NAME>"`` zurueck -- das haette ``basicConfig()`` mit
    ``ValueError: Unknown level`` abstuerzen lassen und damit den gesamten
    Python-Core beim Import wegen eines Tippfehlers in einer reinen
    Diagnose-Einstellung lahmgelegt. Ein unbekannter oder leerer Wert faellt
    daher auf INFO zurueck; der Rueckfall wird als Warnung sichtbar gemacht,
    blockiert aber nichts."""
    raw_level = os.environ.get("GZ_LOG_LEVEL")
    level_name = "INFO" if raw_level is None else raw_level.strip().upper()
    numeric_level = logging.getLevelName(level_name) if level_name else None
    fallback_needed = raw_level is not None and not isinstance(numeric_level, int)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )

    if fallback_needed:
        logger.warning(
            "GZ_LOG_LEVEL=%r ist kein gueltiger Log-Level, falle zurueck auf INFO (#1447)",
            raw_level,
        )

    # Adversary-Befund F001 (#1447): httpx/httpcore protokollieren bei jedem
    # Request die volle URL auf INFO. Die Telegram-Bot-API kodiert den
    # Zugangsschluessel als URL-Pfadsegment
    # (".../bot{token}/sendMessage") -- mit dem Root-Logger auf INFO landet
    # der Klartext-Token sonst bei jedem Alarm/Briefing im Prozess-Log
    # (journalctl). Fest auf WARNING, UNABHAENGIG von GZ_LOG_LEVEL --
    # sonst baut sich das Leck beim Debuggen (GZ_LOG_LEVEL=DEBUG) wieder ein.
    for _noisy_logger_name in ("httpx", "httpcore"):
        logging.getLogger(_noisy_logger_name).setLevel(logging.WARNING)


configure_logging()


def _init_telegram_bot_menu(settings: Settings | None = None) -> None:
    """Setzt das Bot-Menü idempotent beim Startup aus BOT_COMMANDS.

    Fail-soft: wirft niemals — ein Telegram-Ausfall darf den Service-Start nicht blocken.
    Guard: nur ausführen wenn telegram_bot_token gesetzt (NICHT can_send_telegram(),
    da chat_id fürs Menü-Setzen irrelevant ist).
    """
    s = settings or Settings()
    if not s.telegram_bot_token:
        logger.debug("_init_telegram_bot_menu: kein Bot-Token — übersprungen")
        return
    try:
        TelegramOutput(s).set_my_commands()
        logger.info("_init_telegram_bot_menu: setMyCommands OK")
    except Exception as e:  # noqa: BLE001
        logger.warning("_init_telegram_bot_menu: setMyCommands fehlgeschlagen (fail-soft): %s", e)


@asynccontextmanager
async def lifespan(app):  # noqa: ANN001
    # Issue #1337 Scheibe A, Fix F001: Egress-Waechter im ECHTEN Laufzeitprozess
    # (uvicorn api.main:app, systemd gregor-python-staging) scharf schalten.
    # No-Op in Prod (Aktivierungsbedingung liegt im Modul: nur is_test_mode oder
    # env==staging). Idempotent -- Doppel-Install (z.B. conftest-Fixture + App-
    # Start unter TestClient) faengt das _installed-Flag im Modul sauber ab.
    settings = Settings()
    install_egress_guard(settings)
    _init_telegram_bot_menu(settings)
    yield


app = FastAPI(title="Gregor Zwanzig Core API", version="0.1.0", lifespan=lifespan)
app.include_router(health.router)
app.include_router(config.router)
app.include_router(forecast.router)
app.include_router(gpx.router)
app.include_router(scheduler.router)
app.include_router(compare.router)
app.include_router(notify.router)
app.include_router(internal.router)
app.include_router(preview.router)
app.include_router(validator.router)
app.include_router(webhook.router)

if os.environ.get("GZ_ENV") == "staging":
    from api.routers import debug as _debug_router
    app.include_router(_debug_router.router)
