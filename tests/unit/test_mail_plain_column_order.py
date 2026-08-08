"""Die im Editor eingestellte Metrik-Reihenfolge wirkt auch im Plain-Text-Teil
der Briefing-Mail.

Spec: docs/specs/modules/fix_1575_plain_column_order.md (Issue #1575, Scheibe 2).

Scheibe 1 (`tests/unit/test_mail_column_order.py`) hat das fuer den HTML-Teil
bereits sichergestellt. Diese Datei prueft dieselbe Zusicherung am Plain-Text-
WIRKORT (`render_plain`/Plain-Teil von `format_email`), nicht an einer
isolierten Sortierfunktion -- Lehre aus #1457: eine Zusicherung, die nur dort
geprueft wird, wo der Code steht, kann erfuellt und wirkungslos zugleich sein.

AC-6 (HTML bleibt nach der Helper-Extraktion byte-gleich) hat bewusst KEINEN
eigenen Test hier: der Regressionsschutz ist die bereits bestehende
HTML-Testsuite in `test_mail_column_order.py` -- bricht die Extraktion HTML,
wird die dort genau.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.metric_catalog import (
    build_default_display_config, get_col_defs, get_metric,
)
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from output.renderers.channel_layout import render_for_channel
from output.renderers.email.plain import render_plain
from output.renderers.trip_report import TripReportFormatter

TZ = ZoneInfo("Europe/Berlin")

# Spalten, die der HTML-Renderer unabhaengig von der Metrik-Auswahl setzt.
_FRAME_COLUMNS_HTML = {"Time", "Risk"}


def _segment() -> SegmentWeatherData:
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1800),
        start_time=datetime(2026, 8, 29, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc),
        duration_hours=2.0, distance_km=5.0, ascent_m=300, descent_m=0,
    )
    summary = SegmentWeatherSummary(
        temp_min_c=12.0, temp_max_c=18.0, temp_avg_c=15.0,
        wind_max_kmh=25.0, gust_max_kmh=40.0, precip_sum_mm=5.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.5, interp="point_grid",
    )
    data = [
        ForecastDataPoint(
            ts=datetime(2026, 8, 29, h, 0, tzinfo=timezone.utc),
            t2m_c=12.0 + h, wind10m_kmh=15.0 + h, gust_kmh=25.0 + h,
            precip_1h_mm=0.5, cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE, wind_chill_c=8.0 + h,
        )
        for h in range(0, 24)
    ]
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(data=data, meta=meta),
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="test",
    )


def _label_of(metric_id: str) -> str:
    """Metrik-ID -> Spaltenbeschriftung, wie sie in der Mail steht."""
    col_key = get_metric(metric_id).col_key
    for key, label, _ in get_col_defs():
        if key == col_key:
            return label
    raise AssertionError(f"keine Spaltenbeschriftung fuer {metric_id}")


def _place(config, metric_ids: list[str], bucket: str = "primary") -> None:
    """Setzt Bucket + Position genau so, wie der Editor es beim Ziehen tut."""
    by_id = {mc.metric_id: mc for mc in config.metrics}
    for position, metric_id in enumerate(metric_ids):
        by_id[metric_id].bucket = bucket
        by_id[metric_id].order = position


def _mail_columns_html(config) -> list[str]:
    """Spaltenbeschriftungen der HTML-Stundentabelle, links -> rechts."""
    report = TripReportFormatter().format_email(
        [_segment()], "Reihenfolge Trip", "morning", display_config=config,
    )
    head = re.search(r"<thead><tr>(.*?)</tr></thead>", report.email_html, re.S)
    assert head, "Stundentabelle ohne Kopfzeile gerendert"
    cells = [
        re.sub(r"<[^>]+>", "", th).strip()
        for th in re.findall(r"<th[^>]*>.*?</th>", head.group(1), re.S)
    ]
    return [c for c in cells if c not in _FRAME_COLUMNS_HTML]


def _mail_columns_plain(config) -> list[str]:
    """Spaltenbeschriftungen der Plain-Text-Stundentabelle, links -> rechts."""
    report = TripReportFormatter().format_email(
        [_segment()], "Reihenfolge Trip", "morning", display_config=config,
    )
    for line in report.email_plain.splitlines():
        stripped = line.strip()
        if stripped.startswith("Time"):
            cells = re.split(r"\s{2,}", stripped)
            return [c for c in cells if c != "Time"]
    raise AssertionError("keine Plain-Text-Kopfzeile gefunden")


# --- AC-1 -------------------------------------------------------------

def test_configured_order_drives_plain_columns():
    """AC-1: Eine nach vorn gezogene Groesse steht auch im Plain-Text vorn."""
    config = build_default_display_config()
    active = [mc.metric_id for mc in config.metrics if mc.enabled]
    # Nutzer zieht die letzte Groesse auf Position 1.
    _place(config, [active[-1]] + active[:-1])

    columns = _mail_columns_plain(config)
    moved_to_front = _label_of(active[-1])

    assert columns[0] == moved_to_front, (
        f"Die nach vorn gezogene Groesse '{moved_to_front}' muesste im "
        f"Plain-Text die erste Spalte sein, tatsaechlich: {columns}"
    )


# --- AC-2 -------------------------------------------------------------

def test_swapping_two_positions_swaps_plain_columns():
    """AC-2: Werden zwei Positionen getauscht, tauschen auch die
    Plain-Text-Spalten."""
    order = ["temperature", "wind", "gust", "precipitation", "cloud_total"]

    config_a = build_default_display_config()
    _place(config_a, order)
    columns_a = _mail_columns_plain(config_a)

    config_b = build_default_display_config()
    _place(config_b, ["wind", "temperature"] + order[2:])
    columns_b = _mail_columns_plain(config_b)

    temp, wind = _label_of("temperature"), _label_of("wind")
    assert columns_a.index(temp) < columns_a.index(wind)
    assert columns_b.index(wind) < columns_b.index(temp), (
        f"Nach dem Tausch muesste '{wind}' im Plain-Text vor '{temp}' stehen, "
        f"tatsaechlich: {columns_b}"
    )


# --- AC-3 -------------------------------------------------------------

def test_legacy_config_plain_matches_html_baseline():
    """AC-3: Altbestand (alle order=0) -- die Plain-Reihenfolge deckt sich
    mit der bereits verifizierten HTML-Baseline aus Scheibe 1 (inkl. TmpMin
    am Ende statt an Katalog-Position 2, s. AC-5). Die Sortierung erfindet
    fuer Altbestand keine neue Reihenfolge."""
    config = build_default_display_config()
    assert all(mc.order == 0 for mc in config.metrics if mc.enabled), (
        "Vorbedingung verletzt: die Vorgabe-Konfiguration traegt bereits "
        "Positionen, dieser Test prueft dann nicht mehr den Altbestand"
    )

    baseline = [
        "Temp", "Feels", "Wind", "Gust", "Rain",
        "Thdr", "SnowL", "Cloud", "Sun", "TmpMin",
    ]
    columns = _mail_columns_plain(config)
    assert columns == baseline, (
        "Plain-Altbestand-Reihenfolge weicht von der HTML-Baseline "
        f"(Scheibe 1) ab -- Plain zeigt: {columns}"
    )


# --- AC-4 -------------------------------------------------------------

def test_telegram_layout_still_unaffected_by_plain_fix():
    """AC-4: Diese Scheibe aendert nur helpers.py/html.py/plain.py -- Telegram
    (channel_layout.render_for_channel) bleibt unberuehrt. Regressionsschutz,
    analog test_mail_column_order.py::test_telegram_layout_is_not_disturbed."""
    def _fully_placed():
        cfg = build_default_display_config()
        active = [mc.metric_id for mc in cfg.metrics if mc.enabled]
        _place(cfg, ["wind", "temperature", "gust", "precipitation"]
               + [m for m in active
                  if m not in {"wind", "temperature", "gust", "precipitation"}])
        return cfg

    before = render_for_channel("telegram", _fully_placed(), "morning").table_columns

    scrambled = _fully_placed()
    scrambled.metrics = list(reversed(scrambled.metrics))

    after = render_for_channel("telegram", scrambled, "morning").table_columns

    assert before == after, (
        "Telegram-Spalten haben sich veraendert, obwohl diese Scheibe "
        f"Telegram nicht beruehrt: {before} vs. {after}"
    )


# --- AC-5 -------------------------------------------------------------

def test_tmpmin_position_matches_between_html_and_plain():
    """AC-5: TmpMin steht im Plain-Teil an derselben Stelle wie im HTML-Teil
    derselben Mail -- Plain gleicht sich an das bereits produktive
    HTML-Verhalten an (Konvergenzrichtung, nicht umgekehrt)."""
    config = build_default_display_config()

    html_columns = _mail_columns_html(config)
    plain_columns = _mail_columns_plain(config)
    tmpmin = _label_of("temperature_cold")

    assert html_columns == plain_columns, (
        "HTML- und Plain-Teil derselben Mail zeigen unterschiedliche "
        f"Spaltenfolgen: HTML={html_columns} Plain={plain_columns}"
    )
    assert plain_columns[-1] == tmpmin, (
        f"'{tmpmin}' muesste im Plain-Text die letzte Spalte sein "
        f"(wie im HTML-Teil), tatsaechlich: {plain_columns}"
    )


# --- AC-7 -------------------------------------------------------------

def _minimal_dc(order: list[str]) -> UnifiedWeatherDisplayConfig:
    metrics = [
        MetricConfig(metric_id=mid, enabled=True, bucket="primary", order=i)
        for i, mid in enumerate(order)
    ]
    return UnifiedWeatherDisplayConfig(trip_id="t-night-sync", metrics=metrics)


def _header_lines(text: str) -> list[list[str]]:
    """Alle Kopfzeilen (Segment- UND Nacht-Tabelle) einer Plain-Text-Mail."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Time"):
            cells = re.split(r"\s{2,}", stripped)
            lines.append([c for c in cells if c != "Time"])
    return lines


