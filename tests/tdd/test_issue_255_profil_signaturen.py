"""
TDD RED — Issue #255: Profil-Signaturen: CAPS-Eyebrows, Inline-SVG-Icons, Paper-Header.

SPEC: docs/specs/modules/issue_255_email_profil_signaturen.md

RED-Zustand (jetzt):
  - ProfileSignature hat kein icon_html-Feld → AttributeError
  - eyebrow-Werte sind alt ('Wintersport' statt 'WINTERSPORT · PISTE' etc.)
  - render_html setzt Header-BG auf sig.accent_hex, nicht G_PAPER (#f6f4ee)
  - render_html-Eyebrow nutzt color:#ffffff statt G_ACCENT (#c45a2a)
"""
from __future__ import annotations

import pytest

from app.profile import ActivityProfile
from tests.unit.test_renderers_email import _common_kwargs, _make_token_line

# Token-Konstanten für lesbare Assertions
G_PAPER_HEX = "#f6f4ee"
G_ACCENT_HEX = "#c45a2a"


# ── AC-1: icon_html-Feld existiert + ist valides SVG ─────────────────────────

@pytest.mark.parametrize("profile,expected_color", [
    (ActivityProfile.WINTERSPORT,     "#4a7fb5"),
    (ActivityProfile.WANDERN,         "#3a7d44"),
    (ActivityProfile.SUMMER_TREKKING, "#c45a2a"),
    (ActivityProfile.ALLGEMEIN,       "#6b675c"),
])
def test_ac1_255_icon_html_is_valid_svg(profile, expected_color):
    """AC-1: Jedes Profil hat icon_html mit validem inline-SVG in Profil-Akzentfarbe."""
    from src.output.renderers.email.profile_signature import profile_signature
    sig = profile_signature(profile)
    assert hasattr(sig, "icon_html"), (
        f"ProfileSignature hat kein icon_html-Feld für {profile.value}"
    )
    assert sig.icon_html.startswith("<svg"), (
        f"{profile.value}: icon_html muss mit <svg beginnen, bekommen: {sig.icon_html[:30]!r}"
    )
    assert sig.icon_html.endswith("</svg>"), (
        f"{profile.value}: icon_html muss mit </svg> enden"
    )
    assert 'xmlns="http://www.w3.org/2000/svg"' in sig.icon_html, (
        f"{profile.value}: xmlns fehlt im SVG (Gmail-Pflicht)"
    )
    assert expected_color in sig.icon_html, (
        f"{profile.value}: Profil-Akzentfarbe {expected_color} fehlt im SVG"
    )


# ── AC-1: Neue CAPS-Eyebrow-Texte ────────────────────────────────────────────

@pytest.mark.parametrize("profile,expected_eyebrow", [
    (ActivityProfile.WINTERSPORT,     "WINTERSPORT · PISTE"),
    (ActivityProfile.WANDERN,         "WANDERN"),
    (ActivityProfile.SUMMER_TREKKING, "ALPINE TOUR"),
    (ActivityProfile.ALLGEMEIN,       "WETTER-BRIEFING"),
])
def test_ac1_255_eyebrow_caps_format(profile, expected_eyebrow):
    """AC-1: Eyebrow-Texte sind im einheitlichen CAPS-Format."""
    from src.output.renderers.email.profile_signature import profile_signature
    sig = profile_signature(profile)
    assert sig.eyebrow == expected_eyebrow, (
        f"{profile.value}: eyebrow erwartet {expected_eyebrow!r}, bekommen: {sig.eyebrow!r}"
    )


# ── AC-2: Summer-Trekking vs. Allgemein visuell unterscheidbar ───────────────

def test_ac2_255_summer_trekking_vs_allgemein_distinguishable():
    """AC-2: SUMMER_TREKKING und ALLGEMEIN haben unterschiedliche icon_html + Farben."""
    from src.output.renderers.email.profile_signature import profile_signature
    sig_st = profile_signature(ActivityProfile.SUMMER_TREKKING)
    sig_al = profile_signature(ActivityProfile.ALLGEMEIN)
    assert hasattr(sig_st, "icon_html"), "SUMMER_TREKKING hat kein icon_html"
    assert hasattr(sig_al, "icon_html"), "ALLGEMEIN hat kein icon_html"
    assert sig_st.icon_html != sig_al.icon_html, (
        "SUMMER_TREKKING und ALLGEMEIN müssen unterschiedliche SVG-Icons haben"
    )
    assert "#c45a2a" in sig_st.icon_html, "SUMMER_TREKKING-Farbe #c45a2a fehlt im SVG"
    assert "#6b675c" in sig_al.icon_html, "ALLGEMEIN-Farbe #6b675c fehlt im SVG"


# ── AC-3: render_html nutzt G_PAPER als Header-BG + G_ACCENT im Eyebrow ─────

