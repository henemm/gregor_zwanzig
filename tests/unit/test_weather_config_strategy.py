"""
Strategy-Dataclass und Render-Funktion fuer Bug #89 v1.1.

Spec: docs/specs/modules/weather_metrics_dialog_unification.md v1.1

v1.1: Cleanup nach F76-Routen-Aufraeumen
- Location/Subscription-Dialoge entfernt (UI-tot seit F76)
- _DialogStrategy ohne full_columns (nur noch Trip = full)
- Nur _make_trip_save_fn uebrig
"""
from __future__ import annotations



# =====================================================================
# 1. _DialogStrategy Dataclass
# =====================================================================


class TestDialogStrategyDataclass:
    """Spec §2: _DialogStrategy mit 5 Feldern (full_columns entfernt)."""

    def test_dialog_strategy_can_be_imported(self) -> None:
        """GIVEN: weather_config.py
        WHEN: _DialogStrategy importiert
        THEN: Klasse existiert."""
        from web.pages.weather_config import _DialogStrategy
        assert _DialogStrategy is not None

    def test_dialog_strategy_has_required_fields(self) -> None:
        """GIVEN: _DialogStrategy
        WHEN: Felder inspiziert
        THEN: title, subtitle, available_providers, current_configs, save_fn vorhanden.
              full_columns ist entfernt (v1.1)."""
        from dataclasses import fields
        from web.pages.weather_config import _DialogStrategy

        field_names = {f.name for f in fields(_DialogStrategy)}
        required = {
            "title",
            "subtitle",
            "available_providers",
            "current_configs",
            "save_fn",
        }
        assert required.issubset(field_names), (
            f"_DialogStrategy fehlen Felder: {required - field_names}"
        )
        # v1.1: full_columns entfernt
        assert "full_columns" not in field_names, (
            "full_columns sollte in v1.1 entfernt sein"
        )


# =====================================================================
# 2. Render-Funktion
# =====================================================================


class TestRenderFunctionExists:
    """Spec §2: _render_weather_config_dialog(strategy) als Modul-level."""

    def test_render_weather_config_dialog_callable(self) -> None:
        """GIVEN: weather_config.py
        WHEN: _render_weather_config_dialog importiert
        THEN: Callable mit einem Parameter (strategy)."""
        import inspect
        from web.pages.weather_config import _render_weather_config_dialog

        assert callable(_render_weather_config_dialog)
        sig = inspect.signature(_render_weather_config_dialog)
        params = list(sig.parameters.keys())
        assert "strategy" in params, (
            f"_render_weather_config_dialog muss 'strategy' Parameter haben, "
            f"hat aber: {params}"
        )


# =====================================================================
# 3. Save-Factory (Trip-only)
# =====================================================================


class TestSaveFactoriesExist:
    """Spec §3 (v1.1): nur noch _make_trip_save_fn."""

    def test_make_trip_save_fn_callable(self) -> None:
        """_make_trip_save_fn(trip_id, user_id, dialog) -> Callable."""
        from web.pages.weather_config import _make_trip_save_fn
        assert callable(_make_trip_save_fn)

    def test_save_factories_have_three_params(self) -> None:
        """Trip-Factory hat (entity_id, user_id, dialog)-Signatur."""
        import inspect
        from web.pages.weather_config import _make_trip_save_fn

        sig = inspect.signature(_make_trip_save_fn)
        params = list(sig.parameters.keys())
        assert len(params) == 3, (
            f"_make_trip_save_fn muss 3 Parameter haben, hat aber: {params}"
        )


# =====================================================================
# 4. Public Dialog-Funktion
# =====================================================================


class TestPublicDialogFunctionsRemain:
    """Sanity: Trip-Dialog-Funktion bleibt erhalten."""

    def test_show_weather_config_dialog_exists(self) -> None:
        from web.pages.weather_config import show_weather_config_dialog
        assert callable(show_weather_config_dialog)


# =====================================================================
# 5. Issue #89: Alert-Default = False
# =====================================================================


class TestAlertDefaultIsFalse:
    """Issue #89: Alert-Default = False (explizites Opt-in)."""

    def test_default_config_has_no_alerts_enabled(self) -> None:
        """build_default_display_config liefert keine MetricConfig mit alert_enabled=True."""
        from app.metric_catalog import build_default_display_config
        config = build_default_display_config("test-trip")
        for mc in config.metrics:
            assert mc.alert_enabled is False, (
                f"Metric {mc.metric_id} has alert_enabled=True by default — "
                f"Issue #89: alerts must be explicit opt-in"
            )
