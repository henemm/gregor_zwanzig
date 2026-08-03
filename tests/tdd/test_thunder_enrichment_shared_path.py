"""RED-Tests zu #1457 S2a, AC-7 und AC-8 — der GEMEINSAME Gewitter-Anreicherungsweg.

Spec: docs/specs/modules/feat_1457_s2a_blitzdichte_meteofrance.md
Konzept: Issue #1419 Abschnitt 5.

Warum es diese Tests braucht — beide decken Luecken auf, die AC-1..AC-6 offen liessen:

AC-7: Die sechs urspruenglichen ACs pruefen nur den Meteo-France-Provider SELBST.
  Alle waren gruen, der Adversary hatte VERIFIED erteilt — und die Blitzdichte
  erreichte trotzdem nie einen Nutzer, weil
  `MeteoFranceDirectProvider.fetch_forecast` im Produktivcode nur unter
  `if response_data is None:` aufgerufen wird (openmeteo.py:1006), also
  ausschliesslich beim Totalausfall von Open-Meteo.

AC-8 (PO-Vorgabe "keine Einzelloesungen"): Der Anreicherungsweg darf KEINEN
  Providernamen und KEINE Coverage-ID kennen. Sonst entsteht fuer jedes Gebiet
  ein eigener Sonderweg (MF fuer Korsika, DWD fuer die Alpen, ICON-EU fuer den
  Rest), und die driften auseinander.

Testart: Kern-Schicht. Kein Netz — echte lokale HTTP-Server liefern eine
aufgezeichnete Open-Meteo-Antwort bzw. eine aufgezeichnete AROME-GRIB2-Antwort.
Muster: test_issue_1115_model_fallback.py (Open-Meteo) und
test_thunder_signal_enrichment.py (Meteo-France).
"""
from __future__ import annotations

import json
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.config import Location  # noqa: E402
from providers import meteofrance as mf  # noqa: E402
from providers import openmeteo as om  # noqa: E402

# Aufzeichnung ueber GANZ Korsika (41,30-43,11 N / 8,39-9,60 O) — der Ort unten
# liegt DARIN. Zuvor stand hier die Paris-Aufzeichnung (2,30-2,41 O), die ihn
# nicht abdeckt; gruen war das nur durch das Klemmen auf den Randbildpunkt
# (Adversary-Befund F001). Mit AC-11 (verwerfen statt klemmen) muss die
# Aufzeichnung den geprueften Ort wirklich enthalten.
_FIXTURE_GRIB = (
    Path(__file__).resolve().parents[1] / "fixtures" / "meteofrance"
    / "arome_korsika_litota3_20260802.grib2"
)

_KORSIKA = Location(latitude=42.22, longitude=9.07, name="GR20 Petra Piana")
# Karnischer Hoehenweg — PO-Reiseziel; heute NICHT von Meteo-France gedeckt,
# dient hier als Testgebiet fuer den zweiten Provider (AC-8).
_KARNISCHER = Location(latitude=46.65, longitude=12.60, name="Porzehuette")


def _valide_openmeteo_antwort() -> dict:
    """Gueltige Open-Meteo-Antwort — die Hauptquelle funktioniert, KEIN Ausfall.
    Format wie `_parse_response` es erwartet (Muster test_issue_1115)."""
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
            "temperature_2m": [15.0 + i * 0.5 for i in range(n)],
            "wind_speed_10m": [5.0 for _ in range(n)],
            "wind_direction_10m": [180 for _ in range(n)],
            "wind_gusts_10m": [12.0 for _ in range(n)],
            "precipitation": [0.0 for _ in range(n)],
            "weather_code": [1 for _ in range(n)],
            "cape": [0.0 for _ in range(n)],
            "is_day": [1 for _ in range(n)],
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
    """Open-Meteo antwortet normal — die Totalausfall-Weiche wird NICHT erreicht."""
    body = json.dumps(_valide_openmeteo_antwort()).encode("utf-8")

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, port = srv.server_address
    monkeypatch.setattr(om, "BASE_HOST", f"http://{host}:{port}", raising=True)
    monkeypatch.setattr(om, "ENSEMBLE_BASE_HOST", f"http://{host}:{port}", raising=True)
    yield srv
    srv.shutdown()


@pytest.fixture
def meteofrance_laeuft(monkeypatch):
    """Meteo-France liefert die aufgezeichnete GRIB2-Antwort."""
    grib = _FIXTURE_GRIB.read_bytes()
    abrufe: list[str] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = parse_qs(urlparse(self.path).query)
            abrufe.append((q.get("coverageId") or [""])[0])
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


