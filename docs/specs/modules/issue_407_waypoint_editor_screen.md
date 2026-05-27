---
entity_id: issue_407_waypoint_editor_screen
type: module
created: 2026-05-27
updated: 2026-05-27
status: draft
version: "1.0"
tags: [frontend, svelte, edit, waypoints, desktop, mobile, issue-407]
---

# Issue #407 — Wegpunkt-Editor: Vollbild-Route `/trips/[id]/edit`

## Approval

- [ ] Approved

## Purpose

Baut die Route `/trips/[id]/edit` von einer generischen Akkordeon-Maske (mit Sektionen für
Route, Etappen, Wetter, Alarmregeln, Reports) in einen dedizierten Vollbild-Wegpunkt-Editor
um, der die bestehende `WaypointsPanel`-Architektur wiederverwendet und als eigenständige
Seite mit Speichern/Abbrechen-Footer präsentiert wird.

Das Redesign ermöglicht dem User, Wegpunkte einer Tour vollständig in einem einzigen fokussierten
Screen zu bearbeiten — auf Desktop mit SVG-Karte links und Sidebar-Liste rechts, auf Mobile
mit Bottom-Sheet-Overlay und KI-Vorschlag-Bar — während Wetter-, Alarmregeln- und
Briefing-Konfiguration weiterhin über die Tabs der Trip-Detail-Seite erreichbar bleiben.

## Source

- **Files:**
  - `frontend/src/routes/trips/[id]/edit/+page.svelte` (EDIT: TripEditView → WaypointEditorPage)
  - `frontend/src/lib/components/edit/WaypointEditorPage.svelte` (NEU — Haupt-Komponente)
  - `frontend/src/lib/components/edit/StageNavDropdown.svelte` (NEU — Mobile Etappen-Navigator)
  - `frontend/src/lib/components/edit/AISuggestionBar.svelte` (NEU — KI-Vorschlag-Bar Mobile)

## Dependencies

