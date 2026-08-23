"""TDD RED -- Issue #1658 Scheibe S2: INCA-Fehlerstatus wird nicht mehr
verschluckt.

SPEC: docs/specs/modules/fix_1658_inca_fehlerstatus.md (AC-1 bis AC-5).
Kontext: docs/context/fix-1658-inca-fehlerstatus.md.

===========================================================================
Der Bug (verifiziert, nicht hier neu hergeleitet)
===========================================================================
`GeoSphereProvider.fetch_nowcast()` (`src/providers/geosphere.py:495-496`)
schluckt jeden HTTP-Fehlerstatus des INCA-Nowcast-Abrufs lautlos
(`except httpx.HTTPStatusError: return None`). Der einzige Aufrufer
(`RadarNowcastService._fetch_geosphere_inca`, `radar_service.py:747-749`)
steigt daraufhin ueber einen fruehen `if not ts or not ts.data: return []`
aus, OHNE das bestehende Merkzeichen `_inca_unavailable_this_call` zu
setzen. Die zentrale Buchung (`radar_service.py:534-541`) bucht deshalb
`OUTCOME_OK` statt `OUTCOME_FALLBACK`/`OUTCOME_UNAVAILABLE` -- ein echter
INCA-Ausfall sieht im Health-Journal gesund aus.

===========================================================================
Kein Mock-Theater / AC-5
===========================================================================
Der Netzzugriff wird durch eine Ersatzklasse fuer `httpx.Client` vertreten,
die ECHTE `httpx.Response`-Objekte liefert (Muster `_ScriptedClient`,
`tests/unit/test_radar_upstream_failure.py:83-105`, wiederverwendet in
`tests/tdd/test_radar_nowcast_health_journal.py`) -- kein `Mock()`, kein
`patch()` von Rueckgabewerten. AC-5 verlangt ausdruecklich, dass die
Simulation AUSSCHLIESSLICH auf `httpx`-Ebene erfolgt, NICHT ueber ein
Monkeypatch von `GeoSphereProvider.fetch_nowcast` als Ganzes -- ein solcher
Ersatz spraenge ueber die Schluckstelle hinweg und bewiese den Fix nicht
(siehe `tests/tdd/test_radar_inca_fallback_journal.py`, dort als
"bestehender blinder Waechter" dokumentiert). Diese Datei ersetzt deshalb
NUR `httpx.Client`, nie die Methode selbst -- ein URL-Router im
Antwort-Double unterscheidet GeoSphere- von Open-Meteo-Aufrufen anhand des
tatsaechlichen Endpunkt-Pfads.

Das Journal wird ECHT geschrieben (durch den Pruefling) und als JSONL
gelesen -- `providers.enrichment_health.log_enrichment_call` wird hier
nicht direkt gerufen.

===========================================================================
Testkoordinate
===========================================================================
`_INCA_LAT, _INCA_LON = 48.5, 16.3` (Wiener Becken, Oesterreich) liegt
INNERHALB `_within_inca()`, ausserhalb `_within_radolan()` (lon > 15.1) und
ausserhalb `_within_italy_radar()` (lat > 47.5) sowie `_within_arome_france()`
(lon > 10.0) -- der Abruf laeuft also tatsaechlich ueber den GeoSphere-INCA-
Zweig, OHNE vorher an RADOLAN/Italien-Radar/AROME-FR haengenzubleiben. Die
INCA-Box liegt vollstaendig innerhalb der ICON-D2-Box (`radar_service.py:
58-60` vs. `39-43`) -- nach einem INCA-Fehlschlag faellt die Kette deshalb
zwingend auf den ICON-D2-Zweig durch (AC-1: die "nachgelagerte Quelle").
Eine Assertion unten belegt diese Lage explizit, damit eine kuenftige
Verschiebung der Bounding-Boxen den Test sichtbar bricht statt still am
falschen Zweig vorbeizulaufen.

===========================================================================
Erwartete Rotfaerbung
===========================================================================
AC-1, AC-2: ROT -- ohne die durchgereichte Ausnahme entsteht weder die
Journalzeile mit `outcome='fallback'` noch die Warn-Logzeile mit dem
Statuscode.
AC-3: bereits HEUTE GRUEN (Abgrenzungstest, s. dort) -- muss es nach dem
Fix bleiben.
AC-4: siehe Docstring des jeweiligen Tests unten -- die reine Zeilenzahl
ist strukturell unabhaengig vom Bug (schon heute schreibt der Miss-Zweig
GENAU EINE Zeile, nur mit dem falschen `outcome`). Die eigentliche
Zusicherung dieses Tests ist deshalb an die AC-1-Aussage gekoppelt, s.u.

Ausfuehrung:
    uv run pytest tests/tdd/test_inca_fehlerstatus_journal.py -v
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import httpx
import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from services.radar_cache import RadarNowcastCacheService  # noqa: E402
from services.radar_service import (  # noqa: E402
    RadarNowcastService,
    _within_arome_france,
    _within_inca,
    _within_italy_radar,
    _within_radolan,
)

# Wiener Becken: innerhalb der INCA-Box, ausserhalb RADOLAN/Italien-Radar/
# AROME-FR -- s. Modul-Docstring "Testkoordinate".
_INCA_LAT, _INCA_LON = 48.5, 16.3

assert _within_inca(_INCA_LAT, _INCA_LON), (
    "Testaufbau: die Testkoordinate muss innerhalb der INCA-Box liegen, "
    "sonst laeuft der Abruf nie ueber den GeoSphere-Zweig (AC-1-Vorgabe)."
)
assert not _within_radolan(_INCA_LAT, _INCA_LON), (
    "Testaufbau: die Testkoordinate darf nicht in der RADOLAN-Box liegen, "
    "sonst haengt der Abruf schon vorher bei BrightSky."
)
assert not _within_italy_radar(_INCA_LAT, _INCA_LON), (
    "Testaufbau: die Testkoordinate darf nicht in der Italien-Radar-Box "
    "liegen, sonst ist ARPAE die naechste Quelle statt ICON-D2."
)
assert not _within_arome_france(_INCA_LAT, _INCA_LON), (
    "Testaufbau: die Testkoordinate darf nicht in der AROME-FR-Box liegen, "
    "sonst ist AROME-FR die naechste Quelle statt ICON-D2."
)

_JOURNAL_UNTERPFAD = ("diagnostics", "enrichment_calls.jsonl")


# ---------------------------------------------------------------------------
# Netz-Double: echte httpx.Response-Objekte statt Mock/patch, URL-Router
# unterscheidet GeoSphere (INCA) von Open-Meteo (ICON-D2-Fallback + INCA-
# Sidecar-Konvektionscheck).
# ---------------------------------------------------------------------------

_CALL_URLS: List[str] = []
_GEOSPHERE_RESPONSE: list = [None]  # per Test ueberschrieben
_OPENMETEO_RESPONSE: list = [None]  # per Test ueberschrieben


def _geosphere_error_response(url: str) -> httpx.Response:
    """Echter INCA-Fehlerstatus (500) -- nicht in `RETRY_STATUS_CODES`
    (502/503/504, `geosphere.py:56`), also genau EIN HTTP-Versuch."""
    return httpx.Response(
        500, request=httpx.Request("GET", url),
        json={"error": "Internal Server Error"},
    )


def _geosphere_dry_success_response(url: str) -> httpx.Response:
    """Strukturell gueltige INCA-Antwort, HTTP 200, precip durchgehend 0
    (AC-3: regulaerer "nichts zu melden"-Fall, kein Ausfall)."""
    zeiten = [
        (datetime.now(timezone.utc) + timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M")
        for m in (0, 15, 30)
    ]
    return httpx.Response(
        200, request=httpx.Request("GET", url),
        json={
            "timestamps": zeiten,
            "features": [{
                "properties": {"parameters": {
                    "t2m": {"data": [15.0, 15.0, 15.0]},
                    "ff": {"data": [3.0, 3.0, 3.0]},
                    "fx": {"data": [5.0, 5.0, 5.0]},
                    "rr": {"data": [0.0, 0.0, 0.0]},
                    "pt": {"data": [1, 1, 1]},
                    "rh2m": {"data": [60, 60, 60]},
                }},
            }],
        },
    )


def _openmeteo_dry_success_response(url: str) -> httpx.Response:
    """Gueltige Open-Meteo-minutely_15-Antwort -- bedient sowohl den
    ICON-D2-Fallback (AC-1: "nachgelagerte Quelle liefert") als auch den
    INCA-Sidecar-Konvektionscheck (AC-3, sonst loggt ein fehlschlagender
    Sidecar-Aufruf selbst eine WARNING und verfaelscht den Abgrenzungstest).
    """
    zeiten = [
        (datetime.now(timezone.utc) + timedelta(minutes=m)).isoformat()
        for m in (0, 15, 30)
    ]
    return httpx.Response(
        200, request=httpx.Request("GET", url),
        json={"minutely_15": {
            "time": zeiten,
            "precipitation": [0.0, 0.0, 0.0],
            "weather_code": [0, 0, 0],
        }},
    )


def _responder(url: str) -> httpx.Response:
    """URL-Router: GeoSphere-NOWCAST-Endpunkt vs. jeder Open-Meteo-Aufruf
    (ICON-D2-Fallback UND INCA-Sidecar) -- unterscheidet ausschliesslich
    anhand des tatsaechlichen Endpunkt-Pfads, NIE anhand der aufrufenden
    Methode (AC-5: keine Ersetzung von `fetch_nowcast` selbst)."""
    if "geosphere.at" in url and "nowcast-v1-15min" in url:
        return _GEOSPHERE_RESPONSE[0](url)
    return _OPENMETEO_RESPONSE[0](url)


class _ScriptedClient:
    """Ersetzt `httpx.Client` fuer die Testdauer. Zeichnet jede aufgerufene
    URL auf und beantwortet sie ueber `_responder()` -- immer ein ECHTES
    `httpx.Response`-Objekt, kein Mock. Uebernommen aus
    tests/unit/test_radar_upstream_failure.py."""

    def __init__(self, *a, **kw) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a) -> bool:
        return False

    def get(self, url, *a, **kw):
        _CALL_URLS.append(url)
        return _responder(url)


@pytest.fixture(autouse=True)
def _swap_http_client(monkeypatch):
    _CALL_URLS.clear()
    _GEOSPHERE_RESPONSE[0] = _geosphere_dry_success_response
    _OPENMETEO_RESPONSE[0] = _openmeteo_dry_success_response
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    monkeypatch.setattr(httpx, "Client", _ScriptedClient)
    yield
    _CALL_URLS.clear()


# ---------------------------------------------------------------------------
# Helpers (Testplumbing, bewusst dupliziert statt geteilt -- s. Docstring
# von tests/tdd/test_radar_nowcast_health_journal.py: eine gemeinsame
# Ablage in einer conftest wuerde die Rot-Kopplung zwischen Testdateien ueber
# TESTcode statt ueber den PRUEFLING herstellen).
# ---------------------------------------------------------------------------

def _journalpfad() -> Path:
    """Journalpfad, FRISCH aus der aktuell gesetzten Datenwurzel gebildet
    (Falle #1633 -- eine Modulkonstante baende vor der Testfixture)."""
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
        f"Keine Journalzeile mit path='radar_nowcast' in {_journalpfad()} -- "
        f"vorhandene Zeilen: {_zeilen()}."
    )
    return zeilen[-1]


