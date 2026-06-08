---
entity_id: issue_665_e2e_path_helper
type: module
created: 2026-06-08
updated: 2026-06-08
status: draft
version: "1.0"
tags: [infra, tooling, e2e-gate, refactor, hardening]
---

# E2E-Pfad-Logik konsolidieren + gegen fehlerhaften SHA härten

## Approval

- [x] Approved

## Purpose

Die in #662 eingeführten Pfad-Helper (`_head_sha`, `_commit_e2e_path`,
`_default_e2e_path`) sind in `staging_gate.py` **und** `prod_selftest.py`
**dupliziert**. Genau diese Duplikation hat bereits zur Asymmetrie geführt, die
#665 meldet: `staging_gate._head_sha()` gibt bei git-Fehler `""`,
`prod_selftest._head_sha()` dagegen `"UNKNOWN"`. AC-5 von #662 verlangt aber, dass
**beide** Hooks für denselben HEAD **dieselbe** Datei auflösen — derzeit nur durch
zwei von Hand synchron gehaltene Kopien garantiert, ohne Test.

Diese Änderung extrahiert die Pfad-Logik in ein gemeinsames Modul
`.claude/hooks/_e2e_paths.py`, härtet `head_sha` (returncode-Guard) und
`commit_e2e_path` (kein kaputter Dateiname bei leerem SHA), und sichert die
Cross-Hook-Konsistenz mit einem Test ab. Verhaltenserhaltend für den Normalpfad.

## Source

- **File (neu):** `.claude/hooks/_e2e_paths.py` — pure Funktionen `head_sha(repo_dir)`, `commit_e2e_path(repo_dir, sha)`, `default_e2e_path(repo_dir, canonical_path, sha)`
- **File:** `.claude/hooks/staging_gate.py` — `_head_sha`/`_commit_e2e_path`/`_default_e2e_path` werden dünne Shims, die die monkeypatchbaren Konstanten `REPO_DIR`/`CANONICAL_E2E_PATH` ans gemeinsame Modul durchreichen
- **File:** `.claude/hooks/prod_selftest.py` — analog
- **File:** `tests/tdd/test_e2e_path_helper.py` — neue Tests (Cross-Hook-Konsistenz, SHA-Härtung)

Schicht-Hinweis: reine Tooling-Hooks. `--e2e-path`-Override + CLI unverändert →
`deploy-gregor-prod.sh` (Cross-Repo) bleibt unberührt.

## Estimated Scope

- **LoC:** ~80 (neues Modul + zwei Shim-Umbauten + Tests)
- **Files:** 4
- **Effort:** small

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `subprocess` / `pathlib` | stdlib | git-Aufruf + Pfade (keine neue Dep) |
| `staging_gate.py` / `prod_selftest.py` | intern | Konsumenten des gemeinsamen Moduls |

## Implementation Details

```
.claude/hooks/_e2e_paths.py (neu, pure, keine Modul-Konstanten):

  def head_sha(repo_dir) -> str:
      result = git rev-parse HEAD (cwd=repo_dir)
      if result.returncode != 0: return "UNKNOWN"
      return result.stdout.strip() or "UNKNOWN"   # nie ""

  def commit_e2e_path(repo_dir, sha) -> Path:
      # sha kommt von head_sha() → nie leer; defensiv: leer/None → "UNKNOWN"
      sha = sha or "UNKNOWN"
      return Path(repo_dir)/".claude"/"e2e_verified"/f"{sha}.json"

  def default_e2e_path(repo_dir, canonical_path, sha) -> Path:
      tagged = commit_e2e_path(repo_dir, sha)
      if tagged.exists(): return tagged
      if Path(canonical_path).exists(): return Path(canonical_path)
      return tagged

Beide Hooks behalten REPO_DIR / CANONICAL_E2E_PATH als monkeypatchbare
Modul-Konstanten. Ihre _head_sha()/_commit_e2e_path()/_default_e2e_path()
werden Shims, die diese Konstanten ZUR LAUFZEIT lesen und ans Modul reichen:

  import _e2e_paths
  def _head_sha(): return _e2e_paths.head_sha(REPO_DIR)
  def _commit_e2e_path(sha=None): return _e2e_paths.commit_e2e_path(REPO_DIR, sha or _head_sha())
  def _default_e2e_path(): return _e2e_paths.default_e2e_path(REPO_DIR, CANONICAL_E2E_PATH, _head_sha())

Import-Hinweis: Hooks laufen als `python3 .claude/hooks/<x>.py` → sys.path[0]
ist .claude/hooks/, `import _e2e_paths` findet das Geschwister-Modul. In Tests,
die via importlib laden, muss `.claude/hooks` auf sys.path liegen.
```