def test_ac7_regulaerer_weg_liefert_blitzdichte_ohne_ausfall(
    hauptquelle_laeuft, meteofrance_laeuft
):
    """AC-7: Given ein Korsika-Ort und eine NORMAL VERFUEGBARE Hauptquelle,
    When die Vorhersage ueber den regulaeren Weg abgerufen wird,
    Then traegt der Datenpunkt eine Blitzdichte.

    Das ist der Test, der heute gefehlt hat: Er laeuft ueber
    `OpenMeteoProvider.fetch_forecast` bei FUNKTIONIERENDER Hauptquelle — also
    genau den Weg, den jeder echte Briefing-Lauf nimmt.
    """
    reihe = om.OpenMeteoProvider().fetch_forecast(_KORSIKA, enrich_ensemble=False)

    assert reihe.data, "Vorhersage ist leer"
    assert reihe.meta.fallback_reason != "cross_provider_total_outage", (
        "Der Test hat versehentlich die Totalausfall-Weiche getroffen — dann "
        "beweist er nicht den regulaeren Weg"
    )
    assert any(dp.lightning_density_per_km2_3h is not None for dp in reihe.data), (
        "Kein Datenpunkt traegt eine Blitzdichte. Die Anreicherung haengt nur in "
        "der Totalausfall-Weiche und erreicht im Normalbetrieb niemanden"
    )


def test_ac8_zweite_quelle_wirkt_ohne_aenderung_am_anschluss(
    hauptquelle_laeuft, monkeypatch
):
    """AC-8: Given ein zweiter Dienst, der das gemeinsame Protokoll erfuellt,
    When er als Gewitter-Zustaendiger fuer sein Gebiet eingetragen wird,
    Then wirkt er — OHNE dass der Anreicherungsweg angefasst wird.

    Der Doppelgaenger steht hier fuer den DWD (S2b). Faellt dieser Test, gibt es
    fuer jedes Gebiet einen eigenen Sonderweg statt eines gemeinsamen.
    """
    from providers import thunder_routing  # existiert noch nicht -> RED

    class _ZweiteQuelle:
        """Erfuellt nur das Protokoll — kennt weder Meteo-France noch Open-Meteo."""

        @property
        def name(self) -> str:
            return "test_zweite_quelle"

        def fetch_thunder_signals(self, location, start=None, end=None):
            return {h: 7.5 for h in range(1, 25)}

    monkeypatch.setattr(
        thunder_routing, "thunder_provider_for",
        lambda lat, lon: "test_zweite_quelle", raising=True,
    )

    with _registered_test_thunder_provider("test_zweite_quelle", _ZweiteQuelle):
        reihe = om.OpenMeteoProvider().fetch_forecast(_KARNISCHER, enrich_ensemble=False)

    assert any(dp.lightning_density_per_km2_3h == 7.5 for dp in reihe.data), (
        "Die zweite Quelle wurde nicht wirksam. Der Anreicherungsweg muss jede "
        "Quelle ueber das gemeinsame Protokoll bedienen, nicht nur Meteo-France"
    )


