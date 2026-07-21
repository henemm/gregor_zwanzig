---
entity_id: issue_724_trip_name_save_error
type: module
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [frontend, trip-detail, ux, error-handling]
---

# Issue #724 — Trip-Name umbenennen: Fehler-Feedback bei fehlgeschlagenem Save

## Approval

- [x] Approved (PO, 2026-06-10)

## Purpose

Beim Inline-Umbenennen eines Trips (Stift-Icon im Trip-Header) erhält der Nutzer aktuell keine Rückmeldung, wenn der Speichern-Aufruf (`PUT /api/trips/{id}`) fehlschlägt — das Feld bleibt offen, sonst passiert sichtbar nichts. Diese Spec ergänzt eine sichtbare Fehlermeldung, damit fehlgeschlagenes Speichern nicht mit Erfolg verwechselt wird.

## Source

- **File:** `frontend/src/lib/components/trip-detail/TripHeader.svelte`
- **Identifier:** `makeNameSaveHandler()` (Z.35–46) und der `name-edit-row`-Markup-Block (Z.132–154)

## Dependencies

- `frontend/src/lib/api.js` — `api.put` wirft bei `!res.ok` ein `ApiError`-Objekt (`{ error: string; detail?: string }`).
- `frontend/src/lib/types.ts` — `interface ApiError`.
- Etabliertes Muster: `WeatherMetricsTab.svelte` (`saveError`-$state + `catch`), `SavePresetDialog.svelte` (`<div class="error" data-testid=...>`).

## Implementation Details

1. **Fehler-State einführen:** `let nameSaveError: string | null = $state(null);`
2. **`makeNameSaveHandler` um `catch` ergänzen:**
   - Vor dem `await`: `nameSaveError = null` (jeder neue Versuch startet sauber).
   - `catch (e: unknown)`: `nameSaveError = (e as { error?: string })?.error ?? 'Speichern fehlgeschlagen'`.
   - Im Erfolgsfall wie bisher: `onTripUpdate?.(...)` und `isEditingName = false`.
   - `finally`: `nameSaving = false` (unverändert).
   - **Wichtig:** Bei Fehler bleibt `isEditingName = true` (Feld offen, Eingabe erhalten) — `isEditingName = false` darf NUR im Erfolgszweig (nach dem `await`) stehen.
3. **Fehleranzeige im Markup:** innerhalb des `{#if isEditingName}`-Blocks, direkt unter der `name-edit-row`, ein `{#if nameSaveError}<div class="name-edit-error" data-testid="trip-name-save-error" role="alert">{nameSaveError}</div>{/if}`.
4. **State-Reset bei „Abbrechen" und beim Öffnen (Stift):** in beiden `onclick`-Handlern zusätzlich `nameSaveError = null`.
5. **Styling:** kleine `.name-edit-error`-Regel (rote/Warn-Farbe aus Tokens, `font-size: var(--g-text-sm)`), hoher Kontrast (Design-Leitprinzip), kein neues Token erfinden.

## Expected Behavior

- **Input:** Nutzer öffnet Inline-Edit, ändert den Namen, klickt „Umbenennen".
- **Output (Erfolg):** PUT 2xx → `onTripUpdate` feuert, Feld schließt, keine Fehlermeldung.
- **Output (Fehler):** PUT scheitert (Netzfehler/4xx/5xx) → Feld bleibt offen mit erhaltener Eingabe, sichtbare Fehlermeldung erscheint unter dem Feld.
- **Side effects:** keine Backend-/Persistenz-Änderung; rein clientseitiger UI-State.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer auf der Trip-Detail-Seite mit offenem Inline-Namens-Edit / When er „Umbenennen" klickt und der `PUT /api/trips/{id}`-Aufruf fehlschlägt (z. B. Netzwerkfehler oder HTTP 4xx/5xx) / Then bleibt das Eingabefeld geöffnet UND eine sichtbare Fehlermeldung (`data-testid="trip-name-save-error"`) erscheint mit einem nicht-leeren Text, der das Scheitern kommuniziert.
  - Test: Playwright-E2E gegen Staging als eingeloggter Nutzer; den PUT-Request via Route-Interception auf einen Fehlerstatus zwingen; assertieren dass das Edit-Feld (`trip-name-edit`) weiterhin sichtbar ist und `trip-name-save-error` sichtbar mit nicht-leerem Text gerendert wird.

- **AC-2:** Given ein erfolgreich gespeicherter Namens-Edit / When der `PUT`-Aufruf mit 2xx zurückkommt / Then schließt das Eingabefeld, der neue Name ist im Header sichtbar UND es wird KEINE Fehlermeldung angezeigt.
  - Test: Playwright-E2E gegen Staging; echten Namens-Save durchführen (regulärer Backend-Pfad); assertieren dass `trip-name-edit` verschwindet, der neue Name in `trip-detail-h1` erscheint und `trip-name-save-error` nicht im DOM/unsichtbar ist. Aufräumen: Namen zurücksetzen.

- **AC-3:** Given eine zuvor angezeigte Fehlermeldung nach fehlgeschlagenem Save / When der Nutzer „Umbenennen" erneut auslöst ODER „Abbrechen" klickt ODER den Edit über das Stift-Icon neu öffnet / Then ist die Fehlermeldung zurückgesetzt (nicht mehr sichtbar), bevor das Ergebnis des neuen Versuchs feststeht.
  - Test: Playwright-E2E gegen Staging; Fehlschlag provozieren (Meldung sichtbar), dann „Abbrechen" klicken und Edit erneut öffnen; assertieren dass `trip-name-save-error` nicht mehr sichtbar ist.

## Known Limitations

- Die Fehlermeldung zeigt den vom Backend gelieferten `ApiError.error`-Token bzw. einen generischen Fallback „Speichern fehlgeschlagen" — keine feldspezifische Validierungs-Aufschlüsselung (für diesen LOW-Bug nicht nötig).

## Changelog

- 2026-06-10 v1.0: Initiale Spec (Nebenbefund #714 F001, LOW) — Fehler-Feedback beim Inline-Trip-Namens-Save.
