"""Verhaltensbenannt (Namensregel PO 2026-07-09, nicht test_issue_1056_*).

Bug #1056 (v2.0, vereinheitlicht nach Rebase auf #1134/#1200): Amtliche Warnungen
werden farblich uneinheitlich dargestellt — Trip-Briefing level-basiert (Stufe 2
fälschlich grün), Orts-Vergleich hazard-severity-basiert (#1134). Diese Tests
fixieren die EINE amtstreue 4-Stufen-Skala (grün/gelb/orange-rot/violett) für ALLE
amtlichen-Warnung-Farben: Trip-Badge, Compare-Badge und Compare-Übersichts-Chip.

Spec: docs/specs/modules/issue_1056_vigilance_badge_color.md (v2.0).
Kern-Schicht, deterministisch: reine HTML-Renderer, kein Netz, kein Mock.
"""
from __future__ import annotations

import re
import types
from datetime import date, datetime

from output.renderers.alert.official_alerts import (
    collect_trip_alert_entries,
    render_official_alerts_html,
)
from services.official_alerts.models import OfficialAlert

# Amtstreue 4-Stufen-Palette (Spec #1056 v2.0)
GREEN = "#3a7d44"        # Stufe 1 (= G_SUCCESS, unverändert)
YELLOW = "#9a6f00"       # Stufe 2 (neu G_ALERT_L2)
ORANGE_RED = "#c8482a"   # Stufe 3 (neu G_ALERT_L3)
VIOLET = "#6d28d9"       # Stufe 4 (neu G_ALERT_L4)


def _border_colors(html: str) -> list[str]:
    """Alle Badge-Rand-Farben aus dem HTML (Reihenfolge erhalten)."""
    return re.findall(r"border-left:4px solid (#[0-9a-fA-F]{6})", html)


def _alert(level: int, hazard: str = "thunderstorm", label: str | None = None) -> OfficialAlert:
    return OfficialAlert(
        source="test", hazard=hazard, level=level,
        label=label or f"Warnung Stufe {level}",
    )


def _compare_html_with(alerts: list[OfficialAlert]) -> str:
    """Rendert eine echte Compare-Mail mit den Alerts an einem Ort (kein Mock)."""
    from app.models import ForecastDataPoint
    from app.profile import ActivityProfile
    from app.user import ComparisonResult, LocationResult, SavedLocation
    from output.renderers.email.compare_html import render_compare_html

    loc = SavedLocation(id="nice", name="Nizza", lat=43.7, lon=7.26, elevation_m=10)
    dp = ForecastDataPoint(ts=datetime(2026, 7, 8, 9, 0), t2m_c=25.0)
    lr = LocationResult(location=loc, score=80, official_alerts=alerts, hourly_data=[dp])
    result = ComparisonResult(locations=[lr], time_window=(9, 16), target_date=date.today())
    return render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)


# --- AC-1..AC-4: geteilter Renderer, level-basiert -------------------------

def test_level2_badge_is_yellow_not_green():
    """AC-1 (Bug-Repro): Stufe 2 rendert gelb (#9a6f00), NICHT grün (#3a7d44)."""
    colors = _border_colors(render_official_alerts_html([("", [_alert(2)])]))
    assert colors == [YELLOW], f"Stufe-2-Rand erwartet {YELLOW}, war {colors}"
    assert GREEN not in colors, "Stufe 2 darf nicht grün gerendert werden (Bug #1056)"


def test_each_level_has_distinct_color():
    """AC-2: Stufen 1/2/3/4 tragen vier verschiedene, korrekt zugeordnete Farben."""
    mapping = {1: GREEN, 2: YELLOW, 3: ORANGE_RED, 4: VIOLET}
    got: dict[int, str] = {}
    for level, expected in mapping.items():
        colors = _border_colors(render_official_alerts_html([("", [_alert(level)])]))
        assert colors == [expected], f"Stufe {level}: erwartet {expected}, war {colors}"
        got[level] = colors[0]
    assert len(set(got.values())) == 4, f"Farben nicht paarweise verschieden: {got}"


def test_level_above_max_falls_back_to_highest():
    """AC-3: Stufe > 4 fällt defensiv auf die höchste Farbe (Violett), kein Fehler."""
    colors = _border_colors(render_official_alerts_html([("", [_alert(5)])]))
    assert colors == [VIOLET], f"Stufe 5 erwartet Fallback {VIOLET}, war {colors}"


