"""Eine Normalform fuer Premium-SMS-Rueckadressen (Issue #2961, ADR-0116, F004).

Liest dieselbe Tabelle wie der Go-Test
``internal/model/premium_sms_nummer_test.go``; dazu die Wirkung am
Sendeweg: dieselbe Nummer in anderer Schreibweise bei einem zweiten Konto
sperrt den Versand.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.loader import get_data_dir
from output.channels.base import ChannelBlockedError
from output.channels.recipient import PremiumSmsRecipient, normalize_premium_number

TABELLE = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "premium_sms_nummern_normalform.json")
    .read_text(encoding="utf-8")
)


@pytest.mark.parametrize("gruppe", TABELLE["gruppen"], ids=lambda g: g["normalform"])
def test_gleiche_nummer_gleiche_normalform(gruppe):
    for schreibweise in gruppe["schreibweisen"]:
        assert normalize_premium_number(schreibweise) == gruppe["normalform"], schreibweise


def test_verschiedene_nummern_bleiben_verschieden_und_leeres_bleibt_leer():
    formen = [g["normalform"] for g in TABELLE["gruppen"]]
    assert len(set(formen)) == len(formen)
    for leer in TABELLE["leer"]:
        assert normalize_premium_number(leer) == ""


class _Settings:
    is_test_mode = False


def _profil(uid: str, nummer: str) -> None:
    ordner = get_data_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({
        "id": uid, "tier": "premium", "premium_sms_reply_to": nummer,
        "premium_sms_reply_at": datetime.now(timezone.utc).isoformat(),
    }))


def test_andere_schreibweise_bei_zweitem_konto_sperrt_den_versand():
    anna, bert = f"psn-anna-{uuid.uuid4().hex[:6]}", f"psn-bert-{uuid.uuid4().hex[:6]}"
    _profil(anna, "+4917000000071")
    _profil(bert, "0049 170 0000 0071")
    with pytest.raises(ChannelBlockedError):
        PremiumSmsRecipient.for_user(anna, _Settings())
