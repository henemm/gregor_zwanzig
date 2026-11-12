"""Protokollzeilen enthalten keine vollstaendigen Nutzeradressen oder Befehlstexte (#2961, AC-10)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.loader import get_data_dir, get_data_root, lookup_user_by_email
from services.trip_command_processor import InboundMessage, TripCommandProcessor

ADRESSE = "doppelt-vergeben@example.org"


def _profil(user_id: str) -> None:
    d = get_data_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({
        "id": user_id, "mail_to": ADRESSE, "email_verified_at": "2026-01-01T00:00:00Z",
    }))


def test_mehrdeutige_adresse_wird_maskiert_protokolliert(caplog):
    _profil("log-mask-a")
    _profil("log-mask-b")
    with caplog.at_level(logging.ERROR, logger="app.loader"):
        assert lookup_user_by_email(ADRESSE, data_dir=str(get_data_root())) is None
    texte = " ".join(r.getMessage() for r in caplog.records)
    assert "mehrdeutig" in texte
    assert ADRESSE not in texte
    assert "doppelt-vergeben" not in texte


class _Kaputt(TripCommandProcessor):
    """Laesst die innere Verarbeitung scheitern, um die Fehlerbehandlung von process() zu pruefen."""

    def _process(self, msg):  # noqa: ANN001
        raise RuntimeError("innen kaputt")


def test_unerwarteter_fehler_protokolliert_keinen_befehlstext(caplog):
    geheim = "ruhetag mit privater Notiz 0170-1234567 " * 3
    msg = InboundMessage(
        trip_name="T", body=geheim, sender="x@example.org", channel="email",
        received_at=datetime.now(timezone.utc), user_id="log-mask-a",
    )
    with caplog.at_level(logging.ERROR):
        ergebnis = _Kaputt().process(msg)
    assert ergebnis.success is False
    texte = " ".join(r.getMessage() for r in caplog.records)
    assert "unerwarteter Fehler" in texte
    assert "0170-1234567" not in texte
    assert "private" not in texte
