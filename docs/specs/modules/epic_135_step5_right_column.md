---
entity_id: epic_135_step5_right_column
type: module
created: 2026-05-13
updated: 2026-05-13
status: draft
version: "1.0"
parent_spec: epic_135_trip_detail
related: epic_135_step4_left_column, epic_135_step3_trip_hero
issues: [158, 159]
followup_issues: [205, 206, 207, 189]
tags: [frontend, sveltekit, svelte5, trip-detail, epic-135, issue-158, issue-159]
---

# Epic 135 — Sub-Spec #158 + #159: Trip-Detail Overview, rechte Spalte (Briefings + Wetter-Metriken + Alerts + Vorschau)

## Approval

- [ ] Approved

## Purpose

Füllt den bisher leeren `<aside data-testid="trip-overview-right-column">` aus Step 4 mit vier read-only Vorschau-Karten im Overview-Tab der Trip-Detail-Seite: Briefings (#159), Wetter-Metriken (#158), Alerts (#159) und Vorschau (#159). Jede Karte zeigt den aktuellen Trip-Stand kompakt an und verlinkt über einen „Bearbeiten →"-Anker (URL-Hash) zum jeweiligen Tab. Die Implementierung bleibt frontend-only, lesend und greift defensiv über einen Pure-Function-Helper auf `trip.report_config` / `trip.weather_config` / `trip.aggregation` zu, bis Folge-Issues #205 (Alert-Datenmodell), #206 (Preset-Feld), #207 (strukturiertes report_config-Typing) und #189 (Preview-Tab) das Bild komplettieren.

## Source

- **NEU:** `frontend/src/lib/components/trip-detail/BriefingPreviewCard.svelte` — Briefing-Vorschau-Karte (Morgens-/Abends-/Alert-Status + „Bearbeiten →")
- **NEU:** `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` — Wetter-Metriken-Karte (Preset-Label + Tag-Chips)
- **NEU:** `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` — Alert-Karte (Skeleton bis #205)
- **NEU:** `frontend/src/lib/components/trip-detail/PreviewCard.svelte` — Vorschau-Karte mit 2 CTAs (Email + SMS)
- **NEU:** `frontend/src/lib/utils/rightColumn.ts` — Pure-Functions: `getPresetLabel`, `getDefaultMetricsForProfile`, `getActiveMetrics`, `getReportSchedule`, `prettyLabel`
- **NEU:** `frontend/src/lib/utils/rightColumn.test.ts` — Vitest-Unit-Tests (mind. 12)
- **NEU:** `frontend/e2e/trip-detail-overview-right.spec.ts` — Playwright E2E (mind. 12)
- **EDIT:** `frontend/src/lib/components/trip-detail/TripOverview.svelte` — Rechte Spalte (`<aside data-testid="trip-overview-right-column">`) bestückt mit 4 Karten in fixer Reihenfolge
- **EDIT:** `frontend/src/lib/components/trip-detail/index.ts` — Barrel-Export der 4 neuen Karten
- **EDIT:** `frontend/e2e/global.setup.ts` — `e2e-cockpit-test` Trip-Seed um `report_config`, `weather_config.metrics`, `aggregation.activity_profile` erweitern
- **Identifier:** `BriefingPreviewCard`, `WeatherMetricsPreviewCard`, `AlertsPreviewCard`, `PreviewCard`, `getPresetLabel`, `getDefaultMetricsForProfile`, `getActiveMetrics`, `getReportSchedule`, `prettyLabel`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/types.ts` (`Trip`) | bestehend | Lesender Zugriff auf `trip.report_config` (generisch `Record<string, unknown>`), `trip.weather_config`, `trip.aggregation` |
| `frontend/src/lib/components/trip-detail/TripOverview.svelte` | bestehend (EDIT, Step 4) | Hat den `<aside data-testid="trip-overview-right-column">`-Slot; nur Slot-Inhalt wird ergänzt, `selectedStageId`-State bleibt unverändert |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | bestehend (Step 1/2) | Hash-Navigation: `<a href="#briefings">`, `#weather`, `#alerts`, `#preview` setzt den Tab-State via bestehendem `hashchange`-Listener |
| `frontend/src/lib/components/trip-detail/index.ts` | bestehend (EDIT) | Barrel: 4 neue Karten exportieren |
| `frontend/src/lib/components/ui/g-card/GCard.svelte` | bestehend | Card-Container für alle 4 Karten |
| `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte` | bestehend | Eyebrow-Label (`Briefings`, `Wetter-Metriken`, `Alerts`, `Vorschau`) |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | bestehend | Tag-Chips für aktive Metriken in der Wetter-Karte |
| `frontend/src/app.css` (Tokens) | bestehend | `--g-accent`, semantische Farben (success/warning/danger), Surface-Stufen |
| `frontend/src/lib/utils/tripHero.ts` (`getNextBriefing`) | bestehend (Referenz) | Format-Vorbild für Briefing-Zeiten — Step 5 liest jedoch Raw-Zeiten aus `report_config` |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` (`BriefingConfig`, `defaultBriefingConfig`) | bestehend (Referenz) | Strukturierter Briefing-Typ als Vorbild — Step 5 bleibt generisch, bis #207 echtes Typing liefert |
| `frontend/src/routes/_cockpit/BriefingsTimeline.svelte` | bestehend (Stil-Vorbild) | Layout-Muster: GCard + Eyebrow + Zeit-Liste mit Dot-Status |
| `frontend/src/routes/_cockpit/AlertFeed.svelte` | bestehend (Stil-Vorbild) | Cockpit-Alert-Card (Placeholder) — visuelles Empty-State-Muster |
| `frontend/e2e/global.setup.ts` (`e2e-cockpit-test`) | bestehend (EDIT) | Test-Trip um `report_config`, `weather_config.metrics`, `aggregation.activity_profile` erweitern |
| `frontend/e2e/trip-detail-hero.spec.ts` | bestehend (Regressions-Guard) | Step-3-AC-6 (Trip ohne report_config → „Briefings deaktiviert") wird durch Trip-Seed-Edit beeinflusst — siehe Known Limitations |
| `frontend/e2e/trip-detail-overview-left.spec.ts` | bestehend (Regressions-Guard) | Step-4-Tests dürfen durch das Bestücken des rechten Slots nicht brechen |
| `internal/model/segment.go` | bestehend (Referenz) | Liste der 18 möglichen Wetter-Metriken (Quelle der Metrik-Keys für `getDefaultMetricsForProfile` und `prettyLabel`) |

## Implementation Details

### §1 Pure-Functions `frontend/src/lib/utils/rightColumn.ts`

Alle Funktionen sind pure (kein Side-Effect, kein I/O), vollständig unit-testbar. Sie kapseln den unsauberen `Record<string, unknown>`-Zugriff an einer Stelle, bis #207 strukturiertes Typing liefert.

```typescript
import type { Trip } from '$lib/types';

const DEFAULT_LABEL = 'Standard-Metriken';

export function getPresetLabel(trip: Trip): string {
  // Leitet das Preset-Label aus aggregation.activity_profile ab (provisional bis #206).
  //   'wintersport' -> 'Wintersport-Standard'
  //   'wandern'     -> 'Wandern-Standard'
  //   'allgemein'   -> 'Standard-Metriken'
  //   unbekannt/null/undefined -> 'Standard-Metriken'
  const profile = (trip.aggregation as Record<string, unknown> | undefined)?.activity_profile;
  if (profile === 'wintersport') return 'Wintersport-Standard';
  if (profile === 'wandern')     return 'Wandern-Standard';
  if (profile === 'allgemein')   return DEFAULT_LABEL;
  return DEFAULT_LABEL;
}

export function getDefaultMetricsForProfile(profile: unknown): string[] {
  // Default-Metrik-Set wenn weather_config.metrics fehlt.
  //   'wintersport' -> ['temp_min', 'temp_max', 'wind_max', 'snow_new', 'snow_depth', 'thunder_level']
  //   'wandern'     -> ['temp_min', 'temp_max', 'wind_max', 'precip_sum', 'thunder_level', 'cloud_avg']
  //   'allgemein'   -> ['temp_min', 'temp_max', 'wind_max', 'precip_sum']
  //   sonst         -> []
  if (profile === 'wintersport')
    return ['temp_min', 'temp_max', 'wind_max', 'snow_new', 'snow_depth', 'thunder_level'];
  if (profile === 'wandern')
    return ['temp_min', 'temp_max', 'wind_max', 'precip_sum', 'thunder_level', 'cloud_avg'];
  if (profile === 'allgemein')
    return ['temp_min', 'temp_max', 'wind_max', 'precip_sum'];
  return [];
}

export function getActiveMetrics(trip: Trip): string[] {
  // Liest weather_config.metrics falls Array von Strings, sonst Default-Set aus aggregation.activity_profile.
  const wc = trip.weather_config as Record<string, unknown> | undefined;
  const metrics = wc?.metrics;
  if (Array.isArray(metrics) && metrics.every((m) => typeof m === 'string')) {
    return metrics as string[];
  }
  const profile = (trip.aggregation as Record<string, unknown> | undefined)?.activity_profile;
  return getDefaultMetricsForProfile(profile);
}

export interface ReportSchedule {
  morning?: string;
  evening?: string;
  alertOnChanges: boolean;
  enabled: boolean;
}

export function getReportSchedule(trip: Trip): ReportSchedule {
  // Strukturierter Adapter über generisches report_config.
  //   - kein report_config -> { enabled: false, alertOnChanges: false }
  //   - enabled aus rc.enabled (default false)
  //   - morning aus rc.morning_time (string oder undefined)
  //   - evening aus rc.evening_time (string oder undefined)
  //   - alertOnChanges aus rc.alert_on_changes (default false)
  const rc = trip.report_config as Record<string, unknown> | undefined;
  if (!rc) return { enabled: false, alertOnChanges: false };
  return {
    enabled: rc.enabled === true,
    morning: typeof rc.morning_time === 'string' ? (rc.morning_time as string) : undefined,
    evening: typeof rc.evening_time === 'string' ? (rc.evening_time as string) : undefined,
    alertOnChanges: rc.alert_on_changes === true,
  };
}

const METRIC_LABELS: Record<string, string> = {
  temp_min:      'Min-Temp',
  temp_max:      'Max-Temp',
  wind_max:      'Wind',
  gust_max:      'Böen',
  precip_sum:    'Niederschlag',
  thunder_level: 'Gewitter',
  cloud_avg:     'Bewölkung',
  humidity_avg:  'Feuchte',
  snow_new:      'Neuschnee',
  snow_depth:    'Schneehöhe',
};

export function prettyLabel(metricKey: string): string {
  // Lesbares Label für UI-Pills. Unbekannte Keys -> Key selbst (Fallback ist erlaubt).
  return METRIC_LABELS[metricKey] ?? metricKey;
}
```

### §2 `frontend/src/lib/components/trip-detail/BriefingPreviewCard.svelte`

**Prop-Signatur:**

```typescript
import type { Trip } from '$lib/types';
import GCard from '$lib/components/ui/g-card/GCard.svelte';
import Eyebrow from '$lib/components/ui/eyebrow/Eyebrow.svelte';
import { getReportSchedule } from '$lib/utils/rightColumn';

interface Props { trip: Trip; }
let { trip }: Props = $props();

const schedule = $derived(getReportSchedule(trip));
```

**Template-Struktur:**

```svelte
<GCard data-testid="right-card-briefings" class="...">
  <Eyebrow>Briefings</Eyebrow>
  <h3>Tägliche Reports</h3>

  {#if !schedule.enabled && !schedule.morning && !schedule.evening}
    <p class="empty-state">Briefings deaktiviert</p>
  {:else}
    <ul class="schedule-list">
      <li data-testid="right-card-briefings-morning">
        <span class="dot" data-tone={schedule.enabled && schedule.morning ? 'success' : 'muted'}></span>
        Morgens · {schedule.morning ?? '—'}
      </li>
      <li data-testid="right-card-briefings-evening">
        <span class="dot" data-tone={schedule.enabled && schedule.evening ? 'success' : 'muted'}></span>
        Abends · {schedule.evening ?? '—'}
      </li>
      <li data-testid="right-card-briefings-alerts">
        <span class="dot" data-tone={schedule.alertOnChanges ? 'success' : 'muted'}></span>
        Alerts bei Änderungen · {schedule.alertOnChanges ? 'an' : 'aus'}
      </li>
    </ul>
  {/if}

  <a href="#briefings" data-testid="right-card-briefings-edit-link">Bearbeiten →</a>
</GCard>
```

Empty-State (`!schedule.enabled && !schedule.morning && !schedule.evening`) zeigt nur „Briefings deaktiviert" — der „Bearbeiten →"-Link bleibt sichtbar und klickbar.

### §3 `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte`

**Prop-Signatur:**

```typescript
import type { Trip } from '$lib/types';
import GCard from '$lib/components/ui/g-card/GCard.svelte';
import Eyebrow from '$lib/components/ui/eyebrow/Eyebrow.svelte';
import Pill from '$lib/components/ui/pill/Pill.svelte';
import { getPresetLabel, getActiveMetrics, prettyLabel } from '$lib/utils/rightColumn';

interface Props { trip: Trip; }
let { trip }: Props = $props();

const presetLabel = $derived(getPresetLabel(trip));
const metrics = $derived(getActiveMetrics(trip));
```

**Template-Struktur:**

```svelte
<GCard data-testid="right-card-weather" class="...">
  <Eyebrow>Wetter-Metriken</Eyebrow>
  <h3 data-testid="right-card-weather-preset">{presetLabel}</h3>

  {#if metrics.length === 0}
    <p class="empty-state">Keine Metriken aktiv</p>
  {:else}
    <div class="chips" data-testid="right-card-weather-chips">
      {#each metrics as metric (metric)}
        <Pill tone="default" data-testid="right-card-weather-chip-{metric}">
          {prettyLabel(metric)}
        </Pill>
      {/each}
    </div>
  {/if}

  <a href="#weather" data-testid="right-card-weather-edit-link">Bearbeiten →</a>
</GCard>
```

### §4 `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte`

**Prop-Signatur:**

```typescript
import type { Trip } from '$lib/types';
import GCard from '$lib/components/ui/g-card/GCard.svelte';
import Eyebrow from '$lib/components/ui/eyebrow/Eyebrow.svelte';

interface Props { trip: Trip; }
let { trip }: Props = $props();
```

**Template-Struktur:** (Skeleton bis #205 die Datenmodell-Erweiterung liefert)

```svelte
<GCard data-testid="right-card-alerts" class="...">
  <Eyebrow>Alerts</Eyebrow>
  <h3>Wetter-Warnungen</h3>

  <p class="empty-state" data-testid="right-card-alerts-empty">
    Noch keine Alerts konfiguriert
  </p>

  <a href="#alerts" data-testid="right-card-alerts-edit-link">Konfigurieren →</a>
</GCard>
```

Wording „Konfigurieren →" weicht bewusst von den anderen „Bearbeiten →"-Links ab, weil nichts zu bearbeiten ist.

### §5 `frontend/src/lib/components/trip-detail/PreviewCard.svelte`

**Prop-Signatur:**

```typescript
import type { Trip } from '$lib/types';
import GCard from '$lib/components/ui/g-card/GCard.svelte';
import Eyebrow from '$lib/components/ui/eyebrow/Eyebrow.svelte';

interface Props { trip: Trip; }
let { trip }: Props = $props();
```

**Template-Struktur:**

```svelte
<GCard data-testid="right-card-preview" class="...">
  <Eyebrow>Vorschau</Eyebrow>
  <h3>Wie sehen Reports aus?</h3>

  <div class="cta-stack">
    <a href="#preview" data-channel="email" data-testid="right-card-preview-email">
      E-Mail-Vorschau →
    </a>
    <a href="#preview" data-channel="sms" data-testid="right-card-preview-sms">
      SMS-Vorschau →
    </a>
  </div>
</GCard>
```

Beide CTAs setzen denselben Hash `#preview`; die Channel-Differenzierung (`data-channel`) wird vom Preview-Tab (Issue #189) ausgewertet. Für Step 5 reicht der Tab-Wechsel.

### §6 TripOverview-Edit `frontend/src/lib/components/trip-detail/TripOverview.svelte`

**Vorher (Step 4):**

```svelte
<aside data-testid="trip-overview-right-column">
  <!-- Platzhalter für #158 (Tagespanel) und #159 (Briefing-Konfigurator) -->
</aside>
```

**Nachher (Step 5):**

```svelte
<script>
  import BriefingPreviewCard from './BriefingPreviewCard.svelte';
  import WeatherMetricsPreviewCard from './WeatherMetricsPreviewCard.svelte';
  import AlertsPreviewCard from './AlertsPreviewCard.svelte';
  import PreviewCard from './PreviewCard.svelte';
</script>

<aside data-testid="trip-overview-right-column" class="space-y-4">
  <BriefingPreviewCard {trip} />
  <WeatherMetricsPreviewCard {trip} />
  <AlertsPreviewCard {trip} />
  <PreviewCard {trip} />
</aside>
```

Reihenfolge fest: **Briefings → Wetter-Metriken → Alerts → Vorschau**. Der bestehende `selectedStageId`-State und die linke Spalte bleiben komplett unverändert.

### §7 Barrel-Edit `frontend/src/lib/components/trip-detail/index.ts`

Vier neue Zeilen ergänzen:

```typescript
export { default as BriefingPreviewCard }       from './BriefingPreviewCard.svelte';
export { default as WeatherMetricsPreviewCard } from './WeatherMetricsPreviewCard.svelte';
export { default as AlertsPreviewCard }         from './AlertsPreviewCard.svelte';
export { default as PreviewCard }               from './PreviewCard.svelte';
```

Bestehende Exports (`TripOverview`, `FullProfile`, `StageList`, `StageDetailRow`, `TripHero`, Header/Tabs) bleiben unverändert.

### §8 Test-Trip-Erweiterung `frontend/e2e/global.setup.ts`

Der bestehende `e2e-cockpit-test` Trip-Seed wird **minimal-additiv** erweitert. Bestehende Felder (Name, Stages, Waypoints, Status) bleiben unverändert:

```typescript
// Bestehender Trip-Seed, plus drei neue Felder:
{
  id: 'e2e-cockpit-test',
  // ... bestehende Felder unverändert ...
  report_config: {
    enabled: true,
    morning_time: '06:00:00',
    evening_time: '18:00:00',
    alert_on_changes: true,
  },
  weather_config: {
    metrics: ['temp_min', 'temp_max', 'wind_max', 'precip_sum'],
  },
  aggregation: {
    activity_profile: 'wandern',
  },
}
```

**Auswirkung auf Step-3-AC-6:** Der Step-3-Hero-Test, der einen Trip OHNE `report_config` voraussetzt, kann diesen geänderten Seed nicht mehr verwenden. Das ist explizit Known Limitation — eine Anpassung in `trip-detail-hero.spec.ts` (separater Test-Trip-Eintrag) ist OUT OF SCOPE für Step 5 und wird via Folge-Bugfix oder Issue #204 nachgezogen.

### §9 TestID-Inventar

| TestID | Element | Zweck |
|--------|---------|-------|
| `trip-overview-right-column` | `<aside>` (bestehend, aus Step 4) | Container der 4 Karten — Existenz- und Reihenfolge-Check |
| `right-card-briefings` | `<GCard>` Briefing-Karte | Existenz-Check |
| `right-card-briefings-morning` | `<li>` Morgen-Zeile | Text + Dot-Tone |
| `right-card-briefings-evening` | `<li>` Abend-Zeile | Text + Dot-Tone |
| `right-card-briefings-alerts` | `<li>` Alert-Toggle-Zeile | Text „an"/„aus" + Dot-Tone |
| `right-card-briefings-edit-link` | `<a href="#briefings">` | Klick-Ziel → URL-Hash `#briefings` |
| `right-card-weather` | `<GCard>` Wetter-Karte | Existenz-Check |
| `right-card-weather-preset` | `<h3>` Preset-Label | Text aus `getPresetLabel(trip)` |
| `right-card-weather-chip-{metricKey}` | `<Pill>` pro Metrik | Tag-Chip Sichtbarkeit pro aktive Metrik |
| `right-card-weather-edit-link` | `<a href="#weather">` | Klick-Ziel → URL-Hash `#weather` |
| `right-card-alerts` | `<GCard>` Alert-Karte | Existenz-Check |
| `right-card-alerts-empty` | `<p>` Empty-State | „Noch keine Alerts konfiguriert" Sichtbarkeit |
| `right-card-alerts-edit-link` | `<a href="#alerts">` | Klick-Ziel → URL-Hash `#alerts` |
| `right-card-preview` | `<GCard>` Vorschau-Karte | Existenz-Check |
| `right-card-preview-email` | `<a href="#preview" data-channel="email">` | Klick-Ziel → URL-Hash `#preview` |
| `right-card-preview-sms` | `<a href="#preview" data-channel="sms">` | Klick-Ziel → URL-Hash `#preview` |

### §10 Datei-Liste

| Art | Datei | Zweck | LoC |
|-----|-------|-------|-----|
| NEU | `frontend/src/lib/components/trip-detail/BriefingPreviewCard.svelte` | Briefing-Karte (Morgens/Abends/Alert + „Bearbeiten →") | ~90 |
| NEU | `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` | Wetter-Metriken-Karte (Preset + Tag-Chips) | ~80 |
| NEU | `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` | Alert-Karte (Skeleton) | ~50 |
| NEU | `frontend/src/lib/components/trip-detail/PreviewCard.svelte` | Vorschau-Karte (Email + SMS CTAs) | ~60 |
| NEU | `frontend/src/lib/utils/rightColumn.ts` | Pure-Functions: `getPresetLabel`, `getDefaultMetricsForProfile`, `getActiveMetrics`, `getReportSchedule`, `prettyLabel` | ~80 |
| NEU | `frontend/src/lib/utils/rightColumn.test.ts` | Vitest-Unit-Tests (mind. 12) | ~120 |
| NEU | `frontend/e2e/trip-detail-overview-right.spec.ts` | Playwright E2E (mind. 12) | ~140 |
| EDIT | `frontend/src/lib/components/trip-detail/TripOverview.svelte` | Rechte Spalte mit 4 Karten bestücken (statt leerem Platzhalter) | +12 |
| EDIT | `frontend/src/lib/components/trip-detail/index.ts` | Barrel-Export 4 neuer Karten | +4 |
| EDIT | `frontend/e2e/global.setup.ts` | Test-Trip um `report_config`, `weather_config.metrics`, `aggregation.activity_profile` erweitern | +12 |
| **Summe** | | | **~648 LoC** |

**LoC-Override erforderlich vor Phase 6:** `workflow.py set-field loc_limit_override 700 --name epic_135_step5_right_column`

## Expected Behavior

- **Input:** `Trip`-Objekt mit beliebig vorhandenen/fehlenden Feldern `report_config`, `weather_config`, `aggregation` (alle generisch `Record<string, unknown>` getypt).
- **Output:**
  - `getPresetLabel(trip)` liefert deterministisch `'Wintersport-Standard'`, `'Wandern-Standard'` oder `'Standard-Metriken'`.
  - `getDefaultMetricsForProfile(profile)` liefert ein deterministisches Default-Set pro Aktivitätsprofil (oder `[]` für unbekannt).
  - `getActiveMetrics(trip)` liefert entweder die explizit konfigurierten `weather_config.metrics` oder das Default-Set für das Profil.
  - `getReportSchedule(trip)` liefert ein strukturiertes `{ morning?, evening?, alertOnChanges, enabled }`-Objekt; ohne `report_config` ist `enabled === false` und `alertOnChanges === false`.
  - `prettyLabel(metricKey)` liefert ein lesbares deutsches Label oder den Original-Key als Fallback.
  - `BriefingPreviewCard` rendert Morgen-/Abend-/Alert-Zeilen mit Dot-Tone, oder den Empty-State „Briefings deaktiviert" wenn weder Zeiten noch enabled gesetzt sind; „Bearbeiten →" zeigt immer.
  - `WeatherMetricsPreviewCard` rendert das Preset-Label als `<h3>` und N Tag-Chips für N aktive Metriken; bei leerer Liste „Keine Metriken aktiv".
  - `AlertsPreviewCard` rendert immer den Skeleton-Empty-State „Noch keine Alerts konfiguriert" + „Konfigurieren →"-Link.
  - `PreviewCard` rendert 2 CTAs (Email/SMS), beide mit `href="#preview"`, unterscheidbar via `data-channel`.
  - `TripOverview` rendert die 4 Karten in fester DOM-Reihenfolge im `<aside data-testid="trip-overview-right-column">`.
- **Side effects:**
  - Keine externen — alle Helper sind pure. UI-State ist read-only (keine `$state`-Variablen in den Karten).
  - Keine API-Calls — alle Daten kommen aus dem `trip`-Prop, das `+page.server.ts` bereits geladen hat.
  - Klick auf „Bearbeiten →"/„Konfigurieren →"/CTA setzt nur den URL-Hash; der bestehende `hashchange`-Listener in `TripTabs` wechselt den Tab.

## Acceptance Criteria

- **AC-1:** Given eine gerenderte Trip-Detail-Seite mit gültigem Trip und aktivem Overview-Tab / When der DOM von `[data-testid="trip-overview-right-column"]` inspiziert wird / Then enthält er genau 4 Karten in dieser DOM-Reihenfolge: `right-card-briefings`, `right-card-weather`, `right-card-alerts`, `right-card-preview`.
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Trip mit `report_config = { enabled: true, morning_time: '06:00:00', evening_time: '18:00:00', alert_on_changes: true }` / When die Briefing-Karte gerendert wird / Then enthalten `right-card-briefings-morning` den Text `'06:00:00'`, `right-card-briefings-evening` den Text `'18:00:00'` und `right-card-briefings-alerts` das Wort `'an'`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein Trip mit `report_config = { enabled: false }` (keine Zeiten) / When die Briefing-Karte gerendert wird / Then ist der Empty-State-Text „Briefings deaktiviert" sichtbar und `right-card-briefings-morning`/`-evening`/`-alerts` sind nicht im DOM, aber `right-card-briefings-edit-link` bleibt sichtbar und klickbar.
  - Test: (populated after /tdd-red)

- **AC-4:** Given eine gerenderte Trip-Detail-Seite / When der User auf `right-card-briefings-edit-link` klickt / Then ändert sich der URL-Hash zu `#briefings` und das Briefings-Tab ist im `TripTabs` aktiv.
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein Trip mit `aggregation.activity_profile = 'wandern'` / When die Wetter-Metriken-Karte gerendert wird / Then enthält `right-card-weather-preset` den Text `'Wandern-Standard'` als `<h3>`.
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein Trip mit `weather_config.metrics = ['temp_min', 'temp_max', 'wind_max', 'precip_sum']` / When die Wetter-Metriken-Karte gerendert wird / Then sind im DOM genau 4 Pills `right-card-weather-chip-temp_min`, `right-card-weather-chip-temp_max`, `right-card-weather-chip-wind_max`, `right-card-weather-chip-precip_sum` sichtbar.
  - Test: (populated after /tdd-red)

- **AC-7:** Given eine gerenderte Trip-Detail-Seite / When der User auf `right-card-weather-edit-link` klickt / Then ändert sich der URL-Hash zu `#weather` und das Wetter-Tab ist aktiv.
  - Test: (populated after /tdd-red)

- **AC-8:** Given die Alert-Karte rendert für einen beliebigen Trip / When der DOM inspiziert wird / Then ist `right-card-alerts-empty` sichtbar mit Text „Noch keine Alerts konfiguriert" und `right-card-alerts-edit-link` zeigt das Wort „Konfigurieren".
  - Test: (populated after /tdd-red)

- **AC-9:** Given eine gerenderte Trip-Detail-Seite / When der User auf `right-card-alerts-edit-link` klickt / Then ändert sich der URL-Hash zu `#alerts` und das Alert-Tab ist aktiv.
  - Test: (populated after /tdd-red)

- **AC-10:** Given die Vorschau-Karte rendert / When der DOM inspiziert wird / Then sind genau 2 CTAs sichtbar: `right-card-preview-email` und `right-card-preview-sms`, beide mit `href="#preview"`.
  - Test: (populated after /tdd-red)

- **AC-11:** Given eine gerenderte Trip-Detail-Seite / When der User auf `right-card-preview-email` klickt / Then ändert sich der URL-Hash zu `#preview` und das Preview-Tab ist aktiv.
  - Test: (populated after /tdd-red)

- **AC-12:** Given eine gerenderte Trip-Detail-Seite / When der User auf `right-card-preview-sms` klickt / Then ändert sich der URL-Hash zu `#preview` und das Preview-Tab ist aktiv (gleicher Hash, Channel-Differenzierung via `data-channel`-Attribut).
  - Test: (populated after /tdd-red)

- **AC-13:** Given die Pure-Function `getPresetLabel` / When sie mit Trips aufgerufen wird, deren `aggregation.activity_profile` jeweils `'wintersport'`, `'wandern'`, `'allgemein'` und `null` ist / Then liefert sie genau `'Wintersport-Standard'`, `'Wandern-Standard'`, `'Standard-Metriken'`, `'Standard-Metriken'`.
  - Test: (populated after /tdd-red)

- **AC-14:** Given die Pure-Function `getActiveMetrics` / When sie mit Trip `{ weather_config: { metrics: ['temp_min', 'wind_max'] } }` aufgerufen wird / Then liefert sie genau `['temp_min', 'wind_max']`; und mit Trip `{ aggregation: { activity_profile: 'wandern' } }` ohne `weather_config.metrics` liefert sie das Wandern-Default-Set (`['temp_min','temp_max','wind_max','precip_sum','thunder_level','cloud_avg']`).
  - Test: (populated after /tdd-red)

- **AC-15:** Given die Pure-Function `getReportSchedule` / When sie mit Trip `{ report_config: { enabled: true, morning_time: '06:00', evening_time: '18:00', alert_on_changes: true } }` aufgerufen wird / Then liefert sie `{ enabled: true, morning: '06:00', evening: '18:00', alertOnChanges: true }`; und ohne `report_config` liefert sie `{ enabled: false, alertOnChanges: false }` (morning/evening undefined).
  - Test: (populated after /tdd-red)

- **AC-16:** Given eine gerenderte Trip-Detail-Seite mit Step-5-Änderungen und aktivem Overview-Tab / When der DOM inspiziert wird / Then sind alle Step-3-TestIDs (`trip-hero`, `trip-hero-title`) und alle Step-4-TestIDs (`trip-overview`, `trip-overview-left-column`, `trip-full-profile`, `trip-stage-list`) weiterhin sichtbar (Regressions-Guard für Hero + linke Spalte).
  - Test: (populated after /tdd-red)

- **AC-17:** Given eine gerenderte Trip-Detail-Seite / When das Overview-Tab aktiv ist / Then sind die Step-1-TestID `trip-detail-tab-list` (Tab-Navigation) und die Step-2-TestID `trip-detail-breadcrumb` (Header) weiterhin sichtbar und unverändert (Regressions-Guard für Tabs + Header).
  - Test: (populated after /tdd-red)

- **AC-18:** Given ein Trip OHNE `report_config` (separater Test-Trip oder explizit nullifizierter Mock) / When die Briefing-Karte gerendert wird / Then zeigt sie den Empty-State „Briefings deaktiviert" und der `right-card-briefings-edit-link` ist trotzdem sichtbar und führt bei Klick zu URL-Hash `#briefings`.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Alert-Card ist Skeleton:** Inhalt blockiert auf Issue #205 (`Trip.alert_rules` fehlt im Datenmodell, Frontend + Backend). Bis dahin zeigt die Karte nur den Empty-State + „Konfigurieren →"-Link.
- **Wetter-Metriken-Preset-Name provisional:** Solange `weather_config.preset_name` fehlt, leitet `getPresetLabel` das Label aus `aggregation.activity_profile` ab. Folge-Issue #206 trackt das echte Preset-Feld.
- **`report_config` generisch typisiert:** Bleibt `Record<string, unknown>`. Der Helper `getReportSchedule` kapselt den unsauberen Zugriff. Folge-Issue #207 liefert strukturiertes Typing (analog `BriefingConfig` aus dem Wizard).
- **„Bearbeiten →"-Links zeigen auf Tab-Placeholders:** Die jeweiligen Tab-Inhalte (Briefings, Wetter, Alerts) sind noch nicht implementiert. Tab-Wechsel funktioniert, aber der User landet auf einer leeren Seite. Transparente Folge-Arbeit, kein Bug.
- **Vorschau-CTAs setzen nur `#preview`:** Channel-Differenzierung (Email vs. SMS) wird im Preview-Tab (Issue #189) ausgewertet — beide CTAs nutzen denselben Hash, unterscheidbar nur über das `data-channel`-Attribut. Für Step 5 reicht der Tab-Wechsel.
- **Frontend = Desktop-Planungstool:** Unter `lg:`-Breakpoint stapelt das bestehende 2-Spalten-Grid; die rechte Spalte erscheint unter der linken. Funktional korrekt, aber visuell nicht mobile-optimiert. Mobile-Polish bleibt out of scope.
- **Test-Trip-Edit beeinflusst Step-3-AC-6:** `e2e-cockpit-test` bekommt durch Step 5 ein `report_config`. Der bestehende Step-3-Hero-Test, der einen Trip OHNE `report_config` voraussetzte (AC-6: „Briefings deaktiviert"-Pfad), muss in einem separaten Test-Trip-Eintrag laufen. Die entsprechende Anpassung in `frontend/e2e/trip-detail-hero.spec.ts` ist OUT OF SCOPE für Step 5 und gehört in einen separaten Bugfix oder Issue #204.

## Changelog

- 2026-05-13: Initial spec — Issues #158 (Wetter-Metriken-Karte) + #159 (Briefings + Alerts + Vorschau), Epic #135 Step 5 (Trip-Detail Overview, rechte Spalte). 4 neue read-only Vorschau-Karten im `<aside data-testid="trip-overview-right-column">`: `BriefingPreviewCard`, `WeatherMetricsPreviewCard`, `AlertsPreviewCard`, `PreviewCard`. Pure-Function-Helper `rightColumn.ts` (`getPresetLabel`, `getDefaultMetricsForProfile`, `getActiveMetrics`, `getReportSchedule`, `prettyLabel`) kapselt generischen `Record<string, unknown>`-Zugriff bis #207 strukturiertes Typing liefert. Alle Karten verlinken via URL-Hash zum jeweiligen Tab (bestehende `hashchange`-Logik aus Step 1). Test-Trip-Seed in `global.setup.ts` um `report_config`, `weather_config.metrics`, `aggregation.activity_profile` erweitert. 18 Acceptance Criteria im AC-N-Format. TestID-Inventar (16 IDs inkl. bestehender `trip-overview-right-column` aus Step 4). Datei-Liste (~648 LoC, Override 700). Bekannte Limitierungen: Alert-Datenmodell (#205), Preset-Feld (#206), strukturiertes report_config-Typing (#207), Preview-Tab-Inhalt (#189), Hero-Test-Anpassung für Trip-ohne-report_config-Pfad.
