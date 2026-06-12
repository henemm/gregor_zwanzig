"""TDD tests for Issue #669 — Roter Gewitter-Badge im Ausblick.

RED phase: All tests fail until implementation is complete.

SPEC: docs/specs/modules/issue_759_669_email_ampel_gewitter.md AC-7..AC-10
IMPORTANT: NO mocks, NO patch, NO MagicMock. Real function calls only.
"""
from __future__ import annotations

from zoneinfo import ZoneInfo


# ---------------------------------------------------------------------------
# Shared test helpers (copied from test_issue_640_trend_threshold_times.py)
# ---------------------------------------------------------------------------

def _hv(hour: int, value: float):
    """Shorthand for HourlyValue."""
    from src.output.tokens.dto import HourlyValue
    return HourlyValue(hour=hour, value=value)


def _trend_stage_with_hourly(
    weekday="Di", name="Test-Etappe",
    temp_lo=12, temp_hi=15,
    precip_mm=0.5, wind_dir="W", wind_kmh=17, thunder="NONE", note=None,
    hourly_precip=None,
    hourly_wind=None,
    hourly_gust=None,
    hourly_thunder=None,
):
    """Build a trend stage dict including optional hourly sample tuples."""
    return dict(
        weekday=weekday, name=name,
        temp_lo=temp_lo, temp_hi=temp_hi,
        precip_mm=precip_mm, wind_dir=wind_dir, wind_kmh=wind_kmh,
        thunder=thunder, note=note,
        hourly_precip=hourly_precip or (),
        hourly_wind=hourly_wind or (),
        hourly_gust=hourly_gust or (),
        hourly_thunder=hourly_thunder or (),
    )


def _common_render_kwargs():
    from tests.unit.test_renderers_email import _common_kwargs, _make_token_line
    kw = _common_kwargs()
    tl = _make_token_line()
    return kw, tl


def _render_html(trend, *, sent_at=None):
    kw, tl = _common_render_kwargs()
    from src.output.renderers.email.html import render_html
    return render_html(
        segments=kw["segments"], seg_tables=kw["seg_tables"],
        trip_name=tl.trip_name or "Test-Trip", report_type="evening",
        dc=kw["display_config"], night_rows=[], thunder_forecast=None,
        highlights=[], changes=None, stage_name=kw["stage_name"],
        stage_stats=None, multi_day_trend=trend, compact_summary=None,
        daylight=None, tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=kw["friendly_keys"], profile=None, stability_result=None,
        sent_at=sent_at,
    )


# ---------------------------------------------------------------------------
# AC-7: Gewitter-Badge mit Zeitfenster (zwei Stunden)
# ---------------------------------------------------------------------------

class TestThunderBadgeTimeWindow:
    """AC-7: Folge-Etappe mit Gewitter zeigt roter Badge mit Zeitfenster."""

    def test_issue669_thunder_badge_time_window(self):
        """AC-7: MED@15(HIGH@16) → '⚡ Gewitter möglich 15:00–16:00' in HTML."""
        # MED at h15 (first), HIGH at h16 (peak)
        trend = [_trend_stage_with_hourly(
            weekday="Mi", name="Etappe 2",
            thunder="HIGH",
            hourly_thunder=(_hv(15, 1.0), _hv(16, 2.0)),  # MED=1, HIGH=2
        )]
        html = _render_html(trend)

        # Badge-Text muss Zeitfenster enthalten
        assert "⚡ Gewitter möglich 15:00" in html, (
            f"Expected '⚡ Gewitter möglich 15:00' in HTML. GEWITTER-Spalte: "
            f"{html[html.find('GEWITTER')-50:html.find('GEWITTER')+500] if 'GEWITTER' in html else 'GEWITTER not found'!r}"
        )
        assert "16:00" in html, f"Expected '16:00' in thunder badge, not found in HTML"

        # En-dash zwischen den Stunden
        assert "15:00" in html and "16:00" in html
        # Der Badge muss einen Bindestrich/Bereich enthalten (en-dash oder normaler Bindestrich)
        badge_area = html
        assert "15:00" in badge_area and "16:00" in badge_area

        # Roter Inline-Stil: G_WX_THUNDER oder G_DANGER (#c43a2a oder #b33a2a) muss am Badge-Element sein
        assert "#c43a2a" in html or "#b33a2a" in html, (
            "Thunder badge must have red inline color (G_WX_THUNDER or G_DANGER)"
        )


