"""Issue #2961 Welle 2, Fix-Runde (ADR-0117 Nachtrag): Prioritaet ``user_manual``
fuer Handversand und Antwort-Befehle, Zurechnung der Anreicherung.

SPEC: docs/specs/modules/security_haertung_2026_11_abruf_kontingent_interaktiv.md
Ausfuehrung:
    uv run pytest tests/tdd/test_abruf_kontingent_manuell.py -v

Kern-Schicht, netzfrei, kein Mock-Theater. Mengen werden auf Gate-Ebene mit
vorbelegten Zaehlerstaenden belegt (keine Lasttests). Beobachtet wird ueber
HTTP-Status/-Koerper der echten ASGI-App, die Antwort des echten
Befehlsprozessors, die Abruf-Mitschrift des Zaehl-Anbieters und
``ForecastBudgetGate.snapshot()``. Immer zwei Nutzer: A erschoepft, B arbeitet.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
from services.forecast_budget import PROVIDER, ForecastBudgetGate
from tests.helpers.ortstag import utc_tag

REPO = Path(__file__).resolve().parents[2]
MANUELL = "user_manual"
GRENZE_JE_NUTZER = 1500
GRENZE_GLOBAL = int(0.90 * ForecastBudgetGate.DAILY_BUDGET)  # 8100


class ZaehlAnbieter:
    """Echte WeatherProvider-Implementierung (kein Mock), zaehlt Abrufe."""

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


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _schreibe_global(calls: int, aktive, manuell: int = 0) -> None:
    from app.loader import get_data_root

    pfad = get_data_root() / "diagnostics" / "forecast_budget.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({
        "date": utc_tag().isoformat(), "calls": {PROVIDER: calls},
        "manual_calls": {PROVIDER: manuell}, "cache_hits": 0, "cache_misses": 0,
        "active_users": list(aktive),
    }))


def _schreibe_nutzer(uid: str, manuell: int) -> None:
    from app.loader import get_data_dir

    pfad = get_data_dir(uid) / "diagnostics" / "forecast_budget.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({
        "date": utc_tag().isoformat(), "calls": {PROVIDER: manuell},
        "manual": {PROVIDER: manuell},
    }))


def _snap(uid: str) -> dict:
    return ForecastBudgetGate(uid).snapshot()


def _erschoepfe(a: str, b: str, rest: int = 0) -> None:
    _schreibe_global(calls=GRENZE_JE_NUTZER - rest, aktive=[a, b], manuell=GRENZE_JE_NUTZER - rest)
    _schreibe_nutzer(a, GRENZE_JE_NUTZER - rest)


# --- Gate ------------------------------------------------------------------------

def test_manuell_erschoepft_trifft_nur_a_briefing_und_alarm_bleiben():
    a, b = _uid("m1-a"), _uid("m1-b")
    _erschoepfe(a, b)
    assert ForecastBudgetGate(a).reserve(MANUELL) is False
    assert ForecastBudgetGate(b).reserve(MANUELL) is True
    for prio in ("user_briefing", "alert_check", "polling", "user_interactive"):
        assert ForecastBudgetGate(a).reserve(prio) is True, prio
    snap = _snap(a)
    assert snap["user_manual_calls_today"] == GRENZE_JE_NUTZER
    assert snap["manual_limit"] == GRENZE_JE_NUTZER


def test_manuell_global_nie_ueber_90_prozent_alarme_bleiben_offen():
    a, b = _uid("m2-a"), _uid("m2-b")
    _schreibe_global(calls=GRENZE_GLOBAL - 1, aktive=[a, b])
    assert ForecastBudgetGate(b).reserve(MANUELL, units=2) is False
    assert ForecastBudgetGate(b).reserve(MANUELL) is True
    assert ForecastBudgetGate(a).reserve(MANUELL) is False
    assert _snap(a)["calls_today"] == GRENZE_GLOBAL, "nie ueber 90 %"
    assert _snap(a)["manual_budget"] == GRENZE_GLOBAL
    # Alarme werden erst ab 95 % gedrosselt, Briefings nie.
    assert ForecastBudgetGate(a).reserve("alert_check") is True
    assert ForecastBudgetGate(a).reserve("user_briefing") is True


def test_manuell_vorab_buchung_und_erstattung():
    """Die ganze Schaetzung wird beim ersten Abruf gebucht, der ungenutzte
    Rest beim Verlassen erstattet (Cache-Treffer zaehlen nicht)."""
    from services.forecast_budget import manueller_abruf

    a = _uid("m3-a")
    with manueller_abruf(a, 10):
        assert ForecastBudgetGate(a).reserve(MANUELL) is True
        assert _snap(a)["user_manual_calls_today"] == 10, "Vorab-Buchung"
        assert ForecastBudgetGate(a).reserve(MANUELL) is True
    snap = _snap(a)
    assert snap["user_manual_calls_today"] == 2
    assert snap["manual_calls_today"] == 2
    assert snap["calls_today"] == 2


def test_manuell_zu_grosser_versand_wird_vor_dem_ersten_abruf_abgelehnt():
    from services.forecast_budget import manuell_abgelehnt, manueller_abruf

    a, b = _uid("m4-a"), _uid("m4-b")
    _erschoepfe(a, b, rest=4)
    with manueller_abruf(a, 5) as status:
        assert ForecastBudgetGate(a).reserve(MANUELL) is False
        assert ForecastBudgetGate(a).reserve(MANUELL) is False, "kein Teil-Versand"
        assert manuell_abgelehnt() is True
    assert status.abgelehnt
    assert _snap(a)["user_manual_calls_today"] == GRENZE_JE_NUTZER - 4, "nichts gebucht"
    assert ForecastBudgetGate(a).reserve(MANUELL, units=4) is True, "Rest bleibt nutzbar"


# --- Handversand ueber die ASGI-App ------------------------------------------------

def test_handversand_trip_a_erschoepft_429_b_versendet(monkeypatch):
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.tdd import _handversand_fixtures as hv
    from tests.tdd._compare_kette_fixtures import nutzer_anlegen, transport_einrichten

    transport_einrichten(monkeypatch)
    trip_mails = hv.trip_naehte(monkeypatch)
    aufzeichner_installieren(monkeypatch)
    a, b = nutzer_anlegen(), nutzer_anlegen()
    hv.trip_anlegen(a, "trip-m")
    hv.trip_anlegen(b, "trip-m")
    _erschoepfe(a, b)
    c = hv.client()

    r = hv.neu_senden(c, "trip-m", a, "route")
    assert r.status_code == 429, r.text
    assert r.json()["code"] == "kontingent_erschoepft"
    assert int(r.headers["Retry-After"]) >= 1
    assert "kontingent" in r.json()["detail"].lower()
    assert trip_mails == [], "kein Teil-Briefing, auch kein Ausfall-Hinweis"
    assert _snap(a)["user_manual_calls_today"] == GRENZE_JE_NUTZER, "nichts gebucht"

    rb = hv.neu_senden(c, "trip-m", b, "route")
    assert rb.status_code == 200, rb.text
    assert len(trip_mails) == 1
    gebucht = _snap(b)["user_manual_calls_today"]
    assert gebucht >= 1, "Handversand bucht user_manual"
    assert _snap(b)["user_calls_today"] == gebucht, "nichts mehr als user_briefing"


def test_handversand_vergleich_zu_gross_vor_dem_ersten_abruf_abgelehnt(monkeypatch, anbieter):
    import services.scheduler_dispatch_service as sds
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.tdd import _handversand_fixtures as hv
    from tests.tdd._compare_kette_fixtures import (
        fixture_dict, nutzer_anlegen, orte_anlegen, preset_ablegen, transport_einrichten,
    )

    transport_einrichten(monkeypatch)
    mit = aufzeichner_installieren(monkeypatch)
    # Netznaht des Anker-Schreibers (Nowcast), nicht Pruefgegenstand.
    monkeypatch.setattr(sds, "_write_compare_alert_snapshots", lambda *a, **k: None)
    a, b = nutzer_anlegen(), nutzer_anlegen()
    for uid in (a, b):
        roh = fixture_dict("basis")
        roh["id"] = "vgl-m"
        roh["official_alerts_enabled"] = False
        orte_anlegen(uid)
        preset_ablegen(uid, roh)
    # Rest 5 Einheiten, Schaetzung des Vergleichs (2 Orte) ist 7.
    _erschoepfe(a, b, rest=5)
    c = hv.client()

    r = hv.neu_senden(c, "vgl-m", a, "vergleich")
    assert r.status_code == 429, r.text
    assert r.json()["code"] == "kontingent_erschoepft"
    assert anbieter.abrufe == [], "vor dem ersten Abruf abgelehnt"
    assert mit.kanaele == []

    rb = hv.neu_senden(c, "vgl-m", b, "vergleich")
    assert rb.status_code == 200, rb.text
    assert len(anbieter.abrufe) == 2
    assert _snap(b)["user_manual_calls_today"] == 2, "Rest der Vorab-Buchung erstattet"


def test_zeitplan_versand_von_a_bleibt_ungedrosselt(anbieter):
    from app.user import SavedLocation
    from services.comparison_parallel import run_comparison_parallel

    a, b = _uid("m7-a"), _uid("m7-b")
    _erschoepfe(a, b)
    ergebnis = run_comparison_parallel(
        locations=[SavedLocation(id="z", name="z", lat=47.5, lon=11.5, elevation_m=900)],
        time_window=(9, 16), target_date=datetime.now(timezone.utc).date(),
        official_alerts_enabled=False, user_id=a,
    )
    assert ergebnis.locations[0].error is None
    assert _snap(a)["user_manual_calls_today"] == GRENZE_JE_NUTZER


# --- Antwort-Befehle -------------------------------------------------------------

def _trip(uid: str, name: str):
    from app.loader import save_trip
    from app.trip import Stage, Trip, Waypoint

    etappe = Stage(id="s1", name="s1", date=utc_tag(), waypoints=[
        Waypoint(id="w1", name="w1", lat=46.3, lon=11.0, elevation_m=900),
        Waypoint(id="w2", name="w2", lat=46.35, lon=11.05, elevation_m=1100),
    ])
    trip = Trip(id=name.lower(), name=name, stages=[etappe])
    save_trip(trip, user_id=uid)
    return trip


def _befehl(uid: str, kanal: str, name: str = "Tour"):
    from services.trip_command_processor import InboundMessage, TripCommandProcessor

    return TripCommandProcessor().process(InboundMessage(
        trip_name=name, body="### query: glance", sender="t", channel=kanal,
        received_at=datetime.now(timezone.utc), user_id=uid,
    ))


@pytest.mark.parametrize("kanal,limit", [("telegram", None), ("email", None),
                                         ("sms", 160), ("premium_sms", 160)])
def test_befehl_a_erschoepft_kurze_antwort_b_arbeitet(anbieter, kanal, limit):
    a, b = _uid("m8-a"), _uid("m8-b")
    _trip(a, "Tour")
    _trip(b, "Tour")
    _erschoepfe(a, b)

    antwort = _befehl(a, kanal)
    assert antwort.command == "glance"
    assert not antwort.success
    text = antwort.confirmation_body.lower()
    assert "kontingent" in text or "quota" in text, antwort.confirmation_body
    if limit:
        assert len(antwort.confirmation_body) <= limit
    assert anbieter.abrufe == [], "kein Abruf fuer A"

    antwort_b = _befehl(b, kanal)
    assert "quota" not in antwort_b.confirmation_body.lower()
    assert "kontingent" not in antwort_b.confirmation_body.lower()
    assert len(anbieter.abrufe) >= 1
    assert _snap(b)["user_manual_calls_today"] == len(anbieter.abrufe)


# --- F3: Anreicherung im markierten Kontext ---------------------------------------

def test_anreicherung_wird_im_kontext_dem_nutzer_zugerechnet(monkeypatch):
    from services.forecast_budget import interaktiver_abruf
    from services.radar_service import RadarNowcastService

    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    a, b = _uid("m9-a"), _uid("m9-b")

    # Ausserhalb: wie bisher nutzerfrei (globaler Zaehler, kein Nutzer-Topf).
    RadarNowcastService().get_nowcast(39.70, 3.00, priority="user_briefing")
    vorher = _snap(a)["calls_today"]
    assert vorher >= 1, "Vorbedingung: der Radar-Abruf bucht"
    assert _snap(a)["user_calls_today"] == 0

    with interaktiver_abruf(a):
        RadarNowcastService().get_nowcast(39.80, 3.10, priority="user_briefing")
    assert _snap(a)["user_interactive_calls_today"] >= 1, "beim ausloesenden Nutzer"

    # Erschoepft: die Anreicherung entfaellt (throttled), nichts wird gebucht.
    _schreibe_global(calls=_snap(a)["calls_today"], aktive=[a, b])
    from app.loader import get_data_dir
    pfad = get_data_dir(a) / "diagnostics" / "forecast_budget.json"
    pfad.write_text(json.dumps({"date": utc_tag().isoformat(), "calls": {PROVIDER: 1500},
                                "interactive": {PROVIDER: 1500}}))
    stand = _snap(a)["calls_today"]
    with interaktiver_abruf(a) as status:
        ergebnis = RadarNowcastService().get_nowcast(39.90, 3.20, priority="user_briefing")
    assert ergebnis.throttled is True
    assert status.gedrosselt == 0, "eine entfallene Anreicherung macht keine Vorschau ungueltig"
    assert _snap(a)["calls_today"] == stand
