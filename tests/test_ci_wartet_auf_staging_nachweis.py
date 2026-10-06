"""Warte-Skript der CI: liefert nur mit echtem Staging-Nachweis aus (#2047 Scheibe 2).

Verhaltenstests gegen ein Wegwerf-Git-Repo mit lokalem Bare-Repo als ``origin``.
Der Hauptordner steht absichtlich einen Commit HINTER ``origin/main`` und hat eine
uncommittete Aenderung — so faellt jedes ``reset``/``checkout`` des Skripts auf.

Das Gate ist ein kleiner Ersatz-Hook unter ``.claude/hooks/staging_gate.py`` mit
demselben Exit-Vertrag wie das echte Gate (0 = Nachweis da, sonst blockiert). Er
protokolliert seine Argumente (AC-4: dieselbe Gate-Logik wird befragt) und liest
die Folge seiner Exit-Codes aus einer Steuerdatei (AC-5/AC-8: Nachweis erscheint
erst spaeter).

Spec: docs/specs/modules/fix_2047_s2_ci_prod_gate.md
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci_wait_for_verdict.sh"

GATE_STUB = '''\
import sys
from pathlib import Path

LOG = Path({log!r})
CTRL = Path({ctrl!r})
with LOG.open("a", encoding="utf-8") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\\n")
seq = CTRL.read_text(encoding="utf-8").split()
rc = int(seq[0])
if len(seq) > 1:
    CTRL.write_text(" ".join(seq[1:]), encoding="utf-8")
sys.exit(rc)
'''


def _git(cwd: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    proc = subprocess.run(["git", *args], cwd=str(cwd), env=env, capture_output=True, text=True)
    assert proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr}"
    return proc.stdout.strip()


@pytest.fixture
def welt(tmp_path: Path) -> dict:
    gate_log = tmp_path / "gate_calls.log"
    gate_ctrl = tmp_path / "gate_ctrl"
    gate_ctrl.write_text("1", encoding="utf-8")

    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "--initial-branch=main", str(bare))

    seed = tmp_path / "seed"
    _git(tmp_path, "clone", "-q", str(bare), str(seed))
    _git(seed, "checkout", "-q", "-b", "main")
    hooks = seed / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "staging_gate.py").write_text(
        GATE_STUB.format(log=str(gate_log), ctrl=str(gate_ctrl)), encoding="utf-8"
    )
    (seed / "notiz.txt").write_text("stand A\n", encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "A")
    _git(seed, "push", "-q", "origin", "main")
    sha_a = _git(seed, "rev-parse", "HEAD")

    main = tmp_path / "hauptordner"
    _git(tmp_path, "clone", "-q", str(bare), str(main))

    (seed / "code.py").write_text("x = 1\n", encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "B")
    _git(seed, "push", "-q", "origin", "main")
    sha_b = _git(seed, "rev-parse", "HEAD")

    # Laufende Session-Arbeit im Hauptordner: muss jeden Ausgang ueberleben.
    (main / "notiz.txt").write_text("uncommittete Session-Arbeit\n", encoding="utf-8")
    (main / "untrackt.txt").write_text("frei\n", encoding="utf-8")

    return {
        "main": main,
        "bare": bare,
        "sha_a": sha_a,
        "sha_b": sha_b,
        "gate_log": gate_log,
        "gate_ctrl": gate_ctrl,
    }


def _run(welt: dict, sha: str, *, interval: str = "1", window: str = "3", repo: Path | None = None):
    assert SCRIPT.exists(), f"Prüfling fehlt: {SCRIPT}"
    env = {
        **os.environ,
        "GZ_REPO_DIR": str(repo if repo is not None else welt["main"]),
        "GZ_WAIT_INTERVAL": interval,
        "GZ_WAIT_WINDOW": window,
    }
    start = time.monotonic()
    proc = subprocess.run(
        ["bash", str(SCRIPT), sha], env=env, capture_output=True, text=True, timeout=60
    )
    return proc, time.monotonic() - start


def _gate_calls(welt: dict) -> list[str]:
    log = welt["gate_log"]
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def _zustand(main: Path) -> tuple[str, str, str, str]:
    return (
        _git(main, "rev-parse", "HEAD"),
        _git(main, "rev-parse", "--abbrev-ref", "HEAD"),
        _git(main, "status", "--porcelain"),
        (main / "notiz.txt").read_text(encoding="utf-8"),
    )


def test_nachweis_fuer_die_spitze_liefert_exit_0(welt):
    """AC-5 / Test 5: GIVEN Nachweis fuer origin/main-Spitze WHEN Skript laeuft THEN Exit 0."""
    welt["gate_ctrl"].write_text("0", encoding="utf-8")
    proc, _ = _run(welt, welt["sha_b"])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_befragt_dieselbe_gate_logik_mit_dem_sha(welt):
    """AC-4: das Skript ruft staging_gate.py --check --expected-commit <sha> auf."""
    welt["gate_ctrl"].write_text("0", encoding="utf-8")
    proc, _ = _run(welt, welt["sha_b"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    calls = _gate_calls(welt)
    assert calls, "das Gate wurde nie befragt"
    argv = calls[0].split()
    assert "--check" in argv and "--expected-commit" in argv, f"Gate-Aufruf: {calls[0]!r}"
    assert argv[argv.index("--expected-commit") + 1] == welt["sha_b"]


def test_ohne_nachweis_endet_nach_dem_fenster_mit_exit_10(welt):
    """AC-6 / Test 6: GIVEN kein Nachweis WHEN Fenster ablaeuft THEN Exit 10, Laufzeit >= Fenster."""
    proc, dauer = _run(welt, welt["sha_b"], interval="1", window="3")
    assert proc.returncode == 10, proc.stdout + proc.stderr
    assert dauer >= 3, f"Skript endete nach {dauer:.1f}s — vor Ablauf des Fensters (3s)"
    assert dauer < 15, f"Skript endete erst nach {dauer:.1f}s — Fenster wird nicht eingehalten"
    assert len(_gate_calls(welt)) >= 2, "im Fenster wurde nicht wiederholt gepollt"


def test_ueberholter_stand_endet_mit_exit_11_ohne_gate(welt):
    """AC-7 / Test 7: GIVEN origin/main ist weitergezogen WHEN Skript laeuft THEN Exit 11, Gate unbefragt."""
    welt["gate_ctrl"].write_text("0", encoding="utf-8")  # haette der Gate geantwortet: Nachweis da
    proc, _ = _run(welt, welt["sha_a"])
    assert proc.returncode == 11, proc.stdout + proc.stderr
    assert _gate_calls(welt) == [], f"Gate wurde trotz Ueberholung befragt: {_gate_calls(welt)}"


def test_nachweis_im_zweiten_durchlauf_wird_abgewartet(welt):
    """AC-5 / Test 8: GIVEN Nachweis erscheint erst im 2. Durchlauf WHEN Skript laeuft THEN Exit 0."""
    welt["gate_ctrl"].write_text("1 0", encoding="utf-8")
    proc, dauer = _run(welt, welt["sha_b"], interval="1", window="10")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert len(_gate_calls(welt)) == 2, f"erwartet genau 2 Gate-Befragungen: {_gate_calls(welt)}"
    assert dauer >= 1, "zwischen zwei Durchlaeufen wurde nicht gewartet"


@pytest.mark.parametrize(
    "ctrl, sha_key, erwartet",
    [("0", "sha_b", 0), ("1", "sha_b", 10), ("0", "sha_a", 11)],
)
def test_hauptordner_bleibt_bei_jedem_ausgang_unveraendert(welt, ctrl, sha_key, erwartet):
    """AC-15 / Test 9: HEAD, Branch und Arbeitsbaum bleiben bei jedem Ausgang unveraendert."""
    welt["gate_ctrl"].write_text(ctrl, encoding="utf-8")
    vorher = _zustand(welt["main"])
    proc, _ = _run(welt, welt[sha_key], interval="1", window="2")
    # Ohne diese Pruefung waere der Test schon gruen, wenn das Skript fehlt (bash Exit 127).
    assert proc.returncode == erwartet, proc.stdout + proc.stderr
    assert _zustand(welt["main"]) == vorher, "das Warte-Skript hat den Hauptordner veraendert"
    assert (welt["main"] / "untrackt.txt").exists()


def test_ungueltiger_repo_pfad_ist_ein_fehler(welt, tmp_path):
    """AC-8 / Test 10: GIVEN ungueltiger Repo-Pfad WHEN Skript laeuft THEN Exit 1 (nicht 10/11)."""
    proc, _ = _run(welt, welt["sha_b"], repo=tmp_path / "gibt-es-nicht")
    assert proc.returncode == 1, proc.stdout + proc.stderr


def test_fehlschlagender_fetch_ist_ein_fehler(welt, tmp_path):
    """AC-8 / Test 10: GIVEN git fetch scheitert WHEN Skript laeuft THEN Exit 1 (nicht 10/11)."""
    _git(welt["main"], "remote", "set-url", "origin", str(tmp_path / "weg.git"))
    welt["gate_ctrl"].write_text("0", encoding="utf-8")
    proc, _ = _run(welt, welt["sha_b"])
    assert proc.returncode == 1, proc.stdout + proc.stderr
