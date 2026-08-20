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
    """Je ausgeliefertem Katalog-Paar ein Soll-Eintrag, in Katalog-Reihenfolge
    -- MIT Ausnahme: min+max derselben Groesse ergeben EINE zusammengefuehrte
    Spalte (``_merge_min_max_soll``, s. dort).

    ``entries`` injiziert eine Testkopie der Katalogzeilen (Vorbild
    ``get_compare_metric_catalog(entries=...)``), damit die
    Plausibilitaets-Rechnung ohne Monkeypatch des echten Katalogs pruefbar
    ist.
    """
    geliefert = get_compare_metric_catalog(entries)
    haeufigkeit = Counter(e["label"] for e in geliefert)
    roh: list[dict] = []
    for eintrag in geliefert:
        label = eintrag["label"]
        auswertung_label = eintrag.get("aggregation_label", "")
        mehrdeutig = haeufigkeit[label] > 1 and bool(auswertung_label)
        roh.append({
            "key": eintrag["key"],
            "metric_id": eintrag["metric_id"],
            "aggregation": eintrag["aggregation"],
            "label": label,
            "ueberschrift": f"{label} {auswertung_label}" if mehrdeutig else label,
            "summary_field": summary_field_for(
                eintrag["metric_id"], eintrag["aggregation"],
            ),
            "kind": eintrag.get("kind", "range"),
            # Die Paare, die dieser Soll-Eintrag repraesentiert -- fuer
            # unveraenderte Eintraege genau eines, fuer Merges (s.u.) zwei.
            "paare": [{"metric_id": eintrag["metric_id"], "aggregation": eintrag["aggregation"]}],
        })
    return _merge_min_max_soll(roh)


def _merge_min_max_soll(roh: list[dict]) -> list[dict]:
    """#1848 A1 (PO-Entscheid 2026-08-20): min+max derselben Groesse ergeben
    in der Produktivauswahl EINE Spalte (Schraegstrich-Zelle), nicht mehr
    zwei mit Minimum-/Maximum-Suffix -- loest fuer diesen Fall die rein
    paarbasierte Soll-Menge aus Epic #1703 Scheibe 2 ab (dieselbe Merge-
    Regel wie die Produktivfunktion
    ``compare_outlook_metric_ids._merge_min_max_pairs()``).

    „Jede waehlbare GROESSE ergibt genau eine Spalte" (AC-S2-1) bleibt dabei
    wahr -- nur die Menge der Paare, die eine Groesse ausmacht, aendert
    sich. Die Disambiguierungs-Logik (Minimum-/Maximum-Suffix bei
    mehrdeutigem Label) bleibt fuer den Fall bestehen, dass eine Groesse
    KUENFTIG mehr als zwei Auswertungen traegt (z. B. ``avg`` bei
    Temperatur, Scheibe A3): dann mergen min+max weiterhin zur Spanne, aber
    die dritte Auswertung bleibt eine eigene, disambiguierte Spalte.
    """
    by_metric: dict[str, dict[str, int]] = {}
    for i, s in enumerate(roh):
        if s["kind"] == "range" and s["aggregation"] in ("min", "max"):
            by_metric.setdefault(s["metric_id"], {})[s["aggregation"]] = i

    merge_at: dict[int, int] = {}
    consumed: set[int] = set()
    for aggs in by_metric.values():
        if "min" in aggs and "max" in aggs:
            first_idx, second_idx = sorted((aggs["min"], aggs["max"]))
            merge_at[first_idx] = second_idx
            consumed.add(second_idx)

    merged: list[dict] = []
    for i, s in enumerate(roh):
        if i in consumed:
            continue
        if i not in merge_at:
            merged.append(s)
            continue
        partner = roh[merge_at[i]]
        lo = s if s["aggregation"] == "min" else partner
        hi = s if s["aggregation"] == "max" else partner
        merged.append({
            "key": f"{s['key']}+{partner['key']}",
            "metric_id": s["metric_id"],
            "aggregation": None,
            "label": s["label"],
            "ueberschrift": s["label"],
            # Truthy UND informativ (statt None): ein Tupel beider Felder --
            # der Vakuum-Schutz `ohne_feld` in
            # `assert_soll_menge_ist_plausibel()` prueft nur auf Wahrheits-
            # wert, ein `None` wuerde den Merge selbst faelschlich als
            # "kein SegmentWeatherSummary-Feld" melden.
            "summary_field": (lo["summary_field"], hi["summary_field"]),
            "kind": "range",
            "paare": s["paare"] + partner["paare"],
        })
    return merged


def compare_outlook_soll_paare(entries: list[dict] | None = None) -> list[dict]:
    """Die Katalog-Paare hinter der Soll-Menge (#1373-Vokabular).

    Seit #1848 A2 ist das NICHT mehr das Speicherformat der Bedienflaeche --
    gespeichert wird die Kennung (s. ``compare_outlook_soll_kennungen()``).
    Die flache Paar-Menge bleibt als Rechengroesse fuer die
    Vollstaendigkeits-Waechter erhalten: jedes ausgelieferte Katalog-Paar muss
    in genau einem Soll-Eintrag auftauchen."""
    return [p for s in compare_outlook_soll_spalten(entries) for p in s["paare"]]


def compare_outlook_soll_kennungen(entries: list[dict] | None = None) -> list[str]:
    """Die Auswahl im Speicherformat der Bedienflaeche (#1848 A2) — genau das,
    was ein Nutzer speichert, der alles waehlt: die Kennungen, in
    Katalog-Reihenfolge, jede genau einmal.

    Abgeleitet aus derselben Soll-Menge wie die Spalten und die Paare, damit
    Auswahl und Erwartung nicht auseinanderlaufen koennen."""
    kennungen: list[str] = []
    for spalte in compare_outlook_soll_spalten(entries):
        if spalte["metric_id"] not in kennungen:
            kennungen.append(spalte["metric_id"])
    return kennungen


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
    # #1848 A1: min+max derselben Groesse ergeben EINEN Soll-Eintrag mit
    # ZWEI Paaren (``paare``) -- "ein Eintrag je geliefertem Paar" gilt
    # seither nur noch auf PAAR-Ebene (jedes gelieferte Paar erscheint in
    # genau einem Soll-Eintrag), nicht mehr 1:1 auf Spalten-Ebene.
    paare_gesamt = sum(len(s["paare"]) for s in soll)
    assert paare_gesamt == len(geliefert), (
        f"Paar-Menge ueber alle Soll-Eintraege ({paare_gesamt}) und "
        f"ausgelieferter Katalog ({len(geliefert)}) sind auseinandergelaufen"
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
