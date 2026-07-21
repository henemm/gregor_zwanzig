---
entity_id: issue_1059_trip_resume_error_feedback
type: module
created: 2026-07-07
updated: 2026-07-07
status: draft
version: "1.0"
tags: [frontend, svelte, trip-detail, error-handling, issue-1059]
---

# Issue #1059 — "Fortsetzen"-Button ohne sichtbare Reaktion bei fehlgeschlagenem Status-Update

## Approval

- [ ] Approved

## Purpose

Behebt einen stummen Fehlerfall auf der Desktop-Trip-Detail-Seite: Schlägt die PATCH-Anfrage
hinter „Pausieren"/„Fortsetzen" oder „Archivieren"/„Reaktivieren" fehl, wird zwar intern ein
Fehler-State (`errorMsg`) gesetzt, aber nirgendwo gerendert — der Button wirkt für den Nutzer,
als hätte er gar nicht reagiert. Dieselbe Lücke betrifft den Löschen-Bestätigungsdialog
(`handleDeleteConfirm`), der denselben `errorMsg`-State nutzt. Der Fix ergänzt eine sichtbare,
nutzerverständliche Fehleranzeige nach dem bereits im selben File vorhandenen
`testBriefingMessage`-Muster.

## Source

- **File:** `frontend/src/routes/trips/[id]/+page.svelte`
- **Identifier:** `errorMsg` (State, Z.46), `sendStateUpdate()` (Z.53–73, Pause/Archiv),
  `handleDeleteConfirm()` (Z.106–118, Delete)

> Frontend / User-UI — SvelteKit-Route `frontend/src/routes/trips/[id]/+page.svelte`,
> produktive Oberfläche. Kein Go-API- (`internal/handler/trip.go`) und kein Python-Backend-Change
> nötig — der Endpoint `PATCH /api/trips/{id}/state` (`internal/handler/trip.go:263`) ist bereits
> korrekt implementiert.

## Estimated Scope

- **LoC:** ~20 (Fehleranzeige-Markup ~5, Fehlermeldungs-Übersetzung in `sendStateUpdate`/
  `handleDeleteConfirm` ~15)
