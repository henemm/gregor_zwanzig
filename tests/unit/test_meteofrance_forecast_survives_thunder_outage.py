"""#1492 S2a Adversary F001 (CRITICAL): produktiver Aufrufer
`MeteoFranceDirectProvider.fetch_forecast()` musste bisher NIE mit einer
Ausnahme aus der Gewitter-Anreicherung rechnen ("Best effort, fail-soft --
wirft NIE"). Seit dieser Scheibe kann `fetch_thunder_signals()` (ueber
`fetch_thunder_signals_multi`) bei einem Totalausfall der Blitzdichte-Quelle
`ThunderSourceUnavailableError` werfen (Implementation Details Punkt 3,
`meteofrance.py:715-716`). Der Aufruf bei `meteofrance.py:756` lag
UNGESCHUETZT ausserhalb jedes try/except -- ein Blitz-Totalausfall haette die
GESAMTE Vorhersage (inkl. Temperatur/Wind/Niederschlag, bereits erfolgreich
abgerufen) zum Absturz gebracht, obwohl der Kommentar direkt darueber das
Gegenteil verspricht: "scheitert die Anreicherung, bleibt die Vorhersage
unversehrt und nur das Blitzfeld leer" (AC-3/AC-4/AC-5 aus #1457 S2a).

Produktiv erreichbar ueber `openmeteo.py:1051`
(`get_provider("fr_direct").fetch_forecast(...)`, Cross-Provider-Totalausfall
bei einem Ort in Frankreich/Korsika) -- der dortige `except`
(`openmeteo.py:1065`) faengt NUR `ProviderNotImplementedError`,
`ProviderRequestError`, `ProviderNotFoundError`, NICHT den neuen Typ.

Geprueft wird hier der PRODUKTIVE Weg (`fetch_forecast`), nicht die
Anreicherungsebene (`thunder_enrichment`, dort bereits durch
`test_thunder_source_substitution.py` AC-5 abgedeckt) -- AC-5 dort prueft nur
den generischen Aufrufer `enrich_thunder()`. Der ECHTE `fr_direct`-Provider
ruft seine Gewittersignale aber SELBST ab (`fetch_thunder_signals`, nicht
ueber `thunder_enrichment`), ein eigener, bisher ungeschuetzter Code-Pfad.

===========================================================================
Lokaler HTTP-Server unter dem Egress-Waechter
===========================================================================
Wie `test_thunder_source_failure_detection.py`: `ThreadingHTTPServer` auf
127.0.0.1, keine In-Memory-Fakes -- der Test muss echtes HTTP-Verhalten
(200 fuer Grunddaten, 500 fuer JEDEN Blitzdichte-Offset) durch den echten
`MeteoFranceDirectProvider._request`/`_request_once`-Pfad treiben. Kein
Marker noetig, dieselbe CI-Konfiguration
(`--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost`,
`.github/workflows/ci.yml:46-47`) erlaubt 127.0.0.1 ausdruecklich.
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
# Rechteck, das sowohl das 0,1-Grad-Kaestchen der Grunddaten-Abrufe (lat/lon
# +-0.05) als auch das (groessere) Blitzdichte-Fenster um _ORT abdeckt.
_GITTER = (6.0, 38.0, 12.0, 46.0)  # (west, south, east, north)


def _raster(wert: float) -> bytes:
    """GTiff, unkomprimiert -- wie `_fr_raster` in
    `test_thunder_source_failure_detection.py`, hier fuer alle
    Grunddaten-Coverages (Temperatur/Wind/Niederschlag) wiederverwendet."""
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


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        srv = self.server
        query = parse_qs(urlparse(self.path).query)
        coverage_id = query.get("coverageId", [""])[0]
        with srv.lock:
            srv.abrufe.append(coverage_id)
        if coverage_id.startswith(meteofrance.LIGHTNING_COVERAGE):
            # JEDER Blitzdichte-Offset scheitert -- Totalausfall der Quelle.
            self.send_response(500)
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


@contextmanager
def _server(monkeypatch):
    srv = _Server(("127.0.0.1", 0), _Handler)
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
    Singleton) -- analog `_fr_cache_isoliert` in
    `test_thunder_source_failure_detection.py`, hier ohne autouse-Fixture,
    weil diese Datei nur einen einzigen Test enthaelt."""
    reset_thunder_window_cache_for_tests()


