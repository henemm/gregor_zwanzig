"""Deterministische SMS-Fixtures fuer beide Sprachen (Issue #2670, i18n P8).

SPEC: docs/specs/modules/i18n_p8_sms_freitext_2670.md (Abschnitt "Waechter").

Feste Zeit 2026-10-29T06:00+02:00 (Segmente aus der Telegram-Golden-Fixture
von P7), ein Abweichungs-Alarm, ein Regen-Alarm mit Tagesversatz und ein
Ortsvergleich mit zwoelf Orten. Echte Modellobjekte, echte Renderer, netzfrei.

``mit_sprache`` reicht ``lang`` nur an Erzeuger durch, die den Parameter
schon kennen (Alarm-SMS kommt mit P5 #2667, Ortsvergleich-SMS mit P4 #2666).
Der Rueckgabewert sagt, ob die Sprache wirklich angekommen ist, damit ein
Test den englischen Teil sichtbar ueberspringt statt still gruen zu sein.
"""
from __future__ import annotations

import inspect
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.alert.model import AlertEvent, AlertMessage, OnsetEvent
from output.renderers.sms_trip import SMSTripFormatter
from tests.helpers.telegram_briefing_fixture import TZ, _alert, _segment

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden" / "sms_sprachen"

ORTE = ["Zillertal", "Innsbruck", "Stubai", "Seefeld", "Achensee", "Kufstein",
        "Lienz", "Imst", "Landeck", "Reutte", "Schwaz", "Hall"]


def segmente() -> list:
    return [_segment(1, (0.0, 8.4), (7, 12), [_alert()]),
            _segment("Ziel", (8.4, 14.2), (12, 16), [_alert()])]


def trip_sms(lang: str, stage_name: str | None = None, report_type: str = "evening",
             formatter: SMSTripFormatter | None = None) -> str:
    fmt = formatter or SMSTripFormatter()
    return fmt.format_sms(segmente(), stage_name=stage_name,
                          report_type=report_type, tz=TZ, lang=lang)


def golden(name: str, lang: str) -> str:
    return (GOLDEN_DIR / f"{name}.{lang}.txt").read_text(encoding="utf-8").rstrip("\n")


def abweichungs_alarm() -> AlertMessage:
    return AlertMessage(trip_short="GR20", stand_at="06:00", events=(
        AlertEvent(metric_id="wind", value_from=20, value_to=55, threshold=40,
                   cmp="über", occurred_at="14:00", km_from=3.0, km_to=8.4),
        AlertEvent(metric_id="gust", value_from=30, value_to=80, threshold=60,
                   cmp="über", occurred_at="15:00", km_from=3.0, km_to=8.4),
    ))


def regen_alarm_morgen() -> AlertMessage:
    return AlertMessage(trip_short="GR20", stand_at="06:00", source="radar", events=(
        OnsetEvent(onset_minutes=1500, onset_time="15:00", km_from=2.0, km_to=6.0,
                   is_convective=False, intensity_label="mäßig", source_label="Radar",
                   onset_day_offset=1, onset_weekday="Do"),
    ))


def _ort(i: int, name: str) -> LocationResult:
    return LocationResult(
        location=SavedLocation(id=f"o{i}", name=name, lat=47.0, lon=11.0,
                               elevation_m=600),
        score=1, temp_max=20.0 + i, temp_min=10.0, wind_max=15.0, gust_max=25.0,
        cloud_avg=40, sunny_hours=5,
    )


def vergleich_zwoelf_orte() -> ComparisonResult:
    return ComparisonResult(
        locations=[_ort(i, n) for i, n in enumerate(ORTE)], time_window=(0, 23),
        target_date=date(2026, 10, 29), created_at=datetime(2026, 10, 29, 4, 0),
    )


def mit_sprache(fn: Callable[..., str], *args, lang: str, **kwargs) -> tuple[str, bool]:
    """``(text, sprache_angekommen)``; ``lang`` nur, wenn ``fn`` ihn kennt."""
    if "lang" in inspect.signature(fn).parameters:
        return fn(*args, lang=lang, **kwargs), True
    return fn(*args, **kwargs), lang == "de"