## Expected Behavior

- **Input:** `repo_dir` (echtes Git-Repo), optionaler `--e2e-path`-Override.
- **Output:** identische Pfad-Auflösung in beiden Hooks; `head_sha` nie `""`.
- **Side effects:** keine neuen. Verhalten im Normalpfad (git ok, Datei existiert) unverändert.

## Acceptance Criteria

- **AC-1:** Given `staging_gate.py` und `prod_selftest.py` sind beide auf dasselbe echte Git-Temp-Repo gepatcht (gleicher `REPO_DIR`, gleicher `CANONICAL_E2E_PATH`) und HEAD steht auf einem realen Commit, When `staging_gate._default_e2e_path()` und `prod_selftest._default_e2e_path()` aufgerufen werden, Then liefern **beide exakt denselben Pfad** zurück — für alle drei Fälle: (a) commit-getaggte Datei existiert, (b) nur Singleton existiert, (c) keine Datei existiert.
  - Test: echtes Temp-Repo, beide Hooks via importlib geladen, `REPO_DIR`/`CANONICAL_E2E_PATH` gepatcht, drei Szenarien durchspielen, `assert path_a == path_b`.

- **AC-2:** Given ein `repo_dir`, in dem `git rev-parse HEAD` fehlschlägt (kein Git-Repo / leeres Verzeichnis), When `_e2e_paths.head_sha(repo_dir)` aufgerufen wird, Then ist das Ergebnis der String `"UNKNOWN"` (niemals leerer String) — in **beiden** Hook-Shims identisch.
  - Test: Temp-Verzeichnis ohne `.git`, `head_sha()` → `"UNKNOWN"`; zusätzlich `staging_gate._head_sha()` und `prod_selftest._head_sha()` auf dasselbe Verzeichnis gepatcht liefern beide `"UNKNOWN"`.

- **AC-3:** Given `head_sha` liefert `"UNKNOWN"` (oder ein Aufrufer übergibt leeren/None-SHA), When `commit_e2e_path(repo_dir, sha)` aufgerufen wird, Then endet der Pfad auf `e2e_verified/UNKNOWN.json` und **niemals** auf einer Datei mit kaputtem Namen wie `e2e_verified/.json`.
  - Test: `commit_e2e_path(repo, "")` und `commit_e2e_path(repo, None)` → beide enden auf `UNKNOWN.json`.

- **AC-4:** Given die bestehende #662-Testsuite `tests/tdd/test_e2e_commit_namespacing.py` (8 Tests), When sie nach dem Refactor erneut läuft, Then bleiben **alle 8 grün** — der Refactor ist verhaltenserhaltend für den Normalpfad (write-verdict commit-getaggt, gate_check getaggt-vor-Singleton-Fallback, AC-4-Sicherheit Fremd-Commit blockt, prod_selftest konsistent).
  - Test: `pytest tests/tdd/test_e2e_commit_namespacing.py` → 8 passed.

- **AC-5:** Given der Refactor ist abgeschlossen, When man `staging_gate.py` und `prod_selftest.py` nach den drei Helper-Definitionen durchsucht, Then existiert die Pfad-Logik (`git rev-parse`-Aufruf + Pfad-Bildung + Fallback-Kette) **nur noch einmal** im gemeinsamen Modul `_e2e_paths.py`, nicht mehr dupliziert in beiden Hooks (die Hook-Funktionen sind reine Durchreich-Shims). `# doc-compliance-test`.
  - Test: prüft dass `_e2e_paths` in beiden Hooks importiert wird und die Shims das Modul aufrufen.
