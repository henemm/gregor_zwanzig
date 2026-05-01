"""
Golden tests for build_email_subject — TDD RED Phase β2.

Five canonical TokenLine profiles produce frozen subject strings.
Tests must FAIL with ModuleNotFoundError because src/output/subject.py
does not yet exist.

SPEC: docs/specs/modules/output_subject_filter.md v1.0
TEST INVENTORY: docs/specs/tests/output_subject_filter_tests.md v1.0
AUTHORITY: docs/reference/sms_format.md v2.0 §11

Profiles cover: standard summer trip, vigilance trip, wintersport trip,
short update, FR-vigilance trip with HR/TH fusion.
"""
from __future__ import annotations


from src.output.tokens.dto import Token, TokenLine

# WILL FAIL: subject.py does not yet exist
from src.output.subject import build_email_subject


def _tok(symbol: str, value: str, category: str = "forecast", priority: int = 4) -> Token:
    return Token(symbol=symbol, value=value, category=category, priority=priority)


# ---------------------------------------------------------------------------
# 5 canonical golden profiles
# ---------------------------------------------------------------------------


def test_golden_gr221_summer_morning():
    """GR221 Mallorca, summer morning, heat risk."""
    line = TokenLine(
        stage_name="Tag 3: Valldemossa → Sóller",
        report_type="morning",
        tokens=(
            _tok("D", "32"),
            _tok("W", "12"),
            _tok("G", "20"),
        ),
        main_risk="Heat",
        trip_name="GR221",
    )
    subject = build_email_subject(line)
    assert subject == "[GR221] Tag 3: Valldemossa → Sóller — Morgen — Hitze D32 W12 G20"


def test_golden_gr20_spring_evening_vigilance():
    """GR20 Corsica spring evening with FR vigilance HR+TH fusion."""
    line = TokenLine(
        stage_name="Étape 7: Vizzavona",
        report_type="evening",
        tokens=(
            _tok("D", "18"),
            _tok("W", "30@14"),
            _tok("G", "55@15"),
            _tok("HR", ":M@13", category="vigilance", priority=1),
            _tok("TH", ":H@14", category="vigilance", priority=1),
        ),
        main_risk="Storm",
        trip_name="GR20",
    )
    subject = build_email_subject(line)
    assert subject == "[GR20] Étape 7: Vizzavona — Abend — Sturm D18 W30@14 G55@15 HR:M@13TH:H@14"


def test_golden_arlberg_wintersport_update():
    """Wintersport update — snow risk, no whitelist tokens beyond D/W/G."""
    line = TokenLine(
        stage_name="Tag 2: Lech",
        report_type="update",
        tokens=(
            _tok("D", "-4"),
            _tok("W", "45"),
            _tok("G", "70"),
        ),
        main_risk="Snow",
        trip_name="Arlberg",
    )
    subject = build_email_subject(line)
    assert subject == "[Arlberg] Tag 2: Lech — Update — Schnee D-4 W45 G70"


def test_golden_corsica_fr_vigilance_morning():
    """Corsica with full vigilance fusion in morning report."""
    line = TokenLine(
        stage_name="E5: Vizzavona",
        report_type="morning",
        tokens=(
            _tok("D", "32"),
            _tok("W", "30"),
            _tok("G", "45"),
            _tok("HR", ":M@14", category="vigilance", priority=1),
            _tok("TH", ":H@17", category="vigilance", priority=1),
        ),
        main_risk="Thunder",
        trip_name="Corsica",
    )
    subject = build_email_subject(line)
    assert subject == "[Corsica] E5: Vizzavona — Morgen — Gewitter D32 W30 G45 HR:M@14TH:H@17"


def test_golden_gr221_short_update():
    """Short single-stage update, no MainRisk."""
    line = TokenLine(
        stage_name="Tag 1: Port d'Andratx → Esporles",
        report_type="update",
        tokens=(
            _tok("D", "26"),
            _tok("W", "08"),
            _tok("G", "15"),
        ),
        main_risk=None,
        trip_name="GR221",
    )
    subject = build_email_subject(line)
    # No MainRisk → no '— {risk}' segment
    assert subject == "[GR221] Tag 1: Port d'Andratx → Esporles — Update — D26 W08 G15"