- **Files:** 1 (`frontend/src/routes/trips/[id]/+page.svelte`) + 1 neue/erweiterte
  E2E-Test-Datei (`frontend/e2e/`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/routes/trips/[id]/+page.svelte` — `testBriefingStatus`/`testBriefingMessage` (Z.48–49, 227–231) | Internes Vorbild (bestehend, unverändert) | Liefert das Muster für sichtbaren Fehler-Span + 5xx/4xx-Übersetzung, das für `errorMsg` übernommen wird |
| `PATCH /api/trips/{id}/state` (`internal/handler/trip.go:263`, `internal/router/router.go:135`) | Backend-Endpoint (unverändert) | Löst die PATCH-Fehler aus, die jetzt sichtbar gemacht werden |
| `DELETE /api/trips/{id}` | Backend-Endpoint (unverändert) | Löst die DELETE-Fehler aus, die `handleDeleteConfirm` behandelt |
| `docs/specs/modules/issue_302_trip_detail_page.md` | Spec (vorhanden) | Beschreibt Breadcrumb-Actions-Leiste, in der die neue Fehleranzeige platziert wird |

## Implementation Details

```
// 1) sendStateUpdate() — 4xx/5xx-Übersetzung analog handleTestBriefing (Z.144–163):
async function sendStateUpdate(paused, archived) {
  errorMsg = null;          // NEU: alten Fehler beim Start eines neuen Versuchs zurücksetzen
  isLoading = true;
  try {
    const res = await fetch(`/api/trips/${trip.id}/state`, { method: 'PATCH', ... });
    if (!res.ok) {
      let detail;
      try { const body = await res.json(); detail = body?.detail; } catch { /* kein JSON-Body */ }
      if (res.status >= 500) {
        console.error(`Status-Update fehlgeschlagen: HTTP ${res.status}`, detail);
        throw new Error('Aktion fehlgeschlagen — Serverfehler, bitte später erneut versuchen.');
      } else if (detail) {
        throw new Error(detail);
      } else {
        throw new Error('Aktion fehlgeschlagen, bitte später erneut versuchen.');
      }
    }
    const updated = await res.json();
    errorMsg = null;
    trip = updated;
  } catch (e) {
    errorMsg = e instanceof Error ? e.message : String(e);
  } finally {
    isLoading = false;
  }
}

// 2) handleDeleteConfirm() — identisches Übersetzungsmuster für DELETE-Fehler.

// 3) Template — sichtbare Fehleranzeige in .breadcrumb-actions, neben Pause/Archiv-Buttons:
{#if errorMsg}
  <span data-testid="trip-detail-action-error" style="font-size: 12px; color: var(--g-error, #c62828);">
    {errorMsg}
  </span>
{/if}
```

Kein `data-testid` für die Pause-/Archiv-Buttons selbst (Scope von Folge-Issue #1060).

## Expected Behavior

- **Input:** Nutzer klickt „Pausieren"/„Fortsetzen", „Archivieren"/„Reaktivieren" oder bestätigt
  den Löschen-Dialog; die zugehörige PATCH-/DELETE-Anfrage schlägt fehl (5xx, 4xx mit `detail`,
  4xx ohne `detail`, oder Netzwerkfehler).
- **Output:** Ein sichtbarer `<span data-testid="trip-detail-action-error">` erscheint direkt in
  der Breadcrumb-Actions-Leiste mit einer nutzerverständlichen Meldung (5xx → generischer
  Serverfehler-Hinweis, 4xx mit `detail` → `detail`-Text, sonst generischer Fallback).
- **Side effects:** Bei Erfolg eines PATCH/DELETE wird `errorMsg` auf `null` gesetzt (Anzeige
  verschwindet). Bei Start eines neuen Versuchs wird ein zuvor angezeigter Fehler ebenfalls
  sofort zurückgesetzt, statt bis zum Ergebnis des neuen Versuchs stehen zu bleiben.

## Acceptance Criteria

- **AC-1:** Given der Nutzer ist auf der Trip-Detail-Seite eines pausierten Trips / When er auf
  „Fortsetzen" klickt und die PATCH-Anfrage an `/api/trips/{id}/state` mit HTTP 500 fehlschlägt /
  Then erscheint sichtbar im DOM ein Element mit `data-testid="trip-detail-action-error"`, das
  eine handlungsleitende Serverfehler-Meldung zeigt (nicht der rohe String
  `PATCH /state failed: 500`).
  - Test: Playwright-E2E gegen Staging — `page.route()` fängt `PATCH **/api/trips/*/state` ab und
    liefert `{status: 500}`; Klick auf den „Fortsetzen"-Button; `expect(page.getByTestId('trip-detail-action-error')).toBeVisible()` und Text matcht `/Serverfehler|später erneut/i`.

- **AC-2:** Given der Nutzer ist auf der Trip-Detail-Seite eines aktiven Trips / When er auf
  „Archivieren" klickt, den Bestätigungsdialog bestätigt und die PATCH-Anfrage mit HTTP 422 und
  Body `{"detail":"Trip has active alerts"}` fehlschlägt / Then erscheint dieselbe
  Fehleranzeige (`trip-detail-action-error`) mit dem Text „Trip has active alerts".
  - Test: Playwright-E2E gegen Staging — `page.route()` liefert 422 mit `detail` für
    `PATCH **/api/trips/*/state` nach Klick auf „Archivieren" + Dialog-Bestätigung
    (`trip-detail-archive-confirm-yes`); `expect(...).toHaveText('Trip has active alerts')`.

- **AC-3:** Given der Nutzer klickt „Fortsetzen" und die PATCH-Anfrage antwortet mit HTTP 200 und
  einem aktualisierten Trip-Objekt / When die Antwort verarbeitet wird / Then bleibt
  `trip-detail-action-error` unsichtbar/nicht im DOM, und der sichtbare Status-Text wechselt
  (z.B. Button-Beschriftung von „Fortsetzen" zu „Pausieren", da der Trip jetzt aktiv ist) — der
  Erfolgsfall ist unverändert gegenüber dem Verhalten vor diesem Fix.
  - Test: Playwright-E2E gegen Staging ohne Route-Interception (echte Erfolgsantwort); Klick auf
    „Fortsetzen"; `expect(page.getByTestId('trip-detail-action-error')).not.toBeVisible()` und
    `expect(page.getByRole('button', { name: 'Pausieren' })).toBeVisible()`.

- **AC-4:** Given eine vorherige Aktion ist mit sichtbarer Fehlermeldung fehlgeschlagen (wie in
  AC-1) / When der Nutzer denselben oder einen anderen Aktions-Button erneut klickt und diesmal
  die PATCH-Anfrage erfolgreich antwortet / Then verschwindet `trip-detail-action-error` wieder
  aus dem DOM, sobald der erfolgreiche Response verarbeitet wurde — keine veraltete Fehlermeldung
  bleibt neben einem inzwischen erfolgreichen Zustand sichtbar.
  - Test: Playwright-E2E gegen Staging — erst `stubState(500)` + Klick (Fehler sichtbar machen),
    dann `page.unroute()` (echte Erfolgsantwort) + erneuter Klick;
    `expect(page.getByTestId('trip-detail-action-error')).not.toBeVisible({ timeout: 8000 })`.

## Known Limitations

- Die Fehleranzeige hat — anders als das `testBriefingMessage`-Vorbild — **keinen** automatischen
  4-Sekunden-Ausblend-Timer; sie bleibt stehen, bis der nächste PATCH/DELETE-Versuch erfolgreich
  ist (AC-4) oder die Seite neu geladen wird. Das ist bewusst so gewählt, da Pause/Archiv/Delete
  seltenere, folgenreichere Aktionen sind als das häufig wiederholte Test-Briefing.
- Die Test-Selektor-Drift in `frontend/e2e/trip-detail-actions.spec.ts`
  (erwartet `data-testid="trip-detail-action-pause"`/`-archive`/`-status-badge`, die auf den
  eigentlichen Pause-/Archiv-Buttons aktuell fehlen) ist **NICHT** Teil dieses Fixes — das ist
  strukturell größerer Scope und wurde nach Folge-Issue #1060 ausgelagert.
- Kein Backend-Change: der Endpoint `PATCH /api/trips/{id}/state` ist bereits korrekt
  implementiert und mandantengetrennt; dieser Fix ist rein UX-seitig.
- **Delete-Fehlerfall bewusst NICHT abgedeckt:** `handleDeleteClick()` und der zugehörige
  Löschen-Bestätigungsdialog (`trip-detail-delete-confirm-dialog`) sind im aktuellen Markup an
  keinen sichtbaren Button gebunden — es gibt derzeit keinen erreichbaren Weg, einen Trip von der
  Detailseite aus zu löschen. Das ist ein eigenständiger, während der TDD-RED-Vorbereitung
  entdeckter Bug (Folge-Issue #1064), nicht Teil dieses Fixes. Ein ursprünglich geplantes AC-5
  für den Delete-Fehlerfall wurde deshalb aus dieser Spec entfernt — es wäre nicht testbar
  gewesen, solange der Auslöser-Button fehlt. `handleDeleteConfirm()` teilt sich zwar denselben
  `errorMsg`-Mechanismus und profitiert vom selben Fix, sobald #1064 behoben ist, aber das ist
  hier nicht verifizierbar.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kleiner, lokaler UX-Fix innerhalb einer einzelnen bestehenden Datei, der ein
  bereits etabliertes Muster (sichtbarer Fehler-Span, Fehlermeldungs-Übersetzung) aus derselben
  Datei wiederverwendet. Es wird kein neues Konzept, keine neue Abhängigkeit und keine
  Architekturentscheidung eingeführt.

## Changelog

- 2026-07-07: Initial spec created (Issue #1059).
- 2026-07-07: AC-5 (Delete-Fehlerfall) entfernt — Delete-Button ist während TDD-RED-Vorbereitung
  als toter Code (kein Auslöser im Markup) entdeckt worden, siehe Folge-Issue #1064. Spec bleibt
  mit AC-1 bis AC-4 sonst unverändert.
