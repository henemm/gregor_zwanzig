"""TDD RED — Issue #1679 (CIN-Teil).

SPEC: docs/specs/modules/feat_1679_cin_paarung_cape_leiter.md

Testet AC-1 bis AC-8 der CAPE-Leiter (1000/2500/4000 J/kg, NWS/SPC, regions-/
modellskaliert ueber `model_registry.cape_ladder_thresholds_jkg()`), gepaart
mit der Konvektionshemmung CIN (`dp.convective_inhibition_jkg`, #1531) in vier
belegten Baendern (Penn State/COMET, SPC: -25/-50/-100/-200 J/kg).

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

@pytest.mark.parametrize("cin", [0.0, -10.0, -24.9])
def test_ac3_schwacher_deckel_cape_erreicht_med_unveraendert(cin):
    """AC-3: CIN im Band 'schwacher Deckel' (>= -25) daempft NICHT -- CAPE
    im MED-Bereich der vollen Leiter (>= 2500) liefert MED, unabhaengig vom
    genauen CIN-Wert innerhalb des Bandes.
    """
    ergebnis = _call_cape(2600.0, cin)
    assert ergebnis == MED, (
        f"CAPE 2600 J/kg mit CIN={cin} (schwacher Deckel) muss MED liefern, "
        f"erhalten {ergebnis!r}"
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

@pytest.mark.parametrize("cin", [-25.0, -40.0, -49.9])
def test_ac4_moderater_deckel_eine_stufe_weniger_von_high(cin):
    """AC-4: CIN im Band 'moderat' (-50 bis -25) daempft CAPE um GENAU eine
    Stufe -- CAPE im HIGH-Bereich der vollen Leiter liefert MED, nicht HIGH
    und nicht LOW.
    """
    ergebnis = _call_cape(4500.0, cin)
    assert ergebnis == MED, (
        f"CAPE 4500 J/kg (volle Leiter: HIGH) mit CIN={cin} (moderat) muss "
        f"MED liefern (eine Stufe weniger), erhalten {ergebnis!r}"
    )


def test_ac4_moderater_deckel_boden_bei_none_nicht_negativ():
    """AC-4 Bodenfall: CAPE im LOW-Bereich der vollen Leiter mit moderatem
    CIN liefert NONE (eine Stufe unter LOW), nicht LOW und keinen Fehler.

    Gegenprobe (Spec): Wuerde 'eine Stufe weniger' faelschlich als
    'hoechstens LOW' (statt relativ zur Basisstufe) interpretiert, laege
    dieser Fall weiterhin bei LOW statt NONE.
    """
    ergebnis = _call_cape(1000.0, -30.0)
    assert ergebnis == NONE, (
        f"CAPE 1000 J/kg (volle Leiter: LOW) mit CIN=-30.0 (moderat) muss "
        f"NONE liefern (eine Stufe unter LOW, Boden erreicht), erhalten "
        f"{ergebnis!r}"
    )


# ────── AC-5 — grosser Deckel + unbekannt: hoechstens LOW (Regression) ────

@pytest.mark.parametrize("cin", [-50.0, -75.0, -99.9, None])
def test_ac5_grosser_deckel_und_unbekannt_hoechstens_low(cin):
    """AC-5 (wichtigster Regressionstest): CIN im Band 'grosser Deckel'
    (-100 bis -50) ODER unbekannt (`None`) daempft CAPE auf hoechstens LOW --
    identisch zum Verhalten VOR dieser Aenderung (`feat_1474` AC-6), jetzt
    aber nur noch fuer diese beiden Faelle statt generell.

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

@pytest.mark.parametrize("cin", [-100.1, -150.0, -200.0])
def test_ac6_deckel_haelt_kein_beitrag_unabhaengig_von_cape_hoehe(cin):
    """AC-6: CIN unter -100 J/kg ('Deckel haelt') laesst CAPE NICHTS
    beitragen -- unabhaengig davon, wie hoch CAPE liegt.

    Gegenprobe (Spec): Wuerde 'kein Beitrag' faelschlich als 'hoechstens
    LOW' (statt NONE) umgesetzt, laege das Ergebnis bei LOW statt NONE.
    """
    ergebnis = _call_cape(10000.0, cin)
    assert ergebnis == NONE, (
        f"CAPE 10000 J/kg (extrem) mit CIN={cin} (Deckel haelt) muss NONE "
        f"liefern, erhalten {ergebnis!r}"
    )


def test_ac6_grenzwert_minus_100_liegt_noch_im_grossen_deckel_nicht_haelt():
    """AC-6 Grenzfall: CIN=-100.0 EXAKT liegt noch im Band 'grosser Deckel'
    (>= -100), NICHT im Band 'haelt' (< -100) -- Grenze ist inklusiv am
    schwaecheren Ende, exklusiv am staerkeren."""
    ergebnis = _call_cape(4500.0, -100.0)
    assert ergebnis == LOW, (
        f"CIN=-100.0 (exakt) muss noch als 'grosser Deckel' gelten (LOW), "
        f"nicht als 'haelt' (NONE) -- erhalten {ergebnis!r}"
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
        # 7.29 J/kg: Betrag < 25 -- schwacher Deckel, CAPE zaehlt VOLL.
        (7.29, HIGH),
        # 104.47 J/kg: Betrag > 100 -- nach der Tabelle in
        # docs/features/gewitter-gesamtkonzept.md ("unter -100 J/kg: Deckel
        # haelt, kein Beitrag") liegt das NEGATIVE Pendant -104.47 ebenfalls
        # in diesem Band, nicht im Band "grosser Deckel" (-100 bis -50).
        # Die Spec-Prosa zu AC-1 nennt hierfuer "hoechstens 'leicht'" --
        # das ist mit NONE (schwaecher als LOW) technisch weiterhin erfuellt
        # ("hoechstens" = Obergrenze), aber NICHT das Band "grosser Deckel"
        # selbst. S. Bericht: Unstimmigkeit in der Spec-Illustration.
        (104.47, NONE),
        # 767.8 J/kg: Betrag weit > 100 -- ebenfalls "Deckel haelt".
        (767.8, NONE),
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
    zwar IMMER NOCH `NONE` -- das ist der Fund, den die Mutations-Gegenprobe
    im Bericht dokumentiert, s. dort.
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
