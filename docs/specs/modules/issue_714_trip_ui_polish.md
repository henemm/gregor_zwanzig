---
entity_id: issue_714_trip_ui_polish
type: module
created: 2026-06-10
updated: 2026-06-10
status: implemented
version: "1.0"
tags: [frontend, trips, ui, bug]
---

# Issue #714 — Trip-Editor UI-Kleinigkeiten (#706, #713, #719)

## Approval

- [x] Implemented (2026-06-10)

## Purpose

Drei rein frontendseitige UI-Korrekturen in Trip-Übersicht und Trip-Editor:
abgeschnittenes Aktionsmenü (#706), aufgeräumte Titel-Bearbeitung per Stift-Icon
(#713) und ein fehlender Etappen-Lösch-Button im mobilen Etappen-Tab (#719).
(#699 — Doppelter Pfad im Header — ist bereits live, Commit `43fb624f`.)

## Source

- **File:** `frontend/src/routes/trips/+page.svelte` (#706 — Overflow-Menü, Z.~411–487)
- **File:** `frontend/src/lib/components/trip-detail/TripHeader.svelte` (#713 — `name-edit-row`, Z.~115–130)
- **File:** `frontend/src/lib/components/trip-new/TripNewEditor.svelte` (#719 — Mobile Stage-Card, Z.~817–860)
- **Identifier:** Svelte-Komponenten (Frontend / User-UI → `frontend/src/...`)

## Estimated Scope

- **LoC:** ~65
- **Files:** 3 Komponenten + 1 E2E-Test-Anpassung (`e2e/issue-616-trip-one-surface.spec.ts`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `@lucide/svelte/icons/pencil` | Icon | Stift-Icon für #713 (bereits projektweit genutzt) |
| bits-ui Dialog + `pendingRemoveStageId` / `confirmRemoveStage` | bestehend (#708) | Bestätigungsdialog für #719 |
| `getBoundingClientRect()` | DOM | Anker-Koordinaten für `position:fixed`-Menü (#706) |

## Implementation Details

```
#706 — Overflow-Menü bricht aus overflow:hidden aus
  Problem: <Card style="overflow: hidden;"> (Z.373) beschneidet das
           position:absolute-Menü (Z.440) → unten abgeschnitten.
  Fix:     Menü auf position:fixed umstellen, Koordinaten beim Öffnen aus
           getBoundingClientRect() des Buttons berechnen (rechtsbündig zum
           Button, unterhalb). Bei scroll/resize Menü schließen (openMenuId=null),
           damit keine veraltete Position stehenbleibt. Außenklick-Overlay
           bleibt (ist bereits position:fixed). Menüinhalt unverändert.

#713 — Titel nur per Stift-Icon editierbar
  Problem: name-edit-row (Input + "Umbenennen") ist dauerhaft sichtbar.
  Fix:     neues let isEditingName = $state(false).
           - Default: H1 + kleiner Stift-Button (PencilIcon, aria-label
             "Trip-Name bearbeiten", data-testid "trip-name-edit-toggle")
             neben/unter dem Titel; name-edit-row NICHT gerendert.
           - Klick auf Stift → isEditingName = true: name-edit-row erscheint
             (Input testid "trip-name-edit" + Speichern-Btn testid
             "trip-name-save" + Abbrechen).
           - Nach erfolgreichem Save ODER Abbrechen → isEditingName = false.
           - Abbrechen setzt editName auf trip.name zurück.
           Save-Handler (api.put name) unverändert.

#719 — Mobile Etappen-Lösch-Button
  Problem: Mobile Stage-Card (Z.817–860) hat nur GPX-× (makeGpxRemoveHandler),
           keinen Etappen-Lösch-Button.
  Fix:     Im IMMER sichtbaren Card-Header (Z.819) einen ×-Button ergänzen,
           onclick={makeRemoveStageHandler(s.id)} (löst pendingRemoveStageId →
           bestehenden #708-Dialog aus, KEIN sofortiges Löschen),
           aria-label="Etappe entfernen", data-testid="tn-mobile-stage-remove-{idx}",
           min. 44px Touch-Target.
```

## Expected Behavior

- **Input:** Nutzer-Interaktionen in Trip-Übersicht (Desktop-Tabelle), Trip-Detail-Header, mobilem Etappen-Tab von `/trips/new`.
- **Output:** vollständig sichtbares Aktionsmenü; aufgeräumter Titel mit Stift-Toggle; löschbare Etappen auf Mobile mit Rückfrage.
- **Side effects:** keine neuen Persistenz-/Backend-Pfade. #713 nutzt den bestehenden `PUT /api/trips/{id}` (nur `name`).

## Acceptance Criteria

- **AC-1:** Given die Trip-Übersicht (`/trips`) in der Desktop-Tabelle mit mindestens einer Zeile / When der Nutzer auf den „…"-Aktionsknopf einer Zeile klickt / Then ist das vollständige Aktionsmenü sichtbar und **nicht abgeschnitten** — auch der unterste Eintrag „Löschen" ist klick- und sichtbar.
  - Test: Playwright gegen Staging — `trip-row-menu-btn` klicken, prüfen dass der „Löschen"-`menuitem` im Viewport vollständig sichtbar ist (`boundingBox` liegt innerhalb `window.innerHeight`, nicht clipped) und anklickbar ist.

- **AC-2:** Given die Trip-Detail-Seite eines Trips / When die Seite geladen ist (kein Edit-Zustand) / Then ist **kein** dauerhaftes Namens-Eingabefeld sichtbar, sondern nur der Titel mit einem Stift-Icon.
  - Test: Playwright — `trip-name-edit` (Input) ist initial **nicht** sichtbar, `trip-name-edit-toggle` (Stift) ist sichtbar.

- **AC-3:** Given die Trip-Detail-Seite / When der Nutzer auf das Stift-Icon klickt, den Namen ändert und „Speichern" drückt / Then erscheint das Eingabefeld erst nach Klick, der neue Name **persistiert** (via API), und nach dem Speichern ist das Eingabefeld wieder verborgen.
  - Test: Playwright gegen Staging — Stift klicken → `trip-name-edit` wird sichtbar → ausfüllen → `trip-name-save` → `GET /api/trips/{id}` liefert neuen Namen → `trip-name-edit` wieder verborgen. (Cleanup: Name zurücksetzen.)

- **AC-4:** Given der mobile Etappen-Tab (`<900px`) von `/trips/new` mit mindestens einer Etappe / When der Nutzer auf den Etappen-Lösch-Button (`×`) einer Etappen-Karte klickt / Then öffnet sich der **Bestätigungsdialog** (#708) und die Etappe wird **erst nach Bestätigung** entfernt (kein sofortiges Löschen).
  - Test: Playwright @375px — `tn-mobile-stage-remove-0` klicken → Dialog erscheint → „Abbrechen" lässt Etappe bestehen; erneut → „Löschen" entfernt genau diese Etappe (Karten-Anzahl −1).

- **AC-5:** Given der mobile Etappen-Tab / When ein GPX zu einer Etappe hochgeladen ist / Then bleiben GPX-Entfernung (`×` im GPX-Slot) und Etappen-Löschung (`×` im Header) **getrennte** Aktionen — GPX-× entfernt nur das GPX, Header-× löst die Etappen-Löschung aus.
  - Test: Playwright @375px — GPX-× entfernt GPX, Etappe bleibt; Header-× öffnet den Lösch-Dialog.

## Known Limitations

- #706: Bei sehr schnellem Scrollen während offenem Menü schließt das Menü (bewusst), statt mitzuwandern — bewährtes Verhalten, vermeidet veraltete Positionen.
- Bestehender E2E-Test `e2e/issue-616-trip-one-surface.spec.ts` AC-6 erwartet `trip-name-edit` als sofort sichtbar — muss angepasst werden (erst `trip-name-edit-toggle` klicken). Teil dieser Umsetzung.

## Changelog

- 2026-06-10: Initial spec created (Rest-Paket #714: #706, #713, #719; #699 bereits live)
