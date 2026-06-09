# Context: Issue #686 — Echte funktionale Telegram-Live-Tests ermöglichen

## Request Summary
Der funktionale Live-Test des Telegram-Bots (echter Befehl rein → echte sinnvolle
Antwort raus, gegen den **echten** Bot) wurde bei #672 nie ausgeführt (SKIPPED). Wir
bauen die fehlende Test-Infrastruktur (Fixture + automatisierter Harness) und führen
den Test für alle 7 Menü-Befehle wirklich durch.

## Vorarbeit (2026-06-09, bereits erledigt & bewiesen)
- `GZ_TELEGRAM_CHAT_ID = 8346977700` in Staging-`.env`; PO hat dem Staging-Bot
  geschrieben → Chat existiert → send/edit/delete verifiziert (message_id zurück).
- Erster echter Live-Lauf: `/heute` durch `_process_update` (Staging-Tree, `uv run`)
  → PO hat die echte Bot-Antwort in Telegram gesehen. Zustellung end-to-end bewiesen.

## Related Files
| File | Relevance |
|------|-----------|
| `tests/tdd/test_e2e_telegram_pipeline.py` | **Das #672-Artefakt.** AC-1..4 gegen lokalen Socket (kein echter Bot); AC-5 (echter Bot) ist `skipif(not GZ_TELEGRAM_TEST_CHAT_ID)` → war immer SKIPPED, und nur Smoke (getMe/send/edit/delete), kein funktionaler Befehl→Antwort-Test. |
| `src/services/inbound_telegram_reader.py` | `_process_update` (Z.119): callback vs message; **aktiver-Trip-Check (Z.147) VOR Parsing** → ohne Trip jeder Befehl nur „Kein aktiver Trip". `_resolve_user_for_chat` (Z.265), `_find_active_trip` (Z.239), `_parse_command`. |
| `src/services/trip_command_processor.py` | `_QUERY_KEYS` (Z.81): glance/heute/morgen/heute_gewitter/timeline_heute/timeline_morgen; `_VALID_COMMANDS` (Z.67): hilfe/status/now/… `.process()` liefert `CommandResult(confirmation_subject, confirmation_body, reply_markup)`. |
| `src/outputs/telegram.py` | `send()` (Z.49) → **gibt None zurück** (keine message_id fürs Cleanup); `edit_message_text`, `BOT_COMMANDS` (die 7 Menü-Befehle), `set/get_my_commands`. `TELEGRAM_API_BASE` (monkeypatch-bar). |
| `src/app/loader.py` | `lookup_user_by_telegram_chat_id(chat_id, data_dir)` (Z.776) → matcht `profile["telegram_chat_id"]`; `load_all_trips(user_id)`. |
| `api/routers/webhook.py` | `/api/internal/telegram-webhook` → `_process_update` (Z.50); update_id-Dedup. |
| `data/users/<id>/user.json` | Profil: keys id/password_hash/created_at/mail_to/**telegram_chat_id**. Trips in `trips/*.json`. |

## Existing Patterns
- **Mock-frei (Projekt-Standard):** lokaler `http.server`/`socketserver` als echter
  Socket (so AC-1..4 in test_e2e_telegram_pipeline). Für echten Live-Bot: gated hinter
  ENV-Token, send→edit→delete (Bot kann eigene Nachrichten nicht zurücklesen).
- **Gated Live-Test:** `@pytest.mark.skipif(not os.environ.get(...))` — Problem: SKIPPED
  zählt als „grün". #686 muss SKIPPED im Live-Pfad als Versäumnis behandeln (AC-4).
- **E-Mail-Pendant:** `gregor-test@henemm.com` + IMAP-Readback ist das Vorbild für eine
  dedizierte Test-Identität. Telegram-Pendant fehlt → genau das bauen.

## Dependencies
- Upstream: laufender Staging-Bot (`@GregorZwanzigStaging_bot`, Token in
  `gregor_zwanzig_staging/.env`), Telegram Bot API, echte Wetter-Provider.
- Downstream: `/e2e-verify` (Verankerung), `prod_selftest` (Menü-Wächter #685, separat).

## Risks & Considerations
- **Fixture braucht aktiven, gültigen Trip** (Staging `default` hat keinen: 1 korrupt,
  1 lädt nicht). Sonst nur „Kein aktiver Trip" statt Wetter. Vorlage: e2e675user-Trip
  kopieren, Datum auf „heute überlappend" setzen, neuem Test-User zuordnen.
- **`send()` liefert keine message_id** → Cleanup (deleteMessage) braucht die ID. Optionen:
  send um message_id-Rückgabe erweitern (klein, nützlich für Observability) ODER Harness
  sendet direkt via API. Entscheidung in Analyse.
- **Mandantentrennung:** chat 8346977700 einem dedizierten Test-User zuordnen (nicht
  `default` verschmutzen). Auf Prod ist die ID bereits `henning` zugeordnet — Staging-only.
- **Chat-ID-Abgriff:** Webhook aktiv → getUpdates blockt; deleteWebhook → PO schreibt →
  getUpdates → setWebhook 1:1 zurück (bereits durchgeführt).
- **Kein Chat-Müll:** Live-Antworten nach Inhaltsprüfung sofort wieder löschen.

## Existing Specs
- `docs/specs/modules/telegram_webhook_inbound.md` (#637) — Webhook-Pipeline.
- Bot-Menü-Wächter: #671/#685 (prod_selftest), separat.
