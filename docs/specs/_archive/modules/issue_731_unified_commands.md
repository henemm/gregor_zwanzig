---
entity_id: issue_731_unified_commands
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [commands, email, telegram, inbound, ux]
---

# Issue #731 — Antwort-Kommandos vereinheitlichen (abruf-zentriert, kanalübergreifend)

## Approval

- [x] Approved

## Purpose

Die in der Briefing-E-Mail gelisteten „Antwort-Kommandos" stammen aus Abonnenten-Denke (PAUSE/SKIP/STOP/CONFIG) und treffen nicht das Mentalmodell einer Person auf einer Wanderung. Dieses Modul ersetzt sie durch einen **abruf-zentrierten Grundbefehlssatz**, der über E-Mail und Telegram **identische Keywords** nutzt (SMS-Vokabular gleich dokumentiert; SMS-Inbound → #735). Schwache Verwaltungsbefehle (PAUSE/SKIP/CONFIG) entfallen.

## Source

- **File:** `src/services/trip_command_processor.py` — **Identifier:** `_BARE_KEYWORD_MAP`, `_VALID_COMMANDS`, `process`, `_show_help`, `_show_status`, neuer `_resume_trip`; Entfernen von `_apply_pause`/`_apply_skip`/`_show_config`-Routing
- **File:** `src/output/renderers/email/html.py` — **Identifier:** `render_html` (Block „Antwort-Kommandos" + Footer-Zeile)
- **File:** `src/output/renderers/email/plain.py` — **Identifier:** Plaintext-Kommando-Hinweis
- **File:** `src/outputs/telegram.py` — **Identifier:** `BOT_COMMANDS`
- **File:** `src/services/inbound_telegram_reader.py` — **Identifier:** `_SHORTCUT_MAP`

Schicht: **Python-Backend** (FastAPI Core + Renderer). Keine Frontend-/Go-Änderung.

## Estimated Scope

- **LoC:** ~120
- **Files:** 5 (Source) + Tests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripCommandProcessor` | service | Kanal-agnostischer Parser/Dispatcher |
| `RadarNowcastService` | service | `JETZT`-Nowcast (bestehend) |
| `report_config.enabled` | model field | STOP/WEITER schalten Versand aus/an |

## Implementation Details

**Zielbefehlssatz (E-Mail + Telegram identische Keywords):**

| Keyword | Interner Key | Wirkung |
|---------|-------------|---------|
| `HEUTE` | `heute` (query) | Wetter heutige Etappe |
| `MORGEN` | `morgen` (query) | Wetter morgige Etappe |
| `JETZT` / `NOW` | `now` | Nowcast Regen/Gewitter nächste ~2h |
| `GEWITTER` | `heute_gewitter` (query) | Gewittergefahr ganze heutige Etappe |
| `RUHETAG [N]` | `ruhetag` | Etappen um N Tage verschieben |
| `STATUS` | `status` | nur heute + kommende Etappen |
| `STOP` | `abbruch` | Versand abmelden (`enabled=False`) |
| `WEITER` | `weiter` (neu) | Versand reaktivieren (`enabled=True`) |
| `HILFE` / `HELP` | `hilfe` | Befehle anzeigen |

**Parser-Änderungen (`_BARE_KEYWORD_MAP`):**
```python
_BARE_KEYWORD_MAP = {
    "heute":   "heute",          # → _QUERY_KEYS
    "morgen":  "morgen",         # → _QUERY_KEYS
    "jetzt":   "now",
    "now":     "now",
    "gewitter":"heute_gewitter", # → _QUERY_KEYS
    "ruhetag": "ruhetag",
    "status":  "status",
    "stop":    "abbruch",
    "weiter":  "weiter",
    "hilfe":   "hilfe",
    "help":    "hilfe",
}
# entfernt: pause, skip, config
```
`_VALID_COMMANDS` ergänzt um `"weiter"`, bereinigt um `pause`/`skip`/`config`. Dispatch-Zweige für `pause`/`skip`/`config` entfernt; neuer Zweig `weiter` → `_resume_trip` (RMW: `report_config.enabled=True`, `msg.user_id` durchreichen). Die Methoden `_apply_pause`/`_apply_skip`/`_show_config` werden entfernt.

**`_show_status`:** filtert auf Etappen mit `stage.date >= date.today()` (vergangene raus).

**E-Mail-Renderer:** Block „Antwort-Kommandos" (html.py) + Footer-Zeile + Plaintext-Hinweis (plain.py) auf den neuen Satz; kein PAUSE/SKIP/CONFIG.

**Telegram:** `BOT_COMMANDS` bleibt mit interaktiven Extras (glance/timeline), aber `_SHORTCUT_MAP` erhält `jetzt`/`/jetzt`→now und `gewitter`/`/gewitter`→heute_gewitter, damit dieselben Keywords wie E-Mail funktionieren.

**Backward Compatibility:** Bestehende Trips mit gesetztem `paused_until`/`skip_next` (aus #670) bleiben unangetastet; der Scheduler respektiert sie weiterhin (kein Schema-Removal). Nur die **Eingabe** neuer PAUSE/SKIP-Kommandos entfällt.

## Acceptance Criteria

**AC-1:** Given eine gerenderte Briefing-E-Mail (HTML), When der Body via `render_html` erzeugt wird, Then enthält der Block „Antwort-Kommandos" exakt HEUTE/MORGEN/JETZT/GEWITTER/RUHETAG/STATUS/STOP/WEITER/HILFE (Desktop **und** Mobile-Markup) und **kein** PAUSE, SKIP oder CONFIG; die Footer-Befehlszeile ist entsprechend angeglichen.

**AC-2:** Given eine gerenderte Briefing-E-Mail (Plaintext über `plain.py`), When der Plaintext-Body erzeugt wird, Then spiegelt der Kommando-Hinweis denselben neuen Befehlssatz und enthält **kein** PAUSE/SKIP/CONFIG.

**AC-3:** Given eine Inbound-E-Mail an einen existierenden Trip mit dem bare keyword `heute` (bzw. `morgen`) in der ersten Zeile, When `TripCommandProcessor.process` sie verarbeitet, Then liefert das `CommandResult` das Wetter der heutigen (bzw. morgigen) Etappe und **nicht** „Unbekannter Befehl".

**AC-4:** Given eine Inbound-Nachricht mit `jetzt` (oder `now`) bzw. `gewitter`, When verarbeitet, Then liefert `jetzt`/`now` einen Radar-Nowcast (über `RadarNowcastService`) und `gewitter` die Gewittergefahr der heutigen Etappe.

**AC-5:** Given ein Trip mit `report_config.enabled=False` (z.B. nach STOP), When eine Inbound-Nachricht `WEITER` verarbeitet wird, Then wird `report_config.enabled` per Read-Modify-Write auf `True` gesetzt (mit `msg.user_id`, kein default-Fallback) und die Bestätigung nennt die Reaktivierung.

**AC-6:** Given ein Trip mit mindestens einer vergangenen und einer heutigen/künftigen Etappe, When `STATUS` verarbeitet wird, Then listet die Antwort nur Etappen mit Datum `>= heute` und **keine** vergangenen Etappen.

**AC-7:** Given eine Inbound-Nachricht `PAUSE 12h`, `SKIP` oder `CONFIG`, When verarbeitet, Then erfolgt **keine** State-Mutation (kein `paused_until`, kein `skip_next` wird gesetzt) und die Antwort behandelt das Keyword als nicht (mehr) unterstützten/unbekannten Befehl.

**AC-8:** Given eine `HILFE`/`HELP`-Anfrage auf beliebigem Kanal, When `_show_help` antwortet, Then listet die Hilfe den neuen Befehlssatz (HEUTE/MORGEN/JETZT/GEWITTER/RUHETAG/STATUS/STOP/WEITER/HILFE) und **kein** PAUSE/SKIP/CONFIG.

**AC-9:** Given der Telegram-Inbound-Reader, When eine Nachricht `jetzt`, `/jetzt`, `gewitter` oder `/gewitter` eingeht, Then wird sie auf denselben internen Query/Command gemappt wie das E-Mail-Pendant (`now` bzw. `heute_gewitter`), und die interaktiven Telegram-Extras (glance, timeline, Inline-Buttons) bleiben funktional.

**AC-10:** Given zwei verschiedene Nutzer mit je eigenem Trip, When `WEITER`/`STATUS` für Nutzer A verarbeitet wird, Then wirkt die Änderung ausschließlich auf den Trip von Nutzer A (`msg.user_id` durchgereicht, kein Cross-User-Schreiben nach `users/default/`).

## Out of Scope

- Echtes Radar/Blitz für Frankreich & global → **#734**
- SMS-Inbound (Empfang & Antwort per SMS) → **#735**
- Schema-Removal von `paused_until`/`skip_next` (bleiben für Bestandsdaten erhalten)

## Changelog

- 2026-06-11: Initial spec — Issue #731. Abruf-zentrierter, kanalübergreifender Befehlssatz; Entfernen von PAUSE/SKIP/CONFIG; neuer WEITER-Befehl; STATUS auf kommende Etappen abgespeckt; Telegram-Keyword-Angleich. 10 ACs (AC-N-Format). Folge-Issues #734 (Radar/Blitz), #735 (SMS-Inbound).
