"""
Tests für Issue #241 — ActivityProfile durch Mail-Pipeline + Profil-Marker im Header.

SPEC: docs/specs/modules/issue_241_email_profile_pipeline.md
TESTS-SPEC: docs/specs/tests/issue_241_email_profile_pipeline_tests.md
EPIC: #236 (Sub-Issue 3b)

RED-Zustand (jetzt):
  src/output/renderers/email/profile_signature.py existiert NICHT → ImportError.
  render_html / render_email / format_email kennen profile-kwarg nicht → TypeError.
  trip_report_scheduler / preview_service rufen Formatter ohne profile auf → Source-Assert-Fail.
"""
from __future__ import annotations

import pytest

from app.profile import ActivityProfile
from tests.unit.test_renderers_email import _common_kwargs, _make_token_line


PROFILE_CASES = [
    (ActivityProfile.WINTERSPORT, "#4a7fb5", "❄", "WINTERSPORT · PISTE"),
    (ActivityProfile.WANDERN, "#3a7d44", "🥾", "WANDERN"),
    (ActivityProfile.SUMMER_TREKKING, "#c45a2a", "🏔", "ALPINE TOUR"),
    (ActivityProfile.ALLGEMEIN, "#6b675c", "◯", "WETTER-BRIEFING"),
]


# --- AC-1: profile_signature() liefert korrekte Werte pro Profil ----------

def test_ac1_signature_wintersport():
    """AC-1: WINTERSPORT → blau-eis, Schneeflocke, 'WINTERSPORT · PISTE'."""
    from src.output.renderers.email.profile_signature import profile_signature
    sig = profile_signature(ActivityProfile.WINTERSPORT)
    assert sig.accent_hex == "#4a7fb5"
    assert sig.icon == "❄"
    assert sig.eyebrow == "WINTERSPORT · PISTE"


def test_ac1_signature_wandern():
    """AC-1: WANDERN → Wald-Grün, Stiefel, 'WANDERN'."""
    from src.output.renderers.email.profile_signature import profile_signature
    sig = profile_signature(ActivityProfile.WANDERN)
    assert sig.accent_hex == "#3a7d44"
    assert sig.icon == "🥾"
    assert sig.eyebrow == "WANDERN"


def test_ac1_signature_summer_trekking():
    """AC-1: SUMMER_TREKKING → Burnt-Orange, Berg, 'ALPINE TOUR'."""
    from src.output.renderers.email.profile_signature import profile_signature
    sig = profile_signature(ActivityProfile.SUMMER_TREKKING)
    assert sig.accent_hex == "#c45a2a"
    assert sig.icon == "🏔"
    assert sig.eyebrow == "ALPINE TOUR"


def test_ac1_signature_allgemein():
    """AC-1: ALLGEMEIN → Neutral-Grau, Kreis, 'WETTER-BRIEFING'."""
    from src.output.renderers.email.profile_signature import profile_signature
    sig = profile_signature(ActivityProfile.ALLGEMEIN)
    assert sig.accent_hex == "#6b675c"
    assert sig.icon == "◯"
    assert sig.eyebrow == "WETTER-BRIEFING"


# --- AC-2: render_html(profile=...) rendert korrekten Header --------------

@pytest.mark.parametrize("profile,accent_hex,_icon,eyebrow", PROFILE_CASES)
def test_ac2_render_html_with_profile(profile, accent_hex, _icon, eyebrow):
    """
    AC-2: render_html(profile=X) erzeugt HTML mit:
      - {accent_hex} als Akzentfarbe im Eyebrow-SVG
      - Eyebrow-Block "{SVG-Icon} {eyebrow}" im Header
      - (Issue #255: Emoji-Icon wurde durch inline-SVG ersetzt — accent_hex
        erscheint nun als fill/stroke im SVG, nicht mehr als Header-BG.)
    """
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
        profile=profile,
    )
    html_lower = html.lower()
    assert accent_hex.lower() in html_lower, (
        f"Accent-Hex {accent_hex} fehlt im HTML für Profil {profile.value}"
    )
    assert eyebrow in html, f"Eyebrow {eyebrow!r} fehlt im HTML für Profil {profile.value}"
    assert "eyebrow" in html_lower, "CSS-Klasse 'eyebrow' fehlt im HTML"
    assert "<svg" in html, (
        f"SVG-Icon fehlt im HTML für Profil {profile.value} (Issue #255)"
    )


# --- AC-3: render_email reicht profile an render_html + render_plain -------

def test_ac3_render_email_passes_profile_through():
    """
    AC-3: render_email(profile=WINTERSPORT) → html enthält Wintersport-Marker,
    plain enthält Prefix-Zeile mit Schneeflocke.
    """
    from src.output.renderers.email import render_email
    token_line = _make_token_line()
    html, plain = render_email(
        token_line, profile=ActivityProfile.WINTERSPORT, **_common_kwargs(),
    )
    assert "#4a7fb5" in html.lower(), "Wintersport-Accent fehlt im HTML"
    assert "WINTERSPORT · PISTE" in html, "Wintersport-Eyebrow fehlt im HTML"
    assert "❄ WINTERSPORT · PISTE" in plain, "Wintersport-Prefix fehlt im Plain"


# --- AC-4: format_email reicht profile an render_email durch ---------------

