---
entity_id: epic_136_step5_templates
type: module
created: 2026-05-09
updated: 2026-05-19
status: approved
version: "1.0"
parent_spec: epic_136_trip_wizard
related: epic_136_step2_stages
issue: 165
tags: [sveltekit, frontend, wizard, step2, templates, epic-136]
---

# Epic 136 — Sub-Spec #165: Trip-Vorlagen

## Approval

- [x] Approved (2026-05-19, nach vollständiger Implementierung)

## Status

**Approved** — implementiert und dokumentiert.

## Purpose

Definiert die `TemplatePicker`-Komponente und die statischen Vorlagen-Daten fuer Step 2 des Trip-Wizards.
Die Komponente erscheint als rechte Spalte neben dem GPX-Upload-Bereich und erlaubt dem User, per Klick
eine von drei vordefinierten Routen (GR20, Karnischer Hoehenweg, Stubaier Hoehenweg) zu laden — ohne
eigene GPX-Dateien hochzuladen. Klick auf eine Vorlage belegt `wizard.stages`, `wizard.activity`,
`wizard.name` (falls leer) und `wizard.shortcode` (falls leer) sofort mit konkreten Werten.

Diese Sub-Spec ist ein reines Frontend-Feature: kein Backend-Aufruf, keine GPX-Uploads, keine API-Calls.
Der Mehrwert liegt in der Zero-Setup-Erfahrung fuer Wanderer, die einen der drei klassischen Fernwanderwege
planen und sofort mit dem Wizard weiterarbeiten wollen.

## Source

- **Komponente (NEU):** `frontend/src/lib/components/trip-wizard/templates/TemplatePicker.svelte`
- **Daten (NEU):** `frontend/src/lib/components/trip-wizard/templates/tripTemplates.ts`
- **Komponente (EDIT):** `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte`
  — Layout-Umbau von Single-Column zu Two-Column-Grid
- **Tests (NEU):** `frontend/src/lib/components/trip-wizard/__tests__/tripTemplates.test.ts`
- **E2E (NEU):** `frontend/e2e/trip-wizard-templates.spec.ts`

## Verweis auf Master-Spec

Diese Sub-Spec ist eine Detail-Spezifikation der approved Master-Spec
[`docs/specs/modules/epic_136_trip_wizard.md`](./epic_136_trip_wizard.md). Konkret konsumiert sie:

- **§3.1 WizardState** — direkte Zuweisung `wizard.stages = [...]` (NICHT `addStage()`),
  `wizard.activity`, `wizard.name`, `wizard.shortcode`, `wizard.recomputeStageDates()`.
- **§3.2 Pausentag-Konvention** und **§3.3 T-Nummerierung** — Vorlage-Etappen sind keine Pausentage;
  `waypoints.length >= 2` (Start + End) gilt als regulaere Etappe.
- **§1.4 Save-Pipeline** — kein neues Feld; `Waypoint.suggested` wird NICHT gesetzt
  (Vorlage-Waypoints sind pre-confirmed).

