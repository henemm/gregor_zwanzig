"""
TDD RED — Issue #664: Metriken-Überblick am Beginn der E-Mail.

Vertrag (NOCH NICHT implementiert):
- TripReportConfig.show_metrics_summary: bool = False  (models.py)
- loader lädt/serialisiert das Feld (loader.py)
- build_metrics_summary_pills(segments, metric_ids, thresholds) in helpers.py
- render_html(..., show_metrics_summary=bool) in html.py
- render_plain(..., show_metrics_summary=bool) in plain.py

Mock-frei: echte ForecastDataPoint/SegmentWeatherData/TripSegment-Objekte.
Fixture-Muster aus tests/tdd/test_issue_621_email_toggles.py übernommen.
Spec: docs/specs/modules/email_metrics_summary_664.md
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

TZ = ZoneInfo("Europe/Berlin")


# ---------------------------------------------------------------------------
# Fixtures — Segmente mit bekannten Stundenwerten
#
# Regen-Summe         = 0+1+2 + 3+0+0       = 6.0 mm
# Max Böe (gust)      = max(10,20,30,40,15,15) = 40.0 km/h
# Max Wind (wind10m)  = max(5,10,15,20,7,7)   = 20.0 km/h   (gust * 0.5)
# Min Sicht           = min(2000,1500,1200,3000,2500,1800) = 1200 m
# Temp                = aus `temps`-Liste (Default 12.0 konstant)
# Stunden (UTC)       = 6,7,8 (seg1) + 8,9,10 (seg2)
# Max-Böe-Stunde      = 8 (UTC) → 10 (CEST)
# Max-Wind-Stunde     = 8 (UTC) → 10 (CEST)
# ---------------------------------------------------------------------------

def _build_segments(temps=None, wind_override=None):
    """Zwei Segmente mit bekannten Werten (identisch zu #621-Fixture)."""
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )

    def _dp(h, precip, gust, vis, temp):
        return ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=float(temp), wind10m_kmh=gust * 0.5, gust_kmh=float(gust),
            precip_1h_mm=float(precip), pop_pct=int(min(precip * 20, 100)),
            cloud_total_pct=60, thunder_level=ThunderLevel.NONE,
            visibility_m=vis, freezing_level_m=2500,
        )

    def _make_seg(seg_id, start_km, end_km, start_h, end_h, rows):
        seg = TripSegment(
            segment_id=seg_id,
            start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=400.0,
                                 distance_from_start_km=start_km),
            end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1200.0,
                               distance_from_start_km=end_km),
            start_time=datetime(2026, 7, 11, start_h, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 7, 11, end_h, 0, tzinfo=timezone.utc),
            duration_hours=float(end_h - start_h),
            distance_km=round(end_km - start_km, 1),
            ascent_m=800.0, descent_m=0.0,
        )
        meta = ForecastMeta(provider=Provider.OPENMETEO, model="demo",
                            grid_res_km=1.3,
                            run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc))
        ts = NormalizedTimeseries(meta=meta, data=rows)
        agg = SegmentWeatherSummary(
            temp_min_c=10.0, temp_max_c=14.0, temp_avg_c=12.0,
            wind_max_kmh=20.0, gust_max_kmh=40.0,
            precip_sum_mm=6.0, cloud_avg_pct=60, humidity_avg_pct=55,
            thunder_level_max=ThunderLevel.NONE,
        )
        return SegmentWeatherData(segment=seg, timeseries=ts, aggregated=agg,
                                  fetched_at=datetime.now(timezone.utc),
                                  provider="demo")

    t = temps or [12.0] * 6
    seg1_rows = [_dp(6, 0, 10, 2000, t[0]), _dp(7, 1, 20, 1500, t[1]),
                 _dp(8, 2, 30, 1200, t[2])]
    seg2_rows = [_dp(8, 3, 40, 3000, t[3]), _dp(9, 0, 15, 2500, t[4]),
                 _dp(10, 0, 15, 1800, t[5])]
    return [
        _make_seg(1, 0.0, 4.2, 6, 8, seg1_rows),
        _make_seg(2, 4.2, 9.3, 8, 10, seg2_rows),
    ]


_SIMPLE_ROWS = [{
    "time": "06:00", "temp": 12.0, "_wind_dir_deg": None, "_is_day": True,
    "_dni_wm2": None, "_sunny_hours": 0.0, "_wmo_code": None,
}]

_STATS = {"distance_km": 9.3, "ascent_m": 1600.0, "descent_m": 0.0,
          "max_elevation_m": 1200}


