"""TDD RED -- #2554: DWD-Gewitterabruf parallel, eigener Timeout, Budget im Journal.

Spec: docs/specs/modules/fix_2554_dwd_gewitterabruf_budget.md (AC-1 .. AC-8)

Testart: Kern-Schicht, deterministisch, KEIN Netz ausser localhost. Ein echter
lokaler `ThreadingHTTPServer` liefert Rasterdateien (bz2-gepackte GeoTIFF wie
beim echten Dienst) mit einstellbarer Verzoegerung, 404, Haenger, Muellbytes
und Verbindungsabbruch aus und zaehlt JEDEN Abruf mit (Ankunftszeit, Parameter,
Lauf, Zeitschritt, Status). Kein Mock des Providers; nur `monkeypatch` der
Modulkonstanten (`THUNDER_FETCH_DEADLINE_SECONDS`, `THUNDER_REQUEST_TIMEOUT`,
`BASE_URL`).

Der Server kodiert Parameter, Lauf und Zeitschritt in den Zellwert, damit ein
vertauschtes Einsortieren (Fertigstellungsreihenfolge statt Groesse) oder ein
Wert aus dem falschen Lauf als falscher Zahlenwert sichtbar wird:
  - normale Groessen:  lauf_stunde*100 + (param_index+1)*10 + zeitschritt*0.01
  - `grau_gsp` (kumuliert, nichtlinear): 0.1 * t*(t+1)/2  ->  Stundenwert 0.1*t
Die Erwartung wird in `_erwartet` UNABHAENGIG vom Produktivcode berechnet.

Neue Namen des Produktivcodes (THUNDER_REQUEST_TIMEOUT, PATH_THUNDER_BUDGET, ...)
werden per `getattr` gelesen bzw. mit `raising=False` gepatcht, damit der RED-
Zustand als Assertion sichtbar ist und nicht als Import-/AttributeError.

AC-Abdeckung und heutiger Zustand (vor der Implementierung):
  test_ac1_*  ROT   (sequentiell schafft ~4 von 12 Zeitpunkten)
  test_ac2_*  ROT   (kein vollstaendiger Zeitpunkt innerhalb des kleinen Budgets)
  test_ac3_*  ROT   (Haenger kostet 30 s statt 10 s/0,5 s; wird wiederholt)
  test_ac4_*  GRUEN (Regressionsschutz: Lauf-Rueckfall bleibt konsistent)
  test_ac5_*  GRUEN (Regressionsschutz: Werte/Reihenfolge unveraendert)
  test_ac6_*  ROT   (keine Journalzeile `thunder_budget`)
  test_ac7_*  GRUEN (Regressionsschutz: Cache #2465 verhindert Downloads)
  test_ac8_*  GRUEN/ROT je Teil (Konstanten-Teil ROT, "wirft nie" GRUEN)
"""
from __future__ import annotations

import json
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import bz2
import re

import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location  # noqa: E402
from app.loader import get_data_root  # noqa: E402
from providers import dwd, enrichment_health  # noqa: E402
from providers.base import ThunderSourceUnavailableError  # noqa: E402

_KARNISCH = Location(latitude=46.40, longitude=12.52, name="Karnischer Hoehenweg")
_GITTER = (-3.95, 43.17, 20.35, 58.09)  # gemessene Grenzen einer echten Antwort
_DATEINAME = re.compile(r"_(\d{10})_(\d{3})_2d_")
_ANZAHL_ZEITPUNKTE = 12

# Aktion einer Regel: None = normal liefern; sonst eines von
# ("status", code) | ("hang", sekunden) | ("garbage",) | ("abort",)
Regel = Callable[[str, str, int], Optional[tuple]]


# ---------------------------------------------------------------------------
# Erwartungswerte (unabhaengig vom Produktivcode)
# ---------------------------------------------------------------------------

def _wert(param: str, lauf: str, ttt: int) -> float:
    """Rohwert, den der Server fuer (param, lauf, ttt) in die Datei schreibt."""
    if param in dwd.THUNDER_CUMULATIVE_PARAMS:
        return 0.1 * ttt * (ttt + 1) / 2
    idx = dwd.THUNDER_PARAMS.index(param)
    return int(lauf[-2:]) * 100 + (idx + 1) * 10 + ttt * 0.01


def _erwartet(param: str, lauf: str, ttt: int) -> float:
    """Erwarteter Ergebniswert einer Zelle (Stundenwert bei kumuliertem Signal)."""
    if param in dwd.THUNDER_CUMULATIVE_PARAMS:
        return round(_wert(param, lauf, ttt) - _wert(param, lauf, ttt - 1), 4)
    return _wert(param, lauf, ttt)


_RASTER_CACHE_BYTES: dict = {}
_RASTER_LOCK = threading.Lock()


