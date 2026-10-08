"""RED-Tests AC-25 und AC-26: Kontext (call_source, Senken) reist in die Worker, ohne Leck.

Spec: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md (Abschnitt E, AC-25, AC-26)
Muster: tests/unit/test_call_source_ueber_threadgrenze.py
Senken: services/official_alerts/warn_egress.py (_fetch_failure_sink, _capture_id_sink)

RED-Erwartung: ``services.parallel_fetch`` existiert noch nicht -> ModuleNotFoundError.

Ausfuehren: uv run pytest tests/unit/test_parallel_fetch_context.py -v -rA --disable-socket
"""
from __future__ import annotations

import threading
import time

import pytest

PROVIDER = "open_meteo"


@pytest.fixture
def pf_env(monkeypatch):
    def setzen(workers: int) -> None:
        monkeypatch.setenv("GZ_PARALLEL_FETCH_WORKERS", str(workers))
        monkeypatch.setenv("GZ_PARALLEL_FETCH_SLOTS_OPEN_METEO", "8")

    yield setzen
    try:
        from services import parallel_fetch

        parallel_fetch._reset_for_tests()
    except ImportError:
        pass


@pytest.fixture
def thread_fehler():
    gesammelt: list = []
    alt = threading.excepthook
    threading.excepthook = lambda args: gesammelt.append(args.exc_value)
    yield gesammelt
    threading.excepthook = alt


@pytest.mark.timeout(30)
def test_call_source_und_senken_im_worker_und_danach_zurueckgesetzt(pf_env, thread_fehler):
    pf_env(workers=1)  # EIN Worker: die Folgeaufgabe laeuft garantiert im selben Thread
    from services import parallel_fetch as pf

    pf._reset_for_tests()
    from providers.call_log import override_call_source, resolve_call_source
    from services.official_alerts.warn_egress import (
        _record_capture_id,
        _record_fetch_failure,
        observe_capture_id,
        observe_fetch_failure,
    )

    beobachtet: list[tuple[int, str, int]] = []

    def fn(i):
        beobachtet.append((i, resolve_call_source(), threading.get_ident()))
        _record_fetch_failure()
        _record_capture_id(f"cap-{i}")
        return i

    with override_call_source("quelle-A"):
        with observe_fetch_failure() as fehler_senke, observe_capture_id() as cap_senke:
            ergebnis = pf.fetch_ordered(
                [0, 1, 2], fn, provider=PROVIDER, deadline_at=time.monotonic() + 20
            )
            assert [o.value for o in ergebnis] == [0, 1, 2]
            assert {q for _, q, _ in beobachtet} == {"quelle-A"}
            assert fehler_senke["failed"] is True
            assert sorted(cap_senke["capture_ids"]) == ["cap-0", "cap-1", "cap-2"]
            erster_worker = {t for _, _, t in beobachtet}
            assert len(erster_worker) == 1 and threading.get_ident() not in erster_worker
            ids_vorher = list(cap_senke["capture_ids"])

    # Folgeaufruf OHNE Override und ohne Senken, derselbe Worker (Executor-Groesse 1):
    # der Worker darf weder die alte Quelle noch die alten Senken behalten haben.
    beobachtet.clear()
    pf.fetch_ordered([7], fn, provider=PROVIDER, deadline_at=time.monotonic() + 20)
    assert len(beobachtet) == 1
    _, quelle, tid = beobachtet[0]
    assert tid in erster_worker, "Folgeaufgabe lief nicht im selben Worker (Test aussagelos)"
    assert quelle != "quelle-A", "call_source im Worker nicht zurueckgesetzt"
    assert "cap-7" not in cap_senke["capture_ids"]
    assert cap_senke["capture_ids"] == ids_vorher
    assert thread_fehler == []


def _nutzerlauf(pf, name, items, barriere, ergebnis, fehler_liste):
    from providers.call_log import override_call_source, resolve_call_source
    from services.official_alerts.warn_egress import (
        _record_capture_id,
        _record_fetch_failure,
        observe_capture_id,
        observe_fetch_failure,
    )

    quellen: list[str] = []

    def fn(i):
        time.sleep(0.05)
        quellen.append(resolve_call_source())
        _record_capture_id(f"{name}-{i}")
        if name == "A":
            _record_fetch_failure()
        return i

    try:
        with override_call_source(f"quelle-{name}"):
            with observe_fetch_failure() as fs, observe_capture_id() as cs:
                barriere.wait(10)  # beide Nutzer starten gleichzeitig
                pf.fetch_ordered(
                    items, fn, provider=PROVIDER, deadline_at=time.monotonic() + 20
                )
                ergebnis[name] = (set(quellen), fs["failed"], list(cs["capture_ids"]))
    except BaseException as exc:  # noqa: BLE001
        fehler_liste.append((name, exc))


@pytest.mark.timeout(30)
def test_zwei_nutzer_gleichzeitig_ohne_uebersprechen(pf_env, thread_fehler):
    pf_env(workers=8)
    from services import parallel_fetch as pf

    pf._reset_for_tests()
    barriere = threading.Barrier(2)
    ergebnis: dict = {}
    fehler: list = []
    threads = [
        threading.Thread(
            target=_nutzerlauf, args=(pf, n, list(range(6)), barriere, ergebnis, fehler)
        )
        for n in ("A", "B")
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
        assert not t.is_alive()
    assert fehler == []
    assert thread_fehler == []

    quellen_a, failed_a, caps_a = ergebnis["A"]
    quellen_b, failed_b, caps_b = ergebnis["B"]
    assert quellen_a == {"quelle-A"} and quellen_b == {"quelle-B"}
    assert failed_a is True and failed_b is False
    assert sorted(caps_a) == sorted(f"A-{i}" for i in range(6))
    assert sorted(caps_b) == sorted(f"B-{i}" for i in range(6))
