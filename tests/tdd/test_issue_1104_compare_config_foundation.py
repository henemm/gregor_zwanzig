"""TDD RED — Issue #1104: Ortsvergleich Fundament — Editor-Config wirkt im Versand.

Spec: docs/specs/modules/issue_1104_compare_config_foundation.md (AC-2, AC-4)
Kontext: docs/context/fix-1094-compare-config.md

Der Compare-Editor speichert `display_config.top_n` / `display_config.active_metrics`
in `ComparePreset`, aber `send_one_compare_preset()` (scheduler_dispatch_service.py)
liest daraus heute NICHTS und ruft
`render_compare_email(result, profile=profile)` ohne `top_n_details`/
`enabled_metrics` auf. Dieses RED-Modul deckt zwei fehlende Bausteine auf:

  1. Der kanonische ID-Resolver `resolve_enabled_metrics()`
     (`src/output/renderers/compare_metric_ids.py`) existiert noch nicht
     -> ImportError bei jedem Testfall in `TestResolveEnabledMetrics`.
  2. `send_one_compare_preset()` liest `display_config` nicht und uebergibt
     `top_n_details`/`enabled_metrics` nicht an `render_compare_email()` ->
     AssertionError (aufgezeichneter Kwarg fehlt bzw. weicht vom erwarteten
     Wert ab) in den Wiring-Tests.

KEINE Mocks (Projektkonvention CLAUDE.md): Fuer die Wiring-Tests wird das
Symbol `render_compare_email` auf dem Modul `output.renderers.comparison`
per echtem Attribut-Rebind (kein `patch()`/`Mock()`) durch eine reale
Aufzeichnungs-Funktion ersetzt, die die uebergebenen Kwargs festhaelt und dann
gezielt via Sentinel-Exception abbricht, BEVOR SMTP beruehrt wird. Der
vorgelagerte `ComparisonEngine`-Lauf (inkl. Offline-Fixture-Provider ueber
die autouse-Fixture in `tests/conftest.py`) findet dabei vollstaendig echt
statt -- Muster aus `tests/tdd/test_issue_1040_alerts_toggle.py` und
`tests/tdd/test_issue_764_compare_forecast_hours_consume.py`.
"""
from __future__ import annotations

import uuid

import pytest


class TestResolveEnabledMetrics:
    """Reiner Unit-Test fuer den (noch nicht existierenden) kanonischen
    ID-Resolver `resolve_enabled_metrics()`.

    RED: `src/output/renderers/compare_metric_ids.py` existiert noch
    nicht -> ImportError bei jedem Testfall dieser Klasse.
    """

    def test_known_frontend_ids_resolve_to_renderer_ids(self):
        from output.renderers.compare_metric_ids import resolve_enabled_metrics

        result = resolve_enabled_metrics(["wind_max_kmh", "cloud_avg_pct"])
        # Issue #1335 Scheibe 1: reihenfolge-erhaltende Liste statt Set.
        assert result == ["wind_max", "cloud_avg"], (
            f"Erwartet ['wind_max', 'cloud_avg'], erhalten {result!r}"
        )

    def test_empty_list_returns_none(self):
        from output.renderers.compare_metric_ids import resolve_enabled_metrics

        result = resolve_enabled_metrics([])
        assert result is None, f"Leere Liste muss None ergeben (kein Filter), erhalten {result!r}"

    def test_none_returns_none(self):
        from output.renderers.compare_metric_ids import resolve_enabled_metrics

        result = resolve_enabled_metrics(None)
        assert result is None, f"None muss None ergeben (kein Filter), erhalten {result!r}"

    def test_unknown_ids_are_dropped_not_crashed(self):
        from output.renderers.compare_metric_ids import resolve_enabled_metrics

        # Issue #1285: Das Beispiel war bis 2026-07-16 `visibility_min_m` mit der
        # Begruendung "kein ComparisonResult-Feld -> bewusst nicht gemappt". Genau
        # dieses Nicht-Mappen war der Bug (Auswahl wurde still verworfen); Sicht
        # ist jetzt gemappt und taugt nicht mehr als Beispiel fuer eine UNBEKANNTE
        # ID. Die Aussage des Tests bleibt unveraendert -- geprueft mit einer ID,
        # die es wirklich nicht gibt.
        result = resolve_enabled_metrics(["voellig_unbekannte_metrik_xyz"])
        assert result is None, (
            f"Unbekannte ID muss verworfen werden -> Ergebnis None (nicht leeres "
            f"Set, nicht Absturz), erhalten {result!r}"
        )

    def test_scalar_string_input_returns_none_not_crashed(self):
        """Adversary F001: ein einzelner String darf nicht ueber seine
        Zeichen iteriert werden (would silently 'work' but be wrong)."""
        from output.renderers.compare_metric_ids import resolve_enabled_metrics

        result = resolve_enabled_metrics("wind_max_kmh")
        assert result is None, (
            f"Scalar-String-Input muss defensiv zu None fuehren, erhalten {result!r}"
        )

    def test_dict_input_returns_none_not_crashed(self):
        """Adversary F001: ein dict darf nicht ueber seine Keys iteriert werden."""
        from output.renderers.compare_metric_ids import resolve_enabled_metrics

        result = resolve_enabled_metrics({"a": 1})
        assert result is None, (
            f"Dict-Input muss defensiv zu None fuehren, erhalten {result!r}"
        )

    def test_int_input_returns_none_not_typeerror(self):
        """Adversary F001: ein int ist nicht iterierbar -> darf keinen
        TypeError werfen, sondern defensiv zu None fuehren."""
        from output.renderers.compare_metric_ids import resolve_enabled_metrics

        result = resolve_enabled_metrics(5)
        assert result is None, (
            f"Int-Input muss defensiv zu None fuehren (kein TypeError), "
            f"erhalten {result!r}"
        )


