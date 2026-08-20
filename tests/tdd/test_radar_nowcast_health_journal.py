"""TDD RED -- Issue #1581 Scheibe 2: Health-Journal des Radar-Nowcast.

Spec: docs/specs/modules/fix_1581_enrichment_health.md (AC-8, AC-9, AC-10).
Kontext: docs/context/fix-1581-anreicherung-health.md.

Deckt hier ab: AC-8 (echter Anbieterausfall -> `unavailable`), AC-9 (ein
vollstaendig aus dem Cache bedienter Aufruf erzeugt KEINE Zeile), AC-10
(eigene Budget-Drosselung -> `self_throttled`, unterscheidbar vom
Anbieterausfall).

===========================================================================
Kein Mock-Theater
===========================================================================
Der Netzzugriff wird durch eine Ersatzklasse fuer `httpx.Client` vertreten,
die ECHTE `httpx.Response`-Objekte mit dem aufgezeichneten Open-Meteo-
Fehlerkoerper liefert (Muster `_ScriptedClient`,
tests/unit/test_radar_upstream_failure.py) -- kein `Mock()`, kein `patch()`
von Rueckgabewerten. Der Cache ist eine echte `RadarNowcastCacheService`-
Instanz, das Journal wird ECHT geschrieben (durch den Prueflingspfad) und
als JSONL geparst gelesen.

`providers.enrichment_health.log_enrichment_call` wird bewusst NICHT
importiert und nicht direkt gerufen: jede Zusicherung laeuft ueber den
echten Nowcast-Pfad in die echte Journaldatei. Eine Verfaelschung des
gemeinsamen Schreibbausteins (AC-11, Mutations-Gegenprobe) macht damit
DIESE Datei UND test_thunder_enrichment_health_journal.py rot -- nicht nur
eine von beiden.

Die kleinen Journal-Lesehelfer stehen bewusst auch in der Gewitter-Testdatei
(dort mit `path='thunder'`): sie sind Testplumbing, kein geteilter Prueflings-
Baustein -- und eine gemeinsame Ablage in einer conftest wuerde die
Rot-Kopplung zwischen beiden Dateien ueber TESTcode statt ueber den
PRUEFLING herstellen, also genau das, was AC-11 nachweisen soll, vortaeuschen.

===========================================================================
Erwartete Rotfaerbung
===========================================================================
Rot sind AC-8 und AC-10: sie verlangen eine Journalzeile, die es heute nicht
gibt (weder `src/providers/enrichment_health.py` noch ein Aufruf daraus).

AC-9 (Cache-Treffer schreibt nichts) ist heute strukturell gruen -- ohne
Journal schreibt kein Aufruf etwas, auch der Cache-Treffer nicht. Er bleibt
trotzdem kein Blindtest: seine Vorbedingung verlangt, dass der ERSTE Aufruf
(Cache-Miss) GENAU EINE Zeile erzeugt hat. Diese Vorbedingung ist heute rot
und macht damit auch AC-9 rot -- und nach der Implementierung faellt genau
die Fehlplatzierung auf, vor der die Spec warnt: ein Aufruf in
`_derive_result()` (laeuft bei Hit UND Miss) laesse einen aus dem Cache
weiterbedienten Dauerausfall als lebendig erscheinen.

Ausfuehrung:
    uv run pytest tests/tdd/test_radar_nowcast_health_journal.py \
        --disable-socket --allow-unix-socket -v
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import httpx
import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from providers.brightsky import RadarFrame  # noqa: E402
from services.radar_cache import RadarNowcastCacheService  # noqa: E402
from services.radar_service import RadarNowcastService  # noqa: E402

# Atlantik: ausserhalb ALLER fuenf Bounding-Boxen (RADOLAN/INCA/DPC/AROME-FR/
# ICON-D2, radar_service.py:28-58) -- reiner generischer minutely_15-Zweig,
# GENAU EIN HTTP-Versuch pro get_nowcast()-Aufruf. Identische Koordinate wie
# tests/unit/test_radar_upstream_failure.py.
_ATLANTIC_LAT, _ATLANTIC_LON = 35.0, -40.0

_JOURNAL_UNTERPFAD = ("diagnostics", "enrichment_calls.jsonl")


# ---------------------------------------------------------------------------
# Netz-Double: echte httpx.Response-Objekte statt Mock/patch
# ---------------------------------------------------------------------------

_CALL_URLS: List[str] = []
_RESPONDER: list = [None]


def _failing_response(url: str) -> httpx.Response:
    """Wortwoertlicher Open-Meteo-Overload-Koerper (Issue-#1628-Journal)."""
    return httpx.Response(
        503, request=httpx.Request("GET", url),
        json={"error": True, "reason": "The service is overloaded"},
    )


class _ScriptedClient:
    """Ersetzt `httpx.Client` fuer die Testdauer und beantwortet jeden Abruf
    ueber `_RESPONDER[0]` mit einem ECHTEN `httpx.Response` -- kein Mock.
    Uebernommen aus tests/unit/test_radar_upstream_failure.py."""

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
    """Netzsperre + Offline-Fixture aus dem Weg raeumen.

    `GZ_TEST_FIXTURE_DIR` (autouse-Fixture in tests/conftest.py) wuerde in
    `_fetch_openmeteo_15` VOR dem Budget-Gate greifen -- damit liefe weder
    der Ausfall- (AC-8) noch der Drosselungspfad (AC-10) ueberhaupt an.
    """
    _CALL_URLS.clear()
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    monkeypatch.setattr(httpx, "Client", _ScriptedClient)
    yield
    _CALL_URLS.clear()


# ---------------------------------------------------------------------------
# Helpers
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
        f"vorhandene Zeilen: {_zeilen()}. Ohne den Health-Schreibweg "
        f"(providers.enrichment_health.log_enrichment_call) entsteht die "
        f"Datei gar nicht erst."
    )
    return zeilen[-1]