| Abhängigkeit | Art | Zweck |
|---|---|---|
| `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte` | Svelte-Komponente (vorhanden) | Desktop Etappen-Navigationsleiste oben |
| `frontend/src/lib/components/trip-detail/waypoints/MapCanvas.svelte` | Svelte-Komponente (vorhanden) | SVG-Topo-Karte (400×300px Desktop, Vollbreite Mobile) mit Route-Polyline + nummerierten WaypointPins |
| `frontend/src/lib/components/trip-detail/waypoints/ProfileEditor.svelte` | Svelte-Komponente (vorhanden) | Höhenprofil-Panel unter der Karte, klickbare Pins, `onProfileAdd` zum Einfügen |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte` | Svelte-Komponente (vorhanden) | Nummerierte Wegpunkt-Listenzeile (Name, Höhe, Ankunftszeit, Confirm/Reject/Rename/Delete) |
| `frontend/src/lib/components/trip-detail/waypoints/PauseStageView.svelte` | Svelte-Komponente (vorhanden) | Pausentag-Ansicht wenn activeStage ein Pausentag ist |
| `frontend/src/lib/components/trip-detail/WaypointsPanel.svelte` | Svelte-Komponente (vorhanden) | Architektur-Vorlage: State-Pattern, Callback-Factory, Save-Logik — nicht geändert |
| `frontend/src/lib/components/mobile/Sheet.svelte` | Svelte-Komponente (vorhanden) | Bottom-Sheet Mobile (snap: 'half') für ProfileEditor + WaypointCard-Liste |
| `frontend/src/lib/components/ui/select/Select.svelte` | Design-System (vorhanden) | Stage-Auswahl-Dropdown im Mobile-Navigator |
| `frontend/src/lib/utils/waypointEditor.ts` | Utility (vorhanden) | `stripSuggested(stages)` — entfernt suggested-Flag vor PUT |
| `frontend/src/lib/utils/naismith.ts` | Utility (vorhanden) | `computeArrivalTimes(stage, startTime?)` — Ankunftszeiten für WaypointCard |
| `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` | Utility (vorhanden) | `isPauseStage(stage)` — Prüft ob Etappe ein Pausentag ist |
| `frontend/src/lib/api.ts` | Utility (vorhanden) | `api.put('/api/trips/{id}', {...trip, stages})` — Read-Modify-Write Save |
| `$app/navigation` (SvelteKit) | Framework | `goto('/trips')` nach Speichern/Abbrechen; `invalidateAll()` nach Save |
| `frontend/src/lib/types.ts` | TypeScript | `Trip`, `Stage`, `Waypoint` — keine Änderung |

## Scope

**Nur Frontend.** Kein Go-Backend-Endpoint geändert. Kein Python-Backend betroffen.

**Out of Scope (explizit ausgeschlossen):**
- Echte OSM/Leaflet-Karte — folgt in separatem Issue
- Sektion "Wetter" in der Edit-Route — verbleibt im Wetter-Briefing-Tab der Trip-Detail-Seite
- Sektion "Alarmregeln" in der Edit-Route — verbleibt im Alarmregeln-Tab der Trip-Detail-Seite
- Sektion "Reports" in der Edit-Route — verbleibt im Reports-Tab der Trip-Detail-Seite
- `AccordionSection.svelte`, `EditReportConfigSection.svelte`, `EditRouteSection.svelte`,
  `EditStagesPanelNew.svelte`, `WeatherSummaryCard.svelte` — werden durch `WaypointEditorPage`
  ersetzt; bestehende Dateien bleiben erhalten (kein Löschen)

## Implementation Details

### 1. `WaypointEditorPage.svelte` (NEU, ~220 LoC)

Vollständige Neuimplementierung des Edit-Screens. Übernimmt das State-Pattern aus
`WaypointsPanel.svelte` 1:1, ergänzt um Navigation nach Save und Mobile-State.

**Props:**
```typescript
interface Props { trip: Trip; }
let { trip }: Props = $props();
```

**State (identisch mit WaypointsPanel):**
```typescript
let localStages = $state<Stage[]>(JSON.parse(JSON.stringify(trip.stages)));
let activeStageId = $state<string>(trip.stages.find(s => !isPauseStage(s))?.id ?? '');
let activeWaypointId = $state<string | null>(null);
let saving = $state(false);
let saveError = $state<string | null>(null);
let sheetOpen = $state(false); // Mobile Bottom-Sheet
```

**Derivations:**
```typescript
const activeStage = $derived(localStages.find(s => s.id === activeStageId) ?? null);
const activeIsPause = $derived(activeStage ? isPauseStage(activeStage) : false);
const activeStageIndex = $derived(localStages.findIndex(s => s.id === activeStageId));
const prevStage = $derived(activeStageIndex > 0 ? localStages[activeStageIndex-1] : null);
const nextStage = $derived(activeStageIndex < localStages.length-1 ? localStages[activeStageIndex+1] : null);
const arrivals = $derived(activeStage ? computeArrivalTimes(activeStage, activeStage.start_time) : []);
const hasSuggested = $derived(activeStage?.waypoints.some(w => w.suggested) ?? false);
```

**Save-Handler:**
```typescript
async function handleSave(): Promise<void> {
  saving = true;
  saveError = null;
  try {
    await api.put(`/api/trips/${trip.id}`, { ...trip, stages: stripSuggested(localStages) });
    goto('/trips');
  } catch (e) {
    saveError = e instanceof Error ? e.message : 'Speichern fehlgeschlagen';
  } finally {
    saving = false;
  }
}

