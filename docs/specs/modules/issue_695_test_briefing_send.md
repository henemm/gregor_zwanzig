# Spec: Test-Briefing senden (Issue #695)

## Überblick

Der Button „Test-Briefing senden" auf der Trip-Detailseite soll genau eine E-Mail für den aktuellen Trip an die konfigurierten Empfänger auslösen — unabhängig von Uhrzeit und Zeitplan.

**Problem:**
1. Der Button rief bisher `/api/scheduler/trip-reports?hour=18` auf (globaler Scheduler für Stunde 18 — sendet bei den meisten Trips gar nichts, weil die Bedingungen nicht passen).
2. Kein Feedback: keine Ladeanimation, keine Erfolgsmeldung, keine Fehlermeldung.

**Lösung:**
- Neuer trip-spezifischer Backend-Endpunkt `POST /api/scheduler/trips/{trip_id}/send`
- Neuer Go-Proxy-Handler für `/api/trips/{id}/send`
- Frontend ruft den richtigen Endpunkt auf und zeigt Feedback

## Acceptance Criteria

**AC-1:** Given ich bin auf der Detailseite eines Trips und klicke „Test-Briefing senden", When der Request läuft, Then zeigt der Button-Bereich einen Ladeindikator (Button deaktiviert oder Textwechsel zu „Wird gesendet…").

**AC-2:** Given der Versand war erfolgreich, When die Antwort zurückkommt, Then erscheint neben/unter dem Button eine Erfolgsmeldung (z. B. „Test-Briefing gesendet!") für mindestens 3 Sekunden.

**AC-3:** Given der Versand schlug fehl (Server-Fehler oder Netzwerkproblem), When die Antwort zurückkommt, Then erscheint eine Fehlermeldung (z. B. „Fehler beim Senden") statt der Erfolgsmeldung.

**AC-4:** Given ich klicke „Test-Briefing senden", When der neue Endpunkt `POST /api/trips/{trip_id}/send` aufgerufen wird, Then sendet der Backend-Handler genau das E-Mail-Briefing für diesen Trip (report_type=evening als Standard) an die konfigurierten Empfänger.

**AC-5:** Given der Trip existiert nicht oder gehört einem anderen Nutzer, When `POST /api/trips/{trip_id}/send` aufgerufen wird, Then antwortet das Backend mit HTTP 404.

**AC-6:** Given SMTP nicht konfiguriert ist, When `POST /api/trips/{trip_id}/send` aufgerufen wird, Then antwortet das Backend mit HTTP 422 und klarer Fehlermeldung.

## Technische Umsetzung

### Python-Backend (`api/routers/scheduler.py`)

Neuer Endpunkt:
```
POST /api/scheduler/trips/{trip_id}/send?user_id=&report_type=evening
```
- Lädt Trip via `load_all_trips(user_id)`, wirft 404 wenn nicht gefunden
- Prüft `can_send_email()`, wirft 422 wenn nicht konfiguriert
- Ruft `TripReportSchedulerService.send_test_report(trip, report_type)` auf
- Gibt `{"status": "ok", "trip_id": trip_id, "report_type": report_type}` zurück

### Go-Backend (`internal/handler/proxy.go`, `cmd/server/main.go`)

Neuer Proxy-Handler `SendTripReportProxyHandler(pythonURL)`:
- Route: `POST /api/trips/{id}/send`
- Liest Trip-ID aus `chi.URLParam(r, "id")`
- Hängt `user_id` aus Auth-Kontext an
- Proxied zu `/api/scheduler/trips/{id}/send?user_id=...&report_type=evening`

### Frontend (`frontend/src/routes/trips/[id]/+page.svelte`)

Funktion `handleTestBriefing()` ersetzen:
- `testBriefingLoading = $state(false)`
- `testBriefingMsg = $state<string | null>(null)` (null = kein Status, "ok" = Erfolg, "error" = Fehler)
- Button zeigt „Wird gesendet…" wenn loading, sonst „Test-Briefing senden"
- Button disabled wenn loading
- Nach Erfolg: Meldung 4 Sekunden anzeigen, dann reset
- Nach Fehler: Fehlermeldung anzeigen, dann reset

## Abgrenzung

- Kein Morning/Evening-Schalter im UI — Backend-Default `report_type=evening` reicht für den Test
- Keine neuen Konfigurationsoptionen
- Scope: Trip-Detailseite (`/trips/[id]`) — nicht Startseite, nicht Compare

## Changelog

- 2026-06-10: Erstellt (Issue #695)
