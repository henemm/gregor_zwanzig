---
entity_id: issue_1007_heute_voll_briefing
type: feature
created: 2026-07-04
updated: 2026-07-04
status: draft
version: "1.0"
tags: [inbound, briefing, telegram, email, commands]
---

# Issue 1007 — „Heute"/„Morgen" liefern das volle Tages-Briefing

## Approval

- [ ] Approved

## Purpose

PO-Entscheidung (Issue #1007, 2026-07-04): Eine Antwort mit `heute`/`morgen` auf ein
Briefing (E-Mail-Reply-Keyword oder Telegram `/heute`, `/h`, `/morgen`, `/m` sowie die
Inline-Buttons „Heute"/„Morgen") löst künftig das **komplette Tages-Briefing** für den
jeweiligen Tag aus — über die konfigurierten Kanäle des Trips, im vollen Briefing-Format
(HTML-Stundentabellen bzw. Telegram-Multi-Bubbles #1001). Der bisherige Einzeiler
(`_fmt_day`) entfällt für diese beiden Keywords; die Kurzform bleibt unverändert unter
`glance` verfügbar.

## Source

- **File:** `src/services/trip_command_processor.py` — `_handle_query()` Zweige
  `heute`/`morgen` (Zeilen 432-449): statt `_fmt_day()`-Einzeiler den Voll-Briefing-
  Versand auslösen (Wiederverwendung des `_trigger_report`-Pfads, Zeilen 799-831) —
  **Kernänderung**
- **File:** `src/services/trip_report_scheduler.py` — `send_test_report()` (387-409):
  bekommt einen On-Demand-Modus (kein „[TEST]"-Präfix, kein Etappen-Fallback) ODER eine
  dünne Schwester-Methode `send_on_demand_report(trip, report_type)`; die bestehende
  Test-Semantik (#768) bleibt für `report`/UI-Testversand unverändert
- **File:** `src/services/inbound_email_reader.py` — `_send_email_reply()` (156-165):
  bei erfolgreichen `heute`/`morgen`-Kommandos KEINE separate Bestätigungs-Mail (das
  Briefing ist die Antwort); Misserfolgs-Antworten (z.B. „Keine Etappe geplant") werden
  weiterhin als Reply gesendet
- **File:** `src/services/inbound_telegram_reader.py` — Mapping unverändert (33-63);
  Verhalten ändert sich transitiv über den Processor
- **Identifier:** `_handle_query`, `_trigger_report`, `send_test_report`,
  `_get_target_date` (morning=heute, evening=morgen — bereits vorhanden, 312-326)

## Estimated Scope

- **LoC:** ~60-100 Produktionscode, +120 Tests
- **Files:** ~5 (Code 3, Tests 2)
- **Effort:** small-medium — **Risk Level:** LOW-MEDIUM (bestehender Versandpfad wird
  wiederverwendet; heikel sind nur Kennzeichnung, Fallback-Abschaltung, Doppel-Mail)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `send_test_report()` / `_send_trip_report()` | function | Bewährter Voll-Briefing-Versand über alle Trip-Kanäle (seit #1004 mit korrekten SSoT-Startzeiten) |
| `_get_target_date()` | function | morning→heute, evening→morgen — Mapping existiert |
| `_QUERY_KEYS` / `_handle_query()` | dispatch | `heute`/`morgen` bleiben Query-Keys, ändern nur ihr Verhalten |
| `_fmt_glance`/`_fmt_day_agg` | functions | bleiben unverändert (glance-Pfad) |
| Issue #768 Test-Fallback/[TEST]-Präfix | behavior | darf im `report`-/UI-Pfad NICHT verändert werden |

## Implementation Details

1. `_handle_query()`: `heute` → Voll-Briefing `morning`, `morgen` → Voll-Briefing
   `evening`, jeweils über den On-Demand-Modus (kein [TEST], kein Fallback).
2. On-Demand-Modus im Scheduler: Subject/Hinweiszeile kennzeichnen die Mail dezent als
   „auf Anfrage" (statt „[TEST]"); bei fehlender Etappe am Zieltag wird NICHT auf eine
   andere Etappe ausgewichen — Rückgabe False.
3. Rückgabe an den Inbound-Pfad: Erfolg → `CommandResult` mit Flag
   `suppress_email_reply=True` (E-Mail: keine Bestätigungs-Mail; Telegram: kurze
   Bestätigungs-Bubble entfällt ebenfalls — die Briefing-Bubbles kommen ohnehin).
   Misserfolg (keine Etappe) → normale kurze Antwort über den bestehenden Reply-Weg.
4. `glance` und alle übrigen Query-Keys bleiben byte-identisch.

## Expected Behavior

- **Input:** Inbound-Kommando `heute` oder `morgen` (E-Mail-Reply-Keyword, Telegram
  `/heute`//h`//morgen`//m`, Glance-Inline-Button) für einen Trip des Nutzers
- **Output:** Das volle Tages-Briefing für heute bzw. morgen wird sofort über die
  konfigurierten Kanäle des Trips versendet (E-Mail: volles HTML-Briefing derselben
  Pipeline wie der Scheduler; Telegram: Multi-Bubbles). Keine separate
  Bestätigungs-Nachricht bei Erfolg. Ohne Etappe am Zieltag: kurze Antwort
  „Keine Etappe geplant" ohne Briefing-Versand.
- **Side effects:** Kein [TEST]-Präfix im On-Demand-Modus; `briefing_log` wird wie beim
  bisherigen Test-Versand fortgeschrieben; Kurzform `glance` unverändert.

## Acceptance Criteria

- **AC-1 (E-Mail „heute" = volles Briefing):** Given ein Nutzer mit einem Trip, dessen
  Etappe heute liegt und dessen Kanal E-Mail konfiguriert ist / When per Inbound-Pfad
  das Kommando `heute` verarbeitet wird / Then wird das volle HTML-Briefing für HEUTE
  (Stundentabellen, gleiche Render-Pipeline wie der Scheduler-Versand, Marker
  `X-GZ-Mail-Type: trip-briefing`) an die Empfänger des Nutzers versendet — kein
  Einzeiler-Text.
  - Test: Echten Trip unter `data/users/<testuser>/` anlegen,
    `TripCommandProcessor.process()` mit echter `InboundMessage` aufrufen, die real
    zugestellte Mail via IMAP (gregor-test@henemm.com, Stalwart) abrufen und Format
    (Marker-Header, Stundentabelle, Tagesdatum HEUTE) prüfen. Kein Mock.

- **AC-2 („morgen" = volles Briefing für morgen):** Given derselbe Trip mit einer
  Etappe morgen / When das Kommando `morgen` verarbeitet wird / Then wird das volle
  Briefing mit Zieldatum MORGEN versendet (evening-Zieldatum-Mapping), erkennbar am
  Etappen-/Datumsbezug in der Mail.
  - Test: wie AC-1, Assertions auf Datum/Etappe von morgen.

- **AC-3 (Kennzeichnung ohne [TEST]):** Given ein per `heute` ausgelöstes Briefing /
  When die Mail zugestellt ist / Then enthält der Betreff KEIN „[TEST]"-Präfix; die
  Kennzeichnung „auf Anfrage" ist vorhanden; der bestehende `report`-Befehl und der
  UI-Testversand behalten ihr „[TEST]"-Verhalten (#768) unverändert.
  - Test: Subject-Vergleich beider Pfade gegen real zugestellte Mails bzw. den
    Render-Rückgabewert; Regressionstest für `report`.

- **AC-4 (keine Etappe → klare Antwort, kein Fallback):** Given ein Trip OHNE Etappe
  am Zieltag / When `heute` bzw. `morgen` verarbeitet wird / Then wird KEIN Briefing
  versendet (auch nicht für einen anderen Tag — der #768-Test-Fallback greift hier
  nicht) und die Antwort lautet erkennbar „Keine Etappe geplant" (mit Datum) über den
  normalen Reply-Weg.
  - Test: Processor-Aufruf mit passendem Trip-Zustand; prüfen dass kein Versand
    stattfand (briefing_log unverändert / IMAP leer) und die Antwort den Hinweis trägt.

- **AC-5 (keine Doppel-Mail):** Given ein erfolgreiches `heute`-Kommando per E-Mail /
  When der Inbound-Reader die Antwort verarbeitet / Then erhält der Nutzer GENAU EINE
  Mail (das Briefing) — keine zusätzliche Bestätigungs-Mail „Report wird gesendet".
  - Test: IMAP-Postfach vor/nach dem Kommando zählen — genau +1 Mail, und diese ist
    das Briefing (Marker-Header), keine Bestätigung.

- **AC-6 (glance bleibt Kurzform):** Given derselbe Trip-Zustand / When das Kommando
  `glance` verarbeitet wird / Then kommt weiterhin die bisherige Kurzform
  (Einzeiler-Aggregat heute & morgen) als Antwort und KEIN Briefing-Versand —
  byte-gleiches Format wie vor dieser Änderung.
  - Test: bestehende Glance-Tests (#651) bleiben grün + expliziter Vergleich.

- **AC-7 (Telegram-Pfad):** Given ein Nutzer mit konfiguriertem Telegram-Kanal / When
  `/heute` (bzw. Kurzform `/h`) verarbeitet wird / Then werden die vollen
  Briefing-Bubbles (#1001-Format: Kopf, Kurzübersicht, Segment-Tabellen) für HEUTE
  gesendet statt des Einzeilers.
  - Test: Processor-/Reader-Aufruf über den echten Telegram-Codepfad (Staging-Bot,
    `GZ_TELEGRAM_TEST_CHAT_ID`), Bubble-Struktur prüfen; lokal mindestens der
    Processor-Beweis, auf Staging der Live-Beweis.

- **AC-8 (Zwei-Nutzer-Isolation):** Given Nutzer A und B mit jeweils eigenem Trip und
  eigenen Empfängern / When Nutzer A `heute` auslöst / Then wird ausschließlich As Trip
  gerendert und ausschließlich an As Empfänger versendet — B erhält nichts, Bs Daten
  werden nicht angefasst.
  - Test: Echte Persistenz für zwei Test-User, Kommando nur für A, Nachweis über
    Empfänger/briefing_log beider User.

## Known Limitations

- **`report`-Befehl bleibt unverändert** (inkl. „[TEST]"-Präfix und #768-Fallback) —
  bewusst, da er der explizite „Testversand"-Befehl ist.
- **Kein neues Throttling:** Wiederholte `heute`-Kommandos lösen jeweils ein Briefing
  aus (wie heute schon `report`). Missbrauch ist durch den 1-Postfach-Kontext des
  Nutzers begrenzt; ein Cooldown wäre ein separates Feature.
- **SMS bleibt außen vor:** SMS-Kanal erhält das Briefing nur, wenn er am Trip ohnehin
  konfiguriert ist (identisch zum `report`-Verhalten) — keine SMS-spezifische Logik in
  diesem Issue.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine — kein neues Datenschema, kein neuer Kanal, kein neues Gate;
  Wiederverwendung des bestehenden Versandpfads mit einem Modus-Parameter.

## Test Coverage

- `tests/tdd/test_issue_1007_heute_voll_briefing.py` (NEU) — AC-1 bis AC-6, AC-8 +
  F001/F002-Adversary-Fix (kein separates `test_issue_1007_telegram_heute.py`
  angelegt — AC-7 wird lokal per Code-/Processor-Beweis abgedeckt, der
  Live-Beweis erfolgt auf Staging im E2E-Schritt).
- `tests/tdd/test_issue_651_telegram_query_glance.py` — Glance-Tests (AC-1, AC-2,
  AC-6) unverändert grün (Regression); die zwei AC-3-Tests (`heute`/`morgen`
  einzeiler-spezifisch) sind als „Superseded by #1007" markiert, da dieses
  Verhalten durch den Voll-Briefing-Versand ersetzt wurde — reale Abdeckung
  jetzt in `test_issue_1007_heute_voll_briefing.py` (AC-1/AC-2).
- `tests/tdd/test_issue_670_inbound_keywords.py` — brauchte keine Anpassung
  (enthält keine direkten heute/morgen-Assertions). Die zwei dort beobachteten
  Fehlschläge (`test_help_lists_current_keywords`, `test_block_lists_all_keywords`)
  sind vorbestehende, von #1007 unabhängige Test-Drift (#882 vs. #731-Erwartung
  bzw. veralteter #884-Footer) → nachgezogen in Issue #1008.

## Changelog

- 2026-07-04: Initial spec — PO-Entscheidung aus Issue #1007 (Option „volles
  Tages-Briefing"), aufbauend auf `docs/context/feat-1007-heute-voll-briefing.md`.
- 2026-07-04: Adversary-Fix F001/F002 — `_send_trip_report` unterscheidet intern
  die Outcomes `sent`/`no_stage`/`no_weather`/`no_channels` statt eines reinen
  bool (F001: kein Kanal konfiguriert lieferte vorher stillschweigend `True` →
  `suppress_email_reply` unterdrückte die Antwort komplett; F002: „keine
  Wetterdaten" wurde fälschlich als „keine Etappe geplant" gemeldet).
  `send_on_demand_report` gibt das Outcome zurück, `_trigger_on_demand` mappt es
  über die reine Funktion `_on_demand_failure_body()` auf den Antworttext.
  Legacy-Aufrufer (`send_test_report`, `send_reports`, `send_reports_for_hour`)
  behalten ihre exakte bool-Semantik unangetastet.
