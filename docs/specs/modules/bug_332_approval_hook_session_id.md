---
entity_id: bug_332_approval_hook_session_id
type: bugfix
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [bugfix, workflow, tooling, hooks, session-registry, parallel-workflows, issue-332]
---

<!-- Issue #332 — Bug: Approval-Hook ignoriert Session-Registry — parallele Workflows kollidieren -->

# Issue #332 — Bug-Fix: Approval-Hook respektiert Session-Registry

## Approval

- [ ] Approved

## Zweck

Der `workflow_state_updater.py`-Hook (UserPromptSubmit) verarbeitet die Approval-Phrasen `approved` / `go` / `deployed`, um den aktiven Workflow auf die nächste Phase zu schieben. Aktuell extrahiert er die Session-ID **nicht** aus dem stdin-Payload und exportiert sie **nicht** nach `GZ_HOOK_SESSION_ID`. Damit greift in `workflow.py:_active_name()` nur noch der Legacy-Fallback (zuletzt global aktives `active_workflow`), und bei parallel laufenden Workflows landet die Approval beim falschen Auftrag. Der Fix ergänzt die in 7 anderen Hooks bereits etablierte Session-ID-Extraktion am Anfang von `main()`, sodass der Hook konsistent mit der Session-Registry-Migration (Issue #325) arbeitet.

## Quelle / Source

**Geänderte Dateien:**
- `.claude/hooks/workflow_state_updater.py` — Session-ID aus stdin-Payload nach `GZ_HOOK_SESSION_ID` exportieren; bestehende stdin-Logik auf bereits geparsten `_payload` umstellen
- `tests/tdd/test_workflow_state_updater_session_routing.py` — Neuer Integrationstest (zwei simulierte Sessions, ohne Mocks; echte Hook-Aufrufe via subprocess)

> **Schicht-Hinweis:** Reine Tooling-Schicht (`.claude/hooks/`). Kein Frontend-, Go-API- oder Python-Backend-Code betroffen. Der Hook läuft in Claude-Code als UserPromptSubmit-Hook und ist Single-Source-of-Truth für Approval-Phrasen-Verarbeitung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/workflow_state_updater.py` | Python-Hook | UserPromptSubmit-Hook, verarbeitet Approval-Phrasen |
| `.claude/hooks/workflow.py` | Python-Modul | Liefert `_active_name()` mit 3-stufiger Auflösung (Session-Registry → ENV → Legacy) |
| `.claude/hooks/workflow_state_multi.py` | Python-Modul | Bietet `load_state()`, `save_state()`, `set_phase()`; ruft intern `workflow.py:_active_name()` auf |
| `.claude/session_workflows.json` | JSON-Registry | Mapping `session_id` → `workflow_name`; wird von `workflow.py start` und `workflow.py switch` gepflegt |
| `.claude/hooks/post_implementation_gate.py:230-239` | Python-Hook (Referenz-Pattern) | Vorbild für stdin-Session-ID-Extraktion — der Block wird strukturell übernommen, aber für UserPromptSubmit-Payload-Form angepasst |

## Implementation Details

### 1. `workflow_state_updater.py` — Session-ID-Extraktion einbauen

Aktueller `main()`-Anfang (Zeilen 85–94):

```python
def main():
    # Get user input from environment or stdin
    try:
        data = json.load(sys.stdin)
        user_message = data.get("user_prompt", data.get("prompt", ""))
    except (json.JSONDecodeError, Exception):
        user_message = os.environ.get("CLAUDE_USER_PROMPT", "")

    if not user_message:
        sys.exit(0)
```

Wird ersetzt durch:

```python
def main():
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
    except (json.JSONDecodeError, Exception):
        pass

    user_message = _payload.get("user_prompt", _payload.get("prompt", ""))
    if not user_message:
        user_message = os.environ.get("CLAUDE_USER_PROMPT", "")

    if not user_message:
        sys.exit(0)
```

**Differenz zum Referenz-Block aus `post_implementation_gate.py`:**
- Kein `CLAUDE_TOOL_INPUT`-Setting (UserPromptSubmit-Hook hat kein `tool_input`-Feld)
- Kein Guard `if not os.environ.get("CLAUDE_TOOL_INPUT")` (existiert hier nicht)
- Nur `session_id` → `GZ_HOOK_SESSION_ID`-Mapping wird übernommen

**Wirkung:** Sobald `GZ_HOOK_SESSION_ID` gesetzt ist, liest die später aufgerufene `load_state()`-Funktion (über `workflow.py:_active_name()`) die Session-Registry korrekt und löst den zur Session gehörigen Workflow auf — egal welcher Workflow global zuletzt aktiv war.

### 2. `test_workflow_state_updater_session_routing.py` — Integrationstest ohne Mocks

Neuer Test in `tests/tdd/`:

- **Setup pro Test:** Temporäres `.claude/workflows/`-Verzeichnis, zwei echte Workflow-State-Files anlegen (`session_a_workflow.json`, `session_b_workflow.json`), beide in `phase3_spec`, `spec_approved: false`. In `session_workflows.json` zwei Mappings eintragen: `"sid-a" → "session_a_workflow"`, `"sid-b" → "session_b_workflow"`.
- **Test 1 (AC-1):** Subprocess-Call `python3 workflow_state_updater.py` mit stdin `{"session_id": "sid-a", "user_prompt": "approved"}`. Erwartet: `session_a_workflow.json` zeigt `phase4_approved`, `spec_approved: true`; `session_b_workflow.json` unverändert.
- **Test 2 (AC-2):** Wie Test 1, aber mit `"sid-b"`. Erwartet: `session_b_workflow.json` wechselt, `session_a_workflow.json` bleibt.
- **Test 3 (AC-3):** Subprocess-Call ohne `session_id` im Payload, mit `GZ_ACTIVE_WORKFLOW=session_a_workflow` als Env-Var. Erwartet: Fallback auf ENV-var, `session_a_workflow.json` wechselt (Single-Session-Kompatibilität).
- **Test 4 (AC-4):** Subprocess-Call mit `session_id` im Payload UND parallelem `GZ_ACTIVE_WORKFLOW`-Env-Var für anderen Workflow. Erwartet: Session-Registry hat Vorrang.

Tests laufen über `subprocess.run([sys.executable, hook_path], input=json.dumps(payload), env=...)` — echte Hook-Ausführung, keine Mocks.

### 3. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `.claude/hooks/workflow_state_updater.py` | +13 / -7 = netto +6 | ja |
| `tests/tdd/test_workflow_state_updater_session_routing.py` | +~80 (neue Datei) | ja |
| **Gesamt** | **~86 LoC** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** stdin-Payload eines UserPromptSubmit-Events mit `session_id` (Pflichtfeld im Payload) und `user_prompt` (enthält die Phrase `approved` / `go` / `deployed` o.ä.)
- **Output:** Der zur `session_id` gehörige Workflow wechselt in die korrekte Folgephase (`phase3_spec` → `phase4_approved` bei `approved`; `phase6_implement` → `green_approved`-Flag bei `go`; `phase7_validate` → `phase8_complete` bei `deployed`). Andere parallel laufende Workflows bleiben unverändert.
- **Side effects:**
  - `os.environ["GZ_HOOK_SESSION_ID"]` wird gesetzt (nur innerhalb des Hook-Prozesses, nicht persistent)
  - `.claude/workflows/<workflow>.json` wird geschrieben mit neuem `current_phase`, `last_updated`, `phases_completed`, `spec_approved`, `phase_transitions[]`
  - bei `approved`-Phrase mit existierender `pending_validation_<workflow>.json`: `user_approved_validation_<workflow>`-File wird angelegt (Validation-Approval-Mechanik)
- **Fallback:** Wenn keine `session_id` im Payload und kein `GZ_ACTIVE_WORKFLOW`-Env-var gesetzt: Hook fällt auf Legacy-Verhalten zurück (zuletzt aktiver Workflow via `_active_name()`-Stufe 3). Single-Session-Nutzer sind nicht betroffen.

## Acceptance Criteria

- **AC-1:** Given zwei Workflows `A` und `B` in `phase3_spec`, beide via Session-Registry registriert mit Session-IDs `sid-a` und `sid-b` / When `workflow_state_updater.py` mit stdin-Payload `{"session_id": "sid-a", "user_prompt": "approved"}` aufgerufen wird / Then wechselt Workflow `A` auf `phase4_approved` mit `spec_approved: true`, und Workflow `B` bleibt unverändert in `phase3_spec`
  - Test: (populated after /4-tdd-red)

- **AC-2:** Given dieselbe Ausgangslage wie AC-1 / When `workflow_state_updater.py` mit stdin-Payload `{"session_id": "sid-b", "user_prompt": "approved"}` aufgerufen wird / Then wechselt Workflow `B` auf `phase4_approved`, und Workflow `A` bleibt unverändert
  - Test: (populated after /4-tdd-red)

- **AC-3:** Given ein einziger Workflow `solo` ohne Session-Registry-Eintrag, mit `GZ_ACTIVE_WORKFLOW=solo` gesetzt / When `workflow_state_updater.py` mit stdin-Payload `{"user_prompt": "approved"}` (ohne `session_id`) aufgerufen wird / Then wechselt Workflow `solo` korrekt auf `phase4_approved` (Single-Session-Kompatibilität bleibt erhalten)
  - Test: (populated after /4-tdd-red)

- **AC-4:** Given zwei Workflows `A` (in Session-Registry mit `sid-a`) und `C` (nur via `GZ_ACTIVE_WORKFLOW=C` aktiv) / When `workflow_state_updater.py` mit stdin-Payload `{"session_id": "sid-a", "user_prompt": "approved"}` und `GZ_ACTIVE_WORKFLOW=C` im Environment aufgerufen wird / Then wechselt Workflow `A` (Session-Registry hat Vorrang vor ENV-var) und `C` bleibt unverändert
  - Test: (populated after /4-tdd-red)

- **AC-5:** Given ein bestehender, in 7 anderen Hooks aktiv genutzter Session-ID-Extraktions-Pattern (`post_implementation_gate.py:230-239`) / When der Fix in `workflow_state_updater.py` angewendet wird / Then verwendet der Hook das exakt gleiche Auflösungsverhalten (`GZ_HOOK_SESSION_ID` aus Payload-`session_id`), sodass alle UserPromptSubmit-Hooks konsistent mit der Session-Registry-Migration (#325) arbeiten
  - Test: Code-Review-Verifikation (manuell; kein automatisierter Test)

## Known Limitations

- **Hook-Prozess-scoped Env-Var:** `GZ_HOOK_SESSION_ID` ist nur im Hook-Prozess gesetzt — andere parallel laufende Hooks für dieselbe Session müssen den Block selbst implementieren (was sie bereits tun). Kein Server-übergreifender State.
- **Fallback bei fehlender `session_id`:** Wenn der UserPromptSubmit-Payload keine `session_id` enthält (alte Claude-Code-Versionen oder beschädigter Payload), fällt der Hook auf das Legacy-Verhalten zurück. Bei nur einem aktiven Workflow ist das unproblematisch; bei mehreren parallelen Workflows ohne Session-IDs bleibt die Kollision möglich — das ist aber außerhalb des Kontrolle-Scopes dieses Hooks.

## Out of Scope

- Refactoring der 7 anderen Hooks (sie funktionieren bereits korrekt)
- Migration auf eine zentrale `_extract_session_id_from_stdin()`-Helper-Funktion (würde mehr Files anfassen als nötig; das Pattern ist klein genug, um es lokal zu duplizieren)
- Änderungen an `workflow.py:_active_name()`-Auflösungs-Logik (funktioniert korrekt, sobald `GZ_HOOK_SESSION_ID` gesetzt ist)
- E2E-Tests in echter Claude-Code-Session (Subprocess-Integrationstests reichen, weil der Hook ein reiner CLI-Prozess ist)
- Bereinigung des Legacy-`active_workflow`-Feldes oder des `.active`-Symlinks (separate Aufräumarbeit)

## Changelog

- 2026-05-22: Initial spec erstellt. Behebt Approval-Routing-Bug für parallele Workflows durch Übernahme des etablierten Session-ID-Extraktions-Patterns aus `post_implementation_gate.py`. 1 Hook-Datei + 1 Test-Datei, ~86 LoC netto.
