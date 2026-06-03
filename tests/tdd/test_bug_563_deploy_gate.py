"""
TDD RED — Bug #563: Deploy-Gate doppelt

Testet ob die Korrekturen an Workflow-Dateien vorgenommen wurden.
Alle Tests schlagen im RED-Zustand fehl, weil die Fixes noch nicht existieren.
"""

from pathlib import Path

VALIDATE_CMD = Path(".claude/commands/6-validate.md")
DEPLOY_CMD = Path(".claude/commands/7-deploy.md")
CLAUDE_MD = Path("CLAUDE.md")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestAC1_NoRedirectToSevenDeploy:
    """AC-1: 6-validate.md Step 5 leitet nicht mehr an /7-deploy weiter."""

    def test_step5_does_not_contain_naechster_schritt_7_deploy(self):
        """
        GIVEN: 6-validate.md enthält Step 5
        WHEN:  Inhalt wird geprüft
        THEN:  Kein 'Nächster Schritt: `/7-deploy`' vorhanden
        """
        content = _read(VALIDATE_CMD)
        assert "/7-deploy" not in content or "als eigenständiger Befehl" in content, (
            "6-validate.md enthält noch den Hinweis auf /7-deploy als nächsten Schritt — "
            "Step 5 muss stattdessen den Deploy-Prozess inline ausführen"
        )

    def test_step5_does_not_tell_user_to_wait_for_7deploy(self):
        """
        GIVEN: 6-validate.md Step 5
        WHEN:  Übergabe-Text geprüft wird
        THEN:  Kein 'Nächster Schritt: `/7-deploy`' Satz vorhanden
        """
        content = _read(VALIDATE_CMD)
        assert "Nächster Schritt:`/7-deploy`" not in content
        assert "Nächster Schritt: `/7-deploy`" not in content


class TestAC2_InlineDeployFlow:
    """AC-2: 6-validate.md Step 5 enthält den vollständigen Deploy-Ablauf inline."""

    def test_step5_contains_staging_trigger(self):
        """
        GIVEN: 6-validate.md nach dem Fix
        WHEN:  Step 5 gelesen wird
        THEN:  Enthält Staging-Trigger (auto-deploy-gregor-staging.sh)
        """
        content = _read(VALIDATE_CMD)
        assert "auto-deploy-gregor-staging.sh" in content, (
            "6-validate.md Step 5 enthält keinen Staging-Trigger — "
            "Deploy-Prozess muss inline in Step 5 ausgeführt werden"
        )

    def test_step5_contains_e2e_step(self):
        """
        GIVEN: 6-validate.md nach dem Fix
        WHEN:  Step 5 gelesen wird
        THEN:  Enthält E2E-Schritt (/e2e-verify)
        """
        content = _read(VALIDATE_CMD)
        assert "e2e-verify" in content, (
            "6-validate.md Step 5 enthält keinen E2E-Schritt — "
            "E2E muss Bestandteil des inline Deploy-Ablaufs sein"
        )

    def test_step5_contains_prod_deploy(self):
        """
        GIVEN: 6-validate.md nach dem Fix
        WHEN:  Step 5 gelesen wird
        THEN:  Enthält Prod-Deploy-Script
        """
        content = _read(VALIDATE_CMD)
        assert "deploy-gregor-prod.sh" in content, (
            "6-validate.md Step 5 enthält keinen Prod-Deploy-Aufruf — "
            "Prod-Deploy muss inline in Step 5 ausgeführt werden"
        )

    def test_step5_waits_for_go_before_prod(self):
        """
        GIVEN: 6-validate.md nach dem Fix
        WHEN:  Step 5 gelesen wird
        THEN:  Enthält 'go' als Pause vor Prod-Deploy
        """
        content = _read(VALIDATE_CMD)
        assert "'go'" in content or "**'go'**" in content, (
            "6-validate.md Step 5 enthält keine 'go'-Gate vor Prod-Deploy"
        )


class TestAC3_ClaudeMdPhase3Keyword:
    """AC-3: CLAUDE.md Phase-3-Zeile zeigt 'go' statt 'approved'."""

    def test_phase3_row_uses_go_not_approved(self):
        """
        GIVEN: CLAUDE.md Workflow-Tabelle
        WHEN:  Phase-3-Zeile gelesen wird
        THEN:  Enthält ('go') statt ('approved')
        """
        content = _read(CLAUDE_MD)
        # Suche die Phase-3-Zeile
        lines = content.splitlines()
        phase3_lines = [l for l in lines if "/3-write-spec" in l]
        assert phase3_lines, "Phase-3-Zeile nicht in CLAUDE.md gefunden"
        phase3_line = phase3_lines[0]
        assert "'go'" in phase3_line, (
            f"CLAUDE.md Phase-3-Zeile enthält nicht '('go')': {phase3_line!r}"
        )
        assert "'approved'" not in phase3_line, (
            f"CLAUDE.md Phase-3-Zeile enthält noch '('approved')': {phase3_line!r}"
        )


class TestAC4_ClaudeMdPhase8Keyword:
    """AC-4: CLAUDE.md Phase-8-Zeile zeigt 'go', kein '/7-deploy', kein 'ja'."""

    def test_phase8_row_uses_go_not_ja(self):
        """
        GIVEN: CLAUDE.md Workflow-Tabelle
        WHEN:  Phase-8-Zeile gelesen wird
        THEN:  PO-Eingriff enthält 'go' statt 'ja'
        """
        content = _read(CLAUDE_MD)
        lines = content.splitlines()
        phase8_lines = [l for l in lines if "| 8 |" in l]
        assert phase8_lines, "Phase-8-Zeile nicht in CLAUDE.md gefunden"
        phase8_line = phase8_lines[0]
        assert "'go'" in phase8_line or "go'" in phase8_line, (
            f"CLAUDE.md Phase-8-Zeile enthält nicht 'go': {phase8_line!r}"
        )
        assert "'ja'" not in phase8_line, (
            f"CLAUDE.md Phase-8-Zeile enthält noch 'ja' sagen: {phase8_line!r}"
        )

    def test_phase8_row_no_7deploy_command(self):
        """
        GIVEN: CLAUDE.md Workflow-Tabelle
        WHEN:  Phase-8-Zeile gelesen wird
        THEN:  Command-Spalte zeigt '—' statt '/7-deploy'
        """
        content = _read(CLAUDE_MD)
        lines = content.splitlines()
        phase8_lines = [l for l in lines if "| 8 |" in l]
        assert phase8_lines, "Phase-8-Zeile nicht in CLAUDE.md gefunden"
        phase8_line = phase8_lines[0]
        assert "`/7-deploy`" not in phase8_line, (
            f"CLAUDE.md Phase-8-Zeile zeigt noch '/7-deploy' als Command: {phase8_line!r}"
        )


class TestAC5_SevenDeployIntact:
    """AC-5: /7-deploy bleibt als eigenständiger Befehl erhalten."""

    def test_7deploy_still_exists(self):
        """
        GIVEN: .claude/commands/7-deploy.md
        WHEN:  Datei gelesen wird
        THEN:  Datei existiert und enthält den vollständigen Deploy-Ablauf
        """
        assert DEPLOY_CMD.exists(), "7-deploy.md wurde gelöscht — muss erhalten bleiben"
        content = _read(DEPLOY_CMD)
        assert "deploy-gregor-prod.sh" in content
        assert "auto-deploy-gregor-staging.sh" in content
        assert "e2e-verify" in content
