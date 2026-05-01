"""TDD RED — Wetter-Templates Phase A: Template Registry + API.

Tests for:
1. WEATHER_TEMPLATES registry in metric_catalog.py
2. get_all_templates() function
3. build_default_display_config_for_profile() using WEATHER_TEMPLATES
4. GET /templates API endpoint
"""



# ---------------------------------------------------------------------------
# 1. WEATHER_TEMPLATES registry
# ---------------------------------------------------------------------------


class TestWeatherTemplatesRegistry:
    """WEATHER_TEMPLATES must exist and contain all 7 templates."""

    def test_weather_templates_exists(self):
        """GIVEN metric_catalog module
        WHEN importing WEATHER_TEMPLATES
        THEN it should be a dict with 7 entries."""
        from app.metric_catalog import WEATHER_TEMPLATES

        assert isinstance(WEATHER_TEMPLATES, dict)
        assert len(WEATHER_TEMPLATES) == 7

    def test_all_template_ids_present(self):
        """GIVEN WEATHER_TEMPLATES
        WHEN checking keys
        THEN all 7 template IDs are present."""
        from app.metric_catalog import WEATHER_TEMPLATES

        expected_ids = {
            "alpen-trekking", "wandern", "skitouren", "wintersport",
            "radtour", "wassersport", "allgemein",
        }
        assert set(WEATHER_TEMPLATES.keys()) == expected_ids

    def test_each_template_has_label_and_metrics(self):
        """GIVEN WEATHER_TEMPLATES
        WHEN iterating entries
        THEN each has 'label' (str) and 'metrics' (list[str])."""
        from app.metric_catalog import WEATHER_TEMPLATES

        for tid, tdata in WEATHER_TEMPLATES.items():
            assert "label" in tdata, f"Template {tid} missing 'label'"
            assert "metrics" in tdata, f"Template {tid} missing 'metrics'"
            assert isinstance(tdata["label"], str)
            assert isinstance(tdata["metrics"], list)
            assert len(tdata["metrics"]) > 0, f"Template {tid} has empty metrics"

    def test_all_metric_ids_valid(self):
        """GIVEN WEATHER_TEMPLATES
        WHEN checking each template's metric IDs
        THEN all IDs exist in the MetricCatalog."""
        from app.metric_catalog import WEATHER_TEMPLATES, get_all_metrics

        valid_ids = {m.id for m in get_all_metrics()}
        for tid, tdata in WEATHER_TEMPLATES.items():
            for mid in tdata["metrics"]:
                assert mid in valid_ids, (
                    f"Template '{tid}' references unknown metric '{mid}'"
                )

    def test_alpen_trekking_has_14_metrics(self):
        """GIVEN alpen-trekking template
        WHEN counting metrics
        THEN it has 14 metrics including freezing_level, cape, wind_chill."""
        from app.metric_catalog import WEATHER_TEMPLATES

        metrics = WEATHER_TEMPLATES["alpen-trekking"]["metrics"]
        assert len(metrics) == 14
        assert "freezing_level" in metrics
        assert "cape" in metrics
        assert "wind_chill" in metrics

    def test_allgemein_has_7_metrics(self):
        """GIVEN allgemein template
        WHEN counting metrics
        THEN it has 7 basic metrics."""
        from app.metric_catalog import WEATHER_TEMPLATES

        metrics = WEATHER_TEMPLATES["allgemein"]["metrics"]
        assert len(metrics) == 7

    def test_profile_metric_ids_removed(self):
        """GIVEN metric_catalog module
        WHEN checking for old PROFILE_METRIC_IDS
        THEN it should no longer exist (replaced by WEATHER_TEMPLATES)."""
        import app.metric_catalog as mc

        assert not hasattr(mc, "PROFILE_METRIC_IDS"), (
            "PROFILE_METRIC_IDS should be replaced by WEATHER_TEMPLATES"
        )


# ---------------------------------------------------------------------------
# 2. get_all_templates() function
# ---------------------------------------------------------------------------