def test_ac4_format_email_passes_profile_through():
    """
    AC-4: TripReportFormatter.format_email(profile=SUMMER_TREKKING) →
    TripReport.html_body enthält #c45a2a + 'Sommer-Trekking'.
    """
    from src.formatters.trip_report import TripReportFormatter
    kwargs = _common_kwargs()
    formatter = TripReportFormatter()
    report = formatter.format_email(
        segments=kwargs["segments"],
        trip_name="GR20 Test",
        report_type="evening",
        display_config=kwargs["display_config"],
        stage_name=kwargs["stage_name"],
        stage_stats=kwargs["stage_stats"],
        tz=kwargs["tz"],
        profile=ActivityProfile.SUMMER_TREKKING,
    )
    assert "#c45a2a" in report.email_html.lower(), (
        "Summer-Trekking-Accent #c45a2a fehlt in TripReport.email_html"
    )
    assert "ALPINE TOUR" in report.email_html, (
        "Eyebrow 'ALPINE TOUR' fehlt in TripReport.email_html"
    )


# AC-5 (test_ac5_scheduler_passes_profile_to_formatter) — entfernt in #765.
# Las src/services/trip_report_scheduler.py als Quelltext (Datei-Inhalt-Anti-
# Pattern, CLAUDE.md). Das Durchreichen von profile durch die Render-Pipeline
# ist durch test_ac4_format_email_passes_profile_through (TripReportFormatter.
# format_email rendert den Profil-Accent) am echten Output abgedeckt; die
# Scheduler-Verdrahtung selbst ist eine reine Source-Konstante ohne eigenes
# beobachtbares Verhalten in diesem Modul.


# --- AC-6: Eyebrow-Block steht vor <h1> im Header -------------------------

@pytest.mark.parametrize("profile,_accent,_icon,_eyebrow", PROFILE_CASES)
def test_ac6_header_eyebrow_before_h1(profile, _accent, _icon, _eyebrow):
    """
    AC-6: Im HTML kommt 'class="eyebrow"' (oder ähnlicher Eyebrow-Marker)
    VOR dem ersten '<h1>' im Header-Block.
    """
    from src.output.renderers.email import render_email
    token_line = _make_token_line()
    html, _plain = render_email(token_line, profile=profile, **_common_kwargs())

    eyebrow_idx = html.lower().find("class=\"eyebrow\"")
    h1_idx = html.find("<h1>")
    assert eyebrow_idx != -1, "Kein <div class=\"eyebrow\"> im HTML gefunden"
    assert h1_idx != -1, "Kein <h1> im HTML gefunden"
    assert eyebrow_idx < h1_idx, (
        f"Eyebrow-Block muss VOR <h1> stehen (eyebrow@{eyebrow_idx} < h1@{h1_idx}); "
        f"DOM-Reihenfolge ist falsch"
    )


# --- AC-7: render_plain hat Prefix-Zeile {icon} {eyebrow} ------------------

@pytest.mark.parametrize("profile,_accent,icon,eyebrow", PROFILE_CASES)
def test_ac7_render_plain_prefix_line(profile, _accent, icon, eyebrow):
    """
    AC-7: Plain-Text-Output enthält Prefix-Zeile '{icon} {eyebrow}' vor
    Trip-Namen — Profil-Marker geht im Plain-Text-Fallback nicht verloren.
    """
    from src.output.renderers.email import render_email
    token_line = _make_token_line()
    _html, plain = render_email(token_line, profile=profile, **_common_kwargs())
    expected_prefix = f"{icon} {eyebrow}"
    assert expected_prefix in plain, (
        f"Plain-Body enthält Prefix {expected_prefix!r} nicht — "
        f"Profil-Marker fehlt im Plain-Text-Fallback"
    )


# --- AC-8: Backward-Kompat — render_email ohne profile-kwarg ---------------

def test_ac8_render_email_without_profile_kwarg_backward_compat():
    """
    AC-8: render_email(...) OHNE profile-kwarg darf nicht crashen und muss
    auf ALLGEMEIN-Signatur zurückfallen (Backward-Kompat).
    """
    from src.output.renderers.email import render_email
    token_line = _make_token_line()
    html, plain = render_email(token_line, **_common_kwargs())
    assert isinstance(html, str) and html
    assert isinstance(plain, str) and plain
    assert "#6b675c" in html.lower(), (
        "Default-Fallback ALLGEMEIN-Accent #6b675c fehlt im HTML"
    )
    assert "WETTER-BRIEFING" in html, "Default-Fallback Eyebrow 'WETTER-BRIEFING' fehlt im HTML"


# AC-9 (test_ac9_preview_service_passes_profile_through) — entfernt in #765.
# Las src/services/preview_service.py als Quelltext (Datei-Inhalt-Anti-Pattern,
# CLAUDE.md). Das eigentliche Profil-Durchreichen ist über render_email/
# render_html (test_ac2_render_html_with_profile, test_ac3_render_email_passes_
# profile_through) am echten gerenderten Output abgedeckt.


# --- AC-10: Fallback bei None / unbekanntem Wert ---------------------------

def test_ac10_signature_none_fallback():
    """AC-10: profile_signature(None) → ALLGEMEIN-Signatur, keine Exception."""
    from src.output.renderers.email.profile_signature import profile_signature
    sig = profile_signature(None)
    assert sig.accent_hex == "#6b675c"
    assert sig.icon == "◯"
    assert sig.eyebrow == "WETTER-BRIEFING"


def test_ac10_signature_unknown_value_fallback():
    """
    AC-10: profile_signature mit unbekanntem Wert (z.B. String der nicht im
    Enum ist) → ALLGEMEIN-Signatur, keine Exception.
    """
    from src.output.renderers.email.profile_signature import profile_signature
    sig = profile_signature("nicht_im_enum")  # type: ignore[arg-type]
    assert sig.accent_hex == "#6b675c"
    assert sig.icon == "◯"
    assert sig.eyebrow == "WETTER-BRIEFING"
