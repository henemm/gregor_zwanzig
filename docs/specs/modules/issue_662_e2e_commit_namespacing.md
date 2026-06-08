---
entity_id: issue_662_e2e_commit_namespacing
type: module
created: 2026-06-08
updated: 2026-06-08
status: draft
version: "1.0"
tags: [infra, tooling, e2e-gate, race-hardening]
---

# E2E-Gate Race-Hardening: Attestation pro Commit

## Approval

- [ ] Approved

## Purpose

Die E2E-Attestation wird nicht mehr in ein geteiltes Singleton
(`.claude/e2e_verified.json`), sondern unter einem nach dem verifizierten Commit
benannten Pfad (`.claude/e2e_verified/<sha>.json`) abgelegt. Damit kollidieren
parallele Sessions nicht mehr — jede schreibt ihre eigene Datei, und das
Deploy-Gate liest genau die zum auszuliefernden HEAD passende Attestation.

## Source

- **File:** `.claude/hooks/staging_gate.py`
- **Identifier:** `CANONICAL_E2E_PATH`, `write_verdict()`, `gate_check()`, neuer Helper `_commit_e2e_path(sha)`
- **File:** `.claude/hooks/prod_selftest.py`
- **Identifier:** `CANONICAL_E2E_PATH`, `run_selftest()`, neuer Helper `_resolve_e2e_path()`

Schicht-Hinweis: Reine **Tooling-Hooks** (`.claude/hooks/`), kein Frontend/Backend-Produktcode.
Cross-Repo-Konsument: `henemm-infra/scripts/deploy-gregor-prod.sh` (bleibt unverändert,
ruft `staging_gate.py --check` ohne `--e2e-path`).

## Estimated Scope

