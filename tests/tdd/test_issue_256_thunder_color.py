"""
Tests für Bug #256 — --g-wx-thunder Farbkonflikt (violett vs. rot).

SPEC: docs/specs/modules/bug_256_thunder_color.md
TESTS-SPEC: docs/specs/tests/bug_256_thunder_color_tests.md

RED-Zustand (jetzt):
  app.css hat --g-wx-thunder: #5a3a7a (violett) — soll #c43a2a (rot) sein.
  design_tokens.py hat kein G_WX_THUNDER — soll ergänzt werden.
  design_system.md dokumentiert den Konflikt als offen — soll als gelöst markiert werden.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_CSS = REPO_ROOT / "frontend" / "src" / "app.css"
DESIGN_SYSTEM_MD = REPO_ROOT / "docs" / "reference" / "design_system.md"
DESIGN_SYSTEM_TOKENS_CSS = REPO_ROOT / "docs" / "reference" / "design_system_tokens.css"


# ---------------------------------------------------------------------------
# AC-1: app.css enthält den korrekten Rot-Wert
# ---------------------------------------------------------------------------

def test_ac1_app_css_thunder_is_red():
    """
    AC-1: --g-wx-thunder in app.css ist #c43a2a (rot), nicht #5a3a7a (violett).

    GIVEN frontend/src/app.css
    WHEN nach --g-wx-thunder gesucht wird
    THEN enthält die Zeile #c43a2a, nicht #5a3a7a
    """
    content = APP_CSS.read_text(encoding="utf-8")
    assert "#c43a2a" in content, (
        "--g-wx-thunder: #c43a2a (rot) fehlt in app.css — Bug #256 noch nicht gefixt"
    )
    assert "#5a3a7a" not in content, (
        "Veralteter Wert #5a3a7a (violett) noch in app.css — muss durch #c43a2a ersetzt werden"
    )


# ---------------------------------------------------------------------------
# AC-2: design_tokens.py exportiert G_WX_THUNDER
# ---------------------------------------------------------------------------

def test_ac2_design_tokens_py_constant():
    """
    AC-2: G_WX_THUNDER ist in design_tokens.py definiert und hat den Wert #c43a2a.

    GIVEN from src.output.renderers.email.design_tokens import G_WX_THUNDER
    WHEN der Wert geprüft wird
    THEN ist G_WX_THUNDER == "#c43a2a"
    """
    from src.output.renderers.email.design_tokens import G_WX_THUNDER  # noqa: PLC0415
    assert G_WX_THUNDER == "#c43a2a", (
        f"G_WX_THUNDER ist {G_WX_THUNDER!r}, erwartet '#c43a2a'"
    )


# AC-3 (test_ac3_no_old_value_in_tokens_py) — entfernt in #765.
# Las src/output/renderers/email/design_tokens.py als Quelltext (Datei-Inhalt-
# Anti-Pattern, CLAUDE.md). Das relevante Verhalten — die importierte Konstante
# G_WX_THUNDER trägt den korrekten Rot-Wert #c43a2a (statt des alten Violett
# #5a3a7a) — ist durch test_ac2_design_tokens_py_constant über den echten Import
# abgedeckt.


# ---------------------------------------------------------------------------
# AC-4: design_system.md zeigt Konflikt als gelöst
# ---------------------------------------------------------------------------

def test_ac4_design_system_md_updated():
    """
    AC-4: design_system.md dokumentiert den Konflikt als durch Issue #256 gelöst.

    GIVEN docs/reference/design_system.md
    WHEN der Inhalt auf --g-wx-thunder-Einträge geprüft wird
    THEN enthält er #c43a2a in der Token-Tabelle und verweist auf #256 als gelöst;
         #5a3a7a kommt nicht mehr als aktiver Wert vor
    """
    content = DESIGN_SYSTEM_MD.read_text(encoding="utf-8")
    lower = content.lower()

    assert "#c43a2a" in content, (
        "#c43a2a fehlt in design_system.md Token-Tabelle"
    )
    assert "#256" in content, (
        "Keine Referenz auf Issue #256 in design_system.md"
    )
    assert "gelöst" in lower or "resolved" in lower or "fixed" in lower, (
        "Konflikt nicht als gelöst markiert in design_system.md"
    )
    assert "#5a3a7a" not in content, (
        "Veralteter Wert #5a3a7a noch in design_system.md — muss entfernt werden"
    )


# ---------------------------------------------------------------------------
# AC-5: design_system_tokens.css hat korrekten Wert + Issue-Referenz
# ---------------------------------------------------------------------------

def test_ac5_design_system_tokens_css():
    """
    AC-5: design_system_tokens.css hat --g-weather-thunder: #c43a2a
          und einen Kommentar mit Verweis auf Issue #256.

    GIVEN docs/reference/design_system_tokens.css
    WHEN nach --g-weather-thunder gesucht wird
    THEN steht dahinter #c43a2a und in der Nähe eine #256-Referenz
    """
    content = DESIGN_SYSTEM_TOKENS_CSS.read_text(encoding="utf-8")
    assert "--g-weather-thunder" in content, (
        "--g-weather-thunder fehlt in design_system_tokens.css"
    )
    assert "#c43a2a" in content, (
        "#c43a2a fehlt in design_system_tokens.css"
    )
    assert "#256" in content, (
        "Kein Verweis auf Issue #256 in design_system_tokens.css"
    )


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
