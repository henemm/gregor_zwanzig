"""TDD RED — Issue #1474 (S3 zu #1419), AC-9.

SPEC: docs/specs/modules/feat_1474_gewitter_befund_stufen.md v2.3 Abschnitt 3

`thunder_enrichment.enrich_thunder()` -- "DER gemeinsame Anschluss" fuer
Trip UND Ortsvergleich (#1457 S2a AC-8/AC-9) -- ruft nach dem bestehenden
Fuellen von `dp.lightning_density_per_km2_3h` zusaetzlich
`thunder_level_from_signals(dp.thunder_level, dp.lightning_density_per_km2_3h,
dp.cape_jkg)` auf und ueberschreibt `dp.thunder_level` mit dem fusionierten
Ergebnis.

Testart wie #1457 S2a (`test_thunder_enrichment_shared_path.py`): Kern-Schicht,
kein Netz -- ein echter lokaler HTTP-Server liefert eine aufgezeichnete
Open-Meteo-Antwort (Wettercode 1 = kein Gewitter, CAPE 0), ein zweiter eine
ECHTE aufgezeichnete Meteo-France-AROME-GRIB2-Antwort ueber Korsika mit
belegter Blitzaktivitaet (dieselbe Fixture wie in AC-7/#1457 S2a, Spec-Beleg
"Spanne 0...6,19, 470 Punkte > 0").

RED-Ursache (heute): `enrich_thunder()` fuellt `lightning_density_per_km2_3h`,
ruft aber KEINE Fusion auf -- `dp.thunder_level` bleibt bei jedem Datenpunkt
`ThunderLevel.NONE` (aus dem Wettercode 1, "kein Gewitter"), obwohl die
Blitzdichte an vielen Punkten belegt Gewitteraktivitaet zeigt. Zusaetzlich
existiert `thunder_level_from_signals` noch nicht (ImportError, sobald der
Test importiert wird).
"""
from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.config import Location  # noqa: E402
from providers import meteofrance as mf  # noqa: E402
from providers import openmeteo as om  # noqa: E402

_FIXTURE_GRIB = (
    Path(__file__).resolve().parents[1] / "fixtures" / "meteofrance"
    / "arome_korsika_litota3_20260802.grib2"
)

_KORSIKA = Location(latitude=42.22, longitude=9.07, name="GR20 Petra Piana")


def _valide_openmeteo_antwort() -> dict:
    """Gueltige Open-Meteo-Antwort, Wettercode 1 (bewoelkt, KEIN Gewitter) und
    CAPE 0 an jedem Zeitpunkt -- ein etwaiger LOW/MED/HIGH-Befund kann also
    NUR aus der Blitzdichte-Fusion stammen, nicht aus Wettercode oder CAPE."""
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
            "temperature_2m": [15.0 for _ in range(n)],
            "wind_speed_10m": [5.0 for _ in range(n)],
            "wind_direction_10m": [180 for _ in range(n)],
            "wind_gusts_10m": [12.0 for _ in range(n)],
            "precipitation": [0.0 for _ in range(n)],
            "weather_code": [1 for _ in range(n)],
            "cape": [0.0 for _ in range(n)],
            "is_day": [1 for _ in range(n)],
        },
    }


@pytest.fixture
def hauptquelle_laeuft(monkeypatch):
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
    grib = _FIXTURE_GRIB.read_bytes()

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
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
    yield srv
    srv.shutdown()


def test_ac9_regulaerer_weg_traegt_die_fusionierte_stufe(
    hauptquelle_laeuft, meteofrance_laeuft
):
    """AC-9: Ueber den regulaeren Weg (OpenMeteoProvider.fetch_forecast ->
    thunder_enrichment.enrich_thunder()) traegt mindestens ein Datenpunkt eine
    ueber die Blitzdichte fusionierte Stufe -- NICHT mehr blind das
    Wettercode-Ergebnis (NONE), obwohl die Blitzdichte belegt Aktivitaet
    zeigt."""
    from output.metric_format import thunder_ordinal

    reihe = om.OpenMeteoProvider().fetch_forecast(_KORSIKA, enrich_ensemble=False)

    assert reihe.data, "Vorhersage ist leer"
    assert any(dp.lightning_density_per_km2_3h is not None for dp in reihe.data), (
        "Vorbedingung verletzt: kein Datenpunkt traegt ueberhaupt eine "
        "Blitzdichte -- dann kann die Fusion nichts pruefen"
    )
    hoechste = max(
        (thunder_ordinal(dp.thunder_level) for dp in reihe.data), default=0,
    )
    assert hoechste > thunder_ordinal(None), (
        "Kein Datenpunkt zeigt eine ueber NONE hinausgehende Gewitterstufe, "
        "obwohl die Blitzdichte belegt Aktivitaet zeigt -- die Fusion wird "
        "nicht aufgerufen. thunder_level bleibt blind auf dem "
        "Wettercode-Ergebnis stehen."
    )


def test_ac9_identisches_ergebnis_ueber_zwei_unabhaengige_aufrufe(
    hauptquelle_laeuft, meteofrance_laeuft
):
    """AC-9: zwei Aufrufe von fetch_forecast() fuer denselben Korsika-Ort aus
    unterschiedlichem Aufrufkontext (hier: zwei unabhaengige Provider-
    Instanzen, wie sie Trip- und Ortsvergleichs-Pfad je eigenstaendig
    erzeugen) liefern identisches, gefuelltes dp.thunder_level -- EIN
    gemeinsamer Anschluss, kein Sonderweg je Aufrufer."""
    from output.metric_format import thunder_ordinal

    reihe_a = om.OpenMeteoProvider().fetch_forecast(_KORSIKA, enrich_ensemble=False)
    reihe_b = om.OpenMeteoProvider().fetch_forecast(_KORSIKA, enrich_ensemble=False)

    levels_a = [dp.thunder_level for dp in reihe_a.data]
    levels_b = [dp.thunder_level for dp in reihe_b.data]
    assert levels_a == levels_b, (
        "Zwei unabhaengige Aufrufe fuer denselben Ort muessen identische "
        f"thunder_level-Reihen liefern. A={levels_a!r} B={levels_b!r}"
    )
    # Nicht nur "nicht None" (das waere schon ThunderLevel.NONE aus dem
    # Wettercode allein, ohne Fusion) -- mindestens EIN Datenpunkt muss ueber
    # NONE hinausgehen, sonst beweist der Vergleich nur, dass zwei leere
    # Ergebnisse gleich leer sind.
    assert max((thunder_ordinal(lvl) for lvl in levels_a), default=0) > 0, (
        "Beide Aufrufe liefern durchgehend NONE (Wettercode-Ergebnis ohne "
        "Fusion) -- der Vergleich beweist so nicht, dass die fusionierte "
        "Stufe konsistent ueber beide Aufrufe hinweg wirkt"
    )
