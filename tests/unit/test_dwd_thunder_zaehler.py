"""#2554: Zaehler `versucht`/`fehlgeschlagen` bleiben unter Threads exakt.

Echte Threads, kein Mock. Faellt der Lock in `_thunder_zaehle` weg, gehen bei
kleinem Switch-Intervall Inkremente verloren und der Test wird rot.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from providers import dwd  # noqa: E402


class _GibtGilFreiZustand(dict):
    """dict, dessen Lesezugriff auf einen Zaehler den GIL abgibt: macht die
    Luecke zwischen Lesen und Schreiben von `+= 1` deterministisch sichtbar
    (unter Python 3.12 allein per Switch-Intervall nicht zuverlaessig)."""

    def __getitem__(self, schluessel):
        wert = super().__getitem__(schluessel)
        if schluessel != "lock":
            time.sleep(0)  # GIL-Abgabe NACH dem Lesen, VOR dem Schreiben
        return wert


def test_zaehler_verliert_unter_threads_keine_inkremente():
    zustand = _GibtGilFreiZustand(
        versucht=0, fehlgeschlagen=0, lock=threading.Lock()
    )
    alt = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        def arbeit():
            for _ in range(2000):
                dwd._thunder_zaehle(zustand, "versucht")
                dwd._thunder_zaehle(zustand, "fehlgeschlagen")

        threads = [threading.Thread(target=arbeit) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        sys.setswitchinterval(alt)
    assert zustand["versucht"] == 8 * 2000
    assert zustand["fehlgeschlagen"] == 8 * 2000
