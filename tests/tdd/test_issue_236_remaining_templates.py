"""
TDD RED — Issue #236 EPIC 9: Verbleibende E-Mail-Templates

Spec: docs/specs/modules/issue_236_epic9_remaining_templates.md
Test-Manifest: docs/specs/tests/issue_236_epic9_remaining_templates_tests.md

AC-1: Service-Error-Mail hat vollständige HTML-Struktur mit Design-Tokens
AC-2: Service-Error-Mail enthält keine hardkodierten Material-Design-Farben
AC-3: render_comparison_html() zeigt Profil-Eyebrow im Header wenn profile gesetzt
AC-4: Keine Material-Design-Farben (#1976d2, #42a5f5, etc.) im Comparison-HTML
AC-5: render_comparison_text() akzeptiert profile-Parameter ohne Exception
AC-6: compare_subscription übergibt activity_profile + Warning-Banner nutzt Design-Tokens
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.email.design_tokens import (
    G_ACCENT,
    G_DANGER,
    G_INK,
    G_PAPER,
    G_SUCCESS,
    WEB_FONT_LINK,
)
from output.renderers.email.profile_signature import profile_signature


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def minimal_comparison_result() -> ComparisonResult:
    loc = SavedLocation(
        id="loc1",
        name="Testort",
        lat=47.0,
        lon=11.0,
        elevation_m=1500,
    )
    result = LocationResult(location=loc, score=80, temp_min=-5.0, temp_max=2.0)
    return ComparisonResult(
        locations=[result],
        time_window=(9, 15),
        target_date=date(2026, 5, 18),
        created_at=datetime(2026, 5, 18, 8, 0),
    )


# ---------------------------------------------------------------------------
# AC-1: Service-Error-Mail — vollständige HTML-Struktur mit Design-Tokens
# ---------------------------------------------------------------------------

def test_ac1_service_error_mail_structure():
    """
    GIVEN: Modul trip_report_scheduler
    WHEN:  build_service_error_email_html() aufgerufen
    THEN:  HTML enthält G_PAPER, G_ACCENT, G_DANGER, G_INK-Footer, WEB_FONT_LINK,
           'Gregor Zwanzig' im Footer und #ffffff als Footer-Textfarbe

    ERWARTET ROT: build_service_error_email_html existiert noch nicht.
    """
    from services.trip_report_scheduler import build_service_error_email_html  # noqa: PLC0415

    html = build_service_error_email_html(
        trip_name="Test-Trip",
        report_type="morning",
        error_lines="  - Segment 1: Provider timeout",
    )

    assert G_PAPER in html, f"G_PAPER ({G_PAPER}) fehlt im HTML"
    assert G_ACCENT in html, f"G_ACCENT ({G_ACCENT}) fehlt im HTML"
    assert G_DANGER in html, f"G_DANGER ({G_DANGER}) fehlt im HTML"
    assert G_INK in html, f"G_INK-Footer ({G_INK}) fehlt im HTML"
    assert "Gregor Zwanzig" in html, "'Gregor Zwanzig' im Dunkel-Footer fehlt"
    assert WEB_FONT_LINK in html, "WEB_FONT_LINK im <head> fehlt"
    assert "#ffffff" in html, "Footer-Textfarbe #ffffff fehlt"
    assert f"background:{G_INK}" in html or f"background: {G_INK}" in html, (
        "Footer-Hintergrund G_INK fehlt"
    )


# ---------------------------------------------------------------------------
# AC-2: Service-Error-Mail — keine hardkodierten Material-Farben
# ---------------------------------------------------------------------------

def test_ac2_service_error_mail_no_hardcoded_colors():
    """
    GIVEN: build_service_error_email_html()
    WHEN:  Rückgabe auf verbotene Hex-Werte geprüft
    THEN:  #f5f5f5, #1976d2, #42a5f5 kommen nicht vor

    ERWARTET ROT: build_service_error_email_html existiert noch nicht.
    """
    from services.trip_report_scheduler import build_service_error_email_html  # noqa: PLC0415

    html = build_service_error_email_html(
        trip_name="Trip",
        report_type="morning",
        error_lines="  - Segment 1: Timeout",
    )

    forbidden = ["#f5f5f5", "#1976d2", "#42a5f5"]
    for color in forbidden:
        assert color not in html.lower(), f"Verbotene Farbe {color} im HTML gefunden"


# ---------------------------------------------------------------------------
# AC-3: Comparison-HTML — Profil-Eyebrow im Header
# ---------------------------------------------------------------------------

def test_ac3_comparison_html_profile_eyebrow(minimal_comparison_result):
    """
    GIVEN: render_comparison_html() mit profile=ActivityProfile.WANDERN
    WHEN:  Header-Block des zurückgegebenen HTML analysiert
    THEN:  Eyebrow-Zeile mit eyebrow-Text und accent_hex aus profile_signature();
           ohne profile wird ALLGEMEIN-Eyebrow als Fallback gezeigt

    ERWARTET ROT: render_comparison_html() akzeptiert kein 'profile'-Argument.
    """
    from services.comparison_renderers import render_comparison_html  # noqa: PLC0415

    # Mit Profil → Profil-spezifische Signatur
    html_with_profile = render_comparison_html(
        minimal_comparison_result,
        profile=ActivityProfile.WANDERN,
    )
    sig = profile_signature(ActivityProfile.WANDERN)
    assert sig.eyebrow in html_with_profile, f"Eyebrow-Text '{sig.eyebrow}' fehlt im Header"
    assert sig.accent_hex in html_with_profile, f"Profil-Akzentfarbe '{sig.accent_hex}' fehlt"

    # Ohne Profil → ALLGEMEIN-Fallback
    html_no_profile = render_comparison_html(minimal_comparison_result, profile=None)
    fallback = profile_signature(None)
    assert fallback.eyebrow in html_no_profile, f"ALLGEMEIN-Eyebrow '{fallback.eyebrow}' fehlt"


# ---------------------------------------------------------------------------
# AC-4: Comparison-HTML — keine Material-Design-Farben + Design-Tokens vorhanden
# ---------------------------------------------------------------------------

def test_ac4_comparison_html_no_material_colors(minimal_comparison_result):
    """
    GIVEN: render_comparison_html() aufgerufen
    WHEN:  HTML auf Material-Farben und Design-Token-Werte geprüft
    THEN:  Keine Material-Farben; G_PAPER, G_ACCENT, G_SUCCESS, WEB_FONT_LINK vorhanden

    ERWARTET ROT: Material-Farben noch vorhanden + Design-Tokens noch nicht eingebunden.
    """
    from services.comparison_renderers import render_comparison_html  # noqa: PLC0415

    html = render_comparison_html(minimal_comparison_result)

    # Material-Farben verboten
    material_colors = ["#1976d2", "#42a5f5", "#4caf50", "#e8f5e9", "#2e7d32"]
    for color in material_colors:
        assert color not in html.lower(), f"Material-Design-Farbe {color} noch im HTML"

    # Design-Tokens müssen vorhanden sein
    assert G_PAPER in html, f"G_PAPER ({G_PAPER}) fehlt im Comparison-HTML"
    assert G_ACCENT in html, f"G_ACCENT ({G_ACCENT}) fehlt im Comparison-HTML"
    assert G_SUCCESS in html, f"G_SUCCESS ({G_SUCCESS}) fehlt im Comparison-HTML"
    assert WEB_FONT_LINK in html, "WEB_FONT_LINK im <head> fehlt"


# ---------------------------------------------------------------------------
# AC-5: render_comparison_text() akzeptiert profile-Parameter
# ---------------------------------------------------------------------------

def test_ac5_comparison_text_profile_param_ignored(minimal_comparison_result):
    """
    GIVEN: render_comparison_text() mit profile=ActivityProfile.WINTERSPORT
    WHEN:  Funktion aufgerufen
    THEN:  Kein Exception; Rückgabe ist String; Inhalt identisch mit ohne profile

    ERWARTET ROT: 'profile'-Keyword wird noch nicht akzeptiert.
    """
    from services.comparison_renderers import render_comparison_text  # noqa: PLC0415

    text_with_profile = render_comparison_text(
        minimal_comparison_result,
        profile=ActivityProfile.WINTERSPORT,
    )
    text_without = render_comparison_text(minimal_comparison_result)

    assert isinstance(text_with_profile, str), "render_comparison_text() muss str zurückgeben"
    assert text_with_profile == text_without, (
        "Profil darf text-Output noch nicht ändern (spätere Implementierung)"
    )


# ---------------------------------------------------------------------------
# AC-6: Warning-Banner-Tokens + Profil-Weitergabe in compare_subscription.py
# ---------------------------------------------------------------------------

def test_ac6_warning_banner_tokens():
    """
    GIVEN: compare_html.py Source-Code
    WHEN:  Auf verbotene Warning-Farben + G_BOX_WARNING_BG geprüft
    THEN:  #fff3cd und #ffc107 fehlen; G_BOX_WARNING_BG ist referenziert
    """
    from output.renderers.email import compare_html  # noqa: PLC0415
    from output.renderers.email.design_tokens import G_BOX_WARNING_BG  # noqa: PLC0415

    with open(compare_html.__file__) as f:
        source_code = f.read()

    assert "#fff3cd" not in source_code, "Verbotene Farbe #fff3cd im Warning-Banner noch vorhanden"
    assert "#ffc107" not in source_code, "Verbotene Farbe #ffc107 im Warning-Banner noch vorhanden"
    assert "G_BOX_WARNING_BG" in source_code, "G_BOX_WARNING_BG fehlt in compare_html.py"


def test_ac6_compare_subscription_profile_forwarding():
    """
    GIVEN: compare_subscription.py Source-Code
    WHEN:  Aufruf von render_comparison_html() auf profile-Weitergabe geprüft
    THEN:  'profile=' beim render_comparison_html()-Aufruf vorhanden

    ERWARTET ROT: Aktuell kein profile-Argument übergeben.
    """
    import inspect  # noqa: PLC0415
    from services import compare_subscription  # noqa: PLC0415

    source = inspect.getsource(compare_subscription)

    assert "profile=" in source, "profile=-Argument fehlt in compare_subscription.py"
