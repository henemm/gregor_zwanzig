"""
TDD RED — Issue #912: Pill-Textformat METRIKEN-ÜBERBLICK an JSX-Design-Vorlage angleichen.

Alle 12 Tests prüfen das NEUE (noch NICHT implementierte) Format.
Sie müssen ALLE FEHLSCHLAGEN, solange die alte Implementierung aktiv ist.

Spec: docs/specs/modules/issue_912_pill_textformat.md
Referenz-Fixture: tests/tdd/test_issue_664_metrics_summary.py::_build_segments
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
# Fixture-Hilfe: ForecastDataPoint + SegmentWeatherData aus einfachen Werten
# ---------------------------------------------------------------------------

def _dp(h_utc: int, t2m_c=12.0, wind_chill_c=None, wind10m_kmh=5.0,
        gust_kmh=10.0, precip_1h_mm=0.0, pop_pct=0, cloud_total_pct=60,
        visibility_m=10000, freezing_level_m=2500, humidity_pct=55,
        dewpoint_c=None, uv_index=None):
    """Erstellt einen echten ForecastDataPoint für UTC-Stunde h_utc."""
    from app.models import ForecastDataPoint, ThunderLevel
    kwargs = dict(
        ts=datetime(2026, 7, 11, h_utc, 0, tzinfo=timezone.utc),
        t2m_c=float(t2m_c),
        wind10m_kmh=float(wind10m_kmh),
        gust_kmh=float(gust_kmh),
        precip_1h_mm=float(precip_1h_mm),
        pop_pct=int(pop_pct),
        cloud_total_pct=int(cloud_total_pct),
        thunder_level=ThunderLevel.NONE,
        visibility_m=int(visibility_m),
        freezing_level_m=int(freezing_level_m),
        humidity_pct=int(humidity_pct),
    )
    if wind_chill_c is not None:
        kwargs["wind_chill_c"] = float(wind_chill_c)
    if dewpoint_c is not None:
        kwargs["dewpoint_c"] = float(dewpoint_c)
    if uv_index is not None:
        kwargs["uv_index"] = float(uv_index)
    return ForecastDataPoint(**kwargs)


def _make_segment(dps, start_h_utc=6, end_h_utc=10):
    """Erstellt ein SegmentWeatherData mit den angegebenen DataPoints."""
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=400.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1200.0,
                           distance_from_start_km=9.0),
        start_time=datetime(2026, 7, 11, start_h_utc, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, end_h_utc, 0, tzinfo=timezone.utc),
        duration_hours=float(end_h_utc - start_h_utc),
        distance_km=9.0,
        ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
    )
    ts = NormalizedTimeseries(meta=meta, data=dps)
    agg = SegmentWeatherSummary(
        temp_min_c=8.0, temp_max_c=11.0, temp_avg_c=10.0,
        wind_max_kmh=40.0, gust_max_kmh=40.0,
        precip_sum_mm=8.0, cloud_avg_pct=78, humidity_avg_pct=65,
        thunder_level_max=ThunderLevel.NONE,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="demo",
    )


# UTC 6,7,8 → CEST 8,9,10 (UTC+2 Sommer)
# ---------------------------------------------------------------------------
# AC-1: Temperatur — Format "8–11°C · Max HH:00"
# ---------------------------------------------------------------------------

class TestAC1Temperature:
    """AC-1: Temperatur-Pille zeigt Bereich + Uhrzeit des Maximums.

    Daten: 3 Stunden UTC 6,7,8 → CEST 8,9,10. Temps: 8°C, 10°C, 11°C.
    SOLL: "8–11°C · Max 10:00" (Max 11°C um CEST 10).
    IST (aktuell): "Temperatur 8–11 °C" → Test MUSS FEHLSCHLAGEN.
    """

    def _pills(self):
        from output.renderers.email.helpers import build_metrics_summary_pills
        dps = [
            _dp(6, t2m_c=8.0),
            _dp(7, t2m_c=10.0),
            _dp(8, t2m_c=11.0),
        ]
        segs = [_make_segment(dps, start_h_utc=6, end_h_utc=9)]
        return build_metrics_summary_pills(segs, ["temperature"], {}, tz=TZ)

    def test_temperature_format_has_time(self):
        """SOLL: enthält ':00' (Uhrzeit des Maximums)."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any(":00" in t for t in texts), (
            f"AC-1: Uhrzeit ':00' fehlt im Temperatur-Format — got: {texts}"
        )

    def test_temperature_format_no_label_prefix(self):
        """SOLL: kein 'Temperatur'-Label-Präfix, kein Leerzeichen vor '°C'."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert not any(t.startswith("Temperatur") for t in texts), (
            f"AC-1: 'Temperatur'-Präfix darf nicht erscheinen — got: {texts}"
        )

    def test_temperature_format_exact(self):
        """SOLL: '8–11°C · Max 10:00' (kein Leerzeichen vor °C)."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any("8–11°C · Max 10:00" in t for t in texts), (
            f"AC-1: Exaktes Format '8–11°C · Max 10:00' erwartet — got: {texts}"
        )


