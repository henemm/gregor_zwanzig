"""TDD RED -- #1492 Scheibe 2a: Fehlerunterscheidung in den Providern.

Spec: docs/specs/modules/feat_1492_s2a_thunder_vertretung.md.
ADR: docs/adr/0047-gewitter-vertretung-zwischen-direktquellen.md.

Deckt hier ab: AC-3, AC-6 (echte `dwd.py`/`meteofrance.py`-Zaehllogik
`versucht`/`fehlgeschlagen`, Implementation Details Punkt 3) PLUS drei nicht
eigens ACs zugeordnete, aber von der Spec verlangte Nachweise der
Zaehllogik selbst ("Was noch nicht existiert" nennt sie explizit fuer BEIDE
Provider-Dateien): dass der jeweilige Provider bei TOTALEM Ausfall
tatsaechlich `ThunderSourceUnavailableError` wirft (das Gegenstueck zu AC-1,
dort nur ueber einen Fake bewiesen -- ohne einen Nachweis am ECHTEN
Provider koennte die Zaehllogik komplett fehlen, ohne dass irgendein Test
dies faengt), und dass ein Zwischenspeicher-Treffer bei meteofrance.py NICHT
als Versuch zaehlt (Implementation Details Punkt 3, letzter Absatz).

AC-2 wird BEWUSST NICHT hier dupliziert: sein Provider-seitiges Aequivalent
("erfolgreiche, aber leere Antwort wirft nicht") ist strukturell derselbe
Code-Pfad wie AC-3 (Erfolg auf Transportebene, kein Wurf) -- ein eigener
Test waere von AC-3 nicht unterscheidbar und damit blind/redundant. Die
Fake-basierte AC-2-Pruefung (Ersatzquelle wird nicht gerufen) steht in
`test_thunder_source_substitution.py`.

===========================================================================
Lokaler HTTP-Server unter dem Egress-Waechter
===========================================================================
Alle Tests hier brauchen einen echten lokalen `ThreadingHTTPServer`
(127.0.0.1) -- reine In-Memory-Fakes koennen die Unterscheidung
"Verbindungsfehler vs. erfolgreiche-aber-leere-Antwort" nicht abbilden,
die genau der Pruefgegenstand dieser Datei ist. Kein Marker noetig: die
CI faehrt pytest-socket NICHT mit nacktem `--disable-socket`, sondern mit
`--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost`
(`.github/workflows/ci.yml:46-47`) -- unter diesen Flags ist ein Server auf
127.0.0.1 ausdruecklich erlaubt, jeder andere Host bleibt blockiert. Ein
Lauf mit NACKTEM `--disable-socket` (ohne `--allow-hosts`) laesst diese
sechs Tests mit `SocketBlockedError` scheitern -- das ist beabsichtigt und
die sichere Richtung (fail-closed): ohne die CI-Flags soll hier NICHTS ins
Netz duerfen, auch nicht versehentlich, kein Grund, das modulweit ueber
`pytest.mark.enable_socket` wieder aufzuheben (das haette den Schutz fuer
diese Tests VOLLSTAENDIG abgeschaltet, nicht nur fuer localhost -- Lehre
aus #1477).

===========================================================================
Zur "erwarteten Rotfaerbung" -- empirisch nachgemessen, nicht geraten
===========================================================================
AC-3 und AC-6 (dwd.py) sind bereits HEUTE gruen: beide pruefen die
ABWESENHEIT eines Wurfs, und ohne die neue Zaehllogik wirft `dwd.py`
schlicht nie (der alte, unveraenderte Code hat keinerlei
`ThunderSourceUnavailableError`-Pfad). "Kein Mechanismus" und "wirft nie"
fallen also zusammen. Die drei Zaehllogik-Nachweise ("wirft bei totalem
Ausfall") sind dagegen ECHT rot: sie referenzieren
`base.ThunderSourceUnavailableError`, das es noch nicht gibt.
"""
from __future__ import annotations