def _dienst() -> RadarNowcastService:
    """Immer mit EIGENEM Cache -- der geteilte Prozess-Cache
    (`get_shared_radar_cache()`) traegt sonst Eintraege zwischen Tests
    weiter und macht Cache-Treffer/-Fehltreffer nicht mehr steuerbar."""
    return RadarNowcastService(cache=RadarNowcastCacheService())


# ---------------------------------------------------------------------------
# AC-1: INCA-Fehlerstatus + lieferende Ersatzquelle -> outcome='fallback'
# ---------------------------------------------------------------------------

def test_ac1_inca_fehlerstatus_mit_ersatzquelle_bucht_fallback():
    """AC-1: INCA antwortet 500, die naechste Quelle in der Kette
    (ICON-D2) liefert ein gueltiges Ergebnis -> Journalzeile
    outcome='fallback', detail=Name der tatsaechlich verwendeten
    Ersatzquelle ('ICON-D2') -- ausdruecklich NICHT outcome='ok'.

    HEUTE ROT: `fetch_nowcast()` schluckt den 500er und liefert `None`
    (geosphere.py:495-496); der Aufrufer steigt ueber
    `if not ts or not ts.data: return []` aus, OHNE
    `_inca_unavailable_this_call` zu setzen (radar_service.py:747-749) --
    die zentrale Buchung sieht deshalb keinen Ausfall und bucht
    outcome='ok' statt 'fallback'.
    """
    assert _radar_zeilen() == [], "Testaufbau: Journal muss vor dem Abruf leer sein."
    _GEOSPHERE_RESPONSE[0] = _geosphere_error_response
    _OPENMETEO_RESPONSE[0] = _openmeteo_dry_success_response
    dienst = _dienst()

    ergebnis = dienst.get_nowcast(_INCA_LAT, _INCA_LON)

    # Vorbedingung: die Ersatzquelle hat tatsaechlich geliefert -- sonst
    # waere dies der AC-8-Fall (unavailable), nicht AC-1 (fallback).
    assert ergebnis.source == "ICON-D2", (
        f"Testaufbau: erwartet ICON-D2 als tatsaechlich verwendete "
        f"Ersatzquelle, bekommen {ergebnis.source!r} -- entweder liegt die "
        f"Testkoordinate falsch, oder die geskriptete Antwort wird nicht "
        f"als gueltig erkannt."
    )

    zeile = _letzte_radar_zeile()
    assert zeile.get("outcome") == "fallback", (
        f"AC-1: ein INCA-Fehlerstatus MIT lieferender Ersatzquelle muss "
        f"outcome='fallback' hinterlassen, bekommen {zeile.get('outcome')!r} "
        f"(ganze Zeile: {zeile})"
    )
    assert zeile.get("detail") == "ICON-D2", (
        f"AC-1: `detail` muss den Namen der tatsaechlich verwendeten "
        f"Ersatzquelle tragen, bekommen {zeile.get('detail')!r} "
        f"(ganze Zeile: {zeile})"
    )


