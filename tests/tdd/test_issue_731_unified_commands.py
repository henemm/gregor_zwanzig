"""Issue #731 — Antwort-Kommandos vereinheitlichen (abruf-zentriert).

Ersetzt die Abonnenten-Verwaltungsbefehle (PAUSE/SKIP/CONFIG) durch einen
abruf-zentrierten Grundbefehlssatz, der über E-Mail und Telegram identische
Keywords nutzt: HEUTE/MORGEN/JETZT/GEWITTER/RUHETAG/STATUS/STOP/WEITER/HILFE.

Mock-frei: echte ``render_html``/``render_plain``-Ausgabe, echte
``TripCommandProcessor().process()``-Aufrufe mit echtem File-I/O (zwei reale
Nutzerverzeichnisse für die Mandantentrennung), echter Telegram-Parser.

Spec: docs/specs/modules/issue_731_unified_commands.md
"""
from __future__ import annotations

import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.loader import (  # noqa: E402
    get_snapshots_dir, get_trips_dir, load_all_trips, save_trip,
)
from app.models import TripReportConfig  # noqa: E402
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from services.trip_command_processor import (  # noqa: E402
    InboundMessage, TripCommandProcessor,
)

TZ = ZoneInfo("UTC")

_USER_A = "tdd-731-usera"
_USER_B = "tdd-731-userb"
_USER_DEFAULT = "default"
_TRIP_ID = "issue731-unified-trip"
_TRIP_NAME = "Issue731 Unified"

# Keywords, die der neue Befehlssatz garantiert enthalten MUSS
# Note: Plain renderer still uses old #731 keywords; HTML changed with #884.
# Shared subset for AC-2 (plain): HEUTE/MORGEN/JETZT/GEWITTER/WEITER still in plain.py
_NEW_KEYWORDS = ["HEUTE", "MORGEN", "JETZT", "GEWITTER", "WEITER"]
# Keywords, die ENTFERNT sein müssen (PAUSE/SKIP sind seit #882 wieder aktiv)
# CONFIG was removed by #731 and is NOT in plain.py; HTML reintroduced it in #884.
_REMOVED_KEYWORDS = ["CONFIG"]

# HTML-specific keywords added by #884 design (Antwort-Kommandos 3x2-grid)
# Issue #1058: CONFIG removed from the HTML block (dead command, never dispatched).
_HTML_NEW_KEYWORDS = ["PAUSE", "SKIP", "STOP", "STATUS", "HELP"]
# Keywords removed from the HTML kommandos block by #884 / #1058
_HTML_REMOVED_KEYWORDS = ["HILFE", "CONFIG"]


# ---------------------------------------------------------------------------
# E-Mail-Render-Helfer (gespiegelt aus test_issue_612_report_on_demand.py)
# ---------------------------------------------------------------------------

