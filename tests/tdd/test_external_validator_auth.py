"""
TDD-RED-Tests fuer Issue #110 — External Validator Auth.

Spec: docs/specs/modules/external_validator_auth.md
Test-Spec: docs/specs/tests/external_validator_auth_tests.md

Diese Tests muessen FAIL sein, bevor die Implementation existiert:
- .claude/validator.env.example existiert nicht
- .gitignore enthaelt .claude/validator.env nicht
- scripts/setup-validator-user.sh existiert nicht
- .claude/validate-external.sh hat keinen Login-/Dry-Run-Block
- .claude/agents/external-validator.md hat keinen 'Authenticated Requests'-Abschnitt

Live-Tests (Login, Setup) sind als pytest.mark.integration markiert
und brauchen .claude/validator.env + erreichbares Staging.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "docs/specs/modules/external_validator_auth.md"


@pytest.fixture
def hide_validator_env():
    """
    Verschiebt .claude/validator.env temporaer weg, damit Tests den
    'keine Credentials'-Pfad pruefen koennen, ohne von einer real
    vorhandenen .env beeinflusst zu werden.
    """
    env_file = REPO / ".claude/validator.env"
    backup = env_file.with_suffix(".env.test-backup")
    moved = False
    if env_file.exists():
        env_file.rename(backup)
        moved = True
    try:
        yield
    finally:
        if moved and backup.exists():
            backup.rename(env_file)


def test_validator_env_example_exists_with_required_keys():
    """
    GIVEN: Spec verlangt Template-Datei .claude/validator.env.example
    WHEN: Datei wird gelesen
    THEN: Sie existiert und enthaelt die drei erwarteten ENV-Keys
    """
    template = REPO / ".claude/validator.env.example"
    assert template.exists(), f"Template fehlt: {template}"
    content = template.read_text()
    for key in ("GZ_VALIDATOR_USER", "GZ_VALIDATOR_PASS", "GZ_VALIDATION_URL"):
        assert key in content, f"Key {key} fehlt in {template}"


def test_gitignore_excludes_validator_env():
    """
    GIVEN: Spec verlangt, dass .claude/validator.env nie ins Repo gelangt
    WHEN: .gitignore wird gelesen
    THEN: Eintrag .claude/validator.env ist enthalten
    """
    gitignore = REPO / ".gitignore"
    assert gitignore.exists(), ".gitignore fehlt"
    lines = [line.strip() for line in gitignore.read_text().splitlines()]
    assert ".claude/validator.env" in lines, (
        "Eintrag '.claude/validator.env' fehlt in .gitignore — "
        "Credentials koennten ins Repo committed werden"
    )


def test_setup_script_exists_and_is_executable():
    """
    GIVEN: Spec verlangt scripts/setup-validator-user.sh
    WHEN: Datei wird geprueft
    THEN: Existiert, ist Bash-Skript, ist ausfuehrbar
    """
    script = REPO / "scripts/setup-validator-user.sh"
    assert script.exists(), f"Setup-Skript fehlt: {script}"
    assert os.access(script, os.X_OK), f"Setup-Skript nicht ausfuehrbar: {script}"
    first_line = script.read_text().splitlines()[0]
    assert first_line.startswith("#!"), f"Shebang fehlt: {first_line}"
    assert "bash" in first_line, f"Kein Bash-Shebang: {first_line}"


def test_external_validator_agent_documents_authenticated_requests():
    """
    GIVEN: Spec verlangt Abschnitt 'Authenticated Requests' in Agent-Spec
    WHEN: external-validator.md wird gelesen
    THEN: Abschnitt + Cookie-curl-Beispiel sind enthalten
    """
    agent = REPO / ".claude/agents/external-validator.md"
    assert agent.exists(), f"Agent-Spec fehlt: {agent}"
    content = agent.read_text()
    assert "## Authenticated Requests" in content, (
        "Abschnitt '## Authenticated Requests' fehlt in external-validator.md"
    )
    assert 'Cookie: gz_session=' in content, (
        "Cookie-curl-Beispiel fehlt in Agent-Spec"
    )


def test_validate_external_supports_dry_run_mode(hide_validator_env):
    """
    GIVEN: Spec verlangt einen Dry-Run-Modus (GZ_VALIDATOR_DRY_RUN=1),
           der den fertigen Prompt zu stdout ausgibt statt 'claude --print'
           zu starten — sonst sind die Login/Cookie-Pfade nicht testbar
    WHEN: validate-external.sh laeuft mit DRY_RUN=1, ohne Credentials
    THEN: Skript exit 0, gibt einen Prompt-Text aus, startet KEINE Claude-Session
    """
    launcher = REPO / ".claude/validate-external.sh"
    assert launcher.exists(), f"Launcher fehlt: {launcher}"

    env = os.environ.copy()
    env["GZ_VALIDATOR_DRY_RUN"] = "1"
    env.pop("GZ_VALIDATOR_USER", None)
    env.pop("GZ_VALIDATOR_PASS", None)

    result = subprocess.run(
        ["bash", str(launcher), str(SPEC)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
        timeout=15,
    )

    assert result.returncode == 0, (
        f"Dry-Run-Modus exit {result.returncode}, stderr:\n{result.stderr}"
    )
    assert "Du bist der External Validator" in result.stdout, (
        f"Prompt-Text fehlt im Dry-Run-Output:\n{result.stdout[:500]}"
    )


def test_validate_external_warns_when_no_credentials(hide_validator_env):
    """
    GIVEN: Keine Credentials und keine validator.env
    WHEN: validate-external.sh laeuft mit DRY_RUN=1
    THEN: Prompt enthaelt KEINEN Auth-Cookie-Block
    """
    launcher = REPO / ".claude/validate-external.sh"
    env = os.environ.copy()
    env["GZ_VALIDATOR_DRY_RUN"] = "1"
    env.pop("GZ_VALIDATOR_USER", None)
    env.pop("GZ_VALIDATOR_PASS", None)

    result = subprocess.run(
        ["bash", str(launcher), str(SPEC)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
        timeout=15,
    )

    assert "Auth-Cookie" not in result.stdout, (
        "Cookie-Block sollte ohne Credentials FEHLEN, ist aber im Prompt:\n"
        f"{result.stdout}"
    )


@pytest.mark.integration
def test_validate_external_injects_cookie_with_real_login():
    """
    GIVEN: .claude/validator.env mit gueltigen Credentials, Staging erreichbar
    WHEN: validate-external.sh laeuft mit DRY_RUN=1
    THEN: Prompt enthaelt 'Auth-Cookie' und 'gz_session=<wert>'
    """
    env_file = REPO / ".claude/validator.env"
    if not env_file.exists():
        pytest.skip("Kein .claude/validator.env — Setup-Skript noch nicht gelaufen")

    launcher = REPO / ".claude/validate-external.sh"
    env = os.environ.copy()
    env["GZ_VALIDATOR_DRY_RUN"] = "1"

    result = subprocess.run(
        ["bash", str(launcher), str(SPEC)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
        timeout=30,
    )

    assert result.returncode == 0, (
        f"Launcher exit {result.returncode}, stderr:\n{result.stderr}"
    )
    assert "Auth-Cookie" in result.stdout, (
        f"Auth-Cookie-Block fehlt im Prompt:\n{result.stdout}"
    )
    assert "gz_session=" in result.stdout, (
        f"gz_session-Wert fehlt im Prompt:\n{result.stdout}"
    )


@pytest.mark.integration
def test_setup_script_idempotent_against_staging():
    """
    GIVEN: .claude/validator.env mit Credentials, Staging erreichbar
    WHEN: setup-validator-user.sh laeuft (potenziell mehrfach)
    THEN: Exit 0, Output sagt entweder 'angelegt' oder 'existiert bereits'
    """
    env_file = REPO / ".claude/validator.env"
    if not env_file.exists():
        pytest.skip("Kein .claude/validator.env — manueller Setup noetig")

    setup = REPO / "scripts/setup-validator-user.sh"
    if not setup.exists():
        pytest.fail(f"Setup-Skript fehlt: {setup}")

    result = subprocess.run(
        ["bash", str(setup)],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        timeout=30,
    )
    assert result.returncode == 0, (
        f"Setup-Skript exit {result.returncode}:\n{result.stderr}\n{result.stdout}"
    )
    out = result.stdout.lower()
    assert "angelegt" in out or "existiert bereits" in out, (
        f"Unerwarteter Output (weder 'angelegt' noch 'existiert bereits'):\n{result.stdout}"
    )
