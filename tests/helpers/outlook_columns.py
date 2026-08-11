"""Soll-Menge der Ausblick-Spalten des Ortsvergleichs — EINE Ableitung.

Epic #1703 Scheibe 2. SPEC: docs/specs/modules/fix_1703_s2_ausblick_matrix.md

Die Zahl der Ausblick-Spalten wird NICHT getippt. Sie ist genau die Menge der
vom Compare-Katalog AUSGELIEFERTEN Groesse-Auswertung-Paare
(``get_compare_metric_catalog()``) — der Katalog filtert zentral nicht
waehlbare Groessen (``cape``, seit #1585) bereits selbst heraus. Damit erbt der
Waechter die Katalog-Entscheidung, statt sie ein zweites Mal zu fuehren
(Muster ``tests/helpers/hourly_columns.py``: Ausnahmen nie zweimal pflegen).

Waechst der Katalog um ein Paar, zieht die Soll-Menge automatisch mit.

**Grenze, ausdruecklich** (Lehre aus Scheibe 1, Finding F001): wer sein Soll
aus demselben Katalog liest wie der Prueflig, bewacht **Vollstaendigkeit**,
nicht **Zuordnung**. Vertauschte man Einheit oder Auswertung zweier
Katalog-Zeilen, bliebe jede darauf gestuetzte Achse gruen.

Die erwartete Spaltenueberschrift wird hier aus den Katalog-Feldern
``label`` + ``aggregation_label`` GERECHNET und nicht aus
``outlook_columns()`` uebernommen: sonst waeren Massstab und Prueflig
dieselbe Funktion und die Beschriftungs-Zusicherung bewiese nichts. Die Regel
"bei mehrfach vorkommendem Namen haengt die Auswertung an" ist die
freigegebene Produktvorgabe (PO-Entscheidung 2026-07-27, "keine zwei gleich
beschrifteten Spalten") — sie steht hier als Soll, nicht als Kopie einer
Implementierung.
"""
from __future__ import annotations

from collections import Counter

from app.metric_catalog import get_metric, summary_field_for
from output.renderers.compare_metric_catalog import (
    COMPARE_METRIC_CATALOG, get_compare_metric_catalog,
)

# Vakuum-Schutz-Untergrenze (Muster hourly_columns.py:130-158): ein Waechter,
# der ueber eine leere oder stark geschrumpfte Menge iteriert, ist immer gruen
# und bewacht nichts. Gemessen 2026-08-11: 25 ausgelieferte Paare.
OUTLOOK_SOLL_MINDESTGROESSE = 20


def nicht_waehlbare_compare_keys(entries: list[dict] | None = None) -> list[str]:
    """Die Katalog-Schluessel, die ``get_compare_metric_catalog()`` wegen
    ``selectable=False`` zurueckhaelt — gelesen aus dem zentralen Register,
    nicht hier aufgezaehlt."""
    quelle = COMPARE_METRIC_CATALOG if entries is None else entries
    return [e["key"] for e in quelle if not get_metric(e["metric_id"]).selectable]


def compare_outlook_soll_spalten(entries: list[dict] | None = None) -> list[dict]:
    """Je ausgeliefertem Katalog-Paar ein Soll-Eintrag, in Katalog-Reihenfolge.

    ``entries`` injiziert eine Testkopie der Katalogzeilen (Vorbild
    ``get_compare_metric_catalog(entries=...)``), damit die
    Plausibilitaets-Rechnung ohne Monkeypatch des echten Katalogs pruefbar
    ist.
    """
    geliefert = get_compare_metric_catalog(entries)
    haeufigkeit = Counter(e["label"] for e in geliefert)
    soll: list[dict] = []
    for eintrag in geliefert:
        label = eintrag["label"]
        auswertung_label = eintrag.get("aggregation_label", "")
        mehrdeutig = haeufigkeit[label] > 1 and bool(auswertung_label)
        soll.append({
            "key": eintrag["key"],
            "metric_id": eintrag["metric_id"],
            "aggregation": eintrag["aggregation"],
            "label": label,
            "ueberschrift": f"{label} {auswertung_label}" if mehrdeutig else label,
            "summary_field": summary_field_for(
                eintrag["metric_id"], eintrag["aggregation"],
            ),
            "kind": eintrag.get("kind", "range"),
        })
    return soll


def compare_outlook_soll_paare(entries: list[dict] | None = None) -> list[dict]:
    """Die Auswahl im Speicherformat der Bedienflaeche (#1373-Vokabular) —
    genau das, was ein Nutzer waehlt, der alles waehlt."""
    return [
        {"metric_id": s["metric_id"], "aggregation": s["aggregation"]}
        for s in compare_outlook_soll_spalten(entries)
    ]


def assert_soll_menge_ist_plausibel(entries: list[dict] | None = None) -> list[dict]:
    """Vakuum-Schutz mit ausgesprochener Rechnung: Katalog gross genug, Abzug
    begruendet, Ergebnis > 0, jedes Paar aufloesbar. Gibt die Soll-Menge
    zurueck."""
    roh = COMPARE_METRIC_CATALOG if entries is None else entries
    zurueckgehalten = nicht_waehlbare_compare_keys(entries)
    geliefert = get_compare_metric_catalog(entries)
    soll = compare_outlook_soll_spalten(entries)

    assert soll, (
        "Soll-Menge leer — Vakuum. Jede Achse dieser Scheibe liefe ueber null "
        "Faelle und waere immer gruen."
    )
    assert len(soll) >= OUTLOOK_SOLL_MINDESTGROESSE, (
        f"Vakuum-Schutz: nur {len(soll)} waehlbare Ausblick-Paare "
        f"({[s['key'] for s in soll]}) — erwartet mindestens "
        f"{OUTLOOK_SOLL_MINDESTGROESSE}. Entweder ist der Compare-Katalog "
        "geschrumpft oder die Soll-Rechnung greift daneben."
    )
    assert len(geliefert) == len(roh) - len(zurueckgehalten), (
        f"Rechnung geht nicht auf: {len(roh)} rohe Katalog-Zeilen "
        f"- {len(zurueckgehalten)} nicht waehlbare ({zurueckgehalten}) "
        f"!= {len(geliefert)} ausgelieferte"
    )
    assert len(soll) == len(geliefert), (
        f"Soll-Menge ({len(soll)}) und ausgelieferter Katalog "
        f"({len(geliefert)}) sind auseinandergelaufen"
    )
    assert zurueckgehalten, (
        "Der Compare-Katalog haelt keine einzige Zeile mehr wegen "
        "selectable=False zurueck (bis 2026-08-11: 'cape_max_jkg', #1585) — "
        "der Filterschritt waere damit unbewacht, die Rechnung oben trivial."
    )
    ohne_feld = [s["key"] for s in soll if not s["summary_field"]]
    assert not ohne_feld, (
        f"Katalog-Paare ohne ``SegmentWeatherSummary``-Feld: {ohne_feld} — "
        "``outlook_columns()`` verwirft sie stillschweigend "
        "(compare_outlook_metric_ids.py:98-100), die Spalte fehlte dann ganz"
    )
    doppelt = [u for u, n in Counter(s["ueberschrift"] for s in soll).items() if n > 1]
    assert not doppelt, (
        f"Zwei Soll-Spalten teilen sich eine Ueberschrift: {doppelt} — die "
        "Auswertungs-Unterscheidung greift nicht mehr"
    )
    return soll
