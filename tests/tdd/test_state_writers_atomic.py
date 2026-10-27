"""AC-9 (Epic #1539, S1a): Zustands-Schreiber schreiben atomar.

Given eine bereits gueltig geschriebene Datei des jeweiligen Schreibers
When  ein neuer Schreibvorgang MITTEN im Schreiben scheitert
Then  ist die alte Datei byte-genau unveraendert und im Ordner liegt keine
      Temp-Leiche.

Fehlerpunkt (bewusst, nicht "nicht serialisierbares Objekt"): alle heutigen
Schreiber rufen `json.dumps(...)` VOR dem Oeffnen der Zieldatei auf -- ein
Serialisierungsfehler wuerde die Datei also gar nicht beruehren und der Fall
waere heute wertlos gruen. Zerstoerend ist erst ein Fehler NACH dem Oeffnen
(Truncate) der Zieldatei: Platte voll / Groessenlimit. Das wird echt erzeugt
ueber `RLIMIT_FSIZE`: der neue Inhalt ueberschreitet das Limit, der Kernel
verweigert den Schreibvorgang (EFBIG), nachdem `write_text` die Zieldatei
schon abgeschnitten hat. Ein atomarer Schreiber (Temp-Datei + `os.replace`)
scheitert dagegen an der Temp-Datei und raeumt sie weg.

Der Schreibvorgang laeuft in einem Kindprozess (`sys.executable`), damit das
Limit weder pytests Capture-Dateien noch andere Tests trifft. Kein Mock,
kein Netz; echte Dienste auf tmp-Daten (GZ_DATA_DIR im Kindprozess).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
FSIZE_LIMIT = 16384

# Kindprozess: `seed` schreibt klein (normal), `big` schreibt gross unter
# RLIMIT_FSIZE. Gibt den Zielpfad aus; Ausnahmen des Schreibers werden
# geschluckt (manche Schreiber werfen, manche loggen nur).
_CHILD = r"""
import json, resource, sys
from datetime import date, datetime, timezone
sys.path.insert(0, sys.argv[1])
case, mode, cachefile = sys.argv[2], sys.argv[3], sys.argv[4]
big = mode == "big"
n = 60 if big else 1

def segs(count):
    from app.models import GPXPoint, SegmentWeatherData, SegmentWeatherSummary, TripSegment
    out = []
    for i in range(count):
        s = TripSegment(segment_id=i + 1,
            start_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=200.0),
            end_point=GPXPoint(lat=42.2, lon=9.2, elevation_m=300.0),
            start_time=datetime(2026, 6, 11, 7, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 6, 11, 11, 0, tzinfo=timezone.utc),
            duration_hours=4.0, distance_km=15.0, ascent_m=600.0, descent_m=200.0)
        out.append(SegmentWeatherData(segment=s, timeseries=None,
            aggregated=SegmentWeatherSummary(temp_avg_c=18.0, gust_max_kmh=45.0, pop_max_pct=30),
            fetched_at=datetime.now(timezone.utc), provider="openmeteo"))
    return out

def run(write, path):
    print(path, flush=True)
    if big:
        resource.setrlimit(resource.RLIMIT_FSIZE, (%(limit)d, %(limit)d))
    try:
        write()
    except BaseException as e:
        print("writer raised:", type(e).__name__, file=sys.stderr)

if case == "alert_log":
    from app.loader import get_data_dir
    from services import alert_log
    run(lambda: alert_log.append_entry("ac9", entity_id="t1", entity_type="trip",
        changes_count=1, severity="minor", reason="x" * (20000 if big else 1),
        effective_channels=["email"], sent_channels=["email"]),
        get_data_dir("ac9") / "alert_log.json")
elif case == "alert_state":
    from services.alert_state import AlertStateService
    svc = AlertStateService("ac9")
    run(lambda: svc.save("t1", {"k": "x" * (20000 if big else 1)}), svc._path("t1"))
