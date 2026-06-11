"""
TDD RED: Datierter Forecast-Snapshot-Speicher (Issue #747)

Tests fuer save_dated/load_dated Erweiterung von WeatherSnapshotService.

AC-1: save_dated schreibt {trip_id}_{YYYY-MM-DD}.json
AC-2: load_dated deserialisiert korrekt (Round-Trip)
AC-3: load_dated gibt None zurueck wenn keine Datei vorhanden
AC-4: Retention — max. 7 datierte Dateien pro Trip
AC-5: Bestehende save/load bleiben unveraendert (Alert-Regression-Schutz)

SPEC: docs/specs/modules/issue_747_dated_snapshot.md
"""
from datetime import date, datetime, timedelta, timezone

import pytest


def _make_segment_weather(segment_id: int = 1):
    """Minimales SegmentWeatherData-Objekt fuer Tests."""
    from app.models import (
        GPXPoint,
        SegmentWeatherData,
        SegmentWeatherSummary,
        TripSegment,
    )

    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=200.0),
        end_point=GPXPoint(lat=42.2, lon=9.2, elevation_m=300.0),
        start_time=datetime(2026, 6, 11, 7, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 11, 11, 0, tzinfo=timezone.utc),
        duration_hours=4.0,
        distance_km=15.0,
        ascent_m=600.0,
        descent_m=200.0,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=None,
        aggregated=SegmentWeatherSummary(
            temp_avg_c=18.0,
            gust_max_kmh=45.0,
            pop_max_pct=30,
        ),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


class TestSaveDated:
    """AC-1: save_dated schreibt {trip_id}_{YYYY-MM-DD}.json."""

    def test_save_dated_creates_dated_file(self, tmp_path):
        """
        GIVEN: SegmentWeatherData und ein Zieldatum
        WHEN: save_dated aufgerufen wird
        THEN: Datei {trip_id}_{YYYY-MM-DD}.json existiert im Snapshots-Verzeichnis
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        target = date(2026, 6, 11)
        service.save_dated("gr20-trip", target, [_make_segment_weather()])

        expected = tmp_path / "gr20-trip_2026-06-11.json"
        assert expected.exists(), f"Datierte Snapshot-Datei fehlt: {expected}"

    def test_save_dated_filename_contains_correct_date(self, tmp_path):
        """
        GIVEN: Zwei save_dated-Aufrufe fuer verschiedene Daten
        WHEN: beide ausgefuehrt werden
        THEN: je eine Datei mit korrektem Datum im Namen
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        service.save_dated("trip-x", date(2026, 6, 10), [_make_segment_weather()])
        service.save_dated("trip-x", date(2026, 6, 11), [_make_segment_weather()])

        assert (tmp_path / "trip-x_2026-06-10.json").exists()
        assert (tmp_path / "trip-x_2026-06-11.json").exists()


class TestLoadDated:
    """AC-2: load_dated deserialisiert korrekt (Round-Trip)."""

    def test_load_dated_roundtrip(self, tmp_path):
        """
        GIVEN: save_dated wurde fuer gestern aufgerufen
        WHEN: load_dated mit gestrigem Datum aufgerufen wird
        THEN: SegmentWeatherData korrekt zurueck mit gleichen Aggregations-Werten
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        yesterday = date.today() - timedelta(days=1)
        original = _make_segment_weather()
        service.save_dated("tour-abc", yesterday, [original])

        loaded = service.load_dated("tour-abc", yesterday)

        assert loaded is not None
        assert len(loaded) == 1
        agg = loaded[0].aggregated
        assert agg.temp_avg_c == pytest.approx(18.0)
        assert agg.gust_max_kmh == pytest.approx(45.0)
        assert agg.pop_max_pct == 30


class TestLoadDatedMissing:
    """AC-3: load_dated gibt None zurueck wenn keine Datei vorhanden."""

    def test_load_dated_returns_none_for_missing_file(self, tmp_path):
        """
        GIVEN: Keine datierte Snapshot-Datei vorhanden (erster Tag)
        WHEN: load_dated aufgerufen wird
        THEN: None zurueck, keine Exception
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        result = service.load_dated("noch-kein-trip", date(2026, 6, 10))

        assert result is None

    def test_load_dated_returns_none_for_wrong_trip(self, tmp_path):
        """
        GIVEN: Datei fuer trip-a vorhanden, aber trip-b abgefragt
        WHEN: load_dated("trip-b", ...) aufgerufen wird
        THEN: None zurueck
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        service.save_dated("trip-a", date(2026, 6, 11), [_make_segment_weather()])

        result = service.load_dated("trip-b", date(2026, 6, 11))

        assert result is None


class TestRetention:
    """AC-4: Retention — max. 7 datierte Dateien pro Trip nach save_dated."""

    def test_retention_keeps_max_7_dated_files(self, tmp_path):
        """
        GIVEN: 8 datierte Snapshot-Dateien fuer denselben Trip
        WHEN: ein weiterer save_dated-Aufruf erfolgt
        THEN: maximal 7 Dateien uebrig (aelteste geloescht)
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        base = date(2026, 6, 1)
        for i in range(9):
            service.save_dated("trip-ret", base + timedelta(days=i), [_make_segment_weather()])

        dated_files = list(tmp_path.glob("trip-ret_*.json"))
        assert len(dated_files) <= 7, f"Zu viele Dateien: {len(dated_files)}"

    def test_retention_deletes_oldest_files(self, tmp_path):
        """
        GIVEN: 7 Dateien vorhanden (2026-06-01 bis 2026-06-07)
        WHEN: save_dated fuer 2026-06-08 aufgerufen wird
        THEN: 2026-06-01-Datei geloescht, neueste 7 Dateien bleiben
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        base = date(2026, 6, 1)
        for i in range(7):
            service.save_dated("trip-old", base + timedelta(days=i), [_make_segment_weather()])

        service.save_dated("trip-old", date(2026, 6, 8), [_make_segment_weather()])

        oldest = tmp_path / "trip-old_2026-06-01.json"
        assert not oldest.exists(), "Aelteste Datei wurde nicht geloescht"
        assert (tmp_path / "trip-old_2026-06-08.json").exists()


class TestExistingSaveLoadUnchanged:
    """AC-5: Bestehende save/load bleiben byte-identisch (Alert-Regression-Schutz)."""

    def test_save_does_not_create_dated_file(self, tmp_path):
        """
        GIVEN: Nur save() (nicht save_dated) wird aufgerufen
        WHEN: save("trip-x", date, segments)
        THEN: Nur {trip_id}.json existiert, keine datierten Dateien
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        service.save("trip-x", [_make_segment_weather()], date(2026, 6, 11))

        assert (tmp_path / "trip-x.json").exists()
        dated = list(tmp_path.glob("trip-x_*.json"))
        assert len(dated) == 0, f"save() hat unerwartet datierte Datei erstellt: {dated}"

    def test_load_after_save_still_works(self, tmp_path):
        """
        GIVEN: save() wird aufgerufen
        WHEN: load() danach aufgerufen wird
        THEN: SegmentWeatherData korrekt zurueck (unveraendertes Verhalten)
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        original = _make_segment_weather()
        service.save("trip-alert", [original], date(2026, 6, 11))

        loaded = service.load("trip-alert")

        assert loaded is not None
        assert len(loaded) == 1
        assert loaded[0].aggregated.temp_avg_c == pytest.approx(18.0)
