# Context: 829 — Spike Token-Verbrauch pro Workflow protokollieren

## Request Summary
Token-Verbrauch (input/output/cache) aus den Session-Transcripts lesen und pro Workflow im Execution-Log-YAML speichern, damit zukünftig sichtbar ist wie viel ein Workflow gekostet hat.

## Spike-Ergebnis: MACHBAR ✓

### Datenquelle bestätigt
Die Session-Transcript-Dateien (`~/.claude/projects/<project-key>/<session-id>.jsonl`) enthalten pro Assistant-Turn ein vollständiges `usage`-Objekt:

```json
{
  "input_tokens": 3,
  "output_tokens": 286,
  "cache_creation_input_tokens": 43504,
  "cache_read_input_tokens": 1919814,
  "cache_creation": {
    "ephemeral_5m_input_tokens": 0,
    "ephemeral_1h_input_tokens": 43504
  },
  "service_tier": "standard",
  "speed": "standard"
}
```

Aktuelles Beispiel (41 Turns dieser Session):
- `input_tokens`: 49
- `output_tokens`: 16.008
- `cache_creation_input_tokens`: 217.043
- `cache_read_input_tokens`: 1.919.814
- Geschätzte Kosten: ~$1.63 USD

### Zugang per Stop-Hook
Der Stop-Hook bekommt `transcript_path` direkt im stdin-JSON-Payload — kein Pfad-Ableitungs-Hacking nötig:

```json
{
  "session_id": "abc123",
  "transcript_path": "/path/to/<session-id>.jsonl",
  "cwd": "/home/hem/gregor_zwanzig/.claude/worktrees/shiny-jumping-pine",
  "hook_event_name": "Stop",
  "reason": "..."
}
```

### Projekt-Schlüssel-Mapping (verifiziert)
`/` und `.` und `_` in cwd → alle werden zu `-`:
- `/home/hem/gregor_zwanzig` → `-home-hem-gregor-zwanzig`
- `.../worktrees/shiny-jumping-pine` → `...-worktrees-shiny-jumping-pine`

## Related Files

| File | Relevanz |
|------|----------|
| `.claude/hooks/workflow.py` | `cmd_write_log()` schreibt YAML-Log — muss `token_usage` ergänzt bekommen |
| `.claude/hooks/workflow.py:1082` | `log_data`-Dict in `cmd_write_log()` — hier `token_usage`-Feld anhängen |
| `.claude/settings.json` | Stop-Hook-Konfiguration — hier neue Stop-Hook-Zeile eintragen |
| `.claude/workflows/_log/*.yaml` | Execution-Logs — bekommt neues `token_usage`-Top-Level-Feld |
| `~/.claude/projects/<key>/<session-id>.jsonl` | Quelle der usage-Daten |

## Implementierungsplan

### Schritt 1: Stop-Hook-Skript `track_token_usage.py`
- Liest `transcript_path` aus stdin-JSON
- Parst alle JSONL-Zeilen → Assistant-Turns mit `message.usage`
- Summiert `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`
- Ermittelt aktiven Workflow via `GZ_ACTIVE_WORKFLOW` (ENV gesetzt durch Session-Start)
- Schreibt Token-Summe in Workflow-State JSON (Feld `token_usage_session`)

### Schritt 2: `cmd_write_log()` in `workflow.py` erweitern
- Liest `token_usage_session` aus Workflow-State
- Schreibt ins YAML-Log als `token_usage: {input: N, output: N, cache_read: N, cache_write: N}`

### Herausforderungen
- `GZ_ACTIVE_WORKFLOW` muss im Stop-Hook-Prozess verfügbar sein (ENV vererbt sich vom Shell-Prozess)
- Mehrere Sessions pro Workflow: Token-Usage kumulieren (nicht überschreiben)
- Transcript wird _während_ der laufenden Session auch geschrieben — am Stop-Ende ist alles da

## Existing Patterns

- Stop-Hook läuft bereits: `notify_sound.py` (in `.claude/settings.json`)
- Workflow-State wird von Hooks gelesen/geschrieben via `workflow_state_multi.py` → `load_state()`/`save_state()`
- Atomic YAML write: `_atomic_write_yaml()` in `workflow.py`

## Risks & Considerations

- **Fail-Safe:** Stop-Hook DARF NIEMALS den Session-Exit blockieren → immer `exit 0` am Ende
- **Kein GZ_ACTIVE_WORKFLOW gesetzt:** Wenn kein Workflow aktiv, Token still ignorieren (kein Fehler)
- **Transcript noch nicht vollständig:** Die letzte Antwort (Stop-Trigger selbst) fehlt evtl. — akzeptabel, da marginal
- **Kosten-Schätzung:** Optional, da Preise sich ändern könnten; besser nur rohe Token-Zahlen speichern
