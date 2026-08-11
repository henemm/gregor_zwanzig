"""TDD RED -- #1531 S1: DWD ICON-D2 liefert die fehlenden Gewitter-Groessen
(sdi_2, cin_ml, cape_ml, lpi_max, uh_max, uh_max_med, uh_max_low).

Spec: docs/specs/modules/feat_1531_s1_dwd_gewittergroessen.md
Abgedeckte ACs hier (Provider-Ebene): AC-1 (Teil), AC-2, AC-3, AC-4, AC-5, AC-7.
(AC-6 -> test_dwd_eu_thunder_energy_signals_fetch.py, AC-8 -> Mutations-
Gegenprobe in test_dwd_thunder_parameter_names_live.py, AC-9 ->
test_thunder_output_invariance_new_signals.py.)

===========================================================================
EMPIRISCHE VERMESSUNG DES ECHTEN DIENSTES (2026-08-11, opendata.dwd.de)
===========================================================================
Die Spec markiert Abrufnamen und Fehlwert-Marker als bereits geklaert
("Vorbedingung -- bereits geklaert (live gemessen 2026-08-08)"), aber NICHT
die konkreten Zahlen dieser Aufzeichnung -- die wurden HIER, frisch, erneut
gemessen (Projektlehre #1144: erwartete Werte immer aus der Aufzeichnung
LESEN, nie hineinschreiben):

1. ABRUFNAMEN -- bestaetigt. Unter `.../icon-d2/grib/03/` (Lauf 2026-08-11T03Z)
   existieren die Ordner `sdi_2`, `cin_ml`, `cape_ml`, `lpi_max`, `uh_max`,
   `uh_max_med`, `uh_max_low` -- identisches Namensmuster/Dateischema wie die
   bestehenden `lpi`/`grau_gsp`.
2. FEHLWERT-MARKER -- bestaetigt: 9999.0 ausserhalb des Modellgebiets (wie bei
   den bestehenden Basis-Parametern), UND zusaetzlich bei `cin_ml` -999.9 an
   ca. 46 % der Gitterpunkte -- exakt wie in der Spec "Vorbedingung" notiert.
3. GROESSENORDNUNGEN (Lauf 2026081103, Zeitschritt +012, aktives Gewitter in
   den Ligurischen Alpen 44,34 N / 7,56 O): `lpi_max` = 216,73 J/kg,
   `uh_max` = -123,27 m^2/s^2, `uh_max_med` = -40,46 m^2/s^2,
   `uh_max_low` = 13,29 m^2/s^2, `sdi_2` = -0,0000934 1/s (VORZEICHENBEHAFTET,
   passend zur Spec-Groessenordnung -0,0007). Am Karnischen Hoehenweg
   (46,40 N / 12,52 O, ruhigeres Wetter) traegt `cin_ml` = 7,29 J/kg -- fast
   exakt der in der Spec genannte Beispielwert 7,8 J/kg -- und `cape_ml`
   = 753,0 J/kg.
4. NEBENBEFUND (nicht Teil dieser Spec-Vorbedingung, aber gemessen): auch
   `cin_ml` bei ICON-EU traegt den Marker -999.9 (s.
   test_dwd_eu_thunder_energy_signals_fetch.py Docstring) -- die Spec nennt
   das fuer ICON-EU noch "ungemessen" (Known Limitations). Diese Datei
   pruef NUR ICON-D2, wo AC-2 laut Spec gilt.

AUFZEICHNUNGEN (echt abgerufen 2026-08-11, ICON-D2-Lauf 2026-08-11T03Z):
- `icon_d2_alpen_sdi2_2026081103_012.grib2.bz2`,
  `icon_d2_alpen_cin_ml_2026081103_012.grib2.bz2`,
  `icon_d2_alpen_cape_ml_2026081103_012.grib2.bz2`,
  `icon_d2_alpen_uh_max_2026081103_012.grib2.bz2`,
  `icon_d2_alpen_uh_max_med_2026081103_012.grib2.bz2`,
  `icon_d2_alpen_uh_max_low_2026081103_012.grib2.bz2` (Zeitschritt +012,
  jeweils ein einziger echter Netzabruf).
- `icon_d2_alpen_lpi_max_2026081103_0{11,12,13,14}.grib2.bz2`: VIER
  aufeinanderfolgende Zeitschritte an DERSELBEN Koordinate
  (44,34 N / 7,56 O), die einen echten Auf-und-Ab-Verlauf zeigen:
  0,0 -> 216,73 -> 39,66 -> 0,0 J/kg (AC-5).

ABWEICHUNG von der Spec-"Vorbild"-Groessenordnung (9-31 KB): `cape_ml`,
`cin_ml` und `sdi_2` sind KONTINUIERLICHE Felder (an praktisch jedem
Gitterpunkt ein von 0 verschiedener Wert) und komprimieren deshalb deutlich
schlechter als `lpi`/`lpi_max`/`uh_max*` (ueberwiegend exakte Nullen ausserhalb
aktiver Gewitterzellen). Gemessene Dateigroessen: 1,08 MB (`sdi_2`), 1,42 MB
(`cin_ml`), 2,46 MB (`cape_ml`) gegenueber 12-192 KB fuer die uebrigen vier
Groessen. Das ist keine Aufzeichnungs-Wahl, sondern eine Eigenschaft der
Groesse selbst -- an keinem geprueften Zeitschritt kleiner.

===========================================================================
RED-GRUND (heute, unveraenderter Code)
===========================================================================
`providers.dwd.THUNDER_PARAMS` traegt heute nur `("lpi", "grau_gsp")` --
keines der sieben neuen Signale wird angefragt, und `ForecastDataPoint` hat
keines der sieben neuen Felder (`supercell_index_sdi2_1s`,
`convective_inhibition_jkg`, `cape_ml_jkg`, `lightning_potential_max_lpi_jkg`,
`updraft_helicity_max_m2s2`, `updraft_helicity_max_med_m2s2`,
`updraft_helicity_max_low_m2s2`).

Testart: Provider-Ebene, lokaler `ThreadingHTTPServer` liefert die
Aufzeichnungen aus (Muster test_dwd_thunder_signal_fetch.py). Kein echtes
Netz -- trotzdem `pytestmark = pytest.mark.live` (identisches Vorbild: diese
Provider-Tests laufen NICHT im Commit-Gate, sondern nur explizit via
`pytest -m live`, CI-Vermessung #1196).
"""
from __future__ import annotations

