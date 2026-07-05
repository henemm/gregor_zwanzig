# Fix #1014 — Live-Telegram-Tests nur noch opt-in (Versand-Hälfte von „Tests nie über Produktion")

## Analysis

### Type
Bug (Issue #1014) — direkter Nachfolger von #1013 (dessen Daten-/Routing-Hälfte ist live, 397fe7be).

### Symptom (2026-07-05, ~09:41–09:54, reproduziert)
Ein breiter Regressionslauf (`uv run pytest tests/tdd …`) im Worktree hat Live-Telegram-Tests real ausgeführt — der PO erhielt ungefragt Test-Nachrichten (nach Token-Lage via Staging-Bot; mit Prod-.env-Kopie im Worktree wäre ohne env-Override der Prod-Bot benutzt worden).

### Root Causes (bewiesen)
1. **Import-Nebeneffekt öffnet alle Live-Gates:** `tests/tdd/test_issue_1001_telegram_bubbles.py:40-58` — `_load_staging_telegram_env()` läuft beim Modul-IMPORT (pytest-Collection, alphabetisch früh) und schreibt `GZ_TELEGRAM_BOT_TOKEN`/`GZ_TELEGRAM_CHAT_ID`/`GZ_TELEGRAM_TEST_CHAT_ID` aus `gregor_zwanzig_staging/.env` nach `os.environ`. Alle später importierten Live-Tests (`650`, `671`, `686`, `1001`, `e2e_pipeline`, `952`…) sehen „Creds vorhanden" → `skipif`-Gates offen → echte Sends.
2. **Kein Opt-in-Signal:** Live-Gates prüfen nur Creds-Präsenz (`os.environ.get(...)`), nicht die Absicht („will ich live senden?") und nicht die Umgebung (`GZ_ENV=staging`).
3. **Worktree erhält Prod-.env-Kopie:** EnterWorktree provisioniert `.env` 1:1 aus dem Hauptrepo (beobachtet 06:04 Uhr; kein Projekt-/User-Hook verantwortlich → Harness-Verhalten). Tests, die `Settings()` pur laden (z.B. `test_issue_671_bot_menu_autoset.py:195` `TelegramOutput()`), würden ohne env-Override den Prod-Bot-Token nutzen.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| tests/tdd/_telegram_live_fixture.py | MODIFY | zentrales Live-Gate `live_telegram_enabled()` + `load_staging_telegram_env()` (nur bei Opt-in) hierher konsolidieren |
| tests/tdd/test_issue_1001_telegram_bubbles.py | MODIFY | Import-Autoload entfernen → Gate nutzen |
| tests/tdd/test_issue_686_telegram_functional_live.py | MODIFY | Gate nutzen |
| tests/tdd/test_issue_650_telegram_foundation.py | MODIFY | Gate nutzen |
| tests/tdd/test_issue_671_bot_menu_autoset.py | MODIFY | Gate nutzen; Live-Send mit explizitem Staging-Token statt `TelegramOutput()`/`Settings()` |
| tests/tdd/test_e2e_telegram_pipeline.py | MODIFY | Gate nutzen |
| tests/tdd/test_952_onset_alert_e2e.py | MODIFY | Gate nutzen (Telegram-Live-Teil) |
| tests/tdd/test_issue_1014_live_optin.py | CREATE | TDD-Tests |
| .claude/skills bzw. e2e-verify-Doku | MODIFY (klein) | Aufruf-Beispiel um `GZ_TELEGRAM_LIVE=1` ergänzen (Schritt 3c) |

> 7 bestehende Testdateien + 1 neue + Doku — über dem 5-Dateien-Richtwert, aber gleichförmige Mini-Edits (Gate-Import statt eigener skipif-Bedingung). Kein Split nötig.

### Scope Assessment
- Files: ~9 (fast nur Tests/Doku; einzige „echte" Logik im Fixture-Modul)
- Estimated LoC: ~80–120
- Risk Level: LOW (nur Test-Infrastruktur; Produktcode unberührt)

### Technical Approach (Tech-Lead-Empfehlung)
1. **Zentrales Gate** in `tests/tdd/_telegram_live_fixture.py`:
   - `live_telegram_enabled() -> bool`: True NUR wenn `GZ_TELEGRAM_LIVE=1` UND (nach Sourcing) Token+Test-Chat-ID vorhanden.
   - `load_staging_telegram_env()`: wie bisheriges `_load_staging_telegram_env`, aber wird NUR von `live_telegram_enabled()` bei gesetztem Opt-in aufgerufen — nie mehr implizit beim Import.
2. **Alle Live-Testdateien** ersetzen ihre `skipif(not os.environ.get(...))`-Bedingungen durch `skipif(not live_telegram_enabled(), reason="GZ_TELEGRAM_LIVE=1 nicht gesetzt — Live-Sends nur opt-in (#1014)")`. Achtung: skipif wird zur Import-Zeit ausgewertet — Gate-Funktion ist idempotent/billig.
3. **Kein `Settings()`-Token in Live-Sends:** Live-Tests bauen Settings explizit mit `os.environ["GZ_TELEGRAM_BOT_TOKEN"]` (aus dem Staging-Sourcing) — betrifft konkret test_671:195.
4. **e2e-verify Schritt 3c** dokumentiert `GZ_TELEGRAM_LIVE=1` zusätzlich zu den Creds (der bewusste Live-Lauf im Staging-Tree bleibt unverändert möglich).
5. **Worktree-Prod-.env:** nicht repo-seitig lösbar (Harness-Verhalten); durch (1)-(3) für Tests entschärft — Live-Sends nutzen nie mehr die CWD-.env. Rest-Risiko im Issue dokumentiert lassen.

### Dependencies
- #1013 (live): Fixture-Guard GZ_ENV=staging für data_dir="data" — bleibt unverändert bestehen.
- PO-Regel: Telegram-Tests IMMER bewusst via Staging-Bot.
- e2e-verify-Skill (`staging_gate.py` erzwingt Live-Test bei Telegram-Scope) — Aufruf muss künftig GZ_TELEGRAM_LIVE=1 setzen.

### Open Questions
- keine (Mechanismus-Wahl env-Var vs. pytest-Marker: env-Var gewählt — ein Gate, keine Marker-Disziplin über 7 Dateien, kompatibel mit skipif-Import-Zeit-Auswertung)
