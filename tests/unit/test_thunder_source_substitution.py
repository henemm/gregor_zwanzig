"""TDD RED -- #1492 Scheibe 2a: Gewitter-Vertretung auf Anreicherungsebene.

Spec: docs/specs/modules/feat_1492_s2a_thunder_vertretung.md (AC-1..AC-9).
ADR: docs/adr/0047-gewitter-vertretung-zwischen-direktquellen.md.

Deckt hier ab: AC-1, AC-2, AC-4, AC-5, AC-7, AC-8, AC-9 -- die Ebene
`providers.thunder_enrichment` (Orchestrierung + Vertretungstabelle),
geprueft ueber FAKE-Provider, die `providers.base.ThunderSignalProvider`
strukturell erfuellen (kein `Mock()`/`patch()`/`MagicMock`).

AC-3 und AC-6 werden BEWUSST NICHT hier dupliziert, sondern ausschliesslich
in `test_thunder_source_failure_detection.py` (Provider-Ebene) geprueft: auf
Anreicherungsebene sieht diese Datei nur "Fake wirft" oder "Fake liefert
etwas" -- die konkrete Unterscheidung "Gitterrand-Fuellwert vs. echter
Verbindungsfehler" (AC-3) bzw. "ein Zeitpunkt von 24 scheitert" (AC-6) hat
dort ueberhaupt eine Wirkung (echtes GRIB2/HTTP). Ein Fake-Aequivalent waere
von AC-2s Test ("Fake liefert leer, keine Ausnahme") nicht unterscheidbar
und damit redundant/blind.

===========================================================================
Zur "erwarteten Rotfaerbung" -- empirisch nachgemessen, nicht geraten
===========================================================================
Nur Tests, die eine tatsaechliche WIRKUNG der neuen Vertretung verlangen
(ein Feld wird gefuellt, Meta-Felder werden gesetzt), sind heute rot: AC-1,
AC-4, AC-7, AC-9 (dessen Vorbedingung an AC-1 haengt). Tests, die die
ABWESENHEIT einer (heute ohnehin nicht existierenden) Vertretung pruefen,
sind strukturell schon VOR jeder Implementierung gruen -- ohne Mechanismus
passiert per Definition nichts, und "nichts passiert" ist exakt das, was
AC-2/AC-5 dort verlangen. Das gilt genauso fuer AC-8 (Regressions-Waechter,
von der Spec selbst als "wird vermutlich schon gruen sein" erwartet). Jeder
so betroffene Test traegt einen eigenen "Hinweis"-Absatz im Docstring, der
die Mutation nennt, die ihn NACH der Implementierung tatsaechlich rot
machen wuerde -- sonst waere er ein Blindtest, kein Regressions-Test.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location  # noqa: E402
from app.models import (  # noqa: E402
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
)
from providers import base, thunder_enrichment, thunder_routing  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes -- erfuellen providers.base.ThunderSignalProvider strukturell (kein
# Mock/patch/MagicMock). Zwei Formen, analog den beiden echten Providern:
# ---------------------------------------------------------------------------

class _FakeBenannteQuelle:
    """Analog dwd.py/dwd_eu.py: bietet `fetch_thunder_signals_named`."""

    def __init__(
        self, name: str, *, wirft: bool = False,
        signale: Optional[Dict[str, Dict[int, float]]] = None,
    ) -> None:
        self._name = name
        self._wirft = wirft
        self._signale = signale or {}
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    def fetch_thunder_signals(self, location, start=None, end=None):
        return {}

    def fetch_thunder_signals_named(self, location, start=None, end=None):
        self.call_count += 1
        if self._wirft:
            # Referenziert bewusst den NEUEN Typ -- existiert er nicht, ist
            # das der RICHTIGE RED-Grund (fehlender Mechanismus), nicht ein
            # Tippfehler im Test.
            raise base.ThunderSourceUnavailableError(self._name, 1)
        return self._signale


class _FakeSammelQuelle:
    """Analog meteofrance.py: bietet NUR `fetch_thunder_signals_multi`, KEIN
    `fetch_thunder_signals_named` -- der Anreicherungsweg muss dann
    automatisch auf den Sammelweg zurueckfallen (Dispatch-Regel, s.
    `thunder_enrichment._fetch_lightning_density`)."""

    def __init__(
        self, name: str, *, wirft: bool = False,
        werte: Optional[Dict[int, float]] = None,
    ) -> None:
        self._name = name
        self._wirft = wirft
        self._werte = werte or {}
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    def fetch_thunder_signals(self, location, start=None, end=None):
        return {}

    def fetch_thunder_signals_multi(self, locations, start=None, end=None):
        self.call_count += 1
        if self._wirft:
            raise base.ThunderSourceUnavailableError(self._name, 1)
        schluessel = locations[0].name or "?"
        return {schluessel: self._werte}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ORT = Location(latitude=46.40, longitude=12.52, name="Testort")


def _reihe(stunden: int = 4, t2m: float = 12.3, wind: float = 18.0) -> NormalizedTimeseries:
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    data = [
        ForecastDataPoint(ts=start + timedelta(hours=h), t2m_c=t2m, wind10m_kmh=wind)
        for h in range(1, stunden + 1)
    ]
    meta = ForecastMeta(provider=Provider.DWD, model="TEST", grid_res_km=2.2)
    return NormalizedTimeseries(meta=meta, data=data)


def _patch_provider(monkeypatch, mapping: dict) -> None:
    def _get(name):
        if name not in mapping:
            raise base.ProviderNotFoundError(name)
        return mapping[name]
    monkeypatch.setattr(base, "get_provider", _get, raising=True)


def _patch_quelle(monkeypatch, name: str) -> None:
    """Zwingt `thunder_provider_for` auf eine feste Primaerquelle -- entkoppelt
    diese Tests von der Geografie, die AC-8 separat und exakt prueft."""
    monkeypatch.setattr(
        thunder_routing, "thunder_provider_for", lambda lat, lon: name, raising=True,
    )


# ---------------------------------------------------------------------------
# AC-1
# ---------------------------------------------------------------------------

def test_ac1_ausfall_primaerquelle_wird_von_ersatzquelle_aufgefuellt(monkeypatch):
    """AC-1: Primaerquelle (de_direct) wirft bei JEDEM Punkt
    `ThunderSourceUnavailableError`; die Ersatzquelle (eu_direct) liefert
    einen eindeutigen Sentinelwert (42.0). Ausgangswert (None, weil die
    Primaerquelle wirft), Ableitungsquelle (Vertretungstabelle
    de_direct->eu_direct) und Sollwert (42.0 vom Ersatz-Fake) sind drei
    unterscheidbare Groessen -- eine Implementierung, die die Ausnahme nur
    schluckt (heutiges Verhalten), bleibt bei `None` und macht den Test rot.

    RED-Grund (heute): `providers.base.ThunderSourceUnavailableError`
    existiert nicht -- die Primaerquelle kann den Ausfall gar nicht
    signalisieren (AttributeError beim Werfen, unbehandelt bis zu diesem
    Test). Selbst gaebe es den Typ schon: `thunder_routing.
    thunder_vertretung_for` und der neue except-Zweig in
    `_fetch_lightning_density` fehlen komplett -- das Feld bliebe `None`.
    """
    reihe = _reihe()
    primaer = _FakeBenannteQuelle("de_direct", wirft=True)
    ersatz = _FakeBenannteQuelle(
        "eu_direct", signale={"lpi": {h: 42.0 for h in range(1, 5)}},
    )
    _patch_quelle(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer, "eu_direct": ersatz})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    werte = [dp.lightning_potential_lpi_jkg for dp in reihe.data]
    assert any(w == 42.0 for w in werte), (
        f"Erwartet mindestens einen Wert 42.0 (von der Ersatzquelle) -- "
        f"bekommen {werte}. Ohne Vertretung bleibt jeder Wert None."
    )


# ---------------------------------------------------------------------------
# AC-2
# ---------------------------------------------------------------------------

def test_ac2_vertretung_bleibt_aus_bei_leerer_aber_gueltiger_antwort(monkeypatch):
    """AC-2: Primaerquelle liefert ein leeres, aber gueltiges Ergebnis (kein
    Wurf -- "kein Gewitter in Sicht"). Der Ersatz-Fake traegt den
    Sentinelwert 99.0, der bei faelschlicher Vertretung sichtbar wuerde.
    Ausgangswert (None, korrekt leer), Ableitungsquelle (Ersatz-Fake mit
    99.0) und Sollwert (weiterhin None, `call_count == 0`) sind drei
    unterscheidbare Groessen.

    Hinweis (dokumentierte Ausnahme, gemessen -- nicht geraten): dieser Test
    ist bereits HEUTE gruen. Ohne jede Vertretungslogik ruft
    `_fetch_lightning_density` niemals eine zweite Quelle, unabhaengig
    davon, was die erste liefert -- "nichts passiert" ist per Definition
    "die Ersatzquelle wird nicht gerufen". Er bleibt trotzdem kein
    Blindtest: eine kuenftige Implementierung, die "leer ist kein Fehler"
    NICHT von einem echten Ausfall unterscheidet (z. B. jede leere Antwort
    wie AC-1 behandelt), macht GENAU diesen Test rot (`call_count > 0` oder
    ein Wert `!= None`).
    """
    reihe = _reihe()
    primaer = _FakeBenannteQuelle("de_direct", wirft=False, signale={})
    ersatz = _FakeBenannteQuelle(
        "eu_direct", signale={"lpi": {h: 99.0 for h in range(1, 5)}},
    )
    _patch_quelle(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer, "eu_direct": ersatz})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    assert ersatz.call_count == 0, (
        f"Ersatzquelle wurde {ersatz.call_count}x gerufen, obwohl die "
        "Primaerquelle nur leer (nicht fehlerhaft) geantwortet hat."
    )
    werte = [dp.lightning_potential_lpi_jkg for dp in reihe.data]
    assert all(w is None for w in werte), (
        f"Sentinel 99.0 der Ersatzquelle ist durchgesickert: {werte}"
    )


# ---------------------------------------------------------------------------
# AC-4
# ---------------------------------------------------------------------------

def test_ac4_herkunft_wird_in_forecastmeta_vermerkt(monkeypatch):
    """AC-4: nach erfolgreicher Vertretung (AC-1-Szenario) tragen
    `fallback_model`/`fallback_reason`/`fallback_metrics` die Herkunft. Vor
    dem Aufruf sind alle drei Felder leer (`None`/`[]`) -- das ist die
    Gegenprobe der Spec: bleiben sie leer trotz erfolgreicher Vertretung
    (AC-1 gruen, dieser Test rot), ist die Herkunftsangabe nicht verdrahtet.

    RED-Grund: dieselbe fehlende Vertretung wie AC-1 -- ohne sie laeuft der
    Code-Pfad, der die Meta-Felder setzt (Spec Implementation Details
    Punkt 5), nie an.
    """
    reihe = _reihe()
    assert reihe.meta.fallback_model is None
    assert reihe.meta.fallback_reason is None
    assert reihe.meta.fallback_metrics == []

    primaer = _FakeBenannteQuelle("de_direct", wirft=True)
    ersatz = _FakeBenannteQuelle(
        "eu_direct", signale={"lpi": {h: 42.0 for h in range(1, 5)}},
    )
    _patch_quelle(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer, "eu_direct": ersatz})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    assert reihe.meta.fallback_model == "eu_direct", reihe.meta.fallback_model
    assert reihe.meta.fallback_reason == "thunder_source_unavailable", (
        reihe.meta.fallback_reason
    )
    assert "lightning_potential_lpi_jkg" in reihe.meta.fallback_metrics, (
        reihe.meta.fallback_metrics
    )


# ---------------------------------------------------------------------------
# AC-5
# ---------------------------------------------------------------------------

def test_ac5_enrich_thunder_kippt_grundvorhersage_nicht_wenn_beide_quellen_scheitern(
    monkeypatch,
):
    """AC-5: Primaer- UND Ersatzquelle scheitern beide (zwei Fakes, beide
    werfen `ThunderSourceUnavailableError`). Geprueft wird ueber den
    PRODUKTIV verdrahteten Aufrufer `enrich_thunder()`, nicht ueber
    `_fetch_lightning_density` direkt -- sonst waere nicht bewiesen, dass
    der aeussere Fang (`thunder_enrichment.py:157-160`) tatsaechlich greift.

    Gegenprobe: entfernte man den aeusseren `try/except` oder liesse die
    neue Ausnahme ihn umgehen, wuerde dieser Test mit einer unbehandelten
    Exception abbrechen statt gruen zu laufen.

    Hinweis (dokumentierte Ausnahme, gemessen): dieser Test ist bereits
    HEUTE gruen -- der bestehende `except Exception:` in `enrich_thunder()`
    schluckt JEDE Ausnahme, auch den `AttributeError`, der heute entsteht,
    weil `base.ThunderSourceUnavailableError` noch nicht existiert. Er
    bleibt kein Blindtest: eine kuenftige Aenderung, die diesen Fang
    entfernt oder die neue Ausnahme daran vorbeileitet, macht IHN rot
    (unbehandelte Exception statt eines sauberen Testendes) -- exakt die in
    der Spec beschriebene Gegenprobe.
    """
    reihe = _reihe(stunden=4, t2m=12.3, wind=18.0)
    t2m_vorher = [dp.t2m_c for dp in reihe.data]
    wind_vorher = [dp.wind10m_kmh for dp in reihe.data]

    primaer = _FakeBenannteQuelle("de_direct", wirft=True)
    ersatz = _FakeBenannteQuelle("eu_direct", wirft=True)
    _patch_quelle(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer, "eu_direct": ersatz})

    thunder_enrichment.enrich_thunder(reihe, _ORT)  # darf NICHT werfen

    assert [dp.t2m_c for dp in reihe.data] == t2m_vorher
    assert [dp.wind10m_kmh for dp in reihe.data] == wind_vorher
    assert all(dp.lightning_potential_lpi_jkg is None for dp in reihe.data)
    assert all(dp.lightning_density_per_km2_3h is None for dp in reihe.data)


# ---------------------------------------------------------------------------
# AC-7
# ---------------------------------------------------------------------------

def test_ac7_messgroessenwechsel_schreibt_ins_feld_der_ersatzquelle(monkeypatch):
    """AC-7: `fr_direct` scheitert (Fake wirft aus
    `fetch_thunder_signals_multi`), `eu_direct` liefert einen gueltigen
    lpi-Wert. Beide Felder werden explizit geprueft -- eine Implementierung,
    die den Ersatzwert faelschlich in `lightning_density_per_km2_3h`
    schriebe (Feld der Primaerquelle statt der Ersatzquelle), macht diesen
    Test rot, weil `None` erwartet, aber ein Wert vorgefunden wuerde.

    RED-Grund: `thunder_vertretung_for("fr_direct")` existiert nicht.
    """
    reihe = _reihe()
    primaer = _FakeSammelQuelle("fr_direct", wirft=True)
    ersatz = _FakeBenannteQuelle(
        "eu_direct", signale={"lpi": {h: 55.0 for h in range(1, 5)}},
    )
    _patch_quelle(monkeypatch, "fr_direct")
    _patch_provider(monkeypatch, {"fr_direct": primaer, "eu_direct": ersatz})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    dichte = [dp.lightning_density_per_km2_3h for dp in reihe.data]
    potenzial = [dp.lightning_potential_lpi_jkg for dp in reihe.data]
    assert all(w is None for w in dichte), (
        f"Der Ersatzwert landete im Feld der Primaerquelle: {dichte}"
    )
    assert any(w == 55.0 for w in potenzial), (
        f"Der Ersatzwert kam nicht im eigenen Feld an: {potenzial}"
    )


# ---------------------------------------------------------------------------
# AC-8 -- Regressions-Waechter
# ---------------------------------------------------------------------------

def test_ac8_primaerauswahl_und_regionstabelle_bleiben_unveraendert():
    """AC-8: die neue Vertretungstabelle darf die first-match-wins-
    Primaerauswahl nicht anfassen. Referenzkoordinaten wie in
    `feat_1457_s2c_icon_eu_luekenfueller.md` AC-8 (Korsika -> fr_direct,
    Zugspitze -> de_direct), PLUS eine Pruefung, dass `_REGIONS` objektidentisch
    mit dem Stand vor dieser Scheibe bleibt.

    Erwartet GRUEN bereits heute (kein Mechanismus dieser Scheibe beruehrt
    `_REGIONS`/`thunder_provider_for`) -- ein Regressions-Waechter, kein
    RED-Nachweis; die Spec selbst erwartet das ausdruecklich so.

    Gegenprobe: wuerde `_VERTRETUNG` versehentlich in `_REGIONS` verschmolzen
    oder `_REGIONS` umsortiert, wird dieser Test rot.
    """
    korsika = thunder_routing.thunder_provider_for(42.0, 9.0)
    zugspitze = thunder_routing.thunder_provider_for(47.42, 10.98)
    assert korsika == "fr_direct", korsika
    assert zugspitze == "de_direct", zugspitze

    erwartete_regionen = (
        ("FR", 41.3, 51.1, -5.2, 9.7, "fr_direct"),
        ("DE_ALPEN", 43.17, 58.09, -3.95, 20.35, "de_direct"),
        ("EU_REST", -90.0, 90.0, -180.0, 180.0, "eu_direct"),
    )
    ist_regionen = tuple(tuple(r) for r in thunder_routing._REGIONS)
    assert ist_regionen == erwartete_regionen, ist_regionen


# ---------------------------------------------------------------------------
# AC-9
# ---------------------------------------------------------------------------

def test_ac9_hagelrohsignal_bleibt_none_trotz_erfolgreicher_vertretung(monkeypatch):
    """AC-9: nach erfolgreicher Vertretung (AC-1-Szenario) bleibt
    `hail_potential_grau_gsp` an JEDEM betroffenen Datenpunkt `None` --
    nicht `0.0`, kein aus dem Blitzpotenzial abgeleiteter Platzhalter. Die
    Vorbedingung (mindestens ein lpi-Wert wurde tatsaechlich gefuellt) ist
    ABSICHTLICH Teil der Zusicherung: ohne sie wuerde der Test auch dann
    gruen laufen, wenn die Vertretung UEBERHAUPT nichts tut (beide Felder
    bleiben dann trivial `None`) -- das waere kein Nachweis von irgendetwas.

    RED-Grund heute: dieselbe fehlende Vertretung wie AC-1 -- die
    Vorbedingung (mindestens ein lpi-Wert gefuellt) schlaegt fehl, weil kein
    Wert gefuellt wird. Der Test ist damit fuer die RICHTIGE Vorbedingung
    rot, nicht "zufaellig" durch einen Tippfehler.
    """
    reihe = _reihe()
    primaer = _FakeBenannteQuelle("de_direct", wirft=True)
    ersatz = _FakeBenannteQuelle(
        "eu_direct", signale={"lpi": {h: 42.0 for h in range(1, 5)}},
    )
    _patch_quelle(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer, "eu_direct": ersatz})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    gefuellte_lpi_punkte = [
        dp for dp in reihe.data if dp.lightning_potential_lpi_jkg is not None
    ]
    assert gefuellte_lpi_punkte, (
        "Vorbedingung verletzt: kein Datenpunkt traegt einen lpi-Wert -- "
        "ohne erfolgreiche Vertretung (AC-1) prueft dieser Test nichts."
    )
    assert all(dp.hail_potential_grau_gsp is None for dp in gefuellte_lpi_punkte), (
        f"hail_potential_grau_gsp wurde befuellt: "
        f"{[dp.hail_potential_grau_gsp for dp in gefuellte_lpi_punkte]}"
    )


# ---------------------------------------------------------------------------
# Nachtraege aus der Mutations-Gegenprobe (Adversary-Fund, nicht Teil der
# urspruenglichen 13 RED-Tests, s. `docs/specs/modules/feat_1492_s2a_thunder_vertretung.md`
# Known Limitations 3 bzw. Implementation Details Punkt 4/5). Beide Luecken
# wurden durch eine echte Mutation nachgewiesen: die 13 Bestandstests blieben
# gruen, obwohl der jeweilige Schutz vollstaendig entfernt war.
# ---------------------------------------------------------------------------

def test_l1_merge_schutz_laesst_bereits_gesetzten_fallback_model_unangetastet(
    monkeypatch,
):
    """Luecke 1 (WICHTIGER Mutations-Fund): der Merge-Schutz in
    `_fetch_lightning_density` (thunder_enrichment.py:286, Spec Known
    Limitations 3 + Implementation Details Punkt 5) darf
    `fallback_model`/`fallback_reason` NIE ueberschreiben, wenn dort schon
    ein Wert steht -- typischerweise der Vermerk eines
    Grundvorhersage-Fallbacks (#1115/ADR-0018). Ohne diesen Schutz wuerde
    die Gewitter-Vertretung den Vermerk eines FRUEHEREN Ausfalls
    ueberschreiben und damit unsichtbar machen -- genau die Kaschierung,
    die ADR-0018 verbietet und auf die sich ADR-0047 stuetzt.

    🔴 Die beiden Namen (bereits gesetzter `fallback_model`-Wert vs. Name
    der Gewitter-Ersatzquelle) MUESSEN unterscheidbar sein -- sonst koennte
    dieser Test "ueberschrieben" nicht von "unangetastet" unterscheiden
    (dieselbe Blindheit wie in Scheibe 1: Ausgangswert, Ableitungsquelle
    und Sollwert muessen drei unterscheidbare Groessen sein). Deshalb hier
    bewusst "icon_eu" (fiktiver, bereits gesetzter Grundvorhersage-Fallback)
    gegen "eu_direct" (Gewitter-Ersatzquelle, real aus der Vertretungstabelle
    de_direct -> eu_direct) -- NIEMALS spaeter "vereinfachen" und beide
    gleich waehlen, sonst wird dieser Test wieder blind.

    Gemessene Wirkung der Mutation (`if reihe.meta.fallback_model is None:`
    -> `if True:`): `fallback_model` wird auf "eu_direct" ueberschrieben,
    `fallback_reason` auf "thunder_source_unavailable" -- der
    urspruengliche Grundvorhersage-Fallback-Vermerk verschwindet spurlos.
    """
    reihe = _reihe()
    reihe.meta.fallback_model = "icon_eu"
    reihe.meta.fallback_reason = "model_unavailable"

    primaer = _FakeBenannteQuelle("de_direct", wirft=True)
    ersatz = _FakeBenannteQuelle(
        "eu_direct", signale={"lpi": {h: 42.0 for h in range(1, 5)}},
    )
    _patch_quelle(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer, "eu_direct": ersatz})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    assert reihe.meta.fallback_model == "icon_eu", (
        f"Merge-Schutz gebrochen: fallback_model wurde ueberschrieben "
        f"({reihe.meta.fallback_model!r} statt 'icon_eu')."
    )
    assert reihe.meta.fallback_reason == "model_unavailable", (
        f"Merge-Schutz gebrochen: fallback_reason wurde ueberschrieben "
        f"({reihe.meta.fallback_reason!r} statt 'model_unavailable')."
    )
    assert "lightning_potential_lpi_jkg" in reihe.meta.fallback_metrics, (
        "fallback_metrics haette trotz Merge-Schutz weiter befuellt werden "
        f"muessen: {reihe.meta.fallback_metrics}"
    )


def test_l2_kein_zweiter_abruf_wenn_eu_direct_keine_vertretung_hat(monkeypatch):
    """Luecke 2 (kleinerer Mutations-Fund): `eu_direct` hat laut der echten
    Vertretungstabelle (`thunder_routing._VERTRETUNG["eu_direct"] is None`,
    von mir gegen die unveraenderte Tabelle ausgefuehrt) KEINE Ersatzquelle.
    Faellt `eu_direct` als PRIMAERQUELLE selbst aus, darf ueberhaupt kein
    Ersatzabruf versucht werden -- der `ersatz is None`-Schutz in
    `_fetch_lightning_density` (thunder_enrichment.py:251) muss das
    verhindern, BEVOR `get_provider(...)` fuer die (nicht existierende)
    Ersatzquelle ueberhaupt aufgerufen wird.

    `thunder_routing.thunder_vertretung_for` wird HIER bewusst NICHT
    gemockt -- die reale Zustaendigkeit "eu_direct hat keine Vertretung"
    ist der Kern dieses Tests, nur `thunder_provider_for` (Primaerauswahl,
    AC-8 prueft die separat) wird wie ueblich auf "eu_direct" fixiert.

    Ein unter dem Schluessel `None` registrierter Fake macht einen
    sonst nicht beobachtbaren zweiten Abrufversuch sichtbar: ohne diesen
    Fake wuerde `get_provider(None)` mit dem echten, unveraenderten
    `providers.base.get_provider` eine `ProviderNotFoundError` werfen, die
    beim produktiven Aufrufer `enrich_thunder()` vom AEUSSEREN Fang
    geschluckt wird (fail-soft, von mir so nachvollzogen) -- "kein
    Absturz" ist dadurch schon heute unterschiedslos wahr und kann die
    Mutation allein NICHT zeigen. Ein Test, der nur "Felder sind leer"
    prueft, waere ebenso wertlos: leer sind sie AUCH, wenn ein sinnloser
    Ersatzabruf stattfand und (weil `eu_direct` als Provider-Name nicht
    existiert) nichts lieferte. Entscheidend ist ausschliesslich der
    Aufrufzaehler des unter `None` registrierten Fakes.

    `bereits_befragt="fr_direct"` ist bewusst NICHT `None` gewaehlt: die
    Mutation lautet `if ersatz is None or ersatz == bereits_befragt:` ->
    `if ersatz == bereits_befragt:`. Waere `bereits_befragt` ebenfalls
    `None`, wuerde `None == None` weiterhin `True` liefern und die Mutation
    zufaellig "durchrutschen" -- der Test muesste sie dann NICHT fangen,
    obwohl der Schutz de facto weg ist.

    Gemessene Wirkung der Mutation: `ersatz` bleibt `None`,
    `None == "fr_direct"` ist `False` -- die Bedingung greift nicht mehr,
    `_hole_eintraege(None, ...)` wird aufgerufen, `get_provider(None)`
    liefert (durch die Registrierung) den Fake zurueck, dessen
    `fetch_thunder_signals_named` aufgerufen wird und `call_count` auf 1
    hochzaehlt.
    """
    reihe = _reihe()
    primaer = _FakeBenannteQuelle("eu_direct", wirft=True)
    dummy_falls_aufgerufen = _FakeBenannteQuelle(
        "kein-provider-sollte-diesen-namen-tragen",
        signale={"lpi": {h: 77.0 for h in range(1, 5)}},
    )
    _patch_quelle(monkeypatch, "eu_direct")
    _patch_provider(
        monkeypatch, {"eu_direct": primaer, None: dummy_falls_aufgerufen},
    )

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, "fr_direct")

    assert dummy_falls_aufgerufen.call_count == 0, (
        f"Ein zweiter Abrufversuch fand statt ({dummy_falls_aufgerufen.call_count}x), "
        "obwohl eu_direct laut Vertretungstabelle keine Ersatzquelle hat."
    )
    werte = [dp.lightning_potential_lpi_jkg for dp in reihe.data]
    assert all(w is None for w in werte), (
        f"Sentinel 77.0 einer nicht-existenten Ersatzquelle ist durchgesickert: {werte}"
    )


# ---------------------------------------------------------------------------
# Adversary #1492 S2a, Runde F002 (MEDIUM): Gitterrand-Fall auf der
# ERSATZQUELLE. Der Waechter `if not gefuellt: return`
# (thunder_enrichment.py:270-271) hat bisher keinen Test, der ihn beim
# Entfernen rot machen wuerde.
# ---------------------------------------------------------------------------

def test_f002_ersatzquelle_liefert_nur_none_werte_setzt_keine_fallback_meta(
    monkeypatch,
):
    """F002: die Ersatzquelle antwortet ERFOLGREICH (kein Wurf) und hat
    fuer ihr Signal auch Zeitpunkte im Antwortdict -- aber JEDER Wert darin
    ist `None` (Gitterrand-Fall auf der Ersatzquelle selbst, analog AC-3 auf
    der Primaerquelle). Ohne den Fuell-Waechter (`if not gefuellt: return`,
    thunder_enrichment.py:270-271) wuerden `fallback_model`/`fallback_reason`/
    `fallback_metrics` trotzdem gesetzt -- ein irrefuehrender Zustand: das
    System behauptete eine erfolgreiche Vertretung, obwohl NULL Zeitpunkte
    tatsaechlich befuellt wurden.

    Abgrenzung zu AC-2 (dortiger Test): AC-2 prueft eine LEERE Antwort
    ({}), die den frueheren Wachposten bei Zeile 256 (`if not any(werte ...)`)
    bereits abfaengt, BEVOR die Schleife ueberhaupt startet. Hier ist die
    Antwort NICHT leer (das Dict hat Eintraege je Stunde) -- sie besteht nur
    ausschliesslich aus `None`-Werten. Das ist ein STRUKTURELL ANDERER Pfad:
    Zeile 256 laesst diese Antwort passieren (das werte-Dict ist truthy),
    die Schleife laeuft durch, `gefuellt` bleibt aber 0, weil `if wert is
    None: continue` (Zeile 263-264) jeden einzelnen Eintrag ueberspringt.
    Nur der Waechter bei Zeile 270-271 verhindert danach das faelschliche
    Setzen der Meta-Felder.

    Gemessene Wirkung der Mutation (Entfernen von
    `if not gefuellt:\\n    return`): der Code laeuft ungebremst bis Zeile
    283 durch und setzt `fallback_model`/`fallback_reason`/`fallback_metrics`
    trotz `gefuellt == 0`.
    """
    reihe = _reihe()
    primaer = _FakeBenannteQuelle("de_direct", wirft=True)
    ersatz = _FakeBenannteQuelle(
        "eu_direct", signale={"lpi": {h: None for h in range(1, 5)}},
    )
    _patch_quelle(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer, "eu_direct": ersatz})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    assert ersatz.call_count == 1, (
        "Vorbedingung verletzt: Ersatzquelle wurde nicht (oder mehrfach) "
        f"gerufen ({ersatz.call_count}x) -- ohne genau einen Aufruf prueft "
        "dieser Test den Gitterrand-Fall der Ersatzquelle nicht."
    )
    werte = [dp.lightning_potential_lpi_jkg for dp in reihe.data]
    assert all(w is None for w in werte), (
        f"Signalfeld wurde trotz reiner None-Antwort befuellt: {werte}"
    )
    assert reihe.meta.fallback_model is None, (
        f"fallback_model faelschlich gesetzt: {reihe.meta.fallback_model!r} "
        "-- die Ersatzquelle hat NULL Zeitpunkte tatsaechlich befuellt."
    )
    assert reihe.meta.fallback_reason is None, (
        f"fallback_reason faelschlich gesetzt: {reihe.meta.fallback_reason!r}"
    )
    assert reihe.meta.fallback_metrics == [], (
        f"fallback_metrics faelschlich befuellt: {reihe.meta.fallback_metrics}"
    )
