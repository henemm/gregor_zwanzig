---
entity_id: issue_325_session_binding
type: infra
created: 2026-05-24
updated: 2026-05-24
status: draft
version: "1.0"
tags: [workflow, hooks, session-binding, resolver, issue-325, issue-332, issue-258]
---

<!-- Issue #325 — Sanierung der Workflow-/Session-Buchführung: eine Quelle der Wahrheit -->

# Issue #325 — Session-Binding: eine zuverlässige Auflösung statt stiller Rate-Fallbacks

## Approval

- [ ] Approved

## Zweck

Die Auflösung „welcher Workflow gehört zu dieser Session" passiert heute über **drei uneinige Pfade** mit **stillen Rate-Fallbacks**. Dadurch landete am 2026-05-23 ein User-Keyword (`freigegeben`) auf dem falschen Workflow (`bug_329` statt der Session-Aufgabe). Dieser Fix vereinheitlicht alle Pfade auf **eine zuverlässige Methode** — Session-Registry (`session_workflows.json`) → optionaler `GZ_ACTIVE_WORKFLOW`-Override → sonst „kein aktiver Workflow" — und **entfernt die stillen Fallbacks** (`.active`-Symlink als Auflösungsquelle, „erster nicht-archivierter Workflow" in der Aggregation). Das `scope_guard.py`-Muster macht es bereits richtig und dient als Vorbild.

## Quelle / Source

**Wurzelursache (Analyse in #325-Kommentaren, 2026-05-23):**
Keyword-Kette `workflow_state_updater.py` → `workflow_state_multi._aggregate_state()` → `workflow.py:_active_name()`. Wenn `_active_name()` `None` liefert, greift in `_aggregate_state()` der **undokumentierte Fallback „erster nicht-archivierter Workflow"** → falscher Treffer.

**Geänderte Dateien (reine Hook-/Tooling-Schicht, KEIN Produktiv-Code):**
- `.claude/hooks/workflow.py` — `_active_name()`: Symlink NICHT mehr als Auflösungsquelle lesen (Reihenfolge: Session-Registry → `GZ_ACTIVE_WORKFLOW` → `None`); `cmd_status()`: „resolved via .active symlink"-WARNING entfernen.
- `.claude/hooks/workflow_state_multi.py` — `_aggregate_state()`: stillen „erster nicht-archivierter"-Fallback entfernen; `active_workflow` spiegelt ausschließlich `_active_name()`.
- `.claude/hooks/workflow_state_updater.py` — aktiven Workflow DIREKT über die Session-Registry der **aufrufenden** Session auflösen (nicht über `_aggregate_state()`); ohne gebundenen Workflow KEIN Keyword-Effekt.
- `.claude/hooks/scope_guard.py` — bereits korrekt; bei Bedarf als kanonischer Resolver wiederverwenden (read-only Referenz / DRY).

**Bewusst NICHT geändert:** Der `.active`-Symlink wird weiterhin von `cmd_start`/`cmd_switch` geschrieben und von `cmd_complete` aufgeräumt (Lifecycle), damit die bestehenden #258/#333-Tests grün bleiben. Er ist nur keine **Auflösungsquelle** mehr.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/scope_guard.py` | Hook (Vorbild) | Korrektes Resolver-Muster: Registry → Env, kein Symlink, kein Aggregations-Fallback |
| `.claude/session_workflows.json` | Registry | `session_id → workflow_name`; die einzige Wahrheitsquelle |
| `.claude/hooks/workflow.py` | Hook | `_active_name`, `read_active_workflow_fast`, `cmd_status` |
| `.claude/hooks/workflow_state_multi.py` | Hook | `_aggregate_state`, `load_state`, `get_active_workflow` |
| `.claude/hooks/workflow_state_updater.py` | Hook | UserPromptSubmit-Keyword-Routing |
| Issue #332 | GitHub | Teil-Fix Approval-Hook-Session-ID (Keyword-Routing griff trotzdem daneben) |
| Issues #258/#333 | GitHub | Symlink-Lifecycle-Tests — müssen grün bleiben |

## Implementation Details

### Kanonische Auflösungs-Reihenfolge (überall identisch)
1. Session-ID aus `GZ_HOOK_SESSION_ID` bzw. `CLAUDE_CODE_SESSION_ID` → Lookup in `session_workflows.json`.
2. Sonst `GZ_ACTIVE_WORKFLOW` (Override, Rückwärtskompatibilität).
3. Sonst **`None`** — kein Raten, kein Symlink, kein „erster Workflow".

### Keyword-Routing (`workflow_state_updater.py`)
Liest die Session-ID aus stdin (bereits vorhanden, Z. 88–98), löst den gebundenen Workflow DIREKT über die Registry auf und wendet das Keyword **nur** darauf an. Ohne Bindung: nichts tun (kein Phasen-Sprung an fremden Workflows).

### Risiko-Mitigation (Selbst-Referenz)
Diese Hooks werden von ~12 anderen Hooks JEDER Tool-Aktion gelesen — der Umbau verändert das Verhalten der eigenen Session. Vorgehen: Tests zuerst (RED), Implementierung inkrementell, nach JEDER Änderung die Testdatei laufen lassen. Ein Python-Fehler in diesen Hooks endet mit Exit 1 (nicht-blockierend) → erkennbar und per `git checkout` rücksetzbar. Entwicklung im ruhigen Fenster (keine zweite Session am geteilten Baum — vom PO bestätigt).

## Expected Behavior

- **Input:** Zwei Sessions A (gebunden an `wf-a`) und B (gebunden an `wf-b`); A tippt ein Keyword.
- **Output:** Das Keyword wirkt ausschließlich auf `wf-a`. Existiert daneben ein dritter, „erster" nicht-archivierter Workflow, bleibt der unberührt.
- **Side effects:** Keine. Bei fehlender Session-Bindung: kein aktiver Workflow, kein Keyword-Effekt (statt falschem Treffer).

## Acceptance Criteria

- **AC-1:** Given Session-Registry leer und `GZ_ACTIVE_WORKFLOW` ungesetzt, aber ein `.active`-Symlink zeigt auf `wf-x` / When `_active_name()` (bzw. `read_active_workflow_fast()`) aufgerufen wird / Then ist das Ergebnis `None` (der Symlink ist KEINE Auflösungsquelle mehr) — kein FATAL, kein `wf-x`.
  - Test: (populated after /4-tdd-red)

- **AC-2:** Given mehrere nicht-archivierte Workflows existieren, Session-Registry trifft nicht, `GZ_ACTIVE_WORKFLOW` ungesetzt / When `workflow_state_multi.get_active_workflow()` / `_aggregate_state()` aufgerufen wird / Then ist `active_workflow` `None` (KEIN stiller „erster nicht-archivierter"-Fallback).
  - Test: (populated after /4-tdd-red)

- **AC-3:** Given `session_workflows.json` bindet Session-ID `S_A→wf-a`, und `wf-b` ist als „erster" Workflow vorhanden / When `workflow_state_updater.py` mit `session_id=S_A` und Keyword `approved` läuft (Phase von `wf-a` = phase3_spec) / Then wird ausschließlich `wf-a` auf phase4_approved gesetzt; `wf-b` bleibt unverändert.
  - Test: (populated after /4-tdd-red)

- **AC-4:** Given keine Session-Bindung und keine `GZ_ACTIVE_WORKFLOW` / When `workflow_state_updater.py` ein Keyword empfängt / Then wird KEIN Workflow verändert (kein Phasen-Sprung an einem fremden Workflow).
  - Test: (populated after /4-tdd-red)

- **AC-5:** Given die bestehenden Symlink-Lifecycle-Tests aus #258/#333 (`tests/tdd/test_issue_258_hook_arch.py`) / When der Fix angewandt ist / Then bleiben sie grün (cmd_start/cmd_switch schreiben, cmd_complete räumt den Symlink weiterhin auf — nur als Lifecycle, nicht als Resolver).
  - Test: (populated after /4-tdd-red)

- **AC-6:** Given Bestandsverhalten mit gesetzter `GZ_ACTIVE_WORKFLOW` / When eine Session arbeitet / Then löst sie korrekt auf diesen Workflow auf (Override-Vorrang bleibt, Rückwärtskompatibilität).
  - Test: (populated after /4-tdd-red)

- **AC-7:** Given Produktiv-Code in `src/`, `api/`, `internal/`, `frontend/`, `cmd/` / When der Fix abgeschlossen ist / Then ist dieser zeichengleich zur Pre-Fix-Version (Änderung nur in `.claude/hooks/` + Tests + Spec).
  - Test: (populated after /4-tdd-red)

## Known Limitations

- Der `.active`-Symlink bleibt als Lifecycle-Artefakt bestehen (Schreiben/Aufräumen), um #258/#333 nicht zu brechen — er hat nur keine Auflösungsfunktion mehr. Ein vollständiges Entfernen des Symlinks wäre ein separater Aufräum-Schritt.
- `GZ_ACTIVE_WORKFLOW` bleibt als Override erhalten (Rückwärtskompatibilität), ist aber nicht mehr nötig.

## Out of Scope

- Vollständiges Entfernen des `.active`-Symlinks inkl. Lifecycle (separater Aufräum-Auftrag).
- Änderungen an Produktiv-Code (`src/`, `api/`, `internal/`, `frontend/`, `cmd/`).
- Neuerstellung der ~12 importierenden Gate-Hooks — sie profitieren automatisch von der korrigierten zentralen Auflösung.

## Changelog

- 2026-05-24: Initial spec. Vereinheitlicht die Workflow-/Session-Auflösung auf Registry→Env→None (Vorbild `scope_guard.py`), entfernt die stillen Fallbacks (Symlink-Resolver + „erster nicht-archivierter"-Aggregation), routet User-Keywords ausschließlich auf den Session-gebundenen Workflow. Reine Hook-Schicht, kein Produktiv-Code.
