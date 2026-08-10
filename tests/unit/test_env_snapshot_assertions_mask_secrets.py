"""
Nachweis-Test fuer #1535: `os.environ`-Zusicherungen in
`tests/tdd/test_issue_1014_live_optin.py` duerfen bei einer Verletzung keinen
echten Zugang im Diff drucken.

Vor dem Fix vergleicht die AC-1-Zusicherung ein echtes `os.environ`-Abbild
(gefiltert auf `GZ_TELEGRAM_*`) gegen `{}`. Ist `GZ_TELEGRAM_TEST_BOT_TOKEN`
gesetzt (z.B. auf dem Server, sourced aus einer .env), wird die Zusicherung
verletzt und pytest druckt den Wert im Fehlerdiff.

Dieser Test simuliert genau diese Server-Situation ueber einen isolierten
Subprocess-pytest-Lauf **nur auf dem Teil-A-Testknoten** (nicht die ganze
Datei — Teil B startet einen bis zu 240s langen Subprocess-Lauf ueber 6
Live-Dateien und ist hier irrelevant).

Der Kennwert ist ein frei erfundener Zeichenstring, kein echter Zugang.

Spec: docs/specs/fast/fix-1535-env-snapshot-maskieren.md
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

_FAKE_TOKEN = "fake-kennwert-1535-nicht-echt-xyz"

_TARGET_NODE_ID = (
    "tests/tdd/test_issue_1014_live_optin.py::"
    "test_live_telegram_enabled_does_not_touch_environ"
)


def test_masked_snapshot_assertion_survives_set_test_bot_token_and_hides_value():
    env = os.environ.copy()
    env["GZ_TELEGRAM_TEST_BOT_TOKEN"] = _FAKE_TOKEN
    for key in ("GZ_TELEGRAM_LIVE", "GZ_TELEGRAM_BOT_TOKEN", "GZ_TELEGRAM_CHAT_ID", "GZ_TELEGRAM_TEST_CHAT_ID"):
        env.pop(key, None)
    existing_pythonpath = env.get("PYTHONPATH", "")
    parts = [str(_REPO_ROOT), str(_REPO_ROOT / "src")]
    if existing_pythonpath:
        parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(parts)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", _TARGET_NODE_ID, "-v"],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    combined = result.stdout + result.stderr

    assert result.returncode == 0, (
        "Eine gesetzte GZ_TELEGRAM_TEST_BOT_TOKEN-Variable darf den Opt-in-Test "
        "nicht rot machen — sie sagt nichts ueber das Opt-in aus:\n"
        + combined[-4000:]
    )
    assert _FAKE_TOKEN not in combined, (
        "Der Kennwert erscheint in der Testausgabe — die os.environ-Zusicherung "
        "druckt den echten Wert statt eines maskierten Abbilds:\n" + combined[-4000:]
    )


def test_masked_snapshot_diff_names_key_but_hides_value(tmp_path):
    """Nachweis am Wirkort: erzwingt einen Fehlschlag der maskierten
    Zusicherung selbst (statt nur den Erfolgsfall zu beobachten) und prueft,
    dass der Diff den Schluesselnamen nennt, aber keinen der beiden Werte."""
    before_value = "fake-kennwert-1535-before-abc"
    after_value = "fake-kennwert-1535-after-xyz-anders"

    # WICHTIG: die Werte stehen NIRGENDS als Literal im Quelltext der
    # Reprodatei — sonst echot pytest sie beim Fehlschlag ueber den
    # Quellcode-Kontext, unabhaengig vom eigentlichen Diff. Sie werden zur
    # Laufzeit ausschliesslich ueber Umgebungsvariablen (mit neutralen
    # Namen, NICHT GZ_TELEGRAM_*) eingespeist.
    repro_file = tmp_path / "test_repro_masked_diff.py"
    repro_file.write_text(
        "import os\n"
        "from tests.tdd.test_issue_1014_live_optin import _masked_telegram_env_snapshot\n"
        "\n"
        "def test_forced_mismatch():\n"
        "    os.environ['GZ_TELEGRAM_TEST_BOT_TOKEN'] = os.environ['REPRO_BEFORE_VALUE']\n"
        "    before = _masked_telegram_env_snapshot()\n"
        "    os.environ['GZ_TELEGRAM_TEST_BOT_TOKEN'] = os.environ['REPRO_AFTER_VALUE']\n"
        "    after = _masked_telegram_env_snapshot()\n"
        "    assert before == after\n"
    )

    env = os.environ.copy()
    for key in (
        "GZ_TELEGRAM_LIVE",
        "GZ_TELEGRAM_BOT_TOKEN",
        "GZ_TELEGRAM_CHAT_ID",
        "GZ_TELEGRAM_TEST_CHAT_ID",
        "GZ_TELEGRAM_TEST_BOT_TOKEN",
    ):
        env.pop(key, None)
    env["REPRO_BEFORE_VALUE"] = before_value
    env["REPRO_AFTER_VALUE"] = after_value
    existing_pythonpath = env.get("PYTHONPATH", "")
    parts = [str(_REPO_ROOT), str(_REPO_ROOT / "src")]
    if existing_pythonpath:
        parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(parts)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(repro_file), "-v"],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    combined = result.stdout + result.stderr

    assert result.returncode != 0, (
        "Der erzwungene Mismatch haette die maskierte Zusicherung rot machen "
        "muessen — sonst prueft dieser Test gar nichts am Wirkort:\n" + combined[-4000:]
    )
    assert "GZ_TELEGRAM_TEST_BOT_TOKEN" in combined, (
        "Der Diff soll den Schluesselnamen nennen — ein Diff ohne Schluesselnamen "
        "waere nicht mehr aussagekraeftig:\n" + combined[-4000:]
    )
    assert before_value not in combined and after_value not in combined, (
        "Der Diff druckt einen echten Wert statt nur Schluesselname + Hash:\n"
        + combined[-4000:]
    )
