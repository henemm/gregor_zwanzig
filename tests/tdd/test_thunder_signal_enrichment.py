"""RED-Tests zu #1457 S2a — Blitzdichte von Météo-France ins Datenmodell.

Spec: docs/specs/modules/feat_1457_s2a_blitzdichte_meteofrance.md
Konzept + Messwerte: Issue #1419.

Warum diese Tests RED sein MUESSEN: `ForecastDataPoint.lightning_density_per_km2_3h`
und `MeteoFranceDirectProvider.fetch_thunder_signals` existieren noch nicht.

Testart: Kern-Schicht (deterministisch). Kein Netz — ein echter lokaler HTTP-Server
liefert eine **aufgezeichnete** AROME-GRIB2-Antwort aus `tests/fixtures/meteofrance/`.
Muster uebernommen von `test_meteofrance_direct_fallback.py:476-517`.
"""
from __future__ import annotations

import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.config import Location  # noqa: E402
from providers import meteofrance as mf  # noqa: E402

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "meteofrance"
_FIXTURE_GRIB = _FIXTURE_DIR / "arome_paris_20260722.grib2"

# GR20, Refuge de Petra Piana — der Ort aus der Messung vom 2026-08-02
_KORSIKA = Location(latitude=42.22, longitude=9.07, name="GR20 Petra Piana")
# Zillertal — ausserhalb Frankreichs, AROME ist dort nicht zustaendig
_ALPEN = Location(latitude=47.05, longitude=11.50, name="Zillertal")


class _Aufzeichnung:
    """Zaehlt Abrufe je Coverage und kann einzelne gezielt scheitern lassen."""

    def __init__(self):
        self.pfade: list[str] = []
        self.blitz_status = 200
        self.verzoegerung = 0.0


@pytest.fixture
def server(monkeypatch):
    """Lokaler HTTP-Server, der die aufgezeichnete GRIB2-Antwort ausliefert."""
    grib = _FIXTURE_GRIB.read_bytes()
    aufz = _Aufzeichnung()

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = parse_qs(urlparse(self.path).query)
            coverage = (q.get("coverageId") or [""])[0]
            aufz.pfade.append(coverage)
            ist_blitz = "LITOTA3" in coverage
            if ist_blitz and aufz.verzoegerung:
                time.sleep(aufz.verzoegerung)
            if ist_blitz and aufz.blitz_status != 200:
                self.send_response(aufz.blitz_status)
                self.end_headers()
                return
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
    yield aufz
    srv.shutdown()


def test_ac1_blitzdichte_kommt_am_korsika_punkt_an(server):
    """AC-1: Given eine Position auf dem GR20, When die Gewittersignale abgerufen
    werden, Then traegt mindestens ein Zeitpunkt einen Blitzdichte-Wert."""
    provider = mf.MeteoFranceDirectProvider()

    werte = provider.fetch_thunder_signals(_KORSIKA)

    assert werte, "Keine Gewittersignale geliefert"
    gefuellt = [v for v in werte.values() if v is not None]
    assert gefuellt, "Alle Blitzdichte-Werte leer — Signal kommt nicht an"
    assert any("LITOTA3" in p for p in server.pfade), (
        "Die Blitzdichte-Groesse LITOTA3 wurde gar nicht abgerufen"
    )


def test_ac2_fehlender_wert_bleibt_leer_und_wird_nie_null(server):
    """AC-2: Given Météo-France liefert keinen Wert, When die Signale gebaut werden,
    Then bleibt das Feld leer — NIE 0. „Keine Aussage" ist nicht „keine Gefahr"."""
    server.blitz_status = 404
    provider = mf.MeteoFranceDirectProvider()

    werte = provider.fetch_thunder_signals(_KORSIKA)

    assert all(v is None for v in werte.values()), (
        "Fehlender Wert wurde zu einer Zahl gemacht — 0 wuerde 'kein Gewitter' "
        "bedeuten und ist eine falsche Entwarnung"
    )


def test_ac3_ausfall_der_anreicherung_kippt_die_vorhersage_nicht(server):
    """AC-3: Given der Blitzdichte-Abruf scheitert vollstaendig, When eine
    Vorhersage abgerufen wird, Then kommt sie trotzdem vollstaendig — nur ohne
    Blitzdichte."""
    server.blitz_status = 500
    provider = mf.MeteoFranceDirectProvider()

    reihe = provider.fetch_forecast(_KORSIKA)

    assert reihe.data, "Vorhersage ist leer — der Gewitter-Ausfall hat sie mitgerissen"
    assert any(dp.t2m_c is not None for dp in reihe.data), (
        "Temperatur fehlt — die Grunddaten wurden vom Gewitter-Ausfall beschaedigt"
    )
    assert all(dp.lightning_density_per_km2_3h is None for dp in reihe.data)