# ---------------------------------------------------------------------------
# AC-2: Gefühlt (wind_chill) — Format "gef. min X°C · HH:00"
# ---------------------------------------------------------------------------

class TestAC2WindChill:
    """AC-2: Gefühlt-Pille zeigt Mindestwert + Uhrzeit.

    Daten: wind_chill 9°C, 8°C, 6.6°C (min ist 6.6 um CEST 10/UTC 8).
    SOLL: "gef. min 6.6°C · 10:00".
    IST: "Gefühlt 7–9 °C" → FAIL.
    """

    def _pills(self):
        from output.renderers.email.helpers import build_metrics_summary_pills
        dps = [
            _dp(6, t2m_c=15.0, wind_chill_c=9.0),
            _dp(7, t2m_c=15.0, wind_chill_c=8.0),
            _dp(8, t2m_c=15.0, wind_chill_c=6.6),
        ]
        segs = [_make_segment(dps, start_h_utc=6, end_h_utc=9)]
        return build_metrics_summary_pills(segs, ["wind_chill"], {}, tz=TZ)

    def test_wind_chill_has_time(self):
        """SOLL: enthält ':00' (Uhrzeit des Minimums)."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any(":00" in t for t in texts), (
            f"AC-2: Uhrzeit ':00' fehlt in Gefühlt-Format — got: {texts}"
        )

    def test_wind_chill_format_gef_prefix(self):
        """SOLL: beginnt mit 'gef.' (Abkürzung, kein 'Gefühlt'-Label)."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any(t.startswith("gef.") for t in texts), (
            f"AC-2: Kein 'gef.'-Präfix gefunden — got: {texts}"
        )

    def test_wind_chill_format_exact(self):
        """SOLL: 'gef. min 6.6°C · 10:00'."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any("gef. min 6.6°C · 10:00" in t for t in texts), (
            f"AC-2: Exaktes Format 'gef. min 6.6°C · 10:00' erwartet — got: {texts}"
        )


# ---------------------------------------------------------------------------
# AC-3: Wind ohne Schwellenüberschreitung — "Wind max X km/h (HH:00)"
# ---------------------------------------------------------------------------

class TestAC3WindBelowThreshold:
    """AC-3: Wind unter SMS-Schwelle zeigt neues 'max'-Format statt 'Wind ruhig'.

    SMS-Schwelle Wind ist 10 km/h. Daten: wind10m_kmh 3, 5, 7 (max 7 um CEST 10/UTC 8).
    SOLL: "Wind max 7 km/h (10:00)".
    IST: "Wind ruhig" → FAIL.
    """

    def _pills(self):
        from output.renderers.email.helpers import build_metrics_summary_pills
        dps = [
            _dp(6, wind10m_kmh=3.0, gust_kmh=5.0),
            _dp(7, wind10m_kmh=5.0, gust_kmh=8.0),
            _dp(8, wind10m_kmh=7.0, gust_kmh=10.0),
        ]
        segs = [_make_segment(dps, start_h_utc=6, end_h_utc=9)]
        return build_metrics_summary_pills(segs, ["wind"], {}, tz=TZ)

    def test_wind_no_calm_form(self):
        """SOLL: 'Wind ruhig' erscheint nicht mehr."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert not any("Wind ruhig" in t for t in texts), (
            f"AC-3: 'Wind ruhig' darf nicht erscheinen — got: {texts}"
        )

    def test_wind_has_max_format(self):
        """SOLL: enthält 'Wind max' und '7' und '(10:00)'."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any("Wind max" in t and "7" in t and "(10:00)" in t for t in texts), (
            f"AC-3: Format 'Wind max 7 km/h (10:00)' erwartet — got: {texts}"
        )


# ---------------------------------------------------------------------------
# AC-4: Wind mit Schwellenüberschreitung — Präfix ">thr"
# ---------------------------------------------------------------------------

class TestAC4WindAboveThreshold:
    """AC-4: Wind über Schwelle zeigt '>thr'-Präfix-Format.

    Daten: wind10m_kmh 15, 30, 40 (erste ≥10 um CEST 8/UTC 6, Max 40 um CEST 10/UTC 8).
    SOLL-Format: enthält '>10 km/h ab 08:00' und 'max 40'.
    IST: "Wind ab 08:00 · Spitze 40 km/h um 10:00" → FAIL.
    """

    def _pills(self):
        from output.renderers.email.helpers import build_metrics_summary_pills
        dps = [
            _dp(6, wind10m_kmh=15.0, gust_kmh=20.0),
            _dp(7, wind10m_kmh=30.0, gust_kmh=35.0),
            _dp(8, wind10m_kmh=40.0, gust_kmh=45.0),
        ]
        segs = [_make_segment(dps, start_h_utc=6, end_h_utc=9)]
        return build_metrics_summary_pills(segs, ["wind"], {}, tz=TZ)

    def test_wind_above_threshold_has_gt_prefix(self):
        """SOLL: enthält '>10 km/h ab 08:00' (Schwellenwert-Präfix)."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any(">10 km/h ab 08:00" in t for t in texts), (
            f"AC-4: '>10 km/h ab 08:00' erwartet — got: {texts}"
        )

    def test_wind_above_threshold_has_max(self):
        """SOLL: enthält 'max 40' (Spitzenwert)."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any("max 40" in t for t in texts), (
            f"AC-4: 'max 40' erwartet — got: {texts}"
        )

    def test_wind_no_old_spitze_format(self):
        """SOLL: 'Spitze' erscheint nicht im neuen Format."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert not any("Spitze" in t for t in texts), (
            f"AC-4: 'Spitze' darf im neuen Format nicht erscheinen — got: {texts}"
        )