def _write_budget(calls_openmeteo: int) -> None:
    """Echte forecast_budget.json unter der isolierten Datenwurzel
    (Muster tests/unit/test_radar_upstream_failure.py::_write_budget)."""
    from app.loader import get_data_root
    pfad = get_data_root() / "diagnostics" / "forecast_budget.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({
        "date": date.today().isoformat(),
        "calls": {"openmeteo": calls_openmeteo},
        "cache_hits": 0,
        "cache_misses": 0,
    }))


def _nasse_frames(lat: float, lon: float) -> List[RadarFrame]:
    """DI-Seam (`RadarNowcastService.frame_source`): leichter Regen mit
    Onset in 5 Minuten. Vorbild `_light_wet_frames`
    (tests/unit/test_alert_channel_premium_sms.py:276)."""
    jetzt = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=jetzt + timedelta(minutes=5), precip_mm_h=0.5),
        RadarFrame(timestamp=jetzt + timedelta(minutes=15), precip_mm_h=0.6),
    ]


def _dienst(frame_source=None, now_fn=None) -> RadarNowcastService:
    """Immer mit EIGENEM Cache -- der geteilte Prozess-Cache
    (`get_shared_radar_cache()`) traegt sonst Eintraege zwischen Tests
    weiter und macht Cache-Treffer/-Fehltreffer nicht mehr steuerbar."""
    return RadarNowcastService(
        frame_source=frame_source,
        cache=RadarNowcastCacheService(),
        now_fn=now_fn,
    )


# ---------------------------------------------------------------------------
# AC-8: echter Anbieterausfall -> outcome="unavailable"
# ---------------------------------------------------------------------------

