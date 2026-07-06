"""
TDD RED — Workflow briefing-mail-inhalt.

Drei zusammengehörige Änderungen am Inhalt der Trip-Briefing-E-Mail.
Spec: docs/specs/modules/briefing_mail_inhalt.md

KEINE Mocks, KEINE Quelltext-read_text-Checks. Alle Tests prüfen das
tatsächlich gerenderte Verhalten (gerendertes HTML / echter Betreff /
echte summarize-Ausgabe aus einem echt berechneten DayComparison).

RED-Erwartung (gegen den unveränderten Ausgangscode):
  AC-1/AC-6: Mobil-Variante ist im gerenderten HTML inline auf display:none
             versteckt; ohne @media-Queries (Gmail-Typ-Client) ist sie
             unsichtbar und die Desktop-Tabelle sichtbar → leere Tabelle.
  AC-2:      Der echte Betreff enthält die Kürzel D../W../G.. .
  AC-3/4/5:  summarize_day_comparison() kennt den Parameter selected_metrics
             noch nicht → TypeError.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))


# ---------------------------------------------------------------------------
# Gemeinsame Render-Bausteine (echte Objekte, kein Mock)
# ---------------------------------------------------------------------------

_FULL_ROW = {
    "time": "08:00", "temp": "15", "felt": "11", "wind": "12", "gust": "30",
    "precip": "0.2", "pop": "10", "confidence": "ok", "thunder": None,
    "snow_limit": "2500", "cloud": "50", "cloud_low": "30",
    "visibility": "good", "uv": "4.2", "freeze_lvl": "2710",
}


def _build_seg_data():
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=900.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1450.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=14.5, ascent_m=820.0, descent_m=440.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
    )
    data = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=15.0 + h * 0.3, wind10m_kmh=15.0,
            precip_1h_mm=0.2, cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE,
        )
        for h in range(8, 14)
    ]
    ts = NormalizedTimeseries(meta=meta, data=data)
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=22.0, temp_avg_c=18.0,
        wind_max_kmh=22.0, gust_max_kmh=35.0,
        precip_sum_mm=0.8, cloud_avg_pct=50, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="demo",
    )


def _render_full_html() -> str:
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html

    seg_data = _build_seg_data()
    rows = [_FULL_ROW.copy() for _ in range(5)]
    return render_html(
        segments=[seg_data], seg_tables=[rows],
        trip_name="Graveltour im Münsterland", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, highlights=[], changes=None,
        stage_name="Etappe 2", stage_stats={"distance_km": 14.5, "ascent_m": 820},
        multi_day_trend=None, compact_summary="Guter Tag.", daylight=None,
        tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
    )


def _strip_media_blocks(html: str) -> str:
    """Entferne alle @media{...}-Blöcke (balancierte Klammern).

    Simuliert einen Mail-Client, der @media-Queries komplett ignoriert
    (Gmail-Web-Typ). Nur das Basis-CSS bleibt übrig.
    """
    out = []
    i = 0
    while True:
        j = html.find("@media", i)
        if j == -1:
            out.append(html[i:])
            break
        out.append(html[i:j])
        k = html.find("{", j)
        depth, m = 0, k
        while m < len(html):
            if html[m] == "{":
                depth += 1
            elif html[m] == "}":
                depth -= 1
                if depth == 0:
                    break
            m += 1
        i = m + 1
    return "".join(out)


# ---------------------------------------------------------------------------
# AC-1 / AC-6 — Mobil-Tabelle erscheint zuverlässig (Mobile-First)
# ---------------------------------------------------------------------------

class TestAC1MobileFirstVisible:
    """AC-1/AC-6: Ohne @media muss die Mobil-Variante sichtbar sein."""

    def test_mobile_div_not_inline_hidden(self):
        """
        GIVEN das gerenderte HTML der Briefing-Mail
        WHEN der mobile-compact-Container betrachtet wird
        THEN trägt er KEIN inline `display:none`

        RED gegen Ausgangscode: der Container hat
        style="display:none;padding:0 16px" → versteckt.
        """
        html = _render_full_html()
        styles = re.findall(r'class="mobile-compact"\s+style="([^"]*)"', html)
        assert styles, "Kein mobile-compact-Container mit inline style gefunden"
        for st in styles:
            assert "display:none" not in st.replace(" ", ""), (
                f"mobile-compact ist inline versteckt (display:none): {st!r}\n"
                "Ein Client der @media ignoriert blendet die Tabelle nie ein."
            )

    def test_base_css_is_mobile_first(self):
        """
        GIVEN das gerenderte HTML (CSS-Block VOR jedem @media)
        WHEN die Basis-Regeln für .mobile-compact und .desktop-only geprüft werden
        THEN ist .mobile-compact standardmäßig sichtbar (display:block) und
             .desktop-only standardmäßig versteckt (display:none)

        RED gegen Ausgangscode: Basis ist Desktop-First (mobile=none, desktop=block).
        """
        html = _render_full_html()
        style_start = html.find("<style")
        media_start = html.find("@media", style_start)
        base_css = html[style_start:media_start if media_start != -1 else len(html)]
        base_css = base_css.replace(" ", "")

        mc = re.search(r"\.mobile-compact\{[^}]*\}", base_css)
        do = re.search(r"\.desktop-only\{[^}]*\}", base_css)
        assert mc and do, "Basis-Regeln für .mobile-compact/.desktop-only fehlen"
        assert "display:block" in mc.group(0), (
            f".mobile-compact ist nicht standardmäßig sichtbar: {mc.group(0)!r}"
        )
        assert "display:none" in do.group(0), (
            f".desktop-only ist nicht standardmäßig versteckt: {do.group(0)!r}"
        )

    def test_visible_without_media_queries(self, tmp_path):
        """
        GIVEN das gerenderte HTML, bei dem alle @media-Blöcke entfernt wurden
              (Simulation eines Clients der @media ignoriert, z.B. Gmail-Web)
        WHEN die Seite geladen wird
        THEN ist mindestens ein .mobile-compact sichtbar (offsetHeight > 0)
             und kein .desktop-only sichtbar

        RED gegen Ausgangscode: ohne @media bleibt Desktop sichtbar,
        Mobil versteckt → leere Tabelle (der reproduzierte Nutzer-Bug).
        """
        pytest.importorskip("playwright")
        from playwright.sync_api import sync_playwright

        html_no_media = _strip_media_blocks(_render_full_html())
        p_html = tmp_path / "no_media.html"
        p_html.write_text(html_no_media, encoding="utf-8")

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_context(
                viewport={"width": 375, "height": 812}
            ).new_page()
            page.goto(f"file://{p_html}")
            page.wait_for_load_state("networkidle")
            res = page.evaluate("""() => ({
                mobile: Array.from(document.querySelectorAll('.mobile-compact'))
                    .map(e => e.offsetHeight),
                desktop: Array.from(document.querySelectorAll('.desktop-only'))
                    .map(e => e.offsetHeight),
            })""")
            browser.close()

        assert any(h > 0 for h in res["mobile"]), (
            f"Mobil-Variante unsichtbar ohne @media: heights={res['mobile']}\n"
            "Genau der Nutzer-Bug: leere Tabelle im Mail-Client."
        )
        assert all(h == 0 for h in res["desktop"]), (
            f"Desktop-Tabelle sichtbar ohne @media: heights={res['desktop']}"
        )


# ---------------------------------------------------------------------------
# AC-2 — Wetter-Kürzel raus aus dem Betreff
# ---------------------------------------------------------------------------

class TestAC2NoWeatherCodesInSubject:
    """AC-2: Echter Betreff enthält keine D/W/G/TH:/HR:-Kürzel mehr."""

    def _subject(self) -> str:
        from output.renderers.trip_report import TripReportFormatter
        report = TripReportFormatter().format_email(
            [_build_seg_data()],
            trip_name="Graveltour im Münsterland",
            report_type="morning",
            stage_name="Etappe 2",
            tz=ZoneInfo("Europe/Berlin"),
        )
        return report.email_subject

    def test_no_weather_codes(self):
        """
        GIVEN ein echtes Trip-Briefing (Aggregate temp 22 / wind 22 / Böen 35)
        WHEN der Betreff erzeugt wird
        THEN enthält er weder D.., W.., G.. noch TH:/HR:

        RED gegen Ausgangscode: Betreff endet auf "… D22 W22 G35".
        """
        subj = self._subject()
        for pat in (r"\bD\d", r"\bW\d", r"\bG\d", r"TH:", r"HR:"):
            assert re.search(pat, subj) is None, (
                f"Kürzel-Muster {pat!r} im Betreff gefunden: {subj!r}"
            )

    def test_readable_parts_remain(self):
        """
        GIVEN derselbe Betreff
        WHEN er auf die lesbaren Bestandteile geprüft wird
        THEN bleiben Etappenname und ReportType-DE erhalten
        """
        subj = self._subject()
        assert "Etappe 2" in subj, f"Etappenname fehlt: {subj!r}"
        assert "Morgen" in subj, f"ReportType-DE fehlt: {subj!r}"


# ---------------------------------------------------------------------------
# AC-3 / AC-4 / AC-5 — Vortags-Vergleich metrik-getrieben
# ---------------------------------------------------------------------------

def _make_segment(segment_id: int, **summary_kwargs):
    from app.models import (
        GPXPoint, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=200.0),
        end_point=GPXPoint(lat=42.2, lon=9.2, elevation_m=300.0),
        start_time=datetime(2026, 6, 11, 7, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 11, 11, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=15.0, ascent_m=600.0, descent_m=200.0,
    )
    return SegmentWeatherData(
        segment=segment, timeseries=None,
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


class TestAC3MetricDrivenSummary:
    """AC-3: Nur ausgewählte + spürbar veränderte Metriken im Satz."""

    def test_only_salient_selected_metrics_mentioned(self):
        """
        GIVEN Wind +25 km/h (≥ Schwelle 20), Temperatur +1°C (< Schwelle 5),
              Regen unverändert, Gewitter unverändert (NONE→NONE)
              und selected_metrics = ['wind','precipitation','thunder','temperature']
        WHEN summarize_day_comparison(comparison, selected_metrics=...) aufgerufen wird
        THEN nennt der Text den Wind, aber NICHT Temperatur/Regen/Gewitter

        RED: summarize_day_comparison kennt selected_metrics noch nicht → TypeError.
        """
        from app.models import ThunderLevel
        from services.day_comparison import (
            DayComparisonService, summarize_day_comparison,
        )

        today = [_make_segment(1, temp_max_c=21.0, wind_max_kmh=50.0,
                               precip_sum_mm=0.0,
                               thunder_level_max=ThunderLevel.NONE)]
        yesterday = [_make_segment(1, temp_max_c=20.0, wind_max_kmh=25.0,
                                   precip_sum_mm=0.0,
                                   thunder_level_max=ThunderLevel.NONE)]
        comp = DayComparisonService().compare(today, yesterday)

        text = summarize_day_comparison(
            comp, selected_metrics=["wind", "precipitation", "thunder", "temperature"]
        )
        low = text.lower()
        assert "wind" in low, f"Wind fehlt im Vergleich: {text!r}"
        assert "ähnlich" not in low, f"Fälschlich 'ähnlich' trotz Änderung: {text!r}"
        for forbidden in ("wärmer", "kälter", "regen", "nasser", "trockener", "gewitter"):
            assert forbidden not in low, (
                f"Nicht-spürbare/unausgewählte Metrik '{forbidden}' genannt: {text!r}"
            )

    def test_no_salient_change_says_similar(self):
        """
        GIVEN nur Mini-Änderungen unter allen Schwellen
        WHEN summarize_day_comparison(..., selected_metrics=['wind','temperature']) läuft
        THEN lautet der Text sinngemäß 'ähnliches Wetter wie gestern'

        RED: TypeError (selected_metrics unbekannt).
        """
        from services.day_comparison import (
            DayComparisonService, summarize_day_comparison,
        )

        today = [_make_segment(1, temp_max_c=20.5, wind_max_kmh=26.0)]
        yesterday = [_make_segment(1, temp_max_c=20.0, wind_max_kmh=25.0)]
        comp = DayComparisonService().compare(today, yesterday)

        text = summarize_day_comparison(
            comp, selected_metrics=["wind", "temperature"]
        )
        assert "ähnlich" in text.lower(), (
            f"Erwartet 'ähnliches Wetter', bekam: {text!r}"
        )


class TestAC4BackwardCompat:
    """AC-4: selected_metrics=None verhält sich wie das bisherige Verhalten."""

    def test_none_fallback_equals_positional(self):
        """
        GIVEN ein DayComparison mit Temp +7°C und Regen +5 mm
        WHEN summarize mit selected_metrics=None vs. ohne Parameter aufgerufen wird
        THEN sind beide Ergebnisse identisch (alter temp+precip-Pfad)

        RED: summarize_day_comparison(comp, selected_metrics=None) → TypeError.
        """
        from services.day_comparison import (
            DayComparisonService, summarize_day_comparison,
        )

        today = [_make_segment(1, temp_max_c=22.0, precip_sum_mm=6.0)]
        yesterday = [_make_segment(1, temp_max_c=15.0, precip_sum_mm=1.0)]
        comp = DayComparisonService().compare(today, yesterday)

        with_none = summarize_day_comparison(comp, selected_metrics=None)
        legacy = summarize_day_comparison(comp)
        assert with_none == legacy, (
            f"Fallback weicht vom Altverhalten ab: {with_none!r} != {legacy!r}"
        )


class TestAC5WindChillPreferred:
    """AC-5: Gefühlte Temperatur (wind_chill) verdrängt Lufttemperatur."""

    def test_wind_chill_preferred_over_temperature(self):
        """
        GIVEN wind_chill -8°C UND temperature +8°C (beide über Schwelle 5),
              beide in selected_metrics
        WHEN summarize_day_comparison aufgerufen wird
        THEN entspricht das Ergebnis dem mit nur ['wind_chill']
             (Lufttemperatur wird ausgelassen, kein Duplikat)
             und ['temperature'] allein liefert einen nicht-leeren Vergleich

        RED: TypeError (selected_metrics unbekannt) — und compare() befüllt
        wind_chill noch nicht.
        """
        from services.day_comparison import (
            DayComparisonService, summarize_day_comparison,
        )

        today = [_make_segment(1, temp_max_c=22.0, wind_chill_min_c=8.0)]
        yesterday = [_make_segment(1, temp_max_c=14.0, wind_chill_min_c=16.0)]
        comp = DayComparisonService().compare(today, yesterday)

        both = summarize_day_comparison(
            comp, selected_metrics=["wind_chill", "temperature"]
        )
        only_chill = summarize_day_comparison(
            comp, selected_metrics=["wind_chill"]
        )
        only_temp = summarize_day_comparison(
            comp, selected_metrics=["temperature"]
        )
        assert both == only_chill, (
            f"wind_chill+temperature != nur wind_chill (Duplikat?): "
            f"{both!r} vs {only_chill!r}"
        )
        assert "ähnlich" not in only_temp.lower() and only_temp.strip(), (
            f"temperature allein sollte einen Vergleich liefern: {only_temp!r}"
        )


# ---------------------------------------------------------------------------
# Verdrahtungs-Test: render_html / render_plain nutzen selected_metrics
# ---------------------------------------------------------------------------

class TestAC3WiringInRenderer:
    """Beweist, dass render_html und render_plain den metrik-getriebenen
    Pfad aufrufen — schlägt fehl wenn jemand auf Legacy zurückfällt."""

    def _make_comparison_wind_only(self):
        """Wind +25 km/h (> Schwelle 20), Temperatur unverändert → metrik-getrieben
        zeigt 'windiger'; Legacy (temp+precip) würde 'ähnliches Wetter' zeigen."""
        from services.day_comparison import DayComparisonService
        today = [_make_segment(1, temp_max_c=20.0, wind_max_kmh=50.0,
                               precip_sum_mm=0.0)]
        yesterday = [_make_segment(1, temp_max_c=20.0, wind_max_kmh=25.0,
                                   precip_sum_mm=0.0)]
        return DayComparisonService().compare(today, yesterday)

    def _dc_wind_only(self):
        """UnifiedWeatherDisplayConfig mit nur 'wind' enabled."""
        from app.models import MetricConfig, UnifiedWeatherDisplayConfig
        from datetime import datetime, timezone
        return UnifiedWeatherDisplayConfig(
            trip_id="test-wiring",
            metrics=[MetricConfig(metric_id="wind", enabled=True, aggregations=["max"])],
            show_night_block=False,
            night_interval_hours=2,
            thunder_forecast_days=0,
            updated_at=datetime.now(timezone.utc),
        )

    def test_render_html_uses_metric_driven_path(self):
        """
        GIVEN day_comparison mit Wind +25 km/h und dc mit nur 'wind' enabled
        WHEN render_html aufgerufen wird
        THEN enthält die gerenderte Vortags-Box 'wind' (metrik-getrieben),
             NICHT 'ähnlich' (Legacy-Pfad würde 'ähnliches Wetter' ausgeben)

        Schlägt FEHL wenn render_html summarize_day_comparison ohne
        selected_metrics aufruft (dann gilt nur temp+precip → ähnliches Wetter).
        """
        from output.renderers.email.html import render_html
        from zoneinfo import ZoneInfo

        comp = self._make_comparison_wind_only()
        dc = self._dc_wind_only()
        html = render_html(
            segments=[_build_seg_data()],
            seg_tables=[[_FULL_ROW.copy() for _ in range(3)]],
            trip_name="Wiring-Test", report_type="morning",
            dc=dc, night_rows=[], thunder_forecast=None,
            highlights=[], changes=None, stage_name="Etappe 1",
            stage_stats={"distance_km": 10.0, "ascent_m": 500},
            multi_day_trend=None, compact_summary=None, daylight=None,
            tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
            day_comparison=comp,
        )
        low = html.lower()
        assert "wind" in low and "vortag" in low, (
            "Vortags-Box fehlt oder enthält kein 'wind' — Renderer nicht verdrahtet?\n"
            f"HTML-Snippet (Vortag): {html[html.find('vortag')-20:html.find('vortag')+120] if 'vortag' in low else '(kein Vortag-Block)'!r}"
        )
        assert "ähnlich" not in low, (
            "Renderer nutzt Legacy-Pfad (ähnliches Wetter) statt metrik-getrieben.\n"
            "Ursache: summarize_day_comparison ohne selected_metrics aufgerufen."
        )

    def test_render_plain_uses_metric_driven_path(self):
        """
        GIVEN day_comparison mit Wind +25 km/h und dc mit nur 'wind' enabled
        WHEN render_plain aufgerufen wird
        THEN enthält der Plain-Text 'wind' (metrik-getrieben), NICHT 'ähnlich'
        """
        from output.renderers.email.plain import render_plain
        from zoneinfo import ZoneInfo

        comp = self._make_comparison_wind_only()
        dc = self._dc_wind_only()
        text = render_plain(
            segments=[_build_seg_data()],
            seg_tables=[[]],  # leere Tabelle — Wiring-Test fokussiert auf Vortag-Zeile
            trip_name="Wiring-Test", report_type="morning",
            dc=dc, night_rows=[], thunder_forecast=None,
            highlights=[], changes=None, stage_name="Etappe 1",
            stage_stats={"distance_km": 10.0, "ascent_m": 500},
            multi_day_trend=None, compact_summary=None, daylight=None,
            tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
            day_comparison=comp,
        )
        low = text.lower()
        assert "wind" in low and "vortag" in low, (
            f"Vortags-Zeile fehlt oder enthält kein 'wind': {text[:300]!r}"
        )
        assert "ähnlich" not in low, (
            "Plain-Renderer nutzt Legacy-Pfad statt metrik-getrieben."
        )


# ---------------------------------------------------------------------------
# AC-3 vertieft: Deckelung (max 4-6), Sortierung nach Stärke, Wortwahl
# ---------------------------------------------------------------------------

def _comparison(today_kwargs: dict, yday_kwargs: dict):
    from services.day_comparison import DayComparisonService
    return DayComparisonService().compare(
        [_make_segment(1, **today_kwargs)], [_make_segment(1, **yday_kwargs)]
    )


def _sentence_items(text: str) -> list[str]:
    """Zerlegt 'Vortag: heute a, b und c als gestern' → ['a','b','c']."""
    mid = text.split("heute ", 1)[1].rsplit(" als gestern", 1)[0]
    return [p.strip() for p in mid.replace(" und ", ", ").split(", ") if p.strip()]


class TestAC3CapSortWording:
    """AC-3 vertieft: was der Nutzer tatsächlich liest."""

    def test_max_six_changes_cap(self):
        """
        GIVEN acht spürbar veränderte, ausgewählte Metriken
        WHEN summarize_day_comparison aufgerufen wird
        THEN nennt der Satz HÖCHSTENS sechs Änderungen (Deckelung)
        """
        from services.day_comparison import summarize_day_comparison

        # 8 Metriken alle über ihrer Spürbarkeitsschwelle
        comp = _comparison(
            dict(wind_max_kmh=50.0, gust_max_kmh=60.0, precip_sum_mm=20.0,
                 cloud_avg_pct=80, pop_max_pct=70, uv_index_max=8.0,
                 humidity_avg_pct=80, dewpoint_avg_c=18.0),
            dict(wind_max_kmh=25.0, gust_max_kmh=35.0, precip_sum_mm=5.0,
                 cloud_avg_pct=40, pop_max_pct=40, uv_index_max=3.0,
                 humidity_avg_pct=50, dewpoint_avg_c=10.0),
        )
        sel = ["wind", "gust", "precipitation", "cloud_total",
               "rain_probability", "uv_index", "humidity", "dewpoint"]
        text = summarize_day_comparison(comp, selected_metrics=sel)
        items = _sentence_items(text)
        assert len(items) <= 6, (
            f"Mehr als 6 Änderungen genannt ({len(items)}): {text!r}"
        )
        assert len(items) == 6, (
            f"Deckelung greift nicht — erwartet genau 6 (von 8 spürbaren), "
            f"bekam {len(items)}: {text!r}"
        )

    def test_sorted_by_magnitude_descending(self):
        """
        GIVEN drei spürbare Metriken mit klar verschiedener Delta-Stärke
              (cloud +50, wind +30, precip +12)
        WHEN summarize_day_comparison aufgerufen wird
        THEN steht die stärkste Änderung zuerst (bewölkter → windiger → nasser)
        """
        from services.day_comparison import summarize_day_comparison

        comp = _comparison(
            dict(cloud_avg_pct=90, wind_max_kmh=55.0, precip_sum_mm=17.0),
            dict(cloud_avg_pct=40, wind_max_kmh=25.0, precip_sum_mm=5.0),
        )
        text = summarize_day_comparison(
            comp, selected_metrics=["wind", "precipitation", "cloud_total"]
        )
        items = _sentence_items(text)
        assert items == ["bewölkter", "windiger", "nasser"], (
            f"Sortierung nach |delta| (cloud 50 > wind 30 > precip 12) "
            f"nicht eingehalten: {text!r} → {items}"
        )

    def test_wording_per_metric_direction(self):
        """
        GIVEN je eine Metrik mit bekannter Änderungsrichtung
        WHEN summarize_day_comparison aufgerufen wird
        THEN erscheint das erwartete deutsche Wort (das, was der Nutzer liest)
        """
        from app.models import ThunderLevel
        from services.day_comparison import summarize_day_comparison

        cases = [
            # (today, yesterday, selected, erwartetes Wort)
            (dict(wind_max_kmh=55.0), dict(wind_max_kmh=25.0), ["wind"], "windiger"),
            (dict(wind_max_kmh=20.0), dict(wind_max_kmh=55.0), ["wind"], "ruhiger"),
            (dict(temp_max_c=25.0), dict(temp_max_c=15.0), ["temperature"], "wärmer"),
            (dict(temp_max_c=10.0), dict(temp_max_c=22.0), ["temperature"], "kälter"),
            (dict(precip_sum_mm=20.0), dict(precip_sum_mm=2.0), ["precipitation"], "nasser"),
            (dict(precip_sum_mm=1.0), dict(precip_sum_mm=18.0), ["precipitation"], "trockener"),
            (dict(cloud_avg_pct=90), dict(cloud_avg_pct=30), ["cloud_total"], "bewölkter"),
            (dict(cloud_avg_pct=20), dict(cloud_avg_pct=80), ["cloud_total"], "sonniger"),
            (dict(thunder_level_max=ThunderLevel.MED),
             dict(thunder_level_max=ThunderLevel.NONE), ["thunder"], "Gewittergefahr"),
            (dict(thunder_level_max=ThunderLevel.NONE),
             dict(thunder_level_max=ThunderLevel.HIGH), ["thunder"], "kein Gewitter mehr"),
        ]
        for today_kw, yday_kw, sel, expected in cases:
            comp = _comparison(today_kw, yday_kw)
            text = summarize_day_comparison(comp, selected_metrics=sel)
            assert expected in text, (
                f"Erwartetes Wort {expected!r} fehlt für {sel} "
                f"(today={today_kw}, yday={yday_kw}): {text!r}"
            )
