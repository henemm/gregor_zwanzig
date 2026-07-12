"""Official-Alert-Mail-Validator + Gate-Routing (Issue #1197 Luecke).

`renderer_mail_gate.py` routet Aenderungen an `src/output/renderers/alert/*.py`
bislang AUSSCHLIESSLICH an `radar_alert_mail_validator.py` -- der prueft aber
nur `X-GZ-Mail-Type: radar-alert`. Die Standalone-Amtliche-Warnung-Mail
(`official_alerts.py::render_official_alert_html`, Typ `official-alert`,
notification_service.py:530/640) war dadurch strukturell NIE legitim
erfuellbar (Gate-Erosion). Dieses Modul deckt den neuen
`official_alert_mail_validator.py` UND das korrigierte Gate-Routing ab.

Mock-frei: echte `email.message.Message`-Objekte, gebaut ueber die echte
`build_mime_message()`-Pipeline mit echt gerendertem HTML aus
`render_warn_block(variant="standalone", ...)` -- byte-identisch zu dem, was
`EmailOutput.send()` tatsaechlich verschickt. Gate-Routing-Tests: echtes
Temp-Git-Repo + Subprozess-Aufruf des Gate-Hooks (Vorbild:
test_issue_811_renderer_gate.py / test_issue_830_radar_alert_validator.py).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
VALIDATOR_PATH = HOOKS_DIR / "official_alert_mail_validator.py"
GATE_PATH = HOOKS_DIR / "renderer_mail_gate.py"

SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

UTC = timezone.utc


def _load_validator_module():
    if not VALIDATOR_PATH.exists():
        pytest.fail(f"Validator-Datei nicht gefunden: {VALIDATOR_PATH}")
    spec = importlib.util.spec_from_file_location("official_alert_mail_validator", VALIDATOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _alert(level, hazard, label, vf, vt, region="Hermagor-Pressegger See"):
    from services.official_alerts.models import OfficialAlert
    return OfficialAlert(
        source="geosphere_warn", hazard=hazard, level=level, label=label,
        valid_from=vf, valid_to=vt, region_label=region,
    )


def _notice(alert, scope_label, sms_scope, affected_chips, free_chips):
    from output.renderers.alert.official_alerts import OfficialAlertNotice
    return OfficialAlertNotice(
        alert=alert, scope_label=scope_label, sms_scope=sms_scope,
        affected_chips=affected_chips, free_chips=free_chips,
    )


def _render_official_alert_html() -> str:
    """Ein echt gerenderter Standalone-Alert-Body (uniforme Stufe)."""
    from output.renderers.alert.official_alerts import render_warn_block

    vf = datetime(2026, 7, 12, 6, 0, tzinfo=UTC)
    vt = datetime(2026, 7, 12, 20, 0, tzinfo=UTC)
    hitze = _notice(
        _alert(2, "extreme_heat", "Hitzewarnung", vf, vt),
        scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["gesamte Route"], free_chips=[],
    )
    return render_warn_block(
        [hitze], variant="standalone", source_label="GeoSphere Austria",
        stand_at="09:30", tz=UTC,
    )


def _build_real_official_alert_message(html_body: str):
    """Baut die Mail EXAKT ueber die Produktions-Pipeline (build_mime_message),
    mail_type=official-alert -- byte-identisch zum echten Versandweg."""
    from output.channels.email import build_mime_message

    return build_mime_message(
        subject="[GR20] Amtliche Warnung — Hitze",
        body=html_body,
        from_addr="gregor_zwanzig@henemm.com",
        to_header="gregor-test@henemm.com",
        reply_to=None,
        html=True,
        plain_text_body=None,
        mail_type="official-alert",
    )


# ---------------------------------------------------------------------------
# Validator: Datei existiert + ist ladbar
# ---------------------------------------------------------------------------

def test_validator_file_exists():
    assert VALIDATOR_PATH.exists(), (
        f"official_alert_mail_validator.py nicht gefunden: {VALIDATOR_PATH}"
    )


def test_validator_exports_validate_message():
    mod = _load_validator_module()
    assert hasattr(mod, "validate_message"), (
        "validate_message-Funktion fehlt im Validator-Modul"
    )


# ---------------------------------------------------------------------------
# Kernfall 1: valide official-alert-Mail -> True
# ---------------------------------------------------------------------------

def test_valid_official_alert_mail_passes():
    mod = _load_validator_module()
    msg = _build_real_official_alert_message(_render_official_alert_html())

    ok, errors = mod.validate_message(msg)
    assert ok is True, (
        f"Echt gerenderte official-alert-Mail sollte Checks bestehen, "
        f"aber errors={errors}"
    )


# ---------------------------------------------------------------------------
# Kernfall 2: falscher Mail-Typ -> No-Op True mit Info
# ---------------------------------------------------------------------------

def test_wrong_mail_type_is_clean_noop():
    mod = _load_validator_module()
    msg = _build_real_official_alert_message(_render_official_alert_html())
    # X-GZ-Mail-Type auf einen anderen Typ umschreiben.
    del msg["X-GZ-Mail-Type"]
    msg["X-GZ-Mail-Type"] = "trip-briefing"

    ok, errors = mod.validate_message(msg)
    assert ok is True, (
        f"Falscher Mail-Typ sollte No-Op sein (ok=True), aber ok={ok}, errors={errors}"
    )
    assert errors and "trip-briefing" in errors[0], (
        f"No-Op-Info sollte den fremden Mail-Typ nennen: {errors}"
    )


# ---------------------------------------------------------------------------
# Kernfall 3: kaputter/leerer Body -> False
# ---------------------------------------------------------------------------

def test_broken_body_fails():
    from email.mime.text import MIMEText

    mod = _load_validator_module()
    msg = MIMEText("Fehler beim Rendern — leerer Body.", "plain", "utf-8")
    msg["Subject"] = "[GR20] Amtliche Warnung"
    msg["X-GZ-Mail-Type"] = "official-alert"

    ok, errors = mod.validate_message(msg)
    assert ok is False, (
        f"Body ohne Verdict/Warnstufe/Quelle-Struktur sollte scheitern, aber ok={ok}"
    )
    assert errors, "Fehlerliste sollte nicht leer sein"


def test_empty_body_fails():
    from email.mime.text import MIMEText

    mod = _load_validator_module()
    msg = MIMEText("", "plain", "utf-8")
    msg["Subject"] = "[GR20] Amtliche Warnung"
    msg["X-GZ-Mail-Type"] = "official-alert"

    ok, errors = mod.validate_message(msg)
    assert ok is False


# ---------------------------------------------------------------------------
# Gate-Routing: official_alerts.py -> official-Validator (nicht radar);
# render.py (Radar-Renderer) -> radar-Validator (nicht official).
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


_WF_NAME = "fix-1197-official-alert-mail-validator"


def _setup_repo(tmp_path: Path) -> Path:
    import shutil

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.de")
    _git(repo, "config", "user.name", "Test")

    hooks = repo / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    shutil.copy(GATE_PATH, hooks / "renderer_mail_gate.py")
    for helper in ("config_loader.py", "workflow.py", "workflow_state_multi.py", "hook_utils.py"):
        src = HOOKS_DIR / helper
        if src.exists():
            shutil.copy(src, hooks / helper)

    (repo / ".claude" / "workflows" / "_log").mkdir(parents=True)

    alert_dir = repo / "src" / "output" / "renderers" / "alert"
    alert_dir.mkdir(parents=True)
    (alert_dir / "official_alerts.py").write_text("# official alert renderer initial\n")
    (alert_dir / "render.py").write_text("# radar/deviation renderer initial\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    return repo


def _run_gate(repo: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["OPENSPEC_ACTIVE_WORKFLOW"] = _WF_NAME
    env["GZ_ACTIVE_WORKFLOW"] = _WF_NAME
    return subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "renderer_mail_gate.py"), *args],
        cwd=repo, input=stdin, capture_output=True, text=True, env=env,
    )


def _commit_stdin() -> str:
    return json.dumps({"tool_input": {"command": "git commit -m wip"}})


def _write_official_alert_log(repo: Path, *, passed: bool = True, validated_at=None) -> Path:
    now = validated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    log_dir = repo / ".claude" / "workflows" / "_log"
    ts = now.strftime("%Y%m%d_%H%M%S")
    p = log_dir / f"{ts}_{_WF_NAME}_official_alert_validation.yaml"
    p.write_text(
        "validator: official_alert_mail_validator\n"
        f"validated_at: '{now.isoformat()}'\n"
        f"workflow_id: '{_WF_NAME}'\n"
        f"passed: {str(passed).lower()}\n"
        "error_count: 0\n"
    )
    return p


def _write_radar_alert_log(repo: Path, *, passed: bool = True, validated_at=None) -> Path:
    now = validated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    log_dir = repo / ".claude" / "workflows" / "_log"
    ts = now.strftime("%Y%m%d_%H%M%S")
    p = log_dir / f"{ts}_{_WF_NAME}_radar_alert_validation.yaml"
    p.write_text(
        "validator: radar_alert_mail_validator\n"
        f"validated_at: '{now.isoformat()}'\n"
        f"workflow_id: '{_WF_NAME}'\n"
        f"passed: {str(passed).lower()}\n"
        "error_count: 0\n"
    )
    return p


def _write_workflow_state(repo: Path) -> Path:
    state = {"name": _WF_NAME, "phase": "phase6", "issue": 1197, "gates": {}}
    p = repo / ".claude" / "workflows" / f"{_WF_NAME}.json"
    p.write_text(json.dumps(state))
    return p


def test_official_alerts_py_blocked_without_official_nachweis(tmp_path):
    """official_alerts.py gestaged, KEIN official-alert-Validator-Log -> Exit 2."""
    repo = _setup_repo(tmp_path)
    _write_workflow_state(repo)
    official_path = repo / "src" / "output" / "renderers" / "alert" / "official_alerts.py"
    official_path.write_text("# changed\n")
    _git(repo, "add", "src/output/renderers/alert/official_alerts.py")

    res = _run_gate(repo, stdin=_commit_stdin())
    assert res.returncode == 2, (
        f"official_alerts.py ohne official-alert-Validator-Nachweis muss blockieren. "
        f"rc={res.returncode} stderr={res.stderr!r}"
    )
    assert "official_alert_mail_validator.py" in res.stderr, (
        f"Blockierung soll den official-Validator nennen: {res.stderr!r}"
    )


def test_official_alerts_py_passes_with_official_nachweis_alone(tmp_path):
    """official_alerts.py gestaged + official-alert-Log (frisch, passed) -> Exit 0
    OHNE dass ein radar_alert_validation.yaml noetig ist (kein Doppel-Zwang)."""
    repo = _setup_repo(tmp_path)
    _write_workflow_state(repo)
    official_path = repo / "src" / "output" / "renderers" / "alert" / "official_alerts.py"
    official_path.write_text("# changed\n")
    _git(repo, "add", "src/output/renderers/alert/official_alerts.py")

    mtime = official_path.stat().st_mtime
    fresh = datetime.fromtimestamp(mtime + 2.0, tz=timezone.utc)
    _write_official_alert_log(repo, passed=True, validated_at=fresh)

    res = _run_gate(repo, stdin=_commit_stdin())
    assert res.returncode == 0, (
        f"official_alerts.py MIT frischem official-alert-Nachweis muss passieren "
        f"(kein radar-Log noetig). rc={res.returncode} stderr={res.stderr!r}"
    )


def test_render_py_still_requires_radar_nachweis_not_official(tmp_path):
    """render.py (Radar-/Deviation-Renderer) gestaged -> weiterhin radar-Validator
    erforderlich, NICHT der official-Validator (Routing bleibt praezise)."""
    repo = _setup_repo(tmp_path)
    _write_workflow_state(repo)
    render_path = repo / "src" / "output" / "renderers" / "alert" / "render.py"
    render_path.write_text("# changed radar renderer\n")
    _git(repo, "add", "src/output/renderers/alert/render.py")

    res = _run_gate(repo, stdin=_commit_stdin())
    assert res.returncode == 2, "render.py ohne Nachweis muss weiterhin blockieren"
    assert "radar_alert_mail_validator.py" in res.stderr, (
        f"Blockierung soll den radar-Validator nennen: {res.stderr!r}"
    )
    assert "official_alert_mail_validator.py" not in res.stderr, (
        "render.py darf NICHT den official-Validator verlangen (falsches Routing): "
        f"{res.stderr!r}"
    )

    mtime = render_path.stat().st_mtime
    fresh = datetime.fromtimestamp(mtime + 2.0, tz=timezone.utc)
    _write_radar_alert_log(repo, passed=True, validated_at=fresh)

    res2 = _run_gate(repo, stdin=_commit_stdin())
    assert res2.returncode == 0, (
        f"render.py MIT radar-Nachweis (ohne official-Log) muss passieren. "
        f"rc={res2.returncode} stderr={res2.stderr!r}"
    )
