"""TDD RED — Issue #1991: Wegpunkt-Höhe im Kurzfrist-Nowcast (Scheibe S3).

Spec: docs/specs/modules/wegpunkt_hoehe_provider.md (AC-8, AC-9)
Context: docs/context/fix-1991-wegpunkt-hoehe.md (E6)

Root Cause: `RadarNowcastService` führt Koordinaten nur als `lat`/`lon` durch
acht Signaturen (`get_nowcast` bis `_fetch_openmeteo_15`,
radar_service.py:170-490) — die Höhe fehlt dort komplett. Der interne
Open-Meteo-Abruf (`_fetch_openmeteo_15`, :458, hartkodierte f-String-URL)
sendet deshalb nie `elevation`. `RadarNowcastCacheService._key()`
(radar_cache.py:72) bildet den Cache-Schlüssel nur aus
`{lat}_{lon}_{region}` — ebenfalls ohne Höhe.

MOCK-FREI: `httpx.Client` wird für die Testdauer durch `_ScriptedClient`
ersetzt — eine Ersatzklasse, die ECHTE `httpx.Response`-Objekte liefert
(Vorbild `tests/tdd/test_radar_nowcast_health_journal.py`, dort übernommen
aus `tests/unit/test_radar_upstream_failure.py`). Kein `Mock()`/`patch()`.

Beide Tests rufen die AUS SPEC-SICHT künftig erwartete Signatur
`get_nowcast(lat, lon, elevation_m=..., priority=...)` — geschrieben GEGEN
das Zielverhalten, damit sie nach der Implementierung grün werden, statt
rückwärts gegen den heutigen Fehler zu prüfen.

AC-Test-Mapping:
| AC   | Testfunktion                                                       |
|------|----------------------------------------------------------------------|
| AC-8 | test_ac8_nowcast_traegt_hoehe_in_der_anfrage                        |
| AC-9 | test_ac9_gleiche_koordinate_unterschiedliche_hoehe_liefert_unterschiedliche_nowcasts |
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from services.radar_cache import RadarNowcastCacheService  # noqa: E402
from services.radar_service import RadarNowcastService  # noqa: E402

# Atlantik: ausserhalb ALLER Bounding-Boxen (RADOLAN/INCA/ARPAE/AROME-FR/
# ICON-D2, radar_service.py:28-58) -- reiner generischer minutely_15-Zweig,
# GENAU EIN HTTP-Versuch pro get_nowcast()-Aufruf (Vorbild
# tests/tdd/test_radar_nowcast_health_journal.py).
_ATLANTIC_LAT, _ATLANTIC_LON = 35.0, -40.0


# ---------------------------------------------------------------------------
# Netz-Double: echte httpx.Response-Objekte statt Mock/patch
# ---------------------------------------------------------------------------

_CALL_URLS: List[str] = []
_RESPONDER: list = [None]


class _ScriptedClient:
    """Ersetzt `httpx.Client` fuer die Testdauer und beantwortet jeden Abruf
    ueber `_RESPONDER[0]` mit einem ECHTEN `httpx.Response` -- kein Mock.
    Uebernommen aus tests/tdd/test_radar_nowcast_health_journal.py."""

    def __init__(self, *a, **kw) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a) -> bool:
        return False

    def get(self, url, *a, **kw):
        _CALL_URLS.append(url)
        return _RESPONDER[0](url)


def _bald_utc() -> str:
    """N3-Nachbesserung: Zeitstempel relativ zur tatsaechlichen Laufzeit
    (`datetime.now(timezone.utc)`), nicht hart verdrahtet -- `_derive_result`
    (radar_service.py:574) filtert Frames auf das Fenster
    `[self._now_fn(), self._now_fn() + _NOWCAST_HORIZON_MIN]`. Ein fest
    verdrahtetes Datum liegt ausserhalb dieses real-clock-basierten Fensters,
    sobald der Testlauf an einem anderen Tag stattfindet -- der Frame wuerde
    dann herausgefiltert und `intensity_label` faelschlich immer 'Kein
    Niederschlag' liefern, unabhaengig vom angefragten Niederschlag."""
    return (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M")


def _erfolgreiche_antwort(precip_mm_h: float):
    def _responder(url: str) -> httpx.Response:
        return httpx.Response(
            200, request=httpx.Request("GET", url),
            json={
                "minutely_15": {
                    "time": [_bald_utc()],
                    "precipitation": [precip_mm_h / 4.0],  # mm/15min -> *4 = mm/h
                    "weather_code": [61],
                }
            },
        )
    return _responder


@pytest.fixture(autouse=True)
def _swap_http_client(monkeypatch):
    """Netzsperre + Offline-Fixture aus dem Weg raeumen (Vorbild
    test_radar_nowcast_health_journal.py::_swap_http_client)."""
    _CALL_URLS.clear()
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    monkeypatch.setattr(httpx, "Client", _ScriptedClient)
    yield
    _CALL_URLS.clear()


# ---------------------------------------------------------------------------
# AC-8
# ---------------------------------------------------------------------------


def test_ac8_nowcast_traegt_hoehe_in_der_anfrage():
    """AC-8: Given ein Wegpunkt auf 3333 m mit aktivem Kurzfrist-Nowcast /
    When der Nowcast Regen oder Schnee abruft / Then trägt auch diese
    Anfrage die Höhe.

    ROT heute (fehlender Parameter): `RadarNowcastService.get_nowcast()`
    kennt noch kein `elevation_m`-Schlüsselwort -- der Aufruf bricht mit
    `TypeError` ab, bevor überhaupt eine Anfrage gestellt wird.
    """
    _RESPONDER[0] = _erfolgreiche_antwort(precip_mm_h=2.0)
    service = RadarNowcastService(cache=RadarNowcastCacheService(ttl_seconds=300))

    service.get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON, elevation_m=3333)

    assert _CALL_URLS, "kein Open-Meteo-Request beobachtet"
    query = parse_qs(urlparse(_CALL_URLS[0]).query, keep_blank_values=True)
    assert query.get("elevation") == ["3333"], (
        f"AC-8: Nowcast-Anfrage muss elevation=3333 tragen, war "
        f"{query.get('elevation')!r} -- radar_service.py:458 baut die URL "
        "ohne Hoehenparameter (_fetch_openmeteo_15)."
    )