def test_night_table_follows_same_order_as_segment_table():
    """AC-7: Nacht-Tabelle und Segment-Tabelle nutzen im Plain-Text dieselbe
    konfigurierte Reihenfolge -- beide Aufrufstellen von
    `_render_text_table()` (plain.py:280 und plain.py:287) muessen
    denselben `col_order` erhalten."""
    dc = _minimal_dc(["gust", "wind", "temperature"])
    seg_row = {"time": "08:00", "temp": 12.0, "wind": 15.0, "gust": 25.0}
    night_row = {"time": "22:00", "temp": 5.0, "wind": 8.0, "gust": 12.0}

    plain = render_plain(
        segments=[_segment()], seg_tables=[[seg_row]], trip_name="Nacht Test",
        report_type="morning", dc=dc, night_rows=[night_row],
        thunder_forecast=None, changes=None, stage_name=None,
        stage_stats=None, multi_day_trend=None, compact_summary=None,
        tz=TZ, friendly_keys=set(),
    )

    headers = _header_lines(plain)
    assert len(headers) == 2, (
        f"Erwarte genau zwei Kopfzeilen (Segment + Nacht), gefunden: {headers}"
    )
    expected = ["Gust", "Wind", "Temp"]
    assert headers[0] == expected, f"Segment-Tabelle folgt nicht der Reihenfolge: {headers[0]}"
    assert headers[1] == expected, (
        f"Nacht-Tabelle folgt nicht derselben Reihenfolge wie die "
        f"Segment-Tabelle: {headers[1]} (erwartet {expected})"
    )
