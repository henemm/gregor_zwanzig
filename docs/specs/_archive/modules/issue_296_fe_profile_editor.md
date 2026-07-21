---
entity_id: issue_296_fe_profile_editor
type: module
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
parent_issue: 296
related: issue_296_be_naismith_arrival
issues: [296]
tags: [frontend, sveltekit, trip-editor, waypoints, profile, naismith, no-map]
---

# Issue #296-FE — Trip-Editor: Wegpunkte visuell über Höhenprofil (keine Karte) + Ankunftszeiten

## Approval

- [ ] Approved

## Purpose

Der „Etappen"-Abschnitt im Trip-Editor (`/trips/[id]/edit`) zeigt Wegpunkte heute als Lat/Lon/Höhen-Zahlenfelder (`EditStagesSection.svelte`). Diese werden durch eine **visuelle Bearbeitung über das Höhenprofil** ersetzt — **keine Landkarte** (PO-Entscheidung 2026-05-22, siehe `docs/context/issue_296_map_waypoint_editor.md`). Wegpunkte werden auf dem Profil platziert/bestätigt/verworfen; pro Wegpunkt wird die berechnete **Naismith-Ankunftszeit** angezeigt. Wiederverwendung der bereits gebauten epic_137-Komponenten (`ProfileEditor`, `WaypointCard`, `EtappenStrip`) — der Detail-View (`/trips/[id]`) bleibt unverändert.

## Source

**Schicht: Frontend / SvelteKit** — alle Dateien unter `frontend/src/`.

**NEU:**
- `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` — Kern-Komponente (Profil-basierter Etappen-Editor)
- `frontend/src/lib/utils/naismith.ts` — `naismithHours()`, `computeArrivalTimes()`
- `frontend/src/lib/utils/naismith.test.ts` — Unit-Tests
- `frontend/e2e/issue-296-profile-editor.spec.ts` — E2E-Tests neuer Editor

**EDIT:**
- `frontend/src/lib/components/trip-detail/waypoints/ProfileEditor.svelte` — optionales Prop `onProfileAdd` (Klick auf Profil-Fläche)
- `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte` — optionales Prop `arrival` (Anzeige Ankunftszeit)
- `frontend/src/lib/utils/waypointEditor.ts` — `interpolateWaypoint()` (+ Tests in bestehender `waypointEditor.test.ts`)
- `frontend/src/lib/components/edit/TripEditView.svelte` — `EditStagesSection` → `EditStagesPanelNew`, `stripSuggested` vor Save
- `frontend/src/lib/types.ts` — `Waypoint.arrival_calculated?: string` (Feld aus `issue_296_be_naismith_arrival`, hier konsumiert)

**LÖSCHEN:**
- `frontend/src/lib/components/edit/EditStagesSection.svelte` — ersetzt
- `frontend/e2e/bug-273-coordinate-inputmode.spec.ts` — testet entfernte Koordinaten-Inputs
- `frontend/e2e/bug-283-waypoint-table.spec.ts` — testet entfernte Lat/Lon-Tabelle

**Identifier:** `EditStagesPanelNew` (default), `naismithHours`, `computeArrivalTimes`, `interpolateWaypoint`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ProfileEditor.svelte` | component (epic_137) | SVG-Höhenprofil, klickbare Pins — erweitert um Add-Klick |
| `WaypointCard.svelte` | component (epic_137) | Wegpunkt-Listeneintrag (Confirm/Reject/Rename/Delete) — erweitert um Arrival |
| `EtappenStrip.svelte` | component (epic_137) | Horizontaler Etappen-Strip (DnD, Pause-Inserter) — unverändert genutzt |
| `PauseStageView.svelte` | component (epic_137) | Pausentag-Ansicht — unverändert genutzt |
| `WaypointsPanel.svelte` | reference | Architektur-Vorbild (State-Pattern); wird NICHT geändert |
| `waypointEditor.ts` `stripSuggested` | util | Transientes `suggested`-Flag vor Persistenz strippen |
| `headerStats.ts` `haversineKm` | util | Distanzberechnung für `computeArrivalTimes` (kein eigener Haversine) |
| `frontend/src/lib/types.ts` `Stage`/`Waypoint` | types | Datenmodell; `arrival_calculated?` aus BE-Spec |
| `TripEditView.svelte` | file (edit) | Container; bindet Editor ein + persistiert via PUT |
| `issue_296_be_naismith_arrival` | spec | liefert persistiertes `arrival_calculated` (Editor zeigt clientseitig live, Backend persistiert authoritative) |

## Implementation Details

### §1 Naismith-Util (`naismith.ts`) — clientseitige Live-Berechnung

```typescript
// Konstanten gespiegelt aus src/app/models.py EtappenConfig (Single Source dort).
const SPEED_FLAT_KMH = 4.0;
const SPEED_ASCENT_MH = 300.0;
const SPEED_DESCENT_MH = 500.0;

