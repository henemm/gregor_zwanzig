# doc-compliance-test
"""Issue #1208 AC-3 — Struktur-Test: keine report_config-Direktzugriffe im Versandpfad.

Spec: docs/specs/modules/report_config_resolver.md

AST-Assertion (Vorbild tests/tdd/test_765_backend_hygiene_compliance.py):
Die Module des Scheduler-Versandpfads duerfen render-relevante
`report_config`-Felder NICHT mehr direkt lesen — ausschliesslich ueber das
aufgeloeste ReportRenderOptions-Objekt aus
`src/services/report_config_resolver.py` (dieses Modul ist als einziger
Leser whitelisted und wird hier nicht gescannt; Loader/Modelle ebenfalls).

Erfasst werden auch Alias-Zugriffe (`rc = trip.report_config; rc.email_format`).

Nicht-Render-Felder (Zeitplanung, Kanalwahl, Alert-Schwellen, Pre-Render-
Gates) bleiben im Scheduler erlaubt — sie sind laut Spec RENDER_NEUTRAL und
gehoeren nicht in ReportRenderOptions.

RED-Phase: trip_report_scheduler.py und trip_report.py lesen heute mehrere
Render-Felder direkt → Test schlaegt mit Datei+Zeile fehl.
"""
from __future__ import annotations

import ast
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Versandpfad-Module, die render-relevante Felder NUR via Options lesen duerfen.
_SCANNED_FILES = [
    "src/services/trip_report_scheduler.py",
    "src/output/renderers/trip_report.py",
    "src/services/notification_service.py",
]

# Render-klassifizierte Felder (8 render-wirksame + 4 tote #790-Toggles).
# Direktzugriff auf diese Felder ausserhalb des Resolvers = Verstoss.
_FORBIDDEN_FIELDS = {
    # render-wirksam (muenden in ReportRenderOptions)
    "email_format",
    "show_outlook",
    "show_stage_stats",
    "show_stability",
    "show_compact_summary",
    "show_daylight",
    "multi_day_trend_reports",
    "show_yesterday_comparison",
    # tote #790-Toggles (RENDER_NEUTRAL, aber Render-Domaene — kein Handout)
    "show_quick_take_tags",
    "show_highlights",
    "daily_summary_metrics",
    "show_metrics_summary",
}


def _collect_aliases(tree: ast.AST) -> set[str]:
    """Namen, die an ein report_config-Objekt gebunden werden.

    Erfasst: `x = <expr>.report_config`, `x = report_config` sowie
    Funktionsparameter namens `report_config`.
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


def test_no_direct_render_field_reads_in_send_path():
    """AC-3: Given der Versandpfad nach dem Umbau / When der Quellcode per AST
    geprueft wird / Then existiert KEIN direkter Lesezugriff auf
    render-klassifizierte report_config-Felder mehr — nur noch via Resolver."""
    all_findings: list[str] = []
    for rel_path in _SCANNED_FILES:
        all_findings.extend(_violations_in(rel_path))
    assert not all_findings, (
        "AC-3: Direktzugriffe auf render-relevante report_config-Felder im "
        "Versandpfad gefunden (muessen ueber ReportRenderOptions laufen):\n  "
        + "\n  ".join(all_findings)
    )


def test_scanned_files_exist_and_parse():
    """Selbstschutz: Umbenannte/verschobene Pfade duerfen den AC-3-Test nicht
    still ins Leere laufen lassen."""
    for rel_path in _SCANNED_FILES:
        source_path = _PROJECT_ROOT / rel_path
        assert source_path.exists(), f"Gescanntes Modul fehlt: {rel_path}"


def test_send_path_uses_resolver():
    """AC-3-Gegenstueck: Der Scheduler-Versandpfad importiert den zentralen
    Resolver (kein zweiter, paralleler Ableitungsweg) — AST-Import-Pruefung."""
    source_path = _PROJECT_ROOT / "src/services/trip_report_scheduler.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports_resolver = any(
        (isinstance(node, ast.ImportFrom)
         and node.module and "report_config_resolver" in node.module)
        or (isinstance(node, ast.Import)
            and any("report_config_resolver" in a.name for a in node.names))
        for node in ast.walk(tree)
    )
    assert imports_resolver, (
        "AC-3: trip_report_scheduler.py muss resolve_report_render_options aus "
        "src/services/report_config_resolver.py importieren und konsumieren"
    )
