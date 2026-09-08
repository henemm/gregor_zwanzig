"""Gewitter-Signalherkunft — Ablation, CAPE-Zeitverlauf und Stufe-vs-Niederschlag
fuer den KHW-Archiv-Zeitraum (#2181 Scheibe S2c).

Prueft T1 (welcher Signalast traegt die erreichte Stufe?), T3 (CAPE-Vorlauf vor
der ersten Ereignisstunde) und T4 (Stufe-Niederschlag-Paarung), vorgeschaltet
ein Kalibrier-Abgleich (Archiv-CAPE gegen kurzvorlauf-naechste Mitschnitt-
Teilmenge). Reine Funktionen: kein Netz, kein Dateizugriff. Die Fusion selbst
(``thunder_signal_carriers``/``thunder_level_from_signals``) ist NICHT
Pruefling (ADR-0025) -- sie wird mit rekonstruierten Rohwerten aufgerufen.

Fixtures: die 29.08.-Stunden sind reale, unveraendert uebernommene Werte aus
der Live-Machbarkeitspruefung gegen historical-forecast-api.open-meteo.com
(docs/context/feat-2181-s2c-signalherkunft.md). Alle anderen Archiv-Stunden
sind konstruiert, weil die realen Werte am KHW keine der Sprossen-Kombination
liefern, die die jeweilige AC verlangt (S2c-Spec, Implementation Details).
"""

import json
from pathlib import Path

import pytest

from src.analysis.thunder_ablation import (
    ablation_je_stunde,
    ablation_tagesmaximum,
    cape_verlauf_und_ereignisfenster,
    kalibrier_abgleich_kurzvorlauf_cape,
    niederschlag_tagessumme,
    stufe_gegen_niederschlag,
    vergleiche_ablation_mit_mitschnitt,
)
from src.analysis.thunder_replay import tageswerte_je_teilmenge
from src.app.model_registry import cape_ladder_thresholds_jkg, lpi_thresholds_jkg
from src.app.models import ThunderLevel
from src.providers.openmeteo import THUNDER_CODES

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "khw_2026_08_archiv"
_MITSCHNITT_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "khw_2026_08"

_ARCHIV_STUNDENZEILEN_FIXTURES = [
    "wolayersee_29_08_ausschnitt.json",
    "synthetisch_cape_hoch_cin_stark_gedaempft.json",
    "synthetisch_blitzpotenzial_alleiniger_traeger.json",
    "synthetisch_zwei_traeger_selbe_hoechststufe.json",
    "synthetisch_mitschnitt_high_ohne_archiv_treffer.json",
    "synthetisch_wettercode_fehlend_vs_explizit.json",
    "ruhiger_tag_ohne_ereignisstunde.json",
]


def _fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _mitschnitt_zeilen(name: str) -> list[dict]:
    return json.loads((_MITSCHNITT_FIXTURES / name).read_text(encoding="utf-8"))["zeilen"]


def _stunde(stunden: list[dict], zeit: str) -> dict:
    treffer = [s for s in stunden if s["time"] == zeit]
    assert len(treffer) == 1, f"genau eine Stunde {zeit} erwartet, {len(treffer)} gefunden"
    return treffer[0]


def _cape_ladder() -> tuple:
    schwellen = cape_ladder_thresholds_jkg("icon_d2", "DE_ALPEN")
    assert schwellen is not None, "CAPE-Leiter fuer icon_d2/DE_ALPEN nicht kalibriert"
    return schwellen


def _lpi_leiter() -> tuple:
    schwellen = lpi_thresholds_jkg("DE_ALPEN")
    assert schwellen is not None, "LPI-Leiter fuer DE_ALPEN nicht kalibriert"
    return schwellen