# ---------------------------------------------------------------------------
# AC-2: Warn-Logzeile enthaelt den HTTP-Statuscode
# ---------------------------------------------------------------------------

def test_ac2_warnzeile_enthaelt_statuscode(caplog):
    """AC-2: derselbe INCA-Fehlerstatus-Fall wie AC-1 -- die Warn-Logzeile
    aus `_fetch_geosphere_inca()` muss den HTTP-Statuscode (hier 500) im
    Text tragen.

    HEUTE ROT: `fetch_nowcast()` faengt den Fehlerstatus VOR dem Aufrufer
    ab und liefert `None` -- der `except Exception`-Block in
    `_fetch_geosphere_inca()` (radar_service.py:766-769), der die
    Warnzeile erzeugt, wird deshalb nie erreicht. Es entsteht ueberhaupt
    keine Warnzeile, der Statuscode-Nachweis schlaegt fehl.
    """
    _GEOSPHERE_RESPONSE[0] = _geosphere_error_response
    _OPENMETEO_RESPONSE[0] = _openmeteo_dry_success_response
    dienst = _dienst()

    caplog.set_level(logging.WARNING, logger="radar_service")
    dienst.get_nowcast(_INCA_LAT, _INCA_LON)

    warn_texte = [
        r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
    ]
    assert any("500" in text for text in warn_texte), (
        f"AC-2: erwartet eine WARNING-Zeile mit dem Statuscode '500', "
        f"tatsaechliche WARNING-Zeilen: {warn_texte}"
    )


