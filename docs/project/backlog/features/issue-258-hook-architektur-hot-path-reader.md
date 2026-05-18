# Feature: Hook-Architektur: Hot-Path-Reader + cleanup-Kommando

**Status:** open
**Priority:** HIGH
**Category:** Infrastructure
**Mode:** ÄNDERUNG
**GitHub Issue:** #258

## What

Zwei Hook-Dateien (tdd_enforcement, workflow_gate), die bei jedem File-Edit ausgeführt werden, lesen derzeit 198 JSON-Dateien ein, obwohl sie nur eine einzige brauchen. Außerdem fehlt ein Weg, fertige Workflows nachträglich zu archivieren.

## Why

Ein Developer Agent hat einen Workflow durch direktes JSON-Edit abgekürzt und damit die Adversary-Verifikation übersprungen. Ursache: Der langsame, zu breite State-Lesevorgang erzeugt False-Positive-Blockaden, die Umgehungsversuche provozieren.

## Affected Systems

- `.claude/hooks/workflow_state_multi.py` — MODIFIED: neuer Helper `read_active_workflow_fast()` (+30 LOC)
- `.claude/hooks/tdd_enforcement.py` — MODIFIED: Import-Swap auf neuen Helper (±10 LOC)
- `.claude/hooks/workflow_gate.py` — MODIFIED: Import-Swap auf neuen Helper (±10 LOC)
- `.claude/hooks/workflow.py` — MODIFIED: `cmd_complete` mit optionalem Argument + neues `cmd_cleanup` (+50 LOC)
- Tests zu den 4 Dateien — MODIFIED/NEW: (+80 LOC)

## Scoping

- **Files:** 5
- **LOC estimate:** ~180 LOC
- **Complexity:** Medium
- **Within limits:** YES (250-LOC-Limit)

## Key Decisions (vom User vorentschieden)

1. Hot-Path-Hooks lesen nur `.active`-Datei (1 File-Read). `load_state()` bleibt unverändert.
2. `cmd_complete` akzeptiert optionalen Workflow-Namen; mit Argument: Warn-Banner, kein Abbruch.
3. Auto-Archive NUR bei `phase8_complete` (nicht bei `phase7_validate + VERIFIED`).
4. Separates `workflow.py cleanup` für Massen-Archivierung mit Bestätigungs-Prompt.

## Dependencies

- Keine externen Abhängigkeiten
- Worktree-Routing (`worktree_state_routing`) muss nach Änderung intakt bleiben

## Constraints

- Keine Test-Mocks (echte Temp-Dirs)
- Backward Compatibility v2-API erhalten
- Hook-Whitelist nicht anfassen

## Next Steps

1. `/2-analyse` starten (Phase 2: Codebase-Analyse)
2. Spec schreiben
3. User-Approval einholen
4. Implementieren

## Related

- `docs/specs/modules/worktree_state_routing.md`
- `.claude/hooks/workflow_state_multi.py`
- `.claude/hooks/workflow.py`