# ---------------------------------------------------------------------------
# AC-9
# ---------------------------------------------------------------------------


def test_ac9_gleiche_koordinate_unterschiedliche_hoehe_liefert_unterschiedliche_nowcasts():
    """AC-9: Given zwei Punkte gleicher Koordinate mit unterschiedlicher
    Höhe / When der Nowcast für beide läuft / Then liefert der
    Zwischenspeicher nicht das Ergebnis des einen für den anderen aus.

    ROT heute (doppelt): `get_nowcast()` kennt noch kein `elevation_m` --
    der ERSTE Aufruf bricht bereits mit `TypeError` ab. Selbst wenn der
    Parameter existierte, wäre `RadarNowcastCacheService._key()`
    (radar_cache.py:72, nur `{lat}_{lon}_{region}`) blind für die Höhe --
    der zweite Aufruf würde den Cache-Eintrag des ersten erben, statt einen
    eigenen Request auszulösen (derselbe Fehler wie AC-7 beim Wetter-Cache,
    hier für den Radar-Cache).
    """
    cache = RadarNowcastCacheService(ttl_seconds=300)
    service = RadarNowcastService(cache=cache)

    _RESPONDER[0] = _erfolgreiche_antwort(precip_mm_h=0.2)
    result_a = service.get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON, elevation_m=3333)

    _RESPONDER[0] = _erfolgreiche_antwort(precip_mm_h=3.5)
    result_b = service.get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON, elevation_m=100)

    assert len(_CALL_URLS) == 2, (
        f"AC-9: erwartet 2 echte Open-Meteo-Requests (eine je Hoehe), "
        f"beobachtet {len(_CALL_URLS)} -- der zweite Aufruf wurde aus dem "
        "hoehenblinden Radar-Cache-Eintrag des ersten bedient "
        "(radar_cache.py:72 ignoriert die Hoehe im Schluessel)."
    )
    assert result_a.intensity_label != result_b.intensity_label, (
        f"AC-9: beide Nowcasts liefern dieselbe Intensitaet "
        f"({result_a.intensity_label!r}) obwohl 3333 m und 100 m angefragt "
        "wurden -- der zweite Abruf hat das Ergebnis des ersten geerbt."
    )
