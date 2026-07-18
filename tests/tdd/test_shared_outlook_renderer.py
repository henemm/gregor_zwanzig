"""TDD RED — Epic #1301 B4: geteilter Ausblick-Renderer.

Extrahiert render_outlook_table()/render_outlook_plain()/build_outlook_row()
aus html.py/plain.py/trip_report_scheduler.py in ein NEUES Modul
``src/output/renderers/email/outlook.py`` (existiert noch nicht -> ImportError
ist der erwartete RED-Grund fuer jeden Test in dieser Datei).

Kern-Schicht, deterministisch: KEINE Mocks/patch()/MagicMock, kein Netz.
Echte ForecastDataPoint-/SegmentWeatherSummary-/Segment-Objekte; echter
Renderpfad ueber render_html()/render_plain() fuer den "Vorher"-Vergleich und
die neue render_outlook_table()/render_outlook_plain()/build_outlook_row() fuer
den extrahierten Baustein. Kein Dateiinhalt-Check.

SPEC: docs/specs/modules/epic_1301_b4_compare_outlook.md AC-1, AC-2, AC-3, AC-6
KONTEXT: docs/context/epic-1301-b4-ausblick.md
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

TZ = ZoneInfo("Europe/Berlin")

# Eindeutiger Marker der Ausblick-Tabelle in html.py (border-top:2px solid
# #1d1c1a ist nur auf dieser einen Tabelle gesetzt, s. html.py:1258).
_OUTLOOK_TABLE_MARKER = "border-top:2px solid #1d1c1a"


# ---------------------------------------------------------------------------
# Helpers — echte Domaenen-Objekte (analog test_issue_898_901_mail_layout.py)
# ---------------------------------------------------------------------------

def _trend_stage(weekday="Mo", name="Etappe X", *, conf=None, temp_lo=12, temp_hi=22,
                  precip_mm=0.5, wind_kmh=15, thunder="NONE", hourly_gust=()):
    """Row-dict wie vom Scheduler gebaut (trip_report_scheduler._build_stage_trend)."""
    row = dict(
        weekday=weekday, name=name,
        temp_lo=temp_lo, temp_hi=temp_hi,
        precip_mm=precip_mm, wind_dir="W", wind_kmh=wind_kmh,
        thunder=thunder, note=None,
        hourly_precip=(), hourly_wind=(), hourly_gust=hourly_gust, hourly_thunder=(),
        rain_probability_pct=40,
    )
    if conf is not None:
        row["confidence_pct"] = conf
    return row


def _build_segments():
    """Minimaler echter Ein-Segment-Fixture, ausreichend fuer render_html/render_plain."""
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )

    def _dp(h):
        return ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=12.0, wind10m_kmh=10.0, gust_kmh=20.0,
            precip_1h_mm=0.0, pop_pct=10, cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE, visibility_m=20000,
        )

    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=400.0, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1200.0, distance_from_start_km=4.2),
        start_time=datetime(2026, 7, 11, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=4.2, ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
                         run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc))
    ts = NormalizedTimeseries(meta=meta, data=[_dp(6), _dp(7), _dp(8), _dp(9)])
    agg = SegmentWeatherSummary(
        temp_min_c=10.0, temp_max_c=14.0, temp_avg_c=12.0,
        wind_max_kmh=20.0, gust_max_kmh=40.0, precip_sum_mm=1.0,
        cloud_avg_pct=50, humidity_avg_pct=55, thunder_level_max=ThunderLevel.NONE,
    )
    return [SegmentWeatherData(segment=seg, timeseries=ts, aggregated=agg,
                                fetched_at=datetime.now(timezone.utc), provider="demo")]


_SIMPLE_ROWS = [{
    "time": "06:00", "temp": 12.0, "_wind_dir_deg": None, "_is_day": True,
    "_dni_wm2": None, "_sunny_hours": 0.0, "_wmo_code": None,
}]


def _common_params(rows):
    from app.metric_catalog import build_default_display_config
    return dict(
        segments=_build_segments(),
        seg_tables=[_SIMPLE_ROWS],
        trip_name="GR20 Test", report_type="morning",
        dc=build_default_display_config(),
        night_rows=[], thunder_forecast=None, changes=None,
        stage_name=None, stage_stats=None,
        multi_day_trend=rows, compact_summary=None, tz=TZ,
        friendly_keys=set(),
    )


def _render_html(rows, **kwargs):
    from output.renderers.email.html import render_html
    params = _common_params(rows)
    params.update(kwargs)
    return render_html(**params)


def _render_plain(rows, **kwargs):
    from output.renderers.email.plain import render_plain
    params = _common_params(rows)
    params.update(kwargs)
    return render_plain(**params)


def _extract_outlook_table_html(html: str) -> str:
    marker_pos = html.index(_OUTLOOK_TABLE_MARKER)
    table_start = html.rindex("<table", 0, marker_pos)
    table_end = html.index("</table>", marker_pos) + len("</table>")
    return html[table_start:table_end]


# ---------------------------------------------------------------------------
# AC-1: render_outlook_table(show_acc=True) byte-identisch zur Trip-Inline-Tabelle
# ---------------------------------------------------------------------------

def test_show_acc_true_html_byte_identical_to_trip_render():
    """AC-1: Given identische Ausblick-Zeilen wie im bisherigen Trip-Renderer /
    When render_outlook_table(rows, show_acc=True) gerendert wird / Then ist
    das Ergebnis byte-identisch zur bisherigen Inline-Tabelle in render_html.

    RED: output.renderers.email.outlook existiert noch nicht -> ImportError.
    """
    from output.renderers.email.outlook import render_outlook_table

    rows = [
        _trend_stage("Mo", "Etappe A", conf=80, temp_lo=9, temp_hi=21, precip_mm=2.5, wind_kmh=18),
        _trend_stage("Di", "Etappe B", conf=65, temp_lo=11, temp_hi=19, precip_mm=0.0, wind_kmh=25),
        _trend_stage("Mi", "Etappe C", conf=None, temp_lo=13, temp_hi=23, precip_mm=6.0, wind_kmh=32),
    ]

    html = _render_html(rows)
    table_before = _extract_outlook_table_html(html)

    table_direct = render_outlook_table(rows, show_acc=True)

    assert table_direct == table_before, (
        "render_outlook_table(show_acc=True) muss byte-identisch zur bisherigen "
        "Inline-Ausblick-Tabelle in render_html sein (Trip-Zeichengleichheit, AC-1).\n"
        f"--- vorher ---\n{table_before}\n--- direkt ---\n{table_direct}"
    )


# ---------------------------------------------------------------------------
# AC-2: show_acc=False laesst die ACC-Spalte vollstaendig entfallen
# ---------------------------------------------------------------------------

def test_show_acc_false_omits_acc_column():
    """AC-2: Given der Compare-Pfad ruft render_outlook_table mit
    show_acc=False auf / When die Tabelle gerendert wird / Then fehlen die
    ACC-<th>-Kopfzelle und die _acc_dot-<td>-Zellen vollstaendig, alle
    uebrigen Spalten bleiben unveraendert; show_acc=True bleibt unveraendert
    (echtes HTML-Parsing statt reinem String-Contains).
    """
    from output.renderers.email.outlook import render_outlook_table

    rows = [
        _trend_stage("Mo", "A", conf=82, temp_lo=8, temp_hi=20),
        _trend_stage("Di", "B", conf=55, temp_lo=10, temp_hi=18),
    ]
    html_true = render_outlook_table(rows, show_acc=True)
    html_false = render_outlook_table(rows, show_acc=False)

    soup_true = BeautifulSoup(html_true, "html.parser")
    soup_false = BeautifulSoup(html_false, "html.parser")

    headers_true = [th.get_text(strip=True) for th in soup_true.find_all("th")]
    headers_false = [th.get_text(strip=True) for th in soup_false.find_all("th")]

    assert "ACC" in headers_true, f"ACC-Header fehlt bei show_acc=True: {headers_true}"
    assert "ACC" not in headers_false, f"ACC-Header noch vorhanden bei show_acc=False: {headers_false}"
    assert headers_false == [h for h in headers_true if h != "ACC"], (
        f"Uebrige Spalten muessen unveraendert bleiben: true={headers_true} false={headers_false}"
    )

    rows_true = soup_true.find("tbody").find_all("tr")
    rows_false = soup_false.find("tbody").find_all("tr")
    assert len(rows_true) == len(rows_false) == 2

    for tr_true, tr_false in zip(rows_true, rows_false):
        tds_true = [td.get_text(strip=True) for td in tr_true.find_all("td")]
        tds_false = [td.get_text(strip=True) for td in tr_false.find_all("td")]
        assert len(tds_true) == len(tds_false) + 1, (
            f"show_acc=False soll genau eine Zelle (ACC-Dot) weniger tragen: "
            f"{tds_true} vs {tds_false}"
        )
        assert tds_true[:-1] == tds_false, (
            f"Uebrige Zellen muessen identisch bleiben: {tds_true} vs {tds_false}"
        )


# ---------------------------------------------------------------------------
# AC-3: build_outlook_row ist eine reine Funktion (kein Netz-/Fetch-Aufruf)
# ---------------------------------------------------------------------------

def test_build_outlook_row_pure_function():
    """AC-3: Given eine SegmentWeatherSummary + Punktliste + Wochentag + tz /
    When build_outlook_row(...) aufgerufen wird / Then entsteht ein Row-Dict
    mit temp_lo/temp_hi/precip_mm/wind_kmh/hourly_gust/thunder/
    rain_probability_pct, ohne einen einzigen Netz- oder Fetch-Aufruf.

    Reiner In-Process-Aufruf ohne jede Netz-/Provider-Fixture -- waere die
    Funktion nicht rein, wuerde dieser Test crashen oder haengen. Der
    Provider-Call-Counter-Test (test_bug_338_openmeteo_call_counter.py) bleibt
    unveraendert gruen, weil build_outlook_row selbst nichts fetcht.
    """
    from app.models import ForecastDataPoint, SegmentWeatherSummary, ThunderLevel
    from output.renderers.email.outlook import build_outlook_row
    from src.output.tokens.dto import HourlyValue

    summary = SegmentWeatherSummary(
        temp_min_c=9.0, temp_max_c=21.0, precip_sum_mm=3.5,
        wind_max_kmh=28.0, thunder_level_max=ThunderLevel.MED,
        pop_max_pct=60,
    )
    points = [
        ForecastDataPoint(ts=datetime(2026, 7, 20, 14, 0, tzinfo=timezone.utc),
                           gust_kmh=42.0, thunder_level=ThunderLevel.MED),
        ForecastDataPoint(ts=datetime(2026, 7, 20, 15, 0, tzinfo=timezone.utc),
                           gust_kmh=38.0, thunder_level=ThunderLevel.NONE),
    ]

    row = build_outlook_row(summary, points, "Mo", ZoneInfo("Europe/Vienna"))

    assert isinstance(row, dict)
    assert row["weekday"] == "Mo"
    assert row["temp_lo"] == 9
    assert row["temp_hi"] == 21
    assert row["precip_mm"] == 3.5
    assert row["wind_kmh"] == 28
    assert row["thunder"] == "MED"
    assert row["rain_probability_pct"] == 60
    assert isinstance(row["hourly_gust"], tuple) and len(row["hourly_gust"]) == 2
    assert all(isinstance(hv, HourlyValue) for hv in row["hourly_gust"])

    # Optionaler sms_thresholds-Kwarg: metric_id -> sms_threshold_<metric>-Key,
    # None-Werte werden gefiltert (analog trip_report_scheduler._build_stage_trend).
    row2 = build_outlook_row(
        summary, points, "Mo", ZoneInfo("Europe/Vienna"),
        sms_thresholds={"precipitation": 5.0, "wind": 30.0, "gust": 50.0, "thunder": None},
    )
    assert row2["sms_threshold_precip"] == 5.0
    assert row2["sms_threshold_wind"] == 30.0
    assert row2["sms_threshold_gust"] == 50.0
    assert "sms_threshold_thunder" not in row2


# ---------------------------------------------------------------------------
# AC-6 (Regression): render_outlook_plain(show_acc=True) zeichengleich zum
# bisherigen Inline-Block in render_plain
# ---------------------------------------------------------------------------

def test_plain_trip_output_unchanged():
    """AC-6 (Regression): Given derselbe Trip-Ausblick / When render_plain
    (ueber render_outlook_plain) den Klartext rendert / Then bleibt der
    Trip-Klartext-Ausblick zeichengleich zum Ist-Zustand.
    """
    from output.renderers.email.outlook import render_outlook_plain

    rows = [
        _trend_stage("Mo", "Etappe A", temp_lo=9, temp_hi=21, precip_mm=2.5, wind_kmh=18),
        _trend_stage("Di", "Etappe B", temp_lo=11, temp_hi=19, precip_mm=0.0, wind_kmh=25),
    ]
    plain = _render_plain(rows)

    start = plain.index("Nächste Etappen")
    end = plain.index("── Antwort-Kommandos ──")
    expected_block = plain[start:end].strip("\n")

    direct_block = render_outlook_plain(rows, show_acc=True)

    assert direct_block.strip("\n") == expected_block, (
        "render_outlook_plain muss den bisherigen Inline-Block in render_plain "
        f"zeichengleich reproduzieren.\nErwartet:\n{expected_block!r}\n"
        f"Erhalten:\n{direct_block!r}"
    )
