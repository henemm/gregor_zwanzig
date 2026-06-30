"""
TDD-Tests für Issue #911 — Briefing-Mail Detail-Korrekturen.

13 ACs aus docs/specs/modules/issue_911_mail_details.md.

RED-Phase: Tests schlagen fehl, bis der Renderer/die Pipeline angepasst sind.

WICHTIG: KEINE Mocks, KEIN patch, KEIN MagicMock.
Geprüft wird das **gerenderte HTML** des Renderers (Verhalten, nicht Dateiinhalt).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest


# ---------------------------------------------------------------------------
# Shared helpers — echte Domänen-Objekte, keine Mocks
# ---------------------------------------------------------------------------

def _common_kwargs():
    from tests.unit.test_renderers_email import _common_kwargs as _ck
    return _ck()


def _trend_stage(
    weekday="Di", name="Test-Etappe",
    temp_min_c=10, temp_max_c=18,
    precip_mm=0.5, wind_dir="W", wind_kmh=17, thunder="NONE", note=None,
    hourly_precip=None, hourly_wind=None, hourly_gust=None, hourly_thunder=None,
    confidence_pct=None,
):
    """Trend-Stage-dict — wie vom Scheduler gebaut."""
    stage = dict(
        weekday=weekday, name=name,
        # F005 (#911): echte Scheduler-Keys (temp_lo/temp_hi), nicht temp_min_c/temp_max_c —
        # sonst testet die Fixture an der Produktion vorbei (N/D-Spalte zeigte „–").
        temp_lo=temp_min_c, temp_hi=temp_max_c,
        precip_mm=precip_mm, wind_dir=wind_dir, wind_kmh=wind_kmh,
        thunder=thunder, note=note,
        hourly_precip=hourly_precip or (),
        hourly_wind=hourly_wind or (),
        hourly_gust=hourly_gust or (),
        hourly_thunder=hourly_thunder or (),
    )
    if confidence_pct is not None:
        stage["confidence_pct"] = confidence_pct
    return stage


def _render(
    trend=None,
    *,
    compact_summary=None,
    day_comparison=None,
    stage_stats=None,
    stability_result=None,
    show_outlook=True,
    show_stability=True,
    sent_at=None,
    dc=None,
    seg_tables=None,
):
    """Ruft render_html mit realistischen Parametern auf."""
    kw = _common_kwargs()
    from src.output.renderers.email.html import render_html
    return render_html(
        segments=kw["segments"],
        seg_tables=seg_tables if seg_tables is not None else kw["seg_tables"],
        trip_name="Test-Trip",
        report_type="evening",
        dc=dc if dc is not None else kw["display_config"],
        night_rows=[],
        thunder_forecast=None,
        changes=None,
        stage_name=kw["stage_name"],
        stage_stats=stage_stats,
        multi_day_trend=trend,
        compact_summary=compact_summary,
        tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=kw["friendly_keys"],
        stability_result=stability_result,
        show_outlook=show_outlook,
        show_stability=show_stability,
        sent_at=sent_at,
        day_comparison=day_comparison,
    )


def _make_day_comparison_better():
    """Erzeugt ein DayComparison-Objekt, das 'besser' triggert."""
    from services.day_comparison import DayComparison
    return DayComparison(
        wind_delta_kmh=-5.0,
        gust_delta_kmh=-8.0,
        precip_delta_mm=-2.0,
        visibility_delta_m=1500.0,
        thunder_delta=0,
        summary="heute bessere Sicht als gestern",
    )


# ---------------------------------------------------------------------------
# AC-1: VORTAGESVERGLEICH-Headline in Akzent-Orange (#c45a2a)
# ---------------------------------------------------------------------------

class TestAC1VortagesvergleichHeadlineColor:
    """AC-1: Given Briefing-Mail mit Vortagsvergleich, When gerendert,
    Then trägt die 'VORTAGESVERGLEICH'-Headline Farbe #c45a2a (nicht #9a978d)."""

    def test_vortagesvergleich_headline_uses_accent_orange(self):
        """Given day_comparison und compact_summary gesetzt / When render_html /
        Then VORTAGESVERGLEICH-Eyebrow hat color:#c45a2a, nicht #9a978d."""
        day_comp = _make_day_comparison_better()
        html = _render(
            compact_summary="Sommerlicher Tag mit Schauerrisiko",
            day_comparison=day_comp,
        )
        # VORTAGESVERGLEICH muss im Output stehen
        assert "VORTAGESVERGLEICH" in html, "VORTAGESVERGLEICH-Headline fehlt"
        # Finde die Position der VORTAGESVERGLEICH-Headline
        pos = html.find("VORTAGESVERGLEICH")
        # Im HTML vor der Headline muss die Akzent-Orange-Farbe #c45a2a stehen
        # (nicht #9a978d — das wäre grau).
        # Suche im Kontext ~500 Zeichen vor dem ersten Vorkommen
        context = html[max(0, pos - 500):pos]
        assert "#c45a2a" in context, (
            f"VORTAGESVERGLEICH-Headline muss mit color:#c45a2a gerendert werden "
            f"(wie TAGESLAGE), nicht grau (#9a978d). "
            f"Kontext vor 'VORTAGESVERGLEICH': ...{context[-200:]!r}"
        )

    def test_tageslage_also_uses_accent_orange(self):
        """Kontrolltest: TAGESLAGE-Headline hat #c45a2a (bleibt erhalten)."""
        day_comp = _make_day_comparison_better()
        html = _render(
            compact_summary="Sommerlicher Tag",
            day_comparison=day_comp,
        )
        assert "TAGESLAGE" in html, "TAGESLAGE-Headline fehlt"
        pos_tageslage = html.find("TAGESLAGE")
        context = html[max(0, pos_tageslage - 300):pos_tageslage]
        assert "#c45a2a" in context, "TAGESLAGE-Headline muss color:#c45a2a haben"

    def test_vortagesvergleich_not_using_gray(self):
        """VORTAGESVERGLEICH-Eyebrow darf NICHT #9a978d (grau) als Farbe führen."""
        day_comp = _make_day_comparison_better()
        html = _render(
            compact_summary="Sommerlicher Tag",
            day_comparison=day_comp,
        )
        pos = html.find("VORTAGESVERGLEICH")
        assert pos != -1, "VORTAGESVERGLEICH fehlt"
        context = html[max(0, pos - 300):pos]
        # Der span unmittelbar vor VORTAGESVERGLEICH darf NICHT color:#9a978d haben.
        # Wir prüfen: die letzte color:-Angabe vor der Headline ist #c45a2a, nicht #9a978d.
        color_matches = re.findall(r"color:([#\w]+)", context)
        if color_matches:
            last_color = color_matches[-1]
            assert last_color == "#c45a2a", (
                f"Letzte color:-Angabe vor VORTAGESVERGLEICH ist '{last_color}', "
                f"erwartet '#c45a2a'"
            )


