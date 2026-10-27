"""Kern-Schicht: ``tools/weather_validation.py`` verlangt ``--user-id`` als
Pflicht-CLI-Argument statt fuenf Aufrufstellen klaglos auf ``users/default/``
zurueckfallen zu lassen (#2151 Scheibe C) -- der einzige Produktivpfad, der
den Default heute WIRKLICH nutzt (liest ``users/default/*`` unabhaengig vom
aufrufenden Nutzer).

Spec: docs/specs/modules/fix_2151_default_fallbacks_scheibe_c.md (Test 12,
AC-8)

Heute (RED):
  * ``--user-id`` existiert als Argument noch nicht -- ein Aufruf OHNE dieses
    Argument laeuft klaglos durch (kein ``argparse``-Fehler, kein
    ``SystemExit``), statt BEVOR irgendein Trip gelesen wird abzubrechen.
  * Ein Aufruf MIT ``--user-id nutzer_a`` scheitert heute selbst mit
    ``SystemExit(2)`` ("unrecognized arguments"), weil das Argument fehlt --
    also GENAU DAS GEGENTEIL des Zielbilds (soll erfolgreich NUR die Trips
    von ``nutzer_a`` lesen).

Nachweisform: Aufruf von ``main()`` direkt (kein Subprocess -- der Egress-
Waechter aus ``tests/conftest.py`` greift nur INNERHALB des Pytest-Prozesses)
mit umgebogenem ``sys.argv``; ein echter Zaehl-Wrapper um
``app.loader.load_all_trips`` (ruft die Originalfunktion unveraendert auf)
belegt, mit welcher ``user_id`` tatsaechlich gelesen wurde. Isolierte
Datenwurzel (autouse ``tests/conftest.py::_isolate_data_root``) verhindert
jeden Zugriff auf den echten Baum. Beide Tests sind so gebaut, dass fuer das
angefragte Konto KEIN Trip existiert -- ``validate_trip`` bricht dann mit
"nicht gefunden" ab, bevor ``fetch_gregor_pipeline``/Referenzquellen (Netz)
beruehrt werden. Ein gefundener Trip liefe in den Netzpfad.
"""
from __future__ import annotations

import sys
from datetime import date, time
from pathlib import Path

import pytest

from app import loader
from app.loader import save_trip
from app.trip import Stage, TimeWindow, Trip, Waypoint

_TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(_TOOLS_DIR))

import weather_validation  # noqa: E402  -- Prüfling relativ zur eigenen Testdatei aufgeloest

LAT, LON = 47.2692, 11.4041


def _minimaler_trip(trip_id: str, name: str) -> Trip:
    wps = [
        Waypoint(
            id="G1", name="Start", lat=LAT, lon=LON, elevation_m=600,
            time_window=TimeWindow(start=time(0, 0), end=time(0, 0)),
        ),
    ]
    stage = Stage(id="T1", name="Etappe", date=date.today(), start_time=time(8, 0), waypoints=wps)
    return Trip(id=trip_id, name=name, stages=[stage])


def _load_all_trips_zaehler(monkeypatch) -> list[tuple[tuple, dict]]:
    """Echter Zaehl-Wrapper um ``app.loader.load_all_trips`` -- ruft die
    Originalfunktion unveraendert auf. Kein ``Mock()``/``patch()``. Der
    lokale Import ``from app.loader import load_all_trips`` in
    ``validate_trip()`` laeuft PRO AUFRUF frisch, greift also auf das hier
    gepatchte Modulattribut zu."""
    aufrufe: list[tuple[tuple, dict]] = []
    original = loader.load_all_trips

    def _gezaehlt(*args, **kwargs):
        aufrufe.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(loader, "load_all_trips", _gezaehlt)
    return aufrufe


# ═══════════════════════════ AC-8 (Test 12, Teil 1) ══════════════════════════


