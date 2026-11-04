"""Issue #2237: CompareWeatherSnapshotService.delete(preset_id) — echtes
Dateisystem (autouse-Isolation aus tests/conftest.py), Zwei-Nutzer-Test (AC-7).

Spec: docs/specs/bugfix/fix_2237_staging_testdaten.md
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from app.models import SegmentWeatherSummary
from services.compare_weather_snapshot import CompareWeatherSnapshotService
from services.point_weather import PointWeatherData


def _point(loc_id: str) -> PointWeatherData:
    return PointWeatherData(
        id=loc_id, name=loc_id, lat=47.0, lon=11.0,
        timeseries=None, aggregated=SegmentWeatherSummary(temp_avg_c=1.0),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def test_delete_entfernt_nur_eigene_preset_snapshots():
    a = CompareWeatherSnapshotService("user-a-2237")
    b = CompareWeatherSnapshotService("user-b-2237")
    for svc in (a, b):
        svc.save("cp-1", "loc1", _point("loc1"))
        svc.save("cp-1", "loc2", _point("loc2"))
    a.save("cp-10", "loc1", _point("loc1"))
    # Fremddatei mit passendem Praefix, aber ohne .json-Endung: kein Snapshot.
    fremd = a._dir / "cp-1__x.txt"
    fremd.write_text("fremd", encoding="utf-8")

    assert a.delete("cp-1") == (2, 0)
    assert fremd.read_text(encoding="utf-8") == "fremd"
    assert a.load("cp-1", "loc1") == []
    assert a.load("cp-1", "loc2") == []
    # Praefix cp-1 darf cp-10 nicht treffen
    assert len(a.load("cp-10", "loc1")) == 1
    # Nutzer B unberuehrt
    assert len(b.load("cp-1", "loc1")) == 1
    assert len(b.load("cp-1", "loc2")) == 1


def test_delete_ohne_ordner_liefert_null():
    assert CompareWeatherSnapshotService("user-ohne-ordner-2237").delete("cp-x") == (0, 0)


def test_delete_meldet_nicht_loeschbaren_eintrag_als_fehler():
    """Teilerfolg ist sichtbar: ein Verzeichnis mit Snapshot-Namen lässt sich
    per unlink() nicht entfernen (echter IsADirectoryError, kein Mock) und
    zählt als failed; die übrigen Snapshots werden trotzdem entfernt."""
    a = CompareWeatherSnapshotService("user-fail-2237")
    a.save("cp-1", "loc1", _point("loc1"))
    blocker = a._dir / "cp-1__kaputt.json"
    blocker.mkdir()

    assert a.delete("cp-1") == (1, 1)
    assert a.load("cp-1", "loc1") == []
    assert blocker.is_dir()


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignoriert Dateirechte")
def test_delete_meldet_nicht_lesbaren_ordner_als_fehler():
    """Listing-Fehler (Ordner ohne Leserecht, echtes PermissionError) zählt
    als failed=1 statt still (0, 0) zu melden."""
    a = CompareWeatherSnapshotService("user-nolist-2237")
    a.save("cp-1", "loc1", _point("loc1"))
    os.chmod(a._dir, 0)
    try:
        assert a.delete("cp-1") == (0, 1)
    finally:
        os.chmod(a._dir, 0o755)
    assert len(a.load("cp-1", "loc1")) == 1
