---
entity_id: issue_828_express_path
type: module
created: 2026-06-15
updated: 2026-06-15
status: implemented
version: "1.0"
tags: [workflow, tooling, gates]
---

# Express-Pfad für Trivial-Issues (#828)

## Approval

- [ ] Approved

## Purpose

Einführung eines `workflow_type=express` für echte Trivial-Fixes (≤10 LoC tatsächliches Diff). Express-Workflows behalten Spec + TDD-RED, überspringen aber Adversary (phase6b) und Staging-E2E — mit zwei Sicherheitsnetzen gegen Gate-Erosion: einem LoC-Sicherheitsnetz beim Commit und einem Sampling-Counter (jeder 5. Express-Workflow erzwingt den vollen Lauf).

## Source

- **Files:** `.claude/hooks/workflow.py`, `.claude/hooks/pre_commit_gate.py`, `.claude/hooks/workflow_state_multi.py`
- **Identifier:** `cmd_start`, `_check_none_verdict_block`, `_check_verdict_before_complete`

## Estimated Scope

- **LoC:** ~80–100
- **Files:** 3
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `workflow.py` | core | Workflow-State, Start/Complete, Phasen-Transitions |
| `pre_commit_gate.py` | gate | Verdict-Block vor Commit |
| `scope_guard.py` | utility | `_get_loc_delta()` für LoC-Delta-Berechnung |
| `workflow_state_multi.py` | wrapper | `get_active_workflow()` für Gate-Abfragen |

## Implementation Details

### Neuer Workflow-Typ `express`

`workflow.py start <name> --type express` initialisiert den Workflow mit:
- `workflow_type = "express"`
- `express_loc_verified = False` (wird beim Commit-Gate gesetzt)
- Phasen-Skip-Transitions: phase6b_adversary → übersprungen (analog `docs`-Typ)

### LoC-Sicherheitsnetz beim Commit

`pre_commit_gate.py` prüft bei jedem Commit mit `workflow_type=express`:
1. `_get_loc_delta()` aus `scope_guard` berechnen
2. Wenn Delta > 10 LoC: Commit blockieren mit Meldung "Express-Workflow überschreitet LoC-Limit (N/10). Typ auf 'feature' wechseln: workflow.py set-field workflow_type feature"
3. Wenn Delta ≤ 10: `express_loc_verified = True` in Workflow-State schreiben, Commit erlauben (kein Adversary-Verdict nötig)

### Sampling-Counter (Gate-Erosions-Schutz)

Globaler Counter in `.claude/workflows/_express_counter.json`:
```json
{"count": 0, "last_full_run": null}
```
- Bei `workflow.py complete` mit `workflow_type=express`: Counter +1
- Wenn Counter % 5 == 0: `express_sampling_required = True` im Workflow-State setzen
- `pre_commit_gate` und `complete` prüfen `express_sampling_required`: wenn True → voller Adversary-Lauf erzwungen (wie `feature`-Typ)
- Meldung beim Start des erzwungenen Runs: "Express-Sampling: jeder 5. Express-Workflow läuft vollständig (Stichprobe #N)."

### `workflow.py complete` Anpassung

`_check_verdict_before_complete` erweitert:
- Express ohne `express_sampling_required`: Verdict-Check überspringen
- Express mit `express_sampling_required`: normaler Verdict-Check (VERIFIED erforderlich)

### `workflow.py status` Anzeige

Bei Express-Typ zusätzliche Zeile: `Express: LoC-verified=<yes/no>, Sampling=<no/REQUIRED (Stichprobe #N)>`

## Expected Behavior

- **Input:** `workflow.py start <name> --type express`
- **Output:** Workflow mit übersprungener phase6b; Commit ohne Adversary-Verdict erlaubt, wenn LoC ≤ 10
- **Side effects:** Globaler Express-Counter in `_express_counter.json`; jeder 5. Express-Workflow erzwingt vollen Adversary-Lauf

## Acceptance Criteria

**AC-1:** Given ein Express-Workflow gestartet (`--type express`) / When ein Commit mit ≤10 LoC Delta gemacht wird / Then ist der Commit erlaubt ohne dass ein Adversary-Verdict gesetzt wurde (kein Blocker in `pre_commit_gate`).
- Test: `workflow.py start test-express --type express` → Python-Datei mit 5 Zeilen ändern → `git commit` → Exit 0 (kein Verdict-Block)

**AC-2:** Given ein Express-Workflow gestartet / When ein Commit mit >10 LoC Delta versucht wird / Then blockiert `pre_commit_gate` mit der Meldung, den Typ auf `feature` zu wechseln.
- Test: `workflow.py start test-express --type express` → Python-Datei mit 15 Zeilen ändern → `git commit` → Exit 2, Meldung enthält "Express-Workflow überschreitet LoC-Limit"

**AC-3:** Given Express-Workflows wurden 4-mal erfolgreich abgeschlossen / When der 5. Express-Workflow gestartet und implementiert wird / Then zeigt `workflow.py status` "Sampling: REQUIRED" und `pre_commit_gate` blockiert ohne Adversary-Verdict (erzwingt vollen Lauf).
- Test: `_express_counter.json` auf count=4 setzen → neuen Express-Workflow starten → `workflow.py complete` aufrufen → Counter auf 5 → Status zeigt Sampling=REQUIRED; Commit ohne Verdict → blockt

**AC-4:** Given ein Express-Workflow mit `express_sampling_required=True` / When ein VERIFIED Adversary-Verdict gesetzt wird und `workflow.py complete` aufgerufen wird / Then schließt der Workflow erfolgreich ab und setzt den Sampling-Counter zurück auf 0.
- Test: Sampling-Workflow mit Verdict VERIFIED → complete → `_express_counter.json` count=0

**AC-5:** Given `workflow.py start <name> --type express` / When `workflow.py status` aufgerufen wird / Then enthält die Ausgabe eine Express-Zeile mit `LoC-verified` und `Sampling`-Status.
- Test: Status-Output des gestarteten Express-Workflows enthält "Express:"

## Known Limitations

- LoC-Delta basiert auf `git diff HEAD --numstat` — zählt nur bereits gestaggte/committete Zeilen, nicht den uncommitteten Workspace. Das ist gewollt: beim Commit-Gate ist der tatsächliche Diff bekannt.
- Sampling-Counter ist global (nicht per User/Session) — bei parallelen Sessions zählt der Counter über alle Sessions. Akzeptiertes Verhalten.
- Der Counter-Reset bei AC-4 startet bei 0 (nicht bei dem Sampling-Workflow selbst), sodass der nächste Sampling-Trigger wieder nach 5 Workflows kommt.

## Changelog

- 2026-06-15: Initial spec created (abgespalten aus #826 AC-1)
