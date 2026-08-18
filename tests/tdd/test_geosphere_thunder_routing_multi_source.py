"""TDD RED -- #1758 Scheibe B: mehrere Gewitter-Signalquellen je Gebiet
(additiv). GeoSphere-CAPE/CIN entstehen fuer Oesterreich ZUSAETZLICH zum DWD,
ohne ihn zu verdraengen.

Spec: docs/specs/modules/feat_1758_geosphere_cape_cin.md
Abgedeckte ACs hier: AC-6 (Mehrquellen-Zustaendigkeit), AC-7 (Fill-only-
Waechter je Quelle), AC-8 (DWD-Blitzpotenzial bleibt unangetastet).

===========================================================================
RED-GRUND (heute, unveraenderter Code)
===========================================================================
`providers.thunder_routing` hat KEINE Funktion, die MEHRERE zustaendige
Quellen je Gebiet liefert (nur `thunder_provider_for`, first-match-wins,
EINE Quelle). Jeder Test hier ruft entweder direkt `thunder_providers_for`
(existiert nicht -> AttributeError) oder monkeypatcht sie mit `raising=True`
(schlaegt beim Patchen selbst fehl, weil das Attribut fehlt) -- beides ein
praeziser, eindeutiger RED-Grund. Der heutige Fill-only-Waechter in
`enrich_thunder` (`thunder_enrichment.py:222-231`) prueft zudem GLOBAL ueber
ALLE bekannten Felder -- selbst mit einer `thunder_providers_for`-Attrappe
wuerde eine bereits gefuellte DWD-Reihe die zweite Quelle nie erreichen.

Testart: Kern-Schicht, kein Netz -- echte Test-Quellen werden in der echten
Provider-Registry registriert (Muster
`test_thunder_enrichment_fill_guard_generalized.py`).
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
from providers import thunder_enrichment, thunder_routing  # noqa: E402
from providers.thunder_enrichment import enrich_thunder  # noqa: E402

# Karnischer Hoehenweg -- Grundvorhersage kommt von GeoSphere (`at_direct`),
# Gewitter-Zustaendigkeit ist heute `de_direct` (DWD, #1457 S2b AC-10); diese
# Scheibe ergaenzt `geosphere` ZUSAETZLICH, ohne `de_direct` zu verdraengen.
_KARNISCH = Location(latitude=46.66, longitude=12.74, name="Karnischer Hoehenweg")


@contextmanager
def _registrierte_testquelle(name: str, factory):
    """Registriert `factory` temporaer in der ECHTEN Provider-Registry und
    stellt den Vorzustand wieder her (Muster
    test_thunder_enrichment_fill_guard_generalized.py)."""
    import providers.base as base_module

    if not base_module._PROVIDER_FACTORIES:
        base_module._load_providers()
    hatte = name in base_module._PROVIDER_FACTORIES
    vorher = base_module._PROVIDER_FACTORIES.get(name)
    base_module.register_provider(name, factory)
    try:
        yield
    finally:
        if hatte:
            base_module._PROVIDER_FACTORIES[name] = vorher
        else:
            base_module._PROVIDER_FACTORIES.pop(name, None)


def _reihe(**felder_am_ersten_punkt) -> NormalizedTimeseries:
    """Sechs Stunden ab der naechsten vollen Stunde -- dasselbe Zeitraster,
    das `_bezugszeitpunkt` erwartet (Offsets beginnen bei 1)."""
    basis = datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0, tzinfo=None
    ) + timedelta(hours=1)
    punkte = []
    for i in range(6):
        zusatz = felder_am_ersten_punkt if i == 0 else {}
        punkte.append(
            ForecastDataPoint(
                ts=basis + timedelta(hours=i), t2m_c=15.0, wind10m_kmh=8.0, **zusatz
            )
        )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test", grid_res_km=2.2,
        interp="grid_point",
    )
    return NormalizedTimeseries(meta=meta, data=punkte)


class _DwdErsatzBereitsGefuellt:
    """Echte Test-Quelle, die einen DWD-Ersatz simuliert -- zaehlt jeden
    Abruf mit (kein Mock, erfuellt das Protokoll)."""

    abrufe = 0

    @property
    def name(self) -> str:
        return "test_dwd_ersatz_1758"

    def fetch_thunder_signals(self, location, start=None, end=None):
        type(self).abrufe += 1
        return {}

    def fetch_thunder_signals_named(self, location, start=None, end=None):
        type(self).abrufe += 1
        return {"lpi": {h: 48.2 for h in range(1, 7)}}


class _GeosphereErsatz:
    """Echte Test-Quelle, die einen GeoSphere-Ersatz simuliert."""

    abrufe = 0

    @property
    def name(self) -> str:
        return "test_geosphere_ersatz_1758"

    def fetch_thunder_signals(self, location, start=None, end=None):
        return {}

    def fetch_thunder_signals_named(self, location, start=None, end=None):
        type(self).abrufe += 1
        return {
            "cape": {h: 100.0 for h in range(1, 7)},
            "cin": {h: -0.1 for h in range(1, 7)},
        }


# ---------------------------------------------------------------------------
# AC-6 -- Zustaendigkeitsabfrage liefert BEIDE Quellen fuer einen AT-Punkt.
# ---------------------------------------------------------------------------

def test_ac6_at_punkt_hat_beide_gewitterquellen_de_direct_und_geosphere():
    """AC-6: Given einen Ort in Oesterreich innerhalb des AROME-Gitters, When
    die Gewitter-Zustaendigkeit abgefragt wird, Then weist sie BEIDE Quellen
    aus (`de_direct`, `geosphere`) -- nicht nur eine.

    Mutations-Gegenprobe: wuerde `geosphere` aus der Zuordnung entfernt,
    MUSS der `assert set(...) == {...}` unten rot werden -- ein `assert
    "geosphere" in quellen` allein wuerde das nicht zuverlaessig fangen,
    deshalb der exakte Mengenvergleich."""
    quellen = thunder_routing.thunder_providers_for(
        _KARNISCH.latitude, _KARNISCH.longitude
    )
    assert set(quellen) == {"de_direct", "geosphere"}, (
        f"Zustaendigkeit liefert {sorted(quellen)} statt beider Quellen "
        "{'de_direct', 'geosphere'}"
    )
    # Die bestehende Einzel-Abfrage bleibt fuer Bestandsaufrufer unveraendert
    # die PRIMAERE Quelle (Spec Implementation Details 5, Regressionsschutz).
    primaer = thunder_routing.thunder_provider_for(
        _KARNISCH.latitude, _KARNISCH.longitude
    )
    assert primaer == "de_direct", (
        f"thunder_provider_for liefert {primaer!r} statt weiterhin 'de_direct' -- "
        "die additive Erweiterung hat die primaere Zuordnung verschoben"
    )


# ---------------------------------------------------------------------------
# AC-7 -- Fill-only-Waechter je Quelle: eine bereits gefuellte Quelle
# blockiert die ANDERE Quelle nicht mehr.
# ---------------------------------------------------------------------------

def test_ac7_bereits_gefuellte_dwd_quelle_blockiert_geosphere_nicht_mehr(monkeypatch):
    """AC-7: Given ein AT-Punkt, an dem der DWD (`lightning_potential_lpi_jkg`)
    bereits gefuellt hat, When `enrich_thunder` erneut laeuft, Then wird
    `geosphere` TROTZDEM abgerufen und fuellt
    `cape_geosphere_jkg`/`convective_inhibition_geosphere_jkg` -- der
    Fill-only-Waechter bricht nicht mehr GLOBAL ab, sobald irgendeine Quelle
    geliefert hat.

    Mutations-Gegenprobe (Pflicht laut Spec): der ALTE globale Waechter
    (`any(... for feld in _bekannte_felder())`) MUSS diesen Test rot machen,
    wenn er wiederhergestellt wird -- dann sieht er
    `lightning_potential_lpi_jkg` bereits gefuellt und `enrich_thunder`
    kehrt VOR jedem Abruf zurueck; `_GeosphereErsatz.abrufe` bliebe 0.
    """
    _DwdErsatzBereitsGefuellt.abrufe = 0
    _GeosphereErsatz.abrufe = 0
    monkeypatch.setattr(
        thunder_routing, "thunder_providers_for",
        lambda lat, lon: ("test_dwd_ersatz_1758", "test_geosphere_ersatz_1758"),
        raising=True,
    )
    # Simuliert eine vorangegangene Anreicherung: DWD hat bereits geliefert,
    # GeoSphere-Felder sind noch leer.
    reihe = _reihe(lightning_potential_lpi_jkg=48.2)

    with _registrierte_testquelle("test_dwd_ersatz_1758", _DwdErsatzBereitsGefuellt), \
            _registrierte_testquelle("test_geosphere_ersatz_1758", _GeosphereErsatz):
        enrich_thunder(reihe, _KARNISCH)

    assert _DwdErsatzBereitsGefuellt.abrufe == 0, (
        f"DWD-Ersatz wurde {_DwdErsatzBereitsGefuellt.abrufe}x erneut abgerufen, "
        "obwohl sein Feld bereits gefuellt war -- der Waechter greift fuer diese "
        "Quelle nicht"
    )
    assert _GeosphereErsatz.abrufe == 1, (
        f"GeoSphere-Ersatz wurde {_GeosphereErsatz.abrufe}x abgerufen statt genau "
        "einmal -- der globale Fill-Waechter blockiert weiterhin die zweite Quelle, "
        "obwohl DEREN Felder noch leer sind"
    )
    gefuellt = [dp.cape_geosphere_jkg for dp in reihe.data if dp.cape_geosphere_jkg is not None]
    assert gefuellt, (
        "cape_geosphere_jkg wurde trotz erfolgtem Abruf an keinem Datenpunkt gefuellt"
    )


# ---------------------------------------------------------------------------
# AC-8 -- DWD-Blitzpotenzial bleibt unveraendert, GeoSphere schreibt dort nie.
# ---------------------------------------------------------------------------

def test_ac8_lpi_bleibt_identisch_mit_und_ohne_geosphere_in_der_zustaendigkeit(
    monkeypatch,
):
    """AC-8: Given ein AT-Punkt, When die Anreicherung einmal NUR mit DWD und
    einmal mit DWD+GeoSphere in der Zustaendigkeitstabelle laeuft, Then
    traegt `lightning_potential_lpi_jkg` in BEIDEN Laeufen denselben Wert --
    GeoSphere schreibt an keiner Stelle in dieses Feld."""
    _DwdErsatzBereitsGefuellt.abrufe = 0
    _GeosphereErsatz.abrufe = 0
    reihe_nur_dwd = _reihe()
    reihe_beide = _reihe()

    with _registrierte_testquelle("test_dwd_ersatz_1758", _DwdErsatzBereitsGefuellt), \
            _registrierte_testquelle("test_geosphere_ersatz_1758", _GeosphereErsatz):
        monkeypatch.setattr(
            thunder_routing, "thunder_providers_for",
            lambda lat, lon: ("test_dwd_ersatz_1758",), raising=True,
        )
        enrich_thunder(reihe_nur_dwd, _KARNISCH)

        monkeypatch.setattr(
            thunder_routing, "thunder_providers_for",
            lambda lat, lon: ("test_dwd_ersatz_1758", "test_geosphere_ersatz_1758"),
            raising=True,
        )
        enrich_thunder(reihe_beide, _KARNISCH)

    lpi_nur_dwd = [dp.lightning_potential_lpi_jkg for dp in reihe_nur_dwd.data]
    lpi_beide = [dp.lightning_potential_lpi_jkg for dp in reihe_beide.data]
    assert any(v is not None for v in lpi_nur_dwd), (
        "Ohne GeoSphere traegt kein Datenpunkt ueberhaupt ein Blitzpotenzial -- "
        "der Vergleich pruefte nichts"
    )
    assert lpi_nur_dwd == lpi_beide, (
        f"lightning_potential_lpi_jkg unterscheidet sich: nur DWD={lpi_nur_dwd} "
        f"vs. DWD+GeoSphere={lpi_beide} -- GeoSphere hat das Blitzpotenzial-Feld "
        "beeinflusst"
    )
    cape_geo = [dp.cape_geosphere_jkg for dp in reihe_beide.data]
    assert any(v is not None for v in cape_geo), (
        "cape_geosphere_jkg wurde im Zwei-Quellen-Lauf nicht gefuellt -- der "
        "Vergleich bewiese sonst nur einen unveraenderten NICHT-Aufruf"
    )
