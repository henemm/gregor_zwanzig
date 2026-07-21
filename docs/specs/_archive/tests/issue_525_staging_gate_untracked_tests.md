---
entity_id: issue_525_staging_gate_untracked_tests
type: tests
created: 2026-06-01
updated: 2026-06-01
status: active
version: "1.0"
tags: [tests, staging-gate, git, e2e-verified, untracked, persistence, issue-525]
parent: issue_525_staging_gate_untracked
phase: phase5_tdd_red
---

# Issue #525 — Staging Gate: Untracked-Persistenz Tests

## Approval

- [x] Approved

## Zweck

Test-Manifest fuer `tests/tdd/test_staging_gate.py` (neue Klasse `TestE2EVerifiedPersistence`
ans Ende der Datei). Beweist, dass `.claude/e2e_verified.json` nach `git reset --hard` erhalten
bleibt, weil die Datei gitignored und untracked ist. Beide Tests laufen ohne Mocks — nur echte
`subprocess`-Aufrufe und echte Filesystem-Operationen.

## Source

- **File:** `tests/tdd/test_staging_gate.py`
- **Identifier:** `class TestE2EVerifiedPersistence`

## Estimated Scope

- **LoC:** ~45
- **Files:** 1
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `subprocess` | stdlib | Echte Git-Aufrufe (`git ls-files`, `git reset --hard`) |
| `pathlib.Path` | stdlib | Pfad-Konstruktion und Datei-Existenzpruefung |
| `pytest` | test framework | Test-Fixtures (`tmp_path`), Assertions |
| `REPO_DIR` | Konstante in test_staging_gate.py | Pfad zum echten Repo-Root fuer AC-2 |

## Implementation Details

### AC-2 — Untracked-Check gegen echtes Repo

```python
def test_e2e_verified_is_not_git_tracked(self):
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ".claude/e2e_verified.json"],
        cwd=REPO_DIR,
        capture_output=True,
    )
    assert result.returncode != 0, (
        ".claude/e2e_verified.json ist im Git-Index — muss untracked bleiben"
    )
```

Kein temporaeres Repo noetig: `git ls-files --error-unmatch` schlaegt fehl (Exit != 0)
wenn die Datei nicht im Index ist. Das beweist direkt den gitignored/untracked-Status.

### AC-1 — Reset-Persistenz in isoliertem Temp-Repo

```python
def test_e2e_verified_survives_git_reset_hard(self, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo, check=True, capture_output=True,
    )
    # .gitignore mit Eintrag fuer .claude/e2e_verified.json
    gitignore = repo / ".gitignore"
    gitignore.write_text(".claude/e2e_verified.json\n")
    subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo, check=True, capture_output=True,
    )
    # Datei anlegen (wird durch .gitignore ignoriert, bleibt untracked)
    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    verified = claude_dir / "e2e_verified.json"
    verified.write_text('{"verified_commit": "abc123", "staging_verdict": "VERIFIED"}')
    # Reset darf die Datei nicht entfernen
    subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=repo, check=True, capture_output=True)
    assert verified.exists(), (
        ".claude/e2e_verified.json wurde durch git reset --hard geloescht — "
        "sie muss als untracked/gitignored Datei erhalten bleiben"
    )
    content = verified.read_text()
    assert "abc123" in content, "Dateiinhalt wurde veraendert"
```

KEIN `git reset --hard` im echten Live-Repo. Das temporaere `git init` in `tmp_path`
ist vollstaendig isoliert — kein Risiko fuer den echten Repo-State.

## Acceptance Criteria

- **AC-1:** Given `.claude/e2e_verified.json` existiert in einem isolierten Temp-Git-Repo mit passender `.gitignore`-Regel / When `git reset --hard HEAD` in diesem Repo ausgefuehrt wird / Then bleibt die Datei mit unveraendertem Inhalt auf Disk erhalten, weil sie gitignored und damit untracked ist

- **AC-2:** Given das echte Projekt-Repo auf dem Server / When `git ls-files --error-unmatch .claude/e2e_verified.json` ausgefuehrt wird / Then ist der Exit-Code ungleich 0, was beweist dass die Datei nicht im Git-Index liegt (untracked)

## Expected Behavior

- **Input:** Keine externe Eingabe — Tests sind self-contained und nutzen `tmp_path` (AC-1) bzw. `REPO_DIR` (AC-2)
- **Output:** Beide Tests grueen bedeuten: die Datei ueberlebt `git reset --hard` und ist nicht im Index
- **Side effects:** AC-1 legt ein temporaeres Git-Repo in `tmp_path` an (pytest beraeumte automatisch); AC-2 fuehrt einen read-only Git-Befehl im echten Repo aus

## Known Limitations

- AC-2 schlaegt fehl wenn `.claude/e2e_verified.json` versehentlich committed wurde — in diesem Fall muss die Datei erst mit `git rm --cached` aus dem Index entfernt werden
- AC-1 benoetigt Git im PATH (Standard auf dem Produktionsserver)

## Changelog

- 2026-06-01: Initial test manifest erstellt — Issue #525
