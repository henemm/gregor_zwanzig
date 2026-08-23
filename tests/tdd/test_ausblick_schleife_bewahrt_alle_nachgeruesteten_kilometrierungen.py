"""TDD RED — Issue #2109: nachgerüstete Kilometrierung geht in der
Ausblick-Schleife wieder verloren.

SPEC:    docs/specs/modules/fix_2109_kilometrierung_backfill_propagation.md
KONTEXT: docs/context/fix-2109-kilometrierung-verlust.md

Root Cause: ``_convert_trip_to_segments()`` (`trip_report_scheduler.py:1980-
2028`) lässt intern ``backfill_stage_distances()`` den Trip nachträglich
vermessen und via ``save_trip()`` persistieren, gibt das aktualisierte
Trip-Objekt aber NUR als lokale Variable zurück. Vier Aufrufstellen arbeiten
danach mit dem STALE ``trip`` weiter (``_send_trip_report_outcome`` :1248/
:1258, ``_build_stage_trend`` :2396, ``_collect_future_stage_weather``
:2854). Da ``save_trip()`` Listen (``stages``) beim Read-Modify-Write-Merge
wholesale ersetzt statt elementweise zu mergen, überschreibt jeder
nachfolgende Save mit dem stale ``trip`` eine bereits persistierte
Kilometrierung wieder mit dem alten Stand.

Testpolitik (CLAUDE.md "Test-Politik: Zwei Schichten"): kein Mock-Theater.
Echte GR221-Mallorca-Fixtures (``tests/fixtures/data_root/users/default/``)
mit echtem GPX-Bestand + echter ``backfill_stage_distances``/``save_trip``-
Persistenz unter der isolierten Datenwurzel (``tests/conftest.py``
``_isolate_data_root``, autouse). Wetterabruf läuft über den autouse
Offline-``FixtureProvider`` (Issue #346, ``GZ_TEST_FIXTURE_DIR``) — NICHT
gestubbt, sondern der echte Fetch-Pfad, damit die Ausblicks-Zeile
(``build_outlook_row``) real durchläuft (ein leerer ``weather()``-Stub würde
dort scheitern und den Wächter-Wert verfälschen).

Jeder Test läuft unter einem eindeutigen ``user_id`` (uuid-Suffix), weil
``backfill_stage_distances`` einen MODUL-GLOBALEN Fehl-Cache
(``_failed_lookups`` in ``services/track_resolution.py``) über den
Prozess hinweg teilt.
"""
from __future__ import annotations

import dataclasses
import json
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.config import Settings
from app.loader import get_data_dir, load_all_trips, load_trip_from_dict, save_trip
from app.models import OutlookState, TripReportConfig
from app.trip import Stage, Trip, Waypoint
from services.trip_report_scheduler import TripReportSchedulerService

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_ROOT = _REPO_ROOT / "tests" / "fixtures" / "data_root" / "users" / "default"
_TRIP_JSON = _FIXTURE_ROOT / "trips" / "gr221-mallorca.json"
_GPX_TAGE = [
    _FIXTURE_ROOT / "gpx" / "2026-01-17_2753214331_Tag 1_ von Valldemossa nach Deià.gpx",
    _FIXTURE_ROOT / "gpx" / "2026-01-17_2753216748_Tag 2_ von Deià nach Sóller.gpx",
    _FIXTURE_ROOT / "gpx" / "2026-01-17_2753225520_Tag 3_ von Sóller nach Tossals Verds.gpx",
    _FIXTURE_ROOT / "gpx" / "2026-01-17_2753228656_Tag 4_ von Tossals Verds nach Lluc.gpx",
]
assert _TRIP_JSON.exists(), f"Trip-Fixture fehlt: {_TRIP_JSON}"
for _gpx in _GPX_TAGE:
    assert _gpx.exists(), f"GPX-Fixture fehlt: {_gpx}"

_NO_TRANSPORT_FIELDS: dict = {
    "smtp_host": "", "smtp_user": "", "smtp_pass": "", "mail_to": "",
    "telegram_bot_token": "", "telegram_chat_id": "",
    "telegram_test_bot_token": "", "telegram_test_chat_id": "",
    "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
}


def _uid(prefix: str) -> str:
    return f"tdd-2109-{prefix}-{uuid.uuid4().hex[:6]}"


def _settings_no_transport() -> Settings:
    return Settings(**_NO_TRANSPORT_FIELDS)


