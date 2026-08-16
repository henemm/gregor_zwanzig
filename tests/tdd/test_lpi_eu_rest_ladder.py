"""TDD RED — Issue #1678: ICON-EU bekommt eine eigene, belegte
LPI-Schwellenleiter statt der Interim-Werte 5/20/50.

SPEC: docs/specs/modules/feat_1678_lpi_eu_schwellenleiter.md

Deckt AC-1 bis AC-6 der Spec ab (AC-7 -- Bestandsprüfung der Registry-Tabelle
-- liegt in `tests/tdd/test_lpi_threshold_region_table.py`). Geprüft wird am
WIRKORT: ein Datenpunkt läuft durch die produktive Fusion
(`output.metric_format.thunder_level_from_signals()`) mit der aus
`app.model_registry.lpi_thresholds_jkg("<Gebiet>")` aufgelösten Leiter --
NIE der Tabelleninhalt allein.

RED-Ursache (heute): `LPI_THRESHOLDS_JKG["EU_REST"]` ist noch `(5.0, 20.0,
50.0)` (Interim), die Spec verlangt `(7.14, 23.81, 86.16)`
(Schroeder/Goecke/Koehler 2022). Damit fallen 60/21/6 J/kg heute noch auf die
ALTEN Schwellen und ergeben `HIGH`/`MED`/`LOW` statt der geforderten
`MED`/`LOW`/`NONE`.

Keine Mocks: reine Funktionsaufrufe, kein Netz.
"""
from __future__ import annotations

import pytest

from app.model_registry import lpi_thresholds_jkg
from app.models import ThunderLevel
from output.metric_format import thunder_level_from_signals, thunder_signal_carriers

NONE = ThunderLevel.NONE
LOW = ThunderLevel.LOW
MED = ThunderLevel.MED
HIGH = ThunderLevel.HIGH


def _fusion_nur_lpi(value, region):
    """Ruft `thunder_level_from_signals()` NUR mit dem LPI-Signal gesetzt auf
    -- Wettercode/Blitzdichte/CAPE bleiben `None`, die Leiter kommt aus der
    Registry (`lpi_thresholds_jkg()`), nicht als hartkodiertes Tupel."""
    lpi_low, lpi_med, lpi_high = lpi_thresholds_jkg(region) or (None, None, None)
    return thunder_level_from_signals(
        wettercode_level=None, lightning_density=None, cape_jkg=None,
        lightning_potential_jkg=value,
        cape_threshold_jkg=None, cape_med_min=None, cape_high_min=None,
        cin_jkg=None,
        lpi_low_min=lpi_low, lpi_med_min=lpi_med, lpi_high_min=lpi_high,
    )


# ────────────── AC-1 — 60 J/kg in EU_REST ergibt MED (heute HIGH) ─────────

def test_ac1_eu_rest_60_jkg_ergibt_med():
    """AC-1: 60 J/kg im Gebiet EU_REST muss ueber die neue Leiter (7,14 /
    23,81 / 86,16) `MED` ergeben.

    HEUTE (RED-Ursache): die alte Interim-Leiter (5/20/50) klassifiziert 60
    als `HIGH` (60 >= 50) -- dieser Test schlaegt fehl, bis die Registry auf
    `(7.14, 23.81, 86.16)` umgestellt ist.
    """
    ergebnis = _fusion_nur_lpi(60.0, "EU_REST")
    assert ergebnis == MED, (
        f"60 J/kg im Gebiet EU_REST muss ueber die neue Leiter MED ergeben, "
        f"erhalten {ergebnis!r}"
    )


# ────────────── AC-2 — 21 J/kg in EU_REST ergibt LOW (heute MED) ──────────

def test_ac2_eu_rest_21_jkg_ergibt_low():
    """AC-2: 21 J/kg im Gebiet EU_REST muss ueber die neue Leiter `LOW`
    ergeben.

    HEUTE (RED-Ursache): die alte Interim-Leiter klassifiziert 21 als `MED`
    (21 >= 20) -- dieser Test schlaegt fehl, bis die neue Mittel-Sprosse
    23,81 gilt.
    """
    ergebnis = _fusion_nur_lpi(21.0, "EU_REST")
    assert ergebnis == LOW, (
        f"21 J/kg im Gebiet EU_REST muss ueber die neue Leiter LOW ergeben, "
        f"erhalten {ergebnis!r}"
    )


# ────────────── AC-3 — 6 J/kg in EU_REST ergibt NONE (heute LOW) ──────────

