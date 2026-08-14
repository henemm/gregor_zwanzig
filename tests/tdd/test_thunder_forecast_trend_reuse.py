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

from datetime import date, datetime, timedelta, timezone

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
            # Issue #1474: die Render-Skala ist additiv um LOW erweitert
            # (thunder_label_value: NONE=0, LOW=1, MED=2, HIGH=3) -- HIGH
            # traegt seither den Wert 3, nicht mehr 2.
            "hourly_thunder": (
                HourlyValue(hour=2, value=0.0),
                HourlyValue(hour=4, value=3.0),
                HourlyValue(hour=6, value=3.0),
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
            None, _TARGET, now_utc=datetime.now(timezone.utc), tz=None,
            multi_day_trend=_trend_rows(),
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
               (kein Index-Fehlgriff, der die +2-Zeile fälschlich als +1 nähme).
               Die fehlende +1-Etappe löst den Fallback-Fetch aus, der ohne
               Trip-Objekt seit #1498 (Fall 2) fail-soft leer bleibt — vorher
               diente dessen AttributeError-Crash als Sonde; die Eigenschaft
               beweist sich jetzt direkt am Ergebnis.
        """
        rest_day_trend = [
            {
                "date": _TARGET + timedelta(days=2),
                "weekday": "Fr",
                "name": "Nach Ruhetag",
                "thunder": "HIGH",
                # Issue #1474: Render-Skala {NONE:0, LOW:1, MED:2, HIGH:3} --
                # HIGH traegt den Wert 3 (2.0 war die Vor-#1474-Skala).
                "hourly_thunder": (HourlyValue(hour=15, value=3.0),),
            },
        ]
        fc = TripReportSchedulerService()._build_thunder_forecast_from_trend_or_fetch(
            None, _TARGET, now_utc=datetime.now(timezone.utc), tz=None,
            multi_day_trend=rest_day_trend,
        )
        assert "+1" not in fc, (
            f"+2-Zeile wurde als +1 verwechselt (Index- statt Datums-Match): {fc!r}"
        )
        expected = (_TARGET + timedelta(days=2)).strftime("%d.%m.%Y")
        assert fc["+2"]["date"] == expected
        assert fc["+2"]["level"] == ThunderLevel.HIGH
        assert fc["+2"]["hour"] == 15
