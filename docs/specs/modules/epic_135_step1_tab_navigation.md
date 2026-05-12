---
entity_id: epic_135_step1_tab_navigation
type: module
created: 2026-05-12
updated: 2026-05-12
status: approved
version: "1.0"
parent_spec: epic_135_trip_detail
related: epic_135_trip_detail
issue: 155
tags: [frontend, sveltekit, svelte5, bits-ui, tabs, trip-detail, epic-135, issue-155]
---

# Epic 135 — Sub-Spec #155: Trip-Detail Tab-Navigation

## Approval

- [x] Approved (2026-05-12)

## Status

**Draft** — bereit zur Freigabe durch User.

## Purpose

Definiert das Tab-Skelett der Trip-Detail-Seite (`/trips/[id]`): eine `TripTabs.svelte`-Wrapper-Komponente um `bits-ui/Tabs`, die 6 benannte Tabs (Übersicht, Etappen & Wegpunkte, Wetter-Metriken, Briefing-Zeitplan, Alerts, Vorschau) rendert, per URL-Hash synchronisiert und mit optionalen Badge-Zählern ausgestattet werden kann. Tab-Inhalte sind bewusst Placeholder-Texte, die auf die Folge-Sub-Issues verweisen, damit der Fortschritt sichtbar wird ohne einen Big-Bang-Merge abwarten zu müssen.

## Source

- **Route (NEU):** `frontend/src/routes/trips/[id]/+page.svelte` (~30 LoC)
- **Server-Loader (NEU):** `frontend/src/routes/trips/[id]/+page.server.ts` (~20 LoC)
- **Komponente (NEU):** `frontend/src/lib/components/trip-detail/TripTabs.svelte` (~80 LoC)
- **Barrel-Export (NEU):** `frontend/src/lib/components/trip-detail/index.ts` (~5 LoC)
- **E2E-Tests (NEU):** `frontend/e2e/trip-detail-tabs.spec.ts` (~50 LoC)
- **Identifier:** `TripTabs` (default export), `+page.server.ts` load-Funktion

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `bits-ui/Tabs` (`Tabs.Root`, `Tabs.List`, `Tabs.Trigger`, `Tabs.Content`) | package (bereits in `node_modules/bits-ui/`) | Headless ARIA-konforme Tab-Basis mit eingebauter Tastaturnavigation |
| `$app/navigation` (`goto`) | SvelteKit-API | URL-Hash bei Tab-Wechsel aktualisieren (`replaceState: true, noScroll: true`) |
| `$app/stores` (`page`) | SvelteKit-API | Initialen Tab aus `$page.url.hash` ableiten |
| `/api/trips/${id}` | Go-Backend-Endpoint | Trip per ID laden; 404 wenn nicht gefunden |
| `frontend/src/lib/types.ts` (`Trip`) | bestehend | Trip-Typ für den Server-Loader und die Route |
| `frontend/src/routes/trips/[id]/edit/+page.server.ts` | bestehend (Referenz) | Pattern für Trip-Loader + 404-Handling — kein Edit |

## Implementation Details

### §1 Tab-Definitionen (verbindlich)

| # | Label | Hash-Value | Placeholder-Text |
|---|-------|------------|-----------------|
| 1 | Übersicht | `overview` | `Inhalt folgt mit Issue #154 (Hero) + #156 (Höhenprofil) + #157 (Stage-Liste)` |
| 2 | Etappen & Wegpunkte | `stages` | `Inhalt folgt mit Epic #137 (Wegpunkt-Editor)` |
| 3 | Wetter-Metriken | `weather` | `Inhalt folgt mit Issue #158 + Epic #138 (Metriken-Editor)` |
| 4 | Briefing-Zeitplan | `briefings` | `Inhalt folgt mit Issue #159 (rechte Spalte)` |
| 5 | Alerts | `alerts` | `Inhalt folgt mit Epic #139 (Alert-Konfigurator)` |
| 6 | Vorschau | `preview` | `Inhalt folgt mit Issue #189 (Vorschau-Integration)` |

