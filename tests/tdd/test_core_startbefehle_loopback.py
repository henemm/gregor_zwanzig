# doc-compliance-test
"""Issue #2190 AC-7 — Startbefehle des Python-Core bleiben loopback-only.

Der Bind-Guard (api/bind_guard.py) wirkt im Lifespan und damit erst NACH dem
Binden, wenn uvicorn mit ``--workers`` oder ``--reload`` laeuft (Master bzw.
Supervisor halten den Socket). Diese Startwege sind bewusst ausserhalb des
Umfangs; diese Datei bewacht, dass kein Betriebs-Startbefehl sie nutzt und
jeder ``--host 127.0.0.1`` traegt.

Geprueft werden ``frontend/e2e/ci-stack.sh`` (immer) und die systemd-Units in
``henemm-infra`` (nur falls lesbar — in der CI liegt das Nachbar-Repo nicht vor).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_STACK = REPO_ROOT / "frontend" / "e2e" / "ci-stack.sh"
INFRA_UNITS = [
    Path("/home/hem/henemm-infra/systemd/gregor-python.service"),
    Path("/home/hem/henemm-infra/systemd/gregor-python-staging.service"),
]

_CORE_START = "uvicorn api.main:app"


def _logical_lines(text: str) -> list[str]:
    """Fuegt Shell-Fortsetzungszeilen (``\\`` am Zeilenende) zusammen."""
    joined = re.sub(r"\\\n\s*", " ", text)
    return joined.splitlines()


def _core_start_commands(text: str) -> list[str]:
    return [line for line in _logical_lines(text) if _CORE_START in line]


def _assert_loopback_only(command: str, source: str) -> None:
    assert re.search(r"--host[ =]127\.0\.0\.1(\s|$)", command), (
        f"{source}: Core-Start ohne '--host 127.0.0.1': {command.strip()!r}"
    )
    assert "--workers" not in command, f"{source}: '--workers' umgeht den Bind-Guard (#2190): {command.strip()!r}"
    assert "--reload" not in command, f"{source}: '--reload' umgeht den Bind-Guard (#2190): {command.strip()!r}"


def test_ci_stack_startet_core_nur_auf_loopback() -> None:
    """
    GIVEN: frontend/e2e/ci-stack.sh startet den Core im CI-e2e-Job
    WHEN:  sein Startbefehl geprueft wird
    THEN:  enthaelt er --host 127.0.0.1 und weder --workers noch --reload
    """
    commands = _core_start_commands(CI_STACK.read_text())
    assert commands, f"Kein '{_CORE_START}'-Startbefehl in {CI_STACK} gefunden."
    for command in commands:
        _assert_loopback_only(command, "ci-stack.sh")


@pytest.mark.parametrize("unit", INFRA_UNITS, ids=lambda p: p.name)
def test_systemd_unit_startet_core_nur_auf_loopback(unit: Path) -> None:
    """
    GIVEN: die Prod-/Staging-Unit in henemm-infra startet den Core
    WHEN:  ihre ExecStart-Zeile geprueft wird (nur falls die Datei lesbar ist)
    THEN:  enthaelt sie --host 127.0.0.1 und weder --workers noch --reload
    """
    try:
        text = unit.read_text()
    except OSError:
        pytest.skip(f"{unit} nicht lesbar (Nachbar-Repo fehlt, z. B. in der CI)")
    exec_lines = [line for line in _logical_lines(text) if line.strip().startswith("ExecStart=")]
    commands = [line for line in exec_lines if _CORE_START in line]
    assert commands, f"Keine ExecStart-Zeile mit '{_CORE_START}' in {unit}."
    for command in commands:
        _assert_loopback_only(command, unit.name)
