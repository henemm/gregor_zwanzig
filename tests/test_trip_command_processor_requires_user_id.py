"""Kern-Schicht: ``InboundMessage`` verlangt ``user_id`` als Pflichtfeld
statt still auf ``"default"`` zurueckzufallen (#2151 Scheibe C).

Spec: docs/specs/modules/fix_2151_default_fallbacks_scheibe_c.md (Test 11,
AC-7)

Heute (RED): das Dataclass-Feld traegt den Default ``user_id: str =
"default"`` -- eine Konstruktion ohne ``user_id`` gelingt klaglos und traegt
danach still die Kennung ``"default"``, statt mit ``TypeError`` zu scheitern.

Nachweisform: reine Konstruktions-Zusicherung, keine Fixtures/Doubles noetig.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.trip_command_processor import InboundMessage


def test_ac7_inbound_message_ohne_user_id_wirft_typeerror():
    """AC-7 / Test 11: ``InboundMessage(...)`` ohne ``user_id`` wirft
    ``TypeError`` -- kein stiller Rueckfall auf ``"default"``."""
    with pytest.raises(TypeError):
        InboundMessage(  # type: ignore[call-arg]
            trip_name="TourA",
            body="status",
            sender="wanderer-a@example.com",
            channel="email",
            received_at=datetime.now(tz=timezone.utc),
        )


def test_ac9_inbound_message_mit_explizitem_user_id_default_funktioniert_weiter():
    """AC-9 (Regression): das Konto ``"default"`` bleibt gueltig, wenn es
    EXPLIZIT uebergeben wird (Scheibe-A-Entscheid, nicht erneut vorzulegen)."""
    inbound = InboundMessage(
        trip_name="TourA",
        body="status",
        sender="wanderer-a@example.com",
        channel="email",
        received_at=datetime.now(tz=timezone.utc),
        user_id="default",
    )
    assert inbound.user_id == "default"
