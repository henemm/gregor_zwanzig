---
entity_id: bug_691_autosave_trip_new
type: module
created: 2026-06-10
updated: 2026-06-10
status: completed
version: "1.0"
tags: [frontend, trip-new, autosave, ux]
---

# Bug #691 — Trip-New Auto-Save bei Navigation weg

## Approval

- [x] Approved (2026-06-10)

## Purpose

Wenn ein Nutzer einen neuen Trip im `/trips/new`-Wizard anlegt und während der Erstellung
auf einen Link zu einer anderen Seite klickt (z.B. „im Account einrichten" im Zeitplan-Tab),
wird der komplette Trip-State verworfen — der Trip existiert nicht. Der Wizard speichert
den Trip ausschließlich beim expliziten Klick auf den Speichern-Button, ohne jede
Warnung oder Auto-Save beim Wegnavigieren.

**Fix:** SvelteKit `beforeNavigate`-Hook: wenn alle Pflicht-Tabs ausgefüllt sind (`ready === true`),
wird der Trip vor der Navigation automatisch gespeichert. Der Nutzer landet danach
am ursprünglich geklickten Ziel. Der Speichern-Button zeigt nach erfolgreichem Speichern
„Trip gespeichert" statt „Trip speichern".

## Source

- **File:** `frontend/src/lib/components/trip-new/TripNewEditor.svelte`
- **Identifier:** `beforeNavigate`, `makeSaveHandler`, Save-Button-Labels

## Estimated Scope

- **LoC:** ~30
- **Files:** 1 (`TripNewEditor.svelte`)
- **Effort:** small

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$app/navigation.beforeNavigate` | Runtime | Navigations-Interception (SvelteKit built-in) |
| `api.post('/api/trips', ...)` | API | Trip erstellen (bereits vorhanden) |
| `buildCreateTripPayload` | Logic | Payload-Builder (bereits vorhanden) |
| `ready` | State | Gate: `canSave(done)` → nur wenn Zeitplan-Tab besucht |

## Acceptance Criteria

**AC-1:** Given der Nutzer hat alle Pflicht-Tabs durchlaufen (`ready === true`) und klickt auf
einen internen Link (z.B. „im Account einrichten"),
When die Navigation ausgelöst wird,
Then speichert der Wizard den Trip automatisch via POST `/api/trips` und navigiert
anschließend zum ursprünglich geklickten Ziel (nicht zur Trip-Detailseite).

**AC-2:** Given der Trip wurde automatisch gespeichert (AC-1),
When die Navigation zum Ziel-Link startet,
Then erscheint der Trip unter `/trips` in der Trip-Liste des Nutzers.

**AC-3:** Given der Nutzer klickt auf den „Trip speichern"-Button manuell (alle Tabs done),
When der POST erfolgreich zurückkommt,
Then zeigt der Button kurz „Trip gespeichert" und navigiert dann zur Trip-Detailseite.

**AC-4:** Given der Nutzer klickt auf „Abbrechen",
When die Abbrechen-Navigation ausgelöst wird,
Then wird KEIN Auto-Save ausgelöst (intentionales Verwerfen bleibt möglich).

**AC-5:** Given noch nicht alle Pflicht-Tabs ausgefüllt sind (`ready === false`),
When der Nutzer auf einen Link klickt,
Then wird KEIN Auto-Save versucht (unvollständiger Trip kann nicht gespeichert werden).

**AC-6:** Given ein Auto-Save läuft gerade (Speichern in progress),
When der Nutzer erneut auf einen Link klickt,
Then wird die Navigation nicht doppelt ausgelöst (kein Doppel-POST).

**AC-7:** Given der Desktop-Save-Button auf `/trips/new`,
When noch kein Trip gespeichert ist (`savedTripId === null`, `ready === true`),
Then zeigt der Button den Text „Trip speichern" (statt bisher „Tour speichern").

## Implementation Details

### Änderungen in `TripNewEditor.svelte`

1. **Import erweitern:** `beforeNavigate` zu `$app/navigation`-Import hinzufügen.

2. **Neuer State:** `let savedTripId: string | null = $state(null)` — Track ob Trip bereits gespeichert.

3. **Neuer Flag:** `let intentionalCancel = false` — verhindert Auto-Save beim Abbrechen.

4. **`buildAndSave()`-Hilfsfunktion** (extrahiert aus `makeSaveHandler`):
   ```
   async function buildAndSave(): Promise<string | null>
     Guard: if (!ready || saving || savedTripId) return null
     saving = true, saveError = null
     if activeTab === 'wegpunkte': syncEditorBack()
     POST /api/trips mit buildCreateTripPayload(state)
     on success: savedTripId = created.id; return created.id
     on error: saveError = message; return null
     finally: saving = false
   ```

5. **`beforeNavigate`-Hook:**
   ```
   beforeNavigate(({ cancel, to }) => {
     if (!ready || savedTripId || saving || !to || intentionalCancel) return
     cancel()
     void (async () => {
       const id = await buildAndSave()
       if (id) await goto(to.url.href)
     })()
   })
   ```

6. **`makeCancelHandler` anpassen:** `intentionalCancel = true` setzen vor `goto('/trips')`.

7. **`makeSaveHandler` vereinfachen:**
   ```
   return async () => {
     const id = await buildAndSave()
     if (id) await goto(`/trips/${id}`)
   }
   ```

8. **Button-Labels aktualisieren:**
   - Desktop: `saving ? 'Speichere…' : savedTripId ? 'Trip gespeichert' : 'Trip speichern'`
   - Mobile: gleich

## Changelog

- 2026-06-10: Spec erstellt, implementiert und freigegeben (Bug #691, frontend-only, +30 LoC TripNewEditor.svelte)
