"""TDD RED — Issue #1088 (Epic #1073 Slice 4): Amtliche Warnungen als
eigenständiger Alert-Trigger.

SPEC: docs/specs/modules/issue_1088_alert_official_warnings.md
AC-1..AC-7

Verhaltenstests — KEINE Mocks. Echte Fake-Quellen (strukturelles
Protocol-Subtyping von OfficialAlertSource) über register_official_alert_source(),
echte TripAlertService-Läufe, echte alert_state-Persistenz, mail_sink-DI-Seam
(Projektkonvention — kein Mock()/patch()/MagicMock, s. test_issue_1070/test_818).

RED-Ursache (heute, vor der Implementierung):
- `TripAlertService.check_official_alert_triggers()` existiert noch nicht ->
  AttributeError bei jedem AC-1/AC-2/AC-4/AC-6-Test.
- `Trip.official_alert_triggers_enabled` existiert nicht als Konstruktor-Kwarg
  -> TypeError bei AC-2/AC-3.
- `TripAlertService.check_and_send_alerts()` kennt den Kwarg
  `official_notices` noch nicht -> TypeError bei AC-5.
- `NotificationService.send_deviation_alert()` kennt den Kwarg
  `official_notices` noch nicht -> TypeError bei AC-7.
"""
from __future__ import annotations

import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from app.models import (
    ChangeSeverity,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
    UnifiedWeatherDisplayConfig,
    WeatherChange,
)
from app.trip import Stage, Trip, Waypoint

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

LAT, LON = 47.0, 11.0


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _fresh_user(prefix: str) -> str:
    return f"tdd-1088-{prefix}-{uuid.uuid4().hex[:6]}"


def _segment(segment_id: int | str = 1, *, lat: float = LAT, lon: float = LON) -> TripSegment:
    start = datetime(2026, 7, 8, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=1000, distance_from_start_km=12.0),
        end_point=GPXPoint(lat=lat + 0.1, lon=lon + 0.1, elevation_m=1500, distance_from_start_km=18.0),
        start_time=start,
        end_time=end,
        duration_hours=4.0,
        distance_km=6.0,
        ascent_m=500,
        descent_m=0,
    )


def _data(segment_id: int | str = 1, *, lat: float = LAT, lon: float = LON, **summary_kwargs) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(segment_id, lat=lat, lon=lon),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _minimal_trip(trip_id: str, **trip_kwargs) -> Trip:
    """Trip ohne aktive Wetter-Delta-Regeln — für reine Trigger-Detektionstests.

    Issue #1258: `official_warnings=None` als Default, sofern der Aufrufer
    nichts anderes mitgibt — repraesentiert einen NOCH NICHT migrierten
    Bestandstrip (wie er per `load_trip()` aus einer Alt-Datei ohne den
    neuen Schluessel kaeme), NICHT den Neuanlage-Default `enabled=false`
    des blanken Konstruktors (AC-4). Ohne diese Unterscheidung wuerden alle
    hier gebauten Fixtures faelschlich als "amtliche Warnungen deaktiviert"
    gelten.
    """
    trip_kwargs.setdefault("official_warnings", None)
    stage = Stage(
        id="T1", name="Tag 1", date=date(2026, 7, 8),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(id=trip_id, name="Amtliche-Warnung-Trip", stages=[stage], **trip_kwargs)
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=True)
    return trip


def _delta_trip(trip_id: str, **trip_kwargs) -> Trip:
    """Trip mit aktiver metric_alert_levels-Regel (precipitation_sum) — löst bei
    ausreichendem Delta einen Wetter-Delta-Alert aus (Muster: test_issue_816).

    Issue #1258: `official_warnings=None`-Default s. `_minimal_trip`.
    """
    trip_kwargs.setdefault("official_warnings", None)
    stage = Stage(
        id="T1", name="Tag 1", date=date(2026, 7, 8),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(
        id=trip_id, name="Delta-Trip", stages=[stage],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=[MetricConfig(metric_id="precipitation", enabled=True)],
            metric_alert_levels={"precipitation_sum": "standard"},
        ),
        **trip_kwargs,
    )
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=True, alert_on_changes=True)
    return trip


