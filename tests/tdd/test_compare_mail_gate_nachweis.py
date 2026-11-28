"""Compare-Mail-Gate: Herkunft des Nachweises und lokaler Render-Nachweis (#3503).

Spec: docs/specs/modules/fix_3503_compare_mail_gate_imac.md (AC-1 bis AC-8;
AC-9 belegen die Bestandstests test_issue_811_renderer_gate.py und
test_renderer_gate_compare_dispatch.py, deren Fixture-Logs ``quelle: imap``
tragen).

Kern-Schicht, ohne Netz, ohne Mock: echte Wegwerf-Git-Repos mit Kopien von
``src/``, ``scripts/send_gate_test_mails.py`` und ``.claude/hooks/*.py``.
Gate, Recorder ``record-compare-lokal`` und Validator laufen als Subprozess
mit eigener Workflow-Variable; Renderer und Validator laufen echt. Kein Lauf
schreibt in das ``_log`` des echten Repos.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_HOOKS = _ROOT / ".claude" / "hooks"
_GATE_SRC = _HOOKS / "renderer_mail_gate.py"
_WF = "test-3503-compare-nachweis"
_COMPARE = "src/output/renderers/email/compare_html.py"
_COMPARISON = "src/output/renderers/comparison.py"

if not _GATE_SRC.exists():
    pytest.skip(f"Gate-Hook fehlt: {_GATE_SRC}", allow_module_level=True)

try:  # Plugin-Sonde (#1196): hook_utils ist ein Shim auf das Plugin.
    _spec = importlib.util.spec_from_file_location("gate_3503", _GATE_SRC)
    _gate = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_gate)
except ImportError as _exc:
    pytest.skip(f"renderer_mail_gate nicht ladbar ({_exc}) — braucht das "
                "installierte agent-os-openspec-Plugin", allow_module_level=True)


# ---------------------------------------------------------------------------
# Wegwerf-Repo
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _env(workflow: str | None = _WF) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GZ_")}
    env.pop("OPENSPEC_ACTIVE_WORKFLOW", None)
    env.pop("CLAUDE_TOOL_INPUT", None)
    if workflow is not None:
        env["OPENSPEC_ACTIVE_WORKFLOW"] = workflow
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


@pytest.fixture(scope="module")
def _vorlage(tmp_path_factory) -> Path:
    """Einmal gebautes Git-Repo mit Baseline-Commit; Tests kopieren es."""
    repo = tmp_path_factory.mktemp("vorlage") / "repo"
    ign = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(_ROOT / "src", repo / "src", ignore=ign)
    (repo / "scripts").mkdir()
    shutil.copy(_ROOT / "scripts" / "send_gate_test_mails.py", repo / "scripts")
    hooks = repo / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    for py in _HOOKS.glob("*.py"):
        shutil.copy(py, hooks / py.name)
    (repo / ".claude" / "workflows" / "_log").mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.de")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    return repo


@pytest.fixture
def repo(_vorlage, tmp_path) -> Path:
    ziel = tmp_path / "repo"
    shutil.copytree(_vorlage, ziel, symlinks=True)
    state = {"name": _WF, "phase": "phase6_implement", "issue": 3503}
    (ziel / ".claude" / "workflows" / f"{_WF}.json").write_text(json.dumps(state))
    return ziel


def _stage_compare(repo: Path, marker: str) -> None:
    """Echte Compare-Renderer-Datei harmlos aendern (Kommentar) und stagen."""
    p = repo / _COMPARE
    p.write_text(p.read_text() + f"\n# {marker}\n")
    _git(repo, "add", _COMPARE)


def _staged_hash(repo: Path) -> str:
    return _gate._staged_mail_hash(repo, _gate._staged_files(repo))


def _state(repo: Path) -> dict:
    return json.loads((repo / ".claude" / "workflows" / f"{_WF}.json").read_text())


def _write_state(repo: Path, state: dict) -> None:
    (repo / ".claude" / "workflows" / f"{_WF}.json").write_text(json.dumps(state))


def _log_dir(repo: Path) -> Path:
    return repo / ".claude" / "workflows" / "_log"


def _write_log(repo: Path, *, quelle: str | None, passed: bool, name: str,
               mtime_offset: float = 0.0, vat_offset: float = 5.0) -> Path:
    vat = datetime.now(timezone.utc) + timedelta(seconds=vat_offset)
    zeilen = [
        "validator: email_spec_validator",
        f"validated_at: '{vat.isoformat()}'",
        f"workflow_id: {_WF}",
        f"passed: {str(passed).lower()}",
        "error_count: 0",
    ]
    if quelle is not None:
        zeilen.append(f"quelle: {quelle}")
    p = _log_dir(repo) / f"{name}_{_WF}_email_validation.yaml"
    p.write_text("\n".join(zeilen) + "\n")
    t = time.time() + mtime_offset
    os.utime(p, (t, t))
    return p


def _gate_hook(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "renderer_mail_gate.py")],
        cwd=repo, capture_output=True, text=True, env=_env(),
        input=json.dumps({"tool_input": {"command": "git commit -m wip"}}),
    )


def _recorder(repo: Path, workflow: str | None = _WF) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "renderer_mail_gate.py"),
         "record-compare-lokal"],
        cwd=repo, capture_output=True, text=True, env=_env(workflow),
        stdin=subprocess.DEVNULL, timeout=300,
    )


def _break_renderer(repo: Path, lang: str) -> None:
    """Compare-Ausgabe NUR fuer ``lang`` zerstoeren (Wegwerf-Repo, echter Code)."""
    p = repo / _COMPARISON
    p.write_text(p.read_text() + textwrap.dedent(f"""

        _orig_render_compare_email_3503 = render_compare_email

        def render_compare_email(result, *args, lang="de", **kwargs):  # Test #3503
            html, plain = _orig_render_compare_email_3503(result, *args, lang=lang, **kwargs)
            if lang == {lang!r}:
                return "<html><body><p>kaputt</p></body></html>", "kaputt"
            return html, plain
    """))


def _crash_renderer(repo: Path) -> None:
    """Compare-Renderer wirft beim Rendern eine Exception (Wegwerf-Repo)."""
    p = repo / _COMPARISON
    p.write_text(p.read_text() + textwrap.dedent("""

        def render_compare_email(result, *args, **kwargs):  # Test #3503 F001
            raise RuntimeError("Renderer-Absturz #3503")
    """))


def _validiere_im_repo(repo: Path) -> dict:
    """Vorbedingung: rendert im Wegwerf-Repo de+en und prueft mit dem Validator.

    Belegt, dass das Wegwerf-Repo den Renderer tatsaechlich aus seiner eigenen
    Kopie laedt und der Validator die Ausgabe beurteilen kann — sonst waeren
    AC-5/AC-8 bedeutungslos.
    """
    skript = textwrap.dedent("""
        import json, sys, email
        sys.path.insert(0, "scripts"); sys.path.insert(0, ".claude/hooks")
        import send_gate_test_mails as g
        from output.channels.email import build_mime_message
        import email_spec_validator as v
        out = {}
        for lang in ("de", "en"):
            subj, html, plain = g.build_compare_mail("t3503", lang=lang)
            msg = build_mime_message(subj, html, "a@b.de", "c@d.de", None, True, plain,
                                     mail_type="compare", mail_format="full", lang=lang)
            ok, errs = v.validate_message(email.message_from_bytes(msg.as_bytes()))
            out[lang] = [ok, errs[:3], g.__file__]
        print(json.dumps(out))
    """)
    r = subprocess.run([sys.executable, "-c", skript], cwd=repo, capture_output=True,
                       text=True, env=_env(None), timeout=300)
    assert r.returncode == 0, f"Vorbedingung: Rendern im Wegwerf-Repo scheitert:\n{r.stderr[-3000:]}"
    return json.loads(r.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------------------
# AC-1: Herkunftsfeld quelle im Validator-Log
# ---------------------------------------------------------------------------

def _validator(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "email_spec_validator.py"), *args],
        cwd=repo, capture_output=True, text=True, env=_env(), timeout=300,
    )


def _einziges_log(repo: Path) -> dict:
    import yaml
    logs = list(_log_dir(repo).glob("*_email_validation.yaml"))
    assert len(logs) == 1, f"genau ein Log erwartet, gefunden: {logs}"
    return yaml.safe_load(logs[0].read_text())


def test_ac1_eml_lauf_schreibt_quelle_eml(repo):
    """AC-1: Validator mit --eml schreibt ``quelle: eml`` ins Gate-Log."""
    eml = repo / "fixture.eml"
    skript = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, "scripts")
        import send_gate_test_mails as g
        from output.channels.email import build_mime_message
        subj, html, plain = g.build_compare_mail("t3503", lang="de")
        msg = build_mime_message(subj, html, "a@b.de", "c@d.de", None, True, plain,
                                 mail_type="compare", mail_format="full", lang="de")
        open({str(eml)!r}, "wb").write(msg.as_bytes())
    """)
    r = subprocess.run([sys.executable, "-c", skript], cwd=repo, capture_output=True,
                       text=True, env=_env(None), timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]

    _validator(repo, "--eml", str(eml))
    log = _einziges_log(repo)
    assert log.get("workflow_id") == _WF
    assert log.get("quelle") == "eml", (
        f"AC-1: --eml-Lauf muss quelle: eml ins Log schreiben, Log war: {log}")


