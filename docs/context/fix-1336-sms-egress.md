# Context: fix-1336-sms-egress

Issue: #1336 — SMS-Versand (seven.io) hat KEINE Staging-Trennung.
Muster: Teil von #1337 (zentraler Egress-Wächter). Vorbild-Guard: Telegram #1288.

## Analysis

### Type
Bug (fast-track)

### Symptom / Wirkung
SMS ist der einzige ausgehende Kanal ohne Test-Isolation. Auf Staging könnten echte,
kostenpflichtige SMS an echte Nummern rausgehen. Akut entschärft: `GZ_SEVEN_API_KEY`
auf Staging auskommentiert (PO, 2026-07-21) → Kanal dort tot bis Fix. Rückbau hängt am Guard.

### Root Cause (belegt)
| Stelle | Problem |
|---|---|
| `src/output/channels/sms.py:32-46` | `send()` feuert immer direkt an seven.io; kein `is_test_mode`-Check (vgl. `telegram.py:179` `_guard_test_mode_chat_id()`). |
| `src/app/config.py:212` `for_testing()` | Leitet nur SMTP + Telegram um, fasst SMS/`seven_api_key`/`sms_to` gar nicht an. |
| `src/app/config.py:279` `with_user_profile()` | Übernimmt `sms_to` aus Nutzerprofil auch im `force_test`-Fall ungebremst (keine Ausnahme wie beim `telegram_chat_id`-Override). |

`is_test_mode` ist das verlässliche Signal (gesetzt von `for_testing()`, ausgelöst durch Staging
oder Test-User in `with_user_profile()`) — identisch zu Telegram.

### seven.io-Fakten (verifiziert 2026-07-24, PO-bestätigt; siehe Memory reference_sevenio_journal_and_debug_verification)
- **Isolation = SEPARATER Sandbox-API-Key.** Webapp → Developer → API Access → Create New → REST API → Environment=Sandbox. Ein Sandbox-Key **sendet NIE eine echte Nachricht und nutzt NIE ein kostenpflichtiges Produkt** → null Kosten, null Zustellung, per Design. Kein Probe-Risiko.
- **NICHT** der `debug`-Request-Param — der ist **deprecated** (PO-Korrektur).
- **Sendeprotokoll (Verifikation):** `GET /api/journal/outbound`; zusätzlich echot die POST-Antwort `messages[]` mit `recipient`+`text`+`price`+`success`.

### Technical Approach (final — exakt das Mail/Telegram-Muster)
1. **Config-Feld** `test_seven_api_key` (`GZ_TEST_SEVEN_API_KEY`) = Sandbox-Key. `for_testing()` swappt `seven_api_key` → `test_seven_api_key` (analog `test_smtp_*` / `telegram_test_chat_id`).
2. **Bedingungsloser Guard in `SMSOutput`** (Vorbild `_guard_test_mode_chat_id`, #1288): im `is_test_mode` MUSS der aktive `seven_api_key` der Sandbox-Key sein; sonst `OutputConfigError` (fail-closed — fängt die Fallback-Lücke ab, wenn `test_seven_api_key` fehlt).
3. `with_user_profile()` (config.py:279) bleibt, Guard ist der Backstop (im Sandbox-Modus ist die Empfängernummer ohnehin folgenlos).

### Scope Assessment
- Files: `src/app/config.py` (MODIFY: Feld + `for_testing()`), `src/output/channels/sms.py` (MODIFY: Guard), Tests (CREATE).
- Est. LoC: ~ +55 / -2
- Risk: LOW (etabliertes Muster, kein Kostenrisiko durch Sandbox-Design)

### Operative Abhängigkeit (Deploy/Rückbau)
- PO/Betrieb legt in der seven.io-Webapp einen **Sandbox-Key** an und setzt `GZ_TEST_SEVEN_API_KEY` auf Staging.
- Danach kann `GZ_SEVEN_API_KEY` auf Staging wieder aktiviert werden (Pause aus #1336 aufheben) — auf Staging erzwingt `env=staging` ohnehin `for_testing()` → Sandbox-Key; Prod bleibt Prod-Key (is_test_mode=False).

### Open Questions
- [ ] Keine blockierende offene Frage mehr. Sandbox-Key-Provisionierung ist ein Deploy-Schritt, kein Design-Risiko.
