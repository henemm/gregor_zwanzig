---
entity_id: issue_666_e2e_verified_retention_tests
type: tests
created: 2026-06-08
updated: 2026-06-08
status: draft
version: "1.0"
tags: [tests, tooling, e2e-gate, retention, issue-666]
parent: issue_666_e2e_verified_retention
phase: phase5_tdd_red
---

# Issue #666 — E2E-Verified Retention (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für Issue #666 (Retention des commit-getaggten Attestation-Verzeichnisses
`.claude/e2e_verified/<sha>.json`). Jeder Eintrag mappt einen pytest-Funktionsnamen
auf das in der Parent-Spec definierte Acceptance-Criterion, damit der
Spec-Enforcement-Hook die Test-Entities auflösen kann.

Parent-Spec: `docs/specs/modules/issue_666_e2e_verified_retention.md`.

## Source

- **Files:**
  - `tests/tdd/test_e2e_verified_retention.py` (NEU — mock-frei)
- **Implementierung:** `.claude/hooks/staging_gate.py` (`prune_old_attestations`, `write_verdict`)

## Test Inventory

Alle Tests laufen gegen die echten Hooks, ein echtes temporäres Git-Repo und echte
Dateien — `REPO_DIR`/`CANONICAL_E2E_PATH` werden per monkeypatch auf das Temp-Repo
umgebogen (realer Pfad, KEIN Mock).

| Test-Funktion | AC | Was geprüft wird |
|---------------|----|------------------|
| `test_full_dir_keeps_exactly_retention_and_drops_oldest` | AC-1 | Bei 20 vorhandenen Attestationen + neuem Verdict bleiben genau 20 Dateien; die älteste (nach mtime) ist gelöscht, die neue HEAD-Datei existiert. |
| `test_under_limit_deletes_nothing` | AC-2 | Bei weniger als 20 Dateien wird nichts gelöscht — alle vorhandenen Dateien bleiben erhalten. |
| `test_gate_passes_after_pruning_on_full_dir` | AC-3 | Die HEAD-Attestation wird nie weggeprunt; `gate_check` liefert Exit 0 auch bei vollem Verzeichnis. |
| `test_undeletable_old_entry_does_not_fail_verdict` | AC-4 | Ein nicht löschbarer Alt-Eintrag (Verzeichnis statt Datei → echter `IsADirectoryError`/`OSError`) lässt `write_verdict` rc 0 zurückgeben; neue Attestation existiert. |

## Anti-Mock-Nachweis

- Echtes Temp-Git-Repo via `git init` + echte Commits (Backend-Scope), keine Mock-Objekte.
- AC-1/2: reale Dateien mit explizit gesetzten mtimes (`os.utime`) — beweist das echte
  Sortier-/Lösch-Verhalten auf der Platte.
- AC-3: realer `gate_check`-Aufruf gegen die echte Attestation.
- AC-4: realer Filesystem-Fehler (Verzeichnis-Eintrag namens `<sha>.json` → `unlink()`
  wirft `IsADirectoryError`) statt eines Mocks.

## Changelog

- 2026-06-08: Initial test manifest (Issue #666) — alle 4 AC-Tests grün, mock-frei, Adversary VERIFIED.
