"""#2988 S4 (AC-18): mit dem Spiegel sinkt der Eintrag von ``ampelModell.ts`` in der Ratsche.

SPEC: docs/specs/modules/rework_2988_ampel_ableitung.md, AC-18. Ratsche „Ein Katalog, eine Verarbeitung"
(ADR-0127, ``tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py``); Ausnahme vom Dateiinhalt-Verbot
wie die Ratsche selbst: gemessen wird mit dem echten Erkennungs-Kern, nicht per Textsuche.

Stand vor S4 (gemessen 2026-11-26): ``FRONTEND_LISTE`` 2 (``GRUPPEN_FOLGE`` Z. 59, ``HINWEIS_IDS``
Z. 306), ``FRONTEND_VERZWEIGUNG`` 1 (``windrichtungUngueltig``, Z. 242, Teil des Spiegels
``ampelFehler``). Der Spiegel traegt also nur die Verzweigung; die beiden Listen gehoeren zur
Darstellung des Reiters (siehe Bericht RED S4: Abweichung zu „FRONTEND_LISTE 2 auf 0" der Spec).

    uv run pytest tests/unit/test_2988_s4_ratsche_ampelmodell.py
"""
from __future__ import annotations

from collections import Counter

from tests.helpers.katalog_verarbeitung_scan import (
    FRONTEND_LISTE, FRONTEND_VERZWEIGUNG, lade_ausnahmen, scanne_alles,
)

AMPEL_MODELL = "frontend/src/lib/components/shared/wetter-tab/ampelModell.ts"
VOR_S4 = {FRONTEND_LISTE: 2, FRONTEND_VERZWEIGUNG: 1}


def _gemessen() -> Counter:
    return Counter(f.art for f in scanne_alles() if f.datei == AMPEL_MODELL)


def test_ac18_eintrag_ampelmodell_ist_gesunken():
    """Der gemessene Bestand von ``ampelModell.ts`` liegt unter dem Stand vor S4, keine Art steigt."""
    gemessen = _gemessen()
    for art, vorher in VOR_S4.items():
        assert gemessen[art] <= vorher, f"{art} gestiegen: {gemessen[art]} > {vorher}"
    assert gemessen[FRONTEND_VERZWEIGUNG] == 0, (
        "Verzweigung auf eine Metrik-ID im Spiegel (windrichtungUngueltig) steht noch in ampelModell.ts")
    assert sum(gemessen.values()) < sum(VOR_S4.values()), f"nicht gesunken: {dict(gemessen)}"


def test_ac18_ausnahmeliste_folgt_dem_abbau():
    """Die Liste traegt fuer ``ampelModell.ts`` genau den gemessenen Bestand (ohne Nullen)."""
    eintrag = lade_ausnahmen()["eintraege"].get(AMPEL_MODELL, {})
    assert eintrag == {art: n for art, n in _gemessen().items() if n}, f"Liste: {eintrag}"
    assert eintrag.get(FRONTEND_VERZWEIGUNG, 0) == 0, f"Liste traegt noch die Verzweigung: {eintrag}"
