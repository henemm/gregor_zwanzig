"""Per-metric value calculation (Threshold + Peak) per sms_format.md §5.

Renderings:
    '{symbol}{thr}@{thr_h}({max}@{max_h})'   threshold + peak (default)
    '{symbol}{thr}@{thr_h}'                  Threshold == Max optimisation
    '{symbol}-'                              Null form
"""
from __future__ import annotations

from typing import Optional

from src.output.tokens.dto import HourlyValue

LEVELS = {0: "-", 1: "L", 2: "M", 3: "H"}


def _fmt_num(symbol: str, value: float) -> str:
    if symbol == "R":
        return f"{value:.1f}"
    if symbol == "PR":
        return f"{int(round(value))}%"
    return f"{int(round(value))}"


def _level(value: float) -> str:
    return LEVELS.get(int(round(value)), "-")


def render_threshold_peak_value(
    symbol: str, samples: tuple[HourlyValue, ...],
    threshold: Optional[float], *, is_level: bool = False,
) -> str:
    """Render value-tail per §5. '-' for null form."""
    if not samples:
        return "-"
    peak = max(samples, key=lambda s: (s.value, -s.hour))
    if peak.value <= 0:
        return "-"
    if threshold is None:
        first = peak
    else:
        first = next((s for s in sorted(samples, key=lambda s: s.hour)
                      if s.value >= threshold), None)
        if first is None:
            return "-"
    if is_level:
        f_str, p_str = _level(first.value), _level(peak.value)
    else:
        f_str, p_str = _fmt_num(symbol, first.value), _fmt_num(symbol, peak.value)
    if f_str == p_str and first.hour == peak.hour:
        return f"{f_str}@{first.hour}"
    return f"{f_str}@{first.hour}({p_str}@{peak.hour})"


def render_temperature(value: Optional[float]) -> str:
    return "-" if value is None else f"{int(round(value))}"


render_int = render_temperature
