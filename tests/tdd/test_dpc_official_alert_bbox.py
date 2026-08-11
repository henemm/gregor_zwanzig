"""AC-3 (Issue #1648) -- Regressionsschutz: der amtliche italienische
Warnpfad (`DpcSource`, `src/services/official_alerts/dpc.py`) ueberlebt den
Rueckbau der Radar-Quelle unveraendert.

SPEC: docs/specs/modules/fix_1648_radar_dpc_entfernen.md, AC-3.

Warum es diesen Test braucht: `official_alerts/dpc.py` importiert die
Italien-Bbox-Konstanten NICHT selbst, sondern aus `services.radar_service`
(Kopplung, keine Duplikation). Issue #1648 benennt genau diese Konstanten um.
Zieht die Umbenennung den Import dort nicht mit, wirft schon der Modulimport
`ImportError` -- und der amtliche Warnpfad, den die Spec ausdruecklich
unberuehrt lassen will, ist tot.

🔴 Dieser Test importiert die Bbox-Konstanten BEWUSST NICHT selbst. Er prueft
ausschliesslich das VERHALTEN von `DpcSource.covers()` gegen fest
eingetragene Soll-Wahrheitswerte (gemessen am Stand VOR der Umbenennung,
`origin/main` 4e5098a7: lat 36.0-47.5 / lon 6.5-19.0, Grenzen inklusiv).
Wuerde er die Konstanten importieren, pruefte er den Umbau statt seiner
Wirkung und bliebe auch dann gruen, wenn sich die Werte mitverschoben haetten.

Kern-Schicht: deterministisch, netzfrei, KEIN `live`-Marker (`covers()` ist
eine reine Funktion, der Bulletin-Abruf in `fetch()` wird hier nicht
angefasst). Bewusst eine eigene Datei statt einer Erweiterung von
`tests/tdd/test_dpc_bulletin_source.py`: die traegt ein modulweites
`pytestmark = pytest.mark.live` und liefe damit nie im Kern mit.

Dieser Test ist HEUTE SCHON GRUEN und muss es nach der Implementierung
bleiben -- er ist kein RED-Beweis, sondern der Waechter fuer den
Kollateralschaden.
"""
from __future__ import annotations

import pytest

# (lat, lon, erwartetes covers()-Ergebnis) -- Soll-Werte am Stand VOR der
# Umbenennung gemessen, nicht aus den Konstanten abgeleitet.
_COVERS_CASES = [
    # --- innerhalb ---
    (41.9028, 12.4964, True, "Rom, Mittelitalien"),
    (46.7248, 12.2254, True, "Karnischer Hoehenweg, IT-Seite (Zone Tren-A)"),
    (42.1244, 9.1339, True, "Vizzavona/Korsika -- liegt in der groben IT-Box"),
    (37.5, 15.1, True, "Sizilien/Catania"),
    # --- Grenzwerte: inklusiv ---
    (36.0, 12.0, True, "lat exakt auf der Suedgrenze"),
    (47.5, 12.0, True, "lat exakt auf der Nordgrenze"),
    (41.9, 6.5, True, "lon exakt auf der Westgrenze"),
    (41.9, 19.0, True, "lon exakt auf der Ostgrenze"),
    (36.0, 6.5, True, "Suedwest-Ecke exakt"),
    (47.5, 19.0, True, "Nordost-Ecke exakt"),
    # --- knapp ausserhalb ---
    (35.999, 12.0, False, "lat knapp unter der Suedgrenze"),
    (47.501, 12.0, False, "lat knapp ueber der Nordgrenze"),
    (41.9, 6.499, False, "lon knapp westlich der Westgrenze"),
    (41.9, 19.001, False, "lon knapp oestlich der Ostgrenze"),
    # --- eindeutig ausserhalb ---
    (43.2965, 5.3698, False, "Marseille (lon 5.37 < 6.5)"),
    (52.52, 13.40, False, "Berlin"),
    (35.0, -40.0, False, "Nordatlantik"),
]


@pytest.mark.parametrize(
    "lat,lon,expected,label",
    _COVERS_CASES,
    ids=[c[3] for c in _COVERS_CASES],
)
def test_ac3_dpc_official_source_covers_is_unchanged(lat, lon, expected, label):
    """AC-3: `DpcSource().covers()` liefert fuer feste Koordinaten (inkl.
    Grenzwerte) exakt dieselben Wahrheitswerte wie vor der Umbenennung der
    Bbox-Konstanten in `radar_service.py`."""
    from services.official_alerts.dpc import DpcSource

    assert DpcSource().covers(lat, lon) is expected, (
        f"AC-3: covers({lat}, {lon}) [{label}] muss {expected} bleiben -- "
        "der amtliche Warnpfad darf sich durch den Radar-Rueckbau nicht "
        "veraendern"
    )


def test_ac3_dpc_official_source_module_imports_without_radar_dpc():
    """AC-3 (Wirkort statt Codeort): der amtliche Warnpfad muss sich
    ueberhaupt noch importieren und benutzen lassen. Ein nicht mitgezogener
    Konstanten-Import in `official_alerts/dpc.py` faellt hier als `ImportError`
    beim Modulimport auf -- also VOR jeder covers()-Aussage."""
    from services.official_alerts.dpc import DPC_ZIP_URL, DpcSource

    source = DpcSource()

    assert source.name == "dpc", (
        f"AC-3: der Quellenname der amtlichen Warnungen bleibt 'dpc' (war: {source.name!r})"
    )
    assert DPC_ZIP_URL.startswith("https://raw.githubusercontent.com/"), (
        f"AC-3: der Bulletin-Host bleibt unveraendert (war: {DPC_ZIP_URL})"
    )
