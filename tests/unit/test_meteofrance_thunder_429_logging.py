"""#1993: Meteo-France-Rate-Limit (HTTP 429) beim Blitzdichte-Abruf
(`fetch_thunder_signals_multi`) fiel bisher in denselben generischen
"nicht abrufbar"-Log-Pfad wie jeder andere Fehlschlag -- im Betrieb nicht
von echtem Datenausfall unterscheidbar. Seit dieser Scheibe erzeugt ein
429 eine eigene, unterscheidbare WARNING-Zeile ("gedrosselt"/"429"), waehrend
andere Fehlerstatus (z. B. 500) unveraendert die generische Meldung behalten.
Der Rueckgabewert (`None` fuer das betroffene Zeitfenster) aendert sich in
BEIDEN Faellen nicht -- geprueft ueber den produktiven Weg
`fetch_forecast()` (analog `test_meteofrance_forecast_survives_thunder_outage.py`).

===========================================================================
Lokaler HTTP-Server unter dem Egress-Waechter
===========================================================================
Wie im Vorbild-Test: `ThreadingHTTPServer` auf 127.0.0.1, kein Mock-Theater
-- der Test treibt echtes HTTP-Verhalten durch den echten
`MeteoFranceDirectProvider._request`/`_request_once`-Pfad. Kein Marker
noetig, `--disable-socket --allow-hosts=127.0.0.1,::1,localhost` erlaubt
127.0.0.1 ausdruecklich (`.github/workflows/ci.yml`).
"""
from __future__ import annotations

import logging
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location  # noqa: E402
from providers import meteofrance, thunder_routing  # noqa: E402
from providers.thunder_window_cache import (  # noqa: E402
    reset_thunder_window_cache_for_tests,
)

_ORT = Location(latitude=42.0, longitude=9.0, name="Korsika (Test)")
_GITTER = (6.0, 38.0, 12.0, 46.0)  # (west, south, east, north)


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


class _Server(ThreadingHTTPServer):
    def __init__(self, addr, handler):
        super().__init__(addr, handler)
        self.abrufe: list[str] = []
        self.lock = threading.Lock()


def _make_handler(lightning_status: int):
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            srv = self.server
            query = parse_qs(urlparse(self.path).query)
            coverage_id = query.get("coverageId", [""])[0]
            with srv.lock:
                srv.abrufe.append(coverage_id)
            if coverage_id.startswith(meteofrance.LIGHTNING_COVERAGE):
                self.send_response(lightning_status)
                self.end_headers()
                return
            body = _raster(15.5)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    return _Handler


@contextmanager
def _server(monkeypatch, lightning_status: int):
    srv = _Server(("127.0.0.1", 0), _make_handler(lightning_status))
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


def test_429_erzeugt_drosselungs_meldung_statt_generische_meldung(monkeypatch, caplog):
    """429 auf JEDEM Blitzdichte-Offset -> eigene, unterscheidbare
    WARNING-Zeile ("gedrosselt"/"429"), NICHT die generische
    "nicht abrufbar"-Formulierung. Zeitfenster bleibt `None`."""
    reset_thunder_window_cache_for_tests()
    with caplog.at_level(logging.WARNING, logger="meteofrance"):
        with _server(monkeypatch, lightning_status=429) as srv:
            ergebnis = meteofrance.MeteoFranceDirectProvider().fetch_forecast(_ORT)

    lightning_abrufe = [
        c for c in srv.abrufe if c.startswith(meteofrance.LIGHTNING_COVERAGE)
    ]
    assert lightning_abrufe, (
        "Der Blitzdichte-Endpunkt wurde nie angefragt -- der 429-Fall "
        "wurde nicht geprueft"
    )

    warn_texte = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    drossel_zeilen = [t for t in warn_texte if "429" in t or "gedrosselt" in t]
    assert drossel_zeilen, (
        f"Keine Drosselungs-Meldung geloggt -- gesehene WARNING-Zeilen: {warn_texte}"
    )
    generische_zeilen = [t for t in warn_texte if "nicht abrufbar" in t]
    assert not generische_zeilen, (
        f"429 haette NICHT die generische 'nicht abrufbar'-Meldung erzeugen "
        f"duerfen: {generische_zeilen}"
    )

    assert all(dp.lightning_density_per_km2_3h is None for dp in ergebnis.data), (
        "Zeitfenster haette bei 429 None bleiben muessen: "
        f"{[dp.lightning_density_per_km2_3h for dp in ergebnis.data]}"
    )


def test_500_behaelt_generische_meldung(monkeypatch, caplog):
    """Gegenprobe: ein anderer Fehlerstatus (500) bleibt bei der bisherigen
    generischen "nicht abrufbar"-Meldung. Zeitfenster bleibt `None`."""
    reset_thunder_window_cache_for_tests()
    with caplog.at_level(logging.WARNING, logger="meteofrance"):
        with _server(monkeypatch, lightning_status=500) as srv:
            ergebnis = meteofrance.MeteoFranceDirectProvider().fetch_forecast(_ORT)

    lightning_abrufe = [
        c for c in srv.abrufe if c.startswith(meteofrance.LIGHTNING_COVERAGE)
    ]
    assert lightning_abrufe, (
        "Der Blitzdichte-Endpunkt wurde nie angefragt -- der 500-Fall "
        "wurde nicht geprueft"
    )

    warn_texte = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    generische_zeilen = [t for t in warn_texte if "nicht abrufbar" in t]
    assert generische_zeilen, (
        f"Die bisherige generische Meldung fehlt -- gesehene WARNING-Zeilen: {warn_texte}"
    )
    drossel_zeilen = [t for t in warn_texte if "gedrosselt" in t]
    assert not drossel_zeilen, (
        f"500 haette KEINE Drosselungs-Meldung erzeugen duerfen: {drossel_zeilen}"
    )

    assert all(dp.lightning_density_per_km2_3h is None for dp in ergebnis.data), (
        "Zeitfenster haette bei 500 None bleiben muessen: "
        f"{[dp.lightning_density_per_km2_3h for dp in ergebnis.data]}"
    )
