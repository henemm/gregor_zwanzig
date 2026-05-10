---
entity_id: epic_136_step2_stages
type: module
created: 2026-05-09
updated: 2026-05-10
status: draft
version: "1.0"
parent_spec: epic_136_trip_wizard
related: epic_136_trip_wizard
issue: 162
tags: [sveltekit, frontend, wizard, step2, stages, gpx, dnd, epic-136]
---

# Epic 136 — Sub-Spec #162: Step 2 GPX-Multi-Upload + Drag-Sort + Pause

## Approval

- [ ] Approved

## Status

**Draft** — bereit zur Freigabe durch User.

## Purpose

Definiert das UI-Detail von Schritt 2 des Trip-Wizards (`Step2Stages.svelte` + neue `StageRow.svelte`):
Drop-Zone fuer Mehrfach-GPX-Upload, sortierbare Etappen-Liste via Drag-and-Drop (`svelte-dnd-action`),
"+ Pause"-Button zwischen Etappen (erscheint beim Hover), automatische T01/T02-Nummerierung und
Auto-Datierung (`startDate + index`) mit User-Override pro Etappe. Step 2 schreibt nur in
`WizardState.stages` — keine Persistenz, keine API-Trips-Calls. Wiederverwendung der bestehenden
GPX-Logik (`uploadGpx` aus `$lib/api.ts`, `naturalSort` aus `$lib/utils/naturalSort.ts`).

