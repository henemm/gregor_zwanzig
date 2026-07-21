---
entity_id: bug599_telegram_persistent
type: module
created: 2026-06-04
updated: 2026-06-04
status: approved
version: "1.0"
tags: [telegram, bug]
---

# Bug #599: Telegram-Verbindungsfluss — persistenter Offset, Token-Store, Bot-Bestätigung

## Approval

- [x] Approved

## Purpose

Drei separate Bugs verhindern zuverlässige Telegram-Verbindung:
1. `InboundTelegramReader` wird bei jedem API-Call neu erzeugt → Offset verloren → Telegram liefert dieselben `/start`-Updates alle 30s erneut
2. Go-Token-Store ist In-Memory → wird bei jedem Deploy gelöscht → Token ungültig nach Neustart
3. Nach erfolgreichem Connect sendet der Bot keine Bestätigungsnachricht

## Source

- **Files:**
  - `api/routers/scheduler.py` — module-level singleton statt frische Instanz
  - `src/services/inbound_telegram_reader.py` — `_process_start_command` sendet Bestätigung
  - `internal/handler/telegram_connect.go` — dateibasierter Token-Store

## Estimated Scope

- **LoC:** ~60
- **Files:** 3
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `api/routers/scheduler.py` | Source | Singleton-Reader statt frische Instanz |
| `src/services/inbound_telegram_reader.py` | Source | `_process_start_command` Bestätigung |
| `internal/handler/telegram_connect.go` | Source | Dateibasierter Token-Store |
| `outputs/telegram.py` | Dependency | Bestätigungsnachricht senden |

## Implementation Details

### Fix 1: Modul-Singleton in scheduler.py

```python
# api/routers/scheduler.py — vor den Router-Definitionen
_telegram_reader: "InboundTelegramReader | None" = None

@router.post("/inbound-telegram")
def trigger_inbound_telegram():
    global _telegram_reader
    from services.inbound_telegram_reader import InboundTelegramReader
    from app.config import Settings
    
    settings = Settings()
    if not settings.can_send_telegram():
        return {"status": "skipped", "reason": "telegram not configured"}
    if _telegram_reader is None:
        _telegram_reader = InboundTelegramReader()
    count = _telegram_reader.poll_and_process(settings)
    return {"status": "ok", "processed": count}
```

### Fix 2: Bot-Bestätigung in _process_start_command

```python
def _process_start_command(self, token: str, chat_id: str, settings: Settings) -> bool:
    try:
        resp = httpx.post(
            "http://localhost:8090/api/internal/telegram-connect",
            json={"token": token, "chat_id": chat_id},
            timeout=5,
        )
        if resp.status_code == 200:
            logger.info(f"Telegram chat_id {chat_id} via token registriert")
            # Bestätigungsnachricht an User — user-scoped Settings mit chat_id
            user_settings = settings.with_chat_id(chat_id)  # oder direkt mit override
            TelegramOutput(user_settings).send(
                "Verbunden",
                "✓ Du bist jetzt mit Gregor verbunden! Sende 'hilfe' für verfügbare Befehle.",
            )
        else:
            logger.warning(f"telegram-connect returned {resp.status_code}")
    except Exception as e:
        logger.error(f"telegram-connect Fehler: {e}")
    return True
```

### Fix 3: Dateibasierter Token-Store in telegram_connect.go

```go
// Token-Store in data/telegram_tokens.json persistieren
// Read-Modify-Write Pattern
```

## Acceptance Criteria

**AC-1:** Given: InboundTelegramReader-Singleton existiert im `scheduler`-Modul auf Modulebene  
When: `trigger_inbound_telegram()` wird zweimal aufgerufen  
Then: Beide Aufrufe verwenden dieselbe Instanz (kein neues Objekt)

**AC-2:** Given: `_telegram_reader._offset` wird auf 42 gesetzt  
When: `trigger_inbound_telegram()` erneut aufgerufen (mit gemocktem poll)  
Then: `_offset` ist noch 42 (nicht auf 0 zurückgesetzt)

**AC-3:** Given: `_process_start_command` wird mit gültigem Token aufgerufen  
When: Go-Backend antwortet mit 200  
Then: `TelegramOutput.send()` wird mit Bestätigungsnachricht aufgerufen (enthält "verbunden")

**AC-4:** Given: Token-Store in Go-API  
When: Go-API neu gestartet  
Then: Ausstehende Tokens bleiben gültig (persistent in data/telegram_tokens.json)

## Test Plan

Tests: `tests/tdd/test_bug599_telegram_persistent.py`

- `test_scheduler_has_module_level_telegram_reader` → AC-1 RED: AttributeError
- `test_trigger_reuses_reader_instance` → AC-2 RED: neues Objekt bei jedem Aufruf
- `test_process_start_command_sends_confirmation` → AC-3 RED: keine TelegramOutput.send()-Call