@pytest.mark.parametrize("protokoll", ["einzeln", "sammel"])
def test_ac2_leere_stunde_bleibt_am_anschlussweg_leer_und_wird_nie_null(
    hauptquelle_laeuft, monkeypatch, protokoll
):
    """AC-2 am GEMEINSAMEN Anreicherungsweg: Given eine Gewitterquelle, die fuer
    einen Teil der Stunden KEINEN Wert liefert, When die Vorhersage ueber den
    regulaeren Weg abgerufen wird, Then bleiben genau diese Stunden leer — sie
    werden NIE 0.

    Warum dieser Test zusaetzlich zu `test_ac2_...` in
    test_thunder_signal_enrichment.py noetig ist (Adversary-Befund F-ADV1):
    Jener prueft die Zusage am Meteo-France-Provider. Der Weg, auf dem die
    Werte den Nutzer erreichen (AC-7), fuellt die Datenpunkte aber selbst —
    in `thunder_enrichment.enrich_thunder`. Wird dort aus einem fehlenden Wert
    eine 0, meldet die Vorhersage „kein Gewitter" statt „keine Aussage", und
    keiner der 18 bestehenden Tests wird rot. Genau das ist eine falsche
    Entwarnung fuer den Nutzer.

    Beide Spielarten des Protokolls werden geprueft (einzeln/Sammelabruf), weil
    der Anschlussweg beide bedient und sie in dieselbe Fuell-Schleife muenden.
    """
    from providers import thunder_routing

    # Drei Stunden mit Wert, drei ohne — die Quelle sagt fuer sie ausdruecklich
    # „keine Aussage" (None), nicht „keine Gefahr" (0).
    _SIGNALE = {1: 4.2, 2: None, 3: 5.5, 4: None, 5: None, 6: 1.0}
    _MIT_WERT = {4.2, 5.5, 1.0}

    class _LueckenhafteQuelle:
        """Erfuellt das Protokoll, hat aber fuer die Haelfte der Stunden nichts."""

        @property
        def name(self) -> str:
            return "test_lueckenhafte_quelle"

        def fetch_thunder_signals(self, location, start=None, end=None):
            return dict(_SIGNALE)

    class _LueckenhafteSammelQuelle(_LueckenhafteQuelle):
        def fetch_thunder_signals_multi(self, locations, start=None, end=None):
            return {"irgendein_schluessel": dict(_SIGNALE)}

    monkeypatch.setattr(
        thunder_routing, "thunder_provider_for",
        lambda lat, lon: "test_lueckenhafte_quelle", raising=True,
    )

    with _registered_test_thunder_provider(
        "test_lueckenhafte_quelle",
        _LueckenhafteQuelle if protokoll == "einzeln" else _LueckenhafteSammelQuelle,
    ):
        reihe = om.OpenMeteoProvider().fetch_forecast(_KORSIKA, enrich_ensemble=False)

    werte = [dp.lightning_density_per_km2_3h for dp in reihe.data]
    gefuellt = [v for v in werte if v is not None]

    assert gefuellt, (
        "Kein einziger Datenpunkt traegt eine Blitzdichte — die Fuell-Schleife "
        "wurde gar nicht durchlaufen, der Test wuerde nichts pruefen"
    )
    assert 0.0 not in gefuellt, (
        f"Ein Datenpunkt traegt 0 (alle Werte: {werte}). Die Quelle hat fuer "
        "diese Stunde ausdruecklich KEINEN Wert geliefert; 0 bedeutet aber "
        "'kein Gewitter' und ist eine falsche Entwarnung"
    )
    assert set(gefuellt) <= _MIT_WERT, (
        f"Es stehen Werte da, die die Quelle nie geliefert hat: {gefuellt}"
    )
    assert len(gefuellt) == len(_MIT_WERT), (
        f"{len(gefuellt)} Datenpunkte tragen einen Wert, geliefert wurden aber "
        f"nur {len(_MIT_WERT)}. Die leeren Stunden wurden aufgefuellt statt leer "
        "gelassen"
    )


def test_ac8_anschlussweg_kennt_keinen_providernamen():
    """AC-8, statische Haelfte: Der gemeinsame Anreicherungsweg darf KEINEN
    Providernamen und KEINE Coverage-ID enthalten.

    Gegenprobe gegen einen immer-gruenen Waechter: Der Test weist zuerst nach,
    dass er die gesuchten Begriffe ueberhaupt finden KANN (Positivprobe an einer
    Stelle, wo sie legitim stehen) — sonst waere ein Regex, der nichts findet,
    dauerhaft gruen und wertlos.
    """
    from providers import thunder_enrichment  # existiert noch nicht -> RED

    quelle = Path(thunder_enrichment.__file__).read_text(encoding="utf-8")

    # Positivprobe: im Provider-Modul MUESSEN diese Begriffe vorkommen. Aus der
    # Konstante gelesen (nicht hart hineingeschrieben) — #1457 S2a Fix hat den
    # Namen bereits einmal geaendert (LITOTA3 -> ausgeschriebene Form), ein
    # zweiter fest eingetragener Vergleichsstring wuerde die naechste
    # Umbenennung erneut verpassen.
    mf_quelle = Path(mf.__file__).read_text(encoding="utf-8")
    assert mf.LIGHTNING_COVERAGE in mf_quelle, (
        "Positivprobe fehlgeschlagen — der Suchbegriff kommt nicht einmal dort "
        "vor, wo er hingehoert. Der Waechter wuerde nichts pruefen"
    )

    verboten = [
        mf.LIGHTNING_COVERAGE, "fr_direct", "MeteoFranceDirect",
        "de_direct", "lpi_con_max",
    ]
    treffer = [w for w in verboten if w in quelle]
    assert not treffer, (
        f"Der gemeinsame Anreicherungsweg kennt {treffer} — das ist ein "
        "Provider-Sonderweg. Jede Quelle muss ueber Zustaendigkeitstabelle und "
        "Protokoll andocken, nicht ueber einen Namen im Anschlusscode"
    )
