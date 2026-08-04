"""TDD RED — #1457 S2b: DWD ICON-D2 liefert Blitzpotenzial und Hagel.

Spec: docs/specs/modules/feat_1457_s2b_gewitter_dwd_alpen.md
Abgedeckte ACs hier (Provider-Ebene): AC-2, AC-3, AC-4, AC-7.
(AC-1/AC-5/AC-8/AC-9/AC-10 siehe die Nachbardateien, AC-6 der Live-Test.)

===========================================================================
EMPIRISCHE VERMESSUNG DES ECHTEN DIENSTES (2026-08-03, opendata.dwd.de)
===========================================================================
Die Spec markiert Abrufnamen, Fehlwert-Marker und Gittergrenzen ausdruecklich
als **Arbeitshypothese** (Known Limitations 1/3/5) — nach der `LITOTA3`-Lehre
aus S2a (Name existierte beim Dienst 0-mal, jeder Abruf lief lautlos in 404,
24 aufgezeichnete Tests blieben gruen). Deshalb wurde VOR diesen Tests gegen
den echten Dienst gemessen. Befund:

1. ABRUFNAMEN — Hypothese BESTAETIGT. Im Lauf-Verzeichnis
   `.../icon-d2/grib/<HH>/` existieren die Ordner `lpi`, `lpi_max` und
   `grau_gsp` tatsaechlich. Das Dateinamens-Muster ist IDENTISCH zu den vier
   bestehenden Basis-Parametern, d.h. `dwd._build_url` traegt unveraendert:
     .../15/lpi/icon-d2_germany_regular-lat-lon_single-level_2026080315_024_2d_lpi.grib2.bz2
   Je Parameter und Lauf liegen 49 `regular-lat-lon`-Dateien (Zeitschritte
   000..048, STUENDLICH) + 49 `icosahedral`-Dateien.

2. FEHLWERT-MARKER — Hypothese WIDERLEGT: es ist **9999.0**, NICHT -999.0.
   (`echotop=-999.0` aus dem Issue-Kontext gilt fuer eine andere Groesse und
   traegt hier nicht.) rasterio liefert den Marker sauber als
   `dataset.nodata == 9999.0`. Betroffen sind ~151.528 von 906.390 Zellen
   (~17 %): das `regular-lat-lon`-Rechteck ist groesser als das eigentliche
   ICON-D2-Modellgebiet, die Ecken sind Fuellwert. Genau dort greift AC-2 —
   ein Ort im Rechteck, aber ausserhalb des Modellgebiets (z.B. Masuren
   54,0 N / 20,0 O) liefert heute 9999.0 statt "keine Aussage".
   ACHTUNG: `dwd._read_point_value` reicht diesen Rohwert heute ungeprueft
   durch (dwd.py:115-128) — das betrifft auch die bestehenden Basis-Parameter.

3. GITTERGRENZEN (rasterio `dataset.bounds` einer echten Antwort) —
   Hypothese im Wesentlichen bestaetigt, minimal weiter:
     left=-3.95  bottom=43.17  right=20.35  top=58.09   (Aufloesung 0,02 Grad,
     746 x 1215 Bildpunkte, float64)
   Spec-Hypothese war "ca. -3,9 bis 20,3 O" — die Zeile in `thunder_routing`
   soll die gemessenen Werte tragen, nicht die gerundeten.

4. LAUF-VERFUEGBARKEIT / SICHERHEITSABSTAND: Die 2d-Felder des Laufs 15:00Z
   waren am 2026-08-03 um 16:21:57 UTC vollstaendig veroeffentlicht (~1 h 22
   nach Lauf-Zeitpunkt) — `lpi`/`lpi_max`/`grau_gsp` im SELBEN Schub wie
   `t_2m`. Der bestehende `dwd._latest_run` (auf 3 h abrunden, dann 3 h
   abziehen) liefert einen 3-6 h alten Lauf und trifft damit heute immer einen
   veroeffentlichten Lauf. Ein GROESSERER Sicherheitsabstand als bei
   Meteo-France (dort 6 h) ist NICHT noetig; noetig ist aber der
   Rueckfall auf aeltere Laeufe (AC-7), weil der Abstand im ungueenstigsten
   Fall nur ~3 h betraegt und eine Verzoegerung beim DWD ihn aufzehrt.

5. NEBENBEFUND, NICHT IN DER SPEC (Entscheidung noetig, s. Abschlussbericht):
   `grau_gsp` ist offenbar SEIT LAUFBEGINN KUMULIERT, wie `tot_prec` — an der
   Zelle 45,94 N / 7,86 O steigt der Wert bei Zeitschritt +8 h auf 3,3035 und
   bleibt ueber +12/+16/+20/+24 h exakt konstant. Ein Rohwert ist damit KEIN
   Stunden-Hagelsignal.
   ENTSCHIEDEN (2026-08-03, PO-bestaetigt, Spec-Changelog): `grau_gsp` wird
   per Differenzbildung zur Vorstunde in ein Stunden-Signal umgerechnet
   (Muster `_precip_series_from_cumulative`, wie `tot_prec`). `lpi` bleibt
   Momentanwert. AC-8 bleibt unberuehrt — umgerechnet wird die Einheit, nicht
   eine Stufe gebildet. Geprueft in
   `test_hagelsignal_kommt_als_eigenes_zweites_signal_an`.

===========================================================================
AUFZEICHNUNGEN (echt abgerufen 2026-08-03, ICON-D2-Lauf 2026-08-03T15:00Z)
===========================================================================
- `icon_d2_alpen_lpi_2026080315_024.grib2.bz2` (31 KB): Zeitschritt +24 h.
  Echtes Gewitter in den Karnischen Alpen — 46,40 N / 12,52 O traegt
  lpi = 48,1562. Masuren (54,0/20,0) traegt dort den Fuellwert 9999.0.
- `icon_d2_alpen_grau_gsp_2026080315_024.grib2.bz2` (9,5 KB): derselbe
  Zeitschritt; 45,84 N / 6,84 O traegt grau_gsp = 7,3442 (Mont-Blanc-Gebiet).
Die erwarteten Werte werden je Testlauf ERNEUT aus der Aufzeichnung gelesen
(`_rohwert_an`), nie hart hineingeschrieben — Projektlehre aus #1144.

===========================================================================
RED-GRUND (heute, unveraenderter Code)
===========================================================================
`providers.dwd` hat weder `THUNDER_PARAMS` noch
`THUNDER_FETCH_DEADLINE_SECONDS` noch `_thunder_run_candidates`, und
`DwdDirectProvider` hat keine Methode `fetch_thunder_signals_named` →
AttributeError in jedem Test dieser Datei.

Testart: Kern-Schicht. Kein Netz — echter lokaler `ThreadingHTTPServer`
liefert die Aufzeichnungen aus (Muster `test_dwd_direct_fallback.py`).
Keine Mocks.
"""
from __future__ import annotations

