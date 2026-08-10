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
# Adversary F001 (Fix-Loop, #1231 Slice 7 / #1425 S1): die Klassen-Signatur
# allein ist unsichtbar (der Trip-<style>-Block referenziert sie nicht) -- die
# eigentliche Sichtbarkeit ist der additive gruene Border-Balken
# (corridor_mark.MARK_BORDER, G_SUCCESS aus design_tokens).
_MARK_STYLE = "border-left:3px solid #3a7d44"


def _tr_containing(html: str, time_label: str) -> str:
    marker = f'data-label="Time">{time_label}</td>'
    start = html.rindex("<tr", 0, html.index(marker))
    end = html.index("</tr>", html.index(marker)) + len("</tr>")
    return html[start:end]


def _cell_in(tr_html: str, data_label: str) -> str:
    """Wie ``_cell``, aber innerhalb EINER bereits isolierten Tabellenzeile --
    noetig, sobald eine Fixture mehrere Stunden rendert (``_cell`` trifft sonst
    immer die erste Stunde und koennte eine Umkehrung nicht sehen)."""
    marker = f'data-label="{data_label}"'
    idx = tr_html.index(marker)
    start = tr_html.rindex("<td", 0, idx)
    end = tr_html.index("</td>", idx) + len("</td>")
    return tr_html[start:end]


def _cell(html: str, data_label: str) -> str:
    """Isoliert genau die Zelle einer Spalte ueber ihr ``data-label``
    (Mobile-Beschriftung, vom Renderer je <td> gesetzt) -- damit beweist eine
    Marken-Signatur die Markierung DIESER Spalte, nicht irgendeiner."""
    marker = f'data-label="{data_label}"'
    idx = html.index(marker)
    start = html.rindex("<td", 0, idx)
    end = html.index("</td>", idx) + len("</td>")
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


