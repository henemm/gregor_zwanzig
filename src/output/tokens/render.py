"""Render TokenLine to wire format with HR/TH fusion + §6 truncation."""
from __future__ import annotations

import re
from dataclasses import replace

from src.output.tokens.dto import Token, TokenLine

# §6 removal order (one symbol at a time, repeated until budget met).
DROP_ORDER = ["DBG", "WC", "AV", "SFL", "SN24+", "SN", "Z:", "MAX", "M:"]


def _fuse(tokens: list[Token]) -> list[str]:
    parts: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if (t.symbol == "HR:" and t.category == "vigilance"
                and i + 1 < len(tokens)
                and tokens[i + 1].symbol == "TH:"
                and tokens[i + 1].category == "vigilance"):
            parts.append(f"{t.render()}{tokens[i + 1].render()}")
            i += 2
        else:
            parts.append(t.render())
            i += 1
    return parts


def _draw(stage: str, tokens: list[Token]) -> str:
    return f"{stage}: " + " ".join(_fuse(tokens))


def _drop_first(tokens: list[Token], symbol: str) -> bool:
    for i, t in enumerate(tokens):
        if t.symbol == symbol:
            del tokens[i]
            return True
    return False


def _strip_peaks(tokens: list[Token]) -> bool:
    changed = False
    for i, t in enumerate(tokens):
        if t.category == "forecast" and "(" in t.value:
            tokens[i] = replace(t, value=re.sub(r"\([^)]*\)", "", t.value))
            changed = True
    return changed


def _truncate(tokens: list[Token], stage: str, mx: int) -> tuple[list[Token], bool]:
    if len(_draw(stage, tokens)) <= mx:
        return tokens, False
    truncated = False
    for sym in DROP_ORDER:
        while _drop_first(tokens, sym):
            truncated = True
            if len(_draw(stage, tokens)) <= mx:
                return tokens, True
    if _strip_peaks(tokens):
        truncated = True
        if len(_draw(stage, tokens)) <= mx:
            return tokens, True
    while _drop_first(tokens, "PR"):
        truncated = True
        if len(_draw(stage, tokens)) <= mx:
            return tokens, True
    for sym in ("D", "N"):
        if _drop_first(tokens, sym):
            truncated = True
            if len(_draw(stage, tokens)) <= mx:
                return tokens, True
    # Last resort: drop forecast/vigilance tokens by ascending priority.
    while len([t for t in tokens
               if t.category in ("forecast", "vigilance")]) > 1:
        cand = sorted(
            [t for t in tokens if t.category in ("forecast", "vigilance")],
            key=lambda t: t.priority,
        )[0]
        _drop_first(tokens, cand.symbol)
        truncated = True
        if len(_draw(stage, tokens)) <= mx:
            return tokens, True
    if len(_draw(stage, tokens)) > mx:
        raise ValueError(
            f"Cannot truncate token line below {mx} characters; "
            f"current length {len(_draw(stage, tokens))}"
        )
    return tokens, truncated


def render_line(line: TokenLine, max_length: int) -> str:
    """Render with §6 truncation if needed. Mutates frozen DTO via setattr."""
    tokens = list(line.tokens)
    full = _draw(line.stage_name, tokens)
    object.__setattr__(line, "full_length", len(full))
    if len(full) <= max_length:
        return full
    truncated_tokens, was = _truncate(tokens, line.stage_name, max_length)
    object.__setattr__(line, "truncated", was)
    return _draw(line.stage_name, truncated_tokens)
