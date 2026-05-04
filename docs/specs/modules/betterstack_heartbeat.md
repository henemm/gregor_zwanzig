---
entity_id: betterstack_heartbeat
type: module
created: 2026-04-02
updated: 2026-04-02
status: draft
version: "1.0"
tags: [monitoring, betterstack, heartbeat]
---

# BetterStack Heartbeat Monitoring

## Approval

- [x] Approved

## Purpose

Pingt BetterStack Heartbeat-URLs nach erfolgreichem Morning- und Evening-Report, damit BetterStack erkennt, dass die Reports planmaessig laufen. Bei ausbleibenden Pings alarmiert BetterStack automatisch.

## Source

- **File:** `src/web/scheduler.py`
- **Identifier:** `_ping_heartbeat()`, Konstanten `HEARTBEAT_MORNING`, `HEARTBEAT_EVENING`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `httpx` | extern | HTTP GET Request an BetterStack |
| `scheduler.py` | intern | Integration in bestehende Morning/Evening Jobs |

## Implementation Details

### Konstanten

```python
HEARTBEAT_MORNING = "https://uptime.betterstack.com/api/v1/heartbeat/<HEARTBEAT_MORNING_TOKEN>"
HEARTBEAT_EVENING = "https://uptime.betterstack.com/api/v1/heartbeat/<HEARTBEAT_EVENING_TOKEN>"
```

### Hilfsfunktion

```python
def _ping_heartbeat(url: str) -> None:
    """Ping BetterStack heartbeat URL. Fire-and-forget mit Logging."""
    try:
        response = httpx.get(url, timeout=5)
        response.raise_for_status()
        logger.info(f"Heartbeat ping OK: {url[-8:]}")
    except Exception as e:
        logger.warning(f"Heartbeat ping failed: {e}")
```

### Integration

- `run_morning_subscriptions()`: Ruft `_ping_heartbeat(HEARTBEAT_MORNING)` am Ende auf
- `run_evening_subscriptions()`: Ruft `_ping_heartbeat(HEARTBEAT_EVENING)` am Ende auf

Der Heartbeat wird **immer** gepingt wenn die Funktion durchlaeuft — auch wenn keine aktiven Subscriptions existieren. Der Ping signalisiert "der Scheduler laeuft planmaessig", nicht "es wurden E-Mails gesendet".

## Expected Behavior

- **Input:** Heartbeat-URL (String)
- **Output:** Keiner (fire-and-forget)
- **Side effects:** HTTP GET an BetterStack; Log-Eintrag (INFO bei Erfolg, WARNING bei Fehler)

### Szenarien

| Szenario | Verhalten |
|----------|-----------|
| BetterStack erreichbar | `httpx.get()` → 200 OK → Log INFO |
| BetterStack nicht erreichbar | Timeout nach 5s → Log WARNING → kein Abbruch |
| Netzwerkfehler | Exception gefangen → Log WARNING → kein Abbruch |
| Ungueltige URL | Exception gefangen → Log WARNING → kein Abbruch |

## Known Limitations

- URLs sind als Konstanten hardcoded (nicht konfigurierbar via Settings)
- Kein Retry bei fehlgeschlagenem Ping (bewusste Entscheidung: naechster Scheduled Run pingt erneut)
- Heartbeat wird auch gepingt wenn alle Subscription-E-Mails fehlschlagen (signalisiert Scheduler-Lauf, nicht E-Mail-Erfolg)

## Changelog

- 2026-04-02: Initial spec created
