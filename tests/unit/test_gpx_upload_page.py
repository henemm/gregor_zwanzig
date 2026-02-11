"""
Tests for GPX Upload page logic (Feature 1.1).

Tests the process_gpx_upload() function with REAL GPX files.
NO MOCKS!

Spec: docs/specs/modules/gpx_upload.md
"""
from pathlib import Path

import pytest

from web.pages.gpx_upload import process_gpx_upload

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
GPX_TAG4 = DATA_DIR / "2026-01-17_2753228656_Tag 4_ von Tossals Verds nach Lluc.gpx"
GPX_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "users" / "default" / "gpx"


# --- Test 1: Valid GPX returns GPXTrack with correct name ---

class TestValidGPX:
    """GIVEN gueltige GPX-Datei WHEN process_gpx_upload THEN GPXTrack mit Namen."""

    def test_returns_track_with_name(self, tmp_path):
        content = GPX_TAG4.read_bytes()
        track = process_gpx_upload(content, "tag4.gpx", upload_dir=tmp_path)
        assert track.name is not None
        assert len(track.name) > 0
        assert track.total_distance_km > 10.0


# --- Test 2: GPX file saved to upload dir ---

class TestFileSaved:
    """GIVEN gueltige GPX WHEN process_gpx_upload THEN Datei gespeichert."""

    def test_file_saved(self, tmp_path):
        content = GPX_TAG4.read_bytes()
        process_gpx_upload(content, "tag4.gpx", upload_dir=tmp_path)
        saved = tmp_path / "tag4.gpx"
        assert saved.exists()
        assert saved.stat().st_size > 0


# --- Test 3: Invalid extension raises ValueError ---

class TestInvalidExtension:
    """GIVEN Datei mit falscher Endung WHEN process_gpx_upload THEN ValueError."""

    def test_rejects_non_gpx(self, tmp_path):
        with pytest.raises(ValueError, match="gpx"):
            process_gpx_upload(b"some data", "track.kml", upload_dir=tmp_path)


# --- Test 4: Broken XML raises GPXParseError ---

class TestBrokenXML:
    """GIVEN kaputtes XML WHEN process_gpx_upload THEN GPXParseError."""

    def test_rejects_invalid_xml(self, tmp_path):
        from core.gpx_parser import GPXParseError
        with pytest.raises(GPXParseError):
            process_gpx_upload(b"<gpx><broken", "bad.gpx", upload_dir=tmp_path)


# --- Test 5: Empty file raises GPXParseError ---

class TestEmptyFile:
    """GIVEN leere Datei WHEN process_gpx_upload THEN GPXParseError."""

    def test_rejects_empty(self, tmp_path):
        from core.gpx_parser import GPXParseError
        with pytest.raises(GPXParseError):
            process_gpx_upload(b"", "empty.gpx", upload_dir=tmp_path)
