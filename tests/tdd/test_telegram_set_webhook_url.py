"""Issue #1814: telegram_set_webhook.sh registriert eine URL ohne Secret.

Spec: docs/specs/modules/fix_1814_telegram_webhook_secret_nicht_im_pfad.md (AC-1, AC-2)

Das echte Skript laeuft mit einem Stub-`curl` im PATH, der seine Argumente
und (bei ``-K -``) die per stdin gelieferte curl-Konfiguration aufzeichnet und
nichts ins Netz sendet. Seit #2961 stehen Bot-Token und Secret nur noch in der
Konfiguration, nie in den Prozessargumenten.
"""

import json
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "telegram_set_webhook.sh"
SECRET = "UNIQUE-TG-SECRET-1814-xyz"
BASE = "https://gregor.example.test"


STANDARD_ANTWORT = '{"ok":true,"result":true,"url":"STUB"}'


def _lauf(tmp_path: Path, cmd: str, antwort: str = STANDARD_ANTWORT, **env_extra):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "curl_args.log"
    antwort_datei = tmp_path / "curl_antwort.json"
    antwort_datei.write_text(antwort)
    stub = bin_dir / "curl"
    konfig = tmp_path / "curl_konfig.log"
    stub.write_text(
        '#!/usr/bin/env bash\n'
        f'printf "%s\\n" "$@" >> "{log}"\n'
        f'for a in "$@"; do [ "$a" = "-K" ] && cat >> "{konfig}"; done\n'
        f'cat "{antwort_datei}"\n'
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "TELEGRAM_BOT_TOKEN": "123:bot-token-test",
        "TELEGRAM_WEBHOOK_SECRET": SECRET,
        "GZ_PUBLIC_BASE_URL": BASE,
    }
    for name, wert in env_extra.items():
        if wert is None:
            env.pop(name, None)
        else:
            env[name] = wert
    proc = subprocess.run(
        ["bash", str(SCRIPT), cmd], env=env, capture_output=True, text=True, timeout=30
    )
    args = log.read_text().splitlines() if log.exists() else []
    werte = _konfig_werte(konfig.read_text()) if konfig.exists() else []
    return proc, args + werte, args


def _konfig_werte(text: str) -> list[str]:
    """Werte der curl-Konfiguration (``name = "wert"``), Escapes aufgeloest."""
    werte = []
    for zeile in text.splitlines():
        m = re.fullmatch(r'[\w-]+ = "(.*)"', zeile)
        assert m, f"unerwartete Konfigurationszeile: {zeile!r}"
        werte.append(re.sub(r'\\(.)', r"\1", m.group(1)))
    return werte


def test_set_registriert_url_ohne_secret(tmp_path):
    """AC-1: url endet auf /inbound, Secret nur im secret_token-Feld."""
    proc, args, _ = _lauf(tmp_path, "set")
    assert proc.returncode == 0, proc.stderr
    url_args = [a for a in args if a.startswith("url=")]
    assert url_args == [f"url={BASE}/api/webhooks/telegram/inbound"], url_args
    assert f"secret_token={SECRET}" in args
    for a in args:
        if a.startswith("secret_token="):
            continue
        assert SECRET not in a, f"Secret in Argument: {a!r}"


@pytest.mark.parametrize("cmd", ["set", "delete", "info"])
def test_token_und_secret_nie_in_den_prozessargumenten(tmp_path, cmd):
    """#2961: Bot-Token und Secret stehen in der stdin-Konfiguration, nie in argv."""
    proc, alles, argv = _lauf(tmp_path, cmd)
    assert proc.returncode == 0, proc.stderr
    assert "-K" in argv, argv
    for a in argv:
        assert SECRET not in a and "bot-token-test" not in a, f"Geheimnis in argv: {a!r}"
    assert any("bot-token-test" in w for w in alles), "Token fehlt in der Konfiguration"


def test_set_gibt_secret_nirgends_aus(tmp_path):
    """AC-2: weder stdout noch stderr enthalten das Secret."""
    proc, *_ = _lauf(tmp_path, "set")
    assert SECRET not in proc.stdout
    assert SECRET not in proc.stderr


def test_info_gibt_getwebhookinfo_nicht_roh_aus(tmp_path):
    """Spec Implementation Details: getWebhookInfo wird nicht roh ausgegeben."""
    proc, *_ = _lauf(tmp_path, "info")
    assert proc.returncode == 0, proc.stderr
    assert '"url"' not in proc.stdout, proc.stdout


