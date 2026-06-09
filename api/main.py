"""
Gregor Zwanzig Core API — Python FastAPI Wrapper.

Exposes the Python core as HTTP endpoints for the Go API to proxy.
Runs on localhost:8000 (internal only).
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routers import config, compare, forecast, gpx, health, internal, notify, preview, scheduler, validator, webhook
from app.config import Settings
from outputs.telegram import TelegramOutput

logger = logging.getLogger(__name__)


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
    _init_telegram_bot_menu()
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
