# Fix #1012 — Kein Briefing-Versand bei komplettem Wetterdaten-Ausfall

## Analysis

### Type
Bug (Issue #1012)

### Symptom (2026-07-05, 05:00 UTC, Produktion)
Open-Meteo 503 („service is overloaded") für ALLE Segmente + beide Fallback-Modelle → Morning-Briefing (henning, Trip 74de939c) wurde trotzdem mit komplett leeren Wetterdaten versendet (E-Mail + Telegram). Monitoring zeigte „ok".

### Root Causes (bewiesen)
1. **Guard greift nie:** `src/services/trip_report_scheduler.py:523` prüft `if not segment_weather` — `_fetch_weather()` (Z.830-882) liefert bei Provider-Fehlern aber NIE eine leere Liste, sondern pro Segment einen `has_error=True`-Platzhalter (WEATHER-04 Fail-Soft). Einzige has_error-Auswertung: Z.762, NACH dem Versand, nur SMS-only-Zusatzmail.
2. **Job-Zählung falsch:** `send_reports_for_hour` (Z.203-248) zählt jeden Non-Exception-Call als `sent` — auch „no_weather". `/api/scheduler/trip-reports` meldet dadurch nie `partial`.
3. **Go-Monitoring blind:** `internal/scheduler/scheduler.go` `recordRun`/`triggerEndpointForUser` (Z.183-217) werten nur den HTTP-Statuscode aus, nie den JSON-Body → `last_run=ok` trotz Fehlversand; externes Monitoring konnte nichts sehen.

### Wichtige Vorentscheidung: KEIN Sleep-Retry
Der Provider hat bereits pro Request 5× Backoff (2–60s) + 5-Modell-Fallback-Kette (`providers/openmeteo.py:94-98`). Fällt die GESAMTE Kette, ist es ein anhaltender Ausfall — ein zusätzliches Sleep-Retry in der synchronen Trip-Schleife würde die Job-Laufzeit bei echtem Ausfall über alle fälligen User vervielfachen und nichts retten. Echtes Nachholen (Pending-Marker + Catch-up beim nächsten Tick) ist eigener Scope → Folge-Issue.

### On-Demand-Pfad (#1007) profitiert automatisch
`send_on_demand_report` nutzt denselben `_send_trip_report_outcome`; `trip_command_processor.py:193-210` hat für `outcome=="no_weather"` bereits den fertigen Text („Wetterdaten aktuell nicht verfügbar…"). Guard-Fix ⇒ korrektes Verhalten ohne Zusatzarbeit.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/trip_report_scheduler.py | MODIFY | All-Failed-Guard (Z.523), Hinweis-Versand statt leerem Briefing, no_weather→failed-Zählung |
| internal/scheduler/scheduler.go | MODIFY | recordRun wertet JSON-Body aus (failed>0 → last_run error) |
| tests/tdd/test_issue_1012_no_data_guard.py | CREATE | TDD-Tests (Fake-Provider-Seam via bestehendem provider-Injektionsparameter, analog Demo-Mode #483 — Substitution externer Abhängigkeit, kein Mock) |

### Scope Assessment
- Files: 3 (+ evtl. Go-Test)
- Estimated LoC: ~120–190 (Python 90–140 + Go 30–50)
- Risk Level: MEDIUM (Sendepfad-Logik + Go-Rebuild; Teilausfall-Verhalten darf nicht regressieren)

### Technical Approach
1. **Guard:** `if not segment_weather or all(s.has_error for s in segment_weather): → outcome "no_weather"` (kein Briefing, kein briefing_log-Eintrag).
2. **Hinweis-Nachricht (regulärer Pfad):** kurze kanalübergreifende Info über die konfigurierten Kanäle des Trips („Wetterdienst aktuell nicht erreichbar — das Briefing entfällt; nächster Versuch zum nächsten regulären Termin"). Vorlage: `_send_service_error_email`/`build_service_error_email_html` (Z.762-767, 1266-1287) generalisieren; Kanal-Blöcke Z.705-741 als Muster.
3. **Zählung:** `send_reports_for_hour` wertet Outcome aus; „no_weather" → failed. Router liefert dadurch automatisch `partial`.
4. **Go-Observability:** `triggerEndpointForUser` parst den JSON-Body; `failed>0` (oder `status=partial`) → recordRun(error) → `/api/scheduler/status` zeigt last_run error → externes Monitoring schlägt an.
5. **On-Demand:** kein Retry, sofortige „nicht verfügbar"-Antwort (existiert bereits).

### Dependencies
- Provider-Retry-Kette (openmeteo.py) bleibt unverändert — sie IST der Retry.
- `/api/scheduler/status`-Kontrakt (externes Monitoring check-gregor20.sh liest ihn).
- Folge-Issue (neu anzulegen): Catch-up für verpasste Briefing-Slots.

### Open Questions
- keine — Design-Entscheidungen oben (kein Sleep-Retry, Hinweis statt Leer-Briefing, Go-Teil im Scope) sind PO-relevant und stehen in den ACs zur Freigabe.