Default-Tab (kein Hash): `overview`.

### §2 `TripTabs.svelte` — Prop-Signatur

```typescript
// frontend/src/lib/components/trip-detail/TripTabs.svelte
interface Badges {
  overview?: number;
  stages?: number;
  weather?: number;
  briefings?: number;
  alerts?: number;
  preview?: number;
}

interface Props {
  /**
   * Initial-Tab aus URL-Hash (z.B. "alerts"). Wird beim Mounten gesetzt.
   * Default: "overview" wenn undefined oder unbekannter Wert.
   */
  initialTab?: string;
  /**
   * Optionale Badge-Zähler. Nur Einträge mit einem Wert >= 1 werden
   * als Badge gerendert. undefined-Einträge oder fehlender Key → kein Badge.
   */
  badges?: Badges;
}

let { initialTab = 'overview', badges = {} }: Props = $props();
```

### §3 Beispiel-Markup (`bits-ui`-Tabs-Verwendung)

```svelte
<script lang="ts">
  import { Tabs } from 'bits-ui';
  import { goto } from '$app/navigation';

  // ...Props-Deklaration aus §2...

  const TABS = [
    { value: 'overview',  label: 'Übersicht' },
    { value: 'stages',    label: 'Etappen & Wegpunkte' },
    { value: 'weather',   label: 'Wetter-Metriken' },
    { value: 'briefings', label: 'Briefing-Zeitplan' },
    { value: 'alerts',    label: 'Alerts' },
    { value: 'preview',   label: 'Vorschau' },
  ] as const;

  const PLACEHOLDERS: Record<string, string> = {
    overview:  'Inhalt folgt mit Issue #154 (Hero) + #156 (Höhenprofil) + #157 (Stage-Liste)',
    stages:    'Inhalt folgt mit Epic #137 (Wegpunkt-Editor)',
    weather:   'Inhalt folgt mit Issue #158 + Epic #138 (Metriken-Editor)',
    briefings: 'Inhalt folgt mit Issue #159 (rechte Spalte)',
    alerts:    'Inhalt folgt mit Epic #139 (Alert-Konfigurator)',
    preview:   'Inhalt folgt mit Issue #189 (Vorschau-Integration)',
  };

  const VALID_VALUES = TABS.map((t) => t.value);
  const resolvedInitial = VALID_VALUES.includes(initialTab as never)
    ? initialTab
    : 'overview';

  let activeTab = $state(resolvedInitial);

  function handleValueChange(value: string): void {
    activeTab = value;
    goto(`#${value}`, { replaceState: true, noScroll: true });
  }
</script>

