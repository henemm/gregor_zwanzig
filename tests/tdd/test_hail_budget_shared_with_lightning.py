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
from urllib.parse import parse_qs, urlparse

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


# --- AC-5 am WIRKORT: der gemeinsame Aufrufweg `fetch_forecast` -------------
#
# Adversary #1507 F003: der Test oben ruft `fetch_hail_signals_multi`
# ISOLIERT auf. Er beweist damit nur, dass die Hagel-Funktion die Konstante
# `THUNDER_FETCH_DEADLINE_SECONDS` liest -- NICHT, dass Blitzdichte und Hagel
# sich beim eigentlichen Aufrufweg EINE Frist teilen. Belegte Mutation:
# `deadline_at=anreicherung_deadline` aus dem Hagel-Aufruf in
# `fetch_forecast` entfernen -- der Hagel bildet sich dann eine EIGENE volle
# Frist, die Anreicherung verbraucht zwei Budgets hintereinander, und jeder
# bestehende Test bleibt gruen.
#
# Der Test unten misst deshalb am Wirkort: EIN `fetch_forecast`-Aufruf,
# Blitzdichte UND Hagel langsam, Grunddaten schnell.

# Groesserer Abstand als oben, weil hier die Differenz ZWEIER Laeufe
# ausgewertet wird (Grundvorhersage + Anreicherung) statt einer nackten
# Laufzeit.
_ANTWORTZEIT_LANGSAM_S = 3.0
_ZEITGRENZE_GETEILT_S = 1.0

# Die vier Grunddaten-Coverages beantwortet der Testdienst SOFORT. Alles
# andere (Blitzdichte, Hagel -- und auch ein etwaiger falscher
# Coverage-Name) gilt als Anreicherung und wird langsam bedient. So zeigt die
# gemessene Differenz eindeutig auf die Anreicherungsphase.
_GRUNDDATEN = (
    mf.TEMPERATURE_COVERAGE,
    mf.U_WIND_COVERAGE,
    mf.V_WIND_COVERAGE,
    mf.PRECIP_COVERAGE,
)