def _render_hours(*, corridors, enabled: set[str], dps: list[ForecastDataPoint]) -> str:
    """Wie ``_render``, aber mit MEHREREN Stunden in einer Etappen-Tabelle --
    nur so laesst sich beweisen, dass eine Marke genau eine der beiden Stunden
    trifft (eine Ein-Stunden-Fixture kann eine Umkehrung nicht zeigen)."""
    from output.renderers.email import render_email
    from output.renderers.email.helpers import dp_to_row
    from output.tokens.dto import TokenLine

    dc = _dc(enabled)
    tz = ZoneInfo("Europe/Berlin")
    rows = [dp_to_row(dp, dc, tz=tz) for dp in dps]
    tl = TokenLine(trip_name="Test-Trip", report_type="evening", stage_name="Etappe 1")
    html, _plain = render_email(
        tl, segments=[_seg_data(dps[0])], seg_tables=[rows], display_config=dc,
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


# ===========================================================================
# Issue #1425 Schritt 2, Teil 2, Scheibe A -- die 15 nicht-summen
# Katalog-Groessen muessen im Trip-Briefing genauso markieren wie die 5 alten
# Route-Keys. SPEC: docs/specs/modules/fix_1425_s2b_markier_wirkung.md
#
# Warum der komplette Weg (render_email) und nicht _render_html_table: der
# Fehler sitzt genau in der Aufloesung Korridor-Metrik -> Spalten-Key
# (html.py::TRIP_CORRIDOR_METRIC_TO_COL_KEY), die _render_html_table gar nicht
# durchlaeuft -- wer `marks` von Hand baut, prueft am Fehler vorbei.
# ===========================================================================

class TestTripMailCatalogMetricCorridorMark:
    def test_ac1_uv_korridor_markiert_uv_zelle(self):
        """AC-1 (Extremum-Vertreter, Audit-Fall aus dem Issue-Kommentar
        2026-07-31): Korridor uv_index_max [6, offen] + aktive UV-Spalte
        + Stundenwert 8. RED: die Zelle wird gerendert, traegt aber
        keine Marken-Signatur -- der Katalog-Schluessel fehlt in
        TRIP_CORRIDOR_METRIC_TO_COL_KEY, mark_lookup_multi() ueberspringt den
        Korridor still (corridor_mark.py:43).

        Issue #1585: Traeger-Groesse von cape_max_jkg auf uv_index_max
        gewechselt -- CAPE ist zentral nicht mehr waehlbar, sein Korridor
        loest zu None auf und markiert nichts mehr (AC-10). Der
        Pruefgegenstand (Katalog-Groesse ausserhalb der 5 alten Route-Keys
        markiert korrekt) ist unveraendert; die Abwesenheit der
        CAPE-Markierung sichert test_ac10_cape_korridor_markiert_nicht_mehr."""
        dp = _dp(t2m_c=10.0, uv_index=8.0)
        corridors = [Corridor(metric="uv_index_max", range=[6, None], mark=True)]
        html = _render(corridors=corridors, enabled={"temperature", "uv_index"}, dp=dp)

        cell = _cell(html, "UV")
        assert _MARK in cell, (
            "8 liegt in [6, offen] -- die UV-Zelle muss die "
            "Marken-Signatur tragen (heute wirkungsloser Schalter)"
        )
        assert _MARK_STYLE in cell, "UV-Zelle muss den sichtbaren gruenen Border-Balken tragen"

    def test_ac1_uv_korridor_ausserhalb_markiert_nicht(self):
        """Gegenprobe zu AC-1: 3 liegt UNTER der Untergrenze 6 --
        die Zelle darf nicht markiert werden. Verhindert, dass die
        GREEN-Implementierung pauschal jede Zelle einer Korridor-Spalte
        markiert."""
        dp = _dp(t2m_c=10.0, uv_index=3.0)
        corridors = [Corridor(metric="uv_index_max", range=[6, None], mark=True)]
        html = _render(corridors=corridors, enabled={"temperature", "uv_index"}, dp=dp)

        cell = _cell(html, "UV")
        assert _MARK not in cell, "3 liegt ausserhalb [6, offen] -- keine Markierung"
        assert _MARK_STYLE not in cell, "3 darf keinen Border-Balken tragen"

    def test_ac1_uv_korridor_mit_mark_false_markiert_nichts(self):
        """Gegenprobe zu AC-1: derselbe Korridor als reiner Alarm-Korridor
        (mark=False) darf auch nach der Katalog-Aufloesung nichts markieren."""
        dp = _dp(t2m_c=10.0, uv_index=8.0)
        corridors = [Corridor(metric="uv_index_max", range=[6, None], notify=True, mark=False)]
        html = _render(corridors=corridors, enabled={"temperature", "uv_index"}, dp=dp)

        assert _MARK not in html, "mark=False (notify-only) darf keine Markierung erzeugen"

    def test_ac10_cape_korridor_markiert_nicht_mehr(self):
        """Issue #1585 AC-10: ein Bestands-Korridor auf cape_max_jkg markiert
        nichts mehr -- CAPE hat keine Spalte mehr, und
        resolve_corridor_summary_field() loest den Schluessel zu None auf.
        Kein Crash, keine Markierung, kein Rest der frueheren CAPE-Zelle."""
        dp = _dp(t2m_c=10.0, cape_jkg=1500.0)
        corridors = [Corridor(metric="cape_max_jkg", range=[1000, None], mark=True)]
        html = _render(corridors=corridors, enabled={"temperature", "cape"}, dp=dp)

        assert isinstance(html, str) and html
        assert "CAPE" not in html, "CAPE hat keine Spalte mehr (#1585)"
        assert _MARK not in html, "ein CAPE-Korridor darf nichts mehr markieren"

    def test_ac2_humidity_korridor_markiert_humidity_zelle(self):
        """AC-2 (Mittelwert-Vertreter): Korridor {metric='humidity_avg_pct',
        range=[40, 70], mark=True} + aktive Feuchte-Spalte + Stundenwert 55 %.

        Ist-Zustand (RED): keine Marken-Signatur -- selbe Wurzel wie AC-1."""
        dp = _dp(t2m_c=10.0, humidity_pct=55)
        corridors = [Corridor(metric="humidity_avg_pct", range=[40, 70], mark=True)]
        html = _render(corridors=corridors, enabled={"temperature", "humidity"}, dp=dp)

        cell = _cell(html, "Humid")
        assert _MARK in cell, "55 % liegt in [40, 70] -- die Feuchte-Zelle muss markiert sein"
        assert _MARK_STYLE in cell, "Feuchte-Zelle muss den sichtbaren gruenen Border-Balken tragen"

    def test_ac2_humidity_korridor_ausserhalb_markiert_nicht(self):
        """Gegenprobe zu AC-2: 90 % liegt ueber der Obergrenze 70."""
        dp = _dp(t2m_c=10.0, humidity_pct=90)
        corridors = [Corridor(metric="humidity_avg_pct", range=[40, 70], mark=True)]
        html = _render(corridors=corridors, enabled={"temperature", "humidity"}, dp=dp)

        cell = _cell(html, "Humid")
        assert _MARK not in cell, "90 % liegt ausserhalb [40, 70] -- keine Markierung"
        assert _MARK_STYLE not in cell, "90 % darf keinen Border-Balken tragen"

    def test_ac3_snow_line_markiert_weiterhin_die_schneegrenzen_spalte(self):
        """AC-3 (Regressionsschutz Schritt 1, muss von Anfang an GRUEN sein):
        'snow_line' ist einer der 5 alten Route-Keys und mappt auf die
        Spalte 'snow_limit' (col_label 'SnowL'). Die zentrale Registry fuehrt
        'snowfall_limit' UND 'freezing_level' getrennt -- die Katalog-
        Aufloesung darf diese Zuordnung nicht verbiegen."""
        dp = _dp(t2m_c=10.0, snowfall_limit_m=2000)
        corridors = [Corridor(metric="snow_line", range=[1500, None], mark=True)]
        html = _render(corridors=corridors, enabled={"temperature", "snowfall_limit"}, dp=dp)

        cell = _cell(html, "SnowL")
        assert _MARK in cell, "snow_line muss weiterhin die Schneefallgrenzen-Spalte markieren"
        assert _MARK_STYLE in cell, "snow_line-Markierung muss sichtbar bleiben"

    def test_ac4_sunny_hours_korridor_markiert_keine_stundenzelle(self):
        """AC-4 Backend-Teil (muss von Anfang an GRUEN sein und es bleiben):
        'sunny_hours_h' ist eine TAGES-Summe (aggregation='sum'). Der
        Stundenwert der Sonnen-Spalte ist eine ganz andere Groesse
        (Strahlung), der eingestellte Bereich [0, 1000] wuerde ihn
        rechnerisch einschliessen -- markiert werden darf trotzdem nichts."""
        dp = _dp(t2m_c=10.0, dni_wm2=500.0)
        corridors = [Corridor(metric="sunny_hours_h", range=[0, 1000], mark=True)]
        html = _render(corridors=corridors, enabled={"temperature", "sunshine"}, dp=dp)

        assert _MARK not in html, (
            "Tages-Summe sunny_hours_h darf NIE gegen einen Stundenwert gematcht "
            "werden -- sonst markiert der Trip eine fachlich falsche Zelle"
        )
        assert _MARK_STYLE not in html, "kein Border-Balken fuer eine Tages-Summe"

    def test_ac4_neuschnee_summen_korridor_markiert_keine_stundenzelle(self):
        """AC-4 Backend-Teil, zweite Summe: 'snow_new_sum_cm'
        (aggregation='sum') -- Stundenwert 3 cm laege in [0, 50], darf aber
        nicht markieren."""
        dp = _dp(t2m_c=-2.0, snow_new_24h_cm=3.0)
        corridors = [Corridor(metric="snow_new_sum_cm", range=[0, 50], mark=True)]
        html = _render(corridors=corridors, enabled={"temperature", "fresh_snow"}, dp=dp)

        assert _MARK not in html, "Tages-Summe snow_new_sum_cm darf keine Stundenzelle markieren"

    def test_ac5_unbekannte_metrik_id_neben_gueltigem_korridor(self):
        """AC-5 (muss von Anfang an GRUEN sein): eine Korridor-Liste mit einer
        unbekannten/nicht aufloesbaren Metrik-ID (Freitext, Go kennt kein Enum
        fuer Corridor.Metric) rendert ohne Absturz, und der gueltige Korridor
        derselben Liste markiert weiterhin."""
        dp = _dp(t2m_c=10.0, gust_kmh=80.0)
        corridors = [
            Corridor(metric="voellig_unbekannte_groesse_xyz", range=[0, 1], mark=True),
            Corridor(metric="", range=[0, 1], mark=True),
            Corridor(metric="wind_gust", range=[None, 90], mark=True),
        ]
        html = _render(corridors=corridors, enabled={"temperature", "gust"}, dp=dp)

        assert isinstance(html, str) and len(html) > 0, "Rendern darf nicht scheitern"
        cell = _cell(html, "Gust")
        assert _MARK in cell, "der gueltige wind_gust-Korridor muss trotz Nachbar-Muell markieren"
        assert _MARK_STYLE in cell, "Markierung des gueltigen Korridors muss sichtbar bleiben"

    def test_ac5_enum_korridor_stuerzt_nicht_ab_und_markiert_nicht(self):
        """AC-5 (Absturzschutz, Adversary-Fund F001): 'precip_type_dominant'
        ist die einzige Katalog-Groesse mit kind='enum'. Ihr Stundenwert ist
        eine Enum-Instanz (PrecipType), die corridor_inside() nicht gegen die
        Zahlengrenzen eines Korridors vergleichen kann. Wuerde die Aufloesung
        (build_trip_corridor_id_map) diese Groesse aufnehmen, stuerzte die
        komplette Trip-Mail ab:
        ``TypeError: '<' not supported between instances of 'PrecipType' and
        'int'`` -- per Hand belegt durch Entfernen des kind=='enum'-Astes.

        Erwartung: rendert durch, PType-Zelle bleibt unmarkiert."""
        from app.models import PrecipType

        dp = _dp(t2m_c=10.0, precip_type=PrecipType.RAIN)
        corridors = [Corridor(metric="precip_type_dominant", range=[0, 1], mark=True)]
        html = _render(corridors=corridors, enabled={"temperature", "precip_type"}, dp=dp)

        assert isinstance(html, str) and len(html) > 0, "Enum-Korridor darf die Trip-Mail nicht sprengen"
        cell = _cell(html, "PType")
        assert _MARK not in cell, "Enum-Spalte darf (noch) nicht markiert werden"
        assert _MARK_STYLE not in cell, "Enum-Spalte darf keinen Border-Balken tragen"

    def test_ac5_unbekannte_metrik_id_neben_katalog_korridor(self):
        """AC-5 fuer den NEUEN Aufloesungsweg (RED bis Scheibe A steht): auch
        neben einer unbekannten Metrik-ID muss ein Katalog-Korridor
        markieren -- der Ueberspring-Pfad darf die Aufloesung nicht abbrechen.

        Issue #1585: Traeger-Groesse von cape_max_jkg auf uv_index_max
        gewechselt (s. test_ac1_uv_korridor_markiert_uv_zelle)."""
        dp = _dp(t2m_c=10.0, uv_index=8.0)
        corridors = [
            Corridor(metric="voellig_unbekannte_groesse_xyz", range=[0, 1], mark=True),
            Corridor(metric="uv_index_max", range=[6, None], mark=True),
        ]
        html = _render(corridors=corridors, enabled={"temperature", "uv_index"}, dp=dp)

        cell = _cell(html, "UV")
        assert _MARK in cell, "Katalog-Korridor muss auch neben einer unbekannten Metrik-ID markieren"


# ===========================================================================
# Issue #1425 Schritt 2, Teil 2, Scheibe B -- Gewitter zieht vom Trip-eigenen
# Prozent-Schluessel `thunder_level` (0-100) auf den ordinalen Katalog-Eintrag
# `thunder_level_max` (0/1/2) um.
# SPEC: docs/specs/modules/fix_1425_s2b_gewitter_skala.md
#
# Warum der komplette Weg (render_email): der Fehler sitzt in der Aufloesung
# Korridor-Metrik -> Spalten-Key (html.py::TRIP_CORRIDOR_METRIC_TO_COL_KEY /
# build_trip_corridor_id_map) UND in der Skala des gespeicherten Bereichs.
# Wer `marks` von Hand baut, prueft an beidem vorbei.
#
# Stunden-Fixture: 10 Uhr Ortszeit = gewitterfrei (ThunderLevel.NONE),
# 11 Uhr Ortszeit = Gewitter (ThunderLevel.HIGH) -- beide in EINER Tabelle,
# damit eine Umkehrung ueberhaupt sichtbar werden kann.
# ===========================================================================

_THUNDER_COL = "Thdr"  # MetricDefinition('thunder').col_label


def _thunder_hours() -> list[ForecastDataPoint]:
    return [
        _dp(ts=datetime(2026, 7, 30, 8, 0, tzinfo=timezone.utc), t2m_c=10.0,
            thunder_level=ThunderLevel.NONE),
        _dp(ts=datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc), t2m_c=10.0,
            thunder_level=ThunderLevel.HIGH),
    ]