import bz2
import re
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest
import tenacity
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location  # noqa: E402
from providers import base, dwd, meteofrance, thunder_routing  # noqa: E402
from providers.thunder_window_cache import (  # noqa: E402
    reset_thunder_window_cache_for_tests,
)

_KARNISCH = Location(latitude=46.40, longitude=12.52, name="Karnischer Hoehenweg (Test)")


# ---------------------------------------------------------------------------
# DWD-Fake-Server -- ICON-D2-Rechteck (thunder_routing.py), bz2+GTiff wie der
# echte Dienst (Muster test_dwd_read_point_value.py/_kunst_raster).
# ---------------------------------------------------------------------------

_ICON_D2_GITTER = (-3.95, 43.17, 20.35, 58.09)
_DATEINAME = re.compile(r"_(\d{10})_(\d{3})_2d_")


def _dwd_raster(wert: float) -> bytes:
    hoehe, breite = 20, 30
    with MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff", height=hoehe, width=breite, count=1,
            dtype="float64", crs="EPSG:4326",
            transform=from_bounds(*_ICON_D2_GITTER, breite, hoehe),
        ) as dataset:
            dataset.write(np.full((hoehe, breite), wert, dtype="float64"), 1)
        return bz2.compress(memfile.read())


class _DwdServer(ThreadingHTTPServer):
    def __init__(self, addr, handler, *, status_je_zeitschritt, inhalt):
        super().__init__(addr, handler)
        self.status_je_zeitschritt = status_je_zeitschritt  # ttt -> HTTP-Status
        self.inhalt = inhalt  # ttt -> bytes
        self.abrufe: list[int] = []
        self.lock = threading.Lock()


class _DwdHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        srv = self.server
        treffer = _DATEINAME.search(urlparse(self.path).path)
        ttt = int(treffer.group(2)) if treffer else -1
        with srv.lock:
            srv.abrufe.append(ttt)
        status = srv.status_je_zeitschritt.get(ttt, 200)
        if status != 200:
            self.send_response(status)
            self.end_headers()
            return
        body = srv.inhalt(ttt)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@contextmanager
def _dwd_server(monkeypatch, *, status_je_zeitschritt=None, inhalt=None):
    srv = _DwdServer(
        ("127.0.0.1", 0), _DwdHandler,
        status_je_zeitschritt=status_je_zeitschritt or {},
        inhalt=inhalt or (lambda ttt: _dwd_raster(15.5)),
    )
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    host, port = srv.server_address
    monkeypatch.setattr(dwd, "BASE_URL", f"http://{host}:{port}/", raising=True)
    monkeypatch.setattr(
        dwd.DwdDirectProvider._request.retry, "wait", tenacity.wait_none(),
    )
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


def _dwd_fenster(stunden: int = 3):
    """Fenster beginnt exakt am gewaehlten Lauf (`base == run`) -- der
    kumulierte Anker-Abruf fuer `grau_gsp` entfaellt dann (`base > run` ist
    False), was die erwartete Abrufzahl je Test vorhersagbar haelt."""
    run = dwd._latest_run(datetime.now(timezone.utc))
    return run, run + timedelta(hours=stunden)


# ---------------------------------------------------------------------------
# AC-3 -- Gitterrand-Fuellwert loest KEINE Ausfallausnahme aus.
# ---------------------------------------------------------------------------