def test_ac1_kalibrier_abgleich_markiert_toleranzband_und_abweichung():
    """AC-1: Differenz 50 J/kg (< Toleranz 150) -> "im_toleranzband";
    Differenz 400 J/kg (> Toleranz) -> "abweichend"; Differenz GENAU 150 J/kg
    (== Toleranz) -> "im_toleranzband" (inklusive Grenze, F001-Mutationsfund:
    ein ``<`` statt ``<=`` an dieser Stelle liefe hier unbemerkt durch)."""
    daten = _fixture("kalibrier_abgleich_toleranzband_und_abweichend.json")

    ergebnis = kalibrier_abgleich_kurzvorlauf_cape(
        daten["mitschnitt_tageswerte_primaer"],
        daten["archiv_cape_tagesmaximum"],
        daten["toleranz_jkg"],
    )

    assert ergebnis["2026-08-29"]["kategorie"] == "im_toleranzband"
    assert ergebnis["2026-08-29"]["differenz_jkg"] == pytest.approx(50.0)
    assert ergebnis["2026-09-02"]["kategorie"] == "abweichend"
    assert ergebnis["2026-09-02"]["differenz_jkg"] == pytest.approx(400.0)
    assert ergebnis["2026-09-03"]["kategorie"] == "im_toleranzband"
    assert ergebnis["2026-09-03"]["differenz_jkg"] == pytest.approx(150.0)


def test_ac1_toleranz_ist_die_halbe_low_sprosse_nicht_hartkodiert():
    """AC-1: die Toleranz (150 J/kg) ist die HALBE LOW-Sprosse von
    icon_d2/DE_ALPEN -- kein freier Prozentwert im Modul."""
    low, _, _ = _cape_ladder()
    assert low / 2 == 150.0


def test_ac2_tag_ohne_gueltigen_vorlauf_ist_kein_vergleichswert():
    """AC-2: ein Mitschnitt-Tag ohne jede Zeile mit gueltigem Vorlauf fehlt in
    ``mitschnitt_tageswerte_primaer`` komplett -- der Kalibrier-Abgleich
    markiert ihn als "kein_vergleichswert", nie als "im_toleranzband"."""
    zeilen = _mitschnitt_zeilen("negativer_vorlauf_einzelzeile.json")
    mitschnitt_primaer = tageswerte_je_teilmenge(zeilen)["primaer"]
    assert "2026-08-21" not in mitschnitt_primaer

    ergebnis = kalibrier_abgleich_kurzvorlauf_cape(
        mitschnitt_primaer, {"2026-08-21": 500.0}, toleranz_jkg=150.0,
    )

    assert ergebnis["2026-08-21"]["kategorie"] == "kein_vergleichswert"
    assert ergebnis["2026-08-21"]["differenz_jkg"] is None


def test_ac3_wettercode_traegt_high_unabhaengig_von_schwaecheren_signalen():
    """AC-3: ``weather_code=96`` liefert HIGH mit Traeger "wettercode",
    unabhaengig davon, dass CAPE (0.0) und LPI (2.6) unter ihrer HIGH-Sprosse
    bleiben (reale 15:00-Stunde vom 29.08.)."""
    stunde = _stunde(_fixture("wolayersee_29_08_ausschnitt.json")["stunden"], "2026-08-29T15:00")
    assert stunde["weather_code"] == 96

    ergebnis = ablation_je_stunde(stunde, _cape_ladder(), _lpi_leiter())

    assert ergebnis == {"stufe": ThunderLevel.HIGH, "traeger": ["wettercode"]}


def test_ac4_gedaempfte_cape_stufe_erreicht_hoechstens_low():
    """AC-4: CAPE 1500 J/kg (ueber der HIGH-Sprosse 1200) mit CIN=150
    (>100 J/kg) wird durch die CIN-Daempfung auf hoechstens LOW gedeckelt,
    nicht ungedaempft als HIGH gezaehlt."""
    stunde = _fixture("synthetisch_cape_hoch_cin_stark_gedaempft.json")["stunden"][0]

    ergebnis = ablation_je_stunde(stunde, _cape_ladder(), _lpi_leiter())

    assert ergebnis == {"stufe": ThunderLevel.LOW, "traeger": ["cape"]}


def test_ac5_blitzpotenzial_alleiniger_traeger_der_hoechststufe():
    """AC-5: LPI 60 (ueber der HIGH-Sprosse 50) bei code=2 (kein Gewitter)
    und niedrigem CAPE (50) -- "blitzpotenzial" ist der ALLEINIGE Traeger."""
    stunde = _fixture("synthetisch_blitzpotenzial_alleiniger_traeger.json")["stunden"][0]

    ergebnis = ablation_je_stunde(stunde, _cape_ladder(), _lpi_leiter())

    assert ergebnis == {"stufe": ThunderLevel.HIGH, "traeger": ["blitzpotenzial"]}


