"""
TDD tests for Issue #732 — email_spec_validator Scope-Klarstellung in CLAUDE.md.

Hintergrund: Die CLAUDE.md-Sektion „E-MAIL SPEC VALIDATOR (ZWINGEND!)" stellt
`email_spec_validator.py` als universell-zwingend für ALLE E-Mail-Features dar.
Tatsächlich prüft der Validator fest die Orts-Vergleich-Mail (Vergleichstabelle,
Winner-Box, --min-locations) und kann von einer Trip-Briefing-Mail strukturell
nie bestanden werden → Dauer-Exit-1 → Gate-Erosion.

Diese Tests prüfen die Workflow-Datei CLAUDE.md selbst als Artefakt.

# doc-compliance-test

IMPORTANT: NO mocks, NO patch, NO MagicMock. Real file/text operations only.
"""
from __future__ import annotations

import re
from pathlib import Path



def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validator_section() -> str:
    """Extrahiert die Sektion ``## Mail-Validatoren & Renderer-Gate`` aus CLAUDE.md.

    Liefert den Text von der Überschrift bis zur nächsten ``## ``-Überschrift.
    """
    claude_md = _repo_root() / "CLAUDE.md"
    text = claude_md.read_text(encoding="utf-8")
    # Sektion ab Überschrift bis zur nächsten H2-Überschrift (oder Dateiende).
    match = re.search(
        r"^##\s+Mail-Validatoren\s+&\s+Renderer-Gate.*?(?=^##\s+|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match, "Sektion '## Mail-Validatoren & Renderer-Gate' nicht in CLAUDE.md gefunden"
    return match.group(0)


class TestIssue732ValidatorScopeDocs:
    """#732: CLAUDE.md grenzt Validator-Scope auf Orts-Vergleich-Mail ein."""

    def test_section_names_orts_vergleich_scope(self):
        """AC-1: Die Sektion benennt explizit den Orts-Vergleich-Mail-Pfad."""
        section = _validator_section().lower()
        assert "orts-vergleich" in section, (
            "AC-1: Sektion muss den Orts-Vergleich-Mail-Pfad explizit benennen"
        )
        markers = ["winner-box", "vergleichstabelle", "min-locations"]
        assert any(m in section for m in markers), (
            "AC-1: Sektion muss den fest verdrahteten Orts-Vergleich-Struktur-Marker "
            f"nennen (eines von {markers})"
        )

    def test_section_points_trip_briefing_to_own_validator(self):
        """AC-2: Für Trip-Briefing-Mail verweist die Sektion auf den eigenen Validator."""
        section = _validator_section().lower()
        assert "trip-briefing" in section, (
            "AC-2: Sektion muss den Trip-Briefing-Mail-Pfad benennen"
        )
        # Der neue Abschnitt nutzt für Trip-Briefing-Mails den eigenen
        # briefing_mail_validator.py (kein IMAP-MIME-Test mehr).
        briefing_markers = ["briefing_mail_validator", "briefing-mail-validator"]
        assert any(m in section for m in briefing_markers), (
            "AC-2: Sektion muss für Trip-Briefing-Mail den eigenen Validator "
            f"`briefing_mail_validator.py` als Nachweis nennen (eines von {briefing_markers})"
        )

    def test_exit0_rule_is_scoped_not_universal(self):
        """AC-3: Die Exit-0-Pflicht ist auf Orts-Vergleich eingegrenzt, nicht universal."""
        section = _validator_section()
        lower = section.lower()
        # Die alte universell-undifferenzierte PFLICHT-Formulierung darf nicht mehr
        # kontextfrei für ALLE E-Mail-Features gelten.
        bad_universal = 'pflicht vor "e2e test bestanden" bei e-mail-features'
        assert bad_universal not in lower, (
            "AC-3: Die universelle PFLICHT-Formulierung 'bei E-Mail-Features' muss "
            "auf den Orts-Vergleich-Mail-Pfad eingegrenzt werden"
        )
        # Falls eine Exit-0-Pflicht weiterhin genannt wird, muss sie im selben
        # Scope-Kontext (Orts-Vergleich) stehen.
        if "exit 0" in lower:
            assert "orts-vergleich" in lower, (
                "AC-3: Eine Exit-0-Pflicht darf nur im Orts-Vergleich-Scope stehen"
            )
