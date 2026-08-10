"""Issue #1667 S2 — Paritaet der HH:MM-Formatierung (Python-Seite).

AC-1: Eigenschaftsnachweis der Inertheit ueber den vollen Minutenbereich
      0..1439 gegen die alte Klemmformel als lokale Referenz.
AC-3: Randfaelle 1439/1440/1441/2879 gegen die GEMEINSAME JSON-Fixture, die
      auch der Go- und der TS-Test lesen.

Pfadregel #1409: Die Fixture wird relativ zur eigenen Testdatei aufgeloest,
nie ueber einen festen Hauptrepo-Pfad -- sonst pruefte ein Worktree-Lauf eine
fremde Kopie und meldete falsches Gruen.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.naismith import _format_hhmm

_FIXTURE = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "naismith_hhmm_wrap.json"
)

_TAG_MINUTEN = 24 * 60


def _referenz_klemme(total_min: int) -> str:
    """Die ALTE Formel (min(m, 1439)) als lokale Referenz fuer AC-1.

    Bewusst hier hinterlegt statt aus dem Produktivcode importiert: nach dem
    Fix existiert sie dort nicht mehr, der Inertheits-Nachweis braucht sie
    aber weiterhin als Vergleichsmassstab.
    """
    m = min(total_min, _TAG_MINUTEN - 1)
    return f"{m // 60:02d}:{m % 60:02d}"


def _faelle() -> list:
    daten = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return daten["faelle"]


def test_fixture_traegt_die_vier_randfaelle():
    """Ohne diese Zusicherung koennte eine leere Fixture-Liste die
    AC-3-Parametrisierung still auf null Faelle schrumpfen lassen und
    'nichts geprueft' als gruen ausgeben."""
    werte = sorted(f["total_min"] for f in _faelle())
    assert werte == [1439, 1440, 1441, 2879], f"Fixture-Randfaelle veraendert: {werte}"


def test_ac1_normalbereich_bit_identisch_zur_alten_klemme():
    """AC-1: fuer jede Minute 0..1439 liefert die Implementierung denselben
    String wie die alte Klemme -- der Alltagsfall bleibt unveraendert."""
    abweichungen = [
        (m, _referenz_klemme(m), _format_hhmm(m))
        for m in range(_TAG_MINUTEN)
        if _format_hhmm(m) != _referenz_klemme(m)
    ]
    assert abweichungen == [], (
        f"{len(abweichungen)} Minutenwerte im Normalbereich weichen von der alten "
        f"Klemmformel ab (erste: {abweichungen[:3]})"
    )


@pytest.mark.parametrize("fall", _faelle(), ids=lambda f: f["id"])
def test_ac3_randfaelle_gegen_gemeinsame_fixture(fall):
    """AC-3: dieselben vier Faelle, die Go und TS lesen."""
    ist = _format_hhmm(fall["total_min"])
    assert ist == fall["expected_hhmm"], (
        f"total_min={fall['total_min']} ({fall['id']}): erwartet "
        f"{fall['expected_hhmm']!r}, bekommen {ist!r} -- {fall['kommentar']}"
    )
