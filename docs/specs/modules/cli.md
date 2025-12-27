---
entity_id: cli
type: module
created: 2025-12-27
updated: 2025-12-27
status: implemented
version: "1.0"
tags: [cli, entrypoint]
---

# CLI Module

## Approval

- [x] Approved

## Purpose

Einstiegspunkt der Anwendung. Parst CLI-Argumente, laedt Konfiguration und orchestriert den Report-Workflow.

## Source

- **File:** `src/app/cli.py`
- **Identifier:** `main()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| DebugBuffer | class | Debug-Informationen sammeln |
| send_mail | function | E-Mail-Versand |

## Implementation Details

```
Konfigurations-Prioritaet: CLI > ENV > config.ini

Optionen:
- --report {evening,morning,alert}
- --channel {email,none}
- --dry-run
- --config <path>
- --debug {info,verbose}
```

## Expected Behavior

- **Input:** CLI-Argumente, Environment, config.ini
- **Output:** Console-Debug + optional E-Mail-Versand
- **Side effects:** E-Mail-Versand (wenn channel=email und nicht dry-run)

## Known Limitations

- Report-Generierung noch Placeholder
- Provider-Integration fehlt noch

## Changelog

- 2025-12-27: Initial spec created (migrated from existing code)