def test_ac4_eigenes_zeitbudget_schuetzt_die_grundvorhersage(server, monkeypatch):
    """AC-4: Given die Blitzdichte-Abrufe sind sehr langsam, When das Budget der
    Anreicherung erschoepft ist, Then bricht NUR die Anreicherung ab und die
    Grundvorhersage kommt."""
    server.verzoegerung = 0.05
    # raising=True: Die Konstante MUSS existieren. Ein eigenes Budget, das es nicht
    # gibt, kann die Grundvorhersage nicht schuetzen — ohne diese Schaerfe waere der
    # Test auch ohne jede Implementierung gruen und damit wertlos.
    monkeypatch.setattr(mf, "THUNDER_FETCH_DEADLINE_SECONDS", 0.2, raising=True)
    provider = mf.MeteoFranceDirectProvider()

    beginn = time.monotonic()
    reihe = provider.fetch_forecast(_KORSIKA)
    dauer = time.monotonic() - beginn

    assert reihe.data, "Grundvorhersage fehlt"
    assert any(dp.t2m_c is not None for dp in reihe.data), (
        "Temperatur fehlt — der Abbruch der Anreicherung hat die Grunddaten getroffen"
    )
    blitz_abrufe = [p for p in server.pfade if "LITOTA3" in p]
    assert blitz_abrufe, (
        "Die Anreicherung wurde gar nicht erst versucht — der Test wuerde sonst "
        "ein Zeitbudget bescheinigen, das nie zur Anwendung kam"
    )
    # Der SCHARFE Nachweis (nachgeschaerft 2026-08-02): nicht die Laufzeit,
    # sondern die Abrufzahl. Bei 0,05s je Abruf und 0,2s Budget ist nach
    # wenigen Abrufen Schluss; greift die Anreicherung stattdessen auf das
    # grosse Budget der Grundvorhersage zurueck, laufen alle 24 Stunden durch.
    # Zuvor prueften wir nur `dauer < FETCH_DEADLINE_SECONDS` — das blieb bei
    # genau diesem Rueckfall gruen (24 x 0,05s = 1,2s << 180s) und bewachte
    # damit nicht, wofuer der Test da ist. Eine Abrufzahl ist ausserdem
    # robuster als eine Zeitschranke auf einem belasteten Rechner.
    assert len(blitz_abrufe) < 12, (
        f"{len(blitz_abrufe)} von 24 Blitz-Abrufen gelaufen — das eigene "
        "Budget (0,2s) hat nicht gestoppt, die Anreicherung nutzt das grosse "
        "Budget der Grundvorhersage"
    )
    assert dauer < mf.FETCH_DEADLINE_SECONDS, (
        f"Lauf brauchte {dauer:.1f}s — die Anreicherung hat das grosse Budget "
        "der Grundvorhersage aufgebraucht statt ihr eigenes einzuhalten"
    )


def test_ac5_standardwert_schaltet_die_anreicherung_ein(server):
    """AC-5: Given eine Aufrufstelle setzt den Schalter nicht, When sie eine
    Vorhersage fuer einen franzoesischen Ort abruft, Then wird die Blitzdichte
    trotzdem geholt (#1448-Lehre: der Default muss schuetzen)."""
    provider = mf.MeteoFranceDirectProvider()

    reihe = provider.fetch_forecast(_KORSIKA)

    assert any(dp.lightning_density_per_km2_3h is not None for dp in reihe.data), (
        "Ohne ausdruecklichen Schalter kam kein Gewittersignal — ein Schutz, der "
        "am Durchreichen eines Parameters haengt, ist kein Schutz"
    )


def test_ac6_ausserhalb_frankreichs_kein_abruf(server):
    """AC-6: Given ein Ort ausserhalb Frankreichs, When eine Vorhersage abgerufen
    wird, Then findet kein Blitzdichte-Abruf statt."""
    provider = mf.MeteoFranceDirectProvider()

    werte = provider.fetch_thunder_signals(_ALPEN)

    assert not any("LITOTA3" in p for p in server.pfade), (
        "Ausserhalb des AROME-Gebiets wurde trotzdem abgerufen — sinnlose Last"
    )
    assert werte == {} or all(v is None for v in werte.values())
