"""TDD RED -- #1507 (S5c zu #1475): der neue Hagel-Coverage-Abruf TEILT sich
das Zeitbudget mit der Blitzdichte, statt ein zweites unabhaengiges
Vollbudget zu bekommen.

Spec: docs/specs/modules/feat_1507_s5c_hagel_mf_fr.md (AC-5)

Analog zu `test_f003_...` in `tests/tdd/test_thunder_budget_and_failsoft.py`:
nur wenn der Hagel-Abruf DENSELBEN `THUNDER_FETCH_DEADLINE_SECONDS`-Wert
liest wie die Blitzdichte, bricht er bei einer kuenstlich kleingesetzten
gemeinsamen Zeitgrenze rechtzeitig ab. Eine eigene, unabhaengige
Hagel-Deadline-Konstante mit eigenem Default wuerde diesen Test NICHT
bestehen -- die volle Antwortzeit des langsamen Servers wuerde durchlaufen.

`MeteoFranceDirectProvider.fetch_hail_signals_multi` existiert VOR der
Implementierung noch nicht -- dieser Test ist bewusst ROT (AttributeError),
bis die GREEN-Phase ihn anlegt und dabei dasselbe geteilte Budget nutzt.

Testart: Kern-Schicht, echter lokaler HTTP-Server, kein Netz.
"""
from __future__ import annotations

import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location  # noqa: E402
from providers import meteofrance as mf  # noqa: E402

_KORSIKA = Location(latitude=42.22, longitude=9.07, name="GR20 Petra Piana")
_GITTER = (6.0, 38.0, 12.0, 46.0)

# Der langsame Dienst braucht deutlich laenger als die Zeitgrenze -- nur dann
# unterscheiden sich "geteiltes Budget" (Abbruch bei Restzeit) und "eigenes,
# unabhaengiges Budget" (Abbruch erst nach der vollen Antwort) messbar.
_ANTWORTZEIT_S = 1.0
_ZEITGRENZE_S = 0.3


def _raster(wert: float) -> bytes:
    hoehe, breite = 20, 20
    with MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff", height=hoehe, width=breite, count=1,
            dtype="float64", crs="EPSG:4326",
            transform=from_bounds(*_GITTER, breite, hoehe),
        ) as dataset:
            dataset.write(np.full((hoehe, breite), wert, dtype="float64"), 1)
        return memfile.read()


def test_ac5_hagel_abruf_teilt_sich_die_zeitgrenze_mit_der_blitzdichte(monkeypatch):
    """AC-5: Given einen langsamen Hagel-Endpunkt UND eine kuenstlich
    kleingesetzte `THUNDER_FETCH_DEADLINE_SECONDS`, When der Hagel-Rohwert
    geholt wird, Then endet der Aufruf nahe DIESER Zeitgrenze -- er nutzt
    dasselbe Budget wie die Blitzdichte, kein zweites, unabhaengiges
    Vollbudget.

    Gegenprobe (Mutationskandidat): Fuehrt die Implementierung eine eigene
    `HAIL_FETCH_DEADLINE_SECONDS`-Konstante mit eigenem Default ein, bleibt
    dieses Monkeypatch wirkungslos und der Aufruf laeuft bis zur vollen
    Serverantwort (~1,0s) statt bei ~0,3s abzubrechen -- der Test wird rot.
    """
    grib = _raster(7.0)

    class _LangsamerHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            time.sleep(_ANTWORTZEIT_S)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(grib)))
            self.end_headers()
            self.wfile.write(grib)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _LangsamerHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(mf, "BASE_URL", "http://%s:%d/" % srv.server_address)
    monkeypatch.setattr(mf, "THUNDER_FETCH_DEADLINE_SECONDS", _ZEITGRENZE_S)

    try:
        provider = mf.MeteoFranceDirectProvider()
        beginn = time.monotonic()
        ergebnis = provider.fetch_hail_signals_multi([_KORSIKA])
        dauer = time.monotonic() - beginn
    finally:
        srv.shutdown()

    obergrenze = (_ANTWORTZEIT_S + _ZEITGRENZE_S) / 2
    assert dauer < obergrenze, (
        f"Der Hagel-Abruf lief {dauer:.2f}s bei einer (gemeinsamen) "
        f"Zeitgrenze von {_ZEITGRENZE_S}s -- er hat die volle Antwort "
        f"({_ANTWORTZEIT_S}s) abgewartet, statt dasselbe Budget wie die "
        "Blitzdichte zu teilen"
    )
    werte = [v for v in (ergebnis.get(_KORSIKA.name) or {}).values() if v is not None]
    assert not werte, (
        "Es kamen Werte an, obwohl kein Abruf innerhalb der geteilten "
        "Zeitgrenze fertig werden konnte -- der Test misst dann nicht, was "
        "er soll"
    )
