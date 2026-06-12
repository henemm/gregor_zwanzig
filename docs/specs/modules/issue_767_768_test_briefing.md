---
entity_id: issue_767_768_test_briefing
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [test-briefing, frontend, scheduler, error-handling]
---

# Test-Briefing: Fehlermeldungen (#767) + Abend/Morgen-Auswahl & Etappen-Fallback (#768)

## Approval

- [x] Approved

## Purpose

Der „Test-Briefing senden"-Button wird robuster und flexibler: verständliche Fehlermeldungen
bei Serverfehlern (#767) sowie wählbares Abend-/Morgen-Briefing mit Fallback auf die nächste
kommende Etappe, wenn am regulären Zieldatum keine Etappe liegt (#768). Der reguläre Scheduler
bleibt unberührt.

## Source

- **File:** `frontend/src/routes/trips/[id]/+page.svelte` — `handleTestBriefing`, Auswahl-UI
- **File:** `src/services/trip_report_scheduler.py` — `send_test_report`, `_send_trip_report`, `_get_target_date`
- **File:** `api/routers/scheduler.py` — `send_test_trip_report` (Endpoint, `report_type` existiert bereits)
- **Identifier:** `handleTestBriefing`, `TripReportSchedulerService.send_test_report`

## Estimated Scope

- **LoC:** ~110 (Frontend ~50, Python ~55, Tests separat)
- **Files:** 3 (Frontend, Scheduler, Router) — Proxy unverändert
- **Effort:** medium

## Dependencies

- `Trip.get_future_stages(from_date)`, `Trip.get_stage_for_date(d)`, `Trip.numbered_stage_label(stage)`
- Formatter `format_email` (Betreff/Hinweiszeile)
- Settings (SMTP, mandantengetrennt via `with_user_profile(user_id)`)

## Acceptance Criteria

**AC-1 (#767 — handlungsleitende 5xx-Meldung):** Given der Test-Versand schlägt mit einem
HTTP-5xx-Status fehl (z.B. 500 aus dem Backend oder 502 aus dem Proxy), When das Frontend die
Antwort verarbeitet, Then zeigt es eine verständliche, handlungsleitende Meldung
(„Versand fehlgeschlagen — Serverfehler, bitte später erneut versuchen") statt der rohen
`detail`-Zeile oder einer `error`-Struktur ohne `detail`.

**AC-2 (#767 — qualifizierte 4xx-Meldung bleibt):** Given der Test-Versand schlägt mit einem
HTTP-422 (oder anderem 4xx mit aussagekräftigem `detail`) fehl, When das Frontend die Antwort
verarbeitet, Then zeigt es die qualifizierte Backend-`detail`-Meldung unverändert an
(z.B. „SMTP not configured for this user").

**AC-3 (#767 — Observability):** Given ein unerwarteter 5xx- oder Proxy-Fehler tritt auf, When
das Frontend ihn behandelt, Then wird der Fehler mit Statuscode und Rohtext via `console.error`
geloggt, damit echte Produktionsfehler nicht stumm verschwinden.

**AC-4 (#768 — Auswahl Morgen/Abend):** Given der Nutzer ist auf der Trip-Detailseite, When er
das Test-Briefing auslöst, Then kann er über ein kleines Auswahlmenü am Button zwischen
„Morgen" und „Abend" wählen, und die Auswahl wird als `report_type=morning|evening` an
`POST /api/trips/{id}/send` durchgereicht.

**AC-5 (#768 — Fallback auf nächste kommende Etappe):** Given für das reguläre Zieldatum
(Morgen=heute, Abend=morgen) existiert keine Etappe, When ein **Test**-Versand ausgelöst wird,
Then weicht der Test-Pfad auf die zeitlich nächstgelegene kommende Etappe (Datum ≥ heute) aus —
und falls alle Etappen in der Vergangenheit liegen, auf die chronologisch erste Etappe des
Trips — und erzeugt dafür ein vollwertiges Briefing, statt mit 422 abzubrechen.

**AC-6 (#768 — Kennzeichnung als Test/Vorschau):** Given ein Test-Briefing wird erzeugt, When
es versendet wird, Then trägt der Betreff einen `[TEST]`-Präfix und der Mailkopf eine
Hinweiszeile mit dem tatsächlich verwendeten Etappen-/Datumsbezug
(z.B. „Test-Vorschau für Etappe 1 am 12.06.2026"), damit kein Zweifel über den Bezugstag besteht.

**AC-7 (#768 — regulärer Scheduler unverändert):** Given der automatische Morgen-/Abend-Versand
läuft (`send_reports` / `send_reports_for_hour`), When kein Trip-Tag auf das Zieldatum fällt,
Then gibt es **keinen** Etappen-Fallback und **keine** `[TEST]`-Kennzeichnung — der Regelpfad
verhält sich exakt wie bisher (kein Versand außerhalb des Trip-Zeitraums).

**AC-8 (#768 — Mandantentrennung):** Given zwei verschiedene Nutzer mit eigenen Trips, When
jeder einen Test-Versand auslöst, Then arbeitet der Pfad durchgängig mit der echten `user_id`
aus dem Auth-Kontext (kein `default`-Fallback), und Nutzer A erhält niemals Daten/Versand von
Nutzer B.

## Non-Goals

- Keine Änderung am Proxy (`internal/handler/proxy.go`) — Query + Statuscode werden bereits korrekt durchgereicht.
- Keine Änderung am regulären Scheduler-Verhalten (siehe AC-7).
- Keine neuen Kanäle; Telegram-Versand des Test-Briefings bleibt wie bisher an die Briefing-Kanäle gekoppelt.

## Test Strategy

- **#767 (frontend):** Playwright-E2E gegen Staging — `page.route` fängt `POST /api/trips/*/send`
  ab und liefert 500 (→ generische Meldung), 422 mit `detail` (→ Backend-Meldung erhalten),
  und Proxy-Stil `{"error":"upstream unreachable"}` (→ generische Meldung, kein „undefined").
- **#768 backend:** echter Scheduler-Aufruf (mock-frei): Trip mit Etappe ausschließlich in der
  Zukunft → `send_test_report(trip, "morning")` liefert `True`, echte Mail ins Test-Postfach,
  IMAP-Prüfung auf `[TEST]`-Betreff + Hinweiszeile + korrekten Etappenbezug. Zweiter Nutzer
  zur Mandantentrennung. Regelpfad-Test: `send_reports` für ein Datum ohne Etappe sendet nichts.
- **#768 frontend:** Dropdown-Auswahl setzt `report_type` korrekt (E2E gegen Staging).
