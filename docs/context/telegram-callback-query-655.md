# Context: Telegram Hybrid-Navigation — callback_query + editMessageText (#655)

## Request Summary
Teil 6/6 von Epic #639. Die Inline-Buttons der Tier-1/2/3-Ansichten (aus #651/#653/#654)
sind aktuell **tot**: Klicks kommen als `callback_query`-Update, der Webhook-Pfad verarbeitet
aber nur `message`-Updates. Dieser Teil ergänzt die `callback_query`-Verarbeitung mit
Zoom-Navigation (`editMessageText`) und Bestätigung (`answerCallbackQuery`).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/inbound_telegram_reader.py` | `_process_update` verarbeitet NUR `message` (Z.106-108 → return False bei callback_query). Hier callback_query-Zweig ergänzen. |
| `src/outputs/telegram.py` | `TelegramOutput` hat `send`/`set_my_commands`/`get_my_commands`, ABER kein `editMessageText`/`answerCallbackQuery`. Beide ergänzen. |
| `src/services/trip_command_processor.py` | Liefert `CommandResult` mit `reply_markup`. Button-`callback_data`-Tokens: `tl_today`,`tl_tomorrow`,`glance`,`dd_<metric>_<day>`. `process()` versteht `### query: <key>` und `### dd_...`. |
| `api/routers/webhook.py` | Interner Endpoint `/api/internal/telegram-webhook`. **update_id-Dedup (`_already_seen`) existiert bereits** → AC-3 (Idempotenz) ist hier schon abgedeckt, gilt auch für callback_query (top-level `update_id`). |
| `internal/handler/telegram_webhook.go` | Go-Gateway reicht den **rohen Body unverändert** durch → callback_query-Updates kommen bereits an. **Kein Go-Change nötig.** |

## callback_data → Processor-Mapping
| Button-`callback_data` | Quelle | Processor-Body |
|---|---|---|
| `tl_today` | Tier-1-Glance + Drilldown-Zurück | `### query: timeline_heute` |
| `tl_tomorrow` | Tier-1-Glance + Drilldown-Zurück | `### query: timeline_morgen` |
| `glance` | Timeline-Zurück (Tier-2 → Tier-1) | `### query: glance` |
| `dd_thunder_today` u.ä. | Timeline-Drilldown-Buttons | `### dd_thunder_today` (Processor matcht `dd_`-Pattern direkt) |

## Existing Patterns
- **Message-Pfad** (`_process_update` Z.106-167): chat_id auflösen → user/trip resolven → Body bauen → `TripCommandProcessor().process()` → `TelegramOutput.send(..., reply_markup=)`. Callback-Pfad analog, aber **editMessageText statt send** (Nachricht ersetzen = Zoom).
- **Boundary-Capture-Test** (#637, `test_issue_637_telegram_webhook.py`): echter HTTP-POST gegen TestClient-App, ausgehender Telegram-Call an `TelegramOutput.send`/lokalem http.server beobachtet — kein Mock der Logik unter Test.
- **Idempotenz-Infra** (#637, webhook.py `_already_seen`): Seen-Set über `update_id`, greift für JEDEN Update-Typ.

## Dependencies
- Upstream: `WeatherExtractor` (Daten), `TripCommandProcessor` (Query/Drilldown-Dispatch), `TelegramOutput` (API-Calls)
- Downstream: keine — Abschluss der #639-Kette

## Existing Specs
- `docs/specs/modules/telegram_webhook_inbound.md` (#637) — Webhook-Pfad + Dedup
- `docs/specs/modules/inbound_telegram_reader.md` — Reader-Verhalten
- `docs/specs/modules/issue_653_telegram_tier2_timeline.md`, `telegram_tier3_drilldown.md` — Button-Quellen
- Neu zu erstellen: `docs/specs/modules/issue_655_telegram_callback_query.md`

## Risks & Considerations
- **answerCallbackQuery MUSS immer feuern** (AC-2), auch im Fehlerpfad → sonst hängender Lade-Spinner. Früh/`finally` aufrufen.
- **editMessageText fail-soft**: alte Nachrichten / "message is not modified" dürfen nicht crashen.
- **Multi-User-Isolation**: chat_id → echte user_id (kein `default`-Fallback bei bekanntem Chat); editMessageText im user-scoped Settings-Kontext.
- **Backend-only, keine UI-Route** → E2E-Verifikation = Verhaltenstest gegen deployten Staging-Klon (kein Playwright), wie #650/#653/#654.
