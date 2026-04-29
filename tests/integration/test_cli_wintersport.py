"""
Integration tests for CLI Wintersport-Pipeline (β4 — TDD RED Phase).

SPEC: docs/specs/modules/wintersport_profile_consolidation.md §A3, §A4
TESTS-SPEC: docs/specs/tests/wintersport_profile_consolidation_tests.md
EPIC: render-pipeline-consolidation (#96), Phase β4

RED-Zustand (jetzt):
  CLI ruft noch WintersportFormatter — Output ist Legacy-Format
  ('T-15/-5 WC-22 W45 G78 R0.2 SN25'), nicht neue Pipeline-Form.
  Adapter-/Renderer-Module fehlen → ImportError.

GREEN-Zustand (nach β4-Implementation):
  CLI ruft _trip_result_to_normalized + build_token_line + render_sms /
  render_text_report. Output enthält neue Token-Form (`Stage:` Prefix
  + Wintersport-Tokens).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def wintersport_trip_file(tmp_path: Path) -> Path:
    """Create a minimal wintersport trip JSON for CLI consumption."""
    trip = {
        "id": "stubai-test",
        "name": "Stubaier Skitour",
        "stages": [
            {
                "id": "T1",
                "name": "Tag 1",
                "date": "2026-01-15",
                "waypoints": [
                    {
                        "id": "G1", "name": "Start",
                        "lat": 47.0, "lon": 11.0, "elevation_m": 1700,
                        "time_window": "08:00-10:00",
                    },
                    {
                        "id": "G2", "name": "Gipfel",
                        "lat": 47.05, "lon": 11.05, "elevation_m": 3200,
                        "time_window": "11:00-13:00",
                    },
                ],
            }
        ],
        "avalanche_regions": ["AT-7"],
        "aggregation": {"profile": "wintersport"},
    }
    path = tmp_path / "stubaier.json"
    path.write_text(json.dumps(trip), encoding="utf-8")
    return path


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run CLI as subprocess via `python -m src.app.cli`."""
    cmd = [sys.executable, "-m", "src.app.cli", *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_cli_compact_uses_pipeline(wintersport_trip_file: Path):
    """
    GIVEN: Wintersport-Trip-Fixture.
    WHEN:  CLI mit `--trip <fixture> --compact --dry-run` aufgerufen.
    THEN:  CLI importiert `_trip_result_to_normalized` aus dem neuen Adapter
           (Pipeline ist gewired), Output enthält Stage-Prefix `Stubaier:`,
           Länge ≤160, NIEMALS Legacy-Form `T-15/-5`.

    Spec §A3 — Compact-Pfad bit-identisch durch Pipeline.

    Adversary-Härtung: Test prüft *strukturell*, dass CLI das neue
    Adapter-Modul importiert. Reine Output-Asserts greifen in RED nicht,
    weil die Trip-Fixture ohne Provider-Key leeren Forecast liefert und
    der Header-Trip-Name `Stubaier` fälschlicherweise die Body-Asserts
    erfüllt. Erst der Pipeline-Wiring-Check macht den Test echt RED.
    """
    cli_source = (PROJECT_ROOT / "src" / "app" / "cli.py").read_text(
        encoding="utf-8",
    )
    assert "from src.output.adapters.trip_result import" in cli_source or \
           "from output.adapters.trip_result import" in cli_source, (
        "CLI muss `_trip_result_to_normalized` aus "
        "src.output.adapters.trip_result importieren — Pipeline noch nicht "
        "gewired (Spec §A3)."
    )
    assert "from formatters.wintersport import WintersportFormatter" \
        not in cli_source, (
        "CLI darf `WintersportFormatter` nicht mehr importieren — "
        "Big-Bang-Streichung §A1."
    )

    proc = _run_cli(
        "--trip", str(wintersport_trip_file),
        "--compact",
        "--dry-run",
        "--report", "evening",
        "--channel", "console",
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, (
        f"CLI fehlgeschlagen: stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    # Stage-Prefix muss aus build_token_line kommen — sanitized auf 10 Chars.
    # 'Stubaier Skitour' -> 'Stubaier S' (10 chars) gefolgt von ':'.
    assert "Stubaier" in output, (
        f"Stage-Prefix 'Stubaier' nicht im CLI-Output: {output!r}"
    )
    # Compact-Output sollte ≤160 Zeichen sein (SMS-Limit) auf der Body-Zeile.
    body_lines = [
        ln for ln in output.splitlines()
        if ln.strip() and "Stubaier" in ln and ":" in ln
    ]
    assert body_lines, f"Keine Body-Zeile mit Stage-Prefix: {output!r}"
    assert all(len(ln) <= 160 for ln in body_lines), (
        f"Compact-Body >160 Zeichen: "
        f"{[(ln, len(ln)) for ln in body_lines]!r}"
    )
    # Legacy-Form `T-15/-5` darf NICHT mehr im Output erscheinen.
    assert "T-15/-5" not in output, (
        f"Legacy WintersportFormatter-Form 'T-15/-5' noch im Output — "
        f"CLI nutzt nicht die neue Pipeline: {output!r}"
    )


def test_cli_long_report_contains_all_sections(wintersport_trip_file: Path):
    """
    GIVEN: Wintersport-Trip-Fixture mit avalanche_regions.
    WHEN:  CLI ohne --compact aufgerufen.
    THEN:  CLI importiert `render_text_report` aus neuem Renderer (Pipeline
           gewired); Output enthält 'ZUSAMMENFASSUNG', 'WEGPUNKT-DETAILS',
           'LAWINENREGIONEN', Trip-Name UPPERCASE, Token-Zeile sichtbar.

    Spec §A4 — Long-Report-Inhaltserhalt.
    """
    cli_source = (PROJECT_ROOT / "src" / "app" / "cli.py").read_text(
        encoding="utf-8",
    )
    assert "render_text_report" in cli_source, (
        "CLI muss `render_text_report` aus "
        "src.output.renderers.text_report importieren — Long-Report-Renderer "
        "noch nicht gewired (Spec §A4)."
    )

    proc = _run_cli(
        "--trip", str(wintersport_trip_file),
        "--dry-run",
        "--report", "evening",
        "--channel", "console",
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, (
        f"CLI fehlgeschlagen: stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert "ZUSAMMENFASSUNG" in output, (
        f"'ZUSAMMENFASSUNG' fehlt im Long-Report: {output!r}"
    )
    assert "WEGPUNKT-DETAILS" in output, (
        f"'WEGPUNKT-DETAILS' fehlt im Long-Report: {output!r}"
    )
    assert "LAWINENREGIONEN" in output, (
        f"'LAWINENREGIONEN' fehlt im Long-Report: {output!r}"
    )
    assert "STUBAIER SKITOUR" in output, (
        f"Trip-Name UPPERCASE fehlt: {output!r}"
    )
    # Token-Zeile mit Stage-Prefix muss sichtbar sein (Spec §A4 NEU).
    assert "Stubaier" in output and ":" in output, (
        f"Token-Zeile (Stage-Prefix) nicht im Long-Report: {output!r}"
    )


def test_cli_no_wintersport_formatter_import():
    """
    GIVEN: src/-Codebaum nach Big-Bang-Streichung (Spec §A1).
    WHEN:  Modul `formatters.wintersport` wird importiert.
    THEN:  ModuleNotFoundError — wintersport.py ist gelöscht.

    Zusätzlich: src/-Tree enthält keinen Import-String mehr.
    Tests/ wird nicht durchsucht, weil dieser Adversary-Test seine eigenen
    Suchstrings als Assertion-Texte enthält (Self-Reference-Vermeidung).
    """
    import importlib

    # Primary: Modul ist nicht mehr importierbar.
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("formatters.wintersport")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("src.formatters.wintersport")

    # Secondary: src/ enthält keine Referenzen mehr.
    src_dir = PROJECT_ROOT / "src"
    needles = (
        "from formatters" + ".wintersport",
        "import " + "WintersportFormatter",
        "from src.formatters" + ".wintersport",
    )
    for py_file in src_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for needle in needles:
            assert needle not in text, (
                f"Big-Bang-Streichung verletzt: '{needle}' in "
                f"{py_file.relative_to(PROJECT_ROOT)}"
            )


def test_cli_long_report_subject_unchanged(
    wintersport_trip_file: Path, tmp_path: Path,
):
    """
    GIVEN: CLI ohne --compact.
    WHEN:  CLI aufgerufen mit Wintersport-Trip + --report evening.
    THEN:  CLI nutzt `render_text_report` (Pipeline gewired); Subject bleibt
           `f"GZ Evening - {trip.name}"` (wie heute).

    Spec §5.3 Schritt 5: Subject im Long-Report-Pfad bleibt unverändert.
    """
    cli_source = (PROJECT_ROOT / "src" / "app" / "cli.py").read_text(
        encoding="utf-8",
    )
    assert "render_text_report" in cli_source, (
        "CLI muss `render_text_report` importieren — Long-Report-Pipeline "
        "noch nicht gewired (Spec §5.3 Schritt 5)."
    )

    proc = _run_cli(
        "--trip", str(wintersport_trip_file),
        "--dry-run",
        "--report", "evening",
        "--channel", "console",
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, (
        f"CLI fehlgeschlagen: stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    # ConsoleChannel printet typischerweise "Subject: ..." als Header.
    assert "Stubaier Skitour" in output, (
        f"Trip-Name (case-sensitive) muss im Subject erscheinen: {output!r}"
    )
    assert "Evening" in output, (
        f"ReportType.title() ('Evening') muss im Subject erscheinen: {output!r}"
    )
    assert "GZ" in output, (
        f"Subject-Präfix 'GZ' fehlt: {output!r}"
    )
