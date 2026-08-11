"""TDD RED — Issue #1679 (LPI-Teil).

SPEC: docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md

Testet AC-1, AC-2, AC-4, AC-5, AC-6 der neuen Region-Tabelle fuer die
LPI-Blitzpotenzial-Schwellen (`app.model_registry.LPI_THRESHOLDS_JKG` /
`lpi_thresholds_jkg()`, drei neue keyword-only Parameter an
`thunder_level_from_signals()`, dritter Pflichtparameter an
`_fuse_thunder_levels()`) -- Vorbild-Muster `CAPE_THRESHOLDS_JKG` (#1592).

AC-3 (EU_REST-Regression) wird laut Spec NICHT hier als eigener Test
umgesetzt, sondern durch Umwidmung von
`tests/tdd/test_thunder_potential_level_classification.py` (GREEN-Arbeit).
Dieser Datei liegt nur ein Marker-Test bei, der zeigt, dass der dafuer
noetige Lookup heute noch nicht existiert.

RED-Ursache (heute):
- `app.model_registry.LPI_THRESHOLDS_JKG`/`lpi_thresholds_jkg()` existieren
  noch nicht -> ImportError/AttributeError bei jedem Zugriff.
- `thunder_level_from_signals()` kennt die drei Keywords
  `lpi_low_min`/`lpi_med_min`/`lpi_high_min` noch nicht -> TypeError bei
  jedem Aufruf MIT diesen Keywords; ein Aufruf OHNE sie funktioniert heute
  noch klaglos (kein TypeError) -- die AC-5-Tests dazu sind bewusst
  umgekehrt formuliert (`pytest.raises` schlaegt fehl, weil KEIN TypeError
  geworfen wird).
- `_fuse_thunder_levels()` kennt den dritten Parameter `lpi_thresholds`
  noch nicht -> ein Aufruf mit nur zwei Argumenten funktioniert heute noch
  klaglos, der AC-5-Test dazu ist ebenso umgekehrt formuliert.

Keine Mocks: reine Funktionsaufrufe, kein Netz.
"""
from __future__ import annotations

import pytest

from app.models import ThunderLevel
from output.metric_format import thunder_level_from_signals

NONE = ThunderLevel.NONE
LOW = ThunderLevel.LOW
MED = ThunderLevel.MED
HIGH = ThunderLevel.HIGH


def _call(value, *, lpi_low_min, lpi_med_min, lpi_high_min):
    """Ruft `thunder_level_from_signals()` NUR mit dem LPI-Signal gesetzt
    auf -- alle anderen Signale (Wettercode/Blitzdichte/CAPE) `None`."""
    return thunder_level_from_signals(
        wettercode_level=None, lightning_density=None, cape_jkg=None,
        lightning_potential_jkg=value,
        cape_threshold_jkg=None,
        lpi_low_min=lpi_low_min, lpi_med_min=lpi_med_min, lpi_high_min=lpi_high_min,
    )


# ────────────── AC-1 — Tabelle hat genau zwei Eintraege, FR ausgespart ────

def test_ac1_lpi_thresholds_table_has_exactly_two_entries():
    """AC-1: `LPI_THRESHOLDS_JKG` traegt GENAU DE_ALPEN und EU_REST mit den
    belegten Werten, FR bekommt bewusst keinen Eintrag (AROME liefert
    Blitzdichte, kein LPI).

    Gegenprobe (Spec): Bekaeme FR versehentlich einen Eintrag (Copy-Paste
    aus `CAPE_THRESHOLDS_JKG`, wo FR sehr wohl Eintraege hat), laege die
    Tabellenlaenge bei 3 statt 2 -- dieser Test faengt das ueber die
    Laengenpruefung.
    """
    from app.model_registry import LPI_THRESHOLDS_JKG

    assert len(LPI_THRESHOLDS_JKG) == 2, (
        f"Erwartet genau 2 Eintraege (DE_ALPEN, EU_REST), "
        f"gefunden {len(LPI_THRESHOLDS_JKG)}: {sorted(LPI_THRESHOLDS_JKG)}"
    )
    assert LPI_THRESHOLDS_JKG.get("DE_ALPEN") == (1.0, 30.0, 50.0)
    assert LPI_THRESHOLDS_JKG.get("EU_REST") == (5.0, 20.0, 50.0)
    assert "FR" not in LPI_THRESHOLDS_JKG, (
        "FR darf KEINEN Eintrag haben -- AROME liefert Blitzdichte, kein LPI"
    )


