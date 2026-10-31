"""Waechter ADR-0042 Klasse 1: Protokoll-Token des Metrik-Registers (#2662 AC-5).

``sms_code``, ``compact_label`` und ``col_label`` sind Protokoll-Token und werden
nie uebersetzt. Die Fixture ``tests/fixtures/metric_tokens_frozen.json`` wurde
einmalig aus dem Register-Stand vor #2662 erzeugt; dieser Test vergleicht den
Ist-Stand byte-genau dagegen.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.metric_catalog import _METRICS

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "metric_tokens_frozen.json"
FELDER = ("col_label", "compact_label", "sms_code")


def _ist_stand() -> dict[str, dict[str, str]]:
    return {m.id: {f: getattr(m, f) for f in FELDER} for m in _METRICS}


def _serialisiert(daten: dict) -> str:
    return json.dumps(daten, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def test_jede_kennung_in_register_und_fixture():
    eingefroren = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ist = _ist_stand()
    nur_register = sorted(set(ist) - set(eingefroren))
    nur_fixture = sorted(set(eingefroren) - set(ist))
    assert not nur_register, f"Register-Eintrag ohne eingefrorene Token: {nur_register}"
    assert not nur_fixture, f"Eingefrorene Token ohne Register-Eintrag: {nur_fixture}"


def test_token_feldweise_unveraendert():
    eingefroren = json.loads(FIXTURE.read_text(encoding="utf-8"))
    abweichungen = [
        f"{mid}.{feld}: eingefroren {eingefroren[mid][feld]!r}, Register {werte[feld]!r}"
        for mid, werte in _ist_stand().items() if mid in eingefroren
        for feld in FELDER if werte[feld] != eingefroren[mid].get(feld)
    ]
    assert not abweichungen, "Protokoll-Token geaendert (ADR-0042):\n" + "\n".join(abweichungen)


def test_token_byte_genau():
    assert _serialisiert(_ist_stand()) == FIXTURE.read_text(encoding="utf-8")