function handleCancel(): void {
  goto('/trips');
}
```

**Desktop-Layout (≥900px):**
```svelte
<div class="wp-editor-desktop">
  <!-- Etappen-Strip horizontal oben -->
  <EtappenStrip stages={localStages} activeStageId={activeStageId}
    onActivate={handleStageActivate} onReorder={handleStagesReorder} />

  <div class="wp-editor-body">
    <!-- Links: Karte + Höhenprofil -->
    <div class="wp-editor-left">
      <MapCanvas stage={activeStage} activeWaypointId={activeWaypointId}
        onWaypointActivate={...} />
      {#if !activeIsPause}
        <ProfileEditor stage={activeStage} arrivals={arrivals}
          onProfileAdd={handleProfileAdd} activeWaypointId={activeWaypointId} />
      {/if}
    </div>

    <!-- Rechts: Wegpunkt-Sidebar -->
    <div class="wp-editor-sidebar">
      <p class="sidebar-count">{activeStage?.waypoints?.length ?? 0} Wegpunkte</p>
      {#if activeIsPause}
        <PauseStageView stage={activeStage} />
      {:else}
        {#each activeStage?.waypoints ?? [] as wp, i}
          <WaypointCard waypoint={wp} index={i} arrival={arrivals[i]}
            onConfirm={...} onReject={...} onRename={...} onDelete={...} />
        {/each}
      {/if}
    </div>
  </div>

  <!-- Footer -->
  <footer class="wp-editor-footer">
    <Btn variant="primary" disabled={saving} onclick={handleSave}>
      {saving ? 'Speichern…' : 'Speichern'}
    </Btn>
    <Btn variant="ghost" disabled={saving} onclick={handleCancel}>Abbrechen</Btn>
    {#if saveError}<span class="save-error">{saveError}</span>{/if}
  </footer>
</div>
```

**Mobile-Layout (≤899px) — CSS-Breakpoint, kein MobileShell-Wrapper:**
```svelte
<div class="wp-editor-mobile">
  <!-- TopAppBar mit Back-Button + Titel -->
  <header class="mobile-topbar">
    <Btn variant="ghost" size="icon-sm" onclick={handleCancel}>←</Btn>
    <h1>Wegpunkt-Editor</h1>
    <span><!-- Kebab-Placeholder --></span>
  </header>

  <!-- Etappen-Navigator -->
  <StageNavDropdown stages={localStages} activeStageId={activeStageId}
    onActivate={handleStageActivate} prev={prevStage} next={nextStage} />

  <!-- Vollbreite SVG-Karte -->
  <MapCanvas stage={activeStage} activeWaypointId={activeWaypointId}
    onWaypointActivate={...} responsive />

  <!-- Bottom-Sheet -->
  <Sheet bind:open={sheetOpen} snap="half">
    {#if !activeIsPause}
      <ProfileEditor stage={activeStage} arrivals={arrivals}
        onProfileAdd={handleProfileAdd} activeWaypointId={activeWaypointId} />
      {#if hasSuggested}
        <AISuggestionBar stage={activeStage} onAccept={handleAcceptSuggested}
          onReject={handleRejectSuggested} />
      {/if}
    {/if}
    {#each activeStage?.waypoints ?? [] as wp, i}
      <WaypointCard waypoint={wp} index={i} arrival={arrivals[i]}
        onConfirm={...} onReject={...} onRename={...} onDelete={...} />
    {/each}
  </Sheet>
</div>
```

### 2. `StageNavDropdown.svelte` (NEU, ~60 LoC)

Mobile Etappen-Navigator. Zeigt aktive Stage als `<Select>` Dropdown (Stage-Name + Etappen-Index)
flankiert von Prev/Next-Pfeil-Buttons.

**Props:**
```typescript
interface Props {
  stages: Stage[];
  activeStageId: string;
  prev: Stage | null;
  next: Stage | null;
  onActivate: (id: string) => void;
}
```

**Verhalten:**
- `<Select>` zeigt alle Stages als `<option value={s.id}>{i+1}. {s.name}</option>`
- `onchange` ruft `onActivate(selectedId)` auf
- Prev-Button: disabled wenn `prev === null`, onclick `onActivate(prev.id)`
- Next-Button: disabled wenn `next === null`, onclick `onActivate(next.id)`
- Aktive Stage-Zeile zeigt zusätzlich Stage-Index (`02` als Badge wie im Mockup)

### 3. `AISuggestionBar.svelte` (NEU, ~40 LoC)

Erscheint im Mobile-Bottom-Sheet wenn `hasSuggested === true`. Zeigt Infos zum ersten
`suggested`-Wegpunkt (Name, Höhe, ETA) und bietet zwei Buttons.

**Props:**
```typescript
interface Props {
  stage: Stage;
  onAccept: (waypointId: string) => void;
  onReject: (waypointId: string) => void;
}
```

**Verhalten:**
- `firstSuggested = stage.waypoints.find(w => w.suggested)`
- Zeigt: Name + Höhe + "KI-Vorschlag" Label + ETA aus computeArrivalTimes
- "KI-Vorschlag übernehmen" (Btn variant="primary"): ruft `onAccept(firstSuggested.id)` auf
- "Verwerfen" (Btn variant="ghost"): ruft `onReject(firstSuggested.id)` auf
- Nach Bestätigung/Verwerfung: `hasSuggested` wird false → Bar verschwindet reaktiv

### 4. `+page.svelte` (EDIT)

`TripEditView` durch `WaypointEditorPage` ersetzen. SSR-Loader (`+page.server.ts`) bleibt
unverändert — `trip`-Prop wird direkt weitergereicht.

```svelte
<!-- vorher -->
<TripEditView {trip} />

<!-- nachher -->
<WaypointEditorPage {trip} />
```

### 5. Styling

Ausschließlich `var(--g-*)` Design-Tokens. Keine Inline-Hex-Werte, keine Magic-Pixel.

Desktop-Layout-Proportionen:
- `.wp-editor-body`: `display: grid; grid-template-columns: 1fr 380px; gap: var(--g-space-4)`
- `.wp-editor-left`: MapCanvas-Höhe 300px, darunter ProfileEditor
- `.wp-editor-footer`: `display: flex; gap: var(--g-space-3); padding: var(--g-space-4); border-top: 1px solid var(--g-ink-faint)`

Mobile-Breakpoint: `@media (max-width: 899px)` — Desktop-Layout auf `display: none` setzen,
Mobile-Layout auf `display: flex flex-col`.

## Expected Behavior

- **Input:** `trip: Trip` mit `stages[]` (inkl. `waypoints[]`), `id`, `shortcode`, `name`
- **Output:**
  - Desktop: EtappenStrip oben + 2-Spalten-Body (Karte+Profil links, Wegpunkt-Sidebar rechts) + Speichern/Abbrechen Footer
  - Mobile: TopAppBar + StageNavDropdown + Vollbreite MapCanvas + Bottom-Sheet (Profil + KI-Bar + Wegpunkt-Liste)
- **Side effects:**
  - "Speichern": `api.put('/api/trips/{id}', {...trip, stages: stripSuggested(localStages)})` → `goto('/trips')`
  - "Abbrechen": `goto('/trips')` ohne API-Call
  - Waypoint-Callbacks (Confirm/Reject/Rename/Delete): mutieren `localStages` lokal (kein PUT bis Save)
  - `invalidateAll()` wird NICHT nach Save aufgerufen (User navigiert weg → kein Reload nötig)

## Acceptance Criteria

**AC-1:** Given die Route `/trips/[id]/edit` wird aufgerufen /
When die Seite auf Desktop (≥900px) lädt /
Then ist die TripEditView-Akkordeon-Maske nicht mehr sichtbar; stattdessen erscheint der EtappenStrip oben, die SVG-Karte links, das Höhenprofil-Panel darunter und die Wegpunkt-Sidebar rechts.

**AC-2:** Given der User befindet sich auf dem Edit-Screen auf Desktop /
When er auf eine Etappenkarte im EtappenStrip klickt /
Then aktualisieren sich Karte, Höhenprofil und Wegpunkt-Sidebar synchron auf die gewählte Etappe ohne Seitenneuladen.

**AC-3:** Given eine Etappe hat Wegpunkte mit `suggested: true` /
When der User auf Mobile (≤899px) den Edit-Screen öffnet /
Then erscheint im Bottom-Sheet über der Wegpunkt-Liste eine KI-Vorschlag-Bar mit "KI-Vorschlag übernehmen" (Primary) und "Verwerfen" (Ghost).

**AC-4:** Given der User klickt "KI-Vorschlag übernehmen" in der AISuggestionBar /
When der erste `suggested`-Wegpunkt bestätigt wird /
Then verschwindet die AISuggestionBar reaktiv (da `hasSuggested` danach `false` ist) und der Wegpunkt zeigt kein `suggested`-Flag mehr in der Liste.

**AC-5:** Given der User hat Wegpunkte lokal bearbeitet und klickt "Speichern" /
When der PUT-Call an `PUT /api/trips/{id}` abgesetzt wird /
Then enthält der Request-Body `stages` ohne `suggested`-Flags (`stripSuggested` angewendet), und nach Erfolg navigiert der Browser zu `/trips`.

**AC-6:** Given der Speichern-Vorgang läuft /
When `saving === true` /
Then ist der "Speichern"-Button disabled und zeigt den Text "Speichern…"; der "Abbrechen"-Button ist ebenfalls disabled — kein Doppel-Submit möglich.

**AC-7:** Given der PUT-Call schlägt mit einem Netzwerkfehler fehl /
When `saving` auf `false` zurückfällt /
Then zeigt der Footer eine lesbare Fehlermeldung (z.B. "Speichern fehlgeschlagen") neben den Buttons — der User kann erneut versuchen.

**AC-8:** Given der User klickt "Abbrechen" ohne gespeichert zu haben /
When `goto('/trips')` ausgeführt wird /
Then werden keine API-Calls abgesetzt; lokale Änderungen an `localStages` sind verworfen.

**AC-9:** Given die Route `/trips/[id]/edit` wird auf Mobile (≤899px) geöffnet /
When die Seite lädt /
Then zeigt die TopAppBar den Titel "Wegpunkt-Editor" mit einem Back-Button (←) links; der StageNavDropdown enthält ein `<select>`-Dropdown mit allen Etappennamen sowie Prev/Next-Pfeil-Buttons.

**AC-10:** Given eine Pausenetappe ist im StageNavDropdown ausgewählt /
When `activeIsPause === true` /
Then zeigt die Karte `PauseStageView` statt MapCanvas+ProfileEditor; die KI-Vorschlag-Bar erscheint nicht; die Sidebar zeigt "Pausentag" ohne Wegpunkt-Liste.

**AC-11:** Given der User navigiert via Prev/Next-Buttons im StageNavDropdown /
When er auf ">" (Next) klickt und eine nächste Etappe existiert /
Then wechselt `activeStageId` auf die nächste Etappe und Dropdown + Karte + Bottom-Sheet aktualisieren sich synchron; bei letzter Etappe ist der Next-Button disabled.

**AC-12:** Given die Edit-Seite wird geöffnet /
When der User nach Wetter-, Alarmregeln- oder Briefing-Einstellungen sucht /
Then findet er diese Sektionen nicht auf der Edit-Seite; die Akkordeon-Sektionen "Wetter", "Alarmregeln" und "Reports" existieren nicht mehr in dieser Route.

## Affected Files

| Datei | Änderung |
|-------|---------|
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | EDIT: `TripEditView` → `WaypointEditorPage` importieren und rendern |
| `frontend/src/lib/components/edit/WaypointEditorPage.svelte` | NEU — Haupt-Komponente (~220 LoC) |
| `frontend/src/lib/components/edit/StageNavDropdown.svelte` | NEU — Mobile Etappen-Navigator (~60 LoC) |
| `frontend/src/lib/components/edit/AISuggestionBar.svelte` | NEU — KI-Vorschlag-Bar Mobile (~40 LoC) |

Nicht geändert (nur wiederverwendet):
- `frontend/src/lib/components/trip-detail/WaypointsPanel.svelte`
- `frontend/src/lib/components/trip-detail/waypoints/*.svelte` (alle 6 Komponenten)
- `frontend/src/lib/components/mobile/Sheet.svelte`
- `frontend/src/routes/trips/[id]/edit/+page.server.ts`

## LoC Estimate

~320 LoC gesamt: `WaypointEditorPage` ~220, `StageNavDropdown` ~60, `AISuggestionBar` ~40.
`+page.svelte`-Änderung <5 LoC. LoC-Override auf 350 setzen.

## Known Limitations

- Die SVG-Karte (`MapCanvas`) ist eine Pseudo-Karte mit TopoBg-Hintergrund und Route-Polyline.
  Eine echte OSM/Leaflet-Karte ist explizit Out of Scope und folgt in einem separaten Issue.
- Der "Bearbeiten"-Button auf der Trip-Detail-Seite navigiert jetzt zum Wegpunkt-Editor —
  Wetter-/Alarm-/Briefing-Konfiguration ist ausschließlich über die Tab-Navigation der
  Trip-Detail-Seite erreichbar. Diese Vereinfachung ist PO-bestätigt (2026-05-27).
- `TripEditView.svelte` und die ehemaligen Akkordeon-Sektionen (`EditRouteSection`,
  `EditStagesPanelNew` etc.) bleiben vorerst als Dateien erhalten, werden aber nicht mehr
  von der Edit-Route eingebunden.

## Changelog

- 2026-05-27: Initial spec erstellt (Issue #407 — Vollbild-Wegpunkt-Editor für `/trips/[id]/edit`).
