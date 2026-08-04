"""TDD RED — Issue #1474 (S3 zu #1419), AC-9. Erweitert um Issue #1474c
(letzter Restpunkt zu Epic #1419), AC-4/AC-5/AC-6.

SPEC: docs/specs/modules/feat_1474_gewitter_befund_stufen.md v2.3 Abschnitt 3
SPEC (Erweiterung): docs/specs/modules/feat_1474c_blitzpotenzial_stufen.md

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

RED-Ursache (Erweiterung #1474c, AC-4/AC-5/AC-6): `_fuse_thunder_levels()`
reicht `dp.lightning_potential_lpi_jkg` noch NICHT an
`thunder_level_from_signals()` durch (S2b AC-8: "keine Stufenbildung in
dieser Scheibe" gilt noch) -- der Produktionspfad liefert deshalb weiterhin
NONE, obwohl das Blitzpotenzial belegt 48,15625 J/kg (>= MED-Schwelle 20)
traegt. Der Docstring von `enrich_thunder()` behauptet ebenfalls noch, dass
Blitzpotenzial "BEWUSST nicht in die Stufen-Fusion" eingeht.
"""
from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.config import Location  # noqa: E402
from app.models import ThunderLevel  # noqa: E402
from providers import dwd  # noqa: E402
from providers import meteofrance as mf  # noqa: E402
from providers import openmeteo as om  # noqa: E402

_FIXTURE_GRIB = (
    Path(__file__).resolve().parents[1] / "fixtures" / "meteofrance"
    / "arome_korsika_litota3_20260802.grib2"
)

_FIXTURE_DIR_DWD = Path(__file__).resolve().parents[1] / "fixtures" / "dwd"
_FIXTURE_LPI = _FIXTURE_DIR_DWD / "icon_d2_alpen_lpi_2026080315_024.grib2.bz2"
_FIXTURE_GRAU = _FIXTURE_DIR_DWD / "icon_d2_alpen_grau_gsp_2026080315_024.grib2.bz2"

_KORSIKA = Location(latitude=42.22, longitude=9.07, name="GR20 Petra Piana")

# Karnischer Hoehenweg -- ICON-D2-Zustaendigkeitsgebiet fuer Gewittersignale
# (`thunder_routing._REGIONS`, Zeile "DE_ALPEN" -> Provider "de_direct").
# Aufzeichnung traegt an dieser Koordinate lpi = 48,15625 J/kg (Zeitschritt
# +24h, s. `test_dwd_thunder_signal_fetch.py`).
_KARNISCH = Location(latitude=46.40, longitude=12.52, name="Karnischer Hoehenweg")


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


# =============================================================================
# Issue #1474c -- AC-4: Wirkungs-Nachweis ueber den Produktionspfad
# =============================================================================

@pytest.fixture
def dwd_icon_d2_laeuft(monkeypatch):
    """Lokaler Server unter `providers.dwd.BASE_URL`, liefert die ECHTE
    ICON-D2-Aufzeichnung fuer `lpi` bzw. `grau_gsp` aus -- unabhaengig vom
    angefragten Lauf/Zeitschritt (derselbe Wert an jeder Stunde reicht fuer
    den Wirkungsnachweis; die Feinheiten von Lauf-Rueckfall/Kumulation
    deckt bereits `test_dwd_thunder_signal_fetch.py` ab)."""
    lpi_bytes = _FIXTURE_LPI.read_bytes()
    grau_bytes = _FIXTURE_GRAU.read_bytes()

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = urlparse(self.path).path
            if "/lpi/" in path:
                body = lpi_bytes
            elif "/grau_gsp/" in path:
                body = grau_bytes
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, port = srv.server_address
    monkeypatch.setattr(dwd, "BASE_URL", f"http://{host}:{port}/", raising=True)
    yield srv
    srv.shutdown()


