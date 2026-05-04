# Context: F86 E2E Commit Gate Scope

## Request Summary
Der E2E Commit Gate Hook soll den Verification-Scope automatisch aus `git diff --cached --name-only` ableiten, statt immer den vollen Flow (Trip + E-Mail) zu erzwingen.

## Related Files

| File | Relevance |
|------|-----------|
| `.claude/hooks/e2e_commit_gate.py` | **Hauptdatei** — Hook der bei `git commit` prüft |
| `.claude/e2e_verified.json` | State-Datei die vom `/e2e-verify` Skill geschrieben wird |

## Ist-Zustand

- Hook prüft bei jedem `git commit` ob `e2e_verified.json` existiert und < 2h alt ist
- Required fields: `server_restarted`, `test_trip_created`, `emails_checked`, `test_trip_cleaned`
- Es gibt bereits `feature_type: "ui_only"` (Zeile 91) mit reduziertem Check (`server_restarted` only)
- Aber: die Scope-Erkennung ist MANUELL — der Skill `/e2e-verify` muss das Feld setzen

## Soll-Zustand (aus Issue #86)

| Geänderte Pfade | Scope | Gates |
|-----------------|-------|-------|
| Nur `frontend/` | `frontend-only` | Playwright E2E + Vite Build |
| `src/`, `api/`, `internal/` | `backend` | pytest + Report senden + IMAP prüfen |
| Beides | `full-stack` | Alles |

## Implementation

Nur 1 Datei: `.claude/hooks/e2e_commit_gate.py`

Änderungen:
1. `git diff --cached --name-only` ausführen um staged files zu bekommen
2. Scope ableiten: frontend-only / backend / full-stack
3. Required fields je nach Scope anpassen
4. `e2e_verified.json` bekommt ein `scope` Feld das beim Verify geschrieben wird
5. Hook vergleicht: verifizierter Scope >= benötigter Scope

## Risks
- Scope-Erkennung muss korrekt sein — false negatives (Backend-Change als Frontend klassifiziert) wären gefährlich
- docs/, .claude/, tests/ Änderungen sollten keinen Full-Stack-Check auslösen