def test_ac8_ohne_user_id_bricht_die_parametervalidierung_ab_bevor_ein_trip_gelesen_wird(
    monkeypatch,
):
    """AC-8 / Test 12: fehlt ``--user-id``, muss ``argparse`` mit
    ``SystemExit`` (Exit-Code != 0) abbrechen, BEVOR ``load_all_trips``
    ueberhaupt aufgerufen wird.

    RED heute: ``--user-id`` existiert nicht -- der Aufruf laeuft klaglos
    durch (kein SystemExit), ``main()`` kehrt normal zurueck.
    """
    aufrufe = _load_all_trips_zaehler(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["weather_validation.py", "--trip", "existiert-nicht"])

    with pytest.raises(SystemExit) as exc_info:
        weather_validation.main()

    assert exc_info.value.code != 0, (
        f"AC-8: ohne --user-id muss argparse mit Exit-Code != 0 abbrechen; "
        f"erhalten {exc_info.value.code}"
    )
    assert aufrufe == [], (
        "AC-8: load_all_trips wurde aufgerufen, obwohl die Parametervalidierung "
        f"(fehlendes --user-id) das haette verhindern muessen: {aufrufe}"
    )


# ═══════════════════════════ AC-8 (Test 12, Teil 2) ══════════════════════════


def test_ac8_mit_user_id_liest_das_skript_ausschliesslich_die_trips_dieses_kontos(
    monkeypatch, capsys,
):
    """AC-8 / Test 12: mit ``--user-id nutzer_a`` liest das Skript
    ausschliesslich die Trips von ``nutzer_a`` -- ``load_all_trips`` wird bei
    JEDEM Aufruf mit genau dieser Kennung aufgerufen, kein ``SystemExit``,
    und kein Trip eines anderen Kontos kommt zurueck.

    Aufbau: ``t-scope`` existiert NUR bei ``nutzer_b``; ``nutzer_a`` ist leer.
    Richtig gescopt findet das Skript den Trip nicht und bricht mit "nicht
    gefunden" ab, BEVOR ``fetch_gregor_pipeline``/Referenzquellen (Netz)
    beruehrt werden. Liest es faelschlich ein anderes Konto (``nutzer_b``
    oder den alten Rueckfall ``default``), faellt das an der Kennung des
    Aufrufs bzw. am zurueckgelieferten Trip auf.

    RED vor Scheibe C: ``--user-id`` ist kein bekanntes Argument --
    ``argparse`` bricht mit ``SystemExit(2)`` ("unrecognized arguments") ab.
    """
    save_trip(_minimaler_trip("t-scope", "Trip-B"), user_id="nutzer_b")

    aufrufe: list[tuple[tuple, dict, list]] = []
    original = loader.load_all_trips

    def _gezaehlt(*args, **kwargs):
        ergebnis = original(*args, **kwargs)
        aufrufe.append((args, kwargs, [t.id for t in ergebnis]))
        return ergebnis

    monkeypatch.setattr(loader, "load_all_trips", _gezaehlt)
    monkeypatch.setattr(
        sys, "argv",
        ["weather_validation.py", "--trip", "t-scope", "--user-id", "nutzer_a"],
    )

    try:
        weather_validation.main()
    except SystemExit as e:
        pytest.fail(
            f"AC-8: --user-id nutzer_a fuehrte zu SystemExit({e.code}) statt "
            "zum gescopten Trip-Read -- --user-id muss als Pflicht-Argument "
            f"existieren und durchgereicht werden: {e}"
        )

    assert aufrufe, "AC-8: load_all_trips wurde nie aufgerufen"
    for args, kwargs, _ids in aufrufe:
        user_id_uebergeben = kwargs.get("user_id") or (args[0] if args else None)
        assert user_id_uebergeben == "nutzer_a", (
            f"AC-8: load_all_trips wurde nicht mit user_id='nutzer_a' aufgerufen: "
            f"args={args} kwargs={kwargs}"
        )
    gelesen = [tid for _a, _k, ids in aufrufe for tid in ids]
    assert gelesen == [], (
        f"AC-8: das Skript hat Trips eines fremden Kontos gelesen: {gelesen}"
    )
    assert "nicht gefunden" in capsys.readouterr().out, (
        "AC-8: ohne Trip bei nutzer_a muss das Skript mit 'nicht gefunden' "
        "abbrechen -- es hat den Trip offenbar aus einem anderen Konto geladen"
    )
