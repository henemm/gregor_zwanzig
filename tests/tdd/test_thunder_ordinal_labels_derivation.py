"""RED-Tests fuer #1911 (Gewitter-Schwellenliste: Ableitung statt Doppel-Kopie),
Backend-Haelfte AC-4/AC-5.

Spec: docs/specs/modules/thunder_threshold_katalog.md (AC-4, AC-5)

Befund B2 (docs/context/fix-1911-thunder-katalog.md): der Compare-Katalog
(`compare_metric_catalog.py:104-112`) traegt `ordinalLabels` heute als
Literal-Liste `["kein", "leicht", "mittel", "hoch"]` -- die Datei importiert
`THUNDER_LABEL_DE`/`thunder_ordinal` (`output/metric_format.py:283-288`,
`app/thunder_scale.py:47-57`) NICHT. `compareMetricCatalogParity.test.ts`
vergleicht nur den *Wert* der Endpoint-Antwort, nie ihre *Herkunft* -- ein
Rueckfall auf ein Literal bliebe dort unentdeckt.

Mutations-Technik statt Mock (CLAUDE.md, "Mutations-Gegenprobe ist PFLICHT"):
`THUNDER_LABEL_DE` wird zur Laufzeit MUTIERT (dasselbe Dict-Objekt, in place)
und `output.renderers.compare_metric_catalog` per `importlib.reload()` neu
ausgefuehrt. Eine Ableitung liest die mutierten Werte bei jedem Reload frisch
ein (egal ob sie als Modul-Konstante beim Import oder erst beim Aufruf von
`get_compare_metric_catalog()` berechnet wird) -- ein Literal bleibt in
JEDEM Fall unveraendert. Das ist der Unterschied, den die zwei Tests unten
messen.

Beide Tests kombinieren absichtlich Wert-AENDERUNG und Reihenfolge-VERTAUSCHUNG
in einem Zug (test_ac5_...): eine reine Reihenfolge-Vertauschung OHNE
Wertaenderung waere gegen das heutige Literal ["kein","leicht","mittel","hoch"]
zufaellig identisch mit der erwarteten (korrekten) Ausgabe -- ein
"Null-ohne-Varianz"-Scheingruen. Erst mit unterscheidbaren Markerwerten wird
der Test heute nachweisbar ROT.
"""
from __future__ import annotations

import importlib

import pytest

import output.metric_format as metric_format
import output.renderers.compare_metric_catalog as compare_metric_catalog
from app.models import ThunderLevel

_ORIGINAL_LABELS = dict(metric_format.THUNDER_LABEL_DE)


def _restore_and_reload() -> None:
    """Stellt THUNDER_LABEL_DE (Inhalt UND Einfuegereihenfolge) wieder her und
    laedt compare_metric_catalog neu, damit andere Tests im selben Prozess den
    unveraenderten Katalog sehen."""
    metric_format.THUNDER_LABEL_DE.clear()
    for level, label in _ORIGINAL_LABELS.items():
        metric_format.THUNDER_LABEL_DE[level] = label
    importlib.reload(compare_metric_catalog)


@pytest.fixture(autouse=True)
def _cleanup_thunder_label_de():
    yield
    _restore_and_reload()


def _thunder_entry(catalog: list[dict]) -> dict:
    return next(e for e in catalog if e["key"] == "thunder_level_max")