class _RenderCallRecorded(Exception):
    """Sentinel: bricht send_one_compare_preset gezielt nach dem
    render_compare_email-Aufruf ab, bevor SMTP beruehrt wird. Traegt die
    aufgezeichneten Kwargs (oder den Sentinel-String "NOT_PASSED", wenn der
    jeweilige Kwarg fehlt)."""

    def __init__(self, top_n_details, enabled_metrics):
        self.top_n_details = top_n_details
        self.enabled_metrics = enabled_metrics
        super().__init__(
            f"recorded top_n_details={top_n_details!r} enabled_metrics={enabled_metrics!r}"
        )


def _fresh_user() -> str:
    return f"test1104-{uuid.uuid4().hex[:8]}"


def _resolvable_location(loc_id: str):
    """Eine echte SavedLocation (in-memory). Wird ueber den all_locations_cache-
    Parameter von send_one_compare_preset durchgereicht, damit der Orte-Resolve
    NICHT vorher abbricht und die Engine erreicht wird -- ohne Schreib-
    Seiteneffekt im echten data/-Verzeichnis (Muster aus #764/#1040)."""
    from app.loader import SavedLocation

    return SavedLocation(
        id=loc_id,
        name="Innsbruck",
        lat=47.27,
        lon=11.39,
        elevation_m=574,
    )


def _preset(preset_id: str, display_config, loc_id: str) -> dict:
    p = {
        "id": preset_id,
        "name": f"Vergleich {preset_id}",
        "location_ids": [loc_id],
        "schedule": "daily",
        "profil": "SUMMER_TREKKING",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-01-01T00:00:00Z",
    }
    if display_config is not None:
        p["display_config"] = display_config
    return p


def _capture_render_call(preset: dict, location, tmp_path) -> tuple:
    """Fuehrt send_one_compare_preset mit einer echten Aufzeichnungs-Funktion
    fuer render_compare_email aus und gibt (top_n_details, enabled_metrics)
    zurueck, wie sie tatsaechlich uebergeben wurden (oder "NOT_PASSED", wenn
    der jeweilige Kwarg fehlt).

    Mock-frei: echtes Funktions-Rebind auf dem Modul
    output.renderers.comparison, restauriert in finally. Bricht via
    Sentinel-Exception ab, bevor SMTP beruehrt wird -- der vorgelagerte
    ComparisonEngine-Lauf (inkl. Offline-Fixture-Provider) findet vollstaendig
    echt statt.
    """
    import output.renderers.comparison as compare_render_mod
    from app.config import Settings
    from services.scheduler_dispatch_service import send_one_compare_preset as _send_one_compare_preset

    user_id = preset["_user_id"]
    settings = Settings().with_user_profile(user_id)

    original_render = compare_render_mod.render_compare_email

    def _recording_render_compare_email(*args, **kwargs):
        top_n_details = kwargs.get("top_n_details", "NOT_PASSED")
        enabled_metrics = kwargs.get("enabled_metrics", "NOT_PASSED")
        raise _RenderCallRecorded(top_n_details, enabled_metrics)

    compare_render_mod.render_compare_email = _recording_render_compare_email
    try:
        with pytest.raises(_RenderCallRecorded) as exc:
            _send_one_compare_preset(
                {k: v for k, v in preset.items() if k != "_user_id"},
                settings,
                user_id,
                str(tmp_path),
                all_locations_cache=[location],
            )
        return exc.value.top_n_details, exc.value.enabled_metrics
    finally:
        compare_render_mod.render_compare_email = original_render