def _trip_mit_n_unvermessenen_etappen(user_id: str, dates: list) -> Trip:
    """Baut den GR221-Bestandstrip mit ``len(dates)`` Etappen (Etappe i
    erhält das i-te GPX-Tag als exakt passenden Track), jede Etappe
    unvermessen, Etappen-Daten auf ``dates`` gezogen. GPX-Bestand + Trip
    werden im isolierten Datenverzeichnis des Nutzers persistiert."""
    gpx_dir = get_data_dir(user_id) / "gpx"
    gpx_dir.mkdir(parents=True, exist_ok=True)
    for gpx in _GPX_TAGE[: len(dates)]:
        shutil.copyfile(gpx, gpx_dir / gpx.name)

    data = json.loads(_TRIP_JSON.read_text(encoding="utf-8"))
    trip = load_trip_from_dict(data)
    stages = [
        dataclasses.replace(trip.stages[i], date=dates[i])
        for i in range(len(dates))
    ]
    trip = dataclasses.replace(trip, stages=stages)
    assert all(
        wp.distance_from_start_km is None
        for stage in trip.stages for wp in stage.waypoints
    ), "Testaufbau: alle Etappen muessen unvermessen starten"
    save_trip(trip, user_id=user_id)
    return trip


def _minimal_trip(trip_id: str, stage_date: date) -> Trip:
    """Synthetischer Trip ohne GPX-Bestand -- fuer AC-4/AC-5, wo es nur auf
    die Identitaet des durchgereichten ``trip``-Objekts ankommt, nicht auf
    eine echte Vermessung."""
    return Trip(
        id=trip_id, name="Minimal",
        stages=[Stage(
            id="S1", name="E1", date=stage_date,
            waypoints=[Waypoint(id="W1", name="Ort", lat=42.0, lon=9.0, elevation_m=500)],
        )],
    )


def _alle_distanzen_gesetzt(stage) -> bool:
    return all(wp.distance_from_start_km is not None for wp in stage.waypoints)


def _reload(trip_id: str, user_id: str) -> Trip:
    return next(t for t in load_all_trips(user_id=user_id) if t.id == trip_id)


# ---------------------------------------------------------------------------
# AC-1 — heutige UND künftige Etappe behalten nach dem vollen Lauf beide ihre
# Kilometrierung (primäre Bug-Reproduktion)
# ---------------------------------------------------------------------------

def test_ac1_heutige_und_kuenftige_etappe_behalten_beide_ihre_kilometrierung():
    """AC-1: `_send_trip_report_outcome()` konvertiert zuerst die heutige
    Etappe (:1248, Backfill+Save), dann im Ausblick (`_build_stage_trend`)
    die künftige Etappe (Backfill+Save) -- danach müssen BEIDE Etappen ihre
    nachgerüstete Kilometrierung auf der Platte tragen, nicht nur die
    zuletzt gespeicherte.

    RED heute: der zweite Save (Ausblick) überschreibt die `stages`-Liste
    mit dem stale `trip` von VOR dem ersten Backfill -- die heutige Etappe
    verliert ihre gerade erst geschriebene Kilometrierung wieder."""
    heute = date.today()
    user = _uid("ac1")
    trip = _trip_mit_n_unvermessenen_etappen(user, [heute, heute + timedelta(days=1)])
    trip.report_config = TripReportConfig(
        trip_id=trip.id, send_email=False, send_telegram=False, send_sms=False,
    )
    trip.alert_cooldown_minutes = 0

    service = TripReportSchedulerService(_settings_no_transport(), user_id=user)
    outcome = service._send_trip_report_outcome(trip, "evening", target_date=heute)

    assert outcome == "no_channels", f"Testaufbau: unerwarteter Ausgang {outcome!r}"

    reloaded = _reload(trip.id, user)
    for i, stage in enumerate(reloaded.stages):
        assert _alle_distanzen_gesetzt(stage), (
            f"Etappe {i} ({stage.id}, {stage.date}) verlor ihre Kilometrierung: "
            f"{[wp.distance_from_start_km for wp in stage.waypoints]}"
        )


# ---------------------------------------------------------------------------
# AC-2 — Ausblicks-Schleife über DREI künftige Etappen: JEDE behält ihre
# Kilometrierung, nicht nur die zeitlich letzte (Prod-Fund Trip `5f534011`)
# ---------------------------------------------------------------------------

