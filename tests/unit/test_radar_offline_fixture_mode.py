"""Issue #1329, Scheibe C2: Offline-Fixture-Anbindung fuer den Radar-Pfad
(AC-10, AC-11 -- PO-Direktive "Tests duerfen Prod nie belasten").

SPEC: docs/specs/modules/fix_1329_c2_radar_nowcast_cache.md
Ausfuehrung:
    uv run pytest tests/unit/test_radar_offline_fixture_mode.py -v

Kern-Schicht, netzfrei. `GZ_TEST_FIXTURE_DIR` ist ueber die Autouse-Fixture
`tests/conftest.py::_use_fixture_provider` bereits fuer JEDEN nicht
`@pytest.mark.live`-Test gesetzt -- diese Tests setzen es zusaetzlich
EXPLIZIT (Spec-Vorgabe, macht die Bedingung sichtbar statt implizit zu
verlassen).

Tripwire-Technik (kein Mock-Theater -- CLAUDE.md): sowohl `httpx.Client`
als auch die drei Provider-Konstruktoren (`BrightSkyProvider`,
`GeoSphereProvider`, `RadarDPCProvider`) werden per `monkeypatch` (pytest-
Bordmittel) durch Stubs ersetzt, die einen VERSUCH aufzeichnen statt
sofort zu werfen -- `radar_service.py` faengt Exceptions an diesen Stellen
grundsaetzlich breit ab (Fail-soft-Fetch), ein sofortiges `raise` wuerde
dort lautlos geschluckt und die Abwesenheits-Beweisfuehrung waere
wertlos. Die Tests pruefen stattdessen explizit, dass die
Aufzeichnungslisten LEER bleiben.
"""
from __future__ import annotations

import os

import httpx
import pytest

from services.radar_service import RadarNowcastService

# Reale, eindeutig einer einzelnen Quellen-Bounding-Box zugeordnete
# Koordinaten (siehe radar_service.py:27-56).
_RADOLAN_ONLY_LAT, _RADOLAN_ONLY_LON = 52.5, 13.4     # Berlin: RADOLAN, ausserhalb INCA/DPC
_INCA_ONLY_LAT, _INCA_ONLY_LON = 46.5, 13.0           # AT: INCA, ausserhalb RADOLAN
_DPC_ONLY_LAT, _DPC_ONLY_LON = 44.0, 11.0             # IT: DPC, ausserhalb RADOLAN/INCA
# Ausserhalb aller Bounding-Boxen -> reiner open-meteo-Pfad (identisch zu
# test_feature_734_arome_france_nowcast.py).
_PURE_OPENMETEO_LAT, _PURE_OPENMETEO_LON = 35.0, -40.0

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_OPENMETEO_FIXTURE_DIR = os.path.join(_REPO_ROOT, "fixtures", "openmeteo")


# ---------------------------------------------------------------------------
# Tripwires (kein Mock-Theater -- zeichnen Versuche auf statt Werte
# vorzutaeuschen; Abwesenheit ist die eigentliche Aussage)
# ---------------------------------------------------------------------------

_NETWORK_ATTEMPTS: list = []
_PROVIDER_CONSTRUCTION_ATTEMPTS: list[str] = []


class _TripwireHttpClient:
    def __init__(self, *a, **kw) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a) -> bool:
        return False

    def get(self, url, *a, **kw):
        _NETWORK_ATTEMPTS.append(url)
        raise AssertionError(
            "Netzcall-Tripwire (Issue #1329 C2, AC-10): .get() haette "
            "einen echten HTTP-Request an open-meteo ausgeloest, obwohl "
            "GZ_TEST_FIXTURE_DIR gesetzt ist."
        )


def _tripwire_provider_class(label: str):
    class _TripwireProvider:
        def __init__(self, *a, **kw) -> None:
            _PROVIDER_CONSTRUCTION_ATTEMPTS.append(label)
            raise AssertionError(
                f"Konstruktions-Tripwire (Issue #1329 C2, AC-11): {label} "
                "haette im Offline-Modus (GZ_TEST_FIXTURE_DIR gesetzt) "
                "NICHT konstruiert werden duerfen."
            )

    return _TripwireProvider


