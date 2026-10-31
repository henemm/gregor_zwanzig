"""Deterministische Golden-Fixture des Ortsvergleichs (Issue #2666, Epic #2644).

SPEC: docs/specs/modules/i18n_p4_vergleichs_mail_2666.md (Golden-Fixture).

Drei Orte mit Werten plus ein Ort mit Abruffehler, feste Zeit
2026-10-29T06:00+02:00 (Uhr eingefroren, damit der Fuss "Naechster Versand"
stabil ist), Nutzer ``golden-de``. Die Fixture ruft die echten Renderer auf
(HTML, Klartext, Telegram, SMS); ``lang=None`` ruft sie OHNE ``lang`` auf --
so entstanden die deutschen Golden-Dateien mit dem Code vor der Umstellung.

Regeneration (nur bewusst!): ``uv run python -m tests.helpers.vergleichs_mail_fixture``
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from freezegun import freeze_time

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden" / "vergleichs_mail"
JETZT_UTC = "2026-10-29T04:00:00+00:00"
TRENNER = "\n----\n"
PRESET_NAME = "Golden-Vergleich"
ORTSNAMEN = ("Innsbruck", "Lienz", "Kufstein")

# Telegram/SMS-Auswahl: mehr als 7 Groessen (Platzmangel-Hinweis), darunter
# Gewitter und Niederschlagsart (Wortwerte).
KANAL_METRIKEN = [
    "temp_max", "precip_sum", "thunder_max", "precip_type", "gust_max",
    "pop_max", "wind_max", "freezing_level", "humidity_avg", "sunny_hours",
]


def _dp(ts: datetime, i: int, h: int, **extra):
    from app.models import ForecastDataPoint, PrecipType, ThunderLevel

    nass = h in (13, 14, 15)
    werte = dict(
        ts=ts, t2m_c=6.0 + i + (h - 8) * 0.5, wind_chill_c=3.0 + i,
        wind10m_kmh=10.0 + h, wind_direction_deg=200 + 10 * i, gust_kmh=22.0 + h + 5 * i,
        precip_1h_mm=(0.8 + i) if nass else 0.0, cloud_total_pct=30 + 3 * h,
        cloud_low_pct=10 + h, cloud_mid_pct=20 + h, cloud_high_pct=5 + h,
        humidity_pct=60 + h, dewpoint_c=1.0 + i, pressure_msl_hpa=1012.0 + i,
        uv_index=2.0 + (h % 3), pop_pct=70 if nass else 15, visibility_m=18000 - 500 * h,
        thunder_level=ThunderLevel.NONE, freezing_level_m=2400 + 50 * i,
        snowfall_limit_m=2100 + 50 * i, snow_depth_cm=None,
        precip_type=PrecipType.RAIN if nass else None,
    )
    if i == 1 and h in (14, 15):
        werte.update(thunder_level=ThunderLevel.MED if h == 14 else ThunderLevel.LOW,
                     cape_jkg=900.0, hail_flag=True,
                     thunder_level_signals=["cape", "blitzdichte"])
    if i == 2 and nass:
        werte.update(precip_type=PrecipType.SNOW if h == 13 else PrecipType.MIXED)
    werte.update(extra)
    return ForecastDataPoint(**werte)


def _incident():
    from datetime import timezone

    from services.alert_log import UndeliveredIncident

    return UndeliveredIncident(
        at=datetime(2026, 10, 28, 17, 30, tzinfo=timezone.utc), channels=("sms",),
        reasons=("quiet_hours",), metrics=(("wind", "max"),), hazards=(), trigger="forecast_change",
    )


def build_result(*, mit_fehlerort: bool = True):
    from app.user import ComparisonResult, LocationResult, SavedLocation

    orte = []
    for i, name in enumerate(ORTSNAMEN):
        ort = SavedLocation(id=f"golden-{i}", name=name, lat=47.27 - 0.3 * i,
                            lon=11.39 + 0.4 * i, elevation_m=574 + 100 * i,
                            timezone="Europe/Vienna")
        stunden = [_dp(datetime(2026, 10, 29, h - 1, 0), i, h) for h in range(8, 17)]
        ausblick = [] if i == 2 else [
            _dp(datetime(2026, 10, 30, 0, 0) + timedelta(days=d, hours=s), i, 8 + s // 2)
            for d in range(3) for s in range(0, 24, 3)
        ]
        orte.append(LocationResult(
            location=ort, temp_max=11.0 + i, temp_min=2.0 + i, wind_max=26.0, gust_max=38.0 + i,
            sunny_hours=4 + i, cloud_avg=45, official_alerts=[], hourly_data=stunden,
            outlook_hourly_data=ausblick, official_alerts_unavailable=(i == 0),
        ))
    if mit_fehlerort:
        orte.append(LocationResult(
            location=SavedLocation(id="golden-x", name="Brenner", lat=47.0, lon=11.5,
                                   elevation_m=1370, timezone="Europe/Vienna"),
            error="Zeitueberschreitung beim Abruf",
        ))
    return ComparisonResult(
        locations=orte, time_window=(9, 16), target_date=date(2026, 10, 29),
        created_at=datetime(2026, 10, 29, 4, 0),
    )


def _preset() -> dict:
    return {"id": "golden-preset", "name": PRESET_NAME, "weekday": None, "schedule": "daily",
            "location_ids": [f"golden-{i}" for i in range(len(ORTSNAMEN))]}


def _hourly_keys() -> list[str]:
    from output.renderers.email.compare_html import HOUR_METRICS

    return [m["key"] for m in HOUR_METRICS]


def _lang(lang):
    return {} if lang is None else {"lang": lang}


def render_mail(lang=None, result=None) -> tuple[str, str]:
    """(HTML, Klartext) ueber ``render_compare_email`` mit eingefrorener Uhr."""
    from app.profile import ActivityProfile
    from output.renderers.comparison import render_compare_email

    with freeze_time(JETZT_UTC):
        return render_compare_email(
            result or build_result(), profile=ActivityProfile.WANDERN,
            warnings=["Ort Brenner nicht erreichbar"], enabled_metrics=None,
            hourly_metrics=_hourly_keys(), hourly_enabled=True, preset_name=PRESET_NAME,
            outlook_enabled=True, outlook_metrics=None, undelivered=[_incident()],
            preset=_preset(), unresolved_count=1, **_lang(lang),
        )


def render_kanaele(lang=None, result=None) -> list[str]:
    """Telegram-Texte (voll, ohne Auswahl, ohne Orte) und zuletzt der SMS-Text."""
    from app.user import ComparisonResult
    from output.renderers.comparison import render_compare_sms, render_compare_telegram

    result = result or build_result()
    leer = ComparisonResult(locations=[], time_window=(9, 16), target_date=result.target_date,
                            created_at=result.created_at)
    return [
        render_compare_telegram(result, enabled_metrics=KANAL_METRIKEN, preset_name=PRESET_NAME,
                                unresolved_count=1, **_lang(lang)),
        render_compare_telegram(result, enabled_metrics=[], **_lang(lang)),
        render_compare_telegram(leer, **_lang(lang)),
        render_compare_sms(result, enabled_metrics=KANAL_METRIKEN, unresolved_count=1),
    ]


def golden_pfad(name: str) -> Path:
    return GOLDEN_DIR / name


def schreibe_golden(lang: str) -> list[Path]:
    """Schreibt die Golden-Dateien einer Sprache (``de`` ohne ``lang``-Argument)."""
    arg = None if lang == "de" else lang
    html, text = render_mail(arg)
    pfade = {
        f"ortsvergleich_3orte.{lang}.html": html,
        f"ortsvergleich_3orte.{lang}.txt": text,
        f"telegram_sms.{lang}.txt": TRENNER.join(render_kanaele(arg)),
    }
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name, inhalt in pfade.items():
        golden_pfad(name).write_text(inhalt, encoding="utf-8")
    return [golden_pfad(n) for n in pfade]


if __name__ == "__main__":
    import sys

    for sprache in sys.argv[1:] or ["de"]:
        for p in schreibe_golden(sprache):
            print(p)
