"""Issue #670 — Antwort-Kommandos als echte Inbound-Keywords.

Bloße Schlüsselwörter am Zeilenanfang (PAUSE/SKIP/STOP/STATUS/CONFIG/HELP) lösen
Aktionen aus — zusätzlich zum bestehenden ``### key: value``-Pfad. PAUSE/SKIP/STOP
gaten erstmals den geplanten Scheduler-Versand über report_config-Felder.

Mock-frei: echtes File-I/O mit zwei realen Nutzerverzeichnissen, echte
``TripCommandProcessor().process()``- und ``_get_active_trips``-Aufrufe.
Spec: docs/specs/modules/issue_670_inbound_keywords.md
"""
from __future__ import annotations

import dataclasses
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.loader import (  # noqa: E402
    get_data_dir, get_snapshots_dir, get_trips_dir, load_all_trips, save_trip,
)
from app.models import TripReportConfig  # noqa: E402
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from services.trip_command_processor import (  # noqa: E402
    InboundMessage, TripCommandProcessor,
)

TZ = ZoneInfo("Europe/Berlin")

_USER_A = "bug670usera"
_USER_B = "bug670userb"
_USER_DEFAULT = "default"
_TRIP_ID = "issue670-keywords-trip"
_TRIP_NAME = "Issue670 Keywords"


def _make_trip(report_config: TripReportConfig | None = None) -> Trip:
    """Trip mit Etappen heute/morgen/übermorgen (aktiv für morning UND evening)."""
    start = date.today()
    stages = []
    for i in range(3):
        stages.append(Stage(
            id=f"S{i+1}",
            name=f"Tag {i+1}",
            date=start + timedelta(days=i),
            waypoints=[
                Waypoint(id="G1", name="Start", lat=42.13, lon=9.13, elevation_m=400),
                Waypoint(id="G2", name="Ziel", lat=42.10, lon=9.18, elevation_m=1200),
            ],
        ))
    rc = report_config if report_config is not None else TripReportConfig(
        trip_id=_TRIP_ID, enabled=True,
    )
    return Trip(id=_TRIP_ID, name=_TRIP_NAME, stages=stages, report_config=rc)


def _msg(body: str, user_id: str) -> InboundMessage:
    return InboundMessage(
        trip_name=_TRIP_NAME,
        body=body,
        sender="wanderer@example.com",
        channel="email",
        received_at=datetime.now(tz=timezone.utc),
        user_id=user_id,
    )


def _load_trip(user_id: str) -> Trip:
    return next(t for t in load_all_trips(user_id) if t.id == _TRIP_ID)


def _cleanup_user(user_id: str) -> None:
    for d in (get_trips_dir(user_id), get_snapshots_dir(user_id)):
        p = d / f"{_TRIP_ID}.json"
        if p.exists():
            p.unlink()
    log = get_data_dir(user_id) / "command_log.json"
    if log.exists():
        log.unlink()


@pytest.fixture(autouse=True)
def cleanup():
    yield
    for u in (_USER_A, _USER_B, _USER_DEFAULT):
        _cleanup_user(u)


def _active_ids(user_id: str, report_type: str) -> list[str]:
    """Echter Scheduler-Sende-Filter für den Nutzer."""
    from services.trip_report_scheduler import TripReportSchedulerService
    svc = TripReportSchedulerService(user_id=user_id)
    return [t.id for t in svc._get_active_trips(report_type)]


# ---------------------------------------------------------------------------
# AC-1: PAUSE wirkt — paused_until persistiert, Scheduler überspringt
# ---------------------------------------------------------------------------

class TestAC1Pause:
    def test_pause_sets_paused_until_and_excludes_from_schedule(self):
        save_trip(_make_trip(), user_id=_USER_A)
        # Pre: Trip ist aktiv
        assert _TRIP_ID in _active_ids(_USER_A, "morning")

        result = TripCommandProcessor().process(_msg("PAUSE 2d", _USER_A))
        assert result.success is True

        loaded = _load_trip(_USER_A)
        assert loaded.report_config.paused_until is not None
        now = datetime.now(tz=timezone.utc)
        delta = loaded.report_config.paused_until - now
        assert timedelta(days=1, hours=22) < delta < timedelta(days=2, hours=2), \
            f"paused_until ~jetzt+2d erwartet, war {loaded.report_config.paused_until}"

        # Scheduler überspringt den pausierten Trip
        assert _TRIP_ID not in _active_ids(_USER_A, "morning")
        # Bestätigung nennt das Ende-Datum
        assert result.confirmation_body, "Bestätigung darf nicht leer sein"

    def test_pause_expired_resumes_schedule(self):
        rc = TripReportConfig(
            trip_id=_TRIP_ID, enabled=True,
            paused_until=datetime.now(tz=timezone.utc) - timedelta(hours=1),
        )
        save_trip(_make_trip(rc), user_id=_USER_A)
        # Abgelaufene Pause → Trip wieder aktiv
        assert _TRIP_ID in _active_ids(_USER_A, "morning")


