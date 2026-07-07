# Context: #1059 — "Fortsetzen"-Button auf Trip-Detail-Seite ohne sichtbare Reaktion bei Fehlschlag

## Request Summary
Nutzer meldet: Auf der Desktop-Trip-Detail-Seite reagiert der "Fortsetzen"-Button (Pause aufheben) scheinbar nicht. Root Cause: `handlePauseClick()` → `sendStateUpdate()` in `+page.svelte` setzt bei einem fehlgeschlagenen `PATCH /api/trips/{id}/state` zwar `errorMsg`, aber dieser State wird nirgendwo im Template gerendert — der Fehlerfall ist für den Nutzer unsichtbar. Derselbe Handler wird auch für Archivieren/Reaktivieren genutzt, ist also vom selben Fix betroffen. `handleDeleteConfirm` hat dasselbe Problem mit demselben `errorMsg`-State.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/routes/trips/[id]/+page.svelte` | Z.46 `errorMsg`-State; Z.53–73 `sendStateUpdate` (Pause/Archiv); Z.106–118 `handleDeleteConfirm` (Delete); Z.186–192 Pause/Archiv-Buttons ohne `data-testid`; Z.227–230 **Vorbild-Pattern** `testBriefingStatus`/`testBriefingMessage` mit sichtbarem `<span data-testid="test-briefing-error">` direkt neben denselben Buttons |
| `frontend/e2e/trip-detail-actions.spec.ts` | Erwartet `data-testid="trip-detail-action-pause"` / `-archive` / `-status-badge`, die aktuell fehlen (**strukturell größerer Test-Drift, ausgelagert nach Folge-Issue #1060** — nicht Teil dieses Fixes) |
| `internal/handler/trip.go:263` / `internal/router/router.go:135` | Backend-Endpoint `PATCH /api/trips/{id}/state` korrekt implementiert inkl. User-Isolation — kein Backend-Fix nötig |

## Existing Patterns
- **In derselben Datei bereits vorhanden:** `testBriefingStatus`/`testBriefingMessage` (Z.48–49, 227–230) — Status-State + sichtbarer `<span data-testid="…-error" style="color: var(--g-error, #c62828)">`. Dieses Muster ist die naheliegende Vorlage für die Pause/Archiv/Delete-Fehleranzeige, statt ein neues Konzept einzuführen.
- **Verwandtes, bereits behobenes Muster:** Issue #724 (`TripHeader.svelte`) — dort wurde exakt derselbe Fehlertyp (State gesetzt, aber nicht gerendert) durch lokalen Fehler-State + `{#if xError}`-Anzeige direkt am betroffenen Element behoben. Gleiches Rezept hier anwendbar.

## Dependencies
- Upstream: `fetch(...)` auf `/api/trips/{id}/state` und `/api/trips/{id}` (DELETE) — beide unverändert.
- Downstream: keine. Rein lokale UX-Ergänzung in `+page.svelte`, kein Schema-, Backend- oder Mandanten-Bezug.

## Existing Specs
- `docs/specs/modules/issue_302_trip_detail_page.md` — Trip-Detail-Seite, Danger-Zone-Aktionen (Pause/Archiv/Delete).

## Scope Assessment
- Files: 1 (`frontend/src/routes/trips/[id]/+page.svelte`), ggf. 1 Test-Datei ergänzt (neuer E2E- oder Component-Test für den Fehlerfall)
- Estimated LoC: +10/-0 (Fehleranzeige-Markup + ggf. `aria-live`)
- Risk Level: LOW — reine Frontend-UX-Ergänzung, kein bestehendes Verhalten wird geändert (Erfolgsfall bleibt identisch)

## Technical Approach
Sichtbare Fehleranzeige für `errorMsg` direkt bei der Breadcrumb-Actions-Leiste ergänzen (analog zum bereits vorhandenen `test-briefing-error`-Pattern in derselben Datei): `{#if errorMsg}<span data-testid="trip-detail-action-error" style="...">{errorMsg}</span>{/if}`. Zusätzlich `errorMsg` in eine nutzerverständliche Meldung übersetzen (aktuell technischer String `PATCH /state failed: 500` — sollte durch eine handlungsleitende Meldung ersetzt werden, analog Test-Briefing-Pattern Z.153–162: 5xx → generische Meldung, sonst Detail wenn vorhanden). `data-testid` für Pause-/Archiv-Button NICHT in diesem Fix ergänzen (gehört zu #1060, größerer Scope).

## Open Questions
- [ ] Keine — Scope ist eng und klar (Fehleranzeige-Ergänzung, kein Backend-Change, kein Redesign).
