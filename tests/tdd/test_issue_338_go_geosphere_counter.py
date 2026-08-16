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
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Scheibe 2c (#1211): Modul-Marker per Code-Inspektion (Subprozess-Datei,
# nicht per Probe messbar) test-genau feingeschnitten -- ac2 dialt real,
# ac3 startet einen Subprozess, der real gegen api.open-meteo.com dialt;
# ac4 + test_call_log_module_exposes_api_and_marker_order sind rein lokal
# und kommen in den Kern zurueck.

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def subprozess_lauf_ist_beweiskraeftig(proc: "subprocess.CompletedProcess") -> bool:
    """#1708 B1 AC-7: Exit-Code 0 allein beweist nichts -- ein komplett
    uebersprungener Lauf liefert ebenfalls Exit 0 (Befund #1708 B1: genau das
    verdeckte den Skip aus test_bug_338_openmeteo_call_counter.py:211-213
    bisher). Beweiskraeftig ist nur ein Lauf mit returncode 0, OHNE einen
    einzigen Skip und mit mindestens einem tatsaechlich ausgefuehrten Test.
    """
    if proc.returncode != 0:
        return False
    if re.search(r"\bskipped\b", proc.stdout, re.IGNORECASE):
        return False
    match = re.search(r"(\d+) passed", proc.stdout)
    return bool(match) and int(match.group(1)) > 0


# ---------------------------------------------------------------------------
# AC-2: Geosphere _fetch_openmeteo_clouds protokolliert source="geosphere_clouds"
# ---------------------------------------------------------------------------

@pytest.mark.live  # Dialt real bzw. fail-soft-Fetch (#1211 Scheibe 2c) -- nur via -m live
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

@pytest.mark.live  # Dialt real bzw. fail-soft-Fetch (#1211 Scheibe 2c) -- nur via -m live.
# #1708 B1: weiterhin berechtigt -- `-o addopts=` neutralisiert die
# Marker-Filterung im Subprozess, 3 der 6 Zieltests (ac1, ac2_alarm, ac3)
# brauchen echten Netzzugriff -- sie rufen mit `enrich_ensemble=False` ohne
# den Ensemble-Spread-Fallback, der bei den anderen 3 (ac2_trend,
# ac2_preview, ac4) den Offline-Log-Nachweis traegt (gemessen 2026-08-16,
# Details s. test_bug_338_openmeteo_call_counter.py). Ein Standardlauf ohne
# Marker wuerde also entweder haengen/timeouten (kein Netz im
# deterministischen Kern) oder faelschlich "beweiskraeftig" aussehen, ohne
# echten Netzzugriff gehabt zu haben.
def test_ac3_existing_six_tests_still_green():
    """
    AC-3: Nach der Konsolidierung der Logging-Logik in `providers.call_log`
    müssen die 6 bestehenden Tests aus tests/tdd/test_bug_338_openmeteo_call_counter.py
    weiterhin grün sein (identisches Verhalten).

    Wir führen sie als Sub-Prozess aus und prüfen mit
    `subprozess_lauf_ist_beweiskraeftig` (#1708 B1 AC-7), dass der Lauf
    tatsaechlich etwas bewiesen hat -- ein reiner Exit-Code-0-Check waere
    auch bei einem komplett uebersprungenen Lauf gruen (Befund #1708 B1).

    Scheibe 2c (#1211) Vakuum-Test-Fix: die Zieldatei trug frueher selbst
    `pytestmark = pytest.mark.live`, daher deselektierte die geerbte
    pyproject-addopts (`-m 'not email and not live and not staging'`) ALLE
    6 Zieltests -- ohne `-o addopts=` lief dieser Subprozess bislang mit
    Exit 5 (no tests collected) durch: Zieltests wurden deselektiert, Lauf
    verifizierte nichts (Adversary F002, #1211-2c, empirisch korrigiert).
    `-o addopts=` neutralisiert die Marker-Filterung, damit die 6 Tests
    tatsaechlich ausgefuehrt werden -- das gilt nach #1708 B1 unveraendert,
    weil der Modul-Marker der Zieldatei durch 6 Funktions-Marker ersetzt
    wurde (3 live + 3 disable_socket/offline), die `-o addopts=` weiterhin
    fuer die live-markierten neutralisiert (die 3 disable_socket-Tests
    laufen ohnehin, unabhaengig von addopts, da das ein eigener Mechanismus
    von pytest-socket ist).
    """
    existing = REPO_ROOT / "tests" / "tdd" / "test_bug_338_openmeteo_call_counter.py"
    assert existing.exists(), f"Bestehende Testdatei fehlt: {existing}"

    proc = subprocess.run(
        ["uv", "run", "pytest", str(existing), "-q", "-o", "addopts="],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert subprozess_lauf_ist_beweiskraeftig(proc), (
        "Die 6 bestehenden bd8e1e2-Tests müssen nach der call_log-Konsolidierung "
        f"grün bleiben (nicht nur Exit 0 -- kein Skip, mindestens 1 passed).\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
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
