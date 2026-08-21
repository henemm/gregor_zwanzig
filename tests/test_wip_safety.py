"""TDD RED fuer #2047 Scheibe 1 — WIP-Sicherung vor ``git reset --hard`` in CI.

Prueflinge:

* ``scripts/wip_safety.sh`` (Shell-Skript, Aufruf ``bash wip_safety.sh <repo>``)
* ``.github/workflows/ci.yml`` — Verdrahtung im Schritt "Staging-Verdict schreiben (CI smoke)"

Alle Verhaltenstests laufen gegen ein ECHTES Wegwerf-Git-Repo (``tempfile.mkdtemp``,
echtes ``git init``/``clone``, echte Commits, echtes ``git reset --hard``, echter
``subprocess``-Aufruf des Skripts). Keine Mocks — Spec ``docs/specs/modules/ci_wip_sicherung.md``.
"""

import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "wip_safety.sh"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

COMMITTED_TEXT = "stand aus origin/main\n"
WIP_TEXT = "uncommittete WIP-Arbeit einer parallelen Session\n"
TRACKED = "notiz.txt"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Echter Git-Aufruf gegen ``repo`` (nie gegen das Projekt-Repo)."""
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} in {repo} scheiterte (rc={proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc


def _run_wip_safety(repo: Path) -> subprocess.CompletedProcess:
    """Ruft den Pruefling auf — mit sprechender Meldung, falls er fehlt."""
    assert SCRIPT.exists(), (
        f"Pruefling fehlt: {SCRIPT} — das Skript muss in Phase 6 angelegt werden "
        "(Spec docs/specs/modules/ci_wip_sicherung.md)."
    )
    return subprocess.run(
        ["bash", str(SCRIPT), str(repo)], capture_output=True, text=True
    )


def _safety_tags(repo: Path) -> list[str]:
    out = _git(repo, "tag", "--list", "deploy-safety/ci-*").stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


@pytest.fixture()
def workdir():
    """Wegwerf-Verzeichnis, wird nach dem Test restlos abgeraeumt."""
    path = Path(tempfile.mkdtemp(prefix="wip-safety-"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture()
def repo(workdir: Path) -> Path:
    """Echtes Repo mit echtem ``origin/main`` (bare Remote + Klon).

    ``git reset --hard origin/main`` — der Befehl, gegen den die Sicherung
    schuetzen muss — ist damit real ausfuehrbar.
    """
    origin = workdir / "origin.git"
    clone = workdir / "checkout"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(origin)],
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(
        ["git", "clone", str(origin), str(clone)],
        capture_output=True,
        text=True,
        check=True,
    )
    _git(clone, "config", "user.email", "wip-safety@test.invalid")
    _git(clone, "config", "user.name", "WIP Safety Test")
    (clone / TRACKED).write_text(COMMITTED_TEXT, encoding="utf-8")
    _git(clone, "add", TRACKED)
    _git(clone, "commit", "-m", "initial")
    _git(clone, "push", "-u", "origin", "main")
    return clone


def test_uncommittete_aenderung_ueberlebt_harten_reset(repo: Path):
    """AC-1.

    GIVEN eine uncommittete Aenderung an einer getrackten Datei
    WHEN wip_safety.sh laeuft und danach ``git reset --hard origin/main``
    THEN existiert ein Tag ``deploy-safety/ci-<Zeitstempel>`` und
         ``git stash apply <Tag>`` stellt die Aenderung inhaltlich wieder her.
    """
    (repo / TRACKED).write_text(WIP_TEXT, encoding="utf-8")

    proc = _run_wip_safety(repo)
    assert proc.returncode == 0, f"stderr={proc.stderr}"

    tags = _safety_tags(repo)
    assert len(tags) == 1, f"genau ein Sicherungs-Tag erwartet, gefunden: {tags}"

    _git(repo, "reset", "--hard", "origin/main")
    assert (repo / TRACKED).read_text(encoding="utf-8") == COMMITTED_TEXT

    _git(repo, "stash", "apply", tags[0])
    assert (repo / TRACKED).read_text(encoding="utf-8") == WIP_TEXT


def test_arbeitsbaum_bleibt_nach_der_sicherung_unveraendert(repo: Path):
    """AC-2.

    GIVEN der Arbeitsbaum enthaelt uncommittete Aenderungen
    WHEN wip_safety.sh laeuft
    THEN ist der reale Diff davor und danach identisch — die Sicherung darf
         nichts wegnehmen, weil der Checkout mit anderen Sessions geteilt wird.
    """
    (repo / TRACKED).write_text(WIP_TEXT, encoding="utf-8")
    diff_before = _git(repo, "diff").stdout
    cached_before = _git(repo, "diff", "--cached").stdout
    assert diff_before.strip(), "Vorbedingung: der Arbeitsbaum muss schmutzig sein"

    proc = _run_wip_safety(repo)
    assert proc.returncode == 0, f"stderr={proc.stderr}"

    assert _git(repo, "diff").stdout == diff_before
    assert _git(repo, "diff", "--cached").stdout == cached_before


def test_gestagete_aenderung_ist_ueber_den_tag_wiederherstellbar(repo: Path):
    """AC-3.

    GIVEN eine Aenderung ist gestaget (``git add``), aber nicht committet
    WHEN wip_safety.sh laeuft und danach hart resettet wird
    THEN liefert ``git stash apply <Tag>`` den gestageten Inhalt zurueck.
    """
    (repo / TRACKED).write_text(WIP_TEXT, encoding="utf-8")
    _git(repo, "add", TRACKED)
    assert _git(repo, "diff", "--cached").stdout.strip(), (
        "Vorbedingung: die Aenderung muss gestaget sein"
    )

    proc = _run_wip_safety(repo)
    assert proc.returncode == 0, f"stderr={proc.stderr}"

    tags = _safety_tags(repo)
    assert len(tags) == 1, f"genau ein Sicherungs-Tag erwartet, gefunden: {tags}"

    _git(repo, "reset", "--hard", "origin/main")
    assert (repo / TRACKED).read_text(encoding="utf-8") == COMMITTED_TEXT

    _git(repo, "stash", "apply", tags[0])
    assert (repo / TRACKED).read_text(encoding="utf-8") == WIP_TEXT


def test_sauberer_arbeitsbaum_legt_keinen_tag_an(repo: Path):
    """AC-4.

    GIVEN der Arbeitsbaum ist sauber
    WHEN wip_safety.sh laeuft
    THEN wird kein Tag angelegt, keine Fehlermeldung ausgegeben, Exit-Code 0.
    """
    assert not _git(repo, "status", "--porcelain").stdout.strip(), (
        "Vorbedingung: der Arbeitsbaum muss sauber sein"
    )

    proc = _run_wip_safety(repo)

    assert proc.returncode == 0, f"stderr={proc.stderr}"
    assert proc.stderr.strip() == "", f"unerwartete Fehlermeldung: {proc.stderr!r}"
    assert _safety_tags(repo) == []


def test_fehlgeschlagene_sicherung_bricht_mit_fehler_ab(workdir: Path):
    """AC-5.

    GIVEN der Arbeitsbaum ist schmutzig, aber ``git stash create`` liefert kein
          Stash-Objekt
    WHEN wip_safety.sh laeuft
    THEN ist der Exit-Code ungleich 0 und die Meldung benennt ungesicherte Arbeit —
         die Kette darf NICHT mit einem harten Reset weiterlaufen.

    Gewaehlter Weg: Repo OHNE initialen Commit mit gestageter Datei. ``git diff
    --cached --quiet`` meldet dort schmutzig (rc=1), ``git stash create`` bricht
    mangels HEAD ab und gibt nichts auf stdout aus. Genau diese Vorbedingung wird
    unten mit einem echten ``git stash create``-Aufruf nachgewiesen.
    """
    broken = workdir / "ohne-initial-commit"
    broken.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main", str(broken)],
        capture_output=True,
        text=True,
        check=True,
    )
    _git(broken, "config", "user.email", "wip-safety@test.invalid")
    _git(broken, "config", "user.name", "WIP Safety Test")
    (broken / TRACKED).write_text(WIP_TEXT, encoding="utf-8")
    _git(broken, "add", TRACKED)

    assert _git(broken, "diff", "--cached", "--quiet", check=False).returncode != 0, (
        "Vorbedingung: der Baum muss als schmutzig gelten"
    )
    probe = _git(broken, "stash", "create", "probe", check=False)
    assert probe.stdout.strip() == "", (
        f"Vorbedingung verfehlt: stash create lieferte doch ein Objekt ({probe.stdout!r}) "
        "— der Testzustand muss anders konstruiert werden"
    )

    proc = _run_wip_safety(broken)

    assert proc.returncode != 0, (
        "die Kette darf nach fehlgeschlagener Sicherung nicht weiterlaufen "
        f"(stdout={proc.stdout!r})"
    )
    message = (proc.stderr + proc.stdout).lower()
    assert "gesichert" in message, (
        f"Meldung muss ungesicherte Arbeit benennen, war: {message!r}"
    )
    assert any(word in message for word in ("arbeit", "wip", "nderung")), (
        f"Meldung muss benennen, WAS ungesichert ist, war: {message!r}"
    )


def test_ausgegebener_wiederherstellungs_befehl_holt_die_arbeit_zurueck(repo: Path):
    """AC-6.

    GIVEN eine Sicherung wurde angelegt
    WHEN der in der Ausgabe genannte Wiederherstellungs-Befehl tatsaechlich
         ausgefuehrt wird
    THEN ist die Datei inhaltlich zurueck — Ausfuehrungsnachweis, nicht nur
         String-Presence; der Befehl muss den exakten Tag-Namen enthalten.
    """
    (repo / TRACKED).write_text(WIP_TEXT, encoding="utf-8")

    proc = _run_wip_safety(repo)
    assert proc.returncode == 0, f"stderr={proc.stderr}"

    tags = _safety_tags(repo)
    assert len(tags) == 1, f"genau ein Sicherungs-Tag erwartet, gefunden: {tags}"
    tag = tags[0]

    match = re.search(r"git\b[^\n]*?stash\s+apply\s+\S+", proc.stdout)
    assert match, (
        "Ausgabe enthaelt keinen vollstaendigen Wiederherstellungs-Befehl, "
        f"stdout war: {proc.stdout!r}"
    )
    command = match.group(0).strip("`'\"(),. ")
    assert tag in command, (
        f"Wiederherstellungs-Befehl nennt den Tag {tag} nicht: {command!r}"
    )

    _git(repo, "reset", "--hard", "origin/main")
    assert (repo / TRACKED).read_text(encoding="utf-8") == COMMITTED_TEXT

    restore = subprocess.run(
        shlex.split(command), cwd=str(repo), capture_output=True, text=True
    )
    assert restore.returncode == 0, (
        f"ausgegebener Befehl {command!r} scheiterte: {restore.stderr.strip()}"
    )
    assert (repo / TRACKED).read_text(encoding="utf-8") == WIP_TEXT


def test_untrackte_dateien_bleiben_unangetastet(repo: Path):
    """AC-7.

    GIVEN untrackte Dateien liegen im Arbeitsbaum
    WHEN wip_safety.sh laeuft und danach hart resettet wird
    THEN sind sie mit identischem Inhalt weiterhin vorhanden und weiterhin untrackt.
    """
    untracked = repo / "unversioniert.txt"
    untracked_text = "nur lokal, nie committet\n"
    untracked.write_text(untracked_text, encoding="utf-8")
    (repo / TRACKED).write_text(WIP_TEXT, encoding="utf-8")

    proc = _run_wip_safety(repo)
    assert proc.returncode == 0, f"stderr={proc.stderr}"
    assert untracked.read_text(encoding="utf-8") == untracked_text

    _git(repo, "reset", "--hard", "origin/main")
    assert untracked.exists(), "der Reset darf die untrackte Datei nicht entfernen"
    assert untracked.read_text(encoding="utf-8") == untracked_text
    assert "?? unversioniert.txt" in _git(repo, "status", "--porcelain").stdout


def test_ci_ruft_die_sicherung_vor_dem_harten_reset_aus_origin_main_auf():
    """AC-8 — # doc-compliance-test

    GIVEN der CI-Schritt "Staging-Verdict schreiben (CI smoke)" in ci.yml
    WHEN der Schritt gelesen wird
    THEN steht der Aufruf der Sicherung VOR dem ``git reset --hard origin/main``,
         und das Skript wird aus ``origin/main`` bezogen, nicht aus dem Arbeitsbaum.

    ``ci.yml`` ist nicht ausfuehrbar testbar (Context-Doc Punkt 4) — deshalb hier
    ausnahmsweise eine Dateiinhalt-Pruefung.
    """
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    step_marker = "Staging-Verdict schreiben (CI smoke)"
    assert step_marker in text, f"Schritt {step_marker!r} fehlt in {CI_WORKFLOW}"

    rest = text[text.index(step_marker) :]
    next_step = re.search(r"\n\s+- name: ", rest)
    block = rest[: next_step.start()] if next_step else rest

    assert "wip_safety.sh" in block, (
        f"Schritt {step_marker!r} ruft wip_safety.sh nicht auf — Block:\n{block}"
    )
    assert "git reset --hard origin/main" in block, (
        "der abzusichernde harte Reset steht nicht mehr in diesem Schritt"
    )
    assert block.index("wip_safety.sh") < block.index("git reset --hard origin/main"), (
        "die Sicherung muss VOR dem harten Reset laufen"
    )

    call_lines = [line for line in block.splitlines() if "wip_safety.sh" in line]
    assert all("origin/main" in line for line in call_lines), (
        "das Skript muss aus origin/main bezogen werden, nicht aus dem Arbeitsbaum "
        f"(Henne-Ei beim ersten Rollout) — Zeilen: {call_lines}"
    )