@pytest.mark.parametrize(
    "region, erwartet",
    [
        ("DE_ALPEN", (1.0, 30.0, 50.0)),
        ("EU_REST", (5.0, 20.0, 50.0)),
        ("FR", None),
        (None, None),
    ],
)
def test_ac1_lpi_thresholds_jkg_lookup_alle_vier_eingaben(region, erwartet):
    """AC-1: Lookup fuer alle drei Regionsnamen aus `thunder_routing._REGIONS`
    plus `None` liefert die belegten Werte bzw. `None` (FR/unbekannt).

    Gegenprobe (Spec): Bekaeme FR versehentlich einen Eintrag, laege
    `lpi_thresholds_jkg("FR")` bei einem Tupel statt `None`.
    """
    from app.model_registry import lpi_thresholds_jkg

    ergebnis = lpi_thresholds_jkg(region)
    assert ergebnis == erwartet, (
        f"lpi_thresholds_jkg({region!r}) muss {erwartet!r} liefern, "
        f"erhalten {ergebnis!r}"
    )


# ────────────── AC-2 — DE_ALPEN: LPI zwischen 1 und 30 J/kg liefert LOW ───

@pytest.mark.parametrize(
    "wert, erwartet",
    [
        (1.0, LOW),
        (2.0, LOW),
        (29.9, LOW),
        (30.0, MED),
    ],
)
def test_ac2_de_alpen_lpi_werte_liefern_low_low_low_med(wert, erwartet):
    """AC-2: mit den DE_ALPEN-Schwellen (1.0/30.0/50.0) liefert 2.0 J/kg
    LOW -- mit der alten globalen 5er-Schwelle waere das NONE gewesen.
    """
    ergebnis = _call(wert, lpi_low_min=1.0, lpi_med_min=30.0, lpi_high_min=50.0)
    assert ergebnis == erwartet, (
        f"LPI {wert} J/kg mit DE_ALPEN-Schwellen (1.0/30.0/50.0) muss "
        f"{erwartet.name} liefern, erhalten {ergebnis!r}"
    )


def test_ac2_vergleich_mit_alten_schwellen_bei_2_0_jkg_liefert_none():
    """AC-2 Gegenprobe: derselbe Wert 2.0 J/kg liefert mit den ALTEN
    globalen Schwellen (5.0/20.0/50.0) NONE -- Beweis, dass der Unterschied
    zu `test_ac2_de_alpen_lpi_werte_liefern_low_low_low_med` real ist,
    nicht nur ein anderer Rueckgabewert derselben Schwelle.

    Gegenprobe (Spec): Bliebe `enrich_thunder()`/`_fuse_thunder_levels()`
    faelschlich bei der alten globalen Schwelle, laege 2.0 unter 5.0 und
    die Fusion bei NONE statt LOW -- der Vergleich der beiden Tests deckt
    genau das auf.
    """
    ergebnis = _call(2.0, lpi_low_min=5.0, lpi_med_min=20.0, lpi_high_min=50.0)
    assert ergebnis == NONE, (
        f"LPI 2.0 J/kg mit den ALTEN Schwellen (5.0/20.0/50.0) muss NONE "
        f"liefern, erhalten {ergebnis!r}"
    )


# ────────────── AC-3 (Marker) — EU_REST-Lookup existiert heute noch nicht ─

def test_ac3_marker_lpi_thresholds_jkg_eu_rest_existiert_heute_noch_nicht():
    """AC-3 wird NICHT hier als vollstaendiger Regressionstest umgesetzt --
    das ist die Umwidmung von
    `tests/tdd/test_thunder_potential_level_classification.py` auf
    `model_registry.lpi_thresholds_jkg("EU_REST")` (GREEN-Arbeit, s. Spec
    Implementation Details "Scope-Korrektur"). Dieser Marker-Test zeigt,
    dass der Lookup, auf den jene Umwidmung angewiesen ist, HEUTE noch
    nicht existiert (AttributeError) -- und praeft nach der Implementierung
    zugleich den EU_REST-Wert, damit der Test nicht assertion-los bleibt.

    HEUTE (RED-Ursache): `model_registry.lpi_thresholds_jkg` existiert noch
    nicht -> `AttributeError`, bevor die `assert`-Zeile ueberhaupt erreicht
    wird.
    """
    import app.model_registry as model_registry

    ergebnis = model_registry.lpi_thresholds_jkg("EU_REST")
    assert ergebnis == (5.0, 20.0, 50.0)


