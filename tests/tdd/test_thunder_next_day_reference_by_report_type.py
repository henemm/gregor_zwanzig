"""Regression-Anker — Issue #1319 Scheibe E: `TH+:`-Bezugstag pro Report-Typ.

Verankert das (durch Ist-Analyse bestätigt korrekte) Verhalten der Kette
``report_type -> _get_target_date -> "+1"-Offset -> Kalendertag``:

- Morgenbriefing: ``_get_target_date("morning")`` liefert HEUTE, also zeigt
  ``thunder_forecast["+1"]`` auf HEUTE+1 (morgen).
- Abendbriefing: ``_get_target_date("evening")`` liefert HEUTE+1, also zeigt
  ``thunder_forecast["+1"]`` auf HEUTE+2 (übermorgen).

Kein bestehender Test prüft diese komplette Kette End-to-End (nur den
isolierten Trend-Match, s. ``test_thunder_forecast_trend_reuse.py``, oder das
Rendering mit fest injiziertem ``"+1"``, s.
``test_bug_874_th_plus_sms.py``). Diese Lücke schließt dieser Test.

Mock-frei: echter ``TripReportSchedulerService``-Aufruf auf
``_get_target_date`` und ``_build_thunder_forecast_from_trend_or_fetch``,
echte ``HourlyValue``/``ThunderLevel``-Objekte. ``trip=None`` ist sicher,
weil der Trend beide Offsets abdeckt (kein Fallback-Fetch nötig, siehe
``test_thunder_forecast_trend_reuse.py``).

Spec: Issue #1319 (Ist-Analyse, Scheibe E)
"""
from __future__ import annotations

from datetime import date, timedelta

from src.output.tokens.dto import HourlyValue
from src.app.models import ThunderLevel
from src.services.trip_report_scheduler import TripReportSchedulerService


def _trend_rows_for(target: date) -> list[dict]:
    """Trend-Zeilen fuer target+1 und target+2, beide mit Gewitter HIGH, damit
    der Match eindeutig am Kalenderdatum haengt (nicht am Index/Offset-Wert).
    """
    return [
        {
            "date": target + timedelta(days=1),
            "weekday": "Tag+1",
            "name": "Etappe target+1",
            "thunder": "HIGH",
            "hourly_thunder": (HourlyValue(hour=5, value=2.0),),
        },
        {
            "date": target + timedelta(days=2),
            "weekday": "Tag+2",
            "name": "Etappe target+2",
            "thunder": "HIGH",
            "hourly_thunder": (HourlyValue(hour=6, value=2.0),),
        },
    ]


class TestThunderNextDayReferenceByReportType:
    def test_morning_th_plus_refers_to_tomorrow(self):
        """
        GIVEN: report_type="morning" -> target_date = heute
        WHEN:  thunder_forecast aus dem Trend abgeleitet wird
        THEN:  fc["+1"]["date"] == (heute + 1 Tag) — morgen, NICHT uebermorgen
        """
        svc = TripReportSchedulerService()
        target = svc._get_target_date("morning")
        assert target == date.today(), (
            "Vorbedingung: morning-Zieltag muss heute sein"
        )

        fc = svc._build_thunder_forecast_from_trend_or_fetch(
            None, target, tz=None, multi_day_trend=_trend_rows_for(target),
        )

        expected = (target + timedelta(days=1)).strftime("%d.%m.%Y")
        assert fc["+1"]["date"] == expected, (
            f"Morgenbriefing: TH+ muss morgen ({expected}) referenzieren, "
            f"war {fc['+1']['date']!r}"
        )
        assert fc["+1"]["level"] == ThunderLevel.HIGH

    def test_evening_th_plus_refers_to_day_after_tomorrow(self):
        """
        GIVEN: report_type="evening" -> target_date = heute+1
        WHEN:  thunder_forecast aus dem Trend abgeleitet wird
        THEN:  fc["+1"]["date"] == (heute + 2 Tage) — uebermorgen
        """
        svc = TripReportSchedulerService()
        target = svc._get_target_date("evening")
        assert target == date.today() + timedelta(days=1), (
            "Vorbedingung: evening-Zieltag muss heute+1 sein"
        )

        fc = svc._build_thunder_forecast_from_trend_or_fetch(
            None, target, tz=None, multi_day_trend=_trend_rows_for(target),
        )

        expected = (target + timedelta(days=1)).strftime("%d.%m.%Y")
        assert fc["+1"]["date"] == expected, (
            f"Abendbriefing: TH+ muss uebermorgen ({expected}) referenzieren, "
            f"war {fc['+1']['date']!r}"
        )
        assert fc["+1"]["level"] == ThunderLevel.HIGH

    def test_evening_reference_day_is_exactly_one_day_later_than_morning(self):
        """
        Kern-Invariante: der TH+-Kalendertag im Abendbriefing liegt GENAU einen
        Tag spaeter als im Morgenbriefing (uebermorgen vs. morgen) — nicht
        gleich, nicht zwei Tage verschoben.
        """
        svc = TripReportSchedulerService()
        morning_target = svc._get_target_date("morning")
        evening_target = svc._get_target_date("evening")

        fc_morning = svc._build_thunder_forecast_from_trend_or_fetch(
            None, morning_target, tz=None,
            multi_day_trend=_trend_rows_for(morning_target),
        )
        fc_evening = svc._build_thunder_forecast_from_trend_or_fetch(
            None, evening_target, tz=None,
            multi_day_trend=_trend_rows_for(evening_target),
        )

        morning_th_plus_date = date(
            *reversed([int(p) for p in fc_morning["+1"]["date"].split(".")])
        )
        evening_th_plus_date = date(
            *reversed([int(p) for p in fc_evening["+1"]["date"].split(".")])
        )

        assert evening_th_plus_date - morning_th_plus_date == timedelta(days=1), (
            f"Abend-TH+ ({evening_th_plus_date}) muss genau einen Tag nach "
            f"Morgen-TH+ ({morning_th_plus_date}) liegen"
        )
