"""Hinweis-Bausteine der Trip-Briefing-Mail zweisprachig (Issue #2665, AC-4).

SPEC: docs/specs/modules/i18n_p3_briefing_compact_plain_2665.md

Echte Aufrufe der geteilten Bausteine in beiden Sprachen: Starkregen,
"Warnungen nicht abrufbar", "nicht zugestellt" (beide Bloecke, Gruende,
Ausloeser, Rest-Zeile), Ausblick-Zustand (n = 1 und n = 3) und Ersatzquelle.
Deutsch muss wortgleich zu heute bleiben -- die Erwartungen unten sind die
woertlichen Texte vor der Umstellung.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.models import OutlookState
from tests.helpers.briefing_compact_plain_fixture import vorfaelle

TZ = ZoneInfo("Europe/Paris")


# --------------------------------------------------------------------------- #
# Starkregen
# --------------------------------------------------------------------------- #
def _zeit(minuten: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minuten)).astimezone(TZ).strftime("%H:%M")


def test_starkregen_englisch_alle_teilsaetze():
    from output.renderers.email.starkregen_hint import format_starkregen_hint

    text = format_starkregen_hint("Heavy rain", 200, tz=TZ, event_end_minutes=250,
                                  source_reach_minutes=170, lang="en")
    assert text.startswith(f"Heavy rain from about {_zeit(200)} (in ~200 min)"), text
    assert f", last rain around {_zeit(250)}" in text
    assert f" · radar reaches until {_zeit(170)}" in text
    assert " · location imprecise from " in text and text.endswith(".")
    laeuft = format_starkregen_hint("Heavy rain", None, tz=TZ, already_running=True,
                                    event_end_minutes=60, event_ongoing_beyond_horizon=True,
                                    lang="en")
    assert laeuft == f"Heavy rain already running, rain at least until {_zeit(60)}."


def test_starkregen_deutsch_wortgleich():
    from output.renderers.email.starkregen_hint import format_starkregen_hint

    text = format_starkregen_hint("Starker Regen", 200, tz=TZ, event_end_minutes=250,
                                  source_reach_minutes=170)
    assert text.startswith(f"Starker Regen ab ca. {_zeit(200)} (in ~200 Min), letzter Regen gegen ")
    assert " · Radar reicht bis " in text and " · Ortsangabe ab " in text and " unscharf." in text
    assert format_starkregen_hint("Starker Regen", None, tz=TZ, already_running=True,
                                  event_end_minutes=60, event_ongoing_beyond_horizon=True,
                                  lang="de") == f"Starker Regen läuft bereits, Regen mindestens bis {_zeit(60)}."


# --------------------------------------------------------------------------- #
# Warnungen nicht abrufbar
# --------------------------------------------------------------------------- #
def test_nicht_abrufbar_englisch_und_deutsch():
    from output.renderers.email.unavailable_hint import (
        render_official_alerts_unavailable_html as html,
        render_official_alerts_unavailable_plain as plain,
    )

    assert plain(lang="en") == "⚠️ Official warnings are currently unavailable — please check yourself."
    assert plain(ascii_safe=True, lang="en").startswith("!! Official warnings")
    assert "Official warnings currently unavailable</strong>" in html(lang="en")
    assert "Bitte" not in html(lang="en") and "Warndienst" not in html(lang="en")
    assert plain() == "⚠️ Amtliche Warnungen aktuell nicht abrufbar — bitte selbst pruefen."
    assert plain(lang="de") == plain()
    assert html(lang="de") == html()
    assert "Amtliche Warnungen aktuell nicht abrufbar</strong>" in html()


# --------------------------------------------------------------------------- #
# Nicht zugestellt
# --------------------------------------------------------------------------- #
def test_nicht_zugestellt_englisch_bloecke_gruende_rest():
    from output.renderers.email.undelivered_hint import (
        render_undelivered_html, render_undelivered_plain,
    )

    text = render_undelivered_plain(vorfaelle(), tz=TZ, lang="en")
    zeilen = text.split("\n")
    assert zeilen[0] == "FAILED — something went wrong"
    assert zeilen[1] == "  28.10. 10:00 · Rain radar · E-Mail, Premium-SMS · Delivery failed"
    assert "HELD BACK — as you set it up" in zeilen
    for teil in ("Gusts · Telegram · Quiet hours", "Weather change · Telegram · Cooldown",
                 "Official warning · Telegram · Daily limit", "below your threshold",
                 "  … and 2 more"):
        assert teil in text, (teil, text)
    html = render_undelivered_html(vorfaelle(), tz=TZ, lang="en")
    assert "FAILED — something went wrong</strong>" in html and "… and 2 more</div>" in html
    ascii_text = render_undelivered_plain(vorfaelle(), tz=TZ, ascii_safe=True, lang="en")
    assert ascii_text.isascii() and "HELD BACK - as you set it up" in ascii_text


def test_nicht_zugestellt_deutsch_wortgleich():
    from output.renderers.email.undelivered_hint import (
        HEADING_FAILED, HEADING_WITHHELD, render_undelivered_html, render_undelivered_plain,
    )

    text = render_undelivered_plain(vorfaelle(), tz=TZ)
    assert text == render_undelivered_plain(vorfaelle(), tz=TZ, lang="de")
    assert render_undelivered_html(vorfaelle(), tz=TZ) == render_undelivered_html(
        vorfaelle(), tz=TZ, lang="de")
    assert HEADING_FAILED == "FEHLGESCHLAGEN — da ist etwas schiefgegangen"
    assert HEADING_WITHHELD == "ZURÜCKGEHALTEN — so hast du es eingestellt"
    zeilen = text.split("\n")
    assert zeilen[:2] == [HEADING_FAILED,
                          "  28.10. 10:00 · Regenradar · E-Mail, Premium-SMS · Versand fehlgeschlagen"]
    for teil in ("Böen · Telegram · Stille Stunden", "Wetteränderung · Telegram · Cooldown",
                 "Amtliche Warnung · Telegram · Tageslimit", "unter deiner Schwelle",
                 "  … und 2 weitere"):
        assert teil in text, (teil, text)


def test_nicht_zugestellt_unbekannter_code_bleibt_roh():
    from output.renderers.email.undelivered_hint import render_undelivered_plain
    from services.alert_log import UndeliveredIncident

    inc = UndeliveredIncident(at=datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc),
                              channels=("sms",), reasons=("neuer_code",), metrics=(),
                              hazards=(), trigger="nowcast")
    assert render_undelivered_plain([inc], tz=TZ, lang="en").endswith("· SMS · neuer_code")


# --------------------------------------------------------------------------- #
# Ausblick-Zustand
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("n,en,de", [
    (1, "Next stage is too far ahead (max. 1 day).",
     "Nächste Etappe liegt zu weit voraus (max. 1 Tage)."),
    (3, "Next stage is too far ahead (max. 3 days).",
     "Nächste Etappe liegt zu weit voraus (max. 3 Tage)."),
])
def test_ausblick_zustand_plural(n, en, de):
    from output.renderers.email.outlook_state_hint import outlook_state_text

    assert outlook_state_text(OutlookState.BEYOND_HORIZON, n, lang="en") == en
    assert outlook_state_text(OutlookState.BEYOND_HORIZON, n) == de
    assert outlook_state_text(OutlookState.BEYOND_HORIZON, n, lang="de") == de


def test_ausblick_zustand_uebrige_zustaende_und_kanalformen():
    from output.renderers.email.outlook_state_hint import (
        outlook_state_text, render_outlook_state_html, render_outlook_state_plain,
    )

    assert outlook_state_text(OutlookState.NO_STAGES, lang="en") == "No further stages — no outlook."
    assert outlook_state_text(OutlookState.UNAVAILABLE, lang="en") == "Forecast currently unavailable."
    assert outlook_state_text(OutlookState.FOUND, lang="en") == ""
    assert render_outlook_state_plain(OutlookState.UNAVAILABLE, ascii_safe=True, lang="en") == (
        "!! Forecast currently unavailable.")
    html = render_outlook_state_html(OutlookState.UNAVAILABLE, lang="en")
    assert "Outlook</strong>" in html and "Forecast currently unavailable." in html
    assert "Ausblick</strong>" in render_outlook_state_html(OutlookState.UNAVAILABLE)
    assert outlook_state_text(OutlookState.NO_STAGES) == "Keine weiteren Etappen — kein Ausblick."
    assert outlook_state_text(OutlookState.UNAVAILABLE) == "Vorhersage derzeit nicht abrufbar."


# --------------------------------------------------------------------------- #
# Ersatzquelle
# --------------------------------------------------------------------------- #
def _meta(metriken, modell, grund="model_error"):
    return SimpleNamespace(fallback_metrics=metriken, fallback_model=modell, fallback_reason=grund)


def test_ersatzquelle_englisch():
    from output.renderers.fallback_notice import build_fallback_lines as fb

    assert fb(_meta(["lightning_density_per_km2_3h"], "icon_eu", "x"), lang="en") == [
        "Thunderstorm data from a backup source (coarser resolution)",
        "Some weather values from backup model: DWD Europa",
    ]
    assert fb(_meta(["lightning_density_per_km2_3h"], "ecmwf_ifs04",
                    "thunder_source_unavailable"), lang="en") == [
        "Thunderstorm data from backup source: ECMWF (coarser resolution)",
    ]
    assert fb(_meta(["wind_gusts_10m", "weather_code", "foo"], "at_direct"), lang="en") == [
        "Some weather values from backup model: GeoSphere Österreich (Wind gusts, Weather pattern, foo)",
    ]


def test_ersatzquelle_deutsch_wortgleich():
    from output.renderers.fallback_notice import build_fallback_lines as fb

    assert fb(_meta(["lightning_density_per_km2_3h"], "icon_eu", "x")) == [
        "Gewitterdaten von einer Ersatzquelle (gröbere Auflösung)",
        "Einzelne Wetterwerte von Ersatzmodell: DWD Europa",
    ]
    assert fb(_meta(["lightning_density_per_km2_3h"], "ecmwf_ifs04",
                    "thunder_source_unavailable"), lang="de") == [
        "Gewitterdaten von Ersatzquelle: ECMWF (gröbere Auflösung)",
    ]
    assert fb(_meta(["wind_gusts_10m", "weather_code", "foo"], "at_direct")) == [
        "Einzelne Wetterwerte von Ersatzmodell: GeoSphere Österreich (Böen, Wetterlage, foo)",
    ]