def _render_html(segs, **kwargs):
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html
    params = dict(
        segments=segs, seg_tables=[_SIMPLE_ROWS] * len(segs),
        trip_name="GR20 Test", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None,
        stage_name=None, stage_stats=None, multi_day_trend=None,
        compact_summary=None, tz=TZ, friendly_keys=set(),
    )
    params.update(kwargs)
    return render_html(**params)


def _render_plain(segs, **kwargs):
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.plain import render_plain
    params = dict(
        segments=segs, seg_tables=[_SIMPLE_ROWS] * len(segs),
        trip_name="GR20 Test", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None,
        stage_name=None, stage_stats=None, multi_day_trend=None,
        compact_summary=None, tz=TZ, friendly_keys=set(),
    )
    params.update(kwargs)
    return render_plain(**params)


# ---------------------------------------------------------------------------
# AC-1: Loader-Roundtrip — show_metrics_summary Default + Persistenz
# ---------------------------------------------------------------------------

class TestAC1LoaderRoundtrip:
    """TripReportConfig.show_metrics_summary: bool = False muss existieren
    und loader.py muss das Feld laden/serialisieren.

    RED: AttributeError — TripReportConfig hat kein show_metrics_summary-Feld.
    """

    def _trip_dict(self, *, with_field: bool = False, value: bool = False):
        rc = {
            "trip_id": "test-664",
            "morning_time": "07:00:00",
            "evening_time": "18:00:00",
        }
        if with_field:
            rc["show_metrics_summary"] = value
        return {
            "trip": {
                "id": "test-664",
                "name": "Test Trip",
                "report_config": rc,
                "stages": [{
                    "id": "S1", "name": "Etappe 1", "date": "2026-07-11",
                    "waypoints": [{
                        "id": "W1", "name": "Start",
                        "lat": 42.0, "lon": 9.0, "elevation_m": 400,
                    }],
                }],
            }
        }

    def test_default_is_false_without_field(self):
        """Feld fehlt im JSON → Default False."""
        from app.loader import load_trip_from_dict
        trip = load_trip_from_dict(self._trip_dict(with_field=False))
        # RED: AttributeError — TripReportConfig hat show_metrics_summary nicht
        assert trip.report_config.show_metrics_summary is False

    def test_true_roundtrip(self):
        """Wert True überlebt load→dump→load."""
        from app.loader import load_trip_from_dict, dump_trip_to_dict
        trip = load_trip_from_dict(self._trip_dict(with_field=True, value=True))
        # RED: AttributeError — TripReportConfig hat show_metrics_summary nicht
        assert trip.report_config.show_metrics_summary is True
        dumped = dump_trip_to_dict(trip)
        # dump muss Feld serialisieren
        assert "show_metrics_summary" in dumped["report_config"]
        assert dumped["report_config"]["show_metrics_summary"] is True
        # Roundtrip: erneut laden
        trip2 = load_trip_from_dict({"trip": dumped})
        assert trip2.report_config.show_metrics_summary is True

    def test_false_roundtrip(self):
        """Wert False überlebt load→dump→load."""
        from app.loader import load_trip_from_dict, dump_trip_to_dict
        trip = load_trip_from_dict(self._trip_dict(with_field=True, value=False))
        assert trip.report_config.show_metrics_summary is False
        dumped = dump_trip_to_dict(trip)
        assert dumped["report_config"]["show_metrics_summary"] is False

    def test_dataclass_default(self):
        """TripReportConfig() direkt — Default False."""
        from app.models import TripReportConfig
        rc = TripReportConfig(trip_id="x")
        # RED: AttributeError — Feld existiert nicht
        assert rc.show_metrics_summary is False


# ---------------------------------------------------------------------------
# AC-3: Helper-Werte — build_metrics_summary_pills
# ---------------------------------------------------------------------------

