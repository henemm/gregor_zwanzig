"""TDD RED — Issue #1475 Nachbesserung (Epic #1419), AC-7(d)/AC-7(e): der
Ortsvergleich hat ZWEI eigene Ausgabekanaele (SMS, Telegram) -- nicht nur
die HTML-/Klartext-/Ausblick-Fassung -- die in der ersten Recherche-Runde
komplett uebersehen wurden (Spec-Korrektur 2026-08-05, Purpose-Abschnitt).

SPEC: docs/specs/modules/feat_1475_hagel_luecken_nachbesserung.md, AC-7(d)/(e),
Implementation Details Punkt 5b (die beiden zuletzt gefundenen
Aufrufstellen ``_sms_metric_cell``/``_plain_metric_cell``).

RED-Ursache (heute):
  - ``_sms_metric_cell()`` (comparison.py) ruft ``fmt(value)`` (= ``_fmt_thunder``
    fuer die Metrik ``thunder_max``) OHNE den Hagel-Wert des jeweiligen
    ``LocationResult`` auf -- der Hagel-Hinweis fehlt daher IMMER im
    Ortsvergleich-SMS-Kanal (``render_compare_sms``), unabhaengig vom Ort.
  - ``_plain_metric_cell()`` (comparison.py) hat dieselbe Luecke fuer den
    Ortsvergleich-Telegram-Kanal (``render_compare_telegram``).

Keine Mocks/patch()/MagicMock — echte ``ComparisonResult``/``LocationResult``/
``ForecastDataPoint``-DTOs, echte Renderer.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.models import ForecastDataPoint, ThunderLevel  # noqa: E402
from app.user import ComparisonResult, LocationResult, SavedLocation  # noqa: E402
from output.renderers.channel_layout import CHANNEL_LIMITS  # noqa: E402

_HAGEL_HINWEIS = "Hagel: ja"


def _hourly(*, hail_flag) -> list[ForecastDataPoint]:
    return [ForecastDataPoint(
        ts=datetime(2026, 8, 6, h, 0, tzinfo=timezone.utc), t2m_c=20.0,
        thunder_level=ThunderLevel.HIGH, hail_flag=hail_flag if h == 14 else None,
    ) for h in range(12, 16)]


def _result_ein_ort_true_ein_ort_none() -> ComparisonResult:
    loc_true = LocationResult(
        location=SavedLocation(id="hagel-ort", name="Hagelort", lat=42.0, lon=9.0, elevation_m=1200),
        score=50, hourly_data=_hourly(hail_flag=True),
    )
    loc_none = LocationResult(
        location=SavedLocation(id="ruhig-ort", name="Ruhigort", lat=43.0, lon=6.0, elevation_m=500),
        score=50, hourly_data=_hourly(hail_flag=None),
    )
    return ComparisonResult(
        locations=[loc_true, loc_none], time_window=(12, 16),
        target_date=date(2026, 8, 6), created_at=datetime(2026, 8, 5, 18, 0),
    )


# =============================================================================
# AC-7(d) — eigener Ortsvergleich-SMS-Kanal (render_compare_sms/_sms_metric_cell)
# =============================================================================

def test_ac7d_compare_sms_zeigt_hagel_hinweis_nur_beim_true_ort():
    from output.renderers.comparison import render_compare_sms

    result = _result_ein_ort_true_ein_ort_none()
    sms = render_compare_sms(result, enabled_metrics=["thunder_max"])

    vor_ruhigort, *rest = sms.split("Ruhigort")
    assert _HAGEL_HINWEIS in vor_ruhigort, (
        f"Der Ortsvergleich-SMS-Kanal muss beim Ort mit hail_flag=True den "
        f"Hinweis '{_HAGEL_HINWEIS}' zeigen (Textabschnitt vor 'Ruhigort'). "
        f"SMS: {sms!r}"
    )
    if rest:
        assert _HAGEL_HINWEIS not in rest[0], (
            f"Der Ort mit hail_flag=None darf KEINEN Hagel-Zusatz zeigen. "
            f"Abschnitt: {rest[0]!r}"
        )


def test_ac7d_compare_sms_haelt_zeichenbudget_und_stuerzt_nicht_ab():
    """AC-7 Zusatz: das bestehende Zeichenbudget/GSM-7-Verhalten (#1362)
    bleibt intakt -- der Hagel-Zusatz zaehlt regulaer gegen das Budget, kein
    Crash, keine Ueberschreitung von CHANNEL_LIMITS["sms"]["max_chars"]."""
    from output.renderers.comparison import render_compare_sms

    result = _result_ein_ort_true_ein_ort_none()
    sms = render_compare_sms(result, enabled_metrics=["thunder_max"])

    max_chars = CHANNEL_LIMITS["sms"]["max_chars"]
    assert len(sms) <= max_chars, (
        f"render_compare_sms() ueberschreitet das SMS-Zeichenbudget "
        f"({len(sms)} > {max_chars}): {sms!r}"
    )


# =============================================================================
# AC-7(e) — eigener Ortsvergleich-Telegram-Kanal
# (render_compare_telegram/_plain_metric_cell)
# =============================================================================

def test_ac7e_compare_telegram_zeigt_hagel_hinweis_nur_beim_true_ort():
    from output.renderers.comparison import render_compare_telegram

    result = _result_ein_ort_true_ein_ort_none()
    telegram = render_compare_telegram(result, enabled_metrics=["thunder_max"])

    vor_ruhigort, *rest = telegram.split("Ruhigort")
    assert _HAGEL_HINWEIS in vor_ruhigort, (
        f"Der Ortsvergleich-Telegram-Kanal muss beim Ort mit hail_flag=True "
        f"den Hinweis '{_HAGEL_HINWEIS}' zeigen (Textabschnitt vor "
        f"'Ruhigort'). Telegram: {telegram!r}"
    )
    if rest:
        assert _HAGEL_HINWEIS not in rest[0], (
            f"Der Ort mit hail_flag=None darf KEINEN Hagel-Zusatz zeigen. "
            f"Abschnitt: {rest[0]!r}"
        )


def test_ac7e_compare_telegram_rendert_ohne_absturz():
    """Kein TypeError/Crash durch den zusaetzlichen Hagel-Parameter an
    ``_plain_metric_cell()`` -- reine Rauch-Pruefung neben dem Inhalts-Test
    oben."""
    from output.renderers.comparison import render_compare_telegram

    result = _result_ein_ort_true_ein_ort_none()
    telegram = render_compare_telegram(result, enabled_metrics=["thunder_max"])

    assert "Hagelort" in telegram and "Ruhigort" in telegram, (
        f"Beide Orte muessen im gerenderten Telegram-Text erscheinen: "
        f"{telegram!r}"
    )
