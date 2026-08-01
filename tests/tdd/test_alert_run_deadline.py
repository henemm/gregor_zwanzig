"""TDD RED — Issue #1447 Scheibe S1: Harte Zeitgrenze fuer
``TripAlertService.check_all_trips()`` + Sichtbarkeit (AC-1..AC-5, AC-7).

SPEC: docs/specs/modules/fix_1447_s1_alarm_lauf_zeitgrenze.md

Verhaltenstests -- kein Mock-Theater. Echte, kontrollierte Verzoegerung ueber
eine monkeypatchte ``TripAlertService.check_and_send_alerts`` (Projekt-Vorbild
fuer das Zeitbudget-Muster: ``test_meteofrance_direct_fallback.py:476-517``,
dort ein echter langsamer HTTP-Server + ``FETCH_DEADLINE_SECONDS`` per
``monkeypatch`` geschrumpft -- hier uebertragen auf Job-Ebene). Echter
Alarm-Versand nur ueber die bereits bestehende ``mail_sink``-DI-Naht (nie nach
aussen), amtliche Warnungen ueber strukturelle Fake-Quellen (kein
``Mock()``/``patch()``/``MagicMock``), analog
``tests/tdd/test_issue_1088_official_alert_triggers.py``.

RED-Ursachen (heute, vor der Implementierung):
- ``services.trip_alert.ALERT_RUN_DEADLINE_SECONDS`` existiert nicht (AC-7).
- ``check_all_trips()`` prueft keine Deadline und bricht daher nie ab (AC-1).
- ``check_all_trips()`` gibt ``int`` zurueck, nicht ``AlertCheckRunResult``
  (AC-1/AC-3/AC-5) -- Attributzugriffe auf das Ergebnis schlagen fehl.
- ``/api/scheduler/alert-checks`` liefert immer ``status: "ok"``, nie
  ``partial``/``checked``/``skipped``/``reason`` (AC-2).
- ``check_all_trips()`` loggt weder WARNING bei Abbruch (AC-4) noch INFO mit
  der Gesamtlaufzeit (AC-5).
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import date

import pytest

from app.loader import save_trip
from app.models import (
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from services import trip_alert
from services.trip_alert import TripAlertService

LAT, LON = 47.0, 11.0


@pytest.fixture(autouse=True)
def _isolated_official_alert_sources():
    """Analog test_issue_1088: die Modul-Registry echter amtlicher
    Alert-Quellen wird VOR jedem Test geleert und danach wiederhergestellt --
    sonst koennten reale Quellen (Vigilance/MeteoAlarm/...) fuer die hier
    verwendeten Test-Koordinaten zustaendig sein und die Laufzeit dieser
    Kern-Tests unvorhersehbar machen."""
    import services.official_alerts.base as oa_base

    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    yield oa_base
    oa_base._REGISTERED_SOURCES.clear()
    oa_base._REGISTERED_SOURCES.extend(backup)


def _fresh_user(prefix: str) -> str:
    return f"tdd-1447-{prefix}-{uuid.uuid4().hex[:6]}"


def _segment(idx: int | str = 1, *, lat: float = LAT, lon: float = LON) -> TripSegment:
    from datetime import datetime, timezone

    start = datetime(2026, 7, 8, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    return TripSegment(
        segment_id=idx,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=1000, distance_from_start_km=12.0),
        end_point=GPXPoint(lat=lat + 0.1, lon=lon + 0.1, elevation_m=1500, distance_from_start_km=18.0),
        start_time=start,
        end_time=end,
        duration_hours=4.0,
        distance_km=6.0,
        ascent_m=500,
        descent_m=0,
    )


def _weather_data(idx: int | str = 1, *, lat: float = LAT, lon: float = LON, **summary_kwargs) -> SegmentWeatherData:
    from datetime import datetime, timezone

    return SegmentWeatherData(
        segment=_segment(idx, lat=lat, lon=lon),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _save_cached(user_id: str, trip_id: str, cached: list[SegmentWeatherData]) -> None:
    from services.weather_snapshot import WeatherSnapshotService

    WeatherSnapshotService(user_id=user_id).save_dated(trip_id, date.today(), cached)


def _active_trip(trip_id: str, *, lat: float = LAT, lon: float = LON) -> Trip:
    """Trip, der von check_all_trips() NICHT komplett uebersprungen wird
    (official_alert_triggers_enabled defaultet auf aktiv), ohne dass amtliche
    Warnungen fuer diesen Test relevant sind (official_warnings-Default
    ``{"enabled": False}`` laesst check_official_alert_triggers() sofort
    leer zurueckkehren)."""
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(id="G1", name="Start", lat=lat, lon=lon, elevation_m=1000.0)],
    )
    trip = Trip(id=trip_id, name="Deadline-Test-Trip", stages=[stage])
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=True)
    return trip


def _official_trigger_trip(trip_id: str, *, lat: float = LAT, lon: float = LON) -> Trip:
    """Trip mit eigenstaendigem amtlichen Trigger aktiv (official_warnings=None
    -- "noch nicht migrierter Bestandstrip", Fallback auf aktiv), analog
    ``_minimal_trip`` in test_issue_1088."""
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(id="G1", name="Start", lat=lat, lon=lon, elevation_m=1000.0)],
    )
    trip = Trip(id=trip_id, name="Amtliche-Warnung-Trip", stages=[stage], official_warnings=None)
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=True)
    return trip


class _CoveringOfficialAlertSource:
    """Echte, strukturell typisierte Quelle (kein Mock) -- zustaendig fuer
    genau einen Punkt, liefert genau einen OfficialAlert."""

    def __init__(self, lat: float, lon: float, alert) -> None:
        self._lat = lat
        self._lon = lon
        self._alert = alert
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return f"test-1447-source-{self._lat}-{self._lon}"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        self.fetch_calls += 1
        return [self._alert]


def _setup_slow_trips(
    monkeypatch: pytest.MonkeyPatch,
    *,
    trip_count: int,
    sleep_per_trip_s: float,
    deadline_s: float,
) -> tuple[str, list[Trip], list[str]]:
    """Baut ``trip_count`` aktive Trips mit gecachtem Wetter, monkeypatcht
    ``ALERT_RUN_DEADLINE_SECONDS`` auf ``deadline_s`` und
    ``TripAlertService.check_and_send_alerts`` auf eine echte, aber winzige
    Verzoegerung (``time.sleep``) je aufgerufenem Trip -- Vorbild:
    ``FETCH_DEADLINE_SECONDS``-Testmuster in
    ``test_meteofrance_direct_fallback.py:501-503``, hier auf Job-Ebene
    uebertragen. Gibt (user_id, trips, calls) zurueck; ``calls`` sammelt die
    trip_id jedes tatsaechlichen Aufrufs von check_and_send_alerts."""
    user_id = _fresh_user("slow")
    trips: list[Trip] = []
    for i in range(trip_count):
        trip = _active_trip(f"trip-{i}")
        save_trip(trip, user_id=user_id)
        _save_cached(user_id, trip.id, [_weather_data(1, precip_sum_mm=2.0)])
        trips.append(trip)

    calls: list[str] = []

    def _slow_check_and_send(self, trip, cached, fresh_weather=None, official_notices=None):
        calls.append(trip.id)
        time.sleep(sleep_per_trip_s)
        return False

    monkeypatch.setattr(TripAlertService, "check_and_send_alerts", _slow_check_and_send)
    monkeypatch.setattr(trip_alert, "ALERT_RUN_DEADLINE_SECONDS", deadline_s)
    return user_id, trips, calls


# ---------------------------------------------------------------------------
# AC-1 -- ueberschrittene Obergrenze stoppt weitere Touren, nachweislich ueber
# Nicht-Aufruf der Pruef-Funktion (nicht nur ueber einen Zaehler).
# ---------------------------------------------------------------------------

def test_deadline_exceeded_stops_checking_remaining_trips(monkeypatch):
    """AC-1: Given der Lauf hat die Zeitobergrenze bereits ueberschritten,
    waehrend noch weitere Trips in der Liste stehen / When die Schleife die
    naechste Tour erreichen wuerde / Then wird diese und jede weitere
    verbleibende Tour NICHT mehr geprueft -- bewiesen ueber Nicht-Aufruf von
    check_and_send_alerts fuer mindestens einen Trip.

    RED (heute): ``check_all_trips()`` hat keine Deadline-Pruefung, ruft
    check_and_send_alerts fuer ALLE 6 Trips auf -- ``len(calls) < len(trips)``
    ist falsch (6 !< 6).
    """
    user_id, trips, calls = _setup_slow_trips(
        monkeypatch, trip_count=6, sleep_per_trip_s=0.05, deadline_s=0.08,
    )
    service = TripAlertService(user_id=user_id, mail_sink=lambda *_: None)

    result = service.check_all_trips()

    assert len(calls) < len(trips), (
        f"Erwartet: nicht alle {len(trips)} Trips wurden geprueft (Deadline "
        f"0.08s, 0.05s Verzoegerung je Trip) -- tatsaechlich aufgerufen: "
        f"{len(calls)} ({calls!r})"
    )
    assert result.checked == len(calls), (
        f"result.checked muss der Anzahl tatsaechlicher Aufrufe entsprechen: "
        f"result.checked={getattr(result, 'checked', '<fehlt>')!r}, calls={len(calls)}"
    )
    assert result.skipped == len(trips) - len(calls), (
        f"result.skipped muss die restlichen, nicht mehr geprueften Trips "
        f"zaehlen: result.skipped={getattr(result, 'skipped', '<fehlt>')!r}"
    )
    assert result.hit_deadline is True


# ---------------------------------------------------------------------------
# AC-2 -- Endpunkt meldet bei Abbruch status=partial + checked + skipped +
# erkennbaren Grund.
# ---------------------------------------------------------------------------

def test_endpoint_reports_partial_status_checked_skipped_and_reason_on_deadline_abort(monkeypatch):
    """AC-2: Given der Alarm-Lauf fuer einen Nutzer wird durch die
    Zeitobergrenze abgebrochen / When der Scheduler-Endpunkt
    ``/api/scheduler/alert-checks`` antwortet / Then enthaelt die Antwort
    ``status: "partial"``, ``checked``, ``skipped`` und einen erkennbaren
    Abbruchgrund.

    RED (heute): der Router setzt ``status`` fest auf ``"ok"`` und liefert
    weder ``checked`` noch ``skipped`` noch ``reason``.
    """
    from fastapi.testclient import TestClient

    from api.main import app

    user_id, trips, calls = _setup_slow_trips(
        monkeypatch, trip_count=5, sleep_per_trip_s=0.05, deadline_s=0.08,
    )

    client = TestClient(app)
    resp = client.post(f"/api/scheduler/alert-checks?user_id={user_id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data.get("status") == "partial", (
        f"Erwartet status='partial' bei Deadline-Abbruch, erhalten: {data!r}"
    )
    assert data.get("checked") == len(calls), (
        f"Erwartet checked=={len(calls)} (tatsaechliche Aufrufe), erhalten: {data!r}"
    )
    assert data.get("skipped") == len(trips) - len(calls), (
        f"Erwartet skipped=={len(trips) - len(calls)}, erhalten: {data!r}"
    )
    assert data.get("reason"), f"Erwartet einen erkennbaren Abbruchgrund (reason), erhalten: {data!r}"


# ---------------------------------------------------------------------------
# AC-3 -- vollstaendiger Lauf: gleiche Alarm-Anzahl wie heute, skipped=0.
# Regressions-Schutz -- Verhalten des Normalfalls darf sich nicht aendern.
# ---------------------------------------------------------------------------

def test_full_run_matches_legacy_alert_count_with_zero_skipped():
    """AC-3: Given ein Alarm-Lauf fuer einen Nutzer schliesst innerhalb der
    Zeitobergrenze vollstaendig ab / When der Lauf endet / Then ist die
    Anzahl versendeter Alarme identisch zum heutigen ``int``-Rueckgabewert
    UND keine Tour wird uebersprungen (``skipped: 0``).

    Regressions-Kontrolle: der eigentliche Alarm-Versand (2 echte,
    voneinander unabhaengige amtliche Alarme ueber die bestehende
    check_official_alert_triggers()/_send_official_alert_only()-Kette + den
    mail_sink-DI-Seam) laeuft HEUTE bereits korrekt -- ``len(mail_calls) ==
    2`` muss schon vor der Implementierung dieser Scheibe gruen sein. Nur 2
    Trips (nicht mehr) — der Free-Tier-Default-Tageslimit proaktiver Alerts
    (Issue #1070, ``services/user_tier.py::daily_alert_limit``) liegt bei 2
    und ist orthogonal zu dieser Scheibe, soll hier also nicht mitgetestet
    werden.

    RED (heute): ``check_all_trips()`` gibt ein ``int`` zurueck --
    ``result.alerts_sent``/``result.checked``/``result.skipped`` werfen
    AttributeError, obwohl der Alarm-Versand selbst unveraendert korrekt ist.
    """
    from services.official_alerts import OfficialAlert, register_official_alert_source

    user_id = _fresh_user("full")
    mail_calls: list[tuple[str, str]] = []
    trips = []
    for i in range(2):
        lat, lon = LAT + i, LON + i
        trip = _official_trigger_trip(f"trip-{i}", lat=lat, lon=lon)
        save_trip(trip, user_id=user_id)
        _save_cached(user_id, trip.id, [_weather_data(1, lat=lat, lon=lon, precip_sum_mm=2.0)])
        trips.append(trip)

        alert = OfficialAlert(
            source=f"test-1447-src-{i}", hazard="thunderstorm", level=3,
            label=f"Warnung {i} (#1447 AC-3)",
        )
        register_official_alert_source(_CoveringOfficialAlertSource(lat, lon, alert))

    service = TripAlertService(
        user_id=user_id,
        mail_sink=lambda subject, body: mail_calls.append((subject, body)),
    )

    result = service.check_all_trips()

    assert len(mail_calls) == len(trips), (
        f"Erwartet {len(trips)} echte Alarm-Versaende (Regressions-Kontrolle, "
        f"unabhaengig von dieser Scheibe), erhalten: {len(mail_calls)}"
    )
    assert result.alerts_sent == len(trips), (
        f"result.alerts_sent muss der heutigen Alarm-Anzahl entsprechen: "
        f"{getattr(result, 'alerts_sent', '<fehlt>')!r} != {len(trips)}"
    )
    assert result.checked == len(trips)
    assert result.skipped == 0, f"Vollstaendiger Lauf darf keine Tour uebersprungen haben: {getattr(result, 'skipped', '<fehlt>')!r}"
    assert result.hit_deadline is False


# ---------------------------------------------------------------------------
# AC-4 -- WARNING-Zeile bei Abbruch mit Obergrenze/geprueft/uebersprungen.
# ---------------------------------------------------------------------------

def test_deadline_abort_logs_warning_with_threshold_checked_and_skipped(monkeypatch, caplog):
    """AC-4: Given ein Alarm-Lauf wird durch die Zeitobergrenze abgebrochen /
    When der Abbruch eintritt / Then wird eine WARNING-Zeile geschrieben, die
    die Obergrenze, die Anzahl geprueft und die Anzahl uebersprungener Touren
    nennt.

    RED (heute): es gibt keine Deadline-Pruefung, also auch keine
    WARNING-Zeile dazu -- ``warning_records`` bleibt leer.
    """
    deadline_s = 0.08
    user_id, trips, calls = _setup_slow_trips(
        monkeypatch, trip_count=5, sleep_per_trip_s=0.05, deadline_s=deadline_s,
    )
    service = TripAlertService(user_id=user_id, mail_sink=lambda *_: None)

    with caplog.at_level(logging.WARNING, logger="trip_alert"):
        service.check_all_trips()

    warning_records = [
        r for r in caplog.records if r.levelno == logging.WARNING and r.name == "trip_alert"
    ]
    assert warning_records, (
        "Erwartet mindestens eine WARNING-Zeile aus dem 'trip_alert'-Logger "
        "bei Deadline-Abbruch, erhalten: keine"
    )
    checked = len(calls)
    skipped = len(trips) - checked
    combined = "\n".join(r.getMessage() for r in warning_records)
    assert str(deadline_s) in combined, (
        f"WARNING-Zeile nennt nicht die Obergrenze {deadline_s}: {combined!r}"
    )
    assert str(checked) in combined, (
        f"WARNING-Zeile nennt nicht die Anzahl geprueft ({checked}): {combined!r}"
    )
    assert str(skipped) in combined, (
        f"WARNING-Zeile nennt nicht die Anzahl uebersprungen ({skipped}): {combined!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 -- INFO-Zeile mit Gesamtlaufzeit, sowohl vollstaendig als auch
# abgebrochen.
# ---------------------------------------------------------------------------

def _info_records(caplog) -> list:
    return [r for r in caplog.records if r.levelno == logging.INFO and r.name == "trip_alert"]


def test_full_run_logs_info_with_total_duration(caplog):
    """AC-5 (vollstaendiger Fall): Given ein vollstaendiger Alarm-Lauf / When
    er endet / Then wird eine INFO-Zeile mit der tatsaechlichen
    Gesamtlaufzeit geschrieben.

    RED (heute): keine solche INFO-Zeile existiert.
    """
    user_id = _fresh_user("info-full")
    trip = _active_trip("trip-info-full")
    save_trip(trip, user_id=user_id)
    _save_cached(user_id, trip.id, [_weather_data(1, precip_sum_mm=2.0)])
    service = TripAlertService(user_id=user_id, mail_sink=lambda *_: None)

    with caplog.at_level(logging.INFO, logger="trip_alert"):
        service.check_all_trips()

    records = _info_records(caplog)
    combined = "\n".join(r.getMessage() for r in records)
    assert re.search(r"\d+\.\d+", combined), (
        f"Erwartet eine INFO-Zeile mit plausiblem Zeitwert (Gesamtlaufzeit) "
        f"nach vollstaendigem Lauf, erhalten: {combined!r}"
    )


def test_aborted_run_logs_info_with_total_duration(monkeypatch, caplog):
    """AC-5 (abgebrochener Fall): Given ein durch die Zeitobergrenze
    abgebrochener Alarm-Lauf / When er endet / Then wird ebenfalls eine
    INFO-Zeile mit der tatsaechlichen Gesamtlaufzeit geschrieben.

    RED (heute): keine solche INFO-Zeile existiert.
    """
    user_id, trips, calls = _setup_slow_trips(
        monkeypatch, trip_count=5, sleep_per_trip_s=0.05, deadline_s=0.08,
    )
    service = TripAlertService(user_id=user_id, mail_sink=lambda *_: None)

    with caplog.at_level(logging.INFO, logger="trip_alert"):
        service.check_all_trips()

    records = _info_records(caplog)
    combined = "\n".join(r.getMessage() for r in records)
    assert re.search(r"\d+\.\d+", combined), (
        f"Erwartet eine INFO-Zeile mit plausiblem Zeitwert (Gesamtlaufzeit) "
        f"nach abgebrochenem Lauf, erhalten: {combined!r}"
    )


# ---------------------------------------------------------------------------
# AC-7 -- Obergrenze ist eine benannte, per monkeypatch schrumpfbare Konstante.
# ---------------------------------------------------------------------------

def test_deadline_constant_exists_and_is_monkeypatchable_to_milliseconds(monkeypatch):
    """AC-7: Given die Zeitobergrenze ist im Produktivcode als benannte
    Konstante hinterlegt / When ein Test sie testweise verkleinern will /
    Then laesst sie sich per ``monkeypatch.setattr`` auf einen beliebigen,
    auch sehr kleinen Wert setzen, ohne Produktivcode anzufassen.

    RED (heute): ``services.trip_alert.ALERT_RUN_DEADLINE_SECONDS`` existiert
    nicht -> ``hasattr`` liefert False.
    """
    assert hasattr(trip_alert, "ALERT_RUN_DEADLINE_SECONDS"), (
        "ALERT_RUN_DEADLINE_SECONDS Modul-Konstante fehlt in services/trip_alert.py (AC-7)"
    )
    original = trip_alert.ALERT_RUN_DEADLINE_SECONDS
    assert original >= 60, (
        f"Erwartet eine Obergrenze deutlich unter den 120s des Go-Clients, aber "
        f"gross genug fuer echten Betrieb (Spec nennt 90.0s), erhalten: {original}"
    )

    monkeypatch.setattr(trip_alert, "ALERT_RUN_DEADLINE_SECONDS", 0.001)
    assert trip_alert.ALERT_RUN_DEADLINE_SECONDS == 0.001, (
        "monkeypatch.setattr auf ALERT_RUN_DEADLINE_SECONDS muss wirken, ohne "
        "Produktivcode zu aendern"
    )
