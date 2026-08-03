"""Kern-Tests zu #1457 S2a Fix (2026-08-03) — Rueckfall auf aeltere AROME-Laeufe.

Spec: docs/specs/fast/fix-1457-s2a-echte-abrufnamen.md (AC-4, AC-5, AC-7, AC-8)

Der urspruengliche Coverage-Name (`LITOTA3`) und der zu knappe Sicherheitsabstand
(3h) fuehrten dazu, dass JEDER Blitzdichte-Abruf in 404 endete — fail-soft
schluckte es lautlos, 24 gruene Tests fingen es nicht, weil sie alle gegen eine
aufgezeichnete Datei laufen und die Naht zum Dienst nie beruehren. Diese beiden
Tests bewachen den Teil der Loesung, der KEIN Netz braucht: den
Rueckfall-Mechanismus selbst (fuer die Naht zum echten Dienst siehe
`test_thunder_coverage_name_live.py`).

Testart: Kern-Schicht (deterministisch, kein Netz). Echter lokaler HTTP-Server.
"""
from __future__ import annotations

import logging
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.config import Location  # noqa: E402
from providers import meteofrance as mf  # noqa: E402
from providers.thunder_window_cache import get_shared_thunder_window_cache  # noqa: E402

_FIXTURE_GRIB = (
    Path(__file__).resolve().parents[1] / "fixtures" / "meteofrance"
    / "arome_korsika_litota3_20260802.grib2"
)
_KORSIKA = Location(latitude=42.22, longitude=9.07, name="GR20 Petra Piana")


class _Aufzeichnung:
    def __init__(self) -> None:
        self.coverages: list[str] = []


@pytest.fixture
def server_factory(monkeypatch):
    """Baut einen lokalen Server, dessen Statuscode je Lauf-Kandidat (Index in
    `lauf_kandidaten`) frei konfigurierbar ist — alles andere (Grundvorhersage-
    Coverages) bekommt immer 200."""
    grib = _FIXTURE_GRIB.read_bytes()

    def _make(status_by_run_index: dict, lauf_kandidaten: list[datetime]):
        aufz = _Aufzeichnung()
        laeufe_str = [mf._run_str(l) for l in lauf_kandidaten]

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                q = parse_qs(urlparse(self.path).query)
                coverage = (q.get("coverageId") or [""])[0]
                aufz.coverages.append(coverage)
                index = next(
                    (i for i, l in enumerate(laeufe_str) if coverage.endswith(l)),
                    None,
                )
                status = status_by_run_index.get(index, 200)
                if status != 200:
                    self.send_response(status)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(grib)))
                self.end_headers()
                self.wfile.write(grib)

            def log_message(self, *a):
                pass

        srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        host, port = srv.server_address
        monkeypatch.setattr(mf, "BASE_URL", f"http://{host}:{port}/", raising=True)
        return srv, aufz

    yield _make


