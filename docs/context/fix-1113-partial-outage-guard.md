# Context: fix-1113-partial-outage-guard

## Request Summary
Issue #1113: Beim open-meteo-Ausfall am 2026-07-08 (5 von 6 Segmenten 503) wurde das
Trip-Briefing trotzdem versendet — der No-Data-Guard (#1012) greift nur bei 100 %
Ausfall. PO-Entscheidung (2026-07-08): Zurückhalten wenn **>75 %** der Segmente ohne
Daten (dann `send_no_data_hint` + Pending-Marker wie bei Totalausfall); darunter
senden, aber mit **deutlichem Hinweis** auf die fehlenden Abschnitte. Ergänzend
Retry/Backoff beim Wetter-Fetch gegen kurze 503-Aussetzer.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py:639` | Der Guard `all(s.has_error ...)` — Kern des Fixes (Schwelle >75 %) |
| `src/services/trip_report_scheduler.py:907` (`_fetch_weather`) | Fetch-Schleife mit Error-Platzhaltern — Ansatzpunkt für Retry pro Segment |
| `src/services/trip_report_scheduler.py:213` (`_process_pending_markers`) | Nachliefer-Mechanik (#1012 b2) — bleibt unverändert, wird vom neuen Guard mitgenutzt |
| `src/services/notification_service.py:86,259,578` | `catchup_prefix`-Injektion (Hinweiszeile in E-Mail/Telegram) — Vorbild/Mechanik für den „deutlichen Hinweis" bei Teilausfall; `_send_service_error_email` nur SMS-only |
| `src/services/segment_weather.py` | `fetch_segment_weather` — alternativer Retry-Ort |
| `src/providers/` (`base.py`, openmeteo) | Provider-Kette; 503 kommt als Exception nach oben |
| `src/output/renderers/email/{html,plain,helpers}.py`, `trip_report.py` | Rendern `has_error`-Segmente bereits als Fehlerzeile — hier ggf. prominenter Hinweis-Block (ACHTUNG Renderer-Commit-Gate #811) |
| `tests/tdd/test_issue_1012_no_data_guard.py` | Bestehende Tests für Totalausfall-Guard + Marker — Vorbild und Regressionsschutz |
| `tests/tdd/test_issue_766_smtp_retry.py` | Bestehendes Retry-Muster (SMTP) als Referenz |

## Existing Patterns
- **Guard + Marker (#1012):** Totalausfall → `send_no_data_hint` (kurze Hinweis-Mail) +
  `_write_pending_marker`; stündliche Nachlieferung via `_process_pending_markers`
  mit Präfix („Nachgeliefert …" / „Aktualisiert …"). Funktionierte im Incident
  (Nachlieferung 06:23 UTC).
- **Hinweis-Präfix:** `catchup_prefix` wird in `notification_service.py` in
  email_plain/email_html (`_inject_html_hint`) und erste Telegram-Bubble injiziert —
  gleiche Mechanik kann den Teilausfall-Hinweis tragen.
- **Teilausfall heute:** `failed_segments` im Request → Pending-Marker wird bereits
  geschrieben (Schritt 9), aber Briefing geht ungebremst raus; Service-Error-Mail nur
  bei SMS-only-Trips.
- **Fehler-Platzhalter:** `_fetch_weather` liefert nie eine leere Liste — pro Fehler
  ein `SegmentWeatherData(has_error=True)` (WEATHER-04).

## Dependencies
- Upstream: `SegmentWeatherService.fetch_segment_weather` → Provider `openmeteo`
  (503-Exceptions), `get_provider`-Kette.
- Downstream: `send_reports_for_hour` (Outcome-Zählung „partial" für Monitoring #766),
  On-Demand-Pfad (#1007, `on_demand=True` — kein Marker/Hinweis-Versand),
  Test-Versand (`send_test_report`), Briefing-Log (#393), Snapshot/Alert-Reset (#816).

## Existing Specs
- `docs/specs/modules/` — kein eigenes Modul-Spec für trip_report_scheduler-Guard;
  Spec für diesen Fix wird neu unter `docs/specs/modules/` angelegt (AC-N-Format Pflicht).

## Risks & Considerations
- **Renderer-Commit-Gate #811:** Änderungen an `src/output/renderers/email/*` oder
  `notification_service`-nahen Mail-Dateien verlangen frischen
  `test_issue_811_mode_matrix.py`-Lauf + grünen `briefing_mail_validator.py`.
  Falls der Hinweis über den bestehenden `catchup_prefix`-Mechanismus injiziert wird
  (notification_service, kein Renderer-File), bleibt der Eingriff minimal.
- **Schwellen-Semantik:** „>75 % fehlen" — bei 6 Segmenten heißt das: 5 oder 6 fehlen
  → zurückhalten; 4 fehlen (66,7 %)… Achtung Rundung: 5/6 = 83 % > 75 % ✓,
  edge case 3/4 = 75 % ist NICHT >75 % → senden mit Hinweis. In ACs explizit machen.
- **On-Demand (#1007)** darf weiterhin weder Marker noch Hinweis-Mail erzeugen
  (Bot antwortet synchron).
- **Retry-Budget:** Scheduler-Lauf ist synchron im 5-Minuten-Cron-Fenster; Retry
  (z. B. 2 Versuche, kurzer Backoff) darf den Lauf über alle User nicht sprengen.
- **KEINE Mocks:** Tests müssen echtes Verhalten beweisen; für 503-Simulation
  Provider-Injection-Seam (`_fetch_weather(provider=...)`, Demo-Mode-Muster #483)
  nutzen statt `patch()`.
- Monitoring-Sichtbarkeit (briefing_health) ist bewusst **außerhalb** dieses
  Workflows → #1114.

## Analysis

### Type
Bug (Incident-getrieben, Root Cause durch Log-Forensik bewiesen — kein Hypothesen-Risiko)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_report_scheduler.py` | MODIFY | Guard-Schwelle >75 % in `_send_trip_report_outcome`; Retry/Backoff in `_fetch_weather` |
| `src/services/notification_service.py` | MODIFY | Teilausfall-Hinweis (Präfix analog `catchup_prefix`) in E-Mail/Telegram |
| `tests/tdd/test_issue_1113_partial_outage_guard.py` | CREATE | RED-Tests: 5/6-Fall → kein Briefing; 1/6-Fall → Briefing mit Hinweis; Retry-Verhalten |

### Scope Assessment
- Files: 2 Source + 1 Test
- Estimated LoC: ~+80/-10 (unter 250-Limit)
- Risk Level: MEDIUM (Versand-Pfad; Renderer-Gate #811 falls Mail-Dateien berührt)

### Technical Approach
1. In `_send_trip_report_outcome`: `error_ratio = fehlerhafte/alle Segmente`; bei
   `error_ratio > 0.75` denselben Zweig wie Totalausfall nehmen (no_data_hint +
   Marker, return "no_weather"). Bei `0 < error_ratio <= 0.75` einen
   Hinweis-Präfix (Mechanik `catchup_prefix`) mit Liste der fehlenden Abschnitte
   in den Request geben.
2. In `_fetch_weather`: pro Segment bei Exception bis zu 2 Wiederholungen mit
   kurzem Backoff (Gesamtbudget des Scheduler-Laufs beachten); Injection-Seam
   (`provider=`-Parameter) für mock-freie Tests nutzen.
3. Nachliefer-Mechanik (#1012) bleibt unverändert — sie schließt mit der neuen
   Schwelle die Kette (Incident-Verlauf 07./08.07. wäre damit durchgehend korrekt).

### Erkenntnisse aus dem erweiterten Incident (07.07. Abend)
- open-meteo intermittierend down 07.07. 16:00 UTC – 08.07. 06:30 UTC (~14,5 h).
- Evening 07.07.: Totalausfall-Guard griff korrekt (Hinweis-Mail + Marker);
  7+ stündliche Nachlieferversuche scheiterten an anhaltendem 503.
- 08.07. 05:00: Evening-Marker verfiel per AC-7 („regulärer Slot übernimmt") —
  der reguläre Slot lieferte wegen Teilausfall (5/6) die kaputte Mail. Mit der
  >75-%-Schwelle bleibt AC-7 korrekt (Slot hätte Hinweis + frischen Marker erzeugt).
- Service-„Failed"-Meldungen 15:55–16:01 waren geordnete Deploy-Restarts
  (SIGTERM 143), kein Crash — nicht incident-relevant.
- Provider-Redundanz (brightsky/geosphere existieren, werden nicht genutzt) →
  bewusst ausgelagert in #1115.

### Open Questions
- Keine — PO-Entscheidung zur Schwelle (>75 %) liegt vor (2026-07-08); Rundungs-
  Semantik wird in den ACs festgeschrieben (5/6=83 % → zurückhalten; 3/4=75 % →
  senden mit Hinweis).

## Incident-Referenz
- Journal 05:00:11 UTC: 503 für Segmente 2–Ziel; „Failed to build trend" für alle
  Folge-Etappen. Briefing 05:00:14 versendet (email+telegram).
- `pending_briefings.json`: failed_segment_ids=[2,3,4,5,Ziel], attempts=1 (06:00-Lauf
  scheiterte erneut), Nachlieferung 06:23 UTC ok, Marker geleert.