def _raster(wert: float) -> bytes:
    with _RASTER_LOCK:
        if wert in _RASTER_CACHE_BYTES:
            return _RASTER_CACHE_BYTES[wert]
    hoehe, breite = 60, 100
    with MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff", height=hoehe, width=breite, count=1,
            dtype="float64", crs="EPSG:4326",
            transform=from_bounds(*_GITTER, breite, hoehe),
        ) as dataset:
            dataset.write(np.full((hoehe, breite), wert, dtype="float64"), 1)
        daten = bz2.compress(memfile.read())
    with _RASTER_LOCK:
        _RASTER_CACHE_BYTES[wert] = daten
    return daten


# ---------------------------------------------------------------------------
# Lokaler DWD-Ersatz
# ---------------------------------------------------------------------------

class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, handler, *, verzoegerung_s: float, regel: Optional[Regel]):
        super().__init__(addr, handler)
        self.verzoegerung_s = verzoegerung_s
        self.regel = regel
        self.freigabe = threading.Event()  # beendet alle Haenger beim Abbau
        self.abrufe: list = []  # (monotone Ankunft, param, lauf, ttt, status)
        self._lock = threading.Lock()

    def protokolliere(self, eintrag) -> None:
        with self._lock:
            self.abrufe.append(eintrag)

    def kopie(self) -> list:
        with self._lock:
            return list(self.abrufe)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        srv = self.server
        ankunft = time.monotonic()
        path = urlparse(self.path).path
        treffer = _DATEINAME.search(path)
        param = next((p for p in dwd.THUNDER_PARAMS if f"/{p}/" in path), None)
        if param is None or treffer is None:
            self.send_response(404)
            self.end_headers()
            return
        lauf, ttt = treffer.group(1), int(treffer.group(2))
        aktion = srv.regel(param, lauf, ttt) if srv.regel else None
        if aktion and aktion[0] == "hang":
            srv.protokolliere((ankunft, param, lauf, ttt, "hang"))
            srv.freigabe.wait(timeout=aktion[1])
            return
        if srv.verzoegerung_s:
            time.sleep(srv.verzoegerung_s)
        if aktion and aktion[0] == "abort":
            srv.protokolliere((ankunft, param, lauf, ttt, "abort"))
            self.close_connection = True
            return
        if aktion and aktion[0] == "status":
            srv.protokolliere((ankunft, param, lauf, ttt, aktion[1]))
            self.send_response(aktion[1])
            self.end_headers()
            return
        body = b"das ist kein bz2" if aktion and aktion[0] == "garbage" \
            else _raster(_wert(param, lauf, ttt))
        srv.protokolliere((ankunft, param, lauf, ttt, 200))
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@contextmanager
def _dwd_server(monkeypatch, *, verzoegerung_s: float = 0.0, regel: Optional[Regel] = None):
    server = _Server(("127.0.0.1", 0), _Handler, verzoegerung_s=verzoegerung_s, regel=regel)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    monkeypatch.setattr(dwd, "BASE_URL", f"http://{host}:{port}/", raising=True)
    try:
        yield server
    finally:
        server.freigabe.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _cache_leeren():
    dwd._RASTER_CACHE.clear()
    yield
    dwd._RASTER_CACHE.clear()


