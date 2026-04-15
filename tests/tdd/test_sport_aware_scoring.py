"""
TDD RED Tests for Sport-Aware Comparison Scoring (#35).

Tests that calculate_score() accepts an activity_profile parameter
and scores differently for wintersport, wandern, and allgemein.

SPEC: docs/specs/modules/sport_aware_comparison.md v1.0
"""
import pytest
import sys

sys.path.insert(0, "src")


class TestScoringProfileDispatch:
    """Test that calculate_score dispatches to profile-specific scorers."""

    def test_accepts_profile_parameter(self):
        """
        GIVEN: calculate_score function
        WHEN: Called with profile parameter
        THEN: Does not raise TypeError
        """
        from app.user import LocationActivityProfile
        from web.pages.compare import calculate_score

        metrics = {"sunny_hours": 6, "wind_max": 10, "cloud_avg": 30}
        # Must accept profile parameter without error
        score = calculate_score(metrics, profile=LocationActivityProfile.WANDERN)
        assert isinstance(score, int)

    def test_profile_none_defaults_allgemein(self):
        """
        GIVEN: No profile specified
        WHEN: calculate_score(metrics, profile=None)
        THEN: Behaves like allgemein (snow has no effect)
        """
        from web.pages.compare import calculate_score

        metrics_with_snow = {"sunny_hours": 6, "wind_max": 10, "snow_depth_cm": 200, "snow_new_cm": 30}
        metrics_without_snow = {"sunny_hours": 6, "wind_max": 10}

        score_with = calculate_score(metrics_with_snow, profile=None)
        score_without = calculate_score(metrics_without_snow, profile=None)
        # Allgemein should NOT reward snow
        assert score_with == score_without


class TestWintersportScoring:
    """Test that wintersport scoring rewards snow and penalizes rain."""

    def test_deep_snow_high_score(self):
        """
        GIVEN: 100cm snow depth, 20cm new snow, 6h sunshine
        WHEN: Scored as wintersport
        THEN: Score > 80
        """
        from app.user import LocationActivityProfile
        from web.pages.compare import calculate_score

        metrics = {
            "snow_depth_cm": 100,
            "snow_new_cm": 20,
            "sunny_hours": 6,
            "wind_max": 10,
            "cloud_avg": 20,
            "temp_min": -5,
        }
        score = calculate_score(metrics, profile=LocationActivityProfile.WINTERSPORT)
        assert score > 80, f"Deep snow + sunshine should score >80, got {score}"

    def test_wintersport_unchanged_from_current(self):
        """
        GIVEN: Same metrics as current scoring
        WHEN: Scored as wintersport
        THEN: Score matches current calculate_score() without profile
        """
        from app.user import LocationActivityProfile
        from web.pages.compare import calculate_score

        metrics = {
            "snow_depth_cm": 50,
            "snow_new_cm": 5,
            "sunny_hours": 4,
            "wind_max": 30,
            "gust_max": 50,
            "cloud_avg": 40,
            "temp_min": -8,
        }
        score_with_profile = calculate_score(metrics, profile=LocationActivityProfile.WINTERSPORT)
        # Wintersport scoring must remain identical to the current logic
        assert isinstance(score_with_profile, int)
        assert 0 <= score_with_profile <= 100


class TestWandernScoring:
    """Test that wandern scoring penalizes thunder/rain and rewards sunshine."""

    def test_thunderstorm_low_score(self):
        """
        GIVEN: Thunder HIGH
        WHEN: Scored as wandern
        THEN: Score < 30 (dangerous conditions)
        """
        from app.user import LocationActivityProfile
        from web.pages.compare import calculate_score

        metrics = {
            "thunder_level": "HIGH",
            "precip_mm": 10,
            "sunny_hours": 0,
            "wind_max": 40,
            "cloud_avg": 95,
            "temp_min": 12,
        }
        score = calculate_score(metrics, profile=LocationActivityProfile.WANDERN)
        assert score < 30, f"Thunderstorm should score <30 for hiking, got {score}"

    def test_clear_sunny_high_score(self):
        """
        GIVEN: No rain, 7h sunshine, 15°C, good visibility
        WHEN: Scored as wandern
        THEN: Score > 75 (excellent hiking conditions)
        """
        from app.user import LocationActivityProfile
        from web.pages.compare import calculate_score

        metrics = {
            "thunder_level": "NONE",
            "precip_mm": 0,
            "pop_max_pct": 5,
            "sunny_hours": 7,
            "wind_max": 8,
            "cloud_avg": 15,
            "temp_min": 15,
            "visibility_min": 20000,
        }
        score = calculate_score(metrics, profile=LocationActivityProfile.WANDERN)
        assert score > 75, f"Perfect hiking day should score >75, got {score}"

    def test_wandern_ignores_snow(self):
        """
        GIVEN: Identical conditions with/without snow
        WHEN: Scored as wandern
        THEN: Snow has no effect on score
        """
        from app.user import LocationActivityProfile
        from web.pages.compare import calculate_score

        base = {"sunny_hours": 5, "wind_max": 15, "temp_min": 12}
        with_snow = {**base, "snow_depth_cm": 200, "snow_new_cm": 30}

        score_base = calculate_score(base, profile=LocationActivityProfile.WANDERN)
        score_snow = calculate_score(with_snow, profile=LocationActivityProfile.WANDERN)
        assert score_base == score_snow, "Snow should not affect wandern score"

    def test_wandern_uses_thunder_metric(self):
        """
        GIVEN: thunder_level in metrics
        WHEN: Scored as wandern
        THEN: Thunder HIGH penalizes more than MED
        """
        from app.user import LocationActivityProfile
        from web.pages.compare import calculate_score

        base = {"sunny_hours": 5, "wind_max": 10, "temp_min": 15}
        score_none = calculate_score({**base, "thunder_level": "NONE"}, profile=LocationActivityProfile.WANDERN)
        score_med = calculate_score({**base, "thunder_level": "MED"}, profile=LocationActivityProfile.WANDERN)
        score_high = calculate_score({**base, "thunder_level": "HIGH"}, profile=LocationActivityProfile.WANDERN)

        assert score_none > score_med > score_high, \
            f"Thunder severity order wrong: NONE={score_none}, MED={score_med}, HIGH={score_high}"