def _save_cached(user_id: str, trip_id: str, cached: list[SegmentWeatherData]) -> None:
    from services.weather_snapshot import WeatherSnapshotService

    # Testfehler-Korrektur: reale Signatur ist save_dated(trip_id, target_date,
    # segments) — nicht (trip_id, segments, target_date).
    WeatherSnapshotService(user_id=user_id).save_dated(trip_id, date.today(), cached)


class _CountingOfficialAlertSource:
    """Echte Quelle (kein Mock), zuständig für einen Punkt (0.05-Grad-Toleranz),
    liefert genau einen OfficialAlert und zählt jeden fetch()-Aufruf."""

    def __init__(self, lat: float, lon: float, alert) -> None:
        self._lat = lat
        self._lon = lon
        self._alert = alert
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return "test-1088-counting-source"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        self.fetch_calls += 1
        return [self._alert]


class _ErroringOfficialAlertSource:
    """Echte, strukturell fehlerhafte Quelle — wirft bei fetch() immer eine
    RuntimeError (simulierter Quellenausfall, AC-4)."""

    def __init__(self, lat: float, lon: float) -> None:
        self._lat = lat
        self._lon = lon
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return "test-1088-erroring-source"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        self.fetch_calls += 1
        raise RuntimeError("simulierter Quellenausfall (#1088 AC-4)")


class _LevelControllableOfficialAlertSource:
    """Echte Quelle mit von aussen steuerbarem Level (AC-6 Dedupe-Eskalation)."""

    def __init__(self, lat: float, lon: float, hazard: str, region_label: str) -> None:
        self._lat = lat
        self._lon = lon
        self._hazard = hazard
        self._region_label = region_label
        self.level = 2

    @property
    def name(self) -> str:
        return "test-1088-level-source"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        from services.official_alerts import OfficialAlert

        return [OfficialAlert(
            source="test-1088-level", hazard=self._hazard, level=self.level,
            label=f"Warnung {self._hazard} Level {self.level}",
            region_label=self._region_label,
        )]


def _registered_sources_backup():
    import services.official_alerts.base as oa_base
    return oa_base, list(oa_base._REGISTERED_SOURCES)


class TestAC1StandaloneTrigger:
    def test_detects_new_official_alert_independent_of_weather_delta(self):
        """AC-1: Stabiles Wetter (kein Delta-Setup), neue amtliche Warnung an
        der Segment-Koordinate -> check_official_alert_triggers() liefert sie.

        RED: TripAlertService.check_official_alert_triggers() existiert noch
        nicht -> AttributeError.
        """
        from services.official_alerts import OfficialAlert, register_official_alert_source
        from services.trip_alert import TripAlertService

        user_id = _fresh_user("ac1")
        _clean_user(user_id)
        oa_base, backup = _registered_sources_backup()
        oa_base._REGISTERED_SOURCES.clear()
        try:
            trip = _minimal_trip("trip-ac1")
            _save_cached(user_id, trip.id, [_data(1, precip_sum_mm=2.0)])

            alert = OfficialAlert(
                source="test-1088-ac1", hazard="thunderstorm", level=3,
                label="Gewitterwarnung Stufe Orange #1088",
            )
            counting_source = _CountingOfficialAlertSource(LAT, LON, alert)
            register_official_alert_source(counting_source)

            svc = TripAlertService(user_id=user_id)
            result = svc.check_official_alert_triggers(trip)

            assert len(result) == 1, (
                f"Erwartet genau 1 neue amtliche Warnung, erhalten: {result!r}"
            )
            # Issue #1200: Rückgabe sind (OfficialAlert, segment_ids)-Tupel.
            assert result[0][0].label == alert.label
            assert counting_source.fetch_calls >= 1
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
            _clean_user(user_id)


