"""TDD RED fuer #2047 Scheibe 2 — Prod-Gate wirksam machen.

Prueflinge:

* ``scripts/ci_prod_gate.sh`` (Aufruf ``bash ci_prod_gate.sh <repo>``)
* ``.github/workflows/ci.yml`` — Job ``deploy`` (AC-7, YAML-Parse)

Alle Verhaltenstests laufen gegen ECHTE Wegwerf-Git-Repos (bare ``origin`` +
Haupt-Checkout + zweiter Klon als "andere Session"), echte Commits, echter
Skript-Aufruf per ``subprocess``. Nachweise entstehen ueber den echten Erzeuger
``staging_gate.py --write-verdict``. Keine Mocks — Spec
``docs/specs/modules/fix_2047_s2_prod_gate.md``.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci_prod_gate.sh"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
HOOKS_SRC = REPO_ROOT / ".claude" / "hooks"
GITIGNORE_SRC = REPO_ROOT / ".gitignore"

SIX_AMPEL_JOBS = {"test", "lint", "go-test", "frontend-test", "svelte-check", "e2e"}


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} in {repo} scheiterte (rc={proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc


def _clean_env() -> dict:
    """Umgebung ohne Notausgaenge — das Gate muss echt entscheiden."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GZ_")}
    env["GZ_ACTIVE_WORKFLOW"] = "ci-prod-gate-test"
    return env


def _run_gate(repo: Path) -> subprocess.CompletedProcess:
    assert SCRIPT.exists(), (
        f"Pruefling fehlt: {SCRIPT} — Spec docs/specs/modules/fix_2047_s2_prod_gate.md"
    )
    return subprocess.run(
        ["bash", str(SCRIPT), str(repo)], capture_output=True, text=True, env=_clean_env()
    )


def _gate_lines(proc: subprocess.CompletedProcess) -> list[str]:
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.startswith("PROD_GATE=")]