class TestIssue1104ActiveMetricsWiring:
    """AC-4: `display_config.active_metrics` wird resolved und an
    `render_compare_email()` als `enabled_metrics` durchgereicht.

    RED: send_one_compare_preset() liest display_config heute nicht und ruft
    render_compare_email(result, profile=profile) OHNE enabled_metrics auf ->
    aufgezeichneter Kwarg fehlt ("NOT_PASSED") statt der resolvten Auswahl.
    """

    def test_active_metrics_resolved_and_passed_to_renderer(self, tmp_path):
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1104-a")
        preset = _preset(
            "cp-1104-metrics",
            display_config={"active_metrics": ["wind_max_kmh", "cloud_avg_pct"]},
            loc_id="loc-1104-a",
        )
        preset["_user_id"] = user_id

        _, enabled_metrics = _capture_render_call(preset, loc, tmp_path)
        # Issue #1335 Scheibe 1: reihenfolge-erhaltende Liste statt Set.
        assert enabled_metrics == ["wind_max", "cloud_avg"], (
            f"RED: render_compare_email erhielt enabled_metrics={enabled_metrics!r}, "
            "erwartet ['wind_max', 'cloud_avg'] -- der Versandpfad liest "
            "display_config.active_metrics noch nicht und uebergibt "
            "enabled_metrics gar nicht."
        )

    def test_no_active_metrics_passes_none(self, tmp_path):
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1104-b")
        preset = _preset("cp-1104-none", display_config=None, loc_id="loc-1104-b")
        preset["_user_id"] = user_id

        _, enabled_metrics = _capture_render_call(preset, loc, tmp_path)
        assert enabled_metrics is None, (
            f"Ohne active_metrics muss enabled_metrics=None durchgereicht werden "
            f"(kein Filter, alle Metriken wie vor diesem Slice), erhalten "
            f"{enabled_metrics!r} -- der Versandpfad uebergibt enabled_metrics "
            "heute gar nicht (kommt als 'NOT_PASSED' an, nicht als None)."
        )


class TestIssue1104TopNWiring:
    """AC-2: `display_config.top_n` wird an `render_compare_email()` als
    `top_n_details` durchgereicht, Default 3 bei fehlendem Feld.

    RED: send_one_compare_preset() liest top_n heute nicht -> aufgezeichneter
    Kwarg fehlt ("NOT_PASSED") statt 3 bzw. dem konfigurierten Wert.
    """

    def test_missing_top_n_defaults_to_3(self, tmp_path):
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1104-c")
        preset = _preset("cp-1104-default", display_config=None, loc_id="loc-1104-c")
        preset["_user_id"] = user_id

        top_n_details, _ = _capture_render_call(preset, loc, tmp_path)
        assert top_n_details == 3, (
            f"RED: render_compare_email erhielt top_n_details={top_n_details!r}, "
            "erwartet Default 3 -- der Versandpfad uebergibt top_n_details heute "
            "gar nicht (kommt als 'NOT_PASSED' an)."
        )

    def test_explicit_top_n_1_passes_through(self, tmp_path):
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1104-d")
        preset = _preset("cp-1104-topn1", display_config={"top_n": 1}, loc_id="loc-1104-d")
        preset["_user_id"] = user_id

        top_n_details, _ = _capture_render_call(preset, loc, tmp_path)
        assert top_n_details == 1, (
            f"RED: render_compare_email erhielt top_n_details={top_n_details!r}, "
            "erwartet 1 -- display_config.top_n wird vom Versandpfad noch nicht "
            "gelesen."
        )

    def test_corrupt_top_n_falls_back_to_3_no_exception(self, tmp_path):
        """Adversary F001: ein nicht-numerischer top_n-Wert darf keinen
        ValueError werfen, der im Daily-Loop mit 'kein Empfaenger' verwechselt
        und still verschluckt wird -- stattdessen Default 3 + Warnung."""
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1104-e")
        preset = _preset(
            "cp-1104-corrupt-topn",
            display_config={"top_n": "abc"},
            loc_id="loc-1104-e",
        )
        preset["_user_id"] = user_id

        top_n_details, _ = _capture_render_call(preset, loc, tmp_path)
        assert top_n_details == 3, (
            f"Korrupter top_n-Wert 'abc' muss auf Default 3 zurueckfallen "
            f"(kein Exception-Bubble-Up), erhalten {top_n_details!r}"
        )

    def test_top_n_zero_is_clamped_to_1(self, tmp_path):
        """F003: top_n=0 wuerde top_locs[:0] ergeben -> Stundenverlauf-Sektion
        still ausgeblendet. Muss auf 1 geclamped werden (mind. ein Ort)."""
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1104-f")
        preset = _preset("cp-1104-topn0", display_config={"top_n": 0}, loc_id="loc-1104-f")
        preset["_user_id"] = user_id

        top_n_details, _ = _capture_render_call(preset, loc, tmp_path)
        assert top_n_details == 1, (
            f"top_n=0 muss auf 1 geclamped werden, erhalten {top_n_details!r}"
        )

    def test_top_n_too_large_is_clamped_to_10(self, tmp_path):
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1104-g")
        preset = _preset("cp-1104-topn99", display_config={"top_n": 99}, loc_id="loc-1104-g")
        preset["_user_id"] = user_id

        top_n_details, _ = _capture_render_call(preset, loc, tmp_path)
        assert top_n_details == 10, (
            f"top_n=99 muss auf 10 geclamped werden, erhalten {top_n_details!r}"
        )

    def test_top_n_negative_is_clamped_to_1(self, tmp_path):
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1104-h")
        preset = _preset("cp-1104-topn-neg", display_config={"top_n": -5}, loc_id="loc-1104-h")
        preset["_user_id"] = user_id

        top_n_details, _ = _capture_render_call(preset, loc, tmp_path)
        assert top_n_details == 1, (
            f"top_n=-5 muss auf 1 geclamped werden, erhalten {top_n_details!r}"
        )