def test_ac5_fetch_forecast_gibt_blitz_und_hagel_ein_gemeinsames_budget(monkeypatch):
    """AC-5: Given einen Dienst, der die Grunddaten sofort, Blitzdichte und
    Hagel aber quaelend langsam beantwortet, When `fetch_forecast` EINMAL
    laeuft, Then kostet die gesamte Anreicherung hoechstens EINE
    `THUNDER_FETCH_DEADLINE_SECONDS`-Spanne -- nicht zwei.

    Gemessen wird die Differenz zweier Laeufe desselben Providers gegen
    denselben Dienst: einmal ohne Anreicherung (`enrich_thunder=False`, reine
    Grundvorhersage) und einmal mit. Die Differenz IST die Anreicherungszeit;
    die Laufzeit der Grunddaten faellt dadurch heraus und muss nicht
    geschaetzt werden.

    Warum die Blitzdichte hier genau EINEN Abruf macht und der Hagel KEINEN:
    der erste Blitz-Abruf laeuft in die geteilte Frist (Restzeit als
    Timeout), danach ist sie aufgebraucht -- der Hagel-Abruf findet keine
    Restzeit mehr vor und kehrt sofort zurueck, OHNE eine Anfrage zu
    stellen. Genau das ist geteiltes Budget: der zweite Abrufweg erbt den
    Verbrauch des ersten. Ein Hagel-Abruf ohne Anfragen ist hier also der
    ERWARTETE Zustand, kein Zeichen dafuer, dass der Hagel nicht beteiligt
    gewesen waere.

    Gegenprobe (Mutation, belegt): wird die gemeinsame Frist aus dem
    Hagel-Aufruf in `fetch_forecast` entfernt, bildet der Hagel sich eine
    eigene volle Frist, stellt seinerseits einen Abruf, und die Anreicherung
    dauert rund 2 x Zeitgrenze -- der Test wird rot.
    """
    grib = _raster(7.0)
    zaehler = {"grund": 0, "anreicherung": 0}
    zaehler_lock = threading.Lock()

    class _GemischterHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def do_GET(self):  # noqa: N802
            query = parse_qs(urlparse(self.path).query)
            coverage = (query.get("coverageId") or [""])[0]
            ist_grunddatum = any(coverage.startswith(c) for c in _GRUNDDATEN)
            with zaehler_lock:
                zaehler["grund" if ist_grunddatum else "anreicherung"] += 1
            if not ist_grunddatum:
                time.sleep(_ANTWORTZEIT_LANGSAM_S)
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(grib)))
                self.end_headers()
                self.wfile.write(grib)
            except (BrokenPipeError, ConnectionResetError):
                # Der Client hat wegen der Zeitgrenze schon aufgelegt -- das
                # ist der Normalfall dieses Tests, keine Stoerung.
                pass

        def log_message(self, *a):
            pass

    class _StillerServer(ThreadingHTTPServer):
        daemon_threads = True

        def handle_error(self, *a):
            pass

    srv = _StillerServer(("127.0.0.1", 0), _GemischterHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(mf, "BASE_URL", "http://%s:%d/" % srv.server_address)
    monkeypatch.setattr(
        mf, "THUNDER_FETCH_DEADLINE_SECONDS", _ZEITGRENZE_GETEILT_S
    )
    # Kurzer Horizont: die Grundvorhersage holt 4 Coverages je Stunde. Drei
    # Stunden genuegen fuer einen vollstaendigen Lauf und halten das
    # Grundrauschen der Messung klein.
    monkeypatch.setattr(mf, "FORECAST_HOURS", [1, 2, 3])

    try:
        provider = mf.MeteoFranceDirectProvider()
        beginn = time.monotonic()
        provider.fetch_forecast(_KORSIKA, enrich_thunder=False)
        dauer_grunddaten = time.monotonic() - beginn

        beginn = time.monotonic()
        reihe = provider.fetch_forecast(_KORSIKA)
        dauer_gesamt = time.monotonic() - beginn
    finally:
        srv.shutdown()

    dauer_anreicherung = dauer_gesamt - dauer_grunddaten

    # Leerlauf-Schutz: ohne einen einzigen Anreicherungs-Abruf waere die
    # Differenz ~0 und der Test gruen, ohne irgendetwas zu bewachen.
    assert zaehler["anreicherung"] >= 1, (
        "Der Dienst hat keinen einzigen Anreicherungs-Abruf gesehen -- die "
        "Anreicherung lief gar nicht (Ort ausserhalb AROME? Coverage-Name "
        "verdreht?). Die Zeitmessung unten wuerde dann nichts messen "
        f"(Grunddaten-Abrufe: {zaehler['grund']})"
    )

    obergrenze = 1.5 * _ZEITGRENZE_GETEILT_S
    assert dauer_anreicherung < obergrenze, (
        f"Die Anreicherung in `fetch_forecast` dauerte "
        f"{dauer_anreicherung:.2f}s (Gesamt {dauer_gesamt:.2f}s minus "
        f"Grunddaten {dauer_grunddaten:.2f}s) bei einer Zeitgrenze von "
        f"{_ZEITGRENZE_GETEILT_S}s. Blitzdichte und Hagel haben sich also "
        "NICHT eine gemeinsame Frist geteilt, sondern je ein eigenes "
        f"Vollbudget verbraucht ({zaehler['anreicherung']} "
        "Anreicherungs-Abrufe)"
    )

    # Die Grundvorhersage bleibt trotz der abgebrochenen Anreicherung
    # vollstaendig -- sonst maesse der Test einen kaputten Lauf.
    assert len(reihe.data) == 3 and all(
        p.t2m_c is not None for p in reihe.data
    ), (
        "Die Grundvorhersage kam nicht vollstaendig zurueck -- dann sagt die "
        "Zeitmessung nichts ueber die Anreicherung aus"
    )
