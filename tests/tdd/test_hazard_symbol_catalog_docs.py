# doc-compliance-test
"""Alt-Specs zum Kuerzel-Katalog sind mitgezogen (#1318, AC-15).

SPEC: docs/specs/modules/sms_official_alert_tokens.md — AC-15

Ausdruecklich ein DOKU-KONFORMITAETSTEST (`# doc-compliance-test`, siehe
CLAUDE.md „Test-Politik"), kein Verhaltensnachweis: geprueft wird, dass die
beiden Alt-Specs die Kuerzel-Vereinheitlichung nachvollziehen. Das Verhalten
selbst deckt `test_sms_official_alert_tokens.py` (AC-13/AC-14) ab.
"""
from __future__ import annotations

from pathlib import Path

_SPECS = Path(__file__).resolve().parents[2] / "docs" / "specs" / "modules"
_ISSUE_1216 = _SPECS / "issue_1216_official_alert_template.md"
_FIX_1249 = _SPECS / "fix_1249_sms_telegram_scope.md"

_NEW_SYMBOLS = ["HT", "TH", "CD", "W", "HR", "SN", "IC", "CL", "FR"]


def test_ac15_issue_1216_spec_carries_new_symbols_and_ssot_reference():
    text = _ISSUE_1216.read_text(encoding="utf-8")
    for symbol in _NEW_SYMBOLS:
        assert f"`{symbol}`" in text, (
            f"Neues Kuerzel {symbol!r} fehlt in {_ISSUE_1216.name}"
        )
    assert "hazard_symbols.py" in text, (
        f"{_ISSUE_1216.name} nennt `hazard_symbols.py` nicht als Kuerzel-SSOT"
    )


def test_ac15_fix_1249_spec_marks_ac5_as_superseded():
    text = _FIX_1249.read_text(encoding="utf-8")
    assert "AC-5" in text, f"{_FIX_1249.name} nennt AC-5 nicht mehr"
    assert "überholt" in text, (
        f"{_FIX_1249.name} markiert AC-5 nicht sichtbar als ueberholt"
    )
    assert "sms_official_alert_tokens.md" in text, (
        f"{_FIX_1249.name} verweist nicht auf die Nachfolge-Spec"
    )
