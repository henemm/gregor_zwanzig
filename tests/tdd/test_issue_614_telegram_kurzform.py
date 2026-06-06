"""TDD RED — #614/#615: Telegram Kurzform-Option ("Tages-Max").

SPEC: docs/specs/modules/issue_614_615_telegram_kurzform.md (AC-1..AC-5).
TEST-MANIFEST: docs/specs/tests/issue_614_615_telegram_kurzform_tests.md.

Beschreibt die NOCH NICHT existierende API:
  - src/app/models.py: UnifiedWeatherDisplayConfig.telegram_kurzform (neues Feld)
  - src/app/loader.py: _parse_display_config liest/_*_to_dict schreibt telegram_kurzform
  - src/formatters/trip_report.py: hängt SMS-Kurzform an telegram_text wenn Flag gesetzt

Alle Tests MÜSSEN in der RED-Phase rot sein:
  AC-1: TypeError/AssertionError (telegram_kurzform existiert nicht / wird nicht serialisiert)
  AC-2: AssertionError (kein "Tages-Max"-Block, da Feld+Append fehlen)
  AC-3: TypeError (Konstruktor kennt telegram_kurzform nicht)
  AC-4: GREEN-Guard — SMS-Wire-Format bleibt unverändert (muss vor UND nach Fix grün sein)

KEINE Mocks — echte SegmentWeatherData, echte format_email()-Pipeline, echter SMS-Render.
Builder-Muster aus tests/tdd/test_issue_360_channel_renderer.py übernommen.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


# ---------------------------------------------------------------------------
# Helpers (real domain objects, no mocks)
# ---------------------------------------------------------------------------

# 9 Primär-Metriken → mehr als die Telegram-Tabelle in 8 Spalten (Zeit + 7) zeigt.
_NINE_PRIMARY = [
    ("temperature", "primary", 0),
    ("wind", "primary", 1),
    ("gust", "primary", 2),
    ("rain_probability", "primary", 3),
    ("precipitation", "primary", 4),
    ("wind_chill", "primary", 5),
    ("cloud_total", "primary", 6),
    ("thunder", "primary", 7),
    ("fresh_snow", "primary", 8),
]


def _build_dc(metric_specs, **extra):
    """Build UnifiedWeatherDisplayConfig from (id, bucket, order) tuples."""
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig

    metrics = [
        MetricConfig(metric_id=mid, enabled=True, bucket=bucket, order=order)
        for mid, bucket, order in metric_specs
    ]
    return UnifiedWeatherDisplayConfig(
        trip_id="issue-614",
        metrics=metrics,
        updated_at=datetime.now(timezone.utc),
        **extra,
    )


def _make_segment():
    """Minimal real SegmentWeatherData with several hours of forecast."""
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )

    now = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
    points = []
    for h in range(6):
        points.append(ForecastDataPoint(
            ts=datetime(2026, 5, 1, 9 + h, 0, tzinfo=timezone.utc),
            t2m_c=15.0 + h,
            wind10m_kmh=10.0 + h,
            gust_kmh=22.0 + h,
            pop_pct=40,
            precip_1h_mm=0.4,
            wind_chill_c=12.0 + h,
            cloud_total_pct=55,
            freezing_level_m=2800,
            uv_index=5.0,
        ))
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2", run=now,
        grid_res_km=2.0, interp="nearest",
    )
    ts = NormalizedTimeseries(meta=meta, data=points)
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=2000),
        start_time=now,
        end_time=datetime(2026, 5, 1, 15, 0, tzinfo=timezone.utc),
        duration_hours=6.0, distance_km=12.0, ascent_m=500, descent_m=0,
    )
    return SegmentWeatherData(
        segment=segment, timeseries=ts, aggregated=SegmentWeatherSummary(),
        fetched_at=now, provider="openmeteo",
    )


def _render_telegram(telegram_kurzform: bool) -> str:
    """Run the REAL email pipeline and return telegram_text."""
    from src.formatters.trip_report import TripReportFormatter

    dc = _build_dc(_NINE_PRIMARY, telegram_kurzform=telegram_kurzform)
    report = TripReportFormatter().format_email(
        segments=[_make_segment()],
        trip_name="KHW 403",
        report_type="evening",
        display_config=dc,
        stage_name="KHW403",
        tz=ZoneInfo("Europe/Berlin"),
    )
    return report.telegram_text or ""


# ---------------------------------------------------------------------------
# AC-1 — Konfig-Feld existiert, hat Default False, round-trippt im Loader
# ---------------------------------------------------------------------------

def test_ac1_field_default_false():
    """GIVEN frische DisplayConfig WHEN ohne Flag gebaut THEN telegram_kurzform == False."""
    dc = _build_dc(_NINE_PRIMARY)
    assert dc.telegram_kurzform is False


def test_ac1_loader_roundtrip_preserves_flag_and_other_fields():
    """GIVEN display_config dict mit telegram_kurzform=True + anderen Feldern
    WHEN parse THEN Flag bleibt True UND andere Felder erhalten (kein Datenverlust)."""
    from app.loader import _parse_display_config

    raw = {
        "trip_id": "rt-614",
        "telegram_kurzform": True,
        "show_night_block": False,
        "night_interval_hours": 3,
        "metrics": [
            {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
            {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 1},
        ],
        "updated_at": "2026-06-06T08:00:00",
    }
    dc = _parse_display_config(raw)
    assert dc.telegram_kurzform is True
    # Merge/No-Loss: andere Felder unverändert übernommen
    assert dc.show_night_block is False
    assert dc.night_interval_hours == 3
    assert len(dc.metrics) == 2


# ---------------------------------------------------------------------------
# AC-2 — Kurzform wird angehängt und trägt ALLE Metriken (keine Truncation)
# ---------------------------------------------------------------------------

def test_ac2_kurzform_appended_with_all_metrics():
    """GIVEN telegram_kurzform=True + 9 Metriken (>8-Spalten-Limit)
    WHEN Telegram gerendert THEN Tages-Max-Block + vollständige SMS-Kurzform enthalten."""
    from src.formatters.sms_trip import SMSTripFormatter

    text = _render_telegram(telegram_kurzform=True)
    assert "Tages-Max" in text, "Kurzform-Block fehlt im telegram_text"

    # Die unbeschnittene SMS-Kurzform (hohes max_length) muss 1:1 enthalten sein.
    expected = SMSTripFormatter().format_sms(
        [_make_segment()],
        stage_name="KHW403",
        report_type="evening",
        tz=ZoneInfo("Europe/Berlin"),
        max_length=4000,
    )
    assert expected in text, (
        "Vollständige SMS-Kurzform nicht im telegram_text gefunden "
        f"(erwartet: {expected!r})"
    )
    # Überzählige Metrik (Böen = G-Token) muss in der Kurzform auftauchen.
    kurz = text.split("Tages-Max", 1)[1]
    assert " G" in kurz or "G2" in kurz, "Böen-Token (Überlauf) fehlt in der Kurzform"


# ---------------------------------------------------------------------------
# AC-3 — Flag aus (Default) = unverändert, KEIN Kurzform-Block
# ---------------------------------------------------------------------------

def test_ac3_disabled_no_kurzform_block():
    """GIVEN telegram_kurzform=False WHEN Telegram gerendert THEN kein Tages-Max-Block."""
    text = _render_telegram(telegram_kurzform=False)
    assert "Tages-Max" not in text


# ---------------------------------------------------------------------------
# AC-4 — SMS-Wire-Format unverändert (GREEN-Guard, kein Format-Umbau durch #615)
# ---------------------------------------------------------------------------

def test_ac4_sms_format_unchanged():
    """GIVEN denselben Trip WHEN SMS gerendert THEN beginnt mit '{Stage}: ' und
    nutzt das bestehende N/D/W/G-Token-Schema (sms_format.md v2.0)."""
    from src.formatters.sms_trip import SMSTripFormatter

    sms = SMSTripFormatter().format_sms(
        [_make_segment()],
        stage_name="KHW403",
        report_type="evening",
        tz=ZoneInfo("Europe/Berlin"),
        max_length=160,
    )
    assert sms.startswith("KHW403: ")
    assert len(sms) <= 160
    # bestehendes Schema: Tag-Max-Temp-Token 'D' + Wind 'W'
    assert " D" in sms and " W" in sms
