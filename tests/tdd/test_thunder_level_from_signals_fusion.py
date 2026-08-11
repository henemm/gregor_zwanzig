"""TDD RED — Issue #1474 (S3 zu #1419), AC-5 .. AC-8.

SPEC: docs/specs/modules/feat_1474_gewitter_befund_stufen.md v2.3 Abschnitt 3

Neue reine Funktion `thunder_level_from_signals(wettercode_level,
lightning_density, cape_jkg) -> Optional[ThunderLevel]` in
`output/metric_format.py`. Jedes Signal wird EIGENSTAENDIG uebersetzt, die
Fusion nimmt das schaerfste vorhandene Signal ("None" ist kein Signal).

AC-5: Blitzdichte-Dreiteilung (Schwellen 0,003 / 0,015 / 0,075).
AC-6: CAPE gedeckelt bei "leicht" -- eskaliert NIE, auch nicht bei 2630 J/kg.
AC-7: "keine Aussage" != "keine Gefahr" in der Fusion.
AC-8: schaerfstes vorhandenes Signal gewinnt.

RED-Ursache (heute): `thunder_level_from_signals` existiert nicht ->
ImportError bei JEDEM Test dieser Datei (er ist der erste Aufruf in `_fusion()`,
noch vor jeder Assertion). `ThunderLevel.LOW` existiert ebenfalls nicht, wird
hier aber bewusst NICHT auf Modulebene abgefragt (das wuerde die Collection
der ganzen Datei/Suite mit einer AttributeError abbrechen) -- stattdessen
`getattr(ThunderLevel, "LOW", None)`: die Aufloesung passiert bei jedem
frischen pytest-Lauf neu; sobald die Stufe existiert, liefert `getattr` den
echten Enum-Wert statt des `None`-Platzhalters, ohne dass diese Datei
angefasst werden muss.

Keine Mocks: reine Funktionsaufrufe, kein Netz.
"""
from __future__ import annotations

import pytest

from app.models import ThunderLevel

NONE, MED, HIGH = ThunderLevel.NONE, ThunderLevel.MED, ThunderLevel.HIGH
LOW = getattr(ThunderLevel, "LOW", None)


def _fusion(*args, **kwargs):
    from output.metric_format import thunder_level_from_signals

    # Issue #1679: die drei LPI-Schwellen sind keyword-only ohne Default.
    # `None` hier -- diese Testfamilie prueft ausschliesslich
    # Blitzdichte/CAPE/"keine Aussage", das Blitzpotenzial soll dabei kein
    # Signal beitragen.
    for schluessel in ("lpi_low_min", "lpi_med_min", "lpi_high_min"):
        kwargs.setdefault(schluessel, None)
    # Issue #1679 (CIN-Teil): CAPE laeuft ueber eine dreisprossige Leiter,
    # `cin_jkg` ist ebenso keyword-only ohne Default. Die beiden oberen
    # Sprossen entsprechen der rohen NWS-Leiter zur unveraenderten
    # Katalog-Schwelle 1000 unten; `cin_jkg=None` (unbekannte Hemmung) haelt
    # die AC-6-Deckelung auf LOW aufrecht, unter der diese Testfamilie
    # geschrieben wurde.
    for schluessel, wert in (
        ("cape_med_min", 2500.0), ("cape_high_min", 4000.0), ("cin_jkg", None),
    ):
        kwargs.setdefault(schluessel, wert)
    return thunder_level_from_signals(*args, **kwargs)


# ─────────────────────────── AC-5 — Blitzdichte ──────────────────────────

@pytest.mark.parametrize(
    "lightning_density, expected",
    [
        (0.0, NONE),
        (0.004, LOW),
        (0.02, MED),
        # GR20 Refuge de Petra Piana, 2026-08-02 Nachmittag, von vier
        # unabhaengigen Quellen bestaetigtes Gewitter (Spec Abschnitt 3):
        # der reale Messwert 0,1-0,2 landet in "schwer".
        (0.15, HIGH),
    ],
)
def test_ac5_blitzdichte_dreiteilung(lightning_density, expected):
    # Issue #1592 C1: `cape_threshold_jkg` ist keyword-only ohne Default.
    # `cape_jkg=None` hier -- die Schwelle spielt fuer das Ergebnis keine
    # Rolle, `None` ist der mechanische Wert "keine Herkunft im Spiel".
    result = _fusion(
        wettercode_level=None, lightning_density=lightning_density, cape_jkg=None,
        cape_threshold_jkg=None,
    )
    assert result == expected, (
        f"Blitzdichte {lightning_density} muss {expected.name} liefern, "
        f"erhalten {result!r}"
    )


# ─────────────────────────────── AC-6 — CAPE ──────────────────────────────

# Issue #1592 C1: `thunder_level_from_signals()` bewertet CAPE nicht mehr
# gegen die feste Katalog-1000, sondern gegen eine explizit uebergebene,
# geeichte Schwelle. Diese Bestandstests kennen keine Modell-Herkunft --
# um ihre (unveraenderten) Erwartungswerte 500->NONE / 1200->LOW / 2630->LOW
# zu erhalten, wird hier weiterhin die alte, alleinstehend belegte Katalog-
# Schwelle explizit uebergeben, statt sich auf einen Default zu verlassen.
#
# Issue #1679 (CIN-Teil): "CAPE eskaliert nie ueber LOW" gilt seitdem NICHT
# mehr unbedingt, sondern nur bei grosser oder unbekannter Konvektionshemmung.
# Diese Testfamilie laeuft ueber `_fusion()` mit `cin_jkg=None` und prueft
# damit genau diesen (unveraenderten) Fall -- die Eskalation bei schwacher
# Hemmung prueft `test_cape_cin_pairing.py`.
_ALTE_KATALOG_SCHWELLE_JKG = 1000.0


