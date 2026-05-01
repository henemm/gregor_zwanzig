"""
Unit tests for src/output/subject.py — TDD RED Phase β2.

Tests must FAIL with ModuleNotFoundError because src/output/subject.py
does not yet exist, AND with TypeError because TokenLine does not yet
have main_risk / trip_name fields.

SPEC: docs/specs/modules/output_subject_filter.md v1.0
TEST INVENTORY: docs/specs/tests/output_subject_filter_tests.md v1.0
AUTHORITY: docs/reference/sms_format.md v2.0 §11

Critical rules from spec (A1-A6):
- Format: '[{trip}] {stage_name} — {report_type_de} — {main_risk} D... W... G... TH:...'
- ReportType DE: morning→Morgen, evening→Abend, update→Update
- MainRisk DE: Thunder→Gewitter, Storm→Sturm, Heat→Hitze, ...
- Whitelist: only D, W, G, TH: (Vigilance), HR: (Vigilance) — others dropped
- Truncation 78 chars: drop HR:/TH: → G → W → D → trip prefix; never stage_name
- HR:/TH: Vigilance pair fused without space: 'HR:M@13TH:H@14'
"""
from __future__ import annotations


from src.output.tokens.dto import Token, TokenLine

# WILL FAIL: subject.py does not yet exist
from src.output.subject import build_email_subject


def _tok(symbol: str, value: str, category: str = "forecast", priority: int = 4) -> Token:
    """Convenience constructor for Token tuples in tests."""
    return Token(symbol=symbol, value=value, category=category, priority=priority)


# ---------------------------------------------------------------------------
# A1 + A2: Basic format and ReportType-DE labels
# ---------------------------------------------------------------------------


def test_subject_basic_format():
    """
    GIVEN: TokenLine with trip_name, stage_name, report_type=morning, main_risk=Thunder, no tokens
    WHEN: build_email_subject is called
    THEN: Subject is '[GR221] Tag 1 — Morgen — Gewitter'
    """
    line = TokenLine(
        stage_name="Tag 1",
        report_type="morning",
        tokens=(),
        main_risk="Thunder",
        trip_name="GR221",
    )
    subject = build_email_subject(line)
    assert subject == "[GR221] Tag 1 — Morgen — Gewitter"


def test_subject_german_report_type_labels():
    """
    GIVEN: TokenLine with each in-scope report_type
    WHEN: build_email_subject is called
    THEN: Subject contains German label
    """
    base = dict(stage_name="Tag 1", tokens=(), main_risk="Storm", trip_name="GR221")

    morning = build_email_subject(TokenLine(**base, report_type="morning"))
    evening = build_email_subject(TokenLine(**base, report_type="evening"))
    update = build_email_subject(TokenLine(**base, report_type="update"))

    assert "— Morgen —" in morning, f"expected 'Morgen' in {morning!r}"
    assert "— Abend —" in evening, f"expected 'Abend' in {evening!r}"
    assert "— Update —" in update, f"expected 'Update' in {update!r}"


def test_subject_main_risk_german():
    """
    GIVEN: TokenLine with main_risk='Thunder' (English from RiskEngine)
    WHEN: build_email_subject is called
    THEN: Subject contains 'Gewitter' (German), not 'Thunder'
    """
    line = TokenLine(
        stage_name="Tag 1",
        report_type="morning",
        tokens=(),
        main_risk="Thunder",
        trip_name="GR221",
    )
    subject = build_email_subject(line)
    assert "Gewitter" in subject, f"expected 'Gewitter' in {subject!r}"
    assert "Thunder" not in subject, f"'Thunder' should be translated, got {subject!r}"


# ---------------------------------------------------------------------------
# A4: Whitelist enforcement
# ---------------------------------------------------------------------------


def test_subject_with_weather_tokens():
    """
    GIVEN: TokenLine with D, W, G whitelist tokens
    WHEN: build_email_subject is called
    THEN: Tokens appear in whitelist order (D → W → G), space-separated
    """
    line = TokenLine(
        stage_name="Tag 3",
        report_type="morning",
        tokens=(
            _tok("D", "24"),
            _tok("W", "15"),
            _tok("G", "30"),
        ),
        main_risk="Thunder",
        trip_name="GR221",
    )
    subject = build_email_subject(line)
    assert subject.endswith("D24 W15 G30"), f"expected weather tail, got {subject!r}"


def test_subject_drops_non_whitelisted_tokens():
    """
    GIVEN: TokenLine with N, R, PR, TH+ tokens (non-whitelist)
    WHEN: build_email_subject is called
    THEN: None of N/R/PR/TH+ appear in subject
    """
    line = TokenLine(
        stage_name="Tag 1",
        report_type="morning",
        tokens=(
            _tok("N", "14"),  # Nacht-Min — not in whitelist
            _tok("D", "24"),  # whitelist
            _tok("R", "0.2@6"),  # Regen — not in whitelist
            _tok("PR", "40@11"),  # Regenwahrscheinlichkeit — not in whitelist
            _tok("TH+", "H@14"),  # Forecast-Thunder morgen — not in whitelist
        ),
        main_risk="Thunder",
        trip_name="GR221",
    )
    subject = build_email_subject(line)

    for forbidden in ("N14", "R0.2", "PR40", "TH+"):
        assert forbidden not in subject, f"'{forbidden}' must NOT appear in subject, got {subject!r}"
    assert "D24" in subject, f"'D24' must appear in subject, got {subject!r}"


