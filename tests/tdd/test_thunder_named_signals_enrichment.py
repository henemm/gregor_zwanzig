"""TDD RED — #1457 S2b: benannte Gewittersignale erreichen den Nutzer.

Spec: docs/specs/modules/feat_1457_s2b_gewitter_dwd_alpen.md
Abgedeckte ACs hier: AC-1 (Wirkungs-Nachweis Ende-zu-Ende), AC-3 (fail-soft am
gemeinsamen Anschluss), AC-9 (additive Protokoll-Erweiterung), AC-10
(Gewitter-Zustaendigkeit unabhaengig von der Grundvorhersage).

WARUM AC-1 SO FORMULIERT IST: Bei S2a waren AC-1..AC-6 erfuellt und der
Adversary hatte VERIFIED erteilt — die Blitzdichte erreichte trotzdem nie
einen Nutzer, weil der Abruf nur in der Totalausfall-Weiche hing. Deshalb
laeuft der Nachweis hier durch `OpenMeteoProvider.fetch_forecast` bei
FUNKTIONIERENDER Hauptquelle, also genau den Weg jedes echten Briefings.
Ein reiner Methodentest am Provider (den es in
`test_dwd_thunder_signal_fetch.py` zusaetzlich gibt) beweist das NICHT.

Vermessung des echten Dienstes und Herkunft der Aufzeichnungen: siehe
Modul-Docstring von `tests/tdd/test_dwd_thunder_signal_fetch.py`. Kurz:
Abrufnamen `lpi`/`grau_gsp` beim echten Dienst bestaetigt, Fuellwert ist
9999.0 (NICHT -999.0), Gitter -3,95..20,35 O / 43,17..58,09 N.

RED-GRUND (heute, unveraenderter Code):
- `thunder_enrichment` kennt kein `fetch_thunder_signals_named` und keine
  Signal->Feld-Tabelle `_SIGNAL_ZU_FELD` -> AttributeError bzw. kein Wert.
- `ForecastDataPoint` hat weder `lightning_potential_lpi_jkg` noch
  `hail_potential_grau_gsp`.
- `thunder_routing` hat keine Zeile fuer DE/Alpen/AT -> `thunder_provider_for`
  liefert dort `None`.

Testart: Kern-Schicht, echte lokale HTTP-Server (Open-Meteo-Antwort und
ICON-D2-Aufzeichnungen), kein Netz, keine Mocks.
"""
from __future__ import annotations

import json
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location  # noqa: E402
from providers import dwd  # noqa: E402
from providers import openmeteo as om  # noqa: E402
from providers import region_routing, thunder_enrichment, thunder_routing  # noqa: E402

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "dwd"
_FIXTURE_LPI = _FIXTURE_DIR / "icon_d2_alpen_lpi_2026080315_024.grib2.bz2"
_FIXTURE_GRAU = _FIXTURE_DIR / "icon_d2_alpen_grau_gsp_2026080315_024.grib2.bz2"

# Karnische Alpen, Grenze AT/IT — PO-Reiseziel. Grundvorhersage kommt hier von
# GeoSphere (`at_direct`), Gewitter soll kuenftig vom DWD kommen (AC-10).
_KARNISCH = Location(latitude=46.40, longitude=12.52, name="Karnischer Hoehenweg")


