---
entity_id: inbound_telegram_reader
type: module
created: 2026-06-03
updated: 2026-07-23
status: superseded
version: "1.0"
tags: [telegram, inbound, bot, polling, channel, f7, issue-570]
github_issue: 570
related_issue: 637
deprecated_by: telegram_webhook_inbound
---

# Inbound Telegram Reader (DEPRECATED)

> **HISTORISCH / ABGELÖST (2026-07-23).** Diese Modul-Spec beschreibt einen nicht mehr gültigen Stand — die zugrundeliegende Architektur (NiceGUI-UI unter `src/web/`, Python-APScheduler, Signal-Kanal bzw. Compare-Subscriptions) wurde ersetzt (SvelteKit-Frontend, Go-Scheduler `internal/scheduler/`, briefings/trips). Die genannten Quelldateien existieren nicht mehr. **Aktueller Stand:** der Code + `docs/reference/api_contract.md`. Aufbewahrt zur Nachvollziehbarkeit.

> **⚠️ DEPRECATED:** Diese Spec beschreibt die Polling-basierte Implementierung (Issue #570).
> Seit **Issue #637** (2026-06-07) erfolgt der Telegram-Inbound via **Webhook** (push-basiert, kein Polling).
> Die alte `InboundTelegramReader.poll_and_process()`-Schleife ist deaktiviert (Notfall-Fallback nur).
> Siehe: `docs/specs/modules/telegram_webhook_inbound.md` für die aktuellen Specs und `docs/runbooks/telegram-webhook.md` für Betrieb.

## Approval

- [x] Approved

## Purpose

Erweitert Gregor um einen Telegram-Bot-Inbound-Kanal. Der Bot empfängt Befehle via
Telegram (Long-Polling auf `getUpdates`), delegiert an den channel-agnostischen
`TripCommandProcessor` und sendet Bestätigungen zurück per `TelegramOutput` in denselben
Chat. Morgen-/Abend-Briefings gehen ebenfalls als Telegram-Nachricht (über das bereits
existierende `send_telegram`-Flag in `TripReportConfig`).

## Source

- **File:** `src/services/inbound_telegram_reader.py` (NEW)
- **Identifier:** `InboundTelegramReader`
- **Scheduler-Integration:** `api/routers/scheduler.py` (MODIFY — neuer Job + Endpoint)
- **Processor-Erweiterung:** `src/services/trip_command_processor.py` (MODIFY — `status` + `hilfe`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `httpx` | third-party | GET `getUpdates`, POST `sendMessage` |
| `src/app/config.Settings` | module | telegram_bot_token, telegram_chat_id, can_send_telegram() |
| `src/services/trip_command_processor.TripCommandProcessor` | module | Verarbeitet Befehle channel-agnostisch |
| `src/services/trip_command_processor.InboundMessage` | DTO | Channel-agnostisches Eingangs-DTO |
| `src/outputs/telegram.TelegramOutput` | module | Bestätigung zurück an Nutzer |
| `src/app/loader.load_all_trips` | module | Aktiven Trip ermitteln |
| `api/routers/scheduler.py` | module | APScheduler-Registrierung |

## Architecture

```
Telegram Bot API (getUpdates long-polling)
        ↓
InboundTelegramReader
  ├─ _get_updates(offset) → list[Update]
  ├─ _find_active_trip() → Trip | None
  ├─ _parse_command(text) → (key, value)
  └─ poll_and_process(settings) → int
        ↓
InboundMessage(channel="telegram", trip_name=..., body=text, ...)
        ↓
TripCommandProcessor.process(msg) → CommandResult
        ↓
TelegramOutput.send(subject, body)
```

**Architektur-Invariante:** `TripCommandProcessor` hat keine Telegram-Importe.
Der Eingangskanal ist ein dünner Adapter.

## Implementation Details

### 1. Trip-Kontext-Auflösung (Auto-Detect)

Da Telegram kein Subject hat, wird der aktive Trip automatisch ermittelt:

```python
def _find_active_trip(self) -> Trip | None:
    """
    Aktiver Trip = erster Trip dessen Datum-Bereich heute überlappt.
    Fallback: nächster zukünftiger Trip (frühestes Startdatum).
    """
    today = date.today()
    trips = load_all_trips()

    # 1. Trip mit heute-Overlap (erste Etappe <= heute <= letzte Etappe)
    for trip in trips:
        if trip.stages:
            start = trip.stages[0].date
            end = trip.stages[-1].date
            if start <= today <= end:
                return trip

    # 2. Fallback: nächster zukünftiger Trip
    future = [t for t in trips if t.stages and t.stages[0].date > today]
    return min(future, key=lambda t: t.stages[0].date) if future else None
```

### 2. Befehlssyntax (Telegram — kein `### ` Prefix)

Telegram-Nachrichten sind einfach Freitext:

| Befehl | Syntax | Beispiel |
|--------|--------|---------|
| Ruhetag | `ruhetag [N]` | `ruhetag` oder `ruhetag 2` |
| Startdatum | `startdatum YYYY-MM-DD` | `startdatum 2026-07-15` |
| Report | `report morning\|evening` | `report morning` |
| Abbruch | `abbruch` | `abbruch` |
| Status | `status` | `status` |
| Hilfe | `hilfe` | `hilfe` |

**Parser-Logik:** erste Zeile splitten → `parts[0].lower()` = Befehl, `parts[1:]` = Wert.
Kein `### ` Prefix. Der Email-Processor-Parser (`_COMMAND_PATTERN`) bleibt unverändert.

### 3. InboundTelegramReader

```python
TELEGRAM_API_BASE = "https://api.telegram.org"
POLL_TIMEOUT = 30   # Long-polling timeout (Sekunden)
MAX_UPDATES = 10    # Max Updates pro Request

class InboundTelegramReader:
    """Pollt Telegram Bot API auf eingehende Nachrichten."""

    def poll_and_process(self, settings: Settings) -> int:
        """Long-polling: holt neue Updates, verarbeitet Befehle.
        Returns: Anzahl verarbeiteter Befehle."""

    def _get_updates(self, token: str, offset: int) -> list[dict]:
        """GET getUpdates?offset=&timeout=30. Returns update-Liste."""

    def _process_update(self, update: dict, settings: Settings) -> bool:
        """Verarbeitet ein einzelnes Update. Returns True wenn Befehl erkannt."""

    def _find_active_trip(self) -> Trip | None:
        """Aktiven Trip automatisch ermitteln (heute-Overlap oder nächster)."""

    def _parse_command(self, text: str) -> tuple[str | None, str | None]:
        """Erste Zeile parsen: 'ruhetag 2' → ('ruhetag', '2')."""

    def _send_reply(self, token: str, chat_id: str, text: str) -> None:
        """Antwort via sendMessage an chat_id."""
```

**Offset-Persistenz:** `offset` wird im Prozess-Speicher gehalten (Instanzvariable).
Bei Neustart werden ältere Updates ignoriert (getUpdates mit `offset` = letzter `update_id + 1`).

### 4. TripCommandProcessor — neue Befehle

```python
# status: Zeigt aktuelle Etappen-Daten des aktiven Trips
def _show_status(self, trip: Trip) -> CommandResult:
    """Listet aktive und kommende Etappen mit Datum."""

# hilfe: Listet alle verfügbaren Befehle
def _show_help(self) -> CommandResult:
    """Zeigt Befehlsliste mit Syntax."""
```

`_VALID_COMMANDS` erweitern um `{"status", "hilfe"}`.

Der `status`-Befehl braucht keinen `value`-Parameter. Die Email-Parser-Regex bleibt kompatibel.

### 5. Scheduler-Integration

```python
# In api/routers/scheduler.py:

@router.post("/inbound-telegram")
def trigger_inbound_telegram():
    """Trigger Telegram Bot polling (manuelle Auslösung / Test)."""
    from services.inbound_telegram_reader import InboundTelegramReader
    settings = Settings()
    if not settings.can_send_telegram():
        return {"status": "skipped", "reason": "telegram not configured"}
    reader = InboundTelegramReader()
    count = reader.poll_and_process(settings)
    return {"status": "ok", "processed": count}

# APScheduler-Job (alle 30 Sekunden — Kompromiss zwischen Latenz und API-Last):
_scheduler.add_job(
    run_inbound_telegram_poll,
    IntervalTrigger(seconds=30),
    id="inbound_telegram_poll",
    name="Inbound Telegram Poll (every 30s)",
)
```

### 6. Antwort-Format

Bestätigungen werden direkt via `TelegramOutput` gesendet:
- `subject` aus `CommandResult.confirmation_subject`
- `body` aus `CommandResult.confirmation_body`
- Format: `[subject]\n\nbody` (wie in TelegramOutput.send implementiert)

Bei unbekanntem Trip → Antwort: "Kein aktiver Trip gefunden. Erstelle oder aktiviere einen Trip auf gregor20.henemm.com"

## Acceptance Criteria

**AC-1:** Given ein konfigurierter Telegram-Bot (`GZ_TELEGRAM_BOT_TOKEN` + `GZ_TELEGRAM_CHAT_ID`) / When `InboundTelegramReader.poll_and_process()` aufgerufen wird und eine neue Telegram-Nachricht `ruhetag` vorliegt / Then gibt der Processor eine Bestätigung zurück und `TelegramOutput.send()` wird mit `confirmation_subject` und `confirmation_body` aufgerufen.

**AC-2:** Given ein aktiver Trip (heutiges Datum liegt zwischen erster und letzter Etappe) / When eine Telegram-Nachricht `ruhetag` ohne Trip-Name-Angabe eintrifft / Then wird dieser Trip automatisch als Kontext verwendet — kein Fehler, kein `[Trip Name]` nötig.

**AC-3:** Given kein heutiger Trip aber ein zukünftiger Trip existiert / When eine Telegram-Nachricht eintrifft / Then wird der nächste zukünftige Trip (frühestes Startdatum) als Kontext verwendet.

**AC-4:** Given kein Trip existiert / When eine Telegram-Nachricht eintrifft / Then antwortet der Bot mit einer hilfreichen Fehlermeldung auf Deutsch (kein Crash, kein stiller Fehler).

**AC-5:** Given eine Telegram-Nachricht `hilfe` / When `TripCommandProcessor.process()` aufgerufen wird / Then enthält `confirmation_body` alle verfügbaren Befehle mit Syntax.

**AC-6:** Given eine Telegram-Nachricht `status` / When `TripCommandProcessor.process()` aufgerufen wird / Then enthält `confirmation_body` aktive und kommende Etappen mit Datum.

**AC-7:** Given `GZ_TELEGRAM_BOT_TOKEN` oder `GZ_TELEGRAM_CHAT_ID` fehlen / When `poll_and_process()` aufgerufen wird / Then wird 0 zurückgegeben und kein API-Call gemacht.

**AC-8:** Given ein Telegram-Update mit unbekanntem Befehl (z.B. `hallo`) / When verarbeitet / Then antwortet der Bot mit der Hilfe-Nachricht.

**AC-9:** Given der Scheduler-Router / When `POST /inbound-telegram` aufgerufen wird / Then wird `InboundTelegramReader.poll_and_process()` ausgelöst und `{"status": "ok", "processed": N}` zurückgegeben.

**AC-10:** Given die Email-Befehle (`### ruhetag:`) / When nach der Telegram-Integration getestet / Then funktionieren sie weiterhin unverändert (keine Regression im Email-Kanal).

## Configuration

| Parameter | ENV | Beschreibung |
|-----------|-----|--------------|
| Bot-Token | `GZ_TELEGRAM_BOT_TOKEN` | Von @BotFather erhalten |
| Chat-ID | `GZ_TELEGRAM_CHAT_ID` | Empfänger-Chat (Single-User) |
| Poll-Intervall | Hardcoded 30s | APScheduler IntervalTrigger |
| Long-Poll-Timeout | Hardcoded 30s | getUpdates timeout-Parameter |

## Files to Create/Modify

| File | Action | LOC |
|------|--------|-----|
| `src/services/inbound_telegram_reader.py` | NEW | ~120 |
| `src/services/trip_command_processor.py` | MODIFY | ~40 (status + hilfe) |
| `api/routers/scheduler.py` | MODIFY | ~25 |
| `tests/tdd/test_inbound_telegram_reader.py` | NEW | ~80 |

## Testing Strategy

**Keine Mocks!** Tests nutzen echte Telegram-Bot-API:
- Bot-Token + Chat-ID aus Settings (`GZ_TELEGRAM_BOT_TOKEN`, `GZ_TELEGRAM_CHAT_ID`)
- Test sendet via `sendMessage` an sich selbst, prüft via `getUpdates` ob Reply ankam
- `_find_active_trip()`: Test mit echten Trip-Fixtures aus `data/`

```python
def test_poll_returns_zero_without_credentials()
def test_find_active_trip_today_overlap()
def test_find_active_trip_next_future()
def test_find_active_trip_no_trips_returns_none()
def test_parse_command_ruhetag_no_value()
def test_parse_command_ruhetag_with_value()
def test_parse_command_startdatum()
def test_parse_command_unknown_returns_none_key()
def test_status_command_in_processor()
def test_hilfe_command_in_processor()
def test_inbound_message_channel_is_telegram()
```

## Known Limitations

- Single-User: `telegram_chat_id` ist hardcoded auf einen Empfänger
- Keine Multi-Trip-Auflösung bei gleichzeitig aktiven Trips
- Long-Polling-Offset geht bei Service-Neustart verloren (ältere unverarbeitete Updates werden ignoriert)
- Kein Webhook (bewusst: einfacher, kein öffentlicher Endpunkt nötig)

## Changelog

- 2026-06-03: v1.0 Initial spec (Issue #570)