class TestTripThunderOrdinalCorridor:
    def test_ac1_ordinal_korridor_markiert_nur_die_gewitterfreie_stunde(self):
        """AC-1 (Kern-Nachweis): Korridor `thunder_level_max` mit Bereich
        [None, 0] ("bis kein Gewitter") markiert die NONE-Stunde und NICHT die
        HIGH-Stunde.

        Der Backend-Teil dieser Aussage steht bereits seit Scheibe A
        (build_trip_corridor_id_map loest `thunder_level_max` ueber die
        Katalog-Route auf) -- dieser Test friert ihn ein, damit der
        Schluesselwechsel in Scheibe B die einzige noch richtige
        Wirkungsrichtung nicht versehentlich mitreisst."""
        html = _render_hours(
            corridors=[Corridor(metric="thunder_level_max", range=[None, 0], mark=True)],
            enabled={"temperature", "thunder"}, dps=_thunder_hours(),
        )

        frei = _cell_in(_tr_containing(html, "10"), _THUNDER_COL)
        gewitter = _cell_in(_tr_containing(html, "11"), _THUNDER_COL)

        assert _MARK in frei, "kein Gewitter (Ordinal 0) liegt in [offen, kein] -- muss markiert sein"
        assert _MARK_STYLE in frei, "die gewitterfreie Stunde braucht den sichtbaren gruenen Balken"
        assert _MARK not in gewitter, (
            "Gewitter (Ordinal 2) liegt NICHT in [offen, kein] -- die Stunde darf "
            "keine Marken-Signatur tragen (das ist die behobene Umkehrung)"
        )
        assert _MARK_STYLE not in gewitter, "die Gewitterstunde darf keinen gruenen Balken tragen"

    def test_ac1_ordinal_korridor_bis_mittel_markiert_kein_und_mittel_nicht_hoch(self):
        """AC-1 (Gegenprobe zur Stufigkeit): [None, 2] ("bis mittel") -- das
        Ergebnis der Migration der alten Vorgabe "bis 40" -- schliesst MED ein,
        HIGH aber nicht. Verhindert, dass die GREEN-Umsetzung pauschal "nur
        NONE" oder "alles" markiert.

        Issue #1474: die Obergrenze wandert additiv von 1 auf 2 -- die
        Ordinalskala verschiebt sich (LOW schiebt sich bei 1 dazwischen), die
        fachliche Bedeutung "bis mittel" bleibt dieselbe (s.
        metric_format._THUNDER_ORDER, alert_preset.py ORDINAL_LEVEL_BOUNDS)."""
        dps = [
            _dp(ts=datetime(2026, 7, 30, 8, 0, tzinfo=timezone.utc), t2m_c=10.0,
                thunder_level=ThunderLevel.MED),
            _dp(ts=datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc), t2m_c=10.0,
                thunder_level=ThunderLevel.HIGH),
        ]
        html = _render_hours(
            corridors=[Corridor(metric="thunder_level_max", range=[None, 2], mark=True)],
            enabled={"temperature", "thunder"}, dps=dps,
        )

        assert _MARK in _cell_in(_tr_containing(html, "10"), _THUNDER_COL), \
            "mittleres Gewitter (Ordinal 2) liegt in [offen, mittel]"
        assert _MARK not in _cell_in(_tr_containing(html, "11"), _THUNDER_COL), \
            "hohes Gewitter (Ordinal 3) liegt ausserhalb [offen, mittel]"

    def test_umkehrung_prozentschwelle_schliesst_jeden_gewittergrad_ein(self):
        """Wurzel des Fehlers, dauerhaft festgehalten (bleibt auch nach dem Fix
        wahr): Der Stundenwert ist IMMER ein Ordinal 0/1/2
        (metric_format.thunder_ordinal), der alte Trip-Korridor trug aber eine
        PROZENT-Obergrenze. `corridor_inside(<ordinal>, None, 40)` ist deshalb
        fuer JEDEN Gewittergrad wahr -- die Markierung sagte "im Wunschbereich"
        gerade dann, wenn Gewitter herrschte. Der Fehler ist damit eine
        Umkehrung, kein wirkungsloser Schalter."""
        from output.metric_format import thunder_ordinal

        assert corridor_inside(thunder_ordinal(ThunderLevel.NONE), None, 40) is True
        assert corridor_inside(thunder_ordinal(ThunderLevel.MED), None, 40) is True
        assert corridor_inside(thunder_ordinal(ThunderLevel.HIGH), None, 40) is True, (
            "die Umkehrung: auch hohes Gewitter gilt gegen eine Prozent-Schwelle als "
            "'innerhalb' -- genau deshalb zieht Scheibe B den Bereich auf die "
            "Ordinalskala um"
        )
        # Gegenprobe: auf der Ordinalskala trennt derselbe Vergleich sauber.
        assert corridor_inside(thunder_ordinal(ThunderLevel.NONE), None, 0) is True
        assert corridor_inside(thunder_ordinal(ThunderLevel.HIGH), None, 0) is False

    # ── UMKEHRUNG BEHOBEN (war bis zur GREEN-Phase der IST-Fixpunkt) ─────
    # Vorher hielt dieser Test die Umkehrung am gerenderten Briefing fest: der
    # Alt-Korridor `thunder_level`/[None,40] markierte BEIDE Stunden, auch die
    # mit hohem Gewitter. Mit Scheibe B faellt "thunder_level" aus
    # TRIP_CORRIDOR_METRIC_TO_COL_KEY und loest gar nicht mehr auf -> ein nie
    # durch den Editor gelaufener Alt-Korridor markiert NICHTS mehr (statt
    # falsch). Durch den Editor gelaufene Alt-Korridore sind zu diesem
    # Zeitpunkt bereits auf `thunder_level_max` umgeschluesselt
    # (buildRoutePool, AC-3).
    # ─────────────────────────────────────────────────────────────────────
    def test_alter_prozent_korridor_markiert_keine_stunde_mehr(self):
        """Die Umkehrung ist behoben: der gespeicherte Alt-Korridor
        `thunder_level` mit der Vorgabe "bis 40" loest nicht mehr auf die
        Gewitter-Spalte auf und markiert deshalb KEINE Stunde -- insbesondere
        nicht mehr die mit hohem Gewitter."""
        html = _render_hours(
            corridors=[Corridor(metric="thunder_level", range=[None, 40], mark=True)],
            enabled={"temperature", "thunder"}, dps=_thunder_hours(),
        )

        frei = _cell_in(_tr_containing(html, "10"), _THUNDER_COL)
        gewitter = _cell_in(_tr_containing(html, "11"), _THUNDER_COL)

        assert _MARK not in frei, (
            "der Prozent-Schluessel loest nicht mehr auf -- auch die gewitterfreie "
            "Stunde traegt keine Marke mehr"
        )
        assert _MARK not in gewitter, (
            "die behobene Umkehrung: die Gewitterstunde darf keine Marke mehr "
            "tragen, nur weil Ordinal 2 <= Prozent-Schwelle 40 waere"
        )


