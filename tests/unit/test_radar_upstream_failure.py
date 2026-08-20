"""Issue #1628, S1+S3: echter Fetch-Fehler des Radar-NowCast-Pfads muss von
"genuinely dry" unterscheidbar sein (`NowcastResult.data_unavailable`) und
im Nutzertext (`/jetzt`) sichtbar werden, statt lautlos als "Kein
Niederschlag" durchzugehen.

SPEC: docs/specs/modules/fix_1628_nowcast_datenluecke.md (AC-2..AC-9)
Ausfuehrung:
    uv run pytest tests/unit/test_radar_upstream_failure.py -v

Kern-Schicht, netzfrei (CLAUDE.md Test-Politik). Kein Mock/patch von
Rueckgabewerten -- `httpx.Client` wird testweise durch eine deterministische
Ersatzklasse ersetzt (Muster `_TripwireClient`,
tests/unit/test_radar_budget_and_priority.py), deren `.get()` einen ECHTEN
`httpx.Response` mit dem dokumentierten, wortwoertlichen Open-Meteo-503-Koerper
(bzw. einer echten Erfolgsantwort gleicher Form) liefert -- kein Fake-Objekt,
sondern die reale httpx-Klasse mit aufgezeichneten Daten.
"""
from __future__ import annotations

from datetime import date, time

import httpx
import pytest

from services.radar_service import NowcastResult, RadarNowcastService

# Atlantik: ausserhalb ALLER fuenf Bounding-Boxen (RADOLAN/INCA/DPC/AROME-FR/
# ICON-D2, radar_service.py:28-58) -- identische Koordinate wie
# test_radar_budget_and_priority.py, reiner generischer minutely_15-Zweig,
# GENAU EIN HTTP-Versuch pro get_nowcast()-Aufruf.
_ATLANTIC_LAT, _ATLANTIC_LON = 35.0, -40.0

# Ausschliesslich in der ICON-D2-Box (lat 44-58/lon 2-19), ausserhalb
# RADOLAN (lat<=55.1), INCA (lat<=49.1), DPC (lat<=47.5), AROME-FR
# (lat<=51.5) -- fuer AC-4 (Regionalmodell mit `models`-Parameter, danach
# generischer Fallback OHNE `models`).
_ICON_D2_ONLY_LAT, _ICON_D2_ONLY_LON = 56.0, 15.0


# ---------------------------------------------------------------------------
# Netz-Double: echte httpx.Response-Objekte statt Mock/patch
# ---------------------------------------------------------------------------

_CALL_URLS: list[str] = []
_RESPONDER: list = [None]  # per Test ueberschrieben


def _failing_response(url: str) -> httpx.Response:
    """Wortwoertlicher Open-Meteo-Overload-Koerper, Issue-#1628-Journal."""
    return httpx.Response(
        503, request=httpx.Request("GET", url),
        json={"error": True, "reason": "The service is overloaded"},
    )


def _dry_success_response(url: str) -> httpx.Response:
    return httpx.Response(
        200, request=httpx.Request("GET", url),
        json={"minutely_15": {
            "time": ["2026-08-09T00:00", "2026-08-09T00:15", "2026-08-09T00:30"],
            "precipitation": [0.0, 0.0, 0.0],
            "weather_code": [0, 0, 0],
        }},
    )


def _all_none_then_dry_response(url: str) -> httpx.Response:
    """AC-4: regionaler Zweig (`models=icon_d2`) antwortet All-None (Punkt
    ausserhalb des rotierten Gitters); der generische Fallback OHNE
    `models` liefert danach eine echte, trockene Antwort."""
    if "models=icon_d2" in url:
        return httpx.Response(
            200, request=httpx.Request("GET", url),
            json={"minutely_15": {
                "time": ["2026-08-09T00:00", "2026-08-09T00:15"],
                "precipitation": [None, None],
                "weather_code": [None, None],
            }},
        )
    return _dry_success_response(url)


class _ScriptedClient:
    """Ersetzt `httpx.Client` fuer die Testdauer. Zeichnet jede aufgerufene
    URL auf und beantwortet sie ueber die aktuell hinterlegte Responder-
    Funktion (`_RESPONDER[0]`) -- immer ein ECHTES `httpx.Response`-Objekt,
    kein Mock. Analog `_TripwireClient`, hier mit konfigurierbarer Antwort
    statt einer reinen Netz-Tripwire."""

    def __init__(self, *a, **kw) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a) -> bool:
        return False

    def get(self, url, *a, **kw):
        _CALL_URLS.append(url)
        return _RESPONDER[0](url)