def test_ac4_dwd_blitzpotenzial_hebt_die_stufe_ueber_den_produktionspfad(
    hauptquelle_laeuft, dwd_icon_d2_laeuft
):
    """AC-4: Karnischer Hoehenweg (46,40 N / 12,52 O, `de_direct`-
    Zustaendigkeit fuer Gewittersignale) traegt in der Aufzeichnung ein
    Blitzpotenzial von 48,15625 J/kg -- oberhalb der MED-Schwelle (20 J/kg).
    Ueber den REGULAEREN Weg (`OpenMeteoProvider.fetch_forecast` ->
    `thunder_enrichment.enrich_thunder()`, KEIN isolierter Aufruf von
    `thunder_level_from_signals()`) muss mindestens ein Datenpunkt MED
    tragen -- wo derselbe Weg vor dieser Scheibe NONE lieferte (Wettercode 1,
    CAPE 0: kein anderes Signal kann hier MED erzeugen).

    Warum der Nachweis zwingend ueber `enrich_thunder()` laufen muss (Spec):
    ein Test, der `thunder_level_from_signals()` isoliert mit 48,15625
    fuettert, bliebe bei einer Verfaelschung von `_fuse_thunder_levels()`
    (viertes Argument entfernt) GRUEN -- die Aussparung sitzt im Aufrufer,
    nicht in der Fusion (ADR-0025 Entscheidung 5).
    """
    reihe = om.OpenMeteoProvider().fetch_forecast(_KARNISCH, enrich_ensemble=False)

    assert reihe.data, "Vorhersage ist leer"
    assert any(
        dp.lightning_potential_lpi_jkg is not None for dp in reihe.data
    ), (
        "Vorbedingung verletzt: kein Datenpunkt traegt ueberhaupt ein "
        "Blitzpotenzial -- dann kann AC-4 nichts pruefen"
    )
    treffer = [
        dp for dp in reihe.data
        if dp.lightning_potential_lpi_jkg is not None
        and dp.lightning_potential_lpi_jkg >= 20.0
    ]
    assert treffer, (
        "Kein Datenpunkt traegt ein Blitzpotenzial >= 20 J/kg, obwohl die "
        "Aufzeichnung 48,15625 liefert -- die Anreicherung kommt nicht an"
    )
    assert any(dp.thunder_level == ThunderLevel.MED for dp in treffer), (
        "Kein Datenpunkt mit Blitzpotenzial >= 20 J/kg traegt "
        "ThunderLevel.MED. Stufen: "
        f"{[(dp.lightning_potential_lpi_jkg, dp.thunder_level) for dp in treffer]}"
    )


# =============================================================================
# Issue #1474c -- AC-5: doc-compliance-test (Docstring folgt dem Verhalten)
# =============================================================================

def test_ac5_docstring_haelt_blitzpotenzial_nicht_mehr_fuer_ausgespart():
    """AC-5, doc-compliance-test: `enrich_thunder().__doc__` behauptet nach
    dieser Scheibe NICHT mehr, dass Blitzpotenzial ausserhalb der
    Stufen-Fusion bleibt (das Verhalten hat sich mit AC-4 geaendert) --
    Hagel bleibt weiterhin ausdruecklich als ausgespart benannt.

    # doc-compliance-test: dies prueft eine im Docstring GEMACHTE
    ZUSICHERUNG, weil AC-5 der Spec ausdruecklich eine Docstring-Korrektur
    verlangt -- kein Ersatz fuer einen Verhaltensnachweis (das ist AC-4
    oben, ueber den Produktionspfad).
    """
    from providers.thunder_enrichment import enrich_thunder

    doc = enrich_thunder.__doc__ or ""
    assert doc, "enrich_thunder() hat keinen Docstring -- AC-5 kann nichts pruefen"

    absaetze = [p for p in doc.split("\n\n") if p.strip()]

    veraltete_zusicherung = [
        p for p in absaetze
        if "Blitzpotenzial" in p and "nicht" in p and "Stufen-Fusion" in p
    ]
    assert not veraltete_zusicherung, (
        "Der Docstring behauptet in einem Absatz weiterhin, dass "
        "Blitzpotenzial NICHT in die Stufen-Fusion eingeht -- das "
        f"widerspricht dem Verhalten seit AC-4: {veraltete_zusicherung}"
    )

    ausschluss_marker = (
        "nicht", "außen vor", "aussen vor", "ausgespart", "draußen", "drauss",
    )
    hagel_ausschluss = [
        p for p in absaetze
        if ("Hagel" in p or "hail_potential_grau_gsp" in p)
        and any(marker in p for marker in ausschluss_marker)
    ]
    assert hagel_ausschluss, (
        "Kein Absatz haelt mehr fest, dass Hagel WEITERHIN von der "
        f"Stufen-Fusion ausgespart bleibt (S5/#1475). Docstring:\n{doc}"
    )


# =============================================================================
# Issue #1474c -- AC-6: Hagel bleibt draussen (Abgrenzung zu S5/#1475)
# =============================================================================

