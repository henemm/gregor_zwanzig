"""Waechter fuer #1755 (AC-5):Breitlauf-Gate gibt nur die sichere
Offline-Form frei.

SPEC: docs/specs/modules/fix_1755_offline_volllauf.md (AC-5)

Bisher galt ``--disable-socket`` allein als Freigabe fuer einen Volllauf.
Die einzige praktisch benutzbare Erweiterung (``--allow-hosts=127.0.0.1``)
liesse jeden Test Prod/Staging auf Loopback erreichen. Freigegeben wird
kuenftig nur (seit Fix-Loop 6 exakter Vergleich, einzeilig, woertlich,
optional mit `` --ignore=tests/red/`` und/oder `` > <pfad> 2>&1``):

    uv run pytest --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports

Kein Mock-Theater: der echte Hook laeuft als Subprozess mit JSON-Payload auf
stdin (Muster wie test_broad_test_run_gate_pytest_word_position.py). Geprueft
werden Exit-Code und Meldungstext.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
HOOK = ROOT / ".claude" / "hooks" / "broad_test_run_gate.py"

sys.path.insert(0, str(ROOT / ".claude" / "hooks"))
pytest.importorskip("broad_test_run_gate", exc_type=ImportError)

NEW_FORM = (
    "--disable-socket --allow-unix-socket "
    "--allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports"
)
DOCUMENTED_CALL = f"uv run pytest {NEW_FORM} --ignore=tests/red/"


_NO_OVERRIDE_ROOT = Path(tempfile.mkdtemp(prefix="gate1755-"))


def _run_gate(command: str) -> subprocess.CompletedProcess:
    """Echter Hook als Subprozess. ``CLAUDE_PROJECT_DIR`` zeigt auf ein leeres
    Temp-Verzeichnis ohne Override-Token-Datei -- ein Override des PO kann die
    Blockfaelle so nicht verfaelschen (``hook_utils.find_project_root`` liest
    diese Variable zuerst)."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(_NO_OVERRIDE_ROOT)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload, capture_output=True, text=True, cwd=str(ROOT), env=env, timeout=30,
    )


# ---------------------------------------------------------------------------
# Freigegeben
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        DOCUMENTED_CALL,
        f"uv run pytest {NEW_FORM}",
    ],
    ids=["doku-aufruf", "neue-form"],
)
def test_ac5_neue_offline_form_ist_freigegeben(command):
    proc = _run_gate(command)
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest tests/tdd/test_x.py",
        "uv run pytest --collect-only",
        "uv run pytest tests/tdd/test_x.py --disable-socket",
    ],
    ids=["datei-benannt", "collect-only", "datei-plus-disable-socket"],
)
def test_ac5_bisherige_freigaben_bleiben(command):
    proc = _run_gate(command)
    assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------------------
