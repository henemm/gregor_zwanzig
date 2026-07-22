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
from src.app.metric_catalog import get_metric
from src.output.metric_format import severity_for


class TestCapeAmpelThresholds:
    """AC-1: display_thresholds fuer cape == {yellow:300, orange:800, red:1500}."""

    def test_cape_display_thresholds_match_new_calibration(self):
        thresholds = get_metric("cape").display_thresholds
        assert thresholds == {"yellow": 300.0, "orange": 800.0, "red": 1500.0}

    def test_299_is_green(self):
        assert severity_for("cape", 299) == "green"

    def test_300_is_yellow(self):
        assert severity_for("cape", 300) == "yellow"

    def test_799_is_yellow(self):
        assert severity_for("cape", 799) == "yellow"

    def test_800_is_orange(self):
        assert severity_for("cape", 800) == "orange"

    def test_1499_is_orange(self):
        assert severity_for("cape", 1499) == "orange"

    def test_1500_is_red(self):
        assert severity_for("cape", 1500) == "red"
