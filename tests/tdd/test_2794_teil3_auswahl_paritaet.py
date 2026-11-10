"""Drift-Waechter AC-37 (Python-Seite): gemeinsame Auswahl-Fixture.

SPEC: docs/specs/modules/feat_2794_s3a_teil3_wetter.md (AC-37, Implementation
Details §2). Die Fixture ``tests/fixtures/ampel_auswahl_paritaet.json`` haelt
fuer alle 7 Systemvorlagen die Vorlagen-Ampel und die erwartete Menge aktiver
Metriken, dazu Faelle „Vorlage + Abweichungen". Das Frontend
(``ampelModell.ts``, ``node --test``) leitet seine Auswahl aus DERSELBEN Datei
ab; dieser Test stellt sicher, dass die Datei mit der Python-Referenz
``app.ampel.resolve_ampel`` uebereinstimmt. Laeuft eine Seite auseinander,
wird einer der beiden Tests rot.

Kein Mock, kein Netz: reine Funktion gegen eingecheckte Daten.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ampel import resolve_ampel
from app.ampel_templates import AMPEL_TEMPLATES

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ampel_auswahl_paritaet.json"
DATEN = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _aktiv_laut_python(abo_ampel) -> list[str]:
    """Aktive Metriken des Abos nach ``resolve_ampel`` (Reihenfolge der
    aufgeloesten Ampel). Abo als Dict mit ``display_config`` — dieselbe Form
    wie ein Orts-Vergleich; der Trip-Pfad landet in derselben Aufloesung."""
    aufgeloest = resolve_ampel({"display_config": {"ampel": abo_ampel}})
    return [mid for mid, e in aufgeloest["metrics"].items() if e.get("enabled")]


def test_format_ist_dokumentiert():
    assert isinstance(DATEN.get("_format"), str) and "aktiv" in DATEN["_format"]


def test_fixture_deckt_genau_die_sieben_systemvorlagen_ab():
    assert len(AMPEL_TEMPLATES) == 7, sorted(AMPEL_TEMPLATES)
    assert set(DATEN["vorlagen"]) == set(AMPEL_TEMPLATES), (
        "Fixture und AMPEL_TEMPLATES nennen unterschiedliche Vorlagen: "
        f"{sorted(DATEN['vorlagen'])} vs. {sorted(AMPEL_TEMPLATES)}"
    )


@pytest.mark.parametrize("tid", sorted(AMPEL_TEMPLATES))
def test_vorlagen_ampel_der_fixture_gleich_python(tid):
    """Die Vorlagen-Ampel, aus der das Frontend ableitet, ist wortgleich mit
    der Python-Vorlage (Grenzen, enabled, alarm_ab, Gewitter)."""
    assert DATEN["vorlagen"][tid]["ampel"] == AMPEL_TEMPLATES[tid], (
        f"Vorlage {tid!r} in der Fixture veraltet — Fixture neu erzeugen."
    )


@pytest.mark.parametrize("tid", sorted(AMPEL_TEMPLATES))
def test_aktive_menge_je_vorlage_gleich_resolve_ampel(tid):
    erwartet = DATEN["vorlagen"][tid]["aktiv"]
    assert len(erwartet) == len(set(erwartet)), f"{tid}: doppelte IDs {erwartet}"
    assert set(erwartet) == set(_aktiv_laut_python({"template": tid})), tid
    # Unabhaengig von der Aufloesung: genau die Vorlagen-Zeilen mit enabled=true.
    assert set(erwartet) == {
        mid for mid, e in AMPEL_TEMPLATES[tid]["metrics"].items() if e["enabled"]
    }, tid


def test_faelle_decken_entfernen_und_hinzufuegen_ab():
    namen = {f["name"] for f in DATEN["faelle"]}
    assert {"metrik_entfernt", "metrik_hinzugefuegt_vorlagenzeile_aus",
            "metrik_hinzugefuegt_ohne_vorlagenzeile", "entfernt_und_hinzugefuegt"} <= namen
    assert len(namen) == len(DATEN["faelle"]), "Fallnamen muessen eindeutig sein"


@pytest.mark.parametrize("fall", DATEN["faelle"], ids=lambda f: f["name"])
def test_fall_aktive_menge_gleich_resolve_ampel(fall):
    erwartet = fall["aktiv"]
    assert len(erwartet) == len(set(erwartet)), f"{fall['name']}: doppelte IDs"
    assert set(erwartet) == set(_aktiv_laut_python(fall["ampel"])), (
        f"{fall['name']}: Fixture-Erwartung {sorted(erwartet)} weicht von "
        f"resolve_ampel ab: {sorted(_aktiv_laut_python(fall['ampel']))}"
    )


@pytest.mark.parametrize("fall", DATEN["faelle"], ids=lambda f: f["name"])
def test_fall_reihenfolge_vorlagenzeilen_vorn_hinzugefuegte_hinten(fall):
    """Reihenfolge-Konvention der Fixture (fuer den Frontend-Spiegel): erst die
    Vorlagen-Zeilen in Vorlagen-Reihenfolge, Metriken ohne Vorlagen-Zeile hinten."""
    assert fall["aktiv"] == _aktiv_laut_python(fall["ampel"]), fall["name"]
