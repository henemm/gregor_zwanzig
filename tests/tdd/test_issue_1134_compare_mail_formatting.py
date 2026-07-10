"""
TDD RED — Issue #1134: Compare-Mail Formatierungs-Fixes.

SPEC: docs/specs/modules/issue_1134_compare_mail_formatting.md
AC-1 / AC-1a / AC-2 / AC-2a (Backend-Teil; AC-3/AC-3a sind Frontend-E2E).

Verhaltenstests — KEINE Mocks. Es werden ECHTE `OfficialAlert`-Datenklassen
(interne, frozen dataclasses — kein externes System) instanziiert und die
ECHTEN Renderfunktionen `render_official_alerts_html()` (Shared-Renderer) sowie
`render_compare_html()` (oeffentlicher Compare-Renderpfad, ruft intern
`_render_location_section` -> `render_official_alerts_html` auf) auf
kontrollierten Eingabedaten ausgefuehrt. Geprueft wird die reale HTML-Ausgabe
(Hex-Farbwerte, Vorkommens-Anzahl eines Label-Texts), nicht der Quellcode.

Warum diese Tests jetzt (RED) fehlschlagen:
- AC-1:  Der Pro-Ort-Stundenverlauf-Badge faerbt heute rein `alert.level`-basiert
         (hazard-unabhaengig). Fuer eine `extreme_heat`-Warnung Stufe 4 liefert
         das G_DANGER (rot), obwohl die hazard-aware Uebersichtstabelle sie als
         "warn" (orange) klassifiziert -> Farb-Inkonsistenz. Fix: `severity_fn`.
- AC-1a: `render_official_alerts_html()` kennt den `severity_fn`-Parameter noch
         nicht -> der Aufruf mit `severity_fn=None` wirft TypeError (RED). Nach
         dem Fix bleibt der Default-Pfad (Trip-Briefing) byte-gleich.
- AC-2:  Der Compare-Pfad dedupliziert `loc.official_alerts` nicht -> zwei
         identische Warnungen erscheinen zweimal im Pro-Ort-Streifen.

Warum AC-1a-Anmerkung zur Waldbrand-Stufe-3 aus der Spec: Waldbrand-Stufe 3
diskriminiert NICHT (alte Level-3-Farbe == hazard-aware "warn" == G_WARNING),
ist als RED-Treiber also ungeeignet. `extreme_heat` (immer "warn", unabhaengig
vom Level) macht die hazard-aware Korrektur bei Level 4 sichtbar messbar.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.models import ForecastDataPoint
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.email.compare_html import render_compare_html
from output.renderers.email.design_tokens import G_DANGER, G_WARNING
from services.official_alerts.models import OfficialAlert
from src.output.renderers.alert.official_alerts import render_official_alerts_html

# _RISK_CELL["warn"]-Hintergrund der Uebersichtstabellen-Zelle (kanonische
# hazard-aware Quelle, compare_html.py:44). Nur zum Nachweis, dass die
# Uebersichtstabelle die Hitzewarnung als "warn" fuehrt.
WARN_CELL_BG = "#fad6b8"


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
    def test_extreme_heat_badge_uses_warn_color_not_generic_danger(self):
        """
        GIVEN: Ein Ort mit einer `extreme_heat`-Warnung Stufe 4.
        WHEN:  `render_compare_html()` rendert die Mail (Pro-Ort-Streifen ruft
               `render_official_alerts_html` auf).
        THEN:  Der Badge im Pro-Ort-Streifen verwendet die hazard-aware
               "warn"-Farbe (G_WARNING, wie die Uebersichtstabellen-Zelle sie
               klassifiziert), NICHT die generische Level-4-Farbe G_DANGER.

        RED: heute faerbt `render_official_alerts_html` Level>=4 -> G_DANGER,
        der Badge traegt also `border-left:4px solid #b33a2a`. Die Assertion auf
        die "warn"-Farbe schlaegt fehl, die Assertion gegen die Danger-Farbe
        ebenso.
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

        warn_badge = f"border-left:4px solid {G_WARNING}"
        danger_badge = f"border-left:4px solid {G_DANGER}"

        # Uebersichtstabelle klassifiziert die Hitzewarnung als "warn" (Beleg,
        # dass "gleiche Farbe wie Uebersichtszelle" == warn ist).
        assert WARN_CELL_BG in html, (
            "Uebersichtstabelle muss die extreme_heat-Warnung als 'warn' fuehren "
            f"(erwartet Zell-BG {WARN_CELL_BG})."
        )
        assert warn_badge in html, (
            "Pro-Ort-Badge muss die hazard-aware 'warn'-Farbe (G_WARNING) "
            f"verwenden, gefunden: {warn_badge!r} nicht im HTML."
        )
        assert danger_badge not in html, (
            "Pro-Ort-Badge darf NICHT die generische Level-4-Farbe G_DANGER "
            "tragen — extreme_heat ist hazard-aware 'warn', nicht 'danger'."
        )


# ---------------------------------------------------------------------------
# AC-1a: Trip-Pfad (ohne severity_fn) bleibt byte-gleich
# ---------------------------------------------------------------------------

class TestAC1aTripPathUnchanged:
    def test_render_without_severity_fn_is_byte_identical_and_level_based(self):
        """
        GIVEN: Eine `extreme_heat`-Warnung Stufe 3.
        WHEN:  `render_official_alerts_html()` wird EINMAL ohne und EINMAL mit
               `severity_fn=None` aufgerufen (Trip-Briefing-Pfad uebergibt
               nie einen Resolver).
        THEN:  Beide Ausgaben sind byte-identisch und verwenden weiterhin die
               level-basierte Farbe (Level 3 -> G_WARNING) — keine Regression.

        RED: `render_official_alerts_html()` kennt den `severity_fn`-Parameter
        noch nicht -> der zweite Aufruf wirft TypeError (unexpected keyword
        argument). Nach dem Fix existiert der Parameter mit Default None und der
        Default-Pfad bleibt byte-gleich.
        """
        alert = OfficialAlert(
            source="test-1134-trip", hazard="extreme_heat", level=3,
            label="Hitzewarnung Trip 1134",
        )
        entries = [("", [alert])]

        default_output = render_official_alerts_html(entries)

        # RED: severity_fn existiert noch nicht -> TypeError.
        explicit_none = render_official_alerts_html(entries, severity_fn=None)

        assert explicit_none == default_output, (
            "render_official_alerts_html(..., severity_fn=None) muss byte-gleich "
            "zum parameterlosen Aufruf sein (Trip-Pfad unveraendert)."
        )
        assert f"border-left:4px solid {G_WARNING}" in default_output, (
            "Trip-Pfad (ohne severity_fn) muss Level 3 weiterhin level-basiert "
            "als G_WARNING faerben (Bestandsverhalten)."
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
