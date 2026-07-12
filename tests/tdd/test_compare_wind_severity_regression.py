"""
TDD RED: Wind-Schwellen-Divergenz zwischen Compare-Mail und Trip-Briefing
(Issue #1214, Scheibe 2 -- AC-3).

SPEC: docs/specs/modules/issue_1214_metric_format_slice1_2.md

Compare rendert Wind-Ampel bislang mit hartcodierten, vom Katalog abweichenden
Schwellen (compare_html._sev_wind: >40->danger, >30->warn, >20->caution).
Der Katalog (metric_catalog.wind.display_thresholds) definiert
{yellow:30, orange:50, red:70}. Fuer 45 km/h liefert das Trip-Briefing
(helpers.ampel_level, dieselbe Katalog-Quelle) "yellow", Compare aber
"danger" -- derselbe Wert zeigt zwei unterschiedliche Ampel-Farben.

Nach der Scheibe-2-Migration muss Compare denselben kanonischen Wert wie
das Trip-Briefing liefern. Dieser Test ist bewusst ROT gegen den
unveraenderten compare_html.py-Code (siehe RED-Artefakt) und wird erst
nach der Migration in Scheibe 2 gruen.
"""
from src.output.renderers.email.compare_html import _sev_wind
from src.output.renderers.email.helpers import ampel_level


def test_wind_45_kmh_matches_briefing_ampel_after_migration():
    """AC-3: Compare und Trip-Briefing zeigen fuer denselben Wind-Wert
    dieselbe Ampel-Farbe."""
    briefing_level = ampel_level("wind", 45.0)
    assert briefing_level == "yellow", (
        "Erwartungs-Grundlage: Katalog-Schwellen liefern fuer 45 km/h 'yellow'"
    )

    compare_sev = _sev_wind(45.0)
    # Kanonisches Vokabular <-> Compare-lokales Vokabular: yellow<->caution.
    # Vor der Migration liefert _sev_wind(45.0) "danger" (hartcodierte
    # Schwelle >40) -- das ist der zu behebende Bug.
    assert compare_sev == "caution", (
        f"Compare zeigt '{compare_sev}' fuer Wind=45 km/h, erwartet 'caution' "
        f"(== Katalog-Ampel 'yellow'). Vor der Migration: 'danger' (Bug)."
    )