def test_ac6_tagesverdichtung_vereint_alle_traeger_der_hoechststufe():
    """AC-6: zwei Stunden desselben Tages erreichen HIGH ueber je einen
    ANDEREN alleinigen Traeger -- die Tagesverdichtung fuehrt BEIDE Namen."""
    stunden = _fixture("synthetisch_zwei_traeger_selbe_hoechststufe.json")["stunden"]
    cape_ladder, lpi_leiter = _cape_ladder(), _lpi_leiter()

    einzel = [ablation_je_stunde(s, cape_ladder, lpi_leiter) for s in stunden]
    assert [e["stufe"] for e in einzel] == [ThunderLevel.HIGH, ThunderLevel.HIGH]
    assert einzel[0]["traeger"] == ["wettercode"]
    assert einzel[1]["traeger"] == ["cape"]

    tag = ablation_tagesmaximum(stunden, cape_ladder, lpi_leiter)

    assert tag["stufe"] == ThunderLevel.HIGH
    assert set(tag["traeger"]) == {"wettercode", "cape"}


def test_ac7_archiv_erreicht_mitschnitt_high_nicht_eigene_kategorie():
    """AC-7: alle Archiv-Stunden des Tages bleiben hoechstens LOW, waehrend
    der Mitschnitt HIGH zeigt -- ``ablation_erreicht_mitschnitt_stufe`` wird
    False, statt still einem der drei Aeste zugeschlagen zu werden."""
    daten = _fixture("synthetisch_mitschnitt_high_ohne_archiv_treffer.json")
    cape_ladder, lpi_leiter = _cape_ladder(), _lpi_leiter()
    stunden = daten["stunden"]

    assert all(
        ablation_je_stunde(s, cape_ladder, lpi_leiter)["stufe"] != ThunderLevel.HIGH
        for s in stunden
    )

    tag = ablation_tagesmaximum(stunden, cape_ladder, lpi_leiter)
    vergleich = vergleiche_ablation_mit_mitschnitt(tag, ThunderLevel(daten["mitschnitt_stufe"]))

    assert vergleich == {
        "mitschnitt_stufe": ThunderLevel.HIGH,
        "ablation_stufe": tag["stufe"],
        "traeger": tag["traeger"],
        "ablation_erreicht_mitschnitt_stufe": False,
    }
    assert vergleich["ablation_stufe"] != ThunderLevel.HIGH


def test_ac7_gleichstand_zaehlt_als_erreicht():
    """AC-7 (Gegenprobe, F002-Mutationsfund): Ablation und Mitschnitt auf
    GENAU derselben Stufe -- ``ablation_erreicht_mitschnitt_stufe`` muss
    ``True`` sein (``>=`` statt ``>`` an dieser Stelle), nicht nur beim
    Ueberholen der Mitschnitt-Stufe."""
    ablation_tag = {"stufe": ThunderLevel.MED, "traeger": ["cape"]}

    vergleich = vergleiche_ablation_mit_mitschnitt(ablation_tag, ThunderLevel.MED)

    assert vergleich["ablation_erreicht_mitschnitt_stufe"] is True


def test_ac8_fehlender_wettercode_traegt_nicht_explizite_entwarnung_schon():
    """AC-8: ``weather_code=None`` fehlt im Signal-Dict (Gesamtstufe ``None``
    = keine Aussage) -- ``weather_code=2`` liefert dagegen die geprueefte
    Entwarnung ``ThunderLevel.NONE``, bei sonst identischen (fehlenden)
    Signalen."""
    fehlend, explizit = _fixture("synthetisch_wettercode_fehlend_vs_explizit.json")["stunden"]
    cape_ladder, lpi_leiter = _cape_ladder(), _lpi_leiter()

    assert fehlend["weather_code"] is None
    assert ablation_je_stunde(fehlend, cape_ladder, lpi_leiter) == {"stufe": None, "traeger": []}

    assert explizit["weather_code"] == 2
    ergebnis = ablation_je_stunde(explizit, cape_ladder, lpi_leiter)
    assert ergebnis == {"stufe": ThunderLevel.NONE, "traeger": []}


