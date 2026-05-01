---
entity_id: trip_edit_view
type: module
created: 2026-05-01
updated: 2026-05-01
status: draft
version: "1.0"
tags: [sveltekit, frontend, trips, edit, accordion, mobile-first]
---

# Trip Edit View (Akkordeon-Editor)

## Approval

- [x] Approved (2026-05-01, User)

## Purpose

Stellt eine Akkordeon-basierte Bearbeitungsansicht fuer bestehende Trips bereit, in der die vier Konfigurationsbereiche (Route, Etappen, Wetter, Reports) als aufklappbare Sektionen direkt angesprungen werden koennen — ohne den linearen Wizard-Stepper, der nur fuer die Neuerstellung sinnvoll ist. Loest GitHub Issue #91: User muessen sich beim Editieren nicht mehr durch alle 4 Schritte klicken, sondern oeffnen gezielt den gewuenschten Bereich (typischerweise Etappen).

## Scope

### In Scope

- Neue Komponente `TripEditView.svelte` mit Akkordeon-Layout (4 Sektionen)
- Wiederverwendung der bestehenden `WizardStep1Route`/`WizardStep2Stages`/`WizardStep3Weather`/`WizardStep4Reports`-Komponenten als Inhalt der Sektionen
- Initial geoeffnete Sektion: "Etappen" (haeufigster Edit-Case)
- Ein einziger Save-Button am Seitenende (kein Inline-Speichern pro Sektion)
- Abbrechen-Button → Navigation zurueck nach `/trips`
- Mobile-first Layout ab 375px (Safari Mobile getestet)
- Anpassung der Edit-Route `/trips/[id]/edit/+page.svelte`: `TripEditView` statt `TripWizard`

### Out of Scope