Vorgaenger-Sub-Specs:
- [`epic_136_step2_stages.md`](./epic_136_step2_stages.md) (#162, GPX-Upload + DnD) —
  diese Sub-Spec erweitert Step2Stages um die rechte Spalte, beruehrt aber keine bestehende Logik.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WizardState` | class | stages, activity, name, shortcode, recomputeStageDates() |
| `wizardHelpers.ts` | file | `newId()` fuer Stage- und Waypoint-IDs |
| `frontend/src/lib/types.ts` | file | `Stage`, `Waypoint`, `ActivityType` Interfaces |
| `GCard.svelte` | component | Container-Karte fuer jede Vorlage |
| `Btn.svelte` | component | Auswahl-Button pro Vorlage-Karte |
| `Eyebrow.svelte` | component | Abschnitts-Label "Vorlagen" |
| `Pill.svelte` | component | Aktivitaets-Badge auf Vorlage-Karte |
| `Dialog` (bits-ui) | component | Bestaetigungs-Dialog bei vorhandenem `wizard.stages.length > 0` |
| `Step2Stages.svelte` | file (edit) | Layout-Wrapper; bekommt zweite Spalte |

## Template Data

### GR20 (Korsika) — 14 Etappen

| # | Name | Start (lat, lon, ele) | End (lat, lon, ele) |
|---|------|-----------------------|---------------------|
| T01 | Calenzana → Ortu di u Piobbu | 42.509, 8.848, 275m | 42.478, 8.903, 1520m |
| T02 | Ortu → Carrozzu | 42.478, 8.903, 1520m | 42.452, 8.907, 1270m |
| T03 | Carrozzu → Ascu Stagnu | 42.452, 8.907, 1270m | 42.448, 8.916, 1422m |
| T04 | Ascu → Tighjettu | 42.448, 8.916, 1422m | 42.423, 8.950, 1683m |
| T05 | Tighjettu → Ciottulu di i Mori | 42.423, 8.950, 1683m | 42.392, 9.008, 1991m |
| T06 | Ciottulu → Manganu | 42.392, 9.008, 1991m | 42.298, 9.009, 1601m |
| T07 | Manganu → Petra Piana | 42.298, 9.009, 1601m | 42.268, 9.041, 1842m |
| T08 | Petra Piana → L'Onda | 42.268, 9.041, 1842m | 42.245, 9.077, 1430m |
| T09 | L'Onda → Vizzavona | 42.245, 9.077, 1430m | 42.128, 9.135, 1163m |
| T10 | Vizzavona → E'Capannelle | 42.128, 9.135, 1163m | 41.959, 9.233, 1586m |
| T11 | E'Capannelle → Usciolu | 41.959, 9.233, 1586m | 41.935, 9.147, 1750m |
| T12 | Usciolu → Asinau | 41.935, 9.147, 1750m | 41.895, 9.125, 1536m |
| T13 | Asinau → Paliri | 41.895, 9.125, 1536m | 41.758, 9.197, 1055m |
| T14 | Paliri → Conca | 41.758, 9.197, 1055m | 41.666, 9.330, 252m |

Metadaten: `id: 'gr20'`, `name: 'GR20'`, `shortcode: 'GR20'`, `activity: 'trekking'`

### Karnischer Hoehenweg (KHW) — 13 Etappen

| # | Name | Start (lat, lon, ele) | End (lat, lon, ele) |
|---|------|-----------------------|---------------------|
| KHW_00a | Troblach Bhf → Helmhotel | 46.72475, 12.22542, 1212m | 46.73042, 12.32164, 1144m |
| KHW_00b | Helmhotel → Sillianer Huette | 46.73042, 12.32164, 1142m | 46.70606, 12.40627, 2377m |
| KHW_01 | Sillianer Huette → Obstansersee | 46.70607, 12.40627, 2441m | 46.68427, 12.49369, 2312m |
| KHW_02 | Obstansersee → Porzehütte | 46.68427, 12.49369, 2297m | 46.65972, 12.58220, 1930m |
| KHW_03 | Porzehütte → Hochweißsteinhaus | 46.65972, 12.58220, 1950m | 46.64301, 12.74033, 1815m |
| KHW_04 | Hochweißsteinhaus → Wolayersee-Huette | 46.64301, 12.74033, 1867m | 46.61229, 12.86717, 1953m |
| KHW_05 | Wolayersee → Valentinalm | 46.61241, 12.86704, 1949m | 46.62285, 12.93057, 1200m |
| KHW_06 | Valentinalm → Zollnersee Huette | 46.62285, 12.93057, 1190m | 46.60538, 13.07065, 1751m |
| KHW_07 | Zollnersee → Straniger Alm | 46.60539, 13.07064, 1729m | 46.59567, 13.13447, 1504m |
| KHW_08 | Straniger Alm → Nassfeld | 46.59571, 13.13440, 1515m | 46.55762, 13.27852, 1522m |
| KHW_09 | Nassfeld → Egger Alm | 46.55762, 13.27852, 1532m | 46.58570, 13.38018, 1396m |
| KHW_10 | Egger Alm → Dolinza Alm | 46.58570, 13.38018, 1408m | 46.56405, 13.47916, 1483m |
| KHW_11 | Dolinza → Noetsch im Gailtal | 46.56405, 13.47916, 1468m | 46.59079, 13.62275, 560m |

Metadaten: `id: 'khw'`, `name: 'Karnischer Hoehenweg'`, `shortcode: 'KHW'`, `activity: 'trekking'`

### Stubaier Hoehenweg — 7 Etappen

| # | Name | Start (lat, lon, ele) | End (lat, lon, ele) |
|---|------|-----------------------|---------------------|
| T01 | Fulpmes → Franz-Senn-Huette | 47.157, 11.329, 937m | 47.131, 11.206, 2147m |
| T02 | Franz-Senn → Neue Regensburger | 47.131, 11.206, 2147m | 47.062, 11.048, 2286m |
| T03 | Neue Regensburger → Sulzenauhütte | 47.062, 11.048, 2286m | 46.993, 11.068, 2191m |
| T04 | Sulzenauhütte → Nuernberger Huette | 46.993, 11.068, 2191m | 46.986, 11.119, 2280m |
| T05 | Nuernberger → Dresdner Huette | 46.986, 11.119, 2280m | 47.075, 11.110, 2302m |
| T06 | Dresdner → Starkenburger Huette | 47.075, 11.110, 2302m | 47.152, 11.280, 2237m |
| T07 | Starkenburger → Neustift | 47.152, 11.280, 2237m | 47.099, 11.314, 1000m |

Metadaten: `id: 'stubai'`, `name: 'Stubaier Hoehenweg'`, `shortcode: 'SHW'`, `activity: 'trekking'`

## Implementation Details

### 1. `tripTemplates.ts` — Statische Vorlage-Daten

```typescript
// frontend/src/lib/components/trip-wizard/templates/tripTemplates.ts

import type { Stage, Waypoint, ActivityType } from '$lib/types';
import { newId } from '../wizardHelpers';

export interface TripTemplate {
  id: string;
  name: string;
  shortcode: string;
  activity: ActivityType;
  stages: () => Stage[];   // Factory-Funktion: jedes Mal frische IDs via newId()
}

function makeStage(name: string, startLat: number, startLon: number, startEle: number,
                   endLat: number, endLon: number, endEle: number): Stage {
  const start: Waypoint = { id: newId(), lat: startLat, lon: startLon, ele: startEle, name: '' };
  const end: Waypoint   = { id: newId(), lat: endLat,   lon: endLon,   ele: endEle,   name: '' };
  return { id: newId(), name, date: '', waypoints: [start, end] };
}

export const TRIP_TEMPLATES: TripTemplate[] = [
  {
    id: 'gr20',
    name: 'GR20',
    shortcode: 'GR20',
    activity: 'trekking',
    stages: () => [
      makeStage("Calenzana → Ortu di u Piobbu", 42.509, 8.848, 275,  42.478, 8.903, 1520),
      makeStage("Ortu → Carrozzu",              42.478, 8.903, 1520, 42.452, 8.907, 1270),
      makeStage("Carrozzu → Ascu Stagnu",       42.452, 8.907, 1270, 42.448, 8.916, 1422),
      makeStage("Ascu → Tighjettu",             42.448, 8.916, 1422, 42.423, 8.950, 1683),
      makeStage("Tighjettu → Ciottulu di i Mori", 42.423, 8.950, 1683, 42.392, 9.008, 1991),
      makeStage("Ciottulu → Manganu",           42.392, 9.008, 1991, 42.298, 9.009, 1601),
      makeStage("Manganu → Petra Piana",        42.298, 9.009, 1601, 42.268, 9.041, 1842),
      makeStage("Petra Piana → L'Onda",         42.268, 9.041, 1842, 42.245, 9.077, 1430),
      makeStage("L'Onda → Vizzavona",           42.245, 9.077, 1430, 42.128, 9.135, 1163),
      makeStage("Vizzavona → E'Capannelle",     42.128, 9.135, 1163, 41.959, 9.233, 1586),
      makeStage("E'Capannelle → Usciolu",       41.959, 9.233, 1586, 41.935, 9.147, 1750),
      makeStage("Usciolu → Asinau",             41.935, 9.147, 1750, 41.895, 9.125, 1536),
      makeStage("Asinau → Paliri",              41.895, 9.125, 1536, 41.758, 9.197, 1055),
      makeStage("Paliri → Conca",               41.758, 9.197, 1055, 41.666, 9.330,  252),
    ]
  },
  {
    id: 'khw',
    name: 'Karnischer Hoehenweg',
    shortcode: 'KHW',
    activity: 'trekking',
    stages: () => [
      makeStage("Troblach Bhf → Helmhotel",         46.72475, 12.22542, 1212, 46.73042, 12.32164, 1144),
      makeStage("Helmhotel → Sillianer Huette",      46.73042, 12.32164, 1142, 46.70606, 12.40627, 2377),
      makeStage("Sillianer Huette → Obstansersee",   46.70607, 12.40627, 2441, 46.68427, 12.49369, 2312),
      makeStage("Obstansersee → Porzehütte",         46.68427, 12.49369, 2297, 46.65972, 12.58220, 1930),
      makeStage("Porzehütte → Hochweißsteinhaus",    46.65972, 12.58220, 1950, 46.64301, 12.74033, 1815),
      makeStage("Hochweißsteinhaus → Wolayersee",    46.64301, 12.74033, 1867, 46.61229, 12.86717, 1953),
      makeStage("Wolayersee → Valentinalm",          46.61241, 12.86704, 1949, 46.62285, 12.93057, 1200),
      makeStage("Valentinalm → Zollnersee Huette",   46.62285, 12.93057, 1190, 46.60538, 13.07065, 1751),
      makeStage("Zollnersee → Straniger Alm",        46.60539, 13.07064, 1729, 46.59567, 13.13447, 1504),
      makeStage("Straniger Alm → Nassfeld",          46.59571, 13.13440, 1515, 46.55762, 13.27852, 1522),
      makeStage("Nassfeld → Egger Alm",              46.55762, 13.27852, 1532, 46.58570, 13.38018, 1396),
      makeStage("Egger Alm → Dolinza Alm",           46.58570, 13.38018, 1408, 46.56405, 13.47916, 1483),
      makeStage("Dolinza → Noetsch im Gailtal",      46.56405, 13.47916, 1468, 46.59079, 13.62275,  560),
    ]
  },
  {
    id: 'stubai',
    name: 'Stubaier Hoehenweg',
    shortcode: 'SHW',
    activity: 'trekking',
    stages: () => [
      makeStage("Fulpmes → Franz-Senn-Huette",      47.157, 11.329,  937, 47.131, 11.206, 2147),
      makeStage("Franz-Senn → Neue Regensburger",   47.131, 11.206, 2147, 47.062, 11.048, 2286),
      makeStage("Neue Regensburger → Sulzenauhütte",47.062, 11.048, 2286, 46.993, 11.068, 2191),
      makeStage("Sulzenauhütte → Nuernberger Huette",46.993,11.068, 2191, 46.986, 11.119, 2280),
      makeStage("Nuernberger → Dresdner Huette",    46.986, 11.119, 2280, 47.075, 11.110, 2302),
      makeStage("Dresdner → Starkenburger Huette",  47.075, 11.110, 2302, 47.152, 11.280, 2237),
      makeStage("Starkenburger → Neustift",         47.152, 11.280, 2237, 47.099, 11.314, 1000),
    ]
  }
];
```

**Wichtig — Factory-Funktion statt statisches Array:** `stages` ist eine Funktion `() => Stage[]`,
nicht ein fertiges Array. So kommen bei jedem Aufruf frische `newId()`-Werte — zwei gleichzeitige
Wizard-Sessions wuerden sich nicht dieselben IDs teilen.

**Kein `suggested`-Flag:** Vorlage-Wegpunkte sind pre-confirmed; `Waypoint.suggested` wird nicht
gesetzt. Die Save-Pipeline-Anpassung aus Sub-Spec #162 (Strip von `suggested`) ist neutral.

### 2. `TemplatePicker.svelte` — UI-Komponente

```
┌──────────────────────────────────────────┐
│ Eyebrow: "Vorlagen"                      │
│                                          │
│ ┌──────────────────────────────────────┐ │
│ │ GR20                [Pill: Trekking] │ │
│ │ Korsika · 14 Etappen                 │ │
│ │ [Vorlage laden]                      │ │
│ └──────────────────────────────────────┘ │
│                                          │
│ ┌──────────────────────────────────────┐ │
│ │ Karnischer Hoehenweg [Pill: Trekking]│ │
│ │ Karnische Alpen · 13 Etappen         │ │
│ │ [Vorlage laden]                      │ │
│ └──────────────────────────────────────┘ │
│                                          │
│ ┌──────────────────────────────────────┐ │
│ │ Stubaier Hoehenweg  [Pill: Trekking] │ │
│ │ Tirol · 7 Etappen                    │ │
│ │ [Vorlage laden]                      │ │
│ └──────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

```svelte
<script lang="ts">
  import { getContext } from 'svelte';
  import { GCard } from '$lib/components/ui/g-card';
  import { Btn } from '$lib/components/ui/btn';
  import { Eyebrow } from '$lib/components/ui/eyebrow';
  import { Pill } from '$lib/components/ui/pill';
  import { Dialog } from 'bits-ui';
  import { TRIP_TEMPLATES, type TripTemplate } from './tripTemplates';
  import type { WizardState } from '../wizardState.svelte';

  const state = getContext<WizardState>('wizard');

  let pendingTemplate = $state<TripTemplate | null>(null);
  let showConfirm = $state(false);

  function requestApply(tpl: TripTemplate): void {
    if (state.stages.length > 0) {
      pendingTemplate = tpl;
      showConfirm = true;
    } else {
      applyTemplate(tpl);
    }
  }

  function applyTemplate(tpl: TripTemplate): void {
    state.stages = tpl.stages();
    state.activity = tpl.activity;
    if (!state.name)      state.name      = tpl.name;
    if (!state.shortcode) state.shortcode = tpl.shortcode;
    state.recomputeStageDates();
    showConfirm = false;
    pendingTemplate = null;
  }

  function confirmReplace(): void {
    if (pendingTemplate) applyTemplate(pendingTemplate);
  }

  function cancelReplace(): void {
    showConfirm = false;
    pendingTemplate = null;
  }

  const STAGE_COUNTS: Record<string, number> = {
    gr20: 14, khw: 13, stubai: 7
  };
  const REGION: Record<string, string> = {
    gr20: 'Korsika', khw: 'Karnische Alpen', stubai: 'Tirol'
  };
</script>

<div data-testid="trip-wizard-template-picker" class="flex flex-col gap-3">
  <Eyebrow>Vorlagen</Eyebrow>

  {#each TRIP_TEMPLATES as tpl}
    <GCard data-testid={`trip-wizard-template-card-${tpl.id}`}>
      <div class="flex items-start justify-between gap-2">
        <div>
          <p class="font-semibold text-sm">{tpl.name}</p>
          <p class="text-xs text-[var(--g-ink-faint)]">
            {REGION[tpl.id]} · {STAGE_COUNTS[tpl.id]} Etappen
          </p>
        </div>
        <Pill tone="default">{tpl.activity}</Pill>
      </div>
      <Btn
        variant="secondary"
        size="sm"
        class="mt-2 w-full"
        data-testid={`trip-wizard-template-apply-${tpl.id}`}
        onclick={() => requestApply(tpl)}
      >
        Vorlage laden
      </Btn>
    </GCard>
  {/each}
</div>

<!-- Bestaetigungs-Dialog fuer Ueberschreiben bestehender Etappen -->
<Dialog.Root bind:open={showConfirm}>
  <Dialog.Portal>
    <Dialog.Overlay class="fixed inset-0 bg-black/40" />
    <Dialog.Content
      data-testid="trip-wizard-template-confirm-dialog"
      class="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-xl p-6 shadow-xl max-w-sm w-full"
    >
      <Dialog.Title class="font-semibold mb-2">Vorhandene Etappen ersetzen?</Dialog.Title>
      <Dialog.Description class="text-sm text-[var(--g-ink-faint)] mb-4">
        Die aktuellen {state.stages.length} Etappen werden durch die Vorlage
        „{pendingTemplate?.name}" ersetzt. Diese Aktion kann nicht rueckgaengig gemacht werden.
      </Dialog.Description>
      <div class="flex gap-2 justify-end">
        <Btn
          variant="ghost"
          data-testid="trip-wizard-template-confirm-cancel"
          onclick={cancelReplace}
        >
          Abbrechen
        </Btn>
        <Btn
          variant="accent"
          data-testid="trip-wizard-template-confirm-ok"
          onclick={confirmReplace}
        >
          Ja, ersetzen
        </Btn>
      </div>
    </Dialog.Content>
  </Dialog.Portal>
</Dialog.Root>
```

### 3. Layout-Aenderung in `Step2Stages.svelte`

Step2Stages wechselt von Single-Column zu CSS-Grid mit zwei Spalten.
Auf Viewports < 640px stackt die rechte Spalte unter den GPX-Upload-Bereich.

```svelte
<!-- vorher: -->
<div class="flex flex-col gap-6">
  <!-- Drop-Zone + Stages-Liste -->
</div>

<!-- nachher: -->
<div
  data-testid="trip-wizard-step2-layout"
  class="grid gap-6"
  style="grid-template-columns: 2fr minmax(0, 220px);"
>
  <!-- Linke Spalte: Drop-Zone + Stages-Liste (bestehend) -->
  <div class="flex flex-col gap-6">
    <!-- unveraendert: Drop-Zone, Pending-UI, DnD-Liste -->
  </div>

  <!-- Rechte Spalte: TemplatePicker -->
  <div>
    <TemplatePicker />
  </div>
</div>

<style>
  @media (max-width: 640px) {
    div[data-testid="trip-wizard-step2-layout"] {
      grid-template-columns: 1fr;
    }
  }
</style>
```

Die zweite Spalte hat eine fixe Maximalbreite von 220px (`minmax(0, 220px)`). Das schraenkt
die Vorlage-Karten auf eine kompakte Groesse ein und laesst dem GPX-Upload-Bereich den Hauptanteil.

### 4. Anwende-Logik — Detaillierter Ablauf

1. User klickt "Vorlage laden" fuer eine der drei Vorlagen.
2. **Falls `state.stages.length === 0`:** sofortiger `applyTemplate(tpl)`-Aufruf.
3. **Falls `state.stages.length > 0`:** `showConfirm = true` + `pendingTemplate = tpl`.
4. User bestaetigt Dialog ("Ja, ersetzen") → `applyTemplate(tpl)` wird aufgerufen.
5. `applyTemplate`:
   a. `state.stages = tpl.stages()` — direkte Zuweisung (KEINE Iteration via `addStage()`).
      Grund: `addStage()` wuerde `suggested: true` setzen; Vorlage-Waypoints sind pre-confirmed.
   b. `state.activity = tpl.activity`
   c. `if (!state.name) state.name = tpl.name` — bestehendes Name-Feld wird NICHT ueberschrieben.
   d. `if (!state.shortcode) state.shortcode = tpl.shortcode` — ebenso.
   e. `state.recomputeStageDates()` — weist fortlaufende Daten ab `state.startDate` zu.
   f. `showConfirm = false`, `pendingTemplate = null`.

**Name/Shortcode-Schutz:** Hat der User in Step 1 bereits einen Namen eingegeben, wird dieser
bewusst beibehalten. Die Vorlage setzt Name und Shortcode nur als Default, nicht als Override.

### 5. TestID-Inventar

| TestID | Komponente | Zweck |
|--------|------------|-------|
| `trip-wizard-template-picker` | TemplatePicker-Container | Prueft Sichtbarkeit |
| `trip-wizard-template-card-gr20` | GR20-Karte | Prueft Karten-Render |
| `trip-wizard-template-card-khw` | KHW-Karte | Prueft Karten-Render |
| `trip-wizard-template-card-stubai` | Stubai-Karte | Prueft Karten-Render |
| `trip-wizard-template-apply-gr20` | GR20-Button | Ausloeser fuer Vorlage-Laden |
| `trip-wizard-template-apply-khw` | KHW-Button | Ausloeser fuer Vorlage-Laden |
| `trip-wizard-template-apply-stubai` | Stubai-Button | Ausloeser fuer Vorlage-Laden |
| `trip-wizard-template-confirm-dialog` | Bestaetigungs-Dialog | Sichtbar bei stages > 0 |
| `trip-wizard-template-confirm-ok` | Dialog-Bestaetigen-Btn | Bestaetigt Ersetzen |
| `trip-wizard-template-confirm-cancel` | Dialog-Abbrechen-Btn | Schliesst Dialog ohne Aktion |
| `trip-wizard-step2-layout` | Step2-Grid-Wrapper | Prueft Two-Column-Layout |

### 6. Unit-Tests `tripTemplates.test.ts`

```typescript
// frontend/src/lib/components/trip-wizard/__tests__/tripTemplates.test.ts
import { describe, it, expect } from 'vitest';
import { TRIP_TEMPLATES } from '../templates/tripTemplates';

describe('TRIP_TEMPLATES', () => {
  it('enthaelt genau 3 Vorlagen', () => {
    expect(TRIP_TEMPLATES).toHaveLength(3);
  });

  it.each(TRIP_TEMPLATES)('$name: stages() liefert korrekte Etappenanzahl', (tpl) => {
    const counts: Record<string, number> = { gr20: 14, khw: 13, stubai: 7 };
    expect(tpl.stages()).toHaveLength(counts[tpl.id]);
  });

  it.each(TRIP_TEMPLATES)('$name: jede Etappe hat genau 2 Waypoints (Start+End)', (tpl) => {
    for (const stage of tpl.stages()) {
      expect(stage.waypoints).toHaveLength(2);
    }
  });

  it.each(TRIP_TEMPLATES)('$name: kein Waypoint hat suggested=true', (tpl) => {
    for (const stage of tpl.stages()) {
      for (const wp of stage.waypoints) {
        expect((wp as any).suggested).toBeUndefined();
      }
    }
  });

  it.each(TRIP_TEMPLATES)('$name: stages() gibt jedes Mal frische IDs zurueck', (tpl) => {
    const ids1 = tpl.stages().map((s) => s.id);
    const ids2 = tpl.stages().map((s) => s.id);
    expect(ids1).not.toEqual(ids2);
  });

  it.each(TRIP_TEMPLATES)('$name: alle Koordinaten im gueltigen Bereich', (tpl) => {
    for (const stage of tpl.stages()) {
      for (const wp of stage.waypoints) {
        expect(wp.lat).toBeGreaterThan(-90);
        expect(wp.lat).toBeLessThan(90);
        expect(wp.lon).toBeGreaterThan(-180);
        expect(wp.lon).toBeLessThan(180);
      }
    }
  });

  it('KHW erste Etappe hat korrekte Startkoordinaten', () => {
    const khw = TRIP_TEMPLATES.find((t) => t.id === 'khw')!;
    const first = khw.stages()[0];
    expect(first.waypoints[0].lat).toBeCloseTo(46.72475, 4);
    expect(first.waypoints[0].lon).toBeCloseTo(12.22542, 4);
  });

  it('GR20 erste Etappe heisst "Calenzana → Ortu di u Piobbu"', () => {
    const gr20 = TRIP_TEMPLATES.find((t) => t.id === 'gr20')!;
    expect(gr20.stages()[0].name).toBe("Calenzana → Ortu di u Piobbu");
  });
});
```

### 7. LoC-Uebersicht

| Datei | Aktion | Geschaetzte LoC |
|-------|--------|-----------------|
| `tripTemplates.ts` | NEU | ~110 |
| `TemplatePicker.svelte` | NEU | ~95 |
| `Step2Stages.svelte` | EDIT (Layout-Wrapper) | +10 |
| `tripTemplates.test.ts` | NEU | ~60 |
| `trip-wizard-templates.spec.ts` | NEU (E2E) | ~180 |
| **Gesamt** | | **~455** |

Wegen Ueberschreitung des Standard-Limits (250 LoC): `loc_limit_override 500` muss
gesetzt werden, bevor Phase 6 beginnt.

## Expected Behavior

- **Input:** User in Step 2 des Trip-Wizards. `TemplatePicker` ist immer sichtbar in der rechten Spalte, unabhaengig vom aktuellen `state.stages`-Zustand.
- **Output:**
  - Drei Vorlage-Karten (GR20, KHW, Stubai) werden mit Name, Region, Etappenanzahl und Aktivitaets-Badge angezeigt.
  - Klick auf "Vorlage laden" bei leerem `state.stages`: sofortige Befuellung ohne Dialog.
  - Klick auf "Vorlage laden" bei befuelltem `state.stages`: Bestaetigungs-Dialog erscheint.
  - Nach Bestaetigung: `state.stages` enthaelt die Vorlage-Etappen mit Start/End-Koordinaten, `state.activity = 'trekking'`, `state.name` und `state.shortcode` werden nur als Default gesetzt (kein Override wenn bereits belegt).
  - `state.recomputeStageDates()` wird nach Zuweisung aufgerufen — Etappen erhalten aufsteigende Daten ab `state.startDate`.
  - Weiter-Button in Step 2 ist nach Vorlage-Laden enabled (da `state.stages.length > 0`).
- **Side effects:**
  - `state.stages` wird direkt ersetzt (nicht per `addStage()`).
  - Kein API-Call, kein GPX-Upload, keine Netzwerkanfrage.
  - `state.activity`, `state.name` (conditional), `state.shortcode` (conditional) werden mutiert.

## Acceptance Criteria

- **AC-1:** Given der User ist in Step 2 des Trip-Wizards / When die Seite geladen ist / Then sind drei Vorlage-Karten mit TestIDs `trip-wizard-template-card-gr20`, `trip-wizard-template-card-khw`, `trip-wizard-template-card-stubai` sichtbar
  - Test: (populated after /tdd-red)

- **AC-2:** Given `state.stages` ist leer / When der User auf "Vorlage laden" fuer GR20 klickt / Then werden sofort 14 Etappen in `state.stages` geschrieben ohne Bestaetigungs-Dialog
  - Test: (populated after /tdd-red)

- **AC-3:** Given `state.stages` enthaelt bereits mindestens eine Etappe / When der User auf "Vorlage laden" klickt / Then erscheint der Bestaetigungs-Dialog mit TestID `trip-wizard-template-confirm-dialog`
  - Test: (populated after /tdd-red)

- **AC-4:** Given der Bestaetigungs-Dialog ist offen / When der User auf "Abbrechen" klickt / Then schliesst der Dialog und `state.stages` bleibt unveraendert
  - Test: (populated after /tdd-red)

- **AC-5:** Given der Bestaetigungs-Dialog ist offen / When der User auf "Ja, ersetzen" klickt / Then wird `state.stages` durch die Vorlage-Etappen ersetzt und der Dialog schliesst sich
  - Test: (populated after /tdd-red)

- **AC-6:** Given der User ladet die KHW-Vorlage / When `applyTemplate` ausgefuehrt wird / Then hat `state.stages[0].waypoints[0].lat` den Wert 46.72475 (±0.0001) und `state.stages` hat Laenge 13
  - Test: (populated after /tdd-red)

- **AC-7:** Given der User ladet die Stubai-Vorlage / When `applyTemplate` ausgefuehrt wird / Then hat `state.activity` den Wert `'trekking'` und `state.stages` hat Laenge 7
  - Test: (populated after /tdd-red)

- **AC-8:** Given `state.name` ist bereits belegt / When der User eine Vorlage ladet / Then bleibt `state.name` unveraendert (Vorlage-Name wird NICHT ueberschrieben)
  - Test: (populated after /tdd-red)

- **AC-9:** Given `state.startDate` ist gesetzt / When eine Vorlage geladen wird / Then hat `state.stages[0].date` den Wert von `state.startDate` und `state.stages[1].date` den Folgetag
  - Test: (populated after /tdd-red)

- **AC-10:** Given keine Vorlage wurde geladen / When die Vorlage-Karte fuer GR20 gerendert wird / Then zeigt sie den Text "14 Etappen" und den Text "Korsika"
  - Test: (populated after /tdd-red)

- **AC-11:** Given der User ladet eine Vorlage in Step 2 / When danach der Weiter-Button in Step 2 geprueft wird / Then ist er enabled (weil `state.stages.length > 0`)
  - Test: (populated after /tdd-red)

- **AC-12:** Given Step2Stages wird auf einem Viewport >=640px gerendert / When das Layout geprueft wird / Then existieren zwei Spalten (GPX-Upload links, TemplatePicker rechts) im CSS-Grid
  - Test: (populated after /tdd-red)

- **AC-13:** Given `stages()` der Vorlage wird zweimal aufgerufen / When die IDs beider Aufruf-Ergebnisse verglichen werden / Then sind alle Stage-IDs unterschiedlich (kein ID-Clash durch Factory-Funktion)
  - Test: (populated after /tdd-red)

- **AC-14:** Given der User ladet die GR20-Vorlage / When `state.stages` geprueft wird / Then hat kein Waypoint das Attribut `suggested` (Vorlage-Waypoints sind pre-confirmed)
  - Test: (populated after /tdd-red)

- **AC-15:** Given `npm run check` und `npm run build` werden im `frontend/`-Verzeichnis ausgefuehrt / When der Build abgeschlossen ist / Then sind beide Befehle fehlerfrei (Exit 0)
  - Test: (populated after /tdd-red)

## Known Limitations

- **Keine Offline-Karte:** Vorlage-Karten zeigen Etappenanzahl und Region als Text, aber keine Karten-Vorschau. Eine Karten-Preview waere UX-sinnvoll, ist aber nicht in Scope.
- **Koordinaten-Praezision:** GR20- und Stubai-Koordinaten sind gerundete Huetenkoordinaten, keine exakten GPS-Tracks. Fuer Wetterberechnungen ausreichend (naechster Wetterpunkt <= 10km). Detailliertere Tracks erfordern GPX-Upload.
- **Kein Mischen von Vorlage + GPX-Upload:** Nach Vorlage-Laden kann der User weiterhin GPX-Dateien hochladen und so die Etappenliste ergaenzen oder ersetzen. Es gibt keine spezielle Sperre — das bestehende Upload-Flow bleibt vollstaendig funktional.
- **Kein Undo:** Ein versehentliches "Ja, ersetzen" verliert den bisherigen Stage-Stand. Kein Undo-Mechanismus in Scope (gleiches Limit wie in Sub-Spec #162).
- **Drei feste Vorlagen:** Neue Vorlagen erfordern Code-Aenderungen in `tripTemplates.ts`. Kein User-seitiges Vorlagen-Management.
- **`state.shortcode` wird nur bei leerem Feld gesetzt:** Hat der User in Step 1 keinen Shortcode eingegeben aber einen Trip-Namen, bekommt er den Vorlage-Shortcode. Das ist gewuenscht.

## Not In Scope

- **Backend-Aenderungen:** Keine API-Endpoints, kein GPX-Parsing.
- **Weitere Routen:** Weitere Fernwanderwege (z.B. E5, Alpenueberquerung) sind Folge-Issues.
- **Vorlage-Verwaltung durch User:** Kein UI fuer eigene Vorlagen anlegen/speichern.
- **Karten-Vorschau** auf den Vorlage-Karten.
- **Undo-Mechanismus** fuer versehentliches Ersetzen.
- **Step-3/4-Inhalte** — Sub-Issues #163/#164.

## Verweise

- **Master-Spec:** [`epic_136_trip_wizard.md`](./epic_136_trip_wizard.md)
- **Schwester-Sub-Spec:** [`epic_136_step2_stages.md`](./epic_136_step2_stages.md) (#162, GPX-Upload + DnD)
- **Atom-Komponenten:** Epic #133 (`GCard`, `Btn`, `Pill`, `Eyebrow`)
- **Dialog-Bibliothek:** [bits-ui Dialog](https://bits-ui.com/docs/components/dialog)
- **Issue:** [#165 — Wizard: Trip-Vorlagen](https://github.com/henemm/gregor_zwanzig/issues/165)

## Changelog

- 2026-05-19: Stub vollstaendig ausgefuellt — Vorlage-Daten (GR20 14 Etappen, KHW 13 Etappen, Stubai 7 Etappen mit verifizierten Koordinaten), `tripTemplates.ts` Factory-Pattern mit `makeStage`-Helper, `TemplatePicker.svelte` mit Bestaetigungs-Dialog (bits-ui), Two-Column-Grid-Erweiterung in `Step2Stages.svelte`, Name/Shortcode-Conditional-Set-Logik, TestID-Inventar (10 TestIDs), Unit-Test-Suite fuer Koordinaten + IDs + Suggested-Flag, 15 AC-N-Kriterien (Given/When/Then), LoC-Uebersicht (~455 Gesamt, Override 500 noetig). Status `stub` → `draft`, Version `0.1` → `1.0`.
- 2026-05-09: Stub angelegt (Phase 3 der Epic-Master-Spec).