@pytest.fixture(autouse=True)
def _swap_http_client(monkeypatch):
    _CALL_URLS.clear()
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    monkeypatch.setattr(httpx, "Client", _ScriptedClient)
    yield
    _CALL_URLS.clear()


def _write_budget(calls_openmeteo: int) -> None:
    import json
    from app.loader import get_data_root
    path = get_data_root() / "diagnostics" / "forecast_budget.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date.today().isoformat(),
        "calls": {"openmeteo": calls_openmeteo},
        "cache_hits": 0, "cache_misses": 0,
    }
    path.write_text(json.dumps(payload))


# ---------------------------------------------------------------------------
# AC-2: echter HTTP-Fehlerstatus setzt das neue Fehlerfeld.
# ---------------------------------------------------------------------------

def test_real_http_error_sets_data_unavailable_flag():
    """AC-2/AC-9: `NowcastResult` traegt heute kein Fehlerfeld -- RED-
    Aussage ist der `AttributeError` auf `.data_unavailable`. GRUEN muss
    dieses Feld bei einem echten 503 als `True` liefern, bei genau einem
    HTTP-Versuch (AC-9: kein Zusatz-Call)."""
    _RESPONDER[0] = _failing_response
    svc = RadarNowcastService()

    result = svc.get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON)

    assert result.frames == []
    assert result.onset_minutes is None
    assert result.data_unavailable is True, (
        "AC-2: ein echter HTTP-Fehlerstatus (503, kein Budget-Druck, keine "
        "All-None-Antwort) muss das neue Fehlerfeld auf True setzen"
    )
    assert len(_CALL_URLS) == 1, (
        f"AC-9: genau ein HTTP-Versuch erwartet, tatsaechlich: {_CALL_URLS}"
    )


# ---------------------------------------------------------------------------
# AC-3: echt trocken bleibt unberuehrt.
# ---------------------------------------------------------------------------

def test_genuinely_dry_result_leaves_flag_false():
    """AC-3: ein erfolgreicher Abruf mit ausschliesslich Precip=0.0 darf das
    neue Fehlerfeld NICHT setzen -- der Normalfall "echt geprueft, wirklich
    trocken" bleibt unveraendert."""
    _RESPONDER[0] = _dry_success_response
    svc = RadarNowcastService()

    result = svc.get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON)

    assert result.onset_minutes is None
    assert result.data_unavailable is False, (
        "AC-3: ein echt trockenes Ergebnis darf das Fehlerfeld NICHT setzen"
    )


# ---------------------------------------------------------------------------
# AC-4: All-None-Antwort eines Regionalmodells ist keine Ausfall-Meldung.
# ---------------------------------------------------------------------------

def test_all_none_regional_response_does_not_set_flag():
    """AC-4 (ADR-0041 Muster B): der bestehende All-None-Guard signalisiert
    "nicht zustaendig", kein Ausfall -- die Kette faellt zum naechsten
    Modell durch (hier: generischer Fallback OHNE `models`), das neue Feld
    bleibt fuer das GESAMTE Ergebnis False."""
    _RESPONDER[0] = _all_none_then_dry_response
    svc = RadarNowcastService()

    result = svc.get_nowcast(_ICON_D2_ONLY_LAT, _ICON_D2_ONLY_LON)

    assert result.data_unavailable is False, (
        "AC-4: eine All-None-Antwort eines Regionalmodells ist die Auskunft "
        "'nicht zustaendig' -- sie darf das Fehlerfeld NICHT setzen"
    )
    assert len(_CALL_URLS) == 2, (
        "AC-4/AC-9: icon-d2 (All-None) + generischer Fallback, unveraenderte "
        f"Kettenlaenge, tatsaechlich: {_CALL_URLS}"
    )


# ---------------------------------------------------------------------------
# AC-5: Budget-Drosselung bleibt ein getrenntes Signal.
# ---------------------------------------------------------------------------

def test_budget_throttle_does_not_set_data_unavailable_flag():
    """AC-5: eine reine Kontingent-Drosselung setzt weiterhin nur
    `throttled=True` -- das neue Fehlerfeld bleibt False, sonst waeren
    Drosselung und echter Ausfall vermengt (R4)."""
    _write_budget(calls_openmeteo=7200)  # 80% Schwelle
    svc = RadarNowcastService()

    result = svc.get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON, priority="polling")

    assert _CALL_URLS == [], "Drosselung darf keinen HTTP-Versuch ausloesen"
    assert result.throttled is True
    assert result.data_unavailable is False, (
        "AC-5: eine Budget-Drosselung darf das neue Fehlerfeld NICHT "
        "zusaetzlich setzen -- throttled und data_unavailable sind getrennte "
        "Signale"
    )


