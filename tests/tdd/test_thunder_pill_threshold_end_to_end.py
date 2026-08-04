"""TDD -- Adversary-Befund F001/F003 (Nachbesserung zu Issue #1474b, PO-Freigabe
2026-08-04).

SPEC: docs/specs/modules/fix_1474b_gewitterschwelle_cockpit.md

Der Adversary belegte: ersetzt man in ``email/html.py``/``plain.py``/
``compact.py`` den Aufbau von ``sms_mention_thresholds`` durch ein IMMER
LEERES Dict, bleiben alle Bestandstests gruen -- keiner faehrt einen der
drei echten Renderer-Einstiege (``render_html``/``render_plain``/
``render_compact``) DURCHGEHEND mit einem konfigurierten
``MetricConfig("thunder").sms_threshold`` und prueft den erzeugten
Pillen-Text. Die bestehenden Tests (``test_thunder_mention_threshold_shared.py``,
``test_thunder_mail_prosa_low_binding.py``) rufen ausschliesslich die interne
Helferfunktion ``_pill_for_metric()`` direkt auf und uebergeben die Schwelle
von Hand -- sie beweisen nicht, dass ``render_plain()`` sie aus
``dc.metrics`` HERAUSLIEST und weiterreicht.

F003 (Runde 3/4): der erste Fix deckte NUR ``render_plain()`` ab --
``render_html()`` und ``render_compact()`` blieben strukturell identisch
verdrahtet, aber ungeprueft (Mutation an genau dieser Stelle blieb
unentdeckt). Dieser Test parametrisiert deshalb ueber alle DREI echten
Renderer-Einstiege, damit ein kuenftiger vierter Renderer nicht wieder
vergessen wird -- fachlich derselbe Nachweis, aber je Ausgabeform in der
passenden Form geprueft (HTML-Markup vs. Klartext vs. Kompaktform bleiben
unterschiedliche Zeichenketten, der Wortlaut "Gewitter ab" bleibt aber in
allen drei Formen unveraendert, da ``pill_html()`` (html.escape) und
``_ascii()`` (compact) keinen der beiden Woerter veraendern).

Keine Mocks -- echte ``ForecastDataPoint``-Stundenreihe, echte
``UnifiedWeatherDisplayConfig``, echte ``render_html``/``render_plain``/
``render_compact``-Aufrufe.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.metric_catalog import build_default_display_config
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)

_TZ = ZoneInfo("Europe/Berlin")
_MED_HOUR_UTC = 12  # 14:00 lokal (CEST, UTC+2) -- innerhalb des Tagesfensters 04-19


def _dp(hour_utc: int, thunder: ThunderLevel) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 8, 3, hour_utc, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=5.0, gust_kmh=10.0, precip_1h_mm=0.0,
        cloud_total_pct=50, thunder_level=thunder, humidity_pct=55,
    )


def _segment_reaching_med() -> SegmentWeatherData:
    """Ein-Segment-Etappe mit voller 24h-Stundenreihe, die genau eine
    Stunde ThunderLevel.MED erreicht (nie HIGH) -- Ordinal 2."""
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=400.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=900.0),
        start_time=datetime(2026, 8, 3, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 3, 14, 0, tzinfo=timezone.utc),
        duration_hours=8.0, distance_km=12.0, ascent_m=500.0, descent_m=0.0,
    )
    data = [
        _dp(h, ThunderLevel.MED if h == _MED_HOUR_UTC else ThunderLevel.NONE)
        for h in range(0, 24)
    ]
    ts = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
        data=data,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0, temp_max_c=20.0, wind_max_kmh=10.0,
            gust_max_kmh=15.0, precip_sum_mm=0.0,
            thunder_level_max=ThunderLevel.MED,
        ),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _dc_with_thunder_threshold(threshold):
    """Vollstaendige UnifiedWeatherDisplayConfig (alle Metriken wie im
    Editor), nur die Gewitter-Erwaehnungsschwelle wird gesetzt -- genau der
    Weg, den ein echter Trip nimmt (MetricConfig.sms_threshold)."""
    dc = build_default_display_config()
    metrics = [
        dataclasses.replace(mc, sms_threshold=threshold)
        if mc.metric_id == "thunder" else mc
        for mc in dc.metrics
    ]
    return dataclasses.replace(dc, metrics=metrics)


def _render_html(dc) -> str:
    from output.renderers.email.html import render_html

    return render_html(
        segments=[_segment_reaching_med()],
        seg_tables=[[]],
        trip_name="Test-Trip",
        report_type="evening",
        dc=dc,
        night_rows=[],
        night_weather=None,
        changes=None,
        stage_name="Test-Etappe",
        stage_stats=None,
        multi_day_trend=None,
        compact_summary=None,
        tz=_TZ,
        friendly_keys=set(),
    )


def _render_plain(dc) -> str:
    from output.renderers.email.plain import render_plain

    return render_plain(
        segments=[_segment_reaching_med()],
        seg_tables=[[]],
        trip_name="Test-Trip",
        report_type="evening",
        dc=dc,
        night_rows=[],
        night_weather=None,
        changes=None,
        stage_name="Test-Etappe",
        stage_stats=None,
        multi_day_trend=None,
        compact_summary=None,
        tz=_TZ,
        friendly_keys=set(),
    )


def _render_compact(dc) -> str:
    from output.renderers.email.compact import render_compact

    return render_compact(
        segments=[_segment_reaching_med()],
        dc=dc,
        multi_day_trend=None,
        stability_result=None,
        tz=_TZ,
        report_type="evening",
        trip_name="Test-Trip",
        stage_name="Test-Etappe",
        stage_stats=None,
    )


# Issue #1474b Adversary F003: alle DREI echten Renderer-Einstiege -- ein
# kuenftiger vierter Renderer muesste hier ergaenzt werden, sonst faellt er
# durch dasselbe Loch wie html.py/compact.py in Runde 3.
_RENDER_FUNCS = {
    "html": _render_html,
    "plain": _render_plain,
    "compact": _render_compact,
}


@pytest.mark.parametrize("renderer_name", ["html", "plain", "compact"])
def test_configured_threshold_above_med_suppresses_gewitter_ab_sentence(renderer_name):
    """F001/F003: ein Trip mit eigener Gewitter-Erwaehnungsschwelle 3.0
    ('hoch', oberhalb von MED) darf den Satz 'Gewitter ab' in KEINEM der drei
    Renderer-Einstiege zeigen, obwohl die Stundenreihe MED erreicht --
    render_html()/render_plain()/render_compact() muessen die Schwelle aus
    dc.metrics tatsaechlich lesen, nicht nur intern verdrahtet lassen."""
    dc = _dc_with_thunder_threshold(3.0)
    output = _RENDER_FUNCS[renderer_name](dc)
    assert "Gewitter ab" not in output, (
        f"F001/F003 ({renderer_name}): mit eingestellter Schwelle 3.0 "
        "('hoch') darf der Renderer bei einer Stundenreihe, die nur MED "
        f"erreicht (unter der Schwelle), den Satz 'Gewitter ab' NICHT "
        f"zeigen.\n{renderer_name}:\n{output}"
    )


@pytest.mark.parametrize("renderer_name", ["html", "plain", "compact"])
def test_unconfigured_threshold_still_shows_gewitter_ab_sentence(renderer_name):
    """Gegenprobe (derselbe Trip OHNE eigene Einstellung): der Standardwert
    (1.0, 'ab leicht') liegt unter MED -- der Satz MUSS in allen drei
    Renderern erscheinen. Beweist, dass die Unterdrueckung oben tatsaechlich
    an der eingestellten Schwelle haengt, nicht an einem strukturellen
    Defekt, der den Satz immer unterdrueckt."""
    dc = _dc_with_thunder_threshold(None)
    output = _RENDER_FUNCS[renderer_name](dc)
    assert "Gewitter ab" in output, (
        f"Gegenprobe ({renderer_name}): ohne eigene Schwellen-Einstellung "
        "(Standard 1.0, 'ab leicht') muss der Renderer den Satz "
        f"'Gewitter ab' bei einer Stundenreihe zeigen, die MED erreicht.\n"
        f"{renderer_name}:\n{output}"
    )
