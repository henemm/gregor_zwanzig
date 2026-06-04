"""
Notify router — Test channel endpoint.

POST /api/notify/test sends a real test message via the chosen channel.
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.app.config import Settings
from src.outputs.email import EmailOutput
from src.outputs.telegram import TelegramOutput

router = APIRouter()

SUBJECT = "Gregor 20 — Testmeldung"
BODY = "Dein Kanal funktioniert!"


class TestRequest(BaseModel):
    channel: str  # "email" | "telegram"


@router.post("/api/notify/test")
async def test_notify(
    req: TestRequest,
    user_id: str = Query(...),
):
    # Issue #198: Channel-Tests sind konzeptionell Tests → IMMER Gmail-Routing,
    # nie über Production-SMTP (Resend). _is_test_user("default") liefert False,
    # daher zwingen wir .for_testing() unabhängig vom user_id.
    settings = Settings().with_user_profile(user_id).for_testing()
    try:
        if req.channel == "email":
            output = EmailOutput(settings)
            output.send(SUBJECT, BODY, html=False)
        elif req.channel == "telegram":
            output = TelegramOutput(settings)
            output.send(SUBJECT, BODY)
        else:
            return {"error": f"Unbekannter Kanal: {req.channel}"}
        return {"status": "ok"}
    except Exception as exc:
        return {"error": str(exc)}
