---
entity_id: issue_508_workflow_gate_none_verdict
type: module
created: 2026-06-01
updated: 2026-06-01
status: draft
version: "1.0"
tags: [workflow, infra, gate]
---

# Workflow Gate: None-Verdict blockiert Commit

## Approval

- [ ] Approved

## Purpose

Der `pre_commit_gate.py`-Hook soll Commits blockieren, wenn der Adversary-Agent zwar durchgelaufen ist (phase6b in den Transitions), aber kein Verdict registriert wurde (`adversary_verdict = null`). Zusätzlich soll `workflow.py write-log` früh warnen, und die Agenten-Spec soll den obligatorischen `qa_gate.py`-Aufruf explizit dokumentieren.

Hintergrund: 68 Workflows wurden seit dem 12. Mai 2026 deployed, ohne dass ein Adversary-Urteil im System gelandet ist. Der `pre_commit_gate` prüfte nur `AMBIGUOUS`, ließ `None` aber ungehindert durch (Issues #507, #508).

## Source

- **Files:** `.claude/hooks/pre_commit_gate.py`, `.claude/hooks/workflow.py`, `.claude/agents/implementation-validator.md`

## Estimated Scope

- **LoC:** ~25
- **Files:** 3
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `pre_commit_gate.py` | modify | None-Verdict blocken |
| `workflow.py` | modify | Warnung in `cmd_write_log` |
| `implementation-validator.md` | modify | qa_gate-Aufruf als Pflichtschritt |

## Implementation Details

### Fix 1 — `pre_commit_gate.py`: None-Verdict blocken

In `_check_ambiguous_block` nach der bestehenden AMBIGUOUS-Prüfung eine neue Hilfsfunktion `_phase6b_was_run(workflow_data)` einführen, die `phase_transitions[].to` auf `"phase6b_adversary"` prüft.

```python
def _phase6b_was_run(workflow_data: dict) -> bool:
    transitions = workflow_data.get("phase_transitions") or []
    return any(
        isinstance(t, dict) and "phase6b" in (t.get("to") or "")
        for t in transitions
    )

def _check_none_verdict_block(workflow_data: dict) -> tuple[bool, str]:
    """Block commit if phase6b ran but adversary_verdict is still None."""
    verdict = (workflow_data.get("adversary_verdict") or "").upper()
    if verdict:
        return True, "verdict present"
    if not _phase6b_was_run(workflow_data):
        return True, "phase6b did not run"
    return False, (
        "Adversary-Verdict fehlt (None). "
        "qa_gate.py wurde nicht aufgerufen. "
        "Speichere den Test-Output und führe aus: "
        "python3 .claude/hooks/qa_gate.py /tmp/test_output.txt"
    )
```

Aufruf in `main()` direkt nach `_check_ambiguous_block`, vor dem Test-Lauf.
Kein Override für None — das wäre dieselbe Lücke in anderer Form.

### Fix 2 — `workflow.py cmd_write_log`: Warnung bei fehlendem Verdict

Am Ende von `cmd_write_log`, nach dem Log-Schreiben:

```python
verdict = data.get("adversary_verdict")
if not verdict and _phase6b_was_run_from_data(data):
    print(
        "WARNING: adversary_verdict ist None — qa_gate.py wurde nicht aufgerufen.\n"
        "         Führe aus: python3 .claude/hooks/qa_gate.py /tmp/test_output.txt",
        file=sys.stderr,
    )
```

Die Hilfsfunktion `_phase6b_was_run_from_data` ist identisch mit der in pre_commit_gate.py —
sie prüft `phase_transitions[].to` auf `"phase6b_adversary"`. In workflow.py ist sie
lokal zu definieren (anderes Modul).

### Fix 3 — `implementation-validator.md`: qa_gate als Pflichtschritt

Nach Step 5 ("Verify Against Checklist") einen neuen **Step 6** einfügen:

```markdown
### Step 6 (PFLICHT): Verdict im Workflow registrieren

```bash
# Test-Output speichern (falls noch nicht geschehen)
uv run pytest --tb=short -q > /tmp/test_output_$(date +%s).txt 2>&1

# Verdict setzen — setzt adversary_verdict im Workflow-State
python3 .claude/hooks/qa_gate.py /tmp/test_output_$(date +%s).txt
```

Ohne diesen Aufruf bleibt `adversary_verdict = null` und `pre_commit_gate`
blockiert den nächsten Commit.
```

Außerdem den irreführenden Kommentar in Step 2 präzisieren:

Alt: `Save the FULL output — the qa_gate hook will validate it.`
Neu: `Save the FULL output to /tmp/ — Step 6 ruft qa_gate.py explizit auf.`

## Expected Behavior

- **Input:** Workflow in phase6b_adversary oder später, `adversary_verdict = null`
- **Output:** Commit wird geblockt mit erklärender Fehlermeldung und Befehl
- **Side effects:** `workflow.py write-log` gibt Warnung auf stderr aus

## Acceptance Criteria

**AC-1:** Given ein Workflow in `phase6_implement` mit einer `phase6b_adversary`-Transition und `adversary_verdict = null` / When `git commit` ausgeführt wird / Then blockiert `pre_commit_gate` mit der Meldung "Adversary-Verdict fehlt" und dem `qa_gate.py`-Befehl.
- Test: (populated after /tdd-red)

**AC-2:** Given ein Workflow mit `adversary_verdict = null` und KEINER `phase6b_adversary`-Transition (Infra/Doku-Workflow) / When `git commit` ausgeführt wird / Then wird der Commit NICHT durch das None-Verdict-Gate geblockt.
- Test: (populated after /tdd-red)

**AC-3:** Given ein Workflow mit `adversary_verdict = "VERIFIED"` und `phase6b_adversary`-Transition / When `git commit` ausgeführt wird / Then wird der Commit vom Verdict-Gate durchgelassen.
- Test: (populated after /tdd-red)

**AC-4:** Given ein Workflow mit `phase6b_adversary`-Transition und `adversary_verdict = null` / When `workflow.py write-log success` ausgeführt wird / Then erscheint eine WARNING-Zeile auf stderr mit dem `qa_gate.py`-Befehl.
- Test: (populated after /tdd-red)

**AC-5:** Given ein Workflow mit `adversary_verdict = "VERIFIED"` / When `workflow.py write-log success` ausgeführt wird / Then erscheint KEINE WARNING-Zeile auf stderr.
- Test: (populated after /tdd-red)

## Known Limitations

- Bestehende archivierte Workflows (die 68 Fälle) werden durch diesen Fix nicht rückwirkend geprüft — das ist Aufgabe von Issue #510.
- Der Fix greift nur wenn `phase_transitions` befüllt ist (seit 12. Mai 2026). Ältere Workflows ohne Transitions-Daten sind nicht betroffen.

## Changelog

- 2026-06-01: Initial spec (Issues #507 + #508, Analyse-Daten: 68 deployed Workflows ohne Verdict)