def test_404_auf_dem_gewaehlten_lauf_faellt_auf_den_naechstaelteren_zurueck(
    server_factory, caplog,
):
    """AC-4/AC-7: Given der primaere Lauf-Kandidat antwortet mit 404 (existiert
    noch nicht), When die Blitzdichte fuer mehrere Stunden geholt wird, Then
    wird der naechstaeltere Lauf versucht und liefert Werte — UND die
    Rueckfall-Meldung erscheint genau EINMAL im Protokoll, nicht je Stunde."""
    now = datetime.now(timezone.utc)
    kandidaten = mf._thunder_run_candidates(now)
    srv, aufz = server_factory({0: 404}, kandidaten)
    provider = mf.MeteoFranceDirectProvider()
    start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    try:
        with caplog.at_level(logging.WARNING, logger="meteofrance"):
            werte = provider.fetch_thunder_signals(
                _KORSIKA, start=start, end=start + timedelta(hours=3)
            )
    finally:
        srv.shutdown()

    gefuellt = [v for v in werte.values() if v is not None]
    assert gefuellt, (
        "Kein Wert angekommen — der Rueckfall auf den naechstaelteren Lauf "
        "greift nicht"
    )
    primaer_str = mf._run_str(kandidaten[0])
    rueckfall_str = mf._run_str(kandidaten[1])
    assert any(c.endswith(primaer_str) for c in aufz.coverages), (
        "Der primaere Lauf wurde gar nicht erst versucht"
    )
    assert any(c.endswith(rueckfall_str) for c in aufz.coverages), (
        "Der naechstaeltere Lauf wurde nie angefragt — kein Rueckfall"
    )

    rueckfall_zeilen = [
        r for r in caplog.records if "nicht verfuegbar (404)" in r.getMessage()
    ]
    assert len(rueckfall_zeilen) == 1, (
        f"{len(rueckfall_zeilen)} Rueckfall-Meldungen statt genau einer bei "
        f"mehreren Stunden desselben Laufs (AC-7) — das waeren bei einem echten "
        "24h-Lauf 24 gleichlautende Zeilen"
    )

    # AC-8: der primaere Lauf darf im Zwischenspeicher NICHT unter dem
    # Ruckfall-Schluessel auftauchen — der Lauf ist Teil des Schluessels, ein
    # 404 legt dort nie einen (falschen) Eintrag ab.
    speicher = get_shared_thunder_window_cache()
    zeit_str = (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    primaer_coverage = f"{mf.LIGHTNING_COVERAGE}___{primaer_str}"
    bbox = mf._thunder_rechteck([_KORSIKA])
    assert speicher.get(primaer_coverage, zeit_str, bbox) is None, (
        "Der primaere (404-)Lauf hat trotzdem einen Zwischenspeicher-Eintrag "
        "hinterlassen — ein spaeterer Abruf koennte ihn faelschlich als "
        "gueltig lesen"
    )


def test_zwei_erfolglose_rueckfallstufen_liefern_none_die_vorhersage_bleibt_vollstaendig(
    server_factory,
):
    """AC-5: Given ALLE Lauf-Kandidaten antworten mit 404, When eine Vorhersage
    abgerufen wird, Then bleibt die Blitzdichte durchgehend `None` und die
    Grundvorhersage (Temperatur/Wind) kommt trotzdem vollstaendig — UND alle
    Kandidaten wurden tatsaechlich versucht, statt vorzeitig aufzugeben."""
    now = datetime.now(timezone.utc)
    kandidaten = mf._thunder_run_candidates(now)
    assert len(kandidaten) == 3, "Erwartet: primaerer Lauf + zwei Rueckfallstufen"
    srv, aufz = server_factory({0: 404, 1: 404, 2: 404}, kandidaten)
    provider = mf.MeteoFranceDirectProvider()

    try:
        reihe = provider.fetch_forecast(_KORSIKA)
    finally:
        srv.shutdown()

    assert reihe.data, (
        "Vorhersage ist leer — der erschoepfte Rueckfall hat sie mitgerissen"
    )
    assert any(dp.t2m_c is not None for dp in reihe.data), (
        "Temperatur fehlt — die Grunddaten wurden vom erschoepften Rueckfall "
        "beschaedigt"
    )
    assert all(dp.lightning_density_per_km2_3h is None for dp in reihe.data), (
        "Es steht ein Blitzdichte-Wert da, obwohl alle Laeufe 404 meldeten"
    )

    versucht = {mf._run_str(l) for l in kandidaten}
    tatsaechlich = {s for s in versucht if any(c.endswith(s) for c in aufz.coverages)}
    assert tatsaechlich == versucht, (
        f"Nur {tatsaechlich} von {versucht} Laeufen wurden tatsaechlich "
        "angefragt — der Rueckfall gibt vorzeitig auf, statt alle Stufen "
        "auszuschoepfen"
    )
