"""
TDD-Tests für Issue #338 (Erweiterung) — vollständige Open-Meteo-Abruf-Erfassung.

Ergänzt den Zähler aus Commit bd8e1e2 um die beiden bislang ungezählten
Open-Meteo-Ausgangspunkte: den Go-Provider (separater Go-Test) und den
Python-`GeoSphereProvider._fetch_openmeteo_clouds`.

Jeder Test mappt 1:1 auf ein AC aus
docs/specs/modules/issue_338_go_geosphere_counter.md.

KONTEXT: Das Open-Meteo-Tageslimit ist erschöpft — echte Abrufe geben HTTP 429.
Das ist für diese Tests ERWÜNSCHT: der Zähler MUSS auch 429-Abrufe
protokollieren. Es werden KEINE Mocks/patch/MagicMock für API-Calls verwendet
(Projektregel) — der Geosphere-Test macht einen ECHTEN api.open-meteo.com-Abruf.

RED-Phase: Tests schlagen fehl, weil src/providers/call_log.py und die
Geosphere-Instrumentierung sowie die analyze-Skript-Erweiterung noch fehlen.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.live

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


# ---------------------------------------------------------------------------
# AC-2: Geosphere _fetch_openmeteo_clouds protokolliert source="geosphere_clouds"
# ---------------------------------------------------------------------------

def test_ac2_geosphere_clouds_logs_source_geosphere_clouds(tmp_path, monkeypatch):
    """
    AC-2: Ein echter GeoSphereProvider._fetch_openmeteo_clouds-Aufruf
    (Alpenkoordinaten, 429 erlaubt) protokolliert eine JSONL-Zeile mit
    source == "geosphere_clouds".

    KONFIGURATION (kein Mock): das gemeinsame Logging-Modul `providers.call_log`
    wird per DIAGNOSTICS_PATH-Umkonfiguration auf eine tmp_path-Datei umgesetzt,
    um die JSONL-Datei zu isolieren. Der API-Abruf selbst ist echt.
    """
    from providers import call_log
    from providers.geosphere import GeoSphereProvider

    log_path = tmp_path / "openmeteo_calls.jsonl"
    monkeypatch.setattr(call_log, "DIAGNOSTICS_PATH", log_path, raising=False)

    provider = GeoSphereProvider()
    # _fetch_openmeteo_clouds schluckt Fehler still (Cloud-Layer optional);
    # 429 ist hier erlaubt — der Abruf MUSS trotzdem protokolliert werden.
    provider._fetch_openmeteo_clouds(47.27, 11.39, hours=24)

    entries = _read_jsonl(log_path)
    sources = {e.get("source") for e in entries}
    assert entries, (
        "Geosphere-Clouds-Pfad hätte mindestens einen Abruf protokollieren müssen"
    )
    assert "geosphere_clouds" in sources, (
        f"Erwartete source 'geosphere_clouds' aus _fetch_openmeteo_clouds, sah: {sources}"
    )


# ---------------------------------------------------------------------------
# AC-3: Die 6 bestehenden Tests aus bd8e1e2 bleiben grün (Konsolidierung)
# ---------------------------------------------------------------------------

def test_ac3_existing_six_tests_still_green():
    """
    AC-3: Nach der Konsolidierung der Logging-Logik in `providers.call_log`
    müssen die 6 bestehenden Tests aus tests/tdd/test_bug_338_openmeteo_call_counter.py
    weiterhin grün sein (identisches Verhalten).

    Wir führen sie als Sub-Prozess aus und prüfen den Exit-Code.
    """
    existing = REPO_ROOT / "tests" / "tdd" / "test_bug_338_openmeteo_call_counter.py"
    assert existing.exists(), f"Bestehende Testdatei fehlt: {existing}"

    proc = subprocess.run(
        ["uv", "run", "pytest", str(existing), "-q"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "Die 6 bestehenden bd8e1e2-Tests müssen nach der call_log-Konsolidierung "
        f"grün bleiben.\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )


# ---------------------------------------------------------------------------
# AC-4: analyze-Skript aggregiert beide JSONL-Dateien (Python + Go) gemeinsam
# ---------------------------------------------------------------------------

def test_ac4_analyze_aggregates_python_and_go_sources(tmp_path):
    """
    AC-4: scripts/analyze_openmeteo_calls.py liest beide Dateien
    (openmeteo_calls.jsonl + openmeteo_calls_go.jsonl) und aggregiert sie
    gemeinsam, wobei go_*- und Python-Quellen sichtbar bleiben.
    """
    script = REPO_ROOT / "scripts" / "analyze_openmeteo_calls.py"
    assert script.exists(), f"Auswertungs-Skript fehlt: {script}"

    py_jsonl = tmp_path / "openmeteo_calls.jsonl"
    go_jsonl = tmp_path / "openmeteo_calls_go.jsonl"

    py_rows = [
        {"ts": "2026-05-22T08:15:00+00:00", "endpoint": "https://api.open-meteo.com/v1/ecmwf",
         "status": 200, "source": "briefing", "error": None},
        {"ts": "2026-05-22T08:42:00+00:00", "endpoint": "https://api.open-meteo.com/v1/forecast",
         "status": 429, "source": "geosphere_clouds", "error": None},
    ]
    go_rows = [
        {"ts": "2026-05-22T09:05:00+00:00", "endpoint": "https://api.open-meteo.com/v1/dwd-icon",
         "status": 429, "source": "go_forecast", "error": ""},
        {"ts": "2026-05-22T09:55:00+00:00", "endpoint": "https://air-quality-api.open-meteo.com/v1/air-quality",
         "status": 200, "source": "go_uv", "error": ""},
    ]
    py_jsonl.write_text("\n".join(json.dumps(r) for r in py_rows) + "\n")
    go_jsonl.write_text("\n".join(json.dumps(r) for r in go_rows) + "\n")

    # Das Skript erhält die Python-JSONL als Argument und findet die Go-JSONL
    # als Geschwisterdatei (gleiches Verzeichnis) automatisch.
    proc = subprocess.run(
        [sys.executable, str(script), str(py_jsonl)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"Skript-Fehler:\n{proc.stderr}"
    out = proc.stdout

    # Gesamtzahl beider Dateien = 4 (eindeutiger Wortlaut aus dem Skript-Output)
    assert "Gesamt-Abrufe (beide Quellen): 4" in out, (
        f"Eindeutige Gesamtzahl-Zeile (beide Quellen = 4) fehlt im Output:\n{out}"
    )
    # Beide Sprachherkünfte sichtbar
    for src in ("geosphere_clouds", "go_forecast", "go_uv", "briefing"):
        assert src in out, f"Quelle '{src}' fehlt im aggregierten Output:\n{out}"
    # Endpoints aus beiden Dateien
    assert "/v1/dwd-icon" in out, f"Go-Endpoint fehlt:\n{out}"
    assert "/v1/ecmwf" in out, f"Python-Endpoint fehlt:\n{out}"


# ---------------------------------------------------------------------------
# AC-2 (Strukturprüfung): call_log-Modul exportiert die erwartete API
# ---------------------------------------------------------------------------

def test_call_log_module_exposes_api_and_marker_order():
    """
    AC-2 (Vertrag): providers.call_log stellt log_api_call, resolve_call_source,
    DIAGNOSTICS_PATH und _CALL_SOURCE_MARKERS bereit; der geosphere_clouds-Marker
    steht GANZ OBEN (Priorität).
    """
    from providers import call_log

    assert hasattr(call_log, "DIAGNOSTICS_PATH")
    assert callable(call_log.log_api_call)
    assert callable(call_log.resolve_call_source)
    assert call_log._CALL_SOURCE_MARKERS[0][0] == "_fetch_openmeteo_clouds"
    assert call_log._CALL_SOURCE_MARKERS[0][1] == "geosphere_clouds"

    # log_api_call ist fail-soft und parsebar.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        log_path = Path(td) / "openmeteo_calls.jsonl"
        orig = call_log.DIAGNOSTICS_PATH
        call_log.DIAGNOSTICS_PATH = log_path
        try:
            call_log.log_api_call("https://api.open-meteo.com/v1/forecast", 429)
        finally:
            call_log.DIAGNOSTICS_PATH = orig
        rows = _read_jsonl(log_path)
        assert rows and rows[-1]["status"] == 429
        datetime.fromisoformat(rows[-1]["ts"])
