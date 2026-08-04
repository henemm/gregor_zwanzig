"""Tests zu #1457 S2a fuer zwei Adversary-Befunde OHNE eigenen Test (F003, F004).

Spec: docs/specs/modules/feat_1457_s2a_blitzdichte_meteofrance.md (AC-3, AC-4)

Beide Befunde beschreiben Schutzcode, der zwar DA ist, aber von keinem Test
bewacht wird — er liesse sich entfernen, ohne dass etwas rot wird. Genau das
ist die Lage, aus der spaeter still ein Ausfall wird:

**F003** — Der Zeitdeckel je Einzelabruf im Sammelpfad
  (`meteofrance._request_once`, Parameter `timeout`) begrenzt einen Abruf auf
  die RESTZEIT des Anreicherungs-Budgets. Ohne ihn darf ein Abruf, der kurz vor
  der Zeitgrenze startet, noch die vollen `TIMEOUT`-Sekunden laufen und dehnt
  die 45s-Grenze faktisch auf ~75s. Die Zeitgrenze allein faengt das nicht:
  sie wird nur ZWISCHEN den Abrufen geprueft, nicht WAEHREND eines Abrufs.
  (Lehre #1448: eine Zeitgrenze, die den innersten Schritt nicht deckt, ist
  keine.)

**F004** — Die Fail-Soft-Klammer in `thunder_enrichment.enrich_thunder` wird auf
  dem regulaeren Weg nie mit einem echten Fehler durchlaufen, weil die untere
  Schicht (`MeteoFranceDirectProvider`) selbst schon alles abfaengt. Sie ist
  damit heute nur ZUFAELLIG wirksam. Ab S2b docken fremde Quellen ueber das
  Protokoll an, die diese Zusage nicht einhalten muessen — dann entscheidet
  allein diese Klammer darueber, ob eine kaputte Gewitterquelle die ganze
  Vorhersage mitreisst.

Testart: Kern-Schicht, echte lokale HTTP-Server, kein Netz.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.config import Location  # noqa: E402
from providers import meteofrance as mf  # noqa: E402
from providers import openmeteo as om  # noqa: E402

# Live-Schicht (Test-Politik, CLAUDE.md): braucht echtes Netz/echte Dienste --
# lief im Kern nie gruen (CI-Vermessung 2026-08-04, #1196) und gehoert per
# Marker in den /e2e-verify-Lauf, nicht auf eine Ausnahmeliste.
pytestmark = pytest.mark.live

_FIXTURE_GRIB = (
    Path(__file__).resolve().parents[1] / "fixtures" / "meteofrance"
    / "arome_korsika_litota3_20260802.grib2"
)

_KORSIKA = Location(latitude=42.22, longitude=9.07, name="GR20 Petra Piana")

# Der langsame Dienst braucht deutlich laenger als die Zeitgrenze — nur dann
# unterscheiden sich "mit Deckel" (Abbruch bei Restzeit) und "ohne Deckel"
# (Abbruch erst nach der vollen Antwort) messbar.
_ANTWORTZEIT_S = 1.0
_ZEITGRENZE_S = 0.3


def _om_antwort() -> dict:
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


@contextmanager
def _registered_test_thunder_provider(name: str, factory):
    """Registriert `factory` temporaer unter `name` in der echten Provider-
    Registry (`providers.base`) und stellt den Vorzustand danach wieder her —
    kein dauerhafter Seiteneffekt auf andere Tests. Laedt zuerst die echten
    Quellen nach, falls die Registry noch leer ist (Muster:
    test_meteofrance_direct_fallback.py:_registered_test_direct_provider)."""
    import providers.base as base_module

    if not base_module._PROVIDER_FACTORIES:
        base_module._load_providers()
    had_key = name in base_module._PROVIDER_FACTORIES
    previous = base_module._PROVIDER_FACTORIES.get(name)
    base_module.register_provider(name, factory)
    try:
        yield
    finally:
        if had_key:
            base_module._PROVIDER_FACTORIES[name] = previous
        else:
            base_module._PROVIDER_FACTORIES.pop(name, None)


@pytest.fixture
def hauptquelle_laeuft(monkeypatch):
    """Open-Meteo antwortet normal — der regulaere Weg, kein Totalausfall."""
    body = json.dumps(_om_antwort()).encode("utf-8")

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


def test_f003_einzelabruf_haelt_die_restzeit_ein_statt_das_volle_timeout(monkeypatch):
    """F003: Given ein Dienst, der laenger antwortet als die ganze Zeitgrenze,
    When die Blitzdichte geholt wird, Then endet der Aufruf nahe der Zeitgrenze
    — er wartet NICHT die volle Antwort ab.

    Der Nachweis haengt an der Laufzeit, nicht an der Abrufzahl: schon der
    ERSTE Abruf entscheidet. Mit Deckel bricht er nach der Restzeit ab
    (~0,3 s), ohne Deckel laeuft er bis zur Antwort (~1,0 s) und erst DANACH
    greift die Zeitgrenze. Wird `timeout=restzeit` aus dem Sammelpfad
    entfernt, muss dieser Test rot werden.
    """
    grib = _FIXTURE_GRIB.read_bytes()

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
        ergebnis = provider.fetch_thunder_signals_multi([_KORSIKA])
        dauer = time.monotonic() - beginn
    finally:
        srv.shutdown()

    obergrenze = (_ANTWORTZEIT_S + _ZEITGRENZE_S) / 2
    assert dauer < obergrenze, (
        f"Der Abruf lief {dauer:.2f}s bei einer Zeitgrenze von {_ZEITGRENZE_S}s — "
        f"er hat die volle Antwort ({_ANTWORTZEIT_S}s) abgewartet. Ohne Deckel je "
        "Einzelabruf dehnt ein spaet gestarteter Abruf die Zeitgrenze um das "
        "volle Abruf-Timeout"
    )
    werte = [v for v in (ergebnis.get(_KORSIKA.name) or {}).values() if v is not None]
    assert not werte, (
        "Es kamen Werte an, obwohl kein Abruf innerhalb der Zeitgrenze fertig "
        "werden konnte — der Test misst dann nicht, was er soll"
    )


@pytest.mark.parametrize("stelle", ["_thunder_offsets", "_thunder_gruppen"])
def test_f_adv2_fehler_in_der_vorbereitung_liefert_leeres_ergebnis_statt_ausnahme(
    monkeypatch, stelle
):
    """F-ADV2: Given ein Fehler bei der VORBEREITUNG des Sammelabrufs — also
    ausserhalb eines einzelnen HTTP-Abrufs, When die Blitzdichte geholt wird,
    Then kommt ein leeres Ergebnis zurueck und KEINE Ausnahme.

    Warum diese Klammer eigene Tests braucht: Der innere `try` deckt nur den
    Einzelabruf ab. Alles davor und danach — Modell-Lauf bestimmen, Stunden
    ableiten, Orte gruppieren, Rechteck bilden, Antwort auslesen — liegt allein
    unter der aeusseren Klammer. Faellt sie weg, reisst ein Fehler an einer
    dieser Stellen den ganzen Vorhersage-Abruf mit, obwohl die Blitzdichte nur
    eine Zusatzgroesse ist (Spec AC-3: fail-soft). Die Klammer war bis hierher
    von keinem Test bewacht; sie liess sich entfernen, ohne dass etwas rot wurde.

    Zwei Stellen, damit der Test die KLAMMER bewacht und nicht eine einzelne
    Hilfsfunktion.
    """
    # Keine echte Adresse: schlaegt der Schutz fehl und es kommt doch zu einem
    # Abruf, geht er ins Leere statt an die Live-API von Meteo-France.
    monkeypatch.setattr(mf, "BASE_URL", "http://127.0.0.1:1/")

    def _kaputt(*args, **kwargs):
        raise RuntimeError(f"{stelle} kaputt")

    monkeypatch.setattr(mf, stelle, _kaputt, raising=True)

    provider = mf.MeteoFranceDirectProvider()
    ergebnis = provider.fetch_thunder_signals_multi([_KORSIKA])

    assert ergebnis == {_KORSIKA.name: {}}, (
        f"Erwartet wurde ein leeres Ergebnis fuer '{_KORSIKA.name}', bekommen: "
        f"{ergebnis}. Der Aufrufer muss jeden Ort im Ergebnis wiederfinden, auch "
        "wenn nichts geholt werden konnte"
    )


def test_f004_werfende_gewitterquelle_kippt_die_vorhersage_nicht(
    hauptquelle_laeuft, monkeypatch
):
    """F004: Given eine Gewitterquelle, die eine Ausnahme WIRFT, When eine
    Vorhersage ueber den regulaeren Weg abgerufen wird, Then kommt sie
    vollstaendig — nur ohne Blitzdichte.

    Das Protokoll verlangt fail-soft von der Quelle, aber Zusagen sind kein
    Schutz: ab S2b docken fremde Quellen an. Dieser Test erzeugt den Fehler
    genau dort, wo die Fail-Soft-Klammer im Anreicherungsweg ihn abfangen
    muss. Wird sie entfernt, muss der Test rot werden — dann reisst eine
    kaputte Gewitterquelle die ganze Vorhersage mit.
    """
    from providers import thunder_routing

    class _WerfendeQuelle:
        """Erfuellt das Protokoll formal, haelt seine Zusage aber nicht ein."""

        @property
        def name(self) -> str:
            return "test_werfende_quelle"

        def fetch_thunder_signals(self, location, start=None, end=None):
            raise RuntimeError("Gewitterquelle kaputt")

        def fetch_thunder_signals_multi(self, locations, start=None, end=None):
            raise RuntimeError("Gewitterquelle kaputt")

    monkeypatch.setattr(
        thunder_routing, "thunder_provider_for",
        lambda lat, lon: "test_werfende_quelle", raising=True,
    )

    with _registered_test_thunder_provider("test_werfende_quelle", _WerfendeQuelle):
        reihe = om.OpenMeteoProvider().fetch_forecast(_KORSIKA, enrich_ensemble=False)

    assert reihe.data, (
        "Die Vorhersage ist leer — der Fehler der Gewitterquelle hat sie "
        "mitgerissen"
    )
    assert any(dp.t2m_c is not None for dp in reihe.data), (
        "Temperatur fehlt — die Grunddaten wurden vom Gewitter-Fehler beschaedigt"
    )
    assert all(dp.lightning_density_per_km2_3h is None for dp in reihe.data), (
        "Es steht eine Blitzdichte da, obwohl die Quelle nur geworfen hat"
    )