def test_ac8_echter_anbieterausfall_schreibt_unavailable():
    """AC-8: die gesamte Fetch-Kette antwortet mit einem echten HTTP-503
    (kein Cache-Treffer, kein Budget-Druck). `get_nowcast()` durchlaeuft den
    Miss-Zweig und muss `outcome='unavailable'` unter
    `path='radar_nowcast'` hinterlassen.

    Vorbedingung im Test: das Journal ist vorher leer -- die geprueft Zeile
    stammt damit nachweislich aus DIESEM Aufruf.
    """
    assert _radar_zeilen() == [], (
        "Testaufbau: Journal muss vor dem Abruf leer sein."
    )
    _RESPONDER[0] = _failing_response
    dienst = _dienst()

    ergebnis = dienst.get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON)

    # Vorbedingung: es war wirklich der Ausfall-Zweig, nicht Drosselung.
    assert ergebnis.data_unavailable is True and ergebnis.throttled is False, (
        f"Testaufbau: erwartet data_unavailable=True/throttled=False, "
        f"bekommen {ergebnis.data_unavailable}/{ergebnis.throttled}"
    )
    assert len(_CALL_URLS) == 1, (
        f"Testaufbau: genau ein HTTP-Versuch erwartet, tatsaechlich: {_CALL_URLS}"
    )

    zeile = _letzte_radar_zeile()
    assert zeile.get("outcome") == "unavailable", (
        f"AC-8: ein echter Anbieterausfall muss outcome='unavailable' "
        f"hinterlassen, bekommen {zeile.get('outcome')!r} "
        f"(ganze Zeile: {zeile})"
    )


# ---------------------------------------------------------------------------
# AC-10: eigene Budget-Drosselung -> outcome="self_throttled"
# ---------------------------------------------------------------------------

def test_ac10_budget_drosselung_schreibt_self_throttled():
    """AC-10: das Tageskontingent ist erschoepft, der Abruf unterbleibt
    (`throttled=True`, kein HTTP-Versuch). Eigene Drosselung ist KEIN
    Anbieterausfall -- die Zeile muss `outcome='self_throttled'` tragen.

    Der Unterschied zu AC-8 ist die eigentliche Aussage: wer beide Faelle
    auf `unavailable` abbildet, laesst das externe Auswertungsskript einen
    selbst gewaehlten Rueckzug als Fremdausfall eskalieren.
    """
    _write_budget(calls_openmeteo=7200)  # oberhalb der Drosselschwelle
    _RESPONDER[0] = _failing_response  # darf gar nicht erst gerufen werden
    dienst = _dienst()

    ergebnis = dienst.get_nowcast(
        _ATLANTIC_LAT, _ATLANTIC_LON, priority="polling",
    )

    # Vorbedingung: es war wirklich die Drosselung, nicht der Ausfall.
    assert _CALL_URLS == [], (
        f"Testaufbau: eine Drosselung darf keinen HTTP-Versuch ausloesen, "
        f"tatsaechlich: {_CALL_URLS}"
    )
    assert ergebnis.throttled is True and ergebnis.data_unavailable is False, (
        f"Testaufbau: erwartet throttled=True/data_unavailable=False, "
        f"bekommen {ergebnis.throttled}/{ergebnis.data_unavailable}"
    )

    zeile = _letzte_radar_zeile()
    assert zeile.get("outcome") == "self_throttled", (
        f"AC-10: die eigene Budget-Drosselung muss "
        f"outcome='self_throttled' hinterlassen, bekommen "
        f"{zeile.get('outcome')!r} (ganze Zeile: {zeile})"
    )
    assert zeile.get("outcome") != "unavailable", (
        "AC-10: Selbstdrosselung und Anbieterausfall duerfen nicht auf "
        "denselben Ausgang abgebildet werden (s. AC-8)."
    )


