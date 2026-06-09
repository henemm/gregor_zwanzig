---
entity_id: issue_671_bot_menu_autoset
type: module
created: 2026-06-09
updated: 2026-06-09
status: draft
version: "1.0"
tags: [telegram, bot-menu, startup, e2e, bugfix]
---

# Bot-Menü automatisch beim Service-Start + echter Live-E2E (Issue #671)

## Approval

- [x] Approved (2026-06-09, PO — „go, mit echtem Live-E2E gegen den Bot")

## Purpose

**#671 „Telegram Menü funktioniert nicht" — echte, dauerhafte Behebung.**

Der bisherige Fix (#672) setzte das Bot-Menü nur über den **manuellen** Ops-Schritt
`telegram_set_commands.sh set`. Das Menü ist globaler Telegram-Server-State pro Bot
und wurde danach wieder auf den kaputten Stand `briefing/wetter/hilfe` überschrieben —
höchstwahrscheinlich durch eine **parallele Arbeitskopie mit altem Code** (mehrere
Worktrees/Workspaces laufen gleichzeitig). Die Menü-Beschreibungen im Live-Bot
(„🌤️ Aktuelles Briefing" / „📊 Wetter-Details") stammten exakt aus diesem alten
`BOT_COMMANDS`. Zusätzlich gab es **keinen** automatisierten Test gegen den **echten**
Telegram-Bot — der einzige Live-Test in #672 (AC-5) wurde übersprungen, sodass die
Regression ungefangen durchrutschte.

Diese Spec macht zwei Dinge:
1. **Auto-Set beim Start:** Der FastAPI-Service setzt `setMyCommands` beim Start
   idempotent aus dem deployten `BOT_COMMANDS` — der aktuelle origin/main-Code gewinnt
   immer, jeder Deploy/Restart heilt das Menü. Der manuelle Ops-Schritt entfällt damit
   als Standard (und damit die Hauptquelle der Überschreibung).
2. **Echter Live-E2E gegen den Bot:** Ein Test fährt `setMyCommands` gegen den echten
   (Staging-)Bot und verifiziert via `getMyCommands`, dass die 7 Menü-Befehle live
   stehen. `getMyCommands` braucht **keinen gestarteten Chat** (Unterschied zu #672s
   send/edit/delete) → der Test läuft wirklich durch. Zusätzlich prüft der
   Post-Deploy-Selftest das Live-Menü gegen den Prod-Bot.

## Source

- **File (Fix):** `api/main.py` → Lifespan-Startup-Hook ruft idempotent
  `TelegramOutput(settings).set_my_commands()` auf; fail-soft wenn kein Bot-Token.
- **File (Test, neu):** `tests/tdd/test_issue_671_bot_menu_autoset.py`
- **File (Selftest):** `.claude/hooks/prod_selftest.py` → optionaler Live-Menü-Check
  gegen den Prod-Bot (`getMyCommands` == erwartete Befehle), fail-soft/gated.
- **Unter Test, nicht verändert:** `src/outputs/telegram.py` (`BOT_COMMANDS`,
  `set_my_commands`), `src/app/config.py` (`telegram_bot_token`).

## Estimated Scope

- **LoC:** ~30 Fix (api/main.py) + ~90 Test + ~30 Selftest = ~150
- **Files:** 1 berührt (api/main.py) + 1 neu (Test) + 1 berührt (prod_selftest.py)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `api/main.py` | Service-Entry | FastAPI-App; Startup-Hook hängt hier |
| `outputs/telegram.py` | Output | `set_my_commands()` + `BOT_COMMANDS` (Menü-Quelle) |
| `app/config.py` | Config | `telegram_bot_token` (nur Token nötig, NICHT chat_id) |
| Staging-Bot `GregorZwanzigStaging_bot` | extern | Live-E2E-Ziel (gated) |
| `.claude/hooks/prod_selftest.py` | Hook | Post-Deploy Live-Menü-Attestation |

## Implementation Details

**Auto-Set (api/main.py):**
- FastAPI-Lifespan (`@asynccontextmanager`) → beim Startup einmalig
  `_init_telegram_bot_menu()`.
- Guard: nur ausführen wenn `settings.telegram_bot_token` **nicht leer** ist
  (NICHT `can_send_telegram()` — das verlangt zusätzlich eine chat_id, die fürs Menü
  irrelevant ist; ein Bot kann sein Menü ohne chat_id setzen).
- `try/except Exception` → loggt `warning`, wirft NICHT (Readiness-Pattern wie
  `_ping_heartbeat_compare`). Ein Telegram-Ausfall darf den Service-Start nie blocken.
- Idempotent: `setMyCommands` ist eine Replace-Operation; mehrfacher Aufruf ist safe.

**Mock-frei nach Projekt-Standard:**
- Auto-Set-Verhalten: echter lokaler `http.server`-Socket fängt den ausgehenden
  `setMyCommands`-Call (`monkeypatch outputs.telegram.TELEGRAM_API_BASE`), echte
  FastAPI-`TestClient`-Instanziierung triggert den Lifespan. KEIN Mock des HTTP-Calls.
- Live-E2E (gated): echte Telegram-Bot-API gegen den Staging-Bot
  (`GZ_TELEGRAM_BOT_TOKEN`), `setMyCommands` → `getMyCommands`, Vergleich gegen
  `BOT_COMMANDS`. Ohne Token → `skip`. **Läuft im Gegensatz zu #672 wirklich durch,
  weil `getMyCommands` keinen Chat braucht.**

## Expected Behavior

- **Input:** Service-Start (Lifespan) bzw. echter Telegram-Bot-API-Call.
- **Output:** ausgehender `setMyCommands` mit `BOT_COMMANDS`; Live `getMyCommands`
  liefert die 7 Befehle.
- **Side effects:** Bot-Menü wird gesetzt (idempotent). Kein Crash bei fehlendem Token.

## Acceptance Criteria

- **AC-1:** Given die FastAPI-App mit gesetztem `telegram_bot_token` und ein lokaler
  Socket, der Telegram-Calls fängt /
  When die App gestartet wird (Lifespan-Startup) /
  Then wird **genau ein** `setMyCommands`-Call an den Bot abgesetzt, dessen
  `commands`-Payload exakt `BOT_COMMANDS` (die 7 Befehle glance…hilfe) trägt — mock-frei
  am echten Socket erfasst.

- **AC-2:** Given die FastAPI-App **ohne** `telegram_bot_token` (leer) /
  When die App gestartet wird /
  Then startet der Service fehlerfrei (kein Crash, keine Exception) und es geht
  **kein** `setMyCommands`-Call raus (fail-soft; nur der Token zählt, eine fehlende
  chat_id verhindert das Menü-Setzen NICHT).

- **AC-3:** Given gesetzter `GZ_TELEGRAM_BOT_TOKEN` (Staging-Bot) /
  When der Live-E2E `setMyCommands` aus `BOT_COMMANDS` gegen den echten Bot fährt und
  danach `getMyCommands` abruft /
  Then liefert `getMyCommands` `ok=True` und die zurückgegebene Befehlsliste ist
  **identisch** zu `BOT_COMMANDS` (gleiche command-Namen in gleicher Reihenfolge).
  Ohne Token wird der Test sauber übersprungen. (Echter End-to-End-Beweis gegen den
  Telegram-Dienst — die in #672 fehlende Verifikation.)

- **AC-4:** Given der Post-Deploy-Selftest läuft gegen Production mit lesbarem
  Prod-Bot-Token /
  When er nach dem Deploy `getMyCommands` gegen den Prod-Bot abruft /
  Then meldet er PASS nur wenn die Live-Befehlsliste exakt `BOT_COMMANDS` entspricht,
  sonst FAIL (fängt die Menü-Regression im Deploy-Gate). Ohne lesbaren Token →
  sauberes SKIP (keine Fehlklassifikation).

## Known Limitations

- Eine parallele Arbeitskopie mit altem Code kann das Live-Menü zwischen zwei Deploys
  weiterhin **temporär** überschreiben, wenn dort manuell `telegram_set_commands.sh set`
  läuft. Der nächste Deploy/Service-Restart heilt es automatisch, und AC-4 fängt einen
  solchen Stand im Selftest. Das endgültige Abstellen der Alt-Quellen (Aufräumen
  veralteter Worktrees/Workspaces) ist Infra-Hygiene, nicht Teil dieses Code-Fixes.

## Changelog

- 2026-06-09: Initial spec created (Issue #671 echte Behebung — Auto-Set + Live-E2E).