# ---------------------------------------------------------------------------
# AC-5: Regen vereinfacht — "Regen ab HH:00 · X mm"
# ---------------------------------------------------------------------------

class TestAC5Precipitation:
    """AC-5: Regen-Pille ohne 'gesamt, Spitze'.

    Daten: precip 0, 3, 5 mm/h (Regen ab CEST 9/UTC 7, Summe 8 mm).
    SOLL: "Regen ab 09:00 · 8 mm".
    IST: "Regen ab 09:00 · 8 mm gesamt, Spitze HH:00" → FAIL.
    """

    def _pills(self):
        from output.renderers.email.helpers import build_metrics_summary_pills
        dps = [
            _dp(6, precip_1h_mm=0.0),
            _dp(7, precip_1h_mm=3.0),
            _dp(8, precip_1h_mm=5.0),
        ]
        segs = [_make_segment(dps, start_h_utc=6, end_h_utc=9)]
        return build_metrics_summary_pills(segs, ["precipitation"], {}, tz=TZ)

    def test_precipitation_no_gesamt_suffix(self):
        """SOLL: 'gesamt' erscheint nicht mehr im Regen-Format."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert not any("gesamt" in t for t in texts), (
            f"AC-5: 'gesamt' darf nicht mehr erscheinen — got: {texts}"
        )

    def test_precipitation_no_spitze_suffix(self):
        """SOLL: 'Spitze' erscheint nicht mehr im Regen-Format."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert not any("Spitze" in t for t in texts), (
            f"AC-5: 'Spitze' darf nicht mehr erscheinen — got: {texts}"
        )

    def test_precipitation_format_exact(self):
        """SOLL: 'Regen ab 09:00 · 8 mm'."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any("Regen ab 09:00 · 8 mm" in t for t in texts), (
            f"AC-5: Exaktes Format 'Regen ab 09:00 · 8 mm' erwartet — got: {texts}"
        )


# ---------------------------------------------------------------------------
# AC-6: Regenwahrscheinlichkeit — Label "Regen-W." statt "Regenrisiko"
# ---------------------------------------------------------------------------

class TestAC6RainProbability:
    """AC-6: Regenwahrscheinlichkeit-Pille verwendet Label 'Regen-W.'.

    SMS-Schwelle POP ist 20%. Daten: pop_pct 10, 55, 70
    (erste ≥20 um CEST 9/UTC 7, Max 70 um CEST 10/UTC 8).
    SOLL: enthält 'Regen-W.' (nicht 'Regenrisiko').
    IST: "Regenrisiko ab..." → FAIL.
    """

    def _pills(self):
        from output.renderers.email.helpers import build_metrics_summary_pills
        dps = [
            _dp(6, pop_pct=10),
            _dp(7, pop_pct=55),
            _dp(8, pop_pct=70),
        ]
        segs = [_make_segment(dps, start_h_utc=6, end_h_utc=9)]
        return build_metrics_summary_pills(segs, ["rain_probability"], {}, tz=TZ)

    def test_rain_prob_no_regenrisiko_label(self):
        """SOLL: 'Regenrisiko' erscheint nicht mehr."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert not any("Regenrisiko" in t for t in texts), (
            f"AC-6: 'Regenrisiko' darf nicht erscheinen — got: {texts}"
        )

    def test_rain_prob_has_regen_w_label(self):
        """SOLL: enthält 'Regen-W.'."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any("Regen-W." in t for t in texts), (
            f"AC-6: 'Regen-W.' erwartet — got: {texts}"
        )

    def test_rain_prob_format_with_threshold_prefix(self):
        """SOLL: enthält '>20%' (Schwellenwert-Präfix) und 'ab 09:00'."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any(">20%" in t and "ab 09:00" in t for t in texts), (
            f"AC-6: '>20% ab 09:00' erwartet — got: {texts}"
        )