# Blockiert
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest --disable-socket",
        "uv run pytest --disable-socket --ignore=tests/red/",
        "uv run pytest --disable-socket --allow-unix-socket",
        "uv run pytest --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost",
        "uv run pytest --disable-socket --allow-hosts=0.0.0.0/0 --loopback-own-ports",
        "uv run pytest --disable-socket --allow-hosts=8.8.8.8 --loopback-own-ports",
        "uv run pytest --disable-socket --allow-hosts=127.0.0.1,8.8.8.8 --loopback-own-ports",
        "uv run pytest --disable-socket --allow-hosts=127.0.0.0/8 --loopback-own-ports",
        "uv run pytest --loopback-own-ports --allow-hosts=127.0.0.1",
        f"uv run pytest {NEW_FORM} --force-enable-socket",
        f"uv run pytest {NEW_FORM} -p no:socket",
        f"uv run pytest {NEW_FORM} -p no:_loopback_port_guard",
        f"uv run pytest {NEW_FORM} -o addopts=",
        f"uv run pytest {NEW_FORM} -c /tmp/leer.ini",
        f"uv run pytest {NEW_FORM} --override-ini=addopts=",
        "sh -c \"uv run pytest --disable-socket\"",
        "sh -c \"uv run pytest --disable-socket --allow-hosts=8.8.8.8 --loopback-own-ports\"",
        f"sh -c \"uv run pytest {NEW_FORM} -p no:socket\"",
        "uv run pytest --disable-socket --allow-hosts 8.8.8.8 --loopback-own-ports",
        "uv run pytest --disable-socket --allow-hosts=127.0.0.1 --allow-hosts=8.8.8.8 --loopback-own-ports",
        f"uv run pytest {NEW_FORM} -pno:socket",
        f"PYTEST_ADDOPTS=--force-enable-socket uv run pytest {NEW_FORM}",
        f"env PYTEST_ADDOPTS=--force-enable-socket uv run pytest {NEW_FORM}",
        f"export PYTEST_ADDOPTS=-pno:socket && uv run pytest {NEW_FORM}",
        # Fix-Loop 1 (F001): Shell-Metazeichen ohne Leerraum im Wert bzw.
        # Positionsargument -- shlex liefert EIN Token, die Shell startet
        # danach nacktes pytest.
        "python3 -m pytest --disable-socket --allow-hosts=127.0.0.1 --loopback-own-ports --ignore=x;pytest",
        f"uv run pytest {NEW_FORM} tests/;pytest",
        f"uv run pytest {NEW_FORM} --tb=short&&pytest",
        f"uv run pytest {NEW_FORM} --maxfail=1|pytest",
        f"uv run pytest {NEW_FORM} --ignore=$(pytest)",
        f"uv run pytest {NEW_FORM} --ignore=`pytest`",
        "sh -c \"python3 -m pytest --disable-socket --allow-hosts=127.0.0.1 --loopback-own-ports --ignore=x;pytest\"",
        f"sh -c \"uv run pytest {NEW_FORM} tests/;pytest\"",
        # F004: Substitution im Umleitungsziel -- die Argumente vor '>' sind
        # sauber, nur die Pruefung des Gesamtkommandos faengt das.
        f"uv run pytest {NEW_FORM} > $(pytest -q)",
        f"uv run pytest {NEW_FORM} > `pytest -q`",
        f"sh -c \"uv run pytest {NEW_FORM} > $(pytest -q)\"",
    ],
    ids=[
        "disable-socket-allein",
        "disable-socket-ignore-red",
        "disable-plus-unix",
        "ci-form-ohne-port-waechter",
        "cidr-alles",
        "fremder-host",
        "gemischt-fremder-host",
        "loopback-cidr",
        "ohne-disable-socket",
        "force-enable-socket",
        "p-no-socket",
        "p-no-guard",
        "o-addopts",
        "c-ini",
        "override-ini",
        "roh-disable-socket-allein",
        "roh-fremder-host",
        "roh-p-no-socket",
        "allow-hosts-leerzeichen-fremd",
        "allow-hosts-doppelt-letzter-fremd",
        "pno-zusammengeschrieben",
        "pytest-addopts-praefix",
        "env-pytest-addopts",
        "export-pytest-addopts",
        "semikolon-im-ignore-wert",
        "semikolon-im-positionsargument",
        "und-und-im-tb-wert",
        "pipe-im-maxfail-wert",
        "kommandosubstitution-im-wert",
        "backtick-im-wert",
        "roh-semikolon-im-ignore-wert",
        "roh-semikolon-im-positionsargument",
        "umleitungsziel-kommandosubstitution",
        "umleitungsziel-backtick",
        "roh-umleitungsziel-kommandosubstitution",
    ],
)
def test_ac5_unsichere_form_ist_blockiert(command):
    proc = _run_gate(command)
    assert proc.returncode == 2, (
        f"Erwartet Block (Exit 2), bekam {proc.returncode} fuer: {command}\n{proc.stderr}"
    )


# ---------------------------------------------------------------------------
# Fix-Loop 2: Segment-Klebung, Optionswerte als "Datei", Roh-Frueh-Ausgaenge
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        # ';' klebt am Token -- die Folgeanweisung lieferte das --co
        "uv run pytest --disable-socket --allow-hosts=127.0.0.1; uv run pytest --co",
        "uv run pytest --disable-socket; uv run pytest --co",
        # Optionswert --ignore=x.py galt im Roh-Pfad als benannte Datei
        "sh -c \"uv run pytest --disable-socket --allow-hosts=127.0.0.1,::1,localhost "
        "--ignore=x.py --tb=short\"",
        # Roh-Pfad gab bei --collect-only irgendwo im Kommando frei
        "sh -c \"uv run pytest --disable-socket; pytest --collect-only\"",
        # Zeilenumbruch trennt Anweisungen wie ';'
        "uv run pytest --disable-socket\nuv run pytest --co",
        "sh -c \"uv run pytest --disable-socket\nuv run pytest --co\"",
        # '#' mitten im Wort ist fuer die Shell kein Kommentar
        "uv run pytest --co#; uv run pytest tests/",
        "uv run pytest tests/x.py#; pytest tests/",
        # Optionswert in Leerzeichen-Form ist keine benannte Datei
        "uv run pytest --ignore x.py",
        "sh -c \"uv run pytest tests/; pytest --co\"",
    ],
    ids=[
        "semikolon-klebt-allow-hosts-dann-co",
        "semikolon-klebt-disable-socket-dann-co",
        "roh-ignore-py-als-datei",
        "roh-collect-only-in-folgeanweisung",
        "zeilenumbruch-dann-co",
        "roh-zeilenumbruch-dann-co",
        "raute-im-wort-co",
        "raute-im-wort-datei",
        "ignore-leerzeichen-py",
        "roh-breit-dann-co",
    ],
)
def test_fixloop2_umgehungen_sind_blockiert(command):
    proc = _run_gate(command)
    assert proc.returncode == 2, (
        f"Erwartet Block (Exit 2), bekam {proc.returncode} fuer: {command!r}\n{proc.stderr}"
    )
    assert "--loopback-own-ports" in proc.stderr, proc.stderr


