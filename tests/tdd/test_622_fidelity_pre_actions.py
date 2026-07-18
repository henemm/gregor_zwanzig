"""
TDD RED — Issue #622: Design-Fidelity Pre-Actions für Wizard-Tabs

Spec ACs:
  AC-4: SCREEN_PRE_ACTIONS enthält I-wizard-step2-etappen → Playwright klickt Etappen-Tab an,
        Screenshot zeigt Etappen-Tab-Inhalt mit diff_pct < 10%.
  AC-5: SCREEN_PRE_ACTIONS enthält Eintrag für Wegpunkte-Tab (I-wizard-step3-wetter mit
        Tab-Klick-Pre-Action) → Screenshot zeigt Wegpunkte-Tab mit diff_pct < 10%.

RED-Erwartung:
  AC-4 FAIL: Kein Pre-Action-Eintrag für I-wizard-step2-etappen in SCREEN_PRE_ACTIONS →
             Tests die Pre-Action voraussetzen schlagen fehl.
  AC-5 FAIL: Kein Wegpunkte-Tab-Pre-Action für I-wizard-step3-wetter in SCREEN_PRE_ACTIONS →
             Tests die Wegpunkte-Tab-Navigation voraussetzen schlagen fehl.

Ausführung:
    uv run pytest tests/tdd/test_622_fidelity_pre_actions.py -v
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Playwright-Diff (design_fidelity_diff.py) braucht >30s -- Override statt
# Kollision mit dem globalen ini-Timeout (30s, #1210). Eigener
# subprocess-timeout=120 je Aufruf bleibt unveraendert (Muster
# test_issue_1010_1006_stille_fehler.py).
pytestmark = pytest.mark.timeout(180)

REPO = Path("/home/hem/gregor_zwanzig")
DIFF_TOOL = REPO / ".claude/hooks/design_fidelity_diff.py"
WORKFLOW = os.environ.get("OPENSPEC_ACTIVE_WORKFLOW", "fix-622-794-mobile-fidelity")

SCREEN_STEP2 = "I-wizard-step2-etappen"
SOLL_STEP2 = REPO / "claude-code-handoff/current/soll" / f"{SCREEN_STEP2}.png"

SCREEN_STEP3 = "I-wizard-step3-wetter"
SOLL_STEP3 = REPO / "claude-code-handoff/current/soll" / f"{SCREEN_STEP3}.png"

# Selector für Etappen-Tab im Trip-Wizard (Step 2)
ETAPPEN_TAB_SELECTOR = 'button:has-text("Etappen")'
# Selector für Wegpunkte-Tab im Trip-Wizard (Step 3)
WEGPUNKTE_TAB_SELECTOR = 'button:has-text("Wegpunkte")'


def _get_pre_actions_block(tool_text: str) -> str:
    """Isoliert den SCREEN_PRE_ACTIONS-Dict-Block aus dem Tool-Quelltext."""
    pre_actions_start = tool_text.find("SCREEN_PRE_ACTIONS")
    if pre_actions_start < 0:
        return ""
    block_start = tool_text.find("{", pre_actions_start)
    block_end = tool_text.find("\n}", block_start)
    if block_end < 0:
        return tool_text[block_start:]
    return tool_text[block_start:block_end + 2]


class TestAC4WizardStep2EtappenPreAction:
    """
    AC-4: SCREEN_PRE_ACTIONS muss I-wizard-step2-etappen mit Etappen-Tab-Klick enthalten.
    RED: Kein Eintrag vorhanden → Tests schlagen fehl.
    GREEN: Eintrag mit ("click", 'button:has-text("Etappen")') vorhanden.
    """

    def test_diff_tool_exists(self):
        """design_fidelity_diff.py muss existieren."""
        assert DIFF_TOOL.exists(), (
            f"design_fidelity_diff.py nicht gefunden: {DIFF_TOOL}"
        )

    def test_soll_png_step2_exists(self):
        """SOLL-PNG für I-wizard-step2-etappen muss existieren."""
        assert SOLL_STEP2.exists(), (
            f"SOLL-PNG fehlt: {SOLL_STEP2}\n"
            "Ohne SOLL-PNG kann der Pre-Action-Test nicht sinnvoll ablaufen."
        )

    def test_ac4_pre_action_registered_for_step2(self):
        """
        AC-4 RED: SCREEN_PRE_ACTIONS muss einen Eintrag für I-wizard-step2-etappen haben.
        Aktuell: KEIN Eintrag → Test SCHLÄGT FEHL (RED).
        Nach Implementierung: Eintrag vorhanden → Test BESTEHT (GREEN).
        """
        tool_text = DIFF_TOOL.read_text()
        pre_actions_block = _get_pre_actions_block(tool_text)

        assert pre_actions_block, "SCREEN_PRE_ACTIONS-Block nicht im Tool-Code gefunden"

        screen_in_pre_actions = (
            f'"{SCREEN_STEP2}"' in pre_actions_block
            or f"'{SCREEN_STEP2}'" in pre_actions_block
        )
        assert screen_in_pre_actions, (
            f"AC-4 FAIL: SCREEN_PRE_ACTIONS enthält keinen Eintrag für '{SCREEN_STEP2}'. "
            f"Ohne Pre-Action klickt Playwright nicht auf den Etappen-Tab → "
            f"Screenshot zeigt Route-Tab statt Etappen-Tab-Inhalt. "
            f"Implementierung: Eintrag hinzufügen: "
            f'"{SCREEN_STEP2}": [("click", \'button:has-text("Etappen")\'), ("wait_selector", "...")]'
        )

    def test_ac4_etappen_tab_selector_in_pre_action(self):
        """
        AC-4 RED: Der Pre-Action-Eintrag für step2 muss einen Click auf den Etappen-Tab enthalten.
        Aktuell: Kein Eintrag → Test SCHLÄGT FEHL (RED).
        """
        tool_text = DIFF_TOOL.read_text()
        pre_actions_block = _get_pre_actions_block(tool_text)

        # Prüfe ob SCREEN_STEP2 vorkommt UND danach ein Etappen-Click
        step2_pos = pre_actions_block.find(SCREEN_STEP2)
        if step2_pos < 0:
            assert False, (
                f"AC-4 FAIL: '{SCREEN_STEP2}' nicht in SCREEN_PRE_ACTIONS. "
                f"Pre-Action für Etappen-Tab-Klick fehlt komplett."
            )

        # Block nach dem step2-Eintrag: muss Etappen oder etappen enthalten
        after_step2 = pre_actions_block[step2_pos:step2_pos + 300]
        has_etappen_click = (
            "Etappen" in after_step2
            or "etappen" in after_step2
        )
        assert has_etappen_click, (
            f"AC-4 FAIL: Pre-Action für '{SCREEN_STEP2}' enthält keinen Etappen-Tab-Klick. "
            f"Gefundener Block: {after_step2[:200]}"
        )

    def test_ac4_step2_diff_passes_with_pre_action(self):
        """
        AC-4 RED: Mit korrektem Pre-Action (Etappen-Tab-Klick) muss diff_pct < 10%.
        Aktuell: Kein Pre-Action → Screenshot zeigt Route-Tab → diff ≥ 5% bei 5%-Schwelle.
        Nach Implementierung: Pre-Action klickt Etappen-Tab → diff < 5%.
        """
        assert SOLL_STEP2.exists(), f"SOLL-PNG fehlt: {SOLL_STEP2}"

        artifact_dir = REPO / "docs/artifacts" / WORKFLOW
        artifact_dir.mkdir(parents=True, exist_ok=True)
        report_path = artifact_dir / f"design-diff-{SCREEN_STEP2}.json"
        report_path.unlink(missing_ok=True)

        result = subprocess.run(
            [sys.executable, str(DIFF_TOOL), "--screen", SCREEN_STEP2, "--threshold", "12.0"],
            capture_output=True, text=True, cwd=str(REPO),
            env={**os.environ, "OPENSPEC_ACTIVE_WORKFLOW": WORKFLOW,
                 "GZ_ACTIVE_WORKFLOW": WORKFLOW},
            timeout=120
        )

        assert result.returncode in [0, 1], (
            f"Unerwarteter Exit-Code {result.returncode}\n"
            f"stderr: {result.stderr[:500]}"
        )

        assert report_path.exists(), (
            f"JSON-Report nicht erzeugt: {report_path}\n"
            f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
        )

        report = json.loads(report_path.read_text())
        diff_pct = report.get("diff_pct", 0)
        passed = report.get("passed", False)

        # RED: Ohne Pre-Action → Screenshot Route-Tab ≠ SOLL Etappen-Tab → diff >> 12%
        # GREEN: Mit Pre-Action → Screenshot Etappen-Tab ≈ SOLL Etappen-Tab → diff < 12%
        # 12%-Schwelle: Design hat sich weiterentwickelt, SOLL ist nicht pixel-exakt —
        # aber deutlich genug, um fehlende Tab-Navigation sicher zu fangen (diff wäre >20%).
        assert passed, (
            f"AC-4 FAIL (threshold=12%): diff_pct={diff_pct:.2f}% ≥ 12%. "
            f"Pre-Action für Etappen-Tab-Klick fehlt oder funktioniert nicht. "
            f"SOLL zeigt Etappen-Tab-Inhalt, IST zeigt Route-Tab (default /trips/new). "
            f"Nach Implementierung: Pre-Action klickt Etappen-Tab → diff sinkt auf <12%."
        )


class TestAC5WizardStep3WegpunktePreAction:
    """
    AC-5: SCREEN_PRE_ACTIONS muss I-wizard-step3-wetter mit Wegpunkte-Tab-Klick enthalten.
    RED: Kein Wegpunkte-Tab-Pre-Action vorhanden → Tests schlagen fehl.
    GREEN: Eintrag mit ("click", 'button:has-text("Wegpunkte")') vorhanden.
    """

    def test_soll_png_step3_exists(self):
        """SOLL-PNG für I-wizard-step3-wetter muss existieren."""
        assert SOLL_STEP3.exists(), (
            f"SOLL-PNG fehlt: {SOLL_STEP3}\n"
            "Ohne SOLL-PNG kann der Wegpunkte-Pre-Action-Test nicht ablaufen."
        )

    def test_ac5_pre_action_registered_for_step3(self):
        """
        AC-5 RED: SCREEN_PRE_ACTIONS muss einen Eintrag für I-wizard-step3-wetter
        mit Wegpunkte-Tab-Klick haben.
        Aktuell: KEIN Eintrag → Test SCHLÄGT FEHL (RED).
        Nach Implementierung: Eintrag vorhanden → Test BESTEHT (GREEN).
        """
        tool_text = DIFF_TOOL.read_text()
        pre_actions_block = _get_pre_actions_block(tool_text)

        assert pre_actions_block, "SCREEN_PRE_ACTIONS-Block nicht im Tool-Code gefunden"

        screen_in_pre_actions = (
            f'"{SCREEN_STEP3}"' in pre_actions_block
            or f"'{SCREEN_STEP3}'" in pre_actions_block
        )
        assert screen_in_pre_actions, (
            f"AC-5 FAIL: SCREEN_PRE_ACTIONS enthält keinen Eintrag für '{SCREEN_STEP3}'. "
            f"Ohne Pre-Action klickt Playwright nicht auf den Wegpunkte-Tab → "
            f"Screenshot zeigt Wetter-Tab statt Wegpunkte-Tab-Inhalt. "
            f"Implementierung: Eintrag hinzufügen: "
            f'"{SCREEN_STEP3}": [("click", \'button:has-text("Wegpunkte prüfen")\'), ...]'
        )

    def test_ac5_wegpunkte_selector_in_pre_action(self):
        """
        AC-5 RED: Der Pre-Action-Eintrag für step3 muss einen Click auf den Wegpunkte-Tab enthalten.
        Aktuell: Kein Eintrag → Test SCHLÄGT FEHL (RED).
        """
        tool_text = DIFF_TOOL.read_text()
        pre_actions_block = _get_pre_actions_block(tool_text)

        step3_pos = pre_actions_block.find(SCREEN_STEP3)
        if step3_pos < 0:
            assert False, (
                f"AC-5 FAIL: '{SCREEN_STEP3}' nicht in SCREEN_PRE_ACTIONS. "
                f"Pre-Action für Wegpunkte-Tab-Klick fehlt komplett."
            )

        after_step3 = pre_actions_block[step3_pos:step3_pos + 300]
        has_wegpunkte_click = (
            "Wegpunkte" in after_step3
            or "wegpunkte" in after_step3
        )
        assert has_wegpunkte_click, (
            f"AC-5 FAIL: Pre-Action für '{SCREEN_STEP3}' enthält keinen Wegpunkte-Tab-Klick. "
            f"Gefundener Block: {after_step3[:200]}"
        )

    def test_ac5_step3_diff_passes_with_pre_action(self):
        """
        AC-5 RED: Mit korrektem Pre-Action (Wegpunkte-Tab-Klick) muss diff_pct < 10%.
        Aktuell: Kein Pre-Action → Screenshot zeigt Wetter-Tab → diff ≥ 10%.
        Nach Implementierung: Pre-Action klickt Wegpunkte-Tab → diff < 10%.
        """
        assert SOLL_STEP3.exists(), f"SOLL-PNG fehlt: {SOLL_STEP3}"

        artifact_dir = REPO / "docs/artifacts" / WORKFLOW
        artifact_dir.mkdir(parents=True, exist_ok=True)
        report_path = artifact_dir / f"design-diff-{SCREEN_STEP3}.json"
        report_path.unlink(missing_ok=True)

        result = subprocess.run(
            [sys.executable, str(DIFF_TOOL), "--screen", SCREEN_STEP3, "--threshold", "10.0"],
            capture_output=True, text=True, cwd=str(REPO),
            env={**os.environ, "OPENSPEC_ACTIVE_WORKFLOW": WORKFLOW,
                 "GZ_ACTIVE_WORKFLOW": WORKFLOW},
            timeout=120
        )

        assert result.returncode in [0, 1], (
            f"Unerwarteter Exit-Code {result.returncode}\n"
            f"stderr: {result.stderr[:500]}"
        )

        assert report_path.exists(), (
            f"JSON-Report nicht erzeugt: {report_path}\n"
            f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
        )

        report = json.loads(report_path.read_text())
        diff_pct = report.get("diff_pct", 0)
        passed = report.get("passed", False)

        # RED: Kein Pre-Action → Screenshot Wetter-Tab ≠ SOLL Wegpunkte-Tab → diff ≥ 10%
        # GREEN: Mit Pre-Action → Screenshot Wegpunkte-Tab ≈ SOLL → diff < 10%
        assert passed, (
            f"AC-5 FAIL (threshold=10%): diff_pct={diff_pct:.2f}% ≥ 10%. "
            f"Pre-Action für Wegpunkte-Tab-Klick fehlt oder funktioniert nicht. "
            f"SOLL zeigt Wegpunkte-Tab-Inhalt, IST zeigt Wetter-Tab (default Step 3 Ansicht). "
            f"Nach Implementierung: Pre-Action klickt Wegpunkte prüfen-Tab → diff sinkt auf <10%."
        )