def test_fetch_forecast_liefert_vollstaendige_vorhersage_trotz_blitz_totalausfall(
    monkeypatch,
):
    """F001: Gewitter-Endpunkt faellt komplett aus (JEDER Blitzdichte-Offset
    antwortet 500 -> `ThunderSourceUnavailableError`), Grunddaten
    (Temperatur/Wind/Niederschlag) sind da (200) => `fetch_forecast()`
    liefert eine VOLLSTAENDIGE Vorhersage zurueck, Blitzfeld leer, KEINE
    Ausnahme.

    Ausgangswert (Grunddaten erfolgreich, isoliert vom Blitzdichte-Abruf
    ueber den separaten Coverage-Namen), Ableitungsquelle (die neue
    Zaehllogik in `fetch_thunder_signals_multi`, die bei Totalausfall wirft)
    und Sollwert (vollstaendige Vorhersage, kein Wurf) sind drei
    unterscheidbare Groessen -- ohne den Fang bei `meteofrance.py:756` wuerde
    dieser Test mit einer unbehandelten `ThunderSourceUnavailableError`
    abbrechen statt gruen zu laufen.

    Gegenprobe (Adversary-Auftrag, manuell durchgefuehrt): Entfernt man den
    `except ThunderSourceUnavailableError`-Block um den Aufruf bei
    `meteofrance.py:756`, wird DIESER Test rot (unbehandelte Ausnahme statt
    eines sauberen Rueckgabewerts).
    """
    _isoliere_thunder_cache()
    with _server(monkeypatch) as srv:
        ergebnis = meteofrance.MeteoFranceDirectProvider().fetch_forecast(_ORT)

    lightning_abrufe = [
        c for c in srv.abrufe if c.startswith(meteofrance.LIGHTNING_COVERAGE)
    ]
    assert lightning_abrufe, (
        "Der Blitzdichte-Endpunkt wurde nie angefragt -- der Totalausfall "
        "wurde nicht geprueft"
    )
    grunddaten_abrufe = [
        c for c in srv.abrufe if not c.startswith(meteofrance.LIGHTNING_COVERAGE)
    ]
    assert grunddaten_abrufe, (
        "Kein Grunddaten-Abruf fand statt -- ohne diese Vorbedingung ist "
        "'vollstaendige Vorhersage' nicht pruefbar"
    )

    assert len(ergebnis.data) == 24, (
        f"Erwartet 24 Datenpunkte (FORECAST_HOURS), bekommen {len(ergebnis.data)} -- "
        "die Vorhersage ist nicht vollstaendig."
    )
    assert any(dp.t2m_c is not None for dp in ergebnis.data), (
        "Kein einziger Temperaturwert gefuellt -- Grunddaten sind nicht "
        "durchgekommen."
    )
    assert any(dp.wind10m_kmh is not None for dp in ergebnis.data), (
        "Kein einziger Windwert gefuellt -- Grunddaten sind nicht "
        "durchgekommen."
    )
    assert any(dp.precip_1h_mm is not None for dp in ergebnis.data), (
        "Kein einziger Niederschlagswert gefuellt -- Grunddaten sind nicht "
        "durchgekommen."
    )
    assert all(dp.lightning_density_per_km2_3h is None for dp in ergebnis.data), (
        f"Blitzfeld haette trotz Totalausfall leer bleiben muessen: "
        f"{[dp.lightning_density_per_km2_3h for dp in ergebnis.data]}"
    )