class TestAC2ToggleDisabled:
    def test_toggle_false_prevents_fetch_and_returns_no_alerts(self):
        """AC-2: official_alert_triggers_enabled=False -> Fake-Quelle wird
        über den Trigger-Pfad NICHT aufgerufen (Call-Counter=0), kein Alert.

        RED: `Trip` kennt `official_alert_triggers_enabled` noch nicht als
        Konstruktor-Kwarg -> TypeError beim Trip-Aufbau.
        """
        from services.official_alerts import OfficialAlert, register_official_alert_source
        from services.trip_alert import TripAlertService

        user_id = _fresh_user("ac2")
        _clean_user(user_id)
        oa_base, backup = _registered_sources_backup()
        oa_base._REGISTERED_SOURCES.clear()
        try:
            trip = _minimal_trip("trip-ac2", official_alert_triggers_enabled=False)
            assert trip.official_alerts_enabled is None, (
                "Slice-3-Briefing-Checkbox darf vom neuen Trigger-Toggle "
                "strukturell unberührt bleiben"
            )
            _save_cached(user_id, trip.id, [_data(1, precip_sum_mm=2.0)])

            alert = OfficialAlert(
                source="test-1088-ac2", hazard="thunderstorm", level=3,
                label="Darf NICHT erscheinen (#1088 AC-2)",
            )
            counting_source = _CountingOfficialAlertSource(LAT, LON, alert)
            register_official_alert_source(counting_source)

            svc = TripAlertService(user_id=user_id)
            result = svc.check_official_alert_triggers(trip)

            assert counting_source.fetch_calls == 0, (
                f"official_alert_triggers_enabled=False muss den Fetch verhindern, "
                f"aber fetch() wurde {counting_source.fetch_calls}x aufgerufen"
            )
            assert result == []
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
            _clean_user(user_id)


