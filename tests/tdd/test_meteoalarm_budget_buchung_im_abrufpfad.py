"""Issue #1539 (Fix-Loop 1, Adversary F002): das MeteoAlarm-Tagesbudget wird am
PRODUKTIVEN Aufrufer gebucht, nicht nur an der Gate-Methode.

SPEC: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md (AC-7, Wirkung am Aufrufer)

Weg: ``meteoalarm._get_cached_index`` -> ``_fetch_page`` -> ``_do_request`` ->
``MeteoAlarmBudgetGate.reserve()``. Gefakt wird NUR der Netzrand
(``httpx.get``, zaehlend, liefert eine leere 204-Antwort); Budget-Datei,
Gate, Cache und Egress-Kette sind echt (Datenwurzel per Autouse-Isolation).

Ausfuehrung:
    uv run pytest tests/tdd/test_meteoalarm_budget_buchung_im_abrufpfad.py -v -rA --disable-socket
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.loader import get_data_root
from services.official_alerts import meteoalarm

_REPO_SRC = Path(__file__).resolve().parents[2] / "src"


class _Netzrand:
    """Zaehlender Ersatz fuer ``httpx.get`` -- das ist der Netzrand."""

    def __init__(self) -> None:
        self.aufrufe = 0

    def __call__(self, url, **kwargs):
        self.aufrufe += 1
        return httpx.Response(204, request=httpx.Request("GET", url))


def _calls() -> int:
    pfad = get_data_root() / "diagnostics" / "meteoalarm_budget.json"
    if not pfad.exists():
        return 0
    return json.loads(pfad.read_text())["calls"]


def _setze_calls(n: int) -> None:
    from services.official_alerts.meteoalarm_budget import MeteoAlarmBudgetGate

    gate = MeteoAlarmBudgetGate()
    for _ in range(n):
        gate.record_call()


@pytest.fixture
def netz(monkeypatch):
    assert meteoalarm.__file__.startswith(str(_REPO_SRC)), "Pruefling nicht aus diesem Baum"
    meteoalarm._index_cache.clear()
    rand = _Netzrand()
    monkeypatch.setattr(meteoalarm.httpx, "get", rand)
    yield rand
    meteoalarm._index_cache.clear()


def test_restbudget_abruf_bucht_genau_einen_call_in_der_budgetdatei(netz, monkeypatch):
    """Restbudget vorhanden: der Abruf geht raus UND die Buchung steht in der
    Budget-Datei (``reserve`` am Aufrufer, nicht ``allow``)."""
    monkeypatch.setenv("GZ_METEOALARM_DAILY_BUDGET", "5")
    _setze_calls(2)

    meteoalarm._get_cached_index("AT")

    assert netz.aufrufe == 1
    assert _calls() == 3, "Abruf wurde nicht ins Tagesbudget gebucht"


def test_ausgeschoepftes_budget_abruf_erreicht_den_upstream_nicht(netz, monkeypatch):
    """Budget ausgeschoepft: kein einziger Request erreicht den Netzrand, der
    Zaehler bleibt stehen, der Index gilt als nicht abrufbar."""
    monkeypatch.setenv("GZ_METEOALARM_DAILY_BUDGET", "2")
    _setze_calls(2)

    ergebnis = meteoalarm._get_cached_index("AT")

    assert netz.aufrufe == 0, "Upstream-Request trotz ausgeschoepftem Tagesbudget"
    assert _calls() == 2
    assert ergebnis is None
