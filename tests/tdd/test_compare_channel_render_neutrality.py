"""TDD RED — Issue #1270 / Spec docs/specs/modules/compare_channel_preview_dispatch.md

Test 3 (AC-3): Die neuen Kanal-Renderer `render_compare_telegram` /
`render_compare_sms` duerfen weder Rang noch Punktzahl je Ort zeigen. Score
bleibt ausschliesslich interne Sortiergroesse (`comparison_engine.py:185,229`);
#1110 hat Score/Winner aus dem Compare-Mail-Vertrag entfernt — die neuen
Kanaele duerfen das nicht regressieren (KB-5).

RED-Grund: `render_compare_telegram`/`render_compare_sms` existieren in
`src/output/renderers/comparison.py` nicht → ImportError.

KEINE Mocks: echte, synthetische `ComparisonResult`-Objekte (Muster
tests/tdd/test_compare_render_options_resolver.py::_make_comparison_result)
gehen direkt in die echten Renderer — kein Netz, keine Fixtures noetig.

Robustheit der Score-Suche: die drei Orte tragen Punktzahlen (97/64/31), die
in KEINEM Wetterwert dieser Fixture vorkommen (Temperaturen 12.5/13.5/14.5,
Wind 8, Boeen 15, Bewoelkung 30, Sonne 5, Zeitfenster 9-16, Datum 08.07.2026).
Gesucht wird auf Zahl-Grenzen, nicht per naivem Substring — sonst schluege der
Test auf beliebigen Wetterzahlen an.
"""
from __future__ import annotations

import re
from datetime import date, datetime

import pytest

from app.models import ForecastDataPoint, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation

TARGET_DATE = date(2026, 7, 8)

# Punktzahlen, die in keinem Wetterwert dieser Fixture auftauchen (s. Docstring).
SCORES = (97, 64, 31)

# Rang-Marker: "#1"/"#2", Listen-Nummerierung "1. " am Zeilenanfang, sowie die
# Rang-/Score-Vokabeln aus dem abgeschafften Modell (CompareChatBubble/
# CompareSmsPreview, #578) und dem Alt-Renderer vor #1110 (Pokal-Badge).
_RANK_PATTERNS = [
    (r"#\s*[1-9]\b", "Platzierungs-Marker '#N'"),
    (r"(?m)^\s*[1-9]\.\s", "Listen-Rang-Nummerierung 'N.' am Zeilenanfang"),
    (r"🏆", "Gewinner-Pokal"),
    (r"(?i)\bgewinner\b", "Gewinner-Hervorhebung"),
    (r"(?i)\bplatz\s*[1-9]\b", "Platzierungs-Text"),
    (r"(?i)\brang\b", "Rang-Angabe"),
    (r"(?i)\bscore\b", "Score-Beschriftung"),
    (r"(?i)\bpunkte?\b", "Punktzahl-Beschriftung"),
]


def _loc(loc_id: str, name: str) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=47.27, lon=11.39, elevation_m=1000)


def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour, 0),
        t2m_c=13.5,
        wind_chill_c=12.5,
        wind10m_kmh=8.0,
        gust_kmh=15.0,
        precip_1h_mm=0.0,
        cloud_total_pct=30,
        uv_index=4.0,
        thunder_level=ThunderLevel.NONE,
        pop_pct=10,
        visibility_m=9000,
    )


def _result_three_locations() -> ComparisonResult:
    """Drei Orte mit klar unterschiedlicher Score-Reihenfolge — damit ein
    Rang-/Score-Regress ueberhaupt sichtbar werden KANN."""
    names = ["Innsbruck", "Bozen", "Klagenfurt"]
    locations = [
        LocationResult(
            location=_loc(f"loc-{i}", name),
            score=SCORES[i],
            temp_max=12.5 + i,
            temp_min=5.5,
            wind_max=8.0,
            gust_max=15.0,
            cloud_avg=30,
            sunny_hours=5,
            official_alerts=[],
            hourly_data=[_dp(9), _dp(12), _dp(15)],
        )
        for i, name in enumerate(names)
    ]
    return ComparisonResult(
        locations=locations,
        time_window=(9, 16),
        target_date=TARGET_DATE,
        created_at=datetime(2026, 7, 8, 4, 0),
    )


def _assert_neutral(text: str, channel: str) -> None:
    assert text.strip(), f"{channel}-Render darf nicht leer sein"
    for score in SCORES:
        assert not re.search(rf"(?<!\d){score}(?!\d)", text), (
            f"AC-3: Die Punktzahl {score} eines Ortes erscheint im {channel}-Text "
            f"— Score ist ausschliesslich interne Sortiergroesse (#1110). Text: {text[:400]!r}"
        )
    for pattern, label in _RANK_PATTERNS:
        assert not re.search(pattern, text), (
            f"AC-3: {label} im {channel}-Text gefunden — kein Rang, keine "
            f"Gewinner-Hervorhebung erlaubt. Text: {text[:400]!r}"
        )


def _flatten(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "\n".join(_flatten(v) for v in value)
    return str(value)


def test_compare_telegram_render_shows_no_rank_and_no_score():
    """GIVEN ein ComparisonResult mit drei Orten unterschiedlicher Punktzahl
    WHEN render_compare_telegram gerendert wird
    THEN enthaelt der Text weder Rang- noch Score-Marker (Orte bleiben nur
    inhaltlich unterscheidbar).

    RED: render_compare_telegram existiert nicht (ImportError)."""
    from output.renderers.comparison import render_compare_telegram

    text = _flatten(render_compare_telegram(_result_three_locations()))
    _assert_neutral(text, "Telegram")
    for name in ("Innsbruck", "Bozen", "Klagenfurt"):
        assert name in text, f"Ort '{name}' fehlt im Telegram-Text (Inhalt statt Ranking)"


def test_compare_sms_render_shows_no_rank_and_no_score():
    """GIVEN ein ComparisonResult mit drei Orten unterschiedlicher Punktzahl
    WHEN render_compare_sms gerendert wird
    THEN enthaelt die Nachricht weder Rang- noch Score-Marker.

    RED: render_compare_sms existiert nicht (ImportError)."""
    from output.renderers.comparison import render_compare_sms

    text = _flatten(render_compare_sms(_result_three_locations()))
    _assert_neutral(text, "SMS")


@pytest.mark.parametrize("renderer_name", ["render_compare_telegram", "render_compare_sms"])
def test_channel_render_is_order_insensitive_about_ranking(renderer_name):
    """GIVEN dasselbe Orts-Set, einmal in umgekehrter Score-Reihenfolge
    WHEN der Kanal-Renderer laeuft
    THEN bleibt der Output in beiden Faellen rang-/score-frei — die interne
    Sortierung darf sich nicht als sichtbares Ranking niederschlagen.

    RED: die Renderer existieren nicht (ImportError)."""
    import output.renderers.comparison as mod

    renderer = getattr(mod, renderer_name)
    result = _result_three_locations()
    reversed_result = ComparisonResult(
        locations=list(reversed(result.locations)),
        time_window=result.time_window,
        target_date=result.target_date,
        created_at=result.created_at,
    )
    _assert_neutral(_flatten(renderer(reversed_result)), renderer_name)
