"""TDD RED — Issue #1258 Scheibe S1 (AC-4, AC-5, AC-6): Datenmodell-Default
fuer Neuanlagen, Nutzer-Isolation, Pipeline-Vorrang des neuen Feldes.

Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md,
Sektion „Implementation Details" Nr. 1+3 + AC-4/AC-5/AC-6.

Design-Entscheidung dieser RED-Phase (aus dem Spec-Wortlaut „Default im
Konstruktor/Loader, nicht in der Migration" abgeleitet, s.
docs/context/feat-1258-compare-alarme-tab.md „Analysis"): der blanke
Dataclass-Konstruktor (`Trip(...)`/`ComparePreset(...)` OHNE
`official_warnings`-Kwarg) liefert den Neuanlage-Default
`{"enabled": False}`. Ein aus einer bestehenden JSON-Datei GELADENER Trip
ohne `official_warnings`-Schluessel bleibt dagegen `None` („noch nicht
migriert" — die Batch-Migration in `test_official_warnings_migration.py`
fuellt dieses Feld nachtraeglich). Diese Unterscheidung ist zwingend, sonst
liesse sich ein frisch angelegter Trip nicht mehr von einem
unmigrierten Bestandstrip unterscheiden.

RED heute:
- `Trip`/`ComparePreset` kennen `official_warnings` weder als Konstruktor-
  Kwarg noch als Attribut -> TypeError bzw. AttributeError.
- `TripAlertService.check_official_alert_triggers()` liest weiterhin
  ausschliesslich `official_alert_triggers_enabled` -> das Konflikt-Fixture
  (AC-6) loest heute FAELSCHLICH einen Fetch/Alert aus.

Verhaltenstests — KEINE Mocks. Echte Fake-Quellen (strukturelles
Protocol-Subtyping via register_official_alert_source()), echte
save_trip()/load_trip()-Roundtrips, echte Nutzer-Verzeichnisse unter
data/users/ (aufgeraeumt in try/finally, Muster test_issue_1088).
"""
from __future__ import annotations

import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

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

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

LAT, LON = 47.2, 11.3


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _fresh_user(prefix: str) -> str:
    return f"tdd-1258-{prefix}-{uuid.uuid4().hex[:6]}"


def _stage(stage_id: str = "T1") -> Stage:
    return Stage(
        id=stage_id, name="Tag 1", date=date(2026, 7, 15),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )


def _segment(segment_id: int | str = 1) -> TripSegment:
    start = datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000, distance_from_start_km=12.0),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500, distance_from_start_km=18.0),
        start_time=start, end_time=end, duration_hours=4.0, distance_km=6.0,
        ascent_m=500, descent_m=0,
    )


def _cached_data() -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(1),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(precip_sum_mm=2.0),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _save_cached(user_id: str, trip_id: str) -> None:
    from services.weather_snapshot import WeatherSnapshotService

    WeatherSnapshotService(user_id=user_id).save_dated(trip_id, date.today(), [_cached_data()])


def _registered_sources_backup():
    import services.official_alerts.base as oa_base
    return oa_base, list(oa_base._REGISTERED_SOURCES)


class _CountingOfficialAlertSource:
    """Echte Quelle (kein Mock), zaehlt jeden fetch()-Aufruf (Muster
    test_issue_1088_official_alert_triggers.py)."""

    def __init__(self, lat: float, lon: float, alert) -> None:
        self._lat = lat
        self._lon = lon
        self._alert = alert
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return "test-1258-counting-source"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        self.fetch_calls += 1
        return [self._alert]


# ═══════════════════════════════ AC-4 ════════════════════════════════════════

class TestAC4NewEntityDefaultsDisabled:
    def test_bare_trip_constructor_defaults_official_warnings_disabled(self):
        """AC-4: ein frisch im Speicher konstruierter Trip (kein Bestandsfeld
        gesetzt) traegt `official_warnings.enabled = False` — bewusster
        Verhaltenswechsel NUR fuer Neuanlagen (PO-Entscheidung F1).

        RED: `Trip.__init__()` kennt `official_warnings` noch nicht als
        Attribut -> AttributeError beim Zugriff.
        """
        trip = Trip(id="trip-ac4-new", name="Neuanlage", stages=[_stage()])

        assert trip.official_warnings == {"enabled": False}, (
            "Neuanlage muss enabled=false als Default tragen, erhalten: "
            f"{getattr(trip, 'official_warnings', 'FEHLT')!r}"
        )

    def test_bare_compare_preset_constructor_defaults_official_warnings_disabled(self):
        """AC-4 (ComparePreset-Analogon): dieselbe Default-Regel gilt fuer
        neu angelegte Ortsvergleiche.

        RED: `ComparePreset.__init__()` kennt `official_warnings` noch nicht.
        """
        from app.models import ComparePreset

        preset = ComparePreset(id="preset-ac4-new", name="Neuanlage")

        assert preset.official_warnings == {"enabled": False}, (
            "Neuanlage muss enabled=false als Default tragen, erhalten: "
            f"{getattr(preset, 'official_warnings', 'FEHLT')!r}"
        )

    def test_loaded_legacy_trip_without_field_stays_unmigrated_none(self):
        """Abgrenzung: ein aus einer BESTEHENDEN JSON-Datei geladener Trip
        ohne `official_warnings`-Schluessel ist NICHT dasselbe wie eine
        Neuanlage — er bleibt `None` (= „noch nicht migriert"), sonst waere
        die Batch-Migration (AC-1..AC-3) ueberfluessig/wirkungslos, weil
        jeder geladene Bestandstrip faelschlich sofort enabled=false zeigen
        wuerde.

        RED: `load_trip_from_dict()` kennt das Feld noch nicht -> der
        geladene Trip hat gar kein `official_warnings`-Attribut.
        """
        from app.loader import load_trip_from_dict

        data = {
            "id": "trip-ac4-legacy",
            "name": "Bestandstrip",
            "stages": [],
            "official_alert_triggers_enabled": True,
        }
        loaded = load_trip_from_dict(data)

        assert loaded.official_warnings is None, (
            "Ein geladener Bestandstrip ohne official_warnings-Schluessel "
            "muss None bleiben (noch nicht migriert), NICHT den "
            f"Neuanlage-Default: {getattr(loaded, 'official_warnings', 'FEHLT')!r}"
        )