@pytest.mark.parametrize(
    "cape_jkg, expected",
    [
        (500.0, NONE),
        (1200.0, LOW),
        # Realer Messwert eines bestaetigten Gewitters (GR20, 2026-08-02):
        # CAPE 2630 J/kg bleibt trotzdem bei LOW gedeckelt.
        (2630.0, LOW),
    ],
)
def test_ac6_cape_gedeckelt_bei_leicht(cape_jkg, expected):
    result = _fusion(
        wettercode_level=None, lightning_density=None, cape_jkg=cape_jkg,
        cape_threshold_jkg=_ALTE_KATALOG_SCHWELLE_JKG,
    )
    assert result == expected, (
        f"CAPE {cape_jkg} J/kg muss {expected.name} liefern (NIE hoeher, auch "
        f"nicht bei hohem CAPE), erhalten {result!r}"
    )


def test_ac6_gegenprobe_hohes_cape_eskaliert_nicht_auf_med_oder_high():
    """AC-6 Gegenprobe: der reale Hochwert 2630 J/kg darf NICHT MED/HIGH
    liefern -- selbst wenn die Implementierung faelschlich
    risk_thresholds['cape']['high']=2000 als Eskalationsschwelle liest."""
    result = _fusion(
        wettercode_level=None, lightning_density=None, cape_jkg=2630.0,
        cape_threshold_jkg=_ALTE_KATALOG_SCHWELLE_JKG,
    )
    assert result not in (MED, HIGH), (
        f"CAPE allein darf nie ueber 'leicht' hinaus ausloesen, erhalten {result!r}"
    )


# ──────────────────────── AC-7 — keine Aussage != keine Gefahr ────────────

def test_ac7_alle_drei_signale_none_liefert_none():
    result = _fusion(
        wettercode_level=None, lightning_density=None, cape_jkg=None,
        cape_threshold_jkg=None,
    )
    assert result is None, (
        f"Sind ALLE drei Signale None (keine Aussage), muss die Fusion None "
        f"liefern, erhalten {result!r}"
    )


def test_ac7_ein_geprueftes_unauffaelliges_signal_liefert_none_level():
    """Mindestens ein Signal ist aktiv geprueft und unauffaellig (Wettercode
    NONE), die anderen beiden None -> die Fusion liefert ThunderLevel.NONE
    (geprueft, unauffaellig), NICHT die Python-None 'keine Aussage'."""
    result = _fusion(
        wettercode_level=NONE, lightning_density=None, cape_jkg=None,
        cape_threshold_jkg=None,
    )
    assert result == NONE, (
        f"Ein geprueftes, unauffaelliges Signal muss ThunderLevel.NONE liefern "
        f"(nicht die Python-None 'keine Aussage'), erhalten {result!r}"
    )


def test_ac7_gegenprobe_die_beiden_faelle_unterscheiden_sich():
    """AC-7 Gegenprobe: vertauscht die Implementierung 'kein Signal' und
    'ein unauffaelliges Signal', muessen sich die beiden Rueckgaben
    unterscheiden -- sonst ist die Fusion blind fuer 'keine Aussage'."""
    kein_signal = _fusion(
        wettercode_level=None, lightning_density=None, cape_jkg=None,
        cape_threshold_jkg=None,
    )
    ein_unauffaelliges_signal = _fusion(
        wettercode_level=NONE, lightning_density=None, cape_jkg=None,
        cape_threshold_jkg=None,
    )
    assert kein_signal is not ein_unauffaelliges_signal or kein_signal != ein_unauffaelliges_signal, (
        "'kein Signal' (None) und 'ein unauffaelliges Signal' (NONE) muessen "
        "sich unterscheiden koennen"
    )
    assert kein_signal is None
    assert ein_unauffaelliges_signal == NONE


# ────────────────────── AC-8 — schaerfstes Signal gewinnt ─────────────────

def test_ac8_zwei_vorhandene_signale_schaerferes_gewinnt():
    """Wettercode NONE, Blitzdichte 0,02 (MED), CAPE None -> MED gewinnt."""
    result = _fusion(
        wettercode_level=NONE, lightning_density=0.02, cape_jkg=None,
        cape_threshold_jkg=None,
    )
    assert result == MED, (
        f"Das schaerfere der zwei vorhandenen Signale (MED) muss gewinnen, "
        f"erhalten {result!r}"
    )


def test_ac8_wettercode_gewinnt_gegen_schwaechere_blitzdichte():
    """Wettercode HIGH, Blitzdichte 0,004 (LOW) -> HIGH gewinnt, weil schaerfer."""
    result = _fusion(
        wettercode_level=HIGH, lightning_density=0.004, cape_jkg=None,
        cape_threshold_jkg=None,
    )
    assert result == HIGH, (
        f"Wettercode HIGH muss gegen die schwaechere Blitzdichte LOW gewinnen, "
        f"erhalten {result!r}"
    )
