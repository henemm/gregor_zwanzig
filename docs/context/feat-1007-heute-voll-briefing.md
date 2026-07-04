# Context: feat-1007-heute-voll-briefing (Issue #1007)

## Request Summary
PO-Entscheidung (2026-07-04, Issue #1007): Eine Antwort mit `heute`/`morgen` auf ein
Briefing (E-Mail-Reply oder Telegram `/heute`, `/h`, `/morgen`, `/m`) soll künftig das
**volle Tages-Briefing** für den jeweiligen Tag auslösen — nicht mehr den Einzeiler.
Die bisherige Kurzform bleibt unter `glance` erreichbar.

## Ist-Zustand
- `heute`/`morgen` sind Query-Keys (`trip_command_processor.py:96-97, 432-449`,
  `_QUERY_KEYS`) → `_handle_query()` → `_fmt_day()` → EINE Zeile Tages-Aggregat aus dem
  Wetter-Snapshot (`WeatherExtractor.timeline`). Kein Fehler — Design aus #670/#651.
- Volles Briefing on demand existiert bereits: Befehl `report` →
  `_trigger_report()` (`trip_command_processor.py:345, 799-831`) →
  `TripReportSchedulerService.send_test_report(trip, report_type)` — versendet das
  komplette Briefing über die konfigurierten Kanäle des Trips (HTML-Mail, Telegram-
  Bubbles #1001) + separate Bestätigungs-Antwort ("Report wird jetzt gesendet.").
- Zieldatum-Mapping bereits vorhanden (`trip_report_scheduler.py:312-326`):
  `morning` → heute, `evening` → morgen. `heute`≙morning, `morgen`≙evening.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_command_processor.py:289-306,408-449` | Query-Dispatch + `heute`/`morgen`-Zweige — Kernänderung hier |
| `src/services/trip_command_processor.py:799-831` | `_trigger_report()` — bestehender Voll-Briefing-Pfad (Vorbild/Wiederverwendung) |
| `src/services/trip_report_scheduler.py:387-409` | `send_test_report()` — [TEST]-Präfix + `allow_test_fallback=True` (#768) |
| `src/services/trip_report_scheduler.py:312-326` | `_get_target_date()`: morning=heute, evening=morgen |
| `src/services/inbound_email_reader.py:156-165` | E-Mail-Antwortweg (`_send_email_reply` mit `confirmation_body`) |
| `src/services/inbound_telegram_reader.py:33-63` | Telegram-Mapping `/heute`→heute etc. — unverändert nutzbar |
| `tests/tdd/test_issue_670_inbound_keywords.py` | Bestehende Tests der Keyword-Semantik — müssen angepasst werden |
| `tests/tdd/test_issue_651_telegram_query_glance.py` | Glance-Tests — dürfen NICHT brechen (glance bleibt) |
| `tests/tdd/test_issue_612_report_on_demand.py` | Report-on-Demand-Tests — Vorbild |

## Existing Patterns
- Voll-Briefing on demand = `send_test_report()` (ein Aufruf, alle Kanäle des Trips).
- Query-Antworten laufen als `CommandResult.confirmation_body` zurück
  (E-Mail: Reply-Mail; Telegram: Bubble mit `reply_markup`-Buttons).

## Dependencies
- Upstream: `send_test_report` (Compute-on-Send, seit #1004 korrekte SSoT-Startzeiten).
- Downstream: E-Mail-Reply-Pfad, Telegram-Reader, Inline-Buttons (`_HEUTE_BUTTONS`,
  `_MORGEN_BUTTONS`, `_GLANCE_BUTTONS` — Buttons "Heute"/"Morgen" in Glance lösen
  künftig ebenfalls das volle Briefing aus, gleiche Codepfade).

## Risks & Considerations
- **[TEST]-Präfix:** `send_test_report` markiert Mails mit "[TEST]" + Hinweiszeile
  (#768). Für `heute`/`morgen`-Antworten wäre das irreführend — Spec muss entscheiden
  (eigener Kennzeichnungs-Modus "auf Anfrage" oder Präfix akzeptieren).
- **Fallback-Semantik:** `send_test_report` nutzt `allow_test_fallback=True` — ohne
  Etappe am Zieltag weicht es auf die nächste Etappe aus. Für `heute` ohne Etappe ist
  stattdessen eine klare "Keine Etappe geplant"-Antwort erwartbar (Fallback aus).
- **Doppel-Zustellung E-Mail:** Bestätigungs-Reply + Voll-Briefing = 2 Mails. Spec
  sollte die separate Bestätigung für `heute`/`morgen` unterdrücken (das Briefing IST
  die Antwort) oder bewusst beibehalten.
- **glance unverändert:** `_fmt_glance`/`_fmt_day_agg` bleiben (weiter von glance und
  ggf. Buttons genutzt) — keine Löschung.
- Kanal-Konsistenz: Telegram-Kurzbefehle (`/h`, `/m`) und E-Mail-Keywords nutzen
  denselben Query-Pfad — Änderung wirkt automatisch für beide (PO-Vorgabe erfüllt).

## Existing Specs
- `docs/specs/modules/` — #612 (Report-on-Demand), #670 (Inbound-Keywords), #651
  (Query-Glance), #1001 (Telegram-Bubbles) als semantische Nachbarn.
