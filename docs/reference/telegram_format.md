---
entity_id: telegram_format
type: reference
version: "1.0"
status: active
created: 2026-10-21
updated: 2026-10-21
tags: [telegram, channel, renderer, inbound, reference]
---

# Telegram-Format — Referenz (Ist-Stand)

Beschreibt, wie der Kanal **Telegram** heute rendert, versendet und Befehle annimmt. Reiner
Ist-Stand aus dem Code (Stand 2026-10-21), keine Bewertung. Entscheidungen: ADR-0012
(`parse_mode="HTML"`), ADR-0014 (Multi-Bubble), ADR-0095 (Kanal-Parität). Kürzel-/Token-Vertrag der
Kurzform: `docs/reference/sms_format.md`.

## 1. Transport

| Eigenschaft | Wert |
|---|---|
| API | Telegram Bot API `sendMessage` / `editMessageText` / `answerCallbackQuery` / `setMyCommands` |
| Empfänger | `telegram_chat_id` aus `user.json` (einziger Schreiber `POST /api/internal/telegram-connect`, #2141) |
| Längenlimit | **4096 Zeichen je Nachricht** (`MAX_MESSAGE_LENGTH`). Länger → gekürzt; bei HTML tag-sicher (`_truncate_html` schließt offene Tags), sonst hart. Kein Aufteilen auf mehrere Nachrichten |
| Formatierung | `parse_mode="HTML"` für formatierte Nachrichten (`<b>`, `<pre>`); Nutzdaten laufen durch dieselbe `_esc()`-Maskierung wie E-Mail-HTML (ADR-0012). Default bleibt `parse_mode=None` |
| HTML-Fehler | Antwortet Telegram mit HTTP 400 auf eine HTML-Nachricht, wird **einmal ohne `parse_mode`** nachgesendet (Tags gestrippt, Entities unescaped) |
| Drossel | Sende-Slot je Chat (`telegram_rate_limit_max_per_window`); Wartezeit hart gedeckelt auf 30 s (`SEND_SLOT_MAX_WAIT_SECONDS`); 429 → `retry_after` (Fallback 1 s) |
| Tabellenbudget | `CHANNEL_LIMITS["telegram"]` = max. 8 Tabellenspalten (inkl. Zeit/Ort), 4096 Zeichen |

## 2. Varianten

Der Stil wird je Trip/Vergleich über `report_config.telegram_style` gewählt: `rich` (Default) oder
`kurzform` (#1260).

| Variante | `rich` | `kurzform` |
|---|---|---|
| **Trip-Briefing** | **Multi-Bubble** (ADR-0014): Folge einzelner `sendMessage`-Aufrufe, `parse_mode="HTML"`. Reihenfolge: Kopf → ggf. „amtliche Warnungen nicht abrufbar“ → ggf. Starkregen-Kurzfristhinweis → ggf. amtliche Warnungen → Kurzübersicht (alle konfigurierten Metriken) → je Segment/Ziel eine `<pre>`-Tabelle → optional Ausblick → Aktionen-Bubble mit Inline-Keyboard (nur letzte Bubble trägt `reply_markup`). Scheitern Bubbles, folgt ein Hinweis „unvollständig“ | **eine** Nachricht mit dem SMS-Text (`report.sms_text`), `parse_mode=None`, keine Bubbles/Knöpfe |
| **Ortsvergleich-Briefing** | **eine** Nachricht aus `render_compare_telegram()` (kein Score/Rang, ≤ 7 Metrikwerte je Ort, ≤ 4096 Zeichen), `parse_mode=None` | SMS-Vergleichstext (`render_compare_sms`), eine Nachricht, `parse_mode=None` (`scheduler_dispatch_service.py:697`) |
| **Änderungs-/Radar-Alarm** | eine Nachricht aus `alert/render.py::render_telegram()` (fette Kopfzeile, dieselben Sätze wie die E-Mail, #2020), `parse_mode="HTML"`; Ortsvergleich ggf. je Ort aufgefächert | **eine** gemeinsame Nachricht mit dem SMS-Alarmtext, Vorrang vor dem Fan-out je Ort (#1467 K-6) |
| **Amtliche Warnung** | reiche Warnvorlage `render_official_alert_telegram` (+ Entwarnung), `parse_mode="HTML"`, ohne Betreffzeile | SMS-Text, `parse_mode=None` |
| **Befehlsantwort** | Klartext-Bestätigung, optional mit Inline-Keyboard (Zoom-Navigation per `callback_query` + `editMessageText`, #655) | — |

**Stundenzeilen im Änderungs-Alarm (`rich`, #1737):** Unter der Kopfzeile jedes Ereignisses steht je betroffener Stunde eine Zeile `HH:MM | alt → neu` (Ortszeit), dieselben Stunden wie in der E-Mail. Trip: Zellformat (ROH oder EINFACH) des Telegram-Briefings desselben Trips; Ortsvergleich: Werte roh, nur unter betroffenen Orten. Höchstens 6 stärkste Stunden in Zeitfolge plus Hinweiszeile „betroffen HH:MM–HH:MM"; Summen-Metriken tragen die Summe in der Kopfzeile. Ohne Anker nur der neue Wert, ohne Stundenreihe unverändert. Nur Daten, keine Empfehlung. Die Kurzform (`kurzform`) sendet den SMS-Alarmtext mit der Zeitspanne `HH-HH` (`sms_format.md` §3.4f).

## 3. Befehlseingang (Inbound)

Telegram **hat** einen Befehlseingang — push-basiert, kein Poll-Job (`inbound_telegram_poll`
entfernt, #637/#1369).

- **Weg:** Telegram → `POST /api/webhooks/telegram/inbound` (Go, öffentlich; einziger
  Auth-Träger ist der Header `X-Telegram-Bot-Api-Secret-Token`, kein Secret im Pfad, #1814;
  die Alt-Route `/api/webhooks/telegram/{secret}` besteht nur als Übergang) →
  `POST /api/internal/telegram-webhook` (Python, Dedupe über `update_id`) →
  `InboundTelegramReader._process_update`.
- **Nutzerzuordnung:** über die Chat-ID (`lookup_user_by_telegram_chat_id`), nie Fallback auf
  `default`.
- **Eingabeformen:** Freitext-Befehle ohne Präfix und Slash-Befehle aus dem Bot-Menü
  (`BOT_COMMANDS`, deutsch + englisch, z. B. `/heute`, `/morgen`, `/jetzt`, `/gewitter`, `/strecke`,
  `/ruhetag`, `/status`, `/pause`, `/skip`, `/stop`, `/weiter`, `/kuerzel`, `/report`,
  `/startdatum`); Inline-Knöpfe liefern `callback_query`. Das Bot-Menü wird beim Start des
  Python-Core gesetzt (`_init_telegram_bot_menu`).
- **Verarbeitung/Antwort:** gemeinsamer `TripCommandProcessor` (`channel="telegram"`), Antwort über
  `send_command_reply_telegram` an denselben Chat. Telegram-Antworten tragen Emojis
  (`with_emoji = channel == "telegram"`), Ad-hoc-Verläufe ausgeschrieben (nicht Kurzform, s.
  `sms_format.md` §5a).

## 4. Quelle im Code

| Was | Datei:Zeile |
|---|---|
| Längenlimit 4096 | `src/output/channels/telegram.py:25` |
| Tag-sichere Kürzung | `src/output/channels/telegram.py:53` (`_truncate_html`) |
| Bot-Menü-Befehle | `src/output/channels/telegram.py:132` (`BOT_COMMANDS`), `:691` (`set_my_commands`), `api/main.py:72` |
| Sende-Drossel | `src/output/channels/telegram.py:327` (`_reserve_send_slot`) |
| Versand + 400-Fallback ohne `parse_mode` | `src/output/channels/telegram.py:474`, `:534`, `:560` |
| Zoom-Navigation | `src/output/channels/telegram.py:637` (`edit_message_text`), `:668` (`answer_callback_query`) |
| Bubble-Datentyp / Briefing-Renderer | `src/output/renderers/narrow.py:380`, `:659` (`render_telegram_bubbles`) |
| Hinweis „unvollständig“ | `src/output/renderers/narrow.py:640` |
| Spalten-/Zeichenbudget | `src/output/renderers/channel_layout.py:48` |
| Briefing-Versand (kurzform / Bubble-Schleife) | `src/services/notification_service.py:786`, `:804` |
| Vergleichs-Renderer / -Versand | `src/output/renderers/comparison.py:696`, `src/services/notification_service.py:1359` |
| Alarm-Renderer / -Versand | `src/output/renderers/alert/render.py:1483`, `src/services/notification_service.py:1809`, `:1870`, `:1978` |
| Amtliche Warnung | `src/services/notification_service.py:1174`, `:1294` |
| Webhook Go / Python | `internal/handler/telegram_webhook.go:39`, `internal/router/router.go:171`, `api/routers/webhook.py:53` |
| Inbound-Verarbeitung | `src/services/inbound_telegram_reader.py:159`, `:408`, `:582` |
| Befehlsantwort | `src/services/notification_service.py:2153` |
