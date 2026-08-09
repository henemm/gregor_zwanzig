"""Telegram-Kurzuebersicht: Zeile der gefuehlten Temperatur.

Spec:  docs/specs/modules/trip_min_temp_and_felt_shortforms.md (AC-10, AC-11)
Issue: #1410 — Epic #1372, Scheibe 2 zu #1357 S4a

AC-10 sichert BESTEHENDES Verhalten ab (die Zeile existiert heute schon,
ist aber durch keinen Test belegt) und ist deshalb bewusst GRUEN — sie darf
nicht mehr unbemerkt wegbrechen. AC-11 ist RED: abends muss die Untergrenze
die echte gefuehlte Nachttemperatur am Ziel sein, und morgens muss die Zeile
dieselbe Gestalt haben wie die gemessene.

Nachweis ueber ``TripReportFormatter.format_email()``, das intern
``narrow.render_telegram_bubbles()`` mit den echten Stundentabellen aufruft
— derselbe Weg wie im Versand. Keine Mocks, keine Dateiinhalt-Pruefungen.
"""
from __future__ import annotations

import re

import pytest

from output.renderers.trip_report import TripReportFormatter

from tests.tdd import _min_temp_felt_fixtures as F

# '{Kuerzel} {Min}-{Max}@{Spitzenstunde}' — die Gestalt einer Spannen-Zeile.
_SPAN = re.compile(r"^(?P<label>\S+) (?P<lo>-?\d+\.\d)-(?P<hi>-?\d+\.\d)@(?P<hour>\d{1,2})$")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _report(report_type: str):
    # #1660 Scheibe A: die abendliche Untergrenze der TF-Zeile haengt jetzt
    # an der eigenen Groesse "wind_chill_night" -- ohne sie faellt sie still
    # auf den Gehzeit-Tiefstwert zurueck (F.dc() baut MetricConfig direkt,
    # ohne die Bestandsableitung des Ladepfads).
    return TripReportFormatter().format_email(
        [F.segment()],
        trip_name="Issue1410",
        report_type=report_type,
        night_weather=F.night_weather(),
        display_config=F.dc("temperature", "wind_chill", "wind_chill_night"),
        stage_name=F.STAGE_NAME,
        tz=F.TZ,
    )


def _skeleton(line: str) -> str:
    """Gestalt einer Kurzuebersicht-Zeile ohne Kuerzel und ohne Zahlen."""
    body = line.split(" ", 1)[1] if " " in line else ""
    return _NUMBER.sub("#", body)


class TestAC10FeltOverviewLinePresent:
    """AC-10: Given ein Trip mit aktivierter „Gefuehlte Temperatur" / When das
    Telegram-Briefing gerendert wird / Then zeigt die Kurzuebersicht-Zeile
    fuer die gefuehlte Temperatur Minimum, Maximum und die Spitzenstunde.

    Absicherung eines bereits bestehenden Verhaltens (heute gruen)."""

    def test_felt_overview_line_present(self):
        report = _report("morning")
        line = F.overview_line(report, "TF")

        assert line, (
            "Die Telegram-Kurzuebersicht enthaelt keine Zeile fuer die "
            "gefuehlte Temperatur, obwohl die Metrik im Trip aktiviert ist.\n"
            f"Bubble:\n{F.overview_bubble(report)}"
        )
        m = _SPAN.match(line)
        assert m is not None, (
            f"Die Zeile der gefuehlten Temperatur lautet {line!r} und zeigt "
            "nicht Minimum, Maximum und Spitzenstunde in der Form "
            "'TF {min}-{max}@{h}'.\n"
            f"Bubble:\n{F.overview_bubble(report)}"
        )
        assert float(m.group("lo")) == F.FELT_HIKE_MIN_C, (
            f"Minimum der gefuehlten Temperatur ist {m.group('lo')} statt "
            f"{F.FELT_HIKE_MIN_C}.\nZeile: {line!r}"
        )
        assert float(m.group("hi")) == F.FELT_HIKE_MAX_C, (
            f"Maximum der gefuehlten Temperatur ist {m.group('hi')} statt "
            f"{F.FELT_HIKE_MAX_C}.\nZeile: {line!r}"
        )
        assert int(m.group("hour")) == F.WARM_HOUR, (
            f"Spitzenstunde ist {m.group('hour')} statt {F.WARM_HOUR}.\n"
            f"Zeile: {line!r}"
        )


class TestAC11FeltOverviewRangeMorningAndNightValueEvening:
    """AC-11: Given ein Trip mit aktivierter „Gefuehlte Temperatur" / When das
    Telegram-Briefing fuer Morgen UND Abend gerendert wird / Then zeigt die
    Kurzuebersicht-Zeile der gefuehlten Temperatur in BEIDEN Report-Typen
    eine Tiefst-Hoechst-Spanne — morgens mit der kaeltesten Gehzeit-Stunde
    (1 °C) als Untergrenze, abends mit der echten gefuehlten Nachttemperatur
    am Ziel (9 °C) —, exakt symmetrisch zur gemessenen Temperaturzeile."""

    _EXPECTED_LOW = {
        "morning": F.FELT_HIKE_MIN_C,
        "evening": F.FELT_NIGHT_MIN_C,
    }

    def test_felt_overview_shows_range_morning_and_night_value_evening(self):
        lines = {
            rt: (F.overview_line(r, "TF"), F.overview_line(r, "T"))
            for rt, r in ((rt, _report(rt)) for rt in self._EXPECTED_LOW)
        }

        # 1. Spanne und Untergrenze je Report-Typ.
        for report_type, expected_low in self._EXPECTED_LOW.items():
            felt_line, _ = lines[report_type]
            m = _SPAN.match(felt_line)
            assert m is not None, (
                f"[{report_type}] Die Zeile der gefuehlten Temperatur lautet "
                f"{felt_line!r} und zeigt keine Tiefst-Hoechst-Spanne."
            )
            assert float(m.group("lo")) == expected_low, (
                f"[{report_type}] Untergrenze der gefuehlten Temperatur ist "
                f"{m.group('lo')} statt {expected_low}. Abends muss es die "
                f"echte gefuehlte Nachttemperatur am Ziel sein "
                f"({F.FELT_NIGHT_MIN_C}), morgens die kaelteste "
                f"Gehzeit-Stunde ({F.FELT_HIKE_MIN_C}).\n"
                f"Zeile: {felt_line!r}"
            )
            assert float(m.group("hi")) == F.FELT_HIKE_MAX_C, (
                f"[{report_type}] Obergrenze der gefuehlten Temperatur ist "
                f"{m.group('hi')} statt {F.FELT_HIKE_MAX_C}.\n"
                f"Zeile: {felt_line!r}"
            )
        # 2. Symmetrie zur gemessenen Temperaturzeile (gleiche Gestalt).
        for report_type in self._EXPECTED_LOW:
            felt_line, measured_line = lines[report_type]
            assert _skeleton(felt_line) == _skeleton(measured_line), (
                f"[{report_type}] Die gefuehlte Temperaturzeile "
                f"({felt_line!r}) hat eine andere Gestalt als die gemessene "
                f"({measured_line!r}) — beide muessen sich gleich verhalten."
            )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
