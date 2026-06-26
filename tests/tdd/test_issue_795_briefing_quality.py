"""
TDD RED — Issue #795: Briefing-Mail-Qualität + Pill-Inhalt analog SMS.

Die Metrik-Pills im „Metriken-Überblick" sollen die Inhaltslogik der SMS
übernehmen (gleiche Erwähnungsschwellen, Schwellen-/Spitzen-Zeitpunkt), aber
AUSGESCHRIEBEN/lesbar — keine kryptischen SMS-Tokens, kein @-Token. Optik
bleibt die Vollfarb-Kapsel (#664), der WCAG-AA-Konflikt wird mit dunkleren
Vollfarben + weißem Text INNERHALB der Kapselform gelöst. Dazu Qualitäts-Fixes:
Plain-tone-Marker raus, Hierarchie HTML==Plain (Überblick VOR Segment-Tabellen),
Vortag-Zeile prominenter.

Spec v3 (EIN Ampel-System): Die Pill-FARBE/Stufe wird über DIESELBE 4-stufige
Ampel wie die #759-Stundentabelle bestimmt — `ampel_dot`-Logik +
`MetricDefinition.display_thresholds` (SSoT: Wind 30/50/70, Böen 50/65/80,
Regen 1/5/10, Regenwahrsch. 30/60/80), angewandt auf den Spitzenwert. NICHT nach
der Erwähnungsschwelle. Garantie: derselbe Wert ergibt dieselbe Stufe 🟢🟡🟠🔴 in
Tabelle UND Pill. Plain trägt je nach Stufe eines der vier Ampel-Emojis
🟢🟡🟠🔴 (Bereichs-Pills ohne Symbol); HTML hat vier WCAG-AA-gedunkelte
Stufenfarben (weißer Text ≥ 4.5:1).

Mock-frei: echte render_html()/render_plain()-Aufrufe mit echten
ForecastDataPoint/SegmentWeatherData-Objekten + echtes pill_html(). Geprüft wird
der gerenderte Output (Produkt), kein Quelltext.

Diese Tests sind RED gegen Prod-Stand 42794bea (alte ad-hoc Pill-Logik):
- Plain-Überblick steht NACH den Segment-Tabellen (Hierarchie verletzt).
- Plain trägt [INFO]/[WARN]/[GOOD]/[BAD]-Marker statt der 4 Ampel-Emojis.
- Wind-Schwelle ist 20 (Pill-Default), nicht 10 (SMS); unter Schwelle
  „Wind max …" statt „Wind ruhig"; Ereignis-Form ohne „Spitze … um HH:00".
- Temperatur trägt „· Max HH:00"; kein min==max-Einzelwert.
- rain_probability rendert „ab HH" ohne „:00".
- Vortag-Zeile trägt die schwache Signatur (13px + #5c5a52).
- Pill-Farbe folgt der Erwähnungsschwelle (warn ab Wind > 20), NICHT der
  4-stufigen Ampel (display_thresholds 30/50/70) → Stufe weicht von der
  Stundentabelle ab (AC-9 RED).
- Es gibt keinen WCAG-AA-tauglichen 4-Stufen-Vollfarbsatz (warn #c8882a nur
  3.0:1 gegen Weiß).

SPEC: docs/specs/modules/issue_795_briefing_quality.md AC-1..AC-9
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

# Wiederverwendung der mock-freien Render-Helper aus #790.
from tests.tdd.test_issue_790_briefing_simplify import (  # noqa: E402
    _build_segments, _comparison, _empty_metrics_dc, _render_html,
    _render_plain, _seg_for_compare,
)

TZ = ZoneInfo("Europe/Berlin")


# ---------------------------------------------------------------------------
# Eigener Segment-Builder mit präzise gesteuerten Stundenwerten (für AC-3/AC-5)
# ---------------------------------------------------------------------------

def _seg_with_hours(rows_spec):
    """Baue EIN Segment mit explizit gesteuerten Stundenwerten.

    rows_spec: Liste von Dicts mit Schlüsseln hour, temp, wind, gust, precip,
    pop (alle UTC-Stunden). Europe/Berlin = UTC+2 im Juli → HH_local = HH_utc+2.
    """
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )
    dps = []
    for r in rows_spec:
        dps.append(ForecastDataPoint(
            ts=datetime(2026, 7, 11, r["hour"], 0, tzinfo=timezone.utc),
            t2m_c=float(r.get("temp", 15.0)),
            wind10m_kmh=float(r.get("wind", 0.0)),
            gust_kmh=float(r.get("gust", 0.0)),
            precip_1h_mm=float(r.get("precip", 0.0)),
            pop_pct=int(r.get("pop", 0)),
            cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE,
            visibility_m=20000,
            freezing_level_m=2500,
        ))
    start_h = rows_spec[0]["hour"]
    end_h = rows_spec[-1]["hour"]
    # end_time is exclusive (compact_summary uses s_h <= h < e_h since #807).
    # Set end_time one hour past the last data point so all rows are included.
    end_time_h = end_h + 1
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=400.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1200.0,
                           distance_from_start_km=4.2),
        start_time=datetime(2026, 7, 11, start_h, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, end_time_h, 0, tzinfo=timezone.utc),
        duration_hours=float(end_time_h - start_h),
        distance_km=4.2, ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="demo",
                        grid_res_km=1.3,
                        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc))
    ts = NormalizedTimeseries(meta=meta, data=dps)
    agg = SegmentWeatherSummary(
        temp_min_c=min(d.t2m_c for d in dps),
        temp_max_c=max(d.t2m_c for d in dps),
        temp_avg_c=12.0, wind_max_kmh=max(d.wind10m_kmh for d in dps),
        gust_max_kmh=max(d.gust_kmh for d in dps),
        precip_sum_mm=sum(d.precip_1h_mm for d in dps),
        cloud_avg_pct=50, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE,
    )
    return SegmentWeatherData(segment=seg, timeseries=ts, aggregated=agg,
                              fetched_at=datetime.now(timezone.utc),
                              provider="demo")


# Die vier Ampel-Emojis der #759-Stundentabelle (SSoT) → Stufenindex 0..3.
_AMPEL_EMOJIS = ["🟢", "🟡", "🟠", "🔴"]
_AMPEL_LEVEL = {e: i for i, e in enumerate(_AMPEL_EMOJIS)}


def _ampel_level(value, thresholds: dict) -> int:
    """Stufenindex 0..3 aus ampel_dot — die EINE SSoT-Logik der Tabelle.

    Nutzt die echte Produktivfunktion (kein nachgebauter Schwellenvergleich),
    damit der Test bricht, falls die Pill eine ABWEICHENDE Logik benutzt.
    """
    from output.renderers.email.helpers import ampel_dot
    return _AMPEL_LEVEL[ampel_dot(value, thresholds)]


def _metrics_block_plain(plain: str) -> str:
    idx = plain.find("Metriken-Überblick")
    assert idx != -1, "Metriken-Überblick nicht gefunden"
    return plain[idx:idx + 800]


def _metrics_block_html(html: str) -> str:
    idx = html.find("Metriken-Überblick")
    assert idx != -1, "Metriken-Überblick nicht gefunden"
    return html[idx:idx + 2000]


# WCAG relative Luminanz / Kontrast — selbst berechnet (keine Tautologie).
def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
           for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast_ratio(c1: str, c2: str) -> float:
    l1, l2 = _luminance(c1), _luminance(c2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


# ===========================================================================
# AC-1: Hierarchie — Metriken-Überblick VOR der ersten Segment-Tabelle (HTML+Plain)
# ===========================================================================

class TestAC1Hierarchy:

    def test_overview_before_segment_html(self):
        # #884: segment heading changed from "Segment N" to "SEG N"
        html = _render_html(_build_segments())
        pos_overview = html.find("Metriken-Überblick")
        pos_segment = html.find("SEG 1")
        assert pos_overview != -1 and pos_segment != -1
        assert pos_overview < pos_segment, (
            "HTML: Metriken-Überblick muss VOR der ersten Segment-Tabelle stehen"
        )

    def test_overview_before_segment_plain(self):
        plain = _render_plain(_build_segments())
        pos_overview = plain.find("Metriken-Überblick")
        pos_segment = plain.find("Segment 1")
        assert pos_overview != -1 and pos_segment != -1
        assert pos_overview < pos_segment, (
            "Plain: Metriken-Überblick muss VOR der ersten Segment-Tabelle stehen"
        )


# ===========================================================================
# AC-2 (v3): Keine rohen [TONE]-Marker — Ereignis-Pills tragen die GLEICHEN
# vier Ampel-Emojis 🟢🟡🟠🔴 wie die #759-Stundentabelle (Bereichs-Pills ohne).
# ===========================================================================

class TestAC2AmpelEmojis:

    def test_no_raw_tone_markers_plain(self):
        plain = _render_plain(_build_segments())
        for marker in ("[INFO]", "[WARN]", "[GOOD]", "[BAD]"):
            assert marker not in plain, f"roher Marker {marker} im Plain"

    def test_calm_event_pill_is_green_plain(self):
        # Ruhige Lage (unter Erwähnungsschwelle): Ereignis-Pill = grün 🟢.
        segs = [_seg_with_hours([
            {"hour": 6, "temp": 12, "wind": 3, "gust": 5, "precip": 0, "pop": 0},
            {"hour": 7, "temp": 14, "wind": 4, "gust": 6, "precip": 0, "pop": 0},
            {"hour": 8, "temp": 16, "wind": 4, "gust": 6, "precip": 0, "pop": 0},
        ])]
        plain = _render_plain(segs)
        block = _metrics_block_plain(plain)
        assert "🟢" in block, f"kein 🟢 (ruhige Ereignis-Stufe) im Plain:\n{block}"

    def test_thunder_pill_is_red_plain(self):
        # Gewitter → höchste Ampelstufe 🔴.
        plain = _render_plain(_build_segments(thunder=True))
        block = _metrics_block_plain(plain)
        assert "🔴" in block, f"kein 🔴 (Gewitter-Stufe) im Plain:\n{block}"

    def test_event_pill_only_uses_ampel_emoji_set(self):
        """Ereignis-Pills tragen NUR Emojis aus dem 4er-Ampelsatz 🟢🟡🟠🔴.

        RED gegen Prod: Prod schreibt '[GOOD]/[WARN]/[BAD]/[INFO]'-Marker —
        keines der vier Ampel-Emojis erscheint im Überblick.
        """
        # Wind-Spitze 60 km/h → über orange (50) → 🟠-Stufe in der Tabelle.
        segs = [_seg_with_hours([
            {"hour": 6, "temp": 12, "wind": 10, "gust": 15},
            {"hour": 7, "temp": 14, "wind": 35, "gust": 45},
            {"hour": 8, "temp": 16, "wind": 60, "gust": 70},
        ])]
        plain = _render_plain(segs)
        block = _metrics_block_plain(plain)
        assert any(e in block for e in _AMPEL_EMOJIS), (
            f"kein Ampel-Emoji im Ereignis-Pill-Block:\n{block}"
        )


# ===========================================================================
# AC-3: Ereignis-Pills ausgeschrieben, SMS-Schwellen, kein @-Token
# ===========================================================================

class TestAC3EventPills:

    def test_wind_threshold_matches_sms_default(self):
        """Wind-Erwähnungsschwelle MUSS dem SMS-DEFAULT (10 km/h) entsprechen."""
        from src.output.tokens.builder import DEFAULTS
        assert DEFAULTS["W"] == 10.0, "SMS-Wind-Default sollte 10 km/h sein"
        # Wind steigt von 6 → 12 → 18 km/h; Schwelle 10 wird in der 2. Stunde
        # (UTC 7 = local 09) überschritten, Spitze 18 in der 3. (UTC 8 = local 10).
        segs = [_seg_with_hours([
            {"hour": 6, "temp": 12, "wind": 6, "gust": 8},
            {"hour": 7, "temp": 14, "wind": 12, "gust": 18},
            {"hour": 8, "temp": 16, "wind": 18, "gust": 25},
        ])]
        html = _render_html(segs)
        block = _metrics_block_html(html)
        # Schwelle 10 (SMS) → Wind muss als Ereignis erscheinen ("ab HH:00").
        assert re.search(r"Wind ab \d{2}:00", block), (
            "Wind ≥ 10 km/h (SMS-Schwelle) muss als 'Wind ab HH:00' erscheinen; "
            f"Block:\n{block}"
        )

    def test_wind_event_written_out_with_peak(self):
        """Über Schwelle: ausgeschrieben 'ab HH:00 · Spitze X km/h um HH:00',
        KEIN @-Token."""
        segs = [_seg_with_hours([
            {"hour": 6, "temp": 12, "wind": 6, "gust": 8},
            {"hour": 7, "temp": 14, "wind": 12, "gust": 18},
            {"hour": 8, "temp": 16, "wind": 18, "gust": 25},
        ])]
        html = _render_html(segs)
        block = _metrics_block_html(html)
        assert "@" not in block, f"kryptisches @-Token im Pill-Block:\n{block}"
        assert "Spitze" in block, (
            f"ausgeschriebene Spitzen-Form 'Spitze … um HH:00' fehlt:\n{block}"
        )
        assert re.search(r"Spitze\s+18\s*km/h\s+um\s+\d{2}:00", block), (
            f"'Spitze 18 km/h um HH:00' fehlt:\n{block}"
        )

    def test_wind_below_threshold_calm_form(self):
        """Wind durchweg < 10 km/h → ruhige Klartext-Form 'Wind ruhig'."""
        segs = [_seg_with_hours([
            {"hour": 6, "temp": 12, "wind": 3, "gust": 5},
            {"hour": 7, "temp": 14, "wind": 5, "gust": 7},
            {"hour": 8, "temp": 16, "wind": 7, "gust": 9},
        ])]
        html = _render_html(segs)
        block = _metrics_block_html(html)
        assert "Wind ruhig" in block, (
            f"ruhige Klartext-Form 'Wind ruhig' fehlt (Wind < 10):\n{block}"
        )
        assert "max" not in block.split("Wind")[1][:30], (
            f"unter Schwelle darf keine 'max'-Variante erscheinen:\n{block}"
        )

    def test_pill_color_follows_hazard_threshold_not_mention(self):
        """Pill-FARBE/Stufe folgt der GEFAHRENschwelle (display_thresholds),
        NICHT der Erwähnungsschwelle.

        Wind-Spitze 18 km/h: über der SMS-Erwähnungsschwelle (10) → erscheint
        als Ereignis 'Wind ab HH:00', ABER unter der Ampel-Gelbschwelle (30)
        → Stufe muss GRÜN 🟢 sein (wie in der Stundentabelle für 18 km/h).

        RED gegen Prod: Prod färbt nach Erwähnungsschwelle (warn, weil
        18 > 20-Default bzw. > Erwähnung) → keine grüne Ampelstufe.
        """
        from output.renderers.email.helpers import ampel_dot
        from app.metric_catalog import get_metric
        wind_thr = get_metric("wind").display_thresholds
        assert ampel_dot(18.0, wind_thr) == "🟢", "Sanity: 18 km/h ist grün"

        segs = [_seg_with_hours([
            {"hour": 6, "temp": 12, "wind": 6, "gust": 8},
            {"hour": 7, "temp": 14, "wind": 12, "gust": 18},
            {"hour": 8, "temp": 16, "wind": 18, "gust": 25},
        ])]
        plain = _render_plain(segs)
        block = _metrics_block_plain(plain)
        # Wind-Zeile isolieren und ihre Ampelstufe prüfen.
        wind_line = next(
            (ln for ln in block.splitlines() if "Wind" in ln), None
        )
        assert wind_line is not None, f"keine Wind-Pill-Zeile:\n{block}"
        assert "🟢" in wind_line, (
            "Wind-Spitze 18 km/h liegt unter der Ampel-Gelbschwelle (30) → "
            f"Pill-Stufe muss grün 🟢 sein (Gefahrenschwelle), war:\n{wind_line}"
        )
        for hotter in ("🟡", "🟠", "🔴"):
            assert hotter not in wind_line, (
                f"Wind-Pill 18 km/h darf nicht {hotter} (Erwähnungsschwelle "
                f"als Farbquelle?) sein:\n{wind_line}"
            )


# ===========================================================================
# AC-4: Bereichs-Pills ohne Uhrzeit; min==max → Einzelwert
# ===========================================================================

class TestAC4RangePills:

    def test_temperature_range_no_time(self):
        """Temperatur 7..18 → 'Temperatur 7–18 °C' OHNE 'Max HH:00'.

        Der Temperatur-Pill ist eine Bereichs-Metrik (Klasse 2) und darf
        KEINEN Zeitpunkt tragen — heute trägt er '°C · Max HH:00'.
        """
        segs = [_seg_with_hours([
            {"hour": 6, "temp": 7, "wind": 3, "gust": 5},
            {"hour": 7, "temp": 12, "wind": 4, "gust": 6},
            {"hour": 8, "temp": 18, "wind": 4, "gust": 6},
        ])]
        html = _render_html(segs)
        block = _metrics_block_html(html)
        # Isoliere den ersten Pill-Span (Temperatur steht in Katalog-Reihenfolge
        # zuerst). Heute folgt dem '°C' ein ' · Max HH:00' — das ist verboten.
        m = re.search(r"7\s*[–-]\s*18\s*°C([^<]*)", block)
        assert m is not None, f"'7–18 °C' fehlt im Pill-Block:\n{block}"
        tail = m.group(1)
        assert "Max" not in tail and not re.search(r"\d{2}:00", tail), (
            f"Temperatur-Pill darf KEIN 'Max HH:00' tragen, Rest war {tail!r}:\n{block}"
        )

    def test_temperature_constant_single_value(self):
        """Temperatur konstant 12 → Einzelwert 'Temperatur 12 °C' (kein Bereich)."""
        segs = [_seg_with_hours([
            {"hour": 6, "temp": 12, "wind": 3, "gust": 5},
            {"hour": 7, "temp": 12, "wind": 4, "gust": 6},
            {"hour": 8, "temp": 12, "wind": 4, "gust": 6},
        ])]
        html = _render_html(segs)
        block = _metrics_block_html(html)
        assert "12–12" not in block and "12-12" not in block, (
            f"min==max muss Einzelwert ergeben, kein '12–12':\n{block}"
        )
        assert re.search(r"Temperatur\s+12\s*°C", block), (
            f"Einzelwert 'Temperatur 12 °C' fehlt:\n{block}"
        )


# ===========================================================================
# AC-5: Einheitliches Uhrzeitformat HH:00 (behebt rain_probability-:00-Bug)
# ===========================================================================

class TestAC5UniformHourFormat:

    def test_rain_probability_uses_hh00(self):
        """rain_probability über Schwelle → 'ab HH:00', nicht 'ab 14' ohne :00."""
        from app.metric_catalog import build_default_display_config
        import dataclasses
        # Default-config + rain_probability aktiv mit Alert-Schwelle 20%.
        dc = build_default_display_config()
        metrics = []
        seen = False
        for mc in dc.metrics:
            if mc.metric_id == "rain_probability":
                seen = True
                metrics.append(dataclasses.replace(
                    mc, enabled=True, alert_enabled=True, alert_threshold=20.0))
            else:
                metrics.append(mc)
        if not seen:
            from app.models import MetricConfig
            metrics.append(MetricConfig(
                metric_id="rain_probability", enabled=True,
                alert_enabled=True, alert_threshold=20.0))
        dc = dataclasses.replace(dc, metrics=metrics)

        segs = [_seg_with_hours([
            {"hour": 6, "temp": 12, "wind": 3, "gust": 5, "pop": 5},
            {"hour": 7, "temp": 14, "wind": 4, "gust": 6, "pop": 60},
            {"hour": 8, "temp": 16, "wind": 4, "gust": 6, "pop": 80},
        ])]
        html = _render_html(segs, dc=dc)
        block = _metrics_block_html(html)
        # Es muss eine HH:00-Uhrzeit für rain_probability geben.
        assert re.search(r"ab \d{2}:00", block), (
            f"rain_probability-Pill muss 'ab HH:00' (mit :00) tragen, "
            f"nicht 'ab 14' ohne :00:\n{block}"
        )
        # Negativ: keine 'ab <zwei-Ziffern>' ohne folgendes :00.
        assert not re.search(r"ab \d{2}(?!:00)\b", block), (
            f"Variante 'ab HH' OHNE ':00' gefunden:\n{block}"
        )


# ===========================================================================
# AC-6: Vortag-Prominenz — eigene Box ≥14px, nicht 13px/#5c5a52; Plain: eine Zeile
# ===========================================================================

class TestAC6VortagProminence:

    def _comparison_dc(self):
        today = [_seg_for_compare(1, temp_min_c=10.0, temp_max_c=20.0,
                                  wind_max_kmh=20.0, precip_sum_mm=1.0)]
        yday = [_seg_for_compare(1, temp_min_c=6.0, temp_max_c=15.0,
                                 wind_max_kmh=20.0, precip_sum_mm=10.0)]
        return _comparison(today, yday)

    def test_vortag_not_weak_signature_html(self):
        dc = self._comparison_dc()
        html = _render_html(_build_segments(), day_comparison=dc)
        pos = html.find("Vortag: heute")
        assert pos != -1, "Vortag-Zeile fehlt"
        # Umliegender Markup der Vortag-Box.
        box = html[max(0, pos - 250):pos + 50]
        assert not ("font-size:13px" in box and "#5c5a52" in box), (
            "Vortag-Box trägt die schwache Signatur (13px + #5c5a52); sie muss "
            f"eine prominente eigene Einheit (≥14px) sein:\n{box}"
        )

    def test_vortag_at_least_14px_html(self):
        dc = self._comparison_dc()
        html = _render_html(_build_segments(), day_comparison=dc)
        pos = html.find("Vortag: heute")
        assert pos != -1
        box = html[max(0, pos - 250):pos + 50]
        m = re.search(r"font-size:\s*(\d+)px", box)
        assert m is not None, f"keine font-size in Vortag-Box:\n{box}"
        assert int(m.group(1)) >= 14, (
            f"Vortag-Box font-size {m.group(1)}px < 14px (zu schwach):\n{box}"
        )

    def test_exactly_one_vortag_line_plain(self):
        dc = self._comparison_dc()
        plain = _render_plain(_build_segments(), day_comparison=dc)
        count = plain.count("Vortag: heute")
        assert count == 1, f"genau EINE Vortag-Zeile erwartet, gefunden: {count}"


# ===========================================================================
# AC-7 (v3): WCAG-AA Vollfarb-Kapsel — die VIER Ampelstufen-Vollfarben
# (🟢🟡🟠🔴) je ≥ 4.5:1 mit weißem Text, Form bleibt Vollfarb-Kapsel.
# ===========================================================================

# Die vier Stufen-Tone-Namen der SSoT-Ampel-Farbtabelle. Spec v3: EINE
# 4-stufige Farbtabelle (WCAG-gedunkelte Entsprechungen von 🟢🟡🟠🔴).
_AMPEL_STAGE_TONES = ("ampel_green", "ampel_yellow", "ampel_orange", "ampel_red")


class TestAC7WcagFullColorFourStages:

    def _parse_pill(self, html: str):
        """Extrahiere (bg, fg) aus dem gerenderten pill_html-Span."""
        bg = re.search(r"background:\s*(#[0-9a-fA-F]{6})", html)
        fg = re.search(r"color:\s*(#[0-9a-fA-F]{6})", html)
        assert bg and fg, f"bg/fg nicht parsebar:\n{html}"
        return bg.group(1).lower(), fg.group(1).lower()

    def test_four_ampel_stage_colors_meet_wcag_aa(self):
        """Jede der 4 Ampelstufen-Vollfarben + weißer Text ≥ 4.5:1.

        RED gegen Prod: der 4-stufige Ampel-Vollfarbsatz existiert noch nicht
        (pill_html kennt nur good/warn/bad/info; 'ampel_yellow' o.ä. fällt auf
        die neutrale Surface-Farbe #edeae1 mit dunklem Text zurück → bg ist
        nicht die erwartete Stufen-Vollfarbe / kein weißer Text).
        """
        from output.renderers.email.helpers import pill_html
        seen_bg = set()
        for tone in _AMPEL_STAGE_TONES:
            html = pill_html("Beispiel", tone)
            bg, fg = self._parse_pill(html)
            ratio = _contrast_ratio(bg, fg)
            assert ratio >= 4.5, (
                f"Ampelstufe {tone}: Kontrast {round(ratio, 2)}:1 < 4.5:1 "
                f"(bg={bg}, fg={fg})"
            )
            seen_bg.add(bg)
        # ampel_yellow + ampel_orange mappen beide auf 'warn' → 3 distinkte BGs by design (#851)
        assert len(seen_bg) >= 3, (
            f"Mind. 3 unterscheidbare Stufen-Farben erwartet, gefunden: {seen_bg}"
        )

    def test_full_color_capsule_shape(self):
        from output.renderers.email.helpers import pill_html
        for tone in _AMPEL_STAGE_TONES:
            html = pill_html("Beispiel", tone)
            assert "border-radius:2px" in html, (
                f"Ampelstufe {tone}: Outline-Tag-Form (border-radius:2px) fehlt"
            )


# ===========================================================================
# AC-9 (NEU, Kern): Ampel-Konsistenz Pill ↔ #759-Stundentabelle.
# Derselbe Spitzenwert ergibt dieselbe Stufe/Farbe in Tabelle UND Pill,
# weil beide ampel_dot(value, display_thresholds) nutzen (EIN Ampel-System).
# ===========================================================================

def _wind_pill_line_plain(plain: str) -> str:
    """Isoliere die Wind-Pill-Zeile aus dem Plain-Metriken-Block."""
    block = _metrics_block_plain(plain)
    for ln in block.splitlines():
        if "Wind" in ln and "Böe" not in ln and "Böen" not in ln:
            return ln
    raise AssertionError(f"keine Wind-Pill-Zeile im Plain-Block:\n{block}")


def _emoji_level_in(text: str) -> int:
    """Stufenindex 0..3 des im Text vorkommenden Ampel-Emojis (genau eins)."""
    found = [e for e in _AMPEL_EMOJIS if e in text]
    assert len(found) == 1, (
        f"genau EIN Ampel-Emoji erwartet, gefunden {found} in {text!r}"
    )
    return _AMPEL_LEVEL[found[0]]


class TestAC9AmpelConsistency:

    def _segs_with_wind_peak(self, peak: float):
        """Ein Segment, dessen Wind-Spitze (max) genau `peak` km/h ist.

        Der erste Wert liegt knapp unter `peak`, der zweite IST `peak` —
        so ist der aggregierte Spitzenwert deterministisch `peak`.
        """
        lo = max(0.0, peak - 5.0)
        return [_seg_with_hours([
            {"hour": 6, "temp": 12, "wind": lo, "gust": lo + 5},
            {"hour": 7, "temp": 14, "wind": peak, "gust": peak + 5},
            {"hour": 8, "temp": 16, "wind": lo, "gust": lo + 5},
        ])]

    def test_wind_pill_stage_equals_table_ampel_at_boundaries(self):
        """Für Grenzwerte der Wind-Ampel (29/30/50/70) muss die Pill-Stufe
        == ampel_dot(peak, display_thresholds) sein — exakt die Tabellenstufe.

        Wind-display_thresholds: yellow 30, orange 50, red 70.
        Erwartung: 29→🟢(0), 30→🟡(1), 50→🟠(2), 70→🔴(3).

        RED gegen Prod: Prod färbt den Wind-Pill nach der Erwähnungsschwelle
        (warn ab Wind > 20) und schreibt '[WARN]'/'[GOOD]' statt der
        Ampel-Emojis → die Pill-Stufe entspricht NICHT ampel_dot(peak, …).
        """
        from app.metric_catalog import get_metric
        wind_thr = get_metric("wind").display_thresholds
        for peak in (29.0, 30.0, 50.0, 70.0):
            expected = _ampel_level(peak, wind_thr)
            plain = _render_plain(self._segs_with_wind_peak(peak))
            line = _wind_pill_line_plain(plain)
            actual = _emoji_level_in(line)
            assert actual == expected, (
                f"Wind-Spitze {peak} km/h: Tabellen-Ampelstufe ist "
                f"{_AMPEL_EMOJIS[expected]} (Stufe {expected}), Pill zeigt "
                f"{_AMPEL_EMOJIS[actual]} (Stufe {actual}) — Pill ≠ Tabelle:\n{line}"
            )

    def test_rain_probability_pill_stage_equals_table_ampel(self):
        """Analog für Regenwahrscheinlichkeit (Schwellen 30/60/80)."""
        import dataclasses
        from app.metric_catalog import build_default_display_config, get_metric
        from app.models import MetricConfig
        pop_thr = get_metric("rain_probability").display_thresholds

        dc = build_default_display_config()
        metrics, seen = [], False
        for mc in dc.metrics:
            if mc.metric_id == "rain_probability":
                seen = True
                metrics.append(dataclasses.replace(
                    mc, enabled=True, alert_enabled=True, alert_threshold=20.0))
            else:
                metrics.append(mc)
        if not seen:
            metrics.append(MetricConfig(
                metric_id="rain_probability", enabled=True,
                alert_enabled=True, alert_threshold=20.0))
        dc = dataclasses.replace(dc, metrics=metrics)

        # 29→🟢, 30→🟡, 60→🟠, 80→🔴 (display_thresholds 30/60/80).
        for peak in (29, 30, 60, 80):
            expected = _ampel_level(float(peak), pop_thr)
            segs = [_seg_with_hours([
                {"hour": 6, "temp": 12, "wind": 3, "gust": 5, "pop": max(0, peak - 5)},
                {"hour": 7, "temp": 14, "wind": 4, "gust": 6, "pop": peak},
                {"hour": 8, "temp": 16, "wind": 4, "gust": 6, "pop": max(0, peak - 5)},
            ])]
            plain = _render_plain(segs, dc=dc)
            block = _metrics_block_plain(plain)
            pop_line = next(
                (ln for ln in block.splitlines()
                 if ("Regen-W" in ln or "Regenrisiko" in ln
                     or "Regenwahrsch" in ln)),
                None,
            )
            assert pop_line is not None, (
                f"keine Regenwahrsch.-Pill-Zeile (peak={peak}):\n{block}"
            )
            actual = _emoji_level_in(pop_line)
            assert actual == expected, (
                f"Regenwahrsch. {peak}%: Tabellen-Ampelstufe "
                f"{_AMPEL_EMOJIS[expected]}, Pill {_AMPEL_EMOJIS[actual]} — "
                f"Pill ≠ Tabelle:\n{pop_line}"
            )