import re
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location  # noqa: E402
from providers import dwd  # noqa: E402
from tests.tdd._dwd_eu_fixtures import rohwert_an  # noqa: E402

pytestmark = pytest.mark.live

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "dwd"

# Bestehende Signale (heute schon in THUNDER_PARAMS) -- damit der lokale
# Server sie normal beantwortet und der heutige Lauf nicht in
# ThunderSourceUnavailableError faellt (alle Abrufe 404), bevor ueberhaupt
# eine Assertion zu den NEUEN Feldern erreicht wird.
_FIXTURE_LPI = _FIXTURE_DIR / "icon_d2_alpen_lpi_2026080315_024.grib2.bz2"
_FIXTURE_GRAU = _FIXTURE_DIR / "icon_d2_alpen_grau_gsp_2026080315_024.grib2.bz2"

# Die sieben neuen Signale -- EIN Zeitschritt (+012) genuegt fuer AC-1/AC-2/
# AC-3/AC-4 (Punktwert-Nachweise, s. Modul-Docstring Punkt 3).
_NEUE_EINZEL_FIXTUREN: Dict[str, Path] = {
    "sdi_2": _FIXTURE_DIR / "icon_d2_alpen_sdi2_2026081103_012.grib2.bz2",
    "cin_ml": _FIXTURE_DIR / "icon_d2_alpen_cin_ml_2026081103_012.grib2.bz2",
    "cape_ml": _FIXTURE_DIR / "icon_d2_alpen_cape_ml_2026081103_012.grib2.bz2",
    "uh_max": _FIXTURE_DIR / "icon_d2_alpen_uh_max_2026081103_012.grib2.bz2",
    "uh_max_med": _FIXTURE_DIR / "icon_d2_alpen_uh_max_med_2026081103_012.grib2.bz2",
    "uh_max_low": _FIXTURE_DIR / "icon_d2_alpen_uh_max_low_2026081103_012.grib2.bz2",
}

