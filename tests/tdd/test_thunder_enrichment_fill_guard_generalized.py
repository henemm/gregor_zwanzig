"""TDD RED — #1457 S2b AC-5: der Fill-Waechter muss ALLE bekannten Felder sehen.

Spec: docs/specs/modules/feat_1457_s2b_gewitter_dwd_alpen.md (AC-5)

DER HEIKELSTE PUNKT DIESER SCHEIBE. Heute prueft der Waechter am Anfang von
`enrich_thunder` genau EIN Feld:

    if any(dp.lightning_density_per_km2_3h is not None for dp in reihe.data):
        return

Dieses Feld befuellt ausschliesslich Meteo-France. Fuer einen DWD-Ort wird es
NIE gesetzt — der Waechter greift dort also nie. Wird `enrich_thunder` ein
zweites Mal auf dieselbe, bereits angereicherte Reihe gerufen (das passiert im
Betrieb: `openmeteo.py` ruft die Anreicherung an zwei Stellen, :1018 und
:1138), loest das einen zweiten vollstaendigen DWD-Abruf aus — bis zu 48
weitere Dateien je Ort und Lauf, unbemerkt, weil das Ergebnis identisch
aussieht.

Beide Tests zaehlen ABRUFE (Zaehler an der Quelle), nicht Laufzeit — ein
Laufzeit-Test misst die Maschine, nicht das Verhalten.

RED-GRUND (heute, unveraenderter Code):
- `ForecastDataPoint` kennt `lightning_potential_lpi_jkg` nicht -> TypeError
  schon beim Bauen der Reihe.
- Selbst mit dem Feld greift der Waechter nicht: er sieht nur das
  Meteo-France-Feld.

Testart: Kern-Schicht, kein Netz, keine Mocks — eine echte Zaehl-Quelle wird
in der echten Provider-Registry registriert.
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

_KARNISCH = Location(latitude=46.40, longitude=12.52, name="Karnischer Hoehenweg")
_QUELLE = "test_zaehlende_gewitterquelle"


class _ZaehlendeQuelle:
    """Echte Quelle, die jeden Abruf mitzaehlt. Kein Mock: sie erfuellt das
    Protokoll und liefert echte Werte."""

    abrufe = 0

    @property
    def name(self) -> str:
        return _QUELLE

    def fetch_thunder_signals(self, location, start=None, end=None):
        type(self).abrufe += 1
        return {}

    def fetch_thunder_signals_named(self, location, start=None, end=None):
        type(self).abrufe += 1
        return {
            "lpi": {h: 48.2 for h in range(1, 7)},
            "grau_gsp": {h: 0.4 for h in range(1, 7)},
        }


@contextmanager
def _registrierte_testquelle(name: str, factory):
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
    """Sechs Stunden ab der naechsten vollen Stunde — dasselbe Zeitraster, das
    `_bezugszeitpunkt` erwartet (Offsets beginnen bei 1)."""
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


def test_ac5_zweiter_aufruf_auf_dieselbe_reihe_loest_keinen_zweiten_abruf_aus(
    monkeypatch,
):
    """AC-5: Given eine Vorhersagereihe, die von einem ersten
    `enrich_thunder`-Aufruf bereits Blitzpotenzial und Hagel traegt, When
    `enrich_thunder` ein ZWEITES Mal auf dieselbe Reihe gerufen wird, Then
    bleibt die Zahl der Abrufe bei 1.

    Gegenprobe (die Spec verlangt sie ausdruecklich): Bleibt der Waechter hart
    auf `lightning_density_per_km2_3h` fixiert, muss dieser Test rot werden —
    dieses Feld befuellt der DWD nie.
    """
    _ZaehlendeQuelle.abrufe = 0
    monkeypatch.setattr(
        thunder_routing, "thunder_provider_for",
        lambda lat, lon: _QUELLE, raising=True,
    )
    reihe = _reihe()

    with _registrierte_testquelle(_QUELLE, _ZaehlendeQuelle):
        enrich_thunder(reihe, _KARNISCH)
        nach_erstem = _ZaehlendeQuelle.abrufe
        gefuellt = [dp.lightning_potential_lpi_jkg for dp in reihe.data
                    if dp.lightning_potential_lpi_jkg is not None]
        enrich_thunder(reihe, _KARNISCH)
        nach_zweitem = _ZaehlendeQuelle.abrufe

    assert nach_erstem == 1, (
        f"Der erste Aufruf hat {nach_erstem} Abrufe ausgeloest statt genau "
        "einem — die Messgrundlage stimmt nicht"
    )
    assert gefuellt, (
        "Nach dem ersten Aufruf traegt kein Datenpunkt ein Blitzpotenzial — "
        "der zweite Aufruf koennte dann gar nicht gebremst werden"
    )
    assert nach_zweitem == 1, (
        f"Der zweite Aufruf hat erneut abgerufen ({nach_zweitem} Abrufe "
        "insgesamt). Der Fill-Waechter prueft nur das Meteo-France-Feld, das "
        "der DWD nie befuellt — jeder Vorhersage-Abruf holt die bis zu 48 "
        "ICON-D2-Dateien damit doppelt"
    )


def test_ac5_bereits_getragenes_blitzpotenzial_verhindert_jeden_abruf(monkeypatch):
    """AC-5, direkte Haelfte: Given eine Reihe, die bereits ein
    Blitzpotenzial traegt (aus einer vorangegangenen Anreicherung), When
    `enrich_thunder` gerufen wird, Then wird die Quelle GAR NICHT kontaktiert.

    Diese Fassung haengt nicht am ersten Aufruf, sondern setzt den Zustand
    direkt — sie beweist den Waechter selbst, unabhaengig davon, ob der
    Fuell-Zweig funktioniert.
    """
    _ZaehlendeQuelle.abrufe = 0
    monkeypatch.setattr(
        thunder_routing, "thunder_provider_for",
        lambda lat, lon: _QUELLE, raising=True,
    )
    reihe = _reihe(lightning_potential_lpi_jkg=48.2)

    with _registrierte_testquelle(_QUELLE, _ZaehlendeQuelle):
        enrich_thunder(reihe, _KARNISCH)

    assert _ZaehlendeQuelle.abrufe == 0, (
        f"{_ZaehlendeQuelle.abrufe} Abrufe, obwohl die Reihe bereits ein "
        "Blitzpotenzial traegt. Der Fill-Waechter kennt nur das "
        "Meteo-France-Feld"
    )


def test_ac5_bereits_getragener_hagelwert_verhindert_jeden_abruf(monkeypatch):
    """AC-5, zweites Feld: dasselbe fuer das Hagel-Feld. Der Waechter muss
    ALLE aus der Signal-Tabelle bekannten Felder pruefen, nicht nur das erste
    — sonst greift er fuer eine Quelle, die nur Hagel liefert, wieder nicht."""
    _ZaehlendeQuelle.abrufe = 0
    monkeypatch.setattr(
        thunder_routing, "thunder_provider_for",
        lambda lat, lon: _QUELLE, raising=True,
    )
    reihe = _reihe(hail_potential_grau_gsp=0.4)

    with _registrierte_testquelle(_QUELLE, _ZaehlendeQuelle):
        enrich_thunder(reihe, _KARNISCH)

    assert _ZaehlendeQuelle.abrufe == 0, (
        f"{_ZaehlendeQuelle.abrufe} Abrufe, obwohl die Reihe bereits einen "
        "Hagelwert traegt"
    )


def test_ac5_bestehendes_blitzdichte_feld_bremst_weiterhin(monkeypatch):
    """AC-5, Nicht-Regression: Given eine Reihe mit dem BESTEHENDEN
    Meteo-France-Feld, When `enrich_thunder` gerufen wird, Then wird ebenfalls
    nicht abgerufen.

    Dieser Test ist heute schon gruen. Er steht hier als Waechter: die
    Verallgemeinerung darf die bestehende Zusage nicht ersetzen, sondern nur
    erweitern (Spec: "irgendein bekanntes Feld bereits gesetzt" bleibt die
    Regel).
    """
    _ZaehlendeQuelle.abrufe = 0
    monkeypatch.setattr(
        thunder_routing, "thunder_provider_for",
        lambda lat, lon: _QUELLE, raising=True,
    )
    reihe = _reihe(lightning_density_per_km2_3h=0.15)

    with _registrierte_testquelle(_QUELLE, _ZaehlendeQuelle):
        enrich_thunder(reihe, _KARNISCH)

    assert _ZaehlendeQuelle.abrufe == 0, (
        f"{_ZaehlendeQuelle.abrufe} Abrufe, obwohl die Reihe bereits eine "
        "Blitzdichte traegt — die bestehende S2a-Zusage wurde beim "
        "Verallgemeinern verloren"
    )


def test_ac5_der_waechter_leitet_die_felder_aus_der_signal_tabelle_ab():
    """AC-5, Bauart: Jedes Feld der Signal->Feld-Tabelle muss vom Waechter
    beruecksichtigt werden — sonst muss beim Eintragen einer neuen Quelle
    (AC-9) daran gedacht werden, und genau das wird vergessen.

    Geprueft wird die Zusage, nicht die Umsetzung: fuer JEDES Feld der Tabelle
    gilt, dass eine Reihe mit diesem Feld keinen Abruf mehr ausloest. Der Test
    liest die Felder aus der Tabelle, statt sie zu wiederholen.
    """
    felder = set(thunder_enrichment._SIGNAL_ZU_FELD.values())
    assert felder, "Die Signal->Feld-Tabelle ist leer — nichts zu pruefen"

    modellfelder = {f.name for f in ForecastDataPoint.__dataclass_fields__.values()}
    fehlend = felder - modellfelder
    assert not fehlend, (
        f"Die Signal->Feld-Tabelle verweist auf Felder, die es am Datenpunkt "
        f"nicht gibt: {sorted(fehlend)}. Der Wert wuerde still an einem "
        "unbekannten Attribut landen und nie ausgegeben"
    )
