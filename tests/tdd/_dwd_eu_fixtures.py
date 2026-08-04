"""Gemeinsame Test-Naht fuer die ICON-EU-Gewitterquelle (#1457 S2c).

Spec: docs/specs/modules/feat_1457_s2c_icon_eu_luekenfueller.md

===========================================================================
EMPIRISCHE VERMESSUNG DES ECHTEN DIENSTES (2026-08-04, opendata.dwd.de)
===========================================================================
Die Spec markiert Abrufname, Fehlwert-Marker und Zeitbudget ausdruecklich als
Arbeitshypothese (Known Limitations 1/2/5) — nach der `LITOTA3`-Lehre aus S2a.
Deshalb wurde VOR diesen Tests gegen den echten Dienst gemessen:

1. ABRUFNAME — Hypothese BESTAETIGT. Unter `.../icon-eu/grib/<HH>/` existiert
   der Ordner `lpi_con_max` (einziges Gewittersignal; `grau_gsp` gibt es bei
   ICON-EU NICHT, Spec Known Limitation 3 bestaetigt).
2. DATEINAMENS-SCHEMA — ANDERS als ICON-D2, `dwd._build_url` traegt hier NICHT:
     .../00/lpi_con_max/icon-eu_europe_regular-lat-lon_single-level_
     2026080400_015_LPI_CON_MAX.grib2.bz2
   Unterschiede: `icon-eu_europe_` statt `icon-d2_germany_`, Suffix
   `_LPI_CON_MAX` (GROSS) statt `_2d_<param>` (klein).
3. ZEITSCHRITTE: 000..048 STUENDLICH, danach nur noch dreistuendig bis 120.
   Der stuendliche Teil endet also bei +48 h wie bei ICON-D2.
4. GITTER (rasterio `dataset.bounds` einer echten Antwort):
     left=-23.53125 bottom=29.46875 right=62.53125 top=70.53125
   Aufloesung 0,0625 Grad (~6,5 km), 657 x 1377 Bildpunkte, float64.
5. FEHLWERT-MARKER — es gibt KEINEN: `dataset.nodata` ist `None`, die Maske ist
   leer, kein Wert < 0 und keiner >= 9999. Anders als bei ICON-D2 deckt das
   ausgelieferte Rechteck das Modellgebiet vollstaendig ab. Der Fehlwert-Test
   unten prueft deshalb die ZUSAGE (ein als Fehlwert markierter Bildpunkt wird
   nie durchgereicht), nicht eine erfundene Zahl — ICON-D2s 9999.0 wird
   ausdruecklich NICHT uebernommen (S2a/S2b-Lehre: Analogie war zweimal falsch).
6. LATENZ je Datei (gemessen, 6 kalte Abrufe): Download 0,043-0,069 s
   (~100-180 KB), bz2+rasterio-Auswertung 0,035 s — zusammen ~0,085 s.
   Grundlage der Herleitung des eigenen Zeitbudgets (Spec AC-4): EIN Signal
   x bis zu 24 Zeitschritte, kein Hagel, kein Kumulations-Anker.
7. LAUF-VERFUEGBARKEIT: gemessen am 2026-08-04 um 07:32 UTC war der 03Z-Lauf
   veroeffentlicht (~4,5 h alt), der 06Z-Lauf noch NICHT (~1,5 h alt); der
   00Z-Lauf war um 03:37 UTC vollstaendig (~3,6 h). ICON-EU braucht damit
   deutlich laenger als ICON-D2 (~1,4 h) — der Sicherheitsabstand von
   `dwd._latest_run` (3 h) reicht hier NICHT, und der Rueckfall auf aeltere
   Laeufe (AC-7) ist Pflicht, nicht Kuer.
8. `lpi_con_max` ist laut GRIB-Kopf ein MAXIMUM ueber die letzten 60 Minuten
   (statistischer Prozess 2, Dauer 60 min), also KEIN kumulierter Wert —
   die Differenzbildung von `grau_gsp` (S2b) darf hier nicht angewandt werden.

AUFZEICHNUNG: `icon_eu_abruzzen_lpi_con_max_2026080400_015.grib2.bz2`
(echt abgerufen 2026-08-04, Lauf 2026-08-04T00Z, Zeitschritt +15 h). Traegt in
den Abruzzen (41,8125 N / 13,3750 O) ein echtes Gewitter. Erwartungswerte
werden je Testlauf ERNEUT aus der Aufzeichnung gelesen (`rohwert_an`), nie hart
hineingeschrieben — Projektlehre aus #1144.

Testart aller Nutzer dieser Naht: Kern-Schicht. Kein Netz — ein echter lokaler
`ThreadingHTTPServer` liefert die Aufzeichnung aus. Keine Mocks.
"""
from __future__ import annotations

import bz2
import json
import re
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location  # noqa: E402
from providers import openmeteo as om  # noqa: E402

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "dwd"
    / "icon_eu_abruzzen_lpi_con_max_2026080400_015.grib2.bz2"
)

# Abruzzen (Apennin, IT) — liegt AUSSERHALB beider bestehenden Gewittergebiete
# (FR: 41,3..51,1 N / -5,2..9,7 O; DE_ALPEN: 43,17..58,09 N / -3,95..20,35 O)
# und traegt in der Aufzeichnung ein echtes Gewitter (lpi 217,8 J/kg).
ABRUZZEN = Location(latitude=41.8125, longitude=13.3750, name="Abruzzen")
# Gemessene ICON-EU-Gittergrenzen (s. Punkt 4) — Kunst-Raster decken damit
# dieselbe Flaeche ab wie die Aufzeichnung.
GITTER = (-23.53125, 29.46875, 62.53125, 70.53125)