def test_ac8_und_ac10_sind_unterscheidbar():
    """AC-8 vs. AC-10, direkt gegenuebergestellt: derselbe Dienst laeuft
    einmal in die Drosselung und einmal in den echten Ausfall. Die beiden
    Journalzeilen muessen VERSCHIEDENE `outcome`-Werte tragen.

    Ohne diese Gegenueberstellung waere eine Vertauschung der beiden Zweige
    (`if result.data_unavailable` vor `if result.throttled` geprueft, oder
    beide auf denselben Wert abgebildet) von zwei einzeln gruenen Tests
    nicht zu fangen.
    """
    # 1) Drosselung
    _write_budget(calls_openmeteo=7200)
    _RESPONDER[0] = _failing_response
    gedrosselt = _dienst().get_nowcast(
        _ATLANTIC_LAT, _ATLANTIC_LON, priority="polling",
    )
    assert gedrosselt.throttled is True

    # 2) echter Ausfall -- Kontingent zurueck auf null, Prioritaet
    #    "user_briefing" (wird nie gedrosselt)
    _write_budget(calls_openmeteo=0)
    ausgefallen = _dienst().get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON)
    assert ausgefallen.data_unavailable is True

    zeilen = _radar_zeilen()
    assert len(zeilen) == 2, (
        f"Erwartet genau zwei radar_nowcast-Zeilen (Drosselung + Ausfall), "
        f"bekommen {len(zeilen)}: {zeilen}"
    )
    ausgaenge = [z.get("outcome") for z in zeilen]
    assert ausgaenge[0] != ausgaenge[1], (
        f"AC-8/AC-10: Selbstdrosselung und Anbieterausfall haben denselben "
        f"Ausgang {ausgaenge[0]!r} gebucht -- sie sind damit von aussen "
        f"nicht mehr zu trennen."
    )
    assert ausgaenge == ["self_throttled", "unavailable"], (
        f"AC-8/AC-10: erwartet ['self_throttled', 'unavailable'] in dieser "
        f"Reihenfolge, bekommen {ausgaenge} -- die beiden Zweige sind "
        f"vertauscht."
    )


# ---------------------------------------------------------------------------
# AC-9: ein Cache-Treffer erzeugt KEINE Journalzeile
# ---------------------------------------------------------------------------

def test_ac9_cache_treffer_erzeugt_keine_journalzeile():
    """AC-9: derselbe Ort wird zweimal hintereinander abgefragt. Der erste
    Aufruf ist ein Cache-Fehltreffer (echter Abrufversuch -> eine Zeile),
    der zweite wird vollstaendig aus dem Cache bedient -> KEINE weitere
    Zeile.

    Warum das die eigentliche Aussage ist: `_derive_result()` laeuft bei
    Cache-Treffer UND -Fehltreffer. Ein dort platzierter Journal-Aufruf
    buchte jeden Treffer als lebendigen Abruf -- ein Dauerausfall, der aus
    dem Cache weiterbedient wird, saehe von aussen gesund aus. Der Aufruf
    gehoert deshalb in den Miss-Zweig von `get_nowcast()`.

    Die Uhr ist fest gestellt (`now_fn`), damit der Cache-Treffer nicht von
    der Laufzeit des Tests abhaengt.
    """
    fest = datetime.now(timezone.utc)
    dienst = _dienst(frame_source=_nasse_frames, now_fn=lambda: fest)

    erstes = dienst.get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON)
    assert erstes.frames, "Testaufbau: der erste Aufruf lieferte keine Frames."

    # Vorbedingung -- HEUTE ROT: ohne sie waere die Hauptzusicherung unten
    # trivial wahr ("0 Zeilen bleiben 0 Zeilen").
    nach_miss = _radar_zeilen()
    assert len(nach_miss) == 1, (
        f"Vorbedingung AC-9: der Cache-Fehltreffer muss GENAU EINE "
        f"radar_nowcast-Zeile erzeugt haben, bekommen {len(nach_miss)}: "
        f"{nach_miss}. Ohne diese Zeile pruefte die Zusicherung unten nichts."
    )

    zweites = dienst.get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON)

    # Vorbedingung: der zweite Aufruf war wirklich ein Cache-Treffer.
    assert zweites.frames == erstes.frames, (
        "Testaufbau: der zweite Aufruf hat neue Frames geholt -- dann war es "
        "kein Cache-Treffer und AC-9 wird nicht geprueft."
    )

    nach_hit = _radar_zeilen()
    assert nach_hit == nach_miss, (
        f"AC-9: der aus dem Cache bediente Aufruf hat eine Journalzeile "
        f"erzeugt.\n  nach Fehltreffer: {nach_miss}\n  nach Treffer:     "
        f"{nach_hit}\nEin Cache-Treffer ist kein Abrufversuch -- sonst sieht "
        f"ein aus dem Cache weiterbedienter Dauerausfall lebendig aus."
    )


