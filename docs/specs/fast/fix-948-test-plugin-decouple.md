# Mini-Spec: Test #948 vom Plugin-Hook entkoppeln

## Problem
`tests/tdd/test_issue_948_e2e_allowed_dir.py` importiert `edit_gate` via
`sys.path.insert(REPO_ROOT/.claude/hooks)`. `edit_gate.py` ist seit der
Hook→Plugin-Migration nicht mehr im Repo → `ModuleNotFoundError: edit_gate`
→ Collection-Error, der JEDEN vollständigen `tests/tdd/`-Lauf abbricht.
Isoliert (nur diese Datei), fremdverursacht (Commit b1a5f55e, #948).

## Was ändert sich
- Der Test verliert die Abhängigkeit vom Plugin-internen `edit_gate.ALWAYS_ALLOWED_DIRS`.
- Er prüft nur noch die **im Repo** liegende Garantie (Quelle: `openspec.yaml`
  → `strict_code_gate.always_allowed_dirs`):
  1. `e2e/` ist in der Allowlist (der #948-Bugfix bleibt bewacht).
  2. `tests/` (und Geschwister) sind in der Allowlist.
  3. `src/` ist NICHT in der Allowlist → Programmcode bleibt gate-pflichtig (kein Schutzverlust).
- Datei nach Verhalten umbenennen: `tests/tdd/test_code_gate_allowed_dirs.py`
  (weg vom Issue-Nummern-Korpus; test_naming_gate erlaubt Nicht-Issue-Namen).

## Was darf sich nicht ändern
- Die drei geprüften Garantien (e2e/ erlaubt, tests/ erlaubt, src/ gate-pflichtig) bleiben inhaltlich erhalten.
- `openspec.yaml` bleibt unverändert (nur der Test wird angepasst).
- Kein anderer Test wird berührt.

## Manuelle Test-Schritte
1. `uv run pytest tests/tdd/ --co -q` → Collection läuft ohne Error durch (vorher: abgebrochen).
2. `uv run pytest tests/tdd/test_code_gate_allowed_dirs.py -v` → grün.

## Inline-Test (Verhalten)
- [ ] Neuer/umbenannter Test lädt `openspec.yaml`, asserted e2e/+tests/ erlaubt und src/ nicht erlaubt, ohne Plugin-Import.

## Kein Deploy
Reine Test-Änderung (kein src/api/internal/frontend/cmd). Push nach main genügt, kein Staging/Prod.
