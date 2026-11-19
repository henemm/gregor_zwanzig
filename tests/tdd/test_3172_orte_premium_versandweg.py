"""#3172 Adversary F001/F003: Premium-SMS der Orte auf dem ECHTEN Versandweg.

SPEC: docs/specs/modules/feat_3172_orte_sms_token_zeile.md (Premium-Regel
wie beim Trip, #3100)

Regel: die Premium-SMS ist der SMS-Text, solange er in
``CHANNEL_LIMITS["premium_sms"]["max_chars"]`` (153) passt, sonst derselbe
Renderer mit dieser Grenze. Geprueft dort, wo die Regel WIRKT:

* ``send_one_compare_preset`` (Scheduler-Versand) mit echten Aufzeichnern je
  Kanal -- die SMS bekommt 154..160 Zeichen, die Premium-SMS den neu
  gerenderten Text <= 153 (``compare_premium_sms_rendern``);
* ``NotificationService.send_compare_report`` sendet ``premium_sms_text``
  ueber den Premium-Kanal, nicht ``sms_text``;
* Grenzen 153/154 in ``compare_premium_sms_rendern``.

Kern-Schicht: echte Renderer, echte Kanal-Aufloesung, Tageslimit-Dateien
unter ``tmp_path``; ersetzt sind nur die Transporte (Aufzeichner wie in
``test_compare_premium_sms_versand``) und der Wetterabruf (fester
Beispiel-Datensatz ``placements_beispiel``). Kein Netz, kein Mock.
"""
from __future__ import annotations

import pytest

from app.config import Settings
from app.user import SavedLocation
from output.renderers.channel_layout import CHANNEL_LIMITS
from services import compare_briefing_aufbau as aufbau
from services import placements_beispiel as pb
from services.notification_service import NotificationService
from tests.tdd.test_compare_premium_sms_versand import (
    _ENV, _aufzeichner_installieren, _kennung, _nutzer,
)

