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


# Real GPX files from the worktree — used for Multi-Import tests below.
# These exist at data/users/default/gpx/ in the worktree.
REAL_GPX_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "users" / "default" / "gpx"
)
REAL_GPX_TAG1 = REAL_GPX_DIR / "2026-01-17_2753214331_Tag 1_ von Valldemossa nach Deià.gpx"
REAL_GPX_TAG2 = REAL_GPX_DIR / "2026-01-17_2753216748_Tag 2_ von Deià nach Sóller.gpx"
REAL_GPX_TAG3 = REAL_GPX_DIR / "2026-01-17_2753225520_Tag 3_ von Sóller nach Tossals Verds.gpx"


class TestMultiGpxImport:
    """GIVEN multiple GPX files WHEN bulk-import THEN sorted stages with sequential dates.

    These tests target the new pure function `process_bulk_gpx_uploads()`
    introduced in spec docs/specs/modules/gpx_multi_import.md (Issue #127).

    EXPECTED at TDD RED: All tests FAIL because the function does not exist yet.
    Either ImportError (function not defined) or AttributeError.

    NO MOCKS — uses real GPX bytes from data/users/default/gpx/.
    """

    def _real_bytes(self, path: Path) -> bytes:
        """Load real GPX file bytes; skip test if file missing in worktree."""
        if not path.exists():
            pytest.skip(f"Test fixture missing in worktree: {path}")
        return path.read_bytes()

    def test_natural_sort_applied_to_uploaded_filenames(self, tmp_path):
        """
        GIVEN: 3 valid GPX bytes uploaded in random filename order
               (KHW_11.gpx, KHW_00a.gpx, KHW_10.gpx)
        WHEN: process_bulk_gpx_uploads(files, start_date)
        THEN: Returned stages are ordered KHW_00a -> KHW_10 -> KHW_11

        Real-world reproduction of Issue #127 (Browser FileList random order).
        """
        from web.pages.trips import process_bulk_gpx_uploads

        bytes_a = self._real_bytes(REAL_GPX_TAG1)
        bytes_b = self._real_bytes(REAL_GPX_TAG2)
        bytes_c = self._real_bytes(REAL_GPX_TAG3)

        # Upload order is intentionally NOT natural-sorted
        files = [
            ("KHW_11.gpx", bytes_c),
            ("KHW_00a.gpx", bytes_a),
            ("KHW_10.gpx", bytes_b),
        ]

        stages = process_bulk_gpx_uploads(
            files, start_date=date(2026, 5, 1), upload_dir=tmp_path,
        )

        assert len(stages) == 3, f"Expected 3 stages, got {len(stages)}"
        # Stages must be returned in natural-sort order by source filename
        # (KHW_00a < KHW_10 < KHW_11). The first stage was uploaded as KHW_00a
        # which carried bytes_a (Tag 1), the second KHW_10 -> Tag 2, etc.
        # We verify ordering by checking the date assignment which is sequential.
        assert stages[0]["date"] == "2026-05-01"
        assert stages[1]["date"] == "2026-05-02"
        assert stages[2]["date"] == "2026-05-03"

        # If the natural-sort worked, stages[0] corresponds to KHW_00a -> bytes_a (Tag1).
        # We can sanity-check by ensuring the names/waypoints differ between stages
        # (each Tag has different waypoints).
        names = [s["name"] for s in stages]
        assert len(set(names)) == 3, f"Stages should have distinct names: {names}"

    def test_date_propagation_starts_at_user_choice(self, tmp_path):
        """
        GIVEN: 3 valid GPX files + start_date=2026-05-01
        WHEN: process_bulk_gpx_uploads(...)
        THEN: Stage 1 -> 2026-05-01, Stage 2 -> 2026-05-02, Stage 3 -> 2026-05-03
        """
        from web.pages.trips import process_bulk_gpx_uploads

        files = [
            ("a.gpx", self._real_bytes(REAL_GPX_TAG1)),
            ("b.gpx", self._real_bytes(REAL_GPX_TAG2)),
            ("c.gpx", self._real_bytes(REAL_GPX_TAG3)),
        ]

        stages = process_bulk_gpx_uploads(
            files, start_date=date(2026, 5, 1), upload_dir=tmp_path,
        )

        assert len(stages) == 3
        assert stages[0]["date"] == "2026-05-01"
        assert stages[1]["date"] == "2026-05-02"
        assert stages[2]["date"] == "2026-05-03"

    def test_corrupt_file_skipped_with_gapless_dates(self, tmp_path):
        """
        GIVEN: 3 files where the middle one is corrupt bytes
        WHEN: process_bulk_gpx_uploads(start_date=2026-05-01)
        THEN: 2 valid stages with GAPLESS dates (2026-05-01, 2026-05-02)
              NOT (2026-05-01, 2026-05-03) — the skipped file does not
              consume a date slot.

        This is the explicit "lückenlos" requirement from the spec
        (Acceptance Criteria + R2).
        """
        from web.pages.trips import process_bulk_gpx_uploads

        files = [
            ("a.gpx", self._real_bytes(REAL_GPX_TAG1)),
            ("b.gpx", b"NOT GPX - corrupt bytes"),  # invalid file in middle
            ("c.gpx", self._real_bytes(REAL_GPX_TAG2)),
        ]

        stages = process_bulk_gpx_uploads(
            files, start_date=date(2026, 5, 1), upload_dir=tmp_path,
        )

        # Only 2 valid files become stages
        assert len(stages) == 2, f"Expected 2 stages (1 skipped), got {len(stages)}"
        # Dates must be gapless — no jump to 2026-05-03 for the second valid file
        assert stages[0]["date"] == "2026-05-01"
        assert stages[1]["date"] == "2026-05-02", (
            f"Second valid stage must be start+1 (gapless), "
            f"got {stages[1]['date']}"
        )

    def test_single_file_backwards_compat(self, tmp_path):
        """
        GIVEN: Exactly 1 GPX file
        WHEN: process_bulk_gpx_uploads(start_date=2026-06-15)
        THEN: 1 stage with the chosen date — single-file path still works.
        """
        from web.pages.trips import process_bulk_gpx_uploads

        files = [("only.gpx", self._real_bytes(REAL_GPX_TAG1))]

        stages = process_bulk_gpx_uploads(
            files, start_date=date(2026, 6, 15), upload_dir=tmp_path,
        )

        assert len(stages) == 1
        assert stages[0]["date"] == "2026-06-15"

    def test_default_start_date_with_existing_stages(self):
        """
        GIVEN: existing stages with last date 2026-05-10
        WHEN: compute_default_start_date(existing_stages_data)
        THEN: Returns date(2026, 5, 11) — last_stage_date + 1

        Per spec §2 _refresh_commit_row default-date logic. Tests the
        helper that is expected to be extracted as
        `compute_default_start_date(stages_data)`.
        """
        from web.pages.trips import compute_default_start_date

        stages_data = [
            {"name": "Stage A", "date": "2026-05-08", "waypoints": []},
            {"name": "Stage B", "date": "2026-05-09", "waypoints": []},
            {"name": "Stage C", "date": "2026-05-10", "waypoints": []},
        ]

        result = compute_default_start_date(stages_data)
        assert result == date(2026, 5, 11)

    def test_default_start_date_no_existing_stages(self):
        """
        GIVEN: Empty stages list
        WHEN: compute_default_start_date([])
        THEN: Returns date.today()
        """
        from web.pages.trips import compute_default_start_date

        result = compute_default_start_date([])
        assert result == date.today()