def test_ac3_dwd_gitterrand_fuellwert_wirft_keine_ausfallausnahme(monkeypatch):
    """AC-3: `de_direct` antwortet fuer JEDEN angefragten Punkt erfolgreich
    (200, kein Verbindungsfehler), aber der gelesene Wert ist wegen
    Gitterrand-Fuellwert `None` (`_read_point_value`-Muster). Ausgangswert
    (Erfolg auf Transportebene), Ableitungsquelle (`_read_point_value`
    filtert den Fuellwert zu `None`) und Sollwert (kein Wurf) sind drei
    unterscheidbare Groessen -- eine Implementierung, die jedes
    `None`-Ergebnis als Fehlschlag zaehlt, wuerde hier faelschlich werfen.

    Hinweis (dokumentierte Ausnahme, gemessen): bereits HEUTE gruen -- ohne
    Zaehllogik wirft `dwd.py` nie, "kein Wurf" ist also die Ausgangslage.
    Kein Blindtest: eine kuenftige Implementierung, die JEDES `None` als
    Fehlschlag zaehlt (statt nur echte Verbindungsfehler), macht GENAU
    diesen Test rot (`raise` statt eines sauberen Rueckgabewerts).
    """
    start, ende = _dwd_fenster()
    with _dwd_server(
        monkeypatch, inhalt=lambda ttt: _dwd_raster(dwd.THUNDER_FILL_VALUE),
    ) as srv:
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _KARNISCH, start=None, end=ende,
        )
    assert srv.abrufe, "Der Server wurde nie kontaktiert -- nichts geprueft"
    alle = [w for signal in ergebnis.values() for w in signal.values()]
    assert alle, "Kein einziger Eintrag zurueckgekommen -- nichts geprueft"
    assert all(w is None for w in alle), (
        f"Es kamen Werte an, obwohl jeder Punkt nur den Fuellwert traegt: "
        f"{sorted({w for w in alle if w is not None})}"
    )


# ---------------------------------------------------------------------------
# AC-6 -- Teilfehlschlag ist KEIN Dienstausfall (dwd.py).
# ---------------------------------------------------------------------------

def test_ac6_dwd_einzelner_fehlschlag_unter_vielen_wirft_keine_ausfallausnahme(
    monkeypatch,
):
    """AC-6: `de_direct` scheitert an GENAU EINEM von drei angefragten
    Zeitpunkten (500, retryable, alle 5 Versuche scheitern), die uebrigen
    beiden antworten gueltig. Ausgangswert (2 von 3 Erfolge), Ableitungsquelle
    (Zaehllogik `fehlgeschlagen == versucht`) und Sollwert (kein Wurf, 2
    Werte gefuellt) sind drei unterscheidbare Groessen -- eine
    Implementierung, die schon EINEN Fehlschlag als Ausfall wertet, wuerfe
    hier faelschlich.

    Hinweis (dokumentierte Ausnahme, gemessen): bereits HEUTE gruen, aus
    demselben Grund wie AC-3. Kein Blindtest: eine Implementierung mit
    `fehlgeschlagen >= 1` statt `fehlgeschlagen == versucht` als
    Wurf-Bedingung macht GENAU diesen Test rot.
    """
    start, ende = _dwd_fenster(stunden=3)

    def inhalt(ttt):
        return _dwd_raster(15.5)

    with _dwd_server(
        monkeypatch, status_je_zeitschritt={2: 500}, inhalt=inhalt,
    ) as srv:
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _KARNISCH, start=None, end=ende,
        )
    angefragt = {t for _p, t in ((None, t) for t in srv.abrufe)}
    assert 2 in angefragt, "Der praeparierte Fehlschlag-Zeitschritt wurde nie angefragt"

    lpi = ergebnis["lpi"]
    assert lpi.get(2) is None, f"Zeitschritt 2 haette leer bleiben muessen: {lpi}"
    gefuellt = [o for o, w in lpi.items() if o != 2 and w is not None]
    assert gefuellt, (
        f"Kein einziger der uebrigen Zeitschritte wurde gefuellt: {lpi} -- "
        "der einzelne Fehlschlag hat die ganze Reihe mitgerissen"
    )


# ---------------------------------------------------------------------------
# Zaehllogik-Nachweis (dwd.py): totaler Ausfall WIRFT -- Gegenstueck zu AC-1.
# ---------------------------------------------------------------------------