# ---------------------------------------------------------------------------
# AC-2: Trend-Glyph steht HINTER der VORTAGESVERGLEICH-Headline
# ---------------------------------------------------------------------------

class TestAC2TrendGlyphPositionAfterHeadline:
    """AC-2: Given Vortagsvergleich mit Trend-Indikator (▲/▼/▬),
    When gerendert, Then steht der Glyph HINTER 'VORTAGESVERGLEICH'."""

    def test_trend_glyph_after_vortagesvergleich_text(self):
        """Given day_comparison 'besser' / When render_html /
        Then ▲ kommt nach VORTAGESVERGLEICH im HTML, nicht davor."""
        day_comp = _make_day_comparison_better()
        html = _render(
            compact_summary="Sommerlicher Tag",
            day_comparison=day_comp,
        )
        assert "VORTAGESVERGLEICH" in html
        # Glyph ▲ muss im HTML vorkommen
        assert "▲" in html, "Trend-Glyph ▲ fehlt im Output"
        pos_vortag = html.find("VORTAGESVERGLEICH")
        pos_glyph = html.find("▲")
        assert pos_glyph > pos_vortag, (
            f"Trend-Glyph ▲ (pos={pos_glyph}) muss nach 'VORTAGESVERGLEICH' "
            f"(pos={pos_vortag}) stehen, steht aber davor"
        )

    def test_trend_glyph_worse_after_vortagesvergleich(self):
        """Given day_comparison 'schlechter' / When render_html /
        Then ▼ kommt nach VORTAGESVERGLEICH."""
        from services.day_comparison import DayComparison
        day_comp_worse = DayComparison(
            wind_delta_kmh=10.0,
            gust_delta_kmh=15.0,
            precip_delta_mm=5.0,
            visibility_delta_m=-2000.0,
            thunder_delta=1,
            summary="heute schlechtere Bedingungen als gestern",
        )
        html = _render(
            compact_summary="Wechselhafter Tag",
            day_comparison=day_comp_worse,
        )
        assert "VORTAGESVERGLEICH" in html
        assert "▼" in html, "Trend-Glyph ▼ fehlt"
        pos_vortag = html.find("VORTAGESVERGLEICH")
        pos_glyph = html.find("▼")
        assert pos_glyph > pos_vortag, (
            f"Trend-Glyph ▼ (pos={pos_glyph}) muss nach VORTAGESVERGLEICH "
            f"(pos={pos_vortag}) stehen"
        )


# ---------------------------------------------------------------------------
# AC-3: Stundentabellen-Spalten in konfigurierter Metrik-Reihenfolge
# ---------------------------------------------------------------------------

class TestAC3ColumnOrderFollowsDisplayConfig:
    """AC-3: Given konfigurierte Metrik-Reihenfolge, When Stundentabelle,
    Then Spalten erscheinen links→rechts in dieser Reihenfolge."""

    def _dc_with_order(self, metric_ids: list[str]):
        """Baut ein DisplayConfig mit der angegebenen Metrik-Reihenfolge."""
        from app.metric_catalog import build_default_display_config
        from app.models import UnifiedWeatherDisplayConfig, MetricConfig
        dc = build_default_display_config()
        # Nur die gewünschten Metriken in der neuen Reihenfolge
        new_metrics = []
        existing = {mc.metric_id: mc for mc in dc.metrics}
        for mid in metric_ids:
            if mid in existing:
                mc = existing[mid]
                mc = mc.__class__(
                    **{**mc.__dict__, "enabled": True}
                )
                new_metrics.append(mc)
        # Alle anderen deaktivieren
        disabled = [
            mc for mc in dc.metrics
            if mc.metric_id not in metric_ids
        ]
        for mc in disabled:
            mc = mc.__class__(**{**mc.__dict__, "enabled": False})
            new_metrics.append(mc)
        return UnifiedWeatherDisplayConfig(metrics=new_metrics)

    def test_columns_follow_configured_order(self):
        """Given dc mit Reihenfolge [gust, wind, precipitation] /
        When Tabelle gerendert / Then Gust-Header vor Wind-Header vor Rain-Header."""
        from app.metric_catalog import build_default_display_config, get_metric
        dc = build_default_display_config()

        # Baue dc mit umgekehrter Reihenfolge: gust zuerst, dann wind, dann precip
        # Normalerweise kommt wind vor gust
        from app.models import UnifiedWeatherDisplayConfig
        from copy import deepcopy
        metrics = deepcopy(list(dc.metrics))

        # Erzwinge: gust vor wind (anders als Katalog-Default)
        # Standard: [temperature, wind, gust, precipitation, ...]
        # Wir wollen: [temperature, gust, wind, precipitation, ...]
        metric_by_id = {mc.metric_id: mc for mc in metrics}

        ordered_ids = ["temperature", "gust", "wind", "precipitation", "thunder",
                       "visibility", "freezing_level", "uv_index"]
        new_order = []
        for mid in ordered_ids:
            if mid in metric_by_id:
                new_order.append(metric_by_id[mid])
        # Add remaining
        for mc in metrics:
            if mc.metric_id not in ordered_ids:
                new_order.append(mc)
        dc_reordered = UnifiedWeatherDisplayConfig(metrics=new_order)

        # Baue seg_tables mit echten Rows für die Segmente
        from tests.unit.test_renderers_email import _make_segment_weather
        from src.output.renderers.email.helpers import extract_hourly_rows
        seg = _make_segment_weather()
        rows = extract_hourly_rows(seg, dc_reordered, tz=ZoneInfo("Europe/Berlin"))

        html = _render(dc=dc_reordered, seg_tables=[rows])

        # Finde Tabellen-Header-Zeile: erster <thead>
        thead_match = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL)
        assert thead_match, "Keine <thead> im gerenderten HTML"
        thead_html = thead_match.group(1)

        # Extrahiere <th>-Inhalte in Reihenfolge
        th_texts = re.findall(r"<th[^>]*>(.*?)</th>", thead_html, re.DOTALL)
        # Erster ist "Time", dann kommen die Metriken
        col_labels = [re.sub(r"<[^>]+>", "", t).strip() for t in th_texts]

        # Finde Gust und Wind Positionen
        from app.metric_catalog import get_metric
        try:
            gust_label = get_metric("gust").col_label
            wind_label = get_metric("wind").col_label
        except KeyError:
            # Fallback auf bekannte Labels
            gust_label = "Böen"
            wind_label = "Wind"

        gust_positions = [i for i, l in enumerate(col_labels) if gust_label in l]
        wind_positions = [i for i, l in enumerate(col_labels) if wind_label in l]

        assert gust_positions, f"Gust-Spalte ('{gust_label}') nicht in Header: {col_labels}"
        assert wind_positions, f"Wind-Spalte ('{wind_label}') nicht in Header: {col_labels}"

        assert gust_positions[0] < wind_positions[0], (
            f"Gust (pos={gust_positions[0]}) muss vor Wind (pos={wind_positions[0]}) "
            f"stehen — konfigurierte Reihenfolge wird nicht eingehalten. "
            f"Spalten: {col_labels}"
        )


