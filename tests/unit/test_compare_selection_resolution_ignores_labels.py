"""BESTANDSSCHUTZ-ANKER (#1401 Scheibe A1, AC-5) -- bewusst GRUEN, vor UND
nach der Umstellung.

Haelt fest: die gespeicherte Metrik-Auswahl eines Ortsvergleichs wird
ausschliesslich ueber den Auswahl-Schluessel (z. B. "temp_max_c") bzw. das
Paar {metric_id, aggregation} aufgeloest -- der ANZEIGENAME kommt in
Persistenz und Aufloeser gar nicht vor. Die Umbenennung aus #1401 kann die
gespeicherte Auswahl daher strukturell nicht brechen (Bug-Klasse
BUG-DATALOSS #102).

SPEC: docs/specs/modules/fix_1401_a1_namensregister.md (AC-5)
"""
from __future__ import annotations

from output.renderers.compare_metric_catalog import get_compare_metric_catalog
from output.renderers.compare_metric_ids import (
    FRONTEND_TO_RENDERER_METRIC_ID,
    resolve_enabled_metrics,
)

# Eine gespeicherte, nicht-leere Auswahl -- einmal im Altformat (Zeichenkette =
# Auswahl-Schluessel), einmal im Neuformat aus #1373 Scheibe B.
STORED_OLD_FORMAT: list = ["temp_max_c", "temp_min_c", "wind_max_kmh", "cloud_low_avg_pct"]
STORED_NEW_FORMAT: list = [
    {"metric_id": "temperature", "aggregation": "max"},
    {"metric_id": "temperature", "aggregation": "min"},
    {"metric_id": "wind", "aggregation": "max"},
    {"metric_id": "cloud_low", "aggregation": "avg"},
]


def test_both_stored_formats_resolve_to_the_same_renderer_metrics() -> None:
    """Beide Speicherformate ergeben dieselbe aufgeloeste Auswahl in derselben
    Reihenfolge -- die Auswahl haengt am Schluessel/Paar, nicht am Namen."""
    alt = resolve_enabled_metrics(STORED_OLD_FORMAT)
    neu = resolve_enabled_metrics(STORED_NEW_FORMAT)
    assert alt == ["temp_max", "temp_min", "wind_max", "cloud_low_avg"]
    assert neu == alt, f"Neuformat loest anders auf als Altformat: {neu} vs. {alt}"


def test_no_display_name_is_part_of_the_selection_vocabulary() -> None:
    """Der eigentliche Beweis: kein Anzeigename des Compare-Katalogs ist ein
    gueltiger Auswahl-Schluessel -- eine Auswahl aus lauter Namen loest zu
    nichts auf. Die Namensspalte ist vom Auswahlpfad vollstaendig entkoppelt."""
    # #1401 A1: der Name steht nicht mehr in der Katalogzeile, er wird beim
    # Abruf aus dem zentralen Register abgeleitet -- geprueft wird der Name, den
    # der Endpoint tatsaechlich ausliefert.
    labels = [entry["label"] for entry in get_compare_metric_catalog()]
    kollisionen = [lb for lb in labels if lb in FRONTEND_TO_RENDERER_METRIC_ID]
    assert not kollisionen, f"Anzeigenamen doppeln als Auswahl-Schluessel: {kollisionen}"
    assert resolve_enabled_metrics(labels) == [], (
        "Anzeigenamen werden als Auswahl aufgeloest -- eine Umbenennung wuerde "
        "die gespeicherte Auswahl verschieben"
    )


def test_stored_entries_carry_no_label_field() -> None:
    """Was gespeichert wird, traegt keinen Namen: Altformat = Zeichenkette,
    Neuformat = genau metric_id/aggregation. Eine Label-Aenderung kann daher
    keinen gespeicherten Datensatz entwerten."""
    assert all(isinstance(item, str) for item in STORED_OLD_FORMAT)
    for item in STORED_NEW_FORMAT:
        assert set(item) == {"metric_id", "aggregation"}, (
            f"Neuformat-Eintrag traegt zusaetzliche Felder: {sorted(item)}"
        )
