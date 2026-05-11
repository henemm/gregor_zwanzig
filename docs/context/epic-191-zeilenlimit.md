# Context: epic-191-zeilenlimit

## Request Summary

`scope_guard.py` wird um LoC-Delta-Check erweitert: Bei Code-Edit prüft der Hook `git diff HEAD --numstat`, summiert Insertions+Deletions, blockiert bei >250 LoC (Default). Exclude-Patterns für generierte Dateien. Override per `loc_limit_override` im State. `workflow.py status` zeigt aktuellen Delta.

## Realitäts-Check

| Punkt | Status |
|-------|--------|
| `scope_guard.py` existiert (203 LoC) | ✓ |
| Macht Path-Scope-Check (allowed_paths), KEIN LoC-Delta | ✓ |
| In `settings.json` registriert | ✓ |
| `scope_guard`-Sektion in `openspec.yaml` | zu prüfen |

**Strategie:** scope_guard.py erweitern, nicht ersetzen. Memory: "Code-Duplikate konsolidieren statt parallel fixen".

## Related Files

| File | Relevanz |
|------|----------|
| `.claude/hooks/scope_guard.py` | Hauptort — neue LoC-Check-Funktion |
| `.claude/hooks/workflow.py` | `cmd_status` zeigt aktuellen Delta |
| `.claude/hooks/config_loader.py` | Helper `get_scope_loc_config()` |
| `openspec.yaml` | Neue Sektion `scope_guard.max_loc_delta` + `loc_exclude_patterns` |
| `tests/tdd/test_epic_191_zeilenlimit.py` | Neue Tests |

## Existing Patterns

- Hook-Struktur: stdin JSON → check → exit 0/2 (wie alle Edit/Bash-Gates)
- `git diff HEAD --numstat`: bewährter Subprocess-Call
- Override-Pattern (analog zum AMBIGUOUS-Override aus Workflow E-Plan): Workflow-State-Field `loc_limit_override: <int>`

## Dependencies

- **Upstream:** `subprocess` (git diff), `re` (exclude-pattern-match), `config_loader.load_config()`
- **Downstream:** Alle Phase-6-Edit-Aktionen, `workflow.py status`-Ausgabe

## Existing Specs

- `docs/specs/modules/epic_191_state_migration.md` — `workflow.py status` ist dort definiert
- `docs/specs/modules/epic_191_logbuch_audit.md` — `phase_transitions`-Pattern zeigt, wie State-Felder verwaltet werden

## Risks & Considerations

| Risiko | Mitigation |
|--------|-----------|
| **`git diff HEAD --numstat` ist langsam (Subprocess)** | Bei jedem Edit aufgerufen — bei großen Repos potenziell ~100ms. Akzeptabel, da Edits eh sequentiell. |
| **Generierte Dateien (.po, .xcstrings, package-lock.json) blasen Delta auf** | `loc_exclude_patterns` in openspec.yaml — Regex pro Pattern |
| **Workflow A war 635 LoC, Workflow B 222** | Default 250 wäre für solche Workflows zu klein. Override-Mechanismus ist Pflicht: `workflow.py set-field loc_limit_override <N>` |
| **Beim Anwenden auf bestehende, große Workflows brechen viele Edits** | Workflow-spezifisch via `loc_limit_override`. Auch: `--bypass` Pattern (override-token) sollte das deckeln können. |
| **Was ist "HEAD" bei untracked files?** | `git diff HEAD --numstat` zeigt nur modified files, nicht untracked. Untracked werden vollständig als "new" gezählt (über `git diff --no-index /dev/null <file>` oder pragmatisch ignoriert). |
| **Negativer Delta nach Rollback** | Insertions+Deletions sind beide positiv, Summe ist immer >= 0 |

## Out of Scope

- Pre-commit Hook-Integration (separater Issue)
- LoC-Tracking pro Datei (nur Gesamt-Delta)
- Graphical Dashboard