# ---------------------------------------------------------------------------
# AC-7: Bewölkung — Format "X–Y% bewölkt · Max HH:00"
# ---------------------------------------------------------------------------

class TestAC7CloudTotal:
    """AC-7: Bewölkung-Pille zeigt Bereich + 'bewölkt' + Uhrzeit.

    Daten: cloud_total_pct 60, 80, 95 (Max 95 um CEST 10/UTC 8).
    SOLL: "60–95% bewölkt · Max 10:00".
    IST: "Bewölkung 60–95 %" → FAIL.
    """

    def _pills(self):
        from output.renderers.email.helpers import build_metrics_summary_pills
        dps = [
            _dp(6, cloud_total_pct=60),
            _dp(7, cloud_total_pct=80),
            _dp(8, cloud_total_pct=95),
        ]
        segs = [_make_segment(dps, start_h_utc=6, end_h_utc=9)]
        return build_metrics_summary_pills(segs, ["cloud_total"], {}, tz=TZ)

    def test_cloud_no_bewolkung_prefix(self):
        """SOLL: 'Bewölkung'-Label-Präfix erscheint nicht mehr."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert not any(t.startswith("Bewölkung") for t in texts), (
            f"AC-7: 'Bewölkung'-Präfix darf nicht erscheinen — got: {texts}"
        )

    def test_cloud_has_time(self):
        """SOLL: enthält 'Max 10:00' (Uhrzeit des Maximums)."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any("Max 10:00" in t for t in texts), (
            f"AC-7: 'Max 10:00' erwartet — got: {texts}"
        )

    def test_cloud_format_exact(self):
        """SOLL: '60–95% bewölkt · Max 10:00'."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any("60–95% bewölkt · Max 10:00" in t for t in texts), (
            f"AC-7: Exaktes Format '60–95% bewölkt · Max 10:00' erwartet — got: {texts}"
        )


# ---------------------------------------------------------------------------
# AC-8: Sicht gut — "Sicht min X km (HH:00)" statt "gute Sicht"
# ---------------------------------------------------------------------------

class TestAC8VisibilityGood:
    """AC-8: Sicht durchgehend gut → neue Form mit Uhrzeit.

    Sicht durchgehend > 2000m. Min-Sicht 8500m um CEST 8/UTC 6.
    SOLL: enthält 'Sicht min' und 'km' und '(08:00)'.
    IST: 'gute Sicht' → FAIL.
    """

    def _pills(self):
        from output.renderers.email.helpers import build_metrics_summary_pills
        dps = [
            _dp(6, visibility_m=8500),
            _dp(7, visibility_m=9000),
            _dp(8, visibility_m=10000),
        ]
        segs = [_make_segment(dps, start_h_utc=6, end_h_utc=9)]
        return build_metrics_summary_pills(segs, ["visibility"], {}, tz=TZ)

    def test_visibility_no_gute_sicht(self):
        """SOLL: 'gute Sicht' erscheint nicht mehr."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert not any("gute Sicht" in t for t in texts), (
            f"AC-8: 'gute Sicht' darf nicht erscheinen — got: {texts}"
        )

    def test_visibility_has_min_km_and_time(self):
        """SOLL: enthält 'Sicht min' und 'km' und '(08:00)'."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any("Sicht min" in t and "km" in t and "(08:00)" in t for t in texts), (
            f"AC-8: 'Sicht min ... km (08:00)' erwartet — got: {texts}"
        )


# ---------------------------------------------------------------------------
# AC-9: Nullgradgrenze — Label "0°-Linie" + Tausenderpunkt
# ---------------------------------------------------------------------------

class TestAC9FreezingLevel:
    """AC-9: Nullgradgrenze verwendet Label '0°-Linie' und Tausenderpunkt.

    freezing_level_m: 2310, 2450, 2550 (Max 2550 um CEST 10/UTC 8).
    SOLL: enthält '0°-Linie' und '2.310' (Tausenderpunkt).
    IST: "0°-Grenze 2310–2550 m" → FAIL.
    """

    def _pills(self):
        from output.renderers.email.helpers import build_metrics_summary_pills
        dps = [
            _dp(6, freezing_level_m=2310),
            _dp(7, freezing_level_m=2450),
            _dp(8, freezing_level_m=2550),
        ]
        segs = [_make_segment(dps, start_h_utc=6, end_h_utc=9)]
        return build_metrics_summary_pills(segs, ["freezing_level"], {}, tz=TZ)

    def test_freezing_level_no_old_label(self):
        """SOLL: '0°-Grenze' erscheint nicht mehr."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert not any("0°-Grenze" in t for t in texts), (
            f"AC-9: '0°-Grenze' darf nicht erscheinen — got: {texts}"
        )

    def test_freezing_level_new_label(self):
        """SOLL: enthält '0°-Linie'."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any("0°-Linie" in t for t in texts), (
            f"AC-9: '0°-Linie' erwartet — got: {texts}"
        )

    def test_freezing_level_tausenderpunkt(self):
        """SOLL: enthält '2.310' (Tausenderpunkt, nicht '2310')."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any("2.310" in t for t in texts), (
            f"AC-9: Tausenderpunkt '2.310' erwartet — got: {texts}"
        )