<Tabs.Root value={activeTab} onValueChange={handleValueChange}>
  <Tabs.List data-testid="trip-detail-tab-list" class="flex border-b border-[var(--g-border)]">
    {#each TABS as tab}
      <Tabs.Trigger
        value={tab.value}
        data-testid="trip-detail-tab-{tab.value}"
        class="relative px-4 py-2 text-sm font-medium
               data-[state=active]:border-b-2 data-[state=active]:border-[var(--g-accent)]
               data-[state=inactive]:border-b-2 data-[state=inactive]:border-transparent"
      >
        {tab.label}
        {#if badges[tab.value] !== undefined}
          <span
            data-testid="trip-detail-tab-badge-{tab.value}"
            class="ml-1.5 rounded-full bg-[var(--g-accent)] px-1.5 py-0.5 text-xs font-semibold text-white"
          >
            {badges[tab.value]}
          </span>
        {/if}
      </Tabs.Trigger>
    {/each}
  </Tabs.List>

  {#each TABS as tab}
    <Tabs.Content value={tab.value} data-testid="trip-detail-panel-{tab.value}">
      <p class="p-4 text-sm text-[var(--g-ink-faint)]">{PLACEHOLDERS[tab.value]}</p>
    </Tabs.Content>
  {/each}
</Tabs.Root>
```

**Wichtig (Safari-Kompatibilität):** `onValueChange` erhält eine benannte Funktion
(`handleValueChange`), kein Inline-Arrow. Dies folgt dem Factory-/Named-Function-
Pattern aus `CLAUDE.md` und `epic_136_step1_profile.md` — Safari bindet Closures
weniger zuverlässig als Chrome.

### §4 `+page.server.ts` — Server-Loader

Pattern analog zu `frontend/src/routes/trips/[id]/edit/+page.server.ts`:

```typescript
// frontend/src/routes/trips/[id]/+page.server.ts
import type { PageServerLoad } from './$types';
import { error } from '@sveltejs/kit';

export const load: PageServerLoad = async ({ params, fetch }) => {
  const res = await fetch(`/api/trips/${params.id}`);
  if (res.status === 404) {
    throw error(404, `Trip '${params.id}' nicht gefunden`);
  }
  if (!res.ok) {
    throw error(res.status, 'Fehler beim Laden des Trips');
  }
  const trip = await res.json();
  return { trip };
};
```

### §5 `+page.svelte` — Route-Wrapper

```svelte
<!-- frontend/src/routes/trips/[id]/+page.svelte -->
<script lang="ts">
  import { page } from '$app/stores';
  import TripTabs from '$lib/components/trip-detail/TripTabs.svelte';

  let { data } = $props();

  // Hash ohne führendes '#', oder leer wenn kein Hash gesetzt
  const initialTab = $derived($page.url.hash.replace('#', '') || 'overview');
</script>

<TripTabs {initialTab} />
```

### §6 `index.ts` — Barrel-Export

```typescript
// frontend/src/lib/components/trip-detail/index.ts
export { default as TripTabs } from './TripTabs.svelte';
```

### §7 TestID-Inventar

| TestID | Element | Zweck |
|--------|---------|-------|
| `trip-detail-tab-list` | `Tabs.List` | Container der Tab-Trigger (für Count-Assertions) |
| `trip-detail-tab-overview` | `Tabs.Trigger` Übersicht | Tab-Trigger Sichtbarkeit + `data-state` |
| `trip-detail-tab-stages` | `Tabs.Trigger` Etappen | Tab-Trigger Sichtbarkeit + `data-state` |
| `trip-detail-tab-weather` | `Tabs.Trigger` Wetter-Metriken | Tab-Trigger Sichtbarkeit + `data-state` |
| `trip-detail-tab-briefings` | `Tabs.Trigger` Briefing-Zeitplan | Tab-Trigger Sichtbarkeit + `data-state` |
| `trip-detail-tab-alerts` | `Tabs.Trigger` Alerts | Tab-Trigger Sichtbarkeit + `data-state` |
| `trip-detail-tab-preview` | `Tabs.Trigger` Vorschau | Tab-Trigger Sichtbarkeit + `data-state` |
| `trip-detail-panel-overview` | `Tabs.Content` Übersicht | Panel-Sichtbarkeit |
| `trip-detail-panel-stages` | `Tabs.Content` Etappen | Panel-Sichtbarkeit |
| `trip-detail-panel-weather` | `Tabs.Content` Wetter-Metriken | Panel-Sichtbarkeit |
| `trip-detail-panel-briefings` | `Tabs.Content` Briefing-Zeitplan | Panel-Sichtbarkeit |
| `trip-detail-panel-alerts` | `Tabs.Content` Alerts | Panel-Sichtbarkeit |
| `trip-detail-panel-preview` | `Tabs.Content` Vorschau | Panel-Sichtbarkeit |
| `trip-detail-tab-badge-alerts` | Badge-Span im Alerts-Trigger | Badge-Sichtbarkeit + Text-Inhalt |
| `trip-detail-tab-badge-weather` | Badge-Span im Wetter-Trigger | Badge-Sichtbarkeit + Text-Inhalt |

### §8 Datei-Liste

#### NEU

| Datei | Zweck | LoC (Schätzung) |
|-------|-------|-----------------|
| `frontend/src/routes/trips/[id]/+page.svelte` | Route-Wrapper, bindet TripTabs + übergibt initialTab aus Hash | ~30 |
| `frontend/src/routes/trips/[id]/+page.server.ts` | Trip-Loader: GET `/api/trips/${id}`, wirft 404 bei not-found | ~20 |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | bits-ui-Tabs-Wrapper mit 6 Tabs, Hash-Sync, Badge-Props | ~80 |
| `frontend/src/lib/components/trip-detail/index.ts` | Barrel-Export für TripTabs | ~5 |
| `frontend/e2e/trip-detail-tabs.spec.ts` | Playwright-E2E: AC-1 bis AC-9 | ~50 |

#### NICHT BERÜHRT

- `frontend/src/lib/types.ts` (kein Edit)
- `internal/model/trip.go` (kein Edit)
- `internal/handler/trip.go` (kein Edit)
- `frontend/src/lib/components/trip-wizard/` (kein Edit)
- `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` — `TODO(epic-135)`-Marker bleibt bis zum letzten Sub-Issue von Epic #135

## Expected Behavior

- **Input:** SvelteKit-Route-Parameter `id` (Trip-UUID oder Slug), optionaler URL-Hash für den initialen aktiven Tab (`#overview`, `#stages`, `#weather`, `#briefings`, `#alerts`, `#preview`), optionale `badges`-Prop für TripTabs.
- **Output:** Vollständig gerenderte Trip-Detail-Seite mit Tab-Skelett; genau ein Tab-Panel ist sichtbar, die anderen fünf sind ausgeblendet (bits-ui-Standard: `display: none` auf inaktiven Panels). Jedes Panel zeigt den Placeholder-Text mit Verweis auf das zuständige Folge-Issue.
- **Side effects:** Bei Tab-Wechsel wird die URL mit `goto(url, { replaceState: true, noScroll: true })` aktualisiert — kein neuer History-Eintrag pro Klick, kein Scroll-Jump.

## Acceptance Criteria

- **AC-1:** Given ein bestehender Trip mit ID `e2e-cockpit-test` (aus E2E-Setup) / When die Route `/trips/e2e-cockpit-test` aufgerufen wird / Then antwortet der Server mit HTTP 200 UND die Seite rendert eine Tab-Liste (`data-testid="trip-detail-tab-list"`) mit genau 6 sichtbaren Tab-Triggern in dieser Reihenfolge: Übersicht, Etappen & Wegpunkte, Wetter-Metriken, Briefing-Zeitplan, Alerts, Vorschau.
  - Test: (populated after /tdd-red)

- **AC-2:** Given die Tab-Komponente ist gemountet ohne URL-Hash / When der initiale Zustand inspiziert wird / Then ist der Tab "Übersicht" als aktiv markiert (`data-state="active"`) UND nur das zugehörige Panel (`data-testid="trip-detail-panel-overview"`) ist sichtbar.
  - Test: (populated after /tdd-red)

- **AC-3:** Given die Tab-Komponente ist gemountet / When der User auf den Tab "Etappen & Wegpunkte" klickt / Then wechselt `data-state="active"` auf `data-testid="trip-detail-tab-stages"` UND die URL hat danach das Fragment `#stages` UND das Panel `trip-detail-panel-stages` zeigt den Text `Inhalt folgt mit Epic #137 (Wegpunkt-Editor)`.
  - Test: (populated after /tdd-red)

- **AC-4:** Given die Route wird mit Hash `/trips/e2e-cockpit-test#alerts` aufgerufen / When die Seite gemountet ist / Then ist der Tab "Alerts" initial aktiv (`data-state="active"` auf `trip-detail-tab-alerts`) UND das Panel `trip-detail-panel-alerts` zeigt den Text `Inhalt folgt mit Epic #139 (Alert-Konfigurator)`.
  - Test: (populated after /tdd-red)

- **AC-5:** Given die TripTabs-Komponente ist gemountet / When ein Tab als aktiv markiert ist / Then enthält dessen Trigger-Element eine sichtbare untere Linie in der Farbe `var(--g-accent)` (via `border-bottom` oder `data-[state=active]`-CSS). Nicht-aktive Tabs haben keine solche Linie (transparent border).
  - Test: (populated after /tdd-red)

- **AC-6:** Given die TripTabs-Komponente erhält die Prop `badges={{ alerts: 3, weather: 2 }}` / When sie gerendert wird / Then zeigt der Tab "Alerts" ein Badge-Element (`data-testid="trip-detail-tab-badge-alerts"`) mit Text `3` UND der Tab "Wetter-Metriken" ein Badge-Element (`data-testid="trip-detail-tab-badge-weather"`) mit Text `2`. Tabs ohne Badge-Eintrag (Übersicht, Etappen, Briefings, Vorschau) enthalten kein Element mit einem `trip-detail-tab-badge-*`-TestID.
  - Test: (populated after /tdd-red)

- **AC-7:** Given die TripTabs-Komponente ohne `badges`-Prop oder mit `badges={}` / When sie gerendert wird / Then enthält keiner der 6 Tab-Trigger ein Element dessen `data-testid` mit `trip-detail-tab-badge-` beginnt.
  - Test: (populated after /tdd-red)

- **AC-8:** Given eine Trip-ID die im Backend nicht existiert / When `/trips/unknown-id` aufgerufen wird / Then antwortet die Route mit HTTP 404 (analog zum Verhalten von `[id]/edit/`).
  - Test: (populated after /tdd-red)

- **AC-9:** Given die TripTabs-Komponente ist gemountet / When der User mit `Tab` zum aktiven Trigger navigiert und dann `ArrowRight` drückt / Then wandert der Fokus zum nächsten Tab-Trigger in der Reihenfolge (bits-ui ARIA/Tastaturnavigation ist aktiv).
  - Test: (populated after /tdd-red)

## Known Limitations

- **Tab-Inhalte sind Placeholder:** Bis zu den späteren Sub-Issues (#154, #156, #157, #158, #159 und Epics #137, #138, #139, #189) zeigt jedes Panel nur einen Hinweistext. Bewusste Entscheidung — macht Fortschritt sichtbar, vermeidet Big-Bang-Merge.
- **Badge-Quellen fehlen:** Aktuell übergibt die Route keine Badges (alle `undefined`). Die API-Endpoints für `active_alerts_count` und `metrics_count` kommen mit Sub-Issue #159 bzw. Epic #139.
- **`TODO(epic-135)`-Marker in `wizardState.svelte.ts`:** Wird mit diesem Issue NICHT entfernt. Der Marker wird mit dem letzten Sub-Issue von Epic #135 entfernt, wenn die Detail-Seite vollständig nutzbar ist.
- **Kein Trip-Header:** Name, Shortcode, Aktivitätsprofil werden in dieser Issue noch nicht gezeigt — das ist Issue #154 (Hero-Komponente).
- **Kein Ladeindikator:** Wenn der Server-Loader hängt, zeigt SvelteKit seinen Standard-Loader. Kein custom Skeleton-Screen in Scope für #155.

## Changelog

- 2026-05-12: Initial spec — Issue #155 (Epic #135 Sub-Spec: Tab-Navigation). bits-ui/Tabs als Headless-Basis, URL-Hash-Sync, 6 Tab-Definitionen, Badge-Prop, Placeholder-Panels, Server-Loader mit 404-Handling. 9 Acceptance Criteria im AC-N-Format. Datei-Liste (5 NEU), TestID-Inventar (15 IDs), Known Limitations (5 Einträge).