def test_existing_semantic_tokens_unchanged_and_new_tokens_present():
    """AC-4: G_WARNING/G_DANGER unverändert; neue Alert-Tokens vorhanden."""
    from output.renderers.email import design_tokens as dt
    assert dt.G_WARNING == "#c8882a", "G_WARNING darf nicht kollateral geändert werden"
    assert dt.G_DANGER == "#b33a2a", "G_DANGER darf nicht kollateral geändert werden"
    assert dt.G_ALERT_L2 == YELLOW
    assert dt.G_ALERT_L3 == ORANGE_RED
    assert dt.G_ALERT_L4 == VIOLET


# --- AC-5: vereinheitlicht (Compare-Badge level-basiert, amtstreu) ----------

def test_both_mail_paths_badge_level_based_for_level2():
    """AC-5a: Compare-Badge UND Trip-Briefing-Badge zeigen bei Stufe 2 Gelb."""
    alert = _alert(2)
    compare_html = _compare_html_with([alert])
    assert f"border-left:4px solid {YELLOW}" in compare_html, (
        "Compare-Mail rendert Stufe-2-Alert-Badge nicht gelb (level-basiert)"
    )
    seg = types.SimpleNamespace(official_alerts=[alert])
    trip_html = render_official_alerts_html(collect_trip_alert_entries([seg]))
    assert f"border-left:4px solid {YELLOW}" in trip_html, (
        "Trip-Briefing rendert Stufe-2-Alert-Badge nicht gelb"
    )


def test_compare_badge_follows_level_not_hazard_severity():
    """AC-5b: Eine Hitzewarnung (extreme_heat) Stufe 4 färbt VIOLETT (amtliche
    Stufe), NICHT G_WARNING (#c8882a) — belegt Level statt Hazard-Severity (#1134
    severity_fn ersetzt)."""
    heat4 = _alert(4, hazard="extreme_heat", label="Hitzewarnung Süd")
    compare_html = _compare_html_with([heat4])
    assert f"border-left:4px solid {VIOLET}" in compare_html, (
        "Stufe-4-Hitzewarnung muss violett (amtliche Stufe) sein"
    )
    assert "border-left:4px solid #c8882a" not in compare_html, (
        "Compare-Badge darf NICHT mehr hazard-severity-basiert (G_WARNING) färben"
    )


# --- AC-6: Übersichts-Chip level-basiert, konsistent zum Badge -------------

def test_compare_overview_chip_colored_by_level_not_severity():
    """AC-6: Der Warn-Chip in der Übersichtstabelle trägt die Level-Farbe (fg =
    Stufen-Farbe), NICHT die hazard-severity-Zellfarbe (#1134 _RISK_CELL['caution']).
    Waldbrand Stufe 2 -> vorher 'caution' (fg #5e4a00), jetzt Gelb-Familie (#9a6f00)."""
    fire2 = _alert(2, hazard="wildfire_risk", label="Waldbrand 2")
    compare_html = _compare_html_with([fire2])
    # Chip nutzt `color:{fg}` (Badge nutzt `border-left:solid` — eindeutig unterscheidbar).
    assert f"color:{YELLOW}" in compare_html, (
        "Übersichts-Chip muss die Level-2-Farbe (#9a6f00) tragen"
    )
    assert "color:#5e4a00" not in compare_html, (
        "Chip darf NICHT mehr die hazard-severity 'caution'-Zellfarbe (#5e4a00) tragen"
    )


def test_metric_severity_cells_unchanged_by_alert_recolor():
    """AC-6 (Regressionsschutz): Die _RISK_CELL-basierten Wetter-METRIK-Zellen
    (Temp/Wind) bleiben unverändert — nur die Warn-Chips wechseln auf Level."""
    from output.renderers.email import compare_html as ch
    # _RISK_CELL bleibt die kanonische Metrik-Zell-Palette (unberührt).
    assert ch._RISK_CELL["caution"] == ("#fbeeb8", "#5e4a00")
    assert ch._RISK_CELL["warn"] == ("#fad6b8", "#8a3506")
    assert ch._RISK_CELL["danger"] == ("#f6c5bf", "#8a1009")
