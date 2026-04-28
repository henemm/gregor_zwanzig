"""Channel-Renderer-Layer (β3 of Epic #96 Render-Pipeline-Konsolidierung).

SPEC: docs/specs/modules/output_channel_renderers.md v1.0

Re-exports:
  * render_email() - Pure function returning (html, plain) tuple.
  * render_sms()   - Wire-format wrapper over output.tokens.render.render_line.
"""
from __future__ import annotations

from src.output.renderers.email import render_email
from src.output.renderers.sms import render_sms

__all__ = ["render_email", "render_sms"]