- **LoC:** ~90 (beide Hooks + gitignore + 2 Doku-Stellen)
- **Files:** 5 (`staging_gate.py`, `prod_selftest.py`, `.gitignore`, `.claude/agents/staging-validator.md`, `.claude/commands/e2e-verify.md`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `git rev-parse HEAD` | extern | Anker für commit-getaggten Dateinamen (`_head_sha()`, existiert) |
| `pathlib` / `json` | stdlib | Pfad + Serialisierung (keine neue Dep) |
| `deploy-gregor-prod.sh` | Cross-Repo | ruft `--check`; bleibt unverändert; MQ-Info an `infra` |

## Implementation Details

```
Neuer Default-Pfad-Ableiter (beide Hooks):
  _commit_e2e_path(sha) -> REPO_DIR / ".claude" / "e2e_verified" / f"{sha}.json"

write_verdict (staging_gate):
  - schreibt nach _commit_e2e_path(_head_sha()), wenn kein --e2e-path Override
  - mkdir(parents=True, exist_ok=True) auf das Verzeichnis

gate_check / run_selftest (Default-Pfad-Auflösung, wenn kein --e2e-path):
  head = _head_sha()
  candidate = _commit_e2e_path(head)
  if candidate.exists(): use candidate
  elif CANONICAL_E2E_PATH.exists(): use CANONICAL_E2E_PATH   # Fallback (Migration)
  else: behandeln wie "fehlt" (Exit 1 bzw. docs-only-Skip greift vorher)

--e2e-path-Override: bleibt unverändert die explizite Datei (für Tests).

.gitignore:
  .claude/e2e_verified/        # zusätzlich zum bestehenden .claude/e2e_verified.json

Doku-Mitzug:
  - staging-validator.md Step 7: Artefakt-Pfad-Text auf commit-getaggt aktualisieren
  - e2e-verify.md Backend-Pfad: inline python3 -c schreibt commit-getaggt
    (oder Umstellung auf staging_gate.py --write-verdict)
```

## Expected Behavior

- **Input:** `git rev-parse HEAD` (Anker), optionaler `--e2e-path` Override.
- **Output:** Attestation unter `.claude/e2e_verified/<sha>.json`; Gate liest die zum HEAD passende.
- **Side effects:** Neues Verzeichnis `.claude/e2e_verified/` (gitignored, untracked, übersteht `git reset --hard`). Alte Singleton-Datei bleibt lesbar.

## Acceptance Criteria

- **AC-1:** Given zwei Sessions verifizieren parallel zwei verschiedene Commits (SHA-A, SHA-B), When beide `staging_gate.py --write-verdict` (ohne `--e2e-path`) aufrufen, Then existieren danach **beide** Dateien `.claude/e2e_verified/<SHA-A>.json` und `.claude/e2e_verified/<SHA-B>.json` intakt mit jeweils eigenem `verified_commit` — keine überschreibt die andere.
  - Test: Zwei echte `write_verdict`-Aufrufe mit zwei verschiedenen, vorab gesetzten HEAD-SHAs (echtes Git-Temp-Repo); danach beide Dateien lesen und `verified_commit` prüfen.

- **AC-2:** Given eine Attestation `.claude/e2e_verified/<HEAD>.json` mit `VERIFIED`-Verdict und `verified_at` < 24h existiert, When `staging_gate.py --check` (ohne `--e2e-path`) bei Non-docs-Scope läuft, Then leitet der Hook den Pfad selbst aus HEAD ab und gibt Exit 0.
  - Test: `write_verdict` für aktuellen HEAD, dann `gate_check` aufrufen, Exit 0 prüfen.

- **AC-3:** Given **nur** das alte Singleton `.claude/e2e_verified.json` existiert (kein commit-getaggtes Pendant), When `staging_gate.py --check` läuft und das Singleton `verified_commit == HEAD` + `VERIFIED` enthält, Then akzeptiert das Gate über den Fallback (Exit 0) — laufende Workflows brechen nicht.
  - Test: nur Singleton schreiben (kein `e2e_verified/`-Eintrag), `gate_check` → Exit 0; danach commit-getaggte Datei anlegen und prüfen dass diese vorrangig gelesen wird.

- **AC-4:** Given eine commit-getaggte Attestation für SHA-X existiert, aber HEAD steht auf SHA-Y (≠ X) und es gibt keine Attestation für SHA-Y (auch kein Singleton), When `staging_gate.py --check` bei Non-docs-Scope läuft, Then bricht es mit Exit 1 ab (klare Fehlermeldung „fehlt / veraltet") — eine fremde Session-Attestation darf einen anderen Commit nicht freischalten.
  - Test: Datei für SHA-X anlegen, HEAD auf SHA-Y setzen, `gate_check` → Exit 1.

- **AC-5:** Given dieselbe commit-getaggte Attestation für HEAD existiert, When `prod_selftest.py` (ohne `--e2e-path`) läuft, Then liest es dieselbe Datei wie das Gate (Commit-Attestation `HEAD == verified_commit` greift) — Gate und Selftest sind konsistent auf derselben Quelle.
  - Test: `write_verdict` für HEAD, dann `prod_selftest`-Pfadauflösung gegen dieselbe Datei prüfen (Commit-Attestation-Zweig erreicht, kein Commit-Mismatch-FAIL).

- **AC-6:** Given das Verzeichnis `.claude/e2e_verified/`, When `git status` läuft, Then ist es ignoriert (kein versehentliches Committen von Attestationen) und übersteht den `git reset --hard origin/main` des Deploy-Scripts als untracked.
  - Test: `.gitignore`-Eintrag wirkt (`git check-ignore .claude/e2e_verified/<sha>.json` → match).

- **AC-7:** Given der Backend-Pfad in `e2e-verify.md` schreibt die Attestation, When er ausgeführt wird, Then landet sie ebenfalls unter `.claude/e2e_verified/<HEAD>.json` (nicht im Singleton) — sonst bliebe die Backend-Race bestehen.
  - Test: Doku-Compliance-Check, dass der Backend-Schreibpfad commit-getaggt ist bzw. `staging_gate.py --write-verdict` nutzt (`# doc-compliance-test`).