import bz2
import re
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import numpy as np
import pytest
import tenacity
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location  # noqa: E402
from providers import dwd  # noqa: E402

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "dwd"
_FIXTURE_LPI = _FIXTURE_DIR / "icon_d2_alpen_lpi_2026080315_024.grib2.bz2"
_FIXTURE_GRAU = _FIXTURE_DIR / "icon_d2_alpen_grau_gsp_2026080315_024.grib2.bz2"

# Karnische Alpen, Grenze AT/IT — PO-Reiseziel, echtes Gewittersignal in der
# Aufzeichnung. Grundvorhersage-Zustaendigkeit hier: `at_direct` (GeoSphere).
_KARNISCH = Location(latitude=46.40, longitude=12.52, name="Karnischer Hoehenweg")
# Mont-Blanc-Gebiet — einzige Gegend der Aufzeichnung mit Hagel-Rohwert > 0.
_MONTBLANC = Location(latitude=45.84, longitude=6.84, name="Mont-Blanc-Gebiet")
# Masuren: INNERHALB des `regular-lat-lon`-Rechtecks, AUSSERHALB des
# ICON-D2-Modellgebiets — dort steht in der echten Datei der Fuellwert 9999.0.
_MASUREN = Location(latitude=54.0, longitude=20.0, name="Masuren (ausserhalb Modellgebiet)")

# Erwartete Signalnamen als Schluessel des benannten Ergebnisses: NICHT hier
# festgeschrieben, sondern aus dem Produktivcode gelesen (s. AC-6-Lehre).
_DATEINAME = re.compile(r"_(\d{10})_(\d{3})_2d_")


def _rohwert_an(bz2_bytes: bytes, lat: float, lon: float) -> float:
    """Test-lokale Referenzimplementierung (bz2 + rasterio), unabhaengig von
    `providers.dwd`-Internals — liest den ROHWERT von Band 1 an (lat, lon).
    Klemmt bewusst NICHT: die Aufzeichnung deckt jeden hier gepruefften Ort ab."""
    raw = bz2.decompress(bz2_bytes)
    with MemoryFile(raw) as memfile, memfile.open() as dataset:
        row, col = dataset.index(lon, lat)
        return float(dataset.read(1)[row, col])


# Gemessene Gittergrenzen einer echten ICON-D2-Antwort (s. Punkt 3 oben) —
# damit deckt die Kunst-Rasterdatei genau dieselbe Flaeche ab wie die
# Aufzeichnung und kein Testort landet still auf einem Randpixel.
_GITTER = (-3.95, 43.17, 20.35, 58.09)
# Kumulations-Zuwachs je Stunde der Kunst-Reihe: klein genug, dass die
# mehrstuendige Kumulation (5 x 0,5 = 2,5) und der Stundenwert (0,5) sich
# NICHT verwechseln lassen.
_ZUWACHS_JE_STUNDE = 0.5


