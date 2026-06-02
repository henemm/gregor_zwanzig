# Context: Issue #500 — Etappen-Kacheln anklickbar → WaypointEditor-Navigation

## Request Summary

Die Etappen-Kacheln im Tab „Etappen & Wegpunkte" der Trip-Edit-Seite (EditStagesPanelNew)
sollen anklickbar werden und mit `cursor-pointer` + Hover-Feedback ausgestattet sein. Klick
navigiert zum WaypointEditor für die gewählte Etappe; Zurück-Navigation führt zur Edit-Seite
mit Tab „Etappen" aktiv.

## Kritischer Befund: Edit-Seite aktuell unerreichbar

`frontend/src/routes/trips/[id]/edit/+page.server.ts` enthält einen 301-Redirect:
```ts
throw redirect(301, `/trips/${params.id}?tab=stages`);
```
Das bedeutet: `goto('/trips/${trip.id}/edit')` (in `frontend/src/routes/trips/+page.svelte:156`)
landet NICHT bei TripEditView, sondern bei der Trip-Detail-Seite mit `?tab=stages`.
Die `+page.svelte` im `/edit/`-Ordner (inkl. TripEditView) ist derzeit totes Code.
Dieser Redirect muss entfernt und durch eine echte Load-Funktion ersetzt werden.

## Related Files

| Datei | Relevanz |
|-------|---------|
| `frontend/src/routes/trips/[id]/edit/+page.server.ts` | **BLOCKIERT** — 301-Redirect statt Trip-Load; muss repariert werden |
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | Rendert `TripEditView trip={data.trip}` — korrekt, aber nie erreichbar |
| `frontend/src/routes/trips/[id]/+page.server.ts` | Referenz-Implementierung für den Trip-Load (Zeilen 1-22) |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Haupt-Edit-Komponente; `activeTab = $state('etappen')` hardcoded |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Tab-Inhalt; `activeStageId` intern via `$state`, EtappenStrip eingebunden |
| `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte` | Horizontaler Strip mit StageCards; übergibt bereits `onclick={makeStageActivateHandler(id)}` |
| `frontend/src/lib/components/trip-detail/waypoints/StageCard.svelte` | Kachel; `cursor: default` (Zeile 129) statt `cursor: pointer` → visueller Bug |
| `frontend/src/routes/trips/+page.svelte:156` | Einstieg: `goto('/trips/${trip.id}/edit')` |
| `frontend/e2e/issue-407-waypoint-editor-screen.spec.ts` | 12 Skip-Tests — beschreiben verworfene WaypointEditorPage-Architektur, bleiben skip |

## Existing Patterns

- **URL-Query für Tab-State:** `/trips/[id]?tab=...` → `page.url.searchParams.get('tab')` (TripTabs)
- **URL-Query für aktiven Stage:** noch nicht vorhanden, empfohlen: `?stage=[stageId]`
- **StageCard-onclick:** bereits implementiert — EtappenStrip übergibt Handler, StageCard ruft ihn auf; nur CSS-Bug (`cursor: default`)
- **Referenz-Load:** `/trips/[id]/+page.server.ts` holt Trip via `fetch` mit Session-Cookie-Forwarding

## Was „WaypointEditor" in Issue #500 bedeutet

Die Karte + Höhenprofil + Wegpunkt-Sidebar in EditStagesPanelNew IS der WaypointEditor.
Kein eigener Screen/Route. Der Klick wählt die Etappe aus → der Editor darunter zeigt ihre Daten.
„Zurück-Navigation" = Abbrechen-Button in TripEditView (→ `/trips`) oder Browser-Back.
AC-3 ist erfüllt wenn der User nach „Abbrechen" / Browser-Back wieder auf der Edit-Seite
mit Tab Etappen landet — was passiert, wenn die Seite korrekt rendert.

## Dependencies

- **Upstream:** Python-API `/api/trips/{id}` liefert Trip mit Stages/Waypoints
- **Downstream:** Nichts hängt am `/edit/`-Route-Rendering ab

## Existing Specs

- `docs/specs/modules/epic_137_wegpunkt_editor.md` — WaypointEditor-Konzept (StageCard, EtappenStrip)
- `docs/specs/modules/issue_503_etappen_waypoints.md` — Aktueller EditStagesPanelNew-Stand

## Risks & Considerations

1. **Load-Funktion reparieren** — Ohne das Entfernen des 301-Redirects ist alles andere sinnlos
2. **StageCard CSS-Override** — `cursor: pointer` muss bedingt sein (`onclick`-Prop), da die Karte auch in Readonly-Kontexten verwendet wird
3. **Skip-Tests bleiben skip** — Die 12 Tests in `issue-407` beschreiben eine verworfene Architektur; weder reaktivieren noch löschen
4. **Neue E2E-Tests** — `issue-500-stage-card-navigation.spec.ts` für AC-1/2/3 aus Issue #500
5. **`?stage` URL-Param optional** — AC-2 ist bereits durch bestehende `onStageActivate`-Logik erfüllt; URL-Param wäre „nice to have", ist aber kein AC-Requirement
