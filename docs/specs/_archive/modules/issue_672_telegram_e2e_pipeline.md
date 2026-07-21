---
entity_id: issue_672_telegram_e2e_pipeline
type: module
created: 2026-06-08
updated: 2026-06-08
status: draft
version: "1.0"
tags: [telegram, e2e, tests, epic-639]
---

# Telegram E2E-Pipeline-Tests (Issue #672)

## Approval

- [x] Approved (2026-06-08, PO)

## Purpose

Schließt die Test-Lücke im Telegram-Kanal: Bisher prüfen #651/#653/#654 den
`TripCommandProcessor` **direkt** (isoliert) und #655 nur den `callback_query`-Pfad
durch den Webhook. **Kein** Test treibt einen echten **Text-Befehl** durch die
komplette Pipeline (Webhook → `_process_update` → `_parse_command` →
`_find_active_trip` → echter Processor → echter `TelegramOutput`) und beweist den
ausgehenden `sendMessage` mit Inhalt **und** Inline-Keyboard. Genau dort sitzt die
Verdrahtung, in der Bug **#671** lebt: das `setMyCommands`-Menü bewirbt Befehle
(`/briefing`, `/wetter`), die der Parser nicht kennt → „Unbekannter Befehl".

## Source

- **File (neu, Test):** `tests/tdd/test_e2e_telegram_pipeline.py`
- **Identifier:** Pipeline-E2E gegen `api.main:app` (FastAPI-`TestClient`)
- **Fix #671 (PO-Entscheidung: gleich mitfixen) — Python-Backend:**
  - `src/outputs/telegram.py` → `BOT_COMMANDS` auf das **vollständige Menü** setzen
    (PO-Entscheidung): glance, heute, morgen, heute_gewitter, timeline_heute,
    timeline_morgen, hilfe — alle mit gültigen Telegram-Command-Namen.
  - `src/services/inbound_telegram_reader.py` → `_SHORTCUT_MAP` um die
    **Slash-Varianten** der Menü-Befehle ergänzen (`/glance`→glance, `/heute`→heute,
    … `/hilfe`→hilfe), weil Telegram getippte/getappte Menü-Befehle **mit führendem
    Slash** sendet — die aktuelle Wurzel von #671.
- **Unter Test, nicht verändert:** `api/routers/webhook.py`,
  `src/services/trip_command_processor.py`

## Estimated Scope

