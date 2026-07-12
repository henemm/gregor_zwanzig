"""TDD — Issue #1214 Scheibe 5: comparison.py auf metric_format migrieren.

SPEC: docs/specs/modules/issue_1214_metric_format_slice5.md

AC-1 (Golden): render_comparison_text liefert vor UND nach der Migration einen
zeichen-identischen Plain-Text-Report — der Golden-String unten wurde aus dem
unmigrierten Code (Stand 64a762a6) erzeugt und ist der Verhaltens-Anker.
AC-2 (RED vor Migration): die 4 migrierten Uebersichts-Zeilen rufen
metric_format.format_value auf. sunny_hours bleibt AUSSERHALB der Migration
(Fix-Loop F001, Adversary): zur Laufzeit ist sunny_hours float mit 1
Dezimale (calculate_sunny_hours, weather_metrics.py:298; Zuweisungen ohne
Cast in comparison_engine.py:153/466) — format_value(style="bare") wuerde
runden ("4.7h" -> "5h") und damit sichtbares Verhalten aendern.
AC-4 (RED vor Migration, # doc-compliance-test): narrow.py/_LABELS und
compact_summary.py/CompactSummaryFormatter tragen Klassifikations-Kommentare
mit metric_format-Verweis (bewusste Nicht-Migration).
"""
from __future__ import annotations

import inspect
import re
from datetime import date, datetime
from pathlib import Path

from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import render_comparison_text

_REPO = Path(__file__).resolve().parents[2]

# Aus dem UNMIGRIERTEN Code erzeugt (siehe Docstring) — nicht anpassen, ausser
# eine bewusste, PO-freigegebene Verhaltensaenderung liegt vor.
GOLDEN = (
    "ORTS-VERGLEICH\n"
    "========================\n"
    "Datum: Wednesday, 15.07.2026\n"
    "Zeitfenster: 08:00 - 16:00\n"
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
        Funktions-Quelltext untersucht wird / THEN rufen genau die 4
        migrierten Zeilen format_value(...) auf (temp/wind/wolken/
        schneehoehe); snow_new_cm bleibt hartcodiert (Katalog-Luecke),
        sunny_hours bleibt hartcodiert (Fix-Loop F001: Runtime-float mit
        1 Dezimale, format_value(style="bare") wuerde runden)."""
        src = inspect.getsource(render_comparison_text)
        calls = re.findall(r"format_value\(", src)
        assert len(calls) == 4, (
            f"Erwartet 4 format_value-Aufrufe in render_comparison_text, "
            f"gefunden: {len(calls)} — Uebersichts-Zeilen noch hartcodiert "
            f"oder sunny_hours faelschlich migriert (F001)?"
        )


class TestAC4ClassificationComments:
    def test_classification_comments_present(self):  # doc-compliance-test
        """AC-4: GIVEN die bewusst NICHT migrierten Stellen / WHEN die Quell-
        Dateien gelesen werden / THEN steht an beiden Stellen ein
        Klassifikations-Kommentar mit metric_format-Verweis (verhindert
        spaetere 'vergessene Migration'-Fehldiagnosen). Struktur-Artefakt,
        daher doc-compliance."""
        narrow = (_REPO / "src/output/renderers/narrow.py").read_text(encoding="utf-8")
        compact = (_REPO / "src/output/renderers/compact_summary.py").read_text(encoding="utf-8")

        labels_pos = narrow.find("_LABELS = [")
        assert labels_pos != -1, "narrow.py: _LABELS nicht gefunden"
        # Kommentar muss im Umfeld VOR der _LABELS-Definition stehen.
        assert "metric_format" in narrow[max(0, labels_pos - 1500):labels_pos], (
            "narrow.py: Klassifikations-Kommentar mit metric_format-Verweis "
            "oberhalb von _LABELS fehlt"
        )

        cls_pos = compact.find("class CompactSummaryFormatter")
        assert cls_pos != -1, "compact_summary.py: Formatter-Klasse nicht gefunden"
        # Verweis am Klassenkopf (Kommentar davor oder Docstring direkt danach).
        head = compact[max(0, cls_pos - 1500):cls_pos + 1500]
        assert "metric_format" in head, (
            "compact_summary.py: Klassifikations-Kommentar mit metric_format-"
            "Verweis am Kopf von CompactSummaryFormatter fehlt"
        )