def _kunst_raster(wert: float) -> bytes:
    """Rasterdatei mit einem konstanten Wert ueber das ganze ICON-D2-Rechteck,
    bz2-gepackt wie beim echten Dienst.

    Warum kuenstlich und nicht aufgezeichnet: von jedem Parameter existiert
    genau EINE Aufzeichnung (ein Zeitschritt). Eine ueber die Zeit wachsende
    Kumulationskurve — der Regelfall bei `grau_gsp` — laesst sich damit nicht
    nachstellen. Der Weg durch den Produktivcode bleibt vollstaendig echt:
    HTTP -> bz2 -> rasterio -> Pixel-Lookup -> Differenzbildung."""
    hoehe, breite = 60, 100
    daten = np.full((hoehe, breite), wert, dtype="float64")
    with MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff", height=hoehe, width=breite, count=1,
            dtype="float64", crs="EPSG:4326",
            transform=from_bounds(*_GITTER, breite, hoehe),
        ) as dataset:
            dataset.write(daten, 1)
        return bz2.compress(memfile.read())


def _param_aus_pfad(path: str) -> Optional[str]:
    for param in getattr(dwd, "THUNDER_PARAMS", ()):
        if f"/{param}/" in path:
            return param
    return None


class _GewitterServer(ThreadingHTTPServer):
    """Liefert die Aufzeichnungen aus und protokolliert JEDEN Abruf als
    (Parameter, Lauf-Zeichenkette, Zeitschritt)."""

    def __init__(self, server_address, handler, *, fixtures, status_je_lauf,
                 fehlende_zeitschritte, verzoegerung_s, inhalt_je_zeitschritt):
        super().__init__(server_address, handler)
        self.fixtures = fixtures                      # param -> bytes
        self.status_je_lauf = status_je_lauf          # "YYYYMMDDHH" -> int
        self.fehlende_zeitschritte = fehlende_zeitschritte  # set[int] -> 404
        self.verzoegerung_s = verzoegerung_s
        # (param, ttt) -> bytes | None; None faellt auf die Aufzeichnung
        # zurueck. Ohne diese Naht liefert der Server fuer JEDEN Zeitschritt
        # dieselbe Datei — eine ueber die Zeit WACHSENDE Kumulationskurve
        # waere dann strukturell nicht pruefbar (Adversary F002).
        self.inhalt_je_zeitschritt = inhalt_je_zeitschritt
        self.abrufe: list[tuple[str, str, int]] = []
        self._lock = threading.Lock()

    def protokolliere(self, eintrag) -> None:
        with self._lock:
            self.abrufe.append(eintrag)


class _GewitterHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        srv = self.server
        if srv.verzoegerung_s:
            time.sleep(srv.verzoegerung_s)
        path = urlparse(self.path).path
        param = _param_aus_pfad(path)
        treffer = _DATEINAME.search(path)
        lauf = treffer.group(1) if treffer else ""
        ttt = int(treffer.group(2)) if treffer else -1
        if param is None:
            self.send_response(404)
            self.end_headers()
            return
        srv.protokolliere((param, lauf, ttt))
        status = srv.status_je_lauf.get(lauf, 200)
        if ttt in srv.fehlende_zeitschritte:
            status = 404
        if status != 200:
            self.send_response(status)
            self.end_headers()
            return
        body = None
        if srv.inhalt_je_zeitschritt is not None:
            body = srv.inhalt_je_zeitschritt(param, ttt)
        if body is None:
            body = srv.fixtures[param]
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@contextmanager
def _gewitter_server(monkeypatch, *, status_je_lauf=None, fehlende_zeitschritte=None,
                     verzoegerung_s=0.0, inhalt_je_zeitschritt=None):
    """Lokaler Server unter `providers.dwd.BASE_URL`. Dispatch ueber den
    Parameter-Ordner im Pfad — der Provider bestimmt Lauf und Zeitschritt
    selbst, der Test raet sie nicht."""
    fixtures = {}
    namen = list(getattr(dwd, "THUNDER_PARAMS", ()))
    for name in namen:
        if "lpi" in name:
            fixtures[name] = _FIXTURE_LPI.read_bytes()
        else:
            fixtures[name] = _FIXTURE_GRAU.read_bytes()
    server = _GewitterServer(
        ("127.0.0.1", 0), _GewitterHandler,
        fixtures=fixtures,
        status_je_lauf=status_je_lauf or {},
        fehlende_zeitschritte=fehlende_zeitschritte or set(),
        verzoegerung_s=verzoegerung_s,
        inhalt_je_zeitschritt=inhalt_je_zeitschritt,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    monkeypatch.setattr(dwd, "BASE_URL", f"http://{host}:{port}/", raising=True)
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class _AlleLaeufe(dict):
    """Antwortet fuer JEDEN Lauf mit demselben Statuscode — auch fuer jeden
    Rueckfall-Kandidaten, den der Provider selbst bestimmt."""

    def __init__(self, status: int) -> None:
        super().__init__()
        self._status = status

    def get(self, key, default=None):  # noqa: D102
        return self._status


def _fenster(stunden: int = 4) -> tuple[datetime, datetime]:
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return start, start + timedelta(hours=stunden)


# ---------------------------------------------------------------------------
# Grundnachweis (Provider-Haelfte von AC-1): die benannten Signale kommen an.
# ---------------------------------------------------------------------------

def test_benannte_signale_kommen_aus_der_aufzeichnung_an(monkeypatch):
    """Given den ICON-D2-Abruf gegen die echte Aufzeichnung fuer die Karnischen
    Alpen, When `fetch_thunder_signals_named` gerufen wird, Then kommen BEIDE
    Signale unter ihrem eigenen Namen zurueck und tragen genau die Werte, die
    in der Aufzeichnung an dieser Koordinate stehen.

    Die Erwartungswerte werden aus der Aufzeichnung GELESEN, nicht
    hineingeschrieben — sonst prueft der Test sich selbst.
    """
    start, ende = _fenster()
    with _gewitter_server(monkeypatch):
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _KARNISCH, start, ende
        )

    assert set(ergebnis) == set(dwd.THUNDER_PARAMS), (
        f"Erwartet je ein Eintrag pro Signal {tuple(dwd.THUNDER_PARAMS)}, "
        f"bekommen: {sorted(ergebnis)}"
    )
    erwartet_lpi = _rohwert_an(_FIXTURE_LPI.read_bytes(), 46.40, 12.52)
    werte = [v for v in ergebnis["lpi"].values() if v is not None]
    assert werte, "Kein einziger Blitzpotenzial-Wert angekommen"
    assert all(abs(v - erwartet_lpi) < 0.001 for v in werte), (
        f"Blitzpotenzial-Werte {sorted(set(werte))} weichen vom Rohwert der "
        f"Aufzeichnung ({erwartet_lpi}) ab"
    )