# ---------------------------------------------------------------------------
# AC-10: Feuchte gut — "Feuchte X–Y% · Max HH:00" statt "Luft trocken"
# ---------------------------------------------------------------------------

class TestAC10HumidityBelowThreshold:
    """AC-10: Feuchte unter Schwelle zeigt Bereich + Uhrzeit statt 'Luft trocken'.

    SMS-Schwelle Humidity ist 90%. Daten: humidity_pct 55, 65, 72 (Max 72 um CEST 10/UTC 8).
    SOLL: "Feuchte 55–72% · Max 10:00".
    IST: "Luft trocken" → FAIL.
    """

    def _pills(self):
        from output.renderers.email.helpers import build_metrics_summary_pills
        dps = [
            _dp(6, humidity_pct=55),
            _dp(7, humidity_pct=65),
            _dp(8, humidity_pct=72),
        ]
        segs = [_make_segment(dps, start_h_utc=6, end_h_utc=9)]
        return build_metrics_summary_pills(segs, ["humidity"], {}, tz=TZ)

    def test_humidity_no_luft_trocken(self):
        """SOLL: 'Luft trocken' erscheint nicht mehr."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert not any("Luft trocken" in t for t in texts), (
            f"AC-10: 'Luft trocken' darf nicht erscheinen — got: {texts}"
        )

    def test_humidity_format_exact(self):
        """SOLL: 'Feuchte 55–72% · Max 10:00'."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any("Feuchte 55–72% · Max 10:00" in t for t in texts), (
            f"AC-10: Exaktes Format 'Feuchte 55–72% · Max 10:00' erwartet — got: {texts}"
        )


