"""Premium-SMS sendet exakt den gerenderten SMS-Text (Issue #2670, AC-7).

SPEC: docs/specs/modules/i18n_p8_sms_freitext_2670.md AC-7. Der Ortsvergleich-
SMS-Text wird echt gerendert (``render_compare_sms``, mit ``lang``, sobald P4
#2666 den Parameter liefert) und ueber den echten Versandweg
``NotificationService.send_compare_report`` an die Sink-Naht
``premium_sms_sink`` gegeben. Die Naht muss genau diesen Text erhalten: keine
Ergaenzung, keine Uebersetzung im Transport.

Zwei Nutzer mit getrennten Datenordnern (Mandantentrennung): jeder erhaelt
seinen eigenen Text, das Tageslimit laeuft echt je Nutzer. Kein Mock.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest

from app.config import Settings
from output.renderers.comparison import render_compare_sms
from services.notification_service import NotificationService
from tests.helpers.sms_sprachen_fixture import mit_sprache, vergleich_zwoelf_orte


@pytest.fixture
def datenwurzel(tmp_path, monkeypatch):
    from app import loader as app_loader

    root = tmp_path / "data"
    root.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(root))
    monkeypatch.setenv("GZ_ENV", "development")
    return root


def _nutzer() -> str:
    from app.loader import get_data_dir

    uid = f"psms-{uuid.uuid4().hex[:8]}"  # ohne "test"/"tdd" (is_test_user_id)
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({
        "id": uid, "tier": "premium",
        "premium_sms_reply_to": "4915799912345",
        "premium_sms_reply_at": datetime.now(timezone.utc).isoformat(),
    }))
    return uid


def _senden(uid: str, sms_text: str) -> tuple[list[str], object]:
    naht: list[str] = []
    ergebnis = NotificationService(settings=Settings(), user_id=uid).send_compare_report(
        subject="Ortsvergleich", html_body="<p>H</p>", text_body="T",
        telegram_text="TG", sms_text=sms_text, recipients=["to@example.invalid"],
        effective_channels={"premium_sms"}, premium_sms_sink=naht.append,
    )
    return naht, ergebnis


def test_ac7_premium_sms_naht_erhaelt_genau_den_gerenderten_text(datenwurzel):
    en_text, _ = mit_sprache(render_compare_sms, vergleich_zwoelf_orte(), lang="en")
    de_text, _ = mit_sprache(render_compare_sms, vergleich_zwoelf_orte(), lang="de")

    nutzer_en, nutzer_de = _nutzer(), _nutzer()
    naht_en, erg_en = _senden(nutzer_en, en_text)
    naht_de, erg_de = _senden(nutzer_de, de_text)

    assert "premium_sms" in erg_en.sent_channels, erg_en
    assert "premium_sms" in erg_de.sent_channels, erg_de
    assert naht_en == [en_text]
    assert naht_de == [de_text]


def test_ac7_englischer_vergleichstext_erreicht_die_naht(datenwurzel):
    en_text, angekommen = mit_sprache(render_compare_sms, vergleich_zwoelf_orte(), lang="en")
    if not angekommen:
        pytest.skip("render_compare_sms kennt lang noch nicht (P4 #2666)")
    assert not en_text.startswith("Vergleich")
    naht, _ = _senden(_nutzer(), en_text)
    assert naht == [en_text]