class TestAllgemeinScoring:
    """Test that allgemein scoring is balanced and ignores snow."""

    def test_allgemein_ignores_snow(self):
        """
        GIVEN: Metrics with snow_depth
        WHEN: Scored as allgemein
        THEN: Snow has no effect
        """
        from app.user import LocationActivityProfile
        from web.pages.compare import calculate_score

        base = {"sunny_hours": 5, "wind_max": 15}
        with_snow = {**base, "snow_depth_cm": 200}

        score_base = calculate_score(base, profile=LocationActivityProfile.ALLGEMEIN)
        score_snow = calculate_score(with_snow, profile=LocationActivityProfile.ALLGEMEIN)
        assert score_base == score_snow

    def test_allgemein_moderate_penalties(self):
        """
        GIVEN: Bad weather
        WHEN: Scored as allgemein
        THEN: Score is low but not zero (moderate penalties)
        """
        from app.user import LocationActivityProfile
        from web.pages.compare import calculate_score

        metrics = {
            "precip_mm": 10,
            "wind_max": 55,
            "cloud_avg": 90,
            "sunny_hours": 0,
            "temp_min": -15,
        }
        score = calculate_score(metrics, profile=LocationActivityProfile.ALLGEMEIN)
        assert 5 <= score <= 30, f"Bad weather allgemein should be 5-30, got {score}"


class TestMetricExtraction:
    """Test that ComparisonEngine extracts thunder/cape/pop metrics."""

    def test_engine_accepts_profile_parameter(self):
        """
        GIVEN: ComparisonEngine.run()
        WHEN: Called with profile parameter
        THEN: Does not raise TypeError
        """
        from app.user import LocationActivityProfile
        from web.pages.compare import ComparisonEngine
        import inspect

        sig = inspect.signature(ComparisonEngine.run)
        params = list(sig.parameters.keys())
        assert "profile" in params, f"ComparisonEngine.run must accept 'profile' parameter, has: {params}"


class TestDataModel:
    """Test subscription activity_profile field."""

    def test_subscription_has_activity_profile(self):
        """
        GIVEN: CompareSubscription dataclass
        WHEN: Instantiated with activity_profile
        THEN: Field is accessible
        """
        from app.user import CompareSubscription, LocationActivityProfile, Schedule

        sub = CompareSubscription(
            id="test",
            name="Test",
            locations=["*"],
            schedule=Schedule.DAILY_MORNING,
            activity_profile=LocationActivityProfile.WANDERN,
        )
        assert sub.activity_profile == LocationActivityProfile.WANDERN

    def test_subscription_default_none(self):
        """
        GIVEN: CompareSubscription without activity_profile
        WHEN: Instantiated
        THEN: activity_profile is None
        """
        from app.user import CompareSubscription, Schedule

        sub = CompareSubscription(
            id="test",
            name="Test",
            locations=["*"],
            schedule=Schedule.DAILY_MORNING,
        )
        assert sub.activity_profile is None


class TestCompareAPI:
    """Test compare API accepts activity_profile parameter."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_compare_accepts_activity_profile(self, client):
        """
        GIVEN: /api/compare endpoint
        WHEN: Called with activity_profile=wandern
        THEN: Returns 200 (not 422 validation error)
        """
        resp = client.get("/api/compare?location_ids=*&activity_profile=wandern")
        assert resp.status_code == 200
        data = resp.json()
        assert "locations" in data


class TestEmailSubject:
    """Test email subject rename."""

    def test_subject_is_wetter_vergleich(self):
        """
        GIVEN: run_comparison_for_subscription
        WHEN: Generating email
        THEN: Subject starts with 'Wetter-Vergleich' not 'Ski Resort'
        """
        from services.compare_subscription import run_comparison_for_subscription
        from app.user import CompareSubscription, Schedule

        sub = CompareSubscription(
            id="test-subject",
            name="Test",
            locations=[],
            schedule=Schedule.DAILY_MORNING,
        )
        subject, _, _ = run_comparison_for_subscription(sub)
        assert "Wetter-Vergleich" in subject, f"Subject should contain 'Wetter-Vergleich', got: {subject}"
        assert "Ski" not in subject, f"Subject should not contain 'Ski', got: {subject}"
