"""
Tests fuer Issue #240 — Trip-Briefing-Mail auf Design-Tokens umstellen.

SPEC: docs/specs/modules/issue_240_email_design_tokens.md
TESTS-SPEC: docs/specs/tests/issue_240_email_design_tokens_tests.md
EPIC: #236 (Sub-Issue 3a)

RED-Zustand (jetzt):
  src/output/renderers/email/design_tokens.py existiert NICHT → ImportError.
  html.py enthaelt noch alte Hex-Werte → Assertion-Fails.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.unit.test_renderers_email import _common_kwargs, _make_token_line


REPO_ROOT = Path(__file__).resolve().parents[2]
HTML_PY = REPO_ROOT / "src" / "output" / "renderers" / "email" / "html.py"

OLD_HEX_LITERALS = [
    "#1976d2",   # alter Header-Gradient-Start, h3-Border
    "#42a5f5",   # alter Header-Gradient-Ende, Summary-Border
    "#fffde7",   # alter Daylight-BG
    "#f9a825",   # alter Daylight-Border
    "#fff3e0",   # alter Error-BG
    "#e65100",   # alter Error-Border + Text
    "#f0f7ff",   # alter Compact-Summary-BG
    "#fff8e1",   # alter Confidence-BG
    "#fbc02d",   # alter Confidence-Border
    "#f5f5f5",   # altes Body/Footer-Grau
    "#e3f2fd",   # alter Table-Header-BG
    "#90caf9",   # alter Table-Header-Border
]


# --- AC-1: Token-Modul exportiert alle Symbole ----------------------------

def test_ac1_design_tokens_surfaces():
    """AC-1: Surface-Tokens mit korrekten Hex-Werten."""
    from src.output.renderers.email.design_tokens import (
        G_PAPER, G_SURFACE_1, G_SURFACE_2,
    )
    assert G_PAPER == "#f6f4ee"
    assert G_SURFACE_1 == "#edeae1"
    assert G_SURFACE_2 == "#e3dfd4"


def test_ac1_design_tokens_ink():
    """AC-1: Ink-Stufen (Primaer/Sekundaer/Tertiaer)."""
    from src.output.renderers.email.design_tokens import (
        G_INK, G_INK_MUTED, G_INK_FAINT,
    )
    assert G_INK == "#1a1a18"
    assert G_INK_MUTED == "#5c5a52"
    assert G_INK_FAINT == "#9c9a90"


def test_ac1_design_tokens_brand_semantic():
    """AC-1: Brand (Accent) + Semantic-Quartett."""
    from src.output.renderers.email.design_tokens import (
        G_ACCENT, G_SUCCESS, G_WARNING, G_DANGER, G_INFO,
    )
    assert G_ACCENT == "#c45a2a"
    assert G_SUCCESS == "#3a7d44"
    assert G_WARNING == "#c8882a"
    assert G_DANGER == "#b33a2a"
    assert G_INFO == "#2a6cb3"


def test_ac1_design_tokens_box_tints():
    """AC-1: Mail-spezifische Box-Tints (Outlook-tauglich, kein Alpha)."""
    from src.output.renderers.email.design_tokens import (
        G_BOX_WARNING_BG, G_BOX_DANGER_BG, G_BOX_INFO_BG,
    )
    assert G_BOX_WARNING_BG == "#f4ecdd"
    assert G_BOX_DANGER_BG == "#f4dfd9"
    assert G_BOX_INFO_BG == "#dfe7f0"


def test_ac1_design_tokens_fonts():
    """AC-1 + AC-4: Font-Stacks und Web-Font-Link."""
    from src.output.renderers.email.design_tokens import (
        FONT_UI, FONT_DATA, WEB_FONT_LINK,
    )
    assert "Inter Tight" in FONT_UI
    assert "-apple-system" in FONT_UI
    assert "BlinkMacSystemFont" in FONT_UI
    assert "JetBrains Mono" in FONT_DATA
    assert "monospace" in FONT_DATA
    assert "fonts.googleapis.com" in WEB_FONT_LINK
    assert "Inter+Tight" in WEB_FONT_LINK
    assert "JetBrains+Mono" in WEB_FONT_LINK


# --- AC-2: html.py-Quelltext frei von alten Hex-Literalen -----------------

@pytest.mark.parametrize("hex_value", OLD_HEX_LITERALS)
def test_ac2_no_old_hex_in_html_source(hex_value):
    """
    AC-2: src/output/renderers/email/html.py darf keine alten Hex-Literale
    mehr enthalten — alles geht ueber design_tokens.py.
    """
    source = HTML_PY.read_text()
    pattern = re.escape(hex_value)
    matches = re.findall(pattern, source, flags=re.IGNORECASE)
    assert not matches, (
        f"Alter Hex-Wert {hex_value!r} ({len(matches)}x) noch in html.py — "
        f"durch design_tokens.py-Konstante ersetzen"
    )


# --- AC-3 / AC-4: Gerenderte Mail enthaelt neue Tokens ---------------------

def _render_minimal_html() -> str:
    from src.output.renderers.email import render_email
    token_line = _make_token_line()
    html, _ = render_email(token_line, **_common_kwargs())
    return html


def test_ac3_render_html_contains_accent():
    """
    AC-3: Gerenderte Mail enthaelt #c45a2a mehrfach (Header + h3-Border +
    Summary-Border).
    """
    html = _render_minimal_html()
    occurrences = html.lower().count("#c45a2a")
    assert occurrences >= 2, (
        f"#c45a2a (G_ACCENT) erscheint nur {occurrences}x — erwartet >=2"
    )


def test_ac3_render_html_paper_background():
    """AC-3: Paper-Hintergrund #f6f4ee statt grauem #f5f5f5."""
    html = _render_minimal_html().lower()
    assert "#f6f4ee" in html, "G_PAPER (#f6f4ee) fehlt im HTML"
    assert "#f5f5f5" not in html, "altes Grau #f5f5f5 noch im HTML"