def test_hagelsignal_kommt_als_eigenes_zweites_signal_an(monkeypatch):
    """Given einen Ort mit echtem Hagel-Rohwert in der Aufzeichnung
    (Mont-Blanc-Gebiet), When die benannten Signale geholt werden, Then traegt
    das HAGEL-Signal diesen Wert — getrennt vom Blitzpotenzial.

    Beweist, dass die beiden Groessen nicht in EINEN Topf fallen (Spec:
    "bewusst zwei GETRENNTE Felder").

    NACHTRAG 2026-08-03 (Spec-Changelog, PO-bestaetigt): `grau_gsp` ist seit
    Laufbeginn KUMULIERT — der Befund aus Punkt 5 des Modul-Docstrings ist
    entschieden worden. Der Rohwert wird deshalb per Differenzbildung zur
    Vorstunde in ein Stunden-Signal umgerechnet (Muster
    `_precip_series_from_cumulative`). Fuer die Aufzeichnung, die JEDEN
    Zeitschritt mit derselben Datei beantwortet, heisst das: die erste Stunde
    traegt den vollen Rohwert (Kumulation seit Laufbeginn), jede weitere die
    Differenz — hier 0,0, weil der kumulierte Wert nicht weiter steigt. Der
    Nachweis "eigenes zweites Signal, aus der Aufzeichnung gelesen statt
    hineingeschrieben" bleibt davon unberuehrt.

    Das Zeitfenster beginnt hier BEWUSST am Lauf selbst: nur dann ist der
    Stand vor dem ersten Zeitschritt wirklich 0 und die erste Stunde damit
    der volle Rohwert. Der andere, im Betrieb haeufigere Fall (Fenster
    beginnt Stunden nach dem Lauf) steht in
    `test_erste_stunde_traegt_nur_den_zuwachs_dieser_stunde`.
    """
    start = dwd._latest_run(datetime.now(timezone.utc))
    ende = start + timedelta(hours=4)
    with _gewitter_server(monkeypatch):
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _MONTBLANC, start, ende
        )

    erwartet = _rohwert_an(_FIXTURE_GRAU.read_bytes(), 45.84, 6.84)
    assert erwartet > 0, "Aufzeichnung taugt nicht — dort steht gar kein Hagelwert"
    reihe = ergebnis["grau_gsp"]
    hagel = [v for v in reihe.values() if v is not None]
    assert hagel, "Kein Hagel-Wert angekommen"
    erste_stunde = reihe[min(reihe)]
    assert erste_stunde is not None and abs(erste_stunde - erwartet) < 0.001, (
        f"Die erste Stunde traegt {erste_stunde} statt des kumulierten "
        f"Rohwerts der Aufzeichnung ({erwartet}) — das Hagelsignal kommt nicht "
        "aus dieser Datei"
    )
    assert all(v <= erwartet + 0.001 for v in hagel), (
        f"Hagel-Werte {sorted(set(hagel))} liegen ueber dem kumulierten "
        f"Rohwert ({erwartet}) — die Differenzbildung rechnet falsch"
    )
    # Gegenprobe zur Signal-Trennung: das Blitzpotenzial derselben Koordinate
    # ist eine andere Zahl, die Reihen sind also nicht dieselbe Datei.
    blitz = _rohwert_an(_FIXTURE_LPI.read_bytes(), 45.84, 6.84)
    assert abs(blitz - erwartet) > 0.001, (
        "Beide Aufzeichnungen tragen an dieser Koordinate denselben Wert — die "
        "Trennung der Signale waere dann nicht nachweisbar"
    )
    assert any(
        v is not None and abs(v - blitz) < 0.001 for v in ergebnis["lpi"].values()
    ), (
        f"Das Blitzpotenzial-Signal traegt nicht den Wert seiner eigenen "
        f"Aufzeichnung ({blitz}) — die Signale sind vertauscht oder vermischt"
    )


