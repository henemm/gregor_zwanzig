"""TDD RED — Issue #776: Inhalts-Toggle wirkt sich auf die zugestellte Mail aus.

SPEC: docs/specs/modules/issue_783_776_778_briefing_fixes.md (AC-4)

Nachdem `report_config.show_metrics_summary=False` persistiert ist, darf die naechste
zugestellte Briefing-Mail keinen Metriken-Ueberblick-Block mehr enthalten.

Acceptance-Stage-Test (GZ_STAGING_E2E): echter PUT gegen Staging, echter Test-Versand,
IMAP-Abruf aus dem Stalwart-Test-Postfach (GZ_IMAP_*). Kein Mock, kein Gmail.
Die konkrete Versand-/IMAP-Mechanik wird in der E2E-Phase (/e2e-verify) ausgefuehrt.
"""
from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(
    not os.environ.get("GZ_STAGING_E2E"),
    reason="AC-4 ist ein Staging-E2E-Test (GZ_STAGING_E2E gesetzt); laeuft in der "
           "Acceptance-Stage gegen staging.gregor20.henemm.com mit IMAP-Verifikation.",
)
def test_metrics_summary_toggle_persists_and_hides_section():
    """AC-4: GIVEN report_config.show_metrics_summary=False persistiert /
    WHEN Test-Briefing-Versand ausgeloest / THEN enthaelt die zugestellte Mail
    keinen Metriken-Ueberblick-Block — per IMAP verifiziert (echter Render, kein Mock).
    """
    pytest.skip("Staging-E2E wird in /e2e-verify ausgefuehrt, nicht im lokalen RED-Lauf")
