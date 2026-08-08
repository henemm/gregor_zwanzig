"""TDD RED -- Issue #1592 Scheibe B0+C1, AC-1 + AC-5 .. AC-8.

SPEC: docs/specs/modules/fix_1592_s1_cape_modellschwelle.md

B0 (AC-1): statische, versionierte Eichtabelle `CAPE_THRESHOLDS_JKG` in
`app.model_registry` -- 95. Perzentil der Modellklimatologie je (Modell,
Gebiet), mindestens 300 J/kg.

C1 (AC-5..AC-8): `thunder_level_from_signals()` bekommt einen keyword-only
Parameter `cape_threshold_jkg` OHNE Default; `thunder_enrichment.enrich_thunder()`
loest die Herkunft (`effective_cape_model_id` + `thunder_region_for`) EINMAL
je Reihe auf und reicht die kalibrierte Schwelle durch. Kein `= None`-Rueckfall
(ADR-0025): ein Aufrufer, der die Herkunft nicht aufloest, bricht mit
TypeError statt still auf Bestandsverhalten zurueckzufallen.

RED-Ursache (heute):
- AC-1: `app.model_registry` existiert nicht -> ImportError.
- AC-5/AC-7/AC-8: die Fusion kennt noch KEINE Modell-Herkunft -- sie
  bewertet CAPE ausnahmslos gegen die eine feste Katalog-1000 (ueber
  `_cape_low_min_jkg()`), unabhaengig vom liefernden Modell. Ergebnisse
  weichen deshalb vom erwarteten (kalibrierten) Wert ab.
- AC-6: dieselbe feste 1000er-Schwelle laesst CAPE OHNE Ruecksicht auf die
  Herkunft zur Fusion beitragen -- bei unbekannter Herkunft (aggregate/
  snapshot) UND hohem CAPE liefert die heutige Fusion faelschlich
  `ThunderLevel.LOW`/`NONE` statt der erwarteten Python-`None` ("keine
  Aussage").

Testart wie #1474/#1474c (`test_thunder_level_from_signals_fusion.py`,
`test_thunder_enrichment_fuses_level_shared_path.py`): AC-5/AC-6/AC-7/AC-8
laufen zwingend ueber die ECHTE Einstiegsfunktion `enrich_thunder()`
(ADR-0025) -- NICHT ueber den isolierten Aufruf von
`thunder_level_from_signals()`. Um einen echten Netzabruf fuer die
Blitzdichte zu vermeiden (der hier nicht Testgegenstand ist), wird
`thunder_routing.thunder_provider_for()` per `monkeypatch` auf "keine
zustaendige Quelle" gesetzt -- ein regulaerer, dokumentierter Rueckgabewert
dieser Funktion (kein Verhaltens-Mock), der bewusst "Wettercode und
Blitzdichte ohne Signal" (AC-5-Vorgabe) erzeugt.

Keine Mocks im Sinne von Mock()/patch()/MagicMock als Verhaltensnachweis --
`monkeypatch.setattr` ersetzt hier nur eine Konfigurations-/Routing-
Entscheidung, wie es die bestehenden Fixtures dieses Bereichs bereits tun.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.config import Location
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
    ThunderLevel,
)

# GR20 Refuge de Petra Piana -- liegt im FR-Zustaendigkeitsgebiet
# (`thunder_routing._REGIONS`), derselbe Referenzpunkt wie in der Analyse-
# Messung und im bestehenden Gewitter-Testbestand.
_KORSIKA = Location(latitude=42.22, longitude=9.07, name="GR20 Petra Piana")


def _reihe_ohne_signal_ausser_cape(model: str, cape_jkg: float) -> NormalizedTimeseries:
    """Eine Ein-Punkt-Reihe: Wettercode UND Blitzdichte tragen KEIN Signal
    (frische ForecastDataPoint-Defaults), nur CAPE ist gesetzt."""
    meta = ForecastMeta(provider=Provider.METEOFRANCE, model=model, grid_res_km=1.3)
    dp = ForecastDataPoint(ts=datetime.now(timezone.utc), cape_jkg=cape_jkg)
    return NormalizedTimeseries(meta=meta, data=[dp])


def _ohne_lightning_fetch(monkeypatch):
    """Verhindert den (fuer diese Tests irrelevanten) echten Netzabruf der
    Blitzdichte -- `thunder_provider_for` liefert regulaer `None`, wenn fuer
    ein Gebiet keine Gewitterquelle zustaendig ist (Docstring
    `thunder_routing.py`); hier wird dieser dokumentierte Zustand erzwungen,
    damit CAPE das EINZIGE wirksame Signal bleibt (AC-5-Vorgabe "Wettercode
    und Blitzdichte ohne Signal")."""
    import providers.thunder_routing as routing

    monkeypatch.setattr(routing, "thunder_provider_for", lambda lat, lon: None)


# ─────────────────── AC-1 -- Eichtabelle respektiert Untergrenze ──────────

def test_ac1_eichtabelle_respektiert_untergrenze_und_ist_keine_pauschale_klemmung():
    """AC-1: JEDER Eintrag >= 300 J/kg (Konstruktionsregel: max(P95, 300)).
    Zwei EIGENSCHAFTEN der Tabelle belegen, dass 300 eine echte Untergrenze
    ist, keine pauschale Klemmung: MINDESTENS EIN Eintrag liegt EXAKT bei
    300 (die Untergrenze greift, das rohe P95 lag darunter) UND MINDESTENS
    EIN Eintrag liegt STRIKT zwischen 300 und 1000 (die Untergrenze greift
    dort NICHT). Waere die Untergrenze faelschlich als fester Wert
    implementiert, waeren ALLE Eintraege exakt 300 und die zweite
    Bedingung faellt durch.

    Bewusst NICHT an ein bestimmtes Modell/Gebiet-Paar gebunden (PO-
    Korrektur 2026-08-08, nach einer fruehen Fassung, die an
    `icon_d2 x DE_ALPEN` haengengeblieben war): eine Neueichung kann
    einzelne Werte um die Grenze verschieben, ohne dass die Eichregel
    selbst falsch wird -- der Test soll DAS pruefen, nicht einen
    Momentaufnahme-Literalwert."""
    from app.model_registry import CAPE_THRESHOLDS_JKG

    assert CAPE_THRESHOLDS_JKG, (
        "Eichtabelle ist leer -- das Auswertungsskript (B0) wurde nicht "
        "ausgefuehrt bzw. sein Ergebnis nicht committed"
    )

    unterschritten = {
        key: value for key, value in CAPE_THRESHOLDS_JKG.items() if value < 300.0
    }
    assert not unterschritten, (
        f"Folgende Eintraege unterschreiten die Untergrenze 300 J/kg (Verstoss "
        f"gegen die Eichregel max(P95, 300)): {unterschritten}"
    )

    exakt_300 = {k: v for k, v in CAPE_THRESHOLDS_JKG.items() if v == 300.0}
    assert exakt_300, (
        "Kein Eintrag liegt exakt bei 300 J/kg -- AC-1 kann nicht belegen, "
        "dass die Untergrenze ueberhaupt jemals GREIFT (rohes P95 unter 300)"
    )

    strikt_dazwischen = {
        k: v for k, v in CAPE_THRESHOLDS_JKG.items() if 300.0 < v < 1000.0
    }
    assert strikt_dazwischen, (
        "Kein Eintrag liegt STRIKT zwischen 300 und 1000 J/kg -- AC-1 kann "
        "nicht belegen, dass die Untergrenze eine echte Untergrenze ist "
        "(nicht greift, wenn das rohe P95 bereits darueber liegt). Waere "
        "die Untergrenze faelschlich als fester Wert implementiert, waeren "
        "ALLE Eintraege exakt 300 und diese Menge leer."
    )


# ───────── AC-5 -- Kernfall: GR20/AROME traegt jetzt zur Stufe bei ────────

def test_ac5_arome_cape_840_traegt_jetzt_zur_gewitterstufe_bei(monkeypatch):
    """AC-5: GR20/AROME, CAPE=840 J/kg (real gemessener Analyse-Wert),
    Wettercode und Blitzdichte ohne Signal -> ueber den regulaeren Weg
    (`enrich_thunder()`, ADR-0025) liefert `dp.thunder_level`
    `ThunderLevel.LOW`. Mit der alten, festen 1000er-Schwelle bliebe dieser
    reale Wert NIE ueber 'kein Gewitter' hinaus (AROME erreicht 1000 J/kg
    strukturell fast nie, Kontext-Messung: 0,5-0,7 % der Stunden)."""
    from providers.thunder_enrichment import enrich_thunder

    _ohne_lightning_fetch(monkeypatch)
    reihe = _reihe_ohne_signal_ausser_cape("meteofrance_arome", 840.0)

    enrich_thunder(reihe, _KORSIKA)

    dp = reihe.data[0]
    assert dp.thunder_level == ThunderLevel.LOW, (
        f"AROME/GR20, CAPE=840 J/kg muss ueber die kalibrierte Schwelle "
        f"(Eichregel: max(P95, 300), P95 fuer AROME/FR ~260 -> Schwelle "
        f"300 -- 840 liegt sicher darueber) ThunderLevel.LOW liefern, "
        f"erhalten {dp.thunder_level!r}. Mit der alten festen 1000er-"
        f"Katalogschwelle waere das Ergebnis NONE."
    )


# ─────── AC-6 -- Gegenfall: unbekannte Herkunft -> keine Aussage ──────────

def test_ac6_unbekannte_herkunft_liefert_keine_aussage_nicht_kein_gewitter(monkeypatch):
    """AC-6: Ort ohne Modell-Herkunft (Ortsvergleich `model='aggregate'`
    ODER Schnappschuss-Reload `model='snapshot'`), hoher CAPE-Wert, alle
    anderen Signale ohne Wert -> die Fusion liefert Python-`None` ('keine
    Aussage'), NICHT `ThunderLevel.NONE` ('geprueft, unauffaellig').

    Gegenprobe: faellt die Implementierung bei unbekannter Herkunft auf die
    alte feste Schwelle zurueck, liefert `enrich_thunder()` heute
    faelschlich `ThunderLevel.LOW` (CAPE 5000 >= 1000) statt `None` --
    dieser Test faengt genau das (`is None`, nicht nur `!= LOW`)."""
    from providers.thunder_enrichment import enrich_thunder

    _ohne_lightning_fetch(monkeypatch)

    for unbekanntes_modell in ("aggregate", "snapshot"):
        reihe = _reihe_ohne_signal_ausser_cape(unbekanntes_modell, 5000.0)

        enrich_thunder(reihe, _KORSIKA)

        dp = reihe.data[0]
        assert dp.thunder_level is None, (
            f"Modell-Herkunft '{unbekanntes_modell}' ist strukturell "
            f"unbekannt -- trotz CAPE=5000 J/kg muss dp.thunder_level "
            f"'keine Aussage' (Python None) bleiben, erhalten "
            f"{dp.thunder_level!r}. Ein ThunderLevel.NONE waere eine "
            f"faelschlich behauptete gepruefte Entwarnung."
        )


# ─── AC-7 -- Deutschland bleibt funktionsfaehig, jetzt auf Eichbasis ──────

def test_ac7_icon_d2_oberhalb_kalibrierter_schwelle_liefert_leicht(monkeypatch):
    """AC-7: ICON-D2/DE_ALPEN-Herkunft, CAPE oberhalb der fuer diese
    Kombination KALIBRIERTEN Schwelle (aus der Eichtabelle nachgeschlagen,
    nicht als Literal geraten -- die Erwartung ist damit unabhaengig vom
    tatsaechlichen Eichergebnis korrekt) -> `ThunderLevel.LOW`."""
    from app.model_registry import cape_threshold_jkg
    from providers.thunder_enrichment import enrich_thunder

    _ohne_lightning_fetch(monkeypatch)

    schwelle = cape_threshold_jkg("icon_d2", "DE_ALPEN")
    assert schwelle is not None, (
        "icon_d2/DE_ALPEN fehlt in der Eichtabelle -- AC-7 kann ohne "
        "kalibrierte Schwelle nicht pruefen"
    )
    cape_wert = schwelle + 50.0

    reihe = _reihe_ohne_signal_ausser_cape("icon_d2", cape_wert)
    # Der Karnische Hoehenweg liegt im DE_ALPEN-Zustaendigkeitsgebiet
    # (`thunder_routing._REGIONS`).
    karnisch = Location(latitude=46.40, longitude=12.52, name="Karnischer Hoehenweg")

    enrich_thunder(reihe, karnisch)

    dp = reihe.data[0]
    assert dp.thunder_level == ThunderLevel.LOW, (
        f"ICON-D2/DE_ALPEN, CAPE={cape_wert} J/kg (Schwelle+50) muss "
        f"ThunderLevel.LOW liefern, erhalten {dp.thunder_level!r}"
    )


# ───────────── AC-8 -- Deckelung bleibt, unabhaengig von der Schwelle ─────

def test_ac8_sehr_hohes_cape_eskaliert_nie_ueber_leicht(monkeypatch):
    """AC-8: CAPE weit oberhalb der kalibrierten AROME/FR-Schwelle (aus der
    Eichtabelle nachgeschlagen, s. AC-7-Begruendung) -> bleibt bei
    `ThunderLevel.LOW`, eskaliert NIE auf MED/HIGH (dieselbe Zusicherung wie
    feat_1474 AC-6, jetzt mit variabler statt fester Schwelle).

    Bewusst NICHT der Literalwert 5000 J/kg aus der Spec-Beschreibung allein
    (der waere bereits mit der ALTEN festen 1000er-Schwelle >= 1000 und
    liefert schon heute zufaellig LOW -- dieser Test bliebe dann sinnlos
    gruen, obwohl die kalibrierte Schwelle noch gar nicht existiert). Der
    CAPE-Wert wird stattdessen aus der (noch fehlenden) Eichtabelle
    abgeleitet: ein Vielfaches der tatsaechlich kalibrierten Schwelle."""
    from app.model_registry import cape_threshold_jkg
    from providers.thunder_enrichment import enrich_thunder

    _ohne_lightning_fetch(monkeypatch)

    schwelle = cape_threshold_jkg("meteofrance_arome", "FR")
    assert schwelle is not None, (
        "meteofrance_arome/FR fehlt in der Eichtabelle -- AC-8 kann ohne "
        "kalibrierte Schwelle nicht pruefen"
    )
    cape_wert = max(schwelle * 10.0, 5000.0)

    reihe = _reihe_ohne_signal_ausser_cape("meteofrance_arome", cape_wert)

    enrich_thunder(reihe, _KORSIKA)

    dp = reihe.data[0]
    assert dp.thunder_level == ThunderLevel.LOW, (
        f"CAPE={cape_wert} J/kg (weit ueber der kalibrierten Schwelle "
        f"{schwelle}) muss bei LOW gedeckelt bleiben, erhalten "
        f"{dp.thunder_level!r}"
    )
    assert dp.thunder_level not in (ThunderLevel.MED, ThunderLevel.HIGH), (
        f"CAPE allein darf NIE ueber 'leicht' hinaus ausloesen, erhalten "
        f"{dp.thunder_level!r}"
    )
