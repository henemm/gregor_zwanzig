# Mini-Spec: Auto-Save für per Kartentipp angelegte Wegpunkte (#1194)

## Was ändert sich
- `handleMapClick()` in `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` ruft nach dem Anlegen des neuen Wegpunkts den Save-Trigger auf — identisch zu allen anderen Mutations-Handlern: `if (saveController) scheduleSave(); else void save();`
- Damit wird ein per Kartentipp gesetzter Wegpunkt ans Backend persistiert und überlebt Reload/Verlassen der Seite.

## Was darf sich nicht ändern
- Kein anderes Verhalten von `handleMapClick()` (Wegpunkt erscheint weiter sofort im UI-State, `activeWaypointId` wird weiter gesetzt, `addModeHint`-Logik unberührt).
- Kein zusätzlicher Save-Aufruf bei `activeIsPause`/fehlender `activeStage` (Early-Return bleibt).
- User-Isolation: Save läuft weiter über den bestehenden `saveController`/`save()`-Pfad des jeweiligen Nutzers — keine Änderung am Persistenz-Kontrakt.

## Manuelle Test-Schritte (Staging)
1. Trip mit aktiver Etappe im Trip-Editor öffnen.
2. In die Karte tippen → neuer Wegpunkt erscheint in der Liste.
3. Seite neu laden (F5).
4. Erwartung: Der Wegpunkt ist weiterhin vorhanden (vorher: verschwunden).

## Inline-Test (wird während Implementierung geschrieben)
- [ ] E2E: Kartentipp legt Wegpunkt an → nach Reload/erneutem Laden ist der Wegpunkt persistiert (Backend-Nachweis, nicht nur UI-State).
