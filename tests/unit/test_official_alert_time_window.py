"""RED — Issue #1316: Zeitfenster-Filter fuer amtliche Warnungen.

SPEC: docs/specs/modules/issue_1316_alert_time_window_filter.md (AC-1..AC-8)

Deterministischer Kern (Test-Politik Schicht 1, PO-go 2026-07-09): kein Netz,
keine Live-Dienste, keine echten Postfaecher. Alle Fixtures verwenden relative
Zeitstempel (``now +/- timedelta``) statt fixer Kalenderdaten (AC-8), damit
diese Suite nicht durch reines Zeitverstreichen falsch wird.

Weder ``filter_alerts_to_window`` noch die erweiterte Signatur von
``get_official_alerts_for_location(lat, lon, window_start=None,
window_end=None)`` existieren zum Zeitpunkt dieses Commits -> alle Tests sind
RED (ImportError/TypeError/AssertionError je nach betroffener Stelle).

Mock-frei: echte ``OfficialAlert``-DTOs, echte Fake-Quellen (strukturelles
Protocol-Subtyping von ``OfficialAlertSource``, analog
tests/tdd/test_official_alert_dedup_timespan.py), echte Registry-Injektion.
Der AC-7-Test nutzt einen schlanken Argument-Capture anstelle der Fetch-
Funktion (kein Mock-Theater, da er ausschliesslich die reale Verdrahtung
zwischen ``trip_report_scheduler.py`` und ``get_official_alerts_for_location``
beweist, keine eigene Verhaltensannahme zurueckspiegelt).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from services.official_alerts.models import OfficialAlert

LAT, LON = 47.0, 11.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _alert(
    *,
    hazard: str = "thunderstorm",
    level: int = 3,
    source: str = "test-source",
    label: str = "Warnung",
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    dedup_id: str | None = None,
) -> OfficialAlert:
    return OfficialAlert(
        source=source, hazard=hazard, level=level, label=label,
        valid_from=valid_from, valid_to=valid_to, dedup_id=dedup_id,
    )


def _registered_sources_backup():
    import services.official_alerts.base as oa_base
    return oa_base, list(oa_base._REGISTERED_SOURCES)


class _StaticOfficialAlertSource:
    """Echte Test-Quelle (kein Mock): liefert eine feste Alert-Liste fuer
    einen konkreten Punkt (strukturelles Protocol-Subtyping, analog den
    Fake-Quellen in test_official_alert_dedup_timespan.py)."""

    def __init__(self, lat: float, lon: float, alerts: list[OfficialAlert], name: str = "test-static-source") -> None:
        self._lat = lat
        self._lon = lon
        self._alerts = list(alerts)
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        return list(self._alerts)


# ---------------------------------------------------------------------------
# AC-1 / AC-4: abgelaufene Warnungen fliegen raus
# ---------------------------------------------------------------------------

class TestAC1And4ExpiredAlertsAreFilteredOut:
    def test_default_call_excludes_alert_expired_relative_to_real_now(self):
        """AC-4: get_official_alerts_for_location(lat, lon) OHNE Fenster-
        Argumente darf keine Warnung liefern, deren valid_to bereits in der
        Vergangenheit liegt (Default-Fenster [now, +inf))."""
        from services.official_alerts import (
            get_official_alerts_for_location,
            register_official_alert_source,
        )

        now = _now()
        expired = _alert(
            label="Laengst abgelaufenes Gewitter",
            valid_from=now - timedelta(hours=4),
            valid_to=now - timedelta(hours=2),
        )
        source = _StaticOfficialAlertSource(LAT, LON, [expired])

        oa_base, backup = _registered_sources_backup()
        oa_base._REGISTERED_SOURCES.clear()
        try:
            register_official_alert_source(source)
            result = get_official_alerts_for_location(LAT, LON)
            assert expired not in result, (
                f"Abgelaufene Warnung (valid_to={expired.valid_to}) darf im "
                f"Default-Fenster [now, +inf) nicht erscheinen, erhalten: {result!r}"
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)

    def test_alert_ending_before_tomorrow_stage_window_is_filtered(self):
        """AC-1 (Ur-Fall aus dem Issue): Abend-Briefing fuer die Etappe
        MORGEN -- eine Warnung, deren valid_to VOR dem Etappenfenster-Start
        liegt (Gewitter heute Nacht 00:00-01:00), darf im gefilterten
        Ergebnis nicht auftauchen."""
        from services.official_alerts.base import filter_alerts_to_window

        now = _now()
        window_start = now + timedelta(hours=14)  # Beginn der Etappe morgen
        window_end = now + timedelta(hours=24)
        thunderstorm_tonight = _alert(
            label="Gewitter 00:00-01:00",
            valid_from=now + timedelta(hours=1),
            valid_to=now + timedelta(hours=2),  # laengst vorbei, wenn Etappe morgen beginnt
        )

        result = filter_alerts_to_window([thunderstorm_tonight], window_start, window_end)

        assert thunderstorm_tonight not in result, (
            "Eine vor Etappenfenster-Beginn endende Warnung darf im gefilterten "
            f"Ergebnis nicht erscheinen, erhalten: {result!r}"
        )


# ---------------------------------------------------------------------------
# AC-2: Teilueberlappung genuegt
# ---------------------------------------------------------------------------

class TestAC2PartialOverlapIsKept:
    def test_alert_starting_before_window_and_ending_inside_stays(self):
        """AC-2: eine Warnung, die vor Fensterbeginn startet und innerhalb
        des Fensters endet, muss im Ergebnis erhalten bleiben."""
        from services.official_alerts.base import filter_alerts_to_window

        now = _now()
        window_start = now
        window_end = now + timedelta(hours=6)
        overlapping = _alert(
            label="Ueberlappende Warnung",
            valid_from=now - timedelta(hours=2),
            valid_to=now + timedelta(hours=1),
        )

        result = filter_alerts_to_window([overlapping], window_start, window_end)

        assert overlapping in result, (
            f"Teilweise ueberlappende Warnung muss erhalten bleiben, erhalten: {result!r}"
        )


# ---------------------------------------------------------------------------
# AC-3: Warnungen ohne Zeitangabe sind fail-safe immer dabei
# ---------------------------------------------------------------------------

class TestAC3TimelessAlertAlwaysKept:
    def test_alert_without_validity_window_survives_any_window(self):
        """AC-3: eine Warnung ohne valid_from/valid_to (z.B. Massiv-Sperre)
        bleibt unabhaengig vom uebergebenen Fenster erhalten (fail-safe)."""
        from services.official_alerts.base import filter_alerts_to_window

        now = _now()
        timeless = _alert(label="Massiv-Sperre ohne Zeitraum")
        assert timeless.valid_from is None and timeless.valid_to is None

        result = filter_alerts_to_window(
            [timeless], now + timedelta(days=3), now + timedelta(days=4)
        )

        assert timeless in result, (
            f"Warnung ohne Zeitangabe muss fail-safe erhalten bleiben, erhalten: {result!r}"
        )


# ---------------------------------------------------------------------------
# AC-5: Filter VOR Dedup -- abgelaufene starke Quelle darf gueltige schwache
# Quelle nicht verdraengen
# ---------------------------------------------------------------------------

class TestAC5FilterRunsBeforeDedup:
    def test_expired_stronger_source_does_not_swallow_valid_weaker_source(self):
        """AC-5: Quelle X (Level 3) ist bereits abgelaufen, Quelle Y (Level 2)
        derselben Gefahr ist noch gueltig. Der Zeitfenster-Filter muss VOR dem
        Zwei-Pass-Dedup laufen, sonst gewinnt X als 'beste Quelle' (hoechstes
        Level) in Pass 1 und verdraengt Y in Pass 2 -- Ergebnis waere dann
        leer statt der gueltigen Warnung von Y."""
        from services.official_alerts import (
            get_official_alerts_for_location,
            register_official_alert_source,
        )

        now = _now()
        hazard = "extreme_heat"
        expired_strong = _alert(
            source="source-x", hazard=hazard, level=3,
            label="Abgelaufene Hitzewarnung Quelle X",
            valid_from=now - timedelta(hours=6), valid_to=now - timedelta(hours=1),
        )
        valid_weak = _alert(
            source="source-y", hazard=hazard, level=2,
            label="Gueltige Hitzewarnung Quelle Y",
            valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=5),
        )
        source_x = _StaticOfficialAlertSource(LAT, LON, [expired_strong], name="source-x")
        source_y = _StaticOfficialAlertSource(LAT, LON, [valid_weak], name="source-y")

        oa_base, backup = _registered_sources_backup()
        oa_base._REGISTERED_SOURCES.clear()
        try:
            register_official_alert_source(source_x)
            register_official_alert_source(source_y)
            result = get_official_alerts_for_location(LAT, LON)
            heat = [a for a in result if a.hazard == hazard]
            assert len(heat) == 1 and heat[0].source == "source-y", (
                "Filter-vor-Dedup: die abgelaufene Level-3-Warnung von Quelle X darf "
                "die gueltige Level-2-Warnung von Quelle Y nicht verdraengen (leeres "
                f"Ergebnis waere der Bug), erhalten: {result!r}"
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-6: Regression #1245 -- zwei getrennte gueltige Zeitraeume derselben
# Quelle bleiben getrennt
# ---------------------------------------------------------------------------

class TestAC6TwoValidPeriodsSameSourceStayApart:
    def test_two_valid_periods_same_source_both_survive_new_filter(self):
        """AC-6: Regression #1245 mit relativen (statt fixen) Zeitstempeln --
        zwei getrennte, beide noch gueltige Perioden derselben Quelle
        (Vigilance Hitze) muessen auch mit aktivem Zeitfenster-Filter beide
        im Ergebnis erscheinen."""
        from services.official_alerts import (
            get_official_alerts_for_location,
            register_official_alert_source,
        )

        now = _now()
        hazard = "extreme_heat"
        period_a = _alert(
            source="meteo-france", hazard=hazard, level=3,
            label="Vigilance Hitze Periode A",
            valid_from=now + timedelta(hours=1), valid_to=now + timedelta(hours=10),
        )
        period_b = _alert(
            source="meteo-france", hazard=hazard, level=3,
            label="Vigilance Hitze Periode B",
            valid_from=now + timedelta(hours=10), valid_to=now + timedelta(hours=30),
        )
        source = _StaticOfficialAlertSource(LAT, LON, [period_a, period_b], name="meteo-france")

        oa_base, backup = _registered_sources_backup()
        oa_base._REGISTERED_SOURCES.clear()
        try:
            register_official_alert_source(source)
            result = get_official_alerts_for_location(
                LAT, LON, window_start=now, window_end=now + timedelta(hours=48),
            )
            assert len(result) == 2, (
                "Regression #1245: zwei getrennte gueltige Zeitraeume derselben Quelle "
                f"muessen trotz neuem Zeitfenster-Filter getrennt bleiben, erhalten: {result!r}"
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-7: Briefing-Pfad uebergibt exakt segments[0].start_time / segments[-1].end_time
# ---------------------------------------------------------------------------

class TestAC7BriefingPassesExactSegmentWindow:
    def test_scheduler_calls_with_first_segment_start_and_last_segment_end(self):
        """AC-7: trip_report_scheduler.py muss get_official_alerts_for_location()
        mit window_start=segments[0].start_time und window_end=segments[-1].end_time
        aufrufen -- keine parallele Neuberechnung des Etappenfensters (SSoT #822).

        Schlanker Capture (kein Mock-Theater): ersetzt NICHTS Wetter-/Netz-
        bezogenes, sondern ausschliesslich die tatsaechlich aufgerufene
        Funktion, um ihre Argumente zu protokollieren -- der Weather-Fetch
        selbst laeuft real ueber die Offline-FixtureProvider (tests/conftest.py
        autouse-Fixture, Issue #346), kein Netzwerkruf noetig.
        """
        from app.loader import load_trip_from_dict
        from services.trip_report_scheduler import TripReportSchedulerService
        import services.official_alerts as oa_pkg

        user_id = "unit-1316-ac7"
        trip_dict = {
            "id": "unit-1316-ac7-trip",
            "name": "AC7 Fenster-Test",
            "stages": [{
                "id": "s1",
                "name": "Etappe",
                "date": date.today().isoformat(),
                "waypoints": [
                    {"id": "w1", "name": "Start", "lat": LAT, "lon": LON, "elevation_m": 1000},
                    {"id": "w2", "name": "Ziel", "lat": LAT + 0.2, "lon": LON + 0.2, "elevation_m": 1500},
                ],
            }],
            "report_config": {"send_email": False, "send_sms": False, "send_telegram": False},
            "alert_rules": [],
        }
        trip = load_trip_from_dict(trip_dict)

        svc = TripReportSchedulerService(user_id=user_id)
        target_date = svc._get_target_date("morning")
        segments = svc._convert_trip_to_segments(trip, target_date)
        assert segments, "Testvoraussetzung: Etappe muss mindestens 1 Segment liefern"
        expected_start = segments[0].start_time
        expected_end = segments[-1].end_time

        captured: dict = {}
        original = oa_pkg.get_official_alerts_for_location

        def _capturing(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return []

        oa_pkg.get_official_alerts_for_location = _capturing
        try:
            svc.send_on_demand_report(trip, "morning")
        finally:
            oa_pkg.get_official_alerts_for_location = original

        assert captured, "get_official_alerts_for_location wurde beim Briefing-Lauf nicht aufgerufen"
        assert captured["kwargs"].get("window_start") == expected_start, (
            f"window_start muss segments[0].start_time ({expected_start!r}) sein, "
            f"erhalten: {captured['kwargs']!r}"
        )
        assert captured["kwargs"].get("window_end") == expected_end, (
            f"window_end muss segments[-1].end_time ({expected_end!r}) sein, "
            f"erhalten: {captured['kwargs']!r}"
        )


# ---------------------------------------------------------------------------
# Adversary F001 (HIGH): naive (tz-lose) Zeitstempel duerfen den Filter nicht
# mit TypeError zum Absturz bringen -- Quellen wie vigilance.py/meteoalarm.py
# liefern ohne "Z"/Offset im Rohstring naive datetimes. Das dokumentierte
# Versprechen "wirft selbst nie" (base.py) muss auch fuer diesen Fall gelten.
# ---------------------------------------------------------------------------

class TestF001NaiveTimestampsDoNotCrashTheFilter:
    def test_filter_alerts_to_window_accepts_naive_valid_to(self):
        """Naiver valid_to (kein tzinfo) neben einem aware window: kein
        TypeError, naiver Zeitstempel wird als UTC interpretiert."""
        from services.official_alerts.base import filter_alerts_to_window

        now = _now()
        window_start = now - timedelta(hours=1)
        window_end = now + timedelta(hours=1)
        naive_valid_to_alert = _alert(
            label="Naiver valid_to (kein tzinfo)",
            valid_from=(now - timedelta(hours=2)).replace(tzinfo=None),
            valid_to=now.replace(tzinfo=None),
        )

        result = filter_alerts_to_window([naive_valid_to_alert], window_start, window_end)

        assert naive_valid_to_alert in result, (
            f"Naiver Zeitstempel muss als UTC interpretiert und normal "
            f"gefiltert werden (kein Crash), erhalten: {result!r}"
        )

    def test_filter_alerts_to_window_accepts_naive_window_bounds(self):
        """Naives window_start/window_end (aus einem Aufrufer, der ebenfalls
        keine tzinfo mitbringt) neben aware Alert-Zeitstempeln: kein TypeError."""
        from services.official_alerts.base import filter_alerts_to_window

        now = _now()
        naive_window_start = (now - timedelta(hours=1)).replace(tzinfo=None)
        naive_window_end = (now + timedelta(hours=1)).replace(tzinfo=None)
        aware_alert = _alert(
            label="Aware Alert neben naivem Fenster",
            valid_from=now - timedelta(minutes=30),
            valid_to=now + timedelta(minutes=30),
        )

        result = filter_alerts_to_window([aware_alert], naive_window_start, naive_window_end)

        assert aware_alert in result, (
            f"Naives Fenster neben aware Alert-Zeitstempeln darf nicht crashen, "
            f"erhalten: {result!r}"
        )

    def test_get_official_alerts_for_location_never_raises_on_naive_source_timestamps(self):
        """End-to-end (AC-Analogie zu 'wirft selbst nie', base.py): eine Quelle,
        die naive Zeitstempel liefert (Realitaet unnormalisierter Parser),
        darf get_official_alerts_for_location() nicht mit TypeError abbrechen."""
        from services.official_alerts import (
            get_official_alerts_for_location,
            register_official_alert_source,
        )

        now = _now()
        naive_alert = _alert(
            label="Naive Quelle (unnormalisierter Parser)",
            valid_from=(now - timedelta(hours=1)).replace(tzinfo=None),
            valid_to=(now + timedelta(hours=1)).replace(tzinfo=None),
        )
        source = _StaticOfficialAlertSource(LAT, LON, [naive_alert])

        oa_base, backup = _registered_sources_backup()
        oa_base._REGISTERED_SOURCES.clear()
        try:
            register_official_alert_source(source)
            result = get_official_alerts_for_location(LAT, LON)  # darf nicht werfen
            assert naive_alert in result, (
                f"Naiver Zeitstempel muss normal als aktiv gefiltert werden, "
                f"erhalten: {result!r}"
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