def test_ac3_255_render_html_paper_header_and_accent_eyebrow():
    """AC-3: render_html setzt Header auf G_PAPER, Eyebrow-Farbe auf G_ACCENT, nutzt SVG."""
    from src.output.renderers.email.html import render_html
    kwargs = _common_kwargs()
    token_line = _make_token_line()
    html = render_html(
        segments=kwargs["segments"],
        seg_tables=kwargs["seg_tables"],
        trip_name=token_line.trip_name or token_line.stage_name,
        report_type=token_line.report_type,
        dc=kwargs["display_config"],
        night_rows=kwargs["night_rows"] or [],
        thunder_forecast=kwargs["thunder_forecast"],
        highlights=kwargs["highlights"],
        changes=kwargs["changes"],
        stage_name=kwargs["stage_name"],
        stage_stats=kwargs["stage_stats"],
        multi_day_trend=kwargs["multi_day_trend"],
        compact_summary=kwargs["compact_summary"],
        daylight=kwargs["daylight"],
        tz=kwargs["tz"],
        friendly_keys=kwargs["friendly_keys"],
        profile=ActivityProfile.WINTERSPORT,
    )
    assert G_PAPER_HEX in html, (
        f"G_PAPER ({G_PAPER_HEX}) fehlt im HTML — Header muss Paper-Hintergrund haben"
    )
    assert G_ACCENT_HEX in html, (
        f"G_ACCENT ({G_ACCENT_HEX}) fehlt im HTML — Eyebrow-Textfarbe fehlt"
    )
    assert "<svg" in html, (
        "Kein <svg> im generierten HTML — icon_html wird nicht in den Eyebrow-Div gerendert"
    )


# ── AC-4: Profil-Akzentfarbe NICHT als Header-Background ────────────────────

def test_ac4_255_accent_not_as_header_background():
    """AC-4: render_html(ALLGEMEIN) → #6b675c erscheint nicht als Header-background."""
    from src.output.renderers.email.html import render_html
    kwargs = _common_kwargs()
    token_line = _make_token_line()
    html = render_html(
        segments=kwargs["segments"],
        seg_tables=kwargs["seg_tables"],
        trip_name=token_line.trip_name or token_line.stage_name,
        report_type=token_line.report_type,
        dc=kwargs["display_config"],
        night_rows=kwargs["night_rows"] or [],
        thunder_forecast=kwargs["thunder_forecast"],
        highlights=kwargs["highlights"],
        changes=kwargs["changes"],
        stage_name=kwargs["stage_name"],
        stage_stats=kwargs["stage_stats"],
        multi_day_trend=kwargs["multi_day_trend"],
        compact_summary=kwargs["compact_summary"],
        daylight=kwargs["daylight"],
        tz=kwargs["tz"],
        friendly_keys=kwargs["friendly_keys"],
        profile=ActivityProfile.ALLGEMEIN,
    )
    header_start = html.find('<div class="header"')
    assert header_start != -1, "Kein <div class=\"header\"> gefunden"
    header_end = html.find("</div>", header_start + 200)
    header_section = html[header_start:header_end + 6]
    assert "background:#6b675c" not in header_section, (
        "Header-BG ist noch #6b675c (Profil-Akzent) — muss G_PAPER sein"
    )
    assert "background: #6b675c" not in header_section, (
        "Header-BG ist noch #6b675c (mit Leerzeichen) — muss G_PAPER sein"
    )
    assert G_PAPER_HEX in html, f"G_PAPER ({G_PAPER_HEX}) fehlt im HTML"


# ── AC-5: render_plain nutzt Emoji (sig.icon), kein SVG ─────────────────────

def test_ac5_255_render_plain_uses_emoji_not_svg():
    """AC-5: render_plain nutzt sig.icon (Emoji) statt icon_html (SVG)."""
    from src.output.renderers.email import render_email
    token_line = _make_token_line()
    _html, plain = render_email(token_line, profile=ActivityProfile.WANDERN, **_common_kwargs())
    assert "<svg" not in plain, (
        "render_plain darf kein SVG-Markup enthalten — nur Emoji-Icon"
    )
    assert "WANDERN" in plain, (
        "CAPS-Eyebrow 'WANDERN' fehlt im Plain-Text"
    )
    assert "🥾" in plain, (
        "Emoji-Icon 🥾 fehlt im Plain-Text — sig.icon muss weiterhin genutzt werden"
    )


# ── AC-6: Fallback liefert 'WETTER-BRIEFING' statt 'Allgemein' ──────────────

def test_ac6_255_fallback_none_returns_wetter_briefing():
    """AC-6: profile_signature(None) → eyebrow='WETTER-BRIEFING', valides SVG in icon_html."""
    from src.output.renderers.email.profile_signature import profile_signature
    sig = profile_signature(None)
    assert sig.eyebrow == "WETTER-BRIEFING", (
        f"Fallback-Eyebrow erwartet 'WETTER-BRIEFING', bekommen: {sig.eyebrow!r}"
    )
    assert hasattr(sig, "icon_html"), "Fallback-Signatur hat kein icon_html-Feld"
    assert sig.icon_html.startswith("<svg"), (
        "Fallback-icon_html muss gültiges SVG sein"
    )
