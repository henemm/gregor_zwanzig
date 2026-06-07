# Context: #650 Telegram-Foundation — Inline-Keyboards + persistentes Bot-Menü

## Request Summary
Teil 1/6 von #639. Technische Basis für interaktive Telegram-Nachrichten: `TelegramOutput.send()`
soll optional `reply_markup` (Inline-Keyboard-Buttons) tragen, und es soll ein einmaliges
Bot-Menü-Setup via `setMyCommands` geben (analog zu `setWebhook` aus #637). Reines Plumbing,
keine Wetter-Datenlogik, keine Button-Klick-Reaktion (das ist Teil 6/6).

## Related Files
| File | Relevance |
|------|-----------|
| `src/outputs/telegram.py` | `TelegramOutput.send(subject, body)` — hier `reply_markup` ergänzen; baut `sendMessage`-Payload |
| `src/outputs/base.py` | `OutputChannel`-Protocol definiert `send(subject, body)` — Signatur-Kompatibilität wahren (reply_markup nur optionales kwarg) |
| `scripts/telegram_set_webhook.sh` | Referenz-Pattern für einmaliges Bot-Setup (set/delete/info via curl gegen Bot-API) — `setMyCommands` analog |
| `src/app/config.py` | `Settings.telegram_bot_token`, `telegram_chat_id` (Felder vorhanden) |
| `tests/tdd/test_telegram_output.py` | Bestehende Telegram-Output-Tests (Protocol/Factory/Roundtrip) |
| `tests/tdd/test_issue_637_telegram_webhook.py` | Webhook-Testpattern (mock-frei, monkeypatch nur fürs Routing) |
| `tests/tdd/test_issue_645_telegram_outputerror_arity.py` | Mock-freier HTTPError-Test via monkeypatch `TELEGRAM_API_BASE` → echte ConnectError |

## Existing Patterns
- **Bot-API-Call:** `httpx.post(f"{TELEGRAM_API_BASE}/bot{token}/sendMessage", json=payload, timeout=10)`,
  Status 200 → ok, sonst `OutputError("telegram", ...)`. (`telegram.py:35-60`)
- **Einmal-Setup (Bot-Methoden):** Shell-Script gegen `api.telegram.org/bot<token>/<method>` mit
  set/delete/info-Subcommands (`telegram_set_webhook.sh`). `setMyCommands`/`getMyCommands` passen exakt in dieses Muster.
- **`OutputError`-Arität:** IMMER 2 Argumente `OutputError("telegram", msg)` (Lehre #645).
- **Mock-frei testen (Fehlerpfad):** `monkeypatch.setattr(telegram, "TELEGRAM_API_BASE", "http://127.0.0.1:1")` → echte `ConnectError`.

## Dependencies
- Upstream: `httpx`, `Settings` (Bot-Token/Chat-ID), `OutputError`.
- Downstream: Teil 2/6–6/6 von #639 (Text-Kurzbefehle, callback_query). Buttons sind nach #650 sichtbar,
  aber noch ohne Klick-Reaktion. Scheduler/Briefing-Pipeline ruft `send()` weiter ohne `reply_markup` auf → muss unverändert funktionieren.

## Existing Specs
- Keine bestehende Telegram-Output-Spec. Neue Spec: `docs/specs/modules/feature_650_telegram_inline_keyboards.md`.

## Risks & Considerations
- **Protokoll-Kompatibilität:** `OutputChannel.send(subject, body)` ist fix. `reply_markup` MUSS optionales
  kwarg mit Default `None` sein → Altpfad (Scheduler/Briefings) bleibt bit-identisch.
- **Mock-frei gegen echte Bot-API (AC-1/AC-2):** braucht ein echtes Bot-Token + Chat. In ENV aktuell KEIN
  Token (`GZ_TELEGRAM_BOT_TOKEN` leer). Staging-Bot ist von Prod getrennt (#637). Test-Strategie: Token aus
  ENV (`GZ_TELEGRAM_BOT_TOKEN` + `GZ_TELEGRAM_TEST_CHAT_ID`) ziehen; fehlt es → `pytest.skip` (kein Mock-Ersatz),
  echter Lauf in der Acceptance-Stage gegen Staging-Bot.
- **`reply_markup`-Serialisierung:** Telegram erwartet `reply_markup` als JSON-Objekt im Payload
  (bei `json=`-POST automatisch serialisiert). InlineKeyboardMarkup = `{"inline_keyboard": [[{"text":..,"callback_data"/"url":..}]]}`.
- **LoC-Limit 250:** Plumbing, sollte locker passen.
