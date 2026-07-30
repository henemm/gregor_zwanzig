"""Trip-Mail: Korridor-mark-Markierung wirkt im Briefing (Issue #1425 Schritt 1).

Bisher wurde ``Trip.corridors`` von keinem Trip-Ausgabeweg gelesen (Reiter
*Wertebereiche* im Trip war wirkungslos). Dieser Test beweist die Wirkung
ueber echte Renderer-Aufrufe (``_render_html_table`` und den vollen
``render_email``-Adapter) -- kein Mock, kein Dateiinhalt-Check.

corridor_inside() (src/services/corridor_match.py) bleibt die einzige
Match-Quelle, geteilt mit dem Ortsvergleich ueber
``output/renderers/email/corridor_mark.py`` (AC-4).

SPEC: docs/specs/modules/fix_1425_trip_wertebereiche_wirkung.md
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.models import Corridor, ForecastDataPoint, ThunderLevel
from services.corridor_match import corridor_inside

_MARK = 'class="corridor-mark"'


def _tr_containing(html: str, time_label: str) -> str:
    marker = f'data-label="Time">{time_label}</td>'
    start = html.rindex("<tr", 0, html.index(marker))
    end = html.index("</tr>", html.index(marker)) + len("</tr>")
    return html[start:end]


# ---------------------------------------------------------------------------
# AC-1/AC-2/AC-6 -- unit-level gegen _render_html_table (marks direkt gebaut)
# ---------------------------------------------------------------------------

class TestTripHourTableCorridorMark:
    def test_ac1_zelle_innerhalb_markiert_ausserhalb_nicht(self):
        """AC-1: Wert 5.0 (innerhalb [None,20]) markiert, 25.0 (ausserhalb)
        nicht. Vor dieser Aenderung akzeptierte ``_render_html_table`` gar
        keinen ``marks``-Parameter -- Gegenprobe:
        ``TypeError: _render_html_table() got an unexpected keyword
        argument 'marks'`` (manuell gegen den HEAD-Stand von html.py
        verifiziert, s. Entwickler-Bericht)."""
        from output.renderers.email.html import _render_html_table

        rows = [{"time": "08:00", "temp": 5.0}, {"time": "09:00", "temp": 25.0}]
        marks = {"temp": [Corridor(metric="temperature_max", range=[None, 20], mark=True)]}
        html = _render_html_table(rows, friendly_keys=set(), indicator_keys=set(), marks=marks)

        assert _MARK in _tr_containing(html, "08:00"), "5.0 liegt innerhalb -- muss markiert sein"
        assert _MARK not in _tr_containing(html, "09:00"), "25.0 liegt ausserhalb -- darf nicht markiert sein"

    def test_ac2_notify_only_corridor_markiert_nichts(self):
        """AC-2: mark=False (reiner Alarm-Korridor) darf keine Markierung
        setzen -- der Filter sitzt in mark_lookup_multi() (geteilter
        Baustein, corridor_mark.py), NICHT in _render_html_table selbst."""
        from output.renderers.email.html import (
            TRIP_CORRIDOR_METRIC_TO_COL_KEY, _render_html_table,
        )
        from output.renderers.email.corridor_mark import mark_lookup_multi

        rows = [{"time": "08:00", "temp": 5.0}]
        corridors = [Corridor(metric="temperature_max", range=[None, 20], notify=True, mark=False)]
        marks = mark_lookup_multi(corridors, TRIP_CORRIDOR_METRIC_TO_COL_KEY)
        html = _render_html_table(rows, friendly_keys=set(), indicator_keys=set(), marks=marks)

        assert _MARK not in html, "mark=False (notify-only) darf keine Markierung erzeugen"

    def test_ac6_gewitter_ordinal_markiert_nur_none(self):
        """AC-6: ThunderLevel wird ueber thunder_ordinal() verglichen, nicht
        als Enum-Instanz. Corridor{range=[None,0]} ('nur kein Gewitter')
        markiert NONE (Ordinal 0), nicht HIGH (Ordinal 2)."""
        from output.renderers.email.html import _render_html_table

        rows = [
            {"time": "08:00", "thunder": ThunderLevel.NONE},
            {"time": "09:00", "thunder": ThunderLevel.HIGH},
        ]
        marks = {"thunder": [Corridor(metric="thunder_level", range=[None, 0], mark=True)]}
        html = _render_html_table(rows, friendly_keys=set(), indicator_keys=set(), marks=marks)

        assert _MARK in _tr_containing(html, "08:00"), "NONE (Ordinal 0) muss markiert sein"
        assert _MARK not in _tr_containing(html, "09:00"), "HIGH (Ordinal 2) darf nicht markiert sein"

    def test_gewitter_prozent_korridor_gegen_ordinalskala_kein_absturz(self):
        """Bekannter, auf Schritt 2 verschobener Konflikt (s. Spec Abschnitt
        'Was NICHT Teil von Schritt 1 ist'): der Trip speichert Gewitter
        heute als Prozent 0-100 (Vorgabe 40), der Vergleichswert ist ein
        Ordinal 0-2. Ein Prozent-Korridor {range=[None,40]} schliesst dann
        JEDES Ordinal (0,1,2 <= 40) ein -- fachlich unsinnig, aber kein
        Crash und keine Exception."""
        from output.renderers.email.html import _render_html_table

        rows = [{"time": "08:00", "thunder": ThunderLevel.HIGH}]
        marks = {"thunder": [Corridor(metric="thunder_level", range=[None, 40], mark=True)]}
        html = _render_html_table(rows, friendly_keys=set(), indicator_keys=set(), marks=marks)

        assert _MARK in html, (
            "Dokumentierter Ist-Zustand: Ordinal 2 <= Prozent-Schwelle 40 -- "
            "wird (unsinnig, aber ohne Absturz) markiert."
        )


# ---------------------------------------------------------------------------
# AC-3/AC-4/AC-5 -- Integration ueber den echten Durchreichweg (render_email)
# ---------------------------------------------------------------------------

def _dp(**kwargs) -> ForecastDataPoint:
    kwargs.setdefault("ts", datetime(2026, 7, 30, 8, 0, tzinfo=timezone.utc))
    return ForecastDataPoint(**kwargs)


def _dc(enabled: set[str]):
    from app.metric_catalog import build_default_display_config
    dc = build_default_display_config()
    for mc in dc.metrics:
        mc.enabled = mc.metric_id in enabled
    return dc


def _seg_data(dp: ForecastDataPoint):
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 7, 30, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 30, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[dp])
    agg = SegmentWeatherSummary(
        temp_min_c=dp.t2m_c, temp_max_c=dp.t2m_c, temp_avg_c=dp.t2m_c,
        wind_max_kmh=dp.wind10m_kmh or 0.0, gust_max_kmh=dp.gust_kmh or 0.0,
        precip_sum_mm=0.0, cloud_avg_pct=0, humidity_avg_pct=50,
        thunder_level_max=dp.thunder_level,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _render(*, corridors, enabled: set[str], dp: ForecastDataPoint) -> str:
    """ECHTER render_email-Aufruf (Durchreichweg trip_report.py:181 ->
    render_email -> render_html)."""
    from output.renderers.email import render_email
    from output.renderers.email.helpers import dp_to_row
    from output.tokens.dto import TokenLine

    dc = _dc(enabled)
    tz = ZoneInfo("Europe/Berlin")
    row = dp_to_row(dp, dc, tz=tz)
    tl = TokenLine(trip_name="Test-Trip", report_type="evening", stage_name="Etappe 1")
    html, _plain = render_email(
        tl, segments=[_seg_data(dp)], seg_tables=[[row]], display_config=dc,
        tz=tz, friendly_keys=set(), corridors=corridors,
    )
    return html


class TestTripMailCorridorMarkWiring:
    def test_ac1_wind_gust_korridor_markiert_ueber_render_email(self):
        """AC-1 (Durchreichweg): Route-Key 'wind_gust' -> col_key 'gust'
        (TRIP_CORRIDOR_METRIC_TO_COL_KEY) -- der volle Adapter markiert."""
        dp = _dp(t2m_c=10.0, gust_kmh=80.0, thunder_level=ThunderLevel.NONE)
        corridors = [Corridor(metric="wind_gust", range=[None, 90], mark=True)]
        html = _render(corridors=corridors, enabled={"temperature", "gust"}, dp=dp)

        assert _MARK in html, "wind_gust-Korridor muss die Gust-Zelle markieren (80 <= 90)"

    def test_ac3_ohne_korridore_unveraendert(self):
        """AC-3: corridors=None/[] darf am HTML nichts aendern -- weder
        zusaetzliches CSS noch zusaetzliche Klassen (Vorbild compare_html.py,
        Baseline-Schutz test_kein_corridor_rendert_wie_bisher)."""
        dp = _dp(t2m_c=10.0, gust_kmh=80.0)
        html_none = _render(corridors=None, enabled={"temperature", "gust"}, dp=dp)
        html_empty = _render(corridors=[], enabled={"temperature", "gust"}, dp=dp)

        assert _MARK not in html_none
        assert html_none == html_empty, "corridors=None und corridors=[] muessen identisches HTML ergeben"

    def test_ac4_renderer_spiegelt_corridor_inside_grenzwert(self):
        """AC-4: dieselbe Match-Funktion entscheidet -- Grenzwert (Boeen exakt
        auf der Obergrenze) ist per corridor_inside() inklusiv 'innerhalb',
        der Renderer muss das identisch abbilden (keine zweite Match-Logik)."""
        dp = _dp(t2m_c=10.0, gust_kmh=70.0)
        corridors = [Corridor(metric="wind_gust", range=[None, 70], mark=True)]
        html = _render(corridors=corridors, enabled={"temperature", "gust"}, dp=dp)

        assert corridor_inside(70.0, None, 70) is True, "Erwartungs-Grundlage: Grenzwert zaehlt als innerhalb"
        assert _MARK in html, "Renderer muss corridor_inside() inklusive Grenzwerte spiegeln"

    def test_ac5_wertebereich_fuer_nicht_angezeigte_groesse_bricht_nichts(self):
        """AC-5: ein Korridor fuer eine im Trip nicht angezeigte Groesse
        (snow_line, hier nicht aktiviert) wird still ignoriert -- kein Crash,
        keine Markierung."""
        dp = _dp(t2m_c=10.0, gust_kmh=80.0)
        corridors = [Corridor(metric="snow_line", range=[1500, None], mark=True)]
        html = _render(corridors=corridors, enabled={"temperature", "gust"}, dp=dp)

        assert isinstance(html, str) and len(html) > 0
        assert _MARK not in html, "snow_line ohne sichtbare Spalte darf nichts markieren"
