"""Issue #1563 — Nachtrag zu den Adversary-Testluecken F001, F002, F004.

SPEC: docs/specs/modules/feat_1563_compare_vertretungshinweis.md (R5, AC-3,
AC-11)

Kern-Schicht, netzfrei, ohne Mock-Theater: echte ``LocationResult`` /
``ComparisonResult`` / ``ForecastMeta``, echte Renderer, fuer F004 der echte
Briefing-Versand ``send_one_compare_preset`` mit echtem Fake-Provider in der
echten Provider-Registry und der vorgesehenen Premium-SMS-Senke.

- F001: ein Ortsname mit HTML-Markup erscheint im HTML-Hinweis maskiert
  (geprueft OHNE ``html.unescape``, sonst waere die Maskierung unsichtbar).
- F002: Telegram-Langform mit Hinweis UND Ueberlauf: der Hinweis steht am
  Ende, die Gesamtlaenge bleibt im Limit, die Kuerzung ist ausgewiesen.
- F004: Premium-SMS (derselbe ``sms_text`` wie die SMS, ADR-0049) traegt
  keinen Hinweis und bleibt innerhalb von 160 Zeichen.
"""
from __future__ import annotations
from tests.helpers.ampel_allgemein import PRESET_ALLGEMEIN

import html as _html
import threading
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.fallback_notice import build_fallback_lines

GEWITTER_FELD = "lightning_density_per_km2_3h"


def _meta(vertretung: bool = True, kollision: bool = False) -> ForecastMeta:
    kw: dict = {}
    if vertretung:
        metriken = ["temperature_2m", GEWITTER_FELD] if kollision else ["temperature_2m"]
        kw = dict(fallback_model="icon_eu", fallback_metrics=metriken,
                  fallback_reason="metric_gap")
    return ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2",
                        grid_res_km=2.2, **kw)


def _lr(name: str, idx: int, meta=None) -> LocationResult:
    base = datetime(2026, 11, 5, 9, tzinfo=timezone.utc)
    hourly = [ForecastDataPoint(ts=base + timedelta(hours=h), t2m_c=4.0 + h,
                                wind10m_kmh=10.0, gust_kmh=20.0,
                                cloud_total_pct=40, precip_1h_mm=0.0)
              for h in range(8)]
    loc = SavedLocation(id=f"loc-{idx}", name=name, lat=45.0 + idx * 0.01, lon=11.0,
                        elevation_m=1000 + idx, timezone="Europe/Vienna")
    return LocationResult(location=loc, score=0, temp_min=4.0, temp_max=11.0,
                          wind_max=10.0, gust_max=20.0, cloud_avg=40,
                          hourly_data=hourly, forecast_meta=meta)


def _result(lrs: list) -> ComparisonResult:
    return ComparisonResult(locations=lrs, time_window=(9, 16),
                            target_date=date(2026, 11, 5),
                            created_at=datetime(2026, 11, 4, 6, 0))


# ------------------------------------------------------------------- F001

def test_f001_ortsname_mit_markup_erscheint_im_html_hinweis_maskiert():
    from output.renderers.email.compare_html import render_compare_html

    name = "<script>alert(1)</script>"
    res = _result([_lr("Innsbruck", 1), _lr(name, 2, _meta())])
    roh = render_compare_html(res, show_fallback_notice=True, preset=PRESET_ALLGEMEIN)  # bewusst KEIN unescape
    zeile = f"{name}: {build_fallback_lines(_meta(), lang='de')[0]}"
    assert name not in roh, "Roh-Markup des Ortsnamens darf nie im HTML stehen"
    assert _html.escape(zeile) in roh, "Hinweiszeile muss maskiert im HTML stehen"
    assert "&lt;script&gt;" in roh


# ------------------------------------------------------------------- F002

def _ueberlauf_ergebnis() -> ComparisonResult:
    # Zwei betroffene Orte (je zwei Hinweiszeilen) stehen alphabetisch vorn und
    # bleiben damit sichtbar; dahinter so viele Orte, dass 4096 Zeichen reissen.
    lrs = [_lr("Aachkopf", 0, _meta(kollision=True)),
           _lr("Abendspitze", 1, _meta(kollision=True))]
    lrs += [_lr(f"Ort Nummer {i:03d} im Ueberlauf", i) for i in range(2, 160)]
    return _result(lrs)