# ---------------------------------------------------------------------------
# AC-6/AC-7: Nutzertext -- Datenlluecke sichtbar, Normalfall unveraendert.
# ---------------------------------------------------------------------------

def test_format_now_text_shows_data_gap_hint_not_false_all_clear():
    """AC-6 (Wirkungs-AC): bei gesetztem Fehlerfeld darf der `/jetzt`-Text
    NICHT die Entwarnung "Kein Niederschlag." / "In den naechsten 2 Stunden
    kein Regen erwartet." zeigen (R5) -- RED-Aussage ist heute der
    `TypeError` beim Konstruieren von `NowcastResult(data_unavailable=True)`."""
    result = NowcastResult(
        onset_minutes=None, intensity_label="Kein Niederschlag",
        source="minutely_15", frames=[], data_unavailable=True,
    )
    svc = RadarNowcastService()

    text = svc.format_now_text(result, include_source=False)

    assert "In den nächsten 2 Stunden kein Regen erwartet." not in text, (
        f"AC-6: Entwarnungssatz darf bei einer Datenluecke nicht erscheinen: {text!r}"
    )
    assert "Kein Niederschlag." not in text, (
        f"AC-6: Intensitaets-Label ist bei einer Datenluecke keine "
        f"Tatsachenbehauptung, darf nicht auftauchen: {text!r}"
    )
    assert "nicht möglich" in text, (
        f"AC-6: der Text muss einen Hinweis enthalten, dass die "
        f"Kurzfrist-Pruefung nicht durchgefuehrt werden konnte: {text!r}"
    )


def test_format_now_text_dry_result_wording_unchanged():
    """AC-7: der Normalfall (echt trocken, Fehlerfeld False) bleibt
    zeichenidentisch zum bisherigen Wortlaut."""
    result = NowcastResult(
        onset_minutes=None, intensity_label="Kein Niederschlag",
        source="minutely_15", frames=[], data_unavailable=False,
    )
    svc = RadarNowcastService()

    text = svc.format_now_text(result, include_source=False)

    assert text == (
        "Kein Niederschlag.\nIn den nächsten 2 Stunden kein Regen erwartet."
    ), f"AC-7: Normalfall-Wortlaut darf sich nicht aendern, tatsaechlich: {text!r}"


# ---------------------------------------------------------------------------
# F002 (Adversary-Befund, Mutationsfamilie 2): "and not frames" ist der
# einzige Schutz gegen eine Vermengung von "Sidecar-Fehlschlag" mit
# "Datenluecke", wenn der INCA/DPC-Primaerabruf trotzdem echte Frames
# liefert. Kein AC der Spec deckt diesen Fall direkt ab (AC-2/AC-5 pruefen
# frames=[]); dieser Test bewacht den Formelterm selbst.
# ---------------------------------------------------------------------------

# Fest innerhalb der INCA-Box (lat 46.3-49.1/lon 9.5-17.2), ausserhalb der
# RADOLAN-Box (lat 47.0-55.1) -- identische Koordinate wie in der
# Fehlermeldung aus Issue #1628.
_INCA_LAT, _INCA_LON = 46.73042, 12.321643


def _inca_success_sidecar_failure_response(url: str) -> httpx.Response:
    """INCA-Primaerabruf (dataset.api.hub.geosphere.at) liefert echte,
    nicht-leere Frames; der anschliessende Konvektions-Sidecar
    (_fetch_openmeteo_15 innerhalb _fetch_geosphere_inca,
    radar_service.py:366) scheitert mit einem echten HTTP-Fehlerstatus."""
    if "dataset.api.hub.geosphere.at" in url:
        return httpx.Response(
            200, request=httpx.Request("GET", url),
            json={
                "timestamps": [
                    "2026-08-09T00:00:00+00:00",
                    "2026-08-09T00:15:00+00:00",
                ],
                "features": [{"properties": {"parameters": {
                    "t2m": {"data": [15.0, 15.1]},
                    "ff": {"data": [3.0, 3.0]},
                    "fx": {"data": [5.0, 5.0]},
                    "rr": {"data": [0.5, 0.3]},
                    "pt": {"data": [1, 1]},
                    "rh2m": {"data": [70, 70]},
                }}}],
            },
        )
    return _failing_response(url)


