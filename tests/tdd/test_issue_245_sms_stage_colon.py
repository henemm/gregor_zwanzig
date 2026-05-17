"""TDD RED Tests — Issue #245: Leerzeichen vor Prefix-Separator wenn Stage-Name Doppelpunkt enthält.

Spec: docs/specs/modules/issue_245_sms_prefix_separator.md

Root-Cause:
  preview_service.py entfernt ':' via .replace(":", ""), aber der nachfolgende Leerzeichen
  verbleibt und landet nach 10-Char-Truncation in _sanitize_stage_name als trailing Space.

  Beispiel: "Tag 1: von Valldemossa nach Deià"
    → .replace(":", "") → "Tag 1 von Valldemossa nach Deià"
    → _sanitize_stage_name → [:10] → "Tag 1 von " (trailing Space!)
    → token_line: "Tag 1 von : N12 D24 ..." (Space vor Separator)

Fix (2 Stellen):
  1. _sanitize_stage_name in builder.py: [:10].strip()
  2. preview_service.py: .replace(":", "").strip() (Defense-in-Depth)
"""
import pytest

from src.output.tokens.builder import _sanitize_stage_name, build_token_line
from src.output.tokens.dto import DailyForecast, NormalizedForecast


def _minimal_forecast() -> NormalizedForecast:
    """Minimal valid NormalizedForecast für Builder-Tests."""
    day = DailyForecast(temp_min_c=12.0, temp_max_c=24.0)
    return NormalizedForecast(days=(day,))


class TestAC1SanitizeStageName:
    """AC-1: _sanitize_stage_name darf keinen trailing/leading Whitespace zurückgeben.

    Das ist die Root-Cause: [:10] schneidet einen Space mit, wenn der Name
    nach Colon-Entfernung an Position 10 einen Space hat.
    """

    def test_no_trailing_space_after_truncation(self):
        """GIVEN Stage-Name der nach Colon-Entfernung 11+ Zeichen hat und an Position 10
        einen Space trägt WHEN _sanitize_stage_name aufgerufen THEN kein trailing Space.

        "Tag 1 von Valldemossa nach Deià"
          T(0)a(1)g(2) (3)1(4) (5)v(6)o(7)n(8) (9)V(10)...
          [:10] = "Tag 1 von " — Position 9 ist ein Space!
        """
        cleaned = "Tag 1 von Valldemossa nach Deià"
        result = _sanitize_stage_name(cleaned)
        assert not result.endswith(" "), (
            f"_sanitize_stage_name darf keinen trailing Space zurückgeben, "
            f"war: {result!r}"
        )

    def test_no_leading_space_after_truncation(self):
        """GIVEN Stage-Name mit führendem Space (nach Colon-Entfernung am Anfang)
        WHEN _sanitize_stage_name aufgerufen THEN kein leading Space.
        """
        cleaned = " von Valldemossa nach Deià"
        result = _sanitize_stage_name(cleaned)
        assert not result.startswith(" "), (
            f"_sanitize_stage_name darf keinen leading Space zurückgeben, "
            f"war: {result!r}"
        )

    def test_normal_name_unchanged(self):
        """GIVEN normaler Stage-Name ohne Sonderzeichen (kein Doppelpunkt)
        WHEN _sanitize_stage_name aufgerufen THEN unverändertes Ergebnis (kein Regression).
        """
        result = _sanitize_stage_name("GR20 E1")
        assert result == "GR20 E1", f"Normaler Name soll unverändert bleiben, war: {result!r}"


class TestAC1BuildTokenLine:
    """AC-1: build_token_line darf kein ' :' (Space vor Separator-Doppelpunkt) im Output haben.

    Token-Line-Format: "{StageName}: {tokens}" — wenn StageName trailing Space hat,
    entsteht "StageName : tokens" (Space vor ':').
    """

    def test_stage_name_with_space_at_truncation_boundary_no_space_before_colon(self):
        """GIVEN stage_name dessen 10-Char-Truncation auf einen Space endet
        WHEN build_token_line aufgerufen
        THEN enthält render() kein ' :' (kein Space vor Separator-Doppelpunkt).

        Simulation: "Tag 1 von Valldemossa nach Deià" ist das Ergebnis von
        "Tag 1: von Valldemossa nach Deià".replace(":", "") in preview_service.py.
        """
        forecast = _minimal_forecast()
        token_line = build_token_line(
            forecast,
            None,
            report_type="morning",
            stage_name="Tag 1 von Valldemossa nach Deià",
        )
        rendered = token_line.render()
        assert " :" not in rendered, (
            f"token_line darf keinen Space vor ':' enthalten (Issue #245), "
            f"war: {rendered!r}"
        )

    def test_stage_name_with_leading_space_no_space_after_first_colon(self):
        """GIVEN stage_name mit führendem Space (nach Colon-Entfernung am Anfang)
        WHEN build_token_line aufgerufen
        THEN beginnt render() nicht mit einem Space.
        """
        forecast = _minimal_forecast()
        token_line = build_token_line(
            forecast,
            None,
            report_type="morning",
            stage_name=" von Valldemossa nach Deià",
        )
        rendered = token_line.render()
        assert not rendered.startswith(" "), (
            f"token_line darf nicht mit Space beginnen, war: {rendered!r}"
        )


class TestAC2Regression:
    """AC-2: Normale Stage-Namen (ohne Doppelpunkt) zeigen kein verändertes Verhalten."""

    def test_normal_stage_name_has_correct_colon_prefix(self):
        """GIVEN stage_name ohne Doppelpunkt
        WHEN build_token_line aufgerufen
        THEN beginnt render() mit 'StageName: ' (kein zusätzlicher Space).
        """
        forecast = _minimal_forecast()
        token_line = build_token_line(
            forecast,
            None,
            report_type="morning",
            stage_name="GR20 E1",
        )
        rendered = token_line.render()
        assert rendered.startswith("GR20 E1: "), (
            f"Normaler Stage-Name soll unverändert als Prefix erscheinen, war: {rendered!r}"
        )
        assert " :" not in rendered, (
            f"Normaler Stage-Name darf kein ' :' im Output haben, war: {rendered!r}"
        )

    @pytest.mark.parametrize("name", ["Etappe", "GR20", "Tag 1", "Mallorca"])
    def test_short_names_no_trailing_space(self, name: str):
        """GIVEN kurze Stage-Namen (≤10 Zeichen, kein Doppelpunkt)
        WHEN _sanitize_stage_name aufgerufen
        THEN kein trailing Space im Ergebnis.
        """
        result = _sanitize_stage_name(name)
        assert not result.endswith(" "), (
            f"Kurzer Name {name!r} darf keinen trailing Space haben, war: {result!r}"
        )
