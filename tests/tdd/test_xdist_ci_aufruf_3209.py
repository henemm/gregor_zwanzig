# doc-compliance-test
"""Issue #3209 (Fix-Loop 1, F005): der CI-Job ``test`` ruft pytest parallel
mit ``-n 4 --dist loadgroup`` auf.

Konfigurationspruefung statt Verhaltensnachweis, weil die Wirkung nur in CI
sichtbar ist: ohne ``--dist loadgroup`` ist die serielle Gruppe ``echtdaten``
wirkungslos (Tests am echten ``data/users``-Baum liefen verteilt), ohne ``-n``
laeuft der Job wieder seriell (~30 min). Das Verhalten der Gruppe selbst
belegen ``test_xdist_worker_sicherheit.py`` (AC-3/AC-4) per Subprozess.

Spec: docs/specs/modules/perf_3209_pytest_xdist_ci.md (AC-1/AC-2).
"""
from __future__ import annotations

import shlex
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _pytest_argumente() -> list[str]:
    job = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]["test"]
    aufrufe = [
        schritt["run"] for schritt in job["steps"]
        if "run" in schritt and "uv run pytest" in schritt["run"]
    ]
    assert len(aufrufe) == 1, f"erwartet genau einen pytest-Schritt im Job test, gefunden {len(aufrufe)}"
    zeilen = aufrufe[0].replace("\\\n", " ")
    befehl = next(z for z in zeilen.splitlines() if "uv run pytest" in z)
    return shlex.split(befehl.split("uv run pytest", 1)[1])


def test_ci_job_test_laeuft_mit_vier_workern_und_loadgroup():
    args = _pytest_argumente()
    assert "-n" in args and args[args.index("-n") + 1] == "4", args
    assert "--dist" in args and args[args.index("--dist") + 1] == "loadgroup", args


def test_ci_job_test_behaelt_die_sicherheitsflags():
    args = _pytest_argumente()
    for flag in ("--disable-socket", "--allow-unix-socket", "--ignore=tests/red/"):
        assert flag in args, (flag, args)
    assert "--allow-hosts=127.0.0.1,::1,localhost" in args, args