def test_ac1_imap_lauf_schreibt_quelle_imap(repo):
    """AC-1: IMAP-Zweig von main() schreibt ``quelle: imap`` — ohne Netz:
    ohne Zugangsdaten scheitert der Abruf vor jeder Verbindung, das Log wird
    trotzdem geschrieben (passed: false)."""
    r = _validator(repo)
    assert r.returncode != 0
    log = _einziges_log(repo)
    assert log.get("passed") is False
    assert log.get("quelle") == "imap", (
        f"AC-1: IMAP-Lauf muss quelle: imap ins Log schreiben, Log war: {log}")


# ---------------------------------------------------------------------------
# AC-2 bis AC-4: Whitelist quelle: imap im Gate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("quelle", ["eml", None], ids=["quelle-eml", "ohne-quelle"])
def test_ac2_nicht_imap_log_blockiert(repo, quelle):
    """AC-2: nur ein frisches, passendes Log mit quelle eml/ohne quelle → Exit 2."""
    _stage_compare(repo, "ac2")
    _write_log(repo, quelle=quelle, passed=True, name="20991231_000001")
    r = _gate_hook(repo)
    assert r.returncode == 2, (
        f"AC-2: Log mit quelle={quelle!r} darf das Gate nicht erfuellen "
        f"(Exit {r.returncode}).\n{r.stderr}")


