---
entity_id: issue_430_431_wizard_layout_step
type: module
created: 2026-05-28
updated: 2026-05-28
status: draft
version: "1.0"
tags: [frontend, wizard, svelte, stepper, layout-editor, issue-430, issue-431, epic-428]
---

# Issue #430 + #431 — Wizard 4→5 Steps + OutputLayoutEditor + Step 4 Layout

## Approval

- [ ] Approved

## Purpose

Erweitert den Trip-Wizard von 4 auf 5 Schritte, indem zwischen „Wetter" (Metriken aktivieren)
und „Reports" (Zeitplan + Kanäle) ein neuer Schritt „Layout" eingeschoben wird. Dieser neue
Step 4 erlaubt es dem User, pro Ausgangskanal (Email / Telegram / Signal / SMS) die
Reihenfolge der Wetter-Spalten und die Bucket-Zuordnung (primär / sekundär / aus) individuell
festzulegen.

Die beiden Issues werden in einem einzigen PR ausgeliefert, weil #430 allein (Stepper 5 Steps,
aber kein Step-4-Inhalt) eine sichtbare halbfertige UI auf Production erzeugen würde. #431
liefert gleichzeitig die `OutputLayoutEditor`-Komponente und `Step4Layout.svelte`, sodass der
neue Step beim Merge vollständig bedienbar ist. Als Nebeneffekt wird `WeatherMetricsTab.svelte`
zu einem dünnen Wrapper refactored, der seinen Editor-Body aus `OutputLayoutEditor` bezieht —
damit teilen Wizard und Trip-Detail-Tab dieselbe Layout-Logik.

## Source

- **Schicht:** Reines Frontend (SvelteKit). Kein Go-Backend, kein Python-Backend.
- **Dateien (geändert):**
  - `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` (geändert)
  - `frontend/src/lib/components/trip-wizard/Stepper.svelte` (geändert)
  - `frontend/src/lib/components/trip-wizard/stepperCompact.ts` (geändert)
  - `frontend/src/lib/components/trip-wizard/stepperState.ts` (geändert — Doc-Comment)
  - `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` (geändert)
  - `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` (refactored zum Wrapper)
- **Dateien (neu):**
  - `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` (NEU)
  - `frontend/src/lib/components/trip-wizard/steps/Step4Layout.svelte` (NEU)
- **Tests (neu/angepasst):**
  - `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` (angepasst)
  - `frontend/src/lib/components/trip-wizard/__tests__/stepper.test.ts` (angepasst)
  - `frontend/src/lib/components/trip-wizard/__tests__/stepperCompact.test.ts` (angepasst)
  - `frontend/e2e/trip-wizard-step4.spec.ts` (NEU)
  - `frontend/e2e/trip-wizard-shell.spec.ts` (angepasst: Stepper-Asserts)

## Dependencies