def test_subject_hr_th_vigilance_fusion():
    """
    GIVEN: TokenLine with HR (vigilance) and TH: (vigilance) tokens
    WHEN: build_email_subject is called
    THEN: Tokens are fused without space: 'HR:M@13TH:H@14'
    """
    line = TokenLine(
        stage_name="Étape 7",
        report_type="evening",
        tokens=(
            _tok("D", "18"),
            _tok("HR", ":M@13", category="vigilance", priority=1),
            _tok("TH", ":H@14", category="vigilance", priority=1),
        ),
        main_risk="Storm",
        trip_name="GR20",
    )
    subject = build_email_subject(line)

    assert "HR:M@13TH:H@14" in subject, (
        f"vigilance pair must be fused without space, got {subject!r}"
    )
    assert "HR:M@13 TH:H@14" not in subject, (
        f"vigilance pair must NOT have space between HR and TH, got {subject!r}"
    )


# ---------------------------------------------------------------------------
# A5: Truncation
# ---------------------------------------------------------------------------


def test_subject_truncation_to_78_drops_weather_first():
    """
    GIVEN: TokenLine that produces a subject > 78 chars
    WHEN: build_email_subject is called with default max_length=78
    THEN: Weather tokens are dropped in order HR:/TH: → G → W → D until ≤78
    """
    line = TokenLine(
        stage_name="Tag 3: Valldemossa → Sóller via Pass",
        report_type="morning",
        tokens=(
            _tok("D", "24"),
            _tok("W", "15"),
            _tok("G", "30"),
            _tok("HR", ":M@13", category="vigilance", priority=1),
            _tok("TH", ":H@14", category="vigilance", priority=1),
        ),
        main_risk="Thunder",
        trip_name="GR221",
    )
    subject = build_email_subject(line)

    assert len(subject) <= 78, f"subject must be ≤78 chars, got {len(subject)}: {subject!r}"
    if len(subject) < 78:
        assert "HR:" not in subject or "G30" not in subject, (
            f"vigilance should be dropped before D/W, got {subject!r}"
        )


def test_subject_truncation_keeps_stage_name_intact():
    """
    GIVEN: TokenLine with very long stage_name (>78 chars alone)
    WHEN: build_email_subject is called
    THEN: stage_name is NEVER truncated; trip prefix may be dropped instead
    """
    long_stage = "Tag 14: Refuge d'Asco → Bergerie de Ballone via Cirque de la Solitude"
    line = TokenLine(
        stage_name=long_stage,
        report_type="morning",
        tokens=(
            _tok("D", "24"),
            _tok("W", "15"),
            _tok("G", "30"),
        ),
        main_risk="Thunder",
        trip_name="GR20",
    )
    subject = build_email_subject(line)

    assert long_stage in subject, (
        f"stage_name must remain intact, expected {long_stage!r} in {subject!r}"
    )


# ---------------------------------------------------------------------------
# A1: Trip prefix optional
# ---------------------------------------------------------------------------


def test_subject_no_trip_prefix_when_trip_name_none():
    """
    GIVEN: TokenLine with trip_name=None
    WHEN: build_email_subject is called
    THEN: Subject does NOT start with '[' (no trip prefix)
    """
    line = TokenLine(
        stage_name="Tag 1",
        report_type="morning",
        tokens=(),
        main_risk="Thunder",
        trip_name=None,
    )
    subject = build_email_subject(line)

    assert not subject.startswith("["), (
        f"subject must not have trip prefix when trip_name=None, got {subject!r}"
    )
    assert subject.startswith("Tag 1"), f"subject must start with stage_name, got {subject!r}"


# ---------------------------------------------------------------------------
# Validator-Finding HIGH (2026-04-27): trailing dangling " — "
# ---------------------------------------------------------------------------


def test_subject_no_trailing_dash_when_no_risk_and_no_tokens():
    """
    GIVEN: TokenLine with main_risk=None AND tokens=()
    WHEN: build_email_subject is called
    THEN: Subject must NOT end with a dangling em-dash ' — '
          (validator finding 2026-04-27, mail_712.eml)
    """
    line = TokenLine(
        stage_name="Tag 1: Pollença → Lluc",
        report_type="evening",
        tokens=(),
        main_risk=None,
        trip_name="VALIDATOR β2 Test",
    )
    subject = build_email_subject(line)

    assert not subject.endswith(" —"), (
        f"subject must not end with dangling em-dash, got {subject!r}"
    )
    assert not subject.endswith("— "), (
        f"subject must not end with em-dash + space, got {subject!r}"
    )
    assert subject.endswith("Abend"), (
        f"subject should end with the report type label when no risk/tokens, got {subject!r}"
    )
