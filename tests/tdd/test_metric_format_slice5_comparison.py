"""TDD — Issue #1214 Scheibe 5: comparison.py auf metric_format migrieren.

SPEC: docs/specs/modules/issue_1214_metric_format_slice5.md

AC-1 (Golden): render_comparison_text liefert vor UND nach der Migration einen
zeichen-identischen Plain-Text-Report — der Golden-String unten wurde aus dem
unmigrierten Code (Stand 64a762a6) erzeugt und ist der Verhaltens-Anker.
AC-2: die migrierten Uebersichts-Zeilen rufen metric_format.format_value auf
(Scheibe 6 migriert zusaetzlich die Sonne-Zeile, s. Datei-Docstring dort:
5 statt urspruenglich 4 Aufrufe).
AC-4 (Klassifikations-Kommentare in narrow.py/compact_summary.py fuer die
bewusst nicht migrierten Stellen) ist NICHT test-prueflich: das #765-Hygiene-
Gate verbietet Produkt-Quelltext-Reads in Tests. Der zugehoerige Test wurde
ersatzlos entfernt (Issue #1214 Scheibe 6) — die Kommentare selbst bleiben
im Code, nur die automatisierte Praesenzpruefung entfaellt.
"""
from __future__ import annotations

import inspect
import re
from datetime import date, datetime

from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import render_comparison_text

# Aus dem UNMIGRIERTEN Code erzeugt (siehe Docstring) — nicht anpassen, ausser
# eine bewusste, PO-freigegebene Verhaltensaenderung liegt vor.
#
# Issue #1268 (AC-5), PO-freigegeben: Die Zeile "Zeitfenster: 08:00 - 16:00" ist
# hier entfallen — genau der im Kommentar oben vorgesehene Ausnahmefall. Das
# Bewertungs-Zeitfenster ist kein Editor-Feld mehr; der Dispatch wertet immer den
# ganzen Tag (0–23 Uhr) aus. Eine Zeitfenster-Angabe haette damit keinen
# Aussagewert mehr und wurde in comparison.py ersatzlos entfernt. Der Golden
# bleibt im Uebrigen zeichen-identisch — er ankert weiterhin die #1214-Migration.
GOLDEN = (
    "ORTS-VERGLEICH\n"
    "========================\n"
    "Datum: Wednesday, 15.07.2026\n"
    "Erstellt: 12.07.2026 09:00\n"
    "\n"
    "--------------------------------------------------\n"
    "Alpsee\n"
    "   Temp max: 13°C\n"
    "   Wind: 35 km/h\n"
    "   Sonne: 4.7h\n"
    "   Wolken: 57%\n"
    "   Schneehöhe: 15 cm\n"
    "   Neuschnee: 4 cm\n"
    "\n"
    "Zugspitze\n"
    "   Temp max: -\n"
    "   Wind: -\n"
    "   Sonne: -\n"
    "   Wolken: -\n"
    "   Schneehöhe: -\n"
    "   Neuschnee: -\n"
    "\n"
    "---\n"
    "Gregor Zwanzig"
)


def _fixture_result() -> ComparisonResult:
    """Repraesentatives Set: ein Ort voll befuellt (floats mit Nachkommastellen,
    int-Felder), ein Ort komplett None. Keine hourly_data/alerts — Fokus auf
    die 6 Uebersichts-Zeilen."""
    loc_a = SavedLocation(id="a", name="Alpsee", lat=47.5, lon=10.2, elevation_m=800)
    loc_b = SavedLocation(id="b", name="Zugspitze", lat=47.4, lon=11.0, elevation_m=2900)
    full = LocationResult(
        location=loc_a, temp_max=12.6, wind_max=34.7, sunny_hours=4.7,
        cloud_avg=57, snow_depth_cm=15.4, snow_new_cm=3.6,
    )
    empty = LocationResult(location=loc_b)
    return ComparisonResult(
        locations=[full, empty], time_window=(8, 16),
        target_date=date(2026, 7, 15),
        created_at=datetime(2026, 7, 12, 9, 0),
    )


class TestAC1GoldenIdentical:
    def test_comparison_text_matches_golden(self):
        """AC-1: GIVEN repraesentativer ComparisonResult / WHEN
        render_comparison_text laeuft / THEN zeichen-identisch zum
        Vorher-Anker (Golden aus unmigriertem Code)."""
        assert render_comparison_text(_fixture_result()) == GOLDEN


class TestAC2FormatValueCalls:
    def test_overview_lines_use_format_value(self):
        """AC-2: GIVEN render_comparison_text nach der Migration / WHEN der
        Funktions-Quelltext untersucht wird / THEN rufen genau die 5
        migrierten Zeilen format_value(...) auf (temp/wind/wolken/
        schneehoehe/sonne); snow_new_cm bleibt hartcodiert (Katalog-Luecke).
        Issue #1214 Scheibe 6: sunshine.decimals=1 im Katalog macht die
        Sonne-Zeile beweisbar verhaltensneutral migrierbar (vormals F001-
        Ausnahme in Scheibe 5, s. dortiger Fix-Loop-Kommentar), Golden-
        String (AC-1) bleibt identisch."""
        src = inspect.getsource(render_comparison_text)
        calls = re.findall(r"format_value\(", src)
        assert len(calls) == 5, (
            f"Erwartet 5 format_value-Aufrufe in render_comparison_text, "
            f"gefunden: {len(calls)} — Uebersichts-Zeilen noch hartcodiert "
            f"oder Sonne-Zeile nicht migriert (Scheibe 6)?"
        )
