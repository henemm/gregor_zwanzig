---
entity_id: issue_658_trip_new_wegpunkte_tab
type: module
created: 2026-06-07
updated: 2026-06-08
status: live
version: "1.0"
tags: [trips, editor, frontend, design-compliance]
---

# Neue Tour — Wegpunkte-Tab (eingebetteter Waypoint-Editor) (#658)

## Approval

- [x] Approved & LIVE (2026-06-08)

## Purpose

Der optionale Tab „Wegpunkte prüfen" im Anlege-Flow `/trips/new` (Slice 2 / AC-5 von #622)
ersetzt seinen Slice-1-Platzhalter durch den eingebetteten Waypoint-Editor und stellt sicher,
dass die aus den GPX-Dateien berechneten (und ggf. vom Nutzer bearbeiteten) Wegpunkte beim
finalen Speichern der Tour persistiert werden. Aktuell verwirft der Anlege-Flow diese Wegpunkte
(`buildCreateTripPayload` setzt `waypoints: []`) — #658 schließt diese stille Datenlücke.

## Source

- **File:** `frontend/src/lib/components/trip-new/TripNewEditor.svelte`
- **Identifier:** Tab-Branch `activeTab === 'wegpunkte'` (Platzhalter Z. 473–482) + GPX-Upload-Handler
- **File:** `frontend/src/lib/components/trip-new/tripNewLogic.ts`
- **Identifier:** `CreateTripStage`, `buildCreateTripPayload`
- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte`
- **Identifier:** Editor-Kern (`showSave`, `tripId`-Props) = der „embedded"-Modus
- **Design-Quelle (verbindlich, 1:1):** `docs/design-requests/trip-anlegen-2026-06-06/screen-trip-new-v2.jsx` → `TN_WegpunkteTab` (Z. 425–475)
- **SOLL (Pixel-Gate):** `.github/issue-assets/soll-trip-new-wegpunkte-tab.png` (Create-Flow-eigene SOLL — **nicht** die als überholt geschlossene #585-SOLL)

## Estimated Scope

- **LoC:** ~120 (Frontend-only, additiv)
- **Files:** 2–3 (`TripNewEditor.svelte`, `tripNewLogic.ts`, ggf. `EditStagesPanelNew.svelte`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `EditStagesPanelNew.svelte` | Komponente | Editor-Kern (EtappenStrip + Karte + Profil + Wegpunkt-Liste); `showSave={false}` + ohne `tripId` = embedded, kein PUT |
| `/api/gpx/parse` | Endpoint | Liefert bereits `{name, date, waypoints[]}` je GPX (Quelle der Wegpunkte) |
| `Stage` / `Waypoint` | Typ (`frontend/src/lib/types.ts`) | Datenmodell des Editors (string-IDs, `waypoints[]`) |
| `POST /api/trips` | Endpoint | Persistiert `stage.waypoints` — **kein** Schema-Change nötig |

## Implementation Details

```
Datenfluss (lokaler Create-State, Persistenz erst bei POST):

1. GPX-Upload (TripNewEditor.makeGpxUploadHandler):
   - übernimmt aus /api/gpx/parse-Antwort die `waypoints` (und km/asc) in den lokalen Etappen-State
   - StageLocal um `waypoints: Waypoint[]` erweitern

2. Wegpunkte-Tab (activeTab === 'wegpunkte'):
   - Info-Banner (oben): Titel + Beschreibung + [Überspringen →][Wegpunkte übernehmen →]
   - <EditStagesPanelNew bind:stages={editorStages} showSave={false} />   // kein tripId → kein PUT
   - Footer (unten): [Überspringen][Wegpunkte übernehmen →]
   - editorStages = Stage[]-Sicht des lokalen States (string-IDs, waypoints); Editor-Mutationen
     fließen per Binding zurück
   - alle 4 Buttons rufen switchTab('metriken')

3. Persistenz (tripNewLogic.buildCreateTripPayload):
   - CreateTripStage um `waypoints?: Waypoint[]` erweitern
   - statt `waypoints: []` die echten (ggf. editierten) Wegpunkte je Etappe schreiben

embedded-Modus: EditStagesPanelNew ist bereits Editor-Kern ohne Page-Chrome; `save()` ist durch
`if (!tripId) return` geschützt, `showSave={false}` blendet die Save-Bar aus. Additiv —
Default = bisheriges Edit-Verhalten, kein Bruch des Edit-Flows.