class Sandbox:
    """Bare origin, Haupt-Checkout (``checkout``, HEAD bleibt auf dem Live-Stand)
    und ein zweiter Klon (``session``), ueber den neue Commits auf origin/main landen."""

    def __init__(self, root: Path):
        self.origin = root / "origin.git"
        self.checkout = root / "checkout"
        self.session = root / "session"
        subprocess.run(
            ["git", "init", "--bare", "-b", "main", str(self.origin)],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "clone", str(self.origin), str(self.checkout)],
            capture_output=True, text=True, check=True,
        )
        for repo in (self.checkout,):
            self._identify(repo)
        shutil.copytree(
            HOOKS_SRC, self.checkout / ".claude" / "hooks",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.copy(GITIGNORE_SRC, self.checkout / ".gitignore")
        (self.checkout / "README.md").write_text("live stand\n", encoding="utf-8")
        (self.checkout / "src").mkdir()
        (self.checkout / "src" / "app.py").write_text("X = 0\n", encoding="utf-8")
        _git(self.checkout, "add", "-A")
        _git(self.checkout, "commit", "-m", "initial (live)")
        _git(self.checkout, "push", "-u", "origin", "main")
        subprocess.run(
            ["git", "clone", str(self.origin), str(self.session)],
            capture_output=True, text=True, check=True,
        )
        self._identify(self.session)

    @staticmethod
    def _identify(repo: Path) -> None:
        _git(repo, "config", "user.email", "prod-gate@test.invalid")
        _git(repo, "config", "user.name", "Prod Gate Test")

    def land(self, rel: str, text: str) -> str:
        """Commit in der Session-Kopie, Push nach origin/main; liefert die SHA."""
        _git(self.session, "pull", "-q", "origin", "main")
        target = self.session / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        _git(self.session, "add", "-A")
        _git(self.session, "commit", "-m", f"change {rel}")
        _git(self.session, "push", "-q", "origin", "main")
        return _git(self.session, "rev-parse", "HEAD").stdout.strip()

    def verify_session_head(self) -> str:
        """Echter Nachweis-Erzeuger im Session-Klon (HEAD = Zielstand), Datei wird
        in den Haupt-Checkout uebernommen (dort liegt ``.claude/e2e_verified/``)."""
        sha = _git(self.session, "rev-parse", "HEAD").stdout.strip()
        findings = self.session / "findings.json"
        findings.write_text(
            json.dumps([{"ac": "ROOT", "status": "PASS", "url": "/", "evidence": "ok"}]),
            encoding="utf-8",
        )
        proc = subprocess.run(
            ["python3", str(self.session / ".claude" / "hooks" / "staging_gate.py"),
             "--write-verdict", "VERIFIED: Test-Nachweis", "--findings-json", str(findings)],
            capture_output=True, text=True, env=_clean_env(), cwd=str(self.session),
        )
        assert proc.returncode == 0, f"write-verdict scheiterte: {proc.stdout}{proc.stderr}"
        proof = self.session / ".claude" / "e2e_verified" / f"{sha}.json"
        assert proof.exists()
        dest = self.checkout / ".claude" / "e2e_verified"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy(proof, dest / proof.name)
        return sha

    def proofs(self) -> list[str]:
        d = self.checkout / ".claude" / "e2e_verified"
        return sorted(p.name for p in d.iterdir()) if d.exists() else []


@pytest.fixture()
def sb():
    root = Path(tempfile.mkdtemp(prefix="ci-prod-gate-"))
    try:
        yield Sandbox(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ohne_nachweis_ist_das_gate_zu_und_die_ci_erzeugt_keinen(sb: Sandbox):
    """AC-1: Code-Stand auf origin/main ohne Nachweis -> closed, Nachweis-Dir leer."""
    sb.land("src/app.py", "X = 1\n")
    assert sb.proofs() == []

    proc = _run_gate(sb.checkout)

    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert _gate_lines(proc) == ["PROD_GATE=closed"], proc.stdout
    assert sb.proofs() == [], "die CI darf keinen Nachweis erzeugen"


def test_echter_nachweis_fuer_den_zielstand_oeffnet_das_gate(sb: Sandbox):
    """AC-2: gueltiger, vom echten Erzeuger geschriebener Nachweis -> open."""
    sb.land("src/app.py", "X = 2\n")
    sha = sb.verify_session_head()
    assert sb.proofs() == [f"{sha}.json"]

    proc = _run_gate(sb.checkout)

    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert _gate_lines(proc) == ["PROD_GATE=open"], proc.stdout + proc.stderr


def test_nachweis_fuer_aelteren_stand_genuegt_nicht_fuer_neueren_code_commit(sb: Sandbox):
    """AC-3: Nachweis fuer B, danach Code-Commit C auf origin/main -> closed."""
    sb.land("src/app.py", "X = 3\n")
    sb.verify_session_head()
    sb.land("src/app.py", "X = 4\n")

    proc = _run_gate(sb.checkout)

    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert _gate_lines(proc) == ["PROD_GATE=closed"], proc.stdout + proc.stderr


def test_gate_aendert_weder_head_noch_arbeitsbaum_noch_status(sb: Sandbox):
    """AC-4: uncommittete getrackte Aenderung + zurueckliegender HEAD bleiben unberuehrt."""
    sb.land("src/app.py", "X = 5\n")
    (sb.checkout / "README.md").write_text("WIP einer parallelen Session\n", encoding="utf-8")

    def snapshot() -> dict:
        return {
            "head": _git(sb.checkout, "rev-parse", "HEAD").stdout,
            "status": _git(sb.checkout, "status", "--porcelain", "--untracked-files=all").stdout,
            "diff": _git(sb.checkout, "diff").stdout,
            "stash": _git(sb.checkout, "stash", "list").stdout,
            "tags": _git(sb.checkout, "tag", "--list").stdout,
            "readme": (sb.checkout / "README.md").read_text(encoding="utf-8"),
            "app": (sb.checkout / "src" / "app.py").read_text(encoding="utf-8"),
        }

    before = snapshot()
    assert before["status"].strip(), "Vorbedingung: Arbeitsbaum muss schmutzig sein"

    proc = _run_gate(sb.checkout)

    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert _gate_lines(proc) == ["PROD_GATE=closed"]
    assert snapshot() == before


def test_fetch_fehler_gibt_exit_ungleich_null_ohne_gate_zeile(sb: Sandbox):
    """AC-5: Remote nicht erreichbar -> Exit != 0, keine PROD_GATE=-Zeile."""
    sb.land("src/app.py", "X = 6\n")
    _git(sb.checkout, "remote", "set-url", "origin", str(sb.origin.parent / "gibt-es-nicht.git"))

    proc = _run_gate(sb.checkout)

    assert proc.returncode != 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert "PROD_GATE=" not in proc.stdout
    assert "PROD_GATE=" not in proc.stderr


def test_reiner_doku_merge_oeffnet_das_gate_ohne_nachweis(sb: Sandbox):
    """AC-6: nur .md/docs geaendert -> open, auch ohne Nachweis."""
    sb.land("README.md", "neue Doku\n")
    sb.land("docs/notiz.md", "mehr Doku\n")
    assert sb.proofs() == []

    proc = _run_gate(sb.checkout)

    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert _gate_lines(proc) == ["PROD_GATE=open"], proc.stdout + proc.stderr
    assert sb.proofs() == []


def _run_gate_env(repo: Path, extra: dict) -> subprocess.CompletedProcess:
    env = _clean_env()
    env.update(extra)
    return subprocess.run(
        ["bash", str(SCRIPT), str(repo)], capture_output=True, text=True, env=env
    )


def _checkout_to_origin_main(sb: Sandbox) -> None:
    """Server-Checkout steht bereits auf origin/main (HEAD == Ziel, leerer Diff)."""
    _git(sb.checkout, "pull", "-q", "origin", "main")
    assert (
        _git(sb.checkout, "rev-parse", "HEAD").stdout
        == _git(sb.checkout, "rev-parse", "origin/main").stdout
    )


def test_head_gleich_origin_main_ohne_nachweis_ist_das_gate_zu(sb: Sandbox):
    """F001: leerer Diff (HEAD == origin/main) darf nicht als docs-only durchwinken."""
    sb.land("src/app.py", "X = 7\n")
    _checkout_to_origin_main(sb)
    assert sb.proofs() == []

    proc = _run_gate(sb.checkout)

    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert _gate_lines(proc) == ["PROD_GATE=closed"], proc.stdout + proc.stderr


def test_head_gleich_origin_main_mit_echtem_nachweis_oeffnet_das_gate(sb: Sandbox):
    """F001: derselbe Zustand mit echtem Nachweis fuer diese SHA -> open."""
    sb.land("src/app.py", "X = 8\n")
    sb.verify_session_head()
    _checkout_to_origin_main(sb)

    proc = _run_gate(sb.checkout)

    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert _gate_lines(proc) == ["PROD_GATE=open"], proc.stdout + proc.stderr


def test_geerbtes_skip_flag_wird_neutralisiert(sb: Sandbox):
    """F002: GZ_SKIP_E2E_GATE=1 in der Umgebung darf das Gate nicht oeffnen."""
    sb.land("src/app.py", "X = 9\n")

    proc = _run_gate_env(sb.checkout, {"GZ_SKIP_E2E_GATE": "1"})

    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert _gate_lines(proc) == ["PROD_GATE=closed"], proc.stdout + proc.stderr


def test_ssh_befehl_fetcht_vor_dem_skript_bezug():
    """F003 — # doc-compliance-test: Fetch muss VOR `git show origin/main:` stehen."""
    run = _step(_deploy_job(), "Prod-Gate pruefen")["run"]
    fetch = run.find("git fetch origin")
    show = run.find("git show origin/main:scripts/ci_prod_gate.sh")
    assert fetch != -1 and show != -1, run
    assert fetch < show
    between = run[fetch:show]
    assert "&&" in between and ";" not in between.replace("\\;", ""), between


# --- AC-7 / statische Teile von AC-8: ci.yml als geparste Struktur -----------------


def _deploy_job() -> dict:
    return yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))["jobs"]["deploy"]


