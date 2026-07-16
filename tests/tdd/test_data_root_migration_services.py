"""RED-Tests: #1265-Datenpfad-Migration für drei per-User-Reader.

Beweist, dass `user_tier`, `CompareRadarAlertService` und
`CompareWeatherSnapshotService` ihre per-User-Dateien über
`app.loader.get_data_dir(user_id)` (Laufzeit-Auflösung, honoriert `_DATA_ROOT`)
statt hartkodiert unter `data/users/{user_id}/…` lesen/schreiben.

Deterministisch (Kern-Schicht): kein Netz, kein Mock der Service-Logik. Die
autouse-Isolationsfixture (`tests/conftest.py`, #1133) setzt
`app.loader._DATA_ROOT` auf ein tmp_path je Test → `get_data_dir(uid)` liefert
die isolierte Wurzel. Wir schreiben echte Dateien DORT und rufen die echten
Services. HEUTE ROT, weil die Services hartkodiert `data/users` lesen (≠
isolierte Wurzel im Test) → Default/leer.

AC-5 (verhaltens-erhaltend bei Default-Wurzel) ist im isolierten Test nicht
prüfbar (die Fixture erzwingt Isolation). Er ist durch die byte-identische
Pfad-Konstruktion gegeben: bei Default-Wurzel gilt
`get_data_root()/users/uid` == `data/users/uid`. Das Nicht-Regressions-Verhalten
sichert die bestehende Suite im GREEN-Schritt ab.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.config import Settings
from app.loader import get_data_dir
from app.models import SegmentWeatherSummary
from services.point_weather import PointWeatherData


def _uid() -> str:
    return f"tier-mig-{uuid.uuid4().hex[:8]}"


def _write_profile(user_id: str, tier: str) -> None:
    """Echtes user.json unter der ISOLIERTEN get_data_dir-Wurzel."""
    d = get_data_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"tier": tier}))


def _point(point_id: str, name: str, precip_sum_mm: float = 1.5) -> PointWeatherData:
    """Echtes PointWeatherData-DTO (kein Mock), Muster test_issue_1169::_point."""
    return PointWeatherData(
        id=point_id, name=name, lat=42.0, lon=9.0, timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=datetime.now(timezone.utc), provider="test-scripted",
    )


# --- AC-1: sms_allowed liest das Profil aus get_data_dir, nicht den Default ---
def test_ac1_sms_allowed_reads_profile_from_isolated_root():
    from services import user_tier

    uid = _uid()
    _write_profile(uid, tier="premium")  # premium erlaubt SMS

    # Default (Profil nicht gefunden) wäre False → beweist Lesen aus get_data_dir.
    assert user_tier.sms_allowed(uid) is True


# --- AC-2: daily_alert_limit leitet aus dem Tier des get_data_dir-Profils ab ---
def test_ac2_daily_alert_limit_reads_tier_from_isolated_root():
    from services import user_tier

    uid = _uid()
    _write_profile(uid, tier="standard")  # standard -> Limit 4 (Default free -> 2)

    assert user_tier.daily_alert_limit(uid) == 4


# --- AC-3: CompareRadarAlertService-Throttle zeigt unter die isolierte Wurzel ---
def test_ac3_radar_alert_throttle_file_under_isolated_root():
    from services.compare_radar_alert import CompareRadarAlertService

    uid = _uid()
    service = CompareRadarAlertService(settings=Settings(), user_id=uid)

    expected = get_data_dir(uid) / "compare_radar_alert_throttle.json"
    assert service._throttle_file == expected


# --- AC-4: CompareWeatherSnapshotService save/load-Roundtrip unter isolierter Wurzel ---
def test_ac4_compare_snapshot_roundtrip_under_isolated_root():
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    uid = _uid()
    preset_id, location_id = "preset-alps", "loc-alps"
    svc = CompareWeatherSnapshotService(user_id=uid)

    expected_dir = get_data_dir(uid) / "compare_weather_snapshots"
    # Harter Pfad-Assert: Datenverzeichnis MUSS unter der isolierten Wurzel liegen.
    assert svc._dir == expected_dir

    point = _point(location_id, "Alpen-Ort", precip_sum_mm=2.0)
    svc.save(preset_id, location_id, point)

    expected_file = expected_dir / f"{preset_id}__{location_id}.json"
    assert expected_file.exists()

    loaded = svc.load(preset_id, location_id)
    assert len(loaded) == 1
    assert loaded[0].id == point.id
    assert loaded[0].aggregated.precip_sum_mm == point.aggregated.precip_sum_mm


# --- AC-6: Zwei-Nutzer-Isolation (kein Cross-User durch die Migration) ---
def test_ac6_two_user_isolation_no_cross_user_leak():
    """Nach dem Fix grün. Im RED bereits teilweise rot: der True-Fall (a) schlägt
    fehl, weil der Service den Default (data/users) statt get_data_dir liest."""
    from services import user_tier
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    uid_a, uid_b = _uid(), _uid()
    _write_profile(uid_a, tier="premium")  # SMS erlaubt
    _write_profile(uid_b, tier="free")     # SMS verboten

    # Jeder Service liest NUR sein eigenes Profil.
    assert user_tier.sms_allowed(uid_a) is True   # RED: liest Default → False
    assert user_tier.sms_allowed(uid_b) is False

    # Snapshot-Isolation: A speichert, B sieht nichts unter demselben Key.
    svc_a = CompareWeatherSnapshotService(user_id=uid_a)
    svc_b = CompareWeatherSnapshotService(user_id=uid_b)
    svc_a.save("p", "l", _point("l", "Ort-A", precip_sum_mm=3.0))

    assert len(svc_a.load("p", "l")) == 1
    assert svc_b.load("p", "l") == []
    assert svc_a._dir == get_data_dir(uid_a) / "compare_weather_snapshots"
    assert svc_b._dir == get_data_dir(uid_b) / "compare_weather_snapshots"
