"""Wächter — kein Renderer liest die globale Katalog-Ampel (Issue #2792 S1c-1).

SPEC: docs/specs/modules/feat_2792_s1_profil_ampel.md §5 („danach liest kein
Leser ``display_thresholds`` als Nutzer-Bewertung"), Test Plan
``test_kein_leser_liest_display_thresholds.py``.

Nach ADR-0106 ist die Profil-Ampel des Abos die einzige Bewertung. Jeder
Renderer in ``src/output/**`` (inkl. ``renderers/alert/**``) bekommt die
Schwellen über das durchgereichte Ampel-Objekt. Zwei Bugklassen werden per
AST erkannt (Vorbild ``tests/test_output_timezone_guard.py``):

1. Zugriff auf ``.display_thresholds`` bzw. ``getattr(x, "display_thresholds")``.
2. Aufruf ``severity_for(...)`` ohne Schlüsselwort ``ampel=``.

``KNOWN_VIOLATIONS`` ist leer und darf nur leer bleiben: neue Funde machen
den Test rot. Die CAPE-Brücke (S1c-1 noch Katalog-Farbe, entfällt in S1c-4)
liegt bewusst in ``src/app/ampel.py`` außerhalb dieses Scans.

Kern-Schicht: statische Analyse des Quellbaums, kein Netz, keine Mocks.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_OUTPUT = _ROOT / "src" / "output"

# Ausnahmen (Datei relativ zu src/output, Zeile entfällt bewusst, damit
# Verschiebungen nicht wackeln) -> Begründung. Darf nur schrumpfen.
KNOWN_VIOLATIONS: dict[str, str] = {}


def _funde() -> list[str]:
    funde: list[str] = []
    for py in sorted(_OUTPUT.rglob("*.py")):
        rel = py.relative_to(_OUTPUT).as_posix()
        baum = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(baum):
            if isinstance(node, ast.Attribute) and node.attr == "display_thresholds":
                funde.append(f"{rel}:{node.lineno}: .display_thresholds")
            elif isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else None
                if name == "getattr" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) \
                        and node.args[1].value == "display_thresholds":
                    funde.append(f"{rel}:{node.lineno}: getattr(..., 'display_thresholds')")
                if name == "severity_for" and not any(k.arg == "ampel" for k in node.keywords):
                    funde.append(f"{rel}:{node.lineno}: severity_for(...) ohne ampel=")
    return funde


def test_scanner_findet_ueberhaupt_etwas_in_src_output():
    """Selbsttest: der Scan läuft über den echten Baum (sonst wäre leer = grün)."""
    assert len(list(_OUTPUT.rglob("*.py"))) > 50


def test_kein_renderer_liest_display_thresholds_oder_bewertet_ohne_ampel():
    neu = [f for f in _funde() if f.split(":", 1)[0] not in KNOWN_VIOLATIONS]
    assert neu == [], (
        "Renderer lesen die globale Katalog-Ampel statt der Profil-Ampel des "
        "Abos (ADR-0106, #2792). Schwellen über das durchgereichte "
        "``ampel``-Objekt lesen:\n" + "\n".join(neu)
    )


def test_ausnahmeliste_enthaelt_nur_noch_echte_funde():
    """Die Liste darf nur schrumpfen: behobene Funde müssen raus."""
    dateien = {f.split(":", 1)[0] for f in _funde()}
    veraltet = sorted(set(KNOWN_VIOLATIONS) - dateien)
    assert veraltet == [], f"veraltete Ausnahmen entfernen: {veraltet}"