@pytest.fixture(autouse=True)
def _explicit_offline_mode_and_tripwires(monkeypatch):
    """Setzt `GZ_TEST_FIXTURE_DIR` explizit (Spec-Vorgabe, sichtbar statt
    nur ueber die conftest-Autouse-Fixture verlassen) und blockt jede
    reale Netz-/Provider-Beruehrung waehrend dieser Datei."""
    _NETWORK_ATTEMPTS.clear()
    _PROVIDER_CONSTRUCTION_ATTEMPTS.clear()
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", _OPENMETEO_FIXTURE_DIR)
    monkeypatch.setattr(httpx, "Client", _TripwireHttpClient)

    import providers.brightsky as brightsky_module
    import providers.geosphere as geosphere_module
    import providers.radar_dpc as radar_dpc_module

    monkeypatch.setattr(
        brightsky_module, "BrightSkyProvider", _tripwire_provider_class("BrightSkyProvider")
    )
    monkeypatch.setattr(
        geosphere_module, "GeoSphereProvider", _tripwire_provider_class("GeoSphereProvider")
    )
    monkeypatch.setattr(
        radar_dpc_module, "RadarDPCProvider", _tripwire_provider_class("RadarDPCProvider")
    )
    yield
    _NETWORK_ATTEMPTS.clear()
    _PROVIDER_CONSTRUCTION_ATTEMPTS.clear()


# ---------------------------------------------------------------------------
# AC-10: reiner open-meteo-Pfad nutzt im Offline-Modus die Radar-Fixture,
# macht KEINEN echten httpx-Call.
# ---------------------------------------------------------------------------

def test_pure_openmeteo_path_uses_fixture_no_real_network():
    """AC-10: `GZ_TEST_FIXTURE_DIR` gesetzt, Koordinate ausserhalb aller
    RADOLAN/INCA/DPC-Boxen (reiner open-meteo-Pfad) -- `get_nowcast()` OHNE
    `frame_source` darf KEINEN echten httpx-Call ausloesen und liefert
    trotzdem ein wohldefiniertes Ergebnis aus
    `fixtures/radar/minutely_15.json`. Verdoppelt zugleich den in der Spec
    geforderten Regressionsnachweis fuer den 'Selbstheilenden Nebeneffekt'
    (bestehende Radar-Tests wie `test_feature_761_icon_d2_nowcast.py`, die
    `RadarNowcastService()` ohne `frame_source` konstruieren, laufen nach
    dieser Scheibe automatisch offline)."""
    svc = RadarNowcastService()

    result = svc.get_nowcast(_PURE_OPENMETEO_LAT, _PURE_OPENMETEO_LON)

    assert _NETWORK_ATTEMPTS == [], (
        "AC-10: im Offline-Modus darf _fetch_openmeteo_15 KEINEN echten "
        f"httpx-Call ausloesen, tatsaechliche Versuche: {_NETWORK_ATTEMPTS}"
    )
    assert result.frames, (
        "AC-10: trotz Offline-Modus muss ein wohldefiniertes Ergebnis aus "
        "der Radar-Fixture geliefert werden (kein leeres Ergebnis) -- "
        f"tatsaechlich: {result.frames!r}"
    )


def test_pure_openmeteo_path_fixture_result_has_dry_onset():
    """AC-10 / Known Limitation (a): die ausgelieferte Fixture ist bewusst
    trocken (precip_mm_h=0.0 durchgehend) -- der Offline-Pfad darf daher
    NIE einen falschen Regen-Alarm ausloesen."""
    svc = RadarNowcastService()

    result = svc.get_nowcast(_PURE_OPENMETEO_LAT, _PURE_OPENMETEO_LON)

    assert result.onset_minutes is None, (
        "AC-10: die trockene Radar-Fixture darf NIE einen onset_minutes "
        f"liefern (Schein-Alarm-Schutz), tatsaechlich: {result.onset_minutes}"
    )


# ---------------------------------------------------------------------------
# AC-11: RADOLAN/INCA/DPC werden im Offline-Modus NICHT kontaktiert.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "lat,lon,label",
    [
        (_RADOLAN_ONLY_LAT, _RADOLAN_ONLY_LON, "BrightSkyProvider"),
        (_INCA_ONLY_LAT, _INCA_ONLY_LON, "GeoSphereProvider"),
        (_DPC_ONLY_LAT, _DPC_ONLY_LON, "RadarDPCProvider"),
    ],
)
def test_provider_source_not_contacted_in_offline_mode(lat, lon, label):
    """AC-11: innerhalb der jeweiligen Bounding-Box wird die zustaendige
    Quelle im Offline-Modus NICHT konstruiert -- sofortiger Rueckfall auf
    die naechste Kettenstufe bis zum Fixture-gestuetzten open-meteo-Funnel;
    `result.source` ist NIE die eigentlich zustaendige Primaerquelle."""
    svc = RadarNowcastService()

    result = svc.get_nowcast(lat, lon)

    assert _PROVIDER_CONSTRUCTION_ATTEMPTS == [], (
        f"AC-11: {label} haette bei ({lat},{lon}) im Offline-Modus NICHT "
        f"konstruiert werden duerfen, tatsaechlich: "
        f"{_PROVIDER_CONSTRUCTION_ATTEMPTS}"
    )
    assert result.source not in ("radar", "INCA", "DPC"), (
        f"AC-11: source darf im Offline-Modus nie die Primaerquelle sein "
        f"(war: {result.source!r})"
    )
