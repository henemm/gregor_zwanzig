"""Issue #1268 (AC-5) — die Compare-Kanal-Renderer drucken kein Zeitfenster.

Spec: docs/specs/modules/issue_1268_compare_timewindow_removal.md § AC-5

Kontext:
  Mit #1268 ist das Bewertungsfenster keine Einstellung mehr, sondern fest der
  ganze Tag (`time_window=(0, 23)`, scheduler_dispatch_service.py:321). Der
  Klartext-Renderer (`render_comparison_text`) und der HTML-Kopf
  (`compare_html._render_header`) haben ihre Zeitfenster-Angabe deshalb bereits
  verloren. Die mit #1270 hinzugekommenen Kanal-Renderer
  `render_compare_telegram`/`render_compare_sms` drucken sie noch — dort stuende
  jetzt dauerhaft "Zeitfenster: 00:00 - 23:00" bzw. "00-23h:": eine
  Nicht-Information, die bei der SMS zusaetzlich 8 der 140 Zeichen frisst, die
  fuer echte Messwerte fehlen.

RED-Erwartung (vor Fix):
  comparison.py:299-301 (Telegram) und comparison.py:404-407 (SMS) formatieren
  `result.time_window` in den Kopf -> beide Tests rot.

KEINE Mocks: echte, synthetische `ComparisonResult`-Objekte gehen direkt in die
echten Renderer (Muster: tests/tdd/test_compare_channel_overflow.py).
"""
from __future__ import annotations

import re
from datetime import date, datetime

import pytest

from app.models import ForecastDataPoint, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation

TARGET_DATE = date(2026, 7, 8)

# Jede Uhrzeit-/Stundenfenster-Schreibweise, die die Renderer erzeugen koennten:
# "09:00 - 16:00", "00:00 - 23:00", "09-16h", "00-23h".
_TIME_WINDOW_PATTERNS = (
    re.compile(r"\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}"),
    re.compile(r"\d{1,2}\s*[-–]\s*\d{1,2}\s*h", re.IGNORECASE),
    re.compile(r"Zeitfenster", re.IGNORECASE),
)


def _result(time_window: tuple[int, int]) -> ComparisonResult:
    dp = ForecastDataPoint(
        ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, 12, 0),
        t2m_c=21.0,
        wind_chill_c=20.0,
        wind10m_kmh=9.0,
        gust_kmh=16.0,
        precip_1h_mm=0.0,
        cloud_total_pct=25,
        uv_index=5.0,
        thunder_level=ThunderLevel.NONE,
        pop_pct=10,
        visibility_m=9000,
    )
    return ComparisonResult(
        locations=[
            LocationResult(
                location=SavedLocation(
                    id="loc-ibk", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574
                ),
                score=80,
                temp_max=21.0,
                temp_min=11.0,
                wind_max=9.0,
                gust_max=16.0,
                cloud_avg=25,
                sunny_hours=6,
                official_alerts=[],
                hourly_data=[dp],
            )
        ],
        time_window=time_window,
        target_date=TARGET_DATE,
        created_at=datetime(2026, 7, 8, 4, 0),
    )


def _assert_no_time_window(text: str, channel: str) -> None:
    for pattern in _TIME_WINDOW_PATTERNS:
        match = pattern.search(text)
        assert match is None, (
            f"AC-5: Die {channel}-Nachricht nennt ein Zeitfenster "
            f"({match.group(0)!r}). Mit #1268 ist die Bewertung fest der ganze "
            f"Tag — die Angabe waere dauerhaft '00-23' und damit eine "
            f"Nicht-Information. Text: {text!r}"
        )


@pytest.mark.parametrize("time_window", [(0, 23), (9, 16)])
def test_telegram_render_has_no_time_window_line(time_window):
    """GIVEN ein Vergleichsergebnis (mit festem Ganztags-Fenster wie im Versand
    ODER mit einem Alt-Fenster aus einem Bestands-Preset)
    WHEN render_compare_telegram rendert
    THEN enthaelt die Nachricht keine Zeitfenster-Zeile.

    Beide Parameter, damit die Angabe nachweislich ENTFERNT und nicht nur auf
    einen unauffaelligen Wert gebracht ist.

    RED vor Fix: der Kopf traegt f"Zeitfenster: {..:02d}:00 - {..:02d}:00"."""
    from output.renderers.comparison import render_compare_telegram

    text = render_compare_telegram(_result(time_window), preset_name="Urlaubsorte")

    assert "Innsbruck" in text, "Fixture trifft nicht — der Ort muss gerendert sein"
    _assert_no_time_window(text, "Telegram")


@pytest.mark.parametrize("time_window", [(0, 23), (9, 16)])
def test_sms_render_has_no_time_window_in_head(time_window):
    """GIVEN ein Vergleichsergebnis
    WHEN render_compare_sms rendert
    THEN enthaelt der Kopf keine Stundenfenster-Angabe.

    RED vor Fix: der Kopf traegt f"{..:02d}-{..:02d}h:"."""
    from output.renderers.comparison import render_compare_sms

    text = render_compare_sms(_result(time_window))

    assert "Innsbruck" in text, "Fixture trifft nicht — der Ort muss gerendert sein"
    _assert_no_time_window(text, "SMS")


def test_sms_head_stays_within_budget_and_names_the_date():
    """GIVEN ein Vergleichsergebnis
    WHEN render_compare_sms rendert
    THEN bleibt der Kopf eine sinnvolle Ueberschrift: er nennt weiterhin das
    Datum und die SMS haelt ihr 140-Zeichen-Budget.

    Sichert, dass die Zeitfenster-Entfernung nicht versehentlich die
    Datumsangabe mitnimmt (der Kopf muss sagen, worum es geht)."""
    from output.renderers.channel_layout import CHANNEL_LIMITS
    from output.renderers.comparison import render_compare_sms

    text = render_compare_sms(_result((0, 23)))

    assert "08.07." in text, f"Das Datum muss im SMS-Kopf bleiben: {text!r}"
    assert len(text) <= CHANNEL_LIMITS["sms"]["max_chars"]
