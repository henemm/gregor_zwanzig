"""Issue #2681 (A2): Nachweis-Feld ``langs`` im Staging-Gate (AC-5, AC-7, AC-8 Kern).

Spec: docs/specs/modules/i18n_a2_e2e_zweisprachig_2681.md

Schreibseite (``write_verdict``) und Leseseite (``gate_check``) laufen ECHT gegen
Dateien und ein echtes temporaeres Git-Repo. Einzige Seams: die Location-Seams
``_shared_repo_dir``/``_verified_repo_dir`` (Muster
test_staging_gate_ancestor_scope.py) und die UNBETEILIGTEN Live-Gates
(Telegram, Frontend-Browserlauf), Muster test_staging_gate_verdict_merge.py.
Kein Netz in der Kern-Schicht; der Selftest-Lauf (AC-7) dialt Prod und ist
deshalb als ``staging`` markiert.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS = REPO_ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GATE = _load(HOOKS / "staging_gate.py", "staging_gate_sprachen_2681")
PFADE = _load(HOOKS / "_e2e_paths.py", "_e2e_paths_sprachen_2681")
BROWSER = _load(HOOKS / "e2e_browser_test.py", "e2e_browser_sprachen_2681")


def _git(args, cwd) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=True).stdout.strip()


def _repo(root: Path) -> str:
    _git(["init", "-q", "-b", "main"], root)
    _git(["config", "user.email", "t@example.com"], root)
    _git(["config", "user.name", "Tester"], root)
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n")
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "code"], root)
    return _git(["rev-parse", "HEAD"], root)


def _nachweis(root: Path, sha: str, **extra) -> Path:
    pfad = root / ".claude" / "e2e_verified" / f"{sha}.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    data = {"verified_commit": sha, "staging_verdict": "VERIFIED: alles gruen",
            "findings": [], "verified_at": datetime.now(timezone.utc).isoformat(),
            "scope": "backend", "environment": "staging", **extra}
    pfad.write_text(json.dumps(data))
    return pfad


@pytest.fixture
def repo(tmp_path, monkeypatch):
    sha = _repo(tmp_path)
    monkeypatch.setattr(GATE, "_shared_repo_dir", lambda: tmp_path)
    monkeypatch.setattr(GATE, "_verified_repo_dir", lambda: tmp_path)
    monkeypatch.setattr(GATE, "_head_sha", lambda: sha)
    monkeypatch.setattr(GATE, "_telegram_live_gate", lambda: 0)
    monkeypatch.setattr(GATE, "_frontend_browser_gate", lambda scope, checked=None: 0)
    monkeypatch.delenv("GZ_SKIP_E2E_GATE", raising=False)
    (tmp_path / ".claude").mkdir(exist_ok=True)
    (tmp_path / ".claude" / "findings.json").write_text("[]")  # neutraler Pfad
    return tmp_path, sha


def _findings(root: Path) -> Path:
    return root / ".claude" / "findings.json"


# --------------------------------------------------------------------------- reine Helfer
def test_parse_langs_und_vollstaendigkeit():
    assert PFADE.parse_langs("de,en") == ["de", "en"]
    assert PFADE.parse_langs(" en , de ") == ["en", "de"]
    assert PFADE.parse_langs("") == []
    with pytest.raises(ValueError):
        PFADE.parse_langs("de,fr")
    assert PFADE.langs_vollstaendig({"langs": ["de", "en"]}) is True
    assert PFADE.langs_vollstaendig({"langs": ["en", "de"]}) is True
    assert PFADE.langs_vollstaendig({"langs": ["de"]}) is False
    assert PFADE.langs_vollstaendig({"langs": "de,en"}) is False  # keine Liste
    assert PFADE.langs_vollstaendig({}) is False


# --------------------------------------------------------------------------- Schreibseite
@pytest.mark.parametrize("scope", ["backend", "frontend-only"])
def test_write_verdict_ohne_beide_sprachen_kein_artefakt(repo, scope, capsys):
    root, sha = repo
    ziel = root / "nachweis.json"
    for langs in ([], ["de"], ["en"]):
        rc = GATE.write_verdict("VERIFIED: ok", _findings(root), ziel, scope, langs=langs)
        assert rc == 1, f"Scope {scope}, langs={langs}: Artefakt haette verweigert werden muessen"
        assert not ziel.exists(), "ohne beide Sprachen darf KEIN Nachweis entstehen"
    assert "--langs de,en" in capsys.readouterr().err


@pytest.mark.parametrize("scope", ["backend", "frontend-only", "full-stack"])
def test_write_verdict_mit_beiden_sprachen_schreibt_langs(repo, scope):
    root, sha = repo
    ziel = root / "nachweis.json"
    rc = GATE.write_verdict("VERIFIED: ok", _findings(root), ziel, scope, langs=["de", "en"])
    assert rc == 0
    data = json.loads(ziel.read_text())
    assert data["langs"] == ["de", "en"]
    assert data["verified_commit"] == sha
    # Gegenprobe Lese-Seite: genau dieser Nachweis besteht das Gate.
    assert GATE.gate_check(ziel, scope) == 0


def test_write_verdict_docs_only_braucht_keine_sprachen(repo):
    root, _ = repo
    ziel = root / "nachweis.json"
    assert GATE.write_verdict("VERIFIED: doku", _findings(root), ziel, "docs-only") == 0
    assert ziel.exists()


def test_write_verdict_merge_behaelt_langs(repo, tmp_path):
    root, sha = repo
    ziel = root / "nachweis.json"
    assert GATE.write_verdict("VERIFIED: a", _findings(root), ziel, "backend", langs=["de", "en"]) == 0
    assert GATE.write_verdict("VERIFIED: b", _findings(root), ziel, "backend", langs=["en", "de"]) == 0
    assert PFADE.langs_vollstaendig(json.loads(ziel.read_text()))


def test_cli_write_verdict_langs_flag(tmp_path):
    """Die Kommandozeile reicht ``--langs`` durch; ohne Flag: Exit 1, kein Artefakt."""
    sha = _repo(tmp_path)
    hooks = tmp_path / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    for name in ("staging_gate.py", "_e2e_paths.py", "e2e_telegram_live.py"):
        (hooks / name).write_text((HOOKS / name).read_text())
    env = {**os.environ, "GZ_TELEGRAM_TEST_CHAT_ID": "12345", "OPENSPEC_ACTIVE_WORKFLOW": "t-2681"}
    ziel = tmp_path / "out.json"
    (tmp_path / "f.json").write_text("[]")
    basis = [sys.executable, str(hooks / "staging_gate.py"), "--write-verdict", "VERIFIED: ok",
             f"--e2e-path={ziel}", "--scope=backend", f"--findings-json={tmp_path / 'f.json'}"]
    ohne = subprocess.run(basis, cwd=tmp_path, env=env, capture_output=True, text=True)
    assert ohne.returncode == 1 and not ziel.exists(), ohne.stdout + ohne.stderr
    mit = subprocess.run(basis + ["--langs", "de,en"], cwd=tmp_path, env=env,
                         capture_output=True, text=True)
    assert mit.returncode == 0, mit.stdout + mit.stderr
    assert json.loads(ziel.read_text())["langs"] == ["de", "en"]
    assert json.loads(ziel.read_text())["verified_commit"] == sha


# --------------------------------------------------------------------------- Leseseite
@pytest.mark.parametrize("langs", [None, [], ["de"], ["en"]])
def test_gate_check_blockt_exakten_nachweis_ohne_langs(repo, langs, capsys):
    root, sha = repo
    extra = {} if langs is None else {"langs": langs}
    pfad = _nachweis(root, sha, **extra)
    assert GATE.gate_check(pfad, "backend") == 1
    assert "zweisprachig" in capsys.readouterr().err
    assert GATE.gate_check(None, "frontend-only") == 1  # Default-Pfad <sha>.json


def test_gate_check_laesst_vollstaendigen_nachweis_durch(repo):
    root, sha = repo
    pfad = _nachweis(root, sha, langs=["de", "en"])
    assert GATE.gate_check(pfad, "backend") == 0
    assert GATE.gate_check(None, "frontend-only") == 0


def test_gate_check_docs_only_unveraendert_offen(repo):
    root, sha = repo
    _nachweis(root, sha)  # ohne langs
    assert GATE.gate_check(None, "docs-only") == 0


def test_gate_check_ancestor_relaxierung_verlangt_langs(repo, monkeypatch):
    root, basis = repo
    (root / "docs").mkdir()
    (root / "docs" / "x.md").write_text("doku\n")
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "doku"], root)
    kopf = _git(["rev-parse", "HEAD"], root)
    monkeypatch.setattr(GATE, "_head_sha", lambda: kopf)
    pfad = _nachweis(root, basis)  # Vorfahre ohne langs
    assert GATE.gate_check(None, "backend") == 1, "Vorfahren-Nachweis ohne langs darf nicht relaxieren"
    pfad.unlink()
    _nachweis(root, basis, langs=["de", "en"])
    assert GATE.gate_check(None, "backend") == 0


# --------------------------------------------------------------------------- AC-8 Kern
class _CookieSpiegel(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        cookie = self.headers.get("Cookie", "")
        rumpf = f"<html><body><p id='c'>cookie[{cookie}]</p></body></html>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(rumpf)

    def log_message(self, *_a):
        pass


@pytest.mark.parametrize("lang", ["en", "de"])
def test_run_browser_test_setzt_gz_lang_cookie(lang, monkeypatch):
    """Echter Browser gegen einen lokalen Server, der seinen Cookie-Kopf spiegelt."""
    server = HTTPServer(("127.0.0.1", 0), _CookieSpiegel)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("GZ_SVELTE_BASE", f"http://127.0.0.1:{server.server_address[1]}")
        ok, meldung, _shot = BROWSER.run_browser_test("/", f"gz_lang={lang}", lang=lang)
        if not ok and ("Playwright" in meldung or "Executable" in meldung):
            pytest.skip(f"kein Browser verfuegbar: {meldung}")
        assert ok, meldung
        anderer = "de" if lang == "en" else "en"
        ok2, _m, _s = BROWSER.run_browser_test("/", f"gz_lang={anderer}", lang=lang)
        assert not ok2, "Cookie muss die GEWAEHLTE Sprache tragen"
    finally:
        server.shutdown()


# --------------------------------------------------------------------------- AC-7 (live)
@pytest.mark.staging
def test_prod_selftest_ohne_en_zugangsdaten(tmp_path):
    """Selftest mit vollstaendigem Nachweis (langs) und OHNE GZ_E2E_EN_* -> Exit 0."""
    from tests.tdd.conftest import PROD_SELFTEST, REPO_DIR, _make_e2e_verified

    pfad = _make_e2e_verified(tmp_path)
    data = json.loads(pfad.read_text())
    data["langs"] = ["de", "en"]
    pfad.write_text(json.dumps(data))
    env = {k: v for k, v in os.environ.items() if not k.startswith("GZ_E2E_EN_")}
    env.pop("GZ_ACTIVE_WORKFLOW", None)
    lauf = subprocess.run(["python3", str(PROD_SELFTEST), "--e2e-path", str(pfad),
                           "--workflow", "i18n-a2-2681-selftest"],
                          cwd=str(REPO_DIR), env=env, capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
