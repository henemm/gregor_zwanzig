"""TDD RED -- #1507 (S5c zu #1475, Epic #1419, Block C von #2257): neuer
Hagel-Rohwert von Meteo-France fuer FR/Korsika, GETRENNT von `hail_flag`.

Spec: docs/specs/modules/feat_1507_s5c_hagel_mf_fr.md (AC-2, AC-3, AC-4)

`MeteoFranceDirectProvider.fetch_forecast` soll zusaetzlich zur Blitzdichte
(`LIGHTNING_COVERAGE`, #1457 S2a) einen zweiten Coverage-Abruf machen und den
Rohwert in einem NEUEN Feld (`ForecastDataPoint.hail_potential_mf`) ablegen.
`hail_flag` (#1475 S5a, WMO-Code-Ableitung) bleibt davon vollstaendig
unberuehrt -- `fr_direct` setzt strukturell keinen `wmo_code`, eine
Cross-Provider-Fusion ist ausdruecklich NICHT Teil dieser Scheibe (AC-4).

MOCK-FREI: echter lokaler `ThreadingHTTPServer`, Muster 1:1 aus
`tests/unit/test_meteofrance_forecast_survives_thunder_outage.py`
(Handler routet nach `coverageId`-Query-Parameter, synthetisches GTiff-Raster
statt einem echten GRIB2-Fixture -- rasterio erkennt den Treiber aus den
Bytes, das Format der Antwort ist fuer den Testzweck irrelevant).

Sowohl `meteofrance.HAIL_COVERAGE` als auch
`MeteoFranceDirectProvider.fetch_hail_signals_multi` und
`ForecastDataPoint.hail_potential_mf` existieren VOR der Implementierung
noch nicht -- diese Tests sind bewusst ROT (AttributeError), bis die
GREEN-Phase sie anlegt.
"""
from __future__ import annotations

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

# Korsika -- liegt im AROME-Gebiet (analog test_thunder_source_failure_detection.py).
_ORT = Location(latitude=42.0, longitude=9.0, name="Korsika (Test)")
_GITTER = (6.0, 38.0, 12.0, 46.0)  # (west, south, east, north)
_HAGEL_ROHWERT = 42.0


def _raster(wert: float) -> bytes:
    """Synthetisches GTiff, ein Band -- rasterio erkennt den Treiber aus den
    Bytes selbst, das Format der Antwort spielt fuer `_read_point_value`/
    `_read_window_values` keine Rolle."""
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


def _make_handler(hagel_status: int):
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            srv = self.server
            query = parse_qs(urlparse(self.path).query)
            coverage_id = query.get("coverageId", [""])[0]
            with srv.lock:
                srv.abrufe.append(coverage_id)
            if coverage_id.startswith(meteofrance.HAIL_COVERAGE):
                if hagel_status != 200:
                    self.send_response(hagel_status)
                    self.end_headers()
                    return
                body = _raster(_HAGEL_ROHWERT)
            else:
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
def _server(monkeypatch, hagel_status: int):
    srv = _Server(("127.0.0.1", 0), _make_handler(hagel_status))
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


def _isoliere_thunder_cache():
    """Isolation gegen den geteilten Fenster-Zwischenspeicher (Prozess-
    Singleton) -- analog `test_meteofrance_forecast_survives_thunder_outage.py`."""
    reset_thunder_window_cache_for_tests()


def test_ac3_ac4_hagel_rohwert_landet_im_neuen_feld_ohne_hail_flag_zu_beeinflussen(
    monkeypatch,
):
    """AC-3/AC-4: Given ein erfolgreicher Hagel-Coverage-Abruf, When
    `fetch_forecast` laeuft, Then landet der Rohwert in `hail_potential_mf`
    UND `hail_flag` bleibt exakt `None` (fr_direct fuehrt keinen wmo_code) --
    keine Kombination der beiden Felder.

    Gegenprobe (Mutationskandidat): Wird der neue Rohwert versehentlich in
    eine `hail_flag`-Ableitung eingespeist, muss dieser Test rot werden.
    """
    _isoliere_thunder_cache()
    with _server(monkeypatch, hagel_status=200) as srv:
        ergebnis = meteofrance.MeteoFranceDirectProvider().fetch_forecast(_ORT)

    hagel_abrufe = [
        c for c in srv.abrufe if c.startswith(meteofrance.HAIL_COVERAGE)
    ]
    assert hagel_abrufe, (
        "Der Hagel-Endpunkt wurde nie angefragt -- der neue Coverage-Abruf "
        "ist nicht verdrahtet"
    )
    assert any(dp.hail_potential_mf == _HAGEL_ROHWERT for dp in ergebnis.data), (
        f"Kein Datenpunkt traegt den Hagel-Rohwert {_HAGEL_ROHWERT} im neuen "
        f"Feld: {[dp.hail_potential_mf for dp in ergebnis.data]}"
    )
    assert all(dp.hail_flag is None for dp in ergebnis.data), (
        "hail_flag ist nicht mehr None -- der neue Hagel-Rohwert wurde "
        "(verboten) in die WMO-Code-Ableitung eingespeist"
    )


def test_ac2_hagel_endpunkt_ausfall_liefert_none_nie_null_und_kippt_die_vorhersage_nicht(
    monkeypatch,
):
    """AC-2: Given einen Hagel-Endpunkt, der fuer JEDEN Offset 404 liefert,
    When `fetch_forecast` laeuft, Then bleibt `hail_potential_mf` `None`
    (NIEMALS `0.0`) und die Grunddaten (Temperatur) UND `hail_flag` bleiben
    unberuehrt -- ein scheiternder Hagel-Abruf kippt die Vorhersage nicht.
    """
    _isoliere_thunder_cache()
    with _server(monkeypatch, hagel_status=404) as srv:
        ergebnis = meteofrance.MeteoFranceDirectProvider().fetch_forecast(_ORT)

    hagel_abrufe = [
        c for c in srv.abrufe if c.startswith(meteofrance.HAIL_COVERAGE)
    ]
    assert hagel_abrufe, (
        "Der Hagel-Endpunkt wurde nie angefragt -- der Ausfallfall ist nicht "
        "geprueft"
    )
    assert all(dp.hail_potential_mf is None for dp in ergebnis.data), (
        f"Bei einem 404-Totalausfall darf kein Hagel-Rohwert stehen, erst "
        f"recht keine 0.0: {[dp.hail_potential_mf for dp in ergebnis.data]}"
    )
    assert any(dp.t2m_c is not None for dp in ergebnis.data), (
        "Grunddaten (Temperatur) sind trotz Hagel-Totalausfall verloren "
        "gegangen"
    )
    assert all(dp.hail_flag is None for dp in ergebnis.data), (
        "hail_flag wurde durch den gescheiterten Hagel-Abruf veraendert"
    )
