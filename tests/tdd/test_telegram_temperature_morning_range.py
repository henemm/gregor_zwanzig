"""Telegram-Kurzuebersicht: gemessene Temperatur zeigt morgens eine Spanne.

Spec:  docs/specs/modules/trip_min_temp_and_felt_shortforms.md (AC-12)
Issue: #1410 — Epic #1372, Scheibe 2 zu #1357 S4a

Der Morgen-Sonderzweig in ``narrow._overview_line()`` zeigt heute nur den
Hoechstwert. Mit PO-Entscheidung F1 entfaellt er: morgens erscheint die
kaelteste Gehzeit-Stunde als Untergrenze. Nachweis ueber
``TripReportFormatter.format_email()``, das intern
``narrow.render_telegram_bubbles()`` aufruft — derselbe Weg wie im Versand.
Keine Mocks, keine Dateiinhalt-Pruefungen.
"""
from __future__ import annotations

import re

import pytest

from output.renderers.trip_report import TripReportFormatter

from tests.tdd import _min_temp_felt_fixtures as F

_SPAN = re.compile(r"^T (?P<lo>-?\d+\.\d)-(?P<hi>-?\d+\.\d)@(?P<hour>\d{1,2})$")


def _report(report_type: str):
    return TripReportFormatter().format_email(
        [F.segment()],
        trip_name="Issue1410",
        report_type=report_type,
        night_weather=F.night_weather(),
        display_config=F.dc("temperature"),
        stage_name=F.STAGE_NAME,
        tz=F.TZ,
    )


class TestAC12MeasuredOverviewShowsRangeInMorning:
    """AC-12: Given ein Trip mit Morgenbriefing / When das Telegram-Briefing
    gerendert wird / Then zeigt die Kurzuebersicht-Zeile der gemessenen
    Temperatur eine Tiefst-Hoechst-Spanne mit der kaeltesten Gehzeit-Stunde
    (3 °C) als Untergrenze — nicht mehr nur den Hoechstwert (20 °C)."""

    def test_measured_overview_shows_range_in_morning(self):
        report = _report("morning")
        line = F.overview_line(report, "T")

        assert line, (
            "Die Telegram-Kurzuebersicht enthaelt keine Temperatur-Zeile.\n"
            f"Bubble:\n{F.overview_bubble(report)}"
        )
        m = _SPAN.match(line)
        assert m is not None, (
            f"Die morgendliche Temperatur-Zeile lautet {line!r} und zeigt "
            "keine Tiefst-Hoechst-Spanne mit Spitzenstunde, sondern "
            "weiterhin nur einen Einzelwert.\n"
            f"Bubble:\n{F.overview_bubble(report)}"
        )
        assert float(m.group("lo")) == F.HIKE_MIN_C, (
            f"Untergrenze ist {m.group('lo')} statt {F.HIKE_MIN_C} "
            f"(kaelteste Gehzeit-Stunde, lokal {F.COLD_HOUR}:00).\n"
            f"Zeile: {line!r}"
        )
        assert float(m.group("hi")) == F.HIKE_MAX_C, (
            f"Obergrenze ist {m.group('hi')} statt {F.HIKE_MAX_C}.\n"
            f"Zeile: {line!r}"
        )
        assert int(m.group("hour")) == F.WARM_HOUR, (
            f"Spitzenstunde ist {m.group('hour')} statt {F.WARM_HOUR}.\n"
            f"Zeile: {line!r}"
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
