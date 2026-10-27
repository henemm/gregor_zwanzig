"""Reparatur eines unterbrochenen ``freezegun``-Starts (CI-Rot 2026-10-22, Familie A).

``freezegun.api._freeze_time.start()`` legt den neuen Zeitpunkt ZUERST auf den
globalen Stapel ``freeze_factories`` und patcht DANACH alle geladenen Module
(``datetime``, ``time`` ...). Trifft eine Ausnahme mitten in diese Schleife --
im CI das SIGALRM von pytest-timeout (``Failed: Timeout``) --, dann laeuft
``__exit__``/``stop()`` nie: der Stapel behaelt einen toten Eintrag, ein Teil
der Module zeigt auf ``FakeDatetime``, der Rest auf die echte Klasse. Jeder
spaetere ``freeze_time`` glaubt "schon gestartet" und patcht nichts mehr --
in bereits geladenen Testmodulen laeuft dann die ECHTE Uhr. Gemessen am
2026-10-22 08:20 UTC auf ``main``: ein Timeout in
``tests/tdd/test_vorlauf_messort_ereigniszeit.py`` zog 136 Folge-Fehlschlaege
nach sich (``test_freeze_time_stellt_die_uhr_wirklich`` sah die Wanduhr).

``tiefe()`` und ``reparieren()`` gehoeren zur autouse-Fixture
``_freezegun_stapel_waechter`` in ``tests/conftest.py``; der Selbsttest steht
in ``tests/test_freezegun_stapel_reparatur.py``.
"""
from __future__ import annotations

import freezegun.api as _fg
from freezegun import freeze_time


def tiefe() -> int:
    """Aktuelle Tiefe des globalen freezegun-Stapels."""
    return len(_fg.freeze_factories)


def module_sind_gepatcht() -> bool:
    """Zeigt ``datetime``/``time`` auf freezeguns Fakes?"""
    return _fg.datetime.datetime is _fg.FakeDatetime or _fg.time.time is _fg.fake_time


def reparieren(zieltiefe: int) -> None:
    """Den Stapel auf ``zieltiefe`` kuerzen und -- bei Tiefe 0 -- alle Module
    konsequent auf die echte Uhr zuruecksetzen.

    Der Rueckbau benutzt freezeguns eigenen Weg: ein frischer Freezer patcht
    erst konsistent neu (``start()``) und nimmt dann alles zurueck
    (``stop()``). Mit geleertem ``modules_at_start`` durchsucht ``stop()``
    JEDES geladene Modul nach Fake-Resten -- auch die, die der unterbrochene
    Start schon umgebogen hatte."""
    # Den Hilfs-Freezer VOR dem Kuerzen und aus einem echten datetime bauen:
    # ein String ginge durch dateutil und damit durch ``datetime.now()`` --
    # das liest bei gepatchten Modulen und leerem Stapel ``tz_offsets[-1]``
    # und bricht mit IndexError ab.
    freezer = freeze_time(_fg.real_datetime(2000, 1, 1))
    for stapel in (_fg.freeze_factories, _fg.tz_offsets, _fg.ignore_lists, _fg.tick_flags):
        del stapel[zieltiefe:]
    if zieltiefe > 0 or not module_sind_gepatcht():
        return
    freezer.start()
    freezer.modules_at_start = set()
    freezer.stop()