# ---------------------------------------------------------------------------
# Kumulation: die erste gelieferte Stunde ist eine STUNDE, kein Mehrstunden-
# Summenwert (Adversary F001/F002, 2026-08-03).
# ---------------------------------------------------------------------------

def _wachsende_kumulation(param, ttt, ausfall_bei=None):
    """Kunst-Antwort fuer die kumulierten Signale: der Stand waechst je
    Zeitschritt um `_ZUWACHS_JE_STUNDE`. `ausfall_bei` liefert stattdessen den
    Fuellwert des Modellgebiets — "keine Aussage" an genau diesem Zeitschritt.
    `lpi` (Momentanwert) bleibt bei seiner Aufzeichnung (None = Rueckfall)."""
    if param not in dwd.THUNDER_CUMULATIVE_PARAMS:
        return None
    if ausfall_bei is not None and ttt == ausfall_bei:
        return _kunst_raster(dwd.THUNDER_FILL_VALUE)
    return _kunst_raster(_ZUWACHS_JE_STUNDE * ttt)


def _fenster_nach_dem_lauf(abstand=timedelta(hours=4, minutes=38), stunden=3):
    """Zeitfenster, das — wie im Betrieb praktisch immer — erst Stunden NACH
    dem Modelllauf beginnt. Der Abstand ist der am 2026-08-03 gemessene
    (4,64 h zwischen Lauf 15:00Z und Bezugszeitpunkt)."""
    lauf = dwd._latest_run(datetime.now(timezone.utc))
    start = lauf + abstand
    return lauf, start, start + timedelta(hours=stunden)


def test_erste_stunde_traegt_nur_den_zuwachs_dieser_stunde(monkeypatch):
    """Given ein Zeitfenster, das erst Stunden NACH dem Modelllauf beginnt
    (Regelfall: gemessen 4,64 h Abstand) und eine echt wachsende
    Kumulationskurve, When das Hagelsignal geholt wird, Then traegt die erste
    gelieferte Stunde nur den Zuwachs DIESER Stunde — nicht die gesamte
    Kumulation seit Laufbeginn.

    Warum das kein Randfall ist: der Bezugszeitpunkt der Anreicherung ist
    praktisch immer "jetzt", der Lauf liegt 3-6 h zurueck. Der erste
    angefragte Zeitschritt ist damit NIE der erste des Laufs. Wer dort einen
    Stand von 0 unterstellt, meldet die mehrstuendige Summe als Stundenwert —
    eine Groessenordnung, die real nie in einer Stunde gefallen ist, und die
    jede spaetere Schwellenwert-Auswertung zu frueh ausloest.
    """
    lauf, start, ende = _fenster_nach_dem_lauf()
    with _gewitter_server(
        monkeypatch, inhalt_je_zeitschritt=_wachsende_kumulation
    ) as srv:
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _MONTBLANC, start, ende
        )
        angefragt = sorted({t for p, _l, t in srv.abrufe if p == "grau_gsp"})

    reihe = ergebnis["grau_gsp"]
    erster = min(reihe)
    erster_zeitschritt = int((start + timedelta(hours=erster) - lauf).total_seconds() // 3600)
    assert erster_zeitschritt >= 2, (
        f"Der erste angefragte Zeitschritt ist {erster_zeitschritt} — der Test "
        "prueft dann gar keinen Abstand zum Lauf"
    )
    assert angefragt and angefragt[0] == erster_zeitschritt - 1, (
        f"Angefragt wurden die Zeitschritte {angefragt}; der Stand VOR dem "
        f"ersten Fenster-Schritt ({erster_zeitschritt - 1}) wurde nie geholt — "
        "ohne ihn ist die Differenzbildung ohne Anker"
    )
    kumuliert_bis_dahin = _ZUWACHS_JE_STUNDE * erster_zeitschritt
    assert reihe[erster] is not None, (
        "Die erste Stunde ist leer, obwohl der Stand davor abrufbar war"
    )
    assert abs(reihe[erster] - _ZUWACHS_JE_STUNDE) < 0.001, (
        f"Die erste Stunde traegt {reihe[erster]} statt des Stunden-Zuwachses "
        f"{_ZUWACHS_JE_STUNDE}. Die Kumulation seit Laufbeginn betraegt an "
        f"dieser Stelle {kumuliert_bis_dahin} — genau dieser Wert kaeme heraus, "
        "wenn der Stand vor dem Fenster faelschlich als 0 angenommen wird"
    )
    weitere = [reihe[o] for o in sorted(reihe)[1:]]
    assert weitere and all(
        w is not None and abs(w - _ZUWACHS_JE_STUNDE) < 0.001 for w in weitere
    ), (
        f"Die Folgestunden tragen {weitere} statt je {_ZUWACHS_JE_STUNDE} — "
        "die Differenzbildung rechnet ab dem zweiten Wert falsch"
    )


def test_ohne_abrufbaren_stand_davor_bleibt_die_erste_stunde_leer(monkeypatch):
    """AC-2 auf den Anker angewandt: Given der Stand unmittelbar vor dem
    Zeitfenster ist nicht abrufbar (hier: Fuellwert ausserhalb des
    Modellgebiets), When das Hagelsignal geholt wird, Then bleibt die erste
    Stunde leer — statt eine falsche Zahl zu behaupten.

    Eine erfundene Differenz waere schlimmer als eine Luecke: sie sieht aus
    wie eine Messung.
    """
    lauf, start, ende = _fenster_nach_dem_lauf()
    erster_zeitschritt = int(
        (start + timedelta(hours=1) - lauf).total_seconds() // 3600
    )

    def inhalt(param, ttt):
        return _wachsende_kumulation(param, ttt, ausfall_bei=erster_zeitschritt - 1)

    with _gewitter_server(monkeypatch, inhalt_je_zeitschritt=inhalt):
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _MONTBLANC, start, ende
        )

    reihe = ergebnis["grau_gsp"]
    erster = min(reihe)
    assert reihe[erster] is None, (
        f"Die erste Stunde traegt {reihe[erster]}, obwohl der Stand davor "
        "unbekannt ist — diese Zahl ist geraten"
    )
    folge = [reihe[o] for o in sorted(reihe)[1:]]
    assert folge and all(
        w is not None and abs(w - _ZUWACHS_JE_STUNDE) < 0.001 for w in folge
    ), (
        f"Der fehlende Anker hat die ganze Reihe mitgerissen: {folge} — ab dem "
        "zweiten Wert liegt der Stand davor vor und die Rechnung muss stimmen"
    )