# ---------------------------------------------------------------------------
# AC-2: SKIP überspringt genau den nächsten Versand (einmalig konsumiert)
# ---------------------------------------------------------------------------

class TestAC2Skip:
    def test_skip_one_shot_consumed(self):
        save_trip(_make_trip(), user_id=_USER_A)

        result = TripCommandProcessor().process(_msg("SKIP", _USER_A))
        assert result.success is True
        assert _load_trip(_USER_A).report_config.skip_next is True

        # Erster Lauf: Trip ausgelassen UND Flag verbraucht (persistiert)
        assert _TRIP_ID not in _active_ids(_USER_A, "morning")
        assert _load_trip(_USER_A).report_config.skip_next is False, \
            "skip_next muss nach dem Überspringen zurückgesetzt sein"

        # Zweiter Lauf: Trip wieder aktiv
        assert _TRIP_ID in _active_ids(_USER_A, "morning")


# ---------------------------------------------------------------------------
# AC-3: STOP wirkt jetzt tatsächlich (enabled=False gated den Scheduler)
# ---------------------------------------------------------------------------

class TestAC3Stop:
    def test_stop_disables_scheduled_sends(self):
        save_trip(_make_trip(), user_id=_USER_A)
        assert _TRIP_ID in _active_ids(_USER_A, "morning")

        result = TripCommandProcessor().process(_msg("STOP", _USER_A))
        assert result.success is True
        assert _load_trip(_USER_A).report_config.enabled is False

        assert _TRIP_ID not in _active_ids(_USER_A, "morning")
        assert _TRIP_ID not in _active_ids(_USER_A, "evening")


# ---------------------------------------------------------------------------
# AC-4: STATUS/HELP/CONFIG
# ---------------------------------------------------------------------------

class TestAC4StatusHelpConfig:
    def test_status_lists_stages(self):
        save_trip(_make_trip(), user_id=_USER_A)
        result = TripCommandProcessor().process(_msg("STATUS", _USER_A))
        assert result.success is True
        assert "Tag 1" in result.confirmation_body

    def test_help_lists_new_keywords(self):
        result = TripCommandProcessor().process(_msg("HELP", _USER_A))
        assert result.success is True
        body = result.confirmation_body.upper()
        for kw in ("PAUSE", "SKIP", "STOP", "CONFIG"):
            assert kw in body, f"Hilfe muss {kw} nennen"

    def test_config_returns_link_no_mutation(self):
        save_trip(_make_trip(), user_id=_USER_A)
        before = _load_trip(_USER_A).report_config

        result = TripCommandProcessor().process(_msg("CONFIG", _USER_A))
        assert result.success is True
        assert _TRIP_ID in result.confirmation_body or "http" in result.confirmation_body.lower()

        after = _load_trip(_USER_A).report_config
        assert after.enabled == before.enabled
        assert after.paused_until == before.paused_until
        assert after.skip_next == before.skip_next


# ---------------------------------------------------------------------------
# AC-5: Mandantentrennung — nur antwortender Nutzer betroffen
# ---------------------------------------------------------------------------

class TestAC5UserIsolation:
    def test_pause_only_affects_sender(self):
        save_trip(_make_trip(), user_id=_USER_A)
        save_trip(_make_trip(), user_id=_USER_B)

        result = TripCommandProcessor().process(_msg("PAUSE 2d", _USER_A))
        assert result.success is True

        assert _load_trip(_USER_A).report_config.paused_until is not None
        b_rc = _load_trip(_USER_B).report_config
        assert b_rc.paused_until is None, "B darf nicht pausiert werden"
        assert b_rc.enabled is True
        assert _TRIP_ID in _active_ids(_USER_B, "morning")

        # default unberührt
        default_trip = get_trips_dir(_USER_DEFAULT) / f"{_TRIP_ID}.json"
        assert not default_trip.exists(), "default darf nicht beschrieben werden"

    def test_stop_only_affects_sender(self):
        save_trip(_make_trip(), user_id=_USER_A)
        save_trip(_make_trip(), user_id=_USER_B)

        TripCommandProcessor().process(_msg("STOP", _USER_A))

        assert _load_trip(_USER_A).report_config.enabled is False
        assert _load_trip(_USER_B).report_config.enabled is True


# ---------------------------------------------------------------------------
# AC-6: Keine Regression — bestehender ###-Pfad funktioniert unverändert
# ---------------------------------------------------------------------------

