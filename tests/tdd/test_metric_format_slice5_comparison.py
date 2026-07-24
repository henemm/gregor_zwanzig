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

from datetime import date, datetime

from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import render_comparison_text
from output.metric_format import format_value

# Aus dem UNMIGRIERTEN Code erzeugt (siehe Docstring) — nicht anpassen, ausser
# eine bewusste, PO-freigegebene Verhaltensaenderung liegt vor.
#
# Issue #1268 (AC-5), PO-freigegeben: Die Zeile "Zeitfenster: 08:00 - 16:00" ist
# hier entfallen — genau der im Kommentar oben vorgesehene Ausnahmefall. Das
# Bewertungs-Zeitfenster ist kein Editor-Feld mehr; der Dispatch wertet immer den
# ganzen Tag (0–23 Uhr) aus. Eine Zeitfenster-Angabe haette damit keinen
# Aussagewert mehr und wurde in comparison.py ersatzlos entfernt.
#
# GOLDEN neu verankert: #1285 (Regen/Gewitter/Sicht/UV/pop) + #1296
# (temp_min/gust/cape/freezing) erweitern die Klartext-Uebersicht. Die
# Fixture setzt weder temp_min/gust_max noch hourly_data, darum zeigen alle
# neuen Zeilen "-" (Wert fehlt) statt eines Messwerts — manuell gegen den
# echten render_comparison_text(_fixture_result())-Output geprueft (Fix-Loop
# #1296 F001): keine leeren Zeilen, kein "None", keine Duplikate.
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
    "   Temp min: -\n"
    "   Böen: -\n"
    "   Windrichtung: -\n"
    "   Gefühlte Temp. min: -\n"
    "   Gefühlte Temp. max: -\n"
    "   Wolken tief: -\n"
    "   Wolken mittel: -\n"
    "   Wolken hoch: -\n"
    "   Regen: -\n"
    "   Regenwahrscheinlichkeit: -\n"
    "   Gewitter: -\n"
    "   UV max: -\n"
    "   Sicht min: -\n"
    "   CAPE: -\n"
    "   Nullgradgrenze: -\n"
    "   Luftfeuchtigkeit Ø: -\n"
    "   Taupunkt Ø: -\n"
    "   Luftdruck Ø: -\n"
    "   Niederschlagsart: -\n"
    "   Schneefallgrenze: -\n"
    "   Sonne: 4.7h\n"
    "   Wolken: 57%\n"
    "   Schneehöhe: 15 cm\n"
    "   Neuschnee: 4 cm\n"
    "\n"
    "Zugspitze\n"
    "   Temp max: -\n"
    "   Wind: -\n"
    "   Temp min: -\n"
    "   Böen: -\n"
    "   Windrichtung: -\n"
    "   Gefühlte Temp. min: -\n"
    "   Gefühlte Temp. max: -\n"
    "   Wolken tief: -\n"
    "   Wolken mittel: -\n"
    "   Wolken hoch: -\n"
    "   Regen: -\n"
    "   Regenwahrscheinlichkeit: -\n"
    "   Gewitter: -\n"
    "   UV max: -\n"
    "   Sicht min: -\n"
    "   CAPE: -\n"
    "   Nullgradgrenze: -\n"
    "   Luftfeuchtigkeit Ø: -\n"
    "   Taupunkt Ø: -\n"
    "   Luftdruck Ø: -\n"
    "   Niederschlagsart: -\n"
    "   Schneefallgrenze: -\n"
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
    """AC-2 — auf die EIGENSCHAFT umgestellt (Issue #1359).

    Vorher zaehlte dieser Test ``format_value(``-Vorkommen im Quelltext von
    ``render_comparison_text``. Zwei Gruende, warum das nicht mehr trifft:
    (1) er war seit Issue #1324 veraltet und ROT (9 statt der erwarteten 7
    Aufrufe -- die Gefuehlte-Temp-Zeilen kamen dazu, ohne dass ihn jemand
    nachzog); (2) mit #1359 wandern die Uebersichts-Zeilen in die geordnete
    Modul-Tabelle ``_PLAIN_ROWS``, damit die im Editor eingestellte
    Metrik-Reihenfolge ueberhaupt ankommen kann -- ein Zaehler auf dem
    Funktionskoerper misst seitdem strukturell 0.

    Geprueft wird jetzt das, worum es AC-2 ging: die gerenderte Zeile traegt
    exakt das Ergebnis der zentralen ``metric_format.format_value`` und keine
    handgebaute Zweitformatierung. Das ist ein Verhaltensnachweis statt eines
    Quelltext-Greps (#765-Hygiene) und faengt eine Rueck-Handformatierung
    zuverlaessiger als ein Zaehler.
    """

    def test_overview_lines_use_format_value(self):
        loc = SavedLocation(id="a", name="Alpsee", lat=47.5, lon=10.2, elevation_m=800)
        result = ComparisonResult(
            locations=[LocationResult(
                location=loc, temp_max=12.6, temp_min=3.4, wind_max=34.7,
                gust_max=51.2, sunny_hours=4.7, cloud_avg=57, snow_depth_cm=15.4,
            )],
            time_window=(8, 16), target_date=date(2026, 7, 15),
            created_at=datetime(2026, 7, 12, 9, 0),
        )
        text = render_comparison_text(result)
        expected = {
            "Temp max": format_value("temperature", 12.6, style="plain"),
            "Temp min": format_value("temperature", 3.4, style="plain"),
            "Wind": format_value("wind", 34.7, style="plain"),
            "Böen": format_value("wind", 51.2, style="plain"),
            "Sonne": f"{format_value('sunshine', 4.7, style='bare')}h",
            "Wolken": format_value("cloud_total", 57, style="plain"),
            "Schneehöhe": format_value("snow_depth", 15.4, style="plain"),
        }
        for label, value in expected.items():
            assert f"   {label}: {value}\n" in text, (
                f"AC-2: Zeile '{label}' folgt nicht der zentralen Formatierung "
                f"(erwartet '{value}').\nText:\n{text}"
            )