# ---------------------------------------------------------------------------
# AC-4: Tabellen-Styling — Zell-Linien, Header-Farben
# ---------------------------------------------------------------------------

class TestAC4TableStyling:
    """AC-4: Given Stundentabelle, When gerendert, Then Zell-Linien #f0ece1,
    Header-Unterkante #e6e1d3, Header-Text #3a3835."""

    def test_table_cell_border_color_f0ece1(self):
        """Zell-Linien (border-right auf td/tr) müssen #f0ece1 sein."""
        from tests.unit.test_renderers_email import _make_segment_weather
        from app.metric_catalog import build_default_display_config
        from src.output.renderers.email.helpers import extract_hourly_rows
        dc = build_default_display_config()
        seg = _make_segment_weather()
        rows = extract_hourly_rows(seg, dc, tz=ZoneInfo("Europe/Berlin"))
        html = _render(seg_tables=[rows])
        assert "#f0ece1" in html, (
            "Zell-Linienfarbe #f0ece1 fehlt im HTML. "
            "Aktuell verwendet der Code G_INK_FAINT=#9c9a90 fürs Grid."
        )

    def test_header_row_background_white(self):
        """Header-Zeile (<th>) muss weißen Hintergrund haben (background:#fff oder background:white)."""
        from tests.unit.test_renderers_email import _make_segment_weather
        from app.metric_catalog import build_default_display_config
        from src.output.renderers.email.helpers import extract_hourly_rows
        dc = build_default_display_config()
        seg = _make_segment_weather()
        rows = extract_hourly_rows(seg, dc, tz=ZoneInfo("Europe/Berlin"))
        html = _render(seg_tables=[rows])

        # Suche nach th-Styling: background:#fff oder background:white
        # Vorlage: <tr style={{ background: "#fff", borderBottom: "1px solid #e6e1d3" }}>
        thead_match = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL)
        assert thead_match, "Kein <thead>"
        thead_html = thead_match.group(1)
        assert "#fff" in thead_html or "white" in thead_html, (
            "Header-Zeile muss weißen Hintergrund haben (#fff), "
            "aktuell ist G_SURFACE_1 (#edeae1) gesetzt"
        )

    def test_header_text_color_3a3835(self):
        """Header-Text-Farbe muss #3a3835 sein (11px/600)."""
        from tests.unit.test_renderers_email import _make_segment_weather
        from app.metric_catalog import build_default_display_config
        from src.output.renderers.email.helpers import extract_hourly_rows
        dc = build_default_display_config()
        seg = _make_segment_weather()
        rows = extract_hourly_rows(seg, dc, tz=ZoneInfo("Europe/Berlin"))
        html = _render(seg_tables=[rows])

        thead_match = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL)
        assert thead_match, "Kein <thead>"
        thead_html = thead_match.group(1)
        assert "#3a3835" in thead_html, (
            "Header-Text-Farbe #3a3835 fehlt in <thead>. "
            "Vorlage hCellStyle: color:#3a3835, fontWeight:600"
        )

    def test_header_bottom_border_e6e1d3(self):
        """Header-Unterkante muss border-bottom:1px solid #e6e1d3 haben."""
        from tests.unit.test_renderers_email import _make_segment_weather
        from app.metric_catalog import build_default_display_config
        from src.output.renderers.email.helpers import extract_hourly_rows
        dc = build_default_display_config()
        seg = _make_segment_weather()
        rows = extract_hourly_rows(seg, dc, tz=ZoneInfo("Europe/Berlin"))
        html = _render(seg_tables=[rows])

        thead_match = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL)
        assert thead_match, "Kein <thead>"
        thead_html = thead_match.group(1)
        assert "#e6e1d3" in thead_html, (
            "Header-Unterkante #e6e1d3 fehlt in <thead>. "
            "Vorlage: borderBottom:'1px solid #e6e1d3'"
        )


# ---------------------------------------------------------------------------
# AC-5: Letzte Tabellenspalte heißt "Risk" (nicht "·")
# ---------------------------------------------------------------------------

class TestAC5RiskColumnHeader:
    """AC-5: Given Stundentabelle, When gerendert,
    Then heißt die letzte Spalte 'Risk', nicht '·'."""

    def test_last_column_header_is_risk(self):
        """<th> der letzten Spalte enthält 'Risk', nicht den Middot-Punkt '·'."""
        from tests.unit.test_renderers_email import _make_segment_weather
        from app.metric_catalog import build_default_display_config
        from src.output.renderers.email.helpers import extract_hourly_rows
        dc = build_default_display_config()
        seg = _make_segment_weather()
        rows = extract_hourly_rows(seg, dc, tz=ZoneInfo("Europe/Berlin"))
        html = _render(seg_tables=[rows])

        thead_match = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL)
        assert thead_match, "Kein <thead>"
        thead_html = thead_match.group(1)

        th_matches = re.findall(r"<th[^>]*>(.*?)</th>", thead_html, re.DOTALL)
        assert th_matches, "Keine <th>-Elemente"

        last_th_raw = th_matches[-1]
        last_th_text = re.sub(r"<[^>]+>", "", last_th_raw).strip()

        assert "Risk" in last_th_text, (
            f"Letzte Spalten-Überschrift muss 'Risk' sein, "
            f"ist aber: '{last_th_text}' (aktuell '·' / &middot;)"
        )
        assert "·" not in last_th_text and "&middot;" not in last_th_raw, (
            f"Letzte Spalte enthält noch '·' / &middot;: '{last_th_raw!r}'"
        )


