"""Issue #1563 — Vertretungshinweis an den echten Aufrufern (AC-8, Adversary-Fund 1).

SPEC: docs/specs/modules/feat_1563_compare_vertretungshinweis.md (R6, AC-8)

Die Renderer-Tests belegen den Schalter ``show_fallback_notice`` nur am
Renderer. Hier wird die Zusicherung dort geprueft, wo sie WIRKT: am echten
Briefing-Versand (``send_one_compare_preset``, E-Mail HTML + Klartext und
Telegram-Langform) und an der echten Briefing-Vorschau
(``ComparePreviewService.render_all_channels``).

Kern-Schicht, netzfrei, ohne Mock-Theater: ein echter Fake-Provider (erfuellt
das ``WeatherProvider``-Protokoll) haengt in der echten Provider-Registry
(Muster ``test_compare_preview_second_call_uses_cache``); nur Seefeld liefert
eine Vertretung. Transport ueber die vorgesehenen Senken des Versandpfads.

Alarm-Pfade (``compare_official_alert``, ``compare_alert_preview_service``)
rufen die Compare-Renderer gar nicht auf und tragen kein ``forecast_meta``;
ein Test dort waere strukturell nie rot (siehe Report).
"""
from __future__ import annotations

import html as _html
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider

ORTE = [
    ("loc-innsbruck", "Innsbruck", 47.2692, 11.4041, 574),
    ("loc-seefeld", "Seefeld", 47.3297, 11.1880, 1180),
]
SEEFELD_LAT = 47.3297
PRESET_ID = "cp-1563"


def _meta(vertretung: bool) -> ForecastMeta:
    anchor = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    kw = dict(fallback_model="icon_eu", fallback_metrics=["temperature_2m"],
              fallback_reason="metric_gap") if vertretung else {}
    return ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2",
                        grid_res_km=2.2, run=anchor, **kw)


class SeefeldVertretungProvider:
    """Liefert fuer Seefeld eine Zeitreihe mit Vertretung, sonst ohne."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.call_count = 0

    @property
    def name(self) -> str:
        return "openmeteo"

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble: bool = True, enrich_snow: bool = True):
        with self._lock:
            self.call_count += 1
        anchor = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        data = [ForecastDataPoint(ts=anchor + timedelta(hours=i), t2m_c=3.0 + i % 7,
                                  wind10m_kmh=10.0, gust_kmh=20.0,
                                  cloud_total_pct=30, precip_1h_mm=0.0, pop_pct=10)
                for i in range(24 * 6)]
        vertretung = abs(location.latitude - SEEFELD_LAT) < 1e-6
        return NormalizedTimeseries(meta=_meta(vertretung), data=data)


@pytest.fixture
def provider(monkeypatch):
    import providers.base as registry

    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    if not registry._PROVIDER_FACTORIES:
        registry._load_providers()
    p = SeefeldVertretungProvider()
    monkeypatch.setitem(registry._PROVIDER_FACTORIES, "openmeteo", lambda: p)
    return p


def _hinweiszeile() -> str:
    from output.renderers.fallback_notice import build_fallback_lines

    zeilen = build_fallback_lines(_meta(True), lang="de")
    assert zeilen, "Testannahme: die Seefeld-Meta traegt eine Vertretung"
    return f"Seefeld: {zeilen[0]}"


def _lege_vergleich_an() -> tuple[str, dict, list]:
    from app.loader import get_data_root, save_location
    from app.user import SavedLocation
    from tests.helpers.compare_briefings import write_compare_briefings

    uid = f"nutzer-1563-{uuid.uuid4().hex[:8]}"
    orte = [SavedLocation(id=i, name=n, lat=lat, lon=lon, elevation_m=e,
                          timezone="Europe/Vienna") for i, n, lat, lon, e in ORTE]
    for loc in orte:
        save_location(loc, user_id=uid)
    preset = {
        "id": PRESET_ID, "name": "Vertretungs-Vergleich", "user_id": uid,
        "location_ids": [loc.id for loc in orte], "schedule": "daily",
        "weekday": 4, "profil": "ALLGEMEIN",
        "empfaenger": ["gregor-test@henemm.com"],
        "official_alerts_enabled": False, "send_telegram": True,
        "day_window_start_hour": 9, "day_window_end_hour": 16,
        "created_at": "2026-11-05T00:00:00Z",
    }
    write_compare_briefings(get_data_root() / "users" / uid, [preset])
    return uid, preset, orte


def test_briefing_versand_mail_und_telegram_tragen_hinweis(provider):
    from app.config import Settings
    from app.loader import get_data_root
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid, preset, orte = _lege_vergleich_an()
    mails: list[dict] = []
    telegramme: list[str] = []
    send_one_compare_preset(
        dict(preset),
        Settings(mail_to="empfaenger@example.com", telegram_bot_token="tok-1563",
                 telegram_chat_id="1563"),
        uid, str(get_data_root()), all_locations_cache=list(orte),
        mail_sink=lambda subject, body, plain_body=None: mails.append(
            {"html": body, "text": plain_body}),
        sms_sink=lambda *a, **kw: None,
        telegram_sink=telegramme.append,
        premium_sms_sink=lambda *a, **kw: None,
        on_demand=True, lang="de",
    )
    zeile = _hinweiszeile()
    assert provider.call_count >= 1
    assert len(mails) == 1 and len(telegramme) == 1
    assert zeile in _html.unescape(mails[0]["html"]), "HTML-Teil der Briefing-Mail"
    assert zeile in mails[0]["text"], "Klartext-Teil der Briefing-Mail"
    assert zeile in telegramme[0], "Telegram-Langform des Briefings"
    for ausgabe in (_html.unescape(mails[0]["html"]), mails[0]["text"], telegramme[0]):
        assert "Innsbruck: " not in ausgabe


def test_briefing_vorschau_zeigt_hinweis_wie_der_versand(provider):
    from services.compare_preview_service import ComparePreviewService

    uid, _preset, _orte = _lege_vergleich_an()
    vorschau = ComparePreviewService().render_all_channels(PRESET_ID, user_id=uid)
    zeile = _hinweiszeile()
    assert zeile in _html.unescape(vorschau["email_html"]), "E-Mail-Vorschau"
    assert zeile in vorschau["telegram"], "Telegram-Vorschau"
    assert zeile not in vorschau["sms"], "SMS bleibt ohne Hinweis (AC-11)"