Out of scope: Mobile (AC-9, separates Issue); Wegpunkt-/Naismith-Berechnung (#503/#296 vorhanden);
Backend-Schema (unverändert).
```

## Expected Behavior

- **Input:** Eingeloggter Nutzer mit allen hochgeladenen GPX-Dateien öffnet den Wegpunkte-Tab in `/trips/new`; optional Wegpunkt-Bearbeitungen (umbenennen/verschieben/hinzufügen/löschen).
- **Output:** Eingebetteter Editor zeigt die GPX-Wegpunkte je Etappe; beim Speichern (`POST /api/trips`) enthält die Tour genau diese (ggf. editierten) Wegpunkte — auch wenn der Tab übersprungen wurde.
- **Side effects:** **Kein** inkrementelles `PUT` während der Bearbeitung; Persistenz ausschließlich beim finalen POST.

## Acceptance Criteria

- **AC-1:** Given alle GPX einer neuen Tour sind hochgeladen und der Nutzer öffnet den Tab „Wegpunkte prüfen", When der Tab rendert, Then erscheint **kein** „Folgt in Slice 2"-Platzhalter mehr, sondern ein Info-Banner („Wegpunkte aus GPX berechnet — optional prüfen") oben, darunter der eingebettete Wegpunkt-Editor (Etappen-Strip + Karte + Höhenprofil + Wegpunkt-Liste) und unten ein Footer.
  - Test: Playwright gegen Staging — Tour anlegen, GPX hochladen, Wegpunkte-Tab öffnen; Banner-Text, `data-testid="edit-stages-panel"` und Footer-Buttons sichtbar, Platzhalter-Text fehlt.

- **AC-2:** Given der Wegpunkte-Tab ist offen, When der Editor lädt, Then zeigt er für die hochgeladenen Etappen die aus den GPX-Dateien berechneten Wegpunkte (die `/api/gpx/parse`-Wegpunkte je Etappe), nicht eine leere Liste.
  - Test: Playwright — Wegpunkt-Sidebar zeigt `N insgesamt` mit N > 0 für die aktive Etappe.

- **AC-3:** Given der Tab „Wegpunkte prüfen" in der Tab-Leiste, When er freigeschaltet ist, Then trägt er eine `OPTIONAL`-Pill (Mono, uppercase, accent-getönt), und der Tab ist überspringbar (Wetter-Tab ist auch ohne Besuch des Wegpunkte-Tabs erreichbar).
  - Test: Playwright — OPTIONAL-Pill sichtbar; ohne Wegpunkte-Tab-Klick direkt auf Wetter-Tab wechseln gelingt.

- **AC-4:** Given der Wegpunkte-Tab ist offen, When der Nutzer „Überspringen →" **oder** „Wegpunkte übernehmen →" (im Info-Banner oder im Footer) klickt, Then wechselt die Ansicht zum Wetter-Metriken-Tab.
  - Test: Playwright — jeder der vier Buttons führt zum Wetter-Tab (`WeatherMetricsTab` sichtbar).

- **AC-5:** Given der Nutzer hat im Wegpunkte-Editor mindestens einen Wegpunkt bearbeitet (umbenannt, verschoben, hinzugefügt oder gelöscht), When er die Tour über „Tour speichern" anlegt (`POST /api/trips`), Then enthält die gespeicherte Tour genau diese bearbeiteten Wegpunkte je Etappe — nach dem Speichern sind sie in der Trip-Detail-Ansicht (`/trips/<id>`) sichtbar.
  - Test: Playwright gegen Staging — Wegpunkt umbenennen → speichern → in `/trips/<id>` denselben Namen finden (echte DB-Persistenz).

- **AC-6:** Given der Nutzer überspringt den Wegpunkte-Tab vollständig (ohne ihn zu öffnen), When er die Tour speichert, Then enthält die gespeicherte Tour dennoch die aus GPX berechneten Wegpunkte je Etappe (Überspringen = unveränderte GPX-Wegpunkte übernehmen, **nicht** leere Wegpunkte).
  - Test: `node:test` — `buildCreateTripPayload` mit gefüllten Stage-`waypoints` erzeugt Payload mit denselben Wegpunkten (kein leeres Array).

- **AC-7:** Given der Wegpunkte-Editor ist im Anlege-Flow eingebettet, When der Nutzer Wegpunkte bearbeitet, Then erfolgt **kein** Netzwerk-`PUT` (kein inkrementelles Speichern) — der gesamte State bleibt lokal bis zum finalen `POST /api/trips`; es gibt keine „Etappen speichern"-Schaltfläche im eingebetteten Editor.
  - Test: Playwright — Network-Observer: während Wegpunkt-Bearbeitung kein `PUT /api/trips/*`; keine „Etappen speichern"-Schaltfläche im Tab.

- **AC-8:** Given der gerenderte Wegpunkte-Tab im Desktop-Layout, When er gegen `soll-trip-new-wegpunkte-tab.png` per Pixel-Diff geprüft wird, Then liegt die Abweichung unter dem definierten Fidelity-Schwellwert (Layout 1:1: Info-Banner, Button-Beschriftungen, eingebetteter Editor, Footer).
  - Test: Pixel-Diff gegen die SOLL-PNG vor Issue-Close.

## Known Limitations

- **Mobile-Layout** ist nicht Teil dieses Issues (AC-9, separates Issue).
- **State-Divergenz:** Reorder/Add-Stage im eingebetteten Editor und im Etappen-Tab teilen denselben kanonischen Stage-State; auf konsistente Synchronisation ist zu achten.
- Wegpunkt-/Naismith-Berechnung bleibt unverändert (#503/#296).

## Changelog

- 2026-06-07: Initial spec created (#658, Slice 2 / AC-5 von #622)
- 2026-06-08: Implementation LIVE — Wegpunkte-Tab mit eingebettetem Editor + Persistenz in `buildCreateTripPayload` (Commit 2026-06-08). Alle ACs verifiziert.