- Inline-Speichern pro Sektion (ein Save-Button reicht)
- Aenderungen am `TripWizard` (bleibt fuer `/trips/new` unveraendert)
- Backend-API-Aenderungen (`PUT /api/trips/{id}` existiert, Merge ist seit Issue #99/#103 sichergestellt)
- Karten-Preview, Drag-and-Drop-Reordering, Undo/Redo
- Aenderungen an `+page.server.ts` (Trip-Load bleibt identisch)

## Architecture

```
Browser

  /trips/[id]/edit
    +page.server.ts → fetch Trip via Go API (SSR mit Cookie) [unveraendert]
    +page.svelte    → <TripEditView trip={data.trip} />  [neu, ersetzt TripWizard]

  TripEditView.svelte
    ├── Header (Trip-Name, "Trip bearbeiten")
    ├── AccordionSection "Route"
    │     └── WizardStep1Route (eingebunden)
    ├── AccordionSection "Etappen"   ← initial geoeffnet
    │     └── WizardStep2Stages (eingebunden)
    ├── AccordionSection "Wetter"
    │     └── WizardStep3Weather (eingebunden)
    ├── AccordionSection "Reports"
    │     └── WizardStep4Reports (eingebunden)
    └── Action-Bar (sticky bottom)
          ├── Abbrechen → goto('/trips')
          └── Speichern → PUT /api/trips/{id} → goto('/trips')

  /trips/new
    → TripWizard mode="create"  [unveraendert]
```

## Source

### Neue Dateien

| Datei | Zweck | ~LOC |
|-------|-------|------|
| `frontend/src/lib/components/edit/TripEditView.svelte` | Akkordeon-Container, State, Save-Logik | ~180 |
| `frontend/src/lib/components/edit/AccordionSection.svelte` | Wiederverwendbare aufklappbare Sektion | ~60 |

### Geaenderte Dateien

| Datei | Aenderung |
|-------|-----------|
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | `<TripWizard mode="edit" .../>` → `<TripEditView trip={data.trip} />` |

### Unveraenderte Abhaengigkeiten

| Datei | Begruendung |
|-------|------------|
| `frontend/src/lib/components/wizard/TripWizard.svelte` | Bleibt fuer `/trips/new` aktiv |
| `frontend/src/lib/components/wizard/WizardStep1Route.svelte` | Wird in TripEditView wiederverwendet |
| `frontend/src/lib/components/wizard/WizardStep2Stages.svelte` | Wird in TripEditView wiederverwendet |
| `frontend/src/lib/components/wizard/WizardStep3Weather.svelte` | Wird in TripEditView wiederverwendet |
| `frontend/src/lib/components/wizard/WizardStep4Reports.svelte` | Wird in TripEditView wiederverwendet |
| `frontend/src/routes/trips/[id]/edit/+page.server.ts` | Trip-SSR-Load bleibt identisch |

### Gesamt: 2 neue + 1 geaenderte Datei, ~240 LOC

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Go API `GET /api/trips/{id}` | API (existiert) | Trip-Daten laden via SSR (`+page.server.ts`) |
| Go API `PUT /api/trips/{id}` | API (existiert, mergt seit Issue #99/#103) | Aenderungen persistieren ohne opaque Felder zu verlieren |
| `WizardStep1Route` | Komponente (existiert) | Route/GPX-Inhalt der "Route"-Sektion |
| `WizardStep2Stages` | Komponente (existiert) | Stages/Waypoints-Inhalt der "Etappen"-Sektion |
| `WizardStep3Weather` | Komponente (existiert) | weather_config-Inhalt der "Wetter"-Sektion |
| `WizardStep4Reports` | Komponente (existiert) | report_config-Inhalt der "Reports"-Sektion |
| `lib/types.ts` `Trip`, `Stage`, `Waypoint` | Types (existieren) | Datenmodell |
| `lib/api.ts` `api.put` | Modul (existiert) | PUT-Request fuer Save |
| `shadcn-svelte` Button, Card, Input | Library (existiert) | UI-Grundbausteine |
| SvelteKit `goto` | Framework | Navigation nach Save/Abbrechen |
| Svelte 5 `$state`, `$props` | Framework | Reaktiver State |

## Implementation Details

### Phase 1: AccordionSection-Komponente

```svelte
<!-- lib/components/edit/AccordionSection.svelte -->
<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    title: string;
    open: boolean;
    onToggle: () => void;
    children: Snippet;
  }
  let { title, open, onToggle, children }: Props = $props();
</script>

<div class="border rounded-lg mb-3 overflow-hidden">
  <button
    type="button"
    class="w-full flex justify-between items-center px-4 py-3 text-left
           font-medium bg-muted/50 hover:bg-muted active:bg-muted
           min-h-[48px]"
    aria-expanded={open}
    onclick={onToggle}
  >
    <span>{title}</span>
    <span aria-hidden="true">{open ? '−' : '+'}</span>
  </button>
  {#if open}
    <div class="p-4">
      {@render children()}
    </div>
  {/if}
</div>
```

Wichtig: `min-h-[48px]` als Touch-Target (Safari Mobile / iOS HIG).

### Phase 2: TripEditView Container

```svelte
<!-- lib/components/edit/TripEditView.svelte -->
<script lang="ts">
  import type { Trip, Stage } from '$lib/types';
  import { api } from '$lib/api';
  import { goto } from '$app/navigation';
  import AccordionSection from './AccordionSection.svelte';
  import WizardStep1Route from '$lib/components/wizard/WizardStep1Route.svelte';
  import WizardStep2Stages from '$lib/components/wizard/WizardStep2Stages.svelte';
  import WizardStep3Weather from '$lib/components/wizard/WizardStep3Weather.svelte';
  import WizardStep4Reports from '$lib/components/wizard/WizardStep4Reports.svelte';

  interface Props { trip: Trip; }
  let { trip }: Props = $props();

  // State: tiefe Kopie damit Cancel ohne Persistenz auch State verwirft
  let tripName = $state(trip.name);
  let stages: Stage[] = $state(JSON.parse(JSON.stringify(trip.stages)));
  let weatherConfig = $state(JSON.parse(JSON.stringify(trip.weather_config ?? {})));
  let reportConfig = $state(JSON.parse(JSON.stringify(trip.report_config ?? {})));
  let displayConfig = $state(JSON.parse(JSON.stringify(trip.display_config ?? {})));
  let avalancheRegions = $state(JSON.parse(JSON.stringify(trip.avalanche_regions ?? [])));
  let aggregation = $state(JSON.parse(JSON.stringify(trip.aggregation ?? {})));

  // Akkordeon: 'etappen' initial geoeffnet
  let openSection: 'route' | 'etappen' | 'wetter' | 'reports' | null = $state('etappen');

  let saveError: string | null = $state(null);
  let saving = $state(false);

  function makeToggleHandler(section: typeof openSection) {
    return function doToggle() {
      openSection = openSection === section ? null : section;
    };
  }

  async function save() {
    saveError = null;
    saving = true;
    try {
      const updated: Trip = {
        ...trip,
        name: tripName,
        stages,
        weather_config: weatherConfig,
        report_config: reportConfig,
        display_config: displayConfig,
        avalanche_regions: avalancheRegions,
        aggregation,
      };
      await api.put(`/api/trips/${trip.id}`, updated);
      goto('/trips');
    } catch (e) {
      saveError = e instanceof Error ? e.message : 'Speichern fehlgeschlagen';
    } finally {
      saving = false;
    }
  }

  function cancel() {
    goto('/trips');
  }
</script>

<div class="max-w-3xl mx-auto p-4 pb-24">
  <h1 class="text-xl font-semibold mb-4">Trip bearbeiten: {trip.name}</h1>

  <AccordionSection
    title="Route"
    open={openSection === 'route'}
    onToggle={makeToggleHandler('route')}
  >
    <WizardStep1Route bind:tripName bind:stages mode="edit" />
  </AccordionSection>

  <AccordionSection
    title="Etappen"
    open={openSection === 'etappen'}
    onToggle={makeToggleHandler('etappen')}
  >
    <WizardStep2Stages bind:stages />
  </AccordionSection>

  <AccordionSection
    title="Wetter"
    open={openSection === 'wetter'}
    onToggle={makeToggleHandler('wetter')}
  >
    <WizardStep3Weather bind:weatherConfig />
  </AccordionSection>

  <AccordionSection
    title="Reports"
    open={openSection === 'reports'}
    onToggle={makeToggleHandler('reports')}
  >
    <WizardStep4Reports bind:reportConfig />
  </AccordionSection>

  {#if saveError}
    <div class="mt-4 p-3 rounded bg-destructive/10 text-destructive text-sm">
      {saveError}
    </div>
  {/if}

  <div class="fixed bottom-0 left-0 right-0 bg-background border-t p-3
              flex gap-2 justify-end max-w-3xl mx-auto">
    <button type="button" class="btn-secondary min-h-[44px] px-4"
            onclick={cancel} disabled={saving}>
      Abbrechen
    </button>
    <button type="button" class="btn-primary min-h-[44px] px-4"
            onclick={save} disabled={saving}>
      {saving ? 'Speichere…' : 'Speichern'}
    </button>
  </div>
</div>
```

Hinweise:
- **Factory Pattern fuer Click-Handler** (`makeToggleHandler` → `doToggle`) gemaess CLAUDE.md (Safari-Closure-Binding).
- **Save-Bar `fixed bottom-0`** mit `pb-24` am Container, damit Inhalt nicht ueberdeckt wird.
- **`...trip` Spread vor Override**: bewahrt Felder die UI nicht kennt (defensiv, obwohl Backend seit Issue #103 mergt).

### Phase 3: Edit-Route umstellen

```svelte
<!-- frontend/src/routes/trips/[id]/edit/+page.svelte -->
<script lang="ts">
  import TripEditView from '$lib/components/edit/TripEditView.svelte';
  let { data } = $props();
</script>

<TripEditView trip={data.trip} />
```

`+page.server.ts` bleibt unveraendert.

### Phase 4: Step-Komponenten-Props pruefen

Falls `WizardStep1-4` aktuell ueber TripWizard-State per `bind:` gefuettert werden, sollten sie **bereits** mit `bind:`-Props arbeiten. Falls nicht, muessen die Komponenten so angepasst werden, dass sie ihren Teil-State via `$bindable()` exponieren — ohne ihre Wizard-Funktionalitaet zu brechen. Dies ist eine voraussichtlich kleine Anpassung; falls sie groesser ausfaellt, wird ein eigener Refactor-Spec erstellt.

## Expected Behavior

### Akzeptanzkriterien

1. **AC-1:** Klick auf "Bearbeiten" eines Trips in `/trips` oeffnet `/trips/{id}/edit`. Die Seite zeigt `TripEditView` (Akkordeon), **keinen** Stepper und **keinen** "Schritt 1 von 4"-Indikator.
2. **AC-2:** Alle 4 Sektionen ("Route", "Etappen", "Wetter", "Reports") sind als Akkordeon-Header sichtbar. Beim Initial-Render ist genau **eine** Sektion geoeffnet: **Etappen**.
3. **AC-3:** Bestehende Trip-Daten sind in den Sektionen vorgeladen: `name`, `stages` (mit Waypoints), `weather_config`, `report_config`, `display_config`, `avalanche_regions`, `aggregation`.
4. **AC-4:** Genau **ein** "Speichern"-Button am Seitenende sendet `PUT /api/trips/{id}` mit allen Aenderungen. Bei Erfolg → `goto('/trips')`.
5. **AC-5:** "Abbrechen"-Button navigiert zu `/trips` ohne API-Aufruf; State-Aenderungen werden verworfen.
6. **AC-6:** Auf Safari Mobile @ 375px Viewport: alle Sektion-Header sind lesbar (kein Truncation-Bug), das Akkordeon-Pattern funktioniert (Tap oeffnet/schliesst).

### Akkordeon-Verhalten

- **Single-open**: nur eine Sektion gleichzeitig offen. Tap auf einen anderen Header schliesst die aktuelle und oeffnet die neue.
- **Toggle-close**: Tap auf den aktuell offenen Header schliesst ihn (alle Sektionen geschlossen ist erlaubter Zustand).
- **Initial state**: `openSection = 'etappen'`.
- **Keine Tastatur-Hotkeys** in dieser Iteration; native Button-Semantik (Enter/Space) ist ausreichend.

### Save-Verhalten

- **Input:** aktueller State (tripName, stages, weatherConfig, reportConfig, displayConfig, avalancheRegions, aggregation).
- **Request:** `PUT /api/trips/{trip.id}` mit Body `{ ...trip, ...overrides }`. Das `...trip` Spread bewahrt defensiv alle Felder, die UI nicht kennt.
- **Output (Erfolg):** Navigation zu `/trips`.
- **Output (Fehler):** roter Alert-Block ueber der Action-Bar mit der Fehlermeldung; State bleibt erhalten, kein Navigieren.
- **Side effects:** persistiert geaenderten Trip via Backend-Merge (Issue #99/#103).

### Cancel-Verhalten

- **Input:** Klick auf "Abbrechen".
- **Output:** `goto('/trips')` ohne API-Aufruf.
- **Side effects:** keine. Lokaler State wird verworfen (Komponente unmountet).

## Test-Strategie

### Unit / Component-Tests (Vitest + @testing-library/svelte)

| Test | Zweck |
|------|-------|
| `AccordionSection` rendert `title`, ruft `onToggle` bei Klick | Pure-Component-Smoke |
| `AccordionSection` zeigt `children` nur wenn `open === true` | Conditional-Render |
| `TripEditView` initial: nur "Etappen"-Sektion offen | AC-2 |
| `TripEditView` Tap auf "Wetter"-Header: schliesst "Etappen", oeffnet "Wetter" | Single-open-Verhalten |
| `TripEditView` Tap auf bereits offenen Header: schliesst ihn | Toggle-close |
| `TripEditView` zeigt `trip.name` im Header und prefilled in Step1 | AC-3 |

### Integration-Tests (Playwright)

| Test | Zweck |
|------|-------|
| Auf `/trips/{id}/edit` navigieren → `TripEditView` sichtbar, kein Stepper im DOM | AC-1 |
| Etappen-Sektion ist initial offen (sichtbarer Stage-Editor) | AC-2 |
| Stage-Name aendern, Save klicken → PUT-Request gesendet, Redirect nach `/trips` | AC-4 |
| Stage-Name aendern, Cancel klicken → KEIN PUT-Request, Redirect nach `/trips` | AC-5 |
| Backend-Antwort 500 simulieren → Fehlermeldung sichtbar, Bleibt auf Edit-Page | Fehlerpfad |
| Mobile-Viewport 375x667, Safari WebKit: alle 4 Section-Header sichtbar, Tap oeffnet/schliesst | AC-6 |

### Datenintegritaets-Test

- Trip mit gesetzten `weather_config`, `report_config`, `display_config`, `avalanche_regions`, `aggregation` laden, **nur** Stage-Namen aendern, speichern, Trip neu laden — alle anderen Felder muessen unveraendert sein. Schuetzt vor Regression von Issue #102 (BUG-DATALOSS-GR221).

### Browser-Matrix

Reihenfolge gemaess CLAUDE.md "NiceGUI Safari-Kompatibilitaet" (gilt analog fuer SvelteKit-UI):

1. **Safari Mobile (375px)** — strengste; muss zuerst funktionieren
2. **Firefox** Desktop
3. **Chrome** Desktop

## Known Limitations

- Kein Inline-Speichern pro Sektion: Aenderungen in mehreren Sektionen werden gemeinsam gespeichert. Falls der Save fehlschlaegt, gehen alle parallelen Edits verloren (User sieht Fehlermeldung und kann erneut speichern, State bleibt im Memory).
- Kein Browser-Warning bei `beforeunload` mit ungespeicherten Aenderungen (kann in Folgeversion ergaenzt werden).
- Schritt-Komponenten-Wiederverwendung setzt voraus, dass `WizardStep1-4` ihren State per `$bindable()` exponieren. Falls nicht, ist eine kleine Refactor-Phase noetig (siehe Implementation Details Phase 4).
- Akkordeon-State (welche Sektion offen ist) wird nicht persistiert; Reload setzt zurueck auf "Etappen" offen.
- Keine Drag-and-Drop-Reordering der Sektionen — Reihenfolge ist fix (Route → Etappen → Wetter → Reports).

## Changelog

- 2026-05-01: Initial spec created (GitHub Issue #91)
