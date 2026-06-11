# Context: Issue #731 — "Antwort-Kommandos" hinterfragen & kanalübergreifend vereinheitlichen

## Request Summary
Der PO hinterfragt die in der Briefing-E-Mail gelisteten „Antwort-Kommandos" (PAUSE/SKIP/STOP/STATUS/CONFIG/HELP, aus #670): Was bewirkt eine 12h-Pause überhaupt, und welche Befehle braucht eine Person **auf einer Wanderung** wirklich? Ziel: ein **gemeinsamer, sinnvoller Grundbefehlssatz über E-Mail, SMS und Telegram** (Telegram darf zusätzlich interaktiv sein). Es ist explizit ein Recherche-/Diskussions-Issue (`type:bug`, `priority:high`).

## Ist-Zustand pro Kanal

### E-Mail (Block „Antwort-Kommandos", #670)
Quelle: `src/output/renderers/email/html.py:826` + `_show_help` in `trip_command_processor.py:847`
- **PAUSE 2d / 12h** — Briefings pausieren (Tage/Stunden)
- **SKIP** — nächsten Versand einmalig überspringen
- **STOP** — Briefings dauerhaft deaktivieren
- **STATUS** — aktuelle Etappenübersicht
- **CONFIG** — Link zu Trip-Einstellungen
- **HELP** — alle Befehle
- Erweitert (`### key: value`): `ruhetag`, `startdatum`, `report morning|evening`, `abbruch`, `hilfe`
- → **Charakter: Abo-/Schedule-Verwaltung** ("Newsletter-Abonnent"-Denke). Kein leichtgewichtiger Wetter-Abruf.

### Telegram (BOT_COMMANDS, #704/#697/#651)
Quelle: `src/outputs/telegram.py:14`
- **glance** 🌤️ Überblick heute&morgen · **heute** · **morgen** · **now** 🌂 Nowcast (Regen/Gewitter 2h) · **heute_gewitter** ⛈️ · **timeline_heute/morgen** 🕐 · **hilfe**
- Plus **interaktive Inline-Buttons** (Drilldown Stunden/Gewitter/Wind/Regen/Timeline), callback_query-Navigation.
- → **Charakter: On-demand Wetter-Abruf** — genau das, was am Berg nützt. Hat KEINE PAUSE/SKIP/STOP/CONFIG.

### SMS (seven.io)
Quelle: `src/outputs/sms.py`
- **Nur Outbound.** Kein Inbound-Reader, keine Befehls-/Footer-Hinweise. seven.io kann Inbound (eigene Nummer + Webhook), ist aber nicht gebaut.

## Kernbefund (die eigentliche Frage hinter #731)
Die drei Kanäle sind **inhaltlich auseinandergelaufen**:
- E-Mail bietet **Verwaltungsbefehle** (PAUSE/SKIP/STOP/CONFIG) — geschrieben aus Abonnenten-Sicht, nicht aus Wanderer-Sicht.
- Telegram bietet **Abrufbefehle** (now/heute/morgen/gewitter) — das, was unterwegs zählt.
- SMS bietet gar nichts.

Konkret zur 12h-Pause: Briefings kommen 2×/Tag (morgens/abends). Eine 12h-Pause überspringt faktisch genau ein Briefing = identisch zu SKIP. Stunden-Granularität bildet kein Wanderer-Mentalmodell ab. CONFIG (Web-Formular-Link) ist bei eingeschränkter Konnektivität am Trail praktisch nutzlos.

## Related Files
| File | Relevanz |
|------|-----------|
| `src/output/renderers/email/html.py:826` | „Antwort-Kommandos"-Block (Desktop) + Footer-Zeile (851) |
| `src/output/renderers/email/plain.py` | Plaintext-Variante des Kommando-Hinweises (prüfen) |
| `src/services/trip_command_processor.py` | `_show_help`, `_apply_pause/_apply_skip/_apply_stop`, `_show_status` — kanal-agnostischer Parser |
| `src/services/inbound_email_reader.py` | IMAP-Inbound → Processor → Reply |
| `src/services/inbound_telegram_reader.py` | `_SHORTCUT_MAP`, callback_query, Webhook-Inbound |
| `src/outputs/telegram.py:14` | `BOT_COMMANDS` (Bot-Menü) |
| `src/outputs/sms.py` | Outbound-only, kein Inbound |

## Existing Patterns
- **Kanal-agnostisches Command-DTO:** `CommandResult` mit `confirmation_subject/body` + optional `reply_markup` (nur Telegram nutzt es). Ein Parser (`TripCommandProcessor`), pro Kanal ein Reader.
- **Bare-Keyword-Parsing (#670):** Keywords am Zeilenanfang, additiv neben `### key:value`.
- **On-demand Wetter (#697):** Telegram-Befehle holen Wetter live, wenn kein Snapshot da ist.

## Dependencies
- Upstream: `TripCommandProcessor` (zentral), Forecast/Snapshot-Services für On-demand-Abruf.
- Downstream: alle drei Reader/Renderer; Bot-Menü (`setMyCommands`, manueller Ops-Schritt — siehe #672).

## Existing Specs
- `docs/specs/modules/issue_670_inbound_keywords.md` — aktuelle E-Mail-Keywords
- `docs/specs/modules/inbound_command_channels.md` — Kanal-Inbound-Architektur
- `docs/specs/modules/inbound_telegram_reader.md`, `telegram_webhook_inbound.md`

## Risks & Considerations
- **SMS-Inbound existiert nicht** — echte SMS-Befehlsantworten wären ein eigenes Infrastruktur-Feature (seven.io Inbound-Nummer + Webhook). „soweit sinnvoll" → SMS evtl. nur als Abruf-Trigger oder als Folge-Issue.
- **160-Zeichen-SMS** kann keine Kommando-Liste mittragen — Konsistenz heißt hier „gleiche Befehls-Keywords", nicht „gleiche Darstellung".
- **STOP** ist rechtlich/UX sinnvoll (Abmeldung) und sollte bleiben.
- **Bot-Menü-Sync** ist kein Auto-Deploy-Schritt (#672) — Änderungen an `BOT_COMMANDS` brauchen manuellen `telegram_set_commands.sh`.
- Reine Recherche/Diskussion zuerst — Implementierungsumfang erst nach PO-Entscheidung über den Zielbefehlssatz.