| Entity | Type | Zweck |
|--------|------|-------|
| `WizardState` — `wizardState.svelte.ts` | TypeScript-Klasse (geändert) | Neues Feld `channelLayouts`, `currentStep: 1\|2\|3\|4\|5`, `canAdvanceStep4/5`, `toTripPayload`-Erweiterung |
| `ChannelLayouts` — `frontend/src/lib/types.ts:166` | TypeScript-Interface (vorhanden, via Issue #429) | Typdefinition für `wizard.channelLayouts`; bereits in PR #429 ergänzt |
| `WeatherConfigMetric` — `frontend/src/lib/types.ts:127` | TypeScript-Interface (vorhanden) | Einzel-Metrik in Buckets + channel_layouts |
| `DisplayConfig` — `frontend/src/lib/types.ts:166` | TypeScript-Interface (vorhanden, via Issue #429) | `display_config.channel_layouts?` als Ziel-Feld in `toTripPayload()` |
| `BucketSection.svelte` — `frontend/src/lib/components/trip-detail/` | Svelte-Komponente (vorhanden) | Bucket-Tabelle (primär / sekundär) im OutputLayoutEditor |
| `BucketSectionOff.svelte` — `frontend/src/lib/components/trip-detail/` | Svelte-Komponente (vorhanden) | „Nicht im Briefing"-Sektion im OutputLayoutEditor |
| `ChannelPreviewBlock.svelte` — `frontend/src/lib/components/trip-detail/` | Svelte-Komponente (vorhanden) | Live-Vorschau rechts (Desktop) / oberhalb (Mobile) in Step4Layout |
| `ChannelLimitMarkers.svelte` — `frontend/src/lib/components/trip-detail/` | Svelte-Komponente (vorhanden) | Kanal-Limit-Markierungen im OutputLayoutEditor |
| `AboutOutputLayout.svelte` — `frontend/src/lib/components/trip-detail/` | Svelte-Komponente (vorhanden) | Info-Sektion über Ausgabe-Layout; bleibt in trip-detail/ |
| `metricsEditor.ts` — `frontend/src/lib/components/trip-detail/` | TypeScript-Modul (vorhanden) | `autoAssign`, `move`, `reorder`, `buildWeatherConfigMetrics`, `CATEGORY_LABELS`, `INDICATOR_MAP`, `CHANNEL_COL_BUDGET` |
| `stepperState.ts` — `frontend/src/lib/components/trip-wizard/` | TypeScript-Modul (vorhanden) | `stepperStateOf()` für Desktop-Stepper; generisch, unterstützt bereits beliebige Step-Zahlen |
| `Btn`, `Eyebrow`, `Pill`, `GCard` | Design-System-Atome (vorhanden) | UI-Bausteine in Stepper, Shell, Step4Layout |
| `GET /api/metrics` | Go-Backend-Endpoint (vorhanden) | Metrik-Katalog beim Mount in Step4Layout laden |
| `GET /api/templates` | Go-Backend-Endpoint (vorhanden) | Template-Liste beim Mount in Step4Layout laden |
| `GET /api/metric-presets` | Go-Backend-Endpoint (vorhanden) | User-Presets beim Mount in Step4Layout laden |

## Scope

**Nur Frontend.** Keine Änderungen am Go-Backend oder Python-Backend.

Nicht in Scope (explizit):
- Step 3 Wetter-Umbau (Horizon-Pills → Format-Dropdown, 5 Kategorien-Gruppen) — PR 4 (#432)
- Step 5 Reports: 4 Cards auf 3 reduzieren, Mehrtages-Trend-Toggle entfernen, AUTARK-Pill — PR 4 (#432)
- `Step4Reports.svelte` → `Step5Reports.svelte` Datei-Umbenennung — PR 4 (#432)
- 4 Kanal-Tabs im Trip-Detail-Output-Tab (`WeatherMetricsTab.svelte`) — eigenes Folge-Issue
- 4-Optionen-Format-Dropdown (Roh/Skala/Vereinfacht/Symbol) — Issue #435
- Echtes Drag-and-Drop (Touch + Maus) — Issue #433
- Per-Report-Overrides (Abend ≠ Morgen pro Kanal) — Issue #434
- „Inhalt im Output-Editor anpassen →"-Link Routing — Issue #436
- Mehrtages-Trend-Backend-Verkabelung — Issue #437

## Implementation Details

### 1. `wizardState.svelte.ts` — Erweiterung (#430)

**`currentStep`-Typ auf `1|2|3|4|5` erweitern:**

```typescript
currentStep = $state<1 | 2 | 3 | 4 | 5>(1);
```

**Neues State-Feld `channelLayouts`:**

```typescript
// Issue #431: Pro-Kanal-Layouts. null = globale geteilte Liste (Default).
channelLayouts = $state<ChannelLayouts | null>(null);
```

Import von `ChannelLayouts` aus `$lib/types`.

**`canAdvanceStep4` (Layout-Step) — neuer Getter, kein Gate:**

```typescript
// Bisheriger canAdvanceStep4 (Reports) wird zu canAdvanceStep5.
get canAdvanceStep4(): boolean {
  return true; // kein Gate
}

get canAdvanceStep5(): boolean {
  return true; // kein Gate (bisheriges canAdvanceStep4)
}
```

**`canAdvanceCurrent`-Switch um Fall 5 erweitern:**

```typescript
get canAdvanceCurrent(): boolean {
  switch (this.currentStep) {
    case 1: return this.canAdvanceStep1;
    case 2: return this.canAdvanceStep2;
    case 3: return this.canAdvanceStep3;
    case 4: return this.canAdvanceStep4;
    case 5: return this.canAdvanceStep5;
  }
}
```

**`nextStep/prevStep` — Grenze auf 5:**

```typescript
nextStep(): void {
  if (this.currentStep < 5) {
    this.currentStep = (this.currentStep + 1) as 1 | 2 | 3 | 4 | 5;
  }
}

prevStep(): void {
  if (this.currentStep > 1) {
    this.currentStep = (this.currentStep - 1) as 1 | 2 | 3 | 4 | 5;
  }
}
```

**`toTripPayload()` — `channel_layouts` schreiben wenn nicht null:**

```typescript
// Nach dem bestehenden display_config.metrics-Block:
if (this.channelLayouts !== null) {
  trip.display_config = {
    ...(trip.display_config ?? {}),
    channel_layouts: this.channelLayouts
  };
}
```

---

### 2. `Stepper.svelte` — 5-Step-Erweiterung + Mobile-Progressbar (#430)

**Props-Typen anpassen:**

```typescript
interface Props {
  current: 1 | 2 | 3 | 4 | 5;
  labels: string[];
  subLabels?: string[];
}
```

Der Desktop-Full-Stepper (`{#each labels as label, i}`) ist bereits generisch und unterstützt
5 Steps ohne Template-Änderung — `stepperStateOf` ist ebenso generisch. Verbinder-Logik
(`i < labels.length - 1`) erzeugt automatisch 4 Verbinder für 5 Steps.

**Mobile-Compact-Block umbauen: 5-Segment-Progressbar:**

```svelte
<!-- Mobile Compact Stepper (Viewport <= 899px) -->
<div data-testid="trip-wizard-stepper-compact" class="desktop:hidden">
  <!-- Progressbar: 5 Segmente -->
  <div class="flex gap-1 mb-1" data-testid="stepper-progress-bar">
    {#each progressBarSegments(current, labels.length) as seg, i (i)}
      <div
        data-testid={`progress-segment-${i + 1}`}
        data-segment-state={seg}
        class={`h-1 flex-1 rounded-full transition-colors
          ${seg === 'done'    ? 'bg-[var(--g-success)]'     : ''}
          ${seg === 'active'  ? 'bg-[var(--g-accent)]'      : ''}
          ${seg === 'pending' ? 'bg-[var(--g-ink-faint)]/30' : ''}`}
      ></div>
    {/each}
  </div>
  <!-- Eyebrow-Text -->
  <span class="text-xs font-mono text-[var(--g-ink-muted)]">
    SCHRITT {current} VON {labels.length} · {labels[current - 1]}
  </span>
</div>
```

Import in Stepper.svelte:

```typescript
import { progressBarSegments } from './stepperCompact.ts';
```

---

### 3. `stepperCompact.ts` — neuer Helper `progressBarSegments` (#430)

```typescript
export type SegmentState = 'done' | 'active' | 'pending';

/**
 * Liefert den Zustand jedes Progressbar-Segments.
 *
 * @param current 1-basierter aktueller Step (1..total)
 * @param total   Gesamtanzahl Steps
 * @returns Array der Länge `total` mit 'done' | 'active' | 'pending'
 */
export function progressBarSegments(current: number, total: number): SegmentState[] {
  return Array.from({ length: total }, (_, i) => {
    const step = i + 1;
    if (step < current)  return 'done';
    if (step === current) return 'active';
    return 'pending';
  });
}
```

`compactStepperText` bleibt unverändert als Fallback.

---

### 4. `stepperState.ts` — Doc-Comment-Update (#430)

Einzige Änderung: Doc-Comment auf `current: 1..5` aktualisieren. Logik ist bereits
generisch und erfordert keine Code-Änderung.

---

### 5. `TripWizardShell.svelte` — 5-Step-Konfiguration (#430 + #431)

**Imports ergänzen:**

```typescript
import Step4Layout from './steps/Step4Layout.svelte';
// Step4Reports bleibt als Datei-Name — Umbenennung in PR 4 (#432)
```

**Step-Konfiguration:**

```typescript
const stepLabels = ['Route', 'Etappen', 'Wetter', 'Layout', 'Reports'];
const stepSubLabels = [
  'Name & GPX hochladen',
  'Etappen prüfen',
  'Metriken konfigurieren',
  'Reihenfolge pro Kanal',
  'Briefings einrichten'
];

const stepTitles: Record<number, string> = {
  1: 'Route — wie kennt das System deinen Weg?',
  2: 'Etappen — stimmt die Tagesaufteilung?',
  3: 'Wetter — welche Daten gehen ins Briefing?',
  4: 'Layout — wie sieht das Briefing aus?',
  5: 'Reports — wann und wohin?'
};

const stepHints: Record<number, string | null> = {
  1: 'GPX-Upload empfohlen — manuelle Eingabe geht auch.',
  2: 'Algorithmische Wegpunkte sind orange gestrichelt — bestätigen oder verwerfen.',
  3: null,
  4: null,
  5: 'Unterwegs läuft alles autark. Kein Eingreifen nötig.'
};
```

**Eyebrow:** `SCHRITT {state.currentStep} VON 5 · NEUER TRIP`

**Step-Switch um Step 4 erweitern:**

```svelte
{:else if state.currentStep === 4}
  <Step4Layout />
{:else if state.currentStep === 5}
  <Step4Reports />
```

**Save-Button-Logik:**

```svelte
{#if state.currentStep < 5}
  <Btn ... onclick={handleNext} disabled={!state.canAdvanceCurrent}>Weiter</Btn>
{:else}
  <Btn ... onclick={handleSave} disabled={state.saveStatus === 'saving'}>{saveLabel}</Btn>
{/if}
```

---

### 6. `OutputLayoutEditor.svelte` (NEU, #431)

**Pfad:** `frontend/src/lib/components/shared/OutputLayoutEditor.svelte`

**Props (bindable):**

```typescript
interface Props {
  catalog: MetricCatalog;
  buckets: Buckets;        // bindable
  friendlyMap: Record<string, boolean>;  // bindable
  selectedTemplate?: string; // bindable
  channel: 'email' | 'telegram' | 'signal' | 'sms';
  templates?: Template[];
  userPresets?: MetricPreset[];
  onReorder?: (from: number, to: number, bucket: 'primary' | 'secondary') => void;
  onMove?: (metricId: string, targetBucket: 'primary' | 'secondary' | 'off') => void;
  onMode?: (metricId: string, friendly: boolean) => void;
  onSelectPreset?: (id: string) => void;
}
```

**Kernlogik:**

```svelte
{#if channel === 'sms'}
  <!-- SMS-Mode: flache priorisierte Liste, kein Bucket-Table -->
  <div data-testid="output-layout-editor-sms">
    <!-- Budget-Anzeige -->
    <div class="budget-bar" data-testid="sms-budget-display">
      <!-- 140-Zeichen-Budget, berechnet aus buckets.primary.length * ~12 Zeichen -->
    </div>
    <!-- Reorder-Liste primär (nur ▲▼-Buttons, kein DnD) -->
    {#each buckets.primary as metricId, i (metricId)}
      <div class="sms-row" data-testid={`sms-row-${metricId}`}>
        <span>{metricById[metricId]?.label ?? metricId}</span>
        <Btn variant="ghost" size="icon-sm" onclick={() => onReorder?.(i, i - 1, 'primary')}
          disabled={i === 0}>▲</Btn>
        <Btn variant="ghost" size="icon-sm" onclick={() => onReorder?.(i, i + 1, 'primary')}
          disabled={i === buckets.primary.length - 1}>▼</Btn>
      </div>
    {/each}
    <!-- Off-Sektion -->
    <BucketSectionOff {catalog} off={buckets.off} {metricById} onMove={onMove} />
  </div>
{:else}
  <!-- Standard-Mode: Bucket-Editor mit Spalten + Detail-Werte + ChannelLimitMarkers -->
  <div data-testid="output-layout-editor-standard">
    <BucketSection bucket="primary" ids={buckets.primary} {catalog} {metricById}
      {friendlyMap} {onReorder} {onMove} {onMode} />
    <BucketSection bucket="secondary" ids={buckets.secondary} {catalog} {metricById}
      {friendlyMap} {onReorder} {onMove} {onMode} />
    <ChannelLimitMarkers {channel} primary={buckets.primary} secondary={buckets.secondary} />
    <BucketSectionOff {catalog} off={buckets.off} {metricById} {onMove} />
    <AboutOutputLayout />
  </div>
{/if}
```

**Keine API-Calls, keine `trip`-Prop.** Alles über `bind:` oder Handler-Props.

---

### 7. `WeatherMetricsTab.svelte` — Refactor zum dünnen Wrapper (#431)

Der Tab behält alle API-Load-Calls (`GET /api/metrics`, `/api/templates`, `/api/metric-presets`),
den `initFromTrip()`-Block und den Save-Button mit `PUT /api/trips/{id}/weather-config`.

Der bisher inline gerenderte Bucket-Editor-Body wird durch eine `<OutputLayoutEditor>`-Instanz
ersetzt:

```svelte
<OutputLayoutEditor
  channel="email"
  {catalog}
  bind:buckets
  bind:friendlyMap
  bind:selectedTemplate
  {templates}
  {userPresets}
  onReorder={(from, to, bucket) => { buckets = reorder(buckets, from, to, bucket); }}
  onMove={(id, target) => { buckets = move(buckets, id, target); }}
  onMode={(id, friendly) => { friendlyMap = { ...friendlyMap, [id]: friendly }; }}
  onSelectPreset={applyPreset}
/>
```

`BucketSection`, `BucketSectionOff`, `ChannelLimitMarkers`, `AboutOutputLayout` werden aus dem
direkten Import in `WeatherMetricsTab.svelte` entfernt (werden jetzt vom `OutputLayoutEditor`
geladen). `ChannelPreviewBlock`, `WeatherMetricsMobileView`, `PresetRow`, `SavePresetDialog`
bleiben direkte Imports in `WeatherMetricsTab.svelte`.

---

### 8. `Step4Layout.svelte` (NEU, #431)

**Pfad:** `frontend/src/lib/components/trip-wizard/steps/Step4Layout.svelte`

**Lokaler State:**

```typescript
let catalog: MetricCatalog = $state({});
let templates: Template[] = $state([]);
let userPresets: MetricPreset[] = $state([]);
let loading = $state(true);
let activeChannel = $state<'email' | 'telegram' | 'signal' | 'sms'>('email');

// Pro-Kanal Bucket/friendlyMap-State (4 unabhängige Instanzen)
const channelState = $state<Record<string, { buckets: Buckets; friendlyMap: Record<string,boolean>; selectedTemplate: string }>>({
  email:    { buckets: { primary: [], secondary: [], off: [] }, friendlyMap: {}, selectedTemplate: '' },
  telegram: { buckets: { primary: [], secondary: [], off: [] }, friendlyMap: {}, selectedTemplate: '' },
  signal:   { buckets: { primary: [], secondary: [], off: [] }, friendlyMap: {}, selectedTemplate: '' },
  sms:      { buckets: { primary: [], secondary: [], off: [] }, friendlyMap: {}, selectedTemplate: '' },
});
```

**Mount-Hook:**

```typescript
onMount(async () => {
  const [catalogData, templateData, presetData] = await Promise.all([
    api.get<MetricCatalog>('/api/metrics'),
    api.get<Template[]>('/api/templates').catch(() => [] as Template[]),
    api.get<MetricPreset[]>('/api/metric-presets').catch(() => [] as MetricPreset[]),
  ]);
  catalog = catalogData;
  templates = templateData;
  userPresets = presetData;
  // Initialisierung aus wizard.channelLayouts (falls vorhanden) oder
  // wizard.weatherMetrics (Fallback = gleiche Liste für alle Kanäle).
  initChannelState();
  loading = false;
});
```

**Initialisierung `initChannelState()`:**

```typescript
function initChannelState() {
  const channels = ['email', 'telegram', 'signal', 'sms'] as const;
  for (const ch of channels) {
    const saved = wizard.channelLayouts?.[ch];
    if (saved && saved.length > 0) {
      // Aus gespeichertem channelLayouts laden (bucket/order wie WeatherMetricsTab)
      channelState[ch].buckets = bucketsFromMetrics(saved);
      channelState[ch].friendlyMap = friendlyMapFromMetrics(saved);
    } else {
      // Fallback: wizard.weatherMetrics (globale Liste aus Step 3)
      channelState[ch].buckets = autoAssign(
        wizard.weatherMetrics.filter(m => m.enabled).map(m => m.metric_id),
        catalog
      );
    }
  }
}
```

**Template-Struktur:**

```svelte
<div class="step4-layout" data-testid="step4-layout">
  <!-- Channel-Tabs -->
  <div class="channel-tabs" data-testid="channel-tabs">
    {#each ['email','telegram','signal','sms'] as ch}
      <button
        data-testid={`channel-tab-${ch}`}
        aria-pressed={activeChannel === ch}
        onclick={() => activeChannel = ch}
      >
        {channelLabel(ch)}
        <span class="constraint-info">{channelConstraint(ch)}</span>
      </button>
    {/each}
  </div>

  <!-- Desktop: Editor links + Preview rechts. Mobile: Preview oben + Editor unten -->
  <div class="layout-body desktop:flex desktop:gap-6">
    <div class="preview-region" data-testid="layout-preview">
      <ChannelPreviewBlock channel={activeChannel} {buckets} {friendlyMap} />
    </div>
    <div class="editor-region" data-testid="layout-editor">
      <OutputLayoutEditor
        channel={activeChannel}
        {catalog}
        {templates}
        {userPresets}
        bind:buckets={channelState[activeChannel].buckets}
        bind:friendlyMap={channelState[activeChannel].friendlyMap}
        bind:selectedTemplate={channelState[activeChannel].selectedTemplate}
        onReorder={(from, to, bucket) => applyReorder(activeChannel, from, to, bucket)}
        onMove={(id, target) => applyMove(activeChannel, id, target)}
        onMode={(id, friendly) => applyMode(activeChannel, id, friendly)}
        onSelectPreset={(id) => applyPreset(activeChannel, id)}
      />
    </div>
  </div>
</div>
```

**`$effect` — `channelState` → `wizard.channelLayouts` synchronisieren:**

```typescript
$effect(() => {
  // Wenn der User irgendeinen Kanal-State ändert, wizard.channelLayouts aktualisieren.
  const layouts: ChannelLayouts = {};
  for (const ch of ['email', 'telegram', 'signal', 'sms'] as const) {
    layouts[ch] = buildWeatherConfigMetrics(channelState[ch].buckets, channelState[ch].friendlyMap);
  }
  wizard.channelLayouts = layouts;
});
```

**Kanal-Constraint-Texte (Const-Map):**

```typescript
const CHANNEL_CONSTRAINTS: Record<string, string> = {
  email:    'Unbegrenzte Spalten',
  telegram: 'Max. 8 Spalten',
  signal:   'Max. 8 Spalten',
  sms:      '140 Zeichen',
};
```

---

### LoC-Budget (Override auf 1000 gesetzt)

| Datei | Δ LoC (grob) |
|------|------|
| `wizardState.svelte.ts` | +30 |
| `Stepper.svelte` | +50 |
| `stepperState.ts` | +2 |
| `stepperCompact.ts` | +20 |
| `TripWizardShell.svelte` | +25 |
| `OutputLayoutEditor.svelte` (NEU) | +300 |
| `WeatherMetricsTab.svelte` | −150 / +50 |
| `Step4Layout.svelte` (NEU) | +250 |
| Unit-Tests | +200 |
| E2E-Tests | +150 |
| **Summe** | **~900 LoC** |

**LoC-Override:** `workflow.py set-field loc_limit_override 1000` vor Beginn der Implementierung setzen.

## Expected Behavior

- **Input:** Wizard-State nach abgeschlossenem Step 3 (Wetter-Metriken konfiguriert); optional vorhandene `wizard.channelLayouts` aus einem früheren Edit
- **Output:** `wizard.channelLayouts` enthält nach Step 4 pro Kanal eine `WeatherConfigMetric[]`-Liste. `toTripPayload()` schreibt `display_config.channel_layouts` wenn `channelLayouts !== null`. Der Wizard zeigt 5 Steps im Stepper; „Trip speichern" erscheint erst auf Step 5.
- **Side effects:** API-Calls beim Mount von `Step4Layout` (`GET /api/metrics`, `/api/templates`, `/api/metric-presets`); kein PUT/POST in Step 4. `WeatherMetricsTab` im Trip-Detail verhält sich visuell und funktional unverändert.

## Acceptance Criteria

**AC-1:** Given der Wizard wird auf `/trips/new` geöffnet /
When Step 1 gerendert wird /
Then zeigt der Desktop-Stepper genau 5 Circles mit Labels „Route", „Etappen", „Wetter", „Layout", „Reports" und 4 Verbinder-Linien dazwischen — kein „Briefings", kein 4-Step-Layout mehr sichtbar.

**AC-2:** Given der Wizard zeigt Step 1 auf einem mobilen Viewport (≤899px) /
When der Stepper-Compact-Block gerendert wird /
Then sind exakt 5 Segment-Balken sichtbar (`data-testid="progress-segment-N"` für N=1..5), Segment 1 ist `active`, Segmente 2–5 sind `pending`.

**AC-3:** Given der User navigiert von Step 2 zu Step 3 /
When der Mobile-Stepper gerendert wird /
Then sind Segmente 1–2 im Zustand `done` (Erfolgsfarbe), Segment 3 im Zustand `active` (Accent-Farbe), Segmente 4–5 im Zustand `pending` (gedämpfte Farbe) — gemäß `progressBarSegments(3, 5)`.

**AC-4:** Given der Wizard zeigt irgendeinen Step /
When die Eyebrow gerendert wird /
Then lautet der Text „SCHRITT N VON 5 · NEUER TRIP" (N = aktueller Step, 5 = Gesamtzahl, nicht 4).

**AC-5:** Given `WizardState` wird auf Step 4 gesetzt (`state.currentStep = 4`) /
When `state.nextStep()` aufgerufen wird /
Then ist `state.currentStep === 5` und ein weiterer `nextStep()`-Aufruf ändert den Wert nicht (Grenze bei 5, nicht bei 4).

**AC-6:** Given `WizardState` ist auf Step 1 (`state.currentStep = 1`) /
When `state.prevStep()` aufgerufen wird /
Then bleibt `state.currentStep === 1` — kein Unterschreiten der unteren Grenze.

**AC-7:** Given der Wizard zeigt Step 4 (Layout) /
When die vier Channel-Tabs gerendert werden /
Then sind die Tabs mit den Labels für Email, Telegram, Signal und SMS sichtbar, jeweils mit einer Constraint-Info (z.B. „Max. 8 Spalten" für Telegram), und der Email-Tab ist initial aktiv (`aria-pressed="true"`).

**AC-8:** Given `OutputLayoutEditor.svelte` wird instanziiert /
When alle Props übergeben werden und die Komponente rendert /
Then enthält die Komponente weder einen `api.get()`-Aufruf noch eine `trip`-Prop — der Editor ist vollständig trip-agnostisch und kommuniziert nur über `bind:`-Props und Handler.

**AC-9:** Given Step 4 (Layout) zeigt den SMS-Tab (`activeChannel === 'sms'`) /
When der OutputLayoutEditor für SMS gerendert wird /
Then ist keine `BucketSection`-Tabelle sichtbar; stattdessen zeigt der Editor eine flache priorisierte Liste mit ▲▼-Buttons und eine 140-Zeichen-Budget-Anzeige (`data-testid="sms-budget-display"`).

**AC-10:** Given der User wechselt im Step 4 vom Email-Tab zum Signal-Tab und ändert dort die Bucket-Reihenfolge /
When der User zurück zum Email-Tab wechselt /
Then sind die Email-Buckets unverändert — jeder Kanal hat seinen eigenen isolierten Bucket-State, Änderungen in einem Kanal beeinflussen andere Kanäle nicht.

**AC-11:** Given der User hat in Step 4 die Bucket-Reihenfolge für Telegram angepasst /
When `toTripPayload()` in `WizardState` aufgerufen wird /
Then enthält das zurückgegebene Trip-Objekt `display_config.channel_layouts.telegram` als Array von `WeatherConfigMetric`-Objekten mit den vom User gesetzten `bucket`- und `order`-Feldern — die Backend-Spec (Issue #429) liest dieses Feld direkt.

**AC-12:** Given `WizardState.channelLayouts` ist `null` (kein Step 4 besucht oder explizit zurückgesetzt) /
When `toTripPayload()` aufgerufen wird /
Then fehlt `display_config.channel_layouts` im zurückgegebenen Objekt komplett (omitempty-Symmetrie, kein leeres Objekt `{}`).

**AC-13:** Given der Wizard befindet sich auf Step 5 (Reports) /
When der Footer gerendert wird /
Then zeigt der primäre Aktions-Button den Text „Trip speichern" (nicht „Weiter") und `data-testid="trip-wizard-save"` ist sichtbar, `data-testid="trip-wizard-next"` ist nicht sichtbar.

**AC-14:** Given der Wizard befindet sich auf Step 4 (Layout) /
When der Footer gerendert wird /
Then zeigt der primäre Aktions-Button den Text „Weiter" (`data-testid="trip-wizard-next"`), da Step 4 kein finales Save auslöst.

**AC-15:** Given `WeatherMetricsTab.svelte` wird im Trip-Detail-View für einen bestehenden Trip geöffnet /
When der Tab vollständig geladen hat /
Then rendert der Tab visuell identisch zum Stand vor diesem PR (Bucket-Tabellen, Preview, Preset-Zeilen, Save-Button) — alle existierenden Trip-Detail-Tests für `WeatherMetricsTab` bleiben grün; `channel="email"` ist fix instanziiert.

## Out of Scope

- Step 3 Wetter-Umbau (Horizon-Pills → Format-Dropdown, 5 Kategorien-Gruppen) — PR 4 (#432)
- Step 5 Reports von 4 auf 3 Cards reduzieren, Mehrtages-Trend-Toggle entfernen, AUTARK-Pill entfernen — PR 4 (#432)
- `Step4Reports.svelte` → `Step5Reports.svelte` Datei-Umbenennung — PR 4 (#432)
- 4 Kanal-Tabs im Trip-Detail-Output-Tab (`WeatherMetricsTab.svelte`) — eigenes Folge-Issue
- 4-Optionen-Format-Dropdown (Roh/Skala/Vereinfacht/Symbol) — Issue #435
- Echtes Drag-and-Drop (Touch + Maus) — Issue #433
- Per-Report-Overrides (Abend ≠ Morgen pro Kanal) — Issue #434
- „Inhalt im Output-Editor anpassen →"-Link Routing — Issue #436
- Mehrtages-Trend-Backend-Verkabelung — Issue #437
- Master-Spec-Update `epic_136_trip_wizard.md` — kommt in PR 4 (#432), wenn alle Step-Inhalte stehen

## Known Limitations

- `OutputLayoutEditor` wird in `Step4Layout` mit 4 separaten Instanzen gleichzeitig gemountet (eine pro Kanal, alle im selben Step). Das erzeugt 4-fache Mount-Last beim Einstieg in Step 4. Performance-Profiling steht aus; bei Problemen kann auf lazy Mount (nur aktiver Kanal) umgestellt werden.
- `WeatherMetricsTab.svelte` zeigt weiterhin nur Email-Layout (fix `channel="email"`). User müssen den Wizard nutzen, um SMS/Telegram/Signal-Layouts zu konfigurieren. Kanal-Tabs im Trip-Detail-Tab sind Folge-Arbeit.
- Mobile-Touch-Drag wird in dieser PR nicht implementiert; nur ▲▼-Buttons mit min. 36 px Höhe. Echtes Drag-and-Drop für Maus und Touch ist Issue #433.
- Wenn `/api/metrics` beim Mount von `Step4Layout` fehlschlägt, zeigt der Step einen Lade-Spinner ohne Fallback-Metriken. Fehler-Handling (Retry, Toast) ist nicht Teil dieser Spec.
- `progressBarSegments(current, total)` gibt bei `current > total` einen vollständig `done`-Array zurück (kein Guard); das kann bei falscher Nutzung außerhalb des Wizards irreführend sein. Innerhalb des Wizards ist `current` durch den `1..5`-Typ abgesichert.

## Changelog

- 2026-05-28: Initial spec erstellt für Issue #430 + #431 (PR 2+3/4 von Epic #428). Kombinierter PR wegen halbfertiger UI-Gefahr bei #430 allein (PO-Entscheidung 2026-05-28).