# `lpi_max` braucht VIER Zeitschritte (AC-5, Auf-und-Ab-Verlauf) -- Zeitschritt
# der ZIEL-Anfrage (1..4, s. `_fenster_ab_lauf`) -> Fixture-Datei.
_LPI_MAX_JE_TTT: Dict[int, Path] = {
    1: _FIXTURE_DIR / "icon_d2_alpen_lpi_max_2026081103_011.grib2.bz2",
    2: _FIXTURE_DIR / "icon_d2_alpen_lpi_max_2026081103_012.grib2.bz2",
    3: _FIXTURE_DIR / "icon_d2_alpen_lpi_max_2026081103_013.grib2.bz2",
    4: _FIXTURE_DIR / "icon_d2_alpen_lpi_max_2026081103_014.grib2.bz2",
}

# Storm-Standort: aktives Gewitter in der Aufzeichnung (Ligurische Alpen).
_STURM = Location(latitude=44.34, longitude=7.56, name="Ligurische Alpen (Sturmzelle)")
# Ruhigeres Wetter, aber reale Werte fuer cin_ml/cape_ml (Modul-Docstring 3).
_KARNISCH = Location(latitude=46.40, longitude=12.52, name="Karnischer Hoehenweg")
# Ausserhalb des ICON-D2-Modellgebiets -- Fuellwert 9999.0 (Muster
# test_dwd_thunder_signal_fetch.py::_MASUREN).
_MASUREN = Location(latitude=54.0, longitude=20.0, name="Masuren (ausserhalb Modellgebiet)")


_ALLE_PARAMS = (
    "lpi", "grau_gsp", "cin_ml", "sdi_2", "cape_ml", "lpi_max",
    "uh_max_med", "uh_max", "uh_max_low",
)


def _param_aus_pfad(path: str) -> Optional[str]:
    for param in _ALLE_PARAMS:
        if f"/{param}/" in path:
            return param
    return None


# URL-Muster (dwd._build_url): .../<YYYYMMDDHH>_<TTT>_2d_<param>.grib2.bz2
_DATEINAME_TTT = re.compile(r"_(\d{10})_(\d{3})_2d_")


class _Server(ThreadingHTTPServer):
    def __init__(self, adresse, handler, *, einzel_fixturen, lpi_max_je_ttt,
                 verzoegerung_s):
        super().__init__(adresse, handler)
        self.einzel_fixturen = einzel_fixturen
        self.lpi_max_je_ttt = lpi_max_je_ttt
        self.verzoegerung_s = verzoegerung_s
        self.abrufe: list[tuple[str, int]] = []  # (Param, Zeitschritt)
        self._lock = threading.Lock()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        srv = self.server
        if srv.verzoegerung_s:
            time.sleep(srv.verzoegerung_s)
        path = urlparse(self.path).path
        param = _param_aus_pfad(path)
        if param is None:
            self.send_response(404)
            self.end_headers()
            return
        treffer = _DATEINAME_TTT.search(path)
        if treffer is None:
            self.send_response(404)
            self.end_headers()
            return
        ttt = int(treffer.group(2))
        with srv._lock:
            srv.abrufe.append((param, ttt))
        body = None
        if param == "lpi_max":
            body = srv.lpi_max_je_ttt.get(ttt)
        if body is None:
            body = srv.einzel_fixturen.get(param)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@contextmanager