def test_ac4_ordinal_labels_reflect_a_mutated_source_label() -> None:
    """AC-4 (Herkunfts-Nachweis): aendert sich EIN Eintrag in THUNDER_LABEL_DE,
    muss sich das in COMPARE_METRIC_CATALOG['thunder_level_max']['ordinalLabels']
    niederschlagen -- sonst ist ordinalLabels ein Literal, keine Ableitung.

    RED heute: compare_metric_catalog.py:111 ignoriert THUNDER_LABEL_DE
    vollstaendig -- die Mutation bleibt wirkungslos, das Reload liefert
    weiterhin die alte Wortliste ["kein","leicht","mittel","hoch"].
    """
    metric_format.THUNDER_LABEL_DE[ThunderLevel.MED] = "GZ_MARKER_MED"
    importlib.reload(compare_metric_catalog)

    thunder = _thunder_entry(compare_metric_catalog.get_compare_metric_catalog())

    assert "GZ_MARKER_MED" in thunder["ordinalLabels"], (
        "Eine Aenderung an THUNDER_LABEL_DE[MED] schlaegt sich nicht in "
        f"ordinalLabels nieder ({thunder['ordinalLabels']!r}) -- ordinalLabels "
        "ist (noch) ein Literal, keine Ableitung aus THUNDER_LABEL_DE (AC-4)."
    )
    assert thunder["ordinalLabels"][2] == "GZ_MARKER_MED", (
        "Das mutierte Label erscheint nicht an der ordinal-korrekten Position "
        f"(Index 2 = MED, thunder_ordinal()==2): {thunder['ordinalLabels']!r}"
    )


def test_ac5_ordinal_labels_follow_thunder_ordinal_not_dict_insertion_order() -> None:
    """AC-5: die Reihenfolge der abgeleiteten ordinalLabels entsteht ueber
    thunder_ordinal() (NONE=0 < LOW=1 < MED=2 < HIGH=3), NICHT ueber die
    Einfuegereihenfolge von THUNDER_LABEL_DE.

    THUNDER_LABEL_DE wird komplett geleert und in VERTAUSCHTER Reihenfolge
    (HIGH, MED, LOW, NONE) mit unterscheidbaren Markerwerten neu befuellt.
    Eine Ableitung ueber `list(THUNDER_LABEL_DE.values())` (Dict-
    Einfuegereihenfolge) wuerde ["GZ_HIGH","GZ_MED","GZ_LOW","GZ_NONE"]
    liefern -- eine Ableitung ueber thunder_ordinal() liefert unabhaengig von
    der Einfuegereihenfolge ["GZ_NONE","GZ_LOW","GZ_MED","GZ_HIGH"].

    RED heute: aus demselben Grund wie oben -- das Literal ignoriert
    THUNDER_LABEL_DE komplett, unabhaengig von seiner Reihenfolge; die
    erwarteten Marker-Werte erscheinen nirgends in der Antwort.
    """
    metric_format.THUNDER_LABEL_DE.clear()
    metric_format.THUNDER_LABEL_DE[ThunderLevel.HIGH] = "GZ_HIGH"
    metric_format.THUNDER_LABEL_DE[ThunderLevel.MED] = "GZ_MED"
    metric_format.THUNDER_LABEL_DE[ThunderLevel.LOW] = "GZ_LOW"
    metric_format.THUNDER_LABEL_DE[ThunderLevel.NONE] = "GZ_NONE"
    importlib.reload(compare_metric_catalog)

    thunder = _thunder_entry(compare_metric_catalog.get_compare_metric_catalog())

    assert thunder["ordinalLabels"] == ["GZ_NONE", "GZ_LOW", "GZ_MED", "GZ_HIGH"], (
        "ordinalLabels folgt nicht thunder_ordinal() (NONE<LOW<MED<HIGH), "
        f"erhalten: {thunder['ordinalLabels']!r} -- entweder unveraendertes "
        "Literal oder Ableitung ueber Dict-Einfuegereihenfolge "
        "(HIGH,MED,LOW,NONE) statt thunder_ordinal()."
    )


def test_real_catalog_unaffected_after_cleanup() -> None:
    """Gegenprobe: nach der (autouse) Wiederherstellung liefert der echte,
    unveraenderte Katalog wieder die heutigen vier Woerter -- reines
    Prozess-Hygiene-Netz, kein AC-Nachweis fuer sich."""
    importlib.reload(compare_metric_catalog)
    thunder = _thunder_entry(compare_metric_catalog.get_compare_metric_catalog())
    assert thunder["ordinalLabels"] == ["kein", "leicht", "mittel", "hoch"]
