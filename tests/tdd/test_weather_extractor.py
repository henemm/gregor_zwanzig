"""
TDD RED — WeatherExtractor (Snapshot-Datenschicht, Issue #652, Epic #639 Teil 3/6).

Beweist das Verhalten der schlanken Ad-Hoc-Datenschicht gegen ECHTE, auf Platte
persistierte Snapshots (kein Mock, kein Dateiinhalt-Check) — über den realen
WeatherSnapshotService.save/load-Roundtrip.

SPEC: docs/specs/modules/weather_extractor.md v1.0

Diese Tests MÜSSEN initial fehlschlagen:
  * `services.weather_extractor` existiert noch nicht (AC-1/AC-2/AC-3)
  * der Snapshot persistiert die stündliche Reihe noch nicht (AC-2)
"""
from __future__ import annotations

import time
from datetime import date, datetime, timezone
from pathlib import Path

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from services.weather_snapshot import WeatherSnapshotService


# ---------------------------------------------------------------------------
# Helpers — echte Modell-Objekte
# ---------------------------------------------------------------------------

def _hours(*specs: tuple[int, ThunderLevel | None, float | None]) -> list[ForecastDataPoint]:
    """Baue stündliche ForecastDataPoints: (hour, thunder_level, temp).

    ACHTUNG Hausnorm "naive UTC" (Issue #1345, src/app/models.py __post_init__):
    Der hier aware uebergebene `ts` wird vom ForecastDataPoint SOFORT nach UTC
    konvertiert und auf naiv gestrippt — schon vor dem Speichern. Erwartungen
    gegen `ForecastDataPoint.ts` (und alles, was daraus entsteht, z.B.
    DrilldownPoint.ts) muessen daher ZEITZONENLOS formuliert werden.
    Nicht betroffen: TripSegment.start_time/end_time — die bleiben aware
    (siehe TestTimeline.arrival_time).
    """
    return [
        ForecastDataPoint(
            ts=datetime(2026, 2, 14, h, 0, tzinfo=timezone.utc),
            t2m_c=temp,
            thunder_level=thunder,
        )
        for (h, thunder, temp) in specs
    ]


