---
entity_id: token_usage_logging
type: module
created: 2026-06-15
updated: 2026-06-15
status: approved
version: "1.0"
tags: [tooling, workflow, observability]
---

# Token-Usage-Logging

## Approval

- [x] Approved (2026-06-15, Validator: external-validator, Verdict: VERIFIED)

## Purpose

Token-Verbrauch (input/output/cache) jeder Claude-Session aus dem Session-Transcript lesen und pro Workflow kumuliert im Execution-Log-YAML speichern, damit sichtbar wird was ein Workflow an Token-Kosten verursacht hat.

## Source

- **File:** `.claude/hooks/track_token_usage.py` (neu)
- **File:** `.claude/hooks/workflow.py` (erweitert: `cmd_write_log`)
- **File:** `.claude/settings.json` (Stop-Hook-Eintrag)

## Estimated Scope

- **LoC:** ~80
- **Files:** 3
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `workflow_state_multi.py` | intern | Workflow-State lesen/schreiben |
| `~/.claude/projects/<key>/<session>.jsonl` | extern | Quelle der usage-Daten |
| `.claude/settings.json` | Konfiguration | Stop-Hook-Registrierung |

## Implementation Details

### Stop-Hook `track_token_usage.py`

Wird am Session-Ende via Stop-Hook aufgerufen. Bekommt stdin-JSON:
```json
{
  "session_id": "abc123",
  "transcript_path": "/home/hem/.claude/projects/<key>/<session-id>.jsonl",
  "cwd": "/home/hem/gregor_zwanzig/.claude/worktrees/...",
  "hook_event_name": "Stop"
}
```

Ablauf:
1. `transcript_path` aus stdin-JSON lesen
2. Alle Zeilen der JSONL-Datei parsen → `message.usage`-Felder aufsummieren
3. Aktiven Workflow über `GZ_ACTIVE_WORKFLOW` ENV-Variable ermitteln
4. Falls kein aktiver Workflow: still beenden (`exit 0`)
5. Token-Summe in Workflow-State schreiben (Feld `token_usage`, kumulativ über Sessions)
6. Immer `exit 0` — Stop-Hook darf Session-Exit NIEMALS blockieren

Akkumulationslogik (mehrere Sessions pro Workflow):
```python
existing = state.get("token_usage", {})
for key in ["input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens"]:
    existing[key] = existing.get(key, 0) + session_totals[key]
state["token_usage"] = existing
```

### `cmd_write_log()` Erweiterung in `workflow.py`

`log_data`-Dict bekommt neues Top-Level-Feld:
```python
"token_usage": data.get("token_usage") or {},
```

### `settings.json` Stop-Hook-Eintrag

```json
{
  "type": "command",
  "command": "python3 \"${CLAUDE_PROJECT_DIR}/.claude/hooks/track_token_usage.py\"",
  "timeout": 10
}
```

Wird als zusätzlicher Hook in der bestehenden Stop-Hook-Liste eingetragen (nach `notify_sound.py`).

## Expected Behavior

- **Input:** Session endet (Stop-Hook), `transcript_path` im stdin-Payload
- **Output:** Workflow-State JSON enthält `token_usage: {input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens}`. Das YAML-Execution-Log enthält `token_usage`-Block.
- **Side effects:** Keine. Der Hook schreibt nur in den Workflow-State; er blockiert nie.

## Acceptance Criteria

**AC-1:** Given ein aktiver Workflow und eine laufende Session / When die Session endet (Stop-Hook feuert) / Then enthält der Workflow-State das Feld `token_usage` mit allen vier Zählern > 0.
- Test: Workflow starten, mindestens einen Tool-Call machen (erzeugt Assistant-Turn mit usage), Session beenden → `workflow.py status` oder State-JSON prüfen ob `token_usage` gesetzt ist.

**AC-2:** Given ein Workflow mit bereits gespeichertem `token_usage` aus einer Vorgänger-Session / When eine zweite Session endet / Then sind die Zähler kumuliert (nicht überschrieben).
- Test: `token_usage` mit bekannten Werten im State vorbelegen, Track-Hook mit Test-Transcript ausführen, Summe prüfen.

**AC-3:** Given kein aktiver Workflow (`GZ_ACTIVE_WORKFLOW` nicht gesetzt) / When die Session endet / Then endet der Stop-Hook ohne Fehler (exit 0) und schreibt nichts.
- Test: Hook ohne `GZ_ACTIVE_WORKFLOW` ENV aufrufen → Exit-Code 0, kein State-File verändert.

**AC-4:** Given ein abgeschlossener Workflow mit `token_usage` im State / When `workflow.py write-log success` aufgerufen wird / Then enthält das YAML-Execution-Log ein `token_usage`-Feld mit allen vier Zählern.
- Test: Test-Workflow-State mit `token_usage` anlegen, `write-log` ausführen, YAML-Datei lesen und `token_usage`-Block prüfen.

## Known Limitations

- Die letzte Claude-Antwort der Session (der Turn der den Stop-Hook auslöst) kann im Transcript noch fehlen — marginal, akzeptabel.
- Kosten-Berechnung (USD) wird NICHT gespeichert, da Preise sich ändern. Rohe Token-Zahlen sind stabil.
- Subagent-Sessions (andere Worktrees) haben eigene Transcripts und tragen NICHT automatisch zur Hauptworkflow-Summe bei.

## Changelog

- 2026-06-15: Initial spec created (Spike-Ergebnis positiv, direkte Umsetzung)
