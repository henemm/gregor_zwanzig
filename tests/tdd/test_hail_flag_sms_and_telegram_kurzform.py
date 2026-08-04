"""TDD RED — Issue #1475 Scheibe S5a (Epic #1419), AC-6: SMS-Trip-Briefing
zeigt ein zusaetzliches Hagel-Kennzeichen NUR fuer die Etappe mit
hail_flag=True, bleibt <=160 Zeichen, keine sichtbare Aenderung bei
None/False. Telegram-Kurzform (Kurzuebersicht-Bubble) wird als
A/B-Pflichtpruefung gegen dieselben zwei Fixtures mitgeprueft (Referenz:
`reference_telegram_kurzform_ist_der_sms_pruefweg.md` — Telegram-Kurzform
und SMS teilen denselben Pruefweg).

SPEC: docs/specs/modules/feat_1475_s5a_hagel_wmo_flag.md, Implementation
Details Abschnitt 6 (Arbeitshypothese: Suffix am bestehenden FORECAST_TH-
Token — HIER bewusst NICHT auf einen konkreten Glyphen/Kuerzel festgelegt,
weil die Spec das selbst als noch abzugleichende Arbeitshypothese fuehrt,
Known Limitation 4). Dieser Test prueft deshalb einen SCHWARZEN-KASTEN-
Unterschied (True-Rendering != None-Rendering), nicht ein bestimmtes Zeichen.

RED-Ursache (heute): `SegmentWeatherSummary`/`ForecastDataPoint` kennen kein
Feld `hail_flag` -> TypeError bei Fixture-Konstruktion.

Keine Mocks/patch()/MagicMock — echte SegmentWeatherData, echter
SMSTripFormatter, echte TripReportFormatter-Pipeline (Telegram-Bubbles).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.models import (  # noqa: E402
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


def _make_segment(hail_flag) -> SegmentWeatherData:
    now = datetime(2026, 8, 4, 6, 0, tzinfo=timezone.utc)
    points = [ForecastDataPoint(
        ts=datetime(2026, 8, 4, 6 + h, 0, tzinfo=timezone.utc),
        t2m_c=15.0 + h, wind10m_kmh=10.0 + h, gust_kmh=22.0 + h,
        pop_pct=40, precip_1h_mm=0.4, cloud_total_pct=55,
        thunder_level=ThunderLevel.HIGH, hail_flag=hail_flag if h == 4 else None,
    ) for h in range(8)]
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2", run=now,
        grid_res_km=2.0, interp="nearest",
    )
    ts = NormalizedTimeseries(meta=meta, data=points)
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=2000),
        start_time=now, end_time=datetime(2026, 8, 4, 14, 0, tzinfo=timezone.utc),
        duration_hours=8.0, distance_km=12.0, ascent_m=500, descent_m=0,
    )
    return SegmentWeatherData(
        segment=segment, timeseries=ts,
        aggregated=SegmentWeatherSummary(
            thunder_level_max=ThunderLevel.HIGH, hail_flag=hail_flag,
        ),
        fetched_at=now, provider="openmeteo",
    )


def _render_sms(hail_flag) -> str:
    from output.renderers.sms_trip import SMSTripFormatter

    return SMSTripFormatter().format_sms(
        [_make_segment(hail_flag)], stage_name="Etappe1",
        report_type="evening", tz=_TZ, max_length=160,
    )


# =============================================================================
# AC-6 — SMS: zusaetzliches Kennzeichen NUR bei True, <=160 Zeichen
# =============================================================================

def test_ac6_sms_zeigt_unterschied_nur_bei_true_etappe():
    sms_true = _render_sms(True)
    sms_unbekannt = _render_sms(None)

    assert len(sms_true) <= 160, f"SMS True-Variante ueberschreitet 160 Zeichen: {sms_true!r}"
    assert len(sms_unbekannt) <= 160, f"SMS None-Variante ueberschreitet 160 Zeichen: {sms_unbekannt!r}"
    assert sms_true != sms_unbekannt, (
        "SMS-Rendering fuer hail_flag=True und hail_flag=None (unbekannt) "
        f"sind identisch ({sms_true!r}) -- kein zusaetzliches "
        "Hagel-Kennzeichen wird sichtbar"
    )


def test_ac6_sms_none_bleibt_stabil_gegen_wiederholten_bau():
    """Gegenprobe: zwei unabhaengige Renderings derselben None-Fixture
    liefern identischen Text -- der Unterschied oben stammt tatsaechlich vom
    hail_flag-Wert, nicht von Nichtdeterminismus im Renderer."""
    a = _render_sms(None)
    b = _render_sms(None)
    assert a == b, f"Zwei Renderings derselben None-Fixture unterscheiden sich: {a!r} vs {b!r}"


# =============================================================================
# AC-6 — Telegram-Kurzform (Bubbles) als A/B-Pflichtpruefung
# =============================================================================

def _render_telegram_bubbles(hail_flag) -> str:
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    from output.renderers.trip_report import TripReportFormatter

    metrics = [
        MetricConfig(metric_id=mid, enabled=True, bucket="primary", order=i)
        for i, mid in enumerate(["temperature", "wind", "gust", "thunder"])
    ]
    dc = UnifiedWeatherDisplayConfig(
        trip_id="hail-1475", metrics=metrics, updated_at=datetime.now(timezone.utc),
    )
    report = TripReportFormatter().format_email(
        segments=[_make_segment(hail_flag)], trip_name="Hagel-Test",
        report_type="evening", display_config=dc, stage_name="Etappe1", tz=_TZ,
    )
    return "\n".join(report.telegram_bubbles)


def test_ac6_telegram_kurzform_zeigt_denselben_unterschied_wie_sms():
    """A/B-Pflichtpruefung: die Telegram-Kurzuebersicht (Bubbles) muss
    denselben True/None-Unterschied zeigen wie die SMS -- Telegram-Kurzform
    ist der SMS-Pruefweg, kein zweiter, unabhaengiger Textbaustein."""
    telegram_true = _render_telegram_bubbles(True)
    telegram_unbekannt = _render_telegram_bubbles(None)

    assert telegram_true != telegram_unbekannt, (
        "Telegram-Kurzuebersicht zeigt keinen Unterschied zwischen "
        "hail_flag=True und hail_flag=None -- der Hagel-Hinweis kommt in "
        "der Telegram-Kurzform nicht an"
    )
