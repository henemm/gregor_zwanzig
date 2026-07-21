---
entity_id: issue_655_telegram_callback_query
type: module
created: 2026-06-08
updated: 2026-06-08
status: implemented
version: "1.0"
tags: [telegram, callback_query, navigation, epic-639]
---

# Telegram Hybrid-Navigation — callback_query + editMessageText (Zoom/Zurück)

## Approval

- [x] Approved (PO 'go' 2026-06-08)

## Purpose

Macht die Inline-Buttons aus #651/#653/#654 **klickbar**. Button-Klicks erreichen den
Bot als `callback_query`-Update; der heutige Webhook-Pfad verarbeitet nur `message`.
Dieser Teil (6/6 von Epic #639) ergänzt die `callback_query`-Verarbeitung: die
**bestehende Nachricht wird via `editMessageText` an Ort und Stelle ersetzt** (Zoom
zwischen Tier 1/2/3, „Zurück" kehrt zurück), und jeder Klick wird via
`answerCallbackQuery` bestätigt (kein hängender Lade-Spinner). Abschluss der Kette.

## Source

- **Files:** `src/services/inbound_telegram_reader.py`, `src/outputs/telegram.py`
- **Identifier:** `InboundTelegramReader._process_update` (callback-Zweig),
  `InboundTelegramReader._process_callback_query` (neu),
  `TelegramOutput.edit_message_text` (neu), `TelegramOutput.answer_callback_query` (neu)

## Estimated Scope

- **LoC:** ~120
- **Files:** 2 Source + 1 Test + 1 Spec + 1 Test-Manifest
- **Effort:** medium
- **Go-Gateway:** kein Change — reicht rohen Body unverändert durch.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripCommandProcessor.process` (#651/#654) | host | Query-/Drilldown-Dispatch über `### query:`/`### dd_` |
| Button-`callback_data` (#651/#653/#654) | input | `tl_today`,`tl_tomorrow`,`glance`,`dd_<metric>_<day>` |
| webhook.py `_already_seen` (#637) | infra | update_id-Dedup deckt callback_query bereits ab (AC-3) |
| `lookup_user_by_telegram_chat_id` (#572) | upstream | chat_id → echte user_id (Multi-User) |
| Telegram Bot API | external | `editMessageText`, `answerCallbackQuery` |

## callback_data → Processor-Body

| `callback_data` | Processor-Body |
|---|---|
| `tl_today` | `### query: timeline_heute` |
| `tl_tomorrow` | `### query: timeline_morgen` |
| `glance` | `### query: glance` |
| `dd_<metric>_<day>` | `### dd_<metric>_<day>` (Pattern-Match direkt) |

Unbekannte `callback_data` → kein Dispatch, aber **trotzdem** `answerCallbackQuery`
(Spinner beenden), kein editMessageText.

## Acceptance Criteria

**AC-1 (= #639 AC-4): Zoom-Navigation via editMessageText.**
Given ein Klick auf einen Tier-1-Button (`callback_data=tl_today`),
When der `callback_query` im Webhook-Pfad verarbeitet wird,
Then wird die ursprüngliche Nachricht via `editMessageText` (gleicher `chat_id` +
`message_id`) durch den Tier-2-Inhalt (Timeline heute) **ersetzt** — keine neue
Nachricht angehängt — und das neue `reply_markup` enthält einen „Zurück"-Button
(`callback_data=glance`).

**AC-2: answerCallbackQuery wird immer aufgerufen.**
Given ein beliebiger Button-Klick (auch mit unbekanntem/leerem `callback_data` oder
bei Fehler in der Verarbeitung),
When der `callback_query` verarbeitet wird,
Then wird `answerCallbackQuery` mit der `callback_query.id` aufgerufen, sodass der
Telegram-Lade-Spinner beendet wird.

**AC-3: Idempotenz gegen Doppel-Zustellung.**
Given derselbe `callback_query` wird zweimal zugestellt (Telegram-Retry, gleiche
top-level `update_id`),
When beide Updates den Webhook erreichen,
Then wird nur der erste verarbeitet (ein `editMessageText`), der zweite als Duplikat
verworfen (`status=duplicate`), analog zum Seen-Set aus #637.

**AC-4: Drilldown-Navigation (Tier 2 → Tier 3 → zurück).**
Given ein Klick auf einen Drilldown-Button (`callback_data=dd_thunder_today`),
When verarbeitet,
Then wird die Nachricht via `editMessageText` durch den stündlichen Gewitter-Drilldown
ersetzt und bietet einen „Zurück"-Button (`callback_data=tl_today`) zurück zur Timeline.

**AC-5: Multi-User-Isolation.**
Given zwei verschiedene Nutzer mit je eigenem `telegram_chat_id` und eigenem aktiven
Trip, When jeder einen Button in seinem Chat klickt,
Then wird `editMessageText` jeweils an die **eigene** `chat_id` gesendet und der Inhalt
stammt aus dem **eigenen** Trip des klickenden Nutzers — niemals Fallback auf einen
fremden oder `default`-Trip bei bekanntem Chat.

## Implementation Details

```python
# inbound_telegram_reader.py — _process_update Anfang:
callback = update.get("callback_query")
if callback:
    return self._process_callback_query(callback, settings)

_CALLBACK_QUERY_MAP = {
    "tl_today": "timeline_heute",
    "tl_tomorrow": "timeline_morgen",
    "glance": "glance",
}

def _process_callback_query(self, callback, settings) -> bool:
    cq_id = callback.get("id")
    data = (callback.get("data") or "").strip()
    msg = callback.get("message") or {}
    chat_id = str(msg.get("chat", {}).get("id", ""))
    message_id = msg.get("message_id")
    user_id, user_settings = self._resolve_user_for_chat(chat_id, settings)
    out = TelegramOutput(user_settings)
    try:
        body = self._callback_to_body(data)        # None bei unbekannt
        if body and message_id is not None:
            trip = self._find_active_trip(user_id)
            if trip:
                result = TripCommandProcessor().process(InboundMessage(... body, user_id ...))
                out.edit_message_text(chat_id, message_id,
                    f"[{result.confirmation_subject}]\n\n{result.confirmation_body}",
                    reply_markup=result.reply_markup)
    finally:
        if cq_id:
            out.answer_callback_query(cq_id)       # AC-2: immer
    return True
```

`TelegramOutput.edit_message_text(chat_id, message_id, text, reply_markup=None)` →
POST `editMessageText` (fail-soft: loggt Fehler, kein Raise — alte Nachricht/„not
modified" darf nicht crashen).
`TelegramOutput.answer_callback_query(callback_query_id, text=None)` → POST
`answerCallbackQuery` (fail-soft).

## Test Strategy (mock-frei)

- **Boundary-Capture** wie #637: echter HTTP-POST gegen TestClient
  (`/api/internal/telegram-webhook`) mit `callback_query`-Body; ausgehende Telegram-Calls
  gegen lokalen `http.server` (echter Socket) via `TELEGRAM_API_BASE`-Umlenkung beobachten.
- **AC-1/AC-4:** verifizieren dass `editMessageText` (nicht `sendMessage`) gerufen wird,
  mit korrektem `chat_id`/`message_id` und „Zurück"-Button im `reply_markup`.
- **AC-2:** `answerCallbackQuery` wird auch bei unbekanntem `callback_data` gerufen.
- **AC-3:** zweimal gleiches Update → zweite Antwort `status=duplicate`, nur ein edit.
- **AC-5:** zwei echte temporäre Nutzer (user.json), reale `lookup_user_by_telegram_chat_id`.

## Non-Goals

- Keine Go-Änderung (Gateway reicht Body durch).
- Keine neuen Button-Layouts/Inhalte (kommen aus #651/#653/#654).
- Kein Polling-Pfad-Umbau (`poll_and_process` bleibt; live ist der Webhook).