def _server(monkeypatch, *, verzoegerung_s: float = 0.0):
    """Lokaler Server unter `dwd.BASE_URL`, dispatcht ueber den
    Parameter-Ordner im Pfad. `lpi_max` bekommt zusaetzlich eine je-Zeitschritt
    unterschiedliche Antwort (AC-5), alle uebrigen Parameter liefern
    konstant ihre einzige Aufzeichnung."""
    einzel = {name: pfad.read_bytes() for name, pfad in _NEUE_EINZEL_FIXTUREN.items()}
    einzel["lpi"] = _FIXTURE_LPI.read_bytes()
    einzel["grau_gsp"] = _FIXTURE_GRAU.read_bytes()
    lpi_max_bytes = {ttt: pfad.read_bytes() for ttt, pfad in _LPI_MAX_JE_TTT.items()}
    srv = _Server(
        ("127.0.0.1", 0), _Handler,
        einzel_fixturen=einzel, lpi_max_je_ttt=lpi_max_bytes,
        verzoegerung_s=verzoegerung_s,
    )
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(dwd, "BASE_URL", "http://%s:%d/" % srv.server_address)
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


def _fenster_ab_lauf(stunden: int = 4):
    """Zeitfenster GENAU am Lauf beginnend (`start=None` -> `base=run`), damit
    die abgefragten Zeitschritte deterministisch 1..`stunden` sind --
    unabhaengig davon, wann dieser Test tatsaechlich laeuft."""
    run = dwd._latest_run(datetime.now(timezone.utc))
    ende = run + timedelta(hours=stunden)
    return run, ende


# ---------------------------------------------------------------------------
# AC-1 -- Provider-Haelfte: die sieben neuen Signale kommen unter ihrem
# eigenen Namen an und tragen die Rohwerte der Aufzeichnung.
# ---------------------------------------------------------------------------

def test_ac1_alle_sieben_neuen_signale_kommen_mit_ihrem_rohwert_an(monkeypatch):
    """AC-1: Given ICON-D2-Aufzeichnungen fuer alle sieben neuen Groessen,
    When `fetch_thunder_signals_named` laeuft, Then tragen alle sieben
    Signalnamen ein Ergebnis, und jedes traegt an mindestens einer Stunde
    genau den Rohwert, der unabhaengig aus der jeweiligen Aufzeichnung
    gelesen wird (nicht eine im Test notierte Konstante).
    """
    _run, ende = _fenster_ab_lauf()
    with _server(monkeypatch):
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _STURM, None, ende,
        )

    erwartet_je_signal = {
        "sdi_2": rohwert_an(_NEUE_EINZEL_FIXTUREN["sdi_2"].read_bytes(), 44.34, 7.56),
        "uh_max": rohwert_an(_NEUE_EINZEL_FIXTUREN["uh_max"].read_bytes(), 44.34, 7.56),
        "uh_max_med": rohwert_an(_NEUE_EINZEL_FIXTUREN["uh_max_med"].read_bytes(), 44.34, 7.56),
        "uh_max_low": rohwert_an(_NEUE_EINZEL_FIXTUREN["uh_max_low"].read_bytes(), 44.34, 7.56),
        "lpi_max": rohwert_an(_LPI_MAX_JE_TTT[2].read_bytes(), 44.34, 7.56),
    }
    for signal, erwartet in erwartet_je_signal.items():
        assert signal in ergebnis, f"Signal '{signal}' fehlt komplett im Ergebnis {sorted(ergebnis)}"
        werte = [v for v in ergebnis[signal].values() if v is not None]
        assert werte, f"Signal '{signal}': kein einziger Wert angekommen"
        assert any(abs(v - erwartet) < 0.001 for v in werte), (
            f"Signal '{signal}': Werte {sorted(set(werte))} enthalten nicht den "
            f"Rohwert der Aufzeichnung ({erwartet})"
        )


