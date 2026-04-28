"""SMS Channel Renderer (β3, sms_format.md v2.0 §2/§3).

SPEC: docs/specs/modules/output_channel_renderers.md §A3 + 'render_sms() Signatur'.
"""
from __future__ import annotations

from src.output.tokens.dto import TokenLine
from src.output.tokens.render import render_line


def render_sms(token_line: TokenLine, max_length: int = 160) -> str:
    """Render TokenLine to SMS wire-format ≤max_length per sms_format.md v2.0.

    Pure delegation to output.tokens.render.render_line() (β1 authority).
    Exists as channel wrapper for API symmetry with render_email().

    Determinism: identical TokenLine + max_length → bit-identical output.
    """
    return render_line(token_line, max_length)


__all__ = ["render_sms"]
