"""Issue #1474c (letzter Restpunkt zu Epic #1419), AC-2.

SPEC: docs/specs/modules/feat_1474c_blitzpotenzial_stufen.md

DRY-Pflicht (#1481): Blitzdichte UND Blitzpotenzial muessen ihre
Drei-Schwellen-Uebersetzung ueber DIESELBE geteilte Funktion
`(wert, low_min, med_min, high_min) -> ThunderLevel` laufen lassen -- keine
zweite, kopierte if/elif-Kette in `thunder_level_from_signals()`.

Nachweisform: Laufzeit-Sentinel (Muster
test_hail_flag_channel_rendering.py::test_ac7_..._rufen_denselben_helfer):
die geteilte Leiter wird zur Laufzeit auf einen Sentinel umgebogen -- BEIDE
Signalwege muessen ihn zeigen. Eine kopierte Kette wuerde ihn an mindestens
einer Stelle NICHT zeigen. Ersetzt den frueheren AST-Quelltext-Test, den der
Hygiene-Waechter (test_765_no_product_source_read) zu Recht blockiert:
Programmtext-Lektuere ist kein Verhaltensnachweis (Test-Politik, CLAUDE.md).
Kein Netz, kein Mock-Theater -- der Sentinel ersetzt nur die Leiter, nie die
geprueften Fusions-Pfade selbst.
"""
from __future__ import annotations


# ─────────────── AC-2 — genau EINE geteilte Leiter-Funktion ───────────────

def test_ac2_beide_signale_laufen_durch_dieselbe_leiter(monkeypatch):
    """AC-2 DRY-Nachweis: GIVEN die geteilte Leiter ist auf einen Sentinel
    umgebogen, der jeden Aufruf samt Schwellen aufzeichnet und stets HIGH
    liefert / WHEN `thunder_level_from_signals()` einmal nur mit Blitzdichte
    und einmal nur mit Blitzpotenzial laeuft (Werte UNTER jeder echten
    Schwelle, sodass eine kopierte if/elif-Kette NONE liefern wuerde) / THEN
    liefern BEIDE Pfade das Sentinel-HIGH, und die zwei aufgezeichneten
    Aufrufe tragen jeweils die EIGENEN vier Schwellenwerte des Signals.
    """
    from output import metric_format as mf

    aufrufe: list[tuple] = []

    def _sentinel_leiter(value, low_min, med_min, high_min):
        aufrufe.append((value, low_min, med_min, high_min))
        return mf.ThunderLevel.HIGH

    monkeypatch.setattr(mf, "_thunder_level_from_ladder", _sentinel_leiter)

    dichte = mf.thunder_level_from_signals(
        wettercode_level=None, lightning_density=0.0, cape_jkg=None,
    )
    potenzial = mf.thunder_level_from_signals(
        wettercode_level=None, lightning_density=None, cape_jkg=None,
        lightning_potential_jkg=0.0,
    )

    assert dichte == mf.ThunderLevel.HIGH, (
        "Blitzdichte-Pfad zeigt den Sentinel nicht -- "
        "thunder_level_from_signals() uebersetzt die Blitzdichte nicht "
        f"ueber die geteilte Leiter-Funktion (erhalten: {dichte!r})"
    )
    assert potenzial == mf.ThunderLevel.HIGH, (
        "Blitzpotenzial-Pfad zeigt den Sentinel nicht -- entweder haelt "
        "thunder_level_from_signals() eine eigene, kopierte if/elif-Kette "
        "(#1481 DRY-Verstoss) oder kennt lightning_potential_jkg nicht "
        f"(erhalten: {potenzial!r})"
    )
    assert len(aufrufe) == 2, (
        f"Erwartet genau zwei Leiter-Aufrufe (Dichte + Potenzial), "
        f"aufgezeichnet: {aufrufe!r}"
    )
    assert aufrufe[0][1:] == (
        mf._LIGHTNING_LOW_MIN, mf._LIGHTNING_MED_MIN, mf._LIGHTNING_HIGH_MIN,
    ), (
        "Der Blitzdichte-Aufruf traegt nicht die Blitzdichte-Schwellen -- "
        f"jedes Signal muss SEINE vier Schwellen mitbringen: {aufrufe[0]!r}"
    )
    assert aufrufe[1][1:] == (
        mf._LIGHTNING_POTENTIAL_LOW_MIN, mf._LIGHTNING_POTENTIAL_MED_MIN,
        mf._LIGHTNING_POTENTIAL_HIGH_MIN,
    ), (
        "Der Blitzpotenzial-Aufruf traegt nicht die Potenzial-Schwellen -- "
        f"jedes Signal muss SEINE vier Schwellen mitbringen: {aufrufe[1]!r}"
    )


# ─────── Verhaltens-Beleg: gleicher Vergleichsoperator (>=) fuer beide ─────

def test_ac2_beide_signale_liefern_an_der_unteren_schwelle_uebereinstimmend_low():
    """AC-2 Verhaltens-Beleg: Blitzdichte UND Blitzpotenzial liefern an
    ihrer jeweils UNTEREN Schwelle (Wert exakt gleich `low_min`)
    uebereinstimmend LOW -- Beweis, dass beide ueber denselben
    Vergleichsoperator (`>=`) laufen, nicht nur ueber zwei gleich benannte,
    aber unabhaengig implementierte Ketten."""
    from output import metric_format as mf

    blitzdichte_low = mf.thunder_level_from_signals(
        wettercode_level=None, lightning_density=mf._LIGHTNING_LOW_MIN,
        cape_jkg=None,
    )
    blitzpotenzial_low = mf.thunder_level_from_signals(
        wettercode_level=None, lightning_density=None, cape_jkg=None,
        lightning_potential_jkg=mf._LIGHTNING_POTENTIAL_LOW_MIN,
    )

    assert blitzdichte_low == mf.ThunderLevel.LOW, (
        "Blitzdichte an ihrer unteren Schwelle muss LOW liefern "
        f"(Regressions-Bestandsverhalten), erhalten {blitzdichte_low!r}"
    )
    assert blitzpotenzial_low == blitzdichte_low, (
        f"Blitzpotenzial an SEINER unteren Schwelle "
        f"({mf._LIGHTNING_POTENTIAL_LOW_MIN} J/kg) liefert "
        f"{blitzpotenzial_low!r} statt {blitzdichte_low!r} -- beide Signale "
        "muessen an der jeweils unteren Schwelle uebereinstimmend LOW "
        "liefern, wenn sie ueber denselben Vergleichsoperator (>=) laufen"
    )