class _Zeit:
    """Bezugspunkte eines Abrufs: Laeufe, Fenster, Zeitschritt-Basis je Lauf."""

    def __init__(self, ab_lauf: bool = False) -> None:
        now = datetime.now(timezone.utc)
        self.kandidaten = dwd._thunder_run_candidates(now)
        self.laeufe = [k.strftime("%Y%m%d%H") for k in self.kandidaten]
        self.start = self.kandidaten[0] if ab_lauf else now.replace(
            minute=0, second=0, microsecond=0)
        self.ende = self.start + timedelta(hours=_ANZAHL_ZEITPUNKTE)

    def ttt(self, lauf_index: int, offset: int) -> int:
        return int((self.start + timedelta(hours=offset)
                    - self.kandidaten[lauf_index]).total_seconds() // 3600)

    def offset_von(self, lauf: str, ttt: int) -> int:
        k = self.kandidaten[self.laeufe.index(lauf)]
        return int((k + timedelta(hours=ttt) - self.start).total_seconds() // 3600)


def _abruf(zeit: _Zeit):
    return dwd.DwdDirectProvider().fetch_thunder_signals_named(
        _KARNISCH, zeit.start, zeit.ende
    )


def _journal_zeilen(path: str) -> list:
    datei = get_data_root() / "diagnostics" / "enrichment_calls.jsonl"
    if not datei.exists():
        return []
    zeilen = [json.loads(z) for z in datei.read_text().splitlines() if z.strip()]
    return [z for z in zeilen if z.get("path") == path]


def _keine_pool_threads_mehr(grace_s: float = 2.0) -> bool:
    ende = time.monotonic() + grace_s
    while time.monotonic() < ende:
        if not [t for t in threading.enumerate()
                if t.name.startswith("ThreadPoolExecutor") and t.is_alive()]:
            return True
        time.sleep(0.05)
    return False


# ---------------------------------------------------------------------------
# AC-1: parallel schafft deutlich mehr Zeitpunkte innerhalb des Budgets
# ---------------------------------------------------------------------------

@pytest.mark.timeout(40)
def test_ac1_langsamer_dwd_liefert_mindestens_doppelt_so_viele_zeitpunkte(monkeypatch):
    """AC-1: Given ein DWD mit 0,2 s Verzug je Datei und Budget 8 s, When 12
    Zeitpunkte x 9 Groessen abgerufen werden, Then liegen je Groesse mindestens
    10 Zeitpunkte vor (sequentiell hoechstens ~4 -- das Doppelte ist die
    Untergrenze der Spec). ROT heute: der Abruf ist strikt sequentiell."""
    monkeypatch.setattr(dwd, "THUNDER_FETCH_DEADLINE_SECONDS", 8.0)
    zeit = _Zeit()
    with _dwd_server(monkeypatch, verzoegerung_s=0.2):
        ergebnis = _abruf(zeit)
    for param in dwd.THUNDER_PARAMS:
        da = [o for o in range(1, _ANZAHL_ZEITPUNKTE + 1)
              if ergebnis[param].get(o) is not None]
        assert len(da) >= 10, (
            f"'{param}': nur {len(da)} von {_ANZAHL_ZEITPUNKTE} Zeitpunkten "
            f"innerhalb des Budgets angekommen (erwartet >= 10) -- {da}"
        )
    assert _keine_pool_threads_mehr(), "Nach dem Abruf laeuft noch ein Pool-Thread"


# ---------------------------------------------------------------------------
# AC-2: Budget-Ende laesst nur hintere Zeitpunkte / hintere Groessen fehlen
# ---------------------------------------------------------------------------

@pytest.mark.timeout(30)
def test_ac2_budgetende_laesst_nur_hintere_zeitpunkte_und_groessen_fehlen(monkeypatch):
    """AC-2: Given Budget 1,5 s und 0,3 s Verzug je Datei, When der Abruf per
    Budget endet, Then (a) mindestens ein Zeitpunkt ist vollstaendig geladen,
    (b) geladene Zeitpunkte sind lueckenlos 1..k, alle vor k komplett, k ein
    Praefix von THUNDER_PARAMS (nie fehlt eine vordere Groesse bei geladener
    hinterer), (c) NACH dem Budget beginnt kein Download mehr (Budgetpruefung
    in der Worker-Aufgabe), (d) der Abruf endet kurz nach der Frist.
    ROT heute: sequentiell wird innerhalb 1,5 s kein Zeitpunkt vollstaendig."""
    budget, verzug = 1.5, 0.3
    monkeypatch.setattr(dwd, "THUNDER_FETCH_DEADLINE_SECONDS", budget)
    zeit = _Zeit()
    t0 = time.monotonic()
    with _dwd_server(monkeypatch, verzoegerung_s=verzug) as server:
        _abruf(zeit)
        dauer = time.monotonic() - t0
        abrufe = server.kopie()

    geladen: dict = {}
    for ankunft, param, lauf, ttt, status in abrufe:
        if status == 200:
            off = zeit.offset_von(lauf, ttt)
            if off >= 1:  # Offset 0 ist der Anker von grau_gsp
                geladen.setdefault(off, set()).add(param)
    assert geladen, "Gar kein Zeitpunkt geladen"
    k = max(geladen)
    assert sorted(geladen) == list(range(1, k + 1)), f"Zeitpunkte nicht lueckenlos: {sorted(geladen)}"
    assert k < _ANZAHL_ZEITPUNKTE, "Budget war gar nicht erschoepft -- Test misst nichts"
    for off in range(1, k):
        assert geladen[off] == set(dwd.THUNDER_PARAMS), (
            f"Zeitpunkt {off} (vor dem letzten {k}) ist unvollstaendig: "
            f"fehlt {set(dwd.THUNDER_PARAMS) - geladen[off]}"
        )
    erwartetes_praefix = set(dwd.THUNDER_PARAMS[:len(geladen[k])])
    assert geladen[k] == erwartetes_praefix, (
        f"Letzter Zeitpunkt {k}: geladen {sorted(geladen[k])} ist kein Praefix "
        f"von THUNDER_PARAMS -- eine hintere Groesse kam vor einer vorderen"
    )
    assert any(len(v) == len(dwd.THUNDER_PARAMS) for v in geladen.values()), (
        "Innerhalb des Budgets kein einziger Zeitpunkt vollstaendig"
    )
    spaetester_start = max(a for a, *_ in abrufe) - t0
    assert spaetester_start <= budget + 0.35, (
        f"Download begann {spaetester_start:.2f}s nach Start -- nach der Frist "
        f"({budget}s) darf keiner mehr beginnen"
    )
    assert dauer <= budget + verzug + 1.0, f"Abruf dauerte {dauer:.2f}s bei Budget {budget}s"


# ---------------------------------------------------------------------------
# AC-3: eigener Timeout, kein Retry bei Timeout, Zelle None
# ---------------------------------------------------------------------------

@pytest.mark.timeout(30)
def test_ac3_haengender_download_kostet_hoechstens_den_timeout_und_wird_nicht_wiederholt(monkeypatch):
    """AC-3: Given ein Download haengt (Server antwortet 4 s nicht) und
    THUNDER_REQUEST_TIMEOUT=0,5 s, When der Abruf laeuft, Then dauert er
    hoechstens Timeout plus Rand, die URL wurde GENAU EINMAL angefragt
    (kein Retry bei ReadTimeout), die Zelle ist None (nie 0), alle anderen
    Zellen sind gefuellt. ROT heute: der Gewitterweg nutzt TIMEOUT=30 und
    wiederholt ReadTimeout."""
    monkeypatch.setattr(dwd, "THUNDER_REQUEST_TIMEOUT", 0.5, raising=False)
    zeit = _Zeit()
    haenger_off, haenger_param = 3, "cin_ml"
    haenger_ttt = zeit.ttt(0, haenger_off)

    def regel(param, lauf, ttt):
        if param == haenger_param and lauf == zeit.laeufe[0] and ttt == haenger_ttt:
            return ("hang", 4.0)
        return None

    t0 = time.monotonic()
    with _dwd_server(monkeypatch, regel=regel) as server:
        ergebnis = _abruf(zeit)
        dauer = time.monotonic() - t0
        abrufe = server.kopie()

    anzahl = [a for a in abrufe
              if a[1] == haenger_param and a[3] == haenger_ttt and a[2] == zeit.laeufe[0]]
    assert len(anzahl) == 1, f"Haenger-URL wurde {len(anzahl)}x angefragt (erwartet genau 1)"
    assert dauer <= 0.5 + 2.5, f"Abruf dauerte {dauer:.2f}s, erwartet <= Timeout 0,5 s + Rand"
    assert ergebnis[haenger_param][haenger_off] is None, (
        f"Zelle des Haengers ist {ergebnis[haenger_param][haenger_off]!r}, erwartet None"
    )
    for param in dwd.THUNDER_PARAMS:
        for off in range(1, _ANZAHL_ZEITPUNKTE + 1):
            if (param, off) == (haenger_param, haenger_off):
                continue
            assert ergebnis[param].get(off) is not None, f"Zelle {param}+{off} leer"
    assert _keine_pool_threads_mehr(), "Pool-Thread laeuft nach dem Abruf weiter"


# ---------------------------------------------------------------------------
# AC-4: Lauf-Rueckfall bleibt unter Parallelitaet konsistent
# ---------------------------------------------------------------------------

@pytest.mark.timeout(40)
def test_ac4_laufrueckfall_bleibt_konsistent_und_einzelne_luecke_verschiebt_nichts(monkeypatch):
    """AC-4 (Regressionsschutz, heute schon GRUEN): Given der juengste Lauf liefert
    fuer ALLE Dateien 404, der naechste Lauf existiert, und im bestaetigten
    Lauf fehlt EINE Stunde (404), When der Abruf parallel laeuft, Then stammen
    alle Werte aus dem einen bestaetigten Lauf, die Luecke bleibt None, und der
    Server sah nie eine Anfrage gegen den noch aelteren dritten Lauf.
    Fenster beginnt AM Lauf (kein Anker-Abruf), damit die Bestaetigung vor dem
    Fan-out wirklich im Zeitpunkt-Pool entschieden wird (sonst bestaetigt der
    sequentielle Anker und die Mutation 'Bestaetigung entfernt' bliebe unsichtbar)."""
    zeit = _Zeit(ab_lauf=True)
    luecke_off, luecke_param = 5, "cin_ml"
    luecke_ttt = zeit.ttt(1, luecke_off)

    def regel(param, lauf, ttt):
        if lauf == zeit.laeufe[0]:
            return ("status", 404)
        if lauf == zeit.laeufe[1] and param == luecke_param and ttt == luecke_ttt:
            return ("status", 404)
        return None

    with _dwd_server(monkeypatch, verzoegerung_s=0.05, regel=regel) as server:
        ergebnis = _abruf(zeit)
        abrufe = server.kopie()

    assert not [a for a in abrufe if a[2] == zeit.laeufe[2]], (
        "Server sah Anfragen gegen den dritten Lauf -- Rueckfall doppelt ausgeloest"
    )
    for param in dwd.THUNDER_PARAMS:
        if param in dwd.THUNDER_CUMULATIVE_PARAMS:
            continue  # Differenz-Signal: Werte unten ueber Lauf-unabhaengigen Stundenwert
        for off in range(1, _ANZAHL_ZEITPUNKTE + 1):
            ist = ergebnis[param].get(off)
            if (param, off) == (luecke_param, luecke_off):
                assert ist is None, f"Luecke ({param}+{off}) ist {ist!r}, erwartet None"
                continue
            soll = _erwartet(param, zeit.laeufe[1], zeit.ttt(1, off))
            assert ist is not None and abs(ist - soll) < 1e-6, (
                f"{param}+{off}: {ist!r} statt {soll} (Wert muss aus Lauf "
                f"{zeit.laeufe[1]} stammen)"
            )


# ---------------------------------------------------------------------------
# AC-5: Werte und Reihenfolge unveraendert, inkl. grau_gsp mit Anker
# ---------------------------------------------------------------------------

@pytest.mark.timeout(40)
def test_ac5_werte_und_reihenfolge_sind_unveraendert_inklusive_grau_gsp_anker(monkeypatch):
    """AC-5 (Regressionsschutz, heute schon GRUEN): Given ein schneller DWD, When
    der Abruf laeuft, Then stimmen alle Zellen mit dem unabhaengig berechneten
    Sollstand ueberein (Wert kodiert Groesse und Zeitschritt, faengt also
    Vertauschen nach Fertigstellungsreihenfolge), Groessen stehen in
    THUNDER_PARAMS-Reihenfolge, Zeitpunkte aufsteigend, und der grau_gsp-
    Stundenwert der ersten Stunde nutzt den Anker (Differenz, nicht Summe)."""
    zeit = _Zeit()
    with _dwd_server(monkeypatch):
        ergebnis = _abruf(zeit)
    assert list(ergebnis) == list(dwd.THUNDER_PARAMS), "Groessen-Reihenfolge geaendert"
    for param in dwd.THUNDER_PARAMS:
        assert list(ergebnis[param]) == list(range(1, _ANZAHL_ZEITPUNKTE + 1)), (
            f"'{param}': Zeitpunkt-Reihenfolge {list(ergebnis[param])}"
        )
        for off in range(1, _ANZAHL_ZEITPUNKTE + 1):
            soll = _erwartet(param, zeit.laeufe[0], zeit.ttt(0, off))
            ist = ergebnis[param][off]
            assert ist is not None and abs(ist - soll) < 1e-6, (
                f"{param}+{off}: {ist!r}, erwartet {soll}"
            )
    erste = ergebnis["grau_gsp"][1]
    assert abs(erste - 0.1 * zeit.ttt(0, 1)) < 1e-6, (
        f"Erste grau_gsp-Stunde {erste} ist keine Differenz zum Anker"
    )


# ---------------------------------------------------------------------------
# AC-6: Budget-Erschoepfung erscheint im Health-Journal
# ---------------------------------------------------------------------------

def test_ac6_pfadkonstante_thunder_budget_existiert():
    """AC-6: `PATH_THUNDER_BUDGET == "thunder_budget"` in enrichment_health.
    ROT heute: Konstante fehlt."""
    assert getattr(enrichment_health, "PATH_THUNDER_BUDGET", None) == "thunder_budget"


@pytest.mark.timeout(30)
def test_ac6_budgetende_schreibt_genau_eine_journalzeile_fallback(monkeypatch):
    """AC-6: Given erschoepftes Budget, When der Abruf endet, Then steht genau
    eine Journalzeile path=thunder_budget, outcome=fallback,
    detail=icon_d2_budget_erschoepft. ROT heute: keine Zeile."""
    monkeypatch.setattr(dwd, "THUNDER_FETCH_DEADLINE_SECONDS", 1.0)
    zeit = _Zeit()
    with _dwd_server(monkeypatch, verzoegerung_s=0.3):
        _abruf(zeit)
    zeilen = _journal_zeilen("thunder_budget")
    assert len(zeilen) == 1, f"{len(zeilen)} Zeilen path=thunder_budget, erwartet genau 1"
    assert zeilen[0]["outcome"] == "fallback"
    assert zeilen[0]["detail"] == "icon_d2_budget_erschoepft"


@pytest.mark.timeout(30)
def test_ac6_vollstaendiger_lauf_schreibt_genau_eine_zeile_ok(monkeypatch):
    """AC-6: Given ein Abruf ohne Budget-Ende, Then genau eine Zeile
    path=thunder_budget mit outcome=ok. ROT heute: keine Zeile."""
    zeit = _Zeit()
    with _dwd_server(monkeypatch):
        _abruf(zeit)
    zeilen = _journal_zeilen("thunder_budget")
    assert len(zeilen) == 1, f"{len(zeilen)} Zeilen path=thunder_budget, erwartet genau 1"
    assert zeilen[0]["outcome"] == "ok"


# ---------------------------------------------------------------------------
# AC-7: Cache-Treffer loest keinen Download aus
# ---------------------------------------------------------------------------

@pytest.mark.timeout(40)
def test_ac7_zweiter_abruf_desselben_punkts_loest_keinen_download_aus(monkeypatch):
    """AC-7 (Regressionsschutz #2465, heute schon GRUEN): Given ein erster Abruf
    lief, When derselbe Punkt/dasselbe Fenster erneut abgerufen wird, Then sieht
    der Server keine neue Anfrage und die Werte sind identisch."""
    zeit = _Zeit()
    with _dwd_server(monkeypatch) as server:
        erster = _abruf(zeit)
        nach_erstem = len(server.kopie())
        zweiter = _abruf(zeit)
        nach_zweitem = len(server.kopie())
    assert nach_erstem > 0
    assert nach_zweitem == nach_erstem, (
        f"Zweiter Abruf loeste {nach_zweitem - nach_erstem} neue Downloads aus"
    )
    assert zweiter == erster


# ---------------------------------------------------------------------------
# AC-8: wirft nie, Budget fest, kein Thread bleibt zurueck
# ---------------------------------------------------------------------------

def test_ac8_neue_konstanten_und_festes_budget():
    """AC-8/AC-3: THUNDER_REQUEST_TIMEOUT=10, THUNDER_RETRY_ATTEMPTS=2,
    THUNDER_PARALLEL_DOWNLOADS=5; Gewitter-Budget bleibt 150 s, Grundpfad
    (TIMEOUT 30, RETRY_ATTEMPTS 5, FETCH_DEADLINE_SECONDS 180) unveraendert.
    ROT heute: die drei neuen Konstanten fehlen."""
    assert getattr(dwd, "THUNDER_REQUEST_TIMEOUT", None) == 10.0
    assert getattr(dwd, "THUNDER_RETRY_ATTEMPTS", None) == 2
    assert getattr(dwd, "THUNDER_PARALLEL_DOWNLOADS", None) == 5
    assert dwd.THUNDER_FETCH_DEADLINE_SECONDS == 150.0
    assert (dwd.TIMEOUT, dwd.RETRY_ATTEMPTS, dwd.FETCH_DEADLINE_SECONDS) == (30.0, 5, 180.0)


@pytest.mark.timeout(40)
def test_ac8_garbage_abbruch_und_404_werfen_nie_und_hinterlassen_keinen_thread(monkeypatch):
    """AC-8 (Regressionsschutz fuer 'wirft nie', heute schon GRUEN): Given einzelne
    Muellbytes (200), ein Verbindungsabbruch und ein 404 im bestaetigten Lauf,
    When der Abruf laeuft, Then wirft er nicht, die drei Zellen sind None, alle
    anderen gefuellt, und kein Pool-Thread bleibt zurueck."""
    zeit = _Zeit()
    ziele = {("lpi", 2): ("garbage",), ("cin_ml", 3): ("abort",), ("sdi_2", 4): ("status", 404)}

    def regel(param, lauf, ttt):
        for (p, off), aktion in ziele.items():
            if param == p and ttt == zeit.ttt(0, off) and lauf == zeit.laeufe[0]:
                return aktion
        return None

    with _dwd_server(monkeypatch, regel=regel):
        ergebnis = _abruf(zeit)  # darf nicht werfen
    for param in dwd.THUNDER_PARAMS:
        for off in range(1, _ANZAHL_ZEITPUNKTE + 1):
            if (param, off) in ziele:
                assert ergebnis[param].get(off) is None, f"{param}+{off} sollte None sein"
            else:
                assert ergebnis[param].get(off) is not None, f"{param}+{off} leer"
    assert _keine_pool_threads_mehr(), "Pool-Thread laeuft nach dem Abruf weiter"


@pytest.mark.timeout(40)
def test_ac8_totalausfall_wirft_weiterhin_thunder_source_unavailable(monkeypatch):
    """AC-8 (Regressionsschutz, heute schon GRUEN): Given jeder Abruf scheitert
    (Verbindungsabbruch), Then bleibt die einzige erlaubte Ausnahme
    ThunderSourceUnavailableError. (404 zaehlt NICHT als Totalausfall: der
    Lauf-Rueckfall erhoeht `versucht` ohne `fehlgeschlagen`.)"""
    zeit = _Zeit()
    with _dwd_server(monkeypatch, regel=lambda p, l, t: ("abort",)):
        with pytest.raises(ThunderSourceUnavailableError):
            _abruf(zeit)
    assert _keine_pool_threads_mehr(), "Pool-Thread laeuft nach dem Abruf weiter"


@pytest.mark.timeout(30)
def test_ac8_nicht_schreibbares_journal_bricht_den_abruf_nicht(monkeypatch):
    """AC-8: Given das Journalverzeichnis ist nicht anlegbar (an seiner Stelle
    liegt eine Datei), When der Abruf laeuft, Then liefert er sein volles
    Ergebnis ohne Ausnahme (Journal ist fail-soft)."""
    diag = get_data_root() / "diagnostics"
    diag.parent.mkdir(parents=True, exist_ok=True)
    if diag.exists() and diag.is_dir():
        pytest.skip("diagnostics existiert als Verzeichnis in der Test-Datenwurzel")
    diag.write_text("blockiert")
    zeit = _Zeit()
    try:
        with _dwd_server(monkeypatch):
            ergebnis = _abruf(zeit)
    finally:
        diag.unlink()
    assert all(ergebnis[p].get(o) is not None
               for p in dwd.THUNDER_PARAMS for o in range(1, _ANZAHL_ZEITPUNKTE + 1))


# ---------------------------------------------------------------------------
# Fix-Loop 1 (#2554): Zusicherungen dort pruefen, wo sie WIRKEN
# ---------------------------------------------------------------------------

@pytest.mark.timeout(40)
def test_ac3_haenger_mit_unveraendertem_default_timeout_endet_nach_etwa_10s(monkeypatch):
    """AC-3 / F001: Given der UNVERAENDERTE Default THUNDER_REQUEST_TIMEOUT (10 s,
    NICHT gepatcht) und ein Download, der 15 s schweigt, When der Abruf laeuft,
    Then endet er nach ca. 10 s (nicht 15 s und nicht 30 s), die URL wurde genau
    einmal angefragt und die Zelle ist None. Faengt ein Zuruecksetzen der
    Konstante auf 30."""
    assert dwd.THUNDER_REQUEST_TIMEOUT == 10.0
    zeit = _Zeit()
    haenger_off, haenger_param = 3, "cin_ml"
    haenger_ttt = zeit.ttt(0, haenger_off)

    def regel(param, lauf, ttt):
        if param == haenger_param and lauf == zeit.laeufe[0] and ttt == haenger_ttt:
            return ("hang", 15.0)
        return None

    t0 = time.monotonic()
    with _dwd_server(monkeypatch, regel=regel) as server:
        ergebnis = _abruf(zeit)
        dauer = time.monotonic() - t0
        abrufe = server.kopie()
    anzahl = [a for a in abrufe if a[1] == haenger_param and a[3] == haenger_ttt]
    assert len(anzahl) == 1, f"Haenger-URL {len(anzahl)}x angefragt"
    assert 9.5 <= dauer < 13.0, f"Abruf dauerte {dauer:.2f}s, erwartet ca. 10 s"
    assert ergebnis[haenger_param][haenger_off] is None


@pytest.mark.parametrize("budget", [1.2, 1.8])
@pytest.mark.timeout(40)
def test_ac2_nach_fristende_beginnt_kein_download_und_kein_weiterer_zeitpunkt(monkeypatch, budget):
    """AC-2 / F002 + F004: Given Budget 1,2 s bzw. 1,8 s bei 0,3 s Verzug (Frist liegt mitten in einem
    Batch; bei Vielfachen von 0,6 s traefe sie zufaellig eine Batch-Grenze und die
    Mutation "Budgetpruefung in `hole` entfernt" bliebe unsichtbar), When das Budget
    endet, Then (a) beginnt KEIN Einzelabruf (`_thunder_point`) nach der Frist
    (Budgetpruefung in der Worker-Aufgabe), (b) wird das Budget-Ende hoechstens
    einmal je Groesse eines einzigen Zeitpunkts gemeldet -- ein weiterer
    Zeitpunkt wird nach dem Abbruch nicht mehr begonnen, (c) steht die
    Journalzeile fallback."""
    monkeypatch.setattr(dwd, "THUNDER_FETCH_DEADLINE_SECONDS", budget)
    fristen: list = []
    starts: list = []
    meldungen: list = []
    original_pruefung = dwd._thunder_budget_erschoepft
    original_punkt = dwd.DwdDirectProvider._thunder_point

    def pruefung(deadline_at):
        fristen.append(deadline_at)
        erschoepft = original_pruefung(deadline_at)
        if erschoepft:
            meldungen.append(1)
        return erschoepft

    def punkt(self, *args, **kwargs):
        starts.append(time.monotonic())
        return original_punkt(self, *args, **kwargs)

    monkeypatch.setattr(dwd, "_thunder_budget_erschoepft", pruefung)
    monkeypatch.setattr(dwd.DwdDirectProvider, "_thunder_point", punkt)
    vorher = len(_journal_zeilen("thunder_budget"))
    zeit = _Zeit()
    with _dwd_server(monkeypatch, verzoegerung_s=0.3):
        _abruf(zeit)
    frist = fristen[0]
    nach_frist = [s for s in starts if s > frist]
    assert not nach_frist, f"{len(nach_frist)} Einzelabrufe begannen nach der Frist"
    assert len(meldungen) <= len(dwd.THUNDER_PARAMS), (
        f"Budget-Ende {len(meldungen)}x gemeldet -- hoechstens ein Zeitpunkt "
        f"({len(dwd.THUNDER_PARAMS)} Groessen) darf es melden"
    )
    zeilen = _journal_zeilen("thunder_budget")
    assert len(zeilen) == vorher + 1 and zeilen[-1]["outcome"] == "fallback"


@pytest.mark.timeout(40)
def test_ac2_abgeschnittene_vordere_groesse_verwirft_hintere_desselben_zeitpunkts(monkeypatch):
    """AC-2 / F006: Given Budget 1,0 s, und die VORDERE Groesse `lpi` eines
    Zeitpunkts haengt ueber die Frist hinaus, waehrend hintere Groessen
    desselben Zeitpunkts schnell ankommen, When das Budget endet, Then fehlen
    ALLE Groessen dieses Zeitpunkts (nie fehlt eine vordere bei vorhandener
    hinterer); der Zeitpunkt davor ist vollstaendig, die danach fehlen."""
    monkeypatch.setattr(dwd, "THUNDER_FETCH_DEADLINE_SECONDS", 1.0)
    zeit = _Zeit()
    haenger_off = 2
    haenger_ttt = zeit.ttt(0, haenger_off)

    def regel(param, lauf, ttt):
        if param == "lpi" and lauf == zeit.laeufe[0] and ttt == haenger_ttt:
            return ("hang", 6.0)
        return None

    with _dwd_server(monkeypatch, regel=regel) as server:
        ergebnis = _abruf(zeit)
        # SOFORT nach Rueckkehr, ohne Wartezeit: der Pool muss geschlossen sein.
        uebrig = [t.name for t in threading.enumerate()
                  if t.name.startswith("ThreadPoolExecutor") and t.is_alive()]
        abrufe = server.kopie()
    schnelle_hintere = [a for a in abrufe if a[3] == haenger_ttt
                        and a[1] != "lpi" and a[4] == 200]
    assert schnelle_hintere, "Hintere Groessen des Zeitpunkts kamen gar nicht an -- Test misst nichts"
    for param in dwd.THUNDER_PARAMS:
        assert ergebnis[param].get(1) is not None, f"{param}+1 fehlt"
        assert ergebnis[param].get(haenger_off) is None, (
            f"{param}+{haenger_off} = {ergebnis[param].get(haenger_off)!r}: "
            f"hintere Groesse vorhanden, obwohl `lpi` desselben Zeitpunkts fehlt"
        )
        for off in range(haenger_off + 1, _ANZAHL_ZEITPUNKTE + 1):
            assert ergebnis[param].get(off) is None, f"{param}+{off} nach Budget-Ende vorhanden"
    assert not uebrig, f"Pool-Threads direkt nach Rueckkehr noch aktiv: {uebrig}"


@pytest.mark.timeout(60)
def test_ac8_totalausfall_ueber_http_500_wirft_thunder_source_unavailable(monkeypatch):
    """AC-8 / F003: Given jeder Abruf liefert HTTP 500 (Retry, dann Fehler),
    Budget 5 s, Then ThunderSourceUnavailableError wie vor der Aenderung."""
    monkeypatch.setattr(dwd, "THUNDER_FETCH_DEADLINE_SECONDS", 5.0)
    zeit = _Zeit()
    with _dwd_server(monkeypatch, regel=lambda p, l, t: ("status", 500)):
        with pytest.raises(ThunderSourceUnavailableError):
            _abruf(zeit)


@pytest.mark.timeout(40)
def test_ac8_totalausfall_ueber_http_403_wirft_thunder_source_unavailable_ohne_retry(monkeypatch):
    """AC-8 / F003: Given jeder Abruf liefert HTTP 403 (nicht wiederholbar), Then
    ThunderSourceUnavailableError, und jede URL wurde genau einmal angefragt."""
    zeit = _Zeit()
    with _dwd_server(monkeypatch, regel=lambda p, l, t: ("status", 403)) as server:
        with pytest.raises(ThunderSourceUnavailableError):
            _abruf(zeit)
        abrufe = server.kopie()
    urls = [(a[1], a[2], a[3]) for a in abrufe]
    assert urls and len(urls) == len(set(urls)), "403 wurde wiederholt"