class TestTripThunderKeyMigrationBackend:
    def test_ac6_alter_prozentschluessel_ist_aus_der_uebergangs_zuordnung_entfernt(self):
        """AC-6 (RED): nach dem Umzug traegt kein Wertebereich mehr den
        Prozent-Schluessel `thunder_level` -- der explizite Uebergangs-Eintrag
        faellt, damit ein nie durch den Editor gelaufener Alt-Korridor nicht
        weiter mit der falschen Skala markiert. Die vier uebrigen Route-Keys
        bleiben, weil sie keinen 1:1-Katalog-Ersatz haben."""
        from output.renderers.email.html import TRIP_CORRIDOR_METRIC_TO_COL_KEY

        assert "thunder_level" not in TRIP_CORRIDOR_METRIC_TO_COL_KEY, (
            "AC-6 FAIL: der Prozent-Schluessel steht noch in der Uebergangs-Zuordnung "
            "-- ein Alt-Korridor wuerde weiterhin invertiert markieren"
        )
        assert set(TRIP_CORRIDOR_METRIC_TO_COL_KEY) == {
            "wind_gust", "temperature_min", "temperature_max", "snow_line",
        }, "nur der Gewitter-Eintrag darf fallen (die vier uebrigen haben keinen Katalog-Ersatz)"

    def test_ac6_ordinaler_katalogschluessel_loest_weiterhin_auf_spalte_thunder_auf(self):
        """AC-6 (Kehrseite): die katalogbasierte Route in
        build_trip_corridor_id_map() bildet `thunder_level_max` weiterhin auf
        die Stundenspalte "thunder" ab -- der Wegfall des expliziten Eintrags
        darf die Aufloesung nicht mitnehmen."""
        from output.renderers.email.html import build_trip_corridor_id_map

        id_map = build_trip_corridor_id_map()
        assert id_map.get("thunder_level_max") == "thunder", (
            "AC-6 FAIL: der ordinale Katalog-Schluessel loest nicht mehr auf die "
            "Gewitter-Spalte auf -- die Markierung waere komplett wirkungslos"
        )

    def test_ac6_unaufloesbarer_korridor_neben_gewitter_korridor_bricht_nichts(self):
        """AC-6 (Absturzschutz): eine Korridor-Liste mit einer nicht
        aufloesbaren Metrik-Kennung neben dem gueltigen Gewitter-Korridor
        rendert durch; der gueltige Korridor markiert weiterhin richtig."""
        corridors = [
            Corridor(metric="voellig_unbekannte_groesse_xyz", range=[0, 1], mark=True),
            Corridor(metric="thunder_level_max", range=[None, 0], mark=True),
        ]
        html = _render_hours(
            corridors=corridors, enabled={"temperature", "thunder"}, dps=_thunder_hours(),
        )

        assert isinstance(html, str) and len(html) > 0, "Rendern darf nicht scheitern"
        assert _MARK in _cell_in(_tr_containing(html, "10"), _THUNDER_COL), \
            "der gueltige Gewitter-Korridor muss trotz Nachbar-Muell markieren"
        assert _MARK not in _cell_in(_tr_containing(html, "11"), _THUNDER_COL), \
            "und die Gewitterstunde weiterhin nicht"


