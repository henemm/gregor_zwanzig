"""Issue #2961 Welle 2 (ADR-0117): eigenes Abruf-Kontingent fuer interaktive Ausloeser.

SPEC: docs/specs/modules/security_haertung_2026_11_abruf_kontingent_interaktiv.md
Ausfuehrung:
    uv run pytest tests/tdd/test_abruf_kontingent_interaktiv.py -v

Kern-Schicht, netzfrei, ohne Mock-Theater: der ``ZaehlAnbieter`` erfuellt das
``WeatherProvider``-Protokoll echt (deterministische Zeitreihe) und zaehlt nur
seine eigenen Abrufe; eingehaengt wird er ueber die echte Provider-Registry
bzw. die echte FastAPI-Dependency der Etappenwetter-Route. Beobachtet wird an
der Wirkstelle: HTTP-Status und Antwortkoerper der echten ASGI-App,
Anbieter-Abrufe und ``ForecastBudgetGate.snapshot()``. Zaehlerdateien sind nur
Arrangement (Muster ``test_forecast_budget_fairness_je_nutzer.py``).

Immer zwei Nutzer: A verbraucht interaktiv viel, B und die Alarm-/Zeitplanwege
bleiben arbeitsfaehig.
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
from app.user import SavedLocation
from services.forecast_budget import PROVIDER, ForecastBudgetGate
from tests.helpers.ortstag import utc_tag

REPO = Path(__file__).resolve().parents[2]
INTERAKTIV = "user_interactive"
# Vertragswerte (ADR-0117): 70 % der Tagesmenge, Sockel 1500 Einheiten je Nutzer.
GRENZE_GLOBAL = int(0.70 * ForecastBudgetGate.DAILY_BUDGET)
SOCKEL = 1500


# --- Anbieter (kein Mock) ----------------------------------------------------

class ZaehlAnbieter:
    """Liefert je Ort dieselbe Stundenreihe ab heute 00:00 UTC ueber 6 Tage und
    zaehlt threadsicher jeden Abruf samt Koordinate."""

    name = "openmeteo"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.abrufe: list[tuple[float, float]] = []

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble: bool = True, enrich_snow: bool = True):
        with self._lock:
            self.abrufe.append((location.latitude, location.longitude))
        anker = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        daten = [
            ForecastDataPoint(
                ts=anker + timedelta(hours=i), t2m_c=5.0 + (i % 24) * 0.5,
                wind10m_kmh=10.0, gust_kmh=20.0, cloud_total_pct=30,
                precip_1h_mm=0.0, pop_pct=10, wmo_code=1, is_day=1,
            )
            for i in range(24 * 6)
        ]
        meta = ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2",
                            grid_res_km=2.2, run=anker, interp="grid_point")
        return NormalizedTimeseries(meta=meta, data=daten)


@pytest.fixture
def anbieter(monkeypatch):
    import providers.base as registry

    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    if not registry._PROVIDER_FACTORIES:
        registry._load_providers()
    fake = ZaehlAnbieter()
    monkeypatch.setitem(registry._PROVIDER_FACTORIES, "openmeteo", lambda: fake)
    return fake


@pytest.fixture
def client():
    import api.routers.compare as compare_mod
    from api.main import app

    # Pfadregel #1409: nie die Hauptrepo-Kopie pruefen.
    assert Path(compare_mod.__file__).resolve().is_relative_to(REPO)
    return TestClient(app)


# --- Arrangement-Helfer ---------------------------------------------------------

def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _schreibe_global(calls: int, aktive, interaktiv: int = 0) -> None:
    from app.loader import get_data_root

    pfad = get_data_root() / "diagnostics" / "forecast_budget.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({
        "date": utc_tag().isoformat(), "calls": {PROVIDER: calls},
        "interactive_calls": {PROVIDER: interaktiv},
        "cache_hits": 0, "cache_misses": 0, "active_users": list(aktive),
    }))


def _schreibe_nutzer(uid: str, calls: int, interaktiv: int) -> None:
    from app.loader import get_data_dir

    pfad = get_data_dir(uid) / "diagnostics" / "forecast_budget.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({
        "date": utc_tag().isoformat(), "calls": {PROVIDER: calls},
        "interactive": {PROVIDER: interaktiv},
    }))


def _viele_aktive(*namen) -> list[str]:
    """Genug aktive Nutzer, dass der faire Anteil unter den Sockel faellt."""
    return list(namen) + [f"fuell-{i}" for i in range(20)]


def _erschoepfe(uid_a: str, uid_b: str) -> None:
    """A hat sein interaktives Tageskontingent (Sockel) aufgebraucht, B nichts."""
    _schreibe_global(calls=SOCKEL, aktive=_viele_aktive(uid_a, uid_b), interaktiv=SOCKEL)
    _schreibe_nutzer(uid_a, calls=SOCKEL, interaktiv=SOCKEL)


def _ort(oid: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=oid, name=oid, lat=lat, lon=lon, elevation_m=1200,
                         timezone="Europe/Vienna")


def _speichere_orte(uid: str, orte) -> None:
    from app.loader import save_location

    for ort in orte:
        save_location(ort, user_id=uid)


def _vergleich(client, uid: str, ids: str, **extra):
    params = {"location_ids": ids, "user_id": uid,
              "target_date": (date.today() + timedelta(days=1)).isoformat()}
    params.update(extra)
    return client.get("/api/compare", params=params)


def _snap(uid: str) -> dict:
    return ForecastBudgetGate(uid).snapshot()


# --- AC-1/AC-2: Gate: eigene Prioritaet am fairen Anteil mit Sockel ----------

def test_ac1_interaktiv_erschoepft_trifft_nur_a_und_nie_briefing_alarm():
    a, b = _uid("ac1-a"), _uid("ac1-b")
    _erschoepfe(a, b)

    assert ForecastBudgetGate(a).reserve(INTERAKTIV) is False, (
        "A hat sein interaktives Kontingent aufgebraucht und darf nicht weiter buchen"
    )
    assert ForecastBudgetGate(b).reserve(INTERAKTIV) is True, "B bleibt arbeitsfaehig"
    # Zeitplan-Briefing, Handversand und Alarm-Pruefung desselben Nutzers A
    # bleiben unberuehrt.
    assert ForecastBudgetGate(a).reserve("user_briefing") is True
    assert ForecastBudgetGate(a).reserve("alert_check") is True
    assert ForecastBudgetGate(a).reserve("polling") is True


def test_ac2_sockel_gilt_wenn_fairer_anteil_kleiner_ist():
    a, b = _uid("ac2-a"), _uid("ac2-b")
    _schreibe_global(calls=SOCKEL - 1, aktive=_viele_aktive(a, b), interaktiv=SOCKEL - 1)
    _schreibe_nutzer(a, calls=SOCKEL - 1, interaktiv=SOCKEL - 1)

    gate = ForecastBudgetGate(a)
    assert gate.snapshot()["interactive_limit"] == SOCKEL
    assert gate.reserve(INTERAKTIV) is True, "die letzte Einheit bis zum Sockel geht noch"
    assert gate.reserve(INTERAKTIV) is False, "danach ist Schluss"
    assert _snap(a)["user_interactive_calls_today"] == SOCKEL


def test_ac2_ohne_kennung_nie_interaktiv():
    """Ohne Nutzer-Topf gibt es keinen interaktiven Anteil -- ein Aufruf ohne
    Kennung darf nie mehr als einer mit Kennung (ADR-0075 Punkt 4)."""
    assert ForecastBudgetGate(None).reserve(INTERAKTIV) is False
    assert ForecastBudgetGate(None).allow(INTERAKTIV) is False
    assert ForecastBudgetGate(_uid("ac2k")).allow(INTERAKTIV) is True


def test_ac2_erster_nutzer_des_tages_bekommt_nicht_den_ganzen_topf():
    """Fix-Runde F2 (ADR-0117 Nachtrag): feste Grenze 1500 je Nutzer, auch als
    einziger aktiver Nutzer des Tages -- nie die ganzen 6300."""
    a = _uid("ac2f-a")
    _schreibe_global(calls=SOCKEL - 1, aktive=[a], interaktiv=SOCKEL - 1)
    _schreibe_nutzer(a, calls=SOCKEL - 1, interaktiv=SOCKEL - 1)
    gate = ForecastBudgetGate(a)
    assert gate.snapshot()["interactive_limit"] == SOCKEL
    assert gate.reserve(INTERAKTIV) is True
    assert gate.reserve(INTERAKTIV) is False, "N=1 darf nicht ueber 1500 hinaus"
    assert ForecastBudgetGate(_uid("ac2f-b")).reserve(INTERAKTIV) is True


def test_kleinteil_reserve_lehnt_nicht_positive_einheiten_ab():
    gate = ForecastBudgetGate(_uid("units"))
    for wert in (0, -3):
        with pytest.raises(ValueError):
            gate.reserve("user_briefing", units=wert)
    assert gate.snapshot()["calls_today"] == 0


# --- AC-3: globale Reserve fuer Zeitplan-Briefings und Alarme ----------------

def test_ac3_interaktiv_nie_ueber_die_globale_grenze():
    a, b = _uid("ac3-a"), _uid("ac3-b")
    _schreibe_global(calls=GRENZE_GLOBAL - 1, aktive=[a, b])

    assert ForecastBudgetGate(b).reserve(INTERAKTIV, units=2) is False, (
        "zwei Einheiten wuerden die interaktive Grenze ueberbuchen"
    )
    assert ForecastBudgetGate(b).reserve(INTERAKTIV) is True
    assert ForecastBudgetGate(a).reserve(INTERAKTIV) is False, "Grenze erreicht"
    assert _snap(a)["calls_today"] == GRENZE_GLOBAL
    # Die Reserve oberhalb gehoert Briefings und Alarmen.
    assert ForecastBudgetGate(a).reserve("user_briefing") is True
    assert ForecastBudgetGate(a).reserve("alert_check") is True


def test_ac3_interaktiver_verbrauch_zaehlt_nicht_gegen_alarm_fairness():
    """Global 81 % (Stufe 1 fuer polling). A liegt insgesamt ueber dem fairen
    Anteil, aber nur wegen interaktiver Abrufe -- seine Alarm-/Polling-Wege
    bleiben offen."""
    a, b = _uid("ac3f-a"), _uid("ac3f-b")
    _schreibe_global(calls=7300, aktive=[a, b], interaktiv=4800)
    _schreibe_nutzer(a, calls=5000, interaktiv=4800)

    assert ForecastBudgetGate(a).allow("polling") is True
    assert ForecastBudgetGate(a).reserve("polling") is True


# --- AC-4: Vergleich ueber die ASGI-App -----------------------------------------

def test_ac4_vergleich_a_erschoepft_cache_bleibt_b_arbeitet(client, anbieter):
    a, b = _uid("ac4-a"), _uid("ac4-b")
    warm, kalt = _ort("warm", 47.10, 11.10), _ort("kalt", 47.20, 11.20)
    _speichere_orte(a, [warm, kalt])
    _speichere_orte(b, [_ort("b-ort", 47.30, 11.30)])

    # B waermt den (nutzerneutralen) Cache fuer "warm" an.
    _speichere_orte(b, [warm])
    assert _vergleich(client, b, "warm").status_code == 200
    _erschoepfe(a, b)
    vorher = len(anbieter.abrufe)

    resp = _vergleich(client, a, "warm,kalt")
    assert resp.status_code == 200, resp.text
    orte = {o["id"]: o for o in resp.json()["locations"]}
    assert orte["warm"]["error"] is None and orte["warm"]["temp_max"] is not None, (
        "gecachte Daten bleiben trotz erschoepftem Kontingent sichtbar"
    )
    assert orte["kalt"]["error_code"] == "abruf_kontingent_erschoepft"
    assert "Kontingent" in orte["kalt"]["error"], orte["kalt"]["error"]
    assert len(anbieter.abrufe) == vorher, "kein Anbieter-Abruf fuer A"

    nur_kalt = _vergleich(client, a, "kalt")
    assert nur_kalt.status_code == 429, nur_kalt.text
    assert nur_kalt.json()["code"] == "abruf_kontingent_erschoepft"
    assert int(nur_kalt.headers["Retry-After"]) >= 1

    resp_b = _vergleich(client, b, "b-ort")
    assert resp_b.status_code == 200
    assert resp_b.json()["locations"][0]["error"] is None


def test_ac4_vergleich_bucht_als_interaktiv(client, anbieter):
    a = _uid("ac4i-a")
    _speichere_orte(a, [_ort("o1", 47.41, 11.41), _ort("o2", 47.42, 11.42)])
    assert _vergleich(client, a, "*").status_code == 200
    snap = _snap(a)
    assert snap["user_interactive_calls_today"] == 2
    assert snap["interactive_calls_today"] == 2


def test_ac4_zeitplan_und_handversand_pfad_bleibt_ungedrosselt(anbieter):
    """Der Versandweg (Zeitplan und Handversand) laeuft ohne interaktiven
    Kontext und bucht ``user_briefing`` -- auch bei erschoepftem A."""
    from services.comparison_parallel import run_comparison_parallel

    a, b = _uid("ac4v-a"), _uid("ac4v-b")
    _erschoepfe(a, b)
    ergebnis = run_comparison_parallel(
        locations=[_ort("v1", 47.51, 11.51)], time_window=(9, 16),
        target_date=date.today() + timedelta(days=1),
        official_alerts_enabled=False, user_id=a,
    )
    assert ergebnis.locations[0].error is None
    assert _snap(a)["user_interactive_calls_today"] == SOCKEL, "nicht interaktiv gebucht"


# --- AC-5: Etappenwetter ----------------------------------------------------

def _trip_mit_etappe(uid: str, trip_id: str, lat: float):
    from app.loader import save_trip
    from app.trip import Stage, Trip, Waypoint

    etappe = Stage(id="s1", name="s1", date=utc_tag(), waypoints=[
        Waypoint(id="w1", name="w1", lat=lat, lon=11.0, elevation_m=900),
        Waypoint(id="w2", name="w2", lat=lat + 0.05, lon=11.05, elevation_m=1100),
    ])
    trip = Trip(id=trip_id, name=trip_id, stages=[etappe])
    save_trip(trip, user_id=uid)
    return trip


def _etappenwetter(client, uid: str, trip_id: str, fake):
    from api.main import app
    from api.routers import internal as internal_router

    app.dependency_overrides[internal_router.get_stage_weather_provider] = lambda: fake
    try:
        return client.get(f"/api/_internal/trips/{trip_id}/stages-weather",
                          params={"user_id": uid})
    finally:
        app.dependency_overrides.pop(internal_router.get_stage_weather_provider, None)


def test_ac5_etappenwetter_a_erschoepft_429_b_arbeitet(client):
    a, b = _uid("ac5-a"), _uid("ac5-b")
    _trip_mit_etappe(a, "trip-a", 46.1)
    _trip_mit_etappe(b, "trip-b", 46.6)
    _erschoepfe(a, b)
    fake = ZaehlAnbieter()

    resp_a = _etappenwetter(client, a, "trip-a", fake)
    assert resp_a.status_code == 429, resp_a.text
    assert resp_a.json()["code"] == "abruf_kontingent_erschoepft"
    assert fake.abrufe == []

    resp_b = _etappenwetter(client, b, "trip-b", fake)
    assert resp_b.status_code == 200, resp_b.text
    assert resp_b.json()["results"]["s1"] is not None
    assert "hinweis" not in resp_b.json()
    # Eine Einheit je Abschnitt (zwei Wegpunkte ergeben zwei Abschnitte).
    assert _snap(b)["user_interactive_calls_today"] == len(fake.abrufe) == 2


def test_ac5_etappenwetter_teilweise_aus_cache_mit_hinweis(client):
    """Eine Etappe kommt aus dem Cache, die andere waere ein neuer Abruf: die
    erste bleibt sichtbar, die zweite wird benannt statt still leer gelassen."""
    from app.loader import save_trip
    from app.trip import Stage, Trip, Waypoint

    a, b = _uid("ac5t-a"), _uid("ac5t-b")
    fake = ZaehlAnbieter()

    def etappe(sid, lat):
        return Stage(id=sid, name=sid, date=utc_tag(), waypoints=[
            Waypoint(id="w1", name="w1", lat=lat, lon=11.0, elevation_m=900),
            Waypoint(id="w2", name="w2", lat=lat + 0.05, lon=11.05, elevation_m=1100),
        ])

    save_trip(Trip(id="warm", name="warm", stages=[etappe("s1", 45.5)]), user_id=b)
    assert _etappenwetter(client, b, "warm", fake).status_code == 200
    save_trip(Trip(id="mix", name="mix", stages=[etappe("s1", 45.5), etappe("s2", 45.9)]),
              user_id=a)
    _erschoepfe(a, b)

    resp = _etappenwetter(client, a, "mix", fake)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["results"]["s1"] is not None
    assert body["results"]["s2"] is None
    assert body["gedrosselt"] == ["s2"]
    assert "Kontingent" in body["hinweis"]


# --- AC-6: Eingabegrenzen ----------------------------------------------------

@pytest.mark.parametrize("extra", [
    {"forecast_hours": 97}, {"forecast_hours": 0}, {"time_window_start": 24},
    {"time_window_end": -1}, {"target_date": "morgen"},
])
def test_ac6_eingabegrenzen_422_mit_katalogtext(client, anbieter, extra):
    a = _uid("ac6")
    _speichere_orte(a, [_ort("g1", 47.61, 11.61)])
    resp = _vergleich(client, a, "*", **extra)
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["code"] == "vergleich_parameter_ungueltig"
    assert isinstance(body["detail"], str) and body["detail"]
    assert anbieter.abrufe == [], "ungueltige Eingaben erreichen den Anbieter nie"


def test_ac6_obergrenze_96_stunden_bleibt_erlaubt(client, anbieter):
    a = _uid("ac6ok")
    _speichere_orte(a, [_ort("g2", 47.62, 11.62)])
    assert _vergleich(client, a, "*", forecast_hours=96).status_code == 200


# --- AC-7: Koordinaten-Verschiebung -----------------------------------------

def test_ac7_verschieben_um_meter_kostet_eigenes_kontingent(anbieter):
    """Jede Verschiebung in der vierten Nachkommastelle ist ein eigener
    Cache-Schluessel (unveraenderte Genauigkeit) -- sie kostet A je eine
    Einheit seines interaktiven Kontingents und endet an dessen Grenze."""
    from services.comparison_parallel import run_comparison_parallel
    from services.forecast_budget import interaktiver_abruf

    a, b = _uid("ac7-a"), _uid("ac7-b")
    _schreibe_global(calls=SOCKEL - 3, aktive=_viele_aktive(a, b), interaktiv=SOCKEL - 3)
    _schreibe_nutzer(a, calls=SOCKEL - 3, interaktiv=SOCKEL - 3)

    fehler = []
    for i in range(5):
        with interaktiver_abruf():
            ergebnis = run_comparison_parallel(
                locations=[_ort(f"s{i}", 47.7000 + i * 0.0001, 11.7)],
                time_window=(9, 16), target_date=date.today() + timedelta(days=1),
                official_alerts_enabled=False, user_id=a,
            )
        fehler.append(ergebnis.locations[0].error_code)
    assert len(anbieter.abrufe) == 3
    assert fehler == [None, None, None, "abruf_kontingent_erschoepft",
                      "abruf_kontingent_erschoepft"]
    assert ForecastBudgetGate(b).reserve(INTERAKTIV) is True


# --- AC-8: Sichtbarkeit -------------------------------------------------------

def test_ac8_warnzeile_bei_mehr_als_halbem_interaktiven_verbrauch(caplog):
    a, b = _uid("ac8-a"), _uid("ac8-b")
    _schreibe_global(calls=2000, aktive=[a, b], interaktiv=2000)
    _schreibe_nutzer(a, calls=1100, interaktiv=1100)

    with caplog.at_level(logging.WARNING, logger="forecast_budget"):
        assert ForecastBudgetGate(a).reserve(INTERAKTIV) is True
        assert ForecastBudgetGate(a).reserve(INTERAKTIV) is True
    zeilen = [r.getMessage() for r in caplog.records if "interaktiv" in r.getMessage()]
    assert len(zeilen) == 1, zeilen
    assert a not in zeilen[0], "Kennung nur maskiert"
    assert a[:2] in zeilen[0]

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="forecast_budget"):
        assert ForecastBudgetGate(b).reserve(INTERAKTIV) is True
    assert not [r for r in caplog.records if "interaktiv" in r.getMessage()]


def test_ac8_snapshot_weist_interaktiv_getrennt_aus():
    a, b = _uid("ac8s-a"), _uid("ac8s-b")
    assert ForecastBudgetGate(a).reserve(INTERAKTIV, units=3)
    assert ForecastBudgetGate(a).reserve("user_briefing", units=5)
    assert ForecastBudgetGate(b).reserve("alert_check", units=2)
    snap = _snap(a)
    assert snap["calls_today"] == 10
    assert snap["interactive_calls_today"] == 3
    assert snap["user_calls_today"] == 8
    assert snap["user_interactive_calls_today"] == 3


def test_ac8_interner_reserve_endpunkt_kennt_interaktiv(client):
    a, b = _uid("ac8r-a"), _uid("ac8r-b")
    _erschoepfe(a, b)
    pfad = "/api/_internal/forecast-budget/reserve"
    assert client.post(pfad, params={"user_id": a, "priority": INTERAKTIV}).json()["allowed"] is False
    assert client.post(pfad, params={"user_id": b, "priority": INTERAKTIV}).json()["allowed"] is True
    assert _snap(b)["user_interactive_calls_today"] == 2


# --- AC-9: Vorschau ----------------------------------------------------------

def test_ac9_sms_vorschau_erschoepft_429(client):
    a, b = _uid("ac9-a"), _uid("ac9-b")
    _trip_mit_etappe(a, "trip-v", 47.2692)
    _erschoepfe(a, b)
    resp = client.get("/api/preview/trip-v/sms", params={
        "user_id": a, "date": utc_tag().isoformat()})
    assert resp.status_code == 429, resp.text
    assert resp.json()["code"] == "abruf_kontingent_erschoepft"


def _tagesanker(uid: str, trip) -> None:
    """Tages-Anker des Trips wie ihn ein Briefing schreibt (echter Segment-Weg
    ueber den Zaehl-Anbieter), danach leerer Cache: die Vorschau muss frisch
    abrufen."""
    from app.models import GPXPoint, TripSegment
    from providers.base import get_provider
    from services.segment_weather import SegmentWeatherService
    from services.trip_day import trip_local_today
    from services.weather_cache import reset_shared_weather_cache_for_tests
    from services.weather_snapshot import WeatherSnapshotService

    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    wp = trip.stages[0].waypoints
    seg = TripSegment(
        segment_id="1",
        start_point=GPXPoint(lat=wp[0].lat, lon=wp[0].lon, elevation_m=900,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=wp[1].lat, lon=wp[1].lon, elevation_m=1100,
                           distance_from_start_km=5.0),
        start_time=start, end_time=start + timedelta(hours=23, minutes=59),
        duration_hours=23.98, distance_km=5.0, ascent_m=200, descent_m=0,
    )
    anker = SegmentWeatherService(get_provider("openmeteo")).fetch_segment_weather(
        seg, enrich_ensemble=False, enrich_snow=False, priority="alert_check", user_id=uid,
    )
    assert not anker.has_error
    WeatherSnapshotService(uid).save_dated(
        trip.id, trip_local_today(trip, datetime.now(timezone.utc)), [anker])
    reset_shared_weather_cache_for_tests()


def test_ac9_alarm_vorschau_erschoepft_429(client, anbieter):
    from services.weather_cache import reset_shared_weather_cache_for_tests

    a, b = _uid("ac9a-a"), _uid("ac9a-b")
    trip = _trip_mit_etappe(a, "trip-alarm", 47.2692)
    _tagesanker(a, trip)
    body = {
        "changes": [{"metric": "gust_max_kmh", "old_value": 40.0, "new_value": 60.0,
                     "delta": 20.0, "threshold": 50.0, "severity": "moderate",
                     "direction": "above", "segment_id": "1"}],
        "segment_times": [{"segment_id": "1", "start": "08:00", "end": "17:00"}],
    }
    pfad = f"/api/trips/{trip.id}/alert-preview"

    vorher = len(anbieter.abrufe)
    ok = client.post(pfad, params={"user_id": a}, json=body)
    assert ok.status_code == 200, ok.text
    assert len(anbieter.abrufe) > vorher, "Positivkontrolle: die Vorschau ruft frisch ab"
    assert _snap(a)["user_interactive_calls_today"] >= 1, "Vorschau bucht interaktiv"

    reset_shared_weather_cache_for_tests()
    _erschoepfe(a, b)
    resp = client.post(pfad, params={"user_id": a}, json=body)
    assert resp.status_code == 429, resp.text
    assert resp.json()["code"] == "abruf_kontingent_erschoepft"


def test_f4_vergleich_alarm_vorschau_bucht_interaktiv(client, anbieter):
    """Fix-Runde F4: die Ortsvergleich-Alarm-Vorschau (kind=vergleich) bucht
    ueber die echte ASGI-App interaktiv und meldet ein erschoepftes
    Kontingent mit 429."""
    from services.compare_location_weather_source import CompareLocationWeatherSource
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.weather_cache import reset_shared_weather_cache_for_tests
    from tests.tdd.test_alert_preview_compare_paritaet import LOCATIONS, PRESET_ID, _seed

    a, b = _uid("f4-a"), _uid("f4-b")
    _seed(a)
    orte = [loc for loc in LOCATIONS if loc.id in ("loc-ibk", "loc-bz")]
    snap = CompareWeatherSnapshotService(user_id=a)
    for loc in orte:
        punkt = CompareLocationWeatherSource().fetch(
            loc.id, loc.lat, loc.lon, 9, 16, elevation_m=loc.elevation_m, user_id=a)
        snap.save(PRESET_ID, loc.id, punkt)
    reset_shared_weather_cache_for_tests()
    body = {"changes": [
        {"metric": "gust_max_kmh", "old_value": 40.0, "new_value": 60.0, "delta": 20.0,
         "threshold": 50.0, "severity": "moderate", "direction": "above",
         "location_id": loc.id}
        for loc in orte
    ]}
    pfad = f"/api/briefings/{PRESET_ID}/alert-preview"
    params = {"kind": "vergleich", "user_id": a}

    vorher_abrufe = len(anbieter.abrufe)
    vorher_interaktiv = _snap(a)["user_interactive_calls_today"]
    ok = client.post(pfad, params=params, json=body)
    assert ok.status_code == 200, ok.text
    assert len(anbieter.abrufe) > vorher_abrufe, "Positivkontrolle: frischer Abruf"
    assert _snap(a)["user_interactive_calls_today"] > vorher_interaktiv, "bucht interaktiv"

    reset_shared_weather_cache_for_tests()
    _erschoepfe(a, b)
    resp = client.post(pfad, params=params, json=body)
    assert resp.status_code == 429, resp.text
    assert resp.json()["code"] == "abruf_kontingent_erschoepft"


def test_f5_etappe_mit_gedrosseltem_abschnitt_wird_nicht_aus_teildaten_bewertet(client):
    """Fix-Runde F5: liegt EIN Abschnitt einer Etappe im Cache und der andere
    wird vom Kontingent abgelehnt, liefert die Etappe keine Bewertung aus dem
    einen Abschnitt, sondern null samt Hinweis."""
    from services.segment_weather import SegmentWeatherService
    from services.stage_weather import _segments_for_stage

    a, b = _uid("f5-a"), _uid("f5-b")
    trip = _trip_mit_etappe(a, "trip-f5", 45.2)
    abschnitte = _segments_for_stage(trip, trip.stages[0])
    assert len(abschnitte) == 2, "Vorbedingung: zwei Abschnitte"
    fake = ZaehlAnbieter()
    # Ersten Abschnitt ueber den echten Segment-Weg in den geteilten Cache legen.
    erster = SegmentWeatherService(fake).fetch_segment_weather(
        abschnitte[0], enrich_ensemble=False, user_id=b)
    assert not erster.has_error
    _erschoepfe(a, b)

    resp = _etappenwetter(client, a, "trip-f5", fake)
    # Ohne Bewertung bleibt keine Etappe lieferbar -> 429 (nicht 200 mit einer
    # Ampel aus dem einen gecachten Abschnitt).
    assert resp.status_code == 429, resp.text
    assert len(fake.abrufe) == 1, "der zweite Abschnitt wurde nicht abgerufen"


# --- Messung (Herleitung des Sockels, Spec "Zahlen") -------------------------

def test_messung_einheiten_je_vergleich_und_etappenwetter(client, anbieter):
    a = _uid("mess")
    _speichere_orte(a, [_ort(f"m{i}", 46.0 + i * 0.1, 10.0 + i * 0.1) for i in range(10)])
    assert _vergleich(client, a, "*").status_code == 200
    assert _snap(a)["user_interactive_calls_today"] == 10, "Vergleich mit 10 Orten"

    from app.loader import load_trip, save_trip

    vorlage = REPO / "tests/fixtures/data_root/users/default/trips/gr221-mallorca.json"
    trip = load_trip(vorlage, user_id=a)
    save_trip(trip, user_id=a)
    etappen_anbieter = ZaehlAnbieter()
    resp = _etappenwetter(client, a, trip.id, etappen_anbieter)
    assert resp.status_code == 200
    # Referenz-Tour GR221 im Repo: 4 Etappen, 16 Wegpunkte -> 16 Abschnitte
    # (je Wegpunkt ein Abschnitt), je Abschnitt ein Abruf und eine Einheit.
    assert len(trip.stages) == 4
    assert len(etappen_anbieter.abrufe) == 16
    assert _snap(a)["user_interactive_calls_today"] == 10 + 16