def _valide_openmeteo_antwort() -> dict:
    """Gueltige Open-Meteo-Antwort — die Hauptquelle LAEUFT, die
    Totalausfall-Weiche wird nicht erreicht (Muster
    test_thunder_enrichment_shared_path.py)."""
    base = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    times = [(base + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(6)]
    n = len(times)
    return {
        "latitude": _KARNISCH.latitude, "longitude": _KARNISCH.longitude,
        "generationtime_ms": 0.1, "utc_offset_seconds": 0, "timezone": "GMT",
        "hourly_units": {"temperature_2m": "°C"},
        "hourly": {
            "time": times,
            "temperature_2m": [15.0 + i * 0.5 for i in range(n)],
            "wind_speed_10m": [5.0] * n, "wind_direction_10m": [180] * n,
            "wind_gusts_10m": [12.0] * n, "precipitation": [0.0] * n,
            "weather_code": [1] * n, "cape": [0.0] * n, "is_day": [1] * n,
        },
    }


@pytest.fixture
def hauptquelle_laeuft(monkeypatch):
    """Open-Meteo antwortet normal — regulaerer Weg, KEIN Ausfall."""
    body = json.dumps(_valide_openmeteo_antwort()).encode("utf-8")

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(om, "BASE_HOST", "http://%s:%d" % srv.server_address)
    monkeypatch.setattr(om, "ENSEMBLE_BASE_HOST", "http://%s:%d" % srv.server_address)
    yield srv
    srv.shutdown()


@pytest.fixture
def dwd_laeuft(monkeypatch):
    """Der DWD liefert die echten ICON-D2-Aufzeichnungen aus. Dispatch ueber
    den Parameter-Ordner im Pfad — Lauf und Zeitschritt bestimmt der Provider
    selbst."""
    lpi = _FIXTURE_LPI.read_bytes()
    grau = _FIXTURE_GRAU.read_bytes()
    abrufe: list[str] = []
    sperre = threading.Lock()

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = urlparse(self.path).path
            body = None
            for teil in ("/lpi/", "/grau_gsp/"):
                if teil in path:
                    body = lpi if teil == "/lpi/" else grau
                    with sperre:
                        abrufe.append(teil.strip("/"))
                    break
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

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(dwd, "BASE_URL", "http://%s:%d/" % srv.server_address)
    yield abrufe
    srv.shutdown()


@contextmanager
def _registrierte_testquelle(name: str, factory):
    """Registriert `factory` temporaer in der ECHTEN Provider-Registry und
    stellt den Vorzustand wieder her (Muster
    test_thunder_enrichment_shared_path.py)."""
    import providers.base as base_module

    if not base_module._PROVIDER_FACTORIES:
        base_module._load_providers()
    hatte = name in base_module._PROVIDER_FACTORIES
    vorher = base_module._PROVIDER_FACTORIES.get(name)
    base_module.register_provider(name, factory)
    try:
        yield
    finally:
        if hatte:
            base_module._PROVIDER_FACTORIES[name] = vorher
        else:
            base_module._PROVIDER_FACTORIES.pop(name, None)


# ---------------------------------------------------------------------------
# AC-10 — Gewitter-Zustaendigkeit ist unabhaengig von der Grundvorhersage.
# ---------------------------------------------------------------------------

def test_ac10_gewitter_zustaendigkeit_weicht_von_der_grundvorhersage_ab():
    """AC-10: Given einen Ort in den Karnischen Alpen, dessen Grundvorhersage
    von GeoSphere (`at_direct`) kommt, When die Gewitter-Zustaendigkeit
    bestimmt wird, Then liefert `thunder_provider_for` `de_direct` — nicht
    `None` und nicht `at_direct`.

    Das ist der Kern der zweiten Tabelle: GeoSphere ist fuer Schnee und
    Temperatur in Oesterreich die bessere Quelle, hat aber kein
    Gewittersignal. Wuerde die Gewitterquelle aus der Grundvorhersage-Tabelle
    abgeleitet, bliebe der Karnische Hoehenweg dauerhaft ohne Gewitteraussage
    — genau der Ausloeser dieser Scheibe.
    """
    grundvorhersage = region_routing.direct_provider_for(
        _KARNISCH.latitude, _KARNISCH.longitude
    )
    gewitter = thunder_routing.thunder_provider_for(
        _KARNISCH.latitude, _KARNISCH.longitude
    )

    assert gewitter == "de_direct", (
        f"Gewitter-Zustaendigkeit ist {gewitter!r} statt 'de_direct' — der "
        "Karnische Hoehenweg bekommt weiterhin keine Gewitteraussage"
    )
    assert grundvorhersage != gewitter, (
        f"Beide Tabellen liefern {gewitter!r}. Dann beweist der Test nicht, "
        "dass die Gewitterquelle unabhaengig von der Grundvorhersage bestimmt "
        "wird"
    )


@pytest.mark.parametrize(
    "name,lat,lon,erwartet",
    [
        # Frankreich/Korsika bleibt bei Meteo-France: die FR-Zeile steht VOR
        # der neuen DE-Zeile, obwohl das ICON-D2-Rechteck halb Frankreich
        # mit abdeckt (gemessen: linke Gitterkante -3,95 O).
        ("Korsika", 42.22, 9.07, "fr_direct"),
        ("Paris", 48.85, 2.35, "fr_direct"),
        # Deutschland, Alpen, Oesterreich -> DWD.
        ("Berlin", 52.52, 13.405, "de_direct"),
        ("Wien", 48.21, 16.37, "de_direct"),
        ("Innsbruck", 47.27, 11.39, "de_direct"),
        # Ausserhalb des gemessenen ICON-D2-Gitters (43,17..58,09 N). Bis S2b
        # stand hier `None` ("kein Abruf, statt sinnloser Last"); seit #1457
        # S2c uebernimmt dort die Catch-all-Zeile `EU_REST` mit ICON-EU. Die
        # Aussage dieses Falls bleibt dieselbe — Rom faellt NICHT an den DWD —
        # nur die Alternative ist jetzt eine Quelle statt gar keiner.
        ("Rom", 41.9, 12.5, "eu_direct"),
    ],
)
def test_ac10_neue_zustaendigkeitszeile_haelt_die_gemessenen_gittergrenzen(
    name, lat, lon, erwartet
):
    """AC-10, Rangfolge und Grenzen: Given die gemessenen ICON-D2-Gittergrenzen
    (-3,95..20,35 O / 43,17..58,09 N), When die Gewitterquelle bestimmt wird,
    Then gewinnt fuer Frankreich weiterhin Meteo-France, fuer DE/Alpen/AT der
    DWD, und ausserhalb des Gitters wird gar nicht erst abgerufen.

    Die linke Gitterkante liegt bei -3,95 O — das ICON-D2-Rechteck ueberdeckt
    halb Frankreich. Stuende die neue Zeile VOR der FR-Zeile, verloere Korsika
    seine bereits produktive Blitzdichte.
    """
    assert thunder_routing.thunder_provider_for(lat, lon) == erwartet, (
        f"{name} ({lat}/{lon}) faellt an die falsche Gewitterquelle: "
        f"{thunder_routing.thunder_provider_for(lat, lon)!r} statt {erwartet!r}"
    )


# ---------------------------------------------------------------------------
# AC-1 — Wirkungs-Nachweis Ende-zu-Ende ueber den regulaeren Weg.
# ---------------------------------------------------------------------------

def test_ac1_regulaerer_weg_traegt_blitzpotenzial_und_hagel_an_den_datenpunkt(
    hauptquelle_laeuft, dwd_laeuft
):
    """AC-1: Given eine Position am Karnischen Hoehenweg und eine NORMAL
    verfuegbare Hauptquelle, When die Vorhersage ueber den regulaeren Weg
    (`OpenMeteoProvider.fetch_forecast`) geholt wird, Then traegt mindestens
    ein Zeitpunkt sowohl einen Blitzpotenzial- als auch einen Hagelwert aus
    dem DWD.

    Kein Ausfall, keine Sonderweiche — genau der Weg jedes echten Briefings.
    Heute bleibt dieselbe Abfrage fuer beide Felder durchgaengig leer.
    """
    reihe = om.OpenMeteoProvider().fetch_forecast(_KARNISCH, enrich_ensemble=False)

    assert reihe.data, "Vorhersage ist leer"
    assert reihe.meta.fallback_reason != "cross_provider_total_outage", (
        "Der Test hat versehentlich die Totalausfall-Weiche getroffen — dann "
        "beweist er nicht den regulaeren Weg (exakt die S2a-Luecke)"
    )
    assert dwd_laeuft, (
        "Der DWD wurde nie kontaktiert — die Gewitter-Zustaendigkeit fuer die "
        "Alpen greift nicht"
    )

    blitz = [dp.lightning_potential_lpi_jkg for dp in reihe.data]
    hagel = [dp.hail_potential_grau_gsp for dp in reihe.data]
    beides = [
        dp for dp in reihe.data
        if dp.lightning_potential_lpi_jkg is not None
        and dp.hail_potential_grau_gsp is not None
    ]
    assert beides, (
        f"Kein Zeitpunkt traegt BEIDE Werte. Blitzpotenzial: {blitz}, "
        f"Hagel: {hagel}"
    )
    assert any(v for v in blitz if v), (
        f"Alle Blitzpotenzial-Werte sind 0 oder leer ({blitz}) — die "
        "Aufzeichnung traegt an dieser Koordinate ein echtes Gewitter "
        "(lpi 48,16); der Wert kommt also nicht durch"
    )


def test_ac1_gegenprobe_blitzpotenzial_landet_nicht_im_blitzdichte_feld(
    hauptquelle_laeuft, dwd_laeuft
):
    """AC-1, Gegenprobe: Given denselben regulaeren Abruf, When der DWD die
    Signale liefert, Then bleibt das Meteo-France-Feld
    `lightning_density_per_km2_3h` LEER.

    Blitzdichte (Blitze je km^2 und 3 h, Messwerte 0,1-0,2) und
    Blitzpotenzial (energiebasiert, Messwerte bis 225) sind verschiedene
    Groessen auf verschiedenen Skalen. Landeten sie in einem Feld, meldete die
    Auswertung fuer die Alpen ein tausendfach zu hohes Gewitterrisiko.
    """
    reihe = om.OpenMeteoProvider().fetch_forecast(_KARNISCH, enrich_ensemble=False)

    assert dwd_laeuft, (
        "Der DWD wurde nie kontaktiert — dann waere dieser Test aus dem "
        "falschen Grund gruen (es kommt schlicht gar nichts an)"
    )
    fremd = [dp.lightning_density_per_km2_3h for dp in reihe.data
             if dp.lightning_density_per_km2_3h is not None]
    assert not fremd, (
        f"Der DWD hat das Blitzdichte-Feld von Meteo-France befuellt: {fremd}. "
        "Das sind unvergleichbare Skalen — jede Auswertung darauf ist falsch"
    )


# ---------------------------------------------------------------------------
# AC-3 — fail-soft am gemeinsamen Anschluss, jetzt auch fuer den neuen Zweig.
# ---------------------------------------------------------------------------

def test_ac3_werfende_benannte_quelle_kippt_die_vorhersage_nicht(
    hauptquelle_laeuft, monkeypatch
):
    """AC-3: Given eine Gewitterquelle, deren BENANNTER Abruf eine Ausnahme
    wirft, When eine Vorhersage ueber den regulaeren Weg geholt wird, Then
    kommt sie vollstaendig — mit Temperatur und Wind, nur ohne die beiden
    neuen Felder.

    Der bestehende Fail-Soft-Test (test_thunder_budget_and_failsoft.py, F004)
    deckt nur den ALTEN Zweig ab. Der neue Zweig braucht seinen eigenen
    Nachweis, sonst reisst eine kaputte DWD-Antwort die ganze Vorhersage mit.
    """
    class _WerfendeQuelle:
        @property
        def name(self) -> str:
            return "test_werfende_benannte_quelle"

        def fetch_thunder_signals(self, location, start=None, end=None):
            return {}

        def fetch_thunder_signals_named(self, location, start=None, end=None):
            raise RuntimeError("Gewitterquelle kaputt")

    monkeypatch.setattr(
        thunder_routing, "thunder_provider_for",
        lambda lat, lon: "test_werfende_benannte_quelle", raising=True,
    )

    with _registrierte_testquelle("test_werfende_benannte_quelle", _WerfendeQuelle):
        reihe = om.OpenMeteoProvider().fetch_forecast(_KARNISCH, enrich_ensemble=False)

    assert reihe.data, "Die Vorhersage ist leer — der Fehler hat sie mitgerissen"
    assert any(dp.t2m_c is not None for dp in reihe.data), (
        "Temperatur fehlt — die Grunddaten wurden vom Gewitter-Fehler beschaedigt"
    )
    assert all(dp.lightning_potential_lpi_jkg is None for dp in reihe.data), (
        "Es steht ein Blitzpotenzial da, obwohl die Quelle nur geworfen hat"
    )
    assert all(dp.hail_potential_grau_gsp is None for dp in reihe.data), (
        "Es steht ein Hagelwert da, obwohl die Quelle nur geworfen hat"
    )


# ---------------------------------------------------------------------------
# AC-9 — additive Protokoll-Erweiterung: eine dritte Quelle wirkt ohne
#        Aenderung am Kern-Dispatch.
# ---------------------------------------------------------------------------

def test_ac9_dritte_quelle_wirkt_allein_durch_eine_zeile_in_der_signal_tabelle(
    hauptquelle_laeuft, monkeypatch
):
    """AC-9: Given einen dritten, hypothetischen Dienst mit einem frei
    erfundenen Signalnamen, When er als Gewitter-Zustaendiger eingetragen und
    sein Signal um EINE Zeile in der Signal->Feld-Tabelle ergaenzt wird, Then
    erreicht sein Wert den Datenpunkt — ohne dass Fill-Waechter,
    Fehlerbehandlung oder Zeitbudget angefasst werden.

    Faellt dieser Test, bekommt jede neue Quelle ihren eigenen Sonderweg und
    die Wege driften auseinander (PO-Vorgabe "keine Einzelloesungen").
    """
    _SIGNAL = "erfundenes_gewittersignal_der_dritten_quelle"

    class _DritteQuelle:
        @property
        def name(self) -> str:
            return "test_dritte_quelle"

        def fetch_thunder_signals(self, location, start=None, end=None):
            return {}

        def fetch_thunder_signals_named(self, location, start=None, end=None):
            return {_SIGNAL: {h: 42.5 for h in range(1, 25)}}

    # NUR die Tabelle waechst — der Dispatch bleibt unberuehrt.
    erweitert = dict(thunder_enrichment._SIGNAL_ZU_FELD)
    erweitert[_SIGNAL] = "hail_potential_grau_gsp"
    monkeypatch.setattr(
        thunder_enrichment, "_SIGNAL_ZU_FELD", erweitert, raising=True
    )
    monkeypatch.setattr(
        thunder_routing, "thunder_provider_for",
        lambda lat, lon: "test_dritte_quelle", raising=True,
    )

    with _registrierte_testquelle("test_dritte_quelle", _DritteQuelle):
        reihe = om.OpenMeteoProvider().fetch_forecast(_KARNISCH, enrich_ensemble=False)

    assert any(dp.hail_potential_grau_gsp == 42.5 for dp in reihe.data), (
        "Die dritte Quelle wurde nicht wirksam, obwohl sie das Protokoll "
        "erfuellt und in der Tabelle steht. Werte am Datenpunkt: "
        f"{[dp.hail_potential_grau_gsp for dp in reihe.data]}"
    )


def test_ac9_der_kern_dispatch_kennt_keine_quelle_und_kein_einzelnes_signal():
    """AC-9, statische Haelfte: Der Kern-Dispatch (`enrich_thunder` selbst)
    darf weder einen Quellennamen noch einen einzelnen Signalnamen enthalten
    — beides gehoert in die Tabellen daneben.

    Geprueft wird bewusst der QUELLTEXT DER FUNKTION, nicht der des Moduls:
    die Signal->Feld-Tabelle im selben Modul MUSS 'lpi' enthalten, das ist
    genau ihr Zweck. Positivprobe gegen einen immer-gruenen Waechter: die
    gesuchten Begriffe muessen dort auffindbar sein, wo sie hingehoeren.
    """
    import inspect

    dispatch = inspect.getsource(thunder_enrichment.enrich_thunder)

    # Positivprobe: der Waechter KANN ueberhaupt etwas finden.
    tabelle = thunder_enrichment._SIGNAL_ZU_FELD
    assert "lpi" in tabelle, (
        "Positivprobe fehlgeschlagen — 'lpi' steht nicht einmal in der "
        "Signal->Feld-Tabelle. Der Waechter wuerde nichts pruefen"
    )
    assert "de_direct" in Path(dwd.__file__).read_text(encoding="utf-8"), (
        "Positivprobe fehlgeschlagen — 'de_direct' kommt nicht einmal im "
        "DWD-Provider vor"
    )

    verboten = ["de_direct", "DwdDirectProvider", "opendata.dwd.de",
                "fr_direct", "MeteoFranceDirect", "lpi", "grau_gsp"]
    treffer = [w for w in verboten if w in dispatch]
    assert not treffer, (
        f"Der Kern-Dispatch kennt {treffer} beim Namen — das ist ein "
        "Sonderweg. Eine neue Quelle muss allein ueber Zustaendigkeits- und "
        "Signal-Tabelle andocken"
    )
