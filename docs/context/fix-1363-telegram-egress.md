# Context: fix-1363-telegram-egress

Issue: #1363 — Telegram-Egress-Isolation (Scheibe C von #1337).
Vorbild und direkter Zwilling: #1336 / `docs/specs/modules/egress_guard_sms.md` (Scheibe B, SMS).

## Analysis

### Type
Bug (fast-track)

### Korrigierte Ausgangslage (PO-Hinweis 2026-07-24)
Ein dedizierter **Staging-Bot existiert bereits**: `@GregorZwanzigStaging_bot` (id 8859891703),
getrennt vom Prod-Bot `@GregorZwanzig_bot` (id 8330150917). Verifiziert per Fingerabdruck-Vergleich
der `GZ_TELEGRAM_BOT_TOKEN`-Werte in Prod- und Staging-`.env` (unterschiedlich) und per `getMe`.
Beide Bots tragen aktuell dasselbe Befehlsmenü — es wurde nie etwas überschrieben.

**Damit hinfällig:** die ursprüngliche Ticket-Annahme „kein Test-Zugang" und die Idee, einen zweiten
Bot anzulegen. Die bot-globale Gefahr (`set_my_commands` klobbert das Prod-Menü) ist auf Staging
bereits durch den getrennten Bot abgedeckt.

### Root Cause (was wirklich offen ist)
| Stelle | Problem |
|---|---|
| Konfiguration (kein Code) | Die Bot-Trennung ist **reine Konfiguration** und wird von nichts erzwungen. Kein Guard prüft, ob im Test-Modus wirklich der Staging-Bot aktiv ist. Geht die Staging-`.env` verloren/wird überschrieben, läuft Staging still über den Prod-Bot. Lehre aus #1336: Konfiguration ohne fail-closed Guard ist ungeschützt. |
| `telegram.py:250` `_send_fallback_without_parse_mode` | httpx.post ohne Guard, `chat_id` als Argument ungeprüft |
| `telegram.py:289` `delete_message` | dito |
| `telegram.py:332` `edit_message_text` | dito |
| `telegram.py:179` `send()` | prüft `settings.telegram_chat_id`, **nicht** das übergebene Argument — die Guard-Form passt nicht auf die argument-basierten Methoden |
| `src/app/egress_guard.py` / `internal/egress/inventory.go` | `api.telegram.org` = `BLOCKED` → Telegram auf Staging trotz intaktem Staging-Bot komplett untestbar |

**Wo Punkt 2 real beißt:** im **Produktiv-Prozess**, wenn `is_test_mode` durch einen Test-Nutzer
anspringt (`with_user_profile()` → `force_test` → `for_testing()`). Dann ist der **Prod-Bot** aktiv
und das Ziel der argument-basierten Methoden ungeprüft.

### Technical Approach (Bauart 1:1 wie #1336)
1. **Config:** neues Feld `telegram_test_bot_token` (env `GZ_TELEGRAM_TEST_BOT_TOKEN`), Wert = der
   **bestehende** Staging-Bot-Token. `for_testing()` lenkt `telegram_bot_token` darauf um (beide Zweige),
   analog `seven_sandbox_key`.
2. **Token-Guard (fail-closed):** `_guard_test_mode_bot_token()` — im `is_test_mode` MUSS der aktive
   Bot-Token der Test-Bot-Token sein, sonst `OutputConfigError`. Das ist die **strukturelle** Sicherung
   (deckt auch die bot-globalen Methoden ab, die keine chat_id haben).
3. **Chat-ID-Guard auf die argument-basierten Methoden ausweiten:** `_send_fallback_without_parse_mode`,
   `delete_message`, `edit_message_text` prüfen die **übergebene** `chat_id` gegen `telegram_test_chat_id`.
4. **Inventar-Flip** `api.telegram.org`: `BLOCKED` → `TEST_ACCESS` in `src/app/egress_guard.py` UND
   `internal/egress/inventory.go` (drift-gekoppelt via `tests/test_egress_inventory_drift.py`).
5. Bewusst **ohne** Guard: `answer_callback_query` (keine chat_id, quittiert nur einen Ladespinner) und
   `get_my_commands` (rein lesend) — in der Spec zu begründen.

### Operative Abhängigkeit
`GZ_TELEGRAM_TEST_BOT_TOKEN` muss in **Staging UND Prod** hinterlegt werden (Wert jeweils der
bestehende Staging-Bot-Token) — genau wie `GZ_SEVEN_SANDBOX_KEY` in beiden liegt. Grund: in Prod
springt `is_test_mode` für Test-Nutzer an; ohne gesetzten Test-Token würde der fail-closed Guard dort
den Telegram-Versand für Test-Nutzer blockieren.

### Scope Assessment
- Files: `src/app/config.py`, `src/output/channels/telegram.py`, `src/app/egress_guard.py`,
  `internal/egress/inventory.go` (MODIFY) + 1 Testdatei (CREATE)
- Est. LoC: ~ +80 / -2
- Risk: LOW–MEDIUM (mehr Methoden betroffen als bei #1336; Prod-Pfad für Test-Nutzer beachten)

### Open Questions
- [ ] Keine blockierende offene Frage. Token-Provisionierung ist ein Deploy-Schritt.