def _step(job: dict, name_part: str) -> dict:
    hits = [s for s in job["steps"] if name_part in s.get("name", "")]
    assert len(hits) == 1, f"Schritt mit {name_part!r}: {len(hits)} Treffer"
    return hits[0]


def test_deploy_haengt_an_allen_sechs_ampel_jobs():
    """AC-7a — # doc-compliance-test (Konfiguration ist hier der Pruefling)."""
    needs = _deploy_job()["needs"]
    assert isinstance(needs, list)
    assert set(needs) == SIX_AMPEL_JOBS and len(needs) == 6, needs


def test_deploy_schreibt_keinen_nachweis_und_resettet_nicht():
    """AC-7b — # doc-compliance-test."""
    for step in _deploy_job()["steps"]:
        run = step.get("run", "")
        assert "--write-verdict" not in run, f"{step.get('name')}: schreibt Nachweis"
        assert "git reset" not in run, f"{step.get('name')}: git reset"


def test_prod_deploy_und_erfolgsmeldung_nur_bei_offenem_gate():
    """AC-7c + AC-8 (statisch) — # doc-compliance-test."""
    job = _deploy_job()
    gate = _step(job, "Prod-Gate pruefen")
    assert gate.get("id") == "gate"
    assert "ci_prod_gate.sh" in gate["run"]
    assert "PROD_GATE" in gate["run"]

    cond = "steps.gate.outputs.open == 'true'"
    assert cond in _step(job, "Deploy zu Produktion via SSH").get("if", "")
    ok = _step(job, "Deploy erfolgreich").get("if", "")
    assert "success()" in ok and cond in ok

    skipped = _step(job, "Prod-Deploy uebersprungen")
    assert "steps.gate.outputs.open != 'true'" in skipped.get("if", "")
    assert "/70-deploy" in skipped["run"] and "GITHUB_STEP_SUMMARY" in skipped["run"]
    assert "github.sha" in skipped["run"] or "GITHUB_SHA" in skipped["run"] or "SHA" in str(skipped.get("env", ""))


