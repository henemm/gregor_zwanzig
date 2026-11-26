"""TDD RED fuer #3289 — Prod-Deploy per Pull, Nachweis als Git-Note.

Spec: ``docs/specs/modules/prod_pull_deploy.md`` (AC-1, AC-2, AC-8, AC-9).
Der Timer-Teil (AC-3..AC-7) ist im Repo henemm-infra getestet
(``tests/test_pull_deploy_gregor_prod.py``).

Prueflinge:

* ``.claude/hooks/staging_gate.py --write-verdict`` — veroeffentlicht den Nachweis
  zusaetzlich als Git-Note unter ``refs/notes/e2e-verified`` auf ``origin``.
  Nur fuer Tests abschaltbar: ``GZ_E2E_PUBLISH=0``.
* ``scripts/e2e_nachweis_holen.py <repo>`` — holt die Notes-Ref und legt passende
  Notes als ``.claude/e2e_verified/<sha>.json`` ab (fail-closed).
* ``scripts/ci_prod_gate.sh <repo>`` — ruft vor dem Gate das Hol-Skript auf.
* ``.claude/commands/70-deploy.md`` / ``.claude/commands/e2e-verify.md`` (Doku-Anteil).

Alle Verhaltenstests laufen gegen ECHTE Wegwerf-Git-Repos: bare ``origin`` in
einem tmp-Verzeichnis, ein Server-Checkout (``server``, HEAD bleibt auf dem
Live-Stand) und ein Sitzungs-Klon (``session``, dort entstehen Commits und
Nachweise). Nachweise entstehen ueber den echten Erzeuger
``staging_gate.py --write-verdict``. Kein Mock, kein patch, kein GitHub.
"""

from __future__ import annotations

import json
import re
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_SRC = REPO_ROOT / ".claude" / "hooks"
GITIGNORE_SRC = REPO_ROOT / ".gitignore"
HOLEN = REPO_ROOT / "scripts" / "e2e_nachweis_holen.py"
CI_GATE = REPO_ROOT / "scripts" / "ci_prod_gate.sh"
CMD_70 = REPO_ROOT / ".claude" / "commands" / "70-deploy.md"
CMD_E2E = REPO_ROOT / ".claude" / "commands" / "e2e-verify.md"

NOTES_REF = "refs/notes/e2e-verified"