class TestTripLegacyRouteKeysStillMark:
    """Scheibe-A-Regression (muss durchgehend GRUEN bleiben): die vier
    UEBRIGEN alten Route-Kennungen markieren unveraendert weiter -- nur
    Gewitter zieht um."""

    def test_wind_gust_markiert_weiterhin(self):
        dp = _dp(t2m_c=10.0, gust_kmh=80.0)
        html = _render(corridors=[Corridor(metric="wind_gust", range=[None, 90], mark=True)],
                       enabled={"temperature", "gust"}, dp=dp)
        assert _MARK in _cell(html, "Gust")

    def test_temperature_min_markiert_weiterhin(self):
        dp = _dp(t2m_c=10.0)
        html = _render(corridors=[Corridor(metric="temperature_min", range=[5, None], mark=True)],
                       enabled={"temperature"}, dp=dp)
        assert _MARK in _cell(html, "Temp")

    def test_temperature_max_markiert_weiterhin(self):
        dp = _dp(t2m_c=10.0)
        html = _render(corridors=[Corridor(metric="temperature_max", range=[None, 20], mark=True)],
                       enabled={"temperature"}, dp=dp)
        assert _MARK in _cell(html, "Temp")

    def test_snow_line_markiert_weiterhin(self):
        dp = _dp(t2m_c=10.0, snowfall_limit_m=2000)
        html = _render(corridors=[Corridor(metric="snow_line", range=[1500, None], mark=True)],
                       enabled={"temperature", "snowfall_limit"}, dp=dp)
        assert _MARK in _cell(html, "SnowL")
