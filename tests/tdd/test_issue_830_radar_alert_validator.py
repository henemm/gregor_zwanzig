"""TDD RED — Issue #830: Radar-Alert-Mail testbar machen.

RED-Treiber (was jetzt fehlschlägt):
- AC-1: GET /api/debug/trigger-radar-alert → 404 (Endpoint existiert nicht).
- AC-2: radar_alert_mail_validator.py existiert nicht → FileNotFoundError /
        Subprocess-Fehler (non-zero exit).
- AC-3: renderer_mail_gate.py hat den Radar-/Alert-Renderer-Pfad NOCH NICHT in
        _MAIL_PATTERNS → Gate lässt Commit durch (Exit 0) statt zu blockieren.
        (ADR-0017 Slice 3: Pfad ist jetzt src/output/renderers/alert/*.py —
        historisch src/outputs/radar_alert.py.)
- AC-4: Production URL → 404 (schon jetzt true, Guard-Test).
- Bonus: `src/outputs/radar_alert.py` fehlt → ImportError.
         `GZ_ENV`-Feld in Settings fehlt → AttributeError.

Mock-Regel: KEIN Mock()/patch()/MagicMock. Frame-Seam via frame_source-DI
erlaubt (dokumentierter Seam aus RadarNowcastService-Design).

SPEC: docs/specs/modules/issue_830_radar_alert_validator.md
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
import pytest

from tests.helpers.staging_auth import httpx_auth  # Bündel H #987: Staging-Basic-Auth

# Dialt real gegen Staging/Prod (#1211 Scheibe 2a) -- nur via -m staging ausfuehren.
pytestmark = pytest.mark.staging

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
VALIDATOR_PATH = HOOKS_DIR / "radar_alert_mail_validator.py"
GATE_PATH = HOOKS_DIR / "renderer_mail_gate.py"

STAGING_BASE = os.environ.get("GZ_SVELTE_BASE", "https://staging.gregor20.henemm.com")
PROD_BASE = "https://gregor20.henemm.com"

TRIGGER_PATH = "/api/debug/trigger-radar-alert"


# ============================================================================
# AC-1: Staging-Trigger-Endpoint sendet echte Mail
# ============================================================================

def test_ac1_trigger_endpoint_exists_on_staging():
    """
    GIVEN ein laufendes Staging-System (GZ_ENV=staging)
    WHEN  POST /api/debug/trigger-radar-alert?user_id=default aufgerufen wird
    THEN  antwortet der Endpoint mit HTTP 200 (nicht 404/405).

    RED: Endpoint existiert noch nicht → 404.
    """
    resp = httpx.post(
        f"{STAGING_BASE}{TRIGGER_PATH}",
        params={"user_id": "default"},
        auth=httpx_auth(),
        timeout=30.0,
    )
    assert resp.status_code == 200, (
        f"Staging-Trigger-Endpoint antwortet mit {resp.status_code} statt 200. "
        f"Body: {resp.text[:300]}"
    )
    body = resp.json()
    assert body.get("status") in ("sent", "no_trips", "no_segment"), (
        f"Unerwarteter Status: {body}"
    )


def test_ac1_trigger_response_contains_trip_info():
    """
    GIVEN Trigger-Endpoint existiert und Staging hat mindestens einen Trip
    WHEN  POST /api/debug/trigger-radar-alert aufgerufen wird
    THEN  Response enthält status=sent + trip_id + segment (kein leerer String).

    RED: Endpoint existiert nicht → 404.
    """
    resp = httpx.post(
        f"{STAGING_BASE}{TRIGGER_PATH}",
        params={"user_id": "default"},
        auth=httpx_auth(),
        timeout=30.0,
    )
    assert resp.status_code == 200, f"Status: {resp.status_code}"
    body = resp.json()
    assert body.get("status") == "sent", (
        f"Kein 'sent'-Status — möglicherweise kein Trip/Segment: {body}"
    )
    assert body.get("trip_id"), "trip_id fehlt oder leer"
    assert body.get("segment") is not None, "segment fehlt"


# ============================================================================
# AC-2: radar_alert_mail_validator.py — Datei existiert + Exit-Codes korrekt
# ============================================================================

def test_ac2_validator_file_exists():
    """
    GIVEN das Projekt-Hooks-Verzeichnis
    WHEN  wir nach radar_alert_mail_validator.py suchen
    THEN  existiert die Datei.

    RED: Datei existiert noch nicht.
    """
    assert VALIDATOR_PATH.exists(), (
        f"radar_alert_mail_validator.py nicht gefunden: {VALIDATOR_PATH}"
    )


def test_ac2_validator_loadable_as_module():
    """
    GIVEN radar_alert_mail_validator.py existiert
    WHEN  wir das Modul laden
    THEN  exportiert es validate_message() (analog briefing_mail_validator.py).

    RED: Datei fehlt → ImportError.
    """
    if not VALIDATOR_PATH.exists():
        pytest.fail(f"Validator-Datei nicht gefunden: {VALIDATOR_PATH}")

    spec = importlib.util.spec_from_file_location("rmv830", str(VALIDATOR_PATH))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert hasattr(mod, "validate_message"), (
        "validate_message-Funktion fehlt im Validator-Modul"
    )


def test_ac2_validator_exit2_for_wrong_mail_type():
    """
    GIVEN eine MIME-Nachricht mit X-GZ-Mail-Type: trip-briefing (falscher Typ)
    WHEN  validate_message() aufgerufen wird
    THEN  gibt sie (True, [Info-Nachricht]) zurück — sauberes No-Op.

    RED: Datei fehlt → ImportError in Setup.
    """
    from email.mime.text import MIMEText

    if not VALIDATOR_PATH.exists():
        pytest.fail(f"Validator-Datei nicht gefunden: {VALIDATOR_PATH}")

    spec = importlib.util.spec_from_file_location("rmv830_noop", str(VALIDATOR_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    msg = MIMEText("Leichter Regen ab ca. 14:30 (in ~5 Min).", "plain", "utf-8")
    msg["Subject"] = "Test"
    msg["X-GZ-Mail-Type"] = "trip-briefing"

    ok, errors = mod.validate_message(msg)
    assert ok is True, (
        "Falscher Mail-Typ sollte als No-Op durchgehen (ok=True), "
        f"stattdessen: ok={ok}, errors={errors}"
    )


def test_ac2_validator_exit1_for_missing_segment_label():
    """
    GIVEN eine MIME-Nachricht mit X-GZ-Mail-Type: radar-alert aber ohne Segment-Label
    WHEN  validate_message() aufgerufen wird
    THEN  gibt sie (False, [Fehlerdetail]) zurück — Exit 1.

    RED: Datei fehlt → ImportError.
    """
    from email.mime.text import MIMEText

    if not VALIDATOR_PATH.exists():
        pytest.fail(f"Validator-Datei nicht gefunden: {VALIDATOR_PATH}")

    spec = importlib.util.spec_from_file_location("rmv830_fail", str(VALIDATOR_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Mail ohne Segment-Label
    msg = MIMEText(
        "Leichter Regen ab ca. 14:30 (in ~5 Min).\n"
        "Du erhältst diese Warnung höchstens einmal in 2 Stunden.",
        "plain",
        "utf-8",
    )
    msg["Subject"] = "[Tour] Regen zieht auf"
    msg["X-GZ-Mail-Type"] = "radar-alert"

    ok, errors = mod.validate_message(msg)
    assert ok is False, (
        "Mail ohne Segment-Label sollte als FAIL bewertet werden, "
        f"aber ok={ok}"
    )
    assert any(
        "segment" in e.lower() or "etappe" in e.lower() or "km" in e.lower()
        for e in errors
    ), f"Fehlermeldung enthält keinen Hinweis auf fehlendes Segment: {errors}"


def test_ac2_validator_exit0_for_valid_radar_alert_mail():
    """
    GIVEN vollständige MIME-Mail mit X-GZ-Mail-Type: radar-alert und
          allen Pflichtfeldern (Segment-Label, Onset-Zeit, Intensitäts-Label, Cooldown)
    WHEN  validate_message() aufgerufen wird
    THEN  gibt sie (True, []) zurück — Exit 0.

    RED: Datei fehlt → ImportError.
    """
    from email.mime.text import MIMEText

    if not VALIDATOR_PATH.exists():
        pytest.fail(f"Validator-Datei nicht gefunden: {VALIDATOR_PATH}")

    spec = importlib.util.spec_from_file_location("rmv830_pass", str(VALIDATOR_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    body = (
        "Leichter Regen ab ca. 14:30 (in ~5 Min).\n"
        "auf Etappe 3, km 12–24.\n\n"
        "Quelle: Radar (DWD).\n"
        "Du erhältst diese Warnung höchstens einmal in 2 Stunden."
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = "[GR20] Regen zieht auf – Etappe 3"
    msg["X-GZ-Mail-Type"] = "radar-alert"

    ok, errors = mod.validate_message(msg)
    assert ok is True, (
        f"Valide Radar-Alert-Mail sollte Exit 0 ergeben, aber: errors={errors}"
    )


# ============================================================================
# AC-3: renderer_mail_gate.py blockiert Commit bei src/output/renderers/alert/*.py
# ============================================================================

def _run_gate(cwd: Path, workflow_name: str = "issue-830-test") -> int:
    """Führt renderer_mail_gate.py als Subprozess aus. Kein Mock."""
    env = {
        **os.environ,
        "GZ_ACTIVE_WORKFLOW": workflow_name,
        "CLAUDE_TOOL_INPUT": json.dumps({"command": "git commit -m test"}),
    }
    result = subprocess.run(
        [sys.executable, str(GATE_PATH)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )
    return result.returncode


def _make_temp_git_repo_with_workflow(workflow_name: str = "issue-830-test") -> Path:
    """Erstellt minimales Temp-Git-Repo mit Workflow-State-Stub."""
    tmpdir = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init"], cwd=str(tmpdir), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmpdir), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmpdir), check=True, capture_output=True,
    )
    (tmpdir / "README").write_text("init")
    subprocess.run(["git", "add", "README"], cwd=str(tmpdir), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(tmpdir), check=True, capture_output=True,
    )
    wf_dir = tmpdir / ".claude" / "workflows"
    wf_dir.mkdir(parents=True)
    state = {
        "name": workflow_name,
        "phase": "phase6_implementation",
        "gates": {},
    }
    (wf_dir / f"{workflow_name}.json").write_text(json.dumps(state))
    return tmpdir


def test_ac3_gate_blocks_radar_alert_py_without_nachweis():
    """
    GIVEN src/output/renderers/alert/render.py ist in git gestaged
    WHEN  renderer_mail_gate.py als Hook ausgeführt wird
    THEN  Exit-Code ist 2 (blockiert) — kein Nachweis vorhanden.

    ADR-0017 Slice 3: Radar-/Alert-Mail-Inhalt lebt im kanonischen
    Alert-Renderer (src/output/renderers/alert/), nicht mehr in
    src/outputs/radar_alert.py.
    """
    import shutil

    tmpdir = _make_temp_git_repo_with_workflow()
    try:
        radar_file = tmpdir / "src" / "output" / "renderers" / "alert" / "render.py"
        radar_file.parent.mkdir(parents=True)
        radar_file.write_text("# radar alert body builder\n")
        subprocess.run(
            ["git", "add", "src/output/renderers/alert/render.py"],
            cwd=str(tmpdir), check=True, capture_output=True,
        )

        exit_code = _run_gate(tmpdir)
        assert exit_code == 2, (
            f"Gate soll Commit blockieren (Exit 2), hat aber Exit {exit_code}. "
            "src/output/renderers/alert/*.py ist nicht in _MAIL_PATTERNS — "
            "Gate-Muster-Nachzug (ADR-0017 Slice 3) fehlt."
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_ac3_gate_allows_commit_after_radar_nachweis():
    """Positiv-Fall — Gate lässt nach Nachweis durch (skip in RED-Phase)."""
    pytest.skip(
        "Positiv-Fall — wird nach AC-3-Blocking-Implementierung als Guard geprüft."
    )


def test_bonus_settings_has_env_field():
    """
    GIVEN Settings aus src/app/config.py
    WHEN  instanziiert ohne GZ_ENV
    THEN  hat .env == "production" (Default).

    RED: GZ_ENV-Feld fehlt in Settings → AttributeError.
    """
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from app.config import Settings
    s = Settings()
    assert hasattr(s, "env"), (
        "Settings hat kein 'env'-Feld — GZ_ENV-Ergänzung in config.py fehlt."
    )
    assert s.env == "production", (
        f"Default-Wert soll 'production' sein, ist: {s.env!r}"
    )


# ============================================================================
# AC-4: Produktion antwortet mit 404
# ============================================================================

def test_ac4_production_endpoint_returns_404():
    """
    GIVEN das Produktionssystem (gregor20.henemm.com, GZ_ENV nicht 'staging')
    WHEN  POST /api/debug/trigger-radar-alert aufgerufen wird
    THEN  antwortet der Endpoint mit HTTP 404 oder 401 (Go-API-Auth-Gate).

    HTTP 404 = Python-Endpoint gibt 404 (GZ_ENV != staging-Guard).
    HTTP 401 = Go-API-Auth blockt vor dem Python-Routing — Endpoint ebenfalls
               nicht nutzbar (Sicherheitseigenschaft erfüllt).

    Regressionsschutz: Debug-Endpoint darf auf Produktion NIEMALS 200 liefern.
    """
    resp = httpx.post(
        f"{PROD_BASE}{TRIGGER_PATH}",
        params={"user_id": "default"},
        timeout=15.0,
    )
    assert resp.status_code in (401, 404), (
        f"Produktion antwortete mit {resp.status_code} — "
        "Debug-Endpoint darf auf Produktion NICHT aktiv sein (erwartet 401 oder 404)!"
    )
