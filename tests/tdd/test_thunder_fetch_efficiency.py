"""RED-Tests zu #1457 S2a, AC-9 und AC-10 — wie oft abgerufen wird.

Spec: docs/specs/modules/feat_1457_s2a_blitzdichte_meteofrance.md

Warum es diese Tests braucht — kein Geschwindigkeits-, sondern ein Regelthema:

AC-9: Meteo-France begrenzt **pro Minute** (100 Anfragen/min seit Januar 2026, davor 50;
  Ueberschreitung -> HTTP 429). Der heutige Weg macht 24 Abrufe je Ort in ~8 s, also
  ~180/min. Ein Ortsvergleich mit 8 Orten (192 Abrufe) liegt deutlich ueber dem Limit.
  Die WCS-API nimmt aber ein **beliebig grosses Rechteck** entgegen, bei nahezu gleicher
  Antwortzeit (live gemessen 2026-08-02: 1 Punkt 0,49 s / 445 B; Korsika ganz 0,43 s /
  81 KB; ganz Frankreich 0,91 s / 3,9 MB). Der Provider fragt heute je Ort ein
  0,1°-Kaestchen ab und verwirft alles ausser einem Pixel.

AC-10: `fetch_thunder_signals` ignoriert seinen `end`-Parameter und laeuft immer 1..24.
  Im Ortsvergleich (synthetisches 1-Stunden-Fenster) sind das ~13 von 24 Abrufen je Ort
  fuer nichts.

Beide Befunde stammen aus der unabhaengigen Architekturpruefung, nicht aus der
urspruenglichen Planung — die Adversary-Runde ueber AC-1..AC-6 hatte sie nicht gefunden,
weil sie gegen die damaligen Kriterien geprueft hat.

Testart: Kern-Schicht. Echter lokaler HTTP-Server mit Abrufzaehler, aufgezeichnete
AROME-GRIB2-Antwort. Kein Netz.
"""
from __future__ import annotations

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

# Aufzeichnung ueber GANZ Korsika (41,30-43,11 N / 8,39-9,60 O) — alle acht
# Orte unten liegen DARIN. Zuvor stand hier die Paris-Aufzeichnung
# (2,30-2,41 O), die keinen einzigen dieser Orte abdeckt; dass trotzdem Werte
# ankamen, lag am Klemmen auf den Randbildpunkt (Adversary-Befund F001: alle
# acht Orte trugen denselben Wert). Mit AC-11 (verwerfen statt klemmen) muss
# die Aufzeichnung die geprueften Orte wirklich enthalten.
_FIXTURE_GRIB = (
    Path(__file__).resolve().parents[1] / "fixtures" / "meteofrance"
    / "arome_korsika_litota3_20260802.grib2"
)

# Acht Orte auf Korsika — entspricht dem groessten real existierenden Ortsvergleich
_KORSIKA_ORTE = [
    Location(latitude=42.22, longitude=9.07, name="Petra Piana"),
    Location(latitude=42.31, longitude=8.92, name="Castel di Vergio"),
    Location(latitude=42.42, longitude=8.90, name="Ascu Stagnu"),
    Location(latitude=42.13, longitude=9.13, name="Onda"),
    Location(latitude=42.05, longitude=9.15, name="Vizzavona"),
    Location(latitude=41.93, longitude=9.20, name="Capannelle"),
    Location(latitude=41.78, longitude=9.23, name="Usciolu"),
    Location(latitude=41.60, longitude=9.28, name="Bavella"),
]


@pytest.fixture
def zaehler(monkeypatch):
    """Lokaler Server, der jeden Abruf mitzaehlt."""
    grib = _FIXTURE_GRIB.read_bytes()
    abrufe: list[dict] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = parse_qs(urlparse(self.path).query)
            abrufe.append({
                "coverage": (q.get("coverageId") or [""])[0],
                "subsets": q.get("subset", []),
            })
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(grib)))
            self.end_headers()
            self.wfile.write(grib)

        def log_message(self, *args):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, port = srv.server_address
    monkeypatch.setattr(mf, "BASE_URL", f"http://{host}:{port}/", raising=True)
    yield abrufe
    srv.shutdown()


