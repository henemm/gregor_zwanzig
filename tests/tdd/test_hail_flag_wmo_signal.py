"""TDD RED — Issue #1475 Scheibe S5a (Epic #1419): Hagel als eigenes,
rein deskriptives Kennzeichen (`Optional[bool]`), getrennt von `thunder_level`.

SPEC: docs/specs/modules/feat_1475_s5a_hagel_wmo_flag.md, AC-1 bis AC-3.

RED-Ursache (heute): `ForecastDataPoint` kennt kein Feld `hail_flag` — jede
Konstruktion mit `hail_flag=...` wirft `TypeError: unexpected keyword
argument`. `OpenMeteoProvider._parse_hail_flag()` existiert nicht
(`AttributeError`). `output.metric_format.format_hail_note()` existiert nicht
(`ImportError`).

Kern-Schicht, deterministisch: kein Netz (lokaler HTTP-Server liefert eine
aufgezeichnete Open-Meteo-Antwortform), keine Mocks/patch()/MagicMock.
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

from app.models import ForecastDataPoint, ThunderLevel  # noqa: E402
from providers import openmeteo as om  # noqa: E402
from app.config import Location  # noqa: E402

_ORT = Location(latitude=42.22, longitude=9.07, name="GR20 Petra Piana")

# Index der Stunde, die WMO 96 (Gewitter mit leichtem Hagel) traegt -- alle
# anderen Stunden bleiben Code 1 (bewoelkt, kein Gewitter), damit ein
# etwaiges `hail_flag=True` NUR von dieser einen Stunde stammen kann.
_HAGEL_STUNDE = 3


def _openmeteo_antwort_mit_hagelstunde() -> dict:
    base = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    n = 6
    times = [(base + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(n)]
    codes = [1 for _ in range(n)]
    codes[_HAGEL_STUNDE] = 96  # Gewitter mit leichtem Hagel (WMO)
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
            "weather_code": codes,
            "cape": [0.0 for _ in range(n)],
            "is_day": [1 for _ in range(n)],
        },
    }


@pytest.fixture
def openmeteo_liefert_hagelstunde(monkeypatch):
    body = json.dumps(_openmeteo_antwort_mit_hagelstunde()).encode("utf-8")

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


# =============================================================================
# AC-1 — Wirkungsnachweis Ende-zu-Ende: WMO 96/99 -> hail_flag=True -> Text
# =============================================================================

def test_ac1_regulaerer_fetch_pfad_traegt_hail_flag_true_fuer_wmo_96(
    openmeteo_liefert_hagelstunde,
):
    """AC-1: ueber den REGULAEREN Weg (`OpenMeteoProvider.fetch_forecast`,
    KEIN isolierter Aufruf von `_parse_hail_flag()`) traegt der Datenpunkt mit
    WMO-Code 96 `hail_flag=True` -- alle anderen Stunden (Code 1) bleiben
    `hail_flag=None` (Gegenprobe: nicht jede Stunde wird faelschlich `True`).
    """
    reihe = om.OpenMeteoProvider().fetch_forecast(_ORT, enrich_ensemble=False)

    assert reihe.data, "Vorhersage ist leer"
    hagel_punkte = [dp for dp in reihe.data if dp.wmo_code == 96]
    assert hagel_punkte, "Vorbedingung verletzt: keine Stunde traegt WMO 96"
    for dp in hagel_punkte:
        assert dp.hail_flag is True, (
            f"WMO 96 muss hail_flag=True ergeben, ueber den regulaeren "
            f"fetch_forecast()-Weg: bekam {dp.hail_flag!r}"
        )

    andere_punkte = [dp for dp in reihe.data if dp.wmo_code != 96]
    assert andere_punkte, "Vorbedingung verletzt: keine Vergleichsstunde vorhanden"
    for dp in andere_punkte:
        assert dp.hail_flag is None, (
            f"Nicht-Hagel-Code {dp.wmo_code!r} darf kein hail_flag=True "
            f"tragen (bekam {dp.hail_flag!r})"
        )


def test_ac1_gerenderter_text_zeigt_hagel_hinweis_fuer_true_stunde(
    openmeteo_liefert_hagelstunde,
):
    """AC-1 (Fortsetzung): der komplette Weg fetch_forecast -> Aggregation
    (`WeatherMetricsService.compute_basis_metrics`, Level-1) -> geteilter
    Renderer-Textbaustein (`output.metric_format.format_hail_note`, Spec
    Implementation Details Abschnitt 5) zeigt "Hagel: ja" -- NICHT nur ein
    isolierter Aufruf von `_parse_hail_flag()` (Lehre #1467 AG6: Faehigkeit
    != Wirkung).
    """
    from output.metric_format import format_hail_note
    from services.weather_metrics import WeatherMetricsService

    reihe = om.OpenMeteoProvider().fetch_forecast(_ORT, enrich_ensemble=False)
    summary = WeatherMetricsService().compute_basis_metrics(reihe)

    assert summary.hail_flag is True, (
        "Die Tagesaggregation traegt kein hail_flag=True, obwohl eine "
        f"Stunde WMO 96 lieferte: {summary.hail_flag!r}"
    )
    text = format_hail_note(summary.hail_flag)
    assert text == "Hagel: ja", (
        f"format_hail_note(True) muss den Renderer-Hinweistext liefern, "
        f"bekam {text!r}"
    )


# =============================================================================
# AC-2 — WMO 95 und alle anderen Codes -> unbekannt (None), NIE nein (False)
# =============================================================================

class TestAC2UnbekanntNichtNein:
    """AC-2: der WMO-Code kann Hagel nur BEJAHEN (96/99), nie VERNEINEN.
    Code 95 (Gewitter ohne Hagel-Zusatzcode), jeder Nicht-Gewitter-Code und
    ein fehlender Code muessen alle auf `None` ("unbekannt") laufen -- ein
    Test, der fuer Code 95 `False` erwartet, waere hier bewusst falsch (Spec
    Gegenprobe): der Code kann Hagel an dieser Stunde nicht ausschliessen,
    nur nicht bestaetigen.
    """

    def test_code_95_gewitter_ohne_hagelcode_ist_unbekannt(self):
        assert om.OpenMeteoProvider()._parse_hail_flag(95) is None

    def test_nicht_gewitter_code_ist_unbekannt(self):
        # Code 3 = "bewoelkt", kein Gewitter ueberhaupt.
        assert om.OpenMeteoProvider()._parse_hail_flag(3) is None

    def test_fehlender_code_ist_unbekannt(self):
        assert om.OpenMeteoProvider()._parse_hail_flag(None) is None

    def test_wmo_96_und_99_sind_ja(self):
        assert om.OpenMeteoProvider()._parse_hail_flag(96) is True
        assert om.OpenMeteoProvider()._parse_hail_flag(99) is True


# =============================================================================
# AC-3 — PFLICHT-Mutationsschutz: hail_flag beeinflusst thunder_level NICHT
# =============================================================================

def test_ac3_hail_flag_liefert_keinen_beitrag_zur_thunder_stufen_fusion():
    """AC-3 (PO-Vorgabe 2026-08-03, Mutationsschutz): Zwei Datenpunkte mit
    identischer Signalkombination (Wettercode-Stufe LOW, keine anderen
    Signale) unterscheiden sich NUR in `hail_flag` (`None` vs. `True`) --
    `_fuse_thunder_levels()` (der Produktionspfad der Stufen-Fusion, s.
    `test_thunder_enrichment_fuses_level_shared_path.py::test_ac6_...` fuer
    das analoge Muster mit `hail_potential_grau_gsp`) muss BEIDE auf
    identisches `thunder_level` abbilden.

    Gegenprobe (expliziter Adversary-Mutationskandidat, Spec AC-3): wird
    `hail_flag` versehentlich als fuenftes Signal in
    `thunder_level_from_signals()` eingespeist, eskaliert die True-Variante
    (sofern die Mutation ein hohes Ersatz-Level fuer `True` waehlt) und
    dieser Test wird rot.
    """
    from providers.thunder_enrichment import _fuse_thunder_levels

    ts = datetime.now(timezone.utc)
    ohne_hagel = [ForecastDataPoint(
        ts=ts, thunder_level=ThunderLevel.LOW, hail_flag=None,
    )]
    mit_hagel = [ForecastDataPoint(
        ts=ts, thunder_level=ThunderLevel.LOW, hail_flag=True,
    )]

    _fuse_thunder_levels(ohne_hagel)
    _fuse_thunder_levels(mit_hagel)

    assert ohne_hagel[0].thunder_level == mit_hagel[0].thunder_level, (
        f"Gesetztes hail_flag veraendert thunder_level "
        f"({mit_hagel[0].thunder_level!r} statt "
        f"{ohne_hagel[0].thunder_level!r}) -- Hagel darf KEINEN eigenen "
        "Beitrag zur Gewitterstufen-Fusion liefern (AC-3, S5a/#1475)"
    )
