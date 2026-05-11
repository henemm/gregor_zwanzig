# Context: epic-191-logbuch-audit

## Request Summary

Nach jedem abgeschlossenen Workflow wird automatisch ein YAML-Logbuch geschrieben (`.claude/workflows/_log/YYYY-MM-DD_<name>.yaml`). Phase-Transitions werden mit `from`/`to`/`at`/`trigger` festgehalten, der Fix-Loop-Counter (`phase6b → phase6`) zählt Adversary-Schleifen.

## Realitäts-Check (was schon da ist)

Beim Umbau in Workflow A (#192) hat der Developer Agent bereits eingebaut:

| Bestandsfeld | Wo | Status |
|--------------|-----|--------|
| `phase_transitions[]` | State pro Workflow, Default `[]` | ✓ vorhanden |
| `fix_loop_iterations` | State pro Workflow, Default `0` | ✓ vorhanden |
| Auto-Log bei `cmd_phase` | `.claude/hooks/workflow.py:484-494` | ✓ loggt mit `trigger: "command"` |
| Auto-Log bei `cmd_advance` | `.claude/hooks/workflow.py:512-518` | ✓ loggt mit `trigger: "advance"` |
| Fix-Loop-Counter | `cmd_phase` Zeile 493-494 | ✓ inkrementiert automatisch bei phase6b→phase6 |

Bestätigung im Live-Workflow A: `fix_loop_iterations: 1` wurde korrekt gesetzt (manuell, aber auch durch `cmd_phase` würde es ausgelöst).

**Heißt:** Issue #193 ist zu ~50% schon erfüllt. Was fehlt:

1. `cmd_write_log` — schreibt YAML in `_log/`
2. `cmd_complete` muss bei fehlendem Log blockieren
3. `cmd_status` muss Fix-Loop-Counter + Transitions-Count anzeigen
4. Transition-Logging beim Wrapper-Pfad: Wenn `set_phase()` über `workflow_state_multi`-API aufgerufen wird (statt CLI), läuft das auch durch `workflow.py cmd_phase`? Zu prüfen.

## Related Files

| File | Relevanz |
|------|----------|
| `.claude/hooks/workflow.py` | Hauptort der Änderung — neue `cmd_write_log`, erweiterte `cmd_complete` + `cmd_status` |
| `.claude/hooks/workflow_state_multi.py` | Thin-Wrapper — `set_phase()` muss Transition loggen, ggf. an `cmd_phase` delegieren |
| `.claude/hooks/workflow_state_updater.py` | Setzt phase auf `phase4_approved` bei "approved"-Keyword — muss Transition mit `trigger: "user_keyword"` loggen |
| `tests/tdd/test_epic_191_state_migration.py` | Vorbild für Test-Struktur (Fixture-Pattern, fake_repo) |
| `/tmp/aos_workflow.py` | Vorbild für `cmd_write_log` (sed-extrahiert Zeile 339-378) |

## Reference Implementation (agent-os-openspec)

`cmd_write_log` in `/tmp/aos_workflow.py:339-378` schreibt YAML mit:
- `workflow_id`, `project`, `completed_at`
- `phases_completed[]` (aus phase_transitions abgeleitet), `phases_skipped[]`
- `override_used`, `tdd_red_confirmed`, `adversary_verdict`
- `adversary_findings_total`, `adversary_fix_loop_iterations`
- `scope_files_changed`, `scope_loc_delta`, `outcome`

`cmd_complete` in `/tmp/aos_workflow.py:388-405` blockt bei fehlendem Log:
```python
log_dir = find_project_root() / ".claude" / "workflows" / "_log"
if not (log_dir.exists() and any(log_dir.glob(f"*_{name}.yaml"))):
    print(f"BLOCKED: No execution log for '{name}'. Run: workflow.py write-log [outcome]")
    sys.exit(1)
```

## Existing Patterns

- **Atomare Writes:** `_atomic_write` in workflow.py — auch für YAML-Log nutzen
- **Worktree-Routing:** `_get_workflows_root()` → wir nutzen unsere bestehende Worktree-aware Variante (Issue #112 bleibt intakt)
- **Test-Fixtures:** `fake_repo`/`fake_worktree` aus `test_epic_191_state_migration.py` wiederverwenden

## Dependencies

- **Upstream:** `pathlib.Path`, `datetime`, ggf. `yaml` (PyYAML 6.0.1 verfügbar) oder reines Text-Building wie im Vorbild
- **Downstream:** Slash-Commands `workflow.md` und `0-reset.md` (rufen `complete` auf); `workflow_state_updater.py` (setzt phase4_approved); 9 Hooks die State lesen

## Existing Specs

- `docs/specs/modules/epic_191_state_migration.md` — Workflow A, Vorgänger; Felder `phase_transitions` und `fix_loop_iterations` bereits dort schemaweit eingeplant

## Risks & Considerations

| Risiko | Mitigation |
|--------|-----------|
| **Bestehende ~45 archivierte Workflows haben kein Log** | Logbuch-Pflicht greift nur für **neue** `complete`-Aufrufe — Archive bleiben unverändert. Migration nicht nötig. |
| **YAML-Output uneinheitlich (PyYAML vs. Text-Building)** | PyYAML 6.0.1 ist verfügbar — saubere Serialisierung. Aber Vorbild macht Text-Building wegen Lesbarkeit. Entscheidung in Spec-Phase. |
| **Transition-Logging bei direkten `workflow_state_multi.set_phase()`-Calls** | Aktuell delegiert der Wrapper. Aber muss explizit getestet werden, dass `set_phase("workflow", "phase4_approved")` über CLI/Wrapper → cmd_phase → Transition-Log läuft. |
| **`approved`-Keyword von workflow_state_updater.py loggt aktuell mit `trigger: "command"` statt `"user_keyword"`** | Klein, aber für saubere Forensik wichtig. Updater muss expliziten Trigger setzen können. |
| **`complete` blockt → Tests müssen Log-Erzeugung mitmachen** | Test-Fixtures müssen `write-log` vor `complete` aufrufen. |
| **YAML-File-Naming `YYYY-MM-DD_<name>.yaml`** | Was wenn am selben Tag 2x derselbe Workflow abgeschlossen wird? — Unrealistisch, aber `complete` archiviert; ein zweites complete würde dann auf `_archive/` zugreifen wollen. Edge-Case in Spec-Phase. |

## Out of Scope

- Migration alter archivierter Workflows in YAML-Logs
- Dashboard/Report über `_log/` (kann später kommen)
- Vergleichende Statistik über alle Workflows

## Analyse-Ergebnisse (Phase 2)

### Wichtige Befunde aus Explore-Agents

1. **`workflow_state_updater.py:120` setzt Phase direkt im Dict** — umgeht damit das Transition-Logging in `cmd_phase`. **Muss auf `set_phase()`-API umgestellt werden.**
2. **4 Aufrufer von `complete`** identifiziert. Sicherheits-Logik muss in `cmd_complete` UND `cmd_phase` (für phase8_complete-Sprung) sitzen. User-Hook bei "deployed" ruft auto-write-log vor complete.

### Empfehlung

1. `cmd_write_log` schreibt YAML mit Pflichtfeldern
2. `cmd_complete` blockt ohne Log
3. `cmd_phase phase8_complete` blockt ohne Log (Bypass-Schutz)
4. `cmd_status` zeigt fix_loop_iterations + transitions-count
5. `workflow_state_updater.py` Patch: set_phase statt Dict-Edit, auto write-log vor complete
6. Trigger-Vokabular: command | advance | user_keyword | manual

### Scope

- workflow.py: +150 LoC, workflow_state_updater.py: +30/-10, Wrapper: +10, Tests: +180. **Gesamt ~360 LoC.**

### Risiken

- R1: User sagt "deployed" ohne Adversary → Log mit outcome:incomplete, kein harter Block
- R2: Archive ohne Log bleiben unverändert (kein Nachholz)
