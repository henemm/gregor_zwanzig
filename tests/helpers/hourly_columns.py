"""Soll-Menge der Stundenverlauf-Spalten — EINE Ableitung fuer alle Tests.

Issue #1406 Scheibe B. SPEC: docs/specs/modules/feat_1406b_stundenverlauf_katalog.md

Die Zahl der Wert-Spalten wird NICHT getippt. Sie ergibt sich aus dem zentralen
Register minus zwei benannten Ausnahmen:

* dem **Merge-Signal** Windrichtung (erzeugt nie eine eigene Spalte, sondern
  wandert als Kompasstext in die Wind-Zelle — Spec Implementation Details 5),
* den **ausdruecklich ausgenommenen** Groessen, die der Produktivcode selbst
  benennen muss (AC-11, PO-Entscheid 2026-08-01: ``sunshine`` ist stuendlich
  nur als Einstrahlung in W/m² verfuegbar).

Waechst der Katalog um eine Groesse, zieht die Soll-Menge automatisch mit —
genau das war der Grund, warum die erste Fassung dieser Tests mit fest
getippten 23/24 nachgezogen werden musste.

Die Ausnahme-Menge wird aus dem PRODUKTIVCODE gelesen, nicht hier gefuehrt:
sonst haetten Bedienflaeche, Renderer und Test drei Meinungen darueber, was
ausgenommen ist — dieselbe Krankheit, gegen die diese Scheibe antritt.
"""
from __future__ import annotations

import pytest

from app.metric_catalog import MetricDefinition, get_all_metrics

# Die eine Groesse ohne eigene Spalte, weil sie in die Wind-Zelle gemergt wird.
MERGE_ONLY_METRIC_ID = "wind_direction"

# Namen, unter denen der Produktivcode seine benannte Ausnahme-Menge fuehren
# darf. Mehrere Kandidaten, weil die Spec den Bezeichner bewusst offen laesst
# (Muster: `test_ac6_transition_union_carries_a_review_date`).
_AUSNAHME_NAMEN = (
    "HOURLY_EXCLUDED_METRIC_IDS",
    "HOURLY_NOT_SELECTABLE_METRIC_IDS",
    "HOURLY_AUSGENOMMENE_METRIKEN",
)


def hourly_excluded_metric_ids() -> frozenset[str]:
    """Die ausdruecklich vom Stundenverlauf ausgenommenen Katalog-Groessen.

    Faellt mit klarer Ansage durch, solange der Produktivcode keine benannte
    Ausnahme-Menge fuehrt — eine im Test gefuehrte Liste waere ein weiterer
    Vokabular-Ort (AC-10) und wuerde eine kuenftige Ausnahme lautlos
    verschlucken.
    """
    from output.renderers import compare_hourly_metric_ids as modul

    for name in _AUSNAHME_NAMEN:
        wert = getattr(modul, name, None)
        if wert is not None:
            return frozenset(wert)
    pytest.fail(
        "Der Stundenverlauf-Aufloeser fuehrt keine benannte Ausnahme-Menge "
        f"(erwartet z. B. {_AUSNAHME_NAMEN[0]} in "
        "src/output/renderers/compare_hourly_metric_ids.py). AC-11 verlangt, "
        "dass 'sunshine' AUSGESPROCHEN ausgenommen ist statt stillschweigend "
        "zu fehlen."
    )


# Die von AC-11 mindestens verlangte Ausnahme. NUR als Sammelzeit-Rueckfall
# fuer `@pytest.mark.parametrize` — ein `pytest.fail()` waehrend der Sammlung
# waere ein Collect-Fehler und wuerde die ganze Testdatei killen.
_AC11_MINDESTAUSNAHME = frozenset({"sunshine"})