def test_ac1_cin_ml_und_cape_ml_tragen_die_karnisch_rohwerte(monkeypatch):
    """AC-1, zweite Haelfte -- eigener Ort, weil `cin_ml`/`cape_ml` am
    Sturm-Punkt selbst nur nahe-Null-Werte tragen (Modul-Docstring 3): am
    Karnischen Hoehenweg tragen sie reale, von Null klar verschiedene Werte
    (~7,3 J/kg bzw. ~753 J/kg)."""
    _run, ende = _fenster_ab_lauf()
    with _server(monkeypatch):
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _KARNISCH, None, ende,
        )

    erwartet_cin = rohwert_an(_NEUE_EINZEL_FIXTUREN["cin_ml"].read_bytes(), 46.40, 12.52)
    erwartet_cape = rohwert_an(_NEUE_EINZEL_FIXTUREN["cape_ml"].read_bytes(), 46.40, 12.52)
    assert erwartet_cin > 1, "Aufzeichnung traegt am Karnischen Hoehenweg keinen echten cin_ml-Wert"
    assert erwartet_cape > 1, "Aufzeichnung traegt am Karnischen Hoehenweg keinen echten cape_ml-Wert"

    cin_werte = [v for v in ergebnis.get("cin_ml", {}).values() if v is not None]
    cape_werte = [v for v in ergebnis.get("cape_ml", {}).values() if v is not None]
    assert cin_werte and any(abs(v - erwartet_cin) < 0.001 for v in cin_werte), (
        f"cin_ml-Werte {sorted(set(cin_werte))} statt {erwartet_cin}"
    )
    assert cape_werte and any(abs(v - erwartet_cape) < 0.001 for v in cape_werte), (
        f"cape_ml-Werte {sorted(set(cape_werte))} statt {erwartet_cape}"
    )


# ---------------------------------------------------------------------------
# AC-2 -- cin_ml: der Marker -999,9 wird nie durchgereicht, ein echter Wert
# bleibt erhalten (Gegenprobe im selben Test).
# ---------------------------------------------------------------------------

def test_ac2_cin_ml_marker_minus_999_9_wird_nie_durchgereicht_gegenprobe_echter_wert(
    monkeypatch,
):
    """AC-2: Given einen Gitterpunkt mit dem Marker -999,9 (Nordsee-Region),
    When `cin_ml` gelesen wird, Then bleibt der Wert `None` -- UND am
    Karnischen Hoehenweg (echter Wert ~7,3 J/kg) bleibt er erhalten."""
    marker_ort = Location(latitude=53.90, longitude=1.22, name="cin_ml-Marker-Punkt")
    roh_marker = rohwert_an(_NEUE_EINZEL_FIXTUREN["cin_ml"].read_bytes(), 53.90, 1.22)
    assert abs(roh_marker - (-999.9)) < 0.01, (
        f"Aufzeichnung traegt an diesem Punkt {roh_marker} statt -999,9 -- "
        "der Test wuerde nichts pruefen"
    )
    roh_echt = rohwert_an(_NEUE_EINZEL_FIXTUREN["cin_ml"].read_bytes(), 46.40, 12.52)
    assert roh_echt > 1, "Kein echter cin_ml-Wert am Karnischen Hoehenweg -- Gegenprobe untauglich"

    _run, ende = _fenster_ab_lauf()
    with _server(monkeypatch):
        marker_ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            marker_ort, None, ende,
        )
        echt_ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _KARNISCH, None, ende,
        )

    marker_werte = list(marker_ergebnis.get("cin_ml", {}).values())
    assert marker_werte, "Kein Eintrag fuer cin_ml am Marker-Punkt -- nichts geprueft"
    assert all(v is None for v in marker_werte), (
        f"cin_ml am Marker-Punkt traegt {marker_werte} statt durchgaengig None -- "
        "der Marker -999,9 wurde als echter Wert durchgereicht"
    )
    echt_werte = [v for v in echt_ergebnis.get("cin_ml", {}).values() if v is not None]
    assert echt_werte and any(abs(v - roh_echt) < 0.001 for v in echt_werte), (
        f"cin_ml am Karnischen Hoehenweg traegt {echt_werte} statt {roh_echt} -- "
        "ein Filter, der pauschal alles auf None setzt, waere sonst ebenfalls gruen"
    )


# ---------------------------------------------------------------------------
# AC-3 -- Fuellwert 9999,0 bleibt fuer JEDE der sieben neuen Groessen None.
# ---------------------------------------------------------------------------

