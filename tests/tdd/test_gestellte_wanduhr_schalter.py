"""Selbsttest des Uhr-Schalters (Issue #2096, Adversary-Finding F001).

Der Schalter ``GZ_TEST_WALL_CLOCK_UTC`` (Session-Fixture
``_gestellte_wanduhr`` in ``tests/conftest.py``) ist das Werkzeug, mit dem
AC-10 NACHGEWIESEN wird: dieselbe Testmenge um 12:00, 21:06, 22:50 und 23:58
UTC, viermal gruen. Der Adversary hat die Fixture komplett stillgelegt
(``if not roh:`` -> ``if not roh or True:``) und trotzdem 120 passed, 0
failed gemessen -- kein einziger Test wurde rot.

Der Grund ist harmlos (die Zeitunabhaengigkeit kommt inzwischen aus den
``@freeze_time``-Dekoratoren der einzelnen Tests, die also robuster sind als
gefordert), die Folge ist es nicht: hoert der Schalter still auf zu wirken,
sehen die vier Laeufe weiterhin gruen aus und messen nichts. Ein
Nachweiswerkzeug ohne Selbsttest ist genau der blinde Waechter, gegen den
dieses ganze Ticket geschrieben ist.

Zwei Faelle, beide mock-frei:

1. ``test_uhr_folgt_dem_schalter`` prueft den Zustand des LAUFENDEN Prozesses
   gegen eine von freezegun UNABHAENGIGE Zeitquelle -- den Zeitstempel, den
   der Kernel einer soeben geschriebenen Datei gibt. Ohne Schalter muss die
   Prozessuhr dieser Kernel-Uhr folgen, mit Schalter dem Anker.
2. ``test_schalter_bewegt_die_uhr_im_untergeordneten_lauf`` startet einen
   ECHTEN zweiten pytest-Lauf ueber genau diesen ersten Fall, mit dem
   Schalter auf einem festen Zeitpunkt in der VERGANGENHEIT. Nur dieser Fall
   ist der eigentliche Waechter: er laeuft in jedem Testlauf, unabhaengig
   davon, ob die Variable von aussen gesetzt ist, und sein Anker kann per
   Konstruktion nie zufaellig mit der echten Uhr zusammenfallen.

Der Anker wird NICHT nachgerechnet, sondern aus derselben Quelle bezogen,
aus der ihn die Fixture bildet (``tests/helpers/wanduhr.py``) -- ein
Selbsttest gegen die eigene Kopie bemerkte eine abweichende Fixture nicht.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from tests.helpers.wanduhr import ENV_NAME, anker_aus, roh_wert

# Fester Zeitpunkt in der VERGANGENHEIT (voller ISO-Stempel, damit die
# Tagesableitung der `HH:MM`-Form aussen vor bleibt). Weil er vergangen ist,
# kann er nie zufaellig der echten Uhr entsprechen -- genau deshalb taugt er
# als Unterscheidungsmerkmal "Uhr gestellt oder nicht".
_ANKER_VERGANGENHEIT = "2026-08-22T03:14:00+00:00"

# Die Fixture laeuft mit `tick=True`; zwischen ihrem Start und diesem Test
# vergeht echte Zeit. Die Toleranz deckt den Aufbau der Session-Fixtures ab
# und ist trotzdem winzig gegen den Abstand, den eine NICHT gestellte Uhr zu
# `_ANKER_VERGANGENHEIT` haette (Tage).
_TOLERANZ_S = 300

_EIGENER_FALL = "test_uhr_folgt_dem_schalter"


def _kernel_uhr(tmp_path: Path) -> datetime:
    """Eine von freezegun UNABHAENGIGE Zeitquelle.

    freezegun ersetzt ``datetime``/``time.time`` im Prozess, nicht aber die
    Uhr des Kernels: den Zeitstempel einer soeben geschriebenen Datei setzt
    das Dateisystem. Ohne eine solche zweite Quelle liesse sich "die Uhr ist
    gestellt" ueberhaupt nicht von "die Uhr laeuft normal" unterscheiden --
    man haette nur die gestellte Uhr gegen sich selbst geprueft.
    """
    probe = tmp_path / "uhr.probe"
    probe.write_bytes(b"")
    return datetime.fromtimestamp(probe.stat().st_mtime, timezone.utc)


def test_uhr_folgt_dem_schalter(tmp_path):
    """GIVEN den Uhr-Schalter, gesetzt oder nicht
    WHEN dieser Lauf die Prozessuhr gegen die Kernel-Uhr haelt
    THEN folgt sie ohne Schalter der Kernel-Uhr und mit Schalter dem Anker.

    Beide Richtungen in einem Fall: ein Test, der nur den gesetzten Zustand
    prueft, faellt in der Gegenrichtung nicht auf -- eine Fixture, die die
    Uhr IMMER stellt, waere ebenso kaputt wie eine, die es nie tut, und
    verdeckte jede echte Wanduhr-Abhaengigkeit im Bestand.
    """
    jetzt = datetime.now(timezone.utc)
    echt = _kernel_uhr(tmp_path)
    roh = roh_wert()

    if not roh:
        assert abs((jetzt - echt).total_seconds()) <= _TOLERANZ_S, (
            f"Ohne gesetztes {ENV_NAME} darf die Uhr NICHT gestellt sein: "
            f"Prozessuhr {jetzt.isoformat()} weicht von der Kernel-Uhr "
            f"{echt.isoformat()} ab"
        )
        return

    anker = anker_aus(roh)
    assert abs((jetzt - anker).total_seconds()) <= _TOLERANZ_S, (
        f"{ENV_NAME}={roh!r} ist gesetzt, aber die Prozessuhr "
        f"{jetzt.isoformat()} steht nicht auf dem Anker {anker.isoformat()} "
        f"(Kernel-Uhr: {echt.isoformat()}) -- der Schalter wirkt nicht"
    )


def test_schalter_bewegt_die_uhr_im_untergeordneten_lauf():
    """GIVEN einen ECHTEN zweiten pytest-Lauf ueber
    ``test_uhr_folgt_dem_schalter``, dessen Schalter auf einen festen
    Zeitpunkt in der Vergangenheit gestellt ist
    WHEN dieser Lauf faehrt
    THEN endet er mit Exit 0 -- die Fixture hat die Uhr also tatsaechlich
    dorthin bewegt.

    Warum ein eigener Prozess: der Schalter wird EINMAL je Session gelesen;
    innerhalb dieses Laufes laesst er sich nicht mehr umlegen. Ein
    untergeordneter Lauf ist die einzige Moeglichkeit, den gesetzten Zustand
    zu pruefen, ohne davon abzuhaengen, wie dieser Lauf gestartet wurde.

    Der Anker liegt in der Vergangenheit: eine NICHT gestellte Uhr steht
    davon Tage entfernt, der Fall kann also nicht zufaellig bestehen. Legt
    man die Fixture still, faellt der untergeordnete Lauf durch und dieser
    Test wird rot.
    """
    repo = Path(__file__).resolve().parents[2]
    ziel = f"tests/tdd/{Path(__file__).name}::{_EIGENER_FALL}"

    umgebung = dict(os.environ)
    umgebung[ENV_NAME] = _ANKER_VERGANGENHEIT

    lauf = subprocess.run(
        [
            sys.executable, "-m", "pytest", ziel,
            "-p", "no:randomly", "-p", "no:cacheprovider",
            "--disable-socket", "--allow-unix-socket",
            "--allow-hosts=127.0.0.1,::1,localhost",
            # KEIN eigenes `-q`: `addopts` (pyproject.toml) bringt schon eins
            # mit, ein zweites unterdrueckt die Zusammenfassungszeile, die
            # unten als Vorbedingung geprueft wird.
            "--tb=short",
        ],
        cwd=repo, env=umgebung, capture_output=True, text=True, timeout=300,
    )

    assert lauf.returncode == 0, (
        f"Der untergeordnete Lauf mit {ENV_NAME}={_ANKER_VERGANGENHEIT} ist "
        f"fehlgeschlagen -- die Fixture stellt die Uhr nicht.\n"
        f"stdout:\n{lauf.stdout[-3000:]}\nstderr:\n{lauf.stderr[-1500:]}"
    )
    assert "1 passed" in lauf.stdout, (
        "Vorbedingung: der untergeordnete Lauf muss GENAU DIESEN einen Fall "
        f"ausgefuehrt haben -- sonst belegt sein Exit 0 nichts.\n{lauf.stdout[-3000:]}"
    )