def test_ac9_vorlauf_zwischen_cape_maximum_und_erster_ereignisstunde():
    """AC-9: reale 29.08.-Stunden -- CAPE-Maximum 790 J/kg um 13:00, erste
    Ereignisstunde (code=96, in THUNDER_CODES) um 15:00 -> 2.0h Vorlauf.
    Reine Rechenprobe, kein festgeschriebenes "muss 1-3h sein"-Kriterium."""
    stunden = _fixture("wolayersee_29_08_ausschnitt.json")["stunden"]
    assert stunden[1]["weather_code"] in THUNDER_CODES

    ergebnis = cape_verlauf_und_ereignisfenster(stunden)

    assert ergebnis["stundenwerte"] == [
        ("2026-08-29T13:00", 790.0), ("2026-08-29T15:00", 0.0), ("2026-08-29T16:00", 20.0),
    ]
    assert ergebnis["cape_maximum"] == ("2026-08-29T13:00", 790.0)
    assert ergebnis["erste_ereignisstunde"] == "2026-08-29T15:00"
    assert ergebnis["vorlauf_stunden"] == pytest.approx(2.0)


def test_ac10_kein_rechenfehler_ohne_ereignisstunde():
    """AC-10: ein Tag ganz ohne Ereignisstunde liefert ``None``/``None`` fuer
    ``erste_ereignisstunde``/``vorlauf_stunden`` -- kein erfundener Wert."""
    stunden = _fixture("ruhiger_tag_ohne_ereignisstunde.json")["stunden"]
    assert all(s["weather_code"] not in THUNDER_CODES for s in stunden)

    ergebnis = cape_verlauf_und_ereignisfenster(stunden)

    assert ergebnis["erste_ereignisstunde"] is None
    assert ergebnis["vorlauf_stunden"] is None
    assert ergebnis["cape_maximum"] is not None


def test_ac11_stufe_gegen_niederschlag_liefert_nur_das_rohe_tripel():
    """AC-11: NUR (Stufe, Niederschlagssumme, Schauersumme) je Tag -- kein
    Schwellenwert-Interpretationsfeld wie "nahe null"."""
    mitschnitt = _fixture("stufe_gegen_niederschlag_high_tag.json")["mitschnitt_tageswerte"]
    archiv_stunden = _fixture("wolayersee_29_08_ausschnitt.json")["stunden"]
    niederschlag_tag = niederschlag_tagessumme(archiv_stunden)
    assert niederschlag_tag["niederschlag_mm"] == pytest.approx(41.2)
    assert niederschlag_tag["schauer_mm"] == pytest.approx(0.3)

    ergebnis = stufe_gegen_niederschlag(mitschnitt, {"2026-08-29": niederschlag_tag})

    assert set(ergebnis["2026-08-29"]) == {"stufe", "niederschlag_mm", "schauer_mm"}
    assert ergebnis["2026-08-29"]["stufe"] == ThunderLevel.HIGH
    assert ergebnis["2026-08-29"]["niederschlag_mm"] == pytest.approx(41.2)
    assert ergebnis["2026-08-29"]["schauer_mm"] == pytest.approx(0.3)


def test_ac12_fehlende_mitschnitt_stufe_kollabiert_nicht_zu_none_level():
    """AC-12: eine Mitschnitt-Stufe ``None`` (keine Aussage) bleibt im
    Ergebnis ``None`` -- kollabiert nicht zu ``ThunderLevel.NONE``."""
    daten = _fixture("stufe_gegen_niederschlag_keine_mitschnitt_stufe.json")

    ergebnis = stufe_gegen_niederschlag(
        daten["mitschnitt_tageswerte"], daten["archiv_niederschlag_je_tag"],
    )

    assert ergebnis["2026-09-03"]["stufe"] is None


@pytest.mark.parametrize("name", _ARCHIV_STUNDENZEILEN_FIXTURES)
def test_fixtures_tragen_das_archiv_stundenzeilen_format(name):
    """Waechter: jede Archiv-Stundenzeile traegt genau die sieben Felder der
    Zip-Ausgabe (Spec Abschnitt "Archiv-Zeilenformat"), keine mehr, keine
    weniger -- verhindert Fixture-Drift gegen die reale Antwortform."""
    erwartete_schluessel = {
        "time", "weather_code", "cape", "convective_inhibition",
        "lightning_potential", "precipitation", "showers",
    }
    for stunde in _fixture(name)["stunden"]:
        assert set(stunde) == erwartete_schluessel