# --- Hilfen -------------------------------------------------------------------


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} in {repo} scheiterte (rc={proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc


def _clean_env(**extra: str) -> dict:
    """Umgebung ohne geerbte GZ_-Schalter (insbesondere ohne GZ_E2E_PUBLISH und
    GZ_SKIP_E2E_GATE) — das Verhalten muss der Standardfall sein."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GZ_")}
    env.pop("OPENSPEC_ACTIVE_WORKFLOW", None)
    env["GZ_ACTIVE_WORKFLOW"] = "nachweis-transport-test"
    env.update(extra)
    return env


def _identify(repo: Path) -> None:
    _git(repo, "config", "user.email", "transport@test.invalid")
    _git(repo, "config", "user.name", "Transport Test")


class Welt:
    """Bare ``origin`` + Server-Checkout + Sitzungs-Klon."""

    def __init__(self, root: Path):
        self.root = root
        self.origin = root / "origin.git"
        self.server = root / "server"
        self.session = root / "session"
        subprocess.run(["git", "init", "--bare", "-b", "main", str(self.origin)],
                       capture_output=True, text=True, check=True)
        subprocess.run(["git", "clone", str(self.origin), str(self.server)],
                       capture_output=True, text=True, check=True)
        _identify(self.server)
        shutil.copytree(HOOKS_SRC, self.server / ".claude" / "hooks",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(GITIGNORE_SRC, self.server / ".gitignore")
        (self.server / "scripts").mkdir()
        shutil.copy(CI_GATE, self.server / "scripts" / "ci_prod_gate.sh")
        if HOLEN.exists():
            shutil.copy(HOLEN, self.server / "scripts" / "e2e_nachweis_holen.py")
        (self.server / "README.md").write_text("live stand\n", encoding="utf-8")
        (self.server / "src").mkdir()
        (self.server / "src" / "app.py").write_text("X = 0\n", encoding="utf-8")
        _git(self.server, "add", "-A")
        _git(self.server, "commit", "-m", "initial (live)")
        _git(self.server, "push", "-u", "origin", "main")
        subprocess.run(["git", "clone", str(self.origin), str(self.session)],
                       capture_output=True, text=True, check=True)
        _identify(self.session)

    def clone(self, name: str) -> Path:
        path = self.root / name
        subprocess.run(["git", "clone", str(self.origin), str(path)],
                       capture_output=True, text=True, check=True)
        _identify(path)
        return path

    def land(self, rel: str, text: str, repo: Path | None = None) -> str:
        """Commit im Sitzungs-Klon (oder ``repo``), Push nach origin/main; liefert SHA."""
        repo = repo or self.session
        _git(repo, "pull", "-q", "--no-rebase", "origin", "main")
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", f"change {rel}")
        _git(repo, "push", "-q", "origin", "main")
        return _git(repo, "rev-parse", "HEAD").stdout.strip()

    def write_verdict(self, repo: Path | None = None, **env: str) -> subprocess.CompletedProcess:
        """Echter Nachweis-Erzeuger im Klon ``repo`` (HEAD = Zielstand)."""
        repo = repo or self.session
        findings = self.root / f"findings-{repo.name}.json"
        findings.write_text(
            json.dumps([{"ac": "ROOT", "status": "PASS", "url": "/", "evidence": "ok"}]),
            encoding="utf-8",
        )
        return subprocess.run(
            ["python3", str(repo / ".claude" / "hooks" / "staging_gate.py"),
             "--write-verdict", "VERIFIED: Test-Nachweis", "--langs", "de,en",
             "--findings-json", str(findings)],
            capture_output=True, text=True, env=_clean_env(**env), cwd=str(repo),
        )

    def local_proof(self, sha: str, repo: Path | None = None) -> dict:
        repo = repo or self.session
        path = repo / ".claude" / "e2e_verified" / f"{sha}.json"
        assert path.exists(), f"lokaler Nachweis fehlt: {path}"
        return json.loads(path.read_text(encoding="utf-8"))

    def remote_note(self, sha: str) -> str | None:
        """Note vom Remote lesen — in einem frischen Klon, der nur origin kennt."""
        reader = self.root / "reader"
        if reader.exists():
            shutil.rmtree(reader)
        subprocess.run(["git", "clone", "-q", str(self.origin), str(reader)],
                       capture_output=True, text=True, check=True)
        fetched = _git(reader, "fetch", "-q", "origin", f"+{NOTES_REF}:{NOTES_REF}", check=False)
        if fetched.returncode != 0:
            return None
        shown = _git(reader, "notes", "--ref", "e2e-verified", "show", sha, check=False)
        return shown.stdout if shown.returncode == 0 else None

    def push_note(self, sha: str, content: str, repo: Path | None = None) -> None:
        """Note direkt anlegen und pushen (Test-Aufbau fuer AC-2, unabhaengig von AC-1)."""
        repo = repo or self.session
        _git(repo, "fetch", "-q", "origin", f"+{NOTES_REF}:{NOTES_REF}", check=False)
        note_file = self.root / f"note-{sha[:8]}.txt"
        note_file.write_text(content, encoding="utf-8")
        _git(repo, "notes", "--ref", "e2e-verified", "add", "-f", "-F", str(note_file), sha)
        _git(repo, "push", "-q", "origin", NOTES_REF)

    def server_proofs(self) -> list[str]:
        d = self.server / ".claude" / "e2e_verified"
        return sorted(p.name for p in d.iterdir()) if d.exists() else []


@pytest.fixture()
def welt():
    root = Path(tempfile.mkdtemp(prefix="e2e-nachweis-transport-"))
    try:
        yield Welt(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _real_payload(welt: Welt, sha: str) -> dict:
    """Echter Nachweis-Inhalt fuer ``sha`` (Erzeuger mit abgeschalteter
    Veroeffentlichung, damit AC-2 unabhaengig von AC-1 aufgebaut wird)."""
    proc = welt.write_verdict(GZ_E2E_PUBLISH="0")
    assert proc.returncode == 0, f"write-verdict (ohne Publish) scheiterte: {proc.stdout}{proc.stderr}"
    return welt.local_proof(sha)


def _run_holen(repo: Path) -> subprocess.CompletedProcess:
    assert HOLEN.exists(), (
        f"Pruefling fehlt: {HOLEN} — Spec docs/specs/modules/prod_pull_deploy.md (AC-2)"
    )
    return subprocess.run(["python3", str(HOLEN), str(repo)],
                          capture_output=True, text=True, env=_clean_env())


def _run_ci_gate(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(CI_GATE), str(repo)],
                          capture_output=True, text=True, env=_clean_env())


def _gate_lines(proc: subprocess.CompletedProcess) -> list[str]:
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.startswith("PROD_GATE=")]


def _gate_check(repo: Path, expected: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(repo / ".claude" / "hooks" / "staging_gate.py"),
         "--check", "--expected-commit", expected],
        capture_output=True, text=True, env=_clean_env(), cwd=str(repo),
    )


# --- AC-1: Veroeffentlichung als Git-Note ------------------------------------


def test_ac1_write_verdict_legt_vollen_nachweis_als_note_auf_dem_remote_ab(welt: Welt):
    sha = welt.land("src/app.py", "X = 1\n")

    proc = welt.write_verdict()

    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    local = welt.local_proof(sha)
    note = welt.remote_note(sha)
    assert note is not None, (
        f"keine Note {NOTES_REF} fuer {sha[:8]} auf origin — write-verdict muss "
        "den Nachweis veroeffentlichen"
    )
    assert json.loads(note) == local, "Note muss exakt den vollen Nachweis tragen"
    assert local["verified_commit"] == sha


def test_ac1_abgelehnter_push_endet_mit_exit_ungleich_null_und_meldung(welt: Welt):
    sha = welt.land("src/app.py", "X = 2\n")
    hook = welt.origin / "hooks" / "pre-receive"
    hook.write_text(
        "#!/bin/sh\n"
        "while read old new ref; do\n"
        "  case \"$ref\" in refs/notes/*) echo 'notes abgelehnt' >&2; exit 1;; esac\n"
        "done\nexit 0\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)

    proc = welt.write_verdict()

    out = (proc.stdout + proc.stderr).lower()
    assert proc.returncode != 0, (
        f"Veroeffentlichung abgelehnt, aber Exit 0 — die Sitzung glaubte sonst, "
        f"Prod werde ausgeliefert. stdout={proc.stdout} stderr={proc.stderr}"
    )
    assert "nachweis" in out and ("veröffentlich" in out or "veroeffentlich" in out), (
        f"klare Meldung fehlt (erwartet: Nachweis ... nicht veroeffentlicht): {proc.stdout}{proc.stderr}"
    )
    assert welt.remote_note(sha) is None


def test_ac1_ohne_erreichbaren_remote_scheitert_die_veroeffentlichung_fail_closed(welt: Welt):
    welt.land("src/app.py", "X = 3\n")
    _git(welt.session, "remote", "set-url", "origin", str(welt.root / "gibt-es-nicht.git"))

    proc = welt.write_verdict()

    assert proc.returncode != 0, f"stdout={proc.stdout} stderr={proc.stderr}"


def test_ac1_publish_schalter_null_schreibt_nur_lokal(welt: Welt):
    """``GZ_E2E_PUBLISH=0`` (nur fuer Tests): lokal schreiben, nichts veroeffentlichen."""
    sha = welt.land("src/app.py", "X = 4\n")
    _git(welt.session, "remote", "set-url", "origin", str(welt.root / "gibt-es-nicht.git"))

    proc = welt.write_verdict(GZ_E2E_PUBLISH="0")

    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert welt.local_proof(sha)["verified_commit"] == sha


def test_ac1_zweite_sitzung_ueberschreibt_fremde_note_nicht(welt: Welt):
    """Notes-Push-Konflikt: Sitzung B hat die Notes-Ref nie geholt und veroeffentlicht
    nach Sitzung A. Beide Notes muessen danach auf dem Remote liegen (Fetch + Merge
    statt Force-Push)."""
    other = welt.clone("session_b")
    sha_a = welt.land("src/app.py", "X = 5\n")
    proc_a = welt.write_verdict()
    assert proc_a.returncode == 0, proc_a.stdout + proc_a.stderr

    sha_b = welt.land("src/other.py", "Y = 1\n", repo=other)
    proc_b = welt.write_verdict(repo=other)
    assert proc_b.returncode == 0, proc_b.stdout + proc_b.stderr

    note_a = welt.remote_note(sha_a)
    note_b = welt.remote_note(sha_b)
    assert note_a is not None and json.loads(note_a)["verified_commit"] == sha_a
    assert note_b is not None and json.loads(note_b)["verified_commit"] == sha_b


def test_ac1_wettlauf_fremde_note_zwischen_holen_und_push_bleibt_erhalten(welt: Welt):
    """Adversary F002+F003: Zwischen dem Holen der Notes-Ref und dem Push legt eine
    andere Sitzung eine Note fuer einen ANDEREN Commit auf origin ab. Der erste
    Push muss daran scheitern (kein Force), der zweite Versuch holt neu und geht
    durch: Exit 0, eigene Note da UND die fremde Note bleibt erhalten.

    Ausgeloest wird die fremde Note durch einen echten ``reference-transaction``-Hook
    im Sitzungs-Klon: beim ersten Anlegen der Hilfs-Ref (Note anlegen; Loeschen zaehlt
    nicht) pusht er einmalig aus einem dritten Klon eine fremde Note nach origin. Fangen soll
    das sowohl einen Force-Push (fremde Note waere weg) als auch nur einen
    einzigen Versuch (Exit != 0)."""
    other = welt.clone("session_fremd")
    fremd_sha = welt.land("src/fremd.py", "F = 1\n", repo=other)
    fremd_text = json.dumps({"verified_commit": fremd_sha, "fremd": True})
    fremd_file = welt.root / "fremd-note.json"
    fremd_file.write_text(fremd_text, encoding="utf-8")

    sha = welt.land("src/app.py", "X = 80\n")
    marker = welt.root / "fremde-note-gepusht"
    hook = welt.session / ".git" / "hooks" / "reference-transaction"
    hook.write_text(
        "#!/bin/sh\n"
        "[ \"$1\" = committed ] || exit 0\n"
        f"[ -e '{marker}' ] && exit 0\n"
        "treffer=0\n"
        "while read old new ref; do\n"
        "  case \"$new\" in *[!0]*) ;; *) continue;; esac\n"
        "  case \"$ref\" in refs/notes/e2e-verified-publish-*) treffer=1;; esac\n"
        "done\n"
        "[ \"$treffer\" = 1 ] || exit 0\n"
        f": > '{marker}'\n"
        "unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_COMMON_DIR\n"
        f"git -C '{other}' notes --ref e2e-verified add -f -F '{fremd_file}' {fremd_sha} >/dev/null 2>&1\n"
        f"git -C '{other}' push -q origin {NOTES_REF} >/dev/null 2>&1\n"
        "exit 0\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)

    proc = welt.write_verdict()

    assert marker.exists(), "Test-Aufbau: der Hook hat die fremde Note nicht ausgeloest"
    assert proc.returncode == 0, (
        f"zweiter Versuch nach abgelehntem Push muss gelingen: stdout={proc.stdout} stderr={proc.stderr}"
    )
    fremd = welt.remote_note(fremd_sha)
    assert fremd is not None and json.loads(fremd) == json.loads(fremd_text), (
        "fremde Note eines anderen Commits wurde ueberschrieben (Force-Push?)"
    )
    note = welt.remote_note(sha)
    assert note is not None and json.loads(note) == welt.local_proof(sha)
    assert "Versuch 1/" in proc.stdout + proc.stderr, (
        f"der erste Push haette wegen der fremden Note scheitern muessen (kein Force): {proc.stdout}{proc.stderr}"
    )


def test_publish_ist_in_gewoehnlichen_tests_abgeschaltet():
    """Adversary F004: Sicherheitsnetz aus tests/conftest.py — kein Test darf
    versehentlich nach GitHub veroeffentlichen."""
    assert os.environ.get("GZ_E2E_PUBLISH") == "0"


# --- AC-2: Holen, fail-closed, Gate unveraendert -----------------------------


def test_ac2_nur_passende_notes_werden_dateien(welt: Welt):
    c1 = welt.land("src/app.py", "X = 10\n")
    payload = _real_payload(welt, c1)
    welt.push_note(c1, json.dumps(payload, indent=2))

    c2 = welt.land("src/app.py", "X = 11\n")
    falsch = dict(payload)  # verified_commit zeigt auf c1, haengt aber an c2
    welt.push_note(c2, json.dumps(falsch, indent=2))

    c3 = welt.land("src/app.py", "X = 12\n")
    ohne = {k: v for k, v in payload.items() if k != "verified_commit"}
    welt.push_note(c3, json.dumps(ohne, indent=2))

    c4 = welt.land("src/app.py", "X = 13\n")
    welt.push_note(c4, "kein json {")

    head_vorher = _git(welt.server, "rev-parse", "HEAD").stdout
    status_vorher = _git(welt.server, "status", "--porcelain").stdout

    proc = _run_holen(welt.server)

    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert welt.server_proofs() == [f"{c1}.json"], (
        f"nur die passende Note darf Datei werden (c2..c4 fail-closed): {welt.server_proofs()}"
    )
    written = json.loads(
        (welt.server / ".claude" / "e2e_verified" / f"{c1}.json").read_text(encoding="utf-8")
    )
    assert written == payload
    assert _git(welt.server, "rev-parse", "HEAD").stdout == head_vorher
    assert _git(welt.server, "status", "--porcelain").stdout == status_vorher


def test_ac2_ohne_notes_ref_auf_remote_exit_null_und_keine_datei(welt: Welt):
    welt.land("src/app.py", "X = 20\n")

    proc = _run_holen(welt.server)

    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert welt.server_proofs() == []


def test_ac2_bestehende_gleiche_datei_bleibt_unveraendert(welt: Welt):
    c1 = welt.land("src/app.py", "X = 21\n")
    payload = _real_payload(welt, c1)
    text = json.dumps(payload, indent=2)
    welt.push_note(c1, text)
    dest = welt.server / ".claude" / "e2e_verified"
    dest.mkdir(parents=True, exist_ok=True)
    existing = dest / f"{c1}.json"
    existing.write_text(text, encoding="utf-8")
    os.utime(existing, ns=(1_000_000_000_000_000_000, 1_000_000_000_000_000_000))
    mtime_vorher = existing.stat().st_mtime_ns

    proc = _run_holen(welt.server)

    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert existing.stat().st_mtime_ns == mtime_vorher, "gleiche Datei darf nicht neu geschrieben werden"
    assert json.loads(existing.read_text(encoding="utf-8")) == payload


def test_ac2_gate_check_bewertet_geholte_notes_wie_lokale_nachweise(welt: Welt):
    """Commit mit passender Note -> Gate offen; Code-Nachfolger mit Note fuer einen
    fremden Commit -> zu (fail-closed, keine Datei)."""
    c1 = welt.land("src/app.py", "X = 30\n")
    payload = _real_payload(welt, c1)
    welt.push_note(c1, json.dumps(payload, indent=2))
    c2 = welt.land("src/app.py", "X = 31\n")
    welt.push_note(c2, json.dumps(payload, indent=2))  # verified_commit = c1 -> passt nicht

    proc = _run_holen(welt.server)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    _git(welt.server, "fetch", "-q", "origin")

    ok_c1 = _gate_check(welt.server, c1)
    zu_c2 = _gate_check(welt.server, c2)
    assert ok_c1.returncode == 0, f"c1 mit passender Note muss bestehen: {ok_c1.stdout}{ok_c1.stderr}"
    assert zu_c2.returncode != 0, "c2 (Code ueber c1, Note mit fremdem verified_commit) muss blocken"


def test_ac2_vorfahren_regel_mit_geholter_note_und_doku_nachfolger(welt: Welt):
    c1 = welt.land("src/app.py", "X = 40\n")
    payload = _real_payload(welt, c1)
    welt.push_note(c1, json.dumps(payload, indent=2))
    d = welt.land("docs/notiz.md", "nur doku\n")

    proc = _run_holen(welt.server)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    _git(welt.server, "fetch", "-q", "origin")

    ok_d = _gate_check(welt.server, d)
    assert ok_d.returncode == 0, (
        f"Doku-Nachfolger eines per Note belegten Commits muss ueber die "
        f"Vorfahren-Regel bestehen: {ok_d.stdout}{ok_d.stderr}"
    )


def test_ac2_ci_prod_gate_holt_die_note_und_oeffnet(welt: Welt):
    """Nur eine Note auf origin (keine lokale Datei auf dem Server) -> ci_prod_gate.sh
    holt sie vor dem Gate und meldet PROD_GATE=open."""
    c1 = welt.land("src/app.py", "X = 50\n")
    payload = _real_payload(welt, c1)
    welt.push_note(c1, json.dumps(payload, indent=2))
    assert welt.server_proofs() == []

    proc = _run_ci_gate(welt.server)

    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert _gate_lines(proc) == ["PROD_GATE=open"], proc.stdout + proc.stderr
    assert welt.server_proofs() == [f"{c1}.json"]


def test_ac2_ci_prod_gate_bleibt_zu_bei_note_mit_fremdem_commit(welt: Welt):
    c1 = welt.land("src/app.py", "X = 60\n")
    payload = _real_payload(welt, c1)
    c2 = welt.land("src/app.py", "X = 61\n")
    welt.push_note(c2, json.dumps(payload, indent=2))  # verified_commit = c1

    proc = _run_ci_gate(welt.server)

    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert _gate_lines(proc) == ["PROD_GATE=closed"], proc.stdout + proc.stderr
    assert welt.server_proofs() == []


def test_ac1_ac2_ende_zu_ende_sitzung_attestiert_server_gate_oeffnet(welt: Welt):
    """Sitzung ausserhalb des Servers: write-verdict veroeffentlicht, der Server
    (ohne lokale Datei) sieht den Nachweis ueber ci_prod_gate.sh."""
    sha = welt.land("src/app.py", "X = 70\n")
    proc = welt.write_verdict()
    assert proc.returncode == 0, proc.stdout + proc.stderr

    gate = _run_ci_gate(welt.server)

    assert _gate_lines(gate) == ["PROD_GATE=open"], gate.stdout + gate.stderr
    assert welt.server_proofs() == [f"{sha}.json"]


# --- AC-8 / AC-9: Befehlsbeschreibungen (Doku-Anteil) -------------------------


def _abschnitt_ausserhalb(text: str) -> str:
    """Abschnitt ab der Ueberschrift mit 'ausserhalb/außerhalb des Servers' bis zur
    naechsten Ueberschrift gleicher oder hoeherer Ebene."""
    lines = text.splitlines()
    start = level = None
    for i, line in enumerate(lines):
        low = line.lower()
        if line.startswith("#") and ("außerhalb des servers" in low or "ausserhalb des servers" in low):
            start, level = i, len(line) - len(line.lstrip("#"))
            break
    assert start is not None, "Abschnitt 'außerhalb des Servers' fehlt"
    out = [lines[start]]
    for line in lines[start + 1:]:
        if line.startswith("#"):
            lvl = len(line) - len(line.lstrip("#"))
            if lvl <= level and not line.startswith("#!"):
                break
        out.append(line)
    return "\n".join(out)


def test_ac8_70_deploy_ausserhalb_wartet_auf_status_statt_selbst_zu_deployen():
    """# doc-compliance-test — AC-8: verbindliche Warte-Reihenfolge."""
    sec = _abschnitt_ausserhalb(CMD_70.read_text(encoding="utf-8"))
    low = sec.lower()
    assert "deploy/prod" in sec, sec
    assert "gh api repos/henemm/gregor_zwanzig/commits/" in sec and "/status" in sec, sec
    assert "success" in low and "failure" in low, sec
    # nicht selbst deployen: das Deploy-Skript wird hier nicht als Aufruf genannt
    assert "bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh" not in sec, sec
    status_pos = sec.find("deploy/prod")
    close_pos = max(low.find("gh issue close"), low.find("issue schließen"), low.find("issue schliessen"))
    assert close_pos != -1, "Issue-Abschluss fehlt im Abschnitt"
    assert status_pos < close_pos, "erst auf deploy/prod = success warten, dann Issue schliessen"


def test_ac9_e2e_verify_ausserhalb_laeuft_per_ssh_im_staging_checkout():
    """# doc-compliance-test — AC-9: Staging-Schritte per ssh, Nachweis als Note."""
    sec = _abschnitt_ausserhalb(CMD_E2E.read_text(encoding="utf-8"))
    assert "ssh henemm" in sec, sec
    assert "gregor_zwanzig_staging" in sec, sec
    assert "--write-verdict" in sec, sec
    assert "e2e-verified" in sec or "Note" in sec, sec


# --- #3423: Abnahme vom iMac nur ueber den festen Pruefzugang ------------------
# Spec docs/specs/modules/e2e_verify_imac_pruefzugang.md (AC-1 bis AC-8).

PLAYBOOK = REPO_ROOT / "docs" / "reference" / "operations_playbook.md"
_PRUEF_BEFEHLE = ("rev gregor-staging", "staging-deploy", "spec-run", "mail-pruefen", "write-verdict")


def _codezeilen(sec: str) -> list[str]:
    """Zeilen innerhalb von ```-Bloecken (ohne die Zaeune), links bereinigt."""
    out, drin = [], False
    for line in sec.splitlines():
        if line.lstrip().startswith("```"):
            drin = not drin
            continue
        if drin:
            out.append(line.strip())
    return out


def _ssh_codezeilen(sec: str) -> list[str]:
    return [z for z in _codezeilen(sec) if z.startswith("ssh ")]


def test_3423_ac1_jeder_abnahmeschritt_hat_seinen_pruefbefehl():
    """# doc-compliance-test — AC-1: alle fuenf Pruefbefehle als ssh-Aufruf."""
    sec = _abschnitt_ausserhalb(CMD_E2E.read_text(encoding="utf-8"))
    ssh = "\n".join(_ssh_codezeilen(sec))
    for befehl in _PRUEF_BEFEHLE:
        assert f"ssh henemm-pruefen {befehl}" in ssh or f'ssh henemm-pruefen "{befehl}' in ssh, (
            f"Pruefbefehl {befehl!r} fehlt als ssh-henemm-pruefen-Aufruf:\n{ssh}")


def test_3423_ac2_nur_pruefzugang_keine_freie_ssh_form():
    """# doc-compliance-test — AC-2: jede ssh-Codezeile nutzt den Pruefzugang."""
    sec = _abschnitt_ausserhalb(CMD_E2E.read_text(encoding="utf-8"))
    ssh = _ssh_codezeilen(sec)
    assert ssh, "keine ssh-Aufrufe im Abschnitt"
    for z in ssh:
        assert z.startswith("ssh henemm-pruefen "), f"freie ssh-Form: {z}"
    for z in _codezeilen(sec):
        assert "ssh henemm '" not in z and 'ssh henemm "' not in z, z


def test_3423_ac3_ssh_zeilen_ohne_sperrbedingung_des_hooks():
    """# doc-compliance-test — AC-3: kein .claude/-Pfad, keine Schreib-Umleitung;
    Findings nur als Eingabe per '<'."""
    sec = _abschnitt_ausserhalb(CMD_E2E.read_text(encoding="utf-8"))
    for z in _ssh_codezeilen(sec):
        assert ".claude/" not in z, z
        assert ">" not in z, f"Schreib-Umleitung in ssh-Zeile: {z}"
        assert "mktemp" not in z and "cat " not in z, z
    verdict = [z for z in _ssh_codezeilen(sec) if "write-verdict" in z]
    assert verdict, "write-verdict-Aufruf fehlt"
    for z in verdict:
        assert re.search(r"write-verdict (VERIFIED|BROKEN|AMBIGUOUS) '", z), (
            f"Verdict-Wort und Begruendung muessen getrennte Argumente sein: {z}")
        assert re.search(r"<\s*\S*findings\S*\.json\s*$", z), f"Findings nicht per '<': {z}"
        assert "--langs" in z, z


def test_3423_ac4_ac5_ac6_einchecken_grenzen_cloud_und_note():
    """# doc-compliance-test — AC-4/5/6."""
    sec = _abschnitt_ausserhalb(CMD_E2E.read_text(encoding="utf-8"))
    low = sec.lower()
    assert "selben pr" in low and "eincheck" in low, "Einchecken im selben PR fehlt"
    assert "--lang en" in sec and "umgebungsvariable" in low, "spec-run-Grenze fehlt"
    for grenze in ("staging_befehl_pruefen.py", "Telegram", "Premium-SMS", "e2e_browser_test.py"):
        assert grenze in sec, f"Grenze {grenze!r} fehlt"
    assert "server-sitzung" in low, "Verweis auf Server-Sitzung fehlt"
    assert "cloud" in low and "keinen prüfzugang" in low, "Cloud-Hinweis fehlt"
    assert "refs/notes/e2e-verified" in sec and "git notes --ref e2e-verified" in sec


def test_3423_ac7_playbook_nennt_den_pruefzugang():
    """# doc-compliance-test — AC-7: Absatz 'Rueckmeldung an die Sitzung'."""
    text = PLAYBOOK.read_text(encoding="utf-8")
    start = text.find("**Rückmeldung an die Sitzung.**")
    assert start != -1, "Absatz fehlt"
    absatz = text[start:text.find("\n\n", start)]
    assert "ssh henemm-pruefen" in absatz, absatz
    assert "per `ssh henemm`" not in absatz, absatz