def hourly_excluded_metric_ids_for_parametrize() -> frozenset[str]:
    """Sammelzeit-sichere Fassung von ``hourly_excluded_metric_ids()``.

    Fehlt die benannte Ausnahme-Menge im Produktivcode noch — ODER ist sie
    vorhanden, aber LEER —, faellt sie auf die von AC-11 verlangte
    Mindestausnahme zurueck. Dass die Konstante existiert und ``sunshine``
    enthaelt, prueft ``test_the_exemption_set_is_named_in_production_code``
    (laut) — nicht die Sammlung.

    Adversary-Befund F003: „Attribut fehlt" und „Attribut da, aber leer"
    duerfen sich hier nicht unterscheiden. Sonst faellt der parametrisierte
    AC-11-Test bei geleerter Ausnahme-Menge mit 0 Faellen lautlos aus der
    Sammlung — ein Test, der bei einer Mutation verschwindet statt
    fehlzuschlagen, ist wertlos. ``pytest.fail()`` ist hier verboten (Sammelzeit
    -> Collect-Fehler wuerde die ganze Datei erlegen), deshalb Rueckfall.
    """
    try:
        from output.renderers import compare_hourly_metric_ids as modul
    except Exception:  # pragma: no cover - Modul nicht ladbar
        return _AC11_MINDESTAUSNAHME
    for name in _AUSNAHME_NAMEN:
        wert = getattr(modul, name, None)
        if wert is None:
            continue
        menge = frozenset(wert)
        # Leere Menge == „nicht gefuehrt": AC-11-Minimum, nie 0 Faelle.
        return menge or _AC11_MINDESTAUSNAHME
    return _AC11_MINDESTAUSNAHME


def expected_hour_column_metrics() -> list[MetricDefinition]:
    """Katalog-Groessen, die im Stundenverlauf eine eigene Spalte bekommen —
    in Katalog-Reihenfolge."""
    ausgenommen = hourly_excluded_metric_ids()
    return [
        m for m in get_all_metrics()
        if m.id != MERGE_ONLY_METRIC_ID and m.id not in ausgenommen
    ]


def expected_hour_column_metrics_for_parametrize() -> list[MetricDefinition]:
    """Sammelzeit-sichere Fassung von ``expected_hour_column_metrics()`` —
    ausschliesslich fuer ``@pytest.mark.parametrize`` (s. Kommentar oben)."""
    ausgenommen = hourly_excluded_metric_ids_for_parametrize()
    return [
        m for m in get_all_metrics()
        if m.id != MERGE_ONLY_METRIC_ID and m.id not in ausgenommen
    ]


def expected_hour_column_keys() -> list[str]:
    """Renderer-Feldnamen (``dp_field``) der erwarteten Wert-Spalten."""
    return [m.dp_field for m in expected_hour_column_metrics()]


def expected_hour_column_labels() -> list[str]:
    """Spaltenueberschriften (``col_label``) der erwarteten Wert-Spalten."""
    return [m.col_label for m in expected_hour_column_metrics()]


def assert_soll_menge_ist_plausibel() -> list[MetricDefinition]:
    """Vakuum-Schutz mit ausgesprochener Rechnung: Katalog gross genug, genau
    zwei Abzuege, Ergebnis > 0. Gibt die Soll-Menge zurueck."""
    katalog = get_all_metrics()
    ausgenommen = hourly_excluded_metric_ids()
    soll = expected_hour_column_metrics()

    assert len(katalog) >= 24, (
        f"Der Katalog fuehrt nur {len(katalog)} waehlbare Groessen — die "
        "Soll-Menge waere kaum aussagekraeftig."
    )
    assert MERGE_ONLY_METRIC_ID in {m.id for m in katalog}, (
        f"Das Merge-Signal '{MERGE_ONLY_METRIC_ID}' steht nicht im Katalog — "
        "der Abzug haette keine Grundlage."
    )
    assert ausgenommen, (
        "Die Ausnahme-Menge ist leer — AC-11 verlangt mindestens 'sunshine'."
    )
    assert ausgenommen <= {m.id for m in katalog}, (
        f"Ausgenommene Kennungen, die es im Katalog nicht gibt: "
        f"{sorted(ausgenommen - {m.id for m in katalog})}"
    )
    assert len(soll) == len(katalog) - 1 - len(ausgenommen), (
        f"Rechnung geht nicht auf: {len(katalog)} Katalog-Groessen "
        f"- 1 Merge-Signal - {len(ausgenommen)} ausgenommene "
        f"!= {len(soll)} Wert-Spalten"
    )
    assert soll, "Soll-Menge leer — Vakuum."
    return soll