def test_ac3_eml_fehlerlauf_verdeckt_imap_erfolg_nicht(repo):
    """AC-3: imap passed:true (aelter) + eml passed:false (neuer) → Exit 0."""
    _stage_compare(repo, "ac3")
    _write_log(repo, quelle="imap", passed=True, name="20991231_000001", mtime_offset=10)
    _write_log(repo, quelle="eml", passed=False, name="20991231_000002", mtime_offset=20)
    r = _gate_hook(repo)
    assert r.returncode == 0, (
        f"AC-3: das Fixture-Log muss uebersprungen werden (Exit {r.returncode}).\n{r.stderr}")


def test_ac4_imap_fehlerlauf_blockiert_weiter(repo):
    """AC-4: juengstes passendes imap-Log passed:false → Exit 2."""
    _stage_compare(repo, "ac4")
    _write_log(repo, quelle="imap", passed=True, name="20991231_000001", mtime_offset=10)
    _write_log(repo, quelle="imap", passed=False, name="20991231_000002", mtime_offset=20)
    r = _gate_hook(repo)
    assert r.returncode == 2, f"AC-4: imap passed:false muss blocken.\n{r.stderr}"


# ---------------------------------------------------------------------------
# AC-5 / AC-8: Recorder record-compare-lokal
# ---------------------------------------------------------------------------

