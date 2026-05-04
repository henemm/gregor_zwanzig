# Context: E2E Commit Gate — Auto-Scope Detection (#86)

## Request Summary

Der E2E Commit Gate Hook soll den Verifikations-Scope automatisch aus den gestageten Dateien ableiten, statt immer den vollen Backend-E2E-Flow zu erzwingen. Reine Frontend-Commits brauchen keinen IMAP-Check.

## Related Files

| File | Relevanz |
|------|----------|
| `.claude/hooks/e2e_commit_gate.py` | Hauptdatei — wird angepasst |
| `.claude/commands/e2e-verify.md` | Slash-Command — Schritt 6 muss `scope` ins JSON schreiben |
| `.claude/e2e_verified.json` | Ausgabe-Datei — bekommt neues `scope`-Feld |
| `tests/tdd/test_e2e_scope_detection.py` | Bestehende Tests für `detect_scope()` (7 Tests, alle GRÜN) |

## Aktueller Stand (partiell implementiert)

In der letzten Session wurde bereits hinzugefügt:
- `detect_scope()` — klassifiziert gestagete Dateien in `frontend-only`, `backend`, `full-stack`, `docs-only`
- `SCOPE_LEVEL` — numerische Hierarchie der Scopes
- `REQUIRED_BY_SCOPE` — welche JSON-Felder pro Scope nötig sind

**Noch NICHT implementiert:**
- `check_verification()` nutzt noch den alten `feature_type == "ui_only"` Check statt `REQUIRED_BY_SCOPE[scope]`
- Scope-Vergleich: verifizierter Scope vs. erkannter Commit-Scope fehlt
- `e2e-verify.md` Schritt 6 schreibt noch kein `scope`-Feld

## Existing Patterns

- `e2e_verified.json` wird von `/e2e-verify` geschrieben und vom Hook gelesen
- Hook läuft als `PreToolUse` auf `git commit` Befehle
- `user_override: true` im JSON überspringt den Gate vollständig

## Scope-Klassifikation (laut Issue)

| Geänderte Pfade | Scope | Pflicht-Gates |
|-----------------|-------|---------------|
| Nur `frontend/` | `frontend-only` | `server_restarted` |
| `src/`, `api/` | `backend` | `server_restarted`, `test_trip_created`, `emails_checked`, `test_trip_cleaned` |
| Beides | `full-stack` | alle |
| `docs/`, `.claude/`, `*.md` | `docs-only` | Gate wird übersprungen |
| Unbekannte Pfade | `backend` (konservativ) | alle |

## Dependencies

- **Upstream:** `git diff --cached --name-only` (subprocess)
- **Downstream:** `/e2e-verify` Command muss `scope`-Feld schreiben

## Risks & Considerations

- **Backward-Kompatibilität:** Bestehende `e2e_verified.json` ohne `scope`-Feld — Hook muss das tolerieren (konservative Fallback-Strategie)
- **Scope-Eskalation:** Wenn Developer Agent nebenbei Backend-Code ändert, steigt Scope zu `full-stack` — das ist gewünscht
- `.claude/hooks/` ist in `docs-only` als neutral klassifiziert — Hook-Änderungen blockieren den Gate nicht (sinnvoll)
