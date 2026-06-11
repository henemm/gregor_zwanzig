---
entity_id: bug_744_telegram_bare_keywords
type: module
created: 2026-06-11
updated: 2026-06-11
status: complete
version: "1.0"
tags: [telegram, inbound, bare-keywords, channel-consistency, bug, issue-744]
github_issue: 744
related_issue: 731
---

# Bug #744 — Telegram-Inbound: bare Keywords kanalübergreifend konsistent

## Approval

- [x] Approved

## Purpose

Der Telegram-Inbound-Reader (`inbound_telegram_reader.py`) erkennt bare Textnachrichten
`weiter` und `stop` (ohne führenden Slash) nicht — er antwortet „Unbekannter Befehl".
Per E-Mail funktionieren dieselben Keywords. Ursache: Der Telegram-Reader pflegt eine
**eigene, divergierende Whitelist** (`_VALID_COMMANDS`) und verwirft bare Keywords in
`_parse_command`, BEVOR sie den channel-agnostischen `TripCommandProcessor` erreichen.
Der Processor besitzt mit `_BARE_KEYWORD_MAP` bereits den vollständigen, kanonischen
Synonymsatz — der E-Mail-Reader nutzt ihn (Rohtext-Delegation), der Telegram-Reader
umgeht ihn.

Über das Issue hinaus betrifft dieselbe Ursache auch bare `jetzt`, `gewitter` und `help`.

**Fix (root-cause):** Der Telegram-Reader löst bare Keywords über das importierte
`_BARE_KEYWORD_MAP` des Processors auf, statt eine eigene Liste zu führen. Telegram erbt
damit dauerhaft den vollständigen kanalübergreifenden Befehlssatz. Slash-Shortcuts und
das `### key: value`-Format bleiben unberührt. Die veraltete Fehlermeldung wird aktualisiert.

## Source

- **File:** `src/services/inbound_telegram_reader.py` (MODIFY)
  - `_parse_command` (Z.342-369): bare-Keyword-Auflösung über `_BARE_KEYWORD_MAP`
  - `_VALID_COMMANDS` (Z.31-33): ersetzt/abgeleitet aus geteiltem Synonymsatz
  - Fehlermeldung (Z.170): auf aktuellen Befehlssatz aktualisiert
- **Single Source of Truth:** `_BARE_KEYWORD_MAP` in `src/services/trip_command_processor.py:72-86`

## Dependencies

- Upstream: `_BARE_KEYWORD_MAP`, `_QUERY_KEYS` aus `services.trip_command_processor`
- Downstream: Telegram-Inbound-Pipeline (Webhook/Polling → Reader → Processor → TelegramOutput)

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit aktivem Trip und pausiertem Versand / When er dem Telegram-Bot die bare Nachricht `weiter` (ohne Slash, beliebige Groß-/Kleinschreibung) sendet / Then wird der Versand reaktiviert (`_resume_trip`) und der Bot bestätigt — identisch zum E-Mail-Verhalten, NICHT „Unbekannter Befehl".

- **AC-2:** Given ein Nutzer mit aktivem Trip / When er dem Telegram-Bot die bare Nachricht `stop` (ohne Slash) sendet / Then wird der Trip-Versand abgemeldet (interne Aktion `abbruch`, `_cancel_trip`) und der Bot bestätigt die Abmeldung, NICHT „Unbekannter Befehl".

- **AC-3:** Given die kanalübergreifende Konsistenz aus #731 / When ein Nutzer dem Telegram-Bot bare `jetzt`, `gewitter` oder `help` sendet / Then werden diese exakt wie per E-Mail aufgelöst (`jetzt`→Nowcast, `gewitter`→Gewitter-Sicht, `help`→Hilfe), weil Telegram und E-Mail dasselbe `_BARE_KEYWORD_MAP` nutzen.

- **AC-4:** Given ein unbekannter Befehl (z.B. bare `quatsch`) / When er an den Telegram-Bot gesendet wird / Then antwortet der Bot mit „Unbekannter Befehl" und einer Fehlermeldung, die den AKTUELLEN abruf-zentrierten Befehlssatz nennt (heute/morgen/jetzt/gewitter/ruhetag/status/stop/weiter/hilfe) — NICHT die veraltete Liste „ruhetag, startdatum, report, abbruch, status, hilfe".

- **AC-5:** Given das bestehende Verhalten (Regression-Schutz) / When Slash-Shortcuts (`/h`, `/status`, `/jetzt`, …), Query-Keys (`heute`/`morgen`/`gewitter`/`glance` mit On-demand-Wetter-Flow) und das `### key: value`-Format genutzt werden / Then funktionieren sie unverändert; insbesondere lösen Query-Keys weiterhin die Loading-Message + On-demand-Fetch aus (`key in _QUERY_KEYS` greift mit dem aufgelösten internen Key).

## Nachweis (mock-frei)

Mock-freier Test über die echte Telegram-Pipeline analog `tests/tdd/test_e2e_telegram_pipeline.py`:
Update-Dict (bare `weiter`/`stop`/`jetzt`/`gewitter`/`help`/`quatsch`) → `_process_update`/`_parse_command` →
`TripCommandProcessor` → beobachtbares `CommandResult` (`command`, `success`, `confirmation_subject`).
Kein `Mock()`/`patch()` für den Befehls-Dispatch. Vergleichsweise dieselben Keywords gegen den
E-Mail-Pfad-Processor, um identisches Verhalten zu beweisen.

## Out of Scope

- Änderung des `_BARE_KEYWORD_MAP`-Inhalts selbst (Single Source bleibt der Processor).
- Slash-Shortcut-Erweiterungen.
- Neue Befehle.

## Changelog

- **2026-06-11 v1.0:** Initiale Spec (Bug #744, Folge aus #731 F001).
- **2026-06-11 v1.0 (IMPLEMENTED):** Implementation complete in `src/services/inbound_telegram_reader.py` — bare Keywords aufgelöst über `_BARE_KEYWORD_MAP`, Fehlermeldung aktualisiert auf abruf-zentrierten Befehlssatz. Alle ACs verifiziert. Siehe `src/services/inbound_telegram_reader.py:343-378` und Z.171.