# ---------------------------------------------------------------------------
# AC-11: UV mit Uhrzeit — "UV max X.X (HH:00)"
# ---------------------------------------------------------------------------

class TestAC11UvIndex:
    """AC-11: UV-Pille zeigt Spitzenwert + Uhrzeit.

    uv_index: 0.5, 1.2, 2.4 (Max 2.4 um CEST 10/UTC 8).
    SOLL: enthält 'UV max' und '2.4' und '(10:00)'.
    IST: 'UV bis 2' → FAIL.
    """

    def _pills(self):
        from output.renderers.email.helpers import build_metrics_summary_pills
        dps = [
            _dp(6, uv_index=0.5),
            _dp(7, uv_index=1.2),
            _dp(8, uv_index=2.4),
        ]
        segs = [_make_segment(dps, start_h_utc=6, end_h_utc=9)]
        return build_metrics_summary_pills(segs, ["uv_index"], {}, tz=TZ)

    def test_uv_no_old_format(self):
        """SOLL: 'UV bis' erscheint nicht mehr."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert not any("UV bis" in t for t in texts), (
            f"AC-11: 'UV bis' darf nicht erscheinen — got: {texts}"
        )

    def test_uv_has_max_and_time(self):
        """SOLL: enthält 'UV max' und '2.4' und '(10:00)'."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any("UV max" in t and "2.4" in t and "(10:00)" in t for t in texts), (
            f"AC-11: 'UV max 2.4 (10:00)' erwartet — got: {texts}"
        )


# ---------------------------------------------------------------------------
# AC-12: Taupunkt mit Uhrzeit — "Taupunkt min X°C (HH:00)"
# ---------------------------------------------------------------------------

class TestAC12Dewpoint:
    """AC-12: Taupunkt-Pille zeigt Mindestwert + Uhrzeit.

    dewpoint_c: 8.5, 7.0, 5.8 (Min 5.8 um CEST 10/UTC 8).
    SOLL: enthält 'Taupunkt min' und '5.8' und '(10:00)'.
    IST: "Taupunkt 5–8 °C" (als Bereich ohne Uhrzeit) → FAIL.
    """

    def _pills(self):
        from output.renderers.email.helpers import build_metrics_summary_pills
        dps = [
            _dp(6, dewpoint_c=8.5),
            _dp(7, dewpoint_c=7.0),
            _dp(8, dewpoint_c=5.8),
        ]
        segs = [_make_segment(dps, start_h_utc=6, end_h_utc=9)]
        return build_metrics_summary_pills(segs, ["dewpoint"], {}, tz=TZ)

    def test_dewpoint_no_range_format(self):
        """SOLL: 'Taupunkt 5–8 °C' (alter Bereich ohne Uhrzeit) erscheint nicht."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        # Das alte Format hat " °C" mit Leerzeichen vor der Einheit
        assert not any("Taupunkt" in t and " °C" in t and ":00" not in t for t in texts), (
            f"AC-12: Altes Bereich-Format ohne Uhrzeit darf nicht erscheinen — got: {texts}"
        )

    def test_dewpoint_has_min_and_time(self):
        """SOLL: enthält 'Taupunkt min' und '5.8' und '(10:00)'."""
        pills = self._pills()
        texts = [t for t, _ in pills]
        assert any("Taupunkt min" in t and "5.8" in t and "(10:00)" in t for t in texts), (
            f"AC-12: 'Taupunkt min 5.8°C (10:00)' erwartet — got: {texts}"
        )