# ---------------------------------------------------------------------------
# AC-2 — leer bleibt leer: weder 0 noch der rohe Fuellwert.
# ---------------------------------------------------------------------------

def test_ac2_fuellwert_des_modellgebiets_wird_nie_durchgereicht(monkeypatch):
    """AC-2: Given einen Ort im Datei-Rechteck, aber AUSSERHALB des
    ICON-D2-Modellgebiets (Masuren 54,0 N / 20,0 O — dort steht in der echten
    Aufzeichnung der Fuellwert 9999.0), When die Signale geholt werden, Then
    bleibt jeder Wert `None` — nie 0 und nie 9999.

    Warum das kein Randfall ist: Das ausgelieferte Rechteck ist rund 17 %
    groesser als das Modellgebiet. Die neue Zustaendigkeitszeile (AC-10) deckt
    das GANZE Rechteck ab, also faellt genau dieser Fall im Betrieb an. Wuerde
    der Rohwert durchgereicht, stuende 9999 als Blitzpotenzial in der
    Vorhersage — eine erfundene Extremlage.
    """
    roh = _rohwert_an(_FIXTURE_LPI.read_bytes(), 54.0, 20.0)
    assert roh >= 9999.0, (
        f"Die Aufzeichnung traegt an dieser Koordinate {roh} statt des "
        "Fuellwerts — der Test wuerde nichts pruefen"
    )

    start, ende = _fenster()
    with _gewitter_server(monkeypatch):
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _MASUREN, start, ende
        )

    alle = [w for signal in ergebnis.values() for w in signal.values()]
    assert alle, "Es kam gar kein Eintrag zurueck — der Test prueft dann nichts"
    assert all(w is None for w in alle), (
        f"Es kamen Werte an, obwohl an dieser Koordinate nur der Fuellwert "
        f"steht: {sorted({w for w in alle if w is not None})}. "
        "9999 als Blitzpotenzial ist eine erfundene Extremlage, 0 waere eine "
        "falsche Entwarnung"
    )


def test_ac2_fehlende_stunde_bleibt_leer_und_wird_nie_null(monkeypatch):
    """AC-2: Given der Dienst liefert fuer EINEN Zeitschritt nichts (404),
    When die Signale geholt werden, Then bleibt genau diese Stunde `None`,
    waehrend die uebrigen Stunden ihre Werte behalten.

    Eine einzelne fehlende Stunde darf weder zur 0 werden (falsche Entwarnung)
    noch die ganze Reihe kippen.
    """
    start, ende = _fenster(stunden=4)
    with _gewitter_server(monkeypatch, fehlende_zeitschritte={0, 1, 2, 3, 4, 5}) as srv:
        # Ein einzelner Zeitschritt fehlt: der zweite tatsaechlich angefragte.
        srv.fehlende_zeitschritte = set()
        vorlauf = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _KARNISCH, start, ende
        )
        # In der REIHENFOLGE der Abrufe, nicht sortiert: der allererste Abruf
        # darf es nicht sein, sonst gilt der Lauf als "nicht veroeffentlicht"
        # und der Rueckfall auf einen aelteren Lauf greift (AC-7) — dann fehlt
        # gar keine Stunde mehr.
        angefragte = [ttt for _p, _l, ttt in srv.abrufe]
        assert len(set(angefragte)) >= 2, (
            f"Nur {angefragte} Zeitschritte angefragt — zu wenig fuer diesen Test"
        )
        srv.fehlende_zeitschritte = {angefragte[1]}
        srv.abrufe.clear()
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _KARNISCH, start, ende
        )

    assert vorlauf, "Vorlauf leer — der Vergleich haette keine Grundlage"
    for signal, reihe in ergebnis.items():
        leer = [o for o, w in reihe.items() if w is None]
        gefuellt = [w for w in reihe.values() if w is not None]
        assert len(leer) == 1, (
            f"Signal '{signal}': {len(leer)} leere Stunden statt genau einer — "
            f"die fehlende Stunde wurde entweder aufgefuellt (dann waere sie 0 "
            f"und damit eine falsche Entwarnung) oder hat die Reihe mitgerissen. "
            f"Reihe: {reihe}"
        )
        assert gefuellt, (
            f"Signal '{signal}': eine einzelne fehlende Stunde hat die ganze "
            f"Reihe geleert — {reihe}"
        )