def test_ac3_render_html_no_old_gradient():
    """AC-3: Weder #1976d2 noch #42a5f5 im gerenderten HTML."""
    html = _render_minimal_html().lower()
    assert "#1976d2" not in html, "altes Header-Blau #1976d2 noch im HTML"
    assert "#42a5f5" not in html, "altes Header-Hellblau #42a5f5 noch im HTML"


def test_ac4_render_html_inter_tight():
    """AC-4: Body-font-family enthaelt 'Inter Tight'."""
    html = _render_minimal_html()
    assert "Inter Tight" in html, "Inter Tight fehlt im font-family-Stack"


def test_ac4_render_html_jetbrains_mono():
    """AC-4: JetBrains Mono fuer Daten/Zahlen-Stellen."""
    html = _render_minimal_html()
    assert "JetBrains Mono" in html, (
        "JetBrains Mono fehlt — sollte fuer .metric-value/code-Elemente "
        "deklariert sein"
    )


def test_ac4_render_html_web_font_link():
    """AC-4: <head> enthaelt Google-Fonts-Link."""
    html = _render_minimal_html()
    assert "fonts.googleapis.com" in html, "Web-Font-Link im <head> fehlt"
    assert "Inter+Tight" in html


# --- AC-5: Real-Gmail-Test (opt-in via @pytest.mark.email) ----------------

@pytest.mark.email
def test_ac5_real_gmail_briefing_tokens():
    """
    AC-5: Real-Gmail-Versand einer Trip-Briefing-Mail, IMAP-Abruf, Body
    enthaelt #c45a2a + 'Inter Tight' und keine Alt-Werte.

    Laeuft nur mit `pytest -m email tests/tdd/test_email_design_tokens.py`.
    Default deselected (Gmail-API-Latenz/Quota).
    """
    import email as email_mod
    import imaplib
    import smtplib
    import time
    import uuid
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    from app.config import Settings

    settings = Settings().for_testing()

    html = _render_minimal_html()

    marker = uuid.uuid4().hex[:12]
    subject = f"[GZ-TOKENS-{marker}] Trip-Briefing-Test"

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.smtp_user
    msg["To"] = settings.smtp_user
    msg["Subject"] = subject
    msg.attach(MIMEText("Plain-Text-Fallback fuer #240-Test", "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_pass)
        smtp.send_message(msg)

    html_body = None
    with imaplib.IMAP4_SSL(settings.imap_host, 993) as imap:
        imap.login(settings.imap_user, settings.imap_pass)
        imap.select("INBOX")
        for _ in range(30):
            _, data = imap.search(None, f'(SUBJECT "{marker}")')
            if data[0]:
                break
            time.sleep(1)
        else:
            pytest.fail(f"Mail mit Marker {marker} nicht in IMAP gefunden")

        ids = data[0].split()
        _, raw = imap.fetch(ids[-1], "(RFC822)")
        message = email_mod.message_from_bytes(raw[0][1])

        for part in message.walk():
            if part.get_content_type() == "text/html":
                html_body = part.get_payload(decode=True).decode(
                    "utf-8", errors="ignore"
                )
                break

    assert html_body is not None, "Kein HTML-Part in der empfangenen Mail"
    assert "#c45a2a" in html_body.lower(), "G_ACCENT fehlt in empfangener Mail"
    assert "Inter Tight" in html_body, "Inter Tight fehlt in empfangener Mail"
    assert "#1976d2" not in html_body.lower(), "Alt-Blau noch in Mail"
    assert "<!doctype" in html_body.lower(), "DOCTYPE fehlt"
    assert "<table" in html_body.lower(), "<table> fehlt"
