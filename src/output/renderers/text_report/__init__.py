"""Text-Report Renderer (β4, profile-agnostic plain-ASCII long report).

SPEC: docs/specs/modules/wintersport_profile_consolidation.md §4.2, §A4, §A5.

Pure function. Identical inputs -> bit-identical output. Reads `profile`
implicitly via the `token_line` (profile-agnostic per §A5).
"""
from __future__ import annotations

from src.output.renderers.sms import render_sms
from src.output.tokens.dto import ReportType, TokenLine

# Imported lazily inside the renderer to avoid a hard dependency on the
# adapter at import time (TokenLine itself does not need WaypointDetail).
from src.output.adapters.trip_result import WaypointDetail

_SEP = "=" * 60
_SUBSEP = "-" * 44


def _format_waypoint(d: WaypointDetail) -> list[str]:
    """Render one waypoint block (header + indented detail lines)."""
    tw = f"{d.time_window} " if d.time_window else ""
    out = [f"  {tw}{d.id} {d.name} ({d.elevation_m}m)"]
    for line in d.lines:
        out.append(f"               {line}")
    out.append("")
    return out


def render_text_report(
    token_line: TokenLine,
    *,
    waypoint_details: list[WaypointDetail],
    summary_rows: list[tuple[str, str]],
    avalanche_regions: tuple[str, ...] = (),
    report_type: ReportType,
    trip_name: str,
    trip_date: str,
) -> str:
    """Render a long-form plain-ASCII trip report (β4 §A4).

    Sections (in order):
      - Header (trip name UPPERCASE, date, report type)
      - Token line (render_sms output) — pipeline-SSOT manifest
      - ZUSAMMENFASSUNG (summary rows)
      - WEGPUNKT-DETAILS (per-waypoint blocks)
      - LAWINENREGIONEN (only if `avalanche_regions` is non-empty)

    Pure function. Profile-agnostic — `profile` lives inside `token_line`.
    """
    lines: list[str] = []

    lines.append(_SEP)
    lines.append(f"  {trip_name.upper()} - {trip_date}")
    lines.append(f"  {report_type.title()} Report")
    lines.append(_SEP)
    lines.append("")

    # Token line as pipeline-SSOT marker (Spec §A4 NEU).
    lines.append(render_sms(token_line))
    lines.append("")

    lines.append("ZUSAMMENFASSUNG")
    lines.append(_SUBSEP)
    for label, value in summary_rows:
        lines.append(f"  {label + ':':<16}{value}")
    lines.append("")

    lines.append("WEGPUNKT-DETAILS")
    lines.append(_SUBSEP)
    for d in waypoint_details:
        lines.extend(_format_waypoint(d))

    if avalanche_regions:
        lines.append("LAWINENREGIONEN")
        lines.append(_SUBSEP)
        for region in avalanche_regions:
            lines.append(f"  Region: {region}")
        lines.append("  (Lawinendaten noch nicht implementiert)")
        lines.append("")

    lines.append(_SEP)

    return "\n".join(lines)


__all__ = ["render_text_report"]
