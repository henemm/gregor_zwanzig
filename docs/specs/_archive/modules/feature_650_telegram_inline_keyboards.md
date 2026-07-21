---
entity_id: feature_650_telegram_inline_keyboards
type: module
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [telegram, output, foundation, epic-639]
---

# #650 Telegram-Foundation — Inline-Keyboards (reply_markup) + persistentes Bot-Menü

## Approval

- [ ] Approved

## Purpose

Technische Basis (Teil 1/6 von #639) für interaktive Telegram-Nachrichten: ausgehende Nachrichten
können antippbare Inline-Buttons tragen, und der Bot zeigt ein festes Befehlsmenü an. Reines Plumbing —
keine Wetter-Datenlogik, keine Reaktion auf Button-Klicks (das ist Teil 6/6).

## Source

- **File:** `src/outputs/telegram.py`
- **Identifier:** `TelegramOutput.send`, `TelegramOutput.set_my_commands`, `TelegramOutput.get_my_commands`, `BOT_COMMANDS`

## Estimated Scope

- **LoC:** ~70 (Produktivcode), zzgl. Tests + dünnes Ops-Script
- **Files:** `src/outputs/telegram.py` (erweitern), `scripts/telegram_set_commands.sh` (neu), `tests/tdd/test_issue_650_telegram_foundation.py` (neu)
- **Effort:** low

## Dependencies

- Upstream: `httpx`, `Settings` (`telegram_bot_token`, `telegram_chat_id`), `OutputError` aus `outputs.base`.
- Downstream: Teil 2/6–6/6 von #639 (Text-Kurzbefehle, `callback_query`-Reaktion). Buttons sind nach #650
  sichtbar, aber noch ohne Klick-Funktion. Scheduler-/Briefing-Pipeline ruft `send()` unverändert ohne
  `reply_markup` auf.

## Acceptance Criteria

- **AC-1:** Given eine ausgehende Telegram-Nachricht mit einem definierten Inline-Keyboard (`reply_markup` mit mindestens einem Button) / When `TelegramOutput.send(subject, body, reply_markup=...)` gegen die echte Bot-API aufgerufen wird (mock-frei) / Then liefert die Bot-API HTTP 200, die zurückgegebene Message enthält das `reply_markup`-Feld mit dem übergebenen Inline-Keyboard, und der Button-Text stimmt mit dem übergebenen überein.

- **AC-2:** Given das einmalige Menü-Setup mit der Befehlsliste `BOT_COMMANDS` / When `TelegramOutput.set_my_commands()` gegen die echte Bot-API aufgerufen wird (mock-frei) / Then liefert die API `ok: true`, und ein anschließender `TelegramOutput.get_my_commands()`-Aufruf gibt exakt dieselbe Befehlsliste (gleiche `command`-Werte in gleicher Reihenfolge) zurück.

- **AC-3:** Given der bestehende Briefing-/Scheduler-Altpfad / When `TelegramOutput.send(subject, body)` OHNE `reply_markup` aufgerufen wird / Then ist der gesendete Payload bit-identisch zum Verhalten vor #650 (kein `reply_markup`-Schlüssel im Payload), und das Protocol `OutputChannel` bleibt erfüllt (`send(subject, body)` weiterhin gültig).

- **AC-4:** Given ein Bot-API-Fehler beim Senden mit `reply_markup` (z.B. nicht erreichbare API) / When `send(..., reply_markup=...)` aufgerufen wird / Then wird ein `OutputError("telegram", <msg>)` mit korrekter Arität (2 Argumente, Kanal-Name "telegram") geworfen — konsistent mit dem Altpfad (Lehre #645).

- **AC-5:** Given `BOT_COMMANDS` als einzige Quelle der Bot-Befehle / When `set_my_commands()` ohne explizites Argument aufgerufen wird / Then verwendet es genau `BOT_COMMANDS`, und jeder Eintrag hat die von der Bot-API geforderte Struktur (`command`: 1–32 Zeichen, lowercase/Ziffern/Unterstrich; `description`: 1–256 Zeichen).

## Expected Behavior

### `send(subject, body, reply_markup=None)`
- Neues optionales kwarg `reply_markup: dict | None = None`.
- Wenn `None`: Payload unverändert (`{"chat_id", "text"}`) — Altpfad bit-identisch.
- Wenn gesetzt: zusätzlich `"reply_markup": reply_markup` im JSON-Payload. `httpx` serialisiert das
  verschachtelte Objekt (`{"inline_keyboard": [[{"text": ..., "callback_data"/"url": ...}]]}`) automatisch.
- Fehlerbehandlung identisch zum Altpfad (`OutputError("telegram", ...)`, Timeout, HTTPError).

### `set_my_commands(commands=None) -> None`
- POST auf `…/bot<token>/setMyCommands` mit `{"commands": commands or BOT_COMMANDS}`.
- Status 200 + `ok: true` → ok; sonst `OutputError("telegram", ...)`.

### `get_my_commands() -> list[dict]`
- GET/POST auf `…/bot<token>/getMyCommands`, liefert `result`-Liste (`[{"command", "description"}, …]`).

### `BOT_COMMANDS`
- Modul-Konstante: Liste der Bot-Befehle mit Emoji-Labels in der Beschreibung (Sonnenlicht-Lesbarkeit),
  z.B. `{"command": "briefing", "description": "🌤️ Aktuelles Briefing"}`. Grundgerüst — die echten
  Befehlsfunktionen folgen in Teil 2–6/6.

### Ops-Script `scripts/telegram_set_commands.sh`
- Dünner Wrapper analog `telegram_set_webhook.sh`: `set` (ruft setMyCommands), `info` (getMyCommands),
  `delete` (deleteMyCommands). ENV: `TELEGRAM_BOT_TOKEN`. Für das einmalige Deploy-Setup.

## Test Strategy (mock-frei — PFLICHT)

- Echtes Bot-Token + Test-Chat aus ENV: `GZ_TELEGRAM_BOT_TOKEN` + `GZ_TELEGRAM_TEST_CHAT_ID`.
  Fehlt eines → `pytest.skip(...)` (KEIN Mock-Ersatz). Echter Lauf in der Acceptance-Stage gegen den Staging-Bot.
- AC-1: echtes `sendMessage` mit Inline-Keyboard → Response-JSON prüfen (`ok: true`, `result.reply_markup.inline_keyboard[0][0].text`).
- AC-2: `set_my_commands()` → `get_my_commands()` Roundtrip, Listen-Gleichheit asserten.
- AC-3: Altpfad-Payload-Bau ohne Netzwerk verifizierbar (gesendeter Payload hat keinen `reply_markup`-Key);
  mock-frei via monkeypatch `TELEGRAM_API_BASE` → lokaler `http.server`, der den Payload mitschneidet, ODER
  echter Send ohne reply_markup gegen Bot-API mit Response-Check (kein `reply_markup` im Result).
- AC-4: monkeypatch `TELEGRAM_API_BASE` → `http://127.0.0.1:1` → echte `ConnectError` → `OutputError` mit 2 Argumenten (Muster #645).
- AC-5: Struktur-Validierung von `BOT_COMMANDS` (reiner Daten-Check, kein Netzwerk).

## Out of Scope

- Reaktion auf Button-Klicks (`callback_query`) → Teil 6/6.
- Konkrete Befehls-Handler/Wetter-Inhalte → Teil 2–6/6.
- Persistenz von Dialog-Zuständen.