@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest --co",
        f"{DOCUMENTED_CALL} > /tmp/out.txt 2>&1",
        "uv run pytest tests/tdd/x.py",
        "uv run pytest tests/tdd/x.py; echo ok",
        "sh -c \"uv run pytest tests/tdd/x.py --disable-socket\"",
    ],
    ids=["co", "sichere-form-umleitung", "datei",
         "datei-plus-echo", "roh-datei-plus-disable-socket"],
)
def test_fixloop2_freigaben_bleiben(command):
    proc = _run_gate(command)
    assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------------------
# Fix-Loop 3 (F-A1): PYTEST_*-Umgebungsvariablen, per Quotes zerlegt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        f"PYTEST_ADD\"\"OPTS=--force-enable-socket uv run pytest {NEW_FORM}",
        f"env \"PYTEST_\"\"ADDOPTS=--allow-hosts=0.0.0.0/0\" uv run pytest {NEW_FORM}",
        f"env PYTEST_PLUGINS=x uv run pytest {NEW_FORM}",
        f"export PYTEST_ADDOPTS=-p\\ no:socket; uv run pytest {NEW_FORM}",
        f"sh -c 'PYTEST_ADD\"\"OPTS=-pno:socket uv run pytest {NEW_FORM}'",
        f"PYTEST_ADD\\OPTS=-pno:socket uv run pytest {NEW_FORM}",
    ],
    ids=["zuweisung-quote-zerlegt", "env-quote-zerlegt", "env-pytest-plugins",
         "export-addopts-escape", "roh-zuweisung-quote-zerlegt",
         "zuweisung-backslash-zerlegt"],
)
def test_fixloop3_pytest_umgebung_ist_blockiert(command):
    proc = _run_gate(command)
    assert proc.returncode == 2, (
        f"Erwartet Block (Exit 2), bekam {proc.returncode} fuer: {command!r}\n{proc.stderr}"
    )
    assert "--loopback-own-ports" in proc.stderr, proc.stderr


def test_fixloop3_sichere_form_ohne_umgebung_bleibt_frei():
    proc = _run_gate(DOCUMENTED_CALL)
    assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------------------
# Fix-Loop 4: Zeichen-Positivliste der Offline-Argumente (F001) und
# Argumentdatei ``@datei`` (F002)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        # F001: Shell-Expansion im Argument -- erst die Shell bestimmt, was
        # pytest wirklich sieht
        f"{DOCUMENTED_CALL} --ignore=$HOME",
        f"{DOCUMENTED_CALL} $X",
        f"{DOCUMENTED_CALL} tests/*",
        f"{DOCUMENTED_CALL} ~/x",
        f"{DOCUMENTED_CALL} {{a,b}}",
        f"X=-pno:socket; {DOCUMENTED_CALL} $X",
        # F002: pytest liest aus @datei weitere Argumente
        f"uv run pytest {NEW_FORM} @/tmp/a.txt",
        f"{DOCUMENTED_CALL} @args.txt",
    ],
    ids=["ignore-dollar-home", "dollar-variable", "glob-stern", "tilde",
         "klammer-expansion", "variable-mit-socket-flag", "argumentdatei-absolut",
         "argumentdatei-relativ"],
)
def test_fixloop4_expansion_und_argumentdatei_sind_blockiert(command):
    proc = _run_gate(command)
    assert proc.returncode == 2, (
        f"Erwartet Block (Exit 2), bekam {proc.returncode} fuer: {command!r}\n{proc.stderr}"
    )
    assert "--loopback-own-ports" in proc.stderr, proc.stderr