# ---------------------------------------------------------------------------
# AC-6: Etappen-Stats-Block — vertikaler Abstand über Labels
# ---------------------------------------------------------------------------

class TestAC6StatsBlockTopPadding:
    """AC-6: Given Etappen-Stats-Block (DISTANZ/AUFSTIEG…),
    When gerendert, Then ist padding-top > 0 auf den Stat-Zellen."""

    def test_stats_cells_have_top_padding(self):
        """stat_tds (die <td>-Elemente der Stats-Grid-Zellen) dürfen nicht
        padding:0 12px 0 0 haben — top-Abstand muss > 0 sein."""
        stage_stats = {
            "distance_km": 12.5,
            "ascent_m": 800.0,
            "descent_m": 200.0,
            "max_elevation_m": 2400.0,
        }
        html = _render(stage_stats=stage_stats)

        # Suche das Stats-Grid (border-top:1px solid #e6e1d3)
        stats_match = re.search(
            r'border-top:1px solid #e6e1d3.*?</table>',
            html, re.DOTALL
        )
        assert stats_match, "Stats-Grid-Block nicht gefunden"
        stats_html = stats_match.group(0)

        # Prüfe: padding auf den <td>-Elementen (nicht auf der Tabelle selbst)
        # Die Stats-Zellen haben `style="...padding:0 12px 0 0;..."` → top=0 → zu wenig
        # Soll: padding-top > 0 auf den <td>-Elementen (z.B. 14px)
        td_matches = re.findall(r'<td[^>]+style="([^"]+)"', stats_html)
        assert td_matches, "Keine <td>-Elemente mit style im Stats-Grid gefunden"

        # Aktuell: padding:0 12px 0 0 → top=0 → Test ROT
        for td_style in td_matches:
            pad_match = re.search(r'padding:([^;\"]+)', td_style)
            if pad_match:
                pad_val = pad_match.group(1).strip()
                parts = [x.strip() for x in pad_val.split()]
                if len(parts) >= 1:
                    top_val = parts[0]
                    if top_val == "0" or top_val == "0px":
                        pytest.fail(
                            f"Stats-Zelle hat padding-top=0 (padding:{pad_val}). "
                            f"Vorlage: stat-Zellen müssen top-Abstand zur Trennlinie haben "
                            f"(z.B. padding:14px 12px 0 0). "
                            f"Aktuell: padding:0 12px 0 0"
                        )


# ---------------------------------------------------------------------------
# AC-7: METRIKEN-ÜBERBLICK — Abstände laut Vorlage
# ---------------------------------------------------------------------------

class TestAC7MetricsSummarySpacing:
    """AC-7: Given METRIKEN-ÜBERBLICK (Desktop), When gerendert,
    Then padding:14px 28px 18px, Pills gap:6, margin-top:10."""

    def test_metrics_summary_outer_padding(self):
        """Außenabstand des Metriken-Überblick-Containers: padding:14px 28px 18px."""
        html = _render()
        # Suche den Metriken-Überblick-Container
        # Aktuell: padding:8px 16px (zu wenig)
        # Soll: padding:14px 28px 18px
        assert "padding:14px 28px 18px" in html, (
            "Metriken-Überblick-Container fehlt padding:14px 28px 18px. "
            "Aktuell ist padding:8px 16px (zu eng). "
            "Vorlage EmailMetricsSummary: padding:14px 28px 18px"
        )

    def test_metrics_summary_pills_flex_gap(self):
        """Pills-Container muss display:flex mit gap:6 haben."""
        html = _render()
        # Vorlage: display:flex;gap:6;flexWrap:wrap;marginTop:10
        # Aktuell: kein gap definiert
        # Suche nach dem Pills-div im Metriken-Überblick-Kontext
        summary_match = re.search(
            r'Metriken-Überblick.*?</div>',
            html, re.DOTALL
        )
        assert summary_match, "Metriken-Überblick-Abschnitt nicht gefunden"
        context = summary_match.group(0)
        assert "gap:6" in context, (
            "Pills-Container muss gap:6 haben (Flex-Gap). "
            "Aktuell kein gap gesetzt → Pills gedrängt. "
            "Vorlage: display:flex;gap:6;flexWrap:wrap"
        )

    def test_metrics_summary_pills_margin_top_10(self):
        """Pills-Container muss margin-top:10 (px) haben."""
        html = _render()
        summary_match = re.search(
            r'Metriken-Überblick.*?</div>',
            html, re.DOTALL
        )
        assert summary_match, "Metriken-Überblick-Abschnitt nicht gefunden"
        context = summary_match.group(0)
        assert "margin-top:10" in context, (
            "Pills-Container muss margin-top:10 haben. "
            "Vorlage: marginTop:10"
        )


# ---------------------------------------------------------------------------
# AC-8: Ausblick enthält ACC-Spalte mit Risk-Dot (nicht NN%-Text)
# ---------------------------------------------------------------------------

class TestAC8OutlookACCColumn:
    """AC-8: Given Ausblick, When gerendert,
    Then enthält ACC-Spalte mit Risk-Dot aus confidence_pct."""

    def test_outlook_contains_acc_column_header(self):
        """Ausblick-Tabelle hat Spalten-Kopf 'ACC'."""
        trend = [
            _trend_stage(weekday="Di", name="E1", confidence_pct=82),
            _trend_stage(weekday="Mi", name="E2", confidence_pct=55),
            _trend_stage(weekday="Do", name="E3", confidence_pct=30),
        ]
        html = _render(trend=trend)
        assert "ACC" in html, (
            "Spalten-Kopf 'ACC' fehlt im Ausblick. "
            "Vorlage OutlookTable: Spalte 'ACC' für Prognose-Genauigkeit"
        )

    def test_outlook_acc_uses_risk_dot_not_percent_text(self):
        """ACC-Zellen zeigen Risk-Dot (border-radius:50%), KEIN 'NN%'-Text."""
        trend = [
            _trend_stage(weekday="Di", name="E1", confidence_pct=82),
            _trend_stage(weekday="Mi", name="E2", confidence_pct=55),
        ]
        html = _render(trend=trend)

        # Suche Kontext nach ACC-Header bis Tabellen-Ende
        acc_pos = html.find("ACC")
        assert acc_pos != -1, "ACC-Header fehlt"

        # Nach dem ACC-Header: Risk-Dot (border-radius:50%) muss vorkommen,
        # kein roher Prozent-Text wie "82%" oder "55%" als ACC-Wert.
        # fix-911-table-jsx AC-3: Data-Cells tragen nun font-family:FONT_DATA →
        # Zell-HTML länger; Fenster bis Tabellenende statt fixer 2000-Zeichen.
        table_end = html.find("</table>", acc_pos)
        context_after_acc = html[acc_pos:table_end if table_end != -1 else acc_pos + 4000]

        assert "border-radius:50%" in context_after_acc, (
            "ACC-Spalte muss Risk-Dot (border-radius:50%) enthalten, "
            "keinen NN%-Text. "
            "Vorlage: <RiskDot r={r.conf}/>"
        )