PREMIUM_MAX = CHANNEL_LIMITS["premium_sms"]["max_chars"]
NAMEN = ["Aabenraa", "Flensburg", "Schleswig"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolierte Datenwurzel + Dummy-ENV + Aufzeichner je Kanal (wie
    ``test_compare_premium_sms_versand``)."""
    from app import loader as app_loader

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))
    for name, wert in _ENV.items():
        monkeypatch.setenv(name, wert)
    return _aufzeichner_installieren(monkeypatch)


def _orte(anzahl: int) -> list[SavedLocation]:
    return [SavedLocation(id=f"o3172-{i}", name=n, lat=47.27, lon=11.39, elevation_m=600)
            for i, n in enumerate(NAMEN[:anzahl])]


def _preset(uid: str, orte: list[SavedLocation]) -> dict:
    """Orte-Abo, SMS-Spalte nie eingestellt (volle Vorgabeliste), Versand per
    E-Mail, SMS und Premium-SMS."""
    return {
        "id": "cp-3172", "name": "Kueste", "user_id": uid,
        "location_ids": [o.id for o in orte], "schedule": "daily",
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16, "forecast_hours": 48,
        "empfaenger": ["gregor-test@henemm.com"], "created_at": "2026-07-01T00:00:00Z",
        "kind": "vergleich", "send_sms": True, "send_premium_sms": True,
        "alert_channels": {"email": True, "telegram": False, "sms": True, "premium_sms": True},
    }


def _beispiel_wetter(monkeypatch) -> None:
    """Wetterabruf -> fester Beispiel-Datensatz (``placements_beispiel``)."""
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod

    class BeispielEngine(ce_mod.ComparisonEngine):
        @staticmethod
        def run(*args, **kwargs):
            orte = kwargs.get("locations")
            if orte is None and args:
                orte = args[0]
            return pb.orte_ergebnis(list(orte or []))

    monkeypatch.setattr(ce_mod, "ComparisonEngine", BeispielEngine)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)


def _versand(uid: str, orte: list[SavedLocation], tmp_path) -> dict[str, list[str]]:
    from services.scheduler_dispatch_service import send_one_compare_preset

    gesehen: dict[str, list[str]] = {"sms": [], "premium_sms": []}
    send_one_compare_preset(
        _preset(uid, orte), Settings(), uid, str(tmp_path),
        all_locations_cache=orte, target_date=pb.TAG, tage_ab_ortstag=0,
        mail_sink=lambda **k: None, sms_sink=gesehen["sms"].append,
        premium_sms_sink=gesehen["premium_sms"].append,
    )
    return gesehen


def test_f001_versand_premium_ueber_153_neu_gerendert_sms_behaelt_160(env, monkeypatch, tmp_path):
    """Ein Ort, volle Liste: die SMS hat 154..160 Zeichen (Vorbedingung), die
    Premium-SMS ist der mit 153 neu gerenderte Text -- nicht der SMS-Text."""
    _beispiel_wetter(monkeypatch)
    uid = _nutzer(_kennung())
    orte = _orte(1)

    gesehen = _versand(uid, orte, tmp_path)

    assert len(gesehen["sms"]) == 1 and len(gesehen["premium_sms"]) == 1, gesehen
    sms, premium = gesehen["sms"][0], gesehen["premium_sms"][0]
    assert PREMIUM_MAX < len(sms) <= 160, f"Vorbedingung SMS 154..160: {len(sms)} {sms!r}"
    assert len(premium) <= PREMIUM_MAX, (len(premium), premium)
    assert premium != sms, "Premium-SMS bekam den zu langen SMS-Text"
    assert sms.startswith(premium.rsplit(" ", 1)[0]), (sms, premium)
    # Orakel: derselbe Baustein mit demselben Kontext wie der Versand.
    kontext = aufbau.compare_wetter_laden(_preset(uid, orte), orte, pb.TAG, uid,
                                          report_type="morning")
    assert premium == aufbau.compare_premium_sms_rendern(kontext, sms)


def test_f001_versand_premium_unter_153_ist_der_sms_text(env, monkeypatch, tmp_path):
    """Gegenprobe: passt die SMS in 153 Zeichen (drei Orte, kuerzere Zeilen),
    bekommt die Premium-SMS denselben Text."""
    _beispiel_wetter(monkeypatch)
    uid = _nutzer(_kennung())

    gesehen = _versand(uid, _orte(3), tmp_path)

    sms = gesehen["sms"][0]
    assert len(sms) <= PREMIUM_MAX, f"Vorbedingung SMS <= 153: {len(sms)} {sms!r}"
    assert gesehen["premium_sms"] == [sms]


def test_f001_send_compare_report_sendet_premium_text_ueber_premium_kanal(env):
    """``premium_sms_text`` geht ueber den Premium-Transport, ``sms_text`` ueber
    den SMS-Transport -- kein Kanal bekommt den Text des anderen."""
    uid = _nutzer(_kennung())
    svc = NotificationService(settings=Settings(), user_id=uid)

    ergebnis = svc.send_compare_report(
        subject="Ortsvergleich", html_body="<p>H</p>", text_body="T", telegram_text="TG",
        sms_text="O1 D15/19 W30@10(43@16) LANG", premium_sms_text="O1 D15/19 KURZ",
        recipients=["to@example.invalid"], effective_channels={"email", "sms", "premium_sms"},
    )

    assert "premium_sms" in ergebnis.sent_channels, ergebnis
    assert env.je_kanal["premium_sms"] == ["O1 D15/19 KURZ"], env.je_kanal
    assert env.je_kanal["sms"] == ["O1 D15/19 W30@10(43@16) LANG"], env.je_kanal


# ---------------------------------------------------------------------------
# F003: Grenzen 153/154 der Premium-Regel
# ---------------------------------------------------------------------------

def _kontext_ein_ort() -> dict:
    orte = _orte(1)
    preset = {"id": "p", "name": "P", "location_ids": [o.id for o in orte], "display_config": {}}
    from app.ampel import profile_for_template, template_id_for
    from services.report_config_resolver import resolve_compare_render_options

    return {"preset": preset, "result": pb.orte_ergebnis(orte),
            "profile": profile_for_template(template_id_for(preset)),
            "opts": resolve_compare_render_options(preset), "name": "P", "target_date": pb.TAG}


@pytest.mark.parametrize("laenge", [PREMIUM_MAX - 1, PREMIUM_MAX])
def test_f003_premium_bis_153_derselbe_text(laenge):
    """Text mit 152/153 Zeichen geht unveraendert als Premium-SMS (nicht neu
    gerendert) -- faengt ``grenze - 1``."""
    sms = ("O1 " + "D15/19 " * 30)[:laenge]
    assert len(sms) == laenge
    assert aufbau.compare_premium_sms_rendern(_kontext_ein_ort(), sms) == sms


def test_f003_premium_ab_154_neu_gerendert():
    """Text mit 154 Zeichen wird mit 153 neu gerendert (Renderer-Text, nicht
    der uebergebene)."""
    sms = ("O1 " + "D15/19 " * 30)[:PREMIUM_MAX + 1]
    premium = aufbau.compare_premium_sms_rendern(_kontext_ein_ort(), sms)
    assert premium != sms and len(premium) <= PREMIUM_MAX and premium.startswith("O1 D"), premium
