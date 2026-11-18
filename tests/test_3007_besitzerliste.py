# doc-compliance-test
"""TDD RED — Issue #3007 (Epic #2913): Besitzerliste nach den Listen der Reiter Etappen und Orte.

Spec: docs/specs/modules/feat_3007_etappen_orte_listen.md (AC-16, AC-20).
Daten: docs/context/einstellungen_neu/elementliste_besitzer.json (gelesen vom Abgleich,
frontend/e2e/elementliste_abgleich_logik.ts). Geprüft wird der Dateninhalt, nicht Quelltext.

Vertrag für den Developer:
  - kein Abschnitts-Eintrag ``liste`` mehr für trip/etappen und orte/orte (bisher 338/347);
  - kein Sammel-Eintrag ``zusaetzlich`` ``{text}`` mehr für trip/etappen und orte/orte (746/747);
  - Kopf-Einträge (abschnittskopf, #2913-e) dürfen nur paarweise bleiben (beide oder keiner);
  - Abschnitts-Eintrag ``tempo`` (trip/etappen) bleibt mit Verweis #2796;
  - die Knopf-Elemente „Tempo ändern“ (16 IDs in trip/etappen/liste) haben je einen Eintrag
    ``art: element`` mit Verweis #2796 und Grund.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BESITZER = ROOT / "docs" / "context" / "einstellungen_neu" / "elementliste_besitzer.json"
ELEMENTLISTE = ROOT / "docs" / "context" / "einstellungen_neu" / "elementliste.json"
REITER = {("trip", "etappen"), ("orte", "orte")}


@pytest.fixture(scope="module")
def besitzer() -> list[dict]:
    return json.loads(BESITZER.read_text(encoding="utf-8"))["besitzer"]


@pytest.fixture(scope="module")
def tempo_ids() -> set[str]:
    elemente = json.loads(ELEMENTLISTE.read_text(encoding="utf-8"))["elemente"]
    ids = {
        e["id"]
        for e in elemente
        if e["reiter"] == "etappen" and e["abschnitt"] == "liste" and e["text_de"] == "Tempo ändern"
    }
    assert len(ids) == 16, f"Messaufbau: {len(ids)} „Tempo ändern“-Elemente statt 16"
    return ids


def test_ac20_kein_listen_abschnitt_mehr(besitzer):
    rest = [
        b for b in besitzer
        if b["art"] == "abschnitt" and (b["ctx"], b["reiter"]) in REITER and b["abschnitt"] == "liste"
    ]
    assert rest == [], f"Listen-Abschnitte noch in der Besitzerliste: {rest}"


def test_ac20_kein_sammel_eintrag_text_mehr(besitzer):
    rest = [
        b for b in besitzer
        if b["art"] == "zusaetzlich" and (b.get("ctx"), b.get("reiter")) in REITER and b.get("muster") == "{text}"
    ]
    assert rest == [], f"Sammel-Einträge {{text}} noch vorhanden: {rest}"


def test_ac20_kopf_eintraege_nur_paarweise(besitzer):
    kopf = {
        (b["ctx"], b["reiter"]) for b in besitzer
        if b["art"] == "abschnitt" and (b["ctx"], b["reiter"]) in REITER and b["abschnitt"] == "abschnittskopf"
    }
    assert kopf in (set(), REITER), f"Kopf-Einträge nur für einen Reiter entfernt: {kopf}"
    rest_e = [b for b in besitzer if b["verweis"] == "#2913-e"]
    assert len(rest_e) == len(kopf), f"#2913-e: {len(rest_e)} Einträge, erwartet {len(kopf)} (nur Köpfe)"


def test_ac20_tempo_abschnitt_bleibt_bei_2796(besitzer):
    tempo = [
        b for b in besitzer
        if b["art"] == "abschnitt" and b["ctx"] == "trip" and b["reiter"] == "etappen" and b["abschnitt"] == "tempo"
    ]
    assert len(tempo) == 1 and tempo[0]["verweis"] == "#2796"


def test_ac16_tempo_aendern_elemente_haengen_an_2796(besitzer, tempo_ids):
    eintraege = {b["id"]: b for b in besitzer if b["art"] == "element" and b.get("id") in tempo_ids}
    fehlend = sorted(tempo_ids - eintraege.keys())
    assert fehlend == [], f"„Tempo ändern“ ohne Besitzer-Eintrag: {fehlend}"
    for i, b in eintraege.items():
        assert b["verweis"] == "#2796", f"{i}: Verweis {b['verweis']!r} statt #2796"
        assert b.get("grund", "").strip(), f"{i}: ohne Grund"