# ---------------------------------------------------------------------------
# Fix-Loop 5: Umleitung ist kein Argumentende (F001), Waechterfaelle F002-F004
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        # F001: die Shell reicht Woerter HINTER einer Umleitung an pytest weiter
        f"uv run pytest {NEW_FORM} 2>&1 --force-enable-socket",
        f"uv run pytest {NEW_FORM} > o.txt -p no:socket",
        f"uv run pytest {NEW_FORM} > o.txt -o addopts=",
        f"uv run pytest {NEW_FORM} 2>/dev/null -c other.ini",
        f"uv run pytest {NEW_FORM} < /dev/null --override-ini addopts=",
        f"uv run pytest {NEW_FORM} &> o.txt -p no:socket",
        f"sh -c \"uv run pytest {NEW_FORM} > o.txt -p no:socket\"",
        # F002: 0.0.0.0 ist kein Loopback
        "uv run pytest --disable-socket --allow-unix-socket --allow-hosts=0.0.0.0 --loopback-own-ports",
        "uv run pytest --disable-socket --allow-unix-socket --allow-hosts=0.0.0.0,127.0.0.1 "
        "--loopback-own-ports",
        # F003: pytest-Aufruf ohne erkennbares pytest-Wort bzw. in eval
        "sh -c \"p=pytest; $p tests/\"",
        "eval \"uv run pytest tests/\"",
        # F004: weitere PYTEST_*-Umgebung
        f"PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest {NEW_FORM}",
        f"export PYTEST_ADDOPTS; uv run pytest {NEW_FORM}",
        f"${{X}}=1 uv run pytest {NEW_FORM}",
    ],
    ids=["umleitung-2-und-1-dann-flag", "umleitung-dann-p", "umleitung-dann-o",
         "stderr-umleitung-dann-c", "eingabe-umleitung-dann-override-ini",
         "und-umleitung-dann-p", "roh-umleitung-dann-p",
         "allow-hosts-0000", "allow-hosts-0000-und-127",
         "roh-pytest-aus-variable", "eval-breiter-lauf",
         "pytest-disable-plugin-autoload", "export-addopts-ohne-wert",
         "dynamischer-variablenname"],
)
def test_fixloop5_umleitung_und_waechter_sind_blockiert(command):
    proc = _run_gate(command)
    assert proc.returncode == 2, (
        f"Erwartet Block (Exit 2), bekam {proc.returncode} fuer: {command!r}\n{proc.stderr}"
    )
    assert "--loopback-own-ports" in proc.stderr, proc.stderr


@pytest.mark.parametrize(
    "command",
    [
        f"{DOCUMENTED_CALL} > out.txt 2>&1",
        "uv run pytest tests/tdd/x.py > out 2>&1",
    ],
    ids=["umleitung-und-2-und-1", "datei-umleitung"],
)
def test_fixloop5_umleitungen_bleiben_frei(command):
    proc = _run_gate(command)
    assert proc.returncode == 0, proc.stderr


def test_ac5_blockmeldung_nennt_den_neuen_aufruf():
    proc = _run_gate("uv run pytest --disable-socket")
    assert proc.returncode == 2, proc.stderr
    assert "--loopback-own-ports" in proc.stderr, proc.stderr
    assert "--allow-hosts=127.0.0.1,::1,localhost" in proc.stderr, proc.stderr


# ---------------------------------------------------------------------------
# Fix-Loop 6: exakter Vergleich statt Shell-Zerlegung. Frei ist die
# Offline-Form nur als genau eine der zwei festen Zeilen, optional mit
# genau `` > <pfad> 2>&1``. Alles andere faellt ins normale Gate.
# ---------------------------------------------------------------------------

BASE_CALL = f"uv run pytest {NEW_FORM}"