class TestAC6NoRegression:
    def test_hash_ruhetag_still_works(self):
        save_trip(_make_trip(), user_id=_USER_A)
        result = TripCommandProcessor().process(_msg("### ruhetag 2", _USER_A))
        assert result.success is True
        loaded = _load_trip(_USER_A)
        # Etappen nach heute wurden verschoben
        assert loaded.stages[-1].date > date.today() + timedelta(days=2)

    def test_hash_status_still_works(self):
        save_trip(_make_trip(), user_id=_USER_A)
        result = TripCommandProcessor().process(_msg("### status", _USER_A))
        assert result.success is True
        assert "Tag 1" in result.confirmation_body

    def test_unknown_keyword_is_rejected(self):
        save_trip(_make_trip(), user_id=_USER_A)
        result = TripCommandProcessor().process(_msg("GARTENZWERG", _USER_A))
        assert result.success is False


# ---------------------------------------------------------------------------
# AC-7: Block „Antwort-Kommandos" in der E-Mail
# ---------------------------------------------------------------------------

class TestAC7EmailBlock:
    def _render(self):
        from app.metric_catalog import build_default_display_config
        from output.renderers.email.html import render_html
        from app.models import (
            ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
            Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
            TripSegment,
        )
        dp = ForecastDataPoint(
            ts=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
            t2m_c=12.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.0,
            pop_pct=0, cloud_total_pct=50, thunder_level=ThunderLevel.NONE,
            visibility_m=2000, freezing_level_m=2500,
        )
        seg = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=400.0,
                                 distance_from_start_km=0.0),
            end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1200.0,
                               distance_from_start_km=4.2),
            start_time=datetime(2026, 7, 11, 6, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
            duration_hours=2.0, distance_km=4.2, ascent_m=800.0, descent_m=0.0,
        )
        meta = ForecastMeta(provider=Provider.OPENMETEO, model="demo",
                            grid_res_km=1.3,
                            run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc))
        agg = SegmentWeatherSummary(
            temp_min_c=10.0, temp_max_c=14.0, temp_avg_c=12.0,
            wind_max_kmh=20.0, gust_max_kmh=20.0, precip_sum_mm=0.0,
            cloud_avg_pct=50, humidity_avg_pct=55,
            thunder_level_max=ThunderLevel.NONE,
        )
        segs = [SegmentWeatherData(
            segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=[dp]),
            aggregated=agg, fetched_at=datetime.now(timezone.utc), provider="demo",
        )]
        return render_html(
            segments=segs, seg_tables=[[{"time": "06:00", "temp": 12.0,
                "_wind_dir_deg": None, "_is_day": True, "_dni_wm2": None,
                "_sunny_hours": 0.0, "_wmo_code": None}]],
            trip_name="GR20 Test", report_type="morning",
            dc=build_default_display_config(), night_rows=[],
            thunder_forecast=None, highlights=[], changes=None, stage_name=None,
            stage_stats=None, multi_day_trend=None, compact_summary=None,
            daylight=None, tz=TZ, friendly_keys=set(),
        )

    def test_block_lists_all_keywords(self):
        html = self._render()
        assert "Antwort-Kommandos" in html
        for kw in ("PAUSE", "SKIP", "STOP", "STATUS", "CONFIG", "HELP"):
            assert kw in html, f"Mail-Block muss {kw} enthalten"

    def test_block_not_hidden_on_mobile(self):
        """Der Block darf nicht in einem display:none-Mobile-Wrapper verschwinden."""
        html = self._render()
        idx = html.find("Antwort-Kommandos")
        assert idx != -1
        # Im Umfeld vor dem Heading darf kein display:none-Wrapper unmittelbar stehen
        window = html[max(0, idx - 200):idx]
        assert "display:none" not in window, \
            "Antwort-Kommandos-Block darf nicht mobile-versteckt sein"


# ---------------------------------------------------------------------------
# AC-8: Ungültige PAUSE-Dauer → keine Mutation, Format-Hinweis
# ---------------------------------------------------------------------------

class TestAC8PauseInvalidDuration:
    def test_invalid_duration_no_mutation(self):
        save_trip(_make_trip(), user_id=_USER_A)
        result = TripCommandProcessor().process(_msg("PAUSE xyz", _USER_A))
        assert result.success is False
        assert _load_trip(_USER_A).report_config.paused_until is None
        # Format-Hinweis in der Antwort
        assert "2d" in result.confirmation_body or "12h" in result.confirmation_body

    def test_zero_duration_rejected(self):
        save_trip(_make_trip(), user_id=_USER_A)
        result = TripCommandProcessor().process(_msg("PAUSE 0d", _USER_A))
        assert result.success is False
        assert _load_trip(_USER_A).report_config.paused_until is None
        assert "2d" in result.confirmation_body or "12h" in result.confirmation_body
