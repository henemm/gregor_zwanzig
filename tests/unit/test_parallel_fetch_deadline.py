"""RED-Tests AC-22 und AC-23: Frist ist hart, deadline vs. timeout, kein unbegrenztes Warten.

Spec: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md (Abschnitt E, AC-22, AC-23; ADR-0038)
Festlegungen: docs/context/feat-1539-s1b-s2-abruf-baustein.md

RED-Erwartung: ``services.parallel_fetch`` existiert noch nicht -> ModuleNotFoundError.

Ausfuehren: uv run pytest tests/unit/test_parallel_fetch_deadline.py -v -rA --disable-socket
"""
from __future__ import annotations

import threading
import time

import pytest

PROVIDER = "open_meteo"
TOLERANZ = 0.6  # Sekunden ueber der Frist


@pytest.fixture
def pf_env(monkeypatch):
    def setzen(workers: int, slots: int) -> None:
        monkeypatch.setenv("GZ_PARALLEL_FETCH_WORKERS", str(workers))
        monkeypatch.setenv("GZ_PARALLEL_FETCH_SLOTS_OPEN_METEO", str(slots))

    yield setzen
    try:
        from services import parallel_fetch

        parallel_fetch._reset_for_tests()
    except ImportError:
        pass


@pytest.fixture
def freigabe():
    """Event, mit dem haengende Worker am Testende freigegeben werden."""
    ereignis = threading.Event()
    yield ereignis
    ereignis.set()


def _importieren():
    from services import parallel_fetch

    parallel_fetch._reset_for_tests()
    return parallel_fetch


@pytest.mark.timeout(30)
def test_deadline_und_timeout_sind_unterscheidbar(pf_env, freigabe):
    pf_env(workers=4, slots=1)
    pf = _importieren()
    gestartet = []

    def fn(i):
        gestartet.append(i)
        if i == 0:
            freigabe.wait(15)  # laeuft ueber die Frist hinaus
        return f"wert-{i}"

    frist = 0.4
    t0 = time.monotonic()
    ergebnis = pf.fetch_ordered(
        [0, 1, 2, 3], fn, provider=PROVIDER, deadline_at=t0 + frist
    )
    dauer = time.monotonic() - t0
    assert dauer < frist + TOLERANZ, f"Rueckkehr nach {dauer:.2f}s, Frist {frist}s"
    assert [o.index for o in ergebnis] == [0, 1, 2, 3]

    assert ergebnis[0].skipped == "timeout"
    assert ergebnis[0].value is None  # spaetes Ergebnis verworfen
    for o in ergebnis[1:]:
        assert o.skipped == "deadline", (o.index, o.skipped)
        assert o.value is None
    assert 1 not in gestartet and 2 not in gestartet and 3 not in gestartet
    assert {o.skipped for o in ergebnis} == {"timeout", "deadline"}


@pytest.mark.timeout(30)
def test_verwaister_worker_haelt_slot_folgeaufruf_kehrt_fristgerecht_zurueck(
    pf_env, freigabe
):
    pf_env(workers=4, slots=1)
    pf = _importieren()

    def haengend(i):
        freigabe.wait(20)
        return i

    vorlauf = pf.fetch_ordered(
        [0], haengend, provider=PROVIDER, deadline_at=time.monotonic() + 0.2
    )
    assert vorlauf[0].skipped == "timeout"

    aufgerufen = []

    def fn(i):
        aufgerufen.append(i)
        return i

    frist = 0.4
    t0 = time.monotonic()
    ergebnis = pf.fetch_ordered(
        [1, 2], fn, provider=PROVIDER, deadline_at=t0 + frist
    )
    dauer = time.monotonic() - t0
    assert dauer < frist + TOLERANZ, (
        f"Folgeaufruf kehrte erst nach {dauer:.2f}s zurueck (Frist {frist}s)"
    )
    assert [o.skipped for o in ergebnis] == ["deadline", "deadline"]
    assert aufgerufen == []