def test_ac6_hagel_liefert_keinen_eigenen_beitrag_zur_fusion():
    """AC-6: `hail_potential_grau_gsp` gesetzt, `lightning_potential_lpi_jkg`
    None -- liefert denselben `thunder_level` wie derselbe Fall OHNE
    gesetztes Hagelfeld. Hagel liefert weiterhin KEINEN eigenen Beitrag zur
    Stufe (das ist S5/#1475).

    Gegenprobe (Spec): fliesst `hail_potential_grau_gsp` versehentlich als
    fuenftes Signal in die Fusion ein, unterscheiden sich die beiden
    Ergebnisse (250 J/kg Hagel-Rohwert liegt weit ueber jede plausible
    LOW/MED/HIGH-Schwelle) -- dieser Test faengt das.
    """
    from app.models import ForecastDataPoint
    from providers.thunder_enrichment import _fuse_thunder_levels

    ts = datetime.now(timezone.utc)
    ohne_hagel = [ForecastDataPoint(
        ts=ts, thunder_level=ThunderLevel.LOW, hail_potential_grau_gsp=None,
        lightning_potential_lpi_jkg=None,
    )]
    mit_hagel = [ForecastDataPoint(
        ts=ts, thunder_level=ThunderLevel.LOW, hail_potential_grau_gsp=250.0,
        lightning_potential_lpi_jkg=None,
    )]

    _fuse_thunder_levels(ohne_hagel)
    _fuse_thunder_levels(mit_hagel)

    assert ohne_hagel[0].thunder_level == mit_hagel[0].thunder_level, (
        f"Gesetztes Hagelfeld veraendert thunder_level "
        f"({mit_hagel[0].thunder_level!r} statt "
        f"{ohne_hagel[0].thunder_level!r}) -- Hagel darf weiterhin keinen "
        "eigenen Beitrag zur Fusion liefern (AC-6, S5/#1475)"
    )


# =============================================================================
# Fix-Loop-Befund F001 (Adversary Runde 2, Mutation 5) -- AC-3 "None != NONE"
# am PRODUKTIONSPFAD `_fuse_thunder_levels()`, nicht nur am isolierten Aufruf
# von `thunder_level_from_signals()` (das deckt bereits
# `test_thunder_potential_level_classification.py:71` ab).
# =============================================================================

def test_f001_kein_signal_laesst_thunder_level_am_produktionspfad_unveraendert():
    """F001: `_fuse_thunder_levels()` darf `dp.thunder_level` NICHT antasten,
    wenn ALLE vier Signale (Wettercode, Blitzdichte, CAPE, Blitzpotenzial)
    `None` sind -- die Fusion liefert dann `None` ("keine Aussage"), und
    `_fuse_thunder_levels()` ueberschreibt laut eigenem Docstring nur, wenn
    sie NICHT `None` liefert (`thunder_enrichment.py:102`).

    Gegenprobe (Mutation 5, Adversary Runde 2): ersetzt der Aufrufer die
    Weitergabe von `dp.lightning_potential_lpi_jkg` durch einen naheliegenden
    `0.0`-Fail-soft-Default, wird aus "kein Signal" ein viertes Signal
    (`_thunder_level_from_ladder(0.0, ...)` -> `ThunderLevel.NONE`), die
    Fusion liefert dann `ThunderLevel.NONE` statt `None` und ueberschreibt
    `dp.thunder_level` -- dieser Test muss das fangen.
    """
    from app.models import ForecastDataPoint
    from providers.thunder_enrichment import _fuse_thunder_levels

    ts = datetime.now(timezone.utc)
    dp = ForecastDataPoint(
        ts=ts, thunder_level=None, lightning_density_per_km2_3h=None,
        cape_jkg=None, hail_potential_grau_gsp=None,
        lightning_potential_lpi_jkg=None,
    )

    _fuse_thunder_levels([dp])

    assert dp.thunder_level is None, (
        "dp.thunder_level wurde veraendert, obwohl ALLE vier Signale None "
        f"waren -- 'keine Aussage' darf nicht zu {dp.thunder_level!r} "
        "werden (F001)"
    )


def test_f001_blitzpotenzial_null_komma_null_setzt_stufe_none_am_produktionspfad():
    """F001 Gegenfall: `lightning_potential_lpi_jkg=0.0` (aktiv geprueft,
    unter der LOW-Schwelle 5.0) bei sonst None -- liefert am Produktionspfad
    `ThunderLevel.NONE` ('geprueft, unauffaellig'), NICHT unveraendert
    `None`. Zusammen mit dem Test oben belegt das den Unterschied 'keine
    Aussage' vs. 'geprueft, unauffaellig' genau an der Stelle, an der die
    Zusicherung WIRKT (`_fuse_thunder_levels()`), nicht nur am isolierten
    Aufruf von `thunder_level_from_signals()`.
    """
    from app.models import ForecastDataPoint
    from providers.thunder_enrichment import _fuse_thunder_levels

    ts = datetime.now(timezone.utc)
    dp = ForecastDataPoint(
        ts=ts, thunder_level=None, lightning_density_per_km2_3h=None,
        cape_jkg=None, hail_potential_grau_gsp=None,
        lightning_potential_lpi_jkg=0.0,
    )

    _fuse_thunder_levels([dp])

    assert dp.thunder_level == ThunderLevel.NONE, (
        f"dp.thunder_level ist {dp.thunder_level!r} statt ThunderLevel.NONE "
        "-- ein aktiv geprueftes, unauffaelliges Blitzpotenzial (0.0 J/kg) "
        "muss die Stufe NONE setzen, nicht unveraendert None lassen "
        "(F001 Gegenfall)"
    )