def test_dwd_alle_punkte_verbindungsfehler_wirft_ausfallausnahme(monkeypatch):
    """Implementation Details Punkt 3 ("versucht > 0 and fehlgeschlagen ==
    versucht -> raise"), am ECHTEN Provider bewiesen -- nicht nur am Fake
    (AC-1). Ohne diesen Nachweis koennte die Zaehllogik in `dwd.py`
    vollstaendig fehlen (oder nie ausloesen), ohne dass AC-3/AC-6 (die nur
    die Abwesenheit pruefen) das je bemerken wuerden.

    Given `de_direct` antwortet auf JEDEN Punkt mit 500 (retryable, alle 5
    Versuche scheitern), When `fetch_thunder_signals_named` laeuft, Then
    wirft die Methode `base.ThunderSourceUnavailableError` mit
    `provider == "de_direct"` und `attempted > 0`.

    RED-Grund: `base.ThunderSourceUnavailableError` existiert nicht
    (AttributeError schon beim Aufbau von `pytest.raises(...)`).
    """
    start, ende = _dwd_fenster(stunden=3)
    with _dwd_server(monkeypatch, status_je_zeitschritt={1: 500, 2: 500, 3: 500}) as srv:
        with pytest.raises(base.ThunderSourceUnavailableError) as excinfo:
            dwd.DwdDirectProvider().fetch_thunder_signals_named(
                _KARNISCH, start=None, end=ende,
            )
        assert srv.abrufe, "Der Server wurde nie kontaktiert -- nichts geprueft"
    assert excinfo.value.provider == "de_direct", excinfo.value.provider
    assert excinfo.value.attempted > 0, excinfo.value.attempted


# ---------------------------------------------------------------------------
# Météo-France (fr_direct) -- eigene Schleifenform (Gruppen x Offsets).
# ---------------------------------------------------------------------------

_FR_ORT = Location(latitude=42.0, longitude=9.0, name="Korsika (Test)")
_FR_GITTER = (6.0, 38.0, 12.0, 46.0)  # (west, south, east, north) -- deckt die
# gerundete Kachel um _FR_ORT (THUNDER_TILE_DEGREES=2.0) grosszuegig ab.


def _fr_raster(wert: float) -> bytes:
    """WCS liefert GRIB2 UNKOMPRIMIERT (anders als dwd.py) -- kein bz2."""
    hoehe, breite = 20, 20
    with MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff", height=hoehe, width=breite, count=1,
            dtype="float64", crs="EPSG:4326",
            transform=from_bounds(*_FR_GITTER, breite, hoehe),
        ) as dataset:
            dataset.write(np.full((hoehe, breite), wert, dtype="float64"), 1)
        return memfile.read()


class _FrServer(ThreadingHTTPServer):
    def __init__(self, addr, handler, *, offset_von_zeit, status_je_offset, inhalt):
        super().__init__(addr, handler)
        self.offset_von_zeit = offset_von_zeit  # zeit_str -> offset
        self.status_je_offset = status_je_offset  # offset -> HTTP-Status
        self.inhalt = inhalt  # offset -> bytes
        self.abrufe: list[int] = []
        self.lock = threading.Lock()


class _FrHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        srv = self.server
        query = parse_qs(urlparse(self.path).query)
        subsets = query.get("subset", [])
        zeit_roh = next((s for s in subsets if s.startswith("time(")), None)
        zeit = zeit_roh[len("time("):-1] if zeit_roh else None
        offset = srv.offset_von_zeit.get(zeit)
        with srv.lock:
            srv.abrufe.append(offset)
        status = srv.status_je_offset.get(offset, 200)
        if status != 200 or offset is None:
            self.send_response(status if offset is not None else 400)
            self.end_headers()
            return
        body = srv.inhalt(offset)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@contextmanager
