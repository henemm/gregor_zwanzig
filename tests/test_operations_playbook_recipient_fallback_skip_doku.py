# doc-compliance-test
"""TDD RED — Issue #2144, AC-9: Fehl-Fall-Doku im Operations-Playbook.

Spec: docs/specs/bugfix/user_recipient_fallback.md, AC-9.

Reiner Vorhandensein-Nachweis (Ausnahme laut CLAUDE.md-Testpolitik
ausdruecklich fuer `# doc-compliance-test` zulaessig): der Empfaenger-Absatz
beschreibt heute NUR den Override-Fall (`user.json.mail_to` ueberschreibt
`GZ_MAIL_TO`) -- nach dem Fix muss er zusaetzlich den Fehl-Fall korrekt als
"Skip mit Log/reason_code" beschreiben, statt (weiterhin unausgesprochen)
einen globalen Fallback auf `GZ_MAIL_TO`/`GZ_TELEGRAM_CHAT_ID`/`GZ_SMS_TO`
nahezulegen.

Heute ROT: der Absatz nennt weder "reason_code" noch eine Skip-Formulierung
fuer den Fehl-Fall.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK = REPO_ROOT / "docs" / "reference" / "operations_playbook.md"


def test_playbook_describes_skip_with_reason_code_for_missing_recipient():
    text = PLAYBOOK.read_text(encoding="utf-8")

    idx = text.find("überschreibt** das")
    assert idx != -1, (
        "Testaufbau defekt: der bekannte Override-Satz "
        "('...überschreibt** das globale GZ_MAIL_TO...') wurde nicht "
        "gefunden -- Zeilennummern haben sich verschoben, Ankertext pruefen."
    )
    passage = text[max(0, idx - 400):idx + 1200]

    assert "reason_code" in passage, (
        "AC-9 verletzt: der Absatz nennt keinen reason_code fuer den "
        "Fehl-Fall (fehlendes mail_to/telegram_chat_id/sms_to)."
    )
    skip_marker_present = any(
        marker in passage for marker in ("Skip", "übersprungen", "uebersprungen")
    )
    assert skip_marker_present, (
        "AC-9 verletzt: der Absatz beschreibt den Fehl-Fall nicht als "
        "Skip-mit-Log/reason_code -- ohne diese Formulierung suggeriert die "
        "Doku weiterhin (implizit) einen globalen .env-Fallback."
    )
