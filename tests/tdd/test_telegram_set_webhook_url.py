"""Issue #1814: telegram_set_webhook.sh registriert eine URL ohne Secret.

Spec: docs/specs/modules/fix_1814_telegram_webhook_secret_nicht_im_pfad.md (AC-1, AC-2)

Das echte Skript laeuft mit einem Stub-`curl` im PATH, der seine Argumente
aufzeichnet und nichts ins Netz sendet.
"""

import os
import stat
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "telegram_set_webhook.sh"
SECRET = "UNIQUE-TG-SECRET-1814-xyz"
BASE = "https://gregor.example.test"


def _lauf(tmp_path: Path, cmd: str):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "curl_args.log"
    stub = bin_dir / "curl"
    stub.write_text(
        '#!/usr/bin/env bash\n'
        f'printf "%s\\n" "$@" >> "{log}"\n'
        'echo \'{"ok":true,"result":true,"url":"STUB"}\'\n'
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "TELEGRAM_BOT_TOKEN": "123:bot-token-test",
        "TELEGRAM_WEBHOOK_SECRET": SECRET,
        "GZ_PUBLIC_BASE_URL": BASE,
    }
    proc = subprocess.run(
        ["bash", str(SCRIPT), cmd], env=env, capture_output=True, text=True, timeout=30
    )
    args = log.read_text().splitlines() if log.exists() else []
    return proc, args


def test_set_registriert_url_ohne_secret(tmp_path):
    """AC-1: url endet auf /inbound, Secret nur im secret_token-Feld."""
    proc, args = _lauf(tmp_path, "set")
    assert proc.returncode == 0, proc.stderr
    url_args = [a for a in args if a.startswith("url=")]
    assert url_args == [f"url={BASE}/api/webhooks/telegram/inbound"], url_args
    assert f"secret_token={SECRET}" in args
    for a in args:
        if a.startswith("secret_token="):
            continue
        assert SECRET not in a, f"Secret in Argument: {a!r}"


def test_set_gibt_secret_nirgends_aus(tmp_path):
    """AC-2: weder stdout noch stderr enthalten das Secret."""
    proc, _ = _lauf(tmp_path, "set")
    assert SECRET not in proc.stdout
    assert SECRET not in proc.stderr


def test_info_gibt_getwebhookinfo_nicht_roh_aus(tmp_path):
    """Spec Implementation Details: getWebhookInfo wird nicht roh ausgegeben."""
    proc, _ = _lauf(tmp_path, "info")
    assert proc.returncode == 0, proc.stderr
    assert '"url"' not in proc.stdout, proc.stdout