def _segment_weather(
    segment_id: int,
    hour_start: int,
    hour_end: int,
    *,
    end_elevation_m: float | None = None,
    temp_max_c: float | None = None,
    hourly: list[ForecastDataPoint] | None = None,
) -> SegmentWeatherData:
    """SegmentWeatherData mit aggregierter Summary und optionaler Stundenreihe."""
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=39.76, lon=2.65, elevation_m=900.0),
        end_point=GPXPoint(lat=39.80, lon=2.70, elevation_m=end_elevation_m),
        start_time=datetime(2026, 2, 14, hour_start, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 14, hour_end, 0, tzinfo=timezone.utc),
        duration_hours=float(hour_end - hour_start),
        distance_km=5.0,
        ascent_m=300.0,
        descent_m=100.0,
    )
    summary = SegmentWeatherSummary(temp_max_c=temp_max_c, wind_max_kmh=22.0)
    timeseries = None
    if hourly is not None:
        timeseries = NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="best_match", grid_res_km=2.0),
            data=hourly,
        )
    return SegmentWeatherData(
        segment=segment,
        timeseries=timeseries,
        aggregated=summary,
        fetched_at=datetime(2026, 2, 14, 7, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _snapshot_service(tmp_path: Path, user_id: str = "default") -> WeatherSnapshotService:
    """Snapshot-Service, der gegen tmp_path schreibt/liest (echte Datei-I/O)."""
    svc = WeatherSnapshotService(user_id=user_id)
    svc._snapshots_dir = tmp_path
    return svc


def _extractor(tmp_path: Path, user_id: str = "default"):
    """WeatherExtractor, dessen interner Snapshot-Service gegen tmp_path zeigt."""
    from services.weather_extractor import WeatherExtractor

    ex = WeatherExtractor(user_id=user_id)
    ex._snapshots._snapshots_dir = tmp_path
    return ex


# ---------------------------------------------------------------------------
# AC-1 — Vertikale Timeline pro Wegpunkt (Naismith-Ankunftszeit)
# ---------------------------------------------------------------------------

class TestTimeline:
    def test_timeline_one_point_per_waypoint(self, tmp_path: Path) -> None:
        """
        GIVEN ein Snapshot mit zwei Naismith-Segmenten,
        WHEN timeline() aufgerufen wird,
        THEN gibt es pro Wegpunkt einen Eintrag mit Ankunftszeit, Höhe und
             aggregierten Metrikwerten — ohne Report-Build.
        """
        svc = _snapshot_service(tmp_path)
        seg1 = _segment_weather(1, 8, 10, end_elevation_m=1400.0, temp_max_c=9.8)
        seg2 = _segment_weather(2, 10, 12, end_elevation_m=1850.0, temp_max_c=12.5)
        svc.save("gr20", [seg1, seg2], date(2026, 2, 14))

        result = _extractor(tmp_path).timeline("gr20")

        assert result.available is True
        assert len(result.points) == 2

        # Naismith-Ankunftszeit == jeweilige Segment-Endzeit
        assert result.points[0].arrival_time == datetime(2026, 2, 14, 10, 0, tzinfo=timezone.utc)
        assert result.points[1].arrival_time == datetime(2026, 2, 14, 12, 0, tzinfo=timezone.utc)

        # Höhe je Wegpunkt
        assert result.points[0].elevation_m == 1400.0
        assert result.points[1].elevation_m == 1850.0

        # Aggregierte Metrikwerte je Segment
        assert result.points[0].metrics.temp_max_c == 9.8
        assert result.points[1].metrics.temp_max_c == 12.5


# ---------------------------------------------------------------------------
# AC-2 — Stündlicher Single-Metric-Drilldown
# ---------------------------------------------------------------------------

class TestDrilldown:
    def test_drilldown_returns_hourly_series_of_single_metric(self, tmp_path: Path) -> None:
        """
        GIVEN ein Snapshot mit echter stündlicher Reihe,
        WHEN drilldown(metric="thunder_level", hours=12) aufgerufen wird,
        THEN kommt die nach Zeit sortierte Stundenserie genau dieser Metrik
             zurück — auch wenn sie in der Summary normalerweise verborgen ist.
        """
        svc = _snapshot_service(tmp_path)
        hourly = _hours(
            (10, ThunderLevel.NONE, 9.0),
            (11, ThunderLevel.MED, 10.0),
            (12, ThunderLevel.HIGH, 11.0),
        )
        seg = _segment_weather(1, 10, 13, end_elevation_m=1500.0, hourly=hourly)
        svc.save("gr20", [seg], date(2026, 2, 14))

        result = _extractor(tmp_path).drilldown("gr20", "thunder_level", hours=12)

        assert result.available is True
        assert result.metric == "thunder_level"
        assert len(result.points) == 3

        # chronologisch sortiert
        ts = [p.ts for p in result.points]
        assert ts == sorted(ts)
        # Hausnorm #1345: ts ist naive UTC (Wanduhrzeit unveraendert 10:00)
        assert result.points[0].ts == datetime(2026, 2, 14, 10, 0)

        # Enum-Wert je Stunde erhalten
        assert result.points[0].value == ThunderLevel.NONE
        assert result.points[2].value == ThunderLevel.HIGH

    def test_drilldown_respects_hours_window(self, tmp_path: Path) -> None:
        """
        GIVEN eine 6-stündige Reihe,
        WHEN drilldown(hours=3) aufgerufen wird,
        THEN umfasst das Fenster höchstens 3 Stunden ab dem ersten Punkt.
        """
        svc = _snapshot_service(tmp_path)
        hourly = _hours(
            (10, ThunderLevel.NONE, 9.0),
            (11, ThunderLevel.NONE, 9.0),
            (12, ThunderLevel.MED, 10.0),
            (13, ThunderLevel.MED, 10.0),
            (14, ThunderLevel.HIGH, 11.0),
            (15, ThunderLevel.HIGH, 11.0),
        )
        seg = _segment_weather(1, 10, 16, end_elevation_m=1500.0, hourly=hourly)
        svc.save("gr20", [seg], date(2026, 2, 14))

        result = _extractor(tmp_path).drilldown("gr20", "thunder_level", hours=3)

        assert result.available is True
        # Fenster [10:00, 13:00) -> 3 Stunden
        assert len(result.points) == 3
        # Hausnorm #1345: ts ist naive UTC; Fenstergrenze bleibt 13:00
        assert result.points[-1].ts < datetime(2026, 2, 14, 13, 0)

    def test_drilldown_naive_from_time_is_treated_as_utc(self, tmp_path: Path) -> None:
        """
        GIVEN eine 6-stündige Reihe,
        WHEN drilldown() ein ZEITZONENLOSES `from_time` bekommt,
        THEN gilt es per Hausnorm (#1345) unveraendert als UTC und liefert
             genau dieselben Punkte wie das zeitzonenbehaftete Gegenstueck.

        Gegenrichtung zur Normalisierung an der Grenze (`_to_naive_utc`): die
        aware-Richtung ist durch die Drilldown-Tests des Telegram-Pfads
        abgedeckt, die naive war es nicht. Deutete die Grenze einen naiven Wert
        als PROZESS-Zeitzone (die spiegelverkehrte Falle), verschoebe sich das
        Fenster um den UTC-Versatz des Hosts. Deshalb prueft dieser Test feste
        Wanduhrzeiten — und nur deshalb faellt der Fehler ueberhaupt auf: der
        Root-Conftest nagelt die Prozess-Zone auf ``America/St_Johns`` (#1402).
        Auf einem UTC-Prozess waere die Falle unsichtbar, der Test also leer.
        """
        # Vorbedingung, nicht Beiwerk: ohne Versatz zur Weltzeit koennte dieser
        # Test die spiegelverkehrte Falle gar nicht sehen (er waere still gruen).
        assert time.tzname[0] != "UTC", (
            "Prozess-Zeitzone ist UTC — der Zeitzonen-Anker aus conftest.py "
            "(#1402) fehlt, dieser Test kann so nichts mehr beweisen."
        )
        svc = _snapshot_service(tmp_path)
        hourly = _hours(
            (10, ThunderLevel.NONE, 9.0),
            (11, ThunderLevel.NONE, 9.0),
            (12, ThunderLevel.MED, 10.0),
            (13, ThunderLevel.MED, 10.0),
            (14, ThunderLevel.HIGH, 11.0),
            (15, ThunderLevel.HIGH, 11.0),
        )
        seg = _segment_weather(1, 10, 16, end_elevation_m=1500.0, hourly=hourly)
        svc.save("gr20", [seg], date(2026, 2, 14))

        ex = _extractor(tmp_path)
        naive = ex.drilldown(
            "gr20", "thunder_level",
            from_time=datetime(2026, 2, 14, 12, 0), hours=3,
        )
        aware = ex.drilldown(
            "gr20", "thunder_level",
            from_time=datetime(2026, 2, 14, 12, 0, tzinfo=timezone.utc), hours=3,
        )

        assert naive.available is True
        # Fenster [12:00, 15:00) — kein Versatz durch die Host-Zeitzone
        assert [p.ts for p in naive.points] == [
            datetime(2026, 2, 14, 12, 0),
            datetime(2026, 2, 14, 13, 0),
            datetime(2026, 2, 14, 14, 0),
        ]
        # ... und beide Schreibweisen meinen denselben Zeitpunkt
        assert [p.ts for p in naive.points] == [p.ts for p in aware.points]
        assert [p.value for p in naive.points] == [p.value for p in aware.points]


# ---------------------------------------------------------------------------
# AC-3 — Sauberer Leerzustand statt Crash
# ---------------------------------------------------------------------------

class TestEmptyState:
    def test_timeline_missing_snapshot_returns_empty_state(self, tmp_path: Path) -> None:
        """
        GIVEN keinen Snapshot,
        WHEN timeline() aufgerufen wird,
        THEN available=False, leere Punkte, message gesetzt — keine Exception.
        """
        result = _extractor(tmp_path).timeline("nicht_existent")

        assert result.available is False
        assert result.points == []
        assert result.message

    def test_drilldown_without_hourly_returns_empty_state(self, tmp_path: Path) -> None:
        """
        GIVEN ein Alt-Snapshot ohne stündliche Reihe (nur aggregiert),
        WHEN drilldown() aufgerufen wird,
        THEN available=False, leere Punkte — kein Crash.
        """
        svc = _snapshot_service(tmp_path)
        seg = _segment_weather(1, 10, 12, end_elevation_m=1500.0, hourly=None)
        svc.save("gr20", [seg], date(2026, 2, 14))

        result = _extractor(tmp_path).drilldown("gr20", "thunder_level", hours=12)

        assert result.available is False
        assert result.points == []
        assert result.message


# ---------------------------------------------------------------------------
# Mandantentrennung — kein "default"-Fallback
# ---------------------------------------------------------------------------

class TestMultiUserIsolation:
    def test_user_b_does_not_see_user_a_snapshot(self, tmp_path: Path) -> None:
        """
        GIVEN User A hat einen Snapshot, User B nicht (getrennte Verzeichnisse),
        WHEN beide timeline() abfragen,
        THEN A bekommt Daten, B bekommt den Leerzustand.
        """
        dir_a = tmp_path / "alice"
        dir_b = tmp_path / "bob"
        dir_a.mkdir()
        dir_b.mkdir()

        svc_a = _snapshot_service(dir_a, user_id="alice")
        seg = _segment_weather(1, 8, 10, end_elevation_m=1400.0, temp_max_c=20.0)
        svc_a.save("gr20", [seg], date(2026, 2, 14))

        res_a = _extractor(dir_a, user_id="alice").timeline("gr20")
        res_b = _extractor(dir_b, user_id="bob").timeline("gr20")

        assert res_a.available is True
        assert res_a.points[0].metrics.temp_max_c == 20.0
        assert res_b.available is False
        assert res_b.points == []