# ────────────── AC-4 — unbekannte/fehlende Region: kein Signal, kein Fallback

@pytest.mark.parametrize("region", ["XX", None])
def test_ac4_lpi_thresholds_jkg_unbekannte_oder_fehlende_region_liefert_none(region):
    """AC-4: `lpi_thresholds_jkg(None)` (fehlende Region) UND
    `lpi_thresholds_jkg("XX")` (unbekannte Region) liefern beide `None`.
    """
    from app.model_registry import lpi_thresholds_jkg

    assert lpi_thresholds_jkg(region) is None


def test_ac4_fusion_ohne_aufgeloeste_schwelle_liefert_none_nicht_high():
    """AC-4: Fusionsaufruf mit den drei Schwellen `None` (Region unbekannt)
    bei einem hohen LPI-Wert (88.2 J/kg) liefert `None` (keine Aussage),
    NICHT `ThunderLevel.HIGH`.

    Gegenprobe (Spec): Fiele die Implementierung bei fehlender Region auf
    einen Default-Wert zurueck (z.B. die alten globalen 5/20/50 als
    "Sicherheitsnetz"), laege 88.2 weit ueber 50 und die Fusion lieferte
    faelschlich HIGH statt None -- dieser Test faengt das. Genau das ist
    der Fehler, den das keyword-only-ohne-Default-Muster strukturell
    verhindern soll.
    """
    ergebnis = _call(88.2, lpi_low_min=None, lpi_med_min=None, lpi_high_min=None)
    assert ergebnis is None, (
        f"Ohne aufgeloeste LPI-Schwellen (Region unbekannt) darf KEIN "
        f"Signal entstehen, erhalten {ergebnis!r}"
    )


# ────────────── AC-5 — TypeError ohne die neuen Parameter (ganze Kette) ───

def test_ac5_thunder_level_from_signals_ohne_lpi_parameter_bricht_mit_typeerror():
    """AC-5: ein Aufruf von `thunder_level_from_signals()` OHNE die drei
    keyword-only Parameter `lpi_low_min`/`lpi_med_min`/`lpi_high_min` MUSS
    mit `TypeError` brechen -- exakt das `cape_threshold_jkg`-Muster seit
    #1592 C1.

    HEUTE (RED-Ursache, umgekehrt formuliert): dieser Aufruf funktioniert
    bereits klaglos (die drei Parameter existieren noch gar nicht), es
    entsteht also KEIN TypeError -- `pytest.raises` schlaegt deshalb heute
    mit "DID NOT RAISE" fehl. Erst wenn die Parameter keyword-only OHNE
    Default eingefuehrt sind, wirft dieser Aufruf tatsaechlich TypeError
    und der Test wird gruen.

    Gegenprobe (Spec): Bekaemen die drei Parameter versehentlich einen
    Default `= None`, wuerde der Aufruf weiterhin klaglos durchlaufen --
    der Test bleibt dann dauerhaft rot statt nach der Implementierung
    gruen zu werden.
    """
    with pytest.raises(TypeError):
        thunder_level_from_signals(
            wettercode_level=None, lightning_density=None, cape_jkg=None,
            lightning_potential_jkg=5.0,
            cape_threshold_jkg=None,
        )


