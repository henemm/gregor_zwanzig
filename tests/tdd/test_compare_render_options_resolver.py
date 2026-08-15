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
# Die 6 Tests zu `top_n_details` (Default 3 / Clamp 1..10 / ungueltiger Wert)
# sind mit Issue #1360 GELOESCHT: der Regler ist ersatzlos entfallen, sie
# prueften damit veraltetes Verhalten. Der Nachweis, dass ein noch gespeichertes
# `top_n` keinerlei Wirkung mehr hat, liegt in
# `tests/test_compare_top_n_render_invariance.py`.
# ---------------------------------------------------------------------------


def test_resolver_returns_compare_render_options_instance():
    options = resolve_compare_render_options({"id": "p1"})
    assert isinstance(options, CompareRenderOptions)


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
    # Issue #1335 Scheibe 1: reihenfolge-erhaltende Liste statt Set.
    assert options.enabled_metrics == ["temp_max", "cloud_avg"]


def test_no_active_metrics_means_no_filter():
    options = resolve_compare_render_options({"id": "p8"})
    assert options.enabled_metrics is None


# ---------------------------------------------------------------------------
# enabled_metrics_by_channel -- Issue #1703 Scheibe 8 (ADR-0053).
#
# Der Resolver ist die EINZIGE Stelle, an der die kanalweise Uebersichts-
# Auswahl entsteht; seine beiden Leser (scheduler_dispatch_service,
# compare_preview_service) greifen mit festen Keys darauf zu
# (`opts.enabled_metrics_by_channel["email"|"telegram"|"sms"]`). Faellt die
# Befuellung weg oder schrumpft die Schluessel-Menge, bricht der Compare-
# Versand mit KeyError -- deshalb wird hier die Schluessel-Menge UND ein Wert
# zugesichert, nicht nur die Existenz des Feldes.
# ---------------------------------------------------------------------------


def test_enabled_metrics_by_channel_covers_exactly_the_three_compare_channels():
    """Genau email/telegram/sms -- Premium-SMS ist im Vergleich reiner
    Alarm-Kanal (#1745), Signal ist entfernt (#610)."""
    options = resolve_compare_render_options({"id": "p18"})
    assert set(options.enabled_metrics_by_channel) == {"email", "telegram", "sms"}, (
        "Die Leser greifen mit genau diesen drei Keys zu "
        "(scheduler_dispatch_service.py:439/505/509, compare_preview_service.py:65/70/186)"
    )


def test_channel_selection_is_clipped_to_the_global_maximum_per_channel():
    """ADR-0050 Regel 1/2: die Grundauswahl ist das MAXIMUM, ein Kanal darf nur
    ABWAEHLEN. SMS waehlt hier 'wind_max_kmh' zusaetzlich an -- das ist nicht in
    der Grundauswahl und muss weggeschnitten werden; die beiden Kanaele ohne
    eigenen Eintrag folgen unveraendert der Grundauswahl (AC-S8-15)."""
    preset = {
        "id": "p19",
        "display_config": {
            "active_metrics": ["temp_max_c", "cloud_avg_pct"],
            "channel_active_metrics": {"sms": ["temp_max_c", "wind_max_kmh"]},
        },
    }
    options = resolve_compare_render_options(preset)
    by_channel = options.enabled_metrics_by_channel

    assert by_channel["sms"] == ["temp_max"], (
        "Die SMS-Auswahl muss gegen die Grundauswahl geschnitten werden -- "
        "'wind_max' ist dort nicht enthalten und darf nicht durch eine "
        "Kanal-Auswahl wieder hereinkommen"
    )
    assert by_channel["email"] == ["temp_max", "cloud_avg"]
    assert by_channel["telegram"] == ["temp_max", "cloud_avg"]
    # Bewusst additiv: das globale Feld behaelt Bedeutung UND Wert.
    assert options.enabled_metrics == ["temp_max", "cloud_avg"]


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
    # Issue #1335 Scheibe 1: reihenfolge-erhaltende Liste statt Set.
    assert options.hourly_metrics == ["wind10m_kmh"]


def test_no_hourly_metrics_means_no_filter():
    options = resolve_compare_render_options({"id": "p12"})
    assert options.hourly_metrics is None


# ---------------------------------------------------------------------------
# corridors — Issue #1231 Slice 7. Adversary F004 (Fix-Loop): Nicht-Dict-
# Eintraege duerfen den Versandpfad NIEMALS crashen (malformte Korridore
# fallen still raus, analog dem defensiven Trip-Ladepfad, s.
# app/loader.py::_corridor_from_dict / BUG-DATALOSS-GR221-Muster).
# ---------------------------------------------------------------------------


def test_no_corridors_field_means_none():
    options = resolve_compare_render_options({"id": "p14"})
    assert options.corridors is None


def test_valid_corridors_parsed():
    preset = {
        "id": "p15",
        "corridors": [{"metric": "temp_max_c", "range": [15, 35], "mark": True}],
    }
    options = resolve_compare_render_options(preset)
    assert options.corridors is not None
    assert len(options.corridors) == 1
    assert options.corridors[0].metric == "temp_max_c"
    assert options.corridors[0].mark is True


def test_non_dict_corridor_entries_skipped_without_crash():
    """F004: 'not-a-dict' (str), 42 (int), None -- keiner davon darf
    resolve_compare_render_options() zum Absturz bringen (AttributeError bei
    `d.get(...)` auf Nicht-Dicts, vor dem Fix ungefangen)."""
    for bad_corridors in (["not-a-dict"], [42], [None]):
        options = resolve_compare_render_options({"id": "p16", "corridors": bad_corridors})
        assert options.corridors is None, f"Malformte Korridore {bad_corridors!r} muessen leer/None ergeben"


def test_mix_of_valid_and_malformed_corridors_keeps_only_valid():
    preset = {
        "id": "p17",
        "corridors": [
            {"metric": "temp_max_c", "range": [15, 35], "mark": True},
            "not-a-dict",
            None,
            {"metric": "wind_max_kmh", "range": [0, 40], "mark": True},
        ],
    }
    options = resolve_compare_render_options(preset)
    assert options.corridors is not None
    assert len(options.corridors) == 2
    assert {c.metric for c in options.corridors} == {"temp_max_c", "wind_max_kmh"}


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
        enabled_metrics=options.enabled_metrics,
        hourly_metrics=options.hourly_metrics,
        hourly_enabled=options.hourly_enabled,
    )

    assert ">Temperatur<" in html, (
        "Aktivierte Metrik 'Temperatur' muss im HTML sichtbar sein"
    )
    assert ">Wind<" not in html, (
        "AC-2: deaktivierte Metrik 'Wind' (wind_max_kmh nicht in active_metrics) "
        "darf NICHT in der Uebersichtstabelle der gerenderten Compare-Mail (HTML) "
        "erscheinen."
    )
    assert "Temperatur:" in plain, (
        "Aktivierte Metrik 'Temperatur' muss im Klartext sichtbar sein"
    )
    assert "Wind:" not in plain, (
        "AC-2: deaktivierte Metrik 'Wind' (wind_max_kmh nicht in active_metrics) "
        "darf NICHT in der Uebersichtszeile der gerenderten Compare-Mail (Plain) "
        "erscheinen."
    )