# ---------------------------------------------------------------------------
# AC-9: Eyebrow "Ausblick · nächste 3 Tage" über dem Ausblick
# ---------------------------------------------------------------------------

class TestAC9OutlookEyebrow:
    """AC-9: Given Ausblick-Abschnitt, When gerendert,
    Then steht darüber 'Ausblick · nächste 3 Tage'."""

    def test_outlook_eyebrow_present(self):
        """Eyebrow 'Ausblick · nächste 3 Tage' (oder ähnlich) fehlt aktuell."""
        trend = [
            _trend_stage(weekday="Di", name="E1", confidence_pct=80),
            _trend_stage(weekday="Mi", name="E2", confidence_pct=65),
        ]
        html = _render(trend=trend)

        # Vorlage: <EmailEyebrow>Ausblick · nächste 3 Tage</EmailEyebrow>
        # Aktuell: laut Spec AC-6 (#899) wurde der Ausblick-Eyebrow ENTFERNT
        # → dieser Test muss rot sein bis er wieder eingebaut wird
        has_eyebrow = (
            "Ausblick" in html
            and "nächste" in html
            and ("3 Tage" in html or "3&nbsp;Tage" in html)
        )
        assert has_eyebrow, (
            "Eyebrow 'Ausblick · nächste 3 Tage' fehlt über dem Ausblick-Block. "
            "Aktuell wurde dieser Eyebrow in AC-6 (#899) entfernt — "
            "muss laut #911 wiederhergestellt werden."
        )

    def test_outlook_eyebrow_position_before_trend_content(self):
        """Eyebrow steht VOR dem Ausblick-Inhalt (Trend-Chips)."""
        trend = [
            _trend_stage(weekday="Di", name="E1", confidence_pct=80),
        ]
        html = _render(trend=trend)
        pos_eyebrow = html.find("nächste 3 Tage")
        pos_di = html.find("Di")  # Wochentag des ersten Trends
        if pos_eyebrow == -1:
            pytest.fail("Eyebrow 'nächste 3 Tage' fehlt — muss noch implementiert werden")
        assert pos_eyebrow < pos_di, (
            f"Eyebrow (pos={pos_eyebrow}) muss vor dem Trend-Inhalt (Di pos={pos_di}) stehen"
        )


# ---------------------------------------------------------------------------
# AC-10: Stundentabellen-Zellen mit erhöhtem Schweregrad tragen Zell-Hintergrund
# ---------------------------------------------------------------------------

class TestAC10CellBackgroundHighlighting:
    """AC-10: Given Zelle mit erhöhtem Schweregrad, When gerendert,
    Then trägt die ZELLE einen getönten Hintergrund (#fbeeb8/warn #fad6b8/danger #f6c5bf)."""

    def _make_high_gust_rows(self):
        """Erzeugt Rows mit hohem Gust-Wert (>45 km/h → warn)."""
        from tests.unit.test_renderers_email import _make_segment_weather, _make_dp
        from app.metric_catalog import build_default_display_config
        from src.output.renderers.email.helpers import dp_to_row
        from src.app.models import ForecastDataPoint, ThunderLevel
        from datetime import datetime, timezone

        dc = build_default_display_config()
        # Erstelle dp mit hohem Gust
        dp = ForecastDataPoint(
            ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
            t2m_c=15.0,
            wind10m_kmh=30.0,
            gust_kmh=55.0,  # >45 → warn
            precip_1h_mm=0.0,
            cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE,
            wind_chill_c=12.0,
            snowfall_limit_m=None,
            humidity_pct=55,
        )
        row = dp_to_row(dp, dc, tz=ZoneInfo("Europe/Berlin"))
        row["risk"] = "warn"
        return [row]

    def test_warn_cell_has_background_color(self):
        """Warn-Zellen (gust >45) müssen Zell-Hintergrund #fad6b8 tragen."""
        rows = self._make_high_gust_rows()
        html = _render(seg_tables=[rows])

        # Aktuell: nur farbiger Text im <span>, kein Zell-Hintergrund
        # Soll: background:#fad6b8 auf der <td>-Ebene
        assert "#fad6b8" in html, (
            "Warn-Zellen müssen Hintergrund #fad6b8 tragen (warn-Tönung). "
            "Aktuell gibt es nur farbigen Text im <span>, keinen Zell-Hintergrund. "
            "Vorlage RISK_CELL.warn.bg = #fad6b8"
        )

    def _make_danger_thunder_rows(self):
        """Erzeugt Rows mit hohem Gewitter-Wert (>30% → danger)."""
        from src.app.models import ForecastDataPoint, ThunderLevel
        from app.metric_catalog import build_default_display_config
        from src.output.renderers.email.helpers import dp_to_row
        from datetime import datetime, timezone

        dc = build_default_display_config()
        dp = ForecastDataPoint(
            ts=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
            t2m_c=20.0,
            wind10m_kmh=15.0,
            gust_kmh=25.0,
            precip_1h_mm=8.0,
            cloud_total_pct=95,
            thunder_level=ThunderLevel.HIGH,
            wind_chill_c=18.0,
            snowfall_limit_m=None,
            humidity_pct=90,
        )
        row = dp_to_row(dp, dc, tz=ZoneInfo("Europe/Berlin"))
        # Setze Gewitter-Wert explizit (>30 → danger)
        row["thunder"] = 35.0
        row["risk"] = "danger"
        return [row]

    def test_danger_cell_has_background_color(self):
        """Danger-Zellen (thunder >30%) müssen Hintergrund #f6c5bf tragen."""
        rows = self._make_danger_thunder_rows()
        html = _render(seg_tables=[rows])
        assert "#f6c5bf" in html, (
            "Danger-Zellen müssen Hintergrund #f6c5bf tragen. "
            "Aktuell kein Zell-Hintergrund, nur Text-Farbe. "
            "Vorlage RISK_CELL.danger.bg = #f6c5bf"
        )

    def test_caution_cell_has_background_color(self):
        """Caution-Zellen müssen Hintergrund #fbeeb8 tragen."""
        from src.app.models import ForecastDataPoint, ThunderLevel
        from app.metric_catalog import build_default_display_config
        from src.output.renderers.email.helpers import dp_to_row
        from datetime import datetime, timezone

        dc = build_default_display_config()
        dp = ForecastDataPoint(
            ts=datetime(2026, 7, 11, 9, 0, tzinfo=timezone.utc),
            t2m_c=12.0,
            wind10m_kmh=22.0,  # >20 → caution für wind
            gust_kmh=28.0,
            precip_1h_mm=0.0,
            cloud_total_pct=60,
            thunder_level=ThunderLevel.NONE,
            wind_chill_c=10.0,
            snowfall_limit_m=None,
            humidity_pct=65,
        )
        row = dp_to_row(dp, dc, tz=ZoneInfo("Europe/Berlin"))
        row["risk"] = "caution"
        html = _render(seg_tables=[row] if not isinstance(row, list) else row)
        assert "#fbeeb8" in html, (
            "Caution-Zellen müssen Hintergrund #fbeeb8 tragen. "
            "Vorlage RISK_CELL.caution.bg = #fbeeb8"
        )