elif case in ("snapshot_save", "snapshot_dated", "snapshot_anchor"):
    from services.weather_snapshot import WeatherSnapshotService
    svc = WeatherSnapshotService("ac9")
    d = date(2026, 6, 11)
    if case == "snapshot_save":
        run(lambda: svc.save("t1", segs(n), d), svc._snapshots_dir / "t1.json")
    elif case == "snapshot_dated":
        run(lambda: svc.save_dated("t1", d, segs(n)), svc._snapshots_dir / "t1_2026-06-11.json")
    else:
        run(lambda: svc.save_alarm_anchor("t1", d, segs(n), "email"),
            svc._snapshots_dir / "t1_alarm_anchor_email.json")
elif case == "compare_snapshot":
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.point_weather import PointWeatherData
    from app.models import SegmentWeatherSummary
    svc = CompareWeatherSnapshotService("ac9")
    pt = PointWeatherData(id="loc1", name="x" * (20000 if big else 1), lat=47.0, lon=11.0,
        timeseries=None, aggregated=SegmentWeatherSummary(temp_avg_c=1.0),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo")
    run(lambda: svc.save("p1", "loc1", pt), svc._path("p1", "loc1"))
elif case == "openmeteo_cache":
    from pathlib import Path
    import providers.openmeteo as om
    om.AVAILABILITY_CACHE_PATH = Path(cachefile)
    result = {"probe_date": date.today().isoformat(),
              "models": {"m": {"available": ["x" * (20000 if big else 1)], "unavailable": []}}}
    run(lambda: om.OpenMeteoProvider()._save_availability_cache(result), Path(cachefile))
"""


def _kind(case: str, mode: str, tmp_path: Path) -> Path:
    env = {
        **os.environ,
        "GZ_DATA_DIR": str(tmp_path / "data"),
        "PYTHONPATH": str(_SRC),
    }
    env.pop("GZ_ACTIVE_WORKFLOW", None)
    proc = subprocess.run(
        [sys.executable, "-c", _CHILD % {"limit": FSIZE_LIMIT}, str(_SRC), case, mode,
         str(tmp_path / "model_availability.json")],
        capture_output=True, text=True, env=env, cwd=tmp_path, timeout=60,
    )
    assert proc.stdout.strip(), f"Kindprozess ohne Zielpfad ({case}/{mode}): {proc.stderr[-600:]}"
    return Path(proc.stdout.strip().splitlines()[0])


@pytest.mark.parametrize("case", [
    "alert_log",
    "alert_state",
    "snapshot_save",
    "snapshot_dated",
    "snapshot_anchor",
    "compare_snapshot",
    "openmeteo_cache",
])
def test_schreiber_laesst_alte_datei_bei_fehler_mitten_im_schreiben_unveraendert(case, tmp_path):
    """AC-9: alte Datei byte-genau unveraendert, keine Temp-Leiche (je Schreiber)."""
    ziel = _kind(case, "seed", tmp_path)
    assert ziel.exists(), f"{case}: Vorab-Schreiben hat {ziel} nicht angelegt"
    vorher = ziel.read_bytes()
    assert 0 < len(vorher) < FSIZE_LIMIT // 2, "Testaufbau: alte Datei muss klein und gueltig sein"
    json.loads(vorher)
    namen_vorher = {p.name for p in ziel.parent.iterdir() if not p.name.endswith(".lock")}

    _kind(case, "big", tmp_path)

    nachher = ziel.read_bytes() if ziel.exists() else b""
    assert nachher == vorher, (
        f"{case}: alte Datei wurde zerstoert/veraendert "
        f"({len(vorher)} -> {len(nachher)} Bytes)"
    )
    namen_nachher = {p.name for p in ziel.parent.iterdir() if not p.name.endswith(".lock")}
    assert namen_nachher == namen_vorher, (
        f"{case}: Temp-Leiche im Ordner: {sorted(namen_nachher - namen_vorher)}"
    )