def test_ac5_fuse_thunder_levels_ohne_lpi_thresholds_parameter_bricht_mit_typeerror():
    """AC-5: ein Aufruf von `_fuse_thunder_levels()` ohne den dritten
    Parameter `lpi_thresholds` MUSS mit `TypeError` brechen -- die Pflicht
    gilt auf der GANZEN Kette (Aufrufer-Grenze UND interner
    Durchreichungspunkt), nicht nur an der oeffentlichen Fusionsfunktion.

    HEUTE (RED-Ursache, umgekehrt formuliert): `_fuse_thunder_levels()` hat
    aktuell genau zwei Parameter (`data`, `cape_threshold_jkg`) -- ein
    Aufruf mit zwei Argumenten funktioniert also bereits klaglos, KEIN
    TypeError. `pytest.raises` schlaegt deshalb heute mit "DID NOT RAISE"
    fehl.
    """
    from providers.thunder_enrichment import _fuse_thunder_levels

    with pytest.raises(TypeError):
        _fuse_thunder_levels([], None)


# ────────────── AC-6 — FR-Gebiet bleibt vom LPI-Ladder-Umbau unberuehrt ───

def test_ac6_lpi_thresholds_jkg_fr_liefert_none():
    """AC-6 (Wiederholung aus AC-1, hier im Kontext des FR-Pfads
    dokumentiert): `lpi_thresholds_jkg("FR")` liefert `None` -- FR bekommt
    KEINEN Tabelleneintrag, AROME liefert dort Blitzdichte, kein LPI.
    """
    from app.model_registry import lpi_thresholds_jkg

    assert lpi_thresholds_jkg("FR") is None


# ────────────── F001 — Gebiets-Aufloesung END-ZU-ENDE aus Koordinaten ─────

@pytest.mark.parametrize(
    "name, lat, lon, erwartete_region, erwartete_leiter",
    [
        ("Mayrhofen/Zillertal", 47.16, 11.87, "DE_ALPEN", (1.0, 30.0, 50.0)),
        ("Abisko/Nordschweden", 68.35, 18.83, "EU_REST", (5.0, 20.0, 50.0)),
    ],
)
def test_f001_schwellen_fuer_reihe_loest_gebiet_aus_echten_koordinaten_auf(
    name, lat, lon, erwartete_region, erwartete_leiter,
):
    """Schliesst Adversary-Finding F001 (#1679): prueft die Gebiets-Aufloesung
    in `_schwellen_fuer_reihe()` END-ZU-ENDE aus echten Koordinaten, statt die
    Leiter -- wie die AC-2/AC-3-Tests -- von Hand vorzugeben.

    Warum noetig: die bisherigen Produktionspfad-Tests arbeiten mit
    LPI-Rohwerten, die in BEIDEN Leitern (DE_ALPEN 1/30/50, EU_REST 5/20/50)
    dieselbe Stufe ergeben. Eine fest verdrahtete oder vertauschte Region in
    `_schwellen_fuer_reihe()` bliebe dort strukturell unsichtbar (Mutation 5
    des Adversary: "NICHT GEFANGEN"). Hier trennen die beiden Koordinaten die
    Leitern eindeutig.

    Keine Mocks: echte `Location`/`NormalizedTimeseries`-Datencontainer. Das
    Modell `"aggregate"` normalisiert auf "keine Herkunft" -- die
    CAPE-Schwelle loest damit auf `None` auf und der Test bleibt auf dem
    LPI-Teil.
    """
    from app.config import Location
    from app.models import ForecastMeta, NormalizedTimeseries, Provider
    from providers.thunder_enrichment import _schwellen_fuer_reihe
    from providers.thunder_routing import thunder_region_for

    assert thunder_region_for(lat, lon) == erwartete_region, (
        f"Vorbedingung: {name} ({lat}, {lon}) muss im Raster "
        f"{erwartete_region} treffen"
    )

    reihe = NormalizedTimeseries(
        meta=ForecastMeta(
            provider=Provider.OPENMETEO, model="aggregate", grid_res_km=2.2,
        ),
        data=[],
    )
    cape_schwelle, lpi_leiter = _schwellen_fuer_reihe(
        reihe, Location(latitude=lat, longitude=lon, name=name),
    )

    assert lpi_leiter == erwartete_leiter, (
        f"{name} liegt in {erwartete_region} und muss die Leiter "
        f"{erwartete_leiter} bekommen, erhalten {lpi_leiter!r} -- Hinweis auf "
        f"eine fest verdrahtete oder vertauschte Gebiets-Aufloesung"
    )
    assert cape_schwelle is None
