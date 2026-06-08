# Context: E2E-Verified Retention (Issue #666)

## Request Summary
Das Verzeichnis `.claude/e2e_verified/<sha>.json` (eingeführt mit #662) wächst
monoton — pro verifiziertem Commit eine Datei, die nie aufgeräumt wird. Ziel:
Retention analog `.backups/`-Pattern, sodass nur die letzten N (≈20) Dateien
bleiben, ohne Gate/Deploy zu beeinflussen.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/staging_gate.py` | `write_verdict()` schreibt die `<sha>.json` — hier muss nach dem Schreiben geprunt werden |
| `.claude/hooks/_e2e_paths.py` | `commit_e2e_path()` liefert den Verzeichnis-/Dateipfad |
| `.claude/hooks/data_schema_backup.py` | `prune_old_backups()` (`RETENTION=20`, sort by mtime desc, `unlink()` ab Index N) — Vorbild |
| `.claude/hooks/prod_selftest.py` | liest nur die HEAD-passende Datei (Default-Pfad-Auflösung) — Retention darf das nicht stören |
| `tests/tdd/test_e2e_commit_namespacing.py` | Test-Pattern: echtes Temp-Git-Repo, `REPO_DIR` monkeypatchen, echte Hook-Funktionen, keine Mocks |

## Existing Patterns
- **Retention (`data_schema_backup.py::prune_old_backups`):** `sorted(glob, key=mtime, reverse=True)`, dann `for old in files[RETENTION:]: old.unlink()` mit `OSError`-Guard. `RETENTION = 20`.
- **Pfad-Auflösung beim Lesen:** Gate/Selftest lesen ausschließlich die zum aktuellen HEAD passende `<sha>.json` (oder Singleton-Fallback). Ältere Dateien sind reine Historie → gefahrlos löschbar.
- **Schreiben (`write_verdict`):** `e2e_path.parent.mkdir(...)` + `write_text(...)`, danach wäre der natürliche Punkt für das Pruning.

## Dependencies
- **Upstream:** `write_verdict()` wird vom `staging-validator`-Agent via `staging_gate.py --write-verdict` aufgerufen.
- **Downstream:** Gate-Check (`deploy-gregor-prod.sh`) und `prod_selftest.py` lesen nur die HEAD-Datei → Retention beeinflusst sie nicht, solange die HEAD-Datei nie geprunt wird (sie ist immer die jüngste).

## Existing Specs
- `docs/specs/modules/issue_662_e2e_commit_namespacing.md` — Mutter-Spec (commit-getaggte Attestation)

## Risks & Considerations
- **HEAD-Datei nie löschen:** Die gerade geschriebene Datei ist die jüngste (mtime), liegt also immer in `files[:RETENTION]` → nie geprunt. Solange RETENTION ≥ 1, sicher.
- **Pruning darf nie den Verdict-Exit-Code kippen:** Fehler beim Löschen (`OSError`) werden geschluckt — Verdict-Schreiben bleibt erfolgreich.
- **Reihenfolge:** Erst neue Datei schreiben, dann prunen — sonst könnte bei N+1 die neue Datei mitgezählt aber noch nicht geschrieben sein.
- **Nur das getaggte Verzeichnis prunen,** nicht den Singleton `.claude/e2e_verified.json` (Migrations-Fallback).