# ---------------------------------------------------------------------------
# AC-11: RISK-Legende — "RISK"-Präfix + CSS-Dots, NICHT auf dunklem Footer
# ---------------------------------------------------------------------------

class TestAC11RiskLegend:
    """AC-11: Given RISK-Legende, When gerendert,
    Then: 'RISK'-Präfix + CSS-Dots (border-radius:50%), KEIN Emoji auf dunklem Footer."""

    def test_risk_legend_has_risk_prefix(self):
        """Legende beginnt mit 'RISK' (Großbuchstaben, letterSpacing)."""
        html = _render()
        # Aktuell steht die Legende im dunklen Footer als AMPEL_LEGEND
        # Soll: eigene Section mit hellem Hintergrund + RISK-Präfix
        # Suche nach 'RISK' im Kontext einer Legende
        assert "RISK" in html, "RISK-Präfix fehlt in der Legende"

    def test_risk_legend_uses_css_dots_not_emoji(self):
        """Legende nutzt CSS-Dots (border-radius:50%), keine Emoji-Kreise."""
        html = _render()
        # Emoji-Kreise die verboten sind:
        for emoji in ("🟢", "🟡", "🟠", "🔴"):
            # Prüfe im Kontext der Legende (nach dem RISK-Präfix)
            if emoji in html:
                risk_pos = html.find("RISK")
                emoji_pos = html.find(emoji)
                # Wenn Emoji in der Nähe der Legende → Fehler
                if abs(emoji_pos - risk_pos) < 1000:
                    pytest.fail(
                        f"RISK-Legende enthält Emoji-Kreis {emoji!r} — "
                        "muss CSS-Dot (border-radius:50%) verwenden"
                    )

    def test_risk_legend_not_inside_dark_footer(self):
        """RISK-Legende steht NICHT innerhalb des dunklen Footers (#1d1c1a)."""
        html = _render()
        # Footer hat background:#1d1c1a
        # Suche footer-Block
        footer_match = re.search(
            r'background:#1d1c1a.*?</div>',
            html, re.DOTALL
        )
        assert footer_match, "Footer (#1d1c1a) nicht gefunden"
        footer_html = footer_match.group(0)

        # Die 4 Legende-Labels dürfen NICHT alle im Footer stehen
        legend_labels = ["unkritisch", "Achtung", "Warnung", "Gefahr"]
        labels_in_footer = sum(1 for lbl in legend_labels if lbl in footer_html)
        assert labels_in_footer < 3, (
            f"RISK-Legende ({labels_in_footer}/4 Labels) steht im dunklen Footer (#1d1c1a). "
            "Soll: eigener heller Section-Block vor dem Footer. "
            "Vorlage: background:#fbfaf6, borderTop/Bottom:#e6e1d3"
        )

    def test_risk_legend_section_has_light_background(self):
        """RISK-Legende hat hellen Hintergrund (#fbfaf6 oder ähnlich)."""
        html = _render()
        # Suche RISK-Legende-Abschnitt
        risk_pos = html.find("RISK")
        assert risk_pos != -1
        # Im Kontext: light background
        context = html[max(0, risk_pos - 200):risk_pos + 2000]
        has_light_bg = "#fbfaf6" in context or "#fdfcf8" in context or "#fff" in context
        assert has_light_bg, (
            "RISK-Legende-Section muss hellen Hintergrund haben (#fbfaf6 oder ähnlich), "
            "nicht den dunklen Footer-Hintergrund"
        )


# ---------------------------------------------------------------------------
# AC-12: Ausblick als echte Tabelle mit Spalten Tag·N·D·R·PR·Wind·Böen·Gew·ACC
# ---------------------------------------------------------------------------

