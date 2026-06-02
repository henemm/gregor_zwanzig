"""
Tests für Bug #541 + #543 + #544 — Token-Cleanup, native Checkboxen, Tailwind-Rest

#543: Step3Weather + Step5Reports: native <input type="checkbox"> bricht Guard-Test
#544: WeatherConfigDialog: hover:bg-muted/50 (Tailwind-Residual)
#541: Alte Farb-Token-Aliasse --g-good/--g-warn/--g-bad müssen entfernt werden
"""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
APP_CSS = FRONTEND_SRC / "app.css"

STEP3 = FRONTEND_SRC / "lib" / "components" / "trip-wizard" / "steps" / "Step3Weather.svelte"
STEP5 = FRONTEND_SRC / "lib" / "components" / "trip-wizard" / "steps" / "Step5Reports.svelte"
WEATHER_DIALOG = FRONTEND_SRC / "lib" / "components" / "WeatherConfigDialog.svelte"


# ---------------------------------------------------------------------------
# AC-1: Keine nativen Checkboxen in Step3Weather
# ---------------------------------------------------------------------------

def test_ac1_step3weather_no_native_checkbox():
    """
    GIVEN: Step3Weather.svelte nach vollständiger Migration
    WHEN:  Datei nach type="checkbox" durchsucht wird
    THEN:  Kein Treffer außerhalb der Checkbox-Atomic-Komponente
    """
    content = STEP3.read_text()
    assert 'type="checkbox"' not in content, (
        "Step3Weather.svelte enthält noch native <input type=\"checkbox\"> — "
        "muss durch <Checkbox> aus $lib/components/ui/checkbox ersetzt werden"
    )


# ---------------------------------------------------------------------------
# AC-2: Keine nativen Checkboxen in Step5Reports
# ---------------------------------------------------------------------------

def test_ac2_step5reports_no_native_checkbox():
    """
    GIVEN: Step5Reports.svelte nach vollständiger Migration
    WHEN:  Datei nach type="checkbox" durchsucht wird
    THEN:  Kein Treffer außerhalb der Checkbox-Atomic-Komponente
    """
    content = STEP5.read_text()
    assert 'type="checkbox"' not in content, (
        "Step5Reports.svelte enthält noch native <input type=\"checkbox\"> — "
        "muss durch <Checkbox> aus $lib/components/ui/checkbox ersetzt werden"
    )


# ---------------------------------------------------------------------------
# AC-4: WeatherConfigDialog: kein hover:bg-muted/50 mehr
# ---------------------------------------------------------------------------

def test_ac4_weather_dialog_no_tailwind_hover():
    """
    GIVEN: WeatherConfigDialog.svelte nach Fix #544
    WHEN:  Datei nach hover:bg-muted durchsucht wird
    THEN:  Kein Treffer — Hover via var(--g-surface-2) statt Tailwind-Klasse
    """
    content = WEATHER_DIALOG.read_text()
    assert "hover:bg-muted" not in content, (
        "WeatherConfigDialog.svelte enthält noch 'hover:bg-muted' — "
        "Tailwind-Residual aus Spec #285 AC-4; ersetzen durch var(--g-surface-2)"
    )


# ---------------------------------------------------------------------------
# AC-5: Keine var(--g-good/warn/bad) CSS-Referenzen mehr in frontend/src/
# ---------------------------------------------------------------------------

def _find_old_token_files() -> list[Path]:
    """Dateien mit CSS-Variablen-Referenzen auf alte Token-Namen."""
    result = subprocess.run(
        ["rg", "--glob=*.svelte", "--glob=*.css", "-l",
         r"var\(--g-good\)|var\(--g-warn\)|var\(--g-bad\)",
         str(FRONTEND_SRC)],
        capture_output=True, text=True
    )
    if not result.stdout.strip():
        return []
    return [Path(p) for p in result.stdout.strip().splitlines()]


def test_ac5_no_old_token_references():
    """
    GIVEN: frontend/src/ nach vollständigem Token-Rename (#541)
    WHEN:  nach var(--g-good), var(--g-warn), var(--g-bad) gesucht wird
    THEN:  keine Treffer — alle auf --g-success/--g-warning/--g-danger umgestellt
    """
    bad_files = _find_old_token_files()
    assert not bad_files, (
        f"Noch {len(bad_files)} Datei(en) mit alten Token-Referenzen:\n"
        + "\n".join(f"  - {f.relative_to(REPO_ROOT)}" for f in bad_files)
    )


# ---------------------------------------------------------------------------
# AC-6: Bridge-Aliasse aus app.css entfernt
# ---------------------------------------------------------------------------

def test_ac6_bridge_aliases_removed():
    """
    GIVEN: app.css nach Entfernung der Brücken-Aliasse
    WHEN:  nach Alias-Definitionen von --g-success/warning/danger via var(--g-*) gesucht wird
    THEN:  keine Treffer — Token zeigen direkt auf Hex-Werte
    """
    content = APP_CSS.read_text()
    found = [
        alias for alias in ["--g-success", "--g-warning", "--g-danger"]
        if re.search(rf"{alias}\s*:\s*var\(--g-(?:good|warn|bad)\)", content)
    ]
    assert not found, (
        "app.css enthält noch Brücken-Aliasse (zeigen auf alte --g-good/warn/bad):\n"
        + "\n".join(f"  - {a}" for a in found)
    )


# ---------------------------------------------------------------------------
# AC-7: Alte Token-Definitionen existieren nicht mehr in app.css
# ---------------------------------------------------------------------------

def test_ac7_old_token_definitions_gone():
    """
    GIVEN: app.css nach Token-Rename
    WHEN:  nach --g-good:, --g-warn:, --g-bad: (als Definitionen) gesucht wird
    THEN:  keine Treffer — Token heißen jetzt --g-success/--g-warning/--g-danger
    """
    content = APP_CSS.read_text()
    still_present = [
        name for name in ["--g-good", "--g-warn", "--g-bad"]
        if re.search(rf"{name}\s*:", content)
    ]
    assert not still_present, (
        "app.css definiert noch alte Token:\n"
        + "\n".join(f"  - {name}" for name in still_present)
        + "\n  → umbenennen auf --g-success / --g-warning / --g-danger"
    )
