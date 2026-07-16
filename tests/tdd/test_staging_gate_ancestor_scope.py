"""
TDD RED — Deploy-Gate Ancestor+docs-only-Relaxierung (#1197).

Spec: docs/specs/modules/fix_1197_deploy_gate_ancestor_scope.md (AC-1..AC-9)
Kontext: docs/artifacts/fix-1197-deploy-gate-ancestor-scope/context.md

KEINE Mocks der Git-Logik. Jeder Test baut ein ECHTES temporäres Git-Repo
(`git init`, echte Dateien, echte `git commit`s) und ruft das ECHTE
`staging_gate.gate_check` in-process dagegen auf. Der einzige Test-Seam ist ein
ehrlicher *Location*-Seam: `mod._shared_repo_dir` (Ort der Attestationen) und
`mod._verified_repo_dir` (Commit-/Scope-Quelle) werden per monkeypatch auf das
tmp-Repo umgebogen. Die Ancestor-Auflösung, `git merge-base --is-ancestor` und
die Scope-Klassifikation laufen damit REAL gegen das tmp-Repo. Kein Netz.

Warum `scope_override` gesetzt wird: `gate_check` hat vor der Attestations-Logik
einen docs-only-Skip (Schritt 2/3), der HEAD~1..HEAD betrachtet. Ist der Zuwachs
über der Attestation docs-only, würde dieser Skip bereits Exit 0 liefern, BEVOR
die neue Ancestor-Logik greift — die Tests würden dann den falschen Pfad prüfen.
Deshalb wird der Gesamt-Scope des Deploys als `scope_override` übergeben (im
echten Bug #1197: old-prod..EXP == "frontend-only"), was den Skip überspringt und
den Kontrollfluss verlässlich in die Attestations-Auflösung führt. Die
Relaxierungs-Entscheidung selbst berechnet ihren Zuwachs-Scope (C..HEAD)
UNABHÄNGIG davon real per git.

RED-Erwartung: Nur AC-2 (der Kern-Relax) ist aktuell rot (Exit 1 statt 0), weil
weder die Ancestor-Auflösung noch die docs-only-Relaxierung existieren. AC-3, AC-4,
AC-5, AC-6, AC-7, AC-8 sind Nicht-Aufweichen-Guards und aktuell bereits grün
(bestehendes Blocken bei fehlender <HEAD>.json bzw. GZ_SKIP-Override). Sie prüfen,
dass der Fix nicht über den docs-only-Fall hinaus aufweicht. AC-1 und AC-9 sind
unveränderte-Verhalten-Guards.
"""

import importlib.util
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGING_GATE = REPO_ROOT / ".claude" / "hooks" / "staging_gate.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Ein Modul-Objekt reicht: monkeypatch revertiert jede Attribut-Umbiegung nach
# dem Test wieder, die Git-/Datei-Operationen laufen alle gegen das tmp-Repo.
GATE = _load_module(STAGING_GATE, "staging_gate_ancestor_scope")


def _git(args, cwd):
    r = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=str(cwd))
    return r


def _init_repo(root: Path) -> None:
    _git(["init", "-q", "-b", "main"], root)
    _git(["config", "user.email", "t@example.com"], root)
    _git(["config", "user.name", "Tester"], root)


def _commit(root: Path, files: dict, msg: str) -> str:
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    _git(["add", "-A"], root)
    _git(["commit", "-qm", msg], root)
    return _git(["rev-parse", "HEAD"], root).stdout.strip()


def _iso(hours_ago: float = 0.0) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def _write_attestation(
    shared: Path,
    sha: str,
    *,
    verdict: str = "VERIFIED: alles gut",
    scope: str = "frontend-only",
    age_hours: float = 0.0,
) -> Path:
    out = shared / ".claude" / "e2e_verified" / f"{sha}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "verified_commit": sha,
                "staging_verdict": verdict,
                "findings": [],
                "verified_at": _iso(age_hours),
                "scope": scope,
                "environment": "staging",
            }
        )
    )
    return out


def _point(monkeypatch, shared: Path, verified: Path | None = None) -> None:
    """Ehrlicher Location-Seam: Attestations-Ort und Commit-/Scope-Quelle auf das
    echte tmp-Repo umbiegen. Die Git-Logik selbst bleibt ungemockt.
    """
    verified = verified if verified is not None else shared
    monkeypatch.setattr(GATE, "_shared_repo_dir", lambda: shared)
    monkeypatch.setattr(GATE, "_verified_repo_dir", lambda: verified)