Zusaetzlich wird `WizardState` um vier neue Methoden + zwei neue Getter erweitert (additiv,
Master-Spec-Changelog), und der Shell-Refactor von #161 wird auf einen sauberen
`canAdvanceCurrent`-Switch-Getter konsolidiert (skaliert fuer Folge-Steps #163/#164).

## Source

- **Komponente (EDIT, Stub fuellen):** `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte`
- **Komponente (NEU):** `frontend/src/lib/components/trip-wizard/steps/StageRow.svelte`
- **State-Erweiterung (EDIT):** `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts`
- **Type-Erweiterung (EDIT):** `frontend/src/lib/types.ts` — `Stage.dateOverridden?: boolean` (transient)
- **Shell-Refactor (EDIT):** `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte`
- **Dependency (NEU):** `svelte-dnd-action` in `frontend/package.json`
- **Identifier:** `Step2Stages` (default export), `StageRow` (default export), `WizardState.canAdvanceStep2`, `WizardState.canAdvanceCurrent`, `WizardState.addPauseStageAt`, `WizardState.deleteStage`, `WizardState.recomputeStageDates`

## Verweis auf Master-Spec

Diese Sub-Spec ist eine Detail-Spezifikation der approved Master-Spec
[`docs/specs/modules/epic_136_trip_wizard.md`](./epic_136_trip_wizard.md). Konkret konsumiert sie:

- **§3.1 WizardState** — `stages`, `startDate` (gesetzt in Step 1), `addStage`, `addPauseStage`, `reorderStages`. Sub-Spec **erweitert** das Schema additiv um `canAdvanceStep2`, `canAdvanceCurrent`, `addPauseStageAt`, `deleteStage`, `recomputeStageDates` (Master-Spec-Changelog §12).
- **§3.2 Pausentag-Konvention** — Stage mit `waypoints.length === 0` ist ein Pausentag. KEIN neues Modell-Feld. UI-Logik via `isPauseStage()`.
- **§3.3 T-Nummerierung** — `formatStageNumber(index)` liefert T01/T02. Pausentage bekommen KEINE T-Nummer (UI-Entscheidung in dieser Sub-Spec, §5).
- **§4 Vertraege Master-Spec ↔ Sub-Specs** — Schema-Erweiterung erfolgt mit Master-Spec-Changelog-Eintrag (siehe §12).

Vorgaenger-Sub-Specs:
- [`epic_136_step0_shell.md`](./epic_136_step0_shell.md) (#160, Shell + Stepper)
- [`epic_136_step1_profile.md`](./epic_136_step1_profile.md) (#161, Profil + Eckdaten — Pattern fuer `canAdvanceStepN` + Shell-Edit-Pattern + `fillStepN`-Helper)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WizardState` (Master-Spec §3.1) | class | Single Source of Truth fuer Stages und Step-Validation |
| `wizardState.svelte.ts` | file (edit) | 5 neue Methoden/Getter |
| `wizardHelpers.ts` | file | `isPauseStage`, `formatStageNumber`, `addDays`, `newId` |
| `frontend/src/lib/api.ts` | file | `uploadGpx(file, stageDate, startHour): Promise<Stage>` Z. 27–50, ruft `POST /api/gpx/parse` |
| `frontend/src/lib/utils/naturalSort.ts` | file | `naturalSort<T>(arr, key)` fuer Datei-Reihenfolge |
| `TripWizardShell.svelte` | file (edit) | Refactor zu `disabled={!state.canAdvanceCurrent}` |
| `frontend/src/lib/types.ts` | file (edit) | `Stage.dateOverridden?: boolean` transient |
| `$lib/components/ui/btn/Btn.svelte` | component (Epic #133) | "X Etappen anlegen", "+ Pause", Delete-Btn |
| `$lib/components/ui/g-card/GCard.svelte` | component (Epic #133) | Drop-Zone-Container |
| `$lib/components/ui/pill/Pill.svelte` | component (Epic #133) | T01-Anzeige in `StageRow` |
| `$lib/components/ui/eyebrow/Eyebrow.svelte` | component (Epic #133) | Abschnitts-Eyebrows |
| `$lib/components/ui/input/input.svelte` | component (Epic #133) | Datumspicker, Stage-Date-Override |
| `@lucide/svelte` | NPM | Icons `GripVertical` (Drag-Handle), `Trash2` (Delete), `Upload` (Drop-Zone), `Plus` (Pause) |
| `svelte-dnd-action` | NPM (NEU) | Drag-and-Drop fuer sortierbare Etappen-Liste |
| `svelte` (`getContext`) | api | State-Konsum |
| `frontend/e2e/helpers.ts` | file (edit) | `fillStep2`-Helper |
| `frontend/e2e/fixtures/test-trip.gpx` | file (NEU) | E2E-Fixture mit minimalem GPX-Track |

## Implementation Details

### 1. Layout-Wireframe

```
┌────────────────────────────────────────────────────────────────────────┐
│ Eyebrow: „GPX-Dateien"                                                 │
│                                                                        │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │  ⬆ Drag GPX-Dateien hierher oder klicken zum Auswaehlen           │ │
│ │  (Mehrfach-Auswahl moeglich)                                       │ │
│ │                                                                    │ │
│ │  [Hidden <input type="file" multiple accept=".gpx">]               │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│ Wenn pendingFiles.length > 0:                                          │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ N Dateien bereit:  KHW_00.gpx, KHW_01.gpx, KHW_02.gpx              │ │
│ │ Startdatum: [2026-06-01 ▼]                                          │ │
│ │ [N Etappen anlegen]                                                │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│ Eyebrow: „Etappen ({stages.length})"                                   │
│                                                                        │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ ⋮⋮ [T01] 2026-06-01  Stubai-Etappe-1                  [🗑]         │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│         ───────── + Pause einfuegen ─────────  (sichtbar bei Hover)    │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ ⋮⋮ [T02] 2026-06-02  Stubai-Etappe-2                  [🗑]         │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│         ───────── + Pause einfuegen ─────────                          │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ ⋮⋮      2026-06-03  Pausentag                          [🗑]         │ │  ← keine T-Nummer
│ └────────────────────────────────────────────────────────────────────┘ │
│         ───────── + Pause einfuegen ─────────                          │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ ⋮⋮ [T03] 2026-06-04  Stubai-Etappe-3                  [🗑]         │ │
│ └────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

Container nutzt `flex flex-col gap-6`. Drop-Zone ist `<GCard>` mit dashed-Border + Akzent bei `dragover`. Etappen-Liste ist `<div use:dndzone>` mit `flip()`-Animation.

### 2. Datenmodell-Erweiterung — `Stage.dateOverridden`

`frontend/src/lib/types.ts`:

```typescript
export interface Stage {
  id: string;
  name: string;
  date: string;
  waypoints: Waypoint[];
  start_time?: string;
  /**
   * Transientes Frontend-Flag (Wizard-Step 2): true wenn der User das
   * Datum manuell ueberschrieben hat. Verhindert, dass Auto-Re-Date
   * (z.B. nach Reorder oder Pause-Insert) die User-Eingabe ueberschreibt.
   * Wird beim Save (Step 4) gestrippt — analog `Waypoint.suggested`.
   */
  dateOverridden?: boolean;
}
```

**Save-Pipeline-Anpassung (§1.4 Master-Spec):** `WizardState.toTripPayload()` strippt `dateOverridden` aus jedem Stage analog zu `suggested` bei Waypoints. Implementierung in `cleanedStages`-Mapping:

```typescript
const cleanedStages: Stage[] = this.stages.map((stage) => {
  const { dateOverridden: _ignored, ...rest } = stage;
  return {
    ...rest,
    waypoints: stage.waypoints.map((wp) => stripSuggested(wp))
  };
});
```

### 3. WizardState-Erweiterungen

#### 3.1 `canAdvanceStep2`-Getter (additiv)

```typescript
get canAdvanceStep2(): boolean {
  return this.stages.length > 0;
}
```

Pflicht: mindestens eine Etappe (kann auch ein Pausentag sein — Edge-Case bewusst akzeptiert; falls User „Trip ohne Tour" anlegen will, soll er das duerfen).

#### 3.2 `canAdvanceCurrent`-Switch-Getter (Refactor)

```typescript
get canAdvanceCurrent(): boolean {
  switch (this.currentStep) {
    case 1: return this.canAdvanceStep1;
    case 2: return this.canAdvanceStep2;
    case 3: return true;  // bis #163
    case 4: return true;  // bis #164
  }
}
```

Begruendung: verschachteltes Ternary in `TripWizardShell.svelte` skaliert nicht. Switch-Getter ist sauber, additive Erweiterung. Folge-Steps #163/#164 ergaenzen `canAdvanceStep3/4` und ersetzen die `true`-Defaults.

#### 3.3 `addPauseStageAt(afterIndex: number)` (NEU)

```typescript
addPauseStageAt(afterIndex: number): void {
  const pause: Stage = {
    id: newId(),
    name: 'Pause',
    date: '',
    waypoints: []
  };
  // Nach gegebenem Index einfuegen (afterIndex === -1 fuegt am Anfang ein):
  this.stages = [
    ...this.stages.slice(0, afterIndex + 1),
    pause,
    ...this.stages.slice(afterIndex + 1)
  ];
  this.recomputeStageDates();
}
```

Bestehende `addPauseStage()`-Methode bleibt erhalten (fuegt am Ende an); `addPauseStageAt` ist die positionierte Variante.

#### 3.4 `deleteStage(id: string)` (NEU)

```typescript
deleteStage(id: string): void {
  this.stages = this.stages.filter((s) => s.id !== id);
  this.recomputeStageDates();
}
```

Erlaubt Loeschen einer Etappe per Klick auf Trash-Button. Re-Date danach.

#### 3.5 `recomputeStageDates()` (NEU)

```typescript
recomputeStageDates(): void {
  if (!this.startDate) return;
  this.stages = this.stages.map((stage, i) => {
    if (stage.dateOverridden) return stage;  // User-Override schuetzen
    return { ...stage, date: addDays(this.startDate!, i) };
  });
}
```

Wird aufgerufen aus:
- `addStage` (im Step-2-Upload-Flow nach jedem `state.addStage(stage)`)
- `addPauseStageAt`
- `deleteStage`
- `reorderStages` (PATCH: Methode wird erweitert um `this.recomputeStageDates()` am Ende)
- DnD-Reorder-Handler in `Step2Stages.svelte`

**Wichtig:** `addStage` selbst ruft `recomputeStageDates` NICHT direkt auf — sonst wuerde jede Upload-Iteration alle vorherigen Stages re-daten. Der Step-2-Upload-Flow (`commitPending`) ruft `recomputeStageDates` einmal nach Abschluss aller Uploads auf.

### 4. Drop-Zone (Multi-Upload + Datumspicker + Commit)

```svelte
<script lang="ts">
  import { naturalSort } from '$lib/utils/naturalSort';
  import { uploadGpx } from '$lib/api';
  import { addDays } from '../wizardHelpers';

  let pendingFiles = $state<File[]>([]);
  let bulkStartDate = $state<string>('');
  let dragOver = $state(false);
  let uploading = $state(false);

  // bulkStartDate-Default: state.startDate + (stages.length) Tage
  $effect(() => {
    if (state.startDate && pendingFiles.length > 0 && !bulkStartDate) {
      bulkStartDate = addDays(state.startDate, state.stages.length);
    }
  });

  function handleFileSelect(files: FileList | null) {
    if (!files) return;
    const gpx = Array.from(files).filter((f) =>
      f.name.toLowerCase().endsWith('.gpx')
    );
    pendingFiles = [...pendingFiles, ...gpx];
  }

  async function commitPending() {
    if (pendingFiles.length === 0 || !bulkStartDate) return;
    uploading = true;
    const sorted = naturalSort(pendingFiles, (f) => f.name);
    for (let i = 0; i < sorted.length; i++) {
      const file = sorted[i];
      const stageDate = addDays(bulkStartDate, i);
      try {
        const stage = await uploadGpx(file, stageDate, 8);
        state.addStage(stage);
      } catch (err) {
        console.error(`GPX-Upload fehlgeschlagen: ${file.name}`, err);
        // Spec: Skip + warning; valide Stages weiter anlegen.
      }
    }
    pendingFiles = [];
    bulkStartDate = '';
    state.recomputeStageDates();  // Auto-Date konsistent halten
    uploading = false;
  }
</script>

<div
  data-testid="trip-wizard-step2-dropzone"
  role="button"
  tabindex="0"
  class:drag-over={dragOver}
  ondrop={(e) => { e.preventDefault(); dragOver = false; handleFileSelect(e.dataTransfer?.files); }}
  ondragover={(e) => { e.preventDefault(); dragOver = true; }}
  ondragleave={() => (dragOver = false)}
  onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.click(); }}
>
  <input
    bind:this={fileInputRef}
    type="file"
    multiple
    accept=".gpx"
    class="hidden"
    data-testid="trip-wizard-step2-file-input"
    onchange={(e) => handleFileSelect((e.target as HTMLInputElement).files)}
  />
  <span>Drag GPX-Dateien hierher oder klicken zum Auswaehlen</span>
</div>

{#if pendingFiles.length > 0}
  <div data-testid="trip-wizard-step2-pending">
    <p>{pendingFiles.length} Dateien bereit: {pendingFiles.map(f => f.name).join(', ')}</p>
    <Input type="date" bind:value={bulkStartDate} data-testid="trip-wizard-step2-bulk-startdate" />
    <Btn onclick={commitPending} disabled={uploading} data-testid="trip-wizard-step2-commit">
      {pendingFiles.length} Etappen anlegen
    </Btn>
  </div>
{/if}
```

**Validation:** `accept=".gpx"` filtert im File-Picker, `handleFileSelect` filtert per Suffix-Check beim Drop. Backend (`POST /api/gpx/parse`) hat eigene Validation.

### 5. `StageRow.svelte`

```svelte
<script lang="ts">
  import { Pill } from '$lib/components/ui/pill';
  import { Btn } from '$lib/components/ui/btn';
  import { GripVertical, Trash2 } from '@lucide/svelte';
  import { formatStageNumber, isPauseStage } from '../wizardHelpers';
  import type { Stage } from '$lib/types';

  interface Props {
    stage: Stage;
    index: number;
    /** Index innerhalb NICHT-Pause-Stages — fuer T-Nummern-Berechnung. */
    nonPauseIndex: number | null;
    onDateChange: (id: string, newDate: string) => void;
    onDelete: (id: string) => void;
  }
  let { stage, index, nonPauseIndex, onDateChange, onDelete }: Props = $props();

  function handleDateInput(e: Event) {
    const newDate = (e.target as HTMLInputElement).value;
    onDateChange(stage.id, newDate);
  }
</script>

<div
  data-testid={`trip-wizard-step2-stage-row-${index}`}
  data-stage-id={stage.id}
  class="flex items-center gap-3 p-3 rounded border border-[var(--g-ink-faint)]/30"
>
  <span class="cursor-grab" data-testid={`trip-wizard-step2-drag-handle-${index}`}>
    <GripVertical size={18} aria-label="Verschieben" />
  </span>

  {#if isPauseStage(stage)}
    <span class="text-[var(--g-ink-faint)] italic" data-testid={`trip-wizard-step2-pause-marker-${index}`}>
      Pausentag
    </span>
  {:else if nonPauseIndex !== null}
    <Pill tone="default" data-testid={`trip-wizard-step2-stage-pill-${index}`}>
      {formatStageNumber(nonPauseIndex)}
    </Pill>
  {/if}

  <input
    type="date"
    value={stage.date}
    oninput={handleDateInput}
    data-testid={`trip-wizard-step2-stage-date-${index}`}
    class="text-sm"
  />

  <span class="flex-1 truncate">{stage.name}</span>

  <Btn
    variant="ghost"
    size="sm"
    onclick={() => onDelete(stage.id)}
    data-testid={`trip-wizard-step2-stage-delete-${index}`}
  >
    <Trash2 size={16} aria-label="Etappe loeschen" />
  </Btn>
</div>
```

**T-Nummer fuer Nicht-Pause-Stages:** Pausentage bekommen keine T-Nummer (Master-Spec §3.3 sagt das explizit). Step2Stages berechnet `nonPauseIndex` einmal pro Render durch Filtern: jede Nicht-Pause-Etappe bekommt ihren Index in der Liste der Nicht-Pause-Etappen.

```typescript
// in Step2Stages.svelte:
$: nonPauseIndices = state.stages.map((s, i) =>
  isPauseStage(s) ? null : state.stages.slice(0, i + 1).filter(x => !isPauseStage(x)).length - 1
);
```

### 6. `svelte-dnd-action`-Verkabelung

Installation: `npm install svelte-dnd-action` im `frontend/`. Bundle-Impact ~2 KB.

```svelte
<script lang="ts">
  import { dndzone, type DndEvent } from 'svelte-dnd-action';
  import { flip } from 'svelte/animate';

  function handleSort(e: CustomEvent<DndEvent<Stage>>) {
    state.stages = e.detail.items;
    if (e.type === 'finalize') {
      state.recomputeStageDates();  // Auto-Date nach Reorder
    }
  }
</script>

<div
  use:dndzone={{ items: state.stages, flipDurationMs: 200, type: 'stages' }}
  onconsider={handleSort}
  onfinalize={handleSort}
  data-testid="trip-wizard-step2-stages-list"
>
  {#each state.stages as stage, i (stage.id)}
    <div animate:flip={{ duration: 200 }}>
      <StageRow
        {stage}
        index={i}
        nonPauseIndex={nonPauseIndices[i]}
        onDateChange={handleDateChange}
        onDelete={(id) => state.deleteStage(id)}
      />
    </div>
  {/each}
</div>
```

**A11y-Hinweis:** `svelte-dnd-action` rendert Elemente mit `aria-grabbed` und akzeptiert Tastatur-Reorder (Space + Pfeiltasten). Sub-Spec verlaesst sich auf Lib-Default; eigene a11y-Erweiterungen sind nicht in Scope.

### 7. Pause-Insertion (Hover-Button)

Zwischen je zwei `StageRow`s wird ein Inserter gerendert. Beim Hover ueber den Bereich (oder Tastatur-Fokus) erscheint der Button:

```svelte
<div class="pause-inserter" data-testid={`trip-wizard-step2-pause-after-${i}`}>
  <button
    type="button"
    class="opacity-0 hover:opacity-100 focus-visible:opacity-100 transition-opacity"
    onclick={() => state.addPauseStageAt(i)}
    aria-label={`Pausentag nach Etappe ${i + 1} einfuegen`}
  >
    + Pause einfuegen
  </button>
</div>
```

Layout: `display: flex; justify-content: center; height: 1.5rem; border-bottom: dashed`. Hover-Detection auf dem Container (nicht nur auf dem Button) damit User die Maus zum Button hinbewegen kann.

### 8. Auto-Datierung mit User-Override

**Initial-Zuweisung:** Beim Upload via `commitPending()` schreibt `uploadGpx` `stage.date = stageDate` (also `bulkStartDate + i`). `dateOverridden` ist initial `false`.

**Auto-Re-Date:** `recomputeStageDates()` wird aufgerufen aus den 4 Mutations-Methoden (§3.5). Setzt `stage.date = addDays(state.startDate, i)` NUR wenn `stage.dateOverridden !== true`.

**User-Override:** Klickt User in das Date-Input einer StageRow und aendert das Datum, wird `state.stages[i].dateOverridden = true` gesetzt. Beispiel:

```typescript
function handleDateChange(id: string, newDate: string): void {
  state.stages = state.stages.map((s) =>
    s.id === id ? { ...s, date: newDate, dateOverridden: true } : s
  );
}
```

**Reset des Override:** Nicht in dieser Sub-Spec — User kann Override nicht zurueckziehen. Workaround: Etappe loeschen und neu hinzufuegen (Auto-Date greift). Akzeptabel; spaeteres Issue koennte einen Reset-Button ergaenzen.

### 9. Shell-Refactor (`disabled={!state.canAdvanceCurrent}`)

`TripWizardShell.svelte` Z. 121–134 (heute):

```svelte
<Btn
  data-testid="trip-wizard-next"
  variant="accent"
  size="md"
  onclick={handleNext}
  disabled={state.currentStep === 1 ? !state.canAdvanceStep1 : false}
>
  Weiter
</Btn>
```

Wird zu:

```svelte
<Btn
  data-testid="trip-wizard-next"
  variant="accent"
  size="md"
  onclick={handleNext}
  disabled={!state.canAdvanceCurrent}
>
  Weiter
</Btn>
```

### 10. TestID-Inventar

| TestID | Komponente | Zweck |
|--------|------------|-------|
| `trip-wizard-step2-stages` | Step-Container | Bereits aus #160 |
| `trip-wizard-step2-dropzone` | Drop-Zone | Drag/Drop + Klick |
| `trip-wizard-step2-file-input` | File-Input | Hidden, fuer programmatic upload in E2E |
| `trip-wizard-step2-pending` | Pending-Files-Region | Sichtbar wenn Files ausgewaehlt |
| `trip-wizard-step2-bulk-startdate` | Date-Input | Datum fuer Batch-Upload |
| `trip-wizard-step2-commit` | Commit-Btn | "X Etappen anlegen" |
| `trip-wizard-step2-stages-list` | DnD-Container | Sortierbare Liste |
| `trip-wizard-step2-stage-row-{i}` | StageRow | Einzelne Etappe |
| `trip-wizard-step2-stage-pill-{i}` | T-Pill | T01/T02 (nur Nicht-Pause) |
| `trip-wizard-step2-stage-date-{i}` | Date-Input pro Row | Override |
| `trip-wizard-step2-stage-delete-{i}` | Delete-Btn pro Row | Loeschen |
| `trip-wizard-step2-drag-handle-{i}` | Drag-Handle | DnD-Grab-Element |
| `trip-wizard-step2-pause-marker-{i}` | Pause-Label | Anzeige "Pausentag" |
| `trip-wizard-step2-pause-after-{i}` | Pause-Inserter | "+ Pause einfuegen" |

### 11. E2E-Helper `fillStep2` + Test-GPX-Fixture

#### 11.1 Test-GPX-Fixture

Datei `frontend/e2e/fixtures/test-trip.gpx`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="gregor-test" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>Test-Etappe</name>
    <trkseg>
      <trkpt lat="47.0500" lon="11.4500"><ele>1800</ele><time>2026-06-01T08:00:00Z</time></trkpt>
      <trkpt lat="47.0510" lon="11.4520"><ele>1850</ele><time>2026-06-01T08:30:00Z</time></trkpt>
      <trkpt lat="47.0520" lon="11.4540"><ele>1900</ele><time>2026-06-01T09:00:00Z</time></trkpt>
    </trkseg>
  </trk>
</gpx>
```

Minimale GPX, parsebar von Backend. Wird in E2E-Tests via Playwright `setInputFiles` hochgeladen.

#### 11.2 `fillStep2`-Helper

```typescript
// frontend/e2e/helpers.ts
import path from 'node:path';
import type { Page } from '@playwright/test';

const FIXTURE_DIR = path.resolve('./e2e/fixtures');

export interface Step2Input {
  files?: string[];                 // absolute Pfade; default: ['test-trip.gpx']
  bulkStartDate?: string;           // 'YYYY-MM-DD'; default: aus state.startDate
}

export async function fillStep2(page: Page, input: Step2Input = {}): Promise<void> {
  const files = (input.files ?? ['test-trip.gpx']).map((f) => path.join(FIXTURE_DIR, f));
  await page.getByTestId('trip-wizard-step2-file-input').setInputFiles(files);
  if (input.bulkStartDate) {
    await page.getByTestId('trip-wizard-step2-bulk-startdate').fill(input.bulkStartDate);
  }
  await page.getByTestId('trip-wizard-step2-commit').click();
  // Warten bis mindestens eine Stage-Row gerendert ist:
  await page.getByTestId('trip-wizard-step2-stage-row-0').waitFor({ state: 'visible' });
}
```

#### 11.3 Migration `trip-wizard-shell.spec.ts` AC#5a

AC#5a wird erneut anpassen — Step 2 ist jetzt initial disabled (`stages.length === 0`):

```typescript
test('AC#5a: Weiter-Button initial disabled, nach Step 1+2 enabled in Step 3', async ({ page }) => {
  await page.goto('/trips/new');
  await expect(page.getByTestId('trip-wizard-next')).toBeDisabled();
  await fillStep1(page, DEFAULT_STEP1);
  await expect(page.getByTestId('trip-wizard-next')).toBeEnabled();
  await page.getByTestId('trip-wizard-next').click();  // → Step 2
  await expect(page.getByTestId('trip-wizard-next')).toBeDisabled();
  await fillStep2(page);
  await expect(page.getByTestId('trip-wizard-next')).toBeEnabled();
  await page.getByTestId('trip-wizard-next').click();  // → Step 3
  await expect(page.getByTestId('trip-wizard-next')).toBeEnabled();  // Step 3+4: noch keine canAdvance-Flags
});
```

Andere Tests (AC#8 Step 4, AC#11 alle Containers): durchnavigieren mit `fillStep1` + `fillStep2`, dann `next.click()`-Sequenz. Tests die nur Stepper-Animation pruefen (AC#3+4) bleiben unangetastet.

### 12. Master-Spec-Changelog-Eintrag

`docs/specs/modules/epic_136_trip_wizard.md` erhaelt einen neuen Changelog-Eintrag (kein Approval-Reset, weil rein additive `WizardState`-Erweiterungen):

```markdown
- 2026-05-10: §3.1 erweitert um additive Methoden/Getter (Sub-Spec #162):
  `get canAdvanceStep2(): boolean` (Pflicht: stages.length > 0),
  `get canAdvanceCurrent(): boolean` (Switch ueber currentStep — konsolidiert
  Shell-disabled-Pattern aus #161), `addPauseStageAt(afterIndex)`,
  `deleteStage(id)`, `recomputeStageDates()`. Plus `Stage.dateOverridden?: boolean`
  als transientes Frontend-Flag (gestrippt in `toTripPayload`, analog
  `Waypoint.suggested`). Detail in Sub-Spec
  [`epic_136_step2_stages.md`](./epic_136_step2_stages.md).
```

## Expected Behavior

- **Input:** User in Step 2 nach `nextStep()` aus Step 1.
- **Output:**
  - Drop-Zone sichtbar mit Hinweistext, Tastatur- und Maus-bedienbar.
  - Bei Drag/Drop oder File-Picker-Auswahl: ausgewaehlte GPX-Files werden in `pendingFiles` gepuffert; nicht-GPX-Dateien werden gefiltert.
  - „N Etappen anlegen"-Button mit Datumspicker (Default: `state.startDate + state.stages.length` Tage).
  - Klick auf Commit: Files werden naturalSort-iert, sequenziell via `uploadGpx` zu Stages konvertiert, in `state.stages` angehaengt; Datum-Propagation +1 pro File ab `bulkStartDate`. Fehler-Files werden geloggt + ueberspringen, valide laufen weiter.
  - Etappen-Liste ist via Drag-Handle sortierbar (`svelte-dnd-action`); Reorder loest Auto-Re-Date aus (Override geschuetzt).
  - "+ Pause einfuegen"-Button erscheint zwischen Rows beim Hover/Fokus; Klick fuegt Pausentag ein, danach Auto-Re-Date.
  - User kann pro Etappe das Datum manuell ueberschreiben (Date-Input), Override wird in `state.stages[i].dateOverridden = true` markiert und vor Auto-Re-Date geschuetzt.
  - Trash-Button pro Etappe loescht; Auto-Re-Date danach.
  - Pausentage zeigen statt T-Nummer den Text „Pausentag"; Etappen-Namen kommen aus GPX (`Track.name` oder Dateiname-Fallback im Backend).
  - Weiter-Button im Footer ist disabled solange `state.stages.length === 0`; nach Upload mindestens einer Etappe enabled.
- **Side effects:**
  - State-Mutationen: `state.stages` (add, reorder, delete, re-date), kein API-Save in Step 2.
  - `uploadGpx` macht `POST /api/gpx/parse` pro File (sequentiell).
  - Keine Persistenz vor Step 4.

## Acceptance Criteria

| # | Kriterium | Pruefung |
|---|-----------|----------|
| 1 | `Step2Stages.svelte` rendert Drop-Zone mit TestID `trip-wizard-step2-dropzone` | E2E |
| 2 | Drop-Zone akzeptiert Drag-Drop von GPX-Files (filtert non-GPX clientseitig) | E2E (mit nicht-GPX-File: `pendingFiles.length === 0`) |
| 3 | Drop-Zone akzeptiert File-Picker-Auswahl (Klick + Multi-Select) | E2E (`setInputFiles`) |
| 4 | Drop-Zone ist tastatur-bedienbar (Enter/Space oeffnet File-Picker) | E2E (`page.keyboard.press('Enter')`) |
| 5 | Bei `pendingFiles.length > 0` erscheint Datumspicker + „X Etappen anlegen"-Button | E2E |
| 6 | `bulkStartDate`-Default ist `state.startDate + state.stages.length` Tage | E2E (laden Step 1 mit startDate `2026-06-01`, in Step 2 zu erwarten: `2026-06-01`) |
| 7 | Klick auf Commit: Files werden `naturalSort`-iert (`KHW_00a` vor `KHW_10`), sequenziell hochgeladen, Stages in `state.stages` | E2E (3 Files mit unterschiedlichen Namen, Reihenfolge pruefen) |
| 8 | Bei Fehler in einem Upload (HTTP 400 vom Backend): valide Stages werden trotzdem angelegt | E2E mit kaputtem GPX (Backend liefert 400) |
| 9 | Etappen-Liste rendert StageRows mit TestIDs `trip-wizard-step2-stage-row-{i}` | E2E |
| 10 | Nicht-Pause-StageRow zeigt T-Pill mit `formatStageNumber(nonPauseIndex)` | E2E (nach Upload von 2 Files: T01, T02) |
| 11 | Pause-StageRow zeigt „Pausentag"-Text statt T-Pill | E2E (nach `addPauseStageAt`: row.text contains "Pausentag", keine Pill) |
| 12 | Drag-Handle pro Row hat TestID `trip-wizard-step2-drag-handle-{i}`; Drag-Drop reordert | E2E (use `dragTo`); state.stages-Order updated |
| 13 | "+ Pause"-Button erscheint zwischen Rows; Klick fuegt Pausentag an position `afterIndex` | E2E |
| 14 | "+ Pause"-Button ist initial unsichtbar (opacity 0); bei Hover/Focus opacity 1 | E2E (CSS-Check via `evaluate`) |
| 15 | Trash-Button loescht Etappe; danach passt T-Nummerierung sich an | E2E (3 Stages, T02 loeschen → T01 + T02 statt T01 + T03) |
| 16 | Auto-Datum: 1. Stage = startDate, 2. Stage = startDate+1, etc. | E2E nach Upload + `recomputeStageDates` |
| 17 | Reorder via DnD loest Auto-Re-Date aus | E2E (drag T03 vor T01 → neue Reihenfolge mit aufsteigenden Datumswerten) |
| 18 | Pause-Insert verschiebt nachfolgende Daten +1 Tag | E2E |
| 19 | User-Override: manuelles Datum-Aendern setzt `dateOverridden=true`; spaetere Re-Dates ueberschreiben es nicht | E2E (Override + Reorder + check) |
| 20 | Initial in Step 2 ist Weiter-Button disabled | E2E |
| 21 | Nach Upload mindestens einer Etappe ist Weiter-Button enabled | E2E |
| 22 | `state.canAdvanceStep2` ist `true` gdw `stages.length > 0` | Unit-Test (3 Cases: 0 / 1 / mehrere) |
| 23 | `state.canAdvanceCurrent` reagiert korrekt auf `currentStep`-Wechsel | Unit-Test (Switch-Cases 1–4) |
| 24 | `addPauseStageAt(afterIndex)` fuegt Pause an korrekter Stelle ein | Unit-Test |
| 25 | `deleteStage(id)` entfernt Stage und ruft `recomputeStageDates` | Unit-Test |
| 26 | `recomputeStageDates` schuetzt Stages mit `dateOverridden=true` | Unit-Test |
| 27 | `WizardState.toTripPayload()` strippt `dateOverridden` aus jedem Stage | Unit-Test (Stage mit `dateOverridden=true` → Payload-Stage hat das Feld nicht) |
| 28 | `TripWizardShell.svelte` nutzt `state.canAdvanceCurrent` (kein verschachteltes Ternary mehr) | Code-Inspektion + Grep |
| 29 | Master-Spec hat neuen Changelog-Eintrag fuer Step-2-Erweiterungen | Grep |
| 30 | `npm run check` und `npm run build` im `frontend/` gruen | CI-Output |
| 31 | Bestehende `trip-wizard-shell.spec.ts`-Tests AC#5a, AC#8, AC#11 sind via `fillStep1` + `fillStep2` migriert; keine Test-Coverage geht verloren | Test-Run gruen |

## Datei-Liste

### NEU

| Datei | Zweck | LoC (Schaetzung) |
|-------|-------|------------------|
| `frontend/src/lib/components/trip-wizard/steps/StageRow.svelte` | Etappen-Row-Komponente | ~80 |
| `frontend/src/lib/components/trip-wizard/__tests__/Step2Stages.test.ts` | Optional, falls Plain-Node testbar — sonst nur E2E | ~40 |
| `frontend/e2e/trip-wizard-step2.spec.ts` | E2E-Tests AC #1–#21 | ~180 |
| `frontend/e2e/fixtures/test-trip.gpx` | Minimale GPX-Test-Fixture | ~15 |

### EDIT

| Datei | Aenderung | LoC |
|-------|-----------|-----|
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | Stub gefuellt: Drop-Zone, Pending-UI, DnD-Liste, Pause-Inserter | ~150 |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | 5 neue Methoden/Getter + Save-Pipeline-Anpassung (`dateOverridden` strippen) | +60 |
| `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` | ~12 neue Test-Cases fuer Step-2-Methoden + canAdvanceCurrent + dateOverridden-Strip | +90 |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | `disabled={!state.canAdvanceCurrent}` Refactor | -1 / +1 |
| `frontend/src/lib/types.ts` | `Stage.dateOverridden?: boolean` (transient) mit Doc-Kommentar | +8 |
| `frontend/e2e/helpers.ts` | `fillStep2`-Helper + `Step2Input`-Typ | +30 |
| `frontend/e2e/trip-wizard-shell.spec.ts` | AC#5a, AC#8, AC#11 migriert | ~10 |
| `frontend/package.json` | `svelte-dnd-action`-Dependency | +1 |
| `frontend/package-lock.json` | Lockfile-Update | (auto) |
| `docs/specs/modules/epic_136_trip_wizard.md` | Master-Spec Changelog | +8 |

### NICHT BERUEHRT

- `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` (alle benoetigten Helper sind da)
- `frontend/src/lib/api.ts` (uploadGpx unveraendert)
- `frontend/src/lib/utils/naturalSort.ts` (unveraendert)
- `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` / `Step3Waypoints.svelte` / `Step4Briefings.svelte`
- `internal/`, `src/`, `cmd/` (kein Backend-Touch)

## Known Limitations

- **`recomputeStageDates` setzt KEINEN `start_time`** — `Stage.start_time` bleibt `undefined`, wird nicht aus `recomputeStageDates` geschrieben. Falls spaeter `start_time` Auto-Date-bezogen sein soll, eigenes Issue.
- **User-Override-Reset nicht moeglich.** Wer aus Versehen ein Datum manuell aendert und Auto-Date wiederhaben will, muss die Etappe loeschen + neu hinzufuegen. Reset-Button ist ausserhalb Scope.
- **Backend-Validation des GPX** kann auch valide Files ablehnen (z.B. fehlende `<trkpt>`-Elemente). UI zeigt Konsolen-Warnung; kein User-facing Error-Message in dieser Sub-Spec — Folge-Issue koennte das verbessern (Toast-Notify).
- **Mobile-Responsive nicht explizit** — `max-w-3xl` Wrapper aus Shell, StageRow ist `flex` (kann auf schmal-viewports unschoen umbrechen). Mobile-Optimierung ist Folge-Issue.
- **Keine Multi-Pause-zwischen-zwei-Etappen-Logik.** User kann zwischen T01 und T02 zwei Pausen einfuegen (klickt 2x Pause). System macht das, aber die UX ist nicht spezifiziert; akzeptabel.
- **Kein Undo/Redo** — Loeschen einer Etappe ist sofort dauerhaft (im State). User muss neu hochladen. Folge-Issue.
- **`bulkStartDate`-Auto-Default kann verwirren** — der Datumspicker zeigt automatisch `state.startDate + state.stages.length`. Wenn User bereits 3 Etappen hat und 2 weitere Files hochlaedt, zeigt der Picker den Tag NACH der letzten Etappe. Falls User stattdessen die ersten Tage neu uploaden will (3 alte Etappen vorher loeschen), muss er den Datumspicker manuell setzen. Akzeptabel.
- **`svelte-dnd-action` ist eine neue Dependency** — Maintenance-Surface erhoeht. Lib ist gut gewartet (>2k Stars, regelmaessige Updates). User-Entscheidung, akzeptiert.
- **Keine Auto-Save** — wenn User Browser schliesst zwischen Step 2 und Step 4, gehen alle Stages verloren. Folge-Issue (z.B. localStorage-Persistenz).
- **Test-GPX-Fixture deckt nur Happy-Path** — keine Variante mit fehlerhaftem GPX. Tests fuer AC#8 (Fehler-Skip) muessten ein zweites Fixture-File haben oder mocking nutzen. Sub-Spec verweist auf manuelle Verifikation.
- **`dateOverridden`-Flag ist nur Frontend-only.** Bei Reload (Wizard nochmal oeffnen) wuerde es verloren — aber Step 2 hat ohnehin keine Persistenz vor Save, daher kein praktisches Problem.
- **Inline-`dndzone`-Action** — bei Server-Side-Rendering koennte `svelte-dnd-action` Warnings produzieren (DOM-Apis ohne Browser). Pragmatisch via `if (browser)` einklammern, falls noetig. Phase-6-Implementierung pruefen.

## Not In Scope

- **Step-3/4-Inhalte** und deren `canAdvance`-Flags — Sub-Issues #163/#164.
- **Wegpunkte / KI-Vorschlaege** — Step 3 (#163).
- **Save-Pipeline scharfschalten** — Step 4 (#164).
- **Backend-Aenderungen** (z.B. Multi-File-Upload-Endpoint).
- **Trip-Vorlagen** (#165).
- **`start_time`-Auto-Berechnung** (eigenes Issue falls noetig).
- **Mobile-Optimierung von StageRow** (Responsive-Wrap).
- **Undo/Redo / localStorage-Persistenz / Toast-Notifications**.
- **`dateOverridden`-Reset-Mechanismus.**
- **Erweiterte GPX-Validation in der UI** (Track-Anzahl, Mindest-Wegpunkte etc.).
- **A11y-Erweiterungen ueber `svelte-dnd-action`-Defaults hinaus.**

## Verweise

- **Master-Spec:** [`epic_136_trip_wizard.md`](./epic_136_trip_wizard.md)
  - §3.1 WizardState (Erweiterungen)
  - §3.2 Pausentag-Konvention
  - §3.3 T-Nummerierung
  - §1.4 Save-Pipeline (`toTripPayload`-Anpassung fuer `dateOverridden`)
- **Vorgaenger-Sub-Spec:** [`epic_136_step1_profile.md`](./epic_136_step1_profile.md) (#161; Pattern fuer `canAdvanceStepN`, `fillStepN`, Master-Spec-Changelog)
- **Atom-Komponenten:** Epic #133 Lauf B (`Btn`, `GCard`, `Pill`, `Eyebrow`, `Input`)
- **GPX-Spezifikationen:** [`gpx_multi_import.md`](./gpx_multi_import.md), [`gpx_parser.md`](./gpx_parser.md), [`gpx_upload.md`](./gpx_upload.md)
- **DnD-Library:** [svelte-dnd-action](https://github.com/isaacHagoel/svelte-dnd-action)
- **Issue:** [#162 — Step 2: GPX-Multi-Upload + Drag-Sort + Pause](https://github.com/henemm/gregor_zwanzig/issues/162)
- **Phase-1+2-Kontext:** `docs/context/issue-162-wizard-step2-stages.md`

## Changelog

- 2026-05-10: Sub-Spec aus Stub ausgefuellt — Layout-Wireframe (Drop-Zone + Etappen-Liste + Pause-Inserter), `StageRow.svelte` als neue Komponente, Datenmodell-Erweiterung `Stage.dateOverridden` (transient, gestrippt in `toTripPayload`), 5 neue `WizardState`-Methoden/Getter (`canAdvanceStep2`, `canAdvanceCurrent`, `addPauseStageAt`, `deleteStage`, `recomputeStageDates`), Drop-Zone mit clientseitiger GPX-Filterung + Datumspicker + sequenzieller `commitPending`-Flow, `svelte-dnd-action` als neue Dependency (User-Entscheidung 2026-05-10), Pause-Inserter mit Hover/Focus-Sichtbarkeit, Auto-Datierung mit User-Override-Schutz, Shell-Refactor zu `state.canAdvanceCurrent`, TestID-Inventar mit Prefix `trip-wizard-step2-*`, `fillStep2`-E2E-Helper + Test-GPX-Fixture, Migration der 3 brechenden Shell-Tests (AC#5a, AC#8, AC#11), 31 Acceptance Criteria, Datei-Liste (4 NEU + 9 EDIT, geschaetzt ~280 LoC Produktionscode + ~310 LoC Tests + ~10 LoC Spec-Patches + neue NPM-Dep). Status `stub` → `draft`, Version `0.1` → `1.0`.
- 2026-05-09: Stub angelegt (Phase 3 der Epic-Master-Spec).
