# Context: Test-Briefing #767 + #768

## Request Summary
Zwei zusammenhängende Verbesserungen am „Test-Briefing senden"-Button:
- **#767 (Bug):** Bei 5xx/Proxy-Fehlern zeigt das Frontend nur rohe „Internal Server Error"/„Fehler beim Senden" statt einer handlungsleitenden Meldung.
- **#768 (Feature):** Nutzer soll Abend/Morgen wählen können und auch ohne aktive Etappe (Trip startet erst in Zukunft) ein Test-Briefing erhalten (Fallback auf nächste kommende Etappe).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/routes/trips/[id]/+page.svelte` | `handleTestBriefing` (Z.115) — Fehlerbehandlung (#767) + Auswahl-UI (#768) |
| `api/routers/scheduler.py` | `send_test_trip_report` (Z.457) — Endpoint, `report_type`-Query existiert bereits |
| `src/services/trip_report_scheduler.py` | `send_test_report` (Z.330) → `_send_trip_report` (Z.351), `_get_target_date` (Z.286), `_convert_trip_to_segments` (Z.622) — Fallback-Etappe (#768) |
| `internal/handler/proxy.go` | `SendTripReportProxyHandler` (Z.266) — reicht Query + Statuscode durch (kein Eingriff nötig) |
| `src/app/trip.py` | `get_future_stages(from_date)` (Z.233), `get_stage_for_date` (Z.226), `numbered_stage_label` (Z.240) — Etappen-Auswahl + Kennzeichnung |

## Existing Patterns
- Backend liefert bei 422 qualifizierte `detail`-Meldung; das soll erhalten bleiben (#767 AC-2).
- Proxy gibt bei eigenem Fehler `{"error":...}` (KEIN `detail`) → Frontend muss das tolerieren.
- `report_type`-Query wird vom Endpoint und Proxy bereits unterstützt — Frontend hängt ihn heute nur nicht an.
- Scheduler trennt Test-Pfad (`send_test_report`) sauber vom Regelversand (`send_reports*`) — Fallback darf NUR den Test-Pfad berühren (#768 AC-4).

## Dependencies
- Upstream: Trip-Model (`stages`, Datumsangaben), Settings (SMTP), Formatter (`format_email`).
- Downstream: E-Mail/Telegram-Versand; Frontend-UI.

## Existing Specs
- `docs/specs/modules/issue_695_test_briefing_send.md` — Ursprungs-Spec des Test-Versand-Endpoints.

## Risks & Considerations
- **#768 AC-4 (kritisch):** Fallback NUR im manuellen Test-Pfad — der automatische Scheduler darf außerhalb des Trip-Zeitraums NIEMALS echte Briefings versenden.
- **Mandantentrennung (AC-5):** echte `user_id` durchreichen, kein `default`-Fallback; mit zwei Nutzern testen.
- **Kennzeichnung (AC-3):** Test-Briefing muss als Test/Vorschau erkennbar sein inkl. tatsächlich verwendetem Etappen-/Datumsbezug, sonst Verwechslungsgefahr.
- E-Mail-E2E unter SMTP-Rate-Limit am geteilten Loopback-Postfach (siehe frühere Lehren).
