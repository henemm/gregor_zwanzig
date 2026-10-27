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
import types
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


# ---------------------------------------------------------------------------
# Fix-Loop 1 (Adversary F004): die beiden uebrigen Ausstiege schreiben die Zeile ebenfalls.
# ---------------------------------------------------------------------------

def _server_mit(antwort):
    """Lokaler Server; `antwort(Nummer des Abrufs) -> (status, body)`."""
    abrufe: list[str] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            abrufe.append(self.path)
            status, body = antwort(len(abrufe))
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


def test_ac14_budgetabbruch_nach_404_rueckfall_schreibt_die_zeile_trotzdem(monkeypatch, caplog):
    """Zweiter Budget-Ausstieg: der erste Abruf antwortet 404 (Lauf-Rueckfall), und bis dahin
    ist das Zeitbudget aufgebraucht. Die Uhr springt, sobald der Server die 404 ausliefert."""
    echt = time.monotonic
    versatz = [0.0]

    def antwort(n):
        versatz[0] = 10_000.0  # ab jetzt ist jedes Zeitbudget abgelaufen
        return 404, b"run not found"

    srv, abrufe = _server_mit(antwort)
    monkeypatch.setattr(mf, "BASE_URL", "http://%s:%d/" % srv.server_address, raising=True)
    monkeypatch.setattr(mf, "time", types.SimpleNamespace(monotonic=lambda: echt() + versatz[0]))
    caplog.set_level(logging.INFO)
    try:
        ergebnis = _abruf(mf.MeteoFranceDirectProvider(), deadline_at=echt() + 30)
    finally:
        srv.shutdown()
    assert len(abrufe) == 1, f"Rueckfall wurde trotz abgelaufenem Budget weiterverfolgt: {abrufe}"
    assert _fenster_zeilen(caplog) == [(0, 0)]
    assert not [v for v in ergebnis["Petra Piana"].values() if v is not None]


def test_ac14_unerwarteter_fehler_im_abruf_schreibt_die_zeile_und_bleibt_fail_soft(caplog, monkeypatch):
    """Aeusserer `except Exception`: Fehlerinjektion -- das Auslesen der (echten) Antwort wirft.
    Der Abruf bleibt fail-soft (leere Reihen), die Zeile steht trotzdem im Log."""
    srv, abrufe = _server_mit(lambda n: (200, _GRIB.read_bytes()))
    monkeypatch.setattr(mf, "BASE_URL", "http://%s:%d/" % srv.server_address, raising=True)

    def _wirft(raw, gruppe):
        raise RuntimeError("Auslesen kaputt")

    monkeypatch.setattr(mf, "_read_window_values", _wirft)
    caplog.set_level(logging.INFO)
    try:
        ergebnis = _abruf(mf.MeteoFranceDirectProvider())
    finally:
        srv.shutdown()
    assert abrufe, "kein Abruf -- Ort nicht zustaendig?"
    assert ergebnis == {"Petra Piana": {}}
    assert _fenster_zeilen(caplog) == [(1, 0)]