# ---------------------------------------------------------------------------
# AC-3: regulaere, niederschlagsfreie Antwort bleibt 'ok' -- ABGRENZUNGSTEST
# ---------------------------------------------------------------------------

def test_ac3_regulaere_trockene_antwort_bleibt_ok_abgrenzungstest(caplog):
    """AC-3 -- ABGRENZUNGSTEST: bereits HEUTE GRUEN und MUSS es nach dem
    Fix bleiben. INCA antwortet regulaer (HTTP 200), strukturell gueltig,
    aber ohne Niederschlag. Das ist die korrekte Auskunft "fuer diesen
    Punkt nichts zu melden" (ADR-0041 Muster B) -- outcome bleibt 'ok',
    KEINE Warnzeile, `_inca_unavailable_this_call` bleibt False.

    Diese Zusicherung trennt den vorliegenden Fix (echter Fehlerstatus)
    von einer regulaeren Leermeldung -- ein Fix, der jede fehlende
    Niederschlagsmeldung als Ausfall werten wuerde, waere selbst ein Bug.

    Positivkontrolle (PFLICHT): derselbe `caplog`-Mechanismus SIEHT im
    AC-2-Fall (`test_ac2_warnzeile_enthaelt_statuscode`) eine WARNING-Zeile
    mit '500' -- die hier gepruefte Abwesenheit ist also kein Blindtest,
    der auch dann gruen waere, wenn caplog grundsaetzlich nichts erfasst.
    """
    assert _radar_zeilen() == [], "Testaufbau: Journal muss vor dem Abruf leer sein."
    _GEOSPHERE_RESPONSE[0] = _geosphere_dry_success_response
    _OPENMETEO_RESPONSE[0] = _openmeteo_dry_success_response
    dienst = _dienst()

    caplog.set_level(logging.WARNING, logger="radar_service")
    ergebnis = dienst.get_nowcast(_INCA_LAT, _INCA_LON)

    # Vorbedingung: es war wirklich der INCA-Erfolgsfall, keine Drosselung
    # oder ein anderer Ausfall.
    assert ergebnis.source == "INCA", (
        f"Testaufbau: erwartet INCA als Quelle, bekommen {ergebnis.source!r}"
    )
    assert ergebnis.data_unavailable is False and ergebnis.throttled is False, (
        f"Testaufbau: erwartet data_unavailable=False/throttled=False, "
        f"bekommen {ergebnis.data_unavailable}/{ergebnis.throttled}"
    )

    zeile = _letzte_radar_zeile()
    assert zeile.get("outcome") == "ok", (
        f"AC-3: eine regulaere, niederschlagsfreie INCA-Antwort muss "
        f"outcome='ok' bleiben, bekommen {zeile.get('outcome')!r} "
        f"(ganze Zeile: {zeile})"
    )

    warn_texte = [
        r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
    ]
    assert warn_texte == [], (
        f"AC-3: eine regulaere, niederschlagsfreie INCA-Antwort darf KEINE "
        f"Warnzeile erzeugen, tatsaechlich: {warn_texte}"
    )