@pytest.mark.parametrize(
    "command",
    [
        # Runde 5: Zeilenfortsetzung -- die Shell fuegt die Zeilen zusammen
        f"{BASE_CALL} \\\n -o addopts=",
        f"{BASE_CALL} \\\n -c other.ini",
        f"sh -c \"{BASE_CALL} \\\n -o addopts=\"",
        # zusaetzliche Flags, die die Auswahl oder Konfiguration aendern
        f"{BASE_CALL} -m live",
        f"{BASE_CALL} -k foo",
        f"{BASE_CALL} --noconftest",
        f"{BASE_CALL} --rootdir=x",
        f"{BASE_CALL} -W error",
        f"{BASE_CALL} --lf",
        # Leerraum ist Teil des exakten Vergleichs
        BASE_CALL.replace(" --loopback-own-ports", "  --loopback-own-ports"),
        BASE_CALL.replace(" --loopback-own-ports", "\t--loopback-own-ports"),
        # Umleitung nur genau `` > <pfad> 2>&1``
        f"{BASE_CALL} > o.txt 2>&1 -o addopts=",
        f"{BASE_CALL} > -o 2>&1",
        f"{BASE_CALL} > a;b 2>&1",
    ],
    ids=["fortsetzung-o-addopts", "fortsetzung-c-ini", "roh-fortsetzung-o-addopts",
         "m-live", "k-foo", "noconftest", "rootdir", "w-error", "lf",
         "doppel-leerzeichen", "tab-statt-leerzeichen",
         "umleitung-dann-o-addopts", "umleitungsziel-beginnt-mit-strich",
         "umleitungsziel-semikolon"],
)
def test_fixloop6_abweichung_von_der_festen_zeile_ist_blockiert(command):
    proc = _run_gate(command)
    assert proc.returncode == 2, (
        f"Erwartet Block (Exit 2), bekam {proc.returncode} fuer: {command!r}\n{proc.stderr}"
    )
    assert "--loopback-own-ports" in proc.stderr, proc.stderr


@pytest.mark.parametrize(
    "command",
    [
        # bis Fix-Loop 5 frei, jetzt bewusst fail-closed (nicht die feste Zeile)
        "uv run pytest --disable-socket --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports",
        "uv run pytest --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1 --loopback-own-ports",
        f"sh -c \"uv run pytest {NEW_FORM}\"",
        f"{DOCUMENTED_CALL}; echo ok",
        f"{DOCUMENTED_CALL} | tee log",
        f"nohup {DOCUMENTED_CALL} > log &",
        f"{DOCUMENTED_CALL} > ~/out.txt 2>&1",
        f"{DOCUMENTED_CALL} 2> $HOME/err.txt",
        f"timeout 3000 {DOCUMENTED_CALL}",
        f"{DOCUMENTED_CALL} -x -q --tb=short",
        f"{BASE_CALL} tests/unit/",
        f"bash -c \"{DOCUMENTED_CALL}\"",
        # fruehere Mehrzeilen-Doku-Form (Zeilenfortsetzung)
        "uv run pytest --disable-socket --allow-unix-socket \\\n"
        "    --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports --ignore=tests/red/",
    ],
    ids=["failclosed-ohne-unix-socket", "failclosed-nur-127",
         "failclosed-roh-fallback-sicher", "failclosed-sichere-form-plus-echo",
         "failclosed-pipe-tee", "failclosed-nohup-hintergrund",
         "failclosed-umleitungsziel-tilde", "failclosed-umleitungsziel-variable",
         "failclosed-timeout", "failclosed-x-q-tb-short",
         "failclosed-verzeichnis-positional", "failclosed-bash-c-sichere-form",
         "failclosed-mehrzeilen-doku-form"],
)
def test_fixloop6_bewusst_fail_closed(command):
    proc = _run_gate(command)
    assert proc.returncode == 2, (
        f"Erwartet Block (Exit 2), bekam {proc.returncode} fuer: {command!r}\n{proc.stderr}"
    )
    assert "--loopback-own-ports" in proc.stderr, proc.stderr


@pytest.mark.parametrize(
    "command",
    [
        BASE_CALL,
        DOCUMENTED_CALL,
        f"{BASE_CALL} > out.txt 2>&1",
        f"{DOCUMENTED_CALL} > docs/artifacts/x/out-1.txt 2>&1",
        f"  {BASE_CALL}  ",
        f"  {DOCUMENTED_CALL} > out.txt 2>&1  ",
    ],
    ids=["basis-zeile", "doku-zeile", "basis-mit-umleitung", "doku-mit-umleitung",
         "basis-mit-rand-leerzeichen", "doku-umleitung-mit-rand-leerzeichen"],
)
def test_fixloop6_feste_zeilen_sind_frei(command):
    proc = _run_gate(command)
    assert proc.returncode == 0, proc.stderr


def test_fixloop6_blockmeldung_verlangt_einzeilig_woertlich():
    proc = _run_gate("uv run pytest --disable-socket")
    assert proc.returncode == 2, proc.stderr
    assert DOCUMENTED_CALL in proc.stderr, proc.stderr
    assert "einzeilig" in proc.stderr, proc.stderr
    assert "> datei 2>&1" in proc.stderr, proc.stderr


