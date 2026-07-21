---
entity_id: epic_191_adversary_verschaerfung
type: module
created: 2026-05-11
updated: 2026-05-11
status: draft
version: "1.0"
tags: [hooks, workflow, adversary, validation]
---

<!-- Issue #196 — Epic #191: Adversary verschärfen (Workflow E) -->

# Epic 191 — Adversary verschärfen (Workflow E)

## Approval

- [ ] Approved

## Purpose

Zwei Verschärfungen am Adversary-System:

1. **AMBIGUOUS-Verdict blockiert `git commit`**, statt nur zu warnen. Escape via `workflow.py override-ambiguous "<Grund>"` mit 1h-TTL.
2. **Code-Reference Pflicht**: `implementation-validator.md`-Agent muss jedes Finding mit `Code reference: file:line` belegen. Wird in Agent-Doku festgeschrieben.

## Source

- **File:** `.claude/hooks/pre_commit_gate.py` — neuer Block bei AMBIGUOUS ohne Override-Token
- **File:** `.claude/hooks/workflow.py` — neue Subcommand `override-ambiguous <reason>` mit TTL
- **File:** `.claude/agents/implementation-validator.md` — Pflicht-Doku für `Code reference: file:line`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `epic_191_state_migration` Spec | Vorgänger | `_get_workflows_root()` + atomare Writes |
| `epic_191_logbuch_audit` Spec | Vorgänger | `set-field` API, State-Felder |
| `time.time()` | stdlib | TTL für Override-Token |

## Implementation Details

### State-Feld

Neues Feld pro Workflow:
```json
"adversary_ambiguous_override": {
  "reason": "edge case akzeptiert, siehe issue #N",
  "at": "2026-05-11T14:00:00",
  "expires_at": 1715438400.0
}
```

### `workflow.py override-ambiguous <reason>` (~20 LoC)

```python
def cmd_override_ambiguous(args: list[str]) -> None:
    if not args:
        print("Usage: workflow.py override-ambiguous <reason>", file=sys.stderr)
        sys.exit(1)
    reason = " ".join(args)
    data, name = _read_active()
    now = datetime.now()
    data["adversary_ambiguous_override"] = {
        "reason": reason,
        "at": now.isoformat(),
        "expires_at": now.timestamp() + 3600,  # 1h TTL
    }
    _save(data)
    print(f"AMBIGUOUS-Override aktiv (gültig 1h): {reason}")
```

### `pre_commit_gate.py` Block (~25 LoC)

```python
def _check_ambiguous_block(workflow_data: dict) -> tuple[bool, str]:
    verdict = (workflow_data.get("adversary_verdict") or "").upper()
    if not verdict.startswith("AMBIGUOUS"):
        return True, "verdict not AMBIGUOUS"
    
    override = workflow_data.get("adversary_ambiguous_override") or {}
    expires = override.get("expires_at", 0)
    if expires and time.time() < expires:
        return True, f"override active: {override.get('reason', '')}"
    return False, (
        "AMBIGUOUS verdict blocks commit. "
        "Run: workflow.py override-ambiguous '<reason>' (TTL 1h)"
    )
```

Integration in pre_commit_gate.py vor allow():
```python
ok, reason = _check_ambiguous_block(workflow_state)
if not ok:
    print(f"BLOCKED: {reason}", file=sys.stderr)
    sys.exit(2)
```

### `implementation-validator.md` Pflicht-Sektion

Neue Sektion "Findings-Format (Pflicht ab Issue #196)":

```markdown
## Findings-Format

Jedes Finding MUSS enthalten:

- `Code reference: <file>:<line>` — gelesen aus echtem Code, nicht halluziniert
- Severity (CRITICAL / HIGH / MEDIUM / LOW)
- Category (spec_violation / edge_case / regression / security / anti_pattern)
- Evidence (Zeile, Reproduktion)
- Remediation (konkret)

Findings ohne `Code reference: file:line` sind ungültig.
```

## Acceptance Criteria

- **AC-1:** Given Workflow mit `adversary_verdict: "AMBIGUOUS: ..."` und kein Override / When `git commit` läuft / Then blockt `pre_commit_gate.py` mit "AMBIGUOUS verdict blocks commit"
- **AC-2:** Given `workflow.py override-ambiguous "test reason"` wurde aufgerufen / When `git commit` läuft / Then erlaubt der Hook den Commit, im State steht `adversary_ambiguous_override.reason`
- **AC-3:** Given Override existiert aber `expires_at` ist in der Vergangenheit / When `git commit` läuft / Then blockt der Hook wieder (TTL abgelaufen)
- **AC-4:** Given Verdict ist VERIFIED oder BROKEN (nicht AMBIGUOUS) / When `git commit` läuft / Then ignoriert der Hook das Override-Feld (kein Effekt)
- **AC-5:** Given `implementation-validator.md` / When es gelesen wird / Then enthält es eine Sektion "Findings-Format" mit "Code reference: file:line" als Pflicht und Severity + Category dokumentiert

## Expected Behavior

- **Input:** Workflow-State mit Adversary-Verdict + optionalem Override
- **Output:** `git commit` erlaubt oder blockt (Exit 2)
- **Side effects:** Override-Token wird im State persistiert, läuft nach 1h ab

## Known Limitations

- TTL ist hart 1h — nicht konfigurierbar (KISS)
- Override-Reason wird nicht im Logbuch verlinkt (kann später ergänzt werden)
- `implementation-validator.md`-Doku wird nicht automatisch erzwungen (nur Soft-Anweisung an den Agent)

## Changelog

- 2026-05-11: Initial spec — Issue #196, Epic #191 (Abschluss).