def test_inca_sidecar_failure_with_real_frames_leaves_flag_false():
    """F002: ein realer Sidecar-Fehlschlag bei erfolgreichem INCA-
    Primaerabruf (bereits heute durch `_convective_checked=False`
    dokumentiert) darf die gueltigen INCA-Frames NICHT als Datenluecke
    kennzeichnen -- 'and not frames' in der data_unavailable-Formel
    (radar_service.py:586-590) ist der einzige Schutz davor. RED bei
    entferntem Formelterm: data_unavailable wuerde faelschlich True."""
    _RESPONDER[0] = _inca_success_sidecar_failure_response
    svc = RadarNowcastService()

    result = svc.get_nowcast(_INCA_LAT, _INCA_LON)

    assert result.frames, "INCA-Primaerabruf muss echte, nicht-leere Frames liefern"
    assert result.source == "INCA"
    assert result.data_unavailable is False, (
        "F002: ein Sidecar-Fehlschlag bei vorhandenen INCA-Frames darf NICHT "
        "als Datenluecke gezeigt werden"
    )
    assert result.convective_checked is False, (
        "der Gewitter-Sidecar ist tatsaechlich ausgefallen -- das bestehende "
        "Signal dafuer muss weiterhin False bleiben"
    )


# ---------------------------------------------------------------------------
# AC-8: beide echten Alarmwege bekommen dasselbe Signal.
# ---------------------------------------------------------------------------

class _RecordingRadarService:
    """Echter Pass-Through-Wrapper (KEIN Mock) um eine echte
    `RadarNowcastService`-Instanz -- zeichnet nur das tatsaechliche
    `NowcastResult` jedes `get_nowcast()`-Aufrufs auf, veraendert nichts am
    Verhalten (Abgriff-Seam, s. AC-8)."""

    def __init__(self) -> None:
        self._real = RadarNowcastService()
        self.results: list[NowcastResult] = []

    def get_nowcast(
        self, lat, lon, elevation_m=None, priority: str = "user_briefing"
    ) -> NowcastResult:
        result = self._real.get_nowcast(lat, lon, elevation_m=elevation_m, priority=priority)
        self.results.append(result)
        return result


def test_both_alarm_paths_receive_data_unavailable_flag():
    """AC-8: dieselbe Fehlerursache wie in AC-2 erreicht BEIDE echten
    Alarm-Einstiegspunkte -- `TripAlertService.check_radar_alerts()` und
    `CompareRadarAlertService._detect_triggered_locations()` -- ohne dass
    eine Zeile in einer der beiden Dateien geaendert wird."""
    _RESPONDER[0] = _failing_response
    from app.loader import save_trip
    from app.trip import Stage, Trip, Waypoint
    from app.user import SavedLocation
    from services.compare_radar_alert import CompareRadarAlertService
    from services.trip_alert import TripAlertService

    today = date.today()
    trip = Trip(
        id="ac8-fetch-failure-trip", name="AC8 Fetch Failure Trip",
        stages=[Stage(
            id="T1", name="Heute", date=today, start_time=time(0, 0),
            waypoints=[
                Waypoint(id="W1", name="Start", lat=_ATLANTIC_LAT, lon=_ATLANTIC_LON,
                          elevation_m=0, arrival_override="00:00"),
                Waypoint(id="W2", name="Ziel", lat=_ATLANTIC_LAT, lon=_ATLANTIC_LON + 0.02,
                          elevation_m=0, arrival_override="23:59"),
            ],
        )],
    )
    save_trip(trip)

    trip_wrapper = _RecordingRadarService()
    trip_svc = TripAlertService(user_id="default", radar_service=trip_wrapper)
    trip_svc.clear_radar_throttle(trip.id)
    trip_svc.check_radar_alerts()

    compare_wrapper = _RecordingRadarService()
    compare_svc = CompareRadarAlertService(user_id="default", radar_service=compare_wrapper)
    loc = SavedLocation(id="loc-ac8", name="Atlantik-Testort", lat=_ATLANTIC_LAT,
                          lon=_ATLANTIC_LON, elevation_m=0)
    compare_svc._detect_triggered_locations("preset-ac8", ["loc-ac8"], {"loc-ac8": loc})

    assert trip_wrapper.results, "TripAlertService.check_radar_alerts() haette get_nowcast aufrufen muessen"
    assert trip_wrapper.results[0].data_unavailable is True, (
        "AC-8: Trip-Alarmweg muss dasselbe Fehlerfeld sehen"
    )
    assert compare_wrapper.results, (
        "CompareRadarAlertService._detect_triggered_locations() haette get_nowcast aufrufen muessen"
    )
    assert compare_wrapper.results[0].data_unavailable is True, (
        "AC-8: Compare-Alarmweg muss dasselbe Fehlerfeld sehen"
    )