# ---------------------------------------------------------------------------
# AC-4: genau eine neue Journalzeile, kein zweiter Buchungsort
# ---------------------------------------------------------------------------

def test_ac4_genau_eine_neue_journalzeile_bei_korrektem_ausgang():
    """AC-4: derselbe INCA-Fehlerstatus-Fall wie AC-1 -- das Journal
    enthaelt danach GENAU EINE neue Zeile mit path='radar_nowcast', und
    diese eine Zeile traegt den korrekten Ausgang ('fallback').

    Die reine Zeilenzahl (Differenz genau 1) ist fuer sich genommen
    strukturell UNABHAENGIG vom Bug dieser Scheibe: schon heute schreibt
    der Miss-Zweig in `get_nowcast()` (radar_service.py:534-541) genau
    EINE Zeile pro Aufruf -- der Bug veraendert nur deren `outcome`
    (faelschlich 'ok' statt 'fallback'), nicht die Anzahl. Ein reiner
    Zaehltest waere deshalb schon HEUTE gruen und bewiese nichts. Die
    Zusicherung wird erst zum echten Regressionsschutz gegen die von der
    Spec (Implementation Details, Punkt 3) ausdruecklich ausgeschlossene
    Alternative -- ein zweiter Schreibort direkt in `fetch_nowcast()`
    (Snowgrid-Muster) -- indem sie zusaetzlich verlangt, dass die EINE
    verbleibende Zeile den fachlich richtigen Ausgang traegt: eine
    Implementierung, die zwei Zeilen schreibt (eine falsche 'ok'-Zeile aus
    dem alten Aufrufer-Pfad UND eine korrekte 'fallback'-Zeile aus einem
    neuen, direkten Schreibort in `fetch_nowcast()`), faellt hier durch,
    weil dann entweder die Zeilenzahl != 1 waere oder die LETZTE Zeile
    (bei falscher Reihenfolge) den falschen Ausgang traegt.

    HEUTE ROT ueber dieselbe Kette wie AC-1: die eine geschriebene Zeile
    traegt outcome='ok' statt 'fallback'.
    """
    assert _radar_zeilen() == [], "Testaufbau: Journal muss vor dem Abruf leer sein."
    _GEOSPHERE_RESPONSE[0] = _geosphere_error_response
    _OPENMETEO_RESPONSE[0] = _openmeteo_dry_success_response
    dienst = _dienst()

    dienst.get_nowcast(_INCA_LAT, _INCA_LON)

    zeilen_danach = _radar_zeilen()
    assert len(zeilen_danach) == 1, (
        f"AC-4: erwartet genau eine neue radar_nowcast-Zeile, bekommen "
        f"{len(zeilen_danach)}: {zeilen_danach}"
    )
    assert zeilen_danach[0].get("outcome") == "fallback", (
        f"AC-4: die eine verbleibende Zeile muss den korrekten Ausgang "
        f"'fallback' tragen (kein zweiter, widerspruechlicher Buchungsort "
        f"darf sie ueberschreiben oder ersetzen), bekommen "
        f"{zeilen_danach[0].get('outcome')!r} (ganze Zeile: {zeilen_danach[0]})"
    )
