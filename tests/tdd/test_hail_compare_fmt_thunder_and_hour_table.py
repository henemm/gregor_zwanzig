"""TDD RED — Issue #1475 Nachbesserung (Epic #1419), AC-7/AC-8: Ortsvergleich
-- alle vier `_fmt_thunder()`-Aufrufstellen (HTML-Uebersicht, Klartext,
Mehrtages-Ausblick) zeigen den Hagel-Hinweis NUR beim betroffenen Ort, und
die Compare-Stundentabelle zeigt ihn als TEXT-Anhang (nicht als Doppelring --
geklaerte Designfrage, Spec Punkt 5c).

SPEC: docs/specs/modules/feat_1475_hagel_luecken_nachbesserung.md, AC-7/AC-8,
Implementation Details Punkt 5.

RED-Ursache (heute):
  - `_fmt_thunder(v)` kennt keinen `hail`-Parameter -- kein Hagel-Hinweis in
    Uebersicht/Klartext/Ausblick, unabhaengig vom Ort.
  - `_render_hour_row()`/`_render_hour_table()` reichen `dp.hail_flag` nicht
    an die Gewitter-Zelle durch.
  - `format_outlook_value()` (Mehrtages-Ausblick, `compare_outlook_metric_
    ids.py:124,130`) kennt keinen Hagel-Parameter.

Keine Mocks/patch()/MagicMock — echte `ComparisonResult`/`LocationResult`/
`ForecastDataPoint`-DTOs, echte Renderer.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.models import ForecastDataPoint, ThunderLevel  # noqa: E402
from app.user import ComparisonResult, LocationResult, SavedLocation  # noqa: E402

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
# AC-7(a) — HTML-Uebersichtstabelle: nur der True-Ort zeigt den Hinweis
# =============================================================================

def test_ac7a_html_uebersicht_zeigt_hagel_hinweis_nur_beim_true_ort():
    from output.renderers.email.compare_html import render_compare_html

    result = _result_ein_ort_true_ein_ort_none()
    html = render_compare_html(result, enabled_metrics=["thunder_max"])

    assert _HAGEL_HINWEIS in html, (
        f"Die HTML-Uebersichtstabelle muss beim Ort mit hail_flag=True den "
        f"Hinweis '{_HAGEL_HINWEIS}' zeigen. Ausschnitt: {html[:2000]!r}"
    )


def test_ac7a_html_uebersicht_regressionstest_ein_argument_alter_stil():
    """AC-7 Gegenprobe: bestehende Aufrufer, die `_fmt_thunder()` mit NUR
    einem Argument aufrufen (alter Stil), duerfen NICHT brechen (kein
    TypeError) und zeigen KEINEN Hagel-Zusatz (Default-Verhalten
    zeichengleich zum Stand vor dieser Spec)."""
    from output.renderers.email.compare_html import _fmt_thunder

    result = _fmt_thunder(ThunderLevel.HIGH)
    assert result == "hoch", (
        f"_fmt_thunder(ThunderLevel.HIGH) mit einem Argument (Alt-Aufrufer) "
        f"muss weiterhin exakt 'hoch' liefern, kein Hagel-Fragment, bekam: "
        f"{result!r}"
    )


# =============================================================================
# AC-7(b) — Klartext-Vergleichszeile (comparison.py)
# =============================================================================

def test_ac7b_klartext_vergleich_zeigt_hagel_hinweis_nur_beim_true_ort():
    from output.renderers.comparison import render_comparison_text

    result = _result_ein_ort_true_ein_ort_none()
    text = render_comparison_text(result, enabled_metrics=["thunder_max"])

    assert _HAGEL_HINWEIS in text, (
        f"Der Klartext-Vergleich muss beim Ort mit hail_flag=True den "
        f"Hinweis '{_HAGEL_HINWEIS}' zeigen. Text: {text!r}"
    )
    lines = text.splitlines()
    hagel_lines = [ln for ln in lines if "Gewitter" in ln and _HAGEL_HINWEIS in ln]
    assert hagel_lines, f"Keine Gewitter-Zeile mit Hagel-Hinweis gefunden: {lines!r}"


# =============================================================================
# AC-7(c) — Mehrtages-Ausblick des Ortsvergleichs (compare_outlook_metric_ids.py)
# =============================================================================

def test_ac7c_compare_ausblick_zeigt_hagel_hinweis_beim_true_ort():
    from output.renderers.compare_outlook_metric_ids import format_outlook_value

    column = {"kind": "ordinal", "field": "thunder_level_max"}
    text_true = format_outlook_value(ThunderLevel.HIGH, {**column, "hail": True})
    text_unbekannt = format_outlook_value(ThunderLevel.HIGH, {**column, "hail": None})

    assert _HAGEL_HINWEIS in text_true, (
        f"format_outlook_value() muss bei hail=True den Hinweis "
        f"'{_HAGEL_HINWEIS}' anhaengen, bekam: {text_true!r}"
    )
    assert _HAGEL_HINWEIS not in text_unbekannt, (
        f"format_outlook_value() darf bei hail=None keinen Zusatz anhaengen, "
        f"bekam: {text_unbekannt!r}"
    )


# =============================================================================
# AC-8 — Compare-Stundentabelle: Text-Anhang statt Doppelring
# =============================================================================

def test_ac8_compare_stundentabelle_zeigt_hagel_als_text_nicht_als_ring():
    from output.renderers.email.compare_html import render_compare_html

    result = _result_ein_ort_true_ein_ort_none()
    html = render_compare_html(
        result, enabled_metrics=["thunder_max"], hourly_metrics=["thunder_level"],
    )

    assert _HAGEL_HINWEIS in html, (
        f"Die Compare-Stundentabelle muss den Hagel-Hinweis als Text in der "
        f"Zelle zeigen (Stunde 14 des True-Orts). Ausschnitt: {html[:3000]!r}"
    )
    # Gegenprobe (Spec-Pflicht): KEIN zweiter box-shadow-Ring in der
    # Compare-Stundentabelle -- die Doppelring-Loesung (Punkt 2) gilt
    # AUSSCHLIESSLICH fuer die Trip-Stundentabelle.
    assert "box-shadow" not in html, (
        "Die Compare-Stundentabelle darf KEINEN box-shadow-Ring verwenden -- "
        "sie zeigt Gewitter als Textlabel + Zell-Toenung, kein Ampel-Kreis "
        "(Spec AC-8, geklaerte Designfrage)."
    )
