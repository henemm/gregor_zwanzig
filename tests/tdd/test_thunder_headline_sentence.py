"""TDD RED -- Issue #2028.

SPEC: docs/specs/modules/fix_2028_gewitter_satzvorlagen.md -- AC-3, AC-4.

Die Satzkoepfe der Gewitter-Tagesaussage (NONE/LOW/MED/HIGH) werden heute in
``trip_report_scheduler.py`` an zwei Stellen unabhaengig gebaut
(``_thunder_entry_from_trend_row`` und ``_build_thunder_forecast``), das
Nacht-Adjektiv steht lokal in ``day_window._NIGHT_ADDENDUM_WORD``. Der Fix
zieht beides in die kanonische Quelle ``app.thunder_scale``:
``thunder_headline_sentence(level, when, carriers)`` und
``THUNDER_NIGHT_ADJECTIVE_DE``.

Alle Erwartungen sind FEST VERDRAHTETE Literale des heutigen Wortlauts --
nichts wird zur Laufzeit per ``thunder_low_statement_sentence`` berechnet
(das wuerde die Delegation gegen sich selbst testen, Spec AC-3).

LOW-Traeger: ``carriers=["cape"]`` -- die Form, die beide Scheduler-Aufrufer
heute liefern (Trend-Weg: ``union_of_max_carriers(...)`` -> ``list[str]``;
Fetch-Weg: ``summary.thunder_level_max_signals`` -> ``list[str]``). Reine
CAPE-Herkunft ergibt heute den Kern "instabile Luftmasse" plus Stufenwort
"(leicht)", satzanfangs gross: "Instabile Luftmasse (leicht)".

Die neuen Symbole werden bewusst INNERHALB der Testfunktionen importiert,
damit jeder Test einzeln rot wird (ImportError) statt die Sammlung
abzubrechen.

RED-Ursache (vor der Implementierung):
- ``app.thunder_scale.thunder_headline_sentence`` existiert nicht -> ImportError.
- ``app.thunder_scale.THUNDER_NIGHT_ADJECTIVE_DE`` existiert nicht -> ImportError.
- ``app.day_window._NIGHT_ADDENDUM_WORD`` existiert noch -> Assertion rot.
"""
from __future__ import annotations

import pytest

from app.models import ThunderLevel

_LOW_CARRIERS = ["cape"]

# (Stufe, when, erwarteter Satzkopf) -- acht Faelle, Spec AC-3.
_MATRIX = [
    (ThunderLevel.NONE, "14:00", "Kein Gewitter erwartet"),
    (ThunderLevel.NONE, None, "Kein Gewitter erwartet"),
    (ThunderLevel.LOW, "14:00", "Instabile Luftmasse (leicht) ab 14:00"),
    (ThunderLevel.LOW, None, "Instabile Luftmasse (leicht)"),
    (ThunderLevel.MED, "14:00", "Gewitter möglich ab 14:00"),
    (ThunderLevel.MED, None, "Gewitter möglich"),
    (ThunderLevel.HIGH, "14:00", "Starkes Gewitter erwartet ab 14:00"),
    (ThunderLevel.HIGH, None, "Starkes Gewitter erwartet"),
]


@pytest.mark.parametrize(
    ("level", "when", "expected"),
    _MATRIX,
    ids=[f"{lv.name}-{'when' if w else 'ohne_when'}" for lv, w, _ in _MATRIX],
)
def test_ac3_thunder_headline_sentence_liefert_heutigen_wortlaut(
    level, when, expected
):
    """AC-3: Given eine Gewitterstufe (NONE/LOW/MED/HIGH), ``when`` gesetzt
    ("14:00") bzw. ``None`` und fuer LOW die realistische Traegerliste
    ``["cape"]`` / When ``thunder_headline_sentence(level, when, carriers)``
    aus ``app.thunder_scale`` aufgerufen wird / Then liefert sie exakt den
    heutigen Satzkopf der beiden Scheduler-Wege (fest verdrahtetes Literal).
    """
    from app.thunder_scale import thunder_headline_sentence

    assert thunder_headline_sentence(level, when, _LOW_CARRIERS) == expected


def test_ac3_none_ignoriert_traeger_und_when():
    """AC-3: Given Stufe NONE mit gesetzter Traegerliste und gesetztem
    ``when`` / When ``thunder_headline_sentence`` aufgerufen wird / Then
    bleibt der Satzkopf "Kein Gewitter erwartet" -- ohne Uhrzeit-Anhang.
    """
    from app.thunder_scale import thunder_headline_sentence

    assert (
        thunder_headline_sentence(ThunderLevel.NONE, "09:00", ["cape", "blitzdichte"])
        == "Kein Gewitter erwartet"
    )


def test_ac4_night_adjective_tabelle_ist_kanonisch():
    """AC-4: Given die neue kanonische Tabelle ``THUNDER_NIGHT_ADJECTIVE_DE``
    in ``app.thunder_scale`` / When MED und HIGH nachgeschlagen werden /
    Then lauten die Adjektive "mittleres" bzw. "starkes".
    """
    from app.thunder_scale import THUNDER_NIGHT_ADJECTIVE_DE

    assert THUNDER_NIGHT_ADJECTIVE_DE[ThunderLevel.MED] == "mittleres"
    assert THUNDER_NIGHT_ADJECTIVE_DE[ThunderLevel.HIGH] == "starkes"


def test_ac4_lokale_night_addendum_tabelle_ist_entfernt():
    """AC-4: Given der Fix ist umgesetzt / When auf
    ``app.day_window._NIGHT_ADDENDUM_WORD`` zugegriffen wird / Then existiert
    das Attribut nicht mehr -- die lokale Kopie ist ersatzlos entfallen.
    """
    import app.day_window as day_window

    assert not hasattr(day_window, "_NIGHT_ADDENDUM_WORD"), (
        "day_window._NIGHT_ADDENDUM_WORD existiert noch -- lokale Kopie der "
        "Nacht-Adjektive muss zugunsten von "
        "thunder_scale.THUNDER_NIGHT_ADJECTIVE_DE entfallen (#2028)."
    )


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (ThunderLevel.MED, ", nachts mittleres Gewitter ab 22:00"),
        (ThunderLevel.HIGH, ", nachts starkes Gewitter ab 22:00"),
    ],
    ids=["MED", "HIGH"],
)
def test_ac4_night_addendum_wortlaut_bleibt_byte_identisch(level, expected):
    """AC-4: Given ein Nacht-Treffer der Stufe MED bzw. HIGH um 22 Uhr ohne
    Hagel / When ``format_night_addendum`` aufgerufen wird UND die kanonische
    Tabelle ``THUNDER_NIGHT_ADJECTIVE_DE`` existiert / Then bleibt der
    Halbsatz byte-identisch zu heute (Literal aus
    ``tests/unit/test_thunder_night_addendum.py``).
    """
    from app.day_window import format_night_addendum
    from app.thunder_scale import THUNDER_NIGHT_ADJECTIVE_DE

    assert level in THUNDER_NIGHT_ADJECTIVE_DE
    assert format_night_addendum(level, 22) == expected
