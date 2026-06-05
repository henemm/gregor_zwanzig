# Context: issue-612-report-on-demand

## Request Summary
Wanderer sollen jederzeit per E-Mail-Antwort oder Telegram-Nachricht ein Morgen-/Abend-Briefing
adhoc abrufen können (`report morning|evening`), und in jedem ausgehenden Briefing einen Hinweis
auf die verfügbaren Befehle sehen ("Befehle immer anhängen").

## Befund: Feature zu ~80 % vorhanden
Der Befehl `report` ist bereits vollständig im Inbound-System implementiert (E-Mail + Telegram),
steht in der `hilfe` und löst echte Briefings aus. Es fehlen: (1) der sichtbare Befehls-Footer in
ausgehenden Briefings, (2) korrekter User-Kontext beim On-Demand-Abruf.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_command_processor.py` | `_trigger_report` (Z.215) instanziiert `TripReportSchedulerService()` ohne user_id → default. `_find_trip` (Z.147) nutzt `load_all_trips()` ohne user_id. `InboundMessage` (Z.30) hat kein `user_id`-Feld. |
| `src/services/inbound_email_reader.py` | Löst `_user_id` via `lookup_user_by_email` (Z.97/223), baut `InboundMessage` (Z.131) — übergibt user_id NICHT. |
| `src/services/inbound_telegram_reader.py` | Löst `user_id` via `lookup_user_by_telegram_chat_id` (Z.110/185), baut `InboundMessage` (Z.131) — übergibt user_id NICHT. |
| `src/output/renderers/email/html.py` | `render_html` pure function; HTML-Footer-`<div>` bei Z.586. Hier Befehls-Block anhängen. |
| `src/output/renderers/narrow.py` | `render_narrow` pure function für signal+telegram; Body-Aufbau endet Z.208. Footer NUR für `channel=="telegram"`. |
| `src/services/trip_report_scheduler.py` | `__init__(user_id="default")` (Z.152), `send_test_report` (Z.310). Wird vom Processor aufgerufen. |
| `src/formatters/trip_report.py` | Ruft `render_narrow("signal"/"telegram")` (Z.151-173); `render_html` erzeugt `email_html`. |

## Existing Patterns
- **Inbound-Befehl:** `### key: value` (Mail) bzw. Freitext (Telegram) → `TripCommandProcessor.process` → `CommandResult`.
- **User-Scoping:** Reader lösen `user_id` aus Sender und bauen `settings.with_user_profile(user_id)`; `load_all_trips(user_id)`.
- **Renderer = pure functions:** Footer-Anhang ohne I/O direkt im Body-String.
- **Telegram-Body:** `render_narrow("telegram", ...)`; Signal-Body separat (`render_narrow("signal", ...)`).

## Dependencies
- Upstream: `TripReportSchedulerService` (Scheduling/Versand), `load_all_trips(user_id)`, `lookup_user_by_*`.
- Downstream: Inbound-Reader (Mail/Telegram), Formatter `trip_report.py` (nutzt Renderer).

## Existing Specs
- `docs/specs/modules/trip_command_processor.md` v2.1 — Befehls-Verarbeitung
- `docs/specs/modules/trip_report_scheduler.md` v1.0
- `docs/specs/modules/issue_360_signal_channel_renderer.md` — narrow-Renderer

## Risks & Considerations
- **Channel-Trennung:** Footer NUR auf Telegram (kein Signal-Inbound, Issue nennt nur Mail+Telegram). SMS ohnehin kein Rückkanal.
- **report_type "alert":** Footer ist auch auf Alert-Mails harmlos/nützlich → unconditional anhängen.
- **Telegram max_chars:** Footer vor der bestehenden Überlängen-Kappung anhängen; Limit (4096) reicht.
- **User-Durchreichung:** `InboundMessage.user_id` additiv (Default "default") → keine Breaking Change, Reader füllen es.
- **5 Dateien** = an der Scoping-Grenze, aber LOC klein (~40).