def test_f002_telegram_hinweis_bleibt_bei_ueberlauf_am_ende_und_im_limit():
    from output.renderers.channel_layout import CHANNEL_LIMITS
    from output.renderers.comparison import render_compare_telegram
    from output.renderers.fallback_notice import build_compare_fallback_lines

    max_chars = CHANNEL_LIMITS["telegram"]["max_chars"]
    res = _ueberlauf_ergebnis()
    ohne = render_compare_telegram(res)
    zeilen = build_compare_fallback_lines(res.locations, lang="de")
    assert len(zeilen) == 4, "Testannahme: zwei Orte mit je zwei Zeilen"
    trailer = "\n".join(zeilen)
    # Vorbedingung: ohne Hinweis wird bereits gekuerzt, die Luecke zum Limit
    # ist kleiner als der Hinweis (sonst bewiese der Test die Abzugsregel nicht).
    assert len(ohne) <= max_chars and max_chars - len(ohne) < len(trailer)

    tg = render_compare_telegram(res, show_fallback_notice=True)
    assert len(tg) <= max_chars, f"Telegram-Limit gerissen: {len(tg)} > {max_chars}"
    assert tg.endswith(trailer), "Hinweis muss als Abschluss am Ende stehen"
    from i18n import t
    assert any(t("vergleich.telegram.uebersprungen", "de", n=k) in tg
               for k in range(1, len(res.locations))), "Kuerzung muss ausgewiesen sein"


# ------------------------------------------------------------------- F004

SEEFELD_LAT = 47.3297


class _VertretungProvider:
    """Echter Fake-Provider: Seefeld traegt Gewitter- UND Wetter-Vertretung."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "openmeteo"

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble: bool = True, enrich_snow: bool = True):
        anchor = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        data = [ForecastDataPoint(ts=anchor + timedelta(hours=i), t2m_c=3.0 + i % 7,
                                  wind10m_kmh=10.0, gust_kmh=20.0,
                                  cloud_total_pct=30, precip_1h_mm=0.0, pop_pct=10)
                for i in range(24 * 6)]
        betroffen = abs(location.latitude - SEEFELD_LAT) < 1e-6
        meta = _meta(vertretung=betroffen, kollision=True)
        meta.run = anchor
        return NormalizedTimeseries(meta=meta, data=data)


@pytest.fixture
def provider(monkeypatch):
    import providers.base as registry

    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    if not registry._PROVIDER_FACTORIES:
        registry._load_providers()
    p = _VertretungProvider()
    monkeypatch.setitem(registry._PROVIDER_FACTORIES, "openmeteo", lambda: p)
    return p


def test_f004_premium_sms_des_briefings_ohne_hinweis_und_hoechstens_160(provider):
    from app.config import Settings
    from app.loader import get_data_root, save_location
    from services.scheduler_dispatch_service import send_one_compare_preset
    from tests.helpers.compare_briefings import write_compare_briefings
    from tests.tdd._einstellung_auslieferung_fixtures import frisches_profil

    uid = frisches_profil(tier="premium")
    orte = [SavedLocation(id="loc-ibk", name="Innsbruck", lat=47.2692, lon=11.4041,
                          elevation_m=574, timezone="Europe/Vienna"),
            SavedLocation(id="loc-see", name="Seefeld", lat=SEEFELD_LAT, lon=11.1880,
                          elevation_m=1180, timezone="Europe/Vienna")]
    for loc in orte:
        save_location(loc, user_id=uid)
    preset = {
        "id": "cp-1563-psms", "name": "Premium-Vergleich", "user_id": uid,
        "location_ids": [o.id for o in orte], "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "official_alerts_enabled": False,
        "send_premium_sms": True, "alert_channels": [],
        "day_window_start_hour": 9, "day_window_end_hour": 16,
        "created_at": "2026-11-05T00:00:00Z",
    }
    write_compare_briefings(get_data_root() / "users" / uid, [preset])
    mails: list[str] = []
    premium: list[str] = []
    send_one_compare_preset(
        dict(preset), Settings(mail_to="empfaenger@example.com"), uid,
        str(get_data_root()), all_locations_cache=list(orte),
        mail_sink=lambda subject, body, plain_body=None: mails.append(body),
        sms_sink=lambda *a, **kw: None, telegram_sink=lambda *a, **kw: None,
        premium_sms_sink=premium.append, on_demand=True, lang="de",
    )
    zeilen = build_fallback_lines(_meta(kollision=True), lang="de")
    assert len(zeilen) == 2
    # Gegenprobe: die Vertretung ist im Lauf angekommen (die Mail traegt sie).
    assert f"Seefeld: {zeilen[0]}" in _html.unescape(mails[0])
    assert len(premium) == 1, "Premium-SMS muss im Briefing versendet werden"
    sms = premium[0]
    assert len(sms) <= 160
    assert "Seefeld: " not in sms
    for z in zeilen:
        assert z not in sms