def _make_segment_data():
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    points = [
        ForecastDataPoint(
            ts=datetime(2026, 5, 1, 9 + h, 0, tzinfo=timezone.utc),
            t2m_c=15.0 + h, wind10m_kmh=10.0 + h, gust_kmh=22.0 + h,
            pop_pct=40, precip_1h_mm=0.4, wind_chill_c=12.0 + h,
            cloud_total_pct=55,
        )
        for h in range(6)
    ]
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2",
        run=datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.0, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=points)
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 5, 1, 13, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
    )
    agg = SegmentWeatherSummary(
        temp_min_c=15.0, temp_max_c=20.0, temp_avg_c=17.5,
        wind_max_kmh=16.0, gust_max_kmh=28.0,
        precip_sum_mm=2.4, cloud_avg_pct=55,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _make_dc():
    from app.metric_catalog import build_default_display_config
    return build_default_display_config()


def _render_html() -> str:
    from output.renderers.email.html import render_html
    return render_html(
        segments=[_make_segment_data()], seg_tables=[[]],
        trip_name="GR20 Etappe 3", report_type="evening", dc=_make_dc(),
        night_rows=[], thunder_forecast=None, highlights=[], changes=None,
        stage_name="Vizzavona – Capannelle", stage_stats=None,
        multi_day_trend=None, compact_summary="Sonniger Abend",
        daylight=None, tz=TZ, friendly_keys=set(),
    )


def _render_plain() -> str:
    from output.renderers.email.plain import render_plain
    return render_plain(
        segments=[_make_segment_data()], seg_tables=[[]],
        trip_name="GR20 Etappe 3", report_type="evening", dc=_make_dc(),
        night_rows=[], thunder_forecast=None, highlights=[], changes=None,
        stage_name="Vizzavona – Capannelle", stage_stats=None,
        multi_day_trend=None, compact_summary="Sonniger Abend",
        daylight=None, tz=TZ, friendly_keys=set(),
    )


# ---------------------------------------------------------------------------
# Trip/Message-Helfer (gestern/heute/morgen → AC-6 braucht eine Vergangenheit)
# ---------------------------------------------------------------------------

def _make_trip(enabled: bool = True) -> Trip:
    """Trip mit Etappen gestern/heute/morgen."""
    start = date.today() - timedelta(days=1)
    stages = []
    for i in range(3):
        stages.append(Stage(
            id=f"S{i+1}", name=f"Tag {i+1}",
            date=start + timedelta(days=i),
            waypoints=[
                Waypoint(id="G1", name="Start", lat=42.13, lon=9.13, elevation_m=400),
                Waypoint(id="G2", name="Ziel", lat=42.10, lon=9.18, elevation_m=1200),
            ],
        ))
    rc = TripReportConfig(trip_id=_TRIP_ID, enabled=enabled)
    return Trip(id=_TRIP_ID, name=_TRIP_NAME, stages=stages, report_config=rc)


def _msg(body: str, user_id: str, channel: str = "email") -> InboundMessage:
    return InboundMessage(
        trip_name=_TRIP_NAME, body=body, sender="wanderer@example.com",
        channel=channel, received_at=datetime.now(tz=timezone.utc),
        user_id=user_id,
    )


def _load_trip(user_id: str) -> Trip:
    return next(t for t in load_all_trips(user_id) if t.id == _TRIP_ID)


def _ensure_real_user_dir(user_id: str) -> None:
    """Issue #1133: trip_report_scheduler.py schreibt briefing_log.json
    weiterhin über die relative "data/users/..."-Konstruktion (bewusst nicht
    migriert, Known Limitations) und setzt die Existenz des Nutzerverzeichnisses
    voraus."""
    (Path("data/users") / user_id).mkdir(parents=True, exist_ok=True)


def _yesterday_name() -> str:
    return "Tag 1"  # Etappe von gestern


def _today_name() -> str:
    return "Tag 2"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    for u in (_USER_A, _USER_B, _USER_DEFAULT):
        for d in (get_trips_dir(u), get_snapshots_dir(u)):
            p = d / f"{_TRIP_ID}.json"
            if p.exists():
                p.unlink()
        if u != _USER_DEFAULT:
            ud = Path("data/users") / u
            if ud.exists():
                shutil.rmtree(ud, ignore_errors=True)


def _is_unknown(result) -> bool:
    body = (result.confirmation_body or "").lower()
    return ("unbekannter befehl" in body
            or "kein gueltiger befehl" in body
            or "kein gültiger befehl" in body
            or "kein befehl" in body)


# ===========================================================================
# AC-1: HTML-E-Mail-Block listet neuen Satz, kein PAUSE/SKIP/CONFIG
# ===========================================================================

class TestAC1HtmlCommandBlock:
    """AC-1: HTML Antwort-Kommandos block.

    Updated for #884 design: the block now shows PAUSE 2d/SKIP/STOP/STATUS/CONFIG/HELP
    in a dedicated 3x2-grid section with background #fbfaf6. Old #731 keywords
    (HEUTE/MORGEN/JETZT/GEWITTER/WEITER) are no longer in the HTML kommandos block.
    """

    def test_new_keywords_present(self):
        html = _render_html()
        for kw in _HTML_NEW_KEYWORDS:
            assert kw in html, f"HTML-Antwort-Kommandos müssen '{kw}' enthalten (AC-1/#884)"

    def test_old_keywords_removed(self):
        html = _render_html()
        for kw in _HTML_REMOVED_KEYWORDS:
            assert kw not in html, f"'{kw}' darf nicht mehr im HTML stehen (AC-1/#884)"


# ===========================================================================
# AC-2: Plaintext-E-Mail spiegelt neuen Satz, kein PAUSE/SKIP/CONFIG
# ===========================================================================

class TestAC2PlainCommandBlock:
    def test_new_keywords_present(self):
        plain = _render_plain()
        for kw in _NEW_KEYWORDS:
            assert kw in plain, f"Plaintext muss '{kw}' enthalten (AC-2)"

    def test_old_keywords_removed(self):
        plain = _render_plain()
        for kw in _REMOVED_KEYWORDS:
            assert kw not in plain, f"'{kw}' darf nicht mehr im Plaintext stehen (AC-2)"


# ===========================================================================
# AC-3: bare 'heute'/'morgen' → Etappen-Wetter (kein Unbekannter Befehl)
# ===========================================================================

class TestAC3HeuteMorgen:
    def test_heute_routes_to_query(self):
        save_trip(_make_trip(), user_id=_USER_A)
        _ensure_real_user_dir(_USER_A)
        result = TripCommandProcessor().process(_msg("heute", _USER_A))
        assert not _is_unknown(result), "‚heute' darf nicht ‚Unbekannter Befehl' sein (AC-3)"
        assert result.command == "heute", f"command sollte 'heute' sein, war {result.command!r}"

    def test_morgen_routes_to_query(self):
        save_trip(_make_trip(), user_id=_USER_A)
        _ensure_real_user_dir(_USER_A)
        result = TripCommandProcessor().process(_msg("morgen", _USER_A))
        assert not _is_unknown(result), "‚morgen' darf nicht ‚Unbekannter Befehl' sein (AC-3)"
        assert result.command == "morgen", f"command sollte 'morgen' sein, war {result.command!r}"


# ===========================================================================
# AC-4: 'jetzt'/'now' → Nowcast, 'gewitter' → Gewittergefahr heute
# ===========================================================================

class TestAC4JetztGewitter:
    def test_jetzt_routes_to_nowcast(self):
        save_trip(_make_trip(), user_id=_USER_A)
        result = TripCommandProcessor().process(_msg("jetzt", _USER_A))
        assert not _is_unknown(result), "‚jetzt' darf nicht ‚Unbekannter Befehl' sein (AC-4)"
        assert result.command == "now", f"command sollte 'now' sein, war {result.command!r}"

    def test_now_alias_routes_to_nowcast(self):
        save_trip(_make_trip(), user_id=_USER_A)
        result = TripCommandProcessor().process(_msg("now", _USER_A))
        assert result.command == "now", f"command sollte 'now' sein, war {result.command!r}"

    def test_gewitter_routes_to_thunder(self):
        save_trip(_make_trip(), user_id=_USER_A)
        result = TripCommandProcessor().process(_msg("gewitter", _USER_A))
        assert not _is_unknown(result), "‚gewitter' darf nicht ‚Unbekannter Befehl' sein (AC-4)"
        assert result.command == "heute_gewitter", \
            f"command sollte 'heute_gewitter' sein, war {result.command!r}"


# ===========================================================================
# AC-5: WEITER reaktiviert Versand (enabled=True via RMW)
# ===========================================================================

class TestAC5Weiter:
    def test_weiter_reenables_schedule(self):
        save_trip(_make_trip(enabled=False), user_id=_USER_A)
        result = TripCommandProcessor().process(_msg("WEITER", _USER_A))
        assert result.success is True, "WEITER muss erfolgreich sein (AC-5)"
        loaded = _load_trip(_USER_A)
        assert loaded.report_config.enabled is True, \
            "WEITER muss report_config.enabled auf True setzen (AC-5)"
        assert result.confirmation_body, "Bestätigung darf nicht leer sein"


# ===========================================================================
# AC-6: STATUS zeigt nur heute + kommende Etappen, keine vergangenen
# ===========================================================================

class TestAC6StatusUpcomingOnly:
    def test_status_excludes_past_stage(self):
        save_trip(_make_trip(), user_id=_USER_A)
        result = TripCommandProcessor().process(_msg("STATUS", _USER_A))
        body = result.confirmation_body or ""
        assert _today_name() in body, "STATUS muss die heutige Etappe zeigen (AC-6)"
        assert _yesterday_name() not in body, \
            "STATUS darf vergangene Etappen NICHT mehr listen (AC-6)"


# ===========================================================================
# AC-7: PAUSE/SKIP/CONFIG lösen keine State-Mutation mehr aus
# ===========================================================================

class TestAC7RemovedCommands:
    def test_pause_sets_paused_until(self):
        # Since #882: PAUSE is re-enabled and must set paused_until
        save_trip(_make_trip(), user_id=_USER_A)
        TripCommandProcessor().process(_msg("PAUSE 12h", _USER_A))
        loaded = _load_trip(_USER_A)
        assert loaded.report_config.paused_until is not None, \
            "PAUSE muss paused_until setzen (seit #882)"

    def test_skip_sets_skip_next(self):
        # Since #882: SKIP is re-enabled and must set skip_next=True
        save_trip(_make_trip(), user_id=_USER_A)
        TripCommandProcessor().process(_msg("SKIP", _USER_A))
        loaded = _load_trip(_USER_A)
        assert getattr(loaded.report_config, "skip_next", False), \
            "SKIP muss skip_next=True setzen (seit #882)"

    def test_config_treated_as_unknown(self):
        save_trip(_make_trip(), user_id=_USER_A)
        result = TripCommandProcessor().process(_msg("CONFIG", _USER_A))
        assert result.command != "config", \
            "CONFIG darf nicht mehr als eigener Befehl behandelt werden (AC-7)"


# ===========================================================================
# AC-8: HILFE listet neuen Satz, kein PAUSE/SKIP/CONFIG
# ===========================================================================

class TestAC8Help:
    def test_help_lists_new_set(self):
        result = TripCommandProcessor().process(_msg("HILFE", _USER_A))
        body = (result.confirmation_body or "").upper()
        for kw in _NEW_KEYWORDS:
            assert kw in body, f"HILFE muss '{kw}' listen (AC-8)"

    def test_help_drops_removed(self):
        result = TripCommandProcessor().process(_msg("HILFE", _USER_A))
        body = (result.confirmation_body or "").upper()
        for kw in _REMOVED_KEYWORDS:
            assert kw not in body, f"HILFE darf '{kw}' nicht mehr listen (AC-8)"


# ===========================================================================
# AC-9: Telegram — /jetzt und /gewitter gemappt, Extras (glance) intakt
# ===========================================================================

class TestAC9TelegramMapping:
    def test_slash_jetzt_maps_to_now(self):
        from services.inbound_telegram_reader import InboundTelegramReader
        key, _ = InboundTelegramReader()._parse_command("/jetzt")
        assert key == "now", f"/jetzt muss auf 'now' mappen, war {key!r} (AC-9)"

    def test_slash_gewitter_maps_to_thunder(self):
        from services.inbound_telegram_reader import InboundTelegramReader
        key, _ = InboundTelegramReader()._parse_command("/gewitter")
        assert key == "heute_gewitter", \
            f"/gewitter muss auf 'heute_gewitter' mappen, war {key!r} (AC-9)"

    def test_glance_extras_still_interactive(self):
        save_trip(_make_trip(), user_id=_USER_A)
        result = TripCommandProcessor().process(
            _msg("glance", _USER_A, channel="telegram")
        )
        assert result.reply_markup is not None, \
            "glance muss weiterhin interaktive Buttons liefern (AC-9)"


# ===========================================================================
# AC-10: Mandantentrennung — WEITER wirkt nur auf den Trip des Nutzers
# ===========================================================================

class TestAC10UserIsolation:
    def test_weiter_only_affects_own_trip(self):
        save_trip(_make_trip(enabled=False), user_id=_USER_A)
        save_trip(_make_trip(enabled=False), user_id=_USER_B)

        TripCommandProcessor().process(_msg("WEITER", _USER_A))

        assert _load_trip(_USER_A).report_config.enabled is True, \
            "Nutzer A muss reaktiviert sein (AC-10)"
        assert _load_trip(_USER_B).report_config.enabled is False, \
            "Nutzer B darf NICHT verändert werden (AC-10)"
        # Kein versehentliches Schreiben nach users/default/
        default_trip = get_trips_dir(_USER_DEFAULT) / f"{_TRIP_ID}.json"
        assert not default_trip.exists(), \
            "WEITER darf nicht nach users/default/ schreiben (AC-10)"