class TestGetAllTemplates:
    """get_all_templates() returns structured template list."""

    def test_returns_list(self):
        """GIVEN metric_catalog
        WHEN calling get_all_templates()
        THEN it returns a list."""
        from app.metric_catalog import get_all_templates

        result = get_all_templates()
        assert isinstance(result, list)

    def test_returns_7_templates(self):
        """GIVEN metric_catalog
        WHEN calling get_all_templates()
        THEN 7 templates are returned."""
        from app.metric_catalog import get_all_templates

        result = get_all_templates()
        assert len(result) == 7

    def test_template_structure(self):
        """GIVEN get_all_templates() result
        WHEN inspecting each entry
        THEN it has id (str), label (str), metrics (list[str])."""
        from app.metric_catalog import get_all_templates

        for t in get_all_templates():
            assert "id" in t
            assert "label" in t
            assert "metrics" in t
            assert isinstance(t["id"], str)
            assert isinstance(t["label"], str)
            assert isinstance(t["metrics"], list)

    def test_first_template_is_alpen_trekking(self):
        """GIVEN get_all_templates()
        WHEN checking first entry
        THEN it is 'alpen-trekking' (insertion order preserved)."""
        from app.metric_catalog import get_all_templates

        result = get_all_templates()
        assert result[0]["id"] == "alpen-trekking"
        assert result[0]["label"] == "Alpen-Trekking"


# ---------------------------------------------------------------------------
# 3. build_default_display_config_for_profile() backward compat
# ---------------------------------------------------------------------------


class TestBuildDefaultDisplayConfigUpdated:
    """build_default_display_config_for_profile() reads from WEATHER_TEMPLATES."""

    def test_wandern_profile_uses_weather_templates(self):
        """GIVEN a 'wandern' profile
        WHEN building display config
        THEN enabled metrics match WEATHER_TEMPLATES['wandern']."""
        from app.metric_catalog import (
            WEATHER_TEMPLATES,
            build_default_display_config_for_profile,
        )
        from app.user import LocationActivityProfile

        dc = build_default_display_config_for_profile(
            "test-loc", LocationActivityProfile.WANDERN
        )
        enabled = dc.get_enabled_metric_ids()
        expected = set(WEATHER_TEMPLATES["wandern"]["metrics"])
        assert set(enabled) == expected

    def test_wintersport_profile_uses_weather_templates(self):
        """GIVEN a 'wintersport' profile
        WHEN building display config
        THEN enabled metrics match WEATHER_TEMPLATES['wintersport']."""
        from app.metric_catalog import (
            WEATHER_TEMPLATES,
            build_default_display_config_for_profile,
        )
        from app.user import LocationActivityProfile

        dc = build_default_display_config_for_profile(
            "test-loc", LocationActivityProfile.WINTERSPORT
        )
        enabled = dc.get_enabled_metric_ids()
        expected = set(WEATHER_TEMPLATES["wintersport"]["metrics"])
        assert set(enabled) == expected

    def test_allgemein_profile_uses_weather_templates(self):
        """GIVEN an 'allgemein' profile
        WHEN building display config
        THEN enabled metrics match WEATHER_TEMPLATES['allgemein']."""
        from app.metric_catalog import (
            WEATHER_TEMPLATES,
            build_default_display_config_for_profile,
        )
        from app.user import LocationActivityProfile

        dc = build_default_display_config_for_profile(
            "test-loc", LocationActivityProfile.ALLGEMEIN
        )
        enabled = dc.get_enabled_metric_ids()
        expected = set(WEATHER_TEMPLATES["allgemein"]["metrics"])
        assert set(enabled) == expected


# ---------------------------------------------------------------------------
# 4. GET /templates API endpoint
# ---------------------------------------------------------------------------


class TestTemplatesEndpoint:
    """GET /templates returns template list from metric_catalog."""

    def test_endpoint_returns_200(self):
        """GIVEN the FastAPI app
        WHEN calling GET /templates
        THEN it returns 200."""
        from fastapi.testclient import TestClient
        from api.main import app

        client = TestClient(app)
        response = client.get("/templates")
        assert response.status_code == 200

    def test_endpoint_returns_list_of_7(self):
        """GIVEN GET /templates
        WHEN parsing response
        THEN it contains 7 templates."""
        from fastapi.testclient import TestClient
        from api.main import app

        client = TestClient(app)
        response = client.get("/templates")
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 7

    def test_endpoint_template_structure(self):
        """GIVEN GET /templates response
        WHEN inspecting first template
        THEN it has id, label, metrics keys."""
        from fastapi.testclient import TestClient
        from api.main import app

        client = TestClient(app)
        response = client.get("/templates")
        first = response.json()[0]
        assert "id" in first
        assert "label" in first
        assert "metrics" in first

    def test_endpoint_alpen_trekking_metrics(self):
        """GIVEN GET /templates response
        WHEN finding alpen-trekking
        THEN it has 14 metrics including freezing_level."""
        from fastapi.testclient import TestClient
        from api.main import app

        client = TestClient(app)
        data = client.get("/templates").json()
        alpen = next(t for t in data if t["id"] == "alpen-trekking")
        assert len(alpen["metrics"]) == 14
        assert "freezing_level" in alpen["metrics"]