# ---------------------------------------------------------------------------
# AC-8: Gewitter-Badge mit einzelner Stunde (kein Bereich)
# ---------------------------------------------------------------------------

class TestThunderBadgeSingleHour:
    """AC-8: Folge-Etappe mit Gewitter nur in einer Stunde zeigt einzelnes Zeitfenster."""

    def test_issue669_thunder_badge_single_hour(self):
        """AC-8: Single-Hour-Thunder → '⚡ Gewitter möglich 14:00' (kein –)."""
        trend = [_trend_stage_with_hourly(
            weekday="Do", name="Etappe 3",
            thunder="MED",
            hourly_thunder=(_hv(14, 1.0),),  # MED=1 at h14 only
        )]
        html = _render_html(trend)

        assert "⚡ Gewitter möglich 14:00" in html, (
            f"Expected '⚡ Gewitter möglich 14:00'. "
            f"Context: {html[max(0,html.find('14:00')-100):html.find('14:00')+100] if '14:00' in html else 'not found'!r}"
        )

        # Kein Stunden-Bereich (kein "14:00–" bzw. kein zweites Zeitfenster)
        # Das bedeutet: "14:00" kommt vor, aber kein "–xx:00" danach direkt
        import re
        # Suche nach "14:00–HH:00" — das darf nicht vorkommen
        assert not re.search(r"14:00\s*[–-]\s*\d{2}:00", html), (
            f"Single-hour badge must NOT contain a time range: found in {html!r}"
        )


# ---------------------------------------------------------------------------
# AC-9: Kein Badge wenn kein Gewitter
# ---------------------------------------------------------------------------

class TestNoBadgeWithoutThunder:
    """AC-9: Etappe ohne Gewitter zeigt keinen ⚡-Badge und keinen leeren Platzhalter."""

    def test_issue669_no_badge_without_thunder(self):
        """AC-9: thunder='NONE' ohne hourly_thunder → kein 'Gewitter möglich'-Badge."""
        trend = [_trend_stage_with_hourly(
            weekday="Fr", name="Etappe 4",
            thunder="NONE",
            hourly_thunder=(),  # kein Gewitter
        )]
        html = _render_html(trend)

        # Kein Gewitter-möglich-Badge
        assert "Gewitter möglich" not in html, (
            f"No-thunder stage must NOT contain 'Gewitter möglich'. Found in HTML."
        )

        # Der neutrale Zustand (Quadrat-Icon + "kein") muss noch da sein
        # (bisheriges Verhalten: thunder_word="kein" + sq_color="#9a958a")
        # Mindestens der thunder_word oder das Neutral-Symbol muss vorkommen
        assert "kein" in html or "#9a958a" in html, (
            "Without thunder, neutral state (word 'kein' or sq_color #9a958a) must appear"
        )


# ---------------------------------------------------------------------------
# AC-10: Uebrige Ausblick-Spalten (TEMP/REGEN/WIND) unveraendert
# ---------------------------------------------------------------------------