def test_set_scheitert_bei_ok_false(tmp_path):
    """F001: lehnt Telegram setWebhook ab, endet das Skript mit Fehler."""
    proc, *_ = _lauf(tmp_path, "set", antwort='{"ok":false,"description":"Bad"}')
    assert proc.returncode != 0, proc.stdout
    assert "setWebhook ok: nein" in proc.stdout, proc.stdout


def test_set_basis_url_mit_slash_ergibt_keinen_doppelslash(tmp_path):
    """F002: abschliessender Slash der Basis-URL wird entfernt."""
    proc, args, _ = _lauf(tmp_path, "set", GZ_PUBLIC_BASE_URL="https://x.example/")
    assert proc.returncode == 0, proc.stderr
    url_args = [a for a in args if a.startswith("url=")]
    assert url_args == ["url=https://x.example/api/webhooks/telegram/inbound"], url_args


def _info_antwort(url: str, last_error: str = "") -> str:
    return json.dumps(
        {"ok": True, "result": {"url": url, "last_error_message": last_error}}
    )


def _info_zeilen(proc) -> dict:
    zeilen = {}
    for z in proc.stdout.splitlines():
        if z.startswith("→ ") and ": " in z:
            k, v = z[2:].rsplit(": ", 1)
            zeilen[k] = v
    return zeilen


def _assert_nichts_geleakt(proc, url: str):
    for strom in (proc.stdout, proc.stderr):
        assert SECRET not in strom, strom
        assert url not in strom, strom


NEU_URL = f"{BASE}/api/webhooks/telegram/inbound"
ALT_URL = f"{BASE}/api/webhooks/telegram/{SECRET}"


def test_info_korrekte_registrierung_alle_ja(tmp_path):
    """F003a: korrekte /inbound-URL ohne Fehler -> alle Zeilen ja."""
    proc, *_ = _lauf(tmp_path, "info", antwort=_info_antwort(NEU_URL))
    assert proc.returncode == 0, proc.stderr
    assert _info_zeilen(proc) == {
        "Antwort ok": "ja",
        "URL endet auf /api/webhooks/telegram/inbound": "ja",
        "URL frei von Secret": "ja",
        "last_error_message leer": "ja",
    }, proc.stdout
    _assert_nichts_geleakt(proc, NEU_URL)


def test_info_alt_url_mit_secret_im_pfad(tmp_path):
    """F003b: Alt-Registrierung mit Secret im Pfad -> zwei Zeilen nein."""
    proc, *_ = _lauf(tmp_path, "info", antwort=_info_antwort(ALT_URL))
    zeilen = _info_zeilen(proc)
    assert zeilen["URL endet auf /api/webhooks/telegram/inbound"] == "nein", proc.stdout
    assert zeilen["URL frei von Secret"] == "nein", proc.stdout
    assert zeilen["last_error_message leer"] == "ja", proc.stdout
    _assert_nichts_geleakt(proc, ALT_URL)


def test_info_last_error_gesetzt(tmp_path):
    """F003c: gesetzte last_error_message -> Zeile nein."""
    proc, *_ = _lauf(
        tmp_path, "info", antwort=_info_antwort(NEU_URL, "Wrong response: 403")
    )
    zeilen = _info_zeilen(proc)
    assert zeilen["last_error_message leer"] == "nein", proc.stdout
    assert zeilen["URL endet auf /api/webhooks/telegram/inbound"] == "ja", proc.stdout
    _assert_nichts_geleakt(proc, NEU_URL)


def test_info_ohne_secret_meldet_uebersprungen(tmp_path):
    """F004: fehlt TELEGRAM_WEBHOOK_SECRET, wird die Secret-Pruefung sichtbar uebersprungen."""
    proc, *_ = _lauf(
        tmp_path, "info", antwort=_info_antwort(ALT_URL), TELEGRAM_WEBHOOK_SECRET=None
    )
    assert proc.returncode == 0, proc.stderr
    assert (
        "→ URL frei von Secret: übersprungen (TELEGRAM_WEBHOOK_SECRET nicht gesetzt)"
        in proc.stdout.splitlines()
    ), proc.stdout
    assert SECRET not in proc.stdout