_DATEINAME = re.compile(r"_(\d{10})_(\d{3})_")


def dwd_eu():
    """Der Pruefling. Bewusst SPAET importiert, damit jeder Test einzeln mit
    seinem eigenen Grund rot wird, statt die ganze Datei beim Einsammeln zu
    kippen."""
    from providers import dwd_eu as modul

    return modul


def rohwert_an(bz2_bytes: bytes, lat: float, lon: float) -> float:
    """Test-lokale Referenzimplementierung, unabhaengig vom Pruefling."""
    with MemoryFile(bz2.decompress(bz2_bytes)) as memfile, memfile.open() as ds:
        row, col = ds.index(lon, lat)
        return float(ds.read(1)[row, col])


def kunst_raster(wert: float, nodata: Optional[float] = None) -> bytes:
    """Rasterdatei mit konstantem Wert ueber das ganze ICON-EU-Rechteck,
    bz2-gepackt wie beim echten Dienst. Mit `nodata` wird der Wert als
    Fehlwert MARKIERT — genau so, wie ein Dienst "keine Aussage" ausdrueckt."""
    hoehe, breite = 40, 80
    with MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff", height=hoehe, width=breite, count=1, dtype="float64",
            crs="EPSG:4326", nodata=nodata,
            transform=from_bounds(*GITTER, breite, hoehe),
        ) as ds:
            ds.write(np.full((hoehe, breite), wert, dtype="float64"), 1)
        return bz2.compress(memfile.read())


class _Server(ThreadingHTTPServer):
    def __init__(self, adresse, handler, *, inhalt, status_je_lauf,
                 fehlende_zeitschritte, verzoegerung_s):
        super().__init__(adresse, handler)
        self.inhalt = inhalt
        self.status_je_lauf = status_je_lauf
        self.fehlende_zeitschritte = fehlende_zeitschritte
        self.verzoegerung_s = verzoegerung_s
        self.abrufe: list[tuple[str, int]] = []   # (Lauf, Zeitschritt)
        self._lock = threading.Lock()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        srv = self.server
        if srv.verzoegerung_s:
            time.sleep(srv.verzoegerung_s)
        treffer = _DATEINAME.search(urlparse(self.path).path)
        if treffer is None:
            self.send_response(404)
            self.end_headers()
            return
        lauf, ttt = treffer.group(1), int(treffer.group(2))
        with srv._lock:
            srv.abrufe.append((lauf, ttt))
        status = srv.status_je_lauf.get(lauf, 200)
        if ttt in srv.fehlende_zeitschritte:
            status = 404
        if status != 200:
            self.send_response(status)
            self.end_headers()
            return
        body = srv.inhalt(lauf, ttt)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class AlleLaeufe(dict):
    """Antwortet fuer JEDEN Lauf mit demselben Status — auch fuer jeden
    Rueckfall-Kandidaten, den der Pruefling selbst bestimmt."""

    def __init__(self, status: int) -> None:
        super().__init__()
        self._status = status

    def get(self, key, default=None):  # noqa: D102
        return self._status


@contextmanager
def eu_server(monkeypatch, *, inhalt=None, status_je_lauf=None,
              fehlende_zeitschritte=None, verzoegerung_s=0.0):
    """Lokaler Server unter `dwd_eu.BASE_URL`. Lauf und Zeitschritt bestimmt
    der Pruefling selbst — der Test raet sie nie."""
    aufzeichnung = FIXTURE.read_bytes()
    srv = _Server(
        ("127.0.0.1", 0), _Handler,
        inhalt=inhalt or (lambda lauf, ttt: aufzeichnung),
        status_je_lauf=status_je_lauf if status_je_lauf is not None else {},
        fehlende_zeitschritte=fehlende_zeitschritte or set(),
        verzoegerung_s=verzoegerung_s,
    )
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(dwd_eu(), "BASE_URL", "http://%s:%d/" % srv.server_address)
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


@contextmanager
def hauptquelle_laeuft(monkeypatch, ort: Location, stunden: int = 6):
    """Open-Meteo antwortet normal — der REGULAERE Weg, KEIN Totalausfall
    (Muster test_thunder_named_signals_enrichment.py).

    `stunden` bestimmt die Laenge der Vorhersagereihe und damit die NATUERLICHE
    Obergrenze der Gewitter-Abrufe: der Anschluss leitet das Abruffenster aus
    der Reihe ab. Wer eine Zeitgrenze pruefen will, MUSS hier so viele Stunden
    bestellen, dass die Fixture nicht selbst zum Deckel wird — sonst prueft die
    Assertion die Fixture statt der Zeitgrenze (Adversary-Befund F003, Runde 2).
    """
    basis = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    zeiten = [
        (basis + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M")
        for h in range(stunden)
    ]
    n = len(zeiten)
    body = json.dumps({
        "latitude": ort.latitude, "longitude": ort.longitude,
        "generationtime_ms": 0.1, "utc_offset_seconds": 0, "timezone": "GMT",
        "hourly_units": {"temperature_2m": "°C"},
        "hourly": {
            "time": zeiten, "temperature_2m": [15.0 + i * 0.5 for i in range(n)],
            "wind_speed_10m": [5.0] * n, "wind_direction_10m": [180] * n,
            "wind_gusts_10m": [12.0] * n, "precipitation": [0.0] * n,
            "weather_code": [1] * n, "cape": [0.0] * n, "is_day": [1] * n,
        },
    }).encode("utf-8")

    class _OmHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _OmHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(om, "BASE_HOST", "http://%s:%d" % srv.server_address)
    monkeypatch.setattr(om, "ENSEMBLE_BASE_HOST", "http://%s:%d" % srv.server_address)
    try:
        yield srv
    finally:
        srv.shutdown()
