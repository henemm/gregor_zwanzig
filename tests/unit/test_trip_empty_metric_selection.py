"""Leerauswahl heisst leer (Trip) — Issue #1394, Renderer/Versandpfad-Ebene.

Trip-Gegenstueck zu #1366 (Ortsvergleich). Spec:
docs/specs/modules/trip_empty_metric_selection.md
Kontext: docs/context/fix-1394-leere-metrikauswahl.md

Kern-Tests (Test-Politik "Zwei Schichten", CLAUDE.md): kein Netz, keine
Live-Dienste, kein Mail-Versand, kein Mock/patch — echte Renderer-Aufrufe und
echte Datenobjekte. Geprueft wird der gerenderte Output (Produkt), kein
Quelltext.

Der End-to-End-Block (Klasse TestEndToEndVersandpfad) ruft
`TripReportFormatter.format_email()` direkt auf (Python-Objekte, kein
SMTP/IMAP) — das ist der eigentliche Versandpfad-Formatter, nicht der
Transport. Kein echter Mailversand.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.metric_catalog import build_default_display_config
from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, MetricConfig,
    NormalizedTimeseries, Provider, SegmentWeatherData,
    SegmentWeatherSummary, ThunderLevel, TripSegment,
    UnifiedWeatherDisplayConfig,
)

TZ = ZoneInfo("Europe/Berlin")

DEFAULT_SEVEN = (
    "temperature", "wind", "gust", "precipitation",
    "thunder", "freezing_level", "visibility",
)


# ---------------------------------------------------------------------------
# Fixtures (Muster aus tests/tdd/test_issue_790_briefing_simplify.py)
# ---------------------------------------------------------------------------


def _build_segments(thunder=True):
    tl = ThunderLevel.MED if thunder else ThunderLevel.NONE

    def _dp(h, temp, precip, gust, vis):
        return ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=temp, wind10m_kmh=gust * 0.5, gust_kmh=gust,
            precip_1h_mm=precip, pop_pct=int(min(precip * 20, 100)),
            cloud_total_pct=60, thunder_level=tl,
            visibility_m=vis, freezing_level_m=2500,
        )

    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=400.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1200.0),
        start_time=datetime(2026, 7, 11, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=9.3, ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
    )
    rows = [
        _dp(6, 12.0, 0.0, 10.0, 2000), _dp(7, 13.0, 1.0, 20.0, 1500),
        _dp(8, 14.0, 2.0, 30.0, 1200), _dp(9, 14.5, 0.5, 25.0, 1800),
    ]
    ts = NormalizedTimeseries(meta=meta, data=rows)
    agg = SegmentWeatherSummary(
        temp_min_c=10.0, temp_max_c=14.5, temp_avg_c=12.0,
        wind_max_kmh=20.0, gust_max_kmh=30.0,
        precip_sum_mm=3.5, cloud_avg_pct=60, humidity_avg_pct=55,
        thunder_level_max=tl,
    )
    return [SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="demo",
    )]


_SIMPLE_ROWS = [{
    "time": "06:00", "temp": 12.0, "_wind_dir_deg": None, "_is_day": True,
    "_dni_wm2": None, "_sunny_hours": 0.0, "_wmo_code": None,
}]


def _fall_b_dc() -> UnifiedWeatherDisplayConfig:
    """Fall B: bewusste Leerauswahl — Einträge vorhanden, alle enabled=False."""
    metrics = [MetricConfig(metric_id=m, enabled=False) for m in DEFAULT_SEVEN]
    return UnifiedWeatherDisplayConfig(trip_id="fall-b", metrics=metrics)


def _fall_a_dc() -> UnifiedWeatherDisplayConfig:
    """Fall A: Altbestand — Feld fehlt ganz (metrics == [])."""
    dc = build_default_display_config()
    return dataclasses.replace(dc, metrics=[])


def _render_html(segs, *, dc, **kwargs):
    from output.renderers.email.html import render_html
    params = dict(
        segments=segs, seg_tables=[_SIMPLE_ROWS] * len(segs),
        trip_name="GR20 Test", report_type="morning", dc=dc, night_rows=[],
        thunder_forecast=None, changes=None, stage_name=None,
        stage_stats=None, multi_day_trend=None, compact_summary=None,
        tz=TZ, friendly_keys=set(),
    )
    params.update(kwargs)
    return render_html(**params)


def _render_plain(segs, *, dc, **kwargs):
    from output.renderers.email.plain import render_plain
    params = dict(
        segments=segs, seg_tables=[_SIMPLE_ROWS] * len(segs),
        trip_name="GR20 Test", report_type="morning", dc=dc, night_rows=[],
        thunder_forecast=None, changes=None, stage_name=None,
        stage_stats=None, multi_day_trend=None, compact_summary=None,
        tz=TZ, friendly_keys=set(),
    )
    params.update(kwargs)
    return render_plain(**params)


def _render_compact(segs, *, dc, **kwargs):
    from output.renderers.email.compact import render_compact
    params = dict(
        segments=segs, dc=dc, multi_day_trend=None, stability_result=None,
        tz=TZ, report_type="morning", trip_name="GR20 Test", stage_name=None,
        stage_stats=None,
    )
    params.update(kwargs)
    return render_compact(**params)


# ===========================================================================
# AC-1/AC-2/AC-3: Direktaufruf der drei Renderer, Fall B (bewusste
# Leerauswahl) + trip_metrics_altbestand=False → kein Metriken-Ueberblick.
# ===========================================================================


class TestDirektaufrufFallBKeinBlock:

    def test_html_no_metrics_overview_when_conscious_empty(self):
        html = _render_html(
            _build_segments(), dc=_fall_b_dc(), trip_metrics_altbestand=False,
        )
        assert "Metriken-Überblick" not in html, (
            "AC-1: bewusste Leerauswahl darf keinen Metriken-Ueberblick-Block "
            "zeigen (weder Standardsatz noch leere Ueberschrift)."
        )

    def test_plain_no_metrics_overview_when_conscious_empty(self):
        plain = _render_plain(
            _build_segments(), dc=_fall_b_dc(), trip_metrics_altbestand=False,
        )
        assert "Metriken-Überblick" not in plain, (
            "AC-2: Klartext-Teil derselben Mail darf keinen "
            "Metriken-Ueberblick-Block zeigen bei bewusster Leerauswahl."
        )

    def test_compact_no_metrics_overview_when_conscious_empty(self):
        compact = _render_compact(
            _build_segments(), dc=_fall_b_dc(), trip_metrics_altbestand=False,
        )
        assert "Metriken-Ueberblick" not in compact, (
            "AC-3: Kurzformat darf weder Ueberschrift noch Pillen zeigen bei "
            "bewusster Leerauswahl."
        )


# ===========================================================================
# AC-5/AC-6 (Resolver-Ebene, Direktaufruf): Fall A (Altbestand,
# trip_metrics_altbestand=True/Default) → weiterhin Standard-Satz.
# ===========================================================================


class TestDirektaufrufFallARegression:

    def test_html_default_set_when_altbestand(self):
        html = _render_html(
            _build_segments(), dc=_fall_a_dc(), trip_metrics_altbestand=True,
        )
        assert "Metriken-Überblick" in html
        assert "°C" in html, "AC-5: Temperatur-Pille (Default-Satz) fehlt"

    def test_plain_default_set_when_altbestand(self):
        plain = _render_plain(
            _build_segments(), dc=_fall_a_dc(), trip_metrics_altbestand=True,
        )
        assert "Metriken-Überblick" in plain

    def test_compact_default_set_when_altbestand(self):
        """AC-6, echter Bugfix (nicht nur Regressionsschutz): das Kurzformat
        zeigt heute bei Fall A nur eine leere Ueberschrift ohne Pillen-Zeilen
        — nach dem Fix erscheinen die sieben Standardgroessen."""
        compact = _render_compact(
            _build_segments(), dc=_fall_a_dc(), trip_metrics_altbestand=True,
        )
        assert "Metriken-Ueberblick" in compact
        lines = compact.splitlines()
        idx = next(i for i, ln in enumerate(lines) if "Metriken-Ueberblick" in ln)
        # Pillen-Zeilen sind mit "  " eingerueckt und folgen direkt der Ueberschrift.
        pill_lines = []
        for ln in lines[idx + 1:]:
            if not ln.strip():
                break
            pill_lines.append(ln)
        assert len(pill_lines) >= 3, (
            f"AC-6: erwartet mehrere Default-Pillen-Zeilen im Kurzformat, "
            f"gefunden {len(pill_lines)}: {pill_lines!r}"
        )


# ===========================================================================
# End-to-End über den echten Versandpfad (Pflicht laut Spec — beweist den
# Kritischen Befund T0 ist behoben, nicht nur die drei Renderer isoliert).
# ===========================================================================


class TestEndToEndVersandpfad:
    """`TripReportFormatter.format_email()` kollabiert `dc.metrics` für
    report_type in ('morning', 'evening') VOR dem Renderer-Aufruf
    (trip_report.py:113-119) — ein Test, der nur render_html()/render_plain()
    direkt aufruft, beweist den Fix fuer den Versandpfad NICHT (Kritischer
    Befund der Spec)."""

    def _format(self, report_type, dc):
        from output.renderers.trip_report import TripReportFormatter
        return TripReportFormatter().format_email(
            segments=_build_segments(),
            trip_name="GR20 Test",
            report_type=report_type,
            display_config=dc,
            tz=TZ,
        )

    def test_morning_fall_b_no_overview_html_and_plain(self):
        report = self._format("morning", _fall_b_dc())
        assert "Metriken-Überblick" not in report.email_html, (
            "E2E AC-1: bewusste Leerauswahl (Fall B) im echten Morgen-"
            "Versandpfad muss den HTML-Ueberblick-Block entfernen."
        )
        assert "Metriken-Überblick" not in report.email_plain, (
            "E2E AC-2: bewusste Leerauswahl (Fall B) im echten Morgen-"
            "Versandpfad muss den Klartext-Ueberblick-Block entfernen."
        )

    def test_evening_fall_b_no_overview_html_and_plain(self):
        report = self._format("evening", _fall_b_dc())
        assert "Metriken-Überblick" not in report.email_html
        assert "Metriken-Überblick" not in report.email_plain

    def test_morning_fall_a_still_shows_default_set(self):
        """AC-5 E2E: Altbestand-Trip (Feld fehlt ganz) bleibt im echten
        Versandpfad unveraendert — beide Teile zeigen weiterhin die sieben
        Standardgroessen."""
        report = self._format("morning", _fall_a_dc())
        assert "Metriken-Überblick" in report.email_html
        assert "Metriken-Überblick" in report.email_plain
        assert "°C" in report.email_html

    def test_evening_fall_a_still_shows_default_set(self):
        report = self._format("evening", _fall_a_dc())
        assert "Metriken-Überblick" in report.email_html
        assert "Metriken-Überblick" in report.email_plain


# ===========================================================================
# Issue #1552 AC-1/AC-3: der Payload, wie ihn der reparierte Anlege-Flow
# TATSAECHLICH erzeugt (WeatherMetricsTab.buildWeatherConfigMetrics() emittiert
# JEDE Katalog-ID genau einmal, kein leeres Feld, keine Nur-7-Teilmenge) --
# weder Fall A (leere Liste) noch Fall B (nur 7 Eintraege) oben bilden diese
# Form ab. Adversary-Befund F001: AC-1/AC-3 verlangen woertlich ein
# gerendertes Briefing, kein Register-/Ableitungs-/Payload-Assert.
# ===========================================================================


def _create_flow_dc(*, seven_enabled: bool) -> UnifiedWeatherDisplayConfig:
    """Baut dc.metrics so, wie es der Anlege-Flow nach dem Fix persistiert:
    eine vollstaendige Katalogliste (eine MetricConfig je selektierbarer
    Groesse), mit `enabled=True` genau fuer die sieben Standardgroessen
    (AC-1, `seven_enabled=True`) bzw. fuer KEINE Groesse (AC-3, bewusste
    Komplett-Abwahl, `seven_enabled=False`).

    Liest die Vorbelegung ueber den ECHTEN `/api/metrics`-Endpoint
    (`api.routers.config.get_metrics()`), nicht ueber `DEFAULT_TRIP_METRIC_IDS`
    direkt -- das spiegelt exakt den Lesepfad, den `WeatherMetricsTab.svelte`
    (`metricById[id]?.trip_default_enabled`) im Anlege-Modus nutzt (Spec § B).
    Ohne das neue Feld `trip_default_enabled` schlaegt dieser Aufbau mit
    KeyError fehl (RED-Beweis vor dem API-Fix, s. Testbericht)."""
    from api.routers.config import get_metrics

    catalog = get_metrics()
    metrics = [
        MetricConfig(
            metric_id=m["id"],
            enabled=seven_enabled and m["trip_default_enabled"],
        )
        for entries in catalog.values()
        for m in entries
    ]
    return UnifiedWeatherDisplayConfig(trip_id="create-flow", metrics=metrics)


class TestCreateFlowPayloadRendersExactlySevenDefaults:
    """AC-1/AC-3 ueber den echten Versandpfad (TripReportFormatter, wie
    TestEndToEndVersandpfad oben) -- diesmal mit der vollstaendigen
    Katalogliste als dc.metrics, nicht mit den kuenstlichen Fall-A/Fall-B-
    Kurzformen."""

    def _format(self, report_type, dc):
        from output.renderers.trip_report import TripReportFormatter
        return TripReportFormatter().format_email(
            segments=_build_segments(), trip_name="GR20 Test",
            report_type=report_type, display_config=dc, tz=TZ,
        )

    # Issue #1552 Nachbesserung (Adversary-Befund Fix-Loop 1): die Mail hat
    # eine feste Kommando-/Einheiten-Legende ("Einheiten: Temp °C · Wind, Gust
    # km/h ...", "Spalten: ... Gust = Böen ... Visib = Sichtweite ...",
    # Kommando "GEWITTER"), die UNABHAENGIG von den Pillen immer im Text
    # steht. Bloss "°C"/"Wind"/"Böen"/"Gewitter"/"Sicht" waeren dort false-
    # positive gruen -- deshalb die vollen, nur in der Pillen-Zeile
    # vorkommenden Textformen (mit der fixen Fixture deterministisch, s.
    # _build_segments()/oben).
    _PILL_MARKERS = (
        ("°C · Max", "temperature"),
        ("Wind >10 km/h", "wind"),
        ("Böen >20 km/h", "gust"),
        ("Regen ab 09:00", "precipitation"),
        # #1493: Stufenwort in der Pille -- Marker bleibt Pillen-exklusiv.
        ("Gewitter mittel ab 08:00", "thunder"),
        ("0°-Linie 2.500 m", "freezing_level"),
        ("Sicht <2 km", "visibility"),
    )

    def test_ac1_seven_enabled_shows_exactly_the_seven_target_metrics(self):
        report = self._format("morning", _create_flow_dc(seven_enabled=True))
        plain = report.email_plain
        assert "Metriken-Überblick" in plain, (
            "AC-1: der aus buildCreateTripPayload()-aehnlichem Payload "
            "gerenderte Briefing-Teil zeigt keinen Ueberblicksblock."
        )
        for marker, name in self._PILL_MARKERS:
            assert marker in plain, f"AC-1: Pille fuer {name} ({marker!r}) fehlt im Briefing"
        # Gegenprobe "genau diese 7, nicht irgendwelche": rain_probability
        # hat im Fixture ebenfalls Rohdaten (pop_pct), ist aber NICHT in
        # DEFAULT_TRIP_METRIC_IDS -- ihr eigenes Label "Regen-W." darf trotz
        # vorhandener Daten nicht erscheinen, weil enabled=False.
        assert "Regen-W." not in plain, (
            "AC-1: rain_probability (nicht Teil der 7 Standardgroessen) "
            "erscheint trotzdem -- der Payload wird nicht auf die 7 begrenzt."
        )

    def test_ac3_all_disabled_shows_no_overview_block_and_no_default_fallback(self):
        report = self._format("morning", _create_flow_dc(seven_enabled=False))
        plain = report.email_plain
        assert "Metriken-Überblick" not in plain, (
            "AC-3: bewusste Komplett-Abwahl (alle enabled=False in der vollen "
            "Katalogliste) muss den Ueberblicksblock vollstaendig entfernen."
        )
        # Kein stiller Rueckfall auf die sieben Standardgroessen (das waere
        # das #1552-Symptom in neuer Form): keine der sieben Pillen-Textformen
        # darf auftauchen, obwohl dieselben Rohdaten wie oben vorliegen.
        for marker, name in self._PILL_MARKERS:
            assert marker not in plain, (
                f"AC-3: Pille fuer {name} ({marker!r}) erscheint trotz "
                "bewusster Leerauswahl -- stiller Rueckfall auf den Standardsatz"
            )


# ===========================================================================
# AC-4/AC-5: Vortagszeile summarize_day_comparison()
# ===========================================================================


def _big_delta_comparison():
    """Echte, grosse Deltas ueber DayComparisonService (Bug-#800-Muster aus
    tests/tdd/test_issue_790_briefing_simplify.py)."""
    from app.models import GPXPoint, SegmentWeatherSummary, TripSegment
    from services.day_comparison import DayComparisonService

    def _seg(**agg):
        start = datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
        seg = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=1500.0),
            end_point=GPXPoint(lat=42.2, lon=9.2, elevation_m=1600.0),
            start_time=start, end_time=end,
            duration_hours=4.0, distance_km=12.0, ascent_m=600.0, descent_m=300.0,
        )
        meta = ForecastMeta(provider=Provider.OPENMETEO, model="demo", grid_res_km=1.0)
        ts = NormalizedTimeseries(meta=meta, data=[])
        return SegmentWeatherData(
            segment=seg, timeseries=ts, aggregated=SegmentWeatherSummary(**agg),
            fetched_at=datetime.now(timezone.utc), provider="demo",
        )

    today = [_seg(temp_min_c=14.0, temp_max_c=28.0, wind_max_kmh=20.0, precip_sum_mm=0.0)]
    yday = [_seg(temp_min_c=4.0, temp_max_c=15.0, wind_max_kmh=20.0, precip_sum_mm=18.0)]
    return DayComparisonService().compare(today, yday)


class TestVortagszeileAC4AC5:

    def test_conscious_empty_selection_returns_no_line(self):
        """AC-4: bewusst leere Auswahl trotz realer grosser Deltas → keine
        Vortagszeile — weder generische 'aehnliches Wetter'-Aussage noch
        eine auf abgewaehlte Groessen gestuetzte Aussage."""
        from services.day_comparison import summarize_day_comparison
        comp = _big_delta_comparison()
        line = summarize_day_comparison(comp, selected_metrics=[])
        assert line == "", (
            f"AC-4: selected_metrics=[] muss '' liefern (nicht Legacy-Text), "
            f"got: {line!r}"
        )

    def test_none_still_uses_legacy_text(self):
        """AC-5: selected_metrics=None (Altbestand-Signal des Aufrufers)
        bleibt unveraendert der bisherige Legacy-Pfad."""
        from services.day_comparison import summarize_day_comparison
        comp = _big_delta_comparison()
        line = summarize_day_comparison(comp, selected_metrics=None)
        assert line != "", "AC-5: None darf NICHT wie [] behandelt werden"
        assert "Vergleich zum Vortag" in line


# ===========================================================================
# AC-7: Loader — kanal-spezifische Leerauswahl je Kanal wird übernommen.
# ===========================================================================


class TestLoaderKanalspezifischeLeerauswahlAC7:

    def test_all_channel_lists_empty_kept_as_dict_not_none(self):
        """AC-7: alle drei Kanal-Listen bewusst leer → per_channel_layouts
        ist ein Dict mit leeren Listen je Kanal, NICHT None (globaler
        Rueckfall). Widerspricht bewusst der ALTEN Erwartung in
        test_issue_429_channel_layouts.py::
        test_ac1_all_empty_channel_layouts_treated_as_none — diese muss in
        der Implementierungsphase mitgezogen werden (siehe Bericht)."""
        from app.loader import _parse_display_config

        data = {
            "trip_id": "fall-b-per-channel",
            "metrics": [{"metric_id": "temperature", "enabled": True}],
            "channel_layouts": {"email": [], "telegram": [], "sms": []},
            "updated_at": "2026-07-31T10:00:00",
        }
        dc = _parse_display_config(data)
        assert dc.per_channel_layouts is not None, (
            "AC-7: eine bewusst geleerte Kanal-Konfiguration darf nicht auf "
            "den globalen Fallback (None) zurueckfallen."
        )
        assert dc.per_channel_layouts == {"email": [], "telegram": [], "sms": []}


# ===========================================================================
# AC-8: Telegram/SMS — Regressionsnachweis (bereits korrektes Verhalten).
# Dieser Test darf von Anfang an GRUEN sein — er ist KEIN RED-Test.
# ===========================================================================


class TestTelegramSmsRegressionAC8:
    """Regressionsnachweis: Telegram und SMS respektieren die vollstaendige
    Leerauswahl bereits heute korrekt (get_metrics_for_channel() setzt den
    Vertrag um — siehe Spec-Abgrenzung). Kein RED-Test."""

    def test_sms_and_telegram_omit_deselected_thunder_token(self):
        from output.renderers.trip_report import TripReportFormatter
        report = TripReportFormatter().format_email(
            segments=_build_segments(thunder=True),
            trip_name="GR20 Test",
            report_type="morning",
            display_config=_fall_b_dc(),
            tz=TZ,
        )
        assert "TH:" not in (report.sms_text or ""), (
            f"AC-8: SMS darf bei abgewaehltem Gewitter kein TH:-Token zeigen: "
            f"{report.sms_text!r}"
        )
        joined_bubbles = "\n".join(report.telegram_bubbles or [])
        assert "TH:" not in joined_bubbles, (
            "AC-8: Telegram-Bubbles duerfen bei abgewaehltem Gewitter kein "
            "TH:-Token zeigen."
        )
