"""
Issue #728 — Telegram-Scope-Erkennung filtert Doku-/Tooling-Pfade.

Behebt einen False-Positive: `_scope_touches_telegram()` matchte den Substring
`telegram` über ALLE geänderten Dateinamen — auch über Doku-`.md`-Dateien. Eine
reine `docs/`-`.md`-Änderung (z.B. `issue_692_telegram_disabled_unconfigured.md`)
löste dadurch fälschlich den Telegram-Live-Gate aus und blockte `write_verdict`
ohne `GZ_TELEGRAM_TEST_CHAT_ID` (Symptom beim #724-Deploy).

KEINE Mocks: echte temporäre git-Repos, echte `git diff`-Ausgabe, echtes
Close-Gate (`staging_gate.write_verdict`). monkeypatch nur für ENV + REPO_DIR.

Spec: docs/specs/modules/issue_728_telegram_scope_neutral_paths.md
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO / ".claude" / "hooks"

# Der konkrete Doku-Pfad, der den #724-Blocker auslöste.
TELEGRAM_DOC = "docs/specs/modules/issue_692_telegram_disabled_unconfigured.md"


def _load_e2e_hook():
    path = HOOKS_DIR / "e2e_telegram_live.py"
    spec = importlib.util.spec_from_file_location("e2e_telegram_live_728", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_staging_gate():
    path = HOOKS_DIR / "staging_gate.py"
    spec = importlib.util.spec_from_file_location("staging_gate_728", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args):
    subprocess.run(["git", *args], cwd=str(repo), check=True,
                   capture_output=True, text=True)


def _init_repo(repo: Path):
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    # harmloser Erst-Commit (damit HEAD~1 existiert)
    (repo / "AAA.txt").write_text("seed\n")
    _git(repo, "add", "AAA.txt")
    _git(repo, "commit", "-m", "init")


def _committed_changed_files(repo: Path) -> list[str]:
    """Echte `git diff --name-only HEAD~1 HEAD`-Ausgabe — keine Mocks."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
        cwd=str(repo), capture_output=True, text=True, check=True,
    )
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


# ---------------------------------------------------------------------------
# AC-1 — Doku-`.md` mit „telegram" im Pfad → kein Telegram-Scope
# ---------------------------------------------------------------------------

def test_ac1_docs_only_telegram_md_is_not_telegram_scope(tmp_path):
    """
    GIVEN: ein git-Repo, dessen letzter Commit AUSSCHLIESSLICH die Doku-Datei
           docs/specs/modules/issue_692_telegram_disabled_unconfigured.md ändert
    WHEN: `_scope_touches_telegram()` gegen die echte `git diff`-Liste läuft
    THEN: liefert sie False (Doku-`.md` löst keinen Telegram-Scope aus).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    doc = repo / TELEGRAM_DOC
    doc.parent.mkdir(parents=True)
    doc.write_text("# Spec über telegram disabled\n")
    _git(repo, "add", TELEGRAM_DOC)
    _git(repo, "commit", "-m", "docs(#692): Spec als complete markiert")

    changed = _committed_changed_files(repo)
    assert changed == [TELEGRAM_DOC], f"Test-Setup falsch, changed={changed}"

    mod = _load_e2e_hook()
    assert mod._scope_touches_telegram(changed) is False, (
        "Eine reine Doku-`.md` mit 'telegram' im Pfad darf KEINEN Telegram-Scope "
        "auslösen — sie enthält keinen Telegram-Code."
    )


# ---------------------------------------------------------------------------
# AC-2 — echter Code-Pfad + Doku → weiterhin Telegram-Scope
# ---------------------------------------------------------------------------

def test_ac2_real_code_plus_docs_still_telegram_scope(tmp_path):
    """
    GIVEN: ein Commit, der src/outputs/telegram.py (echter Code) UND eine
           Doku-`.md` ändert
    WHEN: `_scope_touches_telegram()` läuft
    THEN: liefert sie True — der echte Telegram-Code darf nicht durch die
          Doku-Filterung maskiert werden.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    code = repo / "src" / "outputs" / "telegram.py"
    code.parent.mkdir(parents=True)
    code.write_text("# touches telegram code\n")
    doc = repo / TELEGRAM_DOC
    doc.parent.mkdir(parents=True)
    doc.write_text("# doc\n")
    _git(repo, "add", "src/outputs/telegram.py", TELEGRAM_DOC)
    _git(repo, "commit", "-m", "feat(telegram): code + docs")

    changed = _committed_changed_files(repo)
    mod = _load_e2e_hook()
    assert mod._scope_touches_telegram(changed) is True, (
        "Ein echter Telegram-Code-Pfad muss weiterhin True liefern, auch wenn "
        "im selben Commit Doku geändert wurde."
    )


# ---------------------------------------------------------------------------
# AC-3 — echtes Close-Gate blockt docs-only Telegram-`.md` NICHT
# ---------------------------------------------------------------------------

def test_ac3_write_verdict_not_blocked_by_docs_only_telegram_md(tmp_path, monkeypatch):
    """
    GIVEN: ein git-Repo, dessen letzter Commit nur eine Telegram-Doku-`.md`
           ändert, und ein staging_gate mit REPO_DIR auf dieses Repo, OHNE
           gesetzte GZ_TELEGRAM_TEST_CHAT_ID
    WHEN: write_verdict("VERIFIED: ...") aufgerufen wird
    THEN: Rückgabe 0 UND das Verdict-Artefakt (out.json) wird geschrieben —
          der Telegram-Live-Gate blockt eine reine Doku-Änderung NICHT.
          (Reproduziert exakt den #724-Blocker.)
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    doc = repo / TELEGRAM_DOC
    doc.parent.mkdir(parents=True)
    doc.write_text("# Spec über telegram\n")
    _git(repo, "add", TELEGRAM_DOC)
    _git(repo, "commit", "-m", "docs(#692): telegram spec complete")

    gate_mod = _load_staging_gate()
    monkeypatch.setattr(gate_mod, "REPO_DIR", repo)
    monkeypatch.delenv("GZ_TELEGRAM_TEST_CHAT_ID", raising=False)

    findings_path = tmp_path / "findings.json"
    findings_path.write_text("[]")
    out_path = tmp_path / "out.json"

    rc = gate_mod.write_verdict("VERIFIED: docs-only telegram md", findings_path, e2e_path=out_path)
    assert rc == 0, (
        "Eine reine Doku-`.md` darf das Close-Gate NICHT blocken — "
        "der Telegram-Live-Gate ist hier irrelevant (Issue #728/#724)."
    )
    assert out_path.exists(), "Verdict-Artefakt muss bei nicht-blockiertem Gate existieren"