def _blitz_abrufe(abrufe):
    return [a for a in abrufe if mf.LIGHTNING_COVERAGE in a["coverage"]]


def test_ac9_acht_orte_kosten_nicht_mehr_abrufe_als_einer(zaehler):
    """AC-9: Given acht Orte auf Korsika, When die Blitzdichte fuer alle geholt wird,
    Then entstehen NICHT mehr Abrufe als fuer einen einzigen Ort.

    Das ist der Kern: ein gemeinsames Abfragefenster statt eines Abrufs je Ort.
    Bei acht Orten waeren es sonst 192 Abrufe -- rund das Doppelte dessen, was
    Meteo-France pro Minute erlaubt.
    """
    provider = mf.MeteoFranceDirectProvider()

    provider.fetch_thunder_signals_multi(_KORSIKA_ORTE)
    fuer_acht = len(_blitz_abrufe(zaehler))

    zaehler.clear()
    provider.fetch_thunder_signals_multi(_KORSIKA_ORTE[:1])
    fuer_einen = len(_blitz_abrufe(zaehler))

    assert fuer_acht <= fuer_einen, (
        f"{fuer_acht} Abrufe fuer acht Orte gegen {fuer_einen} fuer einen — die Orte "
        "werden einzeln abgefragt. Bei acht Orten sind das 192 Abrufe gegen ein Limit "
        "von 100 pro Minute"
    )


def test_ac9_alle_orte_bekommen_werte_aus_dem_gemeinsamen_fenster(zaehler):
    """AC-9, zweite Haelfte: Sparsamkeit darf nicht auf Kosten der Vollstaendigkeit
    gehen — jeder der acht Orte muss seine eigenen Werte bekommen.

    Ohne diese Pruefung waere ein Weg gruen, der einfach nur weniger abruft und
    sieben Orte leer laesst.
    """
    provider = mf.MeteoFranceDirectProvider()

    ergebnis = provider.fetch_thunder_signals_multi(_KORSIKA_ORTE)

    assert len(ergebnis) == len(_KORSIKA_ORTE), (
        f"Nur {len(ergebnis)} von {len(_KORSIKA_ORTE)} Orten haben ein Ergebnis"
    )
    for ort in _KORSIKA_ORTE:
        werte = ergebnis.get(ort.name) or {}
        assert any(v is not None for v in werte.values()), (
            f"Ort '{ort.name}' hat keinen einzigen Wert — das gemeinsame Fenster "
            "deckt ihn nicht ab oder er wird nicht daraus gelesen"
        )


def test_ac10_kurzes_zeitfenster_ruft_weniger_ab(zaehler):
    """AC-10: Given ein Abrufzeitraum von einer Stunde (wie im Ortsvergleich),
    When die Blitzdichte geholt wird, Then werden deutlich weniger Stunden
    abgerufen als bei einem 24-Stunden-Zeitraum.

    Heute laeuft `fetch_thunder_signals` immer 1..24 und ignoriert `end` — im
    Ortsvergleich sind rund 13 von 24 Abrufen je Ort verworfene Arbeit.
    """
    provider = mf.MeteoFranceDirectProvider()
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    provider.fetch_thunder_signals(_KORSIKA_ORTE[0], start=start, end=start + timedelta(hours=1))
    kurz = len(_blitz_abrufe(zaehler))

    zaehler.clear()
    provider.fetch_thunder_signals(_KORSIKA_ORTE[0], start=start, end=start + timedelta(hours=24))
    lang = len(_blitz_abrufe(zaehler))

    assert kurz < lang, (
        f"Ein-Stunden-Fenster erzeugt {kurz} Abrufe, 24-Stunden-Fenster {lang} — der "
        "Zeitraum wird ignoriert und es wird immer voll abgerufen"
    )
    assert kurz <= 3, (
        f"{kurz} Abrufe fuer ein Ein-Stunden-Fenster sind zu viele — erwartet wird "
        "die Groessenordnung der tatsaechlich benoetigten Stunden"
    )
