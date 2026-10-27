"""RED-Test AC-24: verschachteltes ``fetch_ordered`` blockiert den vollen Executor nicht.

Spec: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md (Abschnitt E, AC-24)
Festlegungen: docs/context/feat-1539-s1b-s2-abruf-baustein.md

RED-Erwartung: ``services.parallel_fetch`` existiert noch nicht -> ModuleNotFoundError.

Ausfuehren: uv run pytest tests/unit/test_parallel_fetch_nested.py -v -rA --disable-socket
"""
from __future__ import annotations

import threading
import time

import pytest

PROVIDER = "open_meteo"


@pytest.fixture
def pf_env(monkeypatch):
    monkeypatch.setenv("GZ_PARALLEL_FETCH_WORKERS", "1")
    monkeypatch.setenv("GZ_PARALLEL_FETCH_SLOTS_OPEN_METEO", "8")
    yield
    try:
        from services import parallel_fetch

        parallel_fetch._reset_for_tests()
    except ImportError:
        pass


@pytest.mark.timeout(30)
def test_verschachtelter_aufruf_laeuft_inline_im_selben_thread(pf_env):
    from services import parallel_fetch as pf

    pf._reset_for_tests()
    aeusserer_thread: dict[int, int] = {}
    innere_threads: list[tuple[int, int]] = []  # (aeusseres item, thread-id)
    ergebnis_box: dict = {}
    fehler: list = []

    def innen(j):
        innere_threads.append((j // 10, threading.get_ident()))
        return j + 1

    def aussen(i):
        aeusserer_thread[i] = threading.get_ident()
        inner = pf.fetch_ordered(
            [i * 10, i * 10 + 1],
            innen,
            provider=PROVIDER,
            deadline_at=time.monotonic() + 20,
        )
        return [o.value for o in inner]

    def lauf():
        try:
            ergebnis_box["r"] = pf.fetch_ordered(
                [0, 1], aussen, provider=PROVIDER, deadline_at=time.monotonic() + 20
            )
        except BaseException as exc:  # noqa: BLE001
            fehler.append(exc)

    t0 = time.monotonic()
    th = threading.Thread(target=lauf, daemon=True)
    th.start()
    th.join(10)
    assert not th.is_alive(), "Deadlock: verschachtelter Aufruf endet nicht"
    assert time.monotonic() - t0 < 8, "Aufruf kam nur ueber die Frist zurueck (Deadlock-Aufloesung)"
    assert fehler == []

    ergebnis = ergebnis_box["r"]
    assert [o.skipped for o in ergebnis] == [None, None]
    assert [o.error for o in ergebnis] == [None, None]
    assert [o.value for o in ergebnis] == [[1, 2], [11, 12]]
    assert len(innere_threads) == 4
    for item, tid in innere_threads:
        assert tid == aeusserer_thread[item], "innerer Aufruf lief nicht im Thread des Aufrufers"
