"""Issue #1209 AC-2 — CompareRenderOptions-Resolver fuer den Compare-Versandpfad.

Spec: docs/specs/modules/report_config_resolver_slice_b.md

`resolve_compare_render_options(preset: dict) -> CompareRenderOptions` buendelt
die bisher inline in `scheduler_dispatch_service.py:252-276` verstreute
Default-/Clamp-/Metrik-Aufloesungslogik zu einer reinen Funktion, analog dem
Scheibe-A-Resolver `resolve_report_render_options` (Issue #1208).

RED-Grund: `resolve_compare_render_options`/`CompareRenderOptions` existieren
noch nicht in `src/services/report_config_resolver.py` -> ImportError bei
Modul-Collection (Spec-Vorgabe: "jetzt ROT, existiert noch nicht: ImportError").

KEINE Mocks/patch/MagicMock. Fuer den gerenderten-Mail-Fall (letzte Testklasse)
wird eine synthetische, echte `ComparisonResult` gebaut (Vorbild
tests/tdd/test_issue_1107_compare_sections.py::_make_comparison_result) und
direkt an `render_compare_email()` uebergeben — kein Netzwerk, kein Mock.
"""
from __future__ import annotations

from datetime import date, datetime

from app.models import ForecastDataPoint, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from services.report_config_resolver import CompareRenderOptions, resolve_compare_render_options


def _loc(loc_id: str, name: str) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=47.27, lon=11.39, elevation_m=574)


def _dp(hour: int, **overrides) -> ForecastDataPoint:
    defaults = dict(
        ts=datetime(2026, 7, 8, hour, 0),
        t2m_c=20.0, wind_chill_c=19.0, wind10m_kmh=10.0, gust_kmh=18.0,
        precip_1h_mm=0.0, cloud_total_pct=30, uv_index=4.0,
        thunder_level=ThunderLevel.NONE, pop_pct=15, visibility_m=9000,
    )
    defaults.update(overrides)
    return ForecastDataPoint(**defaults)


def _make_comparison_result(names: list[str]) -> ComparisonResult:
    """Mindestens drei Orte mit vollstaendigen Uebersichts-/Stundendaten."""
    locations = [
        LocationResult(
            location=_loc(f"loc-cro-{i}", name),
            temp_max=20.0 + i,
            wind_max=10.0,
            sunny_hours=5.0,
            cloud_avg=30,
            official_alerts=[],
            hourly_data=[_dp(9), _dp(10)],
        )
        for i, name in enumerate(names)
    ]
    return ComparisonResult(
        locations=locations,
        time_window=(9, 16),
        target_date=date(2026, 7, 8),
        created_at=datetime(2026, 7, 8, 4, 0),
    )


# ---------------------------------------------------------------------------
# top_n_details — Default 3 / Clamp 1..10 / ungueltiger Wert (Bestandsverhalten
# aus scheduler_dispatch_service.py:254-270)
# ---------------------------------------------------------------------------


def test_missing_top_n_defaults_to_3():
    options = resolve_compare_render_options({"id": "p1"})
    assert isinstance(options, CompareRenderOptions)
    assert options.top_n_details == 3


def test_top_n_within_range_passes_through():
    options = resolve_compare_render_options({"id": "p2", "display_config": {"top_n": 5}})
    assert options.top_n_details == 5


def test_top_n_15_is_clamped_to_10():
    options = resolve_compare_render_options({"id": "p3", "display_config": {"top_n": 15}})
    assert options.top_n_details == 10


def test_top_n_invalid_string_falls_back_to_default_3():
    options = resolve_compare_render_options({"id": "p4", "display_config": {"top_n": "abc"}})
    assert options.top_n_details == 3


def test_top_n_zero_is_clamped_to_1():
    options = resolve_compare_render_options({"id": "p5", "display_config": {"top_n": 0}})
    assert options.top_n_details == 1