# ---------------------------------------------------------------------------
# Struktur der Journalzeile -- gemeinsames Schema beider Pfade
# ---------------------------------------------------------------------------

def test_radarzeile_traegt_dieselben_felder_wie_die_gewitterzeile():
    """Beide Anreicherungs-Pfade schreiben ueber DENSELBEN Baustein in
    DASSELBE Journal; die Go-Leseseite (`aggregateEnrichmentCalls`)
    gruppiert nach `path` und sortiert nach `ts`. Fehlt eines der Felder
    oder heisst der Pfad anders als `radar_nowcast`, liefert sie
    stillschweigend ein leeres Aggregat.
    """
    _RESPONDER[0] = _failing_response
    _dienst().get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON)

    zeile = _letzte_radar_zeile()
    for feld in ("ts", "path", "outcome", "detail"):
        assert feld in zeile, (
            f"Journalzeile ohne Feld {feld!r}: {zeile}"
        )
    assert zeile["path"] == "radar_nowcast", (
        f"AC-8: der Pfadname muss 'radar_nowcast' lauten (so gruppiert die "
        f"Go-Leseseite), bekommen {zeile['path']!r}"
    )
    ts = datetime.fromisoformat(zeile["ts"])
    assert ts.tzinfo is not None, (
        f"Zeitstempel {zeile['ts']!r} traegt keine Zeitzone -- die "
        f"Go-Leseseite vergleicht RFC3339-Werte lexikografisch, ein naiver "
        f"Stempel sortiert dabei falsch."
    )


def test_journalpfad_folgt_der_datenwurzel_bei_jedem_aufruf(monkeypatch, tmp_path):
    """Falle #1633, zweiter Pfad: die Datenwurzel wird MITTEN im Test
    verlegt. Die naechste Zeile muss in der NEUEN Wurzel landen.

    Eine Implementierung, die den Journalpfad beim Import bindet
    (Modulkonstante, `lru_cache`, Vorberechnung), bekommt diesen Test NICHT
    gruen. Er steht bewusst in BEIDEN Testdateien: der Pfad wird im
    gemeinsamen Baustein aufgeloest, also muss die Zusicherung ueber beide
    Aufrufer halten.
    """
    from app import loader

    _RESPONDER[0] = _failing_response
    _dienst().get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON)

    erste_wurzel_pfad = _journalpfad()
    assert len(_radar_zeilen()) == 1, (
        f"Vorbedingung: erwartet eine Zeile in der ersten Datenwurzel "
        f"{erste_wurzel_pfad}, bekommen {_radar_zeilen()}"
    )

    zweite_wurzel = tmp_path / "zweite-datenwurzel"
    zweite_wurzel.mkdir()
    monkeypatch.setattr(loader, "_DATA_ROOT", str(zweite_wurzel), raising=False)
    assert _journalpfad() != erste_wurzel_pfad, (
        "Testaufbau nicht diskriminierend: beide Wurzeln ergeben denselben Pfad."
    )

    _dienst().get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON)

    assert len(_radar_zeilen()) == 1, (
        f"Falle #1633: nach dem Umbiegen der Datenwurzel muss die neue Zeile "
        f"unter {_journalpfad()} liegen -- gefunden: {_radar_zeilen()}. Eine "
        f"beim Import gebundene Modulkonstante schriebe weiter in die alte "
        f"Wurzel."
    )
    alte_zeilen: Optional[List[dict]] = None
    if erste_wurzel_pfad.is_file():
        alte_zeilen = [
            json.loads(z)
            for z in erste_wurzel_pfad.read_text().splitlines() if z.strip()
        ]
    assert alte_zeilen is not None and len(alte_zeilen) == 1, (
        f"Falle #1633: die alte Journaldatei {erste_wurzel_pfad} ist "
        f"weitergewachsen ({alte_zeilen}) -- der Pfad wird also nicht bei "
        f"jedem Aufruf frisch aufgeloest."
    )
