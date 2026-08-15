"""TDD RED -- #1531 S1: die sieben neuen Gewittergroessen erreichen den
Datenpunkt ueber den EINEN gemeinsamen Anschluss (`thunder_enrichment.py`).

Spec: docs/specs/modules/feat_1531_s1_dwd_gewittergroessen.md
Abgedeckte ACs hier: AC-1 (Ende-zu-Ende, D2 UND EU), AC-6 (Ende-zu-Ende).

WARUM ENDE-ZU-ENDE UEBER `OpenMeteoProvider.fetch_forecast`: bei #1457 S2a
waren alle Provider-Ebene-ACs erfuellt und die Blitzdichte erreichte
trotzdem nie einen Nutzer, weil der Abruf nur im Totalausfall-Pfad haeng.
Ein reiner Provider-Test (test_dwd_thunder_new_signals_fetch.py /
test_dwd_eu_thunder_energy_signals_fetch.py) beweist NICHT, dass die Werte
am Datenpunkt ankommen -- das prueft diese Datei, ueber den REGULAEREN Weg
bei FUNKTIONIERENDER Hauptquelle (Muster
test_thunder_named_signals_enrichment.py).

Wiederverwendete Fixtures/Server-Bausteine: `_server`/`_STURM`/`_KARNISCH`
aus test_dwd_thunder_new_signals_fetch.py (ICON-D2) und
`eu_server`/`ABRUZZEN`/`hauptquelle_laeuft` aus `_dwd_eu_fixtures.py`
(ICON-EU) -- keine Duplikate der Aufzeichnungswerte, s. dort fuer Herkunft
und Messwerte.

RED-GRUND (heute, unveraenderter Code): `ForecastDataPoint` hat keines der
sieben neuen Felder -> `AttributeError`; `thunder_enrichment._SIGNAL_ZU_FELD`
kennt keines der sieben neuen Signalnamen.

Testart: Kern-Schicht (KEIN `live`-Marker, anders als die beiden
Provider-Ebene-Dateien) -- lokale HTTP-Server, kein echtes Netz, keine Mocks.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.models import ForecastDataPoint  # noqa: E402
from providers import openmeteo as om  # noqa: E402
from providers import thunder_enrichment  # noqa: E402
from tests.tdd._dwd_eu_fixtures import (  # noqa: E402
    ABRUZZEN, FIXTURE_CAPE_CON, FIXTURE_CAPE_ML, FIXTURE_CIN_ML,
    eu_server, hauptquelle_laeuft, rohwert_an,
)
from tests.tdd.test_dwd_thunder_new_signals_fetch import (  # noqa: E402
    _KARNISCH, _NEUE_EINZEL_FIXTUREN, _server as _d2_server,
)

# Sieben neue Signal->Feld-Paare (Spec "Implementation Details" 1/4). Als
# TEST-LOKALE Erwartung notiert, NICHT aus dem Produktivcode gelesen --
# genau DAS ist hier der Pruefgegenstand.
_ERWARTETE_SIGNAL_ZU_FELD = {
    "sdi_2": "supercell_index_sdi2_1s",
    "cin_ml": "convective_inhibition_jkg",
    "cape_ml": "cape_ml_jkg",
    "lpi_max": "lightning_potential_max_lpi_jkg",
    "uh_max": "updraft_helicity_max_m2s2",
    "uh_max_med": "updraft_helicity_max_med_m2s2",
    "uh_max_low": "updraft_helicity_max_low_m2s2",
}


# ---------------------------------------------------------------------------
# Datenmodell: sieben neue Felder, Default None.
# ---------------------------------------------------------------------------

def test_forecastdatapoint_traegt_die_sieben_neuen_felder_mit_none_default():
    """Given ein frisch gebauter `ForecastDataPoint`, When keine Gewitterwerte
    gesetzt werden, Then existieren alle sieben neuen Felder und sind `None`
    (kein Feld fehlt, keins traegt einen stillen Default != None)."""
    dp = ForecastDataPoint(ts=datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc))
    fehlend = [
        feld for feld in _ERWARTETE_SIGNAL_ZU_FELD.values() if not hasattr(dp, feld)
    ]
    assert not fehlend, f"ForecastDataPoint hat diese Felder NICHT: {fehlend}"
    nicht_none = [
        feld for feld in _ERWARTETE_SIGNAL_ZU_FELD.values()
        if hasattr(dp, feld) and getattr(dp, feld) is not None
    ]
    assert not nicht_none, (
        f"Diese Felder tragen einen Default != None: {nicht_none} -- das waere "
        "eine erfundene Messung statt 'keine Aussage'"
    )


# ---------------------------------------------------------------------------
# Signal->Feld-Tabelle: die sieben neuen Paare.
# ---------------------------------------------------------------------------

def test_signal_zu_feld_enthaelt_die_sieben_neuen_paare():
    """Given die Signal->Feld-Tabelle des gemeinsamen Anschlusses, When die
    sieben neuen Groessen nachgeschlagen werden, Then zeigen sie auf genau
    die in der Spec benannten Modellfelder -- je Groesse ein EIGENES Feld."""
    tabelle = thunder_enrichment._SIGNAL_ZU_FELD
    fehlend = {k: v for k, v in _ERWARTETE_SIGNAL_ZU_FELD.items() if tabelle.get(k) != v}
    assert not fehlend, (
        f"Diese Signal->Feld-Paare fehlen oder zeigen falsch: {fehlend} "
        f"(aktuelle Tabelle: {tabelle})"
    )
    # Je Groesse ein EIGENES Feld -- keine zwei Signale teilen sich eins.
    ziel_felder = [_ERWARTETE_SIGNAL_ZU_FELD[k] for k in _ERWARTETE_SIGNAL_ZU_FELD]
    assert len(set(ziel_felder)) == len(ziel_felder), (
        f"Mindestens zwei der sieben neuen Signale zeigen auf dasselbe Feld: {ziel_felder}"
    )


def test_bekannte_felder_deckt_die_sieben_neuen_felder_ab():
    """Given den Fill-Waechter `_bekannte_felder()`, When er heute aufgerufen
    wird, Then enthaelt er bereits alle sieben neuen Felder -- sonst wuerde
    ein zweiter Anreicherungs-Aufruf auf eine Reihe, die NUR eines der neuen
    Felder traegt, unbemerkt einen zweiten vollstaendigen Abruf ausloesen
    (Spec AC-5 des Vorgaenger-Moduls #1457 S2b, hier auf die neuen Felder
    uebertragen)."""
    bekannt = set(thunder_enrichment._bekannte_felder())
    fehlend = set(_ERWARTETE_SIGNAL_ZU_FELD.values()) - bekannt
    assert not fehlend, f"Diese neuen Felder fehlen im Fill-Waechter: {fehlend}"


# ---------------------------------------------------------------------------
# AC-1 Ende-zu-Ende (ICON-D2): der regulaere Weg traegt alle sieben Werte an
# den Datenpunkt.
# ---------------------------------------------------------------------------

def test_ac1_regulaerer_weg_traegt_die_sieben_neuen_werte_an_den_datenpunkt(
    monkeypatch,
):
    """AC-1: Given eine Position am Karnischen Hoehenweg und eine NORMAL
    verfuegbare Hauptquelle, When die Vorhersage ueber den regulaeren Weg
    (`OpenMeteoProvider.fetch_forecast`) geholt wird, Then tragen die
    Datenpunkte an mindestens einer Stunde `convective_inhibition_jkg` und
    `cape_ml_jkg` mit den Rohwerten der Aufzeichnung -- kein Ausfall, keine
    Sonderweiche."""
    with hauptquelle_laeuft(monkeypatch, _KARNISCH), _d2_server(monkeypatch):
        reihe = om.OpenMeteoProvider().fetch_forecast(_KARNISCH, enrich_ensemble=False)

    assert reihe.data, "Vorhersage ist leer"
    assert reihe.meta.fallback_reason != "cross_provider_total_outage", (
        "Der Test hat die Totalausfall-Weiche getroffen -- dann beweist er "
        "nicht den regulaeren Weg"
    )
    erwartet_cin = rohwert_an(_NEUE_EINZEL_FIXTUREN["cin_ml"].read_bytes(), 46.40, 12.52)
    erwartet_cape = rohwert_an(_NEUE_EINZEL_FIXTUREN["cape_ml"].read_bytes(), 46.40, 12.52)

    cin_werte = [dp.convective_inhibition_jkg for dp in reihe.data]
    cape_werte = [dp.cape_ml_jkg for dp in reihe.data]
    assert any(v is not None and abs(v - erwartet_cin) < 0.01 for v in cin_werte), (
        f"Kein Zeitpunkt traegt convective_inhibition_jkg={erwartet_cin}. Angekommen: {cin_werte}"
    )
    assert any(v is not None and abs(v - erwartet_cape) < 0.01 for v in cape_werte), (
        f"Kein Zeitpunkt traegt cape_ml_jkg={erwartet_cape}. Angekommen: {cape_werte}"
    )


# ---------------------------------------------------------------------------
# AC-1/AC-6 Ende-zu-Ende (ICON-EU): die drei Energiegroessen kommen an,
# sdi_2/uh_max* bleiben leer.
# ---------------------------------------------------------------------------

def test_ac1_und_ac6_icon_eu_traegt_energiegroessen_und_laesst_d2_exklusive_felder_leer(
    monkeypatch,
):
    """AC-1 (ICON-EU-Haelfte) + AC-6: Given eine Position in Rest-Europa
    (Abruzzen) und eine normal verfuegbare Hauptquelle, When die Vorhersage
    ueber den regulaeren Weg geholt wird, Then tragen die Datenpunkte
    `cape_ml_jkg` und `convective_inhibition_jkg` mit den Rohwerten der
    Aufzeichnung, UND jeder Datenpunkt hat `supercell_index_sdi2_1s`,
    `updraft_helicity_max_m2s2`, `updraft_helicity_max_med_m2s2` sowie
    `updraft_helicity_max_low_m2s2` durchgaengig `None` -- ICON-EU bietet
    diese vier Groessen laut Spec-Vorbedingung nicht an."""
    fixtures = {
        "lpi_con_max": FIXTURE_CAPE_ML.read_bytes(),  # irrelevant fuer diesen Test
        "cape_ml": FIXTURE_CAPE_ML.read_bytes(),
        "cape_con": FIXTURE_CAPE_CON.read_bytes(),
        "cin_ml": FIXTURE_CIN_ML.read_bytes(),
    }
    with hauptquelle_laeuft(monkeypatch, ABRUZZEN), \
            eu_server(monkeypatch, fixtures=fixtures):
        reihe = om.OpenMeteoProvider().fetch_forecast(ABRUZZEN, enrich_ensemble=False)

    assert reihe.data, "Vorhersage ist leer"
    erwartet_cape = rohwert_an(FIXTURE_CAPE_ML.read_bytes(), ABRUZZEN.latitude, ABRUZZEN.longitude)
    erwartet_cin = rohwert_an(FIXTURE_CIN_ML.read_bytes(), ABRUZZEN.latitude, ABRUZZEN.longitude)
    assert erwartet_cape > 0 and erwartet_cin > 0, "Aufzeichnungen tragen an Abruzzen keine echten Werte"

    cape_werte = [dp.cape_ml_jkg for dp in reihe.data]
    cin_werte = [dp.convective_inhibition_jkg for dp in reihe.data]
    assert any(v is not None and abs(v - erwartet_cape) < 0.01 for v in cape_werte), (
        f"Kein Zeitpunkt traegt cape_ml_jkg={erwartet_cape}. Angekommen: {cape_werte}"
    )
    assert any(v is not None and abs(v - erwartet_cin) < 0.01 for v in cin_werte), (
        f"Kein Zeitpunkt traegt convective_inhibition_jkg={erwartet_cin}. Angekommen: {cin_werte}"
    )

    d2_exklusiv = (
        "supercell_index_sdi2_1s", "updraft_helicity_max_m2s2",
        "updraft_helicity_max_med_m2s2", "updraft_helicity_max_low_m2s2",
    )
    for feld in d2_exklusiv:
        werte = [getattr(dp, feld) for dp in reihe.data]
        assert all(v is None for v in werte), (
            f"Feld '{feld}' traegt trotz ICON-EU-Quelle Werte: {werte} -- "
            "ICON-EU bietet diese Groesse laut Spec nicht an"
        )