/** Angepasste Naismith's Rule (SUMME). distKm + Höhenmeter → Stunden. */
export function naismithHours(distKm: number, ascentM: number, descentM: number): number {
  return distKm / SPEED_FLAT_KMH + ascentM / SPEED_ASCENT_MH + descentM / SPEED_DESCENT_MH;
}

/**
 * Kumulative Ankunftszeiten pro Wegpunkt einer Stage als "HH:MM".
 * startTime "HH:MM" (default "08:00"). Distanz via haversineKm (headerStats).
 * Pausentag (0 Wegpunkte) → []. Erster Wegpunkt = startTime.
 */
export function computeArrivalTimes(stage: Stage, startTime?: string): string[];
```

Identische Formel/Konstanten wie `internal/model/naismith.go` (BE-Spec) → Editor-Anzeige (vor Save) == persistierter Wert (nach Save) == Pipeline-Zeit.

### §2 ProfileEditor — Klick auf Fläche = Wegpunkt hinzufügen (additiv, optional)

Neues optionales Prop, Detail-View bleibt unverändert (gibt das Prop nicht):

```typescript
interface Props {
  stage: Stage;
  activeWaypointId: string | null;
  onWaypointActivate: (waypointId: string) => void;
  onProfileAdd?: (fraction: number) => void; // NEU — fraction 0..1 entlang Profil-x
}
```

- Nur wenn `onProfileAdd` gesetzt: `<svg>` (bzw. transparentes Hintergrund-`<rect>`) bekommt `onclick`, das aus `clickX` die `fraction = (clickX - padding) / innerW` (geclamped 0..1) berechnet und `onProfileAdd(fraction)` ruft.
- Pin-`onclick` ruft `event.stopPropagation()` → Pin-Klick fügt NICHT hinzu, sondern aktiviert nur.
- Ohne `onProfileAdd`: Verhalten exakt wie heute (keine Regression in `waypoints-editor.spec.ts`).

### §3 interpolateWaypoint (`waypointEditor.ts`)

```typescript
/**
 * Linear interpolierter neuer Wegpunkt aus einer fraction (0..1) über den
 * Wegpunkt-Index-Raum. Gibt Felder + Einfügeindex zurück.
 * floatIdx = fraction * (n-1); i = floor(floatIdx); t = floatIdx - i.
 * Felder = lerp(wp[i], wp[i+1], t). insertAfterIndex = i.
 * n < 2 → an wp[0] orientiert (oder leer-handling).
 */
export function interpolateWaypoint(
  waypoints: Waypoint[],
  fraction: number
): { lat: number; lon: number; elevation_m: number; insertAfterIndex: number };
```

### §4 WaypointCard — Ankunftszeit anzeigen (additiv, optional)

```typescript
interface Props {
  // ... bestehende Props unverändert ...
  arrival?: string | null; // NEU — "HH:MM", wird neben elevation_m angezeigt wenn gesetzt
}
```

Detail-View (`WaypointsPanel`) gibt `arrival` nicht → unverändert. TestID für Anzeige: `data-testid="wp-arrival-{index}"`.

### §5 EditStagesPanelNew.svelte — Kern

State-Pattern angelehnt an `WaypointsPanel`, ABER **kein eigener Save** — `stages` wird gebunden, der Save liegt beim Container `TripEditView` (bestehender „Speichern"-Button unten).

```typescript
interface Props {
  stages: Stage[];
}
let { stages = $bindable() }: Props = $props();

