# Fix #1013 — Telegram-Live-Test-Artefakte laufen über Produktion

## Analysis

### Type
Bug (Issue #1013)

### Symptom (2026-07-04/05, Produktion)
- PO erhielt täglich Morning-/Evening-Briefings des Test-Trips "TG Live E2E Test" über den **Prod-Bot**.
- Inbound-Kommandos des PO („heute"/„morgen") wurden dem Test-User `tg-live-e2e` zugeordnet statt `henning` (Beleg: On-Demand-Briefing 2026-07-05 05:55 UTC im `tg-live-e2e`-Briefing-Log).
- Test-User versendete E-Mail über Resend-Prod-Kontingent (mail_to leer → globaler Fallback).

### Root Causes (bewiesen)
1. **Fixture schreibt CWD-relativ in Prod-Daten:** `tests/tdd/_telegram_live_fixture.py` → `ensure_test_user_with_active_trip(chat_id, data_dir="data")`. Aufrufer: `tests/tdd/test_issue_686_telegram_functional_live.py:167` (chat_id aus `GZ_TELEGRAM_TEST_CHAT_ID`), `tests/tdd/test_issue_697_telegram_on_demand_fetch.py`. Lauf im Hauptrepo (= Prod-Maschine) ⇒ `data/users/tg-live-e2e/` in Produktion. Kein Guard.
2. **Chat-ID-Lookup nicht deterministisch:** `src/app/loader.py:821` `lookup_user_by_telegram_chat_id()` — erster Treffer in `iterdir()`-Reihenfolge; bei Kollision (henning und tg-live-e2e hatten beide 8346977700) gewann der Test-User.
3. **Test-Isolation deckt Telegram nicht ab:** `src/app/config.py:141` `for_testing()` leitet nur SMTP auf Stalwart um („SMTP/Telegram infrastructure stays global"); `src/app/config.py:168` `_is_test_user()` matcht nur „test"/„tdd"-Substring; `src/app/loader.py:779` `list_all_user_ids()` filtert nur Prefixe `test`/`_` — `tg-live-e2e` fällt durch alle Raster.

### Sofortmaßnahme (erledigt 2026-07-05)
`data/users/tg-live-e2e/` aus Prod entfernt (Backup gesichert). Staging besitzt den User bereits vollständig (seit 2026-06-10). Lookup liefert in Prod wieder `henning`. **Ohne strukturellen Fix legt der nächste Live-Test-Lauf im Hauptrepo den User erneut an.**

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| tests/tdd/_telegram_live_fixture.py | MODIFY | Hard-Guard: außerhalb Staging-Umgebung abbrechen |
| src/app/loader.py | MODIFY | Lookup deterministisch, echte User vor Test-Usern |
| src/app/config.py | MODIFY | Test-User-Erkennung vereinheitlichen (tg-live-e2e abdecken) |
| tests/tdd/test_issue_1013_*.py | CREATE | TDD-Tests (Guard, Lookup-Kollision, Erkennung) |

### Scope Assessment
- Files: ~4 (Fixture, loader.py, config.py, neue TDD-Tests)
- Estimated LoC: ~90–125 (deutlich unter Limit 250)
- Risk Level: LOW–MEDIUM (Lookup-Änderung betrifft nur Inbound-Kommando-Routing, keinen Scheduler-/Versand-Pfad; `design_tdd` hat weder telegram_chat_id noch mail_to → keine Verhaltensänderung durch erweiterten Filter)

### Technical Approach
(Plan-Agent-Bewertung, bestätigt)

**(a) Fixture-Guard (Root-Cause-Fix, höchste Priorität):** `ensure_test_user_with_active_trip` wirft `RuntimeError`, wenn `data_dir == "data"` UND `Settings().env.lower() != "staging"`. Nutzt das bereits etablierte, load-bearing Signal `GZ_ENV` (config.py:107; Staging-`.env:42` hat `GZ_ENV=staging`, Prod nicht). Bricht keine bestehenden Tests: die beiden Leck-Aufrufer (test_686:168, test_697:320) laufen sollgemäß nur im Staging-Tree; alle anderen Fixture-Nutzungen übergeben explizit `tmp_path`.

**(c) Zentrale Test-User-Erkennung (Grundlage für b):** EINE Prädikatsfunktion, die die Substring-Konvention („test"/„tdd") UND den Fixture-User abdeckt (Fixture schreibt zusätzlich `is_test_user: true` ins `user.json` beim Anlegen). `config.py._is_test_user` wird Thin-Wrapper darauf (Konsolidierung — bisher zwei getrennte, inkonsistente Konventionen: config.py:168 Substring vs. loader.py:794 nur Prefix).

**(b) Lookup deterministisch:** `list_all_user_ids`/`lookup_user_by_telegram_chat_id` (+ `lookup_user_by_email`, gleiche Mechanik) sortiert iterieren, echte User vor Test-Usern (Nachrang via Prädikat aus c). Blast-Radius geprüft: `list_all_user_ids` wird nur von den beiden Lookup-Funktionen genutzt, kein Scheduler-Pfad.

**Reihenfolge:** a (Root-Cause) → c → b; TDD-RED-Tests für (a) Guard und (b) Kollisions-Vorrang zuerst.

### Dependencies
- PO-Regel: Telegram-Tests IMMER via Staging-Bot (Staging-Creds `gregor_zwanzig_staging/.env`).
- `.claude/hooks/e2e_telegram_live.py` (E2E-Hook) — Laufumgebung der Live-Tests.
- Verwandt, nicht in Scope: #1012 (leeres Briefing bei 503), #976 (HTML-Truncation).

### Open Questions
- [ ] Härtung der Fixture: env-Check (`GZ_ENV=staging`) vs. Pfad-Check — was bricht die bestehenden Staging-Läufe nicht?
- [ ] Wo zentrale Test-User-Erkennung verankern, wer muss sie konsumieren (Scheduler-Endpoints, list_all_user_ids, can_send_telegram)?
