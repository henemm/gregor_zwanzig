"""TDD RED — Issue #1474c (letzter Restpunkt zu Epic #1419), AC-1, AC-3.

SPEC: docs/specs/modules/feat_1474c_blitzpotenzial_stufen.md

`thunder_level_from_signals()` bekommt einen VIERTEN Parameter
`lightning_potential_jkg` (DWD-Blitzpotenzial, J/kg) mit einer EIGENEN
Schwellentabelle (5 / 20 / 50 J/kg) -- eine andere Groesse auf einer anderen
Skala als die Blitzdichte (#1419 Abs. 3.1, ADR-0025).

RED-Ursache (heute): `thunder_level_from_signals()` kennt den Parameter
`lightning_potential_jkg` noch nicht -> jeder Aufruf mit diesem Keyword
wirft TypeError ("unexpected keyword argument").

Keine Mocks: reine Funktionsaufrufe, kein Netz.
"""
from __future__ import annotations

import pytest

from app.models import ThunderLevel

NONE = ThunderLevel.NONE
LOW = ThunderLevel.LOW
MED = ThunderLevel.MED
HIGH = ThunderLevel.HIGH


def _fusion(**kwargs):
    from app.model_registry import lpi_thresholds_jkg
    from output.metric_format import thunder_level_from_signals
    # Issue #1592 C1: `cape_threshold_jkg` ist keyword-only ohne Default.
    # `cape_jkg=None` hier -- die Schwelle spielt fuer diese Tests (nur
    # Blitzpotenzial) keine Rolle.
    # Issue #1679: die LPI-Leiter kommt jetzt gebietsabhaengig aus der
    # Tabelle. EU_REST traegt die bis dahin globale 5/20/50-Leiter
    # unveraendert weiter -- damit ist diese Datei der AC-3-Regressionsanker:
    # dieselben Pruefwerte, dieselben Erwartungen, nur die Herkunft der
    # Schwellen hat sich geaendert.
    lpi_low, lpi_med, lpi_high = lpi_thresholds_jkg("EU_REST")
    kwargs.setdefault("lpi_low_min", lpi_low)
    kwargs.setdefault("lpi_med_min", lpi_med)
    kwargs.setdefault("lpi_high_min", lpi_high)
    # Issue #1679 (CIN-Teil): CAPE-Leiter und `cin_jkg` sind keyword-only ohne
    # Default. `None` hier -- diese Datei prueft ausschliesslich das
    # Blitzpotenzial, CAPE soll (wie bisher) kein Signal beitragen.
    return thunder_level_from_signals(
        wettercode_level=None, lightning_density=None, cape_jkg=None,
        cape_threshold_jkg=None, cape_med_min=None, cape_high_min=None,
        cin_jkg=None, **kwargs
    )


# ────────────── AC-1 — Blitzpotenzial-Dreiteilung nach PO-Tabelle ─────────

@pytest.mark.parametrize(
    "wert, erwartet",
    [
        (4.9, NONE),
        (5.0, LOW),
        (19.9, LOW),
        (20.0, MED),
        (49.9, MED),
        (50.0, HIGH),
        # PO-Messwerte 2026-08-02 (Spec Abschnitt AC-1):
        (88.2, HIGH),  # GR20 / Refuge de Petra Piana -- reales Gewitter
        (0.9, NONE),   # Zillertal, ruhiges Wetter
    ],
)
def test_ac1_blitzpotenzial_dreiteilung_nach_po_tabelle(wert, erwartet):
    """AC-1: NUR das Blitzpotenzial-Signal gesetzt (Wettercode, Blitzdichte,
    CAPE alle None) -- die Schwellen 5/20/50 J/kg entscheiden allein.

    Gegenprobe (Spec): liest die Implementierung faelschlich die
    Blitzdichte-Schwellen (0,003/0,015/0,075) statt der eigenen
    Blitzpotenzial-Schwellen, liefert bereits 4,9 J/kg faelschlich HIGH
    (weit ueber 0,075) -- dieser Test faengt das, weil 4,9 hier NONE
    erwartet.
    """
    ergebnis = _fusion(lightning_potential_jkg=wert)
    erwartet_name = erwartet.name if erwartet is not None else None
    assert ergebnis == erwartet, (
        f"Blitzpotenzial {wert} J/kg muss {erwartet_name} liefern "
        f"(Schwellen 5/20/50), erhalten {ergebnis!r}"
    )


# ────────────── AC-3 — None != NONE fuer das vierte Signal ────────────────

def test_ac3_kein_signal_liefert_none_aktiv_geprueft_liefert_thunderlevel_none():
    """AC-3: `lightning_potential_jkg=None` (kein Signal) UND alle anderen
    Signale None -> die Fusion liefert None (keine Aussage).
    `lightning_potential_jkg=0.0` (aktiv geprueft, unter 5) bei sonst None
    -> die Fusion liefert ThunderLevel.NONE (geprueft, unauffaellig) -- die
    beiden Faelle unterscheiden sich.

    Gegenprobe (Spec): behandelt die Implementierung None und 0.0 beim
    vierten Signal gleich (z.B. weil intern ein Default 0.0 statt None
    verwendet wird), liefern beide Aufrufe ThunderLevel.NONE -- dieser Test
    faengt das ueber den letzten `assert`.
    """
    kein_signal = _fusion(lightning_potential_jkg=None)
    aktiv_und_unauffaellig = _fusion(lightning_potential_jkg=0.0)

    assert kein_signal is None, (
        f"Alle vier Signale None (keine Aussage) muss None liefern, "
        f"erhalten {kein_signal!r}"
    )
    assert aktiv_und_unauffaellig == NONE, (
        f"lightning_potential_jkg=0.0 (aktiv geprueft, unter 5 J/kg) muss "
        f"ThunderLevel.NONE liefern, erhalten {aktiv_und_unauffaellig!r}"
    )
    assert kein_signal != aktiv_und_unauffaellig, (
        "'kein Signal' (None) und 'aktiv geprueft, unauffaellig' (NONE) "
        "muessen sich unterscheiden -- sonst ist die Fusion blind fuer "
        "'keine Aussage' beim vierten Signal"
    )
