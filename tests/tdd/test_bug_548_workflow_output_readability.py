"""
TDD RED: Bug #548 — Workflow-Ausgabe Lesbarkeit

Tests prüfen, dass die PO-Zusammenfassungen in den Command-Files
kein `>` Blockquote-Format verwenden, das in Claude Code's UI
zu weißem Text auf schwarzem Hintergrund mit weißen Leerzeichen führt.

Zusätzlich: openspec.yaml muss "go" als approval_phrase enthalten.
"""

import re
from pathlib import Path

COMMANDS_DIR = Path(__file__).parent.parent.parent / ".claude" / "commands"
OPENSPEC_PATH = Path(__file__).parent.parent.parent / "openspec.yaml"


def _po_summary_lines(filepath: Path) -> list[str]:
    """Extrahiert die Zeilen der PO-Zusammenfassung aus einer Command-Datei."""
    content = filepath.read_text(encoding="utf-8")
    lines = content.splitlines()
    in_section = False
    result = []
    for line in lines:
        if "PO-Zusammenfassung" in line or "Tech-Lead-Brief" in line or "Akzeptanzkriterien für PO" in line:
            in_section = True
        if in_section:
            result.append(line)
            # Abschnitt endet beim nächsten ## Heading (außer dem Start)
            if line.startswith("## ") and result and line not in result[:1]:
                break
    return result


class TestNoBlockquoteInPOSummaries:
    """AC-1 bis AC-5: Keine `>` Blockquote-Zeilen in PO-Zusammenfassungen."""

    def test_analyse_no_blockquote_in_po_summary(self):
        """AC-2: 2-analyse.md PO-Zusammenfassung ohne > Prefix."""
        filepath = COMMANDS_DIR / "2-analyse.md"
        assert filepath.exists(), f"Command-Datei fehlt: {filepath}"
        content = filepath.read_text(encoding="utf-8")

        # Finde den PO-Zusammenfassung-Block
        start = content.find("PO-Zusammenfassung")
        assert start != -1, "PO-Zusammenfassung Abschnitt nicht gefunden"

        # Suche nach Blockquote-Zeilen mit den spezifischen PO-Sätzen
        po_section = content[start:start + 600]
        blockquote_po_lines = [
            line for line in po_section.splitlines()
            if line.strip().startswith(">")
            and any(kw in line for kw in ["Das Problem", "Warum das wichtig", "Was ich vorhabe", "Sage", "go"])
        ]
        assert blockquote_po_lines == [], (
            f"PO-Zusammenfassung in 2-analyse.md enthält noch Blockquote-Zeilen:\n"
            + "\n".join(blockquote_po_lines)
        )

    def test_write_spec_no_blockquote_in_po_output(self):
        """AC-3: 3-write-spec.md Akzeptanzkriterien-Ausgabe ohne > Prefix."""
        filepath = COMMANDS_DIR / "3-write-spec.md"
        assert filepath.exists(), f"Command-Datei fehlt: {filepath}"
        content = filepath.read_text(encoding="utf-8")

        start = content.find("Akzeptanzkriterien für PO")
        assert start != -1, "Akzeptanzkriterien Abschnitt nicht gefunden"

        po_section = content[start:start + 600]
        blockquote_po_lines = [
            line for line in po_section.splitlines()
            if line.strip().startswith(">")
            and any(kw in line for kw in ["Was die Software", "AC-", "Sage", "go", "Spec gespeichert"])
        ]
        assert blockquote_po_lines == [], (
            f"Akzeptanzkriterien-Ausgabe in 3-write-spec.md enthält noch Blockquote-Zeilen:\n"
            + "\n".join(blockquote_po_lines)
        )

    def test_tdd_red_no_blockquote_in_po_summary(self):
        """AC-4: 4-tdd-red.md PO-Zusammenfassung ohne > Prefix."""
        filepath = COMMANDS_DIR / "4-tdd-red.md"
        assert filepath.exists(), f"Command-Datei fehlt: {filepath}"
        content = filepath.read_text(encoding="utf-8")

        start = content.find("PO-Zusammenfassung")
        assert start != -1, "PO-Zusammenfassung Abschnitt nicht gefunden"

        po_section = content[start:start + 800]
        blockquote_po_lines = [
            line for line in po_section.splitlines()
            if line.strip().startswith(">")
            and any(kw in line for kw in ["Tests geschrieben", "AC-", "Fehlgeschlagen", "Das ist korrekt", "Ich starte"])
        ]
        assert blockquote_po_lines == [], (
            f"PO-Zusammenfassung in 4-tdd-red.md enthält noch Blockquote-Zeilen:\n"
            + "\n".join(blockquote_po_lines)
        )

    def test_deploy_no_blockquote_in_tech_lead_brief(self):
        """AC-5: 7-deploy.md Tech-Lead-Brief ohne > Prefix."""
        filepath = COMMANDS_DIR / "7-deploy.md"
        assert filepath.exists(), f"Command-Datei fehlt: {filepath}"
        content = filepath.read_text(encoding="utf-8")

        start = content.find("Tech-Lead-Brief")
        assert start != -1, "Tech-Lead-Brief Abschnitt nicht gefunden"

        brief_section = content[start:start + 800]
        blockquote_brief_lines = [
            line for line in brief_section.splitlines()
            if line.strip().startswith(">")
            and any(kw in line for kw in ["Was wurde gebaut", "Staging validiert", "Tests:", "Offene Punkte", "Risiko", "Empfehlung", "Sage", "go"])
        ]
        assert blockquote_brief_lines == [], (
            f"Tech-Lead-Brief in 7-deploy.md enthält noch Blockquote-Zeilen:\n"
            + "\n".join(blockquote_brief_lines)
        )


class TestGoKeywordInOpenspec:
    """Nebenbefund: 'go' muss in openspec.yaml approval_phrases stehen."""

    def test_go_in_approval_phrases_openspec(self):
        """openspec.yaml muss 'go' als approval_phrase enthalten."""
        assert OPENSPEC_PATH.exists(), f"openspec.yaml nicht gefunden: {OPENSPEC_PATH}"
        content = OPENSPEC_PATH.read_text(encoding="utf-8")

        # Finde approval_phrases Block
        start = content.find("approval_phrases")
        assert start != -1, "approval_phrases nicht in openspec.yaml gefunden"

        phrases_section = content[start:start + 300]
        assert '- "go"' in phrases_section or "- go" in phrases_section, (
            f"'go' fehlt in approval_phrases:\n{phrases_section}"
        )
