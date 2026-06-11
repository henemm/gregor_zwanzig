# Context: #724 — Trip-Name umbenennen: kein Fehler-Feedback wenn Save scheitert

## Request Summary
`makeNameSaveHandler` in `TripHeader.svelte` hat kein `catch`: schlägt `PUT /api/trips/{id}` fehl, bleibt das Edit-Feld offen und `nameSaving` wird via `finally` zurückgesetzt — aber der Nutzer bekommt keine Fehlermeldung. Nebenbefund aus #714 (Adversary F001, LOW). Fix: lokales Fehler-`$state`, im `catch` setzen, unter dem Eingabefeld anzeigen, bei erneutem Versuch zurücksetzen.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Z.35–46 `makeNameSaveHandler` (kein catch, keine Fehleranzeige); Z.132–154 `name-edit-row` Markup (Input + Umbenennen/Abbrechen); Z.125 Toggle öffnet Edit |
| `frontend/src/lib/api.js` | `request()` wirft bei `!res.ok` ein `ApiError`-Objekt (`{ error, detail? }`) — also im `catch` greifbar |
| `frontend/src/lib/types.ts` | `interface ApiError { error: string; detail?: string }` |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | **Vorbild-Muster:** `let saveError: string\|null = $state(null)`; catch → `saveError = (e as {error?:string})?.error ?? 'Speichern fehlgeschlagen'`; Markup `{#if saveError}` |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | Weiteres Vorbild: `<div class="error" data-testid="save-preset-error">{error}</div>`, Reset `error = null` vor jedem Versuch |

## Existing Patterns
- **Fehler-State pro Komponente:** `let xError: string | null = $state(null)`, vor try auf `null`, im `catch` aus `ApiError.error` befüllen mit Fallback-Text.
- **Anzeige:** `{#if xError}<div class="error" data-testid="...">{xError}</div>{/if}` direkt beim betroffenen Eingabe-Block.
- **api.* wirft** strukturiertes `ApiError` (kein Boolean-Return) → `try/catch` ist der korrekte Mechanismus.

## Dependencies
- Upstream: `api.put` (wirft ApiError), `onTripUpdate`-Callback (nur bei Erfolg auslösen).
- Downstream: keine — rein lokale UX-Rückmeldung in TripHeader. Kein Backend-Change, kein Schema, keine Mandanten-Relevanz.

## Existing Specs
- `docs/specs/modules/issue_714_trip_ui_polish.md` — #713 Stift-Toggle (machte den Save-Handler über den Toggle sichtbarer; Bug bestand schon vorher).
- `docs/specs/modules/issue_302_trip_detail_page.md` — Trip-Detail-Header AC-6 Inline-Name-Edit.

## Risks & Considerations
- **Severity LOW**, kein Datenverlust (Backend macht RMW-Merge). Reine UX-Lücke.
- Bei Erfolg: Feld schließen (`isEditingName = false`) + Fehler-State leeren. Bei Fehler: Feld OFFEN lassen + Meldung zeigen, damit der Nutzer den Namen nicht neu tippen muss.
- Fehler-State zurücksetzen: vor jedem neuen Save-Versuch, beim Öffnen des Edit (Stift) und bei „Abbrechen".
- Frontend-only → Verifikation via Playwright gegen Staging (E2E muss einen fehlschlagenden PUT provozieren, z.B. via Route-Interception/Offline, um die Meldung zu beobachten — Verhaltensnachweis, kein DOM-String-Check).
- TripHeader wurde gerade von #714 (`bf818b6a`) geändert — auf aktuellem Stand aufsetzen (Worktree bereits ge-fast-forwarded).
