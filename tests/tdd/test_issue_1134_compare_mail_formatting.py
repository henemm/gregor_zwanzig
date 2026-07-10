"""
Issue #1134: Compare-Mail Formatierungs-Fixes.

SPEC: docs/specs/modules/issue_1134_compare_mail_formatting.md
AC-1 / AC-1a / AC-2 / AC-2a (Backend-Teil; AC-3/AC-3a sind Frontend-E2E).

Verhaltenstests — KEINE Mocks. Es werden ECHTE `OfficialAlert`-Datenklassen
(interne, frozen dataclasses — kein externes System) instanziiert und die
ECHTEN Renderfunktionen `render_official_alerts_html()` (Shared-Renderer) sowie
`render_compare_html()` (oeffentlicher Compare-Renderpfad, ruft intern
`_render_location_section` -> `render_official_alerts_html` auf) auf
kontrollierten Eingabedaten ausgefuehrt. Geprueft wird die reale HTML-Ausgabe
(Hex-Farbwerte, Vorkommens-Anzahl eines Label-Texts), nicht der Quellcode.

HINWEIS (Issue #1056 v2.0, 2026-07-10): #1134 fuehrte eine hazard-aware
Severity-Faerbung (`severity_fn`) fuer den Compare-Badge/-Chip ein, die von
der Trip-Briefing-Level-Faerbung abwich. #1056 v2.0 macht diese Divergenz
rueckgaengig und vereinheitlicht BEIDE Pfade auf die amtliche 4-Stufen-Skala
(`OfficialAlert.level`). `TestAC1HazardAwareBadgeColor` und
`TestAC1aTripPathUnchanged` unten wurden entsprechend auf Level-Farben
umgestellt (PO-entschieden, Supersede — nicht rueckgaengig machen). AC-1/AC-1a
heissen historisch weiter so, pruefen aber jetzt die vereinheitlichte
Level-Faerbung statt der urspruenglichen Hazard-Divergenz. AC-2/AC-2a
(Dedup) sind von #1056 UNBERUEHRT und bleiben unveraendert gruen.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.models import ForecastDataPoint
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.email.compare_html import render_compare_html
from output.renderers.email.design_tokens import G_ALERT_L3, G_ALERT_L4, G_WARNING
from services.official_alerts.models import OfficialAlert
from src.output.renderers.alert.official_alerts import render_official_alerts_html


def _loc_with_alerts(loc_id: str, name: str, alerts: list[OfficialAlert]) -> LocationResult:
    """LocationResult mit genau einem Stundenpunkt (noetig, damit
    `_render_location_section` den Pro-Ort-Streifen ueberhaupt rendert — ohne
    hourly_data entfaellt der ganze Abschnitt, Spec §4) und den uebergebenen
    amtlichen Warnungen."""
    loc = SavedLocation(id=loc_id, name=name, lat=42.15, lon=9.05, elevation_m=800)
    dp = ForecastDataPoint(ts=datetime(2026, 7, 9, 9, 0), t2m_c=34.0)
    return LocationResult(location=loc, score=70, official_alerts=alerts, hourly_data=[dp])


# ---------------------------------------------------------------------------
# AC-1: Badge-Farbe im Pro-Ort-Streifen ist hazard-aware (nicht Level-Farbe)
# ---------------------------------------------------------------------------

class TestAC1HazardAwareBadgeColor:
    def test_extreme_heat_badge_uses_level_color_not_hazard_severity(self):
        """#1056 v2.0 supersedes #1134 severity coloring.

        GIVEN: Ein Ort mit einer `extreme_heat`-Warnung Stufe 4.
        WHEN:  `render_compare_html()` rendert die Mail (Pro-Ort-Streifen ruft
               `render_official_alerts_html` auf).
        THEN:  Der Badge im Pro-Ort-Streifen verwendet die amtstreue
               Level-4-Farbe (G_ALERT_L4, Violett) — NICHT mehr die
               hazard-aware "warn"-Farbe (G_WARNING) aus #1134. Issue #1056
               v2.0 ersetzt die hazard-severity-basierte Faerbung amtlicher
               Warnungen durch die amtliche Stufen-Skala (PO-Entscheidung
               2026-07-10).
        """
        alert = OfficialAlert(
            source="test-1134-heat", hazard="extreme_heat", level=4,
            label="Hitzewarnung Sued 1134",
        )
        loc = _loc_with_alerts("loc-heat", "Bavella", [alert])
        result = ComparisonResult(
            locations=[loc], time_window=(9, 16), target_date=date.today(),
        )

        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        level4_badge = f"border-left:4px solid {G_ALERT_L4}"
        warn_badge = f"border-left:4px solid {G_WARNING}"

        assert level4_badge in html, (
            "Pro-Ort-Badge muss die amtliche Level-4-Farbe (G_ALERT_L4, "
            f"Violett) verwenden, gefunden: {level4_badge!r} nicht im HTML."
        )
        assert warn_badge not in html, (
            "Pro-Ort-Badge darf NICHT mehr die hazard-aware 'warn'-Farbe "
            "(G_WARNING, #1134) tragen — #1056 v2.0 faerbt strikt nach "
            "amtlicher Stufe."
        )


# ---------------------------------------------------------------------------
# AC-1a: Trip-Pfad (ohne severity_fn) bleibt byte-gleich
# ---------------------------------------------------------------------------

class TestAC1aTripPathUnchanged:
    def test_render_is_byte_identical_across_calls_and_level_based(self):
        """#1056 v2.0 supersedes #1134 severity coloring.

        GIVEN: Eine `extreme_heat`-Warnung Stufe 3.
        WHEN:  `render_official_alerts_html()` wird zweimal mit identischen
               Argumenten aufgerufen (der `severity_fn`-Parameter aus #1134
               entfaellt mit #1056 v2.0 komplett — es gibt nur noch den
               amtstreuen Level-Pfad).
        THEN:  Beide Ausgaben sind byte-identisch und verwenden die
               level-basierte Farbe (Level 3 -> G_ALERT_L3, #c8482a) —
               dieselbe Farbe wie der (ehemals separate) Compare-Pfad.
        """
        alert = OfficialAlert(
            source="test-1134-trip", hazard="extreme_heat", level=3,
            label="Hitzewarnung Trip 1134",
        )
        entries = [("", [alert])]

        first = render_official_alerts_html(entries)
        second = render_official_alerts_html(entries)

        assert second == first, (
            "render_official_alerts_html() muss deterministisch byte-gleich "
            "rendern (keine versteckte Zustandsabhaengigkeit)."
        )
        assert f"border-left:4px solid {G_ALERT_L3}" in first, (
            "Level 3 muss die amtliche G_ALERT_L3-Farbe (#c8482a) tragen "
            "(#1056 v2.0, ersetzt die vormalige G_WARNING-Faerbung)."
        )


# ---------------------------------------------------------------------------
# AC-2: Dedup identischer Warnungen im Pro-Ort-Streifen
# ---------------------------------------------------------------------------

class TestAC2DedupIdenticalAlerts:
    def test_duplicate_extreme_heat_appears_once_in_location_strip(self):
        """
        GIVEN: Ein Ort, dessen `official_alerts` zwei IDENTISCHE
               `extreme_heat`-Warnungen (gleicher hazard/level/label) enthaelt.
        WHEN:  `render_compare_html()` rendert die Mail.
        THEN:  Das eindeutige Warn-Label erscheint im Pro-Ort-Streifen genau
               einmal.

        RED: der Compare-Pfad dedupliziert nicht -> das Label erscheint zweimal.
        Das Label ist bewusst eindeutig gewaehlt und taucht NUR im
        Pro-Ort-Badge (`<span>{label}</span>`) auf — die Uebersichts-Chips
        nutzen das Kuerzel "Hitze", der Warn-Lead "Extreme Hitze · N Orte".
        """
        unique_label = "Hitzewarnung Dedup-Fall 1134xyz"
        a1 = OfficialAlert(source="s-a", hazard="extreme_heat", level=3, label=unique_label)
        a2 = OfficialAlert(source="s-b", hazard="extreme_heat", level=3, label=unique_label)
        loc = _loc_with_alerts("loc-dup", "Ospedale", [a1, a2])
        result = ComparisonResult(
            locations=[loc], time_window=(9, 16), target_date=date.today(),
        )

        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        assert html.count(unique_label) == 1, (
            f"Identische Warnung muss genau EINMAL erscheinen, gefunden "
            f"{html.count(unique_label)}x (Dedup im Compare-Pfad fehlt)."
        )


# ---------------------------------------------------------------------------
# AC-2a: Kein Falsch-Positiv-Dedup bei unterschiedlichem Label
# ---------------------------------------------------------------------------

class TestAC2aNoFalsePositiveDedup:
    def test_same_hazard_different_label_both_kept(self):
        """
        GIVEN: Ein Ort mit zwei `access_ban`-Warnungen (gleicher hazard+level,
               ABER unterschiedliches `label`, z.B. zwei verschiedene Massive).
        WHEN:  `render_compare_html()` rendert die Mail.
        THEN:  BEIDE Labels erscheinen je einmal — die Dedup-Logik darf sie
               nicht als Duplikat behandeln (Dedup-Key enthaelt `label`).

        Nicht-Regressions-Waechter: schuetzt gegen einen naiven Dedup, der nur
        auf `hazard` schluesselt. Ist heute gruen (kein Dedup unterdrueckt
        etwas) und MUSS nach dem Fix gruen bleiben.
        """
        label_a = "Zugang gesperrt — Massiv Alpha 1134"
        label_b = "Zugang gesperrt — Massiv Beta 1134"
        a1 = OfficialAlert(source="m-a", hazard="access_ban", level=4, label=label_a)
        a2 = OfficialAlert(source="m-b", hazard="access_ban", level=4, label=label_b)
        loc = _loc_with_alerts("loc-massif", "Restonica", [a1, a2])
        result = ComparisonResult(
            locations=[loc], time_window=(9, 16), target_date=date.today(),
        )

        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        assert html.count(label_a) == 1, (
            f"Massiv Alpha muss genau einmal erscheinen, gefunden {html.count(label_a)}x."
        )
        assert html.count(label_b) == 1, (
            f"Massiv Beta muss genau einmal erscheinen, gefunden {html.count(label_b)}x."
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