def test_ac3_eu_rest_6_jkg_ergibt_none():
    """AC-3: 6 J/kg im Gebiet EU_REST muss ueber die neue Leiter `NONE`
    ("kein Gewitter") ergeben -- NICHT verwechseln mit "kein Signal": das
    LPI-Signal ist aktiv geprueft, liegt aber unter der untersten Sprosse
    7,14 (`metric_format._signal_levels()` setzt den Eintrag `blitzpotenzial`
    trotzdem, solange Wert UND alle drei Sprossen `not None` sind).

    HEUTE (RED-Ursache): die alte Interim-Leiter klassifiziert 6 als `LOW`
    (6 >= 5) -- dieser Test schlaegt fehl, bis die neue Nachweisschwelle
    7,14 gilt.
    """
    ergebnis = _fusion_nur_lpi(6.0, "EU_REST")
    assert ergebnis == NONE, (
        f"6 J/kg im Gebiet EU_REST muss ueber die neue Leiter NONE ergeben, "
        f"erhalten {ergebnis!r}"
    )
    # Gegenprobe: das Signal ist trotzdem AKTIV (nicht abwesend) -- es traegt
    # nur die Stufe NONE, weil 6 unter der untersten Sprosse liegt.
    lpi_low, lpi_med, lpi_high = lpi_thresholds_jkg("EU_REST")
    traeger = thunder_signal_carriers(
        wettercode_level=None, lightning_density=None, cape_jkg=None,
        lightning_potential_jkg=6.0,
        cape_threshold_jkg=None, cape_med_min=None, cape_high_min=None,
        cin_jkg=None,
        lpi_low_min=lpi_low, lpi_med_min=lpi_med, lpi_high_min=lpi_high,
    )
    assert traeger == [], (
        "Bei fusionierter Stufe NONE darf KEIN Traeger genannt werden "
        f"(kein Gewitter hat keine Herkunft), erhalten {traeger!r}"
    )


# ────────────── AC-4 — 90 J/kg in EU_REST ergibt HIGH (heute BEREITS gruen)

def test_ac4_eu_rest_90_jkg_ergibt_high():
    """AC-4: 90 J/kg im Gebiet EU_REST muss ueber die neue Leiter `HIGH`
    ergeben -- die oberste Sprosse (86,16) bleibt erreichbar.

    ACHTUNG -- KEIN RED-Nachweis: 90 J/kg ergibt SOWOHL mit der alten
    Interim-Leiter (90 >= 50) ALS AUCH mit der neuen (90 >= 86,16) `HIGH`.
    Dieser Test ist heute bereits gruen und bleibt es nach der
    Implementierung -- er bewacht, dass das Anheben der Hoch-Sprosse die
    Stufe nicht unerreichbar macht (Spec AC-4 / Known Limitations 1).
    """
    ergebnis = _fusion_nur_lpi(90.0, "EU_REST")
    assert ergebnis == HIGH, (
        f"90 J/kg im Gebiet EU_REST muss HIGH ergeben, erhalten {ergebnis!r}"
    )


# ────────────── AC-5 — DE_ALPEN bleibt unberuehrt (heute BEREITS gruen) ───

@pytest.mark.parametrize(
    "wert, erwartet",
    [
        (6.0, LOW),
        (21.0, LOW),
        (60.0, HIGH),
        (90.0, HIGH),
    ],
)
def test_ac5_de_alpen_leiter_bleibt_unveraendert(wert, erwartet):
    """AC-5: dieselben vier Blitzpotenzial-Werte (6/21/60/90 J/kg) ergeben im
    Gebiet DE_ALPEN unverändert LOW/LOW/HIGH/HIGH nach der Leiter 1/30/50 --
    die ICON-D2-Einstufung ist von dieser Arbeit UNBERUEHRT.

    ACHTUNG -- KEIN RED-Nachweis: DE_ALPEN wird von dieser Spec nicht
    veraendert. Regressionswaechter -- schlaegt an, wenn eine kuenftige
    Aenderung versehentlich DE_ALPEN statt EU_REST trifft.
    """
    ergebnis = _fusion_nur_lpi(wert, "DE_ALPEN")
    assert ergebnis == erwartet, (
        f"{wert} J/kg im Gebiet DE_ALPEN muss unveraendert {erwartet.name} "
        f"ergeben, erhalten {ergebnis!r}"
    )


# ────────────── AC-6 — FR traegt kein Blitzpotenzial-Signal (heute BEREITS gruen)

def test_ac6_fr_traegt_kein_blitzpotenzial_signal():
    """AC-6: im Gebiet FR liefert `lpi_thresholds_jkg("FR")` weiterhin `None`
    (FR bewertet Blitzdichte, nicht LPI) -- ein Datenpunkt MIT gesetztem
    Blitzpotenzial traegt deshalb in der Fusion KEIN `blitzpotenzial`-Signal,
    nicht nur der Registry-Rueckgabewert ist `None`.

    ACHTUNG -- KEIN RED-Nachweis: FR ist von dieser Spec nicht betroffen.
    Regressionswaechter gegen den "Alles-oder-nichts"-Verstoss, den die Spec
    unter "Verworfene Alternativen" Punkt 2 ausschliesst.
    """
    region = "FR"
    assert lpi_thresholds_jkg(region) is None, (
        "Vorbedingung: FR darf keine LPI-Leiter haben"
    )
    traeger = thunder_signal_carriers(
        wettercode_level=None, lightning_density=None, cape_jkg=None,
        lightning_potential_jkg=88.2,
        cape_threshold_jkg=None, cape_med_min=None, cape_high_min=None,
        cin_jkg=None,
        lpi_low_min=None, lpi_med_min=None, lpi_high_min=None,
    )
    assert "blitzpotenzial" not in traeger, (
        f"FR darf trotz gesetztem Blitzpotenzial-Wert KEIN "
        f"'blitzpotenzial'-Signal tragen, erhalten {traeger!r}"
    )