def test_ac5_recorder_schreibt_hashgebundenen_nachweis(repo):
    """AC-5: intakter Renderer → Exit 0, compare_lokal {passed, langs de+en,
    Hash des gestagten Stands}, _log unveraendert."""
    vorher = _validiere_im_repo(repo)
    assert vorher["de"][0] and vorher["en"][0], f"Vorbedingung: Fixture besteht: {vorher}"
    assert vorher["de"][2].startswith(str(repo)), "Vorbedingung: Fixture aus Wegwerf-Repo"

    _stage_compare(repo, "ac5")
    log_vorher = sorted(p.name for p in _log_dir(repo).iterdir())
    r = _recorder(repo)
    assert r.returncode == 0, f"AC-5: Exit {r.returncode}\n{r.stdout}\n{r.stderr}"
    eintrag = _state(repo).get("gates", {}).get("renderer_mail", {}).get("compare_lokal")
    assert eintrag, f"AC-5: compare_lokal fehlt im Zustand: {_state(repo)}"
    assert eintrag.get("passed") is True
    assert set(eintrag.get("langs", [])) >= {"de", "en"}
    assert eintrag.get("mail_files_hash") == _staged_hash(repo)
    assert sorted(p.name for p in _log_dir(repo).iterdir()) == log_vorher, (
        "AC-5: record-compare-lokal darf nichts nach _log schreiben")


@pytest.mark.parametrize("kaputt", ["de", "en"])
def test_ac8_recorder_kaputter_renderer_exit1_ohne_eintrag(repo, kaputt):
    """AC-8: Renderer verletzt die Spezifikation in EINER Sprache → Exit 1,
    Fehler genannt, kein Eintrag."""
    _break_renderer(repo, kaputt)
    vorher = _validiere_im_repo(repo)
    assert vorher[kaputt][0] is False, f"Vorbedingung: {kaputt} muss durchfallen: {vorher}"

    _stage_compare(repo, "ac8")
    state_vorher = _state(repo)
    r = _recorder(repo)
    assert r.returncode == 1, (
        f"AC-8: kaputter Renderer ({kaputt}) muss Exit 1 liefern, war "
        f"{r.returncode}\n{r.stdout}\n{r.stderr}")
    assert (r.stdout + r.stderr).strip(), "AC-8: Fehler muessen genannt werden"
    assert _state(repo) == state_vorher, "AC-8: kein Eintrag bei Befund"


def test_ac8_recorder_renderer_exception_exit1_ohne_eintrag(repo):
    """AC-8 (F001): Renderer wirft beim Rendern → Exit 1, Fehler genannt,
    kein compare_lokal-Eintrag (Absturz ist ein Befund, kein Nachweis)."""
    _crash_renderer(repo)
    _stage_compare(repo, "ac8c")
    state_vorher = _state(repo)
    r = _recorder(repo)
    assert r.returncode == 1, (
        f"AC-8: Renderer-Absturz muss Exit 1 liefern, war {r.returncode}\n"
        f"{r.stdout}\n{r.stderr}")
    assert "Renderer-Absturz #3503" in r.stderr, r.stderr
    assert _state(repo) == state_vorher, "AC-8: kein Eintrag bei Absturz"


def test_ac8_recorder_ohne_workflow_exit2(repo):
    """AC-8: ohne aktiven Workflow → Exit 2, kein Eintrag."""
    _stage_compare(repo, "ac8b")
    state_vorher = _state(repo)
    r = _recorder(repo, workflow=None)
    assert r.returncode == 2, f"AC-8: ohne Workflow Exit 2 erwartet, war {r.returncode}"
    assert _state(repo) == state_vorher


# ---------------------------------------------------------------------------
# AC-6 / AC-7: Gate akzeptiert compare_lokal nur hash-gebunden
# ---------------------------------------------------------------------------

