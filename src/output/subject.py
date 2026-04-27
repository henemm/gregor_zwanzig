"""E-Mail Subject Filter — sms_format.md §11.

β2 of Epic #96 (Render-Pipeline-Konsolidierung).
Spec: docs/specs/modules/output_subject_filter.md v1.0

Format:
  [{trip_name}] {stage_name} — {ReportType-DE} — {MainRisk-DE} D... W... G... TH:.../HR:...

The subject is a pure filter over a TokenLine DTO — same source as the SMS/Push
renderer. No parallel data fetching, no side effects, deterministic.
"""
from __future__ import annotations

from src.output.tokens.dto import Token, TokenLine

# A2: ReportType-Mapping (English internal -> German label).
_REPORT_TYPE_DE: dict[str, str] = {
    "morning": "Morgen",
    "evening": "Abend",
    "update": "Update",
    # 'compare' deliberately not in scope (β5).
}

# A3: MainRisk-Mapping (English from RiskEngine -> German label).
# Unknown labels are passed through as-is (fail-soft).
_RISK_DE: dict[str, str] = {
    "Thunder": "Gewitter",
    "Storm": "Sturm",
    "Heat": "Hitze",
    "Cold": "Kälte",
    "Rain": "Regen",
    "Snow": "Schnee",
    "Wind": "Wind",
}

# A4: Whitelist for subject (in display order).
_WHITELIST_FORECAST: tuple[str, ...] = ("D", "W", "G")
_VIGILANCE_HR = "HR"
_VIGILANCE_TH = "TH"

DEFAULT_MAX_LENGTH = 78
_DASH = "—"  # em dash separator


def _translate_risk(risk: str | None) -> str | None:
    if risk is None:
        return None
    return _RISK_DE.get(risk, risk)


def _report_type_label(report_type: str) -> str:
    return _REPORT_TYPE_DE.get(report_type, report_type)


def _whitelisted_forecast_tokens(tokens: tuple[Token, ...]) -> dict[str, Token]:
    """Pick only forecast-category tokens with whitelisted symbols."""
    out: dict[str, Token] = {}
    for tok in tokens:
        if tok.category == "forecast" and tok.symbol in _WHITELIST_FORECAST:
            out[tok.symbol] = tok
    return out


def _vigilance_pair(tokens: tuple[Token, ...]) -> tuple[Token | None, Token | None]:
    """Return (HR, TH) vigilance tokens (category='vigilance')."""
    hr: Token | None = None
    th: Token | None = None
    for tok in tokens:
        if tok.category != "vigilance":
            continue
        if tok.symbol == _VIGILANCE_HR:
            hr = tok
        elif tok.symbol == _VIGILANCE_TH:
            th = tok
    return hr, th


def _render_token(tok: Token) -> str:
    """Render a token: 'D24', 'HR:M@13', 'TH:H@14'.

    Vigilance tokens have value starting with ':' (e.g. ':M@13').
    Forecast tokens have value like '24' or '30@14'.
    """
    return f"{tok.symbol}{tok.value}"


def _build_skeleton(
    *,
    trip_name: str | None,
    stage_name: str,
    report_de: str,
    risk_de: str | None,
) -> str:
    """Build the non-token prefix: '[trip] stage — report — risk'.

    If risk is None, the risk segment is omitted but the trailing dash stays
    so the subject reads '... — Update — D...' (per golden test).
    """
    head = f"[{trip_name}] {stage_name}" if trip_name else stage_name
    if risk_de:
        return f"{head} {_DASH} {report_de} {_DASH} {risk_de}"
    return f"{head} {_DASH} {report_de} {_DASH}"


def _join_with_tokens(skeleton: str, token_strs: list[str]) -> str:
    """Append space-joined tokens to skeleton (single space separator)."""
    if not token_strs:
        return skeleton
    return f"{skeleton} {' '.join(token_strs)}"


def _build_token_strings(
    fc_map: dict[str, Token],
    vigilance: str | None,
    *,
    keep_d: bool = True,
    keep_w: bool = True,
    keep_g: bool = True,
    keep_vigilance: bool = True,
) -> list[str]:
    """Assemble token strings in whitelist order: D -> W -> G -> [HR:TH:]."""
    out: list[str] = []
    if keep_d and "D" in fc_map:
        out.append(_render_token(fc_map["D"]))
    if keep_w and "W" in fc_map:
        out.append(_render_token(fc_map["W"]))
    if keep_g and "G" in fc_map:
        out.append(_render_token(fc_map["G"]))
    if keep_vigilance and vigilance:
        out.append(vigilance)
    return out


def build_email_subject(
    token_line: TokenLine, *, max_length: int = DEFAULT_MAX_LENGTH
) -> str:
    """Build the E-Mail subject as a filter over TokenLine (sms_format.md §11).

    Format:
      [{trip}] {stage_name} — {report_de} — {risk_de} D{val} W{val} G{val} HR:..TH:..

    Truncation order (A5): drop HR:/TH: -> G -> W -> D -> trip prefix.
    Stage name is NEVER truncated.

    Note: 'D' here is Tag-Max temperature (NOT debug).
    """
    risk_de = _translate_risk(token_line.main_risk)
    report_de = _report_type_label(token_line.report_type)
    fc_map = _whitelisted_forecast_tokens(token_line.tokens)
    hr_tok, th_tok = _vigilance_pair(token_line.tokens)

    # A4: HR/TH fusion — render as one block without space.
    vigilance_block: str | None = None
    if hr_tok and th_tok:
        vigilance_block = f"{_render_token(hr_tok)}{_render_token(th_tok)}"
    elif hr_tok:
        vigilance_block = _render_token(hr_tok)
    elif th_tok:
        vigilance_block = _render_token(th_tok)

    # Truncation cascade (A5). Order: HR/TH -> G -> W -> D -> trip prefix.
    truncation_steps: list[dict] = [
        {"trip": True,  "v": True,  "g": True,  "w": True,  "d": True},
        {"trip": True,  "v": False, "g": True,  "w": True,  "d": True},
        {"trip": True,  "v": False, "g": False, "w": True,  "d": True},
        {"trip": True,  "v": False, "g": False, "w": False, "d": True},
        {"trip": True,  "v": False, "g": False, "w": False, "d": False},
        {"trip": False, "v": False, "g": False, "w": False, "d": False},
    ]
    last: str = ""
    for step in truncation_steps:
        skeleton = _build_skeleton(
            trip_name=token_line.trip_name if step["trip"] else None,
            stage_name=token_line.stage_name,
            report_de=report_de,
            risk_de=risk_de,
        )
        token_strs = _build_token_strings(
            fc_map,
            vigilance_block,
            keep_d=step["d"],
            keep_w=step["w"],
            keep_g=step["g"],
            keep_vigilance=step["v"],
        )
        candidate = _join_with_tokens(skeleton, token_strs)
        last = candidate
        if len(candidate) <= max_length:
            return candidate

    # A5 §4: even after dropping all weather + trip prefix, still > max_length.
    # Stage name stays intact; mail client truncates visually.
    return last
