# doc-compliance-test
"""Issue #1405 Scheibe 1, AC-14 (Doku-Teil): das Restrisiko der
Alarm-Wiederholung ohne Versuchsdeckel ist in Spec und ADR-0086 benannt.

ADR-0086 verzichtet bewusst auf einen Versuchsdeckel (#1662). Der Preis —
bei Dauerausfall bis zu 48 Versuche je Ereignis und Tag, bei mehrdeutigen
Fehlschlaegen bis zu 48 moegliche Dubletten, Takt 30 Minuten — muss dort
stehen, wo die Entscheidung getroffen wird. Faellt eine der Zahlen bei
einer spaeteren Ueberarbeitung still heraus, ist die Abwaegung nicht mehr
nachvollziehbar.

Das Verhalten selbst (Wiederholung endet, wenn das Ereignis entfaellt)
pruefen die Verhaltenstests in ``test_alarm_totalausfall_wird_wiederholt.py``.
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SPEC = _REPO / "docs" / "specs" / "modules" / "fix_1405_s1_alarm_zustellung.md"
_ADR = _REPO / "docs" / "adr" / "0086-alarm-erfolg-heisst-zustellung.md"


def _known_limitations(text: str) -> str:
    match = re.search(r"^## Known Limitations\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match, "Spec hat keinen Abschnitt '## Known Limitations'."
    return match.group(1)


def _consequences(text: str) -> str:
    match = re.search(r"^## Konsequenzen\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match, "ADR-0086 hat keinen Abschnitt '## Konsequenzen'."
    return match.group(1)


def _assert_restrisiko_benannt(section: str, quelle: str) -> None:
    flat = " ".join(section.split())
    assert re.search(r"48 Versuche", flat), (
        f"{quelle}: das Restrisiko 'bis zu 48 Versuche je Ereignis und Tag' "
        "(Dauerausfall, kein Versuchsdeckel) ist nicht benannt."
    )
    assert re.search(r"48 (mögliche )?Dubletten", flat), (
        f"{quelle}: das Restrisiko 'bis zu 48 Dubletten' (mehrdeutige "
        "Fehlschläge, Timeout nach Annahme) ist nicht benannt."
    )
    assert re.search(r"30 Min", flat), (
        f"{quelle}: der Wiederholungstakt (30 Minuten) ist nicht benannt."
    )


def test_spec_known_limitations_nennen_restrisiko_der_wiederholung():
    """AC-14: Spec-Abschnitt 'Known Limitations' nennt 48 Versuche,
    48 Dubletten und den 30-Minuten-Takt."""
    _assert_restrisiko_benannt(
        _known_limitations(_SPEC.read_text(encoding="utf-8")), "Spec Known Limitations"
    )


def test_adr_0086_nennt_restrisiko_der_wiederholung():
    """AC-14: ADR-0086 nennt in den Konsequenzen 48 Versuche, 48 Dubletten
    und den 30-Minuten-Takt (Entscheidungsteil)."""
    adr_text = _ADR.read_text(encoding="utf-8")
    _assert_restrisiko_benannt(_consequences(adr_text), "ADR-0086 Konsequenzen")
    assert "30 Minuten" in " ".join(adr_text.split()), (
        "ADR-0086: die Backoff-Frist '30 Minuten' fehlt im Entscheidungstext."
    )
