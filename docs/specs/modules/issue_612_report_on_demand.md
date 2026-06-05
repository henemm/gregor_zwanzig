---
entity_id: issue_612_report_on_demand
type: module
created: 2026-06-05
updated: 2026-06-05
status: draft
version: "1.0"
tags: [inbound, briefing, email, telegram, on-demand]
---

<!-- Issue #612 — E-Mail/Telegram auf Anforderung -->

# Issue 612 — Briefing auf Anforderung

## Approval

- [x] Approved

## Purpose

Wanderer mit wechselndem Empfang sollen jederzeit per E-Mail-Antwort oder Telegram-Nachricht
ein Morgen-/Abend-Briefing adhoc abrufen können — und in jedem ausgehenden Briefing einen
sichtbaren Hinweis auf die verfügbaren Befehle sehen, damit der Einstieg offensichtlich ist.

## Source

- **File:** `src/output/renderers/email/html.py` — `render_html` (Z.245): Befehls-Footer im HTML-Footer-`<div>` (Z.586) anhängen.
- **File:** `src/output/renderers/narrow.py` — `render_narrow` (Z.144): kompakter Befehls-Footer NUR für `channel == "telegram"` (vor Überlängen-Kappung).
- **File:** `src/services/trip_command_processor.py` — `InboundMessage` (Z.30) um additives `user_id`-Feld erweitern; `_find_trip` (Z.147) und `_trigger_report` (Z.215) nutzen `msg.user_id` statt Default.
- **File:** `src/services/inbound_email_reader.py` — `InboundMessage(...)` (Z.131) um `user_id=_user_id` ergänzen.
- **File:** `src/services/inbound_telegram_reader.py` — `InboundMessage(...)` (Z.131) um `user_id=user_id` ergänzen.

## Estimated Scope

- **LoC:** ~40
- **Files:** 5
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripReportSchedulerService` | service | On-Demand-Versand des Briefings (user-scoped via `user_id`) |
| `load_all_trips(user_id)` | loader | User-gescopter Trip-Lookup im Processor |
| `lookup_user_by_email` / `lookup_user_by_telegram_chat_id` | loader | Sender → user_id (bereits in den Readern aufgelöst) |

## Implementation Details

```
# 1. Befehls-Footer (E-Mail, render_html)
#    Statischer Block im bestehenden .footer-div:
#    "Befehle (auf diese Mail antworten): report morning · report evening · status · hilfe"

# 2. Befehls-Footer (Telegram, render_narrow)
#    Nur wenn channel == "telegram": Trennzeile + kompakter Hinweis vor body-join:
#    "Befehle: report morning | report evening | status | hilfe"
#    Signal bleibt unverändert (kein Inbound-Reader).

# 3. User-Kontext durchreichen (additiv, keine Breaking Change)
#    InboundMessage erhält Feld: user_id: str = "default"
#    _find_trip(msg.trip_name) -> load_all_trips(msg.user_id)
#    _trigger_report -> TripReportSchedulerService(user_id=msg.user_id)
#    Reader füllen user_id aus dem bereits aufgelösten Sender-Mapping.
```

## Expected Behavior

- **Input:** Inbound `report morning|evening` (Mail `### report: morning`, Telegram Freitext) vom registrierten Sender.
- **Output:** Das angeforderte Briefing wird an die für DIESEN User konfigurierten Kanäle gesendet;
  ausgehende Briefing-Mails/Telegram-Nachrichten enthalten den Befehls-Footer.
- **Side effects:** Briefing-Versand (E-Mail/Telegram) für den korrekten User; keine Datenänderung.

## Acceptance Criteria

- **AC-1:** Given ein registrierter Nutzer mit einem Trip / When er per E-Mail `### report: evening` als Antwort sendet / Then erhält er innerhalb von 2 Minuten das Abend-Briefing an seine konfigurierte E-Mail-Adresse.
  - Test: Inbound-Mail an Stalwart-Test-Postfach mit `### report: evening` + Trip im Betreff; IMAP-Prüfung dass eine Briefing-Mail (Subject enthält Trip + "Evening") zugestellt wurde.

- **AC-2:** Given ein registrierter Telegram-Nutzer mit Trip / When er `report morning` schickt / Then erhält er das Morgen-Briefing als Telegram-Nachricht.
  - Test: `render_narrow("telegram", report_type="morning", ...)` erzeugt nicht-leeren Body; On-Demand-Pfad sendet über TelegramOutput (echter Aufruf, kein Mock).

- **AC-3:** Given irgendeine automatisch versendete Briefing-E-Mail / When sie gerendert wird / Then enthält der HTML-Body am Ende einen Befehls-Abschnitt mit `report morning`, `report evening`, `status` und `hilfe`.
  - Test: `render_html(...)`-Ausgabe enthält die vier Befehls-Strings im Footer-Bereich (Verhaltensnachweis am gerenderten Body).

- **AC-4:** Given eine Telegram-Briefing-Nachricht / When sie via `render_narrow("telegram", ...)` gerendert wird / Then endet der Text mit einem kompakten Befehls-Hinweis (enthält `report morning` und `hilfe`) und bleibt innerhalb des Telegram-Zeichenlimits.
  - Test: `render_narrow("telegram", ...)` enthält Befehls-Hinweis; `render_narrow("signal", ...)` enthält ihn NICHT; `len(body) <= max_chars`.

- **AC-5:** Given ein Inbound-`report`-Befehl mit ungültigem Typ (z.B. `### report: abend`) / When er verarbeitet wird / Then erhält der Nutzer eine Fehlermeldung die `morning` und `evening` als erlaubte Werte nennt.
  - Test: `TripCommandProcessor().process(InboundMessage(body="### report: abend", ...))` liefert `success=False` und Body mit "morning" + "evening".

- **AC-6:** Given ein Multi-User-Setup mit Nutzer X (nicht "default") und dessen Trip / When X einen `report`-Befehl sendet / Then wird der Trip in X's Daten gefunden und das Briefing für X (nicht für "default") generiert.
  - Test: `InboundMessage(user_id="userX", trip_name=<X-Trip>, body="### report: morning")` → Processor findet den X-Trip via `load_all_trips("userX")` und instanziiert `TripReportSchedulerService(user_id="userX")` (success=True).
