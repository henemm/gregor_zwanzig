"""#2209 — Trip-Mail zeigt Spalte "TmpMin" als Dublette zu "Temp" (RED).

SPEC: docs/specs/bugfix/fix_2209_tmpmin_dublette.md (AC-1, AC-2, AC-4, AC-5).

Pruefort = Wirkort: alle Tests laufen gegen den ECHTEN Produktivpfad
``TripReportFormatter`` (nicht ``email/helpers.dp_to_row``, der den Guard schon
hat und bei dem frueher die Tests fehlgezielt hatten).
"""
from __future__ import annotations

import re

import pytest

from app.metric_catalog import build_default_display_config, get_metric
from app.models import (
    MetricConfig,
    UnifiedWeatherDisplayConfig,
    _SELECTABLE_GATE_EXEMPT,
)
from output.renderers.trip_report import TripReportFormatter
from tests.tdd import _min_temp_felt_fixtures as F
from tests.tdd.test_channel_metric_matrix import _matrix_segment


def _report(dc: UnifiedWeatherDisplayConfig):
    return TripReportFormatter().format_email(
        [_matrix_segment()], trip_name="Issue2209", report_type="evening",
        night_weather=F.night_weather(), display_config=dc,
        stage_name=F.STAGE_NAME, tz=F.TZ,
    )


def _fmt() -> TripReportFormatter:
    f = TripReportFormatter()
    f._tz = F.TZ
    return f


def _dp_and_night_dps():
    seg = _matrix_segment()
    dps = list(seg.timeseries.data)
    return dps[0], dps


# --- AC-1: Spalte "TmpMin" fehlt in HTML und Plain, "Temp" bleibt ----------


def test_ac1_html_hat_keine_tmpmin_spalte_aber_temp():
    report = _report(build_default_display_config())
    heads = re.findall(r"<thead>(.*?)</thead>", report.email_html, re.S)
    assert heads, "keine Tabellenkopfzeile gerendert"
    labels = [
        re.sub(r"<[^>]+>", "", th).strip()
        for h in heads
        for th in re.findall(r"<th[^>]*>.*?</th>", h, re.S)
    ]
    assert "Temp" in labels, f"Spalte 'Temp' fehlt: {labels}"
    assert "TmpMin" not in labels, (
        f"AC-1: Dublette 'TmpMin' steht noch in einer Kopfzeile "
        f"(Stundentabelle/Nacht-Block): {labels}"
    )


def test_ac1_plain_hat_keine_tmpmin_spalte_aber_temp():
    report = _report(build_default_display_config())
    assert "Temp" in report.email_plain
    assert "TmpMin" not in report.email_plain, (
        "AC-1: Plain-Tabelle fuehrt noch die Dublette 'TmpMin'"
    )


# --- AC-2: Zeilenbau des Produktivpfads ignoriert nicht waehlbare Metriken --


@pytest.mark.parametrize("metric_id", ["temperature_cold", "confidence", "cape"])
def test_ac2_dp_to_row_ignoriert_nicht_waehlbare_metrik(metric_id):
    metric = get_metric(metric_id)
    assert metric.selectable is False  # Vorbedingung
    dp, _ = _dp_and_night_dps()
    dc = UnifiedWeatherDisplayConfig(
        trip_id="t", metrics=[
            MetricConfig(metric_id="temperature", enabled=True),
            MetricConfig(metric_id=metric_id, enabled=True),
        ],
    )
    row = _fmt()._dp_to_row(dp, dc)
    assert metric.col_key not in row, (
        f"AC-2: _dp_to_row traegt col_key {metric.col_key!r} einer nicht "
        f"waehlbaren Metrik: {sorted(row)}"
    )
    assert "temp" in row or get_metric("temperature").col_key in row


@pytest.mark.parametrize("metric_id", ["temperature_cold", "confidence", "cape"])
def test_ac2_aggregate_night_block_ignoriert_nicht_waehlbare_metrik(metric_id):
    metric = get_metric(metric_id)
    _, dps = _dp_and_night_dps()
    dc = UnifiedWeatherDisplayConfig(
        trip_id="t", metrics=[
            MetricConfig(metric_id="temperature", enabled=True),
            MetricConfig(metric_id=metric_id, enabled=True),
        ],
    )
    row = _fmt()._aggregate_night_block(dps[:2], dc)
    assert metric.col_key not in row, (
        f"AC-2: _aggregate_night_block traegt col_key {metric.col_key!r} "
        f"einer nicht waehlbaren Metrik: {sorted(row)}"
    )


# --- AC-4: Legende ohne "Tiefsttemperatur-Alarm"/"TmpMin" -------------------


def test_ac4_legende_ohne_tiefsttemperatur_alarm():
    report = _report(build_default_display_config())
    for name, text in (("HTML", report.email_html), ("Plain", report.email_plain)):
        assert "Tiefsttemperatur-Alarm" not in text, (
            f"AC-4: Legende ({name}) fuehrt noch 'Tiefsttemperatur-Alarm'"
        )
        assert "TmpMin" not in text, f"AC-4: {name} verweist noch auf 'TmpMin'"


# --- AC-5: Ausnahmeliste erledigt, kein Kanal verliert Inhalt ---------------


def test_ac5_selectable_gate_exempt_ist_leer():
    assert _SELECTABLE_GATE_EXEMPT == frozenset(), (
        f"AC-5: Ausnahmeliste muss nach dem Fix leer sein: {_SELECTABLE_GATE_EXEMPT}"
    )


@pytest.mark.parametrize("channel", ["email", "telegram", "sms", "premium_sms"])
def test_ac5_kanal_liefert_keine_temperature_cold(channel):
    dc = build_default_display_config()
    ids = [m.metric_id for m in dc.get_metrics_for_channel(channel, "evening")]
    assert "temperature_cold" not in ids, (
        f"AC-5: Kanal {channel} fuehrt noch temperature_cold: {ids}"
    )
    assert "temperature" in ids or channel in ("sms", "premium_sms"), (
        f"AC-5: Kanal {channel} verliert die Temperatur: {ids}"
    )
