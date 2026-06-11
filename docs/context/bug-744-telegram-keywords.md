# Context: Bug #744 — Telegram-Inbound erkennt bare Keywords `weiter`/`stop` nicht

## Request Summary
Bare Textnachrichten `weiter` (Versand reaktivieren) und `stop` (abmelden) ohne führenden Slash werden im Telegram-Bot mit „Unbekannter Befehl" abgewiesen, obwohl dieselben Keywords per E-Mail funktionieren. Folge-Issue aus #731 (Adversary-Finding F001, LOW).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/inbound_telegram_reader.py:31-33` | `_VALID_COMMANDS` — eigene Telegram-Whitelist, OHNE `weiter`/`stop`/`jetzt`/`gewitter`/`help` |
| `src/services/inbound_telegram_reader.py:166-174` | `_process_update` baut `### {key}`-Body, veraltete Fehlermeldung Z.170 |
| `src/services/inbound_telegram_reader.py:342-369` | `_parse_command` — dupliziert Parsing, validiert gegen eigene Whitelist |
| `src/services/trip_command_processor.py:72-86` | `_BARE_KEYWORD_MAP` — Single Source of Truth für bare Keywords (E-Mail-Pfad): `stop`→`abbruch`, `weiter`→`weiter`, `jetzt`→`now`, `gewitter`→`heute_gewitter`, `help`→`hilfe` |
| `src/services/inbound_email_reader.py:127-139` | E-Mail-Reader gibt **Rohtext** an `process()` → nutzt `_BARE_KEYWORD_MAP` direkt |
| `tests/tdd/test_inbound_telegram_reader.py` | Bestehende Reader-Tests |
| `tests/tdd/test_issue_731_unified_commands.py` | #731 Kanal-Vereinheitlichung |
| `tests/tdd/test_e2e_telegram_pipeline.py` | Mock-freie E2E (Webhook→Processor→TelegramOutput) |

## Root Cause
Der Telegram-Reader hat eine **zweite, divergierende Befehls-Whitelist** (`_VALID_COMMANDS`),
die das Parsing des Processors dupliziert. Bare Keywords werden in `_parse_command` gegen
diese lokale Liste geprüft und VOR Erreichen des Processors verworfen. Der Processor besitzt
mit `_BARE_KEYWORD_MAP` bereits den vollständigen, kanalübergreifenden Synonymsatz — der
E-Mail-Reader nutzt ihn (Rohtext-Delegation), der Telegram-Reader umgeht ihn.

**Befund über das Issue hinaus:** Nicht nur `weiter`/`stop` fehlen — bare `jetzt`, `gewitter`
und `help` werden auf Telegram ebenfalls abgelehnt, sind per E-Mail aber gültig. Dieselbe Ursache.

## Subtilität bei `stop`
`stop` ist ein Synonym für die interne Aktion `abbruch`. Würde der Telegram-Reader naiv
`### stop` an den Processor schicken, schlägt es erneut fehl: Der `###`-Pfad des Processors
geht NICHT durch `_BARE_KEYWORD_MAP`, und `stop` ist nicht in dessen `_VALID_COMMANDS`
(dort `abbruch`). Der Telegram-Reader muss `stop`→`abbruch` **auflösen**, bevor er den
`### {key}`-Body baut.

## Existing Patterns
- `_SHORTCUT_MAP` (Telegram, Z.35-55): Slash-Varianten → interner Key. Bare Keywords haben kein Pendant.
- `_BARE_KEYWORD_MAP` (Processor, Z.72-86): kanonische bare-Keyword-Auflösung. Alle Ziel-Keys werden vom Processor-`###`-Pfad + Dispatch erkannt (Query-Keys, `weiter`, `now`, `ruhetag`, `status`, `hilfe`, `abbruch`).

## Lösungsoptionen
- **A (minimal):** `weiter` + `stop`→`abbruch`-Auflösung im Telegram-Reader nachziehen, Fehlermeldung updaten. Behebt das Issue, lässt `jetzt`/`gewitter`/`help` weiter inkonsistent.
- **B (root-cause, empfohlen):** Telegram-`_parse_command` löst bare Keywords über das importierte `_BARE_KEYWORD_MAP` auf. Telegram erbt damit den vollständigen Synonymsatz dauerhaft und automatisch → ganze Bug-Klasse eliminiert, kein erneutes Drift. Quasi gleicher Aufwand.

## Dependencies
- Upstream: `_BARE_KEYWORD_MAP`, `_QUERY_KEYS` aus `trip_command_processor`
- Downstream: Telegram-Inbound-Pipeline (Webhook/Polling → Processor → TelegramOutput)

## Existing Specs
- `docs/specs/modules/inbound_telegram_reader.md` (Reader-Spec)

## Risks & Considerations
- Slash-Befehle (`_SHORTCUT_MAP`) müssen Vorrang/Koexistenz behalten.
- Query-Keys (`heute`/`morgen`/`gewitter`/`glance`) lösen den On-demand-Wetter-Flow (Loading-Message, Z.195) aus — Auflösung muss dieselben internen Keys liefern, damit `key in _QUERY_KEYS` greift.
- Mock-frei testen: echte Pipeline (`test_e2e_telegram_pipeline.py`-Muster) statt Mocks.
- Klein halten (LoC-Limit 250).
