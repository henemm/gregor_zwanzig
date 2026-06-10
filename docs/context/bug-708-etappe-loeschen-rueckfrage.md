# Bug #708: Etappen dürfen nicht ohne Rückfrage gelöscht werden

- **Location:**
  - `frontend/src/lib/components/trip-detail/waypoints/StageCard.svelte:96-103` (× → `onRemove()`)
  - `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte:45` (`onRemoveStage(id)`)
  - `frontend/src/lib/components/edit/EditStagesPanelNew.svelte:163` (`handleRemoveStage` → `stages.filter`)
  - Zweite Bug-Klasse: `frontend/src/lib/components/trip-new/TripNewEditor.svelte:255/617`
- **Problem:** Klick auf das „×" einer Etappen-Karte löscht die Etappe sofort und unwiederbringlich.
- **Expected:** Vor dem Löschen erscheint eine Sicherheitsabfrage (Bestätigen/Abbrechen). Ein Fehlklick wird abgefangen.
- **Root Cause:** Der Lösch-Handler mutiert die Stage-Liste direkt im `onclick`, ohne dazwischengeschalteten Bestätigungsschritt.
- **Test:** Playwright-E2E auf Staging als eingeloggter Nutzer: × klicken → Dialog erscheint → „Abbrechen" lässt Etappe bestehen; × klicken → „Löschen" entfernt Etappe.
- **Effort:** Small (Bestätigungs-Dialog im bits-ui-Standard, ein Pending-State).
