"""TDD #586 — Alert-Config Design-Fidelity Close-Gate.

Beweist behavioral, dass die LIVE Alert-Config (Trip-Detail → Tab "Alerts")
mit dem bindenden JSX `screen-alert-config.jsx` übereinstimmt.

Vorgehen (kein Mock, kein String-Check):
- Phase 6 erzeugt zwei echte PNGs unter docs/artifacts/issue-586-fidelity-gate/:
    * live-alert-config.png      — Screenshot des Live-Alarme-Tabs (Staging @1440px)
    * reference-alert-config.png — aus der bindenden JSX gerenderte Referenz
- Diese Tests rechnen den Pixel-Diff zwischen beiden Bildern SELBST aus
  (gleiche Logik wie das Gate-Tool, Pixel-Threshold 30) und fordern < 10 %.

Das offizielle SOLL-PNG `K-alert-config-list.png` wird BEWUSST NICHT als Referenz
genutzt: es zeigt einen anderen Screen (Reports/Kanäle inkl. des per #610 entfernten
Signal-Kanals), nicht den Alert-Schwellwert-Konfigurator der JSX. Projekt-Regel:
JSX ist die bindende Wahrheit.

RED: Die beiden PNGs existieren noch nicht → Tests schlagen fehl.
GREEN: Nach der Messung in Phase 6 liegen die Bilder vor und der Diff < 10 %.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ARTIFACT_DIR = Path("docs/artifacts/issue-586-fidelity-gate")
LIVE_PNG = ARTIFACT_DIR / "live-alert-config.png"
REFERENCE_PNG = ARTIFACT_DIR / "reference-alert-config.png"
GATE_JSON = ARTIFACT_DIR / "design-diff-K-alert-config-list.json"

THRESHOLD_PCT = 10.0


def _pixel_diff_pct(ist_path: Path, soll_path: Path) -> float:
    """Identische Logik wie .claude/hooks/design_fidelity_diff.py::compute_diff."""
    ist_img = Image.open(ist_path).convert("RGB")
    soll_img = Image.open(soll_path).convert("RGB").resize(ist_img.size, Image.LANCZOS)
    ist_arr = np.array(ist_img, dtype=int)
    soll_arr = np.array(soll_img, dtype=int)
    diff_arr = np.abs(ist_arr - soll_arr)
    changed = np.any(diff_arr > 30, axis=2)
    return float(changed.sum()) / changed.size * 100


def test_live_and_reference_screenshots_exist() -> None:
    """AC-1/AC-2: Live-Screenshot und JSX-gerenderte Referenz müssen vorliegen."""
    assert LIVE_PNG.exists(), (
        f"Live-Screenshot fehlt: {LIVE_PNG} — Alarme-Tab @1440px von Staging erfassen"
    )
    assert REFERENCE_PNG.exists(), (
        f"JSX-Referenz fehlt: {REFERENCE_PNG} — aus screen-alert-config.jsx rendern"
    )
    assert LIVE_PNG.stat().st_size > 5000, "Live-PNG zu klein — vermutlich leerer Screenshot"
    assert REFERENCE_PNG.stat().st_size > 5000, "Referenz-PNG zu klein"


def test_live_matches_binding_jsx_under_threshold() -> None:
    """AC-3: Pixel-Diff Live vs. JSX-Referenz < 10 % (eigenständig berechnet)."""
    if not (LIVE_PNG.exists() and REFERENCE_PNG.exists()):
        pytest.fail("Bilder fehlen — Messung (Phase 6) noch nicht durchgeführt")
    diff_pct = _pixel_diff_pct(LIVE_PNG, REFERENCE_PNG)
    assert diff_pct < THRESHOLD_PCT, (
        f"Live-Alarm-Config weicht {diff_pct:.2f}% von der bindenden JSX ab "
        f"(Schwelle {THRESHOLD_PCT}%) — Layout-Drift gegen screen-alert-config.jsx"
    )


def test_gate_artifact_passed() -> None:
    """AC-3/AC-5: PASS-Artefakt für den Close-Gate-Hook liegt vor und ist bestanden."""
    assert GATE_JSON.exists(), f"Gate-Artefakt fehlt: {GATE_JSON}"
    report = json.loads(GATE_JSON.read_text())
    assert report.get("passed") is True, f"Gate nicht bestanden: {report}"
    assert report.get("diff_pct", 100) < THRESHOLD_PCT, (
        f"diff_pct {report.get('diff_pct')} >= {THRESHOLD_PCT}"
    )
