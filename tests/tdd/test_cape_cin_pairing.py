"""TDD RED — Issue #1679 (CIN-Teil).

SPEC: docs/specs/modules/feat_1679_cin_paarung_cape_leiter.md

Testet AC-1 bis AC-8 der CAPE-Leiter (1000/2500/4000 J/kg, NWS/SPC, regions-/
modellskaliert ueber `model_registry.cape_ladder_thresholds_jkg()`), gepaart
mit der Konvektionshemmung CIN (`dp.convective_inhibition_jkg`, #1531).

🔴 Issue #1896 (SPEC: docs/specs/modules/fix_1896_cin_baender_icon.md) stellt die
CIN-Baender auf die ICON-nahe Quelle ECMWF TM 852 um (frueher 25/50/100 plus
Band "CAPE traegt nichts bei"):

    None            -> hoechstens LOW   (Notbremse, UNVERAENDERT)
    Betrag < 50     -> keine Daempfung
    Betrag <= 100   -> genau eine Stufe herunter
    Betrag > 100    -> hoechstens LOW   (Band NONE entfaellt ersatzlos)

Die Tests, die die ALTEN Grenzen festschrieben, sind darauf neu verankert --
am neuen Sollwert, nicht abgeschwaecht. Eichungsunabhaengige Zusicherungen
(Notbremse `None`, Sentinel-Filter -999,9, Vorzeichen-Symmetrie #1760,
"daempft nie nach oben") bleiben unveraendert bestehen.

RED-Ursache (heute):
- `app.model_registry.cape_ladder_thresholds_jkg()` existiert noch nicht ->
  AttributeError bei jedem Zugriff.
- `thunder_level_from_signals()` kennt die drei Keywords
  `cape_med_min`/`cape_high_min`/`cin_jkg` noch nicht -> TypeError bei jedem
  Aufruf MIT diesen Keywords.
- CAPE ist heute pauschal bei LOW gedeckelt (`feat_1474` AC-6) -- jeder Test,
  der eine Eskalation auf MED/HIGH erwartet, kann das strukturell noch nicht
  liefern.

Keine Mocks: reine Funktionsaufrufe, kein Netz.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models import ThunderLevel
from app.thunder_scale import thunder_ordinal
from output.metric_format import thunder_level_from_signals

NONE = ThunderLevel.NONE
LOW = ThunderLevel.LOW
MED = ThunderLevel.MED
HIGH = ThunderLevel.HIGH

# Nominale Leiter fuer isolierte Fusionstests (AC-3 bis AC-6) -- entspricht
# der Referenzleiter aus dem Gesamtkonzept (NWS/SPC), unabhaengig von einer
# konkreten Modell-/Gebiets-Kalibrierung. Reale, skalierte Werte prueft AC-1.
CAPE_LOW, CAPE_MED, CAPE_HIGH = 1000.0, 2500.0, 4000.0


def _call_cape(cape_jkg, cin_jkg):
    """Ruft `thunder_level_from_signals()` NUR mit dem CAPE+CIN-Signal
    gesetzt auf -- alle anderen Signale (Wettercode/Blitzdichte/LPI) `None`."""
    return thunder_level_from_signals(
        wettercode_level=None, lightning_density=None, cape_jkg=cape_jkg,
        lightning_potential_jkg=None,
        cape_threshold_jkg=CAPE_LOW, cape_med_min=CAPE_MED, cape_high_min=CAPE_HIGH,
        cin_jkg=cin_jkg,
        lpi_low_min=None, lpi_med_min=None, lpi_high_min=None,
    )


# ────────────── AC-1 — Leiter proportional zur bestehenden Kalibrierung ───

@pytest.mark.parametrize(
    "model_id, region, erwartet",
    [
        ("icon_d2", "DE_ALPEN", (300.0, 750.0, 1200.0)),
        ("ecmwf_ifs04", "EU_REST", (420.0, 1050.0, 1680.0)),
    ],
)
def test_ac1_cape_ladder_thresholds_jkg_proportional_zur_kalibrierung(
    model_id, region, erwartet,
):
    """AC-1: `cape_ladder_thresholds_jkg()` liefert (low, med, high) im
    selben Verhaeltnis wie die publizierte NWS-Leiter (2500/1000=2.5x,
    4000/1000=4x), verankert an der bereits geeichten LOW-Schwelle
    (`cape_threshold_jkg()`, #1592) -- kein neuer Kalibrierungslauf.

    Gegenprobe (Spec): Wuerde MED/HIGH mit der UNSKALIERTEN NWS-Leiter
    (2500/4000 direkt) statt der regionsskalierten Version berechnet, laege
    das Ergebnis fuer eine Kombination mit `cape_threshold_jkg` != 1000
    (hier 300.0 bzw. 420.0) falsch.
    """
    from app.model_registry import cape_ladder_thresholds_jkg

    ergebnis = cape_ladder_thresholds_jkg(model_id, region)
    assert ergebnis == erwartet, (
        f"cape_ladder_thresholds_jkg({model_id!r}, {region!r}) muss "
        f"{erwartet!r} liefern, erhalten {ergebnis!r}"
    )


def test_ac1_cape_ladder_low_stimmt_mit_cape_threshold_jkg_ueberein():
    """AC-1: die LOW-Schwelle der Leiter ist IDENTISCH zu
    `cape_threshold_jkg()` -- keine zweite, abweichende Kalibrierung."""
    from app.model_registry import cape_ladder_thresholds_jkg, cape_threshold_jkg

    ladder = cape_ladder_thresholds_jkg("icon_d2", "DE_ALPEN")
    basis = cape_threshold_jkg("icon_d2", "DE_ALPEN")
    assert ladder[0] == basis, (
        f"LOW-Schwelle der Leiter ({ladder[0]!r}) muss identisch zur "
        f"bestehenden CAPE-Schwelle ({basis!r}) sein"
    )


# ────────────── AC-2 — unbekannte/fehlende Kombination: kein Signal ───────

@pytest.mark.parametrize(
    "model_id, region",
    [
        (None, "DE_ALPEN"),
        ("icon_d2", None),
        ("icon_d2", "EU_REST"),  # bewusst OHNE Eintrag, s. model_registry.py
    ],
)
def test_ac2_cape_ladder_thresholds_jkg_unbekannte_kombination_liefert_none(
    model_id, region,
):
    """AC-2: fehlendes Modell, fehlende Region oder eine Kombination ohne
    Kalibrierungseintrag liefern alle `None` -- kein geratener Ersatzwert.

    Gegenprobe (Spec): Fiele die Funktion auf die rohe NWS-Leiter
    (1000/2500/4000) zurueck, laege ein Tupel vor, wo `None` erwartet wird.
    """
    from app.model_registry import cape_ladder_thresholds_jkg

    ergebnis = cape_ladder_thresholds_jkg(model_id, region)
    assert ergebnis is None, (
        f"cape_ladder_thresholds_jkg({model_id!r}, {region!r}) muss None "
        f"liefern, erhalten {ergebnis!r}"
    )


# ────────────── AC-3 — schwacher Deckel: CAPE zaehlt voll, erreicht HIGH ──

@pytest.mark.parametrize("cin", [0.0, -10.0, -26.07, -49.9])
def test_ac3_schwacher_deckel_cape_erreicht_med_unveraendert(cin):
    """AC-3 (#1896 AC-1, neu verankert): CIN unterhalb von 50 J/kg daempft
    NICHT -- CAPE im MED-Bereich der vollen Leiter (>= 2500) liefert MED.
    -26,07 ist der real gemessene ICON-D2-Wert vom Karnischen Hoehenweg
    (Kontextdokument Befund 4); er lag bisher im 25er-Band und nahm eine
    Stufe. Die Obergrenze 49,9 ersetzt die alte 24,9.
    """
    ergebnis = _call_cape(2600.0, cin)
    assert ergebnis == MED, (
        f"CAPE 2600 J/kg mit CIN={cin} (unter 50 J/kg, keine Hemmung) muss "
        f"MED liefern, erhalten {ergebnis!r}"
    )


def test_1896_ac1_echter_icon_d2_wert_26_07_laesst_die_cape_leiter_unveraendert():
    """#1896 AC-1: der real gemessene ICON-D2-Wert 26,07 J/kg (Karnischer
    Hoehenweg, 46.40N/12.52O) liefert ueber die FUSION dieselbe Stufe wie ein
    Datenpunkt ganz ohne Hemmung -- er senkt sie nicht mehr um eine Stufe.
    Prueft am Wirkort (`thunder_level_from_signals()`) und vergleicht gegen
    die ungehemmte Leiter statt gegen eine hart notierte Stufe.
    """
    ohne_hemmung = _call_cape(4500.0, 0.0)
    mit_26_07 = _call_cape(4500.0, 26.07)
    assert ohne_hemmung == HIGH, "Vorbedingung: CAPE 4500 J/kg ist HIGH"
    assert mit_26_07 == ohne_hemmung, (
        f"CIN=26,07 J/kg (real gemessen, ICON-D2) muss die CAPE-Stufe "
        f"unveraendert lassen ({ohne_hemmung!r}), erhalten {mit_26_07!r}"
    )


def test_ac3_schwacher_deckel_cape_erreicht_high_kern_regressionsanker():
    """AC-3 (Kern-Regressionsanker dieser Spec): CAPE im HIGH-Bereich der
    vollen Leiter (>= 4000) MIT schwachem CIN liefert HIGH -- der Beweis,
    dass die Eskalation ueber LOW hinaus TATSAECHLICH moeglich ist.

    Gegenprobe (Spec): Bliebe die alte Deckelung (`min(..., LOW)`)
    versehentlich fuer JEDES CIN-Band aktiv, laege das Ergebnis bei LOW
    statt HIGH -- dieser Test ist der wichtigste dieser Spec.
    """
    ergebnis = _call_cape(4500.0, -5.0)
    assert ergebnis == HIGH, (
        f"CAPE 4500 J/kg mit CIN=-5.0 (schwacher Deckel) muss HIGH liefern "
        f"(Beweis der Kernaenderung: CAPE eskaliert jetzt ueber LOW hinaus), "
        f"erhalten {ergebnis!r}"
    )


# ────────────── AC-4 — moderater Deckel: eine Stufe weniger ───────────────

@pytest.mark.parametrize("cin", [-50.0, -75.0, -100.0])
@pytest.mark.parametrize(
    "cape, erwartet", [(4500.0, MED), (2600.0, LOW), (1100.0, NONE)],
    ids=["basis_high", "basis_med", "basis_low"],
)
def test_ac4_moderater_deckel_eine_stufe_weniger_von_high(cin, cape, erwartet):
    """AC-4 (#1896 AC-2, neu verankert): CIN von 50 bis EINSCHLIESSLICH
    100 J/kg nimmt GENAU eine Stufe -- fuer jede Basisstufe der vollen Leiter.
    HIGH wird MED (nicht LOW, wie es die alten Baender taten), MED wird LOW,
    LOW faellt auf NONE.

    Der Grenzwert 100,0 liegt im staerker daempfenden Band ("<= 100"), 50,0
    ist die untere, inklusive Kante.
    """
    ergebnis = _call_cape(cape, cin)
    assert ergebnis == erwartet, (
        f"CAPE {cape} J/kg mit CIN={cin} (Band 50..100) muss {erwartet!r} "
        f"liefern (genau eine Stufe herunter), erhalten {ergebnis!r}"
    )


def test_ac4_moderater_deckel_boden_bei_none_nicht_negativ():
    """AC-4 Bodenfall (#1896 AC-2): CAPE im LOW-Bereich der vollen Leiter mit
    CIN im Band 50..100 liefert NONE (eine Stufe unter LOW), nicht LOW und
    keinen Fehler.

    Gegenprobe (Spec): Wuerde 'eine Stufe weniger' faelschlich als
    'hoechstens LOW' (statt relativ zur Basisstufe) interpretiert, laege
    dieser Fall weiterhin bei LOW statt NONE.
    """
    ergebnis = _call_cape(1000.0, -75.0)
    assert ergebnis == NONE, (
        f"CAPE 1000 J/kg (volle Leiter: LOW) mit CIN=-75.0 muss NONE liefern "
        f"(eine Stufe unter LOW, Boden erreicht), erhalten {ergebnis!r}"
    )


# ────── AC-5 — grosser Deckel + unbekannt: hoechstens LOW (Regression) ────

@pytest.mark.parametrize("cin", [None])
def test_ac5_grosser_deckel_und_unbekannt_hoechstens_low(cin):
    """AC-5 (#1896 AC-5, Notbremse UNVERAENDERT): unbekanntes CIN (`None`)
    daempft CAPE auf hoechstens LOW -- identisch zum Verhalten VOR dieser
    Aenderung (`feat_1474` AC-6). Die frueher hier mitgepruefte Bandreihe
    -50/-75/-99,9 gehoert seit #1896 ins Band "eine Stufe herunter" und wird
    in `test_ac4_moderater_deckel_eine_stufe_weniger_von_high` geprueft --
    die Notbremse selbst ist von der Eichung unberuehrt.

    Gegenprobe (Spec): Laege `cin_jkg=None` versehentlich im Band
    'schwacher Deckel' (z.B. durch ein `or 0`-Muster), wuerde CAPE bei
    unbekannter Hemmung ploetzlich bis HIGH eskalieren -- genau der Fehler,
    den diese Notbremse verhindern soll.
    """
    ergebnis = _call_cape(4500.0, cin)
    assert ergebnis == LOW, (
        f"CAPE 4500 J/kg (volle Leiter: HIGH) mit CIN={cin!r} (grosser "
        f"Deckel/unbekannt) muss LOW liefern, erhalten {ergebnis!r}"
    )


# ────────────── AC-6 — Deckel haelt: kein Beitrag ─────────────────────────

@pytest.mark.parametrize("cin", [-100.1, -104.47, -767.8])
def test_ac6_deckel_haelt_kein_beitrag_unabhaengig_von_cape_hoehe(cin):
    """AC-6 (#1896 AC-3, neu verankert): CIN ueber 100 J/kg deckelt auf
    hoechstens LOW -- das frueher hier gepruefte Band "CAPE traegt gar nichts
    bei" (NONE) entfaellt ersatzlos, weil TM 852 oberhalb von 100 keinen
    weiteren Stuetzpunkt kennt. -104,47 ist der real gemessene ICON-EU-Wert
    aus den Abruzzen (`test_dwd_eu_thunder_energy_signals_fetch.py:17`),
    -767,8 der Bestands-Extremwert dieser Datei. Selbst bei extremem CAPE
    (10000 J/kg) bleibt LOW stehen.
    """
    ergebnis = _call_cape(10000.0, cin)
    assert ergebnis == LOW, (
        f"CAPE 10000 J/kg (extrem) mit CIN={cin} (ueber 100 J/kg) muss LOW "
        f"liefern (nicht NONE -- das Band entfaellt), erhalten {ergebnis!r}"
    )


def test_ac6_grenzwert_minus_100_liegt_noch_im_grossen_deckel_nicht_haelt():
    """AC-6 Grenzfall (#1896 AC-2/AC-3): CIN=-100.0 EXAKT gehoert ins
    staerker daempfende der beiden angrenzenden Baender -- also noch in
    "eine Stufe herunter" (`<= 100`), NICHT in "hoechstens LOW" (`> 100`).
    Aus Basis HIGH wird damit MED.
    """
    ergebnis = _call_cape(4500.0, -100.0)
    assert ergebnis == MED, (
        f"CIN=-100.0 (exakt) muss noch 'eine Stufe herunter' bedeuten (MED "
        f"aus HIGH), nicht den Deckel LOW -- erhalten {ergebnis!r}"
    )


# ────── AC-7 — FR bleibt verhaltensgleich (CIN strukturell None) ──────────

def test_ac7_fr_gebiet_verhaltensgleich_weil_cin_strukturell_fehlt():
    """AC-7: ein Datenpunkt im FR-Gebiet (Météo-France/AROME liefert kein
    `cin_ml`, `convective_inhibition_jkg` bleibt strukturell `None`) mit
    CAPE ueber der FR-Schwelle liefert LOW ueber den Produktionspfad
    (`_fuse_thunder_levels()`) -- identisch zum Verhalten vor dieser
    Aenderung.

    Gegenprobe (Spec): Bekaeme FR versehentlich einen CIN-Fallback-Wert
    ungleich `None` (z.B. 0, was im Band 'schwacher Deckel' laege), wuerde
    CAPE dort ploetzlich bis HIGH eskalieren -- ein Verhalten, das nirgends
    belegt ist (Météo-France liefert dort keine Hemmungsgroesse).
    """
    from app.model_registry import cape_ladder_thresholds_jkg
    from app.models import ForecastDataPoint
    from providers.thunder_enrichment import _fuse_thunder_levels

    cape_ladder = cape_ladder_thresholds_jkg("meteofrance_arome", "FR")
    assert cape_ladder is not None, "Vorbedingung: FR muss kalibriert sein"

    ts = datetime.now(timezone.utc)
    dp = ForecastDataPoint(
        ts=ts, thunder_level=None, cape_jkg=cape_ladder[2] + 100.0,
        convective_inhibition_jkg=None,
    )

    _fuse_thunder_levels([dp], cape_ladder, None)

    assert dp.thunder_level == LOW, (
        f"FR-Datenpunkt mit CAPE weit ueber der HIGH-Schwelle und "
        f"strukturell fehlendem CIN muss LOW liefern (unveraendertes "
        f"Verhalten), erhalten {dp.thunder_level!r}"
    )


# ────────────── AC-8 — TypeError ohne `cin_jkg` (kein stiller Rueckfall) ──

def test_ac8_thunder_level_from_signals_ohne_cin_parameter_bricht_mit_typeerror():
    """AC-8: ein Aufruf von `thunder_level_from_signals()` mit dem HEUTIGEN
    Parametersatz (ohne `cin_jkg`, und bewusst OHNE `cape_med_min`/
    `cape_high_min` -- deren Pflicht-Status ist laut Spec eine offene
    Implementierungsfrage, s. Known Limitations) MUSS nach dieser Aenderung
    mit `TypeError` brechen, weil `cin_jkg` mindestens keyword-only OHNE
    Default ist -- exakt das `cape_threshold_jkg`/`lpi_low_min`-Muster seit
    #1592 C1/#1679-LPI.

    HEUTE (RED-Ursache): dieser Aufruf entspricht exakt der AKTUELLEN
    Signatur und funktioniert klaglos -- `pytest.raises` schlaegt heute mit
    "DID NOT RAISE" fehl. Ein Aufruf, der stattdessen bereits die (noch
    nicht existierenden) `cape_med_min`/`cape_high_min` mitgeben wuerde,
    waere HEUTE schon aus einem falschen Grund rot (unbekanntes Keyword)
    und damit kein sauberer RED-Test fuer `cin_jkg` allein.

    Gegenprobe (Spec): Bekaeme `cin_jkg` einen Default `= None`, wuerde der
    Aufruf klaglos durchlaufen und automatisch ins 'unbekannt'-Band fallen,
    statt den Aufrufer zu zwingen, die Hemmung ausdruecklich zu nennen.
    """
    with pytest.raises(TypeError):
        thunder_level_from_signals(
            wettercode_level=None, lightning_density=None, cape_jkg=4500.0,
            lightning_potential_jkg=None,
            cape_threshold_jkg=CAPE_LOW,
            lpi_low_min=None, lpi_med_min=None, lpi_high_min=None,
        )


# ===========================================================================
# Issue #1760 -- CIN-Daempfung feuert nie: der DWD liefert `cin_ml` als
# POSITIVEN Betrag, `_gedaempft_durch_cin()` erwartete bisher ausschliesslich
# negative Werte (`cin_jkg > -25` ist fuer jeden positiven Wert wahr).
# SPEC: docs/specs/modules/fix_1760_cin_vorzeichen.md
#
# Reale, gemessene DWD-Werte (`cin_ml`, ICON-D2/ICON-EU, 2026-08-11) --
# NICHT erfunden, sondern aus den belegten Fixture-Aufzeichnungen:
#   - 7.29 J/kg  -- test_dwd_thunder_new_signals_fetch.py:31 (ICON-D2, KHW)
#   - 104.47 J/kg -- test_dwd_eu_thunder_energy_signals_fetch.py:17 (ICON-EU)
#   - 767.8 J/kg  -- NICHT als Fixture-Wert auffindbar (weder in den beiden
#     genannten Dateien noch sonst im Repo). Wird trotzdem verwendet, weil
#     die Spec ihn ausdruecklich als "real gemessen" nennt und die
#     Entwickler-Vorgabe verbietet, eigene Zahlen zu erfinden -- s. Bericht.
# ===========================================================================


# ────────────── #1760 AC-1/AC-5 -- positiver CIN daempft die FUSIONIERTE
# Stufe (Produktivpfad `thunder_level_from_signals()`, nicht isoliert) ─────

@pytest.mark.parametrize(
    "cin_positiv, erwartet",
    [
        # 7.29 J/kg (ICON-D2, KHW): Betrag < 50 -- keine Hemmung, CAPE voll.
        (7.29, HIGH),
        # 26.07 J/kg (ICON-D2, KHW, Positivkontrolle #1896 Befund 4): seit
        # #1896 ebenfalls unter 50 -- keine Daempfung mehr (vorher eine Stufe).
        (26.07, HIGH),
        # 104.47 J/kg (ICON-EU, Abruzzen): Betrag > 100 -- Deckel auf LOW.
        # Bis #1896 lag dieser Wert im inzwischen entfallenen NONE-Band.
        (104.47, LOW),
        # 767.8 J/kg: Betrag weit ueber 100 -- ebenfalls Deckel LOW.
        (767.8, LOW),
    ],
)
def test_1760_ac1_ac5_positiver_cin_daempft_fusionierte_stufe_echte_dwd_werte(
    cin_positiv, erwartet,
):
    """#1760 AC-1 + AC-5: reale, POSITIV gemessene DWD-Werte (`cin_ml`)
    durchlaufen den Produktivpfad `thunder_level_from_signals()` -- NICHT
    isoliert `_gedaempft_durch_cin()` -- mit CAPE oberhalb der HIGH-Sprosse
    (4500 J/kg, volle Leiter: HIGH).

    RED vor dem Fix: `_gedaempft_durch_cin()` prueft `cin_jkg > -25`, was
    fuer JEDEN positiven Wert wahr ist -- alle drei Faelle liefern HEUTE
    HIGH statt des erwarteten, gedaempften Ergebnisses.
    """
    ergebnis = _call_cape(4500.0, cin_positiv)
    assert ergebnis == erwartet, (
        f"CAPE 4500 J/kg mit real gemessenem, POSITIVEM CIN={cin_positiv} "
        f"muss {erwartet!r} liefern (Betragsvergleich), erhalten {ergebnis!r} "
        f"-- vor dem Fix wurde jeder positive Wert wie 'kein Deckel' "
        f"behandelt"
    )


# ────────────── #1760 AC-2 -- Bestandsverhalten (negativ) unveraendert ────
#
# Bewusst KEIN neuer Test hier: AC-2 verlangt, dass die bestehenden
# Parametrisierungen mit negativem CIN (Zeilen 128, 160, 191, 212, 231 vor
# dieser Ergaenzung) UNVERAENDERT gruen bleiben. Sie werden hier nicht
# angefasst -- der Beweis ist ein unveraenderter Testlauf derselben Datei.


# ────────────── #1760 AC-3 -- Sentinel -999.9 erreicht die Daempfung NIE ──

def test_1760_ac3_gefilterter_sentinel_faellt_ueber_fuse_auf_hoechstens_low():
    """#1760 AC-3: der DWD-Fehlwert -999.9 ("kein Ausloesepunkt gefunden")
    wird bereits VOR dieser Funktion gefiltert (`dwd.py:240`/`dwd_eu.py:261`,
    Konstante `dwd.py:206`) und erreicht die Fusion als `None`. Dieser Test
    prueft das am Produktionspfad `_fuse_thunder_levels()` (DE_ALPEN/ICON-D2,
    NICHT das FR-Pendant aus AC-7 oben) -- ein `None`-CIN muss auf
    "hoechstens LOW" fallen: NIEMALS auf den staerksten Deckel (NONE waere
    hier bereits ein AC-6-Verstoss, da CAPE weit ueber HIGH liegt) und
    NIEMALS auf 'kein Deckel' (HIGH waere die Buggy-Interpretation, falls
    ein `abs()` VOR dem Filter angewendet wuerde und -999.9 zu +999.9 wird).

    Gegenprobe (Mutation): Wird der Sentinel-Filter in `dwd.py`/`dwd_eu.py`
    entfernt und ein rohes -999.9 erreicht `convective_inhibition_jkg`
    unveraendert, liefert `_gedaempft_durch_cin()` (Betrag 999.9 > 100)
    zwar IMMER NOCH den staerksten Deckel -- das ist der Fund, den die
    Mutations-Gegenprobe im Bericht dokumentiert, s. dort. (Seit #1896 ist
    dieser staerkste Deckel LOW statt NONE; der Fund bleibt derselbe, den
    Filter selbst prueft `test_1760_f001_...` weiter unten.)
    """
    from app.model_registry import cape_ladder_thresholds_jkg
    from app.models import ForecastDataPoint
    from providers.thunder_enrichment import _fuse_thunder_levels

    cape_ladder = cape_ladder_thresholds_jkg("icon_d2", "DE_ALPEN")
    assert cape_ladder is not None, "Vorbedingung: DE_ALPEN muss kalibriert sein"

    ts = datetime.now(timezone.utc)
    dp = ForecastDataPoint(
        ts=ts, thunder_level=None, cape_jkg=cape_ladder[2] + 500.0,
        convective_inhibition_jkg=None,  # simuliert den bereits gefilterten Sentinel
    )

    _fuse_thunder_levels([dp], cape_ladder, None)

    assert dp.thunder_level == LOW, (
        f"DE_ALPEN-Datenpunkt mit CAPE weit ueber HIGH und gefiltertem "
        f"Sentinel (CIN=None) muss LOW liefern (Notbremse 'hoechstens "
        f"LOW'), erhalten {dp.thunder_level!r}"
    )


# ────────────── #1760 AC-3 -- Adversary F001: der Sentinel-FILTER selbst ──
#
# Der obige Test setzt `convective_inhibition_jkg=None` VORAUS -- er prueft
# die Daempfung, nicht ob der Filter (`dwd.py:206`/`:240`, `dwd_eu.py:261`)
# aus dem rohen -999,9 ueberhaupt `None` macht. Die bisher einzigen Tests,
# die das tun (`test_ac2_..." in test_dwd_thunder_new_signals_fetch.py,
# `test_f001_..." in test_dwd_eu_thunder_energy_signals_fetch.py) tragen
# `pytestmark = pytest.mark.live` auf MODUL-Ebene (identisches Vorbild in
# ~15 weiteren Tests derselben zwei Dateien, CI-Vermessung #1196) und laufen
# damit NICHT im Standardlauf (`pyproject.toml:65`). Ein Entfernen des
# Markers nur an diesen zwei Funktionen ist nicht moeglich, ohne den Marker
# fuer ALLE anderen Tests derselben Datei ebenfalls anzufassen (Modul-Ebene)
# -- diese sind bewusst als 'live' eingestuft, unabhaengig vom eigentlichen
# Netzbedarf. Deshalb hier ein eigener, kleiner Kern-Test statt Entmarkierung
# (Bericht: Wahl (b) statt (a)).

_DWD_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dwd"


@pytest.mark.parametrize(
    "modul_pfad, fixture_name, marker_ort, echt_ort",
    [
        # Koordinaten identisch zu den bestehenden live-Tests uebernommen
        # (nicht neu geraten) -- dort bereits als Sentinel- bzw. Echtwert-
        # Gitterpunkt der jeweiligen, echten Aufzeichnung nachgewiesen.
        (
            "providers.dwd",
            "icon_d2_alpen_cin_ml_2026081103_012.grib2.bz2",
            (53.90, 1.22), (46.40, 12.52),
        ),
        (
            "providers.dwd_eu",
            "icon_eu_abruzzen_cin_ml_2026081100_000.grib2.bz2",
            (70.5, -19.8125), (41.8125, 13.3750),
        ),
    ],
    ids=["icon_d2_dwd_py_240", "icon_eu_dwd_eu_py_261"],
)
def test_1760_f001_dwd_sentinel_filter_faengt_minus_999_9_am_realen_gitterpunkt(
    modul_pfad, fixture_name, marker_ort, echt_ort,
):
    """#1760 Adversary F001: der DWD-Sentinel-Filter fuer `cin_ml`
    (Konstante `CIN_ML_LOWER_SENTINEL`, `dwd.py:206`; Filterzeilen
    `dwd.py:240` und `dwd_eu.py:261`) direkt am Produktionsfilter
    `_read_point_value()` geprueft -- kein Netz, kein lokaler Server, nur
    die bereits eingecheckte, echte Aufzeichnung.

    Mutations-Gegenprobe (Pflicht laut Auftrag, s. Bericht):
    1. `CIN_ML_LOWER_SENTINEL` in `dwd.py:206` auf -9999.9 aendern -> rot.
    2. Filterzeile `dwd.py:240` entfernen -> rot (nimmt wegen des
       gemeinsamen Imports `dwd_eu.py:70` auch den ICON-EU-Fall mit).
    """
    import importlib

    modul = importlib.import_module(modul_pfad)
    compressed = (_DWD_FIXTURES / fixture_name).read_bytes()

    marker_lat, marker_lon = marker_ort
    echt_lat, echt_lon = echt_ort
    marker_ergebnis = modul._read_point_value(
        compressed, marker_lat, marker_lon, param="cin_ml",
    )
    echt_ergebnis = modul._read_point_value(
        compressed, echt_lat, echt_lon, param="cin_ml",
    )

    assert marker_ergebnis is None, (
        f"{modul_pfad}._read_point_value: Sentinel-Gitterpunkt {marker_ort} "
        f"liefert {marker_ergebnis!r} statt None -- der -999,9-Filter greift "
        f"nicht (Fehlwert wuerde als echter, extremer Deckel durchgereicht)"
    )
    assert echt_ergebnis is not None and echt_ergebnis > 1, (
        f"{modul_pfad}._read_point_value: echter Gitterpunkt {echt_ort} "
        f"liefert {echt_ergebnis!r} -- ohne diesen Vergleichswert waere der "
        f"Test auch fuer einen Filter gruen, der PAUSCHAL alles auf None "
        f"setzt statt nur den Sentinel"
    )


# ────────────── #1760 AC-4 -- Vorzeichen-Herkunft am Code belegt ──────────

def test_1760_ac4_docstring_belegt_modellabhaengiges_vorzeichen():
    """#1760 AC-4: die Docstring von `_gedaempft_durch_cin()` muss die
    Vorzeichenfrage BELEGEN (nicht nur behaupten) -- ICON-Quellstelle, GRIB2
    ohne Vorzeichenkonvention, US-Herkunft der Baender. Verhaltensnachweis
    ueber Wortpruefung ist hier per Definition angemessen (Docstring IST der
    Nachweisort von AC-4), daher explizit erlaubt via Marker.

    # doc-compliance-test
    """
    import inspect

    from output.metric_format import _gedaempft_durch_cin

    doc = inspect.getdoc(_gedaempft_durch_cin) or ""
    for beleg in (
        "mo_opt_nwp_diagnostics.f90",  # ICON-Quellcode-Stelle
        "GRIB2",  # Standard ohne Vorzeichenkonvention
        "GFS",  # Gegenbeispiel: negatives Vorzeichen
    ):
        assert beleg in doc, (
            f"Docstring von _gedaempft_durch_cin() muss '{beleg}' als Beleg "
            f"fuer die Vorzeichenfrage enthalten (#1760 AC-4), fehlt aktuell"
        )


# ────────────── #1760 AC-6 -- Daempfung senkt AUSSCHLIESSLICH, hebt nie ───

@pytest.mark.parametrize("cin_betrag", [7.29, 104.47, 767.8])
def test_1760_ac6_positiv_und_negativ_liefern_identisches_ergebnis(cin_betrag):
    """#1760 AC-6: derselbe Betrag mit positivem und negativem Vorzeichen
    liefert IDENTISCHE Ergebnisse -- die Daempfung haengt nur vom Betrag ab,
    nicht vom Vorzeichen. Vor dem Fix war das positive Ergebnis IMMER
    `basis` (HIGH) unabhaengig vom Betrag -- fuer 104.47/767.8 waere die
    Symmetrie damit heute verletzt (RED-Beleg identisch zu AC-1 oben).
    """
    positiv = _call_cape(4500.0, cin_betrag)
    negativ = _call_cape(4500.0, -cin_betrag)
    assert positiv == negativ, (
        f"CIN={cin_betrag} und CIN={-cin_betrag} muessen identisch daempfen "
        f"(nur der Betrag zaehlt), erhalten positiv={positiv!r} vs. "
        f"negativ={negativ!r}"
    )


@pytest.mark.parametrize("cin_positiv", [7.29, 104.47, 767.8, 30.0, 60.0])
def test_1760_ac6_daempfung_hebt_die_stufe_nie_ueber_die_basis(cin_positiv):
    """#1760 AC-6: fuer JEDEN positiven CIN-Wert bleibt das gedaempfte
    Ergebnis auf oder unter der ungedaempften Basisstufe (HIGH, volle
    Leiter fuer CAPE=4500) -- die Daempfung dämpft ausschliesslich, sie
    hebt nie an."""
    ergebnis = _call_cape(4500.0, cin_positiv)
    assert thunder_ordinal(ergebnis) <= thunder_ordinal(HIGH), (
        f"CIN={cin_positiv} (positiv) darf die Stufe NIE ueber HIGH heben, "
        f"erhalten {ergebnis!r}"
    )


# ===========================================================================
# Issue #1896 -- CIN-Baender auf die ICON-nahe Quelle ECMWF TM 852 umgestellt
# (Groenemeijer, Pucik, Tsonevsky, Bechtold 2019, Figure 2). Das Band "CAPE
# traegt gar nichts bei" (NONE) entfaellt ersatzlos.
# SPEC: docs/specs/modules/fix_1896_cin_baender_icon.md
#
# AC-1/AC-2/AC-3/AC-5 sind oben an den bestehenden Bandtests neu verankert.
# Hier stehen die ACs, fuer die es keinen Bestandstest gab.
# ===========================================================================

# CAPE-Werte der nominalen Leiter (1000/2500/4000) je Basisstufe -- die Basis
# wird NICHT behauptet, sondern im Test gegen den ungehemmten Lauf geprueft.
_CAPE_JE_BASIS = {NONE: 500.0, LOW: 1100.0, MED: 2600.0, HIGH: 4500.0}


@pytest.mark.parametrize("cin", [101.0, 200.0, 1000.0, 10000.0])
@pytest.mark.parametrize("basis", [HIGH, MED])
def test_1896_ac4_beliebig_grosses_cin_setzt_das_cape_signal_nie_auf_none(
    basis, cin,
):
    """#1896 AC-4 (zugespitzt nach Adversary-Befund F001): die Hemmung
    schaltet das CAPE-Signal nicht mehr basis-unabhaengig ab -- bei Basis HIGH
    und MED bleibt fuer JEDEN Betrag ueber 100 J/kg mindestens LOW stehen.

    Basis LOW ist bewusst NICHT hier: sie darf um ihre eine Stufe auf NONE
    sinken (normale Ein-Stufen-Daempfung aus AC-2), s. den Test darunter.
    Geprueft am Wirkort (Fusion `thunder_level_from_signals()`).
    """
    ergebnis = _call_cape(_CAPE_JE_BASIS[basis], cin)
    assert thunder_ordinal(ergebnis) >= thunder_ordinal(LOW), (
        f"Basis {basis!r} mit CIN={cin} darf nie unter LOW fallen -- das Band "
        f"'CAPE traegt nichts bei' existiert seit #1896 nicht mehr, erhalten "
        f"{ergebnis!r}"
    )


@pytest.mark.parametrize("cin", [101.0, 200.0, 1000.0, 10000.0])
def test_1896_ac4_basis_low_faellt_ueber_100_auf_denselben_wert_wie_darunter(cin):
    """#1896 AC-4/AC-9: eine Basis LOW ergibt oberhalb von 100 J/kg NONE --
    und zwar DENSELBEN Wert wie im Band darunter (50..100). Ein reiner Deckel
    auf LOW wuerde sie hier wieder anheben; genau diese Naht ist der
    Adversary-Befund F001.
    """
    darunter = _call_cape(_CAPE_JE_BASIS[LOW], 75.0)
    ergebnis = _call_cape(_CAPE_JE_BASIS[LOW], cin)
    assert darunter == NONE, "Vorbedingung: Basis LOW faellt im Band 50..100 auf NONE"
    assert ergebnis == darunter, (
        f"Basis LOW mit CIN={cin} (ueber 100) muss {darunter!r} liefern -- "
        f"denselben Wert wie im Band darunter, nicht mehr; erhalten "
        f"{ergebnis!r}"
    )


@pytest.mark.parametrize("basis", [NONE, LOW, MED, HIGH])
def test_1896_ac9_mehr_hemmung_ergibt_nie_mehr_gewitter_ueber_die_bandnaehte(
    basis,
):
    """#1896 AC-9 (Adversary-Befund F001): ueber eine aufsteigende Wertereihe,
    die die Bandnaehte ausdruecklich einschliesst, faellt das Ergebnis monoton
    -- ein groesserer CIN-Betrag liefert NIE eine hoehere Stufe als ein
    kleinerer.

    RED-Ursache: das oberste Band war ein ABSOLUTER Deckel auf LOW, das
    mittlere rechnet RELATIV zur Basis. An der 100er-Naht ueberholen sie sich:
    Basis LOW faellt bei 100,0 auf NONE, wird bei 100,1 aber wieder auf LOW
    angehoben -- mehr Hemmung ergaebe mehr Gewitter.

    Geprueft am Wirkort (Fusion `thunder_level_from_signals()`).
    """
    reihe = [49.9, 50.0, 99.9, 100.0, 100.1, 200.0, 10000.0]
    cape = _CAPE_JE_BASIS[basis]
    stufen = [_call_cape(cape, cin) for cin in reihe]
    for (cin_klein, stufe_klein), (cin_gross, stufe_gross) in zip(
        zip(reihe, stufen), zip(reihe[1:], stufen[1:]),
    ):
        assert thunder_ordinal(stufe_gross) <= thunder_ordinal(stufe_klein), (
            f"Basis {basis!r}: CIN={cin_gross} liefert {stufe_gross!r}, aber "
            f"das kleinere CIN={cin_klein} nur {stufe_klein!r} -- mehr Hemmung "
            f"darf nie mehr Gewitter ergeben (ganze Reihe: "
            f"{list(zip(reihe, stufen))!r})"
        )


@pytest.mark.parametrize(
    "cin", [None, 0.0, 10.0, 49.9, 50.0, 100.0, 100.1, 500.0, 10000.0],
)
@pytest.mark.parametrize("basis", [NONE, LOW, MED, HIGH])
def test_1896_ac6_daempfung_liefert_nie_mehr_als_die_ungehemmte_basis(
    basis, cin,
):
    """#1896 AC-6: ueber alle vier Basisstufen und die ganze Wertereihe
    (inklusive `None`) gilt Ergebnis <= Basis -- die Hemmung daempft
    ausschliesslich und hebt nie an (Rasmussen & Blanchard 1998,
    Gesamtkonzept 3.7); eichungsunabhaengig. Die Basis stammt aus DEMSELBEN
    Fusionsaufruf ohne Hemmung, nicht aus einer hart notierten Stufe.
    """
    cape = _CAPE_JE_BASIS[basis]
    ungehemmt = _call_cape(cape, 0.0)
    ergebnis = _call_cape(cape, cin)
    assert thunder_ordinal(ergebnis) <= thunder_ordinal(ungehemmt), (
        f"CAPE {cape} J/kg (ungehemmt {ungehemmt!r}) mit CIN={cin!r} liefert "
        f"{ergebnis!r} -- die Hemmung darf die Stufe NIE anheben"
    )


@pytest.mark.parametrize(
    "betrag, erwartet",
    [(10.0, HIGH), (49.0, HIGH), (50.0, MED), (100.0, MED), (150.0, LOW)],
)
def test_1896_ac8_gleicher_betrag_mit_beiden_vorzeichen_daempft_identisch(
    betrag, erwartet,
):
    """#1896 AC-8: derselbe Betrag positiv (ICON-Konvention) und negativ
    (US-Modelle) liefert dasselbe Ergebnis -- die Betragslogik aus #1760
    bleibt wirksam. Zusaetzlich wird das ERGEBNIS am neuen Band festgemacht:
    ein Test, der nur `positiv == negativ` prueft, waere auch mit den alten
    Baendern gruen und bewiese fuer #1896 nichts.
    """
    positiv = _call_cape(4500.0, betrag)
    negativ = _call_cape(4500.0, -betrag)
    assert positiv == negativ == erwartet, (
        f"CIN=+{betrag} und CIN=-{betrag} muessen beide {erwartet!r} liefern "
        f"(Basis HIGH, TM-852-Baender), erhalten positiv={positiv!r}, "
        f"negativ={negativ!r}"
    )


def test_1896_ac7_icon_d2_und_icon_eu_teilen_eine_cin_baenderleiter():
    """#1896 AC-7: derselbe CIN-Betrag fuehrt bei ICON-D2 und ICON-EU zur
    GLEICHEN Daempfung -- beide teilen denselben ICON-Code und damit dieselbe
    CIN-Definition (Spec, Abgrenzung zu ADR-0048).

    Gemessen am Produktionspfad `_fuse_thunder_levels()` mit den echten,
    getrennt kalibrierten CAPE-Leitern beider Modelle -- kein Netz, kein
    Mock. Der Provider-Unterschied (`dwd.py`/`dwd_eu.py`) endet fachlich beim
    Rohwert `cin_ml`: beide liefern denselben positiven Betrag in dasselbe
    Feld (`convective_inhibition_jkg`), und die Baender wirken erst dahinter
    -- ein HTTP-Abruf wuerde hier nur die Providerschicht doppelt testen.
    Geprueft wird nicht nur Gleichheit (die waere auch mit den alten Baendern
    erfuellt), sondern die neue Sollstufe LOW fuer 104,47 J/kg.
    """
    from app.model_registry import cape_ladder_thresholds_jkg
    from app.models import ForecastDataPoint
    from providers.thunder_enrichment import _fuse_thunder_levels

    ts = datetime.now(timezone.utc)
    ergebnisse = {}
    for model_id in ("icon_d2", "icon_eu"):
        ladder = cape_ladder_thresholds_jkg(model_id, "DE_ALPEN")
        assert ladder is not None, f"Vorbedingung: {model_id}/DE_ALPEN kalibriert"
        dp = ForecastDataPoint(
            ts=ts, thunder_level=None, cape_jkg=ladder[2] + 500.0,
            convective_inhibition_jkg=104.47,
        )
        _fuse_thunder_levels([dp], ladder, None)
        ergebnisse[model_id] = dp.thunder_level

    assert ergebnisse["icon_d2"] == ergebnisse["icon_eu"] == LOW, (
        f"CIN=104,47 J/kg (real gemessen, ICON-EU/Abruzzen) muss bei BEIDEN "
        f"ICON-Modellen dieselbe Stufe LOW ergeben (eine Baenderleiter), "
        f"erhalten {ergebnisse!r}"
    )