let activeStageId = $state<string>(stages.find(s => s.waypoints.length > 0)?.id ?? stages[0]?.id ?? '');
let activeWaypointId = $state<string | null>(null);
const activeStage = $derived(stages.find(s => s.id === activeStageId) ?? null);
const activeIsPause = $derived(activeStage ? activeStage.waypoints.length === 0 : false);
const arrivals = $derived(activeStage ? computeArrivalTimes(activeStage, activeStage.start_time) : []);
```

Layout (kein MapCanvas):
- Oben: `EtappenStrip` (stages, activeStageId, onStageActivate, onStagesReorder, onPauseInsert)
- Bei aktiver Nicht-Pause-Stage: `flex gap-4` — links `ProfileEditor` (mit `onProfileAdd`), rechts `WaypointCard`-Liste (jeweils mit `arrival={arrivals[i]}`)
- Bei Pause-Stage: `PauseStageView`

Mutations-Handler (Factory-Pattern, direkt auf gebundenem `stages`):
- `onProfileAdd(fraction)` → `interpolateWaypoint(activeStage.waypoints, fraction)` → neuen Wegpunkt `{id, name: "Neuer Punkt", lat, lon, elevation_m, suggested: true}` nach `insertAfterIndex` einfügen
- Confirm (suggested) → `suggested`-Flag entfernen
- Reject/Delete → Wegpunkt splicen
- Rename → Name ändern (Inline-Input oder Prompt)
- Activate → `activeWaypointId` setzen

TestIDs: `edit-stages-panel` (Root), bestehende von EtappenStrip/ProfileEditor/WaypointCard.

### §6 TripEditView — Verkabelung + suggested strippen

```svelte
import EditStagesPanelNew from './EditStagesPanelNew.svelte';
import { stripSuggested } from '$lib/utils/waypointEditor';
// ...
<EditStagesPanelNew bind:stages />
```

Im `makeSaveHandler`: vor PUT `stages: stripSuggested(stages)` (transientes Flag nicht persistieren — analog WaypointsPanel/Wizard). `EditStagesSection`-Import + -Datei entfernen.

### §7 Test-Migration

- **Löschen:** `bug-273-coordinate-inputmode.spec.ts` (Koordinaten-Inputs existieren nicht mehr), `bug-283-waypoint-table.spec.ts` (Lat/Lon-Tabelle entfernt). Historische Specs in `docs/specs/modules/` bleiben als Archiv.
- **Neu:** `issue-296-profile-editor.spec.ts` — deckt AC-1 bis AC-5, AC-10 ab.
- **Prüfen (nicht brechen):** `trip-edit.spec.ts` (Edit-View-Assertions sind nicht Lat/Lon-spezifisch; `seedTrip()` nutzt Wizard-Inputs, nicht den Edit-View), `trips.spec.ts`, `waypoints-editor.spec.ts` (Detail-View-Regression).
- **Echte E2E:** Server starten, Playwright gegen echten Trip (`e2e-cockpit-test`). KEINE Mocks.

## Expected Behavior

- **Input:** User öffnet `/trips/:id/edit`, „Etappen"-Abschnitt. `stages[]` mit Wegpunkten (lat/lon/elevation_m), optional `suggested`.
- **Output:** EtappenStrip + Höhenprofil + Wegpunkt-Liste mit Ankunftszeiten. Klick auf Profil-Fläche fügt interpolierten Wegpunkt ein. Keine Lat/Lon-Eingabefelder. Save (Container) persistiert via PUT `/api/trips/:id` ohne `suggested`-Flag.
- **Side effects:** Mutation des gebundenen `stages`-Arrays. Persistenz triggert Backend-Naismith-Berechnung (BE-Spec).

## Acceptance Criteria

- **AC-1:** Given die Seite `/trips/:id/edit` mit geöffnetem „Etappen"-Abschnitt / When sie gerendert ist / Then existieren keine Elemente mit `data-testid` `wp-lat`, `wp-lon` oder `wp-ele`
  - Test: (populated after /tdd-red)

- **AC-2:** Given eine aktive Stage mit ≥1 Wegpunkt / When der Editor rendert / Then ist ein `data-testid="profile-editor"` SVG mit einem Pin pro Wegpunkt sichtbar
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein Wegpunkt mit `suggested: true` / When seine WaypointCard rendert / Then sind Bestätigen- und Verwerfen-Buttons sichtbar; ein manueller Wegpunkt zeigt stattdessen Umbenennen + Löschen
  - Test: (populated after /tdd-red)

- **AC-4:** Given der User klickt auf die Höhenprofil-Fläche zwischen Wegpunkt i und i+1 / When `onProfileAdd` feuert / Then wird ein neuer Wegpunkt mit `suggested: true` an Position i+1 eingefügt, dessen lat/lon/elevation_m linear zwischen den Nachbarn interpoliert sind
  - Test: (populated after /tdd-red)

- **AC-5:** Given eine Stage mit `start_time` "08:00" und Wegpunkten / When der Editor rendert / Then zeigt jede WaypointCard eine Ankunftszeit "HH:MM" (`wp-arrival-{i}`), berechnet von `computeArrivalTimes`
  - Test: (populated after /tdd-red)

- **AC-6:** Given die Util-Funktion / When aufgerufen / Then gilt `naismithHours(4,0,0) === 1` und `naismithHours(0,300,0) === 1` und `naismithHours(0,0,500) === 1`
  - Test: (populated after /tdd-red)

- **AC-7:** Given zwei Wegpunkte A und B / When `interpolateWaypoint([A,B], 0.5)` aufgerufen / Then ist das Ergebnis lat/lon/elevation_m der Mittelpunkt von A und B mit `insertAfterIndex === 0`
  - Test: (populated after /tdd-red)

- **AC-8:** Given der User hat Wegpunkte bearbeitet und klickt den „Speichern"-Button / When der Container speichert / Then ruft er PUT `/api/trips/:id` mit `stages` auf, in denen kein Wegpunkt mehr `suggested: true` trägt (stripSuggested)
  - Test: (populated after /tdd-red)

- **AC-9:** Given der Detail-View `/trips/:id` Tab „Etappen" (epic_137) / When er nach dieser Änderung gerendert wird / Then bleibt sein Verhalten unverändert (MapCanvas + ProfileEditor sichtbar, `waypoints-editor.spec.ts` grün) — keine Regression durch die optionalen ProfileEditor/WaypointCard-Props
  - Test: (populated after /tdd-red)

- **AC-10:** Given eine aktive Stage die ein Pausentag ist (`waypoints.length === 0`) / When der Editor rendert / Then wird `PauseStageView` (`data-testid="pause-stage-view"`) statt des Höhenprofils gezeigt
  - Test: (populated after /tdd-red)

## Known Limitations

- **Interpolierte Koordinaten:** Ein rein manuell aufs Profil gesetzter neuer Wegpunkt erhält lat/lon als lineare Schätzung zwischen Nachbarn (kein echter Geländebezug, da keine Karte). Akzeptabel — die relevanten Punkte (Wetterscheiden) liefert der Algorithmus mit echten GPX-Koordinaten. UI kennzeichnet selbst gesetzte Punkte (suggested-Stil + Name „Neuer Punkt").
- **Cross-Modul-Import:** `EditStagesPanelNew` importiert epic_137-Komponenten aus `trip-detail/waypoints/`. Reine Props-Komponenten ohne Store-Abhängigkeit → unkritisch.
- **Keine Inline-Startzeit-Eingabe** in diesem Schritt — `start_time` Default 08:00 (konsistent mit Backend). Editierbare Startzeit = Folge-Issue falls Bedarf.
- **Mobile:** Frontend ist Desktop-Planungstool; Bottom-Sheet-Layout nicht Pflicht.

## Changelog

- 2026-05-23: Initiale Spec. Profil-basierter Editor ohne Karte, Wiederverwendung epic_137 (ProfileEditor/WaypointCard/EtappenStrip), additive optionale Props (onProfileAdd/arrival) → Detail-View regressionsfrei, clientseitige Naismith-Live-Anzeige (parität zu BE), Lat/Lon-Inputs + 2 Regressionstests entfernt. 10 Acceptance Criteria. Sub-Spec von Issue #296 (Editor), Partner: `issue_296_be_naismith_arrival`.
