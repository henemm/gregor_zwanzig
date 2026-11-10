"""TDD RED: Danger-Rot im Kontrast-Messskript und auf der Design-Seite (Issue #1831, AC-5).

Spec: docs/specs/modules/fix_1831_danger_rot.md

Die Design-Seite (/_design) zeigt Kontrastzahlen, die aus scripts/contrast_audit.py stammen.
Das Skript spiegelt die Token-Werte aus frontend/src/app.css. Nach dem Wechsel auf #a83232
muss das Skript denselben Wert wie app.css messen (6.63 auf weisser Card), und die Design-Seite
muss genau diesen Wert anzeigen, nicht den alten #b33a2a / 5.91.

Keine Mocks: echtes Skript, echte app.css, echte Svelte-Quelle der Design-Seite.

Ausfuehrung:
    uv run pytest tests/tdd/test_danger_kontrast_audit.py -v
"""

import importlib.util
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "contrast_audit.py"
_APP_CSS = _ROOT / "frontend" / "src" / "app.css"
_DESIGN = _ROOT / "frontend" / "src" / "routes" / "_design" / "+page.svelte"


@pytest.fixture(scope="module")
def cab():
    spec = importlib.util.spec_from_file_location("contrast_audit", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _hell_root_danger() -> str:
    css = re.sub(r"/\*.*?\*/", "", _APP_CSS.read_text(encoding="utf-8"), flags=re.S)
    root = re.search(r":root\s*\{(.*?)\}", css, flags=re.S)
    assert root, ":root-Block fehlt in app.css"
    m = re.search(r"--g-danger\s*:\s*(#[0-9a-fA-F]{6})\s*;", root.group(1))
    assert m, "--g-danger fehlt im hellen :root"
    return m.group(1).lower()


def test_audit_spiegelt_g_danger_aus_app_css(cab):
    """AC-5: Skript misst denselben --g-danger-Wert, den app.css (hell) setzt."""
    assert cab.TOKENS["--g-danger"].lower() == _hell_root_danger() == "#a83232"


def test_audit_misst_g_danger_6_63_auf_card(cab):
    """AC-5: --g-danger auf weisser Card = 6.63:1 (AA), gemessen, nicht geschaetzt."""
    ratio = cab.contrast_ratio(cab.TOKENS["--g-danger"], "#ffffff")
    assert round(ratio, 2) == 6.63
    assert cab.classify(ratio) == "AA"


def test_design_seite_zeigt_gemessenen_g_danger_wert(cab):
    """AC-5: Design-Seite (Hell-Tabelle) nennt --g-danger mit Wert und Zahl aus dem Skript."""
    quelle = _DESIGN.read_text(encoding="utf-8")
    eintraege = re.findall(
        r"\{\s*name:\s*'--g-danger',\s*hex:\s*'(#[0-9a-fA-F]{6})',\s*ratio:\s*([\d.]+)", quelle
    )
    assert eintraege, "--g-danger-Eintraege fehlen auf der Design-Seite"
    hell_hex, hell_ratio = eintraege[0]
    erwartet = round(cab.contrast_ratio(cab.TOKENS["--g-danger"], "#ffffff"), 2)
    assert hell_hex.lower() == "#a83232"
    assert float(hell_ratio) == erwartet
