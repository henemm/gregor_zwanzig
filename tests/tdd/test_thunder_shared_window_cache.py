"""RED-Tests zu #1457 S2a — AC-9 (neu), AC-11, AC-12.

Spec: docs/specs/modules/feat_1457_s2a_blitzdichte_meteofrance.md

Alle drei Tests gehen auf Adversary-Befunde zurueck, die 12 gruene Tests ueberlebt haben:

**AC-9 (F002)** — Die erste Fassung prueft, ob eine Methode mehrere Orte verarbeiten
  KANN. Sie kann es, wird im Produktivcode aber nur mit Ein-Element-Listen aufgerufen,
  weil die Anreicherung je einzelnem Abruf sitzt. Erfuellt und wirkungslos zugleich —
  dasselbe Muster wie AC-7, zum zweiten Mal in derselben Scheibe. Jetzt wird die
  **Wirkung ueber den regulaeren Weg** geprueft, fuer Trip und Ortsvergleich gemeinsam.

**AC-11 (F001)** — Gegen das alte Paris-Fixture lieferten alle acht Korsika-Orte
  denselben Wert, weil `_read_point_value` ausserhalb liegende Koordinaten auf den
  Randpixel klemmt. Der alte Test prueft nur `any(v is not None)` und kann das
  strukturell nicht sehen. Jetzt gegen eine echte Korsika-Aufzeichnung mit belegt
  unterschiedlichen Werten.

**AC-12 (F005)** — Die Zustaendigkeit wird ueber die Grundvorhersage-Tabelle
  gefiltert statt ueber die Gewitter-Tabelle. Fuer Frankreich identisch, deshalb heute
  folgenlos; bei S2b (Oesterreich: Schnee GeoSphere, Gewitter DWD) der erste Fehlerfall.

Testart: Kern-Schicht, echte lokale HTTP-Server, aufgezeichnete Antworten. Kein Netz.
"""
from __future__ import annotations

import json
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
from providers import openmeteo as om  # noqa: E402

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "meteofrance"
# Echte AROME-Antwort ueber GANZ Korsika (41,30-43,11 N / 8,39-9,60 O),
# aufgezeichnet 2026-08-02. Die Orte unten liegen alle DARIN.
_FIXTURE_KORSIKA = _FIXTURE_DIR / "arome_korsika_litota3_20260802.grib2"

# Gemessene Werte in dieser Aufzeichnung — die Grundlage von AC-11
_PETRA_PIANA = Location(latitude=42.22, longitude=9.07, name="Petra Piana")   # 0,124
_VIZZAVONA = Location(latitude=42.05, longitude=9.15, name="Vizzavona")       # 0,254
_ASCU = Location(latitude=42.42, longitude=8.90, name="Ascu Stagnu")          # 0,0


def _om_antwort() -> dict:
    """Gueltige Open-Meteo-Antwort — Hauptquelle laeuft, kein Ausfall."""
    base = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    times = [(base + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(6)]
    n = len(times)
    return {
        "latitude": 42.22, "longitude": 9.07, "generationtime_ms": 0.1,
        "utc_offset_seconds": 0, "timezone": "GMT",
        "hourly_units": {"temperature_2m": "°C"},
        "hourly": {
            "time": times,
            "temperature_2m": [15.0] * n, "wind_speed_10m": [5.0] * n,
            "wind_direction_10m": [180] * n, "wind_gusts_10m": [12.0] * n,
            "precipitation": [0.0] * n, "weather_code": [1] * n,
            "cape": [0.0] * n, "is_day": [1] * n,
        },
    }


@pytest.fixture
def dienste(monkeypatch):
    """Beide Quellen als echte lokale Server, mit Abrufzaehler fuer Météo-France."""
    om_body = json.dumps(_om_antwort()).encode("utf-8")
    grib = _FIXTURE_KORSIKA.read_bytes()
    mf_abrufe: list[str] = []

    class _OmHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(om_body)))
            self.end_headers()
            self.wfile.write(om_body)

        def log_message(self, *a):
            pass

    class _MfHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = parse_qs(urlparse(self.path).query)
            mf_abrufe.append((q.get("coverageId") or [""])[0])
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(grib)))
            self.end_headers()
            self.wfile.write(grib)

        def log_message(self, *a):
            pass

    om_srv = ThreadingHTTPServer(("127.0.0.1", 0), _OmHandler)
    mf_srv = ThreadingHTTPServer(("127.0.0.1", 0), _MfHandler)
    for s in (om_srv, mf_srv):
        threading.Thread(target=s.serve_forever, daemon=True).start()
    monkeypatch.setattr(om, "BASE_HOST", "http://%s:%d" % om_srv.server_address, raising=True)
    monkeypatch.setattr(om, "ENSEMBLE_BASE_HOST", "http://%s:%d" % om_srv.server_address, raising=True)
    monkeypatch.setattr(mf, "BASE_URL", "http://%s:%d/" % mf_srv.server_address, raising=True)
    yield mf_abrufe
    om_srv.shutdown()
    mf_srv.shutdown()


def _blitz(abrufe):
    return [a for a in abrufe if "LITOTA3" in a]