- **LoC:** ~210 Test + ~12 Fix (#671) = ~222
- **Files:** 1 neu (Test) + 2 berührt (Fix) (+ Test-Manifest in `docs/specs/tests/`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `api/routers/webhook.py` | Endpoint | Eintrittspunkt der Pipeline (`/api/internal/telegram-webhook`) |
| `inbound_telegram_reader.py` | Service | Routing Text/Callback, Parse, User-Auflösung |
| `trip_command_processor.py` | Service | Echte Query-/Mutations-Verarbeitung |
| `outputs/telegram.py` | Output | `sendMessage` + `BOT_COMMANDS` (Menü-Vertrag) |
| Staging-Bot `GregorZwanzigStaging_bot` | extern | Stufe B (Live-Smoke, gated) |

## Implementation Details

**Mock-frei** nach Projekt-Standard, Muster aus `test_issue_655_*`:
- Echter Trip + Wetter-Snapshot in `tmp_path` (Disk-I/O, `get_data_dir`-Redirect).
- Lokaler `http.server`-Socket fängt ausgehende Bot-API-Calls
  (`monkeypatch outputs.telegram.TELEGRAM_API_BASE`) — **kein** Stub von
  `TelegramOutput.send` oder `Processor.process` (Unterschied zu #637!).
- Webhook-Payloads (echte Telegram-`message`- bzw. `callback_query`-Updates) via
  `TestClient` an `/api/internal/telegram-webhook`.
- **Stufe B (Live):** echte Bot-API gegen Staging-Bot, gated über
  `GZ_TELEGRAM_BOT_TOKEN` + `GZ_TELEGRAM_TEST_CHAT_ID`; ohne Env → `skip`.

## Expected Behavior

- **Input:** echtes Telegram-Update (Text bzw. callback_query) als HTTP-POST.
- **Output:** beobachtbare ausgehende Bot-API-Calls am Socket (`sendMessage`,
  `editMessageText`, `answerCallbackQuery`) mit Payload-Assertions.
- **Side effects:** keine (Snapshot/Trip in `tmp_path`; Live-Stufe sendet+löscht).

## Acceptance Criteria

- **AC-1:** Given ein aktiver Trip + Snapshot und der Webhook-Endpoint /
  When ein Text-Update `/s` (Glance) an `/api/internal/telegram-webhook` gepostet wird /
  Then wird am Socket **genau ein** `sendMessage` an die richtige `chat_id` erfasst,
  dessen Text die Glance-Info (heute **und** morgen) enthält und dessen
  `reply_markup.inline_keyboard` mindestens einen Button trägt — ohne Stub von
  Processor oder Output.
  - Test: `client.post(WEBHOOK, message="/s")` → `sendMessage`-Payload prüfen.

- **AC-2:** Given derselbe aktive Trip + Snapshot /
  When ein Text-Update `/th` (timeline_heute) durch den Webhook läuft /
  Then trägt der ausgehende `sendMessage` Timeline-Inhalt und mindestens einen
  Drilldown-Button (`callback_data` beginnt mit `dd_` oder navigiert weiter).
  - Test: `client.post(WEBHOOK, message="/th")` → Timeline-`sendMessage` prüfen.

- **AC-3:** Given die Bot-Menü-Befehle aus `BOT_COMMANDS` (vollständiges Menü) /
  When jeder davon **mit führendem Slash** (`/glance`, `/heute`, …, so wie Telegram
  einen getappten Menü-Befehl sendet) als Text durch den Webhook läuft /
  Then ergibt **jeder** eine *unterstützte* Antwort — der ausgehende `sendMessage`
  enthält **nicht** „Unbekannter Befehl". (Behebt **#671**; rot vor Fix, grün nach
  Fix von `BOT_COMMANDS` + `_SHORTCUT_MAP`.)
  - Test: Schleife über `BOT_COMMANDS`, je `/`+command durch den Webhook,
    `sendMessage`-Text auf „Unbekannter Befehl" prüfen.

- **AC-4:** Given die Inline-Buttons aus der Glance-Antwort (AC-1) /
  When deren `callback_data` gegen den Callback-Pfad geprüft wird /
  Then akzeptiert `InboundTelegramReader._callback_to_body` **jedes** dieser
  `callback_data` (≠ `None`) — kein toter Menü-Button (Schließt die Schleife mit #655).
  - Test: jeden Button-`callback_data` durch `_callback_to_body` schicken, ≠ None.

- **AC-5:** Given gesetzte `GZ_TELEGRAM_BOT_TOKEN` + `GZ_TELEGRAM_TEST_CHAT_ID` /
  When der Live-Smoke gegen den Staging-Bot läuft /
  Then antwortet `getMe` mit `ok=True` und ein `sendMessage`→`editMessageText`→
  `deleteMessage`-Zyklus gegen den Test-Chat liefert je `ok=True`; ohne Env wird
  der Test sauber übersprungen (kein Fehler).
  - Test: gated `@pytest.mark.skipif`, echte Bot-API, sauberer `deleteMessage`.

## Known Limitations

- Stufe B kann gesendete Nachrichten nicht zurücklesen (Bot, Webhook-Modus) →
  Verifikation via `sendMessage`→`editMessageText`→`deleteMessage`, nicht Read-Back.
- Telegram-Command-Namen sind auf `[a-z0-9_]`, 1–32 Zeichen begrenzt — die gewählten
  Menü-Namen (glance, heute, morgen, heute_gewitter, timeline_heute, timeline_morgen,
  hilfe) erfüllen das.

## PO-Entscheidungen (2026-06-08)

- **#671 gleich mitfixen** (statt nur dokumentieren) — AC-3 wird grün nach Fix.
- **Vollständiges Menü** — alle Abfragen im Bot-Menü (maximale Entdeckbarkeit).

## Changelog

- 2026-06-08: Implementation complete (Issue #672) — E2E tests + Fix #671 (Bot-Menü Vollständigkeit + Slash-Varianten)
- 2026-06-08: Initial spec created
