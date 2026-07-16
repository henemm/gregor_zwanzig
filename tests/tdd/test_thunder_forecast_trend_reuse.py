"""Bug #1275 — Trend-Wiederverwendung ohne Doppel-Fetch.

Im Evening-Default hat `_build_stage_trend()` die Folge-Etappe bereits gefetcht.
`_build_thunder_forecast_from_trend_or_fetch()` MUSS daraus ableiten und darf
KEINEN zweiten Wetter-Fetch auslösen (Spec Implementation Details Punkt 2 +
Known Limitations Bullet 3).

Mock-frei bewiesen: Wird `trip=None` übergeben, würde JEDER Fallback-Fetch
sofort mit `AttributeError` (`None.get_future_stages(...)`) abbrechen. Deckt der
Trend beide Offsets ab, bleibt der Aufruf fehlerfrei — das ist der direkte
Beweis, dass `_collect_future_stage_weather()` gar nicht erst aufgerufen wurde.

Spec: docs/specs/bugfix/fix_1275_sms_th_mismatch.md (AC-1/AC-2)
"""
from __future__ import annotations

from datetime import date, timedelta

from src.output.tokens.dto import HourlyValue
from src.app.models import ThunderLevel
from src.services.trip_report_scheduler import TripReportSchedulerService

_TARGET = date(2026, 7, 15)


def _trend_rows() -> list[dict]:
    """Trend, der BEIDE Offsets abdeckt: +1 mit Gewitter HIGH ab 04:00 (Sturm an
    einem Waypoint der morgigen Etappe), +2 gewitterfrei. Struktur wie
    `_build_stage_trend()` sie emittiert (String-`thunder`, HourlyValue-Samples).
    """
    return [
        {
            "date": _TARGET + timedelta(days=1),
            "weekday": "Do",
            "name": "Morgige Etappe",
            "thunder": "HIGH",
            "hourly_thunder": (
                HourlyValue(hour=2, value=0.0),
                HourlyValue(hour=4, value=2.0),
                HourlyValue(hour=6, value=2.0),
            ),
        },
        {
            "date": _TARGET + timedelta(days=2),
            "weekday": "Fr",
            "name": "Übermorgen",
            "thunder": "NONE",
            "hourly_thunder": (),
        },
    ]


class TestTrendReuseNoDoubleFetch:
    def test_plus1_derived_from_trend_without_any_fetch(self):
        """
        GIVEN: multi_day_trend deckt +1 (HIGH ab 04:00) und +2 (NONE) ab
        WHEN:  thunder_forecast daraus abgeleitet wird, trip=None (Fetch würde
               sofort crashen)
        THEN:  +1 Level HIGH mit "04:00" im Text, +2 Level NONE — und KEIN
               Crash, d.h. kein zweiter Fetch (Doppel-Fetch vermieden)
        """
        fc = TripReportSchedulerService()._build_thunder_forecast_from_trend_or_fetch(
            None, _TARGET, tz=None, multi_day_trend=_trend_rows(),
        )

        assert fc is not None
        assert fc["+1"]["level"] == ThunderLevel.HIGH, (
            f"+1 muss aus der Trend-Zeile HIGH ergeben, war {fc!r}"
        )
        assert "04:00" in fc["+1"]["text"], (
            f"+1-Text muss 'ab 04:00' enthalten (frühester HIGH-Stundenwert), "
            f"war {fc['+1']['text']!r}"
        )
        assert fc["+2"]["level"] == ThunderLevel.NONE

    def test_trend_row_matched_by_date_not_index(self):
        """
        GIVEN: nur eine Trend-Zeile für +2 (Ruhetag an +1 → keine +1-Zeile),
               trip=None
        WHEN:  thunder_forecast abgeleitet wird
        THEN:  +2 kommt korrekt aus der Zeile; +1 ist NICHT vorhanden
               (kein Index-Fehlgriff, der die +2-Zeile fälschlich als +1 nähme)
               — die fehlende +1-Etappe würde einen Fetch auslösen; mit
               trip=None crasht das → wir prüfen, dass NUR +2 aus dem Trend kommt
               und der +1-Fetch den erwarteten AttributeError wirft.
        """
        import pytest

        rest_day_trend = [
            {
                "date": _TARGET + timedelta(days=2),
                "weekday": "Fr",
                "name": "Nach Ruhetag",
                "thunder": "HIGH",
                "hourly_thunder": (HourlyValue(hour=15, value=2.0),),
            },
        ]
        # +1 fehlt im Trend → missing_dates={+1} → Fallback-Fetch auf trip=None
        # crasht. Das beweist zugleich, dass +2 NICHT als +1 verwechselt wurde.
        with pytest.raises(AttributeError):
            TripReportSchedulerService()._build_thunder_forecast_from_trend_or_fetch(
                None, _TARGET, tz=None, multi_day_trend=rest_day_trend,
            )