def test_ac3_fuellwert_9999_bleibt_fuer_alle_sieben_neuen_groessen_none(monkeypatch):
    """AC-3: Given Masuren (ausserhalb des ICON-D2-Modellgebiets, Marker
    9999,0 in JEDER der sieben Aufzeichnungen), When die Signale geholt
    werden, Then bleibt jedes der sieben neuen Felder `None`."""
    for name, pfad in _NEUE_EINZEL_FIXTUREN.items():
        roh = rohwert_an(pfad.read_bytes(), 54.0, 20.0)
        assert roh >= 9999.0, f"Signal '{name}': kein Fuellwert an Masuren ({roh}) -- Test untauglich"
    roh_lpi_max = rohwert_an(_LPI_MAX_JE_TTT[2].read_bytes(), 54.0, 20.0)
    assert roh_lpi_max >= 9999.0, f"lpi_max: kein Fuellwert an Masuren ({roh_lpi_max})"

    _run, ende = _fenster_ab_lauf()
    with _server(monkeypatch):
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _MASUREN, None, ende,
        )

    neue_signale = list(_NEUE_EINZEL_FIXTUREN) + ["lpi_max"]
    for signal in neue_signale:
        werte = list(ergebnis.get(signal, {}).values())
        assert werte, f"Signal '{signal}': keine Eintraege am Masuren-Punkt -- nichts geprueft"
        assert all(v is None for v in werte), (
            f"Signal '{signal}' traegt an Masuren {werte} statt durchgaengig "
            "None -- der Fuellwert 9999,0 wurde durchgereicht"
        )


# ---------------------------------------------------------------------------
# AC-4 -- sdi_2 behaelt sein Vorzeichen.
# ---------------------------------------------------------------------------

def test_ac4_sdi2_negativer_wert_behaelt_sein_vorzeichen(monkeypatch):
    """AC-4: Given `sdi_2` traegt an einem Punkt einen negativen Rohwert
    (antizyklonale Rotation, Sturm-Standort), When der Wert gespeichert wird,
    Then steht er MIT Vorzeichen im Ergebnis -- nicht sein Betrag."""
    roh = rohwert_an(_NEUE_EINZEL_FIXTUREN["sdi_2"].read_bytes(), 44.34, 7.56)
    assert roh < 0, f"Aufzeichnung traegt an diesem Punkt {roh} -- kein negativer Wert, Test untauglich"

    _run, ende = _fenster_ab_lauf()
    with _server(monkeypatch):
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _STURM, None, ende,
        )

    werte = [v for v in ergebnis.get("sdi_2", {}).values() if v is not None]
    assert werte, "Kein sdi_2-Wert angekommen"
    assert any(v < 0 for v in werte), (
        f"sdi_2-Werte {sorted(set(werte))} sind alle >= 0 -- das Vorzeichen "
        f"des Rohwerts ({roh}) wurde nicht erhalten (Betragsbildung gehoert "
        "erst in die spaetere Einstufung)"
    )
    assert any(abs(v - roh) < 0.0001 for v in werte), (
        f"sdi_2-Werte {sorted(set(werte))} treffen nicht den Rohwert {roh} "
        "exakt (nur das Vorzeichen zu pruefen waere nicht genug)"
    )


# ---------------------------------------------------------------------------
# AC-5 -- lpi_max folgt dem Momentanverlauf, keine Kumulation.
# ---------------------------------------------------------------------------

