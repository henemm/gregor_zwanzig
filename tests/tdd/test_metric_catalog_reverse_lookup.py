"""TDD RED — Issue #1459: Rueckwaerts-Aufloesung Summary-Feld -> Register-Paar.

SPEC: docs/specs/modules/feat_1459_alert_protokoll.md (AC-5, AC-6, O1)

RED-Grund heute: ``app.metric_catalog.metric_and_aggregation_for_field()``
existiert nicht -> ImportError je Test (die Funktion IST der Prueflings-
Gegenstand dieser ACs).

Mock-frei: reine Katalog-Auswertung auf der echten ``_METRICS``-Registry, kein
Netz, keine Persistenz.
"""
from __future__ import annotations

from collections import defaultdict


def _swapped_registry():
    """Echte Kopie von ``_METRICS`` mit VERTAUSCHTER Position von
    ``temperature``/``temperature_cold`` -- der einzige gemessene
    Mehrdeutigkeits-Fall (``temp_min_c``)."""
    from app.metric_catalog import _METRICS

    registry = list(_METRICS)
    ids = [m.id for m in registry]
    i, j = ids.index("temperature"), ids.index("temperature_cold")
    registry[i], registry[j] = registry[j], registry[i]
    return registry


# ───────────────────────────────── AC-5 ────────────────────────────────────

def test_ac5_mehrdeutiges_feld_haengt_nicht_an_der_listenreihenfolge():
    """AC-5 GIVEN ``temperature`` und ``temperature_cold`` stehen in der
    Registry in vertauschter Reihenfolge
    WHEN ``metric_and_aggregation_for_field("temp_min_c")`` aufgeloest wird
    THEN kommt in BEIDEN Reihenfolgen ``("temperature", "min")`` heraus.

    Der Nachweis laeuft ueber eine tatsaechlich umsortierte Kopie (Test-Seam
    ``_registry``) -- ein Test, der nur das heutige Ergebnis abfragt, koennte
    bei einer Umsortierung der Registry nie anschlagen (#1435 E3a).
    """
    from app.metric_catalog import _METRICS, metric_and_aggregation_for_field

    swapped = _swapped_registry()
    original_ids = [m.id for m in _METRICS]
    swapped_ids = [m.id for m in swapped]
    assert swapped_ids != original_ids, (
        "Der Test-Seam bekommt dieselbe Reihenfolge wie die echte Registry — "
        "damit wuerde AC-5 nichts pruefen."
    )
    assert (
        swapped_ids.index("temperature_cold") < swapped_ids.index("temperature")
    ) != (
        original_ids.index("temperature_cold") < original_ids.index("temperature")
    ), "Die Vorrang-Positionen der beiden Kandidaten sind nicht wirklich getauscht."

    heute = metric_and_aggregation_for_field("temp_min_c")
    vertauscht = metric_and_aggregation_for_field("temp_min_c", _registry=swapped)

    assert heute == ("temperature", "min"), (
        f"Heutige Reihenfolge liefert {heute!r} statt der nutzersichtbaren "
        "Groesse ('temperature', 'min')."
    )
    assert vertauscht == ("temperature", "min"), (
        f"Vertauschte Reihenfolge liefert {vertauscht!r} — die Aufloesung "
        "haengt an der Listenposition statt an selectable=True."
    )


# ───────────────────────────────── AC-6 ────────────────────────────────────

def test_ac6_ratsche_jedes_mehrfach_belegte_summary_feld_ist_aufloesbar():
    """AC-6 GIVEN die vollstaendige Registry ``_METRICS``
    WHEN jedes Summary-Feld mit mehr als einem Eigentuemer aufgeloest wird
    THEN liefert die Aufloesung fuer JEDES dieser Felder ein Ergebnis != None.

    Die Gruppen werden aus der Registry selbst gebildet — keine handgepflegte
    Feldliste, damit die Ratsche mit dem Katalog mitwaechst.
    """
    from app.metric_catalog import _METRICS, metric_and_aggregation_for_field

    owners: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for m in _METRICS:
        for aggregation, summary_field in m.summary_fields.items():
            owners[summary_field].append((m.id, aggregation))

    mehrfach = {f: o for f, o in owners.items() if len(o) > 1}
    assert mehrfach, (
        "Kein einziges Summary-Feld hat mehrere Eigentuemer — die Ratsche "
        "wuerde nichts pruefen und waere immer gruen (Waechter-Falle)."
    )

    for summary_field, kandidaten in mehrfach.items():
        aufgeloest = metric_and_aggregation_for_field(summary_field)
        assert aufgeloest is not None, (
            f"Summary-Feld {summary_field!r} hat {len(kandidaten)} Eigentuemer "
            f"({kandidaten!r}) und bleibt nach der Vorrangregel mehrdeutig — "
            "im Alarm-Protokoll fiele die Wettergroesse still weg."
        )
        assert aufgeloest in kandidaten, (
            f"Aufgeloestes Paar {aufgeloest!r} fuer {summary_field!r} ist kein "
            f"Eigentuemer dieses Feldes ({kandidaten!r})."
        )


def test_eindeutiges_feld_und_unbekanntes_feld():
    """Grundverhalten, auf dem AC-1..AC-3 aufsetzen: ein eindeutig belegtes
    Feld liefert sein Register-Paar, ein unbekanntes Feld liefert fail-soft
    ``None`` (statt den Alarm-Lauf abzubrechen)."""
    from app.metric_catalog import metric_and_aggregation_for_field

    assert metric_and_aggregation_for_field("gust_max_kmh") == ("gust", "max")
    assert metric_and_aggregation_for_field("thunder_level_max") == ("thunder", "max")
    assert metric_and_aggregation_for_field("precip_sum_mm") == ("precipitation", "sum")
    assert metric_and_aggregation_for_field("gibt_es_nicht") is None
