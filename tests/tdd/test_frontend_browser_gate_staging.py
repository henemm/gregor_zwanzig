"""TDD RED (#1558), Live-Schicht: AC-6/AC-7 gegen echtes Staging.

Spec: docs/specs/modules/feat_1558_frontend_browser_gate.md
Schnittstelle: siehe Kopf von tests/tdd/test_frontend_browser_gate.py.

Nur gegen https://staging.gregor20.henemm.com — NIE gegen Produktion.
Zugangsdaten ausschliesslich ueber Variablennamen aus `.claude/validator.env`
(GZ_VALIDATOR_*) und `.env` (GZ_AUTH_*); Lade-Muster wie
design_fidelity_diff.load_validator_env().

Lauf: uv run pytest tests/tdd/test_frontend_browser_gate_staging.py -m staging
"""

import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.staging

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
GATE_PATH = HOOKS_DIR / "e2e_frontend_browser_gate.py"
STAGING_BASE = "https://staging.gregor20.henemm.com"
NEEDED = ("GZ_VALIDATOR_USER", "GZ_VALIDATOR_PASS", "GZ_AUTH_USER", "GZ_AUTH_PASS")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sg = _load("staging_gate_fbg_live", HOOKS_DIR / "staging_gate.py")


def _gate_mod():
    assert GATE_PATH.exists(), f"Gate-Modul fehlt: {GATE_PATH}"
    return _load("e2e_frontend_browser_gate_live", GATE_PATH)


def _staging_env() -> dict:
    env = {"GZ_VALIDATION_URL": STAGING_BASE}
    for f in (REPO_ROOT / ".claude" / "validator.env", REPO_ROOT / ".env"):
        if not f.exists():
            continue
        for line in f.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    missing = [k for k in NEEDED if not env.get(k)]
    if missing:
        pytest.skip(f"Zugangsdaten fehlen: {', '.join(missing)}")
    return env


def test_invalid_app_password_is_not_a_passed_core_page(capsys):
    """AC-6: falsches Anwendungs-Passwort → Nicht-Bestehen, Meldung nennt den
    Anmeldegrund. Eine fehlerfreie Anmeldemaske gilt NICHT als bestanden (#1307)."""
    env = {**_staging_env(), "GZ_AUTH_PASS": "definitiv-falsch-1558"}
    rc = _gate_mod().gate("frontend-only", env)
    text = "".join(capsys.readouterr()).lower()
    assert rc != 0, "Anmeldemaske wurde als bestandene Kernseite gewertet"
    assert any(w in text for w in ("anmeld", "login", "passwort")), (
        f"Meldung nennt den Anmeldegrund nicht: {text!r}"
    )


def test_clean_run_writes_attestation_naming_checked_pages(tmp_path, monkeypatch):
    """AC-7: sauberer Lauf gegen Staging → Attestation entsteht und benennt die
    geprueften Seiten (Feld 'frontend_pages_checked')."""
    for k, v in _staging_env().items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(sg, "_telegram_live_gate", lambda: 0)

    e2e_path = tmp_path / "attestation.json"
    rc = sg.write_verdict("VERIFIED: #1558 Live-Nachweis", tmp_path / "findings.json",
                          e2e_path=e2e_path, scope_override="frontend-only")

    assert rc == 0, "sauberer Frontend-Lauf gegen Staging muss durchlaufen"
    checked = json.loads(e2e_path.read_text()).get("frontend_pages_checked") or []
    assert set(_gate_mod().CORE_PAGES) <= set(checked), (
        f"Attestation benennt die geprueften Seiten nicht vollstaendig: {checked}"
    )
