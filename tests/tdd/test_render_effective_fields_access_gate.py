"""Issue #1209 AC-3 — src-weiter Struktur-Gate: render-wirksame report_config-
Felder duerfen NUR ueber den Resolver gelesen werden.

Spec: docs/specs/modules/report_config_resolver_slice_b.md

Erweitert den Scheibe-A-Gate (`tests/tdd/test_report_config_scheduler_structure.py`,
feste Dateiliste) auf den VOLLEN `src/services/` + `src/output/`-Baum. Geprueft
werden AUSSCHLIESSLICH die 7 `RENDER_EFFECTIVE_FIELDS` aus
`services.report_config_resolver` (importiert, keine Kopie) — RENDER_NEUTRAL-
Felder (`morning_time`, `wind_exposition_min_elevation_m`, `alert_on_changes`,
`alert_preset` etc.) bleiben ausdruecklich unangetastet (Gegenprobe-Test).

Whitelist (keine Verstoss-Pruefung): `src/services/report_config_resolver.py`
selbst (einziger legitimer Leser), `src/app/loader.py`, `src/app/models.py`.

RED-Grund: `src/services/preview_service.py:121` liest
`trip.report_config.show_compact_summary` direkt (Patch-Hack F002) statt
ueber den Resolver -> Fund mit Datei+Zeile.
"""
from __future__ import annotations

import ast
from pathlib import Path

from services.report_config_resolver import RENDER_EFFECTIVE_FIELDS

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

_SCAN_ROOTS = ["src/services", "src/output"]

_WHITELIST = {
    "src/services/report_config_resolver.py",
    "src/app/loader.py",
    "src/app/models.py",
}

_FORBIDDEN_FIELDS: set[str] = set(RENDER_EFFECTIVE_FIELDS)


def _collect_aliases(tree: ast.AST) -> set[str]:
    """Namen, die an ein report_config-Objekt gebunden werden.

    Erfasst: `x = <expr>.report_config`, `x = report_config` sowie
    Funktionsparameter namens `report_config`. Identisches Muster wie
    `test_report_config_scheduler_structure.py::_collect_aliases`.
    """
    aliases: set[str] = {"report_config"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = node.value
            is_rc = (
                (isinstance(value, ast.Attribute) and value.attr == "report_config")
                or (isinstance(value, ast.Name) and value.id in aliases)
            )
            if is_rc:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        aliases.add(target.id)
    return aliases


def _violations_in(rel_path: str) -> list[str]:
    source_path = _PROJECT_ROOT / rel_path
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    aliases = _collect_aliases(tree)
    findings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if node.attr not in _FORBIDDEN_FIELDS:
            continue
        value = node.value
        direct_chain = isinstance(value, ast.Attribute) and value.attr == "report_config"
        alias_read = isinstance(value, ast.Name) and value.id in aliases
        if direct_chain or alias_read:
            findings.append(f"{rel_path}:{node.lineno} — report_config.{node.attr}")
    return findings


def _scanned_files() -> list[str]:
    files: list[str] = []
    for root in _SCAN_ROOTS:
        for path in sorted((_PROJECT_ROOT / root).rglob("*.py")):
            rel = str(path.relative_to(_PROJECT_ROOT))
            if rel in _WHITELIST:
                continue
            files.append(rel)
    return files


def test_render_effective_fields_only_via_resolver():
    """AC-3: Given der komplette Quellbaum unter src/services/ + src/output/
    ausserhalb der Whitelist / When per AST alle Direktzugriffe der 7
    RENDER_EFFECTIVE_FIELDS gesucht werden / Then existiert KEIN Fund."""
    all_findings: list[str] = []
    for rel_path in _scanned_files():
        all_findings.extend(_violations_in(rel_path))
    assert not all_findings, (
        "AC-3: Direktzugriffe auf render-wirksame report_config-Felder "
        "ausserhalb des Resolvers gefunden (muessen ueber "
        "resolve_report_render_options()/ReportRenderOptions laufen):\n  "
        + "\n  ".join(all_findings)
    )


def test_render_effective_fields_is_exactly_seven():
    """Selbstschutz: die gescannte Feldmenge muss den 7 dokumentierten
    render-wirksamen Feldern entsprechen (kein stiller Drift)."""
    assert len(RENDER_EFFECTIVE_FIELDS) == 7, (
        f"Erwartet 7 RENDER_EFFECTIVE_FIELDS, gefunden {len(RENDER_EFFECTIVE_FIELDS)}: "
        f"{RENDER_EFFECTIVE_FIELDS!r}"
    )


def test_scan_roots_exist_and_nonempty():
    """Selbstschutz: verschobene/umbenannte Scan-Wurzeln duerfen den Gate
    nicht still ins Leere laufen lassen."""
    files = _scanned_files()
    assert files, "Kein Python-Modul unter src/services/ oder src/output/ gefunden"
    for root in _SCAN_ROOTS:
        assert (_PROJECT_ROOT / root).is_dir(), f"Scan-Wurzel fehlt: {root}"


def test_render_neutral_access_not_flagged_gegenprobe():
    """Gegenprobe (AC-3): RENDER_NEUTRAL-Zugriffe duerfen NICHT als Verstoss
    gewertet werden — sonst waere der Gate strukturell nie bestehbar
    (Risiko aus dem Context-Dokument). Prueft die konkreten Bestandszugriffe
    `morning_time` (trip_report_scheduler.py) und
    `wind_exposition_min_elevation_m` (stage_weather.py)."""
    assert "morning_time" not in _FORBIDDEN_FIELDS
    assert "wind_exposition_min_elevation_m" not in _FORBIDDEN_FIELDS
    assert "alert_on_changes" not in _FORBIDDEN_FIELDS
    assert "alert_preset" not in _FORBIDDEN_FIELDS

    scheduler_findings = _violations_in("src/services/trip_report_scheduler.py")
    assert not any("morning_time" in f for f in scheduler_findings), (
        f"RENDER_NEUTRAL-Feld 'morning_time' wurde faelschlich als Verstoss "
        f"gewertet: {scheduler_findings!r}"
    )

    stage_weather_path = _PROJECT_ROOT / "src/services/stage_weather.py"
    if stage_weather_path.exists():
        stage_findings = _violations_in("src/services/stage_weather.py")
        assert not any("wind_exposition_min_elevation_m" in f for f in stage_findings), (
            f"RENDER_NEUTRAL-Feld 'wind_exposition_min_elevation_m' wurde "
            f"faelschlich als Verstoss gewertet: {stage_findings!r}"
        )