# ---------------------------------------------------------------------------
# AC-3 — fail-soft: die Vorhersage kippt nie.
# ---------------------------------------------------------------------------

def test_ac3_dauerhafter_serverfehler_liefert_leeres_ergebnis_statt_ausnahme(
    monkeypatch,
):
    """AC-3: Given der DWD antwortet auf JEDEN Gewitter-Abruf mit 503,
    When die benannten Signale geholt werden, Then kommt ein Ergebnis ohne
    Werte zurueck und KEINE Ausnahme — der Aufrufer (Anreicherung, dann
    Vorhersage) darf davon nichts mitbekommen.

    Der Backoff wird auf 0 gesetzt (Muster test_dwd_direct_fallback.py) — hier
    interessiert das Fail-Soft-Verhalten, nicht die Wartezeit.
    """
    monkeypatch.setattr(
        dwd.DwdDirectProvider._request.retry, "wait", tenacity.wait_none()
    )
    start, ende = _fenster()
    with _gewitter_server(monkeypatch) as srv:
        # Jeder Lauf antwortet 503 — auch jeder Rueckfall-Kandidat.
        srv.status_je_lauf = _AlleLaeufe(503)
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _KARNISCH, start, ende
        )
        assert srv.abrufe, "Der Server wurde nie kontaktiert — nichts geprueft"

    werte = [w for signal in ergebnis.values() for w in signal.values() if w is not None]
    assert not werte, f"Es kamen Werte an, obwohl alles 503 meldete: {werte}"


# ---------------------------------------------------------------------------
# AC-4 — eigenes Zeitbudget, gemessen an der Zahl der Abrufe.
# ---------------------------------------------------------------------------

def test_ac4_eigenes_zeitbudget_bricht_nach_wenigen_abrufen_ab(monkeypatch):
    """AC-4: Given ein langsamer Dienst und ein klein gesetztes
    Gewitter-Zeitbudget, When die Signale fuer 24 Stunden geholt werden, Then
    endet der Abruf nach wenigen Abrufen — statt alle 48 abzuwarten — und das
    Budget der GRUNDVORHERSAGE bleibt unangetastet.

    Gezaehlt werden ABRUFE, nicht Laufzeit (Projektlehre: ein Laufzeit-Test
    misst die Maschine, nicht die Zeitgrenze).
    """
    grundbudget_vorher = dwd.FETCH_DEADLINE_SECONDS
    monkeypatch.setattr(dwd, "THUNDER_FETCH_DEADLINE_SECONDS", 0.4, raising=True)

    start, ende = _fenster(stunden=24)
    with _gewitter_server(monkeypatch, verzoegerung_s=0.15) as srv:
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _KARNISCH, start, ende
        )
        abrufe = len(srv.abrufe)

    assert ergebnis is not None, "Der Abruf hat geworfen statt aufzugeben"
    assert abrufe >= 1, "Es wurde gar nicht erst abgerufen — nichts geprueft"
    assert abrufe <= 8, (
        f"{abrufe} Abrufe bei einem Budget von 0,4 s und 0,15 s je Abruf — ohne "
        "eigene Zeitgrenze laeuft der Gewitter-Abruf ueber 48 Zeitschritte "
        "durch und dehnt jeden Vorhersage-Abruf entsprechend"
    )
    assert dwd.FETCH_DEADLINE_SECONDS == grundbudget_vorher, (
        "Das Budget der Grundvorhersage wurde vom Gewitter-Abbruch veraendert "
        "— beide muessen getrennt bleiben"
    )


# ---------------------------------------------------------------------------
# AC-7 — Rueckfall auf einen aelteren Lauf, Nullpunkt bleibt am Zeitfenster.
# ---------------------------------------------------------------------------

