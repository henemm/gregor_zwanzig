"""Gemeinsame Test-Konstanten fuer die Profil-Ampel „allgemein" (Issue #2792 S1c-4b).

Seit S1c-4b sind ``ampel``/``preset`` an den Render-Einstiegen Pflicht ohne
Default. Bestandstests, die bisher still „allgemein" bekamen, reichen die
Vorlage jetzt explizit durch -- aus der Vorlage gebaut, nicht ueber
``resolve_ampel(None)``.
"""
from __future__ import annotations

import copy

from app.ampel_templates import AMPEL_TEMPLATES

#: Aufgeloeste Ampel der Vorlage „allgemein" (fuer ``ampel=``-Parameter).
AMPEL_ALLGEMEIN: dict = copy.deepcopy(AMPEL_TEMPLATES["allgemein"])

#: Rohes Vergleichs-Preset mit Vorlage „allgemein" (fuer ``preset=``-Parameter).
#: ``schedule: manual``: der Mail-Fuss „Naechster Versand" bleibt wie zuvor mit
#: ``preset=None`` „–" -- sonst rechnete er ab der Uhrzeit des Testlaufs und
#: Golden-/Fixture-Vergleiche wuerden zeitabhaengig.
PRESET_ALLGEMEIN: dict = {
    "schedule": "manual",
    "display_config": {"ampel": {"template": "allgemein"}},
}
