"""
Notify router — Test channel endpoint.

POST /api/notify/test sends a real test message via the chosen channel.
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.services.channel_test_service import send_test_message

router = APIRouter()


class TestRequest(BaseModel):
    channel: str  # "email" | "telegram"


@router.post("/api/notify/test")
async def test_notify(
    req: TestRequest,
    user_id: str = Query(...),
):
    return send_test_message(req.channel, user_id)