def test_top_n_negative_is_clamped_to_1():
    options = resolve_compare_render_options({"id": "p6", "display_config": {"top_n": -5}})
    assert options.top_n_details == 1


# ---------------------------------------------------------------------------
# enabled_metrics — deaktivierte Metrik fehlt in der Aufloesung
# ---------------------------------------------------------------------------


def test_deactivated_metric_missing_from_enabled_metrics():
    """active_metrics ohne 'wind_max_kmh' -> enabled_metrics enthaelt kein 'wind_max'."""
    preset = {
        "id": "p7",
        "display_config": {"active_metrics": ["temp_max_c", "cloud_avg_pct"]},
    }
    options = resolve_compare_render_options(preset)
    assert options.enabled_metrics is not None
    assert "wind_max" not in options.enabled_metrics
    assert options.enabled_metrics == {"temp_max", "cloud_avg"}


def test_no_active_metrics_means_no_filter():
    options = resolve_compare_render_options({"id": "p8"})
    assert options.enabled_metrics is None


# ---------------------------------------------------------------------------
# hourly_enabled — TOP-LEVEL Feld (nicht im display_config-Blob), Default True
# ---------------------------------------------------------------------------


def test_hourly_enabled_top_level_true_default():
    options = resolve_compare_render_options({"id": "p9"})
    assert options.hourly_enabled is True


def test_hourly_enabled_top_level_false_respected():
    options = resolve_compare_render_options({"id": "p10", "hourly_enabled": False})
    assert options.hourly_enabled is False


def test_hourly_metrics_resolved_from_display_config():
    preset = {
        "id": "p11",
        "display_config": {"hourly_metrics": ["wind_kmh"]},
    }
    options = resolve_compare_render_options(preset)
    assert options.hourly_metrics == {"wind10m_kmh"}


def test_no_hourly_metrics_means_no_filter():
    options = resolve_compare_render_options({"id": "p12"})
    assert options.hourly_metrics is None


# ---------------------------------------------------------------------------
# AC-2 Hauptfall: deaktivierte Metrik fehlt in der ECHT gerenderten Mail
# (HTML + Plain) — kein Mock, direkte render_compare_email()-Aufrufe mit den
# resolvten Optionen.
# ---------------------------------------------------------------------------


def test_disabled_metric_absent_from_rendered_compare_mail_html_and_plain():
    from output.renderers.comparison import render_compare_email

    result = _make_comparison_result(["Ort A", "Ort B", "Ort C"])
    preset = {
        "id": "p13",
        "display_config": {"active_metrics": ["temp_max_c", "cloud_avg_pct"]},
        # hourly_enabled=False, damit die per-Ort-Stundentabelle (die "Wind"
        # unabhaengig von enabled_metrics zeigt) den Uebersichts-Befund nicht
        # verdeckt — die Stundentabelle ist nicht Gegenstand von AC-2.
        "hourly_enabled": False,
    }
    options = resolve_compare_render_options(preset)
    assert options.hourly_enabled is False

    html, plain = render_compare_email(
        result,
        top_n_details=options.top_n_details,
        enabled_metrics=options.enabled_metrics,
        hourly_metrics=options.hourly_metrics,
        hourly_enabled=options.hourly_enabled,
    )

    assert ">Temp max<" in html, "Aktivierte Metrik 'Temp max' muss im HTML sichtbar sein"
    assert ">Wind<" not in html, (
        "AC-2: deaktivierte Metrik 'Wind' (wind_max_kmh nicht in active_metrics) "
        "darf NICHT in der Uebersichtstabelle der gerenderten Compare-Mail (HTML) "
        "erscheinen."
    )
    assert "Temp max:" in plain, "Aktivierte Metrik 'Temp max' muss im Klartext sichtbar sein"
    assert "Wind:" not in plain, (
        "AC-2: deaktivierte Metrik 'Wind' (wind_max_kmh nicht in active_metrics) "
        "darf NICHT in der Uebersichtszeile der gerenderten Compare-Mail (Plain) "
        "erscheinen."
    )
