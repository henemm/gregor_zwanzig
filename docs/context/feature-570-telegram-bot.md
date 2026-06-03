# Context: Feature 570 — Telegram-Bot als Eingangs- und Ausgangskanal

## Request Summary
Gregor erhält einen Telegram-Bot als zweiten Inbound-Kanal: Nutzer sendet Befehle wie `ruhetag` direkt als Telegram-Nachricht; der Bot antwortet sofort und sendet auch Morgen-/Abend-Briefings als Telegram-Nachricht.

## Related Files
| File | Relevanz |
|------|----------|
| `src/outputs/telegram.py` | TelegramOutput (Ausgangskanal) **bereits vollständig implementiert** |
| `src/services/inbound_email_reader.py` | Referenzimplementierung für Inbound-Reader-Pattern |
| `src/services/trip_command_processor.py` | TripCommandProcessor + InboundMessage DTO — channel-agnostisch |
| `src/app/config.py` | telegram_bot_token, telegram_chat_id, can_send_telegram() |
| `api/routers/scheduler.py` | Scheduler-Router mit /inbound-commands Endpoint + Telegram-Dispatch |
| `docs/specs/modules/inbound_command_channels.md` | Architektur-Spec für Inbound-Channels |
| `docs/specs/modules/telegram_output.md` | Spec für TelegramOutput (bereits implementiert) |
| `tests/tdd/test_telegram_output.py` | Bestehende Telegram-Tests |
| `tests/tdd/test_trip_command_processor.py` | Bestehende Processor-Tests |

## Existing Patterns
- **Inbound-Reader-Pattern:** `poll_and_process(settings) → int` (Anzahl verarbeiteter Befehle)
- **DTO:** `InboundMessage(trip_name, body, sender, channel, received_at)`
- **Antwort gleicher Kanal:** Email-Reader → EmailOutput; Telegram-Reader → TelegramOutput
- **Befehlsformat Email:** `### key: value` (strukturierter Prefix wegen Body-Parsing)
- **Befehlsformat Telegram (neu):** Freitext `ruhetag` oder `ruhetag 2` (kein Prefix nötig)

## Was bereits vorhanden ist
- `TelegramOutput.send(subject, body)` — voll implementiert (fire-and-forget, httpx)
- `telegram_bot_token` + `telegram_chat_id` in Settings + `.env` konfiguriert
- `can_send_telegram()` in Settings
- `TripCommandProcessor` mit Befehlen: `ruhetag`, `report`, `startdatum`, `abbruch`
- Scheduler-Router hat bereits `/inbound-commands` Endpoint (Email-Reader)

## Was fehlt (Scope)
1. `InboundTelegramReader` — long-polling via `getUpdates` API
2. Einfachere Befehlssyntax: `ruhetag [N]`, `startdatum YYYY-MM-DD` (kein `### `)
3. Trip-Kontext ohne Subject: Bot kennt user → aktiver Trip (via Settings oder automatische Auswahl)
4. `status` + `hilfe` Befehle im TripCommandProcessor (Issue #570 nennt sie)
5. Scheduler-Integration für Telegram-Polling-Job

## Offene Design-Frage
**Trip-Kontext-Auflösung:** Email braucht `[Trip Name]` im Subject; beim Telegram-Bot gibt es kein Subject. Optionen:
- A) Aktiver Trip = Trip mit heutigem Datum (oder nächstem Startdatum) — automatisch
- B) User kann explizit Trip wählen: `trip GR20` setzt aktiven Context-Trip
- Empfehlung: Option A (einfachster Weg, passt zu Single-User-Setup)

## Dependencies
- Upstream: `telegram_bot_token`, `telegram_chat_id` in Settings (bereits vorhanden)
- Downstream: `api/routers/scheduler.py` (neuer `/inbound-telegram` Endpoint analog zu `/inbound-commands`)
- External: Telegram Bot API `https://api.telegram.org/bot{TOKEN}/getUpdates`

## Existing Specs
- `docs/specs/modules/inbound_command_channels.md` — Architektur-Referenz (Email-Kanal)
- `docs/specs/modules/telegram_output.md` — Output-Spec
- `docs/specs/modules/trip_command_processor.md` — Command-Processor-Spec

## Risks & Considerations
- **Long-Polling vs. Webhook:** Long-polling ist einfacher (kein öffentlicher Endpoint nötig, kein Nginx-Config); Webhook wäre eleganter aber braucht HTTPS-Endpunkt + Registrierung
- **Befehlssyntax-Kompatibilität:** Neuer Telegram-Parser darf `TripCommandProcessor` nicht brechen (der bleibt `### key` kompatibel für Email)
- **Keine Mocks!** Tests müssen echte Telegram-API nutzen (Bot-Token + Chat-ID vorhanden)