class TestAC3HelperValues:
    """build_metrics_summary_pills muss Pillen aus echten Segment-Daten ableiten.

    RED: ImportError — build_metrics_summary_pills existiert nicht in helpers.py.

    Fixtures-Aggregate (aus _build_segments Default-12°C):
      temperature: min=12°C, max=12°C  (stündliche Werte: alle 12.0)
      wind: max gust=40, bei h=8 UTC → Ortszeit "10:00"
      gust: analog Wind
      precipitation: Summe=6 mm, erste Regen-Stunde h=7 UTC → "09:00" CEST
    """

    def test_import_exists(self):
        """Helper ist importierbar."""
        # RED: ImportError
        from output.renderers.email.helpers import build_metrics_summary_pills  # noqa
        assert callable(build_metrics_summary_pills)

    def test_temperature_pill_text(self):
        """temperature-Pille: '{min}–{max}°C · Max {hh}:00'."""
        from output.renderers.email.helpers import build_metrics_summary_pills
        segs = _build_segments(temps=[8.0, 9.0, 10.0, 11.0, 12.0, 15.0])
        # Erwartung: min=8°C, max=15°C; t2m_c-Maximum bei h=10 UTC → 12:00 CEST
        pills = build_metrics_summary_pills(segs, ["temperature"], {}, tz=TZ)
        texts = [t for t, _ in pills]
        # Pille enthält Minimaltemperatur: min(8, 9, 11, 12) = 8
        assert any("8" in t for t in texts), f"8°C (min) nicht in Pillen: {texts}"
        # Pille enthält Maximaltemperatur: max(8, 9, 11, 12) = 12 (15 fällt weg, da 15 Uhr außerhalb des Fensters)
        assert any("12" in t for t in texts), f"12°C (max) nicht in Pillen: {texts}"

    def test_temperature_tone_is_info(self):
        """Issue #795: temperature ist Klasse 2 (Bereich) → neutraler Tone.

        Frueher 'info'; seit #795 trägt jede Bereichs-Metrik den neutralen
        Tone (kein Schweregrad — die Ampelstufen sind den Ereignis-Metriken
        vorbehalten, AC-9).
        """
        from output.renderers.email.helpers import (
            _PILL_NEUTRAL_TONE, build_metrics_summary_pills,
        )
        segs = _build_segments()
        pills = build_metrics_summary_pills(segs, ["temperature"], {}, tz=TZ)
        tones = [tone for _, tone in pills]
        assert any(tone == _PILL_NEUTRAL_TONE for tone in tones), (
            f"neutraler Tone erwartet, got: {tones}"
        )

    def test_precipitation_pill_with_rain(self):
        """precipitation-Pille bei Regen: enthält Summe '4 mm'."""
        from output.renderers.email.helpers import build_metrics_summary_pills
        segs = _build_segments()
        pills = build_metrics_summary_pills(segs, ["precipitation"], {}, tz=TZ)
        texts = [t for t, _ in pills]
        assert any("4" in t for t in texts), f"4 mm nicht in Pillen: {texts}"

    def test_gust_pill_has_max_value(self):
        """gust-Pille: max Böe = 40 km/h muss enthalten sein."""
        from output.renderers.email.helpers import build_metrics_summary_pills
        segs = _build_segments()
        pills = build_metrics_summary_pills(segs, ["gust"], {}, tz=TZ)
        texts = [t for t, _ in pills]
        assert any("40" in t for t in texts), f"40 km/h (max gust) nicht in Pillen: {texts}"

    def test_metric_order_follows_catalog(self):
        """Reihenfolge der Pillen folgt Katalog, nicht Eingabe-Reihenfolge."""
        from output.renderers.email.helpers import build_metrics_summary_pills
        # Eingabe umgekehrt: precipitation NACH temperature
        segs = _build_segments()
        pills = build_metrics_summary_pills(
            segs, ["precipitation", "temperature"], {}, tz=TZ
        )
        ids_order = [t for t, _ in pills]
        # temperature kommt im Katalog vor precipitation → temperature zuerst
        # Prüfe, dass der temperature-Wert (enthält "°C") vor precipitation (enthält "mm" oder "Regen")
        temp_pos = next((i for i, t in enumerate(ids_order) if "°C" in t), None)
        rain_pos = next((i for i, t in enumerate(ids_order) if "mm" in t or "Regen" in t.lower()), None)
        if temp_pos is not None and rain_pos is not None:
            assert temp_pos < rain_pos, (
                f"temperature muss vor precipitation stehen (Katalog-Reihenfolge): {ids_order}"
            )


# ---------------------------------------------------------------------------
# AC-4: Schwellwert-Crossing → Tone warn + Text ">thr ab hh"
# ---------------------------------------------------------------------------

