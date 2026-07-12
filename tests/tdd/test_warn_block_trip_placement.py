"""WarnBlock im Trip-Briefing: Platzierung VOR der Tageslage (#1216, embedded).

SPEC: docs/specs/modules/issue_1216_embedded_warnblock.md (AC-1/AC-2)

RED-Phase: Heute wird der amtliche-Warnung-Block via `render_official_alerts_html`
NACH der Tageslage eingefügt (html.py:1531, Reihenfolge `{changes_html}
{official_alerts_html}` nach `{tageslage_html}`). Die Spec verlangt den WarnBlock
als erstes inhaltliches Element direkt nach dem Header und VOR der Tageslage,
in der neuen `.wb`-Struktur (Eyebrow „Amtliche Warnung").

Verhaltenstests — KEINE Mocks. Echte `render_html`-Aufrufe mit echten
`SegmentWeatherData`/`OfficialAlert`-Objekten (Muster
test_issue_898_901_mail_layout.py).
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from services.official_alerts.models import OfficialAlert

TZ = ZoneInfo("Europe/Vienna")
UTC = timezone.utc

# Distinktiver Marker, der sonst nirgends im Briefing steht.
ALERT_LABEL = "Gewitterwarnung Testmarker XYZ"
TAGESLAGE_MARKER = "TAGESLAGE"

_SIMPLE_ROWS = [
    {"time": "06", "temp": "12°", "risk_color": "#2f8a3e"},
]


def _alert():
    return OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=3, label=ALERT_LABEL,
        valid_from=datetime(2026, 7, 11, 15, 0, tzinfo=UTC),
        valid_to=datetime(2026, 7, 11, 21, 0, tzinfo=UTC),
        region_label="Hermagor",
    )


def _build_segments(*, with_alert: bool):
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )

    def _dp(h):
        return ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=UTC),
            t2m_c=18.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.0,
            pop_pct=10, cloud_total_pct=40, thunder_level=ThunderLevel.NONE,
            visibility_m=20000, freezing_level_m=3000,
        )

    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=46.62, lon=13.68, elevation_m=600.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=46.60, lon=13.70, elevation_m=1200.0,
                           distance_from_start_km=5.0),
        start_time=datetime(2026, 7, 11, 6, 0, tzinfo=UTC),
        end_time=datetime(2026, 7, 11, 10, 0, tzinfo=UTC),
        duration_hours=4.0, distance_km=5.0, ascent_m=600.0, descent_m=0.0,
    )
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3)
    ts = NormalizedTimeseries(meta=meta, data=[_dp(6), _dp(7), _dp(8)])
    agg = SegmentWeatherSummary(
        temp_min_c=10.0, temp_max_c=20.0, temp_avg_c=15.0,
        wind_max_kmh=20.0, gust_max_kmh=30.0, precip_sum_mm=0.0,
        cloud_avg_pct=40, humidity_avg_pct=55, thunder_level_max=ThunderLevel.NONE,
    )
    kwargs = dict(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(UTC), provider="demo",
    )
    if with_alert:
        kwargs["official_alerts"] = [_alert()]
    return [SegmentWeatherData(**kwargs)]


def _render(segs):
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html
    return render_html(
        segments=segs,
        seg_tables=[_SIMPLE_ROWS] * len(segs),
        trip_name="GR20 Test",
        report_type="morning",
        dc=build_default_display_config(),
        night_rows=[],
        thunder_forecast=None,
        changes=None,
        stage_name=None,
        stage_stats=None,
        multi_day_trend=None,
        # compact_summary -> Tageslage-Block erscheint (sonst kein Vergleichsanker).
        compact_summary="Wechselhaft mit Schauern.",
        tz=TZ,
        friendly_keys=set(),
    )


# ---------------------------------------------------------------------------
# AC-1 — WarnBlock erscheint VOR der Tageslage (+ neue `.wb`-Struktur)
# ---------------------------------------------------------------------------
def test_ac1_warn_block_before_tageslage_and_new_structure():
    html = _render(_build_segments(with_alert=True))

    # Der Tageslage-Anker existiert (compact_summary gesetzt).
    assert TAGESLAGE_MARKER in html, "Tageslage-Block fehlt trotz compact_summary"
    # Neue WarnBlock-Struktur: Eyebrow „Amtliche Warnung" + `.wb`-Markup.
    assert 'class="wb' in html, f"kein .wb-WarnBlock im Trip-HTML: RED erwartet"
    assert "Amtliche Warnung" in html
    # Das Warn-Label ist im Body enthalten.
    assert ALERT_LABEL in html

    # Positions-Assertion: der WarnBlock steht VOR der Tageslage.
    warn_idx = html.index(ALERT_LABEL)
    tageslage_idx = html.index(TAGESLAGE_MARKER)
    assert warn_idx < tageslage_idx, (
        "WarnBlock muss VOR der Tageslage stehen "
        f"(Warn-Index {warn_idx} !< Tageslage-Index {tageslage_idx})."
    )


# ---------------------------------------------------------------------------
# AC-2 — keine Warnung -> kein WarnBlock, kein leeres `.wb`-Div (Invariante)
# ---------------------------------------------------------------------------
def test_ac2_no_warning_no_warn_block():
    html = _render(_build_segments(with_alert=False))
    assert "class=\"wb" not in html, "Ohne Warnung darf kein .wb-WarnBlock erscheinen"
    assert "Amtliche Warnung" not in html
    assert ALERT_LABEL not in html
