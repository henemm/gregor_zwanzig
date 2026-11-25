"""#2988 S1: Der Abweichungszaehler existiert nur noch im Frontend (Editier-Delta).

Spec: docs/specs/modules/rework_2988_ampel_ableitung.md (Scheiben, S1). Die
Python-Zaehlung hatte keinen Produktaufrufer; die Aufloesung bleibt unveraendert.
"""

import pytest

import app.ampel as ampel


@pytest.mark.parametrize("name", ["deviation_count", "_richtung_weicht_ab", "_ohne_offene"])
def test_python_zaehler_entfernt(name):
    assert not hasattr(ampel, name), f"app.ampel.{name} hat keinen Produktaufrufer und soll entfallen"


def test_aufloesung_und_gewitterfarbe_bleiben():
    abo = {"display_config": {"ampel": {"template": "wandern", "thunder": {"mittel": "red"}}}}
    aufgeloest = ampel.resolve_ampel(abo)
    assert aufgeloest["template"] == "wandern"
    assert aufgeloest["thunder"]["mittel"] == "red"
    assert callable(ampel.thunder_color)
