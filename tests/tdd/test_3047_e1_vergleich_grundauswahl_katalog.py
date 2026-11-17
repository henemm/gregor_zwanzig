"""Issue #3047 Runde 7, Befund E1 (Go-Teil): Grundauswahl neuer Orts-Briefings.

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md
(„Nachtrag Runde 7", Tech-Lead-Entscheidung: neues Orts-Briefing aus
Standard-Vorlage speichert die Grundauswahl ausdruecklich).

Go schreibt bei der Neuanlage ``active_metrics`` als ``{metric_id, aggregation}``
mit der Auswertung aus ``tests/fixtures/vergleich_grundauswahl_aggregation.json``
(Go-Test ``TestF3047E1_AggregationstabelleGleichPythonKatalog``). Hier wird die
Fixture gegen den ausgelieferten Vergleichs-Katalog geprueft (Drift-Waechter)
und gezeigt, dass jede so geschriebene Zeile von der Mail-Aufloesung
(``resolve_enabled_metrics``) als genau diese Zeile erkannt wird: keine
stille Verwerfung, keine Vertauschung.
"""
from __future__ import annotations

import json
from pathlib import Path

from output.renderers.compare_metric_catalog import get_compare_metric_catalog, key_for
from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID, resolve_enabled_metrics

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "vergleich_grundauswahl_aggregation.json"


def _fixture() -> dict[str, str]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_gleich_erstem_katalogeintrag_je_groesse():
    """Editor-Regel (``WetterTabInhalt.svelte``: ``katalog.find(metric_id)``):
    erster Eintrag des ausgelieferten Katalogs je Groesse."""
    erwartet: dict[str, str] = {}
    for eintrag in get_compare_metric_catalog():
        erwartet.setdefault(eintrag["metric_id"], eintrag["aggregation"])
    assert _fixture() == erwartet


def test_jede_go_zeile_landet_als_genau_diese_mailzeile():
    tabelle = _fixture()
    eintraege = [{"metric_id": mid, "aggregation": agg} for mid, agg in tabelle.items()]
    aufgeloest = resolve_enabled_metrics(eintraege)
    soll = [FRONTEND_TO_RENDERER_METRIC_ID[key_for(e["metric_id"], e["aggregation"])] for e in eintraege]
    assert aufgeloest == soll and len(aufgeloest) == len(tabelle)
