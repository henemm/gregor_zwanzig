"""TDD RED — #1457 S2c: DWD ICON-EU fuellt die Gewitterluecke fuer Rest-Europa.

Spec: docs/specs/modules/feat_1457_s2c_icon_eu_luekenfueller.md
Abgedeckte ACs hier: AC-1, AC-2, AC-3, AC-5, AC-8, AC-10.
(AC-4 -> test_dwd_eu_thunder_time_budget.py, AC-7 -> test_dwd_eu_thunder_run_
fallback.py, AC-6 -> test_dwd_eu_thunder_parameter_names_live.py, AC-9 ->
test_thunder_enrichment_shared_path.py.)

Vermessung des echten Dienstes, Herkunft der Aufzeichnung und Testart: siehe
Modul-Docstring von `tests/tdd/_dwd_eu_fixtures.py`.

RED-GRUND (heute, unveraenderter Code): `providers.dwd_eu` existiert nicht
(ModuleNotFoundError), und `thunder_routing._REGIONS` hat keine Catch-all-Zeile
-> `thunder_provider_for` liefert fuer Rest-Europa `None`.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import tenacity

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider,
)
from providers import openmeteo as om  # noqa: E402
from providers import thunder_routing  # noqa: E402
from providers.thunder_enrichment import enrich_thunder  # noqa: E402
from tests.tdd._dwd_eu_fixtures import (  # noqa: E402
    ABRUZZEN, FIXTURE, AlleLaeufe, dwd_eu, eu_server, hauptquelle_laeuft,
    kunst_raster, rohwert_an,
)


# ---------------------------------------------------------------------------
# AC-8 — die Catch-all-Zeile steht ZULETZT: FR und DE_ALPEN bleiben unberuehrt.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name,lat,lon,erwartet",
    [
        ("Korsika", 42.22, 9.07, "fr_direct"),
        ("Paris", 48.85, 2.35, "fr_direct"),
        ("Berlin", 52.52, 13.405, "de_direct"),
        ("Innsbruck", 47.27, 11.39, "de_direct"),
        # Rest-Europa: bisher `None`, kuenftig ICON-EU.
        ("Abruzzen", 41.8125, 13.375, "eu_direct"),
        ("Madrid", 40.4, -3.7, "eu_direct"),
        ("Oslo", 59.91, 10.75, "eu_direct"),
        ("Sofia", 42.7, 23.32, "eu_direct"),
    ],
)
def test_ac8_rangfolge_der_zustaendigkeit_bleibt_erhalten(name, lat, lon, erwartet):
    """AC-8: Given die neue Catch-all-Zeile `EU_REST`, When die
    Gewitter-Zustaendigkeit bestimmt wird, Then behalten Frankreich
    (`fr_direct`) und DE/Alpen/AT (`de_direct`) ihre bestehende Quelle, und nur
    der Rest faellt an `eu_direct`.

    `_REGIONS` ist first-match-wins. Stuende die neue Zeile vor FR/DE_ALPEN,
    verschluckte sie beide bereits produktiven Gebiete — Korsika verloere seine
    Blitzdichte, die Alpen ihr Blitzpotenzial, und keiner der bestehenden
    Tests dieser Datei-Familie wuerde das an der Ausgabe sehen.
    """
    tatsaechlich = thunder_routing.thunder_provider_for(lat, lon)
    assert tatsaechlich == erwartet, (
        f"{name} ({lat}/{lon}) faellt an {tatsaechlich!r} statt {erwartet!r}"
    )


# ---------------------------------------------------------------------------
# AC-1 — Wirkungs-Nachweis Ende-zu-Ende ueber den REGULAEREN Weg.
# ---------------------------------------------------------------------------

def test_ac1_regulaerer_weg_traegt_blitzpotenzial_an_den_datenpunkt(monkeypatch):
    """AC-1: Given eine Position in Rest-Europa (Abruzzen) und eine NORMAL
    verfuegbare Hauptquelle, When die Vorhersage ueber den regulaeren Weg
    (`OpenMeteoProvider.fetch_forecast`) geholt wird, Then traegt mindestens
    ein Zeitpunkt den Blitzpotenzial-Wert, der in der Aufzeichnung an dieser
    Koordinate steht.

    Kein Ausfall, keine Sonderweiche — genau der Weg jedes echten Briefings.
    Heute bleibt dieselbe Abfrage dort durchgaengig leer. Ein reiner
    Methodentest am Provider bewiese das NICHT: bei S2a waren alle ACs gruen
    und der Wert erreichte trotzdem nie einen Nutzer.
    """
    with hauptquelle_laeuft(monkeypatch, ABRUZZEN), eu_server(monkeypatch) as srv:
        reihe = om.OpenMeteoProvider().fetch_forecast(ABRUZZEN, enrich_ensemble=False)
        abrufe = list(srv.abrufe)

    assert reihe.data, "Vorhersage ist leer"
    assert reihe.meta.fallback_reason != "cross_provider_total_outage", (
        "Der Test hat die Totalausfall-Weiche getroffen — dann beweist er "
        "nicht den regulaeren Weg (exakt die S2a-Luecke)"
    )
    assert abrufe, (
        "ICON-EU wurde nie kontaktiert — die Catch-all-Zustaendigkeit greift "
        "im regulaeren Weg nicht"
    )
    erwartet = rohwert_an(FIXTURE.read_bytes(), ABRUZZEN.latitude, ABRUZZEN.longitude)
    assert erwartet > 0, "Die Aufzeichnung traegt dort gar kein Gewitter"
    werte = [dp.lightning_potential_lpi_jkg for dp in reihe.data]
    assert any(w is not None and abs(w - erwartet) < 0.001 for w in werte), (
        f"Kein Zeitpunkt traegt das Blitzpotenzial der Aufzeichnung "
        f"({erwartet}). Angekommen: {werte}"
    )


def test_ac1_gegenprobe_fremde_gewitterfelder_bleiben_leer(monkeypatch):
    """AC-1, Gegenprobe: Given denselben regulaeren Abruf, When ICON-EU
    liefert, Then bleiben das Meteo-France-Feld (`lightning_density_per_km2_3h`)
    und das Hagelfeld (`hail_potential_grau_gsp`) LEER.

    ICON-EU hat gemessen KEIN Hagelsignal (nur `lpi_con_max`), und Blitzdichte
    (Blitze je km^2/3 h, Messwerte 0,1-0,2) ist eine voellig andere Skala als
    Blitzpotenzial (J/kg, bis 269 gemessen). Landete der Wert im falschen Feld,
    meldete jede Auswertung ein tausendfach zu hohes Risiko.
    """
    with hauptquelle_laeuft(monkeypatch, ABRUZZEN), eu_server(monkeypatch) as srv:
        reihe = om.OpenMeteoProvider().fetch_forecast(ABRUZZEN, enrich_ensemble=False)
        assert srv.abrufe, "ICON-EU wurde nie kontaktiert — nichts geprueft"

    fremd = [dp.lightning_density_per_km2_3h for dp in reihe.data
             if dp.lightning_density_per_km2_3h is not None]
    hagel = [dp.hail_potential_grau_gsp for dp in reihe.data
             if dp.hail_potential_grau_gsp is not None]
    assert not fremd, f"ICON-EU hat das Blitzdichte-Feld befuellt: {fremd}"
    assert not hagel, (
        f"Es steht ein Hagelwert da: {hagel} — ICON-EU liefert gar keinen"
    )


# ---------------------------------------------------------------------------
# AC-2 — leer bleibt leer: weder 0 noch ein roher Fehlwert.
# ---------------------------------------------------------------------------

def test_ac2_fehlende_stunde_bleibt_leer_und_wird_nie_null(monkeypatch):
    """AC-2: Given der Dienst liefert fuer EINE Stunde nichts (404), When die
    Signale geholt werden, Then bleibt genau diese Stunde `None`, waehrend die
    uebrigen ihre Werte behalten — eine fehlende Stunde darf weder zur 0
    werden (falsche Entwarnung) noch die ganze Reihe kippen.
    """
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    ende = start + timedelta(hours=4)
    with eu_server(monkeypatch) as srv:
        provider = dwd_eu().DwdEuDirectProvider()
        provider.fetch_thunder_signals_named(ABRUZZEN, start, ende)
        # In der REIHENFOLGE der Abrufe, nicht sortiert: der allererste darf es
        # nicht sein, sonst gilt der Lauf als unveroeffentlicht und der
        # Rueckfall (AC-7) greift — dann fehlt gar keine Stunde mehr.
        angefragt = [ttt for _lauf, ttt in srv.abrufe]
        assert len(set(angefragt)) >= 2, f"Nur {angefragt} angefragt — zu wenig"
        srv.fehlende_zeitschritte = {angefragt[1]}
        srv.abrufe.clear()
        ergebnis = provider.fetch_thunder_signals_named(ABRUZZEN, start, ende)

    for signal, reihe in ergebnis.items():
        leer = [o for o, w in reihe.items() if w is None]
        gefuellt = [w for w in reihe.values() if w is not None]
        assert len(leer) == 1, (
            f"Signal '{signal}': {len(leer)} leere Stunden statt genau einer — "
            f"die fehlende wurde aufgefuellt (dann waere sie 0 und eine falsche "
            f"Entwarnung) oder hat die Reihe mitgerissen. Reihe: {reihe}"
        )
        assert gefuellt, f"Signal '{signal}': die ganze Reihe ist leer — {reihe}"


def test_ac2_als_fehlwert_markierter_bildpunkt_wird_nie_durchgereicht(monkeypatch):
    """AC-2, zweite Haelfte: Given der Dienst liefert eine Rasterdatei, deren
    Bildpunkte als FEHLWERT markiert sind, When die Signale geholt werden,
    Then bleibt jeder Wert `None` — nie 0 und nie die rohe Markierungszahl.

    Warum die Zusage geprueft wird und keine feste Zahl: Die echte
    ICON-EU-Antwort traegt gemessen GAR KEINEN Fehlwert (`dataset.nodata` ist
    `None`, Maske leer, Wertebereich 0..269) — anders als ICON-D2, wo 9999.0
    ausserhalb des Modellgebiets steht. ICON-D2s Zahl wird hier ausdruecklich
    NICHT uebernommen (zweimal war die Analogie falsch: S2a `echotop`,
    S2b -999.0). Geprueft wird deshalb, dass eine ALS FEHLWERT MARKIERTE
    Antwort nicht als Messung durchgereicht wird — stuende die Markierungszahl
    als Blitzpotenzial in der Vorhersage, waere das eine erfundene Extremlage.

    Die Markierungszahl ist BEWUSST weder 9999.0 noch 0: waere sie 9999.0 (der
    ICON-D2-Sentinel), bliebe dieser Test auch dann gruen, wenn der Pruefling
    statt der Markierung wieder eine feste Zahl `== 9999.0` hartcodierte —
    genau der Analogieschluss, den die Spec fuer ICON-EU verbietet. Mit einem
    dienstfremden Wert wird eine solche Regression sichtbar rot.
    """
    markiert = -111.0
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    with eu_server(
        monkeypatch,
        inhalt=lambda lauf, ttt: kunst_raster(markiert, nodata=markiert),
    ) as srv:
        ergebnis = dwd_eu().DwdEuDirectProvider().fetch_thunder_signals_named(
            ABRUZZEN, start, start + timedelta(hours=3)
        )
        assert srv.abrufe, "Der Dienst wurde nie kontaktiert — nichts geprueft"

    alle = [w for reihe in ergebnis.values() for w in reihe.values()]
    assert alle, "Es kam gar kein Eintrag zurueck — der Test prueft dann nichts"
    assert all(w is None for w in alle), (
        f"Es kamen Werte an, obwohl die Antwort nur Fehlwerte trug: "
        f"{sorted({w for w in alle if w is not None})}"
    )


# ---------------------------------------------------------------------------
# AC-3 — fail-soft: ein Ausfall kippt die Vorhersage nie.
# ---------------------------------------------------------------------------

def test_ac3_dauerhafter_serverfehler_kippt_die_vorhersage_nicht(monkeypatch):
    """AC-3: Given ICON-EU antwortet auf JEDEN Abruf mit 503, When eine
    Vorhersage ueber den regulaeren Weg geholt wird, Then kommt sie vollstaendig
    (Temperatur, Wind) und nur das Blitzpotenzial-Feld bleibt leer.
    """
    monkeypatch.setattr(
        dwd_eu().DwdEuDirectProvider._request.retry, "wait", tenacity.wait_none()
    )
    with hauptquelle_laeuft(monkeypatch, ABRUZZEN), \
            eu_server(monkeypatch, status_je_lauf=AlleLaeufe(503)) as srv:
        reihe = om.OpenMeteoProvider().fetch_forecast(ABRUZZEN, enrich_ensemble=False)
        assert srv.abrufe, "Der Dienst wurde nie kontaktiert — nichts geprueft"

    assert reihe.data, "Die Vorhersage ist leer — der Fehler hat sie mitgerissen"
    assert any(dp.t2m_c is not None for dp in reihe.data), (
        "Temperatur fehlt — die Grunddaten wurden vom Gewitter-Fehler beschaedigt"
    )
    assert all(dp.lightning_potential_lpi_jkg is None for dp in reihe.data), (
        "Es steht ein Blitzpotenzial da, obwohl jeder Abruf 503 meldete"
    )


def test_ac3_fehler_vor_der_abrufschleife_wirft_nicht_nach_aussen(monkeypatch):
    """AC-3, isoliert: Given die Lauf-Bestimmung selbst scheitert (also ETWAS
    ausserhalb der Pro-Zeitschritt-Schleife, wo keine der inneren Absicherungen
    greift), When `fetch_thunder_signals_named` DIREKT gerufen wird, Then kommt
    ein leeres Ergebnis zurueck statt einer Ausnahme.

    Der Nachweis geht bewusst NICHT ueber den geteilten Anreicherungsweg:
    `thunder_enrichment` faengt Ausnahmen bereits selbst ab, deshalb bliebe
    jeder Ende-zu-Ende-Test auch dann gruen, wenn die Fail-soft-Zusage DIESES
    Moduls ("wirft NIE") ersatzlos verschwaende. Genau so waere sie bei einer
    kuenftigen isolierten Nutzung (Direktaufruf, anderer Anschluss) lautlos
    weg — und ein Ausfall der Gewitterquelle risse dort die Grundvorhersage
    mit.
    """
    def kracht(_now):
        raise RuntimeError("Lauf-Bestimmung kaputt")

    monkeypatch.setattr(dwd_eu(), "_thunder_run_candidates", kracht)
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    with eu_server(monkeypatch):
        ergebnis = dwd_eu().DwdEuDirectProvider().fetch_thunder_signals_named(
            ABRUZZEN, start, start + timedelta(hours=3)
        )

    assert isinstance(ergebnis, dict), f"Kein Ergebnis-Verzeichnis: {ergebnis!r}"
    assert all(not reihe for reihe in ergebnis.values()), (
        f"Es kamen trotz Fehler Werte zurueck: {ergebnis}"
    )


# ---------------------------------------------------------------------------
# AC-5 — der bestehende Fill-Waechter greift bereits, ohne neue Tabellenzeile.
# ---------------------------------------------------------------------------

def _reihe_ab_naechster_stunde() -> NormalizedTimeseries:
    basis = datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0, tzinfo=None
    ) + timedelta(hours=1)
    punkte = [
        ForecastDataPoint(ts=basis + timedelta(hours=i), t2m_c=15.0, wind10m_kmh=8.0)
        for i in range(6)
    ]
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test", grid_res_km=6.5,
        interp="grid_point",
    )
    return NormalizedTimeseries(meta=meta, data=punkte)


def test_ac5_zweiter_aufruf_auf_dieselbe_reihe_loest_keinen_zweiten_abruf_aus(
    monkeypatch,
):
    """AC-5: Given eine Reihe, die von einem ersten `enrich_thunder`-Aufruf
    bereits Blitzpotenzial aus ICON-EU traegt, When `enrich_thunder` ein
    ZWEITES Mal auf dieselbe Reihe gerufen wird, Then geht KEIN weiterer Abruf
    an den Dienst.

    Beweist zugleich die Spec-Zusage, dass dafuer NICHTS an
    `thunder_enrichment.py` geaendert werden muss: der generalisierte
    Fill-Waechter aus S2b sieht `lightning_potential_lpi_jkg` bereits, weil
    ICON-EU denselben Signal-Schluessel `lpi` benutzt. Gezaehlt werden ABRUFE
    am Dienst, nicht Laufzeit.
    """
    reihe = _reihe_ab_naechster_stunde()
    with eu_server(monkeypatch) as srv:
        enrich_thunder(reihe, ABRUZZEN)
        nach_erstem = len(srv.abrufe)
        gefuellt = [dp.lightning_potential_lpi_jkg for dp in reihe.data
                    if dp.lightning_potential_lpi_jkg is not None]
        enrich_thunder(reihe, ABRUZZEN)
        nach_zweitem = len(srv.abrufe)

    assert nach_erstem >= 1, "Der erste Aufruf hat gar nicht abgerufen"
    assert gefuellt, (
        "Nach dem ersten Aufruf traegt kein Datenpunkt ein Blitzpotenzial — "
        "der zweite Aufruf koennte dann gar nicht gebremst werden"
    )
    assert nach_zweitem == nach_erstem, (
        f"Der zweite Aufruf hat erneut abgerufen ({nach_zweitem} statt "
        f"{nach_erstem}). Jeder Vorhersage-Abruf holt die ICON-EU-Dateien "
        "damit doppelt"
    )


# ---------------------------------------------------------------------------
# AC-10 — keine Stufenbildung, keine Ausgaben-Aenderung in dieser Scheibe.
# ---------------------------------------------------------------------------

def test_ac10_gewitterstufe_aendert_sich_durch_icon_eu_nicht(monkeypatch):
    """AC-10: Given dieselbe Vorhersage einmal MIT ICON-EU-Blitzpotenzial und
    einmal ohne jede Gewitterquelle, When beide ueber den regulaeren Weg
    gebaut werden, Then sind die Gewitterstufen aller Datenpunkte identisch.

    Diese Scheibe liefert nur Rohwerte; die Schwellenlogik baut #1474. Faengt
    hier eine bestehende Einstufung an, das Feld mitzulesen, entstuenden zwei
    konkurrierende Gewitter-Aussagen im selben Briefing (ADR-0025).
    Ergaenzt den bestehenden Renderer-Nachweis
    `test_thunder_raw_signals_do_not_change_outputs.py` (SMS/Stufe bei
    gesetztem `lightning_potential_lpi_jkg`) um den Ende-zu-Ende-Weg.
    """
    with hauptquelle_laeuft(monkeypatch, ABRUZZEN), eu_server(monkeypatch):
        mit = om.OpenMeteoProvider().fetch_forecast(ABRUZZEN, enrich_ensemble=False)
    with hauptquelle_laeuft(monkeypatch, ABRUZZEN):
        monkeypatch.setattr(
            thunder_routing, "thunder_provider_for", lambda lat, lon: None,
        )
        ohne = om.OpenMeteoProvider().fetch_forecast(ABRUZZEN, enrich_ensemble=False)

    assert any(dp.lightning_potential_lpi_jkg is not None for dp in mit.data), (
        "Im Vergleichsfall kam gar kein Blitzpotenzial an — der Test wuerde "
        "zwei identische Laeufe vergleichen und nichts pruefen"
    )
    assert all(dp.lightning_potential_lpi_jkg is None for dp in ohne.data), (
        "Der Gegenfall traegt trotzdem ein Blitzpotenzial"
    )
    assert [dp.thunder_level for dp in mit.data] == [
        dp.thunder_level for dp in ohne.data
    ], (
        "Die Gewitterstufen unterscheiden sich, sobald ICON-EU liefert — das "
        "Blitzpotenzial fliesst in eine bestehende Einstufung ein"
    )
