"""Geteilte Bausteine fuer die Alarm-Protokoll-Tests (Issue #1459).

Mock-frei: echte Modelle, echte Persistenz ueber die pytest-isolierte
``app.loader.get_data_dir()``-Basis (#1133), Transport ausschliesslich ueber
die vorhandenen DI-Naehte (``mail_sink``/``radar_service``).

Pfadregel #1409: alle Pruefling-Pfade laufen ueber ``get_data_dir()`` bzw.
werden relativ zur Testdatei aufgeloest -- nie ueber einen festen
Hauptrepo-Pfad. Einzige bewusste Ausnahme ist ``COMPARE_DATA_ROOT``: der
Compare-Loader liest Presets ueber den cwd-relativen Pfad ``data/users/...``
(``loader.load_compare_presets(data_root="data")``), also ueber das ``cwd``
des Pruefling -- das ist die in CLAUDE.md ausgenommene "geteilte Ablage".
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.config import Settings
from app.loader import get_data_dir
from app.models import (
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
)
from app.trip import Stage, Trip, Waypoint

LAT, LON = 47.0, 11.0

# s. Modul-Docstring: cwd-relative Ablage des Compare-Preset-Loaders.
COMPARE_DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"


def fresh_user(prefix: str) -> str:
    return f"tdd-1459-{prefix}-{uuid.uuid4().hex[:6]}"


def clean_compare_user(user_id: str) -> None:
    d = COMPARE_DATA_ROOT / user_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def settings_email_only() -> Settings:
    """``can_send_email() == True``, Telegram/SMS unkonfiguriert."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
        telegram_bot_token="", telegram_chat_id="",
    )


def settings_email_and_failing_telegram() -> Settings:
    """E-Mail zustellbar, Telegram konfiguriert **und garantiert scheiternd**.

    Kein Mock und kein Netz: ``is_test_mode=True`` mit einem Bot-Token, der
    nicht der konfigurierte Test-Token ist, laesst
    ``TelegramOutput._guard_test_mode_bot_token()`` (Issue #1363) VOR jedem
    ``httpx.post`` ein ``OutputConfigError`` werfen -- der echte Fehlerpfad
    des echten Transports.
    """
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
        telegram_bot_token="tdd-1459-kein-test-token", telegram_chat_id="4711",
        is_test_mode=True,
    )


def segment(segment_id: int | str = 1) -> TripSegment:
    """Etappe im aktiven Fenster (beginnt heute, endet in der Zukunft)."""
    now = datetime.now(timezone.utc)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500, distance_from_start_km=6.0),
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=3),
        duration_hours=4.0, distance_km=6.0, ascent_m=500, descent_m=0,
    )


def weather(segment_id: int | str = 1, **summary_kwargs) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=segment(segment_id),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def gust_alert_trip(
    trip_id: str, *, corridors: list | None = None, alert_channels: dict | None = None,
    with_thunder: bool = False,
) -> Trip:
    """Tour, deren Boeen-Delta-Regel scharf ist (Standard-Schwelle 20 km/h).

    ``with_thunder`` schaltet zusaetzlich die Gewitter-Empfindlichkeit scharf --
    seit Issue #1460 (P1b) meldet die Stufe "standard" das Erreichen der
    hoechsten Gefahrenstufe, sodass eine Tour ZWEI gleichzeitige Ausloeser
    haben kann (gebraucht fuer AC-7: mehrere Ausloeser, EIN Protokoll-Eintrag).
    """
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    metrics = [MetricConfig(metric_id="gust", enabled=True)]
    levels = {"wind_gust": "standard"}
    if with_thunder:
        metrics.append(MetricConfig(metric_id="thunder", enabled=True))
        levels["thunder_level"] = "standard"
    trip = Trip(
        id=trip_id, name="Protokoll-Trip", stages=[stage],
        official_warnings=None, corridors=corridors or [],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id, metrics=metrics, metric_alert_levels=levels,
        ),
    )
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=True, alert_on_changes=True)
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    if alert_channels is not None:
        trip.alert_channels = alert_channels
    return trip


def read_log(user_id: str) -> dict:
    """Rohes ``alert_log.json`` des Nutzers (leeres Geruest, wenn nicht da)."""
    path = get_data_dir(user_id) / "alert_log.json"
    if not path.exists():
        return {"entries": [], "not_delivered": []}
    data = json.loads(path.read_text())
    data.setdefault("entries", [])
    data.setdefault("not_delivered", [])
    return data


def reason_for_channel(entry: dict, channel: str) -> str | None:
    """Grund, aus dem ``channel`` NICHT zugestellt wurde.

    Akzeptiert bewusst beide selbstbeschreibenden Traegerformen
    (``{"telegram": "channel_disabled"}`` oder
    ``[{"channel": "telegram", "reason": "channel_disabled"}]``) -- die
    Akzeptanzkriterien legen die Bedeutung je Kanal fest, nicht die
    Behaelterform. Liefert ``None``, wenn der Kanal nicht gelistet ist.
    """
    not_sent = entry.get("channels_not_sent")
    if isinstance(not_sent, dict):
        return not_sent.get(channel)
    for item in not_sent or []:
        if isinstance(item, dict) and item.get("channel") == channel:
            return item.get("reason")
    return None