class TestAC12OutlookTable:
    """AC-12: Given Ausblick, When gerendert,
    Then echte Tabelle mit Spalten Tag N D R PR Wind Böen Gew ACC."""

    def test_outlook_table_has_required_columns(self):
        """Ausblick-Tabelle hat Köpfe: Tag, N, D, R, PR, Wind, Böen, Gew, ACC."""
        trend = [
            _trend_stage(weekday="Di", name="E1", confidence_pct=82),
            _trend_stage(weekday="Mi", name="E2", confidence_pct=55),
            _trend_stage(weekday="Do", name="E3", confidence_pct=30),
        ]
        html = _render(trend=trend)

        # Soll-Spaltenköpfe laut OutlookTable in JSX
        required_headers = ["Tag", "N", "D", "R", "PR", "Wind", "Böen", "Gew", "ACC"]
        missing = [h for h in required_headers if h not in html]
        assert not missing, (
            f"Ausblick-Tabelle fehlen Spalten: {missing}. "
            "Aktuell rendert der Renderer Chip-Zeilen statt einer Tabelle. "
            "Vorlage OutlookTable: Tag·N·D·R·PR·Wind·Böen·Gew·ACC"
        )

    def test_outlook_is_html_table_not_just_divs(self):
        """Ausblick-Block enthält eine <table> MIT den Ausblick-Spalten
        (nicht nur <div>-Chips oder die Segment-Stundentabelle)."""
        trend = [
            _trend_stage(weekday="Di", name="E1", confidence_pct=82),
            _trend_stage(weekday="Mi", name="E2", confidence_pct=55),
        ]
        html = _render(trend=trend)

        # Suche nach <table> das Ausblick-spezifische Spaltenköpfe enthält
        # Aktuell: Trend-Sektion hat nur <div>-Chips, keine <table>
        # Soll: OutlookTable mit Tag/N/D/R/PR/Wind/Böen/Gew/ACC in <thead>
        # Prüfe: Ein <thead> enthält mindestens "Tag" und "ACC"
        theads = re.findall(r"<thead>(.*?)</thead>", html, re.DOTALL)
        outlook_thead_found = any(
            "ACC" in t and "Tag" in t
            for t in theads
        )
        assert outlook_thead_found, (
            f"Kein <thead> mit Ausblick-Spalten (Tag + ACC) gefunden. "
            f"Aktuell rendert der Ausblick <div>-Chips statt einer <table>. "
            f"Vorhandene <thead>-Blöcke: {len(theads)}. "
            "Vorlage: OutlookTable mit <thead><th>Tag</th>...<th>ACC</th></thead>"
        )

    def test_outlook_table_has_code_legend(self):
        """Unter der Ausblick-Tabelle steht eine Code-Legende."""
        trend = [
            _trend_stage(weekday="Di", name="E1", confidence_pct=82),
        ]
        html = _render(trend=trend)
        # Vorlage: "N Nacht-Tief · D Tag-Hoch °C · R Regen mm · PR Regen-W. %@h ..."
        has_legend = (
            "Nacht-Tief" in html
            or ("N Nacht" in html)
            or ("D Tag-Hoch" in html)
        )
        assert has_legend, (
            "Code-Legende unter der Ausblick-Tabelle fehlt. "
            "Vorlage: 'N Nacht-Tief · D Tag-Hoch °C · R Regen mm...'"
        )

    def test_outlook_cells_with_high_values_have_background(self):
        """Ausblick-Zellen mit erhöhtem Wert tragen Hintergrund-Tönung."""
        # Stage mit hohem Regen und Gewitter
        trend = [
            _trend_stage(
                weekday="Di", name="E1",
                precip_mm=10.0,  # >8 → danger
                confidence_pct=30,
            ),
        ]
        # Füge thunder_pct_max dem Stage-dict direkt hinzu
        stage = trend[0].copy()
        stage["thunder_pct_max"] = 35  # >30 → danger
        stage["rain_probability_pct"] = 90  # >85 → danger
        html = _render(trend=[stage])

        # Wenn die Tabelle gerendert wird, muss mindestens eine Gefahren-Farbe da sein
        has_cell_bg = "#fad6b8" in html or "#f6c5bf" in html or "#fbeeb8" in html
        assert has_cell_bg, (
            "Ausblick-Tabellen-Zellen mit hohen Werten müssen Hintergrund-Tönung haben. "
            "Vorlage: sevCellStyle → RISK_CELL bg-Farben"
        )


# ---------------------------------------------------------------------------
# AC-13: Datenpipeline — PR und Gewitter-% im Trend-Stage-dict
# ---------------------------------------------------------------------------