def test_ac2_ausblicksschleife_bewahrt_alle_drei_etappen_nicht_nur_die_letzte():
    """AC-2: `_build_stage_trend()` durchläuft bis zu drei künftige Etappen
    nacheinander; jede Iteration ruft `_convert_trip_to_segments()` auf und
    rüstet dabei ihre eigene Etappe nach. Nach Abschluss der Schleife muss
    JEDE der drei durchlaufenen Etappen ihre Kilometrierung tragen.

    RED heute: nur die dritte (zuletzt gespeicherte) Etappe überlebt --
    jeder Save überschreibt die Kilometrierung der vorherigen Iteration mit
    dem Stand vor deren eigenem Backfill.

    Datumswahl: der Offline-``FixtureProvider`` liefert genau 72 Stunden
    (heute+heute+1+heute+2) Wetterdaten, verankert am ECHTEN UTC-Tag,
    unabhängig vom ``target_date``-Argument -- die drei Etappen liegen
    deshalb auf heute/heute+1/heute+2, `target_date` (für "künftig") auf
    gestern."""
    heute = date.today()
    gestern = heute - timedelta(days=1)
    user = _uid("ac2")
    dates = [heute, heute + timedelta(days=1), heute + timedelta(days=2)]
    trip = _trip_mit_n_unvermessenen_etappen(user, dates)

    service = TripReportSchedulerService(_settings_no_transport(), user_id=user)
    result = service._build_stage_trend(trip, gestern, now_utc=datetime.now(timezone.utc))

    assert result.rows and len(result.rows) == 3, (
        f"Testaufbau: Ausblick nicht vollstaendig gebaut (state={result.state}, "
        f"rows={result.rows}) -- der Test misst sonst nichts"
    )

    reloaded = _reload(trip.id, user)
    for i, stage in enumerate(reloaded.stages):
        assert _alle_distanzen_gesetzt(stage), (
            f"Etappe {i} ({stage.id}, {stage.date}) verlor ihre Kilometrierung: "
            f"{[wp.distance_from_start_km for wp in stage.waypoints]}"
        )


# ---------------------------------------------------------------------------
# AC-3 — dieselbe Kette wie AC-1, Assertion fokussiert gezielt auf die
# HEUTIGE Etappe (Cross-Boundary `_send_trip_report_outcome` -> `_build_
# stage_trend`)
# ---------------------------------------------------------------------------

def test_ac3_heutige_etappe_verliert_kilometrierung_nicht_durch_spaeteren_ausblick_save():
    """AC-3: `_send_trip_report_outcome()` rüstet die heutige Etappe nach
    (:1248) und übergibt den Trip danach an `_build_stage_trend()`, wo eine
    künftige Etappe ebenfalls nachgerüstet UND gespeichert wird. Die heutige
    Etappe darf ihre Kilometrierung NICHT verlieren, obwohl der Speichervorgang
    der künftigen Etappe zeitlich SPÄTER erfolgt.

    RED heute: exakt dieser zeitlich spätere Save der künftigen Etappe
    überschreibt die `stages`-Liste mit dem stale (unvermessenen) Stand der
    heutigen Etappe."""
    heute = date.today()
    user = _uid("ac3")
    trip = _trip_mit_n_unvermessenen_etappen(user, [heute, heute + timedelta(days=1)])
    trip.report_config = TripReportConfig(
        trip_id=trip.id, send_email=False, send_telegram=False, send_sms=False,
    )
    trip.alert_cooldown_minutes = 0

    service = TripReportSchedulerService(_settings_no_transport(), user_id=user)
    service._send_trip_report_outcome(trip, "evening", target_date=heute)

    reloaded = _reload(trip.id, user)
    heutige_etappe = reloaded.stages[0]
    assert heutige_etappe.date == heute, "Testaufbau: Etappe 0 ist nicht die heutige"
    assert _alle_distanzen_gesetzt(heutige_etappe), (
        "Die HEUTIGE Etappe hat ihre Kilometrierung verloren, obwohl der "
        f"spaetere Ausblicks-Save (kuenftige Etappe) nicht ihr eigener war: "
        f"{[wp.distance_from_start_km for wp in heutige_etappe.waypoints]}"
    )


# ---------------------------------------------------------------------------
# AC-7 — On-Demand-Snapshot-Pfad (Adversary-Finding F001): fünfte Aufrufstelle
# in trip_command_processor.py._fetch_and_save_snapshot() teilt denselben
# Bug -- zwei Aufrufe (heute, morgen) auf demselben stale `trip`.
# ---------------------------------------------------------------------------

