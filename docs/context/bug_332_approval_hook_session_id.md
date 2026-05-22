# Bug #332: Approval-Hook ignoriert Session-Registry

## Symptom

Bei parallel laufenden Workflows (mehrere Claude-Sessions gleichzeitig) landet ein im Chat getipptes `approved` / `go` / `deployed` beim falschen Workflow — meist beim zuletzt global aktiven.

Konkret 2026-05-22: Fünf parallele Bug-Workflows (#326–#330). `approved` für #329 wurde fälschlich auf #328 gebucht.

## Reproduktion

1. Zwei Sessions parallel starten, jeweils einen Workflow registrieren (`workflow.py start <name>`)
2. In Workflow A: Spec schreiben, in Phase `phase3_spec` warten
3. In Workflow B: einen beliebigen Befehl absetzen (verschiebt globales `active_workflow` auf B)
4. In Session A `approved` tippen
5. **Erwartet:** Workflow A → `phase4_approved`
6. **Tatsächlich:** Workflow B → `phase4_approved`, A bleibt liegen

## Root Cause

**Datei:** `.claude/hooks/workflow_state_updater.py:104-105`

```python
state = load_state()
active_name = state.get("active_workflow")
```

`load_state()` ruft intern `workflow.py:_active_name()` auf — die korrekte Auflösung mit Priorität:

1. Session-Registry (`session_workflows.json`)
2. `GZ_ACTIVE_WORKFLOW` ENV var
3. Legacy: zuletzt global beschriebenes `active_workflow`-Feld

Die Session-Registry verlangt aber, dass `GZ_HOOK_SESSION_ID` aus dem stdin-Payload gesetzt wurde, bevor `_active_name()` läuft. Diese Vorarbeit fehlt in `workflow_state_updater.py` — alle anderen relevanten Hooks (`workflow_gate`, `scope_guard`, `post_implementation_gate`, `tdd_enforcement`, `red_test_gate`, `ui_screenshot_gate`, `track_changes`) tun das, der Approval-Hook wurde bei der Migration zur Session-Registry vergessen.

Folge: `_active_name()` fällt auf Schritt 3 zurück → zuletzt aktiver Workflow gewinnt → Approval landet woanders.

## Erwartung

Approval-Hook ehrt die Session-Registry genau wie alle anderen Hooks. Bei parallelen Workflows gibt es keine Kollision mehr.

## Fix-Strategie

Adaption des Patterns aus `post_implementation_gate.py:230–239`, **angepasst für UserPromptSubmit-Hook** (kein `tool_input`, sondern `user_prompt`):

In `workflow_state_updater.py:main()` direkt nach `def main():`, **vor** dem bestehenden stdin-Read, folgenden Block einfügen:

```python
# Per-session workflow resolution (#332/#325): stdin nur EINMAL lesen,
# session_id extrahieren, GZ_HOOK_SESSION_ID exportieren. Der nachfolgende
# Code nutzt das bereits geparste _payload — kein zweiter stdin-Read möglich.
_payload = {}
try:
    _raw = sys.stdin.read()
    if _raw.strip():
        _payload = json.loads(_raw)
        _sid = (_payload.get("session_id") or "").strip()
        if _sid:
            os.environ["GZ_HOOK_SESSION_ID"] = _sid
except Exception:
    pass
```

Bestehender Block in Zeile 87–91 wird ersetzt durch:
```python
user_message = _payload.get("user_prompt", _payload.get("prompt", ""))
if not user_message:
    user_message = os.environ.get("CLAUDE_USER_PROMPT", "")
```

**Differenz zu post_implementation_gate.py:** Kein `CLAUDE_TOOL_INPUT`-Setting (UserPromptSubmit hat kein tool_input). Kein Guard `if not os.environ.get("CLAUDE_TOOL_INPUT")` (gibt es hier nicht).

## Test (Pflicht-Mocks-frei)

- Integrationstest mit zwei Mock-Sessions: jede setzt eigene `session_id` in stdin-Payload, registriert eigenen Workflow in `session_workflows.json`, sendet `approved` → State des jeweils eigenen Workflows wechselt auf `phase4_approved`, anderer bleibt unverändert
- Regression: Single-Session-Workflow (kein `session_workflows.json`-Eintrag) muss weiterhin per `GZ_ACTIVE_WORKFLOW` / Legacy-Fallback funktionieren
- E2E: Echte Approval-Sequenz mit echtem Hook-Run via `echo '{"session_id":"X","user_prompt":"approved"}' | python3 workflow_state_updater.py`

## Aufwand

Klein. Ein File, ~10 Zeilen Diff. Pattern in 7 anderen Hooks bereits etabliert.

## Affected Workflows (Stand 2026-05-22)

#326–#330 alle gefährdet, solange Bug existiert. Manuelles Lenken via `workflow.py phase` + `workflow.py set-field` ist die einzige Workaround-Option.
