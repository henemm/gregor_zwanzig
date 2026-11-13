"""Mail-Validator-Vertrauen: der From-Kopf muss genau EINE Dienst-Adresse tragen (#2961).

Prueft ``.claude/hooks/_mail_trust.pruefen`` mit echten Kopfzeilen: zwei
Adressen in einem From-Kopf bzw. ein Anzeigename, der wie eine Dienst-Adresse
aussieht, werden verworfen.
"""
from __future__ import annotations

import email
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))

import _mail_trust  # noqa: E402

DIENST = "gregor-test@henemm.com"
VERTRAUEN = _mail_trust.Vertrauen(frozenset({DIENST}), "mail.henemm.com")


def _kopf(von: str):
    return email.message_from_string(f"From: {von}\nTo: x@henemm.com\nSubject: s\n\nx\n")


@pytest.mark.parametrize("von", [
    f"{DIENST}, angreifer@example.org",
    f"Gregor <{DIENST}>, Angreifer <angreifer@example.org>",
    f'"{DIENST}" <angreifer@example.org>',
    f"{DIENST} <angreifer@example.org>",
])
def test_from_mit_zweiter_oder_vorgetaeuschter_adresse_wird_verworfen(von):
    grund, _ = _mail_trust.pruefen(_kopf(von), VERTRAUEN)
    assert grund is not None and grund.startswith("ABSENDER"), (von, grund)