# ═══════════════════════════════ AC-5 ════════════════════════════════════════

class TestAC5TwoUserIsolation:
    def test_official_warnings_change_for_user_a_does_not_affect_user_b(self):
        """AC-5: Nutzer A aendert `official_warnings` seines Trips — der
        gleichnamige Trip von Nutzer B bleibt unveraendert (Isolation ueber
        user_id, kein Cross-User-Leck, PFLICHT-Test lt. CLAUDE.md).

        RED: `Trip(..., official_warnings=...)` ist kein gueltiger Kwarg ->
        TypeError beim Aufbau der Fixture.
        """
        from app import loader
        from app.loader import load_trip, save_trip

        user_a = _fresh_user("ac5a")
        user_b = _fresh_user("ac5b")
        _clean_user(user_a)
        _clean_user(user_b)
        try:
            trip_a = Trip(
                id="trip-shared-id", name="Trip A", stages=[_stage()],
                official_warnings={"enabled": True, "sources": ["meteofrance_vigilance"]},
            )
            trip_b = Trip(
                id="trip-shared-id", name="Trip B", stages=[_stage()],
                official_warnings={"enabled": False},
            )
            save_trip(trip_a, user_id=user_a)
            save_trip(trip_b, user_id=user_b)

            # Nutzer A schaltet amtliche Warnungen aus (Aenderung). data_dir
            # explizit ueber loader.get_data_root() (statt hartem "data")
            # bestimmt: muss zum data_dir-losen save_trip() oben denselben
            # Root treffen, sonst greift unter der autouse-Isolation
            # (tests/conftest.py _isolate_data_root) ein anderer Root als
            # beim Schreiben (Bugfix im Rahmen der S1-Implementierung, kein
            # Verhaltenswechsel der Assertion selbst).
            data_root = str(loader.get_data_root())
            reloaded_a = load_trip("trip-shared-id", data_dir=data_root, user_id=user_a)
            reloaded_a.official_warnings = {"enabled": False}
            save_trip(reloaded_a, user_id=user_a)

            final_b = load_trip("trip-shared-id", data_dir=data_root, user_id=user_b)
            assert final_b.official_warnings == {"enabled": False}, (
                "Nutzer B's Trip hatte von Anfang an enabled=false — Aenderung "
                f"bei Nutzer A darf ihn nicht beruehren, erhalten: {final_b.official_warnings!r}"
            )
            assert final_b.name == "Trip B", "Cross-User-Leck: falscher Trip-Inhalt geladen"
        finally:
            _clean_user(user_a)
            _clean_user(user_b)


# ═══════════════════════════════ AC-6 ════════════════════════════════════════