_FEHLT = object()


def _set_compare_lokal(repo: Path, mail_hash: str, *, langs=("de", "en"),
                       passed=True) -> None:
    eintrag = {"mail_files_hash": mail_hash, "langs": list(langs),
               "recorded_at": datetime.now(timezone.utc).isoformat()}
    if passed is not _FEHLT:
        eintrag["passed"] = passed
    state = _state(repo)
    state.setdefault("gates", {}).setdefault("renderer_mail", {})["compare_lokal"] = eintrag
    _write_state(repo, state)


def test_ac6_compare_lokal_erfuellt_gate_ohne_imap_log(repo):
    """AC-6: compare_lokal fuer den gestagten Stand, kein imap-Log → Exit 0."""
    _stage_compare(repo, "ac6")
    _set_compare_lokal(repo, _staged_hash(repo))
    r = _gate_hook(repo)
    assert r.returncode == 0, f"AC-6: compare_lokal muss genuegen.\n{r.stderr}"


def test_ac7_veralteter_compare_lokal_blockiert_und_nennt_beide_wege(repo):
    """AC-7: nach Aufzeichnung erneut geaendert → Exit 2, Meldung nennt
    Server-Weg (Validator gegen zugestellte Mail) und record-compare-lokal."""
    _stage_compare(repo, "ac7-a")
    _set_compare_lokal(repo, _staged_hash(repo))
    _stage_compare(repo, "ac7-b")
    r = _gate_hook(repo)
    assert r.returncode == 2, f"AC-7: veralteter Nachweis muss blocken.\n{r.stderr}"
    assert "email_spec_validator" in r.stderr, r.stderr
    assert "record-compare-lokal" in r.stderr, (
        f"AC-7: Meldung muss den lokalen Weg nennen:\n{r.stderr}")
    assert "Ohne Test-Postfach" in r.stderr and "iMac" in r.stderr, (
        f"AC-7: Meldung muss den Weg ohne Test-Postfach (iMac) nennen:\n{r.stderr}")
    assert "Test-Postfach:" in r.stderr.replace("Ohne Test-Postfach", ""), (
        f"AC-7: Meldung muss den Server-Weg mit Test-Postfach nennen:\n{r.stderr}")


@pytest.mark.parametrize("langs", [["de"], ["en"], []], ids=["nur-de", "nur-en", "leer"])
def test_ac6_compare_lokal_ohne_beide_sprachen_blockiert(repo, langs):
    """AC-6 (F002): passender Hash, passed, aber nicht de UND en → Exit 2."""
    _stage_compare(repo, "f002")
    _set_compare_lokal(repo, _staged_hash(repo), langs=langs)
    r = _gate_hook(repo)
    assert r.returncode == 2, f"langs={langs} darf nicht genuegen.\n{r.stderr}"


@pytest.mark.parametrize("passed", [_FEHLT, "true"], ids=["passed-fehlt", "passed-string"])
def test_ac6_compare_lokal_ohne_passed_true_blockiert(repo, passed):
    """AC-6 (F003): passender Hash, de+en, aber passed fehlt/ist kein True → Exit 2."""
    _stage_compare(repo, "f003")
    _set_compare_lokal(repo, _staged_hash(repo), passed=passed)
    r = _gate_hook(repo)
    assert r.returncode == 2, f"passed={passed!r} darf nicht genuegen.\n{r.stderr}"


def test_ac4_veraltetes_imap_log_blockiert(repo):
    """F004: imap-Log passed:true, validated_at aelter als die gestagte
    Compare-Datei, kein compare_lokal → Exit 2 (Frische-Pruefung)."""
    _stage_compare(repo, "f004")
    _write_log(repo, quelle="imap", passed=True, name="20991231_000001",
               vat_offset=-3600)
    r = _gate_hook(repo)
    assert r.returncode == 2, f"veraltetes imap-Log muss blocken.\n{r.stderr}"
