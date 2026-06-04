---
entity_id: bug_workflow_gate_metrics
type: module
created: 2026-06-04
updated: 2026-06-04
status: draft
version: "1.0"
tags: [workflow, tooling, debug, metrics]
---

# Workflow Gate Metrics & Debug Logs

## Approval

- [ ] Approved

## Purpose

Macht den IST-Zustand der 3 User-Gates sichtbar: Wurde jedes Pflicht-Gate mit "go" freigegeben, oder wurde es per Befehl übersprungen? Ermöglicht Retrospektive (YAML-Log) und Live-Diagnose (neuer `workflow.py gates` Befehl) ohne bestehende Enforcement-Logik zu ändern.

## Source

- **Files:** `.claude/hooks/workflow.py`, `.claude/hooks/workflow_state_updater.py`
- **Typ:** Internes Tooling (kein Produktiv-Code in `src/`, `api/`, `frontend/`)

## Estimated Scope

- **LoC:** ~80
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `workflow.py` | modify | `write-log` + neuer `gates` Befehl |
| `workflow_state_updater.py` | modify | Debug-Ausgabe wenn "go" erkannt/nicht auslöst |

## Gate-Definitionen (SOLL)

| Gate-ID | Von Phase | Zu Phase | Pflicht? | Freigabe-Trigger |
|---------|-----------|----------|----------|-----------------|
| `analyse_summary` | `phase2_analyse` | `phase3_spec` | nein | user_keyword ("go") |
| `spec_approval` | `phase3_spec` | `phase4_approved` | **ja** | user_keyword ("go") |
| `deploy_approval` | `phase7_validate` | `phase8_complete` | **ja** | user_keyword ("go") |

## Implementation Details

### 1. `_compute_gate_history(transitions)` — neue Hilfsfunktion in `workflow.py`

Aus der `phase_transitions`-Liste:
- Für jedes Gate: finde die passende Transition (`from==X, to==Y`)
- Feld `status`:
  - `"user_approved"` wenn `trigger=="user_keyword"`
  - `"bypassed"` wenn Transition existiert aber `trigger != "user_keyword"` (Anomalie!)
  - `"not_reached"` wenn Transition fehlt
  - `"not_required"` für optionale Gates die nicht erreicht wurden

Rückgabe: Dict mit Gate-ID → `{status, trigger, at}` (at=None wenn not_reached)

### 2. `cmd_write_log` erweitern

`gate_history` Feld zum YAML-Log hinzufügen.

Zusätzlich: `gate_anomalies` Zähler (Anzahl Pflicht-Gates mit status="bypassed") als separates Top-Level-Feld für einfaches Filtern.

### 3. Neuer `workflow.py gates` Befehl

Gibt Gate-Status des aktiven Workflows aus:

```
=== Gate-Status: bug-workflow-gate-metrics ===

Gate 1 | analyse_summary  | optional  | NOT REACHED
Gate 2 | spec_approval    | PFLICHT   | BYPASSED ⚠  (trigger: command, 2026-06-04T05:48)
Gate 3 | deploy_approval  | PFLICHT   | NOT REACHED

Anomalien: 1 Pflicht-Gate übersprungen
```

Exit-Code 0 (immer — dieses Tool blockiert nie).

### 4. Debug-Ausgabe in `workflow_state_updater.py`

Wenn "go" erkannt wird (`is_approval=True`), aber kein Übergang ausgelöst wird:
- Schreibe auf stderr: `[DEBUG go] Erkannt, aber keine Transition: phase=X, active_workflow=Y`

Damit wird sichtbar warum "go" manchmal nichts tut (falsche Phase, kein aktiver Workflow).

## Acceptance Criteria

**AC-1:** Given ein abgeschlossener Workflow bei dem Gate 2 mit "go" freigegeben wurde, When `workflow.py write-log` ausgeführt wird, Then enthält das YAML-Log ein `gate_history`-Feld mit `spec_approval.status == "user_approved"`.

**AC-2:** Given ein abgeschlossener Workflow bei dem `phase3_spec` direkt zu `phase5_tdd_red` überging (trigger="command"), When `workflow.py write-log` ausgeführt wird, Then enthält das YAML-Log `gate_history.spec_approval.status == "bypassed"` und `gate_anomalies == 1`.

**AC-3:** Given ein aktiver Workflow in phase3_spec, When `workflow.py gates` ausgeführt wird, Then gibt der Befehl für alle 3 Gates den Status aus (user_approved / bypassed / not_reached / not_required) mit Timestamp wo vorhanden.

**AC-4:** Given der User tippt "go" in einer Session ohne aktiven Workflow oder in einer Phase wo "go" kein Gate auslöst, When der `workflow_state_updater.py` Hook läuft, Then erscheint auf stderr eine einzeilige Debug-Zeile: `[DEBUG go] Erkannt aber kein Übergang: phase=X workflow=Y`.
