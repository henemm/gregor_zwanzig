"""
Notify router — Test channel endpoint.

POST /api/notify/test sends a real test message via the chosen channel.
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.app.config import Settings
from src.outputs.email import EmailOutput
from src.outputs.signal import SignalOutput
from src.outputs.telegram import TelegramOutput

router = APIRouter()

SUBJECT = "Gregor 20 — Testmeldung"
BODY = "Dein Kanal funktioniert!"


class TestRequest(BaseModel):
    channel: str  # "email" | "signal" | "telegram"


@router.post("/api/notify/test")
async def test_notify(
    req: TestRequest,
    user_id: str = Query(...),
):
    settings = Settings().with_user_profile(user_id)
    try:
        if req.channel == "email":
            output = EmailOutput(settings)
            output.send(SUBJECT, BODY, html=False)
        elif req.channel == "signal":
            output = SignalOutput(settings)
            output.send(SUBJECT, BODY)
        elif req.channel == "telegram":
            output = TelegramOutput(settings)
            output.send(SUBJECT, BODY)
        else:
            return {"error": f"Unbekannter Kanal: {req.channel}"}
        return {"status": "ok"}
    except Exception as exc:
        return {"error": str(exc)}