class TestAC3LoaderRoundtripPersistence:
    def test_save_load_roundtrip_preserves_official_alert_triggers_enabled(self, tmp_path):
        """AC-3 (Python-Teil, RMW-Vorbedingung): Feld übersteht einen echten
        save_trip()/load_trip()-Roundtrip, andere Felder bleiben unverändert
        (BUG-DATALOSS-GR221 — kein Datenverlust).

        RED: `Trip`-Dataclass kennt `official_alert_triggers_enabled` noch
        nicht als Konstruktor-Kwarg -> TypeError bereits beim Trip-Aufbau.
        """
        from app.loader import load_trip, save_trip

        wp = Waypoint(id="w1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)
        stage = Stage(id="s1", name="Tag 1", date=date(2026, 7, 8), waypoints=[wp])
        trip = Trip(
            id="tdd-1088-loader-roundtrip",
            name="Roundtrip Trip",
            stages=[stage],
            alert_rules=[],
            official_alert_triggers_enabled=True,
        )
        user_id = "tdd-1088-loader"

        save_trip(trip, user_id=user_id, data_dir=str(tmp_path))
        loaded = load_trip(trip.id, data_dir=str(tmp_path), user_id=user_id)

        assert loaded is not None
        assert loaded.official_alert_triggers_enabled is True, (
            "official_alert_triggers_enabled=True muss erhalten bleiben, geladen: "
            f"{getattr(loaded, 'official_alert_triggers_enabled', 'FEHLT')!r}"
        )
        assert loaded.name == "Roundtrip Trip", "Read-Modify-Write darf andere Felder nicht verändern"
        assert len(loaded.stages) == 1 and loaded.stages[0].id == "s1"


class TestAC4FailSoft:
    def test_erroring_source_does_not_propagate_and_other_trip_stays_unaffected(self):
        """AC-4: Quellenausfall (RuntimeError bei fetch()) darf den Alert-Zyklus
        nicht crashen — ein betroffener Trip liefert still [] zurück, ein
        unbetroffener Trip (andere Koordinate, andere Quelle) bleibt normal
        funktionsfähig.

        RED: `check_official_alert_triggers()` existiert noch nicht -> AttributeError.
        """
        from services.official_alerts import OfficialAlert, register_official_alert_source
        from services.trip_alert import TripAlertService

        user_id = _fresh_user("ac4")
        _clean_user(user_id)
        oa_base, backup = _registered_sources_backup()
        oa_base._REGISTERED_SOURCES.clear()
        try:
            trip_affected = _minimal_trip("trip-ac4-affected")
            _save_cached(user_id, trip_affected.id, [_data(1, lat=LAT, lon=LON, precip_sum_mm=2.0)])

            other_lat, other_lon = LAT + 5.0, LON + 5.0
            trip_unaffected = _minimal_trip("trip-ac4-unaffected")
            _save_cached(
                user_id, trip_unaffected.id,
                [_data(1, lat=other_lat, lon=other_lon, precip_sum_mm=2.0)],
            )

            erroring_source = _ErroringOfficialAlertSource(LAT, LON)
            register_official_alert_source(erroring_source)

            good_alert = OfficialAlert(
                source="test-1088-ac4-good", hazard="wind", level=2,
                label="Unbetroffene Warnung (#1088 AC-4)",
            )
            good_source = _CountingOfficialAlertSource(other_lat, other_lon, good_alert)
            register_official_alert_source(good_source)

            svc = TripAlertService(user_id=user_id)

            result_affected = svc.check_official_alert_triggers(trip_affected)
            assert result_affected == [], (
                "Betroffener Trip: fail-soft muss [] liefern statt einer Exception"
            )
            assert erroring_source.fetch_calls >= 1

            result_unaffected = svc.check_official_alert_triggers(trip_unaffected)
            assert len(result_unaffected) == 1, (
                f"Unbetroffener Trip muss weiterhin normal geprüft werden, erhalten: "
                f"{result_unaffected!r}"
            )
            # Issue #1200: Rückgabe sind (OfficialAlert, segment_ids)-Tupel.
            assert result_unaffected[0][0].label == good_alert.label
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
            _clean_user(user_id)


class TestAC5Bundling:
    def test_single_send_bundles_weather_delta_and_official_notice(self):
        """AC-5: Wetter-Delta UND neue amtliche Warnung im selben Zyklus ->
        genau EIN Versand (kein zweiter Alert).

        RED: `check_and_send_alerts()` kennt den Kwarg `official_notices`
        noch nicht -> TypeError (gültiges RED, analog test_issue_1040).
        """
        from services.official_alerts import OfficialAlert, register_official_alert_source
        from services.trip_alert import TripAlertService

        user_id = _fresh_user("ac5")
        _clean_user(user_id)
        oa_base, backup = _registered_sources_backup()
        oa_base._REGISTERED_SOURCES.clear()
        try:
            trip = _delta_trip("trip-ac5")
            trip.alert_cooldown_minutes = 0

            cached = [_data(1, precip_sum_mm=2.0)]
            fresh = [_data(1, precip_sum_mm=18.0)]  # Δ=16 > Katalog-Schwelle 10
            # Testfehler-Korrektur: check_official_alert_triggers() ermittelt die
            # Segment-Koordinaten über _get_cached_weather() (Snapshot-Datei) —
            # ohne diesen Persistenz-Schritt bliebe die Quelle unerreichbar.
            _save_cached(user_id, trip.id, cached)

            alert = OfficialAlert(
                source="test-1088-ac5", hazard="thunderstorm", level=3,
                label="Gebündelte Warnung (#1088 AC-5)",
            )
            register_official_alert_source(_CountingOfficialAlertSource(LAT, LON, alert))

            mail_calls: list = []
            svc = TripAlertService(
                user_id=user_id,
                mail_sink=lambda subject, body: mail_calls.append((subject, body)),
            )

            official_notices = svc.check_official_alert_triggers(trip)
            assert len(official_notices) == 1

            sent = svc.check_and_send_alerts(
                trip, cached, fresh_weather=fresh, official_notices=official_notices,
            )

            assert sent is True, "Erwartet genau EIN erfolgreicher Alert-Versand"
            assert len(mail_calls) == 1, (
                f"Erwartet genau 1 Mail-Versand (Bündelung), erhalten: {len(mail_calls)}"
            )
            _, body = mail_calls[0]
            # Adversary F002 (warnmail): der eingebettete Plain-Zusatz zeigt
            # seit dem Fix `_display_label(alert)` statt des rohen
            # `alert.label` -- fuer ein hazard="thunderstorm"-Label ohne
            # Bezug zum deutschen Typ-Wort ("Gebündelte Warnung...") ersetzt
            # `_display_label` es durch "Gewitter" (Fall (d), kein Regress:
            # die Warnung selbst ist weiterhin im Body vorhanden).
            from output.renderers.alert.official_alerts import _display_label
            assert _display_label(alert) in body, "Amtliche Warnung fehlt im gebündelten Alert-Body"
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
            _clean_user(user_id)


class TestAC6Dedupe:
    def test_same_level_deduped_then_escalation_fires_again(self):
        """AC-6: Level 2 gemeldet -> Level 2 erneut (dedupe, kein Ergebnis) ->
        Level 3 (Eskalation, erneut im Ergebnis).

        RED: `check_official_alert_triggers()` existiert noch nicht -> AttributeError.
        """
        from services.alert_state import AlertStateService
        from services.official_alerts import register_official_alert_source
        from services.trip_alert import TripAlertService

        user_id = _fresh_user("ac6")
        _clean_user(user_id)
        oa_base, backup = _registered_sources_backup()
        oa_base._REGISTERED_SOURCES.clear()
        try:
            trip = _minimal_trip("trip-ac6")
            _save_cached(user_id, trip.id, [_data(1, precip_sum_mm=2.0)])

            hazard, region_label = "avalanche", "Massif-1088"
            level_source = _LevelControllableOfficialAlertSource(LAT, LON, hazard, region_label)
            register_official_alert_source(level_source)

            svc = TripAlertService(user_id=user_id)
            state_svc = AlertStateService(user_id=user_id)

            # Runde 1: Level 2, noch nie gemeldet -> feuert.
            level_source.level = 2
            round1 = svc.check_official_alert_triggers(trip)
            assert len(round1) == 1, f"Runde 1 (Level 2, neu) muss feuern, erhalten: {round1!r}"

            # Simuliert erfolgreichen Versand: alert_state über die echte
            # Produktionslogik fortschreiben (nicht über ein hartkodiertes State-Key-Format).
            svc._record_official_alert_state(trip.id, round1)

            # Runde 2: weiterhin Level 2 -> Dedupe, kein erneuter Alert.
            round2 = svc.check_official_alert_triggers(trip)
            assert round2 == [], f"Runde 2 (unveränderter Level 2) muss dedupliziert werden, erhalten: {round2!r}"

            # Runde 3: Level steigt auf 3 -> erneuter Alert (Eskalation).
            level_source.level = 3
            round3 = svc.check_official_alert_triggers(trip)
            assert len(round3) == 1, f"Runde 3 (Eskalation auf Level 3) muss erneut feuern, erhalten: {round3!r}"
            # Issue #1200: Rückgabe sind (OfficialAlert, segment_ids)-Tupel.
            assert round3[0][0].level == 3
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
            _clean_user(user_id)


class TestF001OfficialTriggerViaCheckAllTrips:
    def test_check_all_trips_fires_official_alert_when_weather_delta_disabled(self):
        """Adversary Finding F001 (Verdict BROKEN, Runde 2): check_all_trips()
        darf einen Trip mit deaktiviertem Wetter-Delta-Alert
        (alert_on_changes=False, keine aktive Regel) NICHT komplett
        überspringen, solange der eigenständige amtliche Trigger
        (official_alert_triggers_enabled != False) grundsätzlich aktiv ist.

        RED (vor dem Fix): check_all_trips() `continue`t
        (trip_alert.py:346-349) BEVOR check_official_alert_triggers()
        aufgerufen wird -> counting_source.fetch_calls bleibt 0,
        alerts_sent bleibt 0.
        """
        from app.loader import save_trip
        from services.official_alerts import OfficialAlert, register_official_alert_source
        from services.trip_alert import TripAlertService

        user_id = _fresh_user("f001")
        _clean_user(user_id)
        oa_base, backup = _registered_sources_backup()
        oa_base._REGISTERED_SOURCES.clear()
        try:
            stage = Stage(
                id="T1", name="Tag 1", date=date.today(),
                waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
            )
            # Issue #1258: official_warnings=None (noch nicht migrierter
            # Bestandstrip) statt Neuanlage-Default enabled=false — sonst
            # wuerde save_trip() unten faelschlich "deaktiviert" persistieren.
            trip = Trip(
                id="trip-f001", name="Kein-Wetter-Delta-Trip", stages=[stage],
                official_warnings=None,
            )
            # Wetter-Delta-Alert vom Nutzer explizit deaktiviert, keine aktive Regel
            # (kein preset, keine metric_alert_levels, keine alert_rules).
            trip.report_config = TripReportConfig(
                trip_id=trip.id, send_email=True, alert_on_changes=False,
            )
            # official_alert_triggers_enabled bleibt None -> Default = aktiv.
            save_trip(trip, user_id=user_id)
            _save_cached(user_id, trip.id, [_data(1, precip_sum_mm=2.0)])

            alert = OfficialAlert(
                source="test-1088-f001", hazard="thunderstorm", level=3,
                label="Eigenständiger Trigger trotz alert_on_changes=False (#1088 F001)",
            )
            counting_source = _CountingOfficialAlertSource(LAT, LON, alert)
            register_official_alert_source(counting_source)

            mail_calls: list = []
            svc = TripAlertService(
                user_id=user_id,
                mail_sink=lambda subject, body: mail_calls.append((subject, body)),
            )

            alerts_sent = svc.check_all_trips()

            assert counting_source.fetch_calls >= 1, (
                "check_official_alert_triggers() wurde nie erreicht — der "
                "Wetter-Delta-Gate hat den Trip komplett übersprungen (F001)"
            )
            assert alerts_sent == 1, f"Erwartet genau 1 versendeter Alert, erhalten: {alerts_sent}"
            assert len(mail_calls) == 1, (
                f"Erwartet genau 1 Mail-Versand, erhalten: {len(mail_calls)}"
            )
            _, body = mail_calls[0]
            # ADR-0033/Befund 2 (#1326b): das Test-Label traegt keine echte
            # Zusatzinfo (kein Massiv-Name, kein "—"-Separator, keine
            # Erweiterung des Typ-Worts) -- _display_label zeigt daher nur
            # das gemappte deutsche Typ-Wort ("Gewitter" fuer "thunderstorm"),
            # nicht das rohe Test-Label. Die Quelle bleibt als Beleg im Body.
            assert "Gewitter" in body, "Amtliche Warnung (Typ-Wort) fehlt im eigenständig versendeten Alert-Body"
            assert alert.source in body, "Warnquelle fehlt im eigenständig versendeten Alert-Body"
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
            _clean_user(user_id)


class TestAC7SmsWithoutParity:
    def test_sms_render_unaffected_email_gets_official_notice_appended(self):
        """AC-7: SMS bleibt ohne Zusatztext für die amtliche Warnung (bewusste
        Nicht-Parität, analog Slice-3-AC-6); die E-Mail (via mail_sink-DI-Seam,
        kein echter Netzwerk-Call) enthält den Zusatz.

        RED: `_dispatch_alert_message()` kennt den Kwarg `official_notices`
        noch nicht -> TypeError.
        """
        from app.config import Settings
        from output.renderers.alert.project import to_alert_message
        from output.renderers.alert.render import render_sms as render_alert_sms
        from services.notification_service import NotificationService
        from services.official_alerts import OfficialAlert

        user_id = _fresh_user("ac7")
        _clean_user(user_id)
        try:
            weather = [_data(1, precip_sum_mm=18.0)]
            change = WeatherChange(
                metric="precip_sum_mm", old_value=2.0, new_value=18.0, delta=16.0,
                threshold=10.0, severity=ChangeSeverity.MODERATE, direction="increase",
                segment_id="1",
            )
            alert = OfficialAlert(
                source="test-1088-ac7", hazard="thunderstorm", level=3,
                label="SMS darf mich nicht enthalten (#1088 AC-7)",
            )
            alert_msg = to_alert_message(
                [change], weather, "AC7-Trip", tz=timezone.utc, stand_at="08:00",
            )
            sms_before = render_alert_sms(alert_msg)

            settings = Settings(
                smtp_host="smtp.test.invalid", smtp_user="t@test.invalid",
                smtp_pass="x", mail_to="to@test.invalid",
            )
            notification_service = NotificationService(settings, user_id)

            mail_calls: list = []
            # Issue #1200: official_notices sind (OfficialAlert, segment_ids)-Tupel.
            notification_service._dispatch_alert_message(
                alert_msg=alert_msg,
                effective_channels={"email"},
                mail_sink=lambda subject, body: mail_calls.append((subject, body)),
                official_notices=[(alert, [])],
            )

            assert len(mail_calls) == 1
            _, body = mail_calls[0]
            # Adversary F002 (warnmail): s. Begründung in TestAC5Bundling oben --
            # der eingebettete Plain-Zusatz zeigt `_display_label(alert)`, nicht
            # mehr das rohe `alert.label`.
            from output.renderers.alert.official_alerts import _display_label
            assert _display_label(alert) in body, (
                "E-Mail-Body muss den Zusatz für die amtliche Warnung enthalten"
            )

            sms_after = render_alert_sms(alert_msg)
            assert alert.label not in sms_after, "SMS-Rendering darf keinen Alert-Text-Zusatz enthalten"
            assert sms_after == sms_before, "SMS-Ausgabe darf sich durch official_notices NICHT verändern"
        finally:
            _clean_user(user_id)