@pytest.fixture(autouse=True)
def _no_skip_override(monkeypatch):
    """Notfall-Override darf die ACs (außer AC-9) nicht verfälschen."""
    monkeypatch.delenv("GZ_SKIP_E2E_GATE", raising=False)


# ---------------------------------------------------------------------------
# AC-1 (Guard, aktuell grün): exakte <HEAD>.json-Übereinstimmung → Exit 0.
# ---------------------------------------------------------------------------
def test_ac1_exact_head_match_passes(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    head = _commit(tmp_path, {"src/app.py": "x = 1\n", "frontend/a.js": "//a\n"}, "product")
    _write_attestation(tmp_path, head, scope="full-stack")
    _point(monkeypatch, tmp_path)

    rc = GATE.gate_check(None, "full-stack", expected_commit=None)
    assert rc == 0, "exakte <HEAD>.json VERIFIED muss unverändert bestehen"


# ---------------------------------------------------------------------------
# AC-2 (KERN, aktuell ROT): keine <HEAD>.json, VERIFIED-Ancestor, docs-only-Zuwachs
# → Exit 0 erwartet. Aktuell: <HEAD>.json fehlt → Singleton-Fallback greift nicht
# (existiert nicht) → Exit 1. Prüft den NEUEN Ancestor+Relax-Pfad.
# ---------------------------------------------------------------------------
def test_ac2_docs_only_increment_over_verified_ancestor_passes(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    base = _commit(tmp_path, {"src/app.py": "x = 1\n", "frontend/a.js": "//a\n"}, "product (attested)")
    # Zuwachs = reiner Doku-/Tooling-Commit obendrauf. HEAD hat KEINE eigene Attestation.
    head = _commit(tmp_path, {"docs/notes.md": "# notes\n"}, "docs-only on top")
    assert head != base
    _write_attestation(tmp_path, base, scope="frontend-only")
    _point(monkeypatch, tmp_path)

    rc = GATE.gate_check(None, "frontend-only", expected_commit=None)
    assert rc == 0, (
        "docs-only-Zuwachs über verifiziertem Ancestor muss durchgelassen werden "
        "(Ancestor-Auflösung + docs-only-Relaxierung) — aktuell rot, weil beide fehlen"
    )


# ---------------------------------------------------------------------------
# AC-3 (Guard): Zuwachs enthält frontend/ → kein Relax → Exit 1.
# ---------------------------------------------------------------------------
def test_ac3_frontend_increment_blocks(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    base = _commit(tmp_path, {"src/app.py": "x = 1\n"}, "product (attested)")
    _commit(tmp_path, {"frontend/new.js": "//neu\n"}, "frontend change on top")
    _write_attestation(tmp_path, base, scope="backend")
    _point(monkeypatch, tmp_path)

    rc = GATE.gate_check(None, "frontend-only", expected_commit=None)
    assert rc == 1, "echter Frontend-Code im Zuwachs darf NICHT relaxiert werden"


# ---------------------------------------------------------------------------
# AC-4 (Guard): Zuwachs enthält src/ (Backend-Code) → kein Relax → Exit 1.
# ---------------------------------------------------------------------------
def test_ac4_backend_increment_blocks(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    base = _commit(tmp_path, {"frontend/a.js": "//a\n"}, "product (attested)")
    _commit(tmp_path, {"src/handler.py": "y = 2\n"}, "backend change on top")
    _write_attestation(tmp_path, base, scope="frontend-only")
    _point(monkeypatch, tmp_path)

    rc = GATE.gate_check(None, "backend", expected_commit=None)
    assert rc == 1, "echter Backend-Code im Zuwachs darf NICHT relaxiert werden"


# ---------------------------------------------------------------------------
# AC-5 (Guard): HEAD ist Nachfahre KEINER Attestation (unverwandter Root) → Exit 1.
# ---------------------------------------------------------------------------
def test_ac5_divergent_head_blocks(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    base = _commit(tmp_path, {"src/app.py": "x = 1\n"}, "product on main")
    # Zweiter, unverwandter Wurzel-Branch: HEAD hat KEINEN gemeinsamen Ancestor mit base.
    _git(["checkout", "-q", "--orphan", "other"], tmp_path)
    _git(["rm", "-rfq", "--cached", "."], tmp_path)
    for p in tmp_path.glob("*"):
        if p.name != ".git":
            if p.is_dir():
                subprocess.run(["rm", "-rf", str(p)], check=False)
            else:
                p.unlink()
    orphan = _commit(tmp_path, {"src/other.py": "z = 9\n"}, "unrelated root")
    assert orphan != base
    # Attestation existiert NUR für den unverwandten base-Commit.
    _write_attestation(tmp_path, base, scope="backend")
    _point(monkeypatch, tmp_path)

    rc = GATE.gate_check(None, "backend", expected_commit=None)
    assert rc == 1, "unverwandter/divergenter HEAD darf nie relaxiert werden"


# ---------------------------------------------------------------------------
# AC-6 (Guard): nächster Ancestor mit Attestation trägt NICHT-VERIFIED-Verdict
# (BROKEN) → nicht als Basis akzeptiert → Exit 1 (Zuwachs ist docs-only).
# ---------------------------------------------------------------------------
def test_ac6_non_verified_ancestor_blocks(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    base = _commit(tmp_path, {"src/app.py": "x = 1\n"}, "product (broken attest)")
    _commit(tmp_path, {"docs/notes.md": "# notes\n"}, "docs-only on top")
    _write_attestation(tmp_path, base, verdict="BROKEN: kaputt", scope="backend")
    _point(monkeypatch, tmp_path)

    rc = GATE.gate_check(None, "frontend-only", expected_commit=None)
    assert rc == 1, "BROKEN-Ancestor darf nicht als verifizierte Basis dienen"


# ---------------------------------------------------------------------------
# AC-7 (Guard): Ancestor-Attestation ist stale (> STALE_HOURS) → Exit 1
# (Zuwachs ist docs-only, würde sonst relaxiert).
# ---------------------------------------------------------------------------
def test_ac7_stale_ancestor_blocks(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    base = _commit(tmp_path, {"src/app.py": "x = 1\n"}, "product (stale attest)")
    _commit(tmp_path, {"docs/notes.md": "# notes\n"}, "docs-only on top")
    _write_attestation(tmp_path, base, scope="backend", age_hours=GATE.STALE_HOURS + 5)
    _point(monkeypatch, tmp_path)

    rc = GATE.gate_check(None, "frontend-only", expected_commit=None)
    assert rc == 1, "Staleness muss auch für die Ancestor-Basis gelten"


# ---------------------------------------------------------------------------
# AC-8 (Guard): Scope-Ermittlung des Zuwachses scheitert (Commit-/Scope-Quelle
# nicht auflösbar) → fail-closed → Exit 1. Der Attestations-Ort bleibt intakt,
# nur die git-basierte Zuwachs-/HEAD-Auflösung schlägt fehl (Nicht-Git-Verzeichnis).
# ---------------------------------------------------------------------------
def test_ac8_scope_resolution_failure_fails_closed(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    base = _commit(tmp_path, {"src/app.py": "x = 1\n"}, "product (attested)")
    _commit(tmp_path, {"docs/notes.md": "# notes\n"}, "docs-only on top")
    _write_attestation(tmp_path, base, scope="backend")
    broken = tmp_path / "not_a_git_repo"
    broken.mkdir()
    # Attestationen liegen im echten Repo, aber HEAD-/Scope-Auflösung läuft gegen
    # ein Nicht-Git-Verzeichnis → alle git-Aufrufe scheitern → fail-closed.
    _point(monkeypatch, shared=tmp_path, verified=broken)

    rc = GATE.gate_check(None, "backend", expected_commit=None)
    assert rc == 1, "git-/Scope-Auflösungsfehler des Zuwachses muss fail-closed blocken"


# ---------------------------------------------------------------------------
# AC-9 (Guard): GZ_SKIP_E2E_GATE=1 → Exit 0 unabhängig von allem.
# ---------------------------------------------------------------------------
def test_ac9_skip_override_passes(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    _commit(tmp_path, {"src/app.py": "x = 1\n"}, "product without attestation")
    _point(monkeypatch, tmp_path)
    monkeypatch.setenv("GZ_SKIP_E2E_GATE", "1")

    rc = GATE.gate_check(None, None, expected_commit=None)
    assert rc == 0, "Notfall-Override muss unverändert Exit 0 liefern"
