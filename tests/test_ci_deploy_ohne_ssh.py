"""Job ``deploy`` in ci.yml liefert nicht mehr nach Produktion aus (#3394, henemm-infra#522).

# doc-compliance-test — ``ci.yml`` ist nicht als Ganzes ausfuehrbar; geprueft wird die
geparste Struktur. Produktion liefert allein der Pull-Deploy auf dem Server
(``henemm-infra/scripts/pull-deploy-gregor-prod.sh``, #3289). Der CI-Job darf daher
keinen SSH-Zugang, keine ``DEPLOY_*``-Geheimnisse und keine Telegram-Meldung mehr
enthalten; Staging-Warten und Smoke-Test bleiben.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _deploy_job() -> dict:
    jobs = yaml.safe_load(CI_YML.read_text(encoding="utf-8"))["jobs"]
    assert "deploy" in jobs, "Job 'deploy' fehlt in ci.yml"
    return jobs["deploy"]


def _job_text() -> str:
    return yaml.safe_dump(_deploy_job(), allow_unicode=True)


def test_deploy_job_enthaelt_kein_ssh():
    text = _job_text()
    for verboten in ("ssh ", "ssh-", "scp ", "gz-deploy", "deploy-gregor-prod.sh", "prod_selftest.py"):
        assert verboten not in text, f"Job deploy enthaelt noch {verboten!r}"


def test_deploy_job_nutzt_keine_deploy_geheimnisse():
    text = _job_text()
    for secret in ("DEPLOY_SSH_KEY", "DEPLOY_USER", "DEPLOY_HOST", "DEPLOY_KNOWN_HOSTS", "HENEMM_DEPLOY"):
        assert secret not in text, f"Job deploy nutzt noch {secret}"


def test_deploy_job_sendet_kein_telegram():
    text = _job_text()
    assert "api.telegram.org" not in text
    assert "Telegram" not in text


def test_deploy_job_hat_keine_prod_serialisierung_mehr():
    assert "concurrency" not in _deploy_job(), "concurrency prod-deploy ohne Auslieferung ueberfluessig"


def test_staging_warten_und_smoke_test_sind_noch_da():
    steps = _deploy_job()["steps"]
    names = [s.get("name", "") for s in steps]
    assert "Warten bis Staging aktuellen Commit hat" in names, names
    assert "Smoke-Test Staging" in names, names
    smoke = next(s for s in steps if s.get("name") == "Smoke-Test Staging")
    assert "STAGING_BASIC_AUTH" in smoke.get("env", {}), "Smoke-Test braucht STAGING_BASIC_AUTH"


def test_environment_bleibt_fuer_staging_secret():
    """STAGING_BASIC_AUTH ist ein Environment-Secret von ``production``."""
    assert _deploy_job().get("environment") == "production"
