"""TDD RED -- Issue #1992 Amendment: Health-Journal des INCA-spezifischen
Radar-Nowcast-Fallbacks.

Spec: docs/specs/modules/feat_1992_geosphere_health_amendment.md (AC-6, AC-7).
Vorbild: tests/tdd/test_radar_nowcast_health_journal.py (#1581 Scheibe 2).

Deckt hier ab: AC-6 (INCA-Abruf scheitert, eine andere Quelle liefert danach
Frames -> `path="radar_nowcast"`, `outcome="fallback"`, `detail="ICON-D2"` --
NICHT `outcome="ok"`), AC-7 (INCA liefert selbst erfolgreich -> unveraendert
`outcome="ok"`, Regressionsschutz fuer das #1581-Verhalten).

===========================================================================
Kein Mock-Theater
===========================================================================
Der Open-Meteo-Netzzugriff (ICON-D2-Fallback UND der INCA-Konvektions-
Sidecar) wird durch eine Ersatzklasse fuer `httpx.Client` vertreten, die
ECHTE `httpx.Response`-Objekte liefert (Muster `_ScriptedClient`,
tests/unit/test_radar_upstream_failure.py) -- kein `Mock()`. Der
GeoSphere-INCA-Abruf selbst wird gezielt ueber `GeoSphereProvider.
fetch_nowcast` monkeygepatcht (so von der Spec als Testmethode benannt:
"Exception in der internen fetch_nowcast-Kette") -- fuer AC-7 liefert der
Fake ein ECHTES `NormalizedTimeseries`-Objekt statt eines Mock-Rueckgabewerts.
Der Cache ist eine echte `RadarNowcastCacheService`-Instanz, das Journal wird
ECHT geschrieben und als JSONL geparst gelesen.

===========================================================================
Erwartete Rotfaerbung
===========================================================================
AC-6 ist heute rot: `get_nowcast()` unterscheidet INCA-Fallback (Miss +
andere Quelle liefert) heute NICHT von einem gesunden INCA-Abruf -- beide
buchen `outcome="ok"`, weil weder `throttled` noch `data_unavailable`
gesetzt sind. Der Test verlangt `outcome="fallback"`/`detail="ICON-D2"` und
scheitert heute an der falschen `outcome`.

AC-7 ist heute STRUKTURELL GRUEN (Regressionsschutz, bewusst): ein
erfolgreicher INCA-Abruf bucht schon jetzt `outcome="ok"` (#1581). Er bleibt
kein Blindtest -- er wird rot, sobald eine kuenftige Implementierung der
neuen `elif`-Verzweigung (AC-6) den bestehenden Erfolgsfall versehentlich
mit-faengt.

Ausfuehrung:
    uv run pytest tests/tdd/test_radar_inca_fallback_journal.py \
        --disable-socket --allow-unix-socket -v
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import httpx

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pytest  # noqa: E402

from app.models import (  # noqa: E402
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
)
from providers.geosphere import GeoSphereProvider  # noqa: E402
from services.radar_cache import RadarNowcastCacheService  # noqa: E402
from services.radar_service import RadarNowcastService  # noqa: E402

# Wien: innerhalb INCA (46.3-49.1 lat, 9.5-17.2 lon) UND innerhalb ICON_D2
# (44.0-58.0 lat, 2.0-19.0 lon), radar_service.py:32-61 -- AUSSERHALB von
# RADOLAN (lon 16.37 > 15.1), Italien-Radar (lat 48.2 > 47.5) und AROME-FR
# (lon 16.37 > 10.0): einzig INCA- und ICON-D2-Zweig sind erreichbar, genau
# die Kette, die AC-6 braucht. Innsbruck (47.26/11.39) waere UNGEEIGNET --
# liegt zusaetzlich in RADOLAN UND Italien-Radar, beide vor INCA/ICON-D2
# geprueft (_fetch_frames_with_fallback-Reihenfolge).
_LAT, _LON = 48.2, 16.37

_JOURNAL_UNTERPFAD = ("diagnostics", "enrichment_calls.jsonl")


# ---------------------------------------------------------------------------
# Netz-Double fuer den Open-Meteo-Anteil (ICON-D2-Fallback + INCA-Sidecar)
# -- echte httpx.Response-Objekte statt Mock/patch, uebernommen aus
# tests/unit/test_radar_upstream_failure.py.
# ---------------------------------------------------------------------------

_CALL_URLS: List[str] = []
_RESPONDER: list = [None]


def _icon_d2_erfolg(url: str) -> httpx.Response:
    jetzt = datetime.now(timezone.utc)
    times = [
        (jetzt + timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M")
        for m in (15, 30, 45, 60)
    ]
    body = {
        "minutely_15": {
            "time": times,
            "precipitation": [0.0, 0.0, 0.0, 0.0],
            "weather_code": [0, 0, 0, 0],
        }
    }
    return httpx.Response(200, request=httpx.Request("GET", url), json=body)


class _ScriptedClient:
    def __init__(self, *a, **kw) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a) -> bool:
        return False

    def get(self, url, *a, **kw):
        _CALL_URLS.append(url)
        return _RESPONDER[0](url)


@pytest.fixture(autouse=True)
def _swap_http_client(monkeypatch):
    """Netzsperre + Offline-Fixture aus dem Weg raeumen (Muster
    test_radar_nowcast_health_journal.py)."""
    _CALL_URLS.clear()
    _RESPONDER[0] = _icon_d2_erfolg
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    monkeypatch.setattr(httpx, "Client", _ScriptedClient)
    yield
    _CALL_URLS.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _journalpfad() -> Path:
    from app.loader import get_data_root
    return get_data_root().joinpath(*_JOURNAL_UNTERPFAD)


def _zeilen() -> List[dict]:
    pfad = _journalpfad()
    if not pfad.is_file():
        return []
    return [json.loads(z) for z in pfad.read_text().splitlines() if z.strip()]


def _radar_zeilen() -> List[dict]:
    return [z for z in _zeilen() if z.get("path") == "radar_nowcast"]


def _letzte_radar_zeile() -> dict:
    zeilen = _radar_zeilen()
    assert zeilen, (
        f"Keine Journalzeile mit path='radar_nowcast' in {_journalpfad()} "
        f"-- vorhandene Zeilen: {_zeilen()}."
    )
    return zeilen[-1]


def _dienst() -> RadarNowcastService:
    """Immer mit EIGENEM Cache -- der geteilte Prozess-Cache traegt sonst
    Eintraege zwischen Tests weiter (Muster
    test_radar_nowcast_health_journal.py::_dienst)."""
    return RadarNowcastService(cache=RadarNowcastCacheService())


def _inca_wirft(self, lat: float, lon: float):
    """Ersetzt `GeoSphereProvider.fetch_nowcast` -- simuliert eine
    Exception in der internen fetch_nowcast-Kette (Spec-Testmethode fuer
    AC-6), z.B. ein GeoSphere-Ausfall."""
    raise RuntimeError("GeoSphere INCA nicht erreichbar (simuliert)")


def _inca_erfolgreich(self, lat: float, lon: float) -> NormalizedTimeseries:
    """Ersetzt `GeoSphereProvider.fetch_nowcast` mit einem ECHTEN
    Erfolgsergebnis (kein Mock-Rueckgabewert) fuer AC-7."""
    jetzt = datetime.now(timezone.utc)
    meta = ForecastMeta(provider=Provider.GEOSPHERE, model="NOWCAST", grid_res_km=1.0)
    data = [
        ForecastDataPoint(
            ts=jetzt + timedelta(minutes=m), t2m_c=8.0, wind10m_kmh=6.0,
            precip_1h_mm=0.0,
        )
        for m in (15, 30, 45, 60)
    ]
    return NormalizedTimeseries(meta=meta, data=data)


# ---------------------------------------------------------------------------
# AC-6: INCA-Fallback -> outcome="fallback", detail="ICON-D2" (NICHT "ok")
# ---------------------------------------------------------------------------

def test_ac6_inca_fallback_auf_icon_d2_schreibt_fallback_zeile(monkeypatch) -> None:
    assert _radar_zeilen() == [], (
        "Testaufbau: Journal muss vor dem Abruf leer sein."
    )
    monkeypatch.setattr(GeoSphereProvider, "fetch_nowcast", _inca_wirft)

    dienst = _dienst()
    ergebnis = dienst.get_nowcast(_LAT, _LON)

    # Vorbedingung: der INCA-Ausfall hat wirklich zu ICON-D2 durchgereicht.
    assert ergebnis.source == "ICON-D2", (
        f"Testaufbau: erwartete Quelle 'ICON-D2' nach simuliertem "
        f"INCA-Ausfall, bekommen {ergebnis.source!r} -- dann lief nicht "
        f"der erwartete Fallback-Zweig und die Zusicherung unten prueft "
        f"nichts Sinnvolles."
    )
    assert ergebnis.frames, (
        "Testaufbau: der ICON-D2-Fallback lieferte keine Frames."
    )

    zeile = _letzte_radar_zeile()
    assert zeile.get("outcome") == "fallback", (
        f"AC-6: ein INCA-Ausfall mit erfolgreichem Ersatz muss "
        f"outcome='fallback' hinterlassen (NICHT 'ok' -- heute erscheint "
        f"dieser Fall identisch zu einem gesunden INCA-Abruf), bekommen "
        f"{zeile.get('outcome')!r} (ganze Zeile: {zeile})"
    )
    assert zeile.get("detail") == "ICON-D2", (
        f"AC-6: `detail` muss die tatsaechlich verwendete Ersatzquelle "
        f"nennen ('ICON-D2'), bekommen {zeile.get('detail')!r} "
        f"(ganze Zeile: {zeile})"
    )


# ---------------------------------------------------------------------------
# AC-7: INCA erfolgreich -> outcome bleibt "ok" (Regressionsschutz #1581)
# ---------------------------------------------------------------------------

def test_ac7_inca_erfolg_bleibt_ok(monkeypatch) -> None:
    assert _radar_zeilen() == [], (
        "Testaufbau: Journal muss vor dem Abruf leer sein."
    )
    monkeypatch.setattr(GeoSphereProvider, "fetch_nowcast", _inca_erfolgreich)

    dienst = _dienst()
    ergebnis = dienst.get_nowcast(_LAT, _LON)

    # Vorbedingung: es war wirklich der gesunde INCA-Pfad, keine Vertretung.
    assert ergebnis.source == "INCA", (
        f"Testaufbau: erwartete Quelle 'INCA', bekommen {ergebnis.source!r} "
        f"-- dann lief nicht der erwartete Erfolgs-Zweig."
    )

    zeile = _letzte_radar_zeile()
    assert zeile.get("outcome") == "ok", (
        f"AC-7: ein erfolgreicher INCA-Abruf muss weiterhin outcome='ok' "
        f"hinterlassen (Regressionsschutz #1581 -- die neue elif-"
        f"Verzweigung darf den bisherigen Erfolgsfall nicht mit-fangen), "
        f"bekommen {zeile.get('outcome')!r} (ganze Zeile: {zeile})"
    )
    assert zeile.get("outcome") != "fallback", (
        "AC-7: ein erfolgreicher INCA-Abruf darf NICHT als 'fallback' "
        "gebucht werden."
    )


# ---------------------------------------------------------------------------
# Scheibe C (#2218, Eintrag C5-37): LEERE INCA-Antwort ist ein Fallback.
# SPEC: docs/specs/modules/fix_2218_scheibe_c_observability.md (AC-10..AC-12)
#
# Fake nur an der Systemgrenze (GeoSphereProvider.fetch_nowcast); Journal wird
# echt geschrieben und als JSONL gelesen, Warnzeilen ueber caplog.
# ---------------------------------------------------------------------------

import logging  # noqa: E402


def _inca_none(self, lat: float, lon: float):
    """INCA antwortet ohne Zeitreihe."""
    return None


def _inca_ohne_datenpunkte(self, lat: float, lon: float) -> NormalizedTimeseries:
    """INCA antwortet mit Zeitreihe, aber ohne Datenpunkte."""
    meta = ForecastMeta(provider=Provider.GEOSPHERE, model="NOWCAST", grid_res_km=1.0)
    return NormalizedTimeseries(meta=meta, data=[])


def _inca_warnzeilen(caplog) -> list:
    return [
        r.getMessage() for r in caplog.records
        if r.levelno >= logging.WARNING and "inca" in r.getMessage().lower()
    ]


@pytest.mark.parametrize("leere_antwort", [_inca_none, _inca_ohne_datenpunkte])
def test_ac10_leere_inca_antwort_bucht_fallback_und_warnt(
    monkeypatch, caplog, leere_antwort,
) -> None:
    """AC-10: INCA antwortet ohne Zeitreihe bzw. ohne Datenpunkte -> das Journal
    bucht fuer ``radar_nowcast`` den Ausgang ``fallback`` (nicht ``ok``) mit
    der Ersatzquelle als Detail, und im Log steht eine Warnzeile zu INCA."""
    assert _radar_zeilen() == [], "Testaufbau: Journal muss vor dem Abruf leer sein."
    monkeypatch.setattr(GeoSphereProvider, "fetch_nowcast", leere_antwort)

    with caplog.at_level(logging.WARNING):
        ergebnis = _dienst().get_nowcast(_LAT, _LON)

    assert ergebnis.source == "ICON-D2", (
        f"Testaufbau: erwartete Ersatzquelle 'ICON-D2', bekommen {ergebnis.source!r}"
    )
    zeile = _letzte_radar_zeile()
    assert zeile.get("outcome") == "fallback", (
        f"AC-10: leere INCA-Antwort muss outcome='fallback' hinterlassen, "
        f"bekommen {zeile.get('outcome')!r} (ganze Zeile: {zeile})"
    )
    assert zeile.get("detail") == "ICON-D2", zeile
    assert _inca_warnzeilen(caplog), (
        "AC-10: keine Warnzeile zur leeren INCA-Antwort: "
        f"{[r.getMessage() for r in caplog.records]}"
    )


def test_ac11_trockene_inca_antwort_bleibt_ok_ohne_warnung(monkeypatch, caplog) -> None:
    """AC-11 (Gegenprobe): INCA liefert Datenpunkte mit Nullniederschlag ->
    Journal bleibt ``ok``, keine INCA-Warnzeile (trocken ist kein Ausfall)."""
    monkeypatch.setattr(GeoSphereProvider, "fetch_nowcast", _inca_erfolgreich)

    with caplog.at_level(logging.WARNING):
        ergebnis = _dienst().get_nowcast(_LAT, _LON)

    assert ergebnis.source == "INCA", f"Testaufbau: Quelle {ergebnis.source!r}"
    assert _letzte_radar_zeile().get("outcome") == "ok"
    assert not _inca_warnzeilen(caplog), (
        f"AC-11: trockenes Wetter darf nicht warnen: {_inca_warnzeilen(caplog)}"
    )


def test_ac12_offline_fixture_modus_setzt_kein_flag_und_warnt_nicht(
    monkeypatch, caplog, tmp_path,
) -> None:
    """AC-12: im Offline-Fixture-Modus liefert ``_fetch_geosphere_inca`` leise
    ``[]``; das Flag bleibt ungesetzt, es gibt keine Warnzeile, der Provider
    wird gar nicht erst gefragt."""
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(tmp_path))

    def _darf_nicht_laufen(self, lat, lon):
        raise AssertionError("Offline-Modus darf GeoSphere nicht abrufen")

    monkeypatch.setattr(GeoSphereProvider, "fetch_nowcast", _darf_nicht_laufen)
    dienst = _dienst()

    with caplog.at_level(logging.WARNING):
        frames = dienst._fetch_geosphere_inca(_LAT, _LON)

    assert frames == []
    assert dienst._inca_unavailable_this_call is False
    assert not _inca_warnzeilen(caplog), _inca_warnzeilen(caplog)
