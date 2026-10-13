"""Live-Schicht (nur ``/e2e-verify``): Push-Eingang fuer Befehle gegen STAGING.

Issue #2439 Scheibe (a). Spec: docs/specs/modules/feat_2439_befehle_push_eingang.md

Marker ``live`` + ``staging``: laeuft NICHT im Kern-Testlauf und NICHT lokal
(Opt-in ``GZ_STAGING_E2E=1``).

AC-Zuordnung:
  AC-11  HTTP-Smoke von aussen: ungueltiges Secret auf den Webhook-Pfaden ->
         403 (nicht 401/404/Basic-Auth-Challenge); ein uebriger Staging-Pfad
         -> 401 (Basic-Auth bleibt dort aktiv).
  AC-1   SMS: ``push.last_received`` von ``premium_sms_poll`` und ``last_run``
         des Jobs liegen Sekunden auseinander, nicht Minuten.
  AC-2   Mail: dasselbe fuer ``inbound_command_poll``.
  AC-8   ``push.last_received`` existiert im Status (Sichtbarkeit eines
         Ausfalls des Sofort-Wegs).

Voraussetzung fuer AC-1/AC-2: der /e2e-verify-Treiber hat VOR diesem Test eine
echte Befehls-SMS (zweite seven.io-Nummer) bzw. -Mail (``gregor-test+...@``)
auf Staging ausgeloest. Der Test misst nur den Zeitabstand im Status-Endpoint
(``X-GZ-Status-Token`` aus ``GZ_STAGING_STATUS_TOKEN``); Basic-Auth fuer
Staging optional aus ``GZ_STAGING_BASIC_AUTH`` (``user:pass``, nie im Klartext
ins Repo).
"""
from __future__ import annotations

import os
from datetime import datetime

import httpx
import pytest

STAGING = "https://staging.gregor20.henemm.com"
GRENZE_SEKUNDEN = 60  # "Sekunden, nicht Minuten" -- weit unter dem 5-min-Raster

pytestmark = [
    pytest.mark.live,
    pytest.mark.staging,
    pytest.mark.skipif(
        os.environ.get("GZ_STAGING_E2E") != "1",
        reason="Staging-Live-Test: nur /e2e-verify (GZ_STAGING_E2E=1)",
    ),
]


def _basic_auth() -> tuple[str, str] | None:
    roh = os.environ.get("GZ_STAGING_BASIC_AUTH", "")
    if ":" not in roh:
        return None
    user, _, pw = roh.partition(":")
    return user, pw


# ---------------------------------------------------------------------------
# AC-11: HTTP-Smoke von aussen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kanal", ["sms", "mail"])
def test_ac11_webhook_pfad_ungueltiges_secret_ist_403_ohne_basic_auth(kanal):
    antwort = httpx.post(
        f"{STAGING}/api/webhooks/{kanal}/ungueltiges-secret-ac11",
        content=b"{}", headers={"Content-Type": "application/json"}, timeout=15,
    )  # bewusst OHNE Basic-Auth: die Ausnahme fuer diese Pfade ist die Pruefung
    assert antwort.status_code == 403, (
        f"/api/webhooks/{kanal}/ auf Staging: erwartet 403 (Go-API erreicht, kein "
        f"Basic-Auth-Hindernis), bekam {antwort.status_code} "
        f"(WWW-Authenticate={antwort.headers.get('www-authenticate')!r})"
    )
    assert "www-authenticate" not in {k.lower() for k in antwort.headers}


def test_ac11_uebriger_staging_pfad_bleibt_geschuetzt():
    antwort = httpx.get(f"{STAGING}/api/scheduler/status", timeout=15)  # ohne Basic-Auth
    assert antwort.status_code == 401, (
        f"uebrige Staging-Pfade muessen hinter Basic-Auth bleiben, bekam {antwort.status_code}"
    )


# ---------------------------------------------------------------------------
# AC-1 / AC-2 / AC-8: Zeitabstand last_received -> last_run im Status
# ---------------------------------------------------------------------------

def _job_status(job_id: str) -> dict:
    token = os.environ.get("GZ_STAGING_STATUS_TOKEN")
    assert token, "GZ_STAGING_STATUS_TOKEN fehlt (Befund der Testumgebung, kein Flake)"
    antwort = httpx.get(
        f"{STAGING}/api/scheduler/status",
        headers={"X-GZ-Status-Token": token}, auth=_basic_auth(), timeout=15,
    )
    assert antwort.status_code == 200, antwort.text[:200]
    for job in antwort.json()["jobs"]:
        if job.get("id") == job_id:
            return job
    raise AssertionError(f"Job {job_id!r} nicht im Staging-Status")


def _pruefe_sofortweg(job_id: str):
    job = _job_status(job_id)
    push = job.get("push")
    assert isinstance(push, dict) and "last_received" in push, (
        f"{job_id}: Status-Feld push.last_received fehlt: {push!r}"  # AC-8
    )
    assert push["last_received"], (
        f"{job_id}: kein Webhook eingegangen (push.last_received leer) -- Treiber hat "
        f"keinen Befehl ausgeloest oder der Sofort-Weg ist ausgefallen: {push!r}"
    )
    assert push.get("received_total", 0) >= 1
    empfangen = datetime.fromisoformat(push["last_received"])
    assert job.get("last_run"), f"{job_id}: kein last_run"
    gelaufen = datetime.fromisoformat(job["last_run"]["time"])
    abstand = (gelaufen - empfangen).total_seconds()
    assert 0 <= abstand <= GRENZE_SEKUNDEN, (
        f"{job_id}: last_run {abstand:.0f} s nach last_received (erwartet Sekunden, "
        f"nicht Minuten): {push!r} / {job['last_run']!r}"
    )


def test_ac1_sms_last_run_sekunden_nach_webhook():
    _pruefe_sofortweg("premium_sms_poll")


def test_ac2_mail_last_run_sekunden_nach_webhook():
    _pruefe_sofortweg("inbound_command_poll")