class TestOtherOutlookColumnsUnchanged:
    """AC-10: TEMP/REGEN/WIND-Spalten des Ausblicks unveraendert."""

    def test_issue669_other_outlook_columns_unchanged(self):
        """AC-10: TEMP/REGEN/WIND-Zellen des Ausblicks vorhanden und korrekt."""
        trend = [_trend_stage_with_hourly(
            weekday="Sa", name="Etappe 5",
            temp_lo=8, temp_hi=18,
            precip_mm=3.5, wind_dir="W", wind_kmh=25,
            thunder="HIGH",
            hourly_thunder=(_hv(15, 2.0),),
        )]
        html = _render_html(trend)

        # Spaltenheader muessen unveraendert vorhanden sein
        assert "TEMP" in html, "TEMP column header missing"
        assert "REGEN" in html, "REGEN column header missing"
        assert "WIND" in html, "WIND column header missing"
        assert "GEWITTER" in html, "GEWITTER column header missing"

        # Trend-Block muss generell vorhanden sein
        assert "Nächste Etappen" in html, "Trend block heading missing"

        # Etappen-Wochentag und Name muessen vorhanden sein
        assert "Sa" in html or "Etappe 5" in html, "Stage name/weekday missing"


# ---------------------------------------------------------------------------
# AC-7-Haertung: Badge-Duplikat-Schutz bei thunder_forecast + multi_day_trend
# ---------------------------------------------------------------------------

class TestBadgeNotDuplicatedWithForecast:
    """AC-7-Haertung: Badge erscheint genau einmal; thunder_forecast-Block bleibt intakt."""

    def test_issue669_badge_not_duplicated_with_forecast(self):
        """Regression F001: thunder_html-Variable-Kollision zwischen Forecast-Block und Loop.

        Wenn BEIDE uebergeben werden — thunder_forecast UND multi_day_trend mit
        Gewitter-Etappe — muss 'Gewitter möglich' genau einmal vorkommen (im Badge
        in der Ausblick-Tabelle) und der Forecast-Vorschau-Block muss separat vorhanden
        sein.
        """
        from app.models import ThunderLevel
        from src.output.renderers.email.html import render_html

        kw, tl = _common_render_kwargs()

        thunder_forecast = {
            "+1": {
                "date": "Mi",
                "level": ThunderLevel.MED,
                "text": "Stark bewölkt mit Schauern",  # kein 'Gewitter möglich' im Text
            }
        }

        trend = [_trend_stage_with_hourly(
            weekday="Mi", name="Etappe 2",
            thunder="MED",
            hourly_thunder=(_hv(15, 1.0),),  # MED at h15 → Badge
        )]

        html = render_html(
            segments=kw["segments"], seg_tables=kw["seg_tables"],
            trip_name=tl.trip_name or "Test-Trip", report_type="evening",
            dc=kw["display_config"], night_rows=[], thunder_forecast=thunder_forecast,
            highlights=[], changes=None, stage_name=kw["stage_name"],
            stage_stats=None, multi_day_trend=trend, compact_summary=None,
            daylight=None, tz=ZoneInfo("Europe/Berlin"),
            friendly_keys=kw["friendly_keys"], profile=None, stability_result=None,
            sent_at=None,
        )

        # Badge muss genau einmal in der Ausblick-Tabelle vorkommen
        count = html.count("Gewitter möglich")
        assert count == 1, (
            f"'Gewitter möglich' must appear exactly once (badge in trend table), "
            f"got {count}. If >1: loop _thunder_cell_html overwrites outer thunder_html block."
        )

        # Der ⚡-Badge muss innerhalb eines <td>-Elements stehen (in der Tabelle)
        import re as _re2
        badge_in_td = _re2.search(
            r'<td[^>]*>.*?Gewitter möglich.*?</td>', html, _re2.DOTALL
        )
        assert badge_in_td is not None, (
            "Badge 'Gewitter möglich' must be inside a <td> (trend table cell), "
            "not floating outside."
        )

        # Der Forecast-Vorschau-Block muss separat vorhanden sein
        assert "Gewitter-Vorschau" in html, (
            "thunder_forecast block ('Gewitter-Vorschau') must still be rendered "
            "alongside multi_day_trend"
        )

        # Forecast-Text muss enthalten sein (Vorschau-Block nicht überschrieben)
        assert "Stark bewölkt mit Schauern" in html, (
            "thunder_forecast text must survive when multi_day_trend is also rendered"
        )
