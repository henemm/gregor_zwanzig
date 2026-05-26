"""TDD RED: Issue #377 — Contrast-Audit der Ink-Skala (WCAG-AA auf weißer Card).

Spec: docs/specs/modules/issue_377_contrast_audit.md
Manifest: docs/specs/tests/issue_377_contrast_audit_tests.md

Prueft das (noch nicht existierende) Mess-Werkzeug scripts/contrast_audit.py:
- contrast_ratio(): WCAG-2.1-relative-luminance-Berechnung (keine Mocks, echte Mathematik)
- classify(): Zuordnung Ratio -> WCAG-Freigabe-Klasse

RED-Zustand: scripts/contrast_audit.py existiert noch nicht -> Modul-Load wirft
FileNotFoundError beim Collecten -> alle Tests erroren. Nach GREEN: Script liefert
die in der Spec dokumentierten, real gemessenen Werte.

Ausfuehrung:
    uv run pytest tests/tdd/test_issue_377_contrast_audit.py -v
"""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "contrast_audit.py"


def _load_module():
    """Laedt scripts/contrast_audit.py als Modul. RED: Datei fehlt -> FileNotFoundError."""
    spec = importlib.util.spec_from_file_location("contrast_audit", _SCRIPT)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(f"Mess-Script nicht ladbar: {_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # FileNotFoundError wenn _SCRIPT fehlt (RED)
    return mod


@pytest.fixture(scope="module")
def cab():
    return _load_module()


# --- WCAG-Referenzpaare ---


def test_contrast_ratio_black_on_white(cab):
    """AC-1: schwarz auf weiss = 21.0:1 (WCAG-Maximum)."""
    assert abs(cab.contrast_ratio("#000000", "#ffffff") - 21.0) < 0.05


def test_contrast_ratio_white_on_white(cab):
    """AC-1: white-on-white = 1.0:1 (kein Kontrast)."""
    assert abs(cab.contrast_ratio("#ffffff", "#ffffff") - 1.0) < 0.01


# --- Token-Verstoesse und -Konformitaet auf weisser Card (#ffffff) ---


def test_ink_faint_fails_on_card(cab):
    """AC-2: --g-ink-faint #9c9a90 auf weiss faellt durch (< 3.0:1)."""
    assert cab.contrast_ratio("#9c9a90", "#ffffff") < 3.0


def test_ink_4_fails_on_card(cab):
    """AC-2: --g-ink-4 #9a958a auf weiss faellt ebenfalls durch (< 3.0:1)."""
    assert cab.contrast_ratio("#9a958a", "#ffffff") < 3.0


def test_ink_muted_passes_on_card(cab):
    """AC-3: --g-ink-muted #5c5a52 auf weiss erfuellt AA (>= 4.5:1)."""
    assert cab.contrast_ratio("#5c5a52", "#ffffff") >= 4.5


def test_accent_fails_body_text(cab):
    """AC-2: --g-accent #c45a2a auf weiss ist nur AA-large, faellt fuer Body-Text durch (< 4.5:1)."""
    assert cab.contrast_ratio("#c45a2a", "#ffffff") < 4.5


def test_accent_deep_passes(cab):
    """AC-3: --g-accent-deep #8c3e1a auf weiss erfuellt AA (>= 4.5:1)."""
    assert cab.contrast_ratio("#8c3e1a", "#ffffff") >= 4.5


# --- Klassifikations-Funktion ---


def test_classify_thresholds(cab):
    """AC-1: classify() ordnet Ratios den WCAG-Freigabe-Klassen zu."""
    assert cab.classify(21.0) == "AAA-text"
    assert cab.classify(7.0) == "AAA-text"
    assert cab.classify(4.5) == "AA-text"
    assert cab.classify(3.0) == "AA-large"
    assert cab.classify(2.82) == "FAIL"
