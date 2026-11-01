# doc-compliance-test
"""#2698: Die Login-Schritte der Browser-Gates klicken den Knopf "Anmelden".

Die Login-Seite hat mehr als einen Submit-Knopf (Sprachumschalter, #2648);
``button[type='submit']`` traf den falschen bzw. war mehrdeutig. Beide Hooks
muessen den Anmelde-Knopf ueber seine Rolle und seinen Namen ansprechen.
"""
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
DATEIEN = ["e2e_frontend_browser_gate.py", "design_fidelity_diff.py"]
NEU = 'get_by_role("button", name="Anmelden", exact=True).click()'


@pytest.mark.parametrize("name", DATEIEN)
def test_login_klickt_anmelden_knopf_statt_submit_selektor(name):
    quelltext = (HOOKS / name).read_text(encoding="utf-8")
    assert "/login" in quelltext
    assert "button[type='submit']" not in quelltext
    assert 'button[type="submit"]' not in quelltext
    assert NEU in quelltext