def test_ac7_404_auf_dem_juengsten_lauf_faellt_auf_einen_aelteren_zurueck(monkeypatch):
    """AC-7: Given der vom Code gewaehlte Lauf antwortet mit 404 (noch nicht
    veroeffentlicht), When die Signale geholt werden, Then wird ein aelterer
    Lauf angefragt und liefert Werte.

    Gemessen wurde: der Lauf 15:00Z war 1 h 22 min spaeter vollstaendig da,
    `_latest_run` haelt 3-6 h Abstand. Der Rueckfall ist trotzdem noetig — im
    unguenstigsten Fall betraegt der Abstand nur 3 h, eine Verzoegerung beim
    DWD zehrt ihn auf. Ohne Rueckfall liefe dann JEDER Abruf lautlos in 404
    (exakt die S2a-Lehre).
    """
    kandidaten = dwd._thunder_run_candidates(datetime.now(timezone.utc))
    assert len(kandidaten) >= 2, (
        f"Erwartet: gewaehlter Lauf + mindestens eine Rueckfallstufe, "
        f"bekommen {kandidaten}"
    )
    primaer = kandidaten[0].strftime("%Y%m%d%H")
    rueckfall = kandidaten[1].strftime("%Y%m%d%H")

    start, ende = _fenster()
    with _gewitter_server(monkeypatch, status_je_lauf={primaer: 404}) as srv:
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _KARNISCH, start, ende
        )
        versucht = {lauf for _p, lauf, _t in srv.abrufe}

    assert primaer in versucht, "Der gewaehlte Lauf wurde gar nicht erst versucht"
    assert rueckfall in versucht, (
        f"Der naechstaeltere Lauf ({rueckfall}) wurde nie angefragt — kein "
        f"Rueckfall. Angefragt: {sorted(versucht)}"
    )
    werte = [w for signal in ergebnis.values() for w in signal.values() if w is not None]
    assert werte, "Kein Wert angekommen — der Rueckfall greift nicht"


def test_ac7_nullpunkt_bleibt_am_zeitfenster_nicht_am_rueckfall_lauf(monkeypatch):
    """AC-7, zweite Haelfte: Given der Rueckfall auf einen aelteren Lauf,
    When die Signale fuer ein Zeitfenster geholt werden, Then bezeichnen die
    zurueckgegebenen Stunden-Offsets weiterhin `start + Offset` — die
    angefragten Zeitschritte des aelteren Laufs sind entsprechend groesser.

    Ohne diese Zusage verschoeben sich beim Rueckfall alle Werte um die
    Lauf-Differenz — das Gewitter stuende dann drei Stunden zu frueh in der
    Vorhersage. Genau diese Verschiebung sieht man einer Vorhersage nicht an.
    """
    kandidaten = dwd._thunder_run_candidates(datetime.now(timezone.utc))
    primaer, rueckfall_lauf = kandidaten[0], kandidaten[1]
    start, ende = _fenster(stunden=3)

    with _gewitter_server(
        monkeypatch, status_je_lauf={primaer.strftime("%Y%m%d%H"): 404}
    ) as srv:
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _KARNISCH, start, ende
        )
        rueckfall_str = rueckfall_lauf.strftime("%Y%m%d%H")
        zeitschritte = sorted(
            {ttt for _p, lauf, ttt in srv.abrufe if lauf == rueckfall_str}
        )

    assert zeitschritte, "Der Rueckfall-Lauf wurde nie angefragt"
    gueltige_zeiten = {
        rueckfall_lauf.replace(tzinfo=timezone.utc) + timedelta(hours=t)
        for t in zeitschritte
    }
    erwartete_zeiten = {
        start + timedelta(hours=o) for o in sorted(ergebnis["lpi"])
    }
    assert erwartete_zeiten <= gueltige_zeiten, (
        f"Die zurueckgegebenen Offsets zeigen auf {sorted(erwartete_zeiten)}, "
        f"tatsaechlich geholt wurden aber die Zeitpunkte "
        f"{sorted(gueltige_zeiten)}. Beim Rueckfall auf einen aelteren Lauf "
        "wurde der Nullpunkt mitverschoben — die Werte stehen dann an der "
        "falschen Stunde"
    )
    offsets = sorted(ergebnis["lpi"])
    assert offsets == list(range(offsets[0], offsets[0] + len(offsets))), (
        f"Die Offsets {offsets} sind nicht lueckenlos stuendlich — ICON-D2 "
        "liefert stuendliche Zeitschritte (gemessen: 000..048)"
    )


@pytest.mark.parametrize("signalname", ["lpi", "grau_gsp"])
def test_abrufnamen_stehen_als_konstante_im_produktivcode(signalname):
    """Waechter zur Namensfalle: die Abrufnamen muessen als KONSTANTE im
    Provider stehen (nicht verstreut), damit der Live-Test (AC-6) sie von dort
    lesen kann statt sie zu wiederholen. Gemessen am 2026-08-03 existieren
    genau diese Ordner beim echten Dienst."""
    assert signalname in tuple(dwd.THUNDER_PARAMS), (
        f"'{signalname}' fehlt in `dwd.THUNDER_PARAMS` "
        f"({getattr(dwd, 'THUNDER_PARAMS', None)}) — der Live-Test kann die "
        "Naht zum echten Dienst dann nicht pruefen"
    )
