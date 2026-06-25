# Kontext: Issue #885 — ADR-Enforcement

## Ziel

ADR-Nutzung (`docs/adr/`) mechanisch erzwingen, auf zwei Ebenen: ein Commit-Gate und ein
Spec-Pflichtfeld bei der Freigabe.

## Recon — echte Gate-Mechanik (verifiziert)

> **Korrektur:** Eine erste Explore-Runde behauptete eine Datei `.claude/hooks/pre_commit_gate.py`
> als Commit-Gate-Kette. **Diese Datei existiert nicht** (halluziniert). Die echte Mechanik wurde
> per Datei-Read verifiziert:

- **Commit-Gating läuft in `.claude/hooks/bash_gate.py`** — dem zentralen PreToolUse-Bash-Hook.
  - `main()` Schritt 5 (`if "git commit" in command`, ab Zeile 242) liest die gestageten Dateien via
    `git diff --cached --name-only` (Zeile 247–251).
  - Schritt **5a** (Zeile 253–262) ist bereits config-getrieben: `config.get("pre_commit", {}).get("required_staged_files")`.
  - Blockieren via `block(msg)` → Exit 2.
  - Die Commit-Message steht im `command`-String (`git commit -m "..."`) und ist dort parsbar.
- **Konvention** (bash_gate.py Zeile 14): „Project-specific gates belong in module hooks." → daher
  reine Prüflogik in neuem `adr_guard.py`, von bash_gate Schritt **5d** aufgerufen.
- **Vorbild-Muster** für Standalone-Gate + No-Op-Verhalten: `.claude/hooks/renderer_mail_gate.py`
  (Hook-Modus, Exit 2, **kein** ENV-Bypass — bewusst).
- **Spec-Freigabe-Gating:** `.claude/hooks/workflow.py` `_validate_transition` (Zeile 330), Block
  vor `phase4_approved` an Zeile 363–367 (`spec_file` gesetzt + `spec_approved`). Hier kommt der
  zusätzliche ADR-Feld-Check hin.
- **Test-Muster (KEINE Mocks):** `tests/tdd/test_issue_811_renderer_gate.py` — echtes tmp-Git-Repo,
  Gate per Subprocess, `git add`/`git diff --cached`.

## Entscheidungsflächen (Start-Heuristik, config-overridebar)

`src/outputs/*`, `src/output/renderers/*`, `docs/reference/decision_matrix.md`, `src/providers/*`,
Metrik-`selectable`-Pfade, `.claude/hooks/*_gate.py`.

## Scope

Reines `.claude/hooks/`-Tooling + Template + Config. Kein `src/`/Go/SvelteKit → docs/tooling-only,
kein Staging-/Prod-Deploy-Pfad.
