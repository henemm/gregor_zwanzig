"""Konfigurierbares Tagesfenster pro Wanderung (Epic #1319, Scheibe B+C).

Spec: docs/specs/modules/daywindow_configurable_window.md
Kontext: docs/context/issue-1319-slice-b.md
Vorgaenger: tests/tdd/test_sms_daywindow_aggregation.py (Scheibe A, festes
Fenster 04-19, Commit 087f643f) — diese Datei ersetzt/erweitert dessen
Grundannahme NICHT, sondern deckt die neue Konfigurierbarkeit ab.

TDD RED: `TripReportConfig` hat `day_window_start_hour`/`day_window_end_hour`
noch nicht, `build_day_window_points()` und `compute_has_gap()` akzeptieren
noch kein Fenster-Parameterpaar. Jeder Test hier schlaegt JETZT fehl.

Keine Mocks, keine Dateiinhalt-Checks. Reale Fixtures, reale Aufrufe, reale
Roundtrips ueber ein isoliertes `tmp_path`-Datenverzeichnis (Mandantentrennung
per echtem `save_trip()`/`load_trip()`-Dateipfad, kein API-Mock).
"""
from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from src.app.loader import load_trip, save_trip
from src.app.metric_catalog import build_default_display_config
from src.app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripReportConfig,
    TripSegment,
)
from src.app.trip import Stage, Trip, Waypoint
from src.output.renderers.day_window import build_day_window_points
from src.output.renderers.trip_report import TripReportFormatter
from src.services.notification_service import compute_has_gap

_YEAR, _MONTH = 2026, 7
_TZ = ZoneInfo("Europe/Paris")
_WALK_START_H = 8
_ARRIVAL_H = 12


# ---------------------------------------------------------------------------
# Gemeinsame Fixture-Helfer (Muster aus test_sms_daywindow_aggregation.py)
# ---------------------------------------------------------------------------

def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=datetime(_YEAR, _MONTH, 15, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0,
        interp="point_grid",
    )


def _local_to_utc(day: int, hour: int) -> datetime:
    local_dt = datetime(_YEAR, _MONTH, day, hour, 0, tzinfo=_TZ)
    return local_dt.astimezone(timezone.utc)


def _dp(day: int, hour: int, *, thunder: ThunderLevel = ThunderLevel.NONE) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=_local_to_utc(day, hour),
        t2m_c=15.0,
        wind10m_kmh=5.0,
        gust_kmh=5.0,
        precip_1h_mm=0.0,
        pop_pct=0,
        cloud_total_pct=50,
        thunder_level=thunder,
        humidity_pct=55,
    )


