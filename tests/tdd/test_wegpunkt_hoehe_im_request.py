"""TDD RED — Issue #1991: Wegpunkt-Höhe an die Open-Meteo-Provider-Anfrage.

Spec: docs/specs/modules/wegpunkt_hoehe_provider.md (AC-1, AC-2, AC-3, AC-5, AC-13)
Context: docs/context/fix-1991-wegpunkt-hoehe.md

Root Cause: `Location.elevation_m` (src/app/config.py:92) ist gefuellt, wird aber
beim Bau der HTTP-Anfrage an Open-Meteo verworfen -- `fetch_forecast` (:973),
`fb_params` (:1175) und `_fetch_ensemble_spread` (:724) bauen `params` nur aus
`latitude`/`longitude`/`hourly`/`timezone`. Open-Meteo rechnet deshalb mit
seiner eigenen, geglaetteten Geländehöhe statt der echten Wegpunkt-Hoehe.

MOCK-FREI (kein Mock()/patch()/MagicMock): der Netzzugriff wird ueber
`httpx.MockTransport` ersetzt (Vorbild `tests/test_provider_tz_normalization.py`)
-- der Prüfling (`OpenMeteoProvider`/`GeoSphereProvider`) setzt einen ECHTEN
`httpx.Request` ab, der Test liest dessen fertig kodierte Query.

AC-Test-Mapping:
| AC    | Testfunktion                                                          |
|-------|------------------------------------------------------------------------|
| AC-1  | test_ac1_wegpunkt_mit_hoehe_traegt_elevation_in_der_anfrage           |
| AC-2  | test_ac2_wegpunkt_ohne_hoehe_traegt_keinen_elevation_parameter        |
| AC-3  | test_ac3_haupt_und_ensemble_anfrage_tragen_beide_die_hoehe            |
| AC-3  | test_ac3_wolken_abruf_ueber_geosphere_kennt_noch_keine_hoehe          |
| AC-5  | test_ac5_gemeldete_modellhoehe_landet_in_meta                        |
| AC-13 | test_ac13_luftqualitaets_abruf_traegt_keine_hoehe_und_liefert_ergebnis|
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qs

import httpx
import json
import tenacity

from app.config import Location
from providers.geosphere import GeoSphereProvider
from providers.openmeteo import OpenMeteoProvider

# Schaufelspitze (Stubai, echte Hoehe 3333 m, faellt in die ICON-D2-Box aus
# providers/region_routing.py bzw. REGIONAL_MODELS: 43-56 lat, 2-18 lon --
# derselbe Endpunkt /v1/dwd-icon, den der Produktivpfad fuer die Alpen waehlt.
_SCHAUFELSPITZE = Location(
    latitude=47.0614, longitude=11.1211, name="Schaufelspitze", elevation_m=3333
)
_SCHAUFELSPITZE_OHNE_HOEHE = Location(
    latitude=47.0614, longitude=11.1211, name="Schaufelspitze", elevation_m=None
)

# Alle bekannten Open-Meteo-Modell-IDs (Vorbild test_provider_tz_normalization.py),
# fuer eine vorausgefuellte Availability-Cache-Datei, die den Auto-Probe-
# Seitenpfad in `fetch_forecast` (WEATHER-05b) ueberspringt.
_OM_ALL_MODEL_IDS = [
    "meteofrance_arome", "icon_d2", "metno_nordic", "icon_eu", "ecmwf_ifs04",
]


def _write_all_available_cache(path: Path) -> None:
    path.write_text(json.dumps({
        "probe_date": date.today().isoformat(),
        "models": {
            mid: {"available": [], "unavailable": []} for mid in _OM_ALL_MODEL_IDS
        },
    }))


def _prepare_provider(monkeypatch, tmp_path) -> OpenMeteoProvider:
    """Availability-Cache vorausfuellen + Retry neutralisieren (Vorbild
    tests/test_provider_tz_normalization.py:184)."""
    cache_path = tmp_path / "model_availability.json"
    _write_all_available_cache(cache_path)
    monkeypatch.setattr("providers.openmeteo.AVAILABILITY_CACHE_PATH", cache_path)
    monkeypatch.setattr(
        "providers.openmeteo.DIAGNOSTICS_PATH", tmp_path / "openmeteo_calls.jsonl"
    )
    monkeypatch.setattr(OpenMeteoProvider._request.retry, "wait", tenacity.wait_none())
    monkeypatch.setattr(
        OpenMeteoProvider._request.retry, "stop", tenacity.stop_after_attempt(1)
    )
    return OpenMeteoProvider()


def _handler(seen: List[httpx.Request], *, elevation_response: Optional[float] = None):
    """Ein Handler fuer ALLE Open-Meteo-Hosts (Haupt, Ensemble, Air-Quality) --
    MockTransport ist host-unabhaengig, das reale `OpenMeteoProvider` waehlt
    den Host selbst ueber `base_host`/`self._ensemble_host`."""

    def _respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        payload: dict = {
            "hourly": {"time": ["2026-08-21T12:00"], "temperature_2m": [5.0]}
        }
        if elevation_response is not None:
            payload["elevation"] = elevation_response
        return httpx.Response(200, json=payload)

    return _respond


def _query(request: httpx.Request) -> dict:
    # AC-2: `keep_blank_values=True` ist PFLICHT -- ein versehentliches
    # `params["elevation"] = None` kodiert httpx zu `elevation=` (Leerstring),
    # und ohne dieses Flag wuerde `parse_qs` genau diesen Leerwert STILL
    # WEGLASSEN -- der Wächter am Wirkort waere blind fuer exakt die Mutation,
    # die AC-2 verbietet.
    return parse_qs(request.url.query.decode(), keep_blank_values=True)


def _main_requests(seen: List[httpx.Request]) -> List[httpx.Request]:
    return [r for r in seen if r.url.host == "api.open-meteo.com"]


# ---------------------------------------------------------------------------
# AC-1
# ---------------------------------------------------------------------------


def test_ac1_wegpunkt_mit_hoehe_traegt_elevation_in_der_anfrage(monkeypatch, tmp_path):
    """AC-1: Wegpunkt mit Hoehe 3333 m -> die abgesetzte HTTP-Anfrage traegt
    `elevation=3333` in der Adresszeile.

    ROT heute: `fetch_forecast` (openmeteo.py:973) baut `params` nur aus
    latitude/longitude/hourly/timezone -- `location.elevation_m` wird nie
    gelesen.
    """
    provider = _prepare_provider(monkeypatch, tmp_path)
    seen: List[httpx.Request] = []
    provider._client = httpx.Client(transport=httpx.MockTransport(_handler(seen)))

    provider.fetch_forecast(_SCHAUFELSPITZE, enrich_ensemble=False)

    main = _main_requests(seen)
    assert main, "kein Hauptvorhersage-Request an api.open-meteo.com beobachtet"
    query = _query(main[0])
    assert query.get("elevation") == ["3333"], (
        f"AC-1: Anfrage muss elevation=3333 tragen, war {query.get('elevation')!r} "
        "-- Location.elevation_m wird beim Params-Bau verworfen "
        "(openmeteo.py:973 baut params nur aus latitude/longitude/hourly/timezone)."
    )


# ---------------------------------------------------------------------------
# AC-2
# ---------------------------------------------------------------------------


def test_ac2_wegpunkt_ohne_hoehe_traegt_keinen_elevation_parameter(monkeypatch, tmp_path):
    """AC-2: Wegpunkt ohne Hoehe (`elevation_m is None`) -> die Anfrage
    enthaelt UEBERHAUPT KEINEN `elevation`-Parameter (Abwesenheit, nicht
    Gleichheit mit Leerstring) und der Abruf liefert weiterhin ein Ergebnis.

    Heute strukturell erfuellt (kein Feld wird je gesendet) -- der Test
    schuetzt die Nicht-Erfindungs-Garantie waehrend AC-1 implementiert wird
    und ist Teil derselben Datei, damit eine kuenftige Regression
    (`params["elevation"] = None`) sofort auffaellt.
    """
    provider = _prepare_provider(monkeypatch, tmp_path)
    seen: List[httpx.Request] = []
    provider._client = httpx.Client(transport=httpx.MockTransport(_handler(seen)))

    result = provider.fetch_forecast(_SCHAUFELSPITZE_OHNE_HOEHE, enrich_ensemble=False)

    main = _main_requests(seen)
    assert main, "kein Hauptvorhersage-Request an api.open-meteo.com beobachtet"
    query = _query(main[0])
    assert "elevation" not in query, (
        f"AC-2: ohne Hoehenangabe darf 'elevation' gar nicht in der Anfrage "
        f"stehen (weder leer noch Platzhalter), war {query.get('elevation')!r}."
    )
    assert result is not None and result.data, (
        "AC-2: der Abruf muss trotzdem ein Ergebnis liefern."
    )


# ---------------------------------------------------------------------------
# AC-3
# ---------------------------------------------------------------------------


def test_ac3_haupt_und_ensemble_anfrage_tragen_beide_die_hoehe(monkeypatch, tmp_path):
    """AC-3: mit eingeschalteter Ensemble-Anreicherung tragen ALLE
    beobachteten Open-Meteo-Anfragen (Haupt UND Ensemble) die Hoehe -- nicht
    nur die erste. Die Luftqualitaets-Anfrage ist bewusst ausgenommen (AC-13,
    eigener Test).

    ROT heute: weder `fetch_forecast`s Haupt-`params` (:973) noch
    `_fetch_ensemble_spread`s `params` (:724) lesen `location.elevation_m`.
    """
    provider = _prepare_provider(monkeypatch, tmp_path)
    seen: List[httpx.Request] = []
    provider._client = httpx.Client(transport=httpx.MockTransport(_handler(seen)))

    start = datetime(2026, 8, 21, 6, tzinfo=timezone.utc)
    end = datetime(2026, 8, 21, 18, tzinfo=timezone.utc)
    provider.fetch_forecast(_SCHAUFELSPITZE, start=start, end=end, enrich_ensemble=True)

    hoehe_pflicht = [
        r for r in seen if r.url.host in ("api.open-meteo.com", "ensemble-api.open-meteo.com")
    ]
    assert len(hoehe_pflicht) >= 2, (
        f"AC-3: erwartet mindestens Haupt- UND Ensemble-Request, beobachtet "
        f"{[r.url.host for r in seen]}"
    )
    fehlend = []
    for request in hoehe_pflicht:
        query = _query(request)
        if query.get("elevation") != ["3333"]:
            fehlend.append((request.url.host, request.url.path, query.get("elevation")))
    assert not fehlend, (
        f"AC-3: diese Open-Meteo-Anfragen tragen NICHT elevation=3333: {fehlend}"
    )


def test_ac3_wolken_abruf_ueber_geosphere_kennt_noch_keine_hoehe(monkeypatch):
    """AC-3 (Wolken-Anteil): `GeoSphereProvider._fetch_openmeteo_clouds`
    (geosphere.py:508) ist die zweite, hartkodierte Open-Meteo-URL ausserhalb
    von `openmeteo.py` -- sie kennt heute weder `Location` noch Hoehe. Der
    Test ruft die kuenftig erwartete Signatur (mit `elevation_m=`) und prueft
    die abgesetzte Anfrage -- geschrieben GEGEN das Zielverhalten, nicht gegen
    den heutigen Fehler (sonst waere der Test nach der Implementierung rot
    statt gruen).

    ROT heute (fehlender Parameter): die Methode nimmt noch kein
    `elevation_m`-Schluesselwort entgegen -- der Aufruf bricht mit `TypeError`
    ab, bevor ueberhaupt eine Anfrage gestellt wird.
    """
    seen: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={
            "hourly": {
                "time": [], "cloud_cover_low": [], "cloud_cover_mid": [], "cloud_cover_high": [],
            }
        })

    provider = GeoSphereProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))

    provider._fetch_openmeteo_clouds(47.0614, 11.1211, hours=1, elevation_m=3333)

    assert seen, "kein Wolken-Request beobachtet"
    query = parse_qs(seen[0].url.query.decode(), keep_blank_values=True)
    assert query.get("elevation") == ["3333"], (
        f"AC-3: der Wolken-Abruf ueber GeoSphere muss elevation=3333 tragen, "
        f"war {query.get('elevation')!r} (geosphere.py:508, hartkodierte URL "
        "ohne Hoehenparameter)."
    )


# ---------------------------------------------------------------------------
# AC-5
# ---------------------------------------------------------------------------


def test_ac5_gemeldete_modellhoehe_landet_in_meta(monkeypatch, tmp_path):
    """AC-5: die Antwort enthaelt `"elevation": 3333.0` (Open-Meteo meldet die
    tatsaechlich verwendete Hoehe zurueck); nach dem Abruf traegt
    `ts.meta.model_elevation_m` diesen Wert.

    ROT heute: `ForecastMeta` (app/models.py:81-95) kennt kein Feld
    `model_elevation_m` -- der Zugriff wirft `AttributeError`. `_parse_response`
    (openmeteo.py) liest `data["elevation"]` heute nicht.
    """
    provider = _prepare_provider(monkeypatch, tmp_path)
    seen: List[httpx.Request] = []
    provider._client = httpx.Client(
        transport=httpx.MockTransport(_handler(seen, elevation_response=3333.0))
    )

    ts = provider.fetch_forecast(_SCHAUFELSPITZE, enrich_ensemble=False)

    assert ts.meta.model_elevation_m == 3333.0, (
        "AC-5: ts.meta.model_elevation_m muss die von der API gemeldete "
        f"Hoehe tragen, war {getattr(ts.meta, 'model_elevation_m', '<fehlt>')!r}."
    )


# ---------------------------------------------------------------------------
# AC-13
# ---------------------------------------------------------------------------


def test_ac13_luftqualitaets_abruf_traegt_keine_hoehe_und_liefert_ergebnis(
    monkeypatch, tmp_path
):
    """AC-13: der Luftqualitaets-Abruf (`_fetch_uv_data`, CAMS-Endpunkt) kennt
    keinen Hoehenparameter -- er laeuft bei einem Wegpunkt MIT Hoehe
    unveraendert und ohne Fehler weiter, OHNE `elevation` in seiner eigenen
    Anfrage.

    Heute strukturell erfuellt (die UV-Anfrage sendet ohnehin nie
    `elevation`) -- der Test schuetzt die Ausnahme waehrend AC-1/AC-3
    implementiert werden: eine versehentliche globale Anwendung des kuenftigen
    Params-Erbauers auf `_fetch_uv_data` (Spec-Ausnahme, `openmeteo.py:807`)
    darf diesen Test rot machen.
    """
    provider = _prepare_provider(monkeypatch, tmp_path)
    seen: List[httpx.Request] = []
    provider._client = httpx.Client(transport=httpx.MockTransport(_handler(seen)))

    start = datetime(2026, 8, 21, 6, tzinfo=timezone.utc)
    end = datetime(2026, 8, 21, 18, tzinfo=timezone.utc)
    result = provider.fetch_forecast(
        _SCHAUFELSPITZE, start=start, end=end, enrich_ensemble=False
    )

    uv_requests = [r for r in seen if r.url.host == "air-quality-api.open-meteo.com"]
    assert uv_requests, "AC-13: kein Luftqualitaets-Request beobachtet"
    query = _query(uv_requests[0])
    assert "elevation" not in query, (
        f"AC-13: der Luftqualitaets-Endpunkt kennt keinen Hoehenparameter -- "
        f"'elevation' darf hier nicht auftauchen, war {query.get('elevation')!r}."
    )
    assert result is not None, "AC-13: der Abruf muss trotzdem ein Ergebnis liefern."