class TestAC6PipelinePrefersNewFieldOverLegacy:
    def test_check_official_alert_triggers_reads_official_warnings_not_legacy(self):
        """AC-6: Trip mit `official_warnings.enabled = False` ABER
        `official_alert_triggers_enabled = True` (Konflikt-Fixture) -> die
        Pipeline muss das NEUE Feld befolgen und KEINEN Alarm/Fetch ausloesen
        — unabhaengig vom weiterhin gespeicherten Legacy-Wert.

        RED: `Trip(..., official_warnings=...)` ist kein gueltiger Kwarg ->
        TypeError beim Fixture-Aufbau (heutiger Code kennt nur das Legacy-
        Feld und wuerde faelschlich fetchen/alarmieren).
        """
        from services.official_alerts import OfficialAlert, register_official_alert_source
        from services.trip_alert import TripAlertService

        user_id = _fresh_user("ac6")
        _clean_user(user_id)
        oa_base, backup = _registered_sources_backup()
        oa_base._REGISTERED_SOURCES.clear()
        try:
            trip = Trip(
                id="trip-ac6-conflict", name="Konflikt-Trip", stages=[_stage()],
                official_warnings={"enabled": False},
                official_alert_triggers_enabled=True,
            )
            trip.report_config = TripReportConfig(trip_id=trip.id, send_email=True)
            _save_cached(user_id, trip.id)

            alert = OfficialAlert(
                source="test-1258-ac6", hazard="thunderstorm", level=3,
                label="Darf NICHT erscheinen (#1258 AC-6)",
            )
            counting_source = _CountingOfficialAlertSource(LAT, LON, alert)
            register_official_alert_source(counting_source)

            svc = TripAlertService(user_id=user_id)
            result = svc.check_official_alert_triggers(trip)

            assert result == [], (
                "official_warnings.enabled=False muss den Alarm verhindern, auch "
                f"wenn das Legacy-Feld noch True ist, erhalten: {result!r}"
            )
            assert counting_source.fetch_calls == 0, (
                "official_warnings.enabled=False muss den Fetch verhindern (Legacy-"
                f"Feld darf nicht mehr befragt werden), fetch_calls={counting_source.fetch_calls}"
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
            _clean_user(user_id)

    def test_check_official_alert_triggers_fires_when_official_warnings_enabled_true(self):
        """Kontrollfall zu AC-6: `official_warnings.enabled = True` ABER
        `official_alert_triggers_enabled = False` (umgekehrter Konflikt) ->
        die Pipeline MUSS trotzdem feuern, weil das neue Feld allein
        massgeblich ist.

        RED: gleicher Grund wie oben — Kwarg existiert noch nicht.
        """
        from services.official_alerts import OfficialAlert, register_official_alert_source
        from services.trip_alert import TripAlertService

        user_id = _fresh_user("ac6b")
        _clean_user(user_id)
        oa_base, backup = _registered_sources_backup()
        oa_base._REGISTERED_SOURCES.clear()
        try:
            trip = Trip(
                id="trip-ac6-reverse-conflict", name="Konflikt-Trip-2", stages=[_stage()],
                official_warnings={"enabled": True},
                official_alert_triggers_enabled=False,
            )
            trip.report_config = TripReportConfig(trip_id=trip.id, send_email=True)
            _save_cached(user_id, trip.id)

            alert = OfficialAlert(
                source="test-1258-ac6b", hazard="wind", level=2,
                label="Muss erscheinen (#1258 AC-6 Kontrollfall)",
            )
            counting_source = _CountingOfficialAlertSource(LAT, LON, alert)
            register_official_alert_source(counting_source)

            svc = TripAlertService(user_id=user_id)
            result = svc.check_official_alert_triggers(trip)

            assert len(result) == 1, (
                "official_warnings.enabled=True muss den Alarm ausloesen, auch wenn "
                f"das Legacy-Feld False ist, erhalten: {result!r}"
            )
            assert counting_source.fetch_calls >= 1
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
            _clean_user(user_id)

    def test_check_official_alert_triggers_treats_empty_dict_as_unmigrated_legacy_fallback(self):
        """Fix-Loop F003: `official_warnings = {}` (kein "enabled"-Schluessel
        — Datenmuell/abgebrochene Migration) darf NICHT als "migriert,
        enabled=true" (Default-True-Fail-Open von `.get('enabled', True)`)
        gelesen werden, sondern muss wie `None` auf das Legacy-Feld
        zurueckfallen. Legacy-Feld hier bewusst False -> kein Fetch/Alarm.
        """
        from services.official_alerts import OfficialAlert, register_official_alert_source
        from services.trip_alert import TripAlertService

        user_id = _fresh_user("ac6-f003")
        _clean_user(user_id)
        oa_base, backup = _registered_sources_backup()
        oa_base._REGISTERED_SOURCES.clear()
        try:
            trip = Trip(
                id="trip-ac6-f003-empty", name="Leeres-Objekt-Trip", stages=[_stage()],
                official_warnings={},
                official_alert_triggers_enabled=False,
            )
            trip.report_config = TripReportConfig(trip_id=trip.id, send_email=True)
            _save_cached(user_id, trip.id)

            alert = OfficialAlert(
                source="test-1258-ac6-f003", hazard="wind", level=2,
                label="Darf NICHT erscheinen (F003 Legacy-Fallback)",
            )
            counting_source = _CountingOfficialAlertSource(LAT, LON, alert)
            register_official_alert_source(counting_source)

            svc = TripAlertService(user_id=user_id)
            result = svc.check_official_alert_triggers(trip)

            assert result == [], (
                "F003: official_warnings={} muss wie None auf das Legacy-Feld "
                f"(hier False) zurueckfallen -> kein Alarm, erhalten: {result!r}"
            )
            assert counting_source.fetch_calls == 0, (
                "F003: kein Fetch, da Legacy-Fallback official_alert_triggers_enabled=False greift, "
                f"fetch_calls={counting_source.fetch_calls}"
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
            _clean_user(user_id)
