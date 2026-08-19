"""TDD RED -- #1758 Scheibe A: GeoSphere liefert cape/cin als benannte
Gewittersignale, zweiter gekapselter Abruf analog `fetch_snowgrid`.

Spec: docs/specs/modules/feat_1758_geosphere_cape_cin.md
Abgedeckte ACs hier (Provider-Ebene): AC-1, AC-2, AC-3, AC-4, AC-5, AC-11.

===========================================================================
AUFZEICHNUNG (echt abgerufen 2026-08-18, live gemessen vom Team-Lead)
===========================================================================
`GET https://dataset.api.hub.geosphere.at/v1/timeseries/forecast/nwp-v1-1h-2500m?lat_lon=46.66,12.74&parameters=cape&parameters=cin&parameters=t2m`
-- `reference_time` 2026-08-18T12:00+00:00, 56 Stundenwerte, Punkt Karnischer
Hoehenweg. `cape` in `m2 s-2`, `cin` in `J kg-1` -- dimensionsgleich zu J/kg,
NICHT umrechnen (Spec Invariante 2). CAPE-Maximum eindeutig: 713.5 beim
56-stuendigen Verlauf (Index 42, Zeitstempel 2026-08-20T11:00+00:00) -- Anker
fuer AC-11.

Zweite Aufzeichnung: reale HTTP-400-Antwort ausserhalb des Gitters (Korsika,
42.22/9.07), Koerper `{"detail":"Requested point 42.22,9.07 is outside of
dataset bounds!"}`.

Fixtures: `tests/fixtures/geosphere/nwp_cape_cin_karnisch_2026081812.json`,
`tests/fixtures/geosphere/nwp_cape_cin_outside_bounds_400.json`. Fuer die
unveraenderte Grundvorhersage (AC-2) wird die BESTEHENDE Fixture
`tests/fixtures/geosphere_nwp_innsbruck.json` wiederverwendet -- kein Duplikat.

===========================================================================
RED-GRUND (heute, unveraenderter Code)
===========================================================================
`GeoSphereProvider` kennt weder `fetch_thunder_signals_named` noch
`CAPE_CIN_PARAMS` noch `_parse_cape_cin_response` -> AttributeError. Die
`_hole_eintraege`-Tabelle `_SIGNAL_ZU_FELD` kennt weder "cape" noch "cin" ->
selbst nach Ergaenzung der Provider-Methode liefe AC-5 mit einer leeren
Zuordnung.

Testart: Kern-Schicht -- lokaler `ThreadingHTTPServer` liefert die
Aufzeichnungen aus (Muster `test_dwd_thunder_new_signals_fetch.py`), kein
echtes Netz, keine Mocks. KEIN `live`-Marker (anders als das DWD-Vorbild):
hier wird nichts gegen den echten Dienst gemessen, nur gegen aufgezeichnete
Antworten -- das ist Kern-Schicht.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List, Tuple
from urllib.parse import parse_qs, urlparse

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location  # noqa: E402
from providers import geosphere  # noqa: E402
from providers import thunder_enrichment  # noqa: E402

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "geosphere"
_FIXTURE_CAPE_CIN_KHW = _FIXTURE_DIR / "nwp_cape_cin_karnisch_2026081812.json"
_FIXTURE_CAPE_CIN_OUTSIDE = _FIXTURE_DIR / "nwp_cape_cin_outside_bounds_400.json"
_FIXTURE_BASE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "geosphere_nwp_innsbruck.json"
)

_KARNISCH = Location(latitude=46.66, longitude=12.74, name="Karnischer Hoehenweg")
_AUSSERHALB = Location(latitude=42.22, longitude=9.07, name="Korsika (ausserhalb AROME-Gitter)")


def _cape_cin_features(fixture_path: Path) -> Tuple[List[datetime], List[float], List[float]]:
    """Liest Zeitstempel + cape/cin-Rohwerte UNABHAENGIG aus der Aufzeichnung
    -- nie als Konstante im Test notiert (Projektlehre #1144)."""
    payload = json.loads(fixture_path.read_text())
    timestamps = [datetime.fromisoformat(t) for t in payload["timestamps"]]
    params = payload["features"][0]["properties"]["parameters"]
    return timestamps, params["cape"]["data"], params["cin"]["data"]


class _Server(ThreadingHTTPServer):
    def __init__(self, addr, handler, *, cape_cin_status, cape_cin_body, base_body,
                 verzoegerung_s: float = 0.0):
        super().__init__(addr, handler)
        self.cape_cin_status = cape_cin_status
        self.cape_cin_body = cape_cin_body
        self.base_body = base_body
        self.verzoegerung_s = verzoegerung_s
        self.requests: list = []
        self._lock = threading.Lock()

    def handle_error(self, request, client_address):
        # AC-13: bei kurzem Client-Zeitbudget (< verzoegerung_s) trennt der
        # Client die Verbindung, bevor der Server (noch schlafend) antworten
        # kann -- ein erwarteter BrokenPipeError, kein Testfehler. Bewusst
        # geschluckt statt Standard-Traceback auf stderr (Muster `log_message`
        # unten).
        pass


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        srv = self.server
        if srv.verzoegerung_s:
            # AC-13: simuliert einen langsamen/haengenden GeoSphere-Server --
            # antwortet erst NACH der Verzoegerung, damit der eigene Zeit-
            # budget-Wert (`geosphere.THUNDER_FETCH_TIMEOUT_SECONDS`) greift.
            time.sleep(srv.verzoegerung_s)
        qs = parse_qs(urlparse(self.path).query)
        params = tuple(sorted((qs.get("parameters", [""])[0]).split(",")))
        with srv._lock:
            srv.requests.append(params)
        if params == ("cape", "cin"):
            status, body = srv.cape_cin_status, srv.cape_cin_body
        else:
            status, body = 200, srv.base_body
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@contextmanager
def _server(monkeypatch, *, cape_cin_status: int = 200, cape_cin_body=None, base_body=None,
            verzoegerung_s: float = 0.0):
    """Lokaler Server unter `geosphere.BASE_URL`. Dispatch NUR ueber den
    `parameters`-Query-Parameter -- derselbe Endpunkt bedient sowohl den
    Grundvorhersage- als auch den cape/cin-Abruf (Spec Implementation Details
    1: beide nutzen `ENDPOINTS["nwp"]`). `verzoegerung_s` (AC-13): laesst JEDE
    Antwort um diese Zeit verzoegern, um das Zeitbudget des additiven Abrufs
    zu pruefen."""
    cape_cin_body = cape_cin_body if cape_cin_body is not None else _FIXTURE_CAPE_CIN_KHW.read_bytes()
    base_body = base_body if base_body is not None else _FIXTURE_BASE.read_bytes()
    srv = _Server(
        ("127.0.0.1", 0), _Handler,
        cape_cin_status=cape_cin_status, cape_cin_body=cape_cin_body, base_body=base_body,
        verzoegerung_s=verzoegerung_s,
    )
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(geosphere, "BASE_URL", "http://%s:%d/v1" % srv.server_address)
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# AC-1 -- benannter Abruf liefert cape/cin mit den Rohwerten der Aufzeichnung.
# ---------------------------------------------------------------------------

def test_ac1_cape_und_cin_tragen_die_rohwerte_der_aufzeichnung(monkeypatch):
    """AC-1: Given den Karnischen Hoehenweg (im AROME-Gitter) mit veroeffent-
    lichtem Lauf, When `fetch_thunder_signals_named` laeuft, Then liefert er
    `cape` und `cin` mit denselben Zahlen, die die Aufzeichnung an diesem
    Gitterpunkt enthaelt -- unabhaengig aus der Fixture gelesen, nicht als
    Konstante notiert."""
    timestamps, cape_data, cin_data = _cape_cin_features(_FIXTURE_CAPE_CIN_KHW)
    basis = timestamps[0] - timedelta(hours=1)
    ende = timestamps[-1]

    with _server(monkeypatch):
        ergebnis = geosphere.GeoSphereProvider().fetch_thunder_signals_named(
            _KARNISCH, basis, ende,
        )

    assert "cape" in ergebnis and "cin" in ergebnis, f"Signale fehlen komplett: {sorted(ergebnis)}"
    cape_werte, cin_werte = ergebnis["cape"], ergebnis["cin"]
    assert cape_werte, "keine cape-Werte angekommen"
    assert cin_werte, "keine cin-Werte angekommen"

    for i in (0, len(cape_data) // 2, len(cape_data) - 1):
        offset = i + 1
        erwartet = cape_data[i]
        tatsaechlich = cape_werte.get(offset)
        assert tatsaechlich is not None and abs(tatsaechlich - erwartet) < 0.001, (
            f"Offset {offset}: erwartet cape={erwartet} (Rohwert Index {i}), bekommen {tatsaechlich}"
        )
    for i in (0, len(cin_data) // 2, len(cin_data) - 1):
        offset = i + 1
        erwartet = cin_data[i]
        tatsaechlich = cin_werte.get(offset)
        assert tatsaechlich is not None and abs(tatsaechlich - erwartet) < 0.001, (
            f"Offset {offset}: erwartet cin={erwartet}, bekommen {tatsaechlich}"
        )


# ---------------------------------------------------------------------------
# AC-2 -- Ausfall des gekapselten Abrufs kippt die Grundvorhersage nicht.
# ---------------------------------------------------------------------------

def test_ac2_gekapselter_abruf_scheitert_ohne_die_grundvorhersage_zu_beruehren(monkeypatch):
    """AC-2: Given der cape/cin-Abruf scheitert (HTTP 400, z.B. unbekannter
    Parametername), When dieselbe Reihe trotzdem Temperatur/Wind/Schnee
    enthaelt, Then bleiben die GeoSphere-Felder leer, und `t2m_c`,
    `wind10m_kmh`, `snow_new_acc_cm` sind gegenueber einem Lauf OHNE den
    Zusatzabruf zeichenweise (datenpunktweise) unveraendert."""
    with _server(monkeypatch):
        baseline = geosphere.GeoSphereProvider().fetch_combined(
            _KARNISCH.latitude, _KARNISCH.longitude,
            include_snow=False, include_cloud_layers=False,
        )

    fehlerantwort = b'{"detail":"Parameters {\'gibtesnicht\'} do not exist or access is denied"}'
    with _server(monkeypatch, cape_cin_status=400, cape_cin_body=fehlerantwort):
        fehlgeschlagen = geosphere.GeoSphereProvider().fetch_thunder_signals_named(
            _KARNISCH, None, None,
        )
        danach = geosphere.GeoSphereProvider().fetch_combined(
            _KARNISCH.latitude, _KARNISCH.longitude,
            include_snow=False, include_cloud_layers=False,
        )

    assert fehlgeschlagen == {"cape": {}, "cin": {}}, (
        f"Fehlgeschlagener Abruf liefert {fehlgeschlagen} statt leerer Dicts -- "
        "der HTTP-400 wurde nicht abgefangen"
    )
    assert baseline.data and len(baseline.data) == len(danach.data), (
        "Grundvorhersage-Laenge unterscheidet sich -- Vergleichsgrundlage kaputt"
    )
    for dp_a, dp_b in zip(baseline.data, danach.data):
        assert dp_a.t2m_c == dp_b.t2m_c, f"t2m_c weicht ab: {dp_a.t2m_c} vs. {dp_b.t2m_c}"
        assert dp_a.wind10m_kmh == dp_b.wind10m_kmh, (
            f"wind10m_kmh weicht ab: {dp_a.wind10m_kmh} vs. {dp_b.wind10m_kmh}"
        )
        assert dp_a.snow_new_acc_cm == dp_b.snow_new_acc_cm, (
            f"snow_new_acc_cm weicht ab: {dp_a.snow_new_acc_cm} vs. {dp_b.snow_new_acc_cm}"
        )


# ---------------------------------------------------------------------------
# AC-3 -- keine Umrechnung, Werte exakt wie in der Antwort (inkl. Vorzeichen).
# ---------------------------------------------------------------------------

def test_ac3_keine_umrechnung_werte_bleiben_exakt_wie_in_der_antwort(monkeypatch):
    """AC-3: Given `cape`/`cin` liegen in `m2 s-2` bzw. `J kg-1` vor (dimen-
    sionsgleich zu J/kg), When die Werte gespeichert werden, Then entspricht
    die gespeicherte Zahl exakt dem Rohwert -- jede Umrechnung (z.B. Faktor
    1000 oder /9.81) wuerde diesen Test rot machen. Zusaetzlich: ein
    negativer `cin`-Wert behaelt sein Vorzeichen."""
    timestamps, cape_data, cin_data = _cape_cin_features(_FIXTURE_CAPE_CIN_KHW)
    basis = timestamps[0] - timedelta(hours=1)
    ende = timestamps[-1]

    index = 26  # Nachmittagsspitze im Verlauf -- Position strukturell gewaehlt, Wert gelesen.
    erwartetes_cape = cape_data[index]
    negativ_index = next(i for i, v in enumerate(cin_data) if v < 0)
    erwartetes_cin = cin_data[negativ_index]
    assert erwartetes_cin < 0, "Aufzeichnung traegt keinen negativen cin-Wert -- Test untauglich"

    with _server(monkeypatch):
        ergebnis = geosphere.GeoSphereProvider().fetch_thunder_signals_named(
            _KARNISCH, basis, ende,
        )

    tatsaechliches_cape = ergebnis["cape"].get(index + 1)
    assert tatsaechliches_cape == erwartetes_cape, (
        f"cape={tatsaechliches_cape} statt exakt {erwartetes_cape} -- eine Umrechnung waere hier sichtbar"
    )
    tatsaechliches_cin = ergebnis["cin"].get(negativ_index + 1)
    assert tatsaechliches_cin == erwartetes_cin, (
        f"cin={tatsaechliches_cin} statt exakt {erwartetes_cin} -- Vorzeichen/Umrechnung veraendert"
    )


# ---------------------------------------------------------------------------
# AC-4 -- ausserhalb des Gitters bleiben beide Felder leer, nie 0.
# ---------------------------------------------------------------------------

def test_ac4_ausserhalb_des_gitters_bleiben_beide_felder_leer_gegenprobe_mit_gitterpunkt(
    monkeypatch,
):
    """AC-4: Given einen Punkt ausserhalb des AROME-Gitters (live gemessen:
    HTTP 400 "outside of dataset bounds"), When die Anreicherung laeuft,
    Then bleiben beide Felder leer (kein Eintrag, kein 0.0) -- Gegenprobe im
    selben Test mit einem Punkt im Gitter, der reale Werte behaelt, sonst
    waere ein Filter, der pauschal alles verwirft, ebenfalls gruen."""
    timestamps, _cape_data, _cin_data = _cape_cin_features(_FIXTURE_CAPE_CIN_KHW)
    basis = timestamps[0] - timedelta(hours=1)
    ende = timestamps[-1]

    with _server(
        monkeypatch, cape_cin_status=400, cape_cin_body=_FIXTURE_CAPE_CIN_OUTSIDE.read_bytes(),
    ):
        ergebnis_ausserhalb = geosphere.GeoSphereProvider().fetch_thunder_signals_named(
            _AUSSERHALB, basis, ende,
        )
    assert ergebnis_ausserhalb.get("cape") == {}, (
        f"cape traegt Werte ausserhalb des Gitters: {ergebnis_ausserhalb.get('cape')}"
    )
    assert ergebnis_ausserhalb.get("cin") == {}, (
        f"cin traegt Werte ausserhalb des Gitters: {ergebnis_ausserhalb.get('cin')}"
    )

    with _server(monkeypatch):
        ergebnis_gitter = geosphere.GeoSphereProvider().fetch_thunder_signals_named(
            _KARNISCH, basis, ende,
        )
    assert ergebnis_gitter.get("cape"), (
        "Gegenprobe schlaegt fehl: am Gitterpunkt kommt kein einziger cape-Wert an -- "
        "ein Filter, der pauschal alles verwirft, waere sonst ebenfalls gruen"
    )
    assert ergebnis_gitter.get("cin"), (
        "Gegenprobe schlaegt fehl: am Gitterpunkt kommt kein einziger cin-Wert an"
    )


# ---------------------------------------------------------------------------
# AC-5 -- der gemeinsame Anschluss erkennt GeoSphere ueber den benannten Weg.
# ---------------------------------------------------------------------------

def test_ac5_hole_eintraege_erkennt_den_benannten_weg_und_ordnet_ueber_signal_zu_feld_zu(
    monkeypatch,
):
    """AC-5: Given `GeoSphereProvider` implementiert `fetch_thunder_signals_named`,
    When `thunder_enrichment._hole_eintraege` die Quelle "geosphere" befragt,
    Then erkennt sie den benannten Weg und ordnet cape/cin ueber
    `_SIGNAL_ZU_FELD` den Feldern `cape_geosphere_jkg` /
    `convective_inhibition_geosphere_jkg` zu."""
    timestamps, _cape_data, _cin_data = _cape_cin_features(_FIXTURE_CAPE_CIN_KHW)
    von = timestamps[0] - timedelta(hours=1)
    bis = timestamps[-1]

    with _server(monkeypatch):
        eintraege = thunder_enrichment._hole_eintraege("geosphere", _KARNISCH, von, bis)

    nicht_leere_felder = {feld for feld, werte in eintraege if werte}
    assert {"cape_geosphere_jkg", "convective_inhibition_geosphere_jkg"} <= nicht_leere_felder, (
        f"Erwartete Felder fehlen oder sind leer. Nicht-leere Felder im Ergebnis: "
        f"{sorted(nicht_leere_felder)} (alle Eintraege: {[f for f, _w in eintraege]})"
    )


# ---------------------------------------------------------------------------
# AC-11 -- Offset-Konvention: das Maximum landet am richtigen Zeitstempel.
# ---------------------------------------------------------------------------

def test_ac11_cape_maximum_liegt_am_richtigen_zeitstempel_nicht_eine_stunde_verschoben(
    monkeypatch,
):
    """AC-11: Given `cape` hat ueber die Stunden ein eindeutiges Maximum
    (Nachmittagsgang, Tag 3 der Aufzeichnung), When die Werte den Offsets
    zugeordnet werden, Then steht das Maximum GENAU am Offset, der aus dem
    gewaehlten Bezugszeitpunkt (`_bezugszeitpunkt`-Konvention: Nullpunkt eine
    Stunde vor dem ersten gewuenschten Zeitpunkt, Offsets beginnen bei 1)
    folgt -- nicht eine Stunde davor oder danach.

    Mutations-Gegenprobe (Pflicht laut Spec): ein `enumerate()`-ab-0-Parser
    (der `start` ignoriert) wuerde jeden Wert um genau eine Stunde fruehver-
    schieben und MUSS diesen Test rot machen -- genau der Fehlertyp aus
    #874/#1275."""
    timestamps, cape_data, _cin_data = _cape_cin_features(_FIXTURE_CAPE_CIN_KHW)
    basis = timestamps[0] - timedelta(hours=1)
    ende = timestamps[-1]

    max_index = max(range(len(cape_data)), key=lambda i: cape_data[i])
    erwarteter_offset = max_index + 1
    erwartetes_maximum = cape_data[max_index]
    assert cape_data.count(erwartetes_maximum) == 1, (
        f"Maximum {erwartetes_maximum} kommt {cape_data.count(erwartetes_maximum)}x vor -- "
        "kein eindeutiger Zeitpunkt, Test untauglich"
    )

    with _server(monkeypatch):
        ergebnis = geosphere.GeoSphereProvider().fetch_thunder_signals_named(
            _KARNISCH, basis, ende,
        )

    cape_werte = ergebnis.get("cape", {})
    offsets_des_maximums = [o for o, v in cape_werte.items() if v == erwartetes_maximum]
    assert offsets_des_maximums == [erwarteter_offset], (
        f"Das Maximum {erwartetes_maximum} steht bei Offset(s) {offsets_des_maximums} statt bei "
        f"{erwarteter_offset} (Zeitstempel {timestamps[max_index].isoformat()}) -- eine "
        "Verschiebung der Offset-Abbildung um +-1 Stunde wuerde genau diesen Fehler erzeugen"
    )