def test_ac9_zweiter_ort_in_der_naehe_kostet_keine_zusaetzlichen_abrufe(dienste):
    """AC-9: Given zwei nahe beieinander liegende Korsika-Orte, When beide
    NACHEINANDER ueber den regulaeren Weg abgerufen werden, Then entstehen zusammen
    nicht mehr Meteo-France-Abrufe als fuer einen einzigen Ort.

    Entscheidend ist der regulaere Weg (`OpenMeteoProvider.fetch_forecast`) — genau so
    rufen Trip UND Ortsvergleich, jeweils Ort fuer Ort. Ein Zwischenspeicher mit
    Rechteck-Granularitaet bedient den zweiten Ort aus der Antwort des ersten.
    """
    provider = om.OpenMeteoProvider()

    provider.fetch_forecast(_PETRA_PIANA, enrich_ensemble=False)
    nach_einem = len(_blitz(dienste))

    provider.fetch_forecast(_VIZZAVONA, enrich_ensemble=False)
    nach_zweien = len(_blitz(dienste))

    assert nach_einem > 0, "Der erste Ort hat gar keine Blitzdichte geholt"
    assert nach_zweien == nach_einem, (
        f"Erster Ort: {nach_einem} Abrufe, nach dem zweiten: {nach_zweien}. Der zweite "
        "Ort loest eigene Abrufe aus, obwohl er im selben Fenster liegt — die Ersparnis "
        "erreicht weder Trip noch Ortsvergleich"
    )


def test_ac11_jeder_ort_bekommt_seinen_eigenen_wert(dienste):
    """AC-11: Given mehrere Orte im selben Fenster mit belegt unterschiedlichen Werten,
    When ihre Blitzdichte gelesen wird, Then bekommt jeder seinen EIGENEN Wert.

    Gegen die echte Korsika-Aufzeichnung: Petra Piana 0,124 · Vizzavona 0,254 ·
    Ascu Stagnu 0,0 (gemessen 2026-08-02). Der alte Test prueft nur, DASS ein Wert da
    ist — gegen das Paris-Fixture lieferten alle acht Orte denselben Randpixel.
    """
    provider = mf.MeteoFranceDirectProvider()

    ergebnis = provider.fetch_thunder_signals_multi([_PETRA_PIANA, _VIZZAVONA, _ASCU])

    werte_je_ort = {}
    for ort in (_PETRA_PIANA, _VIZZAVONA, _ASCU):
        werte = [v for v in (ergebnis.get(ort.name) or {}).values() if v is not None]
        assert werte, f"Ort '{ort.name}' hat keinen einzigen Wert"
        werte_je_ort[ort.name] = werte[0]

    assert len(set(werte_je_ort.values())) > 1, (
        f"Alle Orte liefern denselben Wert: {werte_je_ort}. Entweder wird mehrfach "
        "derselbe Bildpunkt gelesen, oder Koordinaten werden auf den Gitterrand "
        "geklemmt — Werte da, aber vom falschen Ort"
    )


def test_ac11_ort_ausserhalb_des_fensters_wird_verworfen_nicht_geklemmt(dienste):
    """AC-11, Zusatzbedingung: Given ein Ort AUSSERHALB des geladenen Fensters,
    When sein Wert gelesen wird, Then wird er verworfen (`None`) — nicht auf den
    naechstgelegenen Randpixel geklemmt.

    Das war die Ursache von F001: `_read_point_value` klemmt row/col auf den Rand und
    liefert damit still den Wert eines fremden Ortes.
    """
    # Paris — liegt weit ausserhalb der Korsika-Aufzeichnung
    paris = Location(latitude=48.85, longitude=2.35, name="Paris")
    provider = mf.MeteoFranceDirectProvider()

    ergebnis = provider.fetch_thunder_signals_multi([_PETRA_PIANA, paris])

    paris_werte = [v for v in (ergebnis.get("Paris") or {}).values() if v is not None]
    assert not paris_werte, (
        f"Paris liegt ausserhalb des geladenen Fensters, bekommt aber Werte "
        f"{paris_werte[:3]} — das ist der Randpixel eines fremden Ortes"
    )


def _fenster(nr: int) -> tuple[str, str, tuple[float, float, float, float]]:
    """Ein eindeutiges Fenster je Nummer — verschiedene Rechtecke, damit jeder
    Ablage-Vorgang einen eigenen Schluessel bekommt."""
    return ("LITOTA3", "2026-08-02T12:00:00Z", (41.0 + nr, 42.0 + nr, 9.0, 9.5))


