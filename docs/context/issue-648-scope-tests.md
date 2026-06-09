# Context: Issue #648 — detect_scope() klassifiziert `tests/` als has_backend

## Request Summary
Dateien unter `tests/` landen in der Scope-Erkennung im else-Zweig und werden
konservativ als `has_backend=True` gewertet, statt neutral behandelt zu werden.
Folge: Ein Commit, der **nur** Test-Dateien ändert, wird als `backend`
klassifiziert und erzwingt fälschlich Staging-/Deploy-Gate-Aufwand, obwohl
`tests/` nie ein Prod-Artefakt ist.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/e2e_commit_gate.py` (`detect_scope`, Z.48-94) | Im Issue genannte Funktion. Informationell (Hook „immer Exit 0", Z.11) — klassifiziert nur. |
| `.claude/hooks/staging_gate.py` (`_detect_committed_scope`, Z.73-115) | **Identischer Bug, real konsequent:** `gate_check()` (Z.187-190) überspringt das Deploy-Gate bei `docs-only`. Hier entscheidet die Klassifikation tatsächlich. |
| `tests/tdd/test_e2e_scope_detection.py` | Bestehende Tests für `detect_scope()` (7 Stück) — **gemockt** via `monkeypatch.setattr(subprocess, "run")`. Neue Tests mock-frei (echtes Temp-Git-Repo). |

## Existing Patterns
- Beide Funktionen klassifizieren `git diff --name-only` in 4 Scopes:
  `frontend-only | backend | full-stack | docs-only`.
- Neutrale Pfade (kein has_*-Flag): `docs/`, `.claude/`, `*.md`, `README`,
  `.gitignore` (nur staging_gate). `tests/` fehlt in beiden neutralen Zweigen.
- Deployte Artefakte: Go-Binary (`cmd/`, `internal/`, `api/`), Frontend-Build
  (`frontend/`), Python-Service (`src/`). **`tests/` wird nie deployed.**

## Dependencies
- Upstream: `git diff` Output (gestagte bzw. HEAD~1..HEAD Dateien).
- Downstream: `staging_gate.gate_check()` (Deploy-Hard-Gate), `write_verdict()`
  (Scope-Feld in `e2e_verified.json`), informationelle Ausgabe in e2e_commit_gate.

## Existing Specs
- Kein eigenes Spec-Modul. Tooling-Hook, Verhalten dokumentiert im Docstring.

## Risks & Considerations
- **Korrektheit der Semantik:** `tests/`-only-Commit → `docs-only` → Staging-Gate
  übersprungen, kein Prod-Deploy-Zwang. Sicher, da Tests nie in Prod laufen.
- **Gemischter Commit** (`src/` + `tests/`) bleibt `backend` — `src/` triggert,
  `tests/` neutral. Kein Verlust an Schutzwirkung.
- **Konsistenz:** Beide Funktionen fixen, sonst divergieren die Klassifikationen
  (informationeller Hook vs. Deploy-Gate würden unterschiedlich entscheiden).
- Tooling-only-Change (`.claude/hooks/`) → kein Prod-Deploy nötig (außer Drift).
