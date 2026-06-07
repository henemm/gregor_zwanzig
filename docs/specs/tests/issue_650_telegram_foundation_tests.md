---
entity_id: issue_650_telegram_foundation_tests
type: tests
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [telegram, outputs, inline-keyboard, bot-commands, tests, epic-639]
---

# Tests: #650 Telegram-Foundation — Inline-Keyboards + persistentes Bot-Menü

Test-Spec zu `docs/specs/modules/feature_650_telegram_inline_keyboards.md`.

Mock-frei auf zwei Ebenen (KEIN `Mock()`/`patch()`/`MagicMock`):
1. **Echte Telegram-Bot-API** — gated auf `GZ_TELEGRAM_BOT_TOKEN` + `GZ_TELEGRAM_TEST_CHAT_ID`;
   lokal übersprungen (`pytest.skip`), echter Lauf in der Acceptance-Stage gegen den Staging-Bot.
2. **Lokaler Real-HTTP-Server** (`http.server`, echter Socket, echter `httpx`-Code-Pfad) — schneidet
   den tatsächlich gesendeten Payload mit. `monkeypatch.setattr` auf die Modul-Konstante
   `TELEGRAM_API_BASE` ist erlaubt (Muster #645), das ist kein Mock.

## Test-Fälle

- **test_send_with_reply_markup_puts_inline_keyboard_on_the_wire** — `send(subject, body, reply_markup=...)`
  gegen den lokalen Real-Server; der mitgeschnittene Payload trägt `reply_markup.inline_keyboard[0][0]`
  mit `text == "🌤️ Briefing"` und `callback_data == "briefing"` (AC-1). RED vor Fix (`send()` akzeptiert
  kein `reply_markup`-kwarg → `TypeError`), GRÜN danach.
- **test_send_without_reply_markup_has_no_reply_markup_key** — `send(subject, body)` ohne `reply_markup`
  erzeugt einen Payload OHNE `reply_markup`-Schlüssel; `text == "[Test #650]\n\nBody"` (AC-3). Behavior-Guard.
- **test_telegramoutput_still_satisfies_protocol** — `TelegramOutput` erfüllt weiterhin das
  `OutputChannel`-Protocol (`isinstance`-Check, `name == "telegram"`) (AC-3).
- **test_set_then_get_my_commands_roundtrip** — `set_my_commands()` gefolgt von `get_my_commands()`
  liefert exakt dieselbe Befehlsliste (gleiche `command`-Werte in gleicher Reihenfolge) (AC-2). RED vor
  Fix (Methoden existieren nicht → `AttributeError`), GRÜN danach.
- **test_set_my_commands_accepts_explicit_list** — `set_my_commands(custom)` verwendet die übergebene
  Liste statt `BOT_COMMANDS`; `get_my_commands()` spiegelt sie zurück (AC-2/AC-5). RED vor Fix, GRÜN danach.
- **test_send_with_reply_markup_unreachable_raises_outputerror** — bei unerreichbarer API
  (`monkeypatch` → `http://127.0.0.1:1`, echte `ConnectError`) wirft `send(..., reply_markup=...)` einen
  `OutputError(channel="telegram")` mit Präfix `[telegram]` — KEIN `TypeError` (AC-4, Muster #645). RED vor
  Fix (kwarg-`TypeError` entweicht `pytest.raises(OutputError)`), GRÜN danach.
- **test_bot_commands_structure_is_telegram_valid** — reiner Daten-Check: jeder `BOT_COMMANDS`-Eintrag
  hat `command` (1–32 Zeichen, `[a-z0-9_]`) und `description` (1–256 Zeichen), keine Duplikate (AC-5). RED
  vor Fix (`BOT_COMMANDS` existiert nicht → `AttributeError`/`ImportError`), GRÜN danach.
- **test_real_api_send_with_inline_keyboard_returns_buttons** — kanonischer AC-1-Nachweis gegen die ECHTE
  Bot-API: `send(..., reply_markup=...)` + direkter `sendMessage`-Read bestätigt HTTP 200 und das im
  Result enthaltene Inline-Keyboard (AC-1). `skipif` ohne `GZ_TELEGRAM_BOT_TOKEN`/`GZ_TELEGRAM_TEST_CHAT_ID`.
- **test_real_api_set_get_my_commands_roundtrip** — kanonischer AC-2-Nachweis gegen die ECHTE Bot-API:
  `set_my_commands()` → `get_my_commands()` liefert dieselbe Liste (AC-2). `skipif` ohne `GZ_TELEGRAM_BOT_TOKEN`.

## Behavior-Preservation

Der Altpfad `send(subject, body)` ohne `reply_markup` bleibt bit-identisch (kein `reply_markup`-Schlüssel
im Payload), das `OutputChannel`-Protocol bleibt erfüllt. Alle Neuerungen sind additiv.
