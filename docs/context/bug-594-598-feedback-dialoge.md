# Context: bug-594-598-feedback-dialoge

## Request Summary
Zwei Frontend-Bugs: #594 — „Test-Briefing senden" auf Trip-Detailseite zeigt nach Klick kein sichtbares Feedback. #598 — „Archivieren" in der Trips-Liste führt sofort aus ohne Bestätigungs-Dialog (inkonsistent zu „Löschen").

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | #594: Button + State + Inline-Meldung |
| `frontend/src/routes/trips/+page.svelte` | #598: handlePrimaryAction + ConfirmDialog für Delete |
| `frontend/src/lib/components/molecules/ConfirmDialog.svelte` | Bestehende Molekül-Komponente für Dialoge |
| `frontend/src/lib/components/molecules/TestReportDialog.svelte` | Referenz: Dialog-Muster für Test-Briefings |
| `frontend/src/lib/components/mobile/Toast.svelte` | Mobile-Toast (nur Mobile, kein Desktop-Toast) |

## Existing Patterns

- **ConfirmDialog**: `open={target !== null}`, `onConfirm`, `onCancel`, `onOpenChange` — Pattern aus delete-flow
- **Delete-Flow**: `deleteTarget` State → ConfirmDialog → `handleDelete` ausführen
- **Inline-Feedback**: `testBriefingMsg` State → `{#if testBriefingMsg}` → `<p class="briefing-msg">` (zu unauffällig)

## Bug-Details

### #594 — Test-Briefing ohne Feedback (TripHeader.svelte)
- `handleTestBriefing()` setzt `testBriefingMsg` auf Erfolg/Fehler-Text
- `<p class="briefing-msg">` mit `color: var(--g-ink-muted)` — WCAG-Verstoß für Content (2.85:1) und kaum wahrnehmbar
- Fix: `testBriefingKind` State hinzufügen, `briefing-msg` je nach kind grün/rot stylen

### #598 — Archivieren ohne Dialog (trips/+page.svelte)
- `handlePrimaryAction`: für paused/archived Trips → sofort PATCH ohne Confirmation
- Delete hat: `deleteTarget` State → ConfirmDialog → `handleDelete`
- Fix: `archiveTarget` State + ConfirmDialog hinzufügen, PATCH-Logic aus handlePrimaryAction auslagern

## Dependencies
- Upstream: `/api/trips/{id}/state` PATCH (Go-Backend, vorhanden)
- Downstream: Trips-Liste, Trip-Detail-Header

## Risks & Considerations
- Kein Backend-Eingriff nötig
- `handlePrimaryAction` auch via Mobile Bottom-Sheet aufgerufen — Archive-Pfad dort auch prüfen
- `Dearchivieren` auch Confirmation? Issue #598 erwähnt nur Archivieren — Dearchivieren ist reversibel, kein Dialog nötig