def _fr_server(monkeypatch, *, run, offsets, status_je_offset=None, inhalt=None):
    offset_von_zeit = {
        (run + timedelta(hours=o)).strftime("%Y-%m-%dT%H:%M:%SZ"): o for o in offsets
    }
    srv = _FrServer(
        ("127.0.0.1", 0), _FrHandler,
        offset_von_zeit=offset_von_zeit,
        status_je_offset=status_je_offset or {},
        inhalt=inhalt or (lambda o: _fr_raster(0.2)),
    )
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    host, port = srv.server_address
    monkeypatch.setattr(meteofrance, "BASE_URL", f"http://{host}:{port}/", raising=True)
    monkeypatch.setattr(
        thunder_routing, "thunder_provider_for", lambda lat, lon: "fr_direct",
        raising=True,
    )
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


def _fr_fenster(stunden: int = 3):
    run = meteofrance._latest_run(datetime.now(timezone.utc))
    return run, run + timedelta(hours=stunden)


@pytest.fixture(autouse=True)
def _fr_cache_isoliert():
    """Isolation zwischen Testfaellen -- der Fenster-Zwischenspeicher ist ein
    Prozess-Singleton (`thunder_window_cache.py`)."""
    reset_thunder_window_cache_for_tests()
    yield
    reset_thunder_window_cache_for_tests()


# ---------------------------------------------------------------------------
# AC-6-Analogon (meteofrance.py) -- andere Schleifenform, dieselbe Regel.
# ---------------------------------------------------------------------------

def test_ac6_meteofrance_einzelner_fehlschlag_unter_vielen_wirft_keine_ausfallausnahme(
    monkeypatch,
):
    """Implementation Details Punkt 3, letzter Absatz: dieselbe Regel wie
    AC-6, hier fuer `fetch_thunder_signals_multi` (Gruppen x Offsets statt
    Einzelpunkt-Schleife). Ein Fehlschlag von drei Offsets darf keine
    Vertretung ausloesen.

    Hinweis (dokumentierte Ausnahme, gemessen): bereits HEUTE gruen, aus
    demselben Grund wie AC-6 (dwd.py) -- ohne Zaehllogik wirft
    `meteofrance.py` nie.
    """
    run, ende = _fr_fenster(stunden=3)
    with _fr_server(
        monkeypatch, run=run, offsets=(1, 2, 3), status_je_offset={2: 500},
    ) as srv:
        ergebnis = meteofrance.MeteoFranceDirectProvider().fetch_thunder_signals_multi(
            [_FR_ORT], start=None, end=ende,
        )
    assert srv.abrufe, "Der Server wurde nie kontaktiert -- nichts geprueft"
    reihe = ergebnis[_FR_ORT.name]
    assert reihe.get(2) is None, f"Offset 2 haette leer bleiben muessen: {reihe}"
    gefuellt = [o for o, w in reihe.items() if o != 2 and w is not None]
    assert gefuellt, (
        f"Kein einziger der uebrigen Offsets wurde gefuellt: {reihe} -- der "
        "einzelne Fehlschlag hat die ganze Reihe mitgerissen"
    )


# ---------------------------------------------------------------------------
# Zaehllogik-Nachweis (meteofrance.py): totaler Ausfall WIRFT.
# ---------------------------------------------------------------------------

def test_meteofrance_alle_offsets_verbindungsfehler_wirft_ausfallausnahme(monkeypatch):
    """Gegenstueck zu AC-1 am ECHTEN `fr_direct`-Provider (analog zum
    dwd.py-Nachweis oben). Given JEDER angefragte Offset antwortet mit 500,
    When `fetch_thunder_signals_multi` laeuft, Then wirft die Methode
    `base.ThunderSourceUnavailableError` mit `provider == "fr_direct"`.

    RED-Grund: `base.ThunderSourceUnavailableError` existiert nicht.
    """
    run, ende = _fr_fenster(stunden=3)
    with _fr_server(
        monkeypatch, run=run, offsets=(1, 2, 3),
        status_je_offset={1: 500, 2: 500, 3: 500},
    ) as srv:
        with pytest.raises(base.ThunderSourceUnavailableError) as excinfo:
            meteofrance.MeteoFranceDirectProvider().fetch_thunder_signals_multi(
                [_FR_ORT], start=None, end=ende,
            )
        assert srv.abrufe, "Der Server wurde nie kontaktiert -- nichts geprueft"
    assert excinfo.value.provider == "fr_direct", excinfo.value.provider


