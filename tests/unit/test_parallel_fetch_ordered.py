"""RED-Tests AC-19 bis AC-21: geordnetes, fehlerisoliertes, begrenztes Parallel-Abrufen.

Spec: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md (Abschnitt E, AC-19..AC-21)
Festlegungen: docs/context/feat-1539-s1b-s2-abruf-baustein.md ("Schnittstellen-Festlegungen")

RED-Erwartung: ``services.parallel_fetch`` existiert noch nicht -> jeder Test scheitert
mit ModuleNotFoundError (Import steht bewusst IN der Testfunktion).

Ausfuehren: uv run pytest tests/unit/test_parallel_fetch_ordered.py -v -rA --disable-socket
"""
from __future__ import annotations

import threading
import time

import pytest

PROVIDER = "open_meteo"


@pytest.fixture
def pf_env(monkeypatch):
    """Setzt Env-Werte; Reset passiert im Test selbst (Modul darf fehlen)."""

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
def thread_fehler():
    """Sammelt nicht eingesammelte Thread-Ausnahmen selbst ein (C4-62)."""
    gesammelt: list = []
    alt = threading.excepthook
    threading.excepthook = lambda args: gesammelt.append(args.exc_value)
    yield gesammelt
    threading.excepthook = alt


def _importieren():
    from services import parallel_fetch

    parallel_fetch._reset_for_tests()
    return parallel_fetch


@pytest.mark.timeout(30)
def test_ergebnisse_in_eingabereihenfolge_bei_umgekehrter_fertigstellung(pf_env):
    pf_env(workers=8, slots=8)
    pf = _importieren()
    items = list(range(6))

    def fn(i):
        time.sleep((5 - i) * 0.08)  # Item 5 fertig zuerst, Item 0 zuletzt
        return f"wert-{i}"

    def lauf():
        return pf.fetch_ordered(
            items, fn, provider=PROVIDER, deadline_at=time.monotonic() + 20
        )

    erste, zweite = lauf(), lauf()
    for ergebnis in (erste, zweite):
        assert [o.index for o in ergebnis] == items
        assert [o.item for o in ergebnis] == items
        assert [o.value for o in ergebnis] == [f"wert-{i}" for i in items]
        assert all(o.error is None and o.skipped is None for o in ergebnis)
    assert [(o.index, o.item, o.value) for o in erste] == [
        (o.index, o.item, o.value) for o in zweite
    ]


@pytest.mark.timeout(30)
def test_teilausfall_nur_im_outcome_der_betroffenen_aufgabe(pf_env, thread_fehler):
    pf_env(workers=8, slots=8)
    pf = _importieren()

    def fn(i):
        if i == 2:
            raise ValueError("kaputt-2")
        return i * 10

    ergebnis = pf.fetch_ordered(
        list(range(5)), fn, provider=PROVIDER, deadline_at=time.monotonic() + 20
    )
    assert [o.index for o in ergebnis] == [0, 1, 2, 3, 4]
    fehler = [o for o in ergebnis if o.error is not None]
    assert [o.index for o in fehler] == [2]
    assert isinstance(fehler[0].error, ValueError)
    assert fehler[0].value is None
    for o in ergebnis:
        if o.index != 2:
            assert o.error is None and o.skipped is None
            assert o.value == o.index * 10
    time.sleep(0.2)
    assert thread_fehler == [], f"uneingesammelte Thread-Ausnahmen: {thread_fehler}"


@pytest.mark.timeout(30)
def test_spitzenzaehler_nie_ueber_slotzahl_und_retry_haelt_slot(pf_env, thread_fehler):
    slots = 2
    pf_env(workers=8, slots=slots)
    pf = _importieren()
    lock = threading.Lock()
    zustand = {"jetzt": 0, "spitze": 0}

    def betreten():
        with lock:
            zustand["jetzt"] += 1
            zustand["spitze"] = max(zustand["spitze"], zustand["jetzt"])

    def verlassen():
        with lock:
            zustand["jetzt"] -= 1

    def fn(i):
        betreten()
        try:
            if i == 0:
                # interne Wiederholungen: der Slot bleibt ueber alle Versuche belegt
                for _ in range(3):
                    time.sleep(0.1)
            else:
                time.sleep(0.1)
            return i
        finally:
            verlassen()

    ergebnis = pf.fetch_ordered(
        list(range(8)), fn, provider=PROVIDER, deadline_at=time.monotonic() + 25
    )
    assert [o.value for o in ergebnis] == list(range(8))
    assert zustand["spitze"] <= slots, f"Spitze {zustand['spitze']} > Slots {slots}"
    assert zustand["spitze"] == slots, "Parallelitaet wurde nie ausgeschoepft (Test waere vakuum)"
    assert thread_fehler == []
