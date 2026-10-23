"""Ein unterbrochener ``freeze_time``-Start darf den Rest des Laufs nicht vergiften.

Nachgestellt wird der CI-Befund vom 2026-10-22 (run 39747019320): pytest-timeout
warf sein ``Failed`` mitten in ``freezegun.api._freeze_time.start()``; der
globale Stapel behielt einen toten Eintrag, und 136 spaetere Tests sahen trotz
``freeze_time`` die echte Wanduhr (``test_freeze_time_stellt_die_uhr_wirklich``).

Die Unterbrechung wird HIER ohne Mock erzeugt: ein echtes Modul in
``sys.modules``, dessen ``dir()`` wirft, bringt die Modul-Schleife von
``start()`` genau dort zum Abbruch, wo das Signal im CI einschlug -- nach dem
``append`` auf den Stapel, vor dem Ende des Patchens.
"""
from __future__ import annotations

import datetime as _dt
import sys
import time as _time
import types
from datetime import datetime, timezone

import freezegun.api as fg
import pytest
from freezegun import freeze_time

from tests.helpers.freezegun_stapel import module_sind_gepatcht, reparieren, tiefe

GEFROREN = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
#: Zeitpunkt des toten Stapeleintrags -- bewusst fern jeder plausiblen Testuhr.
TOT = datetime(1999, 1, 1, tzinfo=timezone.utc)
_ZUSTAND: dict[str, int] = {}


class _Abbruch(Exception):
    """Spielt das ``Failed`` von pytest-timeout."""


class _StoerModul(types.ModuleType):
    def __dir__(self):  # noqa: D401 -- genau das trifft freezeguns Modul-Schleife
        raise _Abbruch("SIGALRM mitten in freezegun.start()")


def _start_unterbrechen() -> None:
    if tiefe() > 0:
        # Unter einer aeusseren Uhr (GZ_TEST_WALL_CLOCK_UTC, Session-Fixture)
        # patcht ein innerer Start keine Module mehr und ist in der Schleife
        # nicht unterbrechbar. Der Leak ist dann ein gestarteter, nie
        # gestoppter Freezer (Timeout NACH dem Start) -- auch er laesst jeden
        # Folgetest die falsche Uhr lesen.
        freeze_time(TOT).start()
        return
    name = "gz_stoermodul_freezegun_start"
    sys.modules[name] = _StoerModul(name)
    try:
        with pytest.raises(_Abbruch):
            with freeze_time(TOT):
                pass  # pragma: no cover -- der Start kommt nie bis hierher
    finally:
        sys.modules.pop(name, None)


def _uhr_ist_echt() -> bool:
    return abs((datetime.now(timezone.utc) - fg.real_datetime.now(timezone.utc)).total_seconds()) < 5


def test_unterbrochener_start_hinterlaesst_toten_stapeleintrag_und_reparatur_raeumt_ihn():
    """Direkter Nachweis: der kaputte Zustand ist echt, und ``reparieren()``
    stellt Stapel, Modulreferenzen und die Wirkung von ``freeze_time`` wieder her."""
    basis = tiefe()
    _start_unterbrechen()
    assert tiefe() == basis + 1, "Testvoraussetzung: der tote Eintrag liegt auf dem Stapel"
    if basis == 0:
        assert module_sind_gepatcht(), "Testvoraussetzung: Module zeigen auf die Fakes"
    else:
        assert datetime.now(timezone.utc) == TOT, "Testvoraussetzung: der tote Eintrag stellt die Uhr"

    reparieren(basis)

    assert tiefe() == basis
    if basis == 0:
        assert _dt.datetime is fg.real_datetime and _dt.date is fg.real_date
        assert _time.time is fg.real_time and _time.monotonic is fg.real_monotonic
        assert datetime is fg.real_datetime, "die Referenz dieses Moduls ist wieder echt"
        assert _uhr_ist_echt()
    assert datetime.now(timezone.utc).year != TOT.year, "der tote Eintrag stellt die Uhr nicht mehr"
    with freeze_time(GEFROREN):
        assert datetime.now(timezone.utc) == GEFROREN, "freeze_time wirkt nach der Reparatur wieder"
    assert tiefe() == basis


def test_a_test_hinterlaesst_den_unterbrochenen_start_absichtlich():
    """Erster Teil des Fixture-Nachweises: dieser Test endet BEWUSST im kaputten
    Zustand -- genau wie ein per Timeout abgebrochener Test im CI."""
    _ZUSTAND["basis"] = tiefe()
    _start_unterbrechen()
    assert tiefe() == _ZUSTAND["basis"] + 1


def test_b_folgetest_sieht_dank_fixture_eine_saubere_gestellte_uhr():
    """Zweiter Teil: ohne ``_freezegun_stapel_waechter`` (tests/conftest.py)
    liefe hier die echte Wanduhr trotz ``freeze_time`` -- der 136-fache CI-Fehler."""
    basis = _ZUSTAND.get("basis", tiefe())
    assert tiefe() == basis, "der tote Eintrag des Vorgaengers liegt noch auf dem Stapel"
    if basis == 0:
        assert datetime is fg.real_datetime and _uhr_ist_echt()
    assert datetime.now(timezone.utc).year != TOT.year, "die Uhr des Vorgaengers haengt nicht nach"
    with freeze_time(GEFROREN):
        assert datetime.now(timezone.utc) == GEFROREN
        assert _dt.date.today() == GEFROREN.date()