# ---------------------------------------------------------------------------
# Zwischenspeicher-Treffer zaehlt NICHT als Versuch (Implementation Details
# Punkt 3, letzter Absatz) -- Mutations-Gegenprobe gegen eine Zaehllogik, die
# faelschlich JEDE Schleifeniteration statt nur frische Abrufe zaehlt.
# ---------------------------------------------------------------------------

def test_meteofrance_zwischenspeicher_treffer_zaehlt_nicht_als_versuch(monkeypatch):
    """Given Offset 1 ist bereits im geteilten Fenster-Zwischenspeicher (ein
    vorheriger, erfolgreicher Abruf hat ihn befuellt), When ein zweiter
    Aufruf Offset 1 (Zwischenspeicher-Treffer) UND Offset 2 (frischer
    Abruf, scheitert) anfragt, Then wirft die Methode dennoch
    `ThunderSourceUnavailableError` -- der Zwischenspeicher-Treffer darf NICHT
    als zusaetzlicher "Versuch" mitgezaehlt werden, sonst waere
    `fehlgeschlagen (1) < versucht (2)` und die Ausnahme bliebe faelschlich
    aus, obwohl JEDER tatsaechlich frische Abruf gescheitert ist.

    Ausgangswert (1 frischer Fehlschlag), Ableitungsquelle (Zaehllogik, die
    Zwischenspeicher-Treffer bewusst NICHT zaehlt) und Sollwert (Wurf trotz
    scheinbar "nur 1 von 2" Anfragen) sind drei unterscheidbare Groessen.

    RED-Grund: `base.ThunderSourceUnavailableError` existiert nicht.
    """
    run, ende_kurz = _fr_fenster(stunden=1)
    with _fr_server(monkeypatch, run=run, offsets=(1,)) as srv:
        vorlauf = meteofrance.MeteoFranceDirectProvider().fetch_thunder_signals_multi(
            [_FR_ORT], start=None, end=ende_kurz,
        )
        assert any(v is not None for v in vorlauf[_FR_ORT.name].values()), (
            "Der Vorlauf-Abruf hat den Zwischenspeicher nicht befuellt -- "
            "der Test haette dann keine Grundlage"
        )
        erste_abrufzahl = len(srv.abrufe)

    _, ende_lang = _fr_fenster(stunden=2)
    with _fr_server(
        monkeypatch, run=run, offsets=(1, 2), status_je_offset={2: 500},
    ) as srv2:
        with pytest.raises(base.ThunderSourceUnavailableError) as excinfo:
            meteofrance.MeteoFranceDirectProvider().fetch_thunder_signals_multi(
                [_FR_ORT], start=None, end=ende_lang,
            )
        # Offset 1 darf beim ZWEITEN Server gar nicht mehr ankommen -- er
        # kommt aus dem Zwischenspeicher des ERSTEN Servers.
        assert 1 not in srv2.abrufe, (
            f"Offset 1 wurde erneut ueber HTTP angefragt ({srv2.abrufe}) -- "
            "der Zwischenspeicher-Treffer aus dem Vorlauf griff nicht, der "
            "Test kann die Zaehllogik dann nicht isoliert pruefen"
        )
    assert excinfo.value.attempted == 1, (
        f"attempted={excinfo.value.attempted} -- erwartet 1 (nur der frische, "
        f"gescheiterte Offset 2; der Zwischenspeicher-Treffer aus {erste_abrufzahl} "
        "Vorlauf-Abrufen darf nicht mitgezaehlt werden)"
    )
