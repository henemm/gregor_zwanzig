"""
Tests for GPX Import in Trip Dialogs (Stage-level GPX import).

Tests gpx_to_stage_data() with REAL GPX files. NO MOCKS!

Spec: docs/specs/modules/gpx_import_in_trip_dialog.md
"""
from datetime import date
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
GPX_TAG1 = DATA_DIR / "2026-01-17_2753214331_Tag 1_ von Valldemossa nach Deià.gpx"
GPX_TAG4 = DATA_DIR / "2026-01-17_2753228656_Tag 4_ von Tossals Verds nach Lluc.gpx"


class TestGpxToStageData:
    """GIVEN valid GPX file WHEN gpx_to_stage_data THEN stage dict with waypoints."""

    def test_returns_dict_with_required_keys(self, tmp_path):
        """
        GIVEN: Valid GPX file bytes
        WHEN: gpx_to_stage_data() is called
        THEN: Returns dict with keys 'name', 'date', 'waypoints'

        EXPECTED: FAIL - gpx_to_stage_data doesn't exist yet
        """
        from web.pages.trips import gpx_to_stage_data

        content = GPX_TAG1.read_bytes()
        result = gpx_to_stage_data(content, "tag1.gpx", upload_dir=tmp_path)

        assert "name" in result
        assert "date" in result
        assert "waypoints" in result

    def test_waypoints_have_required_fields(self, tmp_path):
        """
        GIVEN: Valid GPX file
        WHEN: gpx_to_stage_data() returns waypoints
        THEN: Each waypoint has id, name, lat, lon, elevation_m
        """
        from web.pages.trips import gpx_to_stage_data

        content = GPX_TAG1.read_bytes()
        result = gpx_to_stage_data(content, "tag1.gpx", upload_dir=tmp_path)

        assert len(result["waypoints"]) > 0
        for wp in result["waypoints"]:
            assert "id" in wp
            assert "name" in wp
            assert "lat" in wp
            assert "lon" in wp
            assert "elevation_m" in wp

    def test_name_from_gpx_track(self, tmp_path):
        """
        GIVEN: GPX file with track name
        WHEN: gpx_to_stage_data()
        THEN: Stage name is taken from GPX track
        """
        from web.pages.trips import gpx_to_stage_data

        content = GPX_TAG1.read_bytes()
        result = gpx_to_stage_data(content, "tag1.gpx", upload_dir=tmp_path)

        assert len(result["name"]) > 0
        assert result["name"] != "Stage 1"  # not a default name


class TestGpxToStageDataCustomDate:
    """GIVEN custom date WHEN gpx_to_stage_data THEN date is used."""

    def test_uses_provided_date(self, tmp_path):
        """
        GIVEN: GPX file + explicit stage_date
        WHEN: gpx_to_stage_data(stage_date=2026-03-15)
        THEN: Returned date matches provided date
        """
        from web.pages.trips import gpx_to_stage_data

        content = GPX_TAG4.read_bytes()
        result = gpx_to_stage_data(
            content, "tag4.gpx",
            stage_date=date(2026, 3, 15),
            upload_dir=tmp_path,
        )

        assert result["date"] == "2026-03-15"

    def test_default_date_is_today(self, tmp_path):
        """
        GIVEN: GPX file without explicit date
        WHEN: gpx_to_stage_data() without stage_date
        THEN: date defaults to today
        """
        from web.pages.trips import gpx_to_stage_data

        content = GPX_TAG4.read_bytes()
        result = gpx_to_stage_data(content, "tag4.gpx", upload_dir=tmp_path)

        assert result["date"] == date.today().isoformat()


class TestGpxToStageDataInvalid:
    """GIVEN invalid GPX WHEN gpx_to_stage_data THEN raises exception."""

    def test_invalid_extension_raises(self, tmp_path):
        """
        GIVEN: File with .kml extension
        WHEN: gpx_to_stage_data()
        THEN: ValueError raised
        """
        from web.pages.trips import gpx_to_stage_data

        with pytest.raises(ValueError):
            gpx_to_stage_data(b"data", "track.kml", upload_dir=tmp_path)

    def test_broken_xml_raises(self, tmp_path):
        """
        GIVEN: Broken XML content
        WHEN: gpx_to_stage_data()
        THEN: Exception raised
        """
        from web.pages.trips import gpx_to_stage_data

        with pytest.raises(Exception):
            gpx_to_stage_data(b"<gpx><broken", "bad.gpx", upload_dir=tmp_path)
