"""Lese-Helfer fuer die Orte-SMS (Issue #3172, ADR-0125, PO 2026-11-19).

Die Orte-SMS hat keinen Kopf, kein Datum und keine Ortsnamen: je Ort
``O{n} {Token}`` (n = Stelle in der Reihenfolge des Abos), Orte durch ein
Leerzeichen getrennt, am Ende optional `` +k Orte`` und `` X?``, z. B.
``O1 D15/19 W30@10(43@16) O2 D16/20 W- O3 n/a +2 Orte X?``.

Reine Textzerlegung fuer Tests -- keine Renderer-Logik.
"""
from __future__ import annotations

import re

_ENDE = re.compile(r"( \+\d+ Orte)?( X\?)?$")
_TRENNER = re.compile(r" (?=O\d+(?: |$))")


def orte_teile(sms: str) -> list[str]:
    """Ortsteile ``O{n} ...`` in SMS-Folge (ohne ``+k Orte``/``X?``)."""
    rumpf = _ENDE.sub("", sms)
    return [t for t in _TRENNER.split(rumpf) if t] if rumpf else []


def orte_nummern(sms: str) -> list[int]:
    return [int(t.split(" ", 1)[0][1:]) for t in orte_teile(sms)]


def orte_teil(sms: str, nummer: int) -> str:
    """Ortsteil des Orts an Stelle ``nummer`` (1-basiert)."""
    treffer = [t for t in orte_teile(sms) if t == f"O{nummer}" or t.startswith(f"O{nummer} ")]
    assert treffer, f"Ort O{nummer} fehlt in der SMS: {sms!r}"
    return treffer[0]


def orte_token(teil: str) -> list[str]:
    """Token eines Ortsteils ohne ``O{n}``, bis zum Warnblock ``!``."""
    out = []
    for tok in teil.split(" ")[1:]:
        if tok.startswith("!"):
            break
        out.append(tok)
    return out


def orte_kuerzel(teil: str) -> list[str]:
    """Buchstaben-Kuerzel der Token (``TH:-`` -> ``TH``, ``NS24+0`` -> ``NS``)."""
    return [m.group(0) for m in (re.match(r"[A-Z]+", t) for t in orte_token(teil)) if m]


def assert_premium_folgt_sms(sms: str, premium: str, grenze: int = 153) -> None:
    """#3172 (Regel #3100 wie im Trip): die Premium-SMS ist der SMS-Text,
    solange er in ``grenze`` passt, sonst derselbe Text erneut vom Listenende
    gekuerzt (jeder gezeigte Ortsteil ist ein Anfang des SMS-Ortsteils mit
    derselben Nummer; ``X?`` bleibt)."""
    if len(sms) <= grenze:
        assert premium == sms, (premium, sms)
        return
    assert len(premium) <= grenze, (len(premium), premium)
    assert premium.endswith(" X?") == sms.endswith(" X?"), (premium, sms)
    voll = {t.split(" ", 1)[0]: orte_token(t) for t in orte_teile(sms)}
    for teil in orte_teile(premium):
        nummer, token = teil.split(" ", 1)[0], orte_token(teil)
        assert nummer in voll and voll[nummer][:len(token)] == token, (teil, sms)