# --- Schrittlogik der CI-Schritte real ausgefuehrt (bash), ``${{ }}`` ersetzt ------


def _run_step(step: dict, workdir: Path, extra_env: dict, ssh_script: str | None = None):
    """Fuehrt ``run`` eines Workflow-Schritts mit bash -e aus. ``ssh`` ist ein kleines
    Transport-Shim (Fake-Binary im PATH, das Ausgabe/Exit-Code vorgibt) — der
    Gate-Entscheid selbst ist oben gegen echte Repos getestet; hier geht es um die
    Weiterverarbeitung der Antwort im Schritt (outputs.open / Rot bei fehlender Zeile)."""
    import re

    script = re.sub(r"\$\{\{[^}]*\}\}", "x", step["run"])
    bin_dir = workdir / "bin"
    bin_dir.mkdir(exist_ok=True)
    if ssh_script is not None:
        shim = bin_dir / "ssh"
        shim.write_text("#!/usr/bin/env bash\n" + ssh_script + "\n", encoding="utf-8")
        shim.chmod(0o755)
    out_file = workdir / "gh_output"
    sum_file = workdir / "gh_summary"
    out_file.write_text("", encoding="utf-8")
    sum_file.write_text("", encoding="utf-8")
    env = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "HOME": str(workdir),
        "GITHUB_OUTPUT": str(out_file),
        "GITHUB_STEP_SUMMARY": str(sum_file),
        **extra_env,
    }
    proc = subprocess.run(
        ["bash", "-e", "-c", script], capture_output=True, text=True, env=env, cwd=str(workdir)
    )
    return proc, out_file.read_text(encoding="utf-8"), sum_file.read_text(encoding="utf-8")


@pytest.fixture()
def stepdir():
    path = Path(tempfile.mkdtemp(prefix="ci-prod-gate-step-"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.mark.parametrize(
    "ssh_script,expect_rc0,expect_output",
    [
        ('echo "[staging-gate] Meldung"; echo "PROD_GATE=open"', True, "open=true"),
        ('echo "PROD_GATE=closed"', True, "open=false"),
        ('echo "kein Gate-Satz"; exit 0', False, ""),
        ('echo "PROD_GATE=open"; exit 3', False, ""),
        ("exit 255", False, ""),
    ],
)
def test_gate_schritt_setzt_output_und_wird_rot_ohne_entscheidung(
    stepdir: Path, ssh_script: str, expect_rc0: bool, expect_output: str
):
    """AC-5/AC-7 (Schrittlogik): fehlende Entscheidung oder ssh-Fehler -> Schritt rot,
    kein ``open=``-Output; sonst open=true|false."""
    gate = _step(_deploy_job(), "Prod-Gate pruefen")
    proc, out, _ = _run_step(gate, stepdir, {}, ssh_script)
    assert (proc.returncode == 0) is expect_rc0, proc.stdout + proc.stderr
    assert out.strip() == expect_output


def test_uebersprungen_schritt_nennt_sha_und_70_deploy_in_der_job_summary(stepdir: Path):
    """AC-8 (Inhalt der Job-Summary, Schritt real ausgefuehrt)."""
    skipped = _step(_deploy_job(), "Prod-Deploy uebersprungen")
    sha = "abc123def4567890abc123def4567890abc123de"
    proc, _, summary = _run_step(skipped, stepdir, {"SHA": sha})
    assert proc.returncode == 0, proc.stderr
    assert sha in summary and "/70-deploy Schritt 4" in summary
    assert "::notice::" in proc.stdout
