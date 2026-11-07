"""
TDD RED: CAPE-Ampel-Schwellen neu kalibrieren (Workflow fix-briefing-grid-and-summary, Fix A).

SPEC: docs/specs/modules/briefing_grid_and_summary_consistency.md AC-1/AC-3(a)

Reale CAPE-Werte im Gebirge liegen meist unter der bisherigen Flachland-
Konvektionsskala (yellow:1000/orange:2500/red:3500) -> die CAPE-Ampel zeigte
in der Praxis dauerhaft gruen, obwohl echte Gewittergefahr bestand. Diese
Tests pruefen die neu kalibrierten Grenzen (yellow:300/orange:800/red:1500)
gegen `severity_for("cape", v)` -- kein Mock, direkter Katalog-Roundtrip.

Muss VOR Fix A rot sein (aktuelle Katalog-Schwellen 1000/2500/3500 liefern
z.B. fuer 300 "green" statt "yellow"), NACH Fix A gruen.
"""
from app.ampel import resolve_ampel
from src.app.metric_catalog import get_metric
from src.output.metric_format import severity_for


class TestCapeAmpelThresholds:
    """AC-1: display_thresholds fuer cape == {yellow:300, orange:800, red:1500}."""

    def test_cape_display_thresholds_match_new_calibration(self):
        thresholds = get_metric("cape").display_thresholds
        assert thresholds == {"yellow": 300.0, "orange": 800.0, "red": 1500.0}

    # Issue #2792 S1c-4b (AC-6, AC-19 a) -- umgekehrt: CAPE traegt keine eigene
    # Farbe mehr (die Gewitterstufe faerbt ueber ``thunder_level_from_signals``).
    # Die frueheren Bandgrenzen 300/800/1500 und der AC-6-Wert 1600 liefern in
    # jeder Vorlage keine Stufe; der Katalog-Wert oben bleibt unveraendert.
    def test_cape_ohne_farbe_an_allen_frueheren_bandgrenzen(self):
        from app.ampel import AMPEL_TEMPLATES
        for vorlage in AMPEL_TEMPLATES:
            ampel = resolve_ampel({"ampel": {"template": vorlage}})
            for wert in (299, 300, 799, 800, 1499, 1500, 1600):
                assert severity_for("cape", wert, ampel=ampel) is None, (vorlage, wert)

    def test_andere_metrik_wird_weiter_gefaerbt(self):
        # Gegenprobe: ``severity_for`` liefert fuer Ampel-Metriken weiter Stufen,
        # das ``None`` oben ist CAPE-spezifisch und kein allgemeiner Ausfall.
        assert severity_for("gust", 60, ampel=resolve_ampel(None)) in ("orange", "red")