def _segment(
    day: int = 20,
    start_h: int = _WALK_START_H,
    end_h: int = _ARRIVAL_H,
    early_event: tuple[int, ThunderLevel] | None = None,
) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=600.0),
        start_time=_local_to_utc(day, start_h),
        end_time=_local_to_utc(day, end_h),
        duration_hours=float(end_h - start_h),
        distance_km=12.0,
        ascent_m=300.0,
        descent_m=0.0,
    )
    early_h, early_lvl = early_event if early_event else (None, ThunderLevel.NONE)
    data = [
        _dp(day, h, thunder=(early_lvl if h == early_h else ThunderLevel.NONE))
        for h in range(0, 24)
    ]
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0, temp_max_c=20.0, wind_max_kmh=15.0, gust_max_kmh=25.0,
            precip_sum_mm=0.0, thunder_level_max=ThunderLevel.NONE,
        ),
        fetched_at=datetime(_YEAR, _MONTH, day, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _night_weather(
    day: int = 20,
    arrival_h: int = _ARRIVAL_H,
    event_hour: int | None = 14,
    thunder: ThunderLevel = ThunderLevel.HIGH,
) -> NormalizedTimeseries:
    points: list[ForecastDataPoint] = []
    for h in range(arrival_h, 24):
        is_ev = event_hour is not None and event_hour == h
        points.append(_dp(day, h, thunder=thunder if is_ev else ThunderLevel.NONE))
    for h in range(0, 7):
        points.append(_dp(day + 1, h, thunder=ThunderLevel.NONE))
    return NormalizedTimeseries(meta=_meta(), data=points)


def _dc():
    return build_default_display_config()


def _report(segments, night_weather, *, report_config=None, has_gap: bool = False):
    return TripReportFormatter().format_email(
        segments,
        trip_name="E7",
        report_type="morning",
        night_weather=night_weather,
        display_config=_dc(),
        stage_name="E7",
        tz=_TZ,
        report_config=report_config,
        has_gap=has_gap,
    )


def _compact_line(email_plain: str) -> str:
    for line in email_plain.splitlines():
        if line.startswith("E7:"):
            return line
    return ""


def _telegram_text(report) -> str:
    return "\n".join(report.telegram_bubbles)


def _minimal_trip(trip_id: str, *, show_stability: bool = True,
                   daily_summary_metrics: list[str] | None = None) -> Trip:
    waypoints = [
        Waypoint(id=f"{trip_id}-wp1", name="Start", lat=42.0, lon=9.0, elevation_m=500),
        Waypoint(id=f"{trip_id}-wp2", name="Ziel", lat=42.1, lon=9.1, elevation_m=600),
    ]
    stage = Stage(id=f"{trip_id}-s1", name="Etappe 1", date=date(2026, 8, 1), waypoints=waypoints)
    return Trip(
        id=trip_id,
        name=f"Test-Trip {trip_id}",
        stages=[stage],
        report_config=TripReportConfig(
            trip_id=trip_id,
            show_stability=show_stability,
            daily_summary_metrics=daily_summary_metrics or ["precipitation", "wind"],
        ),
    )


# ---------------------------------------------------------------------------
# AC-1: Persistenz, zwei Nutzer, RMW ohne Datenverlust
# ---------------------------------------------------------------------------

class TestAC1PersistenceTwoUsersRMW:
    """AC-1: Nutzer A speichert ein Fenster 05-17 — nur seine Trip-Datei
    aendert sich, Nutzer Bs Trip bleibt unberuehrt beim Default, und
    bestehende report_config-Keys (show_stability, daily_summary_metrics)
    bleiben in BEIDEN Dateien unangetastet (RMW-Merge, Mandantentrennung).

    RED: `TripReportConfig` hat noch kein `day_window_start_hour`/
    `_end_hour`-Feld -> `dataclasses.replace(...)` wirft TypeError
    ('unexpected keyword argument'), bevor ueberhaupt gespeichert wird."""

    def test_day_window_persists_only_for_own_user_preserving_existing_keys(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        trip_a = _minimal_trip("trip-a", show_stability=False, daily_summary_metrics=["wind", "thunder"])
        trip_b = _minimal_trip("trip-b", show_stability=False, daily_summary_metrics=["wind", "thunder"])
        save_trip(trip_a, user_id="user-a", data_dir=data_dir)
        save_trip(trip_b, user_id="user-b", data_dir=data_dir)

        loaded_a = load_trip("trip-a", data_dir=str(data_dir), user_id="user-a")
        assert loaded_a is not None, "Vorbedingung verletzt: trip-a nicht geladen"

        # Nutzer A setzt das Fenster 05-17 (RMW: nur dieses Feld-Paar aendert sich).
        new_rc = dataclasses.replace(
            loaded_a.report_config,
            day_window_start_hour=5,
            day_window_end_hour=17,
        )
        loaded_a.report_config = new_rc
        save_trip(loaded_a, user_id="user-a", data_dir=data_dir)

        file_a = json.loads(
            (data_dir / "users" / "user-a" / "briefings" / "trip-a.json").read_text(encoding="utf-8")
        )
        file_b = json.loads(
            (data_dir / "users" / "user-b" / "briefings" / "trip-b.json").read_text(encoding="utf-8")
        )

        assert file_a["report_config"]["day_window_start_hour"] == 5, (
            f"Nutzer As Fenster-Start nicht persistiert: {file_a['report_config']}"
        )
        assert file_a["report_config"]["day_window_end_hour"] == 17, (
            f"Nutzer As Fenster-Ende nicht persistiert: {file_a['report_config']}"
        )
        assert file_a["report_config"]["show_stability"] is False, (
            "RMW-Merge hat einen bestehenden report_config-Key (show_stability) verloren"
        )
        assert file_a["report_config"]["daily_summary_metrics"] == ["wind", "thunder"], (
            "RMW-Merge hat einen bestehenden report_config-Key (daily_summary_metrics) verloren"
        )

        assert file_b["report_config"].get("day_window_start_hour") is None, (
            f"Cross-User-Datenleck: Nutzer Bs Datei traegt Nutzer As Fenster-Wert: {file_b['report_config']}"
        )
        assert file_b["report_config"]["show_stability"] is False, (
            "Nutzer Bs bestehender report_config-Key wurde durch Nutzer As Speichern veraendert"
        )
        assert file_b["report_config"]["daily_summary_metrics"] == ["wind", "thunder"], (
            "Nutzer Bs bestehender report_config-Key wurde durch Nutzer As Speichern veraendert"
        )


# ---------------------------------------------------------------------------
# AC-2: Rueckwaertskompatibilitaet
# ---------------------------------------------------------------------------

class TestAC2BackwardCompatibility:
    """AC-2: `build_day_window_points()` ohne Fenster-Argument muss identisch
    zu `start_hour=4, end_hour=19` sein; ein Alt-Trip ohne die neuen Felder
    laedt still auf den Default.

    RED: `build_day_window_points()` akzeptiert `start_hour`/`end_hour` noch
    nicht -> TypeError. Alt-Trip-Fixture: `TripReportConfig` hat noch kein
    `day_window_start_hour`-Attribut -> AttributeError."""

    def test_build_day_window_points_default_equals_explicit_4_19(self):
        segments = [_segment(day=20)]
        night = _night_weather(day=20, event_hour=14, thunder=ThunderLevel.HIGH)

        result_default = build_day_window_points(segments, night, _TZ)
        result_explicit = build_day_window_points(segments, night, _TZ, start_hour=4, end_hour=19)

        assert result_default == result_explicit, (
            "Ohne explizites Fenster-Argument muss build_day_window_points() "
            "identisch zu start_hour=4/end_hour=19 sein (Rueckwaertskompatibilitaet "
            "fuer Alt-Aufrufer)."
        )

    def test_old_trip_without_day_window_fields_loads_to_default(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        trip = _minimal_trip("legacy-trip")
        save_trip(trip, user_id="legacy-user", data_dir=data_dir)

        loaded = load_trip("legacy-trip", data_dir=str(data_dir), user_id="legacy-user")
        assert loaded is not None

        assert loaded.report_config.day_window_start_hour is None, (
            "Alt-Trip ohne day_window_start_hour muss beim Laden still None "
            "(= Default 4) liefern, kein KeyError/AttributeError."
        )
        assert loaded.report_config.day_window_end_hour is None, (
            "Alt-Trip ohne day_window_end_hour muss beim Laden still None "
            "(= Default 19) liefern, kein KeyError/AttributeError."
        )


# ---------------------------------------------------------------------------
# AC-3: Wirkung ueber alle vier Kurzformen + compute_has_gap konsistent
# ---------------------------------------------------------------------------

class TestAC3ConfiguredWindowAppliesToAllFourChannelsAndGapCheck:
    """AC-3: konfiguriertes Fenster 06-16. Ein Ereignis um 05:00 (ausserhalb)
    darf NICHT erscheinen, ein Ereignis um 16:00 (Grenzstunde, inklusiv) MUSS
    in SMS, Kurzzusammenfassung, Metriken-Pille UND Telegram-Fusszeile
    erscheinen — UND `compute_has_gap()` (derselbe Datenstand/dasselbe
    Fenster) darf fuer 16:00 keine Luecke melden.

    RED: `TripReportConfig(day_window_start_hour=..., day_window_end_hour=...)`
    wirft TypeError (Feld existiert nicht) -> die gesamte Kette schlaegt schon
    beim Setup fehl. `compute_has_gap()` akzeptiert zusaetzlich noch kein
    `start_hour`/`end_hour`-Kwarg -> TypeError, falls das Setup je repariert
    wuerde, bevor die Fenster-Durchreichung existiert."""

    def _report_config(self) -> TripReportConfig:
        return TripReportConfig(
            trip_id="e7",
            day_window_start_hour=6,
            day_window_end_hour=16,
        )

    def test_event_before_configured_window_start_excluded_in_all_four_channels(self):
        segments = [_segment(day=20, early_event=(5, ThunderLevel.HIGH))]
        report = _report(segments, None, report_config=self._report_config())
        compact = _compact_line(report.email_plain)
        telegram = _telegram_text(report)

        assert "TH:H@5" not in report.sms_text, (
            f"Konfiguriertes Fenster beginnt bei 06:00 -- ein Ereignis um "
            f"05:00 darf nicht in der SMS erscheinen.\nSMS: {report.sms_text}"
        )
        assert "⚡" not in compact, f"Kompakt-Zusammenfassung: {compact!r}"
        assert "kein Gewitter" in report.email_plain, f"Plain:\n{report.email_plain}"
        assert "⚡ kein" in telegram, f"Telegram:\n{telegram}"

    def test_event_at_inclusive_window_end_shown_in_all_four_channels_and_no_gap(self):
        segments = [_segment(day=20)]
        night = _night_weather(day=20, event_hour=16, thunder=ThunderLevel.HIGH)
        report = _report(segments, night, report_config=self._report_config())
        compact = _compact_line(report.email_plain)
        telegram = _telegram_text(report)

        assert "TH:H@16" in report.sms_text, (
            f"Konfiguriertes Fenster endet inklusive bei 16:00 -- ein "
            f"Ereignis um 16:00 muss in der SMS erscheinen.\nSMS: {report.sms_text}"
        )
        assert "⚡" in compact and "16:00" in compact, f"Kompakt: {compact!r}"
        assert "Gewitter ab 16:00 · stärkste 16:00" in report.email_plain, (
            f"Plain:\n{report.email_plain}"
        )
        assert "⚡ HIGH" in telegram, f"Telegram:\n{telegram}"

        has_gap = compute_has_gap(segments, night, _TZ, start_hour=6, end_hour=16)
        assert has_gap is False, (
            "compute_has_gap() muss dasselbe konfigurierte Fenster (06-16) "
            "verwenden wie die vier Kurzformen -- fuer 16:00 (vollstaendig "
            "abgedeckt) darf keine Luecke gemeldet werden (Erkennung == Anzeige)."
        )


# ---------------------------------------------------------------------------
# AC-4: defensive Klemmung eines ungueltigen Feld-Paars
# ---------------------------------------------------------------------------

class TestAC4DefensiveClampingInvalidWindowPair:
    """AC-4: ein ueber die API/Migration direkt gesetztes ungueltiges
    Feld-Paar (start=20 >= end=10) wird beim Laden still auf None (= Default
    4/19) zurueckgesetzt -- kein Crash, kein leeres Briefing. Simuliert eine
    Umgehung der UI-Validierung durch direktes Schreiben in die Trip-JSON
    (kein Python-/Go-Konstruktor-Aufruf).

    RED: `TripReportConfig` hat noch kein `day_window_start_hour`-Attribut
    -> AttributeError statt geklemmtem Rueckfall auf None."""

    def test_invalid_raw_window_pair_loads_and_renders_with_default_fallback(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        trip = _minimal_trip("invalid-window-trip")
        save_trip(trip, user_id="clamp-user", data_dir=data_dir)

        path = data_dir / "users" / "clamp-user" / "briefings" / "invalid-window-trip.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        # Direkte Plattenmanipulation (Import/Migration/API-Umgehung, DEC-2) --
        # bewusst KEIN TripReportConfig(...)-Konstruktor-Aufruf hier.
        raw["report_config"]["day_window_start_hour"] = 20
        raw["report_config"]["day_window_end_hour"] = 10
        path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")

        loaded = load_trip("invalid-window-trip", data_dir=str(data_dir), user_id="clamp-user")
        assert loaded is not None

        assert loaded.report_config.day_window_start_hour is None, (
            "Ungueltiges Feld-Paar (start=20 >= end=10) haette beim Laden auf "
            "None (= Default 4/19) zurueckgesetzt werden muessen."
        )
        assert loaded.report_config.day_window_end_hour is None, (
            "Ungueltiges Feld-Paar (start=20 >= end=10) haette beim Laden auf "
            "None (= Default 4/19) zurueckgesetzt werden muessen."
        )

        segments = [_segment(day=20)]
        night = _night_weather(day=20, event_hour=18, thunder=ThunderLevel.HIGH)
        report = _report(segments, night, report_config=loaded.report_config)

        assert report.sms_text, "Kein leeres Briefing erwartet trotz ungueltigem Feld-Paar."
        assert "TH:H@18" in report.sms_text, (
            f"Erwarteter Default-Fenster-Fallback (4-19): Ereignis um 18:00 "
            f"sollte sichtbar sein.\nSMS: {report.sms_text}"
        )