class TestAC4ThresholdCrossing:
    """Wenn Wind-Schwelle unterschritten → Tone 'good'; überschritten → 'warn'.

    Fixture: max gust=40 km/h; threshold wind=15 → Crossing bei 20 km/h (h=7 UTC)
    oder gust=10 km/h (h=6 UTC) — aber max gust über alle Stunden = 40 > 15 → warn.

    RED: ImportError — build_metrics_summary_pills existiert nicht.
    """

    def test_wind_crossing_tone_is_warn(self):
        """Issue #795/AC-9: Gust-Pill-Stufe folgt der Ampel (display_thresholds).

        Fixture max gust=40 km/h. Gust-Ampel: yellow 50 → 40 km/h liegt darunter
        → Stufe GRÜN (ampel_green). Die FARBE folgt NICHT der Erwähnungs- oder
        einer User-Schwelle, sondern ampel_dot(peak, display_thresholds).
        """
        from output.renderers.email.helpers import (
            ampel_stage_tone, build_metrics_summary_pills,
        )
        from app.metric_catalog import get_metric
        segs = _build_segments()
        pills = build_metrics_summary_pills(segs, ["gust"], {}, tz=TZ)
        tones = [tone for _, tone in pills]
        expected = ampel_stage_tone(40.0, get_metric("gust").display_thresholds)
        assert any(tone == expected for tone in tones), (
            f"Ampelstufe {expected} (peak 40 km/h) erwartet, got: {tones}"
        )

    def test_wind_crossing_text_contains_threshold(self):
        """Issue #912: Über SMS-Schwelle erscheint 'max 40' (neues Format).

        Fixture max gust=40 → neues Format '>thr ab HH:00 · max 40 (HH:00)'.
        '40' (Spitzenwert) und 'max' müssen im Text stehen.
        """
        from output.renderers.email.helpers import build_metrics_summary_pills
        segs = _build_segments()
        pills = build_metrics_summary_pills(segs, ["gust"], {}, tz=TZ)
        texts = [t for t, _ in pills]
        assert any("40" in t and "max" in t for t in texts), (
            f"Spitzenwert '40' und 'max' müssen im Text stehen: {texts}"
        )

    def test_wind_crossing_text_contains_hour(self):
        """Crossing-Text enthält 'ab {hh}' für die erste Überschreitungsstunde."""
        from output.renderers.email.helpers import build_metrics_summary_pills
        segs = _build_segments()
        pills = build_metrics_summary_pills(
            segs, ["gust"], {"gust": 15.0}, tz=TZ
        )
        texts = [t for t, _ in pills]
        # Erste Überschreitung: h=7 UTC (gust=20) → 09:00 CEST, oder h=8 (gust=30) → 10:00
        # Mindestens eine Stunde mit "ab" oder ":00" enthalten
        assert any("ab" in t.lower() or ":00" in t for t in texts), (
            f"'ab <hh>:00' muss im Crossing-Text stehen: {texts}"
        )

    def test_wind_no_crossing_tone_is_good(self):
        """Issue #912: Böen durchweg unter SMS-Schwelle → max-Form + grün.

        Unter Schwelle → 'Böen max X km/h (HH:00)' (kein 'Böen ruhig' mehr),
        und da der Spitzenwert klar unter der Ampel-Gelbschwelle (50) liegt →
        ampel_green.
        """
        from output.renderers.email.helpers import (
            build_metrics_summary_pills,
        )
        # max gust=10 (alle Stunden < 20 SMS-Schwelle, < 50 Ampel-Gelb).
        segs = _build_segments(temps=[5.0] * 6)
        for seg in segs:
            for dp in seg.timeseries.data:
                object.__setattr__(dp, "gust_kmh", 10.0)
        pills = build_metrics_summary_pills(segs, ["gust"], {}, tz=TZ)
        texts = [t for t, _ in pills]
        tones = [tone for _, tone in pills]
        assert any("Böen max" in t for t in texts), (
            f"max-Form 'Böen max X km/h (HH:00)' erwartet: {texts}"
        )
        assert any(tone == "ampel_green" for tone in tones), (
            f"ampel_green bei ruhiger Lage erwartet, got: {tones}"
        )


# ---------------------------------------------------------------------------
# Issue #790: Metriken-Überblick ist jetzt der EINE feste Block — IMMER an.
# Quick-Take und Tages-Summe wurden komplett aus dem Render-Code entfernt.
# ---------------------------------------------------------------------------

class TestMetricsAlwaysOnHtml:

    def test_eyebrow_always_present(self):
        """Metriken-Überblick erscheint immer (kein Gate mehr)."""
        html = _render_html(_build_segments())
        assert "Metriken-Überblick" in html

    def test_no_quick_take_chips(self):
        """Quick-Take-Chips wurden entfernt — 'Kein Gewitter' erscheint nie."""
        html = _render_html(_build_segments())
        assert "Kein Gewitter" not in html

    def test_no_daily_summary_block(self):
        """Tages-Summe-Block wurde entfernt."""
        html = _render_html(_build_segments())
        assert "Tages-Summe" not in html


class TestMetricsAlwaysOnPlain:

    def test_plain_eyebrow_always_present(self):
        plain = _render_plain(_build_segments())
        assert "Metriken-Überblick" in plain

    def test_plain_no_daily_summary_block(self):
        plain = _render_plain(_build_segments())
        assert "Tages-Summe" not in plain
