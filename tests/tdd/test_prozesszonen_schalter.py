"""#2314 (Durchgang 2), AC-1/AC-2/AC-3: der Env-Knopf ``GZ_TEST_PROCESS_TZ``
fuer die Prozesszone existiert in Root-`conftest.py` noch NICHT (das ist
/50) -- dieser Datei geht es einzig darum, das MESSBAR zu machen und rot zu
zeigen, solange der Knopf fehlt.

Warum ein frischer Subprozess je Messung
-----------------------------------------
Root-`conftest.py` setzt ``os.environ["TZ"]`` auf MODUL-EBENE, also beim
IMPORT -- das ist bereits geschehen, bevor der erste Test in DIESEM Prozess
laeuft. Eine Umgebungsvariable innerhalb des laufenden Testprozesses zu
setzen haette also keinerlei Wirkung mehr auf ``time.tzname``/``date.today()``
dieses Prozesses. Jede Messung startet deshalb einen FRISCHEN
``pytest``-Subprozess (Vorbild ``tests/helpers/wanduhr_matrix.py``:
``sys.executable``-Subprozess, PYTEST_*-Variablen nicht durchgereicht), mit
``GZ_TEST_PROCESS_TZ`` gesetzt/ungesetzt VOR dem Start -- nur so kann die
Variable ueberhaupt zum Tragen kommen, sobald sie implementiert ist.

Warum die Sondendatei DIREKT unter REPO_ROOT liegt (nicht in ``tmp_path``)
---------------------------------------------------------------------------
Damit Root-`conftest.py` fuer die Sonde wirklich als Ahnenverzeichnis greift
(pytests conftest-Kette laeuft ueber die Verzeichnis-Vorfahren der
Testdatei, nicht ueber ``cwd``), liegt jede Sondendatei in einem frischen,
punkt-praefigierten Temp-Verzeichnis DIREKT unter ``REPO_ROOT`` --
``tempfile.mkdtemp(dir=REPO_ROOT)`` statt ``tmp_path`` (das ausserhalb des
Repos liegt und die Kette nicht laedt). Das Verzeichnis liegt bewusst
AUSSERHALB von ``tests/``, damit die Wanduhr-Ratsche (#1667, scannt
``tests/**/*.py``) sich nicht selbst meldet, und wird nach jeder Messung
wieder entfernt.

Was heute (RED) passiert und warum
-----------------------------------
``GZ_TEST_PROCESS_TZ`` wird von Root-`conftest.py` schlicht IGNORIERT -- die
Prozesszone bleibt in JEDEM Subprozess ``America/St_Johns``, egal welcher
Wert gesetzt ist. Daraus folgt:

* AC-1 (ohne Variable): Prozesszone ist ``America/St_Johns`` -- das gilt
  HEUTE SCHON, weil es der Status quo ist. Dieser Test ist deshalb bewusst
  ein GRUENER Regressionswaechter, kein RED-Nachweis (Marker im Testnamen).
* AC-2 (mit gesetzter Gestern-Zone): erwartet ``prozess_heute == utc_heute -
  1 Tag``. Weil die Prozesszone tatsaechlich St_Johns bleibt (nicht die
  gesetzte Gestern-Zone), stimmt diese Gleichung zur Messzeit i. A. NICHT --
  ROT.
* AC-3 (Selbstschutz bei nicht-tragender Zone): der in der Spec geforderte
  Selbstschutz-Mechanismus existiert nirgends -- weder in Root-`conftest.py`
  noch anderswo. Die Sonde laeuft deshalb anstandslos durch (Exit 0), obwohl
  sie eine garantiert nicht tragende Zone gesetzt bekommt. Der aeussere Test
  erwartet einen sichtbaren Fehlschlag mit Zone+Zeit in der Meldung --
  findet keinen -- ROT.

Spec: ``docs/specs/modules/fix_2314_nachtfenster_utc_tag.md``.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests.helpers.gestern_zone import GESTERN_ZONE, echte_utc_jetzt, gestern_zone_fuer

# Wurzel DIESES Checkouts (Worktree, #1409) -- Subprozesse laufen mit dieser
# cwd, damit Root-`conftest.py` fuer sie greift.
REPO_ROOT = Path(__file__).resolve().parents[2]

_SUBPROC_TIMEOUT_SEC = 60


# Echte Uhr (``date -u`` im Subprozess, #2096) und Zonenwahl stehen seit #2744
# an EINER Stelle: ``tests/helpers/gestern_zone.py``.


def _lauf_sonde(env_overrides: dict[str, str]) -> dict:
    """Fuehrt eine winzige Sonde in einem FRISCHEN ``pytest``-Subprozess aus,
    dessen Sondendatei DIREKT unter ``REPO_ROOT`` liegt (s. Modul-Docstring).
    Gibt ``{"tz_env", "prozess_heute", "utc_heute", "exit_code", "stdout",
    "stderr"}`` zurueck -- die Sonde schreibt ihr Ergebnis als JSON in eine
    Datei (kein stdout-Parsing fuer die MESSWERTE), stdout/stderr werden
    zusaetzlich fuer AC-3 (Fehlertext-Pruefung) mitgegeben."""
    sonde_dir = Path(tempfile.mkdtemp(dir=REPO_ROOT, prefix=".gz_tz_probe_"))
    try:
        ausgabe = sonde_dir / "ergebnis.json"
        sonde_datei = sonde_dir / "test_sonde.py"
        sonde_datei.write_text(
            "import json, os\n"
            "from datetime import datetime, timezone, date\n"
            "\n"
            "def test_sonde():\n"
            "    ergebnis = {\n"
            "        'tz_env': os.environ.get('TZ'),\n"
            "        'prozess_heute': date.today().isoformat(),\n"
            "        'utc_heute': datetime.now(timezone.utc).date().isoformat(),\n"
            "    }\n"
            f"    with open({str(ausgabe)!r}, 'w', encoding='utf-8') as f:\n"
            "        json.dump(ergebnis, f)\n",
            encoding="utf-8",
        )
        # Adversary-Fund F001: Sondendatei kann selbst unter GZ_TEST_PROCESS_TZ
        # / GZ_TEST_WALL_CLOCK_UTC laufen (z.B. beim Vollsuite-Nachweis unter
        # Gestern-Zone) -- ohne Entfernen wuerde die AEUSSERE Variable in die
        # Sonde durchsickern, obwohl der jeweilige Test sie explizit NICHT
        # gesetzt haben will (AC-1-Regressionswaechter).
        env = {
            k: v for k, v in os.environ.items()
            if not k.startswith("PYTEST_")
            and k not in ("GZ_TEST_PROCESS_TZ", "GZ_TEST_WALL_CLOCK_UTC")
        }
        env.update(env_overrides)
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(sonde_datei), "-q", "--no-header"],
            cwd=str(REPO_ROOT), capture_output=True, text=True,
            timeout=_SUBPROC_TIMEOUT_SEC, env=env,
        )
        ergebnis: dict = {}
        if ausgabe.exists():
            ergebnis = json.loads(ausgabe.read_text(encoding="utf-8"))
        ergebnis["exit_code"] = proc.returncode
        ergebnis["stdout"] = proc.stdout
        ergebnis["stderr"] = proc.stderr
        return ergebnis
    finally:
        shutil.rmtree(sonde_dir, ignore_errors=True)


# ══════════════════ AC-1: Default bleibt St_Johns (heute GRUEN) ══════════════════

def test_ac1_ohne_variable_bleibt_die_prozesszone_st_johns_regressionswaechter():
    """AC-1: ohne ``GZ_TEST_PROCESS_TZ`` ist die Prozesszone byte-identisch
    zum Verhalten vor dieser Lieferung -- ``America/St_Johns``. Das gilt
    bereits HEUTE (Status quo), dieser Test ist deshalb bewusst ein GRUENER
    Regressionswaechter: er soll nach der Implementierung des Knopfs (/50)
    GRUEN BLEIBEN, nicht erst gruen werden."""
    ergebnis = _lauf_sonde({})
    assert ergebnis["exit_code"] == 0, (
        f"Sonde ohne gesetzte Variable ist unerwartet fehlgeschlagen:\n"
        f"{ergebnis.get('stdout')}\n{ergebnis.get('stderr')}"
    )
    assert ergebnis["tz_env"] == "America/St_Johns", (
        f"Default-Prozesszone muss America/St_Johns bleiben, gemessen: "
        f"{ergebnis['tz_env']!r}"
    )


# ══════════════════ AC-2: Gestern-Zone -> Prozesstag = UTC-Tag-1 (heute ROT) ══════════════════

def test_ac2_gestern_zone_liefert_prozesstag_gleich_utc_tag_minus_eins():
    """AC-2: unter einer gesetzten Gestern-Zone muss ``date.today()`` im
    Subprozess den UTC-Tag minus 1 liefern. ROT heute, weil Root-
    `conftest.py` ``GZ_TEST_PROCESS_TZ`` noch nicht kennt -- die Prozesszone
    bleibt St_Johns, ``prozess_heute`` weicht i. A. nicht um genau 1 Tag vom
    UTC-Tag ab.

    Startzeit per ``echte_utc_jetzt()``, NICHT ``datetime.now(timezone.utc)``:
    unter einer session-weit gestellten Wanduhr (``GZ_TEST_WALL_CLOCK_UTC``,
    #2096) waere dieser Prozess selbst eingefroren, waehrend der Sonden-
    Subprozess unten real laeuft. Die Zone (``gestern_zone_fuer``) traegt
    den ganzen UTC-Tag (#2744)."""
    start_utc = echte_utc_jetzt()
    zone = gestern_zone_fuer(start_utc)
    ergebnis = _lauf_sonde({"GZ_TEST_PROCESS_TZ": zone})
    assert ergebnis["exit_code"] == 0, (
        f"Sonde mit gesetzter Gestern-Zone {zone!r} ist unerwartet "
        f"fehlgeschlagen:\n{ergebnis.get('stdout')}\n{ergebnis.get('stderr')}"
    )
    prozess_heute = datetime.fromisoformat(ergebnis["prozess_heute"]).date()
    utc_heute = datetime.fromisoformat(ergebnis["utc_heute"]).date()
    erwartet = utc_heute - timedelta(days=1)
    assert prozess_heute == erwartet, (
        f"AC-2: unter Gestern-Zone {zone!r} (Startzeit {start_utc.isoformat()} "
        f"UTC) muss date.today() im Subprozess {erwartet.isoformat()} "
        f"(UTC-Tag-1) liefern, gemessen wurde {prozess_heute.isoformat()} "
        f"(tz_env={ergebnis['tz_env']!r}) -- der Knopf GZ_TEST_PROCESS_TZ "
        f"existiert in Root-conftest.py noch nicht (/50)."
    )


# ══════════════════ AC-3: Selbstschutz bei nicht tragender Zone (heute ROT) ══════════════════

def test_ac3_selbstschutz_bei_nicht_tragender_zone_scheitert_sichtbar():
    """AC-3: ``GZ_TEST_PROCESS_TZ=UTC`` traegt NIE (Offset 0, Prozesstag ==
    UTC-Tag immer) -- der in der Spec geforderte Selbstschutz muss den Lauf
    sichtbar mit Zone+Zeit in der Meldung scheitern lassen, statt still
    gruen durchzulaufen. ROT heute, weil dieser Selbstschutz nirgends
    implementiert ist: die Sonde laeuft anstandslos durch (Exit 0), obwohl
    sie eine garantiert wirkungslose Zone gesetzt bekommt."""
    # Echte Zeit (``date -u``): die Sonde laeuft nie eingefroren, ihre Meldung
    # nennt die ECHTE UTC-Zeit, auch unter gestellter Wanduhr (#2744, AC-6).
    start_utc = echte_utc_jetzt()
    ergebnis = _lauf_sonde({"GZ_TEST_PROCESS_TZ": "UTC"})
    meldungstext = (ergebnis.get("stdout") or "") + (ergebnis.get("stderr") or "")
    assert ergebnis["exit_code"] != 0, (
        f"AC-3: GZ_TEST_PROCESS_TZ=UTC (Startzeit {start_utc.isoformat()} "
        f"UTC) traegt garantiert nicht (Prozesstag == UTC-Tag zu jeder "
        f"Uhrzeit) und muss den Lauf sichtbar scheitern lassen -- der "
        f"Selbstschutz existiert noch nicht, die Sonde lief mit Exit 0 "
        f"durch:\n{meldungstext}"
    )
    assert "UTC" in meldungstext and (
        start_utc.strftime("%Y-%m-%d") in meldungstext
        or start_utc.strftime("%H:") in meldungstext
    ), (
        "AC-3: die Fehlermeldung des Selbstschutzes muss Zone und UTC-Zeit "
        f"nennen -- gemessene Ausgabe:\n{meldungstext}"
    )


def test_gestern_zone_ist_dieselbe_wie_die_gemeinsame_hilfe():
    """Selbstbeleg (kein AC-Nachweis): dieser Test nutzt die gemeinsame
    Zonenwahl (#2744) und keine eigene Stundengrenze -- vor und nach den
    frueheren Grenzen (09:30, 23:30 UTC) dieselbe Zone. Dass sie traegt,
    belegt ``tests/tdd/test_gestern_zone_hilfe.py``."""
    zonen = {
        gestern_zone_fuer(datetime(2026, 9, 15, h, m, tzinfo=timezone.utc))
        for h, m in ((0, 0), (9, 0), (9, 45), (12, 0), (23, 45))
    }
    assert zonen == {GESTERN_ZONE}
