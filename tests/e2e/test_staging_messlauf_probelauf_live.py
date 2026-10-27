"""Live-Schicht (nur ``/e2e-verify``): Messtreiber-Probelauf gegen das ECHTE Staging.

Issue #2439, Spec: docs/specs/modules/feat_2439_staging_messtreiber.md (AC-20).

Die Fake-Transport-Tests (``tests/tdd/test_staging_messlauf.py``) beweisen den Ablauf,
nicht die Wirklichkeit: die drei Defekte aus dem ersten Live-Lauf (http-Basis, warmes
MORGEN, ``fr_direct``-Pflicht) waren dort unsichtbar. Dieser Test faehrt den Treiber im
Modus ``--nur-probelauf`` echt gegen Staging (Wegwerf-Nutzer, echte Mails, Journal).

Marker ``live`` + ``staging``; Opt-in ``GZ_STAGING_E2E=1``. Der Treiber sperrt selbst das
Zeitfenster 23:45-00:15 (Exit 2 = Umgebung, kein Befund).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

TREIBER = Path(__file__).resolve().parents[2] / ".claude" / "tools" / "staging_messlauf.py"

pytestmark = [
    pytest.mark.live,
    pytest.mark.staging,
    pytest.mark.skipif(
        os.environ.get("GZ_STAGING_E2E") != "1",
        reason="Staging-Live-Test: nur /e2e-verify (GZ_STAGING_E2E=1)",
    ),
]


def test_nur_probelauf_gegen_echtes_staging_endet_mit_exit_0_und_raeumt_auf():
    erg = subprocess.run([sys.executable, str(TREIBER), "--nur-probelauf"],
                         capture_output=True, text=True, timeout=1800)
    if erg.returncode == 2:
        pytest.skip(f"Umgebung/Zeitfenster, kein Befund: {erg.stderr[-400:]}")
    assert erg.returncode == 0, f"Probelauf Exit {erg.returncode}; stderr: {erg.stderr[-1500:]}"
    assert "eu_direct" in erg.stderr, "Korsika-Ersatzquelle nicht offen ausgewiesen"
    assert "Rest" not in erg.stderr or "kein Rest" in erg.stderr, f"Aufraeumen unsauber: {erg.stderr[-600:]}"