def test_ac5_lpi_max_folgt_dem_momentanverlauf_und_wird_nicht_kumuliert(monkeypatch):
    """AC-5: Given eine Zeitreihe, in der `lpi_max` an einem festen Punkt
    real steigt und wieder faellt (0,0 -> 216,73 -> 39,66 -> 0,0 -- vier
    aufeinanderfolgende, echt abgerufene Zeitschritte), When die Werte
    gelesen werden, Then folgen sie GENAU diesem Verlauf -- keine kumulierte
    Rueckrechnung (die wuerde monoton bleiben oder falsche Differenzen
    zeigen)."""
    run, ende = _fenster_ab_lauf(stunden=4)
    with _server(monkeypatch):
        ergebnis = dwd.DwdDirectProvider().fetch_thunder_signals_named(
            _STURM, None, ende,
        )

    reihe = ergebnis.get("lpi_max", {})
    assert set(reihe) == {1, 2, 3, 4}, f"Erwartet Offsets 1..4, bekommen {sorted(reihe)}"
    for offset, fixture_pfad in _LPI_MAX_JE_TTT.items():
        erwartet = rohwert_an(fixture_pfad.read_bytes(), 44.34, 7.56)
        tatsaechlich = reihe[offset]
        assert tatsaechlich is not None and abs(tatsaechlich - erwartet) < 0.01, (
            f"Offset {offset}: erwartet {erwartet} (Rohwert der Aufzeichnung), "
            f"bekommen {tatsaechlich}"
        )
    assert reihe[2] > reihe[3] > reihe[1], (
        f"Der Verlauf {reihe} steigt nicht erst und faellt dann wieder -- bei "
        "kumulierter Ruckrechnung waere er monoton"
    )
    assert reihe[4] == 0.0, (
        f"Offset 4 traegt {reihe[4]} statt zurueck auf ~0 zu fallen -- ein "
        "kumulierter Wert koennte NIE wieder auf 0 zurueckfallen"
    )


# ---------------------------------------------------------------------------
# AC-7 -- Reihenfolge/Budget: die drei vordersten Signale sind bereits
# abgerufen, wenn das Budget greift.
# ---------------------------------------------------------------------------

def test_ac7_reihenfolge_und_budget_erschoepfung_bevorzugen_die_vorderen_signale(
    monkeypatch,
):
    """AC-7: Given das Zeitbudget (150 s) ist erschoepft, When der Abbruch
    greift, Then sind `lpi`, `grau_gsp` und `cin_ml` bereits abgerufen, weil
    sie in der Reihenfolge vorn stehen -- die HINTEREN Signale fallen bei
    knappem Budget komplett aus (dwd.py:446-448/457-458), die Reihenfolge ist
    also eine fachliche Entscheidung.

    Strukturteil (muss heute rot sein, ohne Netz): `THUNDER_PARAMS` traegt
    heute nur zwei statt neun Eintraege und beginnt nicht mit
    ('lpi', 'grau_gsp', 'cin_ml').
    """
    params = tuple(dwd.THUNDER_PARAMS)
    assert params[:3] == ("lpi", "grau_gsp", "cin_ml"), (
        f"THUNDER_PARAMS beginnt mit {params[:3] if len(params) >= 3 else params} "
        "statt ('lpi', 'grau_gsp', 'cin_ml') -- die drei kontingent-kritischsten "
        "Signale muessen VORN stehen, sonst fallen sie bei knappem Budget zuerst aus"
    )
    assert len(params) == 9, (
        f"Erwartet 9 Gewitterparameter (2 bestehende + 7 neue), THUNDER_PARAMS "
        f"traegt {len(params)}: {params}"
    )

    monkeypatch.setattr(dwd, "THUNDER_FETCH_DEADLINE_SECONDS", 0.4, raising=True)
    _run, ende = _fenster_ab_lauf(stunden=24)
    with _server(monkeypatch, verzoegerung_s=0.1) as srv:
        dwd.DwdDirectProvider().fetch_thunder_signals_named(_KARNISCH, None, ende)
        angefragte_params = {p for p, _ttt in srv.abrufe}

    assert "lpi" in angefragte_params and "grau_gsp" in angefragte_params, (
        f"Die vordersten Signale wurden nicht kontaktiert: {angefragte_params}"
    )
    assert "uh_max_low" not in angefragte_params, (
        f"Das LETZTE Signal der Reihenfolge wurde trotz Budget von 0,4 s "
        f"kontaktiert: {angefragte_params} -- die Reihenfolge greift nicht"
    )