# ---------------------------------------------------------------------------
# Fix-Loop 7: ``#`` am Wortanfang ist fuer die Shell ein Kommentar (F001),
# Umleitung VOR der Datei (F002), nur ASCII-Rand-Leerraum wird gestrippt (F003).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest --disable-socket #x.py",
        "uv run pytest --disable-socket --allow-hosts=0.0.0.0/0 --loopback-own-ports #x.py",
        f"{BASE_CALL} -p no:socket #x.py",
        f"{BASE_CALL} --force-enable-socket # --co",
        "uv run pytest tests/ #x.py",
        # Roh-Pfad (verschachtelte Shell): dort gilt ``#`` genauso
        "sh -c \"uv run pytest --disable-socket #x.py\"",
    ],
    ids=["raute-datei-nur-disable-socket", "raute-datei-allow-hosts-alles",
         "raute-datei-p-no-socket", "raute-leer-dann-co", "raute-datei-verzeichnis",
         "roh-raute-datei"],
)
def test_fixloop7_kommentar_am_wortanfang_ist_blockiert(command):
    proc = _run_gate(command)
    assert proc.returncode == 2, (
        f"Erwartet Block (Exit 2), bekam {proc.returncode} fuer: {command!r}\n{proc.stderr}"
    )
    assert "--loopback-own-ports" in proc.stderr, proc.stderr


def test_fixloop7_umleitung_vor_der_datei_bleibt_frei():
    proc = _run_gate("uv run pytest > o.txt tests/tdd/x.py")
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize(
    "command",
    [f"{BASE_CALL} ", f"{BASE_CALL} ", f"{DOCUMENTED_CALL} "],
    ids=["basis-mit-nbsp", "basis-mit-em-space", "doku-mit-nbsp"],
)
def test_fixloop7_unicode_leerraum_am_rand_ist_nicht_die_feste_zeile(command):
    proc = _run_gate(command)
    assert proc.returncode == 2, (
        f"Erwartet Block (Exit 2), bekam {proc.returncode} fuer: {command!r}\n{proc.stderr}"
    )
    assert "--loopback-own-ports" in proc.stderr, proc.stderr


# ---------------------------------------------------------------------------
# Fix-Loop 8: Testschutz fuer ueberlebende Mutanten (Adversary F001, F003)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest tests/ > x.py",
        "uv run pytest tests/ 2> x.py",
        "uv run pytest tests/ >> x.py",
        "uv run pytest > x.py",
        "sh -c \"uv run pytest tests/ > x.py\"",
    ],
    ids=["stdout-ziel-py", "stderr-ziel-py", "anhaengen-ziel-py",
         "ohne-argumente-ziel-py", "roh-stdout-ziel-py"],
)
def test_fixloop8_umleitungsziel_ist_keine_benannte_testdatei(command):
    """F001: das Ziel einer Umleitung (``> x.py``) ist eine Ausgabedatei, kein
    Testlauf-Argument -- es darf einen Verzeichnis-/Volllauf nicht als
    'benannte Testdatei' freischalten (``_args_after``, ``skip_target``)."""
    proc = _run_gate(command)
    assert proc.returncode == 2, (
        f"Erwartet Block (Exit 2), bekam {proc.returncode} fuer: {command!r}\n{proc.stderr}"
    )
    assert "--loopback-own-ports" in proc.stderr, proc.stderr


@pytest.mark.parametrize(
    "command",
    [
        "grep pytest docs/x.md",
        "rg pytest docs/",
        "grep pytest docs/x.md && echo ok",
    ],
    ids=["grep-muster-ohne-flag", "rg-muster-ohne-flag", "grep-muster-dann-echo"],
)
def test_fixloop8_pytest_als_suchmuster_ohne_flag_ist_frei(command):
    """F003: ``pytest`` direkt hinter einem Suchbefehl (kein Flag dazwischen)
    ist dessen Suchmuster, kein Testlauf (``_TEXT_MATCH_COMMANDS``)."""
    proc = _run_gate(command)
    assert proc.returncode == 0, proc.stderr


def test_fixloop8_suchmuster_ausnahme_gilt_nicht_fuer_folgeanweisung():
    """Gegenprobe zu F003: die grep-Ausnahme reicht nicht ueber einen Trenner
    -- ein echter Breitlauf danach bleibt blockiert."""
    proc = _run_gate("grep pytest docs/x.md; uv run pytest tests/")
    assert proc.returncode == 2, proc.stderr
