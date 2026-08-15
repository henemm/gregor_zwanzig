"""AC-4 (#1765/#1839 Scheibe A): ``TimezoneFinder`` wird auch bei gleichzeitigem
Erstzugriff genau EINMAL gebaut.

Spec: docs/specs/modules/fix_1765_1839_sa_vorschau_entblockung.md

``src/utils/timezone.py`` haelt ``_tf_instance`` als Lazy-Singleton OHNE Sperre.
Solange alle Vorschau-Handler ``async def`` ohne ``await`` waren, hat der
blockierte Event-Loop sie unfreiwillig serialisiert — die Luecke war nie
erreichbar. Ae1 (``async def`` → ``def``) laesst sie erstmals wirklich parallel
laufen: Beide Vorschau-Pfade fuehren hierher (Trip ueber ``tz_for_coords()``,
Vergleich ueber ``location_tz()``), und ``TimezoneFinder`` laedt ~12 MB.

Geprueft wird die **Wirkung** — die tatsaechliche Zahl der Konstruktionen —,
nicht die Anwesenheit eines ``Lock()`` im Quelltext.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest


class _ZaehlenderFinder:
    """Leichtgewichtiger Ersatz fuer ``TimezoneFinder`` (~12 MB) mit Zaehler.

    Ersetzt wird ausschliesslich das TEURE, fremde Objekt — die zu pruefende
    Logik (``_get_tf`` und der Weg dorthin) bleibt die echte. Die Zusicherung
    lautet "genau eine Konstruktion", nicht "TimezoneFinder rechnet richtig".
    """

    aufbauten = 0
    _zaehler_lock = threading.Lock()
    #: Trifft ein zweiter Thread waehrend der Konstruktion ebenfalls hier ein,
    #: gibt die Barriere sofort frei (= ungesicherter Fall). Bleibt er aus,
    #: laeuft die Barriere in den Timeout — der gesicherte Fall wartet also
    #: einmalig 1 s statt sich auf Zufalls-Timing zu verlassen.
    treffpunkt = threading.Barrier(2)

    def __init__(self) -> None:
        with _ZaehlenderFinder._zaehler_lock:
            _ZaehlenderFinder.aufbauten += 1
        try:
            _ZaehlenderFinder.treffpunkt.wait(timeout=1.0)
        except threading.BrokenBarrierError:
            pass  # allein angekommen — genau das ist der Zielzustand

    def timezone_at(self, lat=None, lng=None):  # noqa: ANN001, ARG002
        return "Europe/Vienna"


@pytest.fixture
def leerer_zeitzonen_zustand(monkeypatch):
    """Setzt ``_tf_instance`` auf den Ausgangszustand (None) und stellt ihn
    danach wieder her — sonst vergiftet dieser Test jeden Folgetest, der eine
    Zeitzone aufloest."""
    from utils import timezone as tz_modul
    import timezonefinder

    vorher = tz_modul._tf_instance
    tz_modul._tf_instance = None
    _ZaehlenderFinder.aufbauten = 0
    _ZaehlenderFinder.treffpunkt = threading.Barrier(2)
    monkeypatch.setattr(timezonefinder, "TimezoneFinder", _ZaehlenderFinder)
    try:
        yield tz_modul
    finally:
        tz_modul._tf_instance = vorher


def test_gleichzeitiger_erstzugriff_baut_timezonefinder_genau_einmal(
    leerer_zeitzonen_zustand,
):
    """AC-4: Zwei Threads treffen per Barriere garantiert gleichzeitig auf den
    leeren Zustand; danach ist der Konstruktions-Zaehler exakt 1.

    Die beiden Threads nehmen bewusst die zwei ECHTEN Einstiege der beiden
    Vorschau-Pfade: ``tz_for_coords()`` (Trip, ``preview_service.py:180``) und
    ``location_tz()`` (Vergleich, ``comparison_engine.py:155``).
    """
    tz_modul = leerer_zeitzonen_zustand
    start = threading.Barrier(2)
    ergebnisse: dict[str, object] = {}
    fehler: list[BaseException] = []

    def trip_pfad():
        try:
            start.wait(timeout=5)
            ergebnisse["trip"] = tz_modul.tz_for_coords(47.2692, 11.4041)
        except BaseException as e:  # noqa: BLE001
            fehler.append(e)

    def vergleichs_pfad():
        try:
            start.wait(timeout=5)
            ort = SimpleNamespace(timezone=None, lat=47.2692, lon=11.4041)
            ergebnisse["vergleich"] = tz_modul.location_tz(ort)
        except BaseException as e:  # noqa: BLE001
            fehler.append(e)

    threads = [
        threading.Thread(target=trip_pfad, name="trip"),
        threading.Thread(target=vergleichs_pfad, name="vergleich"),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
        assert not t.is_alive(), f"Thread {t.name} haengt — Verklemmung in _get_tf()?"

    assert not fehler, f"Ausnahme in einem der Threads: {fehler!r}"

    assert _ZaehlenderFinder.aufbauten == 1, (
        f"TimezoneFinder wurde {_ZaehlenderFinder.aufbauten}x gebaut statt genau 1x. "
        "Zwei gleichzeitige Vorschau-Anfragen sehen beide '_tf_instance is None' und "
        "laden je ~12 MB (kurzzeitig 24 MB), eine Instanz wird kommentarlos verworfen. "
        "Abhilfe: doppelt gepruefte Sperre in _get_tf() nach dem Muster "
        "services/weather_cache.py:300-305 (AC-4, Spec "
        "fix_1765_1839_sa_vorschau_entblockung.md)."
    )
    assert str(ergebnisse["trip"]) == "Europe/Vienna"
    assert str(ergebnisse["vergleich"]) == "Europe/Vienna"


def test_beide_threads_erhalten_dieselbe_instanz(leerer_zeitzonen_zustand):
    """AC-4, zweite Haelfte: ``... und beide Threads erhalten dieselbe Instanz``.

    Der Zaehler allein wuerde eine Umsetzung durchlassen, die zwar nur einmal
    baut, aber je Thread ein eigenes Objekt zurueckgibt (z.B. thread-lokaler
    Speicher statt Prozess-Singleton).
    """
    tz_modul = leerer_zeitzonen_zustand
    start = threading.Barrier(2)
    instanzen: list[object] = []
    sperre = threading.Lock()

    def hole():
        start.wait(timeout=5)
        instanz = tz_modul._get_tf()
        with sperre:
            instanzen.append(instanz)

    threads = [threading.Thread(target=hole) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert len(instanzen) == 2, "Beide Threads muessen eine Instanz erhalten haben"
    assert instanzen[0] is instanzen[1], (
        "Die beiden Threads haben VERSCHIEDENE TimezoneFinder-Instanzen erhalten — "
        "_get_tf() muss prozessweit dieselbe Instanz liefern (AC-4)."
    )