class TestAC13PipelineRainProbAndThunderPct:
    """AC-13: Given Ausblick-Tabelle benötigt PR und Gewitter-% pro Folgetag,
    When Trend-Builder aggregiert, Then diese Werte sind im Stage-dict vorhanden."""

    def _make_seg_weather_with_pop_and_thunder(self, pop_max_pct: int, thunder_pct: float):
        """Echtes SegmentWeatherData mit pop_max_pct und Thunder-Daten."""
        from datetime import datetime, timezone
        from src.app.models import (
            GPXPoint, TripSegment, SegmentWeatherData, SegmentWeatherSummary,
            ThunderLevel, ForecastDataPoint, NormalizedTimeseries, ForecastMeta, Provider,
        )
        seg = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
            end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
            start_time=datetime(2026, 7, 12, 8, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc),
            duration_hours=4.0,
            distance_km=8.0,
            ascent_m=800.0,
            descent_m=0.0,
        )
        agg = SegmentWeatherSummary(
            temp_min_c=14.0, temp_max_c=24.0, temp_avg_c=19.0,
            wind_max_kmh=22.0, gust_max_kmh=35.0,
            precip_sum_mm=5.0, cloud_avg_pct=80, humidity_avg_pct=85,
            thunder_level_max=ThunderLevel.MED,
            pop_max_pct=pop_max_pct,
            aggregation_config={
                "temp_min_c": "min", "temp_max_c": "max", "temp_avg_c": "avg",
                "wind_max_kmh": "max", "gust_max_kmh": "max",
                "precip_sum_mm": "sum",
                "pop_max_pct": "max",
                "thunder_level_max": "max",
                "confidence_pct_min": "min",
            },
        )
        meta = ForecastMeta(
            provider=Provider.OPENMETEO, model="arome_france",
            run=datetime(2026, 7, 12, 0, 0, tzinfo=timezone.utc),
            grid_res_km=1.3, interp="point_grid",
        )
        # Erstelle Timeseries mit thunder-Daten
        dps = []
        for h in range(8, 13):
            from src.app.models import ForecastDataPoint
            dp = ForecastDataPoint(
                ts=datetime(2026, 7, 12, h, 0, tzinfo=timezone.utc),
                t2m_c=15.0 + h * 0.3,
                wind10m_kmh=12.0,
                gust_kmh=25.0,
                precip_1h_mm=1.0,
                cloud_total_pct=80,
                thunder_level=ThunderLevel.MED,
                wind_chill_c=12.0,
                snowfall_limit_m=None,
                humidity_pct=85,
                pop_pct=pop_max_pct,
            )
            dps.append(dp)
        ts = NormalizedTimeseries(meta=meta, data=dps)
        return SegmentWeatherData(
            segment=seg, timeseries=ts, aggregated=agg,
            fetched_at=datetime.now(timezone.utc), provider="openmeteo",
        )

    def test_aggregate_stage_preserves_pop_max_pct(self):
        """aggregate_stage muss pop_max_pct (Regenwahrscheinlichkeit) durchreichen."""
        from services.weather_metrics import aggregate_stage
        sw = self._make_seg_weather_with_pop_and_thunder(pop_max_pct=78, thunder_pct=25.0)
        agg = aggregate_stage([sw])
        assert agg.pop_max_pct is not None, (
            "aggregate_stage gibt pop_max_pct=None zurück. "
            "Feld muss in aggregation_config stehen und durchgereicht werden."
        )
        assert agg.pop_max_pct == 78, (
            f"pop_max_pct sollte 78 sein, ist {agg.pop_max_pct}"
        )

    def test_outlook_table_renders_pr_column_from_stage(self):
        """PR-Spalte in der Ausblick-Tabelle muss rain_probability_pct aus dem
        Stage-dict rendern — nicht als leeres/fehlendes Feld."""
        # Baue Stage-dict mit explizitem rain_probability_pct
        stage = _trend_stage(weekday="Di", name="E1", confidence_pct=70)
        stage["rain_probability_pct"] = 65  # explizit gesetzt

        html = _render(trend=[stage])

        # Soll: PR-Spalte mit Wert "65%" in der Ausblick-Tabelle
        # Aktuell: Ausblick rendert nur Chips, keine Tabelle → PR-Wert fehlt
        # Wenn die Tabelle existiert, muss die PR-Spalte den Wert aus dem Stage-dict zeigen
        assert "PR" in html, (
            "PR-Spalten-Kopf fehlt im Ausblick. "
            "AC-13: rain_probability_pct muss als PR-Spalte in OutlookTable gerendert werden."
        )
        # Die Spalte muss den Prozentwert enthalten (65% → "65%")
        assert "65%" in html, (
            "PR-Wert '65%' fehlt im Ausblick-HTML. "
            "Stage-dict hat rain_probability_pct=65, Renderer muss diesen Wert als PR zeigen."
        )

    def test_gew_column_shows_level_for_med_thunder(self):
        """F003: Gew-Spalte zeigt 'mittel' (nicht %) bei ThunderLevel.MED im Stage-dict."""
        from src.app.models import ThunderLevel
        from src.output.tokens.dto import HourlyValue
        stage = _trend_stage(weekday="Mi", name="E-Gewitter", confidence_pct=70)
        stage["thunder"] = "MED"
        stage["hourly_thunder"] = (HourlyValue(hour=14, value=1.0),)
        html = _render(trend=[stage])
        assert "mittel" in html, (
            "Gew-Spalte muss 'mittel' zeigen bei ThunderLevel.MED. "
            "F002: Gew zeigt Stufe, keine Fake-%."
        )
        assert "%" not in html.split("mittel")[0].split("Gew")[-1] if "Gew" in html else True, \
            "Gew-Zelle darf kein %-Zeichen für Gewitter enthalten"

    def test_gew_column_shows_dash_for_none_thunder(self):
        """F003: Gew-Spalte zeigt '–' bei ThunderLevel.NONE."""
        stage = _trend_stage(weekday="Do", name="E-klar", confidence_pct=85)
        stage["thunder"] = "NONE"
        html = _render(trend=[stage])
        assert "PR" in html, "PR-Spalte muss vorhanden sein"
        # Nach dem PR-Bereich muss eine Gew-Zelle mit '–' kommen
        assert "–" in html, "Gew-Spalte muss '–' zeigen bei NONE"

    def test_trend_stage_dict_dash_when_no_data(self):
        """Wenn pop_max_pct=None, darf die Ausblick-Tabelle '–' zeigen (kein Fehler)."""
        from services.weather_metrics import aggregate_stage
        from src.app.models import (
            GPXPoint, TripSegment, SegmentWeatherData, SegmentWeatherSummary,
            ThunderLevel,
        )
        from datetime import datetime, timezone
        seg = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
            end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
            start_time=datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc),
            duration_hours=4.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
        )
        agg_no_pop = SegmentWeatherSummary(
            temp_min_c=14.0, temp_max_c=22.0, temp_avg_c=18.0,
            wind_max_kmh=18.0, gust_max_kmh=28.0,
            precip_sum_mm=0.0, cloud_avg_pct=40, humidity_avg_pct=55,
            thunder_level_max=ThunderLevel.NONE,
            pop_max_pct=None,  # kein Wert
            aggregation_config={"temp_min_c": "min", "temp_max_c": "max"},
        )
        sw_no_pop = SegmentWeatherData(
            segment=seg, timeseries=None, aggregated=agg_no_pop,
            fetched_at=datetime.now(timezone.utc), provider="openmeteo",
        )
        # aggregate_stage darf KEINEN Fehler werfen wenn pop_max_pct fehlt
        try:
            agg = aggregate_stage([sw_no_pop])
        except Exception as e:
            pytest.fail(f"aggregate_stage wirft Fehler bei fehlendem pop_max_pct: {e}")

        # Render-Test: Stage-dict ohne rain_probability_pct → Zelle zeigt '–'
        stage = _trend_stage(weekday="Fr", name="E-ohne-PR")
        # Kein rain_probability_pct im dict
        assert "rain_probability_pct" not in stage, "Kontrollbedingung: Feld fehlt"

        trend = [stage]
        html = _render(trend=trend)
        # Kein Crash beim Rendern
        assert html, "render_html darf nicht abstürzen wenn PR-Daten fehlen"

    def test_outlook_nd_columns_render_real_values_from_scheduler_keys(self):
        """F005: N/D-Spalten zeigen echte Werte aus den Scheduler-Keys temp_lo/temp_hi.

        Regression: Der Renderer las temp_min_c/temp_max_c, der Scheduler schreibt aber
        temp_lo/temp_hi → N/D zeigten in der echten Produktionsmail immer '–'. Die Fixture
        nutzt jetzt die Produktions-Keys (temp_lo/temp_hi); der Wert MUSS gerendert werden.
        """
        stage = _trend_stage(weekday="Do", name="E1", temp_min_c=-1, temp_max_c=13,
                             confidence_pct=82)
        assert stage["temp_lo"] == -1 and stage["temp_hi"] == 13, (
            "Fixture muss Produktions-Keys temp_lo/temp_hi setzen (F005)"
        )
        html = _render(trend=[stage])
        assert ("13°" in html), (
            "Tag-Hoch (D=13°) fehlt in der Ausblick-Tabelle — N/D liest die "
            "Scheduler-Keys temp_lo/temp_hi nicht (F005-Regression)."
        )
        assert ("-1°" in html or "−1°" in html), (
            "Nacht-Tief (N=-1°) fehlt in der Ausblick-Tabelle (F005-Regression)."
        )
