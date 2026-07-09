# doc-compliance-test — Hook als deterministisches CLI-Artefakt, kein Mock
"""Issue #1148 — Gate: Prod-Send-Deny (Baustein C aus #1147).

Mock-frei: der Hook `.claude/hooks/prod_send_gate.py` wird als echter
Subprozess mit stdin-JSON aufgerufen (identisches Muster wie ein
PreToolUse:Bash-Aufruf durch Claude Code). Der Hook EXISTIERT in der
RED-Phase NOCH NICHT -> alle Tests schlagen fehl (gueltiges RED).

Block-Kommandos muessen sowohl `returncode == 2` ALS AUCH `"1148" in stderr`
liefern -- ein `python3 <fehlende-datei>`-Fehlschlag liefert zwar ebenfalls
Exit 2, aber ohne den Issue-Verweis im stderr, wodurch die Block-Tests in
der RED-Phase garantiert rot sind.

Spec: docs/specs/modules/gate_1148_prod_send_deny.md
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = _REPO_ROOT / ".claude" / "hooks" / "prod_send_gate.py"

_WORKFLOW_NAME = "gate-1148-prod-send-deny"


def _run_hook(cmd: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_input": {"command": cmd}}),
        text=True,
        capture_output=True,
        env=env,
    )


def _isolated_env(tmp_path: Path, **extra: str) -> dict:
    """Env mit CLAUDE_PROJECT_DIR auf ein leeres tmp_path -- isoliert vom
    echten Repo-.claude/user_override_token.json (kein Token dort)."""
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}
    env.update(extra)
    return env


def _assert_blocked(result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 2, (
        f"Erwartet Exit 2 (blockiert), bekam {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "1148" in result.stderr, (
        f"stderr muss auf Issue #1148 verweisen. stderr={result.stderr!r}"
    )


def _assert_allowed(result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 0, (
        f"Erwartet Exit 0 (erlaubt), bekam {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


# --- AC-1 ---------------------------------------------------------------

def test_prod_python_port_post_send_blocked(tmp_path):
    env = _isolated_env(tmp_path)
    cmd_localhost = (
        "curl -X POST 'http://localhost:8000/api/scheduler/trips/1/send?user_id=x'"
    )
    cmd_loopback = (
        "curl -X POST 'http://127.0.0.1:8000/api/scheduler/trips/1/send?user_id=x'"
    )
    _assert_blocked(_run_hook(cmd_localhost, env))
    _assert_blocked(_run_hook(cmd_loopback, env))


# --- AC-2 ---------------------------------------------------------------

def test_staging_python_port_post_send_allowed(tmp_path):
    env = _isolated_env(tmp_path)
    cmd_localhost = (
        "curl -X POST 'http://localhost:8001/api/scheduler/trips/1/send?user_id=x'"
    )
    cmd_loopback = (
        "curl -X POST 'http://127.0.0.1:8001/api/scheduler/trips/1/send?user_id=x'"
    )
    _assert_allowed(_run_hook(cmd_localhost, env))
    _assert_allowed(_run_hook(cmd_loopback, env))


# --- AC-3 -----------------------------------------------------------------

def test_valid_override_token_allows_once_then_consumed(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    token_path = claude_dir / "user_override_token.json"
    token_path.write_text(json.dumps({
        "version": 2,
        "tokens": {
            _WORKFLOW_NAME: {
                "created": datetime.now(timezone.utc).isoformat(),
                "granted_by": "user_prompt",
            }
        },
    }))

    env = _isolated_env(
        tmp_path,
        OPENSPEC_ACTIVE_WORKFLOW=_WORKFLOW_NAME,
        GZ_ACTIVE_WORKFLOW=_WORKFLOW_NAME,
    )
    cmd = "curl -X POST 'http://localhost:8000/api/scheduler/trips/1/send?user_id=x'"

    first = _run_hook(cmd, env)
    assert first.returncode == 0, (
        f"Erster Aufruf mit gueltigem Override-Token muss Exit 0 liefern. "
        f"stdout={first.stdout!r} stderr={first.stderr!r}"
    )

    second = _run_hook(cmd, env)
    _assert_blocked(second)

    data = json.loads(token_path.read_text())
    assert _WORKFLOW_NAME not in data.get("tokens", {}), (
        "Token-Eintrag muss nach erfolgreichem Verbrauch entfernt sein: "
        f"{data}"
    )


# --- AC-4 ---------------------------------------------------------------

def test_get_health_against_prod_allowed(tmp_path):
    env = _isolated_env(tmp_path)
    cmd_local = "curl http://localhost:8000/api/health"
    cmd_hostname = "curl https://gregor20.henemm.com/api/health"
    _assert_allowed(_run_hook(cmd_local, env))
    _assert_allowed(_run_hook(cmd_hostname, env))


# --- AC-5 ---------------------------------------------------------------

def test_smtp_direct_connection_blocked(tmp_path):
    env = _isolated_env(tmp_path)
    cmd = "openssl s_client -connect smtp.resend.com:587 -starttls smtp"
    _assert_blocked(_run_hook(cmd, env))


# --- AC-6 ---------------------------------------------------------------

def test_smtp_grep_reference_allowed(tmp_path):
    env = _isolated_env(tmp_path)
    cmd = "grep -rn smtp.resend.com src/"
    _assert_allowed(_run_hook(cmd, env))


# --- AC-7 ---------------------------------------------------------------

def test_sh_c_obfuscated_prod_send_blocked(tmp_path):
    env = _isolated_env(tmp_path)
    cmd = 'bash -c "curl -X POST localhost:8000/api/scheduler/trips/1/send"'
    _assert_blocked(_run_hook(cmd, env))


# --- AC-8 ---------------------------------------------------------------

def test_gregor20_hostname_post_send_blocked(tmp_path):
    env = _isolated_env(tmp_path)
    cmd = "curl -X POST https://gregor20.henemm.com/api/scheduler/trip-reports"
    _assert_blocked(_run_hook(cmd, env))


# --- AC-9 ---------------------------------------------------------------

def test_staging_hostname_post_send_allowed(tmp_path):
    env = _isolated_env(tmp_path)
    cmd = "curl -X POST https://staging.gregor20.henemm.com/api/scheduler/trip-reports"
    _assert_allowed(_run_hook(cmd, env))


# --- Adversary Fix-Runde 1 (2026-07-09): F001-F006 -----------------------

def test_curl_request_long_form_post_send_blocked(tmp_path):
    """F001: curl --request POST ist curls Alias-Schreibweise zu -X POST."""
    env = _isolated_env(tmp_path)
    cmd = "curl --request POST http://localhost:8000/api/scheduler/trips/1/send"
    _assert_blocked(_run_hook(cmd, env))


def test_curl_form_and_json_post_send_blocked(tmp_path):
    """F002 (curl -F, Multipart) und F003 (curl --json) implizieren POST."""
    env = _isolated_env(tmp_path)
    cmd_form = "curl -F 'a=b' http://localhost:8000/api/scheduler/trips/1/send"
    cmd_json = "curl --json '{}' http://localhost:8000/api/scheduler/trips/1/send"
    _assert_blocked(_run_hook(cmd_form, env))
    _assert_blocked(_run_hook(cmd_json, env))


def test_wget_method_post_send_blocked(tmp_path):
    """F004: wget --method=POST ist die Alternative zu --post-data."""
    env = _isolated_env(tmp_path)
    cmd = "wget --method=POST http://localhost:8000/api/scheduler/trip-reports"
    _assert_blocked(_run_hook(cmd, env))


def test_smtp_ncat_socat_blocked(tmp_path):
    """F005: ncat/socat fehlten als SMTP-Verbindungs-Indikatoren."""
    env = _isolated_env(tmp_path)
    cmd_ncat = "ncat smtp.resend.com 587"
    cmd_socat = "socat - TCP:smtp.resend.com:587"
    _assert_blocked(_run_hook(cmd_ncat, env))
    _assert_blocked(_run_hook(cmd_socat, env))


def test_gh_issue_comment_quoting_block_example_allowed(tmp_path):
    """F006: ein woertliches Zitat eines Block-Beispiels im Freitext-Body ist
    keine echte Ausfuehrung -- darf nicht blockiert werden."""
    env = _isolated_env(tmp_path)
    cmd = (
        'gh issue comment 1148 --body '
        '"Repro: curl -X POST localhost:8000/api/scheduler/trips/1/send"'
    )
    _assert_allowed(_run_hook(cmd, env))


def test_gh_body_with_command_substitution_still_blocked(tmp_path):
    """Gegenprobe zu F006: Command-Substitution im Freitext-Body WIRD von der
    Shell tatsaechlich ausgefuehrt und darf nicht durch die Freitext-Ausnahme
    durchrutschen."""
    env = _isolated_env(tmp_path)
    cmd = (
        'gh issue comment 1148 --body '
        '"$(curl -X POST localhost:8000/api/scheduler/trips/1/send)"'
    )
    _assert_blocked(_run_hook(cmd, env))


# --- Adversary Fix-Runde 2 (2026-07-09): F007-F009 -----------------------

def test_ifs_obfuscated_post_send_blocked(tmp_path):
    """F008: ${IFS} statt Leerzeichen umgeht \\s-verankerte POST-Indikatoren,
    obwohl Host/Port/Pfad literal sichtbar bleiben."""
    env = _isolated_env(tmp_path)
    cmd_xpost = (
        "curl${IFS}-XPOST${IFS}http://localhost:8000/api/scheduler/trips/1/send"
    )
    cmd_request = (
        "curl${IFS}--request${IFS}POST${IFS}localhost:8000/api/scheduler/trip-reports"
    )
    _assert_blocked(_run_hook(cmd_xpost, env))
    _assert_blocked(_run_hook(cmd_request, env))


def test_ifs_obfuscated_smtp_blocked(tmp_path):
    """F008: ${IFS} umgeht die SMTP-Verbindungs-Indikatoren nc/openssl."""
    env = _isolated_env(tmp_path)
    cmd_nc = "nc${IFS}smtp.resend.com${IFS}587"
    cmd_openssl = "openssl${IFS}s_client${IFS}-connect${IFS}smtp.resend.com:587"
    _assert_blocked(_run_hook(cmd_nc, env))
    _assert_blocked(_run_hook(cmd_openssl, env))


def test_gh_body_then_chained_ifs_command_blocked(tmp_path):
    """F007: ein an einen gh/git-Freitext-Wert angehaengtes, per ${IFS}
    obfuskiertes Kommando darf nicht durch die Freitext-Ausnahme
    verschluckt werden -- die Shell fuehrt es bei echter Ausfuehrung
    tatsaechlich aus."""
    env = _isolated_env(tmp_path)
    cmd_send = (
        'gh issue comment 1148 --body "note"&&curl${IFS}-XPOST${IFS}'
        'localhost:8000/api/scheduler/trips/1/send'
    )
    cmd_smtp = (
        'gh issue comment 1148 --body "x"&&nc${IFS}smtp.resend.com${IFS}587'
    )
    _assert_blocked(_run_hook(cmd_send, env))
    _assert_blocked(_run_hook(cmd_smtp, env))


def test_grep_dash_F_and_tail_F_allowed(tmp_path):
    """F009: der toolunabhaengige -F-Indikator (F002-Fix) darf reine
    Lese-/Diagnose-Kommandos (grep -F, strings|grep -F, tail -F) nicht
    blockieren -- nur curl/wget nutzen -F als POST-Multipart-Flag."""
    env = _isolated_env(tmp_path)
    cmd_grep = (
        'grep -F "localhost:8000/api/scheduler/trips/1/send" src/routes.py'
    )
    cmd_strings = (
        "strings /home/hem/gregor_zwanzig/gregor-api | grep -F "
        '"trips/1/send"'
    )
    cmd_tail = "tail -F /var/log/x.log"
    _assert_allowed(_run_hook(cmd_grep, env))
    _assert_allowed(_run_hook(cmd_strings, env))
    _assert_allowed(_run_hook(cmd_tail, env))


def test_curl_dash_F_form_still_blocked(tmp_path):
    """Regressions-Gegenprobe zu F009: curl -F bleibt ein POST-Indikator,
    wenn das fuehrende Kommando-Token tatsaechlich curl ist."""
    env = _isolated_env(tmp_path)
    cmd = (
        "curl -F 'a=b' -X POST http://localhost:8000/api/scheduler/trips/1/send"
    )
    _assert_blocked(_run_hook(cmd, env))


# --- Adversary Fix-Runde 3 (2026-07-09): F010/F012 -----------------------

def test_line_continuation_post_send_blocked(tmp_path):
    """F010: Backslash-Newline-Zeilenfortsetzung (Standard-Bash-Syntax, von
    Bash beim Parsen entfernt) darf `-X\\s*POST` nicht umgehen -- Bash
    fuehrt `curl -X\\<NEWLINE>POST ...` real als `curl -XPOST ...` aus."""
    env = _isolated_env(tmp_path)
    cmd_xpost = (
        "curl -X\\\nPOST http://localhost:8000/api/scheduler/trips/1/send"
    )
    cmd_smtp = (
        "openssl s_client -connect \\\nsmtp.resend.com:587"
    )
    _assert_blocked(_run_hook(cmd_xpost, env))
    _assert_blocked(_run_hook(cmd_smtp, env))


def test_wrapper_prefix_curl_form_blocked(tmp_path):
    """F012: alltaegliche Wrapper-Praefixe (sudo/env/Absolutpfad) duerfen
    den `-F`/`--form`-POST-Indikator nicht umgehen -- das tatsaechlich
    ausgefuehrte Tool bleibt curl."""
    env = _isolated_env(tmp_path)
    cmd_sudo = (
        "sudo curl -F 'a=b' http://localhost:8000/api/scheduler/trips/1/send"
    )
    cmd_env = (
        "env curl -F 'a=b' http://localhost:8000/api/scheduler/trips/1/send"
    )
    cmd_abspath = (
        "/usr/bin/curl -F 'a=b' http://localhost:8000/api/scheduler/trips/1/send"
    )
    _assert_blocked(_run_hook(cmd_sudo, env))
    _assert_blocked(_run_hook(cmd_env, env))
    _assert_blocked(_run_hook(cmd_abspath, env))


def test_grep_dash_F_and_tail_F_still_allowed_round3(tmp_path):
    """Regressions-Gegenprobe zu F009 (darf durch F010/F012-Fix nicht
    kaputtgehen): reine Lese-/Diagnose-Kommandos bleiben erlaubt."""
    env = _isolated_env(tmp_path)
    cmd_grep = (
        'grep -F "localhost:8000/api/scheduler/trips/1/send" src/x.py'
    )
    cmd_tail_sudo = "sudo tail -F /var/log/x.log"
    _assert_allowed(_run_hook(cmd_grep, env))
    _assert_allowed(_run_hook(cmd_tail_sudo, env))


# --- Adversary Fix-Runde 4 (2026-07-09): F013 -----------------------------

def test_line_continuation_inside_keyword_blocked(tmp_path):
    """F013: Bash entfernt Backslash-Newline VOLLSTAENDIG (kein Leerzeichen)
    -- steht der Umbruch mitten in einem Indikator-Keyword, darf das
    Gate keinen Ersatz-Whitespace einfuegen, der das Wort zerreisst und
    dadurch die zusammenhaengenden Regexe (--form, POST, -F, s_client)
    verfehlen laesst."""
    env = _isolated_env(tmp_path)
    cmd_form = (
        "curl --fo\\\nrm 'a=b' http://localhost:8000/api/scheduler/trips/1/send"
    )
    cmd_post = (
        "curl -X PO\\\nST http://localhost:8000/api/scheduler/trips/1/send"
    )
    cmd_dash_f = (
        "curl -\\\nF 'a=b' http://localhost:8000/api/scheduler/trips/1/send"
    )
    cmd_smtp = (
        "openssl s_cli\\\nent -connect smtp.resend.com:587"
    )
    _assert_blocked(_run_hook(cmd_form, env))
    _assert_blocked(_run_hook(cmd_post, env))
    _assert_blocked(_run_hook(cmd_dash_f, env))
    _assert_blocked(_run_hook(cmd_smtp, env))