def test_ac7_on_demand_snapshot_pfad_bewahrt_heutige_etappe():
    """AC-7 (Adversary-Finding F001): `_fetch_and_save_snapshot()` ruft
    `scheduler._convert_trip_to_segments(trip, today)` und danach
    `scheduler._convert_trip_to_segments(trip, tomorrow)` auf demselben
    `scheduler` auf -- der erste Aufruf rüstet die heutige Etappe nach und
    speichert, der zweite (morgige) Aufruf darf diese Kilometrierung nicht
    wieder mit dem stale Stand überschreiben."""
    from services.trip_command_processor import _fetch_and_save_snapshot

    heute = date.today()
    morgen = heute + timedelta(days=1)
    user = _uid("ac7")
    trip = _trip_mit_n_unvermessenen_etappen(user, [heute, morgen])

    _fetch_and_save_snapshot(trip=trip, user_id=user, today=heute, tomorrow=morgen)

    reloaded = _reload(trip.id, user)
    heutige_etappe = reloaded.stages[0]
    assert heutige_etappe.date == heute, "Testaufbau: Etappe 0 ist nicht die heutige"
    assert _alle_distanzen_gesetzt(heutige_etappe), (
        "Die HEUTIGE Etappe hat ihre Kilometrierung verloren, obwohl der "
        f"spaetere Save (morgige Etappe) nicht ihr eigener war: "
        f"{[wp.distance_from_start_km for wp in heutige_etappe.waypoints]}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Regressions-Wächter für den Reset-Mechanismus SELBST
#
# Strukturell bereits VOR dem Fix grün: der Seitenkanal (`self.
# _last_converted_trip`) existiert heute noch nicht, also kann er auch
# nichts kontaminieren. Zweck des Tests: sobald der Fix den Seitenkanal
# einführt, wacht dieser Test darüber, dass das Reset VOR jedem Aufruf steht
# -- eine unvollständige Fix-Variante (Reset vergessen) würde einen fremden
# `trip` aus einem FRÜHEREN, nicht überschriebenen Aufruf derselben Instanz
# übernehmen.
# ---------------------------------------------------------------------------

def test_ac4_ueberschriebene_convert_methode_bleibt_frei_von_fremdem_trip():
    """AC-4: Eine Unterklasse überschreibt `_convert_trip_to_segments(self,
    trip, target_date)` mit der alten 2-Positional-Argument-Signatur (wie
    `test_outlook_scheduler_wires_hiking_window.py:48`). VOR dem
    überschriebenen Aufruf läuft auf DERSELBEN Instanz ein echter, NICHT
    überschriebener Aufruf mit einem ANDEREN Trip (`trip_other`). Danach
    muss `_build_stage_trend(trip_a, ...)` weiterhin mit `trip_a` arbeiten
    -- nicht mit dem Ergebnis des früheren `trip_other`-Aufrufs."""
    heute = date.today()
    user = _uid("ac4")
    trip_other = _minimal_trip(f"i2109-ac4-other-{uuid.uuid4().hex[:6]}", heute)
    trip_a = _minimal_trip(f"i2109-ac4-a-{uuid.uuid4().hex[:6]}", heute + timedelta(days=1))

    class _ToggleScheduler(TripReportSchedulerService):
        def __init__(self, *a, **kw) -> None:
            super().__init__(*a, **kw)
            self.override_active = False
            self.recorded_trips: list = []

        def _convert_trip_to_segments(self, trip, target_date):
            if self.override_active:
                return ["ein-segment"]
            return TripReportSchedulerService._convert_trip_to_segments(
                self, trip, target_date,
            )

        def _fetch_weather(self, segments, provider=None):
            from tests.helpers.alert_log_fixtures import weather
            return [weather("1")]

        def _enrich_ensemble_for_trip(self, trip, weather_data):
            self.recorded_trips.append(trip)

    service = _ToggleScheduler(_settings_no_transport(), user_id=user)

    # Schritt 1: echter (nicht überschriebener) Aufruf mit trip_other.
    service.override_active = False
    service._convert_trip_to_segments(trip_other, heute)

    # Schritt 2: überschriebener Aufruf über _build_stage_trend mit trip_a.
    service.override_active = True
    service._build_stage_trend(trip_a, heute, now_utc=datetime.now(timezone.utc))

    assert service.recorded_trips, (
        "_enrich_ensemble_for_trip wurde nicht erreicht -- der Test misst sonst nichts"
    )
    letztes = service.recorded_trips[-1]
    assert letztes is trip_a, (
        f"Der Aufrufer arbeitet nicht mehr mit seinem eigenen trip_a-Objekt "
        f"(id={id(letztes)}), sondern mit einem fremden Objekt (trip_a-id={id(trip_a)})"
    )
    assert letztes is not trip_other, (
        "Der Aufrufer hat faelschlich das trip-Objekt aus dem FRUEHEREN, "
        "nicht ueberschriebenen Aufruf uebernommen"
    )


# ---------------------------------------------------------------------------
# AC-5 — Fail-soft bei Exception in backfill_stage_distances
#
# Strukturell bereits VOR dem Fix grün: `_build_stage_trend()` umschließt
# JEDEN Schleifendurchlauf bereits heute mit einem eigenen `try/except`
# (trip_report_scheduler.py:2395/2495) -- eine Exception aus dem Backfill
# bricht schon jetzt nicht den ganzen Lauf ab. Zweck: der Fix darf diese
# Eigenschaft NICHT versehentlich brechen (z.B. Reset NACH statt VOR dem
# Aufruf, der bei einer Exception uebersprungen wuerde).
# ---------------------------------------------------------------------------

def test_ac5_backfill_exception_bleibt_fail_soft():
    """AC-5: `backfill_stage_distances` wirft eine Exception während eines
    Aufrufs von `_convert_trip_to_segments()` innerhalb der Ausblick-
    Schleife -- der Report-Lauf darf nicht abstürzen, `_build_stage_trend()`
    muss ein reguläres `TrendResult` (kein unbehandelter Fehler) liefern."""
    import services.track_resolution as track_resolution

    def _boom(*_a, **_kw):
        raise RuntimeError("simulierter Absturz der Track-Aufloesung")

    original = track_resolution.backfill_stage_distances
    track_resolution.backfill_stage_distances = _boom
    try:
        heute = date.today()
        user = _uid("ac5")
        trip = _minimal_trip(f"i2109-ac5-{uuid.uuid4().hex[:6]}", heute + timedelta(days=1))
        service = TripReportSchedulerService(_settings_no_transport(), user_id=user)

        result = service._build_stage_trend(trip, heute, now_utc=datetime.now(timezone.utc))
    finally:
        track_resolution.backfill_stage_distances = original

    assert result is not None, "Aufruf ist abgesturzt statt fail-soft ein TrendResult zu liefern"
    assert result.state == OutlookState.UNAVAILABLE, (
        f"Erwartet UNAVAILABLE (einzige Etappe scheiterte fail-soft), erhalten {result.state}"
    )


# ---------------------------------------------------------------------------
# AC-6 — persist=False bleibt unverändert folgenlos (Preview-Pfad)
# ---------------------------------------------------------------------------

def test_ac6_persist_false_schreibt_weiterhin_nichts_auf_die_platte():
    """AC-6: `_convert_trip_to_segments(trip, date, persist=False)` darf
    weiterhin NICHTS auf die Platte schreiben -- der neue Seitenkanal
    (`self._last_converted_trip`) ändert nichts am Persistenz-Verhalten des
    `persist=False`-Pfads (`PreviewService`, #2036 CI-Nachschlag).

    Bestehender Test `test_preview_does_not_mutate_trip_data.py` bleibt
    unverändert und wird von dieser Änderung nicht berührt."""
    heute = date.today()
    user = _uid("ac6")
    trip = _trip_mit_n_unvermessenen_etappen(user, [heute])

    trip_datei = get_data_dir(user) / "briefings" / f"{trip.id}.json"
    assert trip_datei.exists(), f"Trip-Datei fehlt: {trip_datei}"
    inhalt_vorher = trip_datei.read_bytes()
    mtime_vorher = trip_datei.stat().st_mtime_ns

    service = TripReportSchedulerService(_settings_no_transport(), user_id=user)
    segments = service._convert_trip_to_segments(trip, heute, persist=False)

    assert segments, "Testaufbau: Segmente muessen entstehen, sonst prueft der Test nichts"
    assert trip_datei.stat().st_mtime_ns == mtime_vorher, (
        "persist=False hat die Trip-Datei dennoch neu geschrieben (mtime geaendert)"
    )
    assert trip_datei.read_bytes() == inhalt_vorher, (
        "persist=False hat den Trip-Bestand inhaltlich veraendert"
    )
