"""
Bug #353 — Mehrtages-Trend überschreitet Open-Meteo-Vorhersagehorizont.

SPEC: docs/specs/modules/bug_353_trend_forecast_horizon.md

Open-Meteo validiert ``start_date`` endpoint-übergreifend gegen ein globales
Fenster ``[today-92, today+15]`` (empirisch bestätigt 2026-05-25). Eine Etappe
jenseits ``today+15`` löst HTTP 400 aus — verschwendeter Call, ERROR-Rauschen,
leeres Trend-Segment. Der Fix prüft den Horizont PROAKTIV vor dem Call und
überspringt nicht-vorhersagbare Etappen (kein Call, kein Fehler, keine Zeile).

TDD-RED: Diese Tests MÜSSEN JETZT FEHLSCHLAGEN, weil ``is_within_forecast_horizon``
und ``OPENMETEO_MAX_FORECAST_DAYS`` in ``providers.openmeteo`` noch nicht
existieren (Import-Fehler → Collection-Error für die ganze Datei). Das ist gewollt.

KEINE Mocks (CLAUDE.md): Reine Funktion deterministisch + echte Trip-Objekte.
Da ferne Etappen (nach dem Fix) übersprungen werden, machen diese Tests im
GREEN-Zustand KEINEN Netzwerk-Call. Kein ``pytest.mark.live``.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

# RED: Dieser Import schlägt JETZT fehl (Symbole existieren noch nicht).
# Er gehört bewusst auf Modul-Ebene, damit die ganze Datei rot wird.
from providers.openmeteo import (
    OPENMETEO_MAX_FORECAST_DAYS,
    is_within_forecast_horizon,
)


# ---------------------------------------------------------------------------
# Helpers — KEINE Mocks
# ---------------------------------------------------------------------------

def _count_trend_calls() -> int:
    """Anzahl der Open-Meteo-Abrufe mit Quelle ``"trend"`` im Diagnose-JSONL.

    Mock-frei: liest den echten Call-Counter (#338,
    ``providers.call_log.DIAGNOSTICS_PATH``). Datei evtl. nicht vorhanden → 0.
    """
    import json

    from providers.call_log import DIAGNOSTICS_PATH

    if not DIAGNOSTICS_PATH.exists():
        return 0
    count = 0
    with DIAGNOSTICS_PATH.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("source") == "trend":
                count += 1
    return count


def _make_far_future_trip():
    """Echter Trip mit AUSSCHLIESSLICH fernen Etappen (>15 Tage in der Zukunft).

    Korsika-Koordinaten (42.0/9.0) — gültig, aber durch den Horizont-Fix
    übersprungen, daher kein Live-Call.
    """
    from app.trip import AggregationConfig, Stage, Trip, Waypoint

    wp = Waypoint(id="G1", name="Korsika", lat=42.0, lon=9.0, elevation_m=500)
    today = date.today()

    stages = [
        Stage(
            id="T1",
            name="Ferne Etappe +20",
            date=today + timedelta(days=20),
            waypoints=[wp],
        ),
        Stage(
            id="T2",
            name="Ferne Etappe +30",
            date=today + timedelta(days=30),
            waypoints=[wp],
        ),
    ]

    return Trip(
        id="bug353-far-future",
        name="Bug 353 Far Future",
        stages=stages,
        avalanche_regions=[],
        aggregation=AggregationConfig(),
    )


# ===========================================================================
# AC-4 — reine Funktion (Kernbeweis, deterministisch, kein Netzwerk)
# ===========================================================================

class TestForecastHorizonPureFunction:
    """AC-4: ``is_within_forecast_horizon`` + ``OPENMETEO_MAX_FORECAST_DAYS``."""

    def test_max_forecast_days_constant_is_15(self):
        """Konstante ist exakt 15 (empirisch endpoint-übergreifend bestätigt)."""
        assert OPENMETEO_MAX_FORECAST_DAYS == 15

    def test_today_is_within_horizon(self):
        """Heute (stage_date == reference_date) liegt im Horizont → True."""
        ref = date(2026, 6, 1)
        assert is_within_forecast_horizon(ref, ref) is True

    def test_exact_boundary_15_days_is_within(self):
        """Grenze inklusive: reference_date + 15 Tage → True."""
        ref = date(2026, 6, 1)
        assert is_within_forecast_horizon(ref + timedelta(days=15), ref) is True

    def test_beyond_boundary_16_days_is_outside(self):
        """Jenseits der Grenze: reference_date + 16 Tage → False (400-Bereich)."""
        ref = date(2026, 6, 1)
        assert is_within_forecast_horizon(ref + timedelta(days=16), ref) is False

    def test_past_date_is_within(self):
        """Vergangenheit ist unkritisch: reference_date - 1 Tag → True."""
        ref = date(2026, 6, 1)
        assert is_within_forecast_horizon(ref - timedelta(days=1), ref) is True


# ===========================================================================
# AC-1 — ferne Etappen übersprungen, KEIN API-Call
# ===========================================================================

class TestFarStagesSkippedNoCall:
    """AC-1: Trip nur mit fernen Etappen → kein Trend, kein Open-Meteo-Call."""

    def test_far_future_only_returns_none(self):
        """Alle Etappen >15 Tage → ``_build_stage_trend`` liefert None."""
        from services.trip_report_scheduler import TripReportSchedulerService

        trip = _make_far_future_trip()
        service = TripReportSchedulerService()

        result = service._build_stage_trend(trip, date.today(), tz=None)

        assert result is None, (
            "Ein Trip ausschließlich mit Etappen jenseits today+15 darf KEINE "
            f"Trend-Zeile erzeugen, bekam: {result!r}"
        )

    def test_far_future_makes_no_trend_call(self):
        """Übersprungene ferne Etappen erhöhen den Trend-Call-Counter NICHT."""
        from services.trip_report_scheduler import TripReportSchedulerService

        trip = _make_far_future_trip()
        service = TripReportSchedulerService()

        before = _count_trend_calls()
        service._build_stage_trend(trip, date.today(), tz=None)
        after = _count_trend_calls()

        assert after == before, (
            "Für Etappen jenseits today+15 darf KEIN Open-Meteo-Call abgesetzt "
            f"werden — Trend-Calls vorher={before}, nachher={after}"
        )


# ===========================================================================
# AC-3 — kein ERROR-Log beim Skip
# ===========================================================================

class TestNoErrorLogOnSkip:
    """AC-3: Horizont-Skip erzeugt kein ``logger.error`` (Rauschen weg)."""

    def test_no_error_record_on_far_future_skip(self, caplog):
        """Ferne Etappen übersprungen → keine ERROR-Records vom Scheduler."""
        from services.trip_report_scheduler import TripReportSchedulerService

        trip = _make_far_future_trip()
        service = TripReportSchedulerService()

        with caplog.at_level(logging.ERROR, logger="trip_report_scheduler"):
            service._build_stage_trend(trip, date.today(), tz=None)

        error_records = [
            r for r in caplog.records if r.levelno >= logging.ERROR
        ]
        assert error_records == [], (
            "Horizont-Skip darf kein ERROR loggen, bekam: "
            f"{[r.getMessage() for r in error_records]}"
        )

        messages = " ".join(r.getMessage() for r in caplog.records)
        assert "Weather fetch failed" not in messages, (
            "Der has_error-Placeholder-Fehlerpfad (_fetch_weather) darf für ferne "
            "Etappen gar nicht erst erreicht werden"
        )


# ===========================================================================
# AC-2 — nahe Etappen passieren den Guard (reine Funktion, kein Netzwerk)
# ===========================================================================

class TestNearStagesWithinHorizon:
    """AC-2: Etappen innerhalb 15 Tagen passieren den Horizont-Guard (True)."""

    def test_near_stage_plus_5_days_is_within(self):
        """Etappe +5 Tage liegt im Horizont → True (wird NICHT übersprungen)."""
        ref = date(2026, 6, 1)
        assert is_within_forecast_horizon(ref + timedelta(days=5), ref) is True

    def test_all_near_offsets_within_horizon(self):
        """+1, +10, +14 Tage — alle innerhalb 15 → durchweg True."""
        ref = date(2026, 6, 1)
        for offset in (1, 10, 14):
            assert (
                is_within_forecast_horizon(ref + timedelta(days=offset), ref)
                is True
            ), f"Etappe +{offset} Tage muss den Horizont-Guard passieren (True)"


# ===========================================================================
# AC-6 — Backward-Compat: kein Skip für nahen Trip (mock-frei, kein Netzwerk)
# ===========================================================================

class TestBackwardCompatNoSkipForNearTrip:
    """AC-6: Für nahe Etappen kein Verhaltensunterschied zum Pre-Fix.

    Bewusst KEIN ``_build_stage_trend``-Aufruf mit nahen Etappen — das würde
    echte Open-Meteo-Calls auslösen. Stattdessen wird der Guard direkt geprüft:
    nahe Etappen werden NIE übersprungen, der Trend-Pfad läuft also unverändert
    weiter wie vor dem Fix.
    """

    def test_no_skip_for_any_near_stage(self):
        """``ref+1``, ``ref+7``, ``ref+15`` — alle True → kein Skip, Pre-Fix-Verhalten."""
        ref = date(2026, 6, 1)
        near_stage_dates = [
            ref + timedelta(days=1),
            ref + timedelta(days=7),
            ref + timedelta(days=15),
        ]
        for stage_date in near_stage_dates:
            assert is_within_forecast_horizon(stage_date, ref) is True, (
                f"Nahe Etappe {stage_date} darf NICHT übersprungen werden — "
                "der Horizont-Fix ändert das Verhalten für nahe Etappen nicht"
            )


# ===========================================================================
# AC-5 — Guard nur im Trend-Pfad (statische Quelltext-Inspektion, mock-frei)
# ===========================================================================

class TestGuardOnlyInTrendPath:
    """AC-5: Horizont-Guard existiert nur in ``_build_stage_trend``.

    ``_fetch_weather`` (Tagesbericht-Pfad, WEATHER-04) bleibt unberührt.
    Statische Inspektion via ``inspect.getsource`` — kein Mock, kein Netzwerk.
    """

    def test_horizon_guard_only_in_trend_not_in_fetch_weather(self):
        import inspect

        from services.trip_report_scheduler import TripReportSchedulerService

        trend_src = inspect.getsource(
            TripReportSchedulerService._build_stage_trend
        )
        fetch_src = inspect.getsource(
            TripReportSchedulerService._fetch_weather
        )

        assert "is_within_forecast_horizon" in trend_src, (
            "Der Horizont-Guard MUSS im Trend-Pfad (_build_stage_trend) "
            "vorkommen"
        )
        assert "is_within_forecast_horizon" not in fetch_src, (
            "Der Horizont-Guard darf NICHT in _fetch_weather vorkommen — "
            "der Tagesbericht-Pfad (WEATHER-04) bleibt unverändert"
        )