def test_f_adv4_anzahl_deckel_verdraengt_den_aeltesten_eintrag():
    """F-ADV4, erste Schranke: Given ein Speicher mit einer Obergrenze fuer die
    Anzahl der Eintraege, When mehr Fenster abgelegt werden als erlaubt, Then
    weicht der aelteste und die Anzahl bleibt unter der Grenze.

    Warum das bewacht sein muss: Der Speicher ist ein Prozess-Singleton, der
    ueber alle Touren und Ortsvergleiche eines Serverlaufs hinweg gefuellt wird.
    Ohne wirksame Verdraengung waechst er unbegrenzt — im Dauerbetrieb bedeutet
    das einen langsam vollaufenden Prozess. Beide Schranken werden getrennt
    geprueft, weil eine allein nicht traegt: ein Fenster kostet je nach
    Kantenlaenge 81 KB bis 1,3 MB, eine reine Anzahl-Schranke waere im einen
    Fall zu knapp und im anderen zu grosszuegig.
    """
    from providers.thunder_window_cache import ThunderWindowCache

    speicher = ThunderWindowCache(max_entries=3, max_bytes=10 * 1024 * 1024)
    for nr in range(5):
        speicher.put(*_fenster(nr), b"x" * 100)

    stats = speicher.stats()
    assert stats["total_entries"] <= 3, (
        f"{stats['total_entries']} Eintraege bei einer Grenze von 3 — die "
        "Anzahl-Schranke verdraengt nicht, der Speicher waechst unbegrenzt"
    )
    assert speicher.get(*_fenster(0)) is None, (
        "Der aelteste Eintrag liegt noch da — verdraengt wird offenbar der "
        "falsche (oder gar keiner)"
    )
    assert speicher.get(*_fenster(4)) == b"x" * 100, (
        "Der zuletzt abgelegte Eintrag fehlt — die Verdraengung raeumt zu viel weg"
    )


def test_f_adv4_byte_deckel_greift_auch_bei_wenigen_grossen_eintraegen():
    """F-ADV4, zweite Schranke: Given wenige, aber grosse Fenster, When ihre
    Summe die Byte-Grenze ueberschreiten wuerde, Then weicht der aelteste und
    der belegte Speicher bleibt unter der Grenze.

    Die Anzahl-Schranke faengt diesen Fall NICHT: hier sind es nur drei
    Eintraege, also weit unter 48 — sie wuerden zusammen aber mehr belegen als
    erlaubt. Genau dafuer gibt es die zweite Schranke.
    """
    from providers.thunder_window_cache import ThunderWindowCache

    grenze = 1000
    brocken = b"y" * 400
    speicher = ThunderWindowCache(max_entries=1000, max_bytes=grenze)
    for nr in range(3):
        speicher.put(*_fenster(nr), brocken)

    stats = speicher.stats()
    assert stats["total_bytes"] <= grenze, (
        f"{stats['total_bytes']} Bytes belegt bei einer Grenze von {grenze} — "
        "die Byte-Schranke greift nicht. Bei 1,3 MB je Fenster laeuft der "
        "Prozess so ueber die Zeit voll"
    )
    assert speicher.get(*_fenster(0)) is None, (
        "Der aelteste Eintrag liegt noch da, obwohl die Byte-Grenze ueberschritten "
        "war — verdraengt wird der falsche oder gar keiner"
    )
    assert speicher.get(*_fenster(2)) == brocken, (
        "Der zuletzt abgelegte Eintrag fehlt — die Verdraengung raeumt zu viel weg"
    )
    assert stats["total_bytes"] > 0, (
        "Der Speicher ist ganz leer — dann bewiese der Test nur, dass nichts "
        "abgelegt wurde, nicht dass die Schranke sauber verdraengt"
    )


def test_ac12_zustaendigkeit_kommt_aus_der_gewitter_tabelle(dienste, monkeypatch):
    """AC-12: Given ein Ort, fuer den Grundvorhersage- und Gewitter-Tabelle
    UNTERSCHIEDLICH antworten, When die Gewitter-Zustaendigkeit bestimmt wird,
    Then entscheidet die Gewitter-Tabelle.

    Heute filtert `fetch_thunder_signals_multi` ueber `region_routing` (Grundvorhersage).
    Fuer Frankreich sind beide gleich — bei S2b bricht es am Zielfall Oesterreich:
    Schnee von GeoSphere, Gewitter vom DWD.
    """
    from providers import thunder_routing

    # WICHTIG: `meteofrance.py:60` importiert `direct_provider_for` direkt in den
    # Modul-Namensraum (`from providers.region_routing import direct_provider_for`).
    # Ein monkeypatch auf `region_routing.direct_provider_for` wuerde deshalb INS
    # LEERE laufen — das Modul haelt seine eigene Referenz. Gepatcht werden muss
    # `mf.direct_provider_for`. (Genau daran war die erste Fassung dieses Tests
    # faelschlich gruen und bewies nichts.)
    monkeypatch.setattr(
        thunder_routing, "thunder_provider_for",
        lambda lat, lon: "fr_direct", raising=True,
    )
    monkeypatch.setattr(
        mf, "direct_provider_for", lambda lat, lon: None, raising=True,
    )

    provider = mf.MeteoFranceDirectProvider()
    ergebnis = provider.fetch_thunder_signals_multi([_PETRA_PIANA])

    werte = [v for v in (ergebnis.get("Petra Piana") or {}).values() if v is not None]
    assert werte, (
        "Kein Wert geholt, obwohl die GEWITTER-Tabelle den Ort als zustaendig meldet — "
        "die Entscheidung faellt ueber die Grundvorhersage-Tabelle statt ueber die "
        "eigens dafuer angelegte Gewitter-Tabelle"
    )
