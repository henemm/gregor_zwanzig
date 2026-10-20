"""Kern: Kalt-Signal `fr_direct_fenster` des Meteo-France-Providers (#2439, AC-14).

Spec: docs/specs/modules/feat_2439_push_eingang_prod_scharf.md (Abschnitt 5)

Je Abruf von `_fetch_coverage_signals_multi` genau EINE Zeile
    fr_direct_fenster fenster_s=<s.ss> downloads=<N> cache_treffer=<M>
mit N = tatsaechlich ueber das Netz geholte Fenster, M = aus dem geteilten
Fenster-Zwischenspeicher bediente Fenster -- auch beim Abbruch durch das Zeitbudget und
beim Totalausfall (vor jedem Ausstieg). Vorlage: `dwd_fenster` in `src/providers/dwd.py`.

Testart: Kern, echter Provider gegen einen lokalen HTTP-Server mit der echten
Korsika-AROME-Aufzeichnung (Muster `tests/tdd/test_thunder_shared_window_cache.py`).
Kein Netz, kein Mock der eigenen Annahme.
"""
from __future__ import annotations

import logging
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.config import Location  # noqa: E402
from providers import meteofrance as mf  # noqa: E402
from providers.base import ThunderSourceUnavailableError  # noqa: E402

_GRIB = (Path(__file__).resolve().parent / "fixtures" / "meteofrance"
         / "arome_korsika_litota3_20260802.grib2")
_PETRA_PIANA = Location(latitude=42.22, longitude=9.07, name="Petra Piana")
_ZEILE = re.compile(
    r"^fr_direct_fenster fenster_s=\d+\.\d{2} downloads=(\d+) cache_treffer=(\d+)$")


def _server(status: int):
    grib = _GRIB.read_bytes()
    abrufe: list[str] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = parse_qs(urlparse(self.path).query)
            abrufe.append((q.get("coverageId") or [""])[0])
            body = grib if status == 200 else b"server error"
            self.send_response(status)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, abrufe


@pytest.fixture
def mf_ok(monkeypatch):
    srv, abrufe = _server(200)
    monkeypatch.setattr(mf, "BASE_URL", "http://%s:%d/" % srv.server_address, raising=True)
    yield abrufe
    srv.shutdown()


@pytest.fixture
def mf_kaputt(monkeypatch):
    srv, abrufe = _server(500)
    monkeypatch.setattr(mf, "BASE_URL", "http://%s:%d/" % srv.server_address, raising=True)
    yield abrufe
    srv.shutdown()


def _fenster_zeilen(caplog) -> list[tuple[int, int]]:
    zeilen = [r.getMessage() for r in caplog.records if "fenster_s=" in r.getMessage()]
    treffer = [_ZEILE.match(z) for z in zeilen]
    assert all(treffer), f"Zeile im falschen Format: {zeilen}"
    return [(int(m.group(1)), int(m.group(2))) for m in treffer]


def _abruf(provider, **kw):
    start = datetime.now(timezone.utc)
    return provider.fetch_thunder_signals_multi(
        [_PETRA_PIANA], start=start, end=start + timedelta(hours=3), **kw)


def test_ac14_kalter_abruf_schreibt_eine_zeile_mit_der_zahl_der_downloads(mf_ok, caplog):
    caplog.set_level(logging.INFO)
    ergebnis = _abruf(mf.MeteoFranceDirectProvider())
    assert mf_ok, "kein Meteo-France-Abruf -- Ort nicht zustaendig?"
    assert _fenster_zeilen(caplog) == [(len(mf_ok), 0)]
    werte = [v for v in ergebnis["Petra Piana"].values() if v is not None]
    assert werte, "Rueckgabe veraendert: keine Werte mehr trotz erfolgreicher Abrufe"


def test_ac14_warmer_abruf_aus_dem_zwischenspeicher_hat_null_downloads(mf_ok, caplog):
    provider = mf.MeteoFranceDirectProvider()
    _abruf(provider)
    geladen = len(mf_ok)
    caplog.clear()
    caplog.set_level(logging.INFO)
    _abruf(provider)
    assert len(mf_ok) == geladen, "zweiter Abruf ging doch ans Netz"
    assert _fenster_zeilen(caplog) == [(0, geladen)]


def test_ac14_budgetabbruch_schreibt_die_zeile_trotzdem(mf_ok, caplog):
    caplog.set_level(logging.INFO)
    _abruf(mf.MeteoFranceDirectProvider(), deadline_at=time.monotonic() - 1)
    assert not mf_ok
    assert _fenster_zeilen(caplog) == [(0, 0)]


def test_ac14_totalausfall_schreibt_die_zeile_und_wirft_weiter(mf_kaputt, caplog):
    caplog.set_level(logging.INFO)
    with pytest.raises(ThunderSourceUnavailableError):
        _abruf(mf.MeteoFranceDirectProvider())
    assert mf_kaputt, "Ausfall-Server wurde nicht gefragt"
    assert _fenster_zeilen(caplog) == [(0, 0)]


def test_ac14_zeile_traegt_nicht_den_dwd_praefix(mf_ok, caplog):
    caplog.set_level(logging.INFO)
    _abruf(mf.MeteoFranceDirectProvider())
    assert not [r for r in caplog.records if r.getMessage().startswith("dwd_fenster")]
