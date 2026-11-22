"""Sonde AC-4 (#3209): unbeteiligter Test OHNE ``real_data_root``. Er wartet,
bis die Echtdaten-Gruppe (anderer Worker) ihr Schreibfenster im echten Baum
geoeffnet hat, und endet, waehrend es offen ist. Sein Waechter darf diese
legitime Gruppenaenderung NICHT als Verstoss werten.

Eigene ``xdist_group("beobachter")``, damit ``--dist loadgroup`` ihn sicher
auf einen anderen Worker als die Echtdaten-Gruppe legt (beide Gruppen sind
die ersten beiden Arbeitseinheiten, zwei Worker).
"""
from __future__ import annotations

import pytest

from _probe_util import REAL_USERS, probe_dir, protokolliere, warte_auf


@pytest.mark.xdist_group("beobachter")
def test_probe_ac4_beobachter_sieht_fenster():
    fenster = REAL_USERS / "probe-3209-ac4-fenster" / "fenster.txt"
    gesehen = warte_auf(fenster, 15.0)
    protokolliere("ac4_beobachter", fenster_gesehen=gesehen)
    (probe_dir() / "beobachter_fertig").write_text("ja\n", encoding="utf-8")
    assert gesehen, (
        "Nachweis ungueltig: das Schreibfenster der Echtdaten-Gruppe war nie "
        "sichtbar (gleicher Worker oder Gruppe lief nicht)."
    )
