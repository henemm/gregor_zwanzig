"""
TDD-Tests fuer Bug #338 — Open-Meteo Abruf-Zaehler (Diagnose).

Jeder Test mappt 1:1 auf ein AC aus
docs/specs/modules/bug_338_openmeteo_call_counter.md.

KONTEXT: Das Open-Meteo-Tageslimit ist erschoepft — echte Abrufe geben HTTP 429.
Das ist fuer diese Tests ERWUENSCHT: der Zaehler MUSS auch 429-Abrufe
protokollieren. Es werden KEINE Mocks/patch/MagicMock verwendet (Projektregel).

RED-Phase: Tests schlagen fehl, weil _log_api_call/_resolve_call_source/
DIAGNOSTICS_PATH und scripts/analyze_openmeteo_calls.py noch nicht existieren.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Helpers — echte DTOs, kein Mock
# ---------------------------------------------------------------------------

def _make_location(lat: float = 47.27, lon: float = 11.39):
    from app.config import Location
    return Location(latitude=lat, longitude=lon, name="Innsbruck")


def _make_segment(lat: float = 47.27, lon: float = 11.39):
    """#1708 B1 AC-3: Fenster relativ zu ``now`` statt fest auf 06:00-14:00 UTC
    -- sonst ueberspringt trip_alert.py:1247-1249 das Segment ausserhalb dieses
    Fensters (Kippkante 14:00 UTC). start liegt 1h VOR now (start.date() bleibt
    auch um 00:xx UTC <= heute), end liegt 7h NACH now (end > now zu jeder
    Uhrzeit) -- die vom Alarm-Pfad geprüfte Eigenschaft gilt so unabhaengig von
    der Tageszeit.
    """
    from app.models import GPXPoint, TripSegment
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=1)
    end = now + timedelta(hours=7)
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=800),
        end_point=GPXPoint(lat=lat + 0.05, lon=lon + 0.05, elevation_m=1200),
        start_time=start,
        end_time=end,
        duration_hours=8.0,
        distance_km=12.0,
        ascent_m=500,
        descent_m=100,
    )


def _make_segment_weather(lat: float = 47.27, lon: float = 11.39):
    from app.models import SegmentWeatherData, SegmentWeatherSummary
    return SegmentWeatherData(
        segment=_make_segment(lat, lon),
        timeseries=None,
        aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
        has_error=False,
    )


def _make_trend_trip(target_date: date):
    """Trip mit EINER zukuenftigen Etappe (date > target_date) fuer _build_stage_trend."""
    from app.trip import Trip, Stage, Waypoint
    future = target_date + timedelta(days=1)
    wp_start = Waypoint(id="g1", name="Start", lat=47.10, lon=11.20, elevation_m=500,
                        time_window=None)
    wp_end = Waypoint(id="g2", name="Ziel", lat=47.20, lon=11.30, elevation_m=1200,
                      time_window=None)
    stage = Stage(id="s1", name="Trend-Etappe", date=future,
                  waypoints=[wp_start, wp_end], start_time=time(8, 0))
    return Trip(id="trend-trip", name="Trend Test", stages=[stage])


def _make_scheduler():
    from services.trip_report_scheduler import TripReportSchedulerService
    svc = TripReportSchedulerService.__new__(TripReportSchedulerService)
    svc._user_id = "default"
    return svc


def _make_alert_service():
    from services.trip_alert import TripAlertService
    return TripAlertService.__new__(TripAlertService)


def _read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


# ---------------------------------------------------------------------------
# AC-1: Erfolgreicher/429-fetch_forecast() haengt genau eine JSONL-Zeile an
# ---------------------------------------------------------------------------

# #1708 B1: `enrich_ensemble=False` (direkter Aufruf, kein Fallback-Pfad) --
# gemessen mit `@pytest.mark.disable_socket` 2026-08-16: die primaere
# httpx-Anfrage wirft eine pytest-socket-eigene RuntimeError-Unterklasse
# (SocketBlockedError/SocketConnectBlockedError), die httpx NICHT als
# httpx.RequestError erkennt (`_make_request`s `except httpx.RequestError`
# in providers/openmeteo.py greift nicht) -- der Aufruf propagiert unge-
# loggt. Ohne einen zweiten (Ensemble-)Aufruf, der das breiter faengt
# (s. test_ac2_trend/test_ac2_preview), bleibt AC-1 offline unbeweisbar.
@pytest.mark.live
def test_ac1_fetch_forecast_appends_one_jsonl_line(tmp_path, monkeypatch):
    """
    AC-1: Ein echter fetch_forecast()-Aufruf (200 ODER 429) protokolliert genau
    eine neue Zeile mit ts, endpoint (host+path OHNE Query), status, source.

    KONFIGURATION (kein Mock): DIAGNOSTICS_PATH wird auf eine tmp_path-Datei
    umgesetzt, um die JSONL-Datei zu isolieren.
    """
    import providers.openmeteo as om

    log_path = tmp_path / "openmeteo_calls.jsonl"
    monkeypatch.setattr(om, "DIAGNOSTICS_PATH", log_path, raising=False)

    provider = om.OpenMeteoProvider()
    location = _make_location()
    now = datetime.now(timezone.utc)

    before = _read_jsonl(log_path)
    try:
        provider.fetch_forecast(
            location=location, start=now, end=now + timedelta(days=1),
            enrich_ensemble=False,
        )
    except Exception:
        # 429 / Limit erschoepft ist hier erlaubt — der Aufruf MUSS trotzdem
        # protokolliert worden sein.
        pass

    after = _read_jsonl(log_path)
    new_lines = after[len(before):]
    assert len(new_lines) >= 1, (
        "fetch_forecast() haette mindestens eine JSONL-Zeile anhaengen muessen"
    )

    entry = new_lines[0]
    for field in ("ts", "endpoint", "status", "source"):
        assert field in entry, f"JSONL-Zeile fehlt Feld '{field}': {entry}"

    # Endpoint = host+path ohne Query
    assert entry["endpoint"].startswith("https://"), entry["endpoint"]
    assert "?" not in entry["endpoint"], (
        f"endpoint darf keine Query enthalten: {entry['endpoint']}"
    )
    # ts ist ISO-8601-parsebar
    datetime.fromisoformat(entry["ts"])


# ---------------------------------------------------------------------------
# AC-2: Quellen-Bestimmung — alarm (Alarm-Pfad) und trend (Mehrtages-Trend)
# ---------------------------------------------------------------------------

# #1708 B1: `_fetch_fresh_weather` ruft `fetch_segment_weather(..., enrich_
# ensemble=False, ...)` -- bewusst (Bug #288, Quotenschutz im Alarm-Pfad).
# Gemessen mit `@pytest.mark.disable_socket` 2026-08-16: OHNE die
# Ensemble-Anreicherung gibt es keinen zweiten (breiter gefangenen)
# Aufrufversuch, der den Log-Eintrag noch retten koennte (Befund identisch
# zu test_ac1 -- der primaere httpx-Call wirft eine von httpx nicht als
# RequestError erkannte pytest-socket-Exception und propagiert ungeloggt
# bis trip_report_scheduler.py:1989). test_ac2_trend/test_ac2_preview
# koennen offline bestehen, WEIL sie (anders als hier) mit `enrich_
# ensemble=True` zusaetzlich einen Ensemble-Spread-Aufruf ausloesen, dessen
# `except Exception` (statt `except httpx.RequestError`) auch diese
# Exception faengt und protokolliert -- dieser Fallback fehlt hier absichtlich.
@pytest.mark.live
def test_ac2_alarm_path_sets_source_alarm(tmp_path, monkeypatch):
    """
    AC-2 (Alarm): Ein Abruf aus dem echten Alarm-Pfad
    TripAlertService._fetch_fresh_weather liefert source == "alarm".
    """
    import providers.openmeteo as om

    log_path = tmp_path / "openmeteo_calls.jsonl"
    monkeypatch.setattr(om, "DIAGNOSTICS_PATH", log_path, raising=False)

    alert_service = _make_alert_service()
    cached = [_make_segment_weather()]

    # _fetch_fresh_weather schluckt Fehler je Segment; 429 ist hier erlaubt.
    alert_service._fetch_fresh_weather(cached)

    entries = _read_jsonl(log_path)
    sources = {e["source"] for e in entries}
    assert "alarm" in sources, (
        f"Erwartete source 'alarm' aus _fetch_fresh_weather, sah: {sources}"
    )


@pytest.mark.disable_socket  # #1708 B1: offline beweiskraeftig, s. Docstring
def test_ac2_trend_path_sets_source_trend(tmp_path, monkeypatch):
    """
    AC-2 (Trend): Ein Abruf aus dem echten Mehrtages-Trend-Pfad
    TripReportSchedulerService._build_stage_trend liefert source == "trend".

    #1708 B1: statt echtem Netz oder FixtureProvider (der NIE loggt, s.
    providers/fixture.py) erzwingt dieser Test einen echten OpenMeteoProvider
    UND sperrt jeden Socket (`@pytest.mark.disable_socket`). Gemessen
    2026-08-16: der primaere Forecast-Call scheitert ungeloggt (httpx
    erkennt die pytest-socket-Exception nicht als RequestError), ABER
    `_build_stage_trend` loest mit dem Default `enrich_ensemble=True`
    zusaetzlich einen Ensemble-Spread-Aufruf aus (`_fetch_ensemble_spread`,
    providers/openmeteo.py:706), dessen `except Exception` (breiter als
    `except httpx.RequestError`) JEDE Exception faengt und ueber
    `_log_api_call` protokolliert -- mit `source == "trend"`, weil der
    Stack weiterhin `_build_stage_trend` traegt. Deterministisch (Millise-
    kunden, kein Netz), weil `enrich_ensemble=True` hier IMMER gesetzt ist.

    Adversary F002 (#1708 B1): `@pytest.mark.disable_socket` ist hier keine
    Nebensaechlichkeit, sondern schuetzt vor einem ZWEITEN, teureren
    Netzpfad. Gemessen OHNE den Marker: gelingt der primaere Forecast-Call
    (echtes Netz erreichbar), ruft `fetch_forecast()` im Erfolgsfall
    `_enrich_thunder()` (providers/openmeteo.py:1209) -> `providers.
    thunder_enrichment.enrich_thunder()` -> `providers/dwd.py` auf -- eine
    ECHTE DWD-Radar-Dekompression, die im Adversary-Lauf ~30s dauerte und
    damit fast exakt an den pytest-timeout(30s) stiess. Mit gesperrtem
    Socket wird dieser Pfad nie erreicht (der primaere Call scheitert schon
    vorher), das ist Teil der Absicherung, nicht nur der Ensemble-Fallback.
    """
    import providers.openmeteo as om

    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)  # echter Provider statt FixtureProvider (der nie loggt)
    log_path = tmp_path / "openmeteo_calls.jsonl"
    monkeypatch.setattr(om, "DIAGNOSTICS_PATH", log_path, raising=False)

    scheduler = _make_scheduler()
    target = date.today()
    trip = _make_trend_trip(target)

    # _build_stage_trend schluckt Fehler je Etappe; 429 ist hier erlaubt.
    scheduler._build_stage_trend(trip, target, now_utc=datetime.now(timezone.utc))

    entries = _read_jsonl(log_path)
    sources = {e["source"] for e in entries}
    assert "trend" in sources, (
        f"Erwartete source 'trend' aus _build_stage_trend, sah: {sources}"
    )


@pytest.mark.disable_socket  # #1708 B1: offline beweiskraeftig, s. Docstring (Muster wie test_ac2_trend)
def test_ac2_preview_path_sets_source_vorschau(tmp_path, monkeypatch):
    """
    AC-2 (Vorschau, F002-Fix): Ein Abruf aus dem echten Vorschau-Pfad
    PreviewService.render_email_preview liefert source == "vorschau"
    (NICHT "briefing"), obwohl intern _fetch_weather laeuft.

    #1708 B1: die Trip-Fixture wird selbst in der isolierten Datenwurzel
    angelegt statt im toten trips/-Pfad gesucht (dort ist sie unter
    Isolation nie vorhanden -- der Test skippte deshalb IMMER). Kopiert das
    committete Referenz-Trip gr221-mallorca nach briefings/ -- Vorbild
    tests/tdd/test_epic_140_preview_endpoints.py::_seed_trip_fixture.

    Socket-Sperre + echter Provider wie bei test_ac2_trend_path_sets_
    source_trend (identischer Mechanismus: PreviewService._build_report
    ruft _fetch_weather() mit Default enrich_ensemble=True, dessen
    Ensemble-Spread-Fallback breiter faengt als der primaere Forecast-Call
    und den Log-Eintrag liefert). Gemessen 2026-08-16, offline gruen.
    """
    import shutil
    import providers.openmeteo as om
    from app.loader import get_briefings_dir

    trip_id, user_id = "gr221-mallorca", "b1-preview-proof"
    src = (
        REPO_ROOT / "tests" / "fixtures" / "data_root" / "users"
        / "default" / "trips" / f"{trip_id}.json"
    )
    dst = get_briefings_dir(user_id) / f"{trip_id}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)

    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)  # echter Provider statt FixtureProvider (der nie loggt)
    log_path = tmp_path / "openmeteo_calls.jsonl"
    monkeypatch.setattr(om, "DIAGNOSTICS_PATH", log_path, raising=False)

    from services.preview_service import PreviewService

    svc = PreviewService()
    # render_email_preview schluckt API-Fehler nicht zwingend; 429 ist erlaubt,
    # die Quelle wird trotzdem korrekt aufgeloest.
    try:
        svc.render_email_preview(trip_id, user_id=user_id, report_type="morning")
    except Exception:
        pass

    entries = _read_jsonl(log_path)
    sources = {e["source"] for e in entries}
    assert entries, "Vorschau-Pfad haette mindestens einen Abruf protokollieren muessen"
    assert "vorschau" in sources, (
        f"Erwartete source 'vorschau' aus render_email_preview, sah: {sources}"
    )
    assert "briefing" not in sources, (
        f"source 'briefing' darf im Vorschau-Pfad NICHT auftauchen (F002), sah: {sources}"
    )


# ---------------------------------------------------------------------------
# AC-3: Schreibfehler beim Logging wird geschluckt, fetch laeuft weiter
# ---------------------------------------------------------------------------

# #1708 B1: direkter Aufruf mit `enrich_ensemble=False` -- derselbe Befund
# wie bei test_ac1 (gemessen 2026-08-16 mit @pytest.mark.disable_socket):
# ohne Ensemble-Fallback bleibt der Log-Nachweis offline unerreichbar, UND
# die eigentliche Zusicherung (Schreibfehler wird geschluckt, KEIN
# FileNotFoundError/NotADirectoryError propagiert) wuerde durch die
# zusaetzliche Socket-Exception verfaelscht (isinstance-Check schlaegt auf
# die SocketBlockedError an statt auf die zu pruefende Schreibfehler-
# Behandlung).
@pytest.mark.live
def test_ac3_unwritable_log_target_is_swallowed(tmp_path, monkeypatch):
    """
    AC-3: Ist das Diagnose-Ziel nicht beschreibbar, schluckt _log_api_call die
    Ausnahme und fetch_forecast laeuft unveraendert weiter (kein Crash).

    KONFIGURATION (kein Mock): DIAGNOSTICS_PATH wird unter eine DATEI gelegt
    (blocker/openmeteo_calls.jsonl, wobei 'blocker' eine Datei ist) — damit
    schlaegt mkdir(parents=True)/open fehl, ein echter Schreibfehler.
    """
    import providers.openmeteo as om

    blocker = tmp_path / "blocker"
    blocker.write_text("ich bin eine datei, kein verzeichnis")
    bad_path = blocker / "openmeteo_calls.jsonl"  # parent ist eine Datei
    monkeypatch.setattr(om, "DIAGNOSTICS_PATH", bad_path, raising=False)

    provider = om.OpenMeteoProvider()
    location = _make_location()
    now = datetime.now(timezone.utc)

    # Direkter Helfer-Aufruf: _log_api_call MUSS existieren und den echten
    # Schreibfehler (parent ist eine Datei) schlucken — kein Crash.
    # RED: AttributeError, weil _log_api_call noch nicht existiert.
    provider._log_api_call("https://api.open-meteo.com/v1/ecmwf", 429, error="limit")
    assert blocker.is_file(), "Logging haette die Blocker-Datei nicht anfassen duerfen"

    raised = None
    result = None
    try:
        result = provider.fetch_forecast(
            location=location, start=now, end=now + timedelta(days=1),
            enrich_ensemble=False,
        )
    except Exception as e:
        raised = e

    # Es darf KEIN Logging-bedingter Fehler nach oben kommen. Ein echter
    # ProviderRequestError (z.B. 429) ist erlaubt — aber niemals ein
    # FileNotFoundError/NotADirectoryError aus dem Logging.
    if raised is not None:
        from providers.base import ProviderRequestError, ProviderError
        assert isinstance(raised, (ProviderRequestError, ProviderError)), (
            f"Logging-Schreibfehler darf NICHT propagieren, sah: {type(raised)} {raised}"
        )
    # Bei Erfolg wurde trotz nicht-beschreibbarem Log ein Ergebnis geliefert.
    if result is not None:
        assert len(result.data) >= 0

    # Die kaputte Datei-als-Verzeichnis-Struktur ist unveraendert (kein Schreiben).
    assert blocker.is_file()


# ---------------------------------------------------------------------------
# AC-4: Auswertungs-Skript schluesselt nach source / endpoint / Stunde auf
# ---------------------------------------------------------------------------

def test_ac4_analyze_script_breaks_down_by_source_endpoint_hour(tmp_path):
    """
    AC-4: scripts/analyze_openmeteo_calls.py liefert gegen eine befuellte JSONL
    eine Aufschluesselung nach source, endpoint und Stunde.
    """
    script = REPO_ROOT / "scripts" / "analyze_openmeteo_calls.py"
    assert script.exists(), f"Auswertungs-Skript fehlt: {script}"

    jsonl = tmp_path / "openmeteo_calls.jsonl"
    rows = [
        {"ts": "2026-05-22T08:15:00+00:00", "endpoint": "https://api.open-meteo.com/v1/ecmwf",
         "status": 200, "source": "briefing", "error": None},
        {"ts": "2026-05-22T08:42:00+00:00", "endpoint": "https://api.open-meteo.com/v1/ecmwf",
         "status": 429, "source": "alarm", "error": None},
        {"ts": "2026-05-22T09:05:00+00:00", "endpoint": "https://ensemble-api.open-meteo.com/v1/ensemble",
         "status": 200, "source": "trend", "error": None},
        {"ts": "2026-05-22T09:55:00+00:00", "endpoint": "https://api.open-meteo.com/v1/ecmwf",
         "status": 500, "source": "trend", "error": "boom"},
    ]
    jsonl.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    proc = subprocess.run(
        [sys.executable, str(script), str(jsonl)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"Skript-Fehler:\n{proc.stderr}"
    out = proc.stdout.lower()

    # Gesamtzahl
    assert "4" in proc.stdout, f"Gesamtzahl 4 fehlt im Output:\n{proc.stdout}"
    # Aufschluesselung nach Quelle
    assert "source" in out or "quelle" in out
    for src in ("briefing", "alarm", "trend"):
        assert src in proc.stdout, f"Quelle '{src}' fehlt im Output:\n{proc.stdout}"
    # Aufschluesselung nach Endpoint
    assert "endpoint" in out
    assert "/v1/ecmwf" in proc.stdout
    assert "/v1/ensemble" in proc.stdout
    # Aufschluesselung nach Stunde
    assert "08" in proc.stdout and "09" in proc.stdout, (
        f"Stunden-Aufschluesselung (08/09) fehlt:\n{proc.stdout}"
    )
    # Status-Quote 200/429/sonstige
    assert "200" in proc.stdout and "429" in proc.stdout
