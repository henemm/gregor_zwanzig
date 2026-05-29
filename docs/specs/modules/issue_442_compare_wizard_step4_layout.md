---
entity_id: issue_442_compare_wizard_step4_layout
type: module
created: 2026-05-29
updated: 2026-05-29
status: draft
version: "1.0"
tags: [frontend, wizard, svelte, stepper, layout-editor, compare, issue-442, epic-440]
---

# Issue #442 — Compare-Wizard Step 4 Layout

## Approval

- [ ] Approved

## Purpose

Ergänzt den Compare-Wizard um einen vierten Schritt „Layout", in dem der Nutzer pro Ausgangskanal
(Email / Telegram / Signal / SMS) die Reihenfolge der Wetter-Spalten und die Bucket-Zuordnung
(primär / sekundär / aus) individuell festlegt. Die Implementierung adaptiert das in Issue #431
etablierte Trip-Wizard-Step4Layout-Muster direkt auf den Compare-Wizard — derselbe
`OutputLayoutEditor` und dieselben `metricsEditor.ts`-Helfer werden wiederverwendet, sodass
keine Logik doppelt gepflegt wird.

## Source

- **Schicht:** Reines Frontend (SvelteKit). Kein Go-Backend, kein Python-Backend.
- **Dateien (neu):**
  - `frontend/src/lib/components/compare/steps/Step4Layout.svelte`
  - `frontend/src/lib/components/compare/__tests__/issue_442_compare_wizard_step4.test.ts`
- **Dateien (geändert):**
  - `frontend/src/lib/components/compare/compareWizardState.svelte.ts`
  - `frontend/src/lib/components/compare/CompareWizard.svelte`
  - `frontend/src/routes/compare/[id]/edit/+page.svelte`

## Dependencies

| Entity | Type | Zweck |
|--------|------|-------|
| `CompareWizardState` — `compareWizardState.svelte.ts` | TypeScript-Klasse (geändert) | Neues Feld `channelLayouts`, Persistenz in `save()` und `toggleEnabled()` |
| `ChannelLayouts` — `frontend/src/lib/types.ts` | TypeScript-Interface (vorhanden) | Typdefinition für `state.channelLayouts`; bereits durch Issue #429 vorhanden |
| `WeatherConfigMetric` — `frontend/src/lib/types.ts` | TypeScript-Interface (vorhanden) | Einzel-Metrik in Buckets + channel_layouts |
| `OutputLayoutEditor.svelte` — `frontend/src/lib/components/shared/` | Svelte-Komponente (vorhanden, via #431) | Bucket-Editor mit Channel-Tabs, SMS-Modus, Preview — keinerlei Änderungen an dieser Datei |
| `ChannelPreviewBlock.svelte` — `frontend/src/lib/components/trip-detail/` | Svelte-Komponente (vorhanden) | Live-Vorschau rechts (Desktop) / oben (Mobile) in Step4Layout |
| `metricsEditor.ts` — `frontend/src/lib/components/trip-detail/` | TypeScript-Modul (vorhanden) | `autoAssign`, `buildWeatherConfigMetrics`, `move`, `reorder`, `CHANNEL_COL_BUDGET` |
| `GET /api/metrics` | Go-Backend-Endpoint (vorhanden) | Metrik-Katalog beim Mount in Step4Layout laden |
| `GET /api/templates` | Go-Backend-Endpoint (vorhanden) | Template-Liste beim Mount in Step4Layout laden |
| `GET /api/metric-presets` | Go-Backend-Endpoint (vorhanden) | User-Presets beim Mount in Step4Layout laden |
| `CompareWizard.svelte` — `frontend/src/lib/components/compare/` | Svelte-Komponente (geändert) | Routing auf `Step4Layout` wenn `currentStep === 4` |
| `+page.svelte` — `frontend/src/routes/compare/[id]/edit/` | SvelteKit-Page (geändert) | Edit-Modus: Prefill von `channelLayouts` aus vorhandener `display_config` |

## Scope

**Nur Frontend.** Keine Änderungen am Go-Backend oder Python-Backend.

Nicht in Scope (explizit):
- Kanal-Tabs im Compare-Detail-View (`CompareWeatherMetricsTab` o. ä.) — eigenes Folge-Issue
- Echtes Drag-and-Drop für Buckets — Issue #433
- Per-Report-Overrides (Abend ≠ Morgen pro Kanal) — Issue #434
- Format-Modus-Dropdown (Roh / Skala / Vereinfacht / Symbol) im Compare-Kontext — Issue #444

## Implementation Details

### 1. `compareWizardState.svelte.ts` — Erweiterung

**Neues State-Feld:**

```typescript
// Issue #442: Pro-Kanal-Layouts. null = kein Step 4 besucht / noch nicht konfiguriert.
channelLayouts = $state<ChannelLayouts | null>(null);
```

**`save()` — additives Schreiben von `channel_layouts`:**

```typescript
// Nach dem bestehenden display_config-Block:
...(this.channelLayouts !== null ? { channel_layouts: this.channelLayouts } : {})
```

**`toggleEnabled()` — analog zu `save()` erweitern:** Dasselbe additive Pattern anwenden,
damit der Kanal-Toggle das `channel_layouts`-Feld nicht verliert.

---

### 2. `compare/steps/Step4Layout.svelte` (NEU)

Direktes Adaptat von `trip-wizard/steps/Step4Layout.svelte` mit drei Unterschieden:

| Aspekt | Trip-Wizard | Compare-Wizard |
|--------|-------------|----------------|
| State-Klasse | `WizardState` | `CompareWizardState` |
| Context-Key | `'trip-wizard-state'` | `'compare-wizard-state'` |
| Fallback bei neuen Subscriptions | `wizard.weatherMetrics` (aus Step 3) | `autoAssign([], catalog)` — kein `weatherMetrics`-Fallback-Zweig |

**Lokaler State:**

```typescript
let catalog: MetricCatalog = $state({});
let templates: Template[] = $state([]);
let userPresets: MetricPreset[] = $state([]);
let loading = $state(true);
let activeChannel = $state<'email' | 'telegram' | 'signal' | 'sms'>('email');

const channelState = $state<Record<string, {
  buckets: Buckets;
  friendlyMap: Record<string, boolean>;
  selectedTemplate: string;
}>>({
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
  initChannelState();
  loading = false;
});
```

**`initChannelState()` — Prefill oder autoAssign:**

```typescript
function initChannelState() {
  const channels = ['email', 'telegram', 'signal', 'sms'] as const;
  for (const ch of channels) {
    const saved = wizard.channelLayouts?.[ch];
    if (saved && saved.length > 0) {
      channelState[ch].buckets = bucketsFromMetrics(saved);
      channelState[ch].friendlyMap = friendlyMapFromMetrics(saved);
    } else {
      // Kein weatherMetrics-Fallback im Compare-Kontext — neue Subscription startet leer.
      channelState[ch].buckets = autoAssign([], catalog);
    }
  }
}
```

**Kritischer `$effect`-Timing-Guard (PFLICHT):**

```typescript
$effect(() => {
  // Guard MUSS vorhanden sein — fehlt er, werden bei Mount leere Layouts in den State
  // geschrieben und neue Subscriptions starten mit leerem Editor.
  if (loading || Object.keys(catalog).length === 0) return;

  const layouts: ChannelLayouts = {};
  for (const ch of ['email', 'telegram', 'signal', 'sms'] as const) {
    layouts[ch] = buildWeatherConfigMetrics(
      channelState[ch].buckets,
      channelState[ch].friendlyMap
    );
  }
  wizard.channelLayouts = layouts;
});
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
      <ChannelPreviewBlock
        channel={activeChannel}
        buckets={channelState[activeChannel].buckets}
        friendlyMap={channelState[activeChannel].friendlyMap}
      />
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

**Kanal-Constraint-Texte:**

```typescript
const CHANNEL_CONSTRAINTS: Record<string, string> = {
  email:    'Unbegrenzte Spalten',
  telegram: 'Max. 7 Spalten',
  signal:   'Max. 5 Spalten',
  sms:      '140 Zeichen',
};
```

(Werte aus `CHANNEL_COL_BUDGET` in `metricsEditor.ts`: email=Infinity, telegram=7, signal=5, sms=0.)

---

### 3. `+page.svelte` (Edit-Modus) — Prefill

```typescript
// Nach dem bestehenden Prefill-Block für andere Felder:
const saved = state.existingDisplayConfig?.channel_layouts as ChannelLayouts | undefined;
if (saved) state.channelLayouts = saved;
```

---

### 4. `CompareWizard.svelte` — Routing

```svelte
{:else if state.currentStep === 4}
  <Step4Layout />
```

Import ergänzen:

```typescript
import Step4Layout from './steps/Step4Layout.svelte';
```

---

### 5. LoC-Budget

| Datei | Δ LoC (grob) |
|-------|-------------|
| `compareWizardState.svelte.ts` | +12 |
| `compare/steps/Step4Layout.svelte` (NEU) | ~400 |
| `CompareWizard.svelte` | +5 |
| `+page.svelte` (Edit) | +4 |
| Tests (NEU) | ~80 |
| **Summe** | **~501 LoC** |

**LoC-Override vor Beginn:** `workflow.py set-field loc_limit_override 500`

## Expected Behavior

- **Input:** Compare-Wizard-State mit mindestens einem konfigurierten Standort (Schritt 1–3
  abgeschlossen); optional vorhandene `existingDisplayConfig.channel_layouts` aus einer
  früheren Speicherung (Edit-Modus).
- **Output:** `state.channelLayouts` enthält nach Step 4 pro Kanal eine
  `WeatherConfigMetric[]`-Liste. `save()` schreibt `display_config.channel_layouts` wenn
  `channelLayouts !== null`. Der „Weiter"-Button in Step 4 ist immer aktiv (kein Gate).
- **Side effects:** API-Calls beim Mount von `Step4Layout`
  (`GET /api/metrics`, `/api/templates`, `/api/metric-presets`); kein PUT/POST in Step 4.
  Bestehende Schritte 1–3 und der `save()`-Pfad bleiben unverändert.

## Acceptance Criteria

**AC-1:** Given der Compare-Wizard zeigt Step 4 / When der Nutzer im Email-Tab eine Metrik von
„primär" nach „sekundär" verschiebt und dann zum Telegram-Tab wechselt /
Then sind die Telegram-Buckets unverändert — Änderungen in einem Kanal beeinflussen andere
Kanäle nicht.
- Test: `issue_442_compare_wizard_step4.test.ts` — „AC-1: Step4Layout enthält alle 4 Channel-Identifier"

**AC-2:** Given Step 4 ist aktiv und `loading === false` und `catalog` enthält mindestens einen
Eintrag / When der Nutzer eine Bucket-Änderung vornimmt /
Then wird `wizard.channelLayouts` durch den `$effect` mit den aktuellen Werten aller vier
Kanäle aktualisiert (email, telegram, signal, sms je als `WeatherConfigMetric[]`).
- Test: `issue_442_compare_wizard_step4.test.ts` — „AC-2: Step4Layout referenziert wizard.channelLayouts (State-Sync)"

**AC-3:** Given ein bestehender Compare-Eintrag mit `display_config.channel_layouts` wird im
Edit-Modus geöffnet / When `+page.svelte` den `CompareWizardState` initialisiert /
Then sind die gespeicherten `channel_layouts` per `state.channelLayouts = saved` vorbefüllt
und im Step-4-Editor sofort sichtbar.
- Test: `issue_442_compare_wizard_step4.test.ts` — „AC-3: Edit +page.svelte liest channel_layouts / setzt state.channelLayouts"

**AC-4:** Given eine neue Compare-Subscription (keine vorherigen `channelLayouts`) /
When `initChannelState()` in Step4Layout aufgerufen wird /
Then wird für jeden Kanal `autoAssign([], catalog)` verwendet — kein `weatherMetrics`-
Fallback-Zweig, kein Crash wenn `wizard.weatherMetrics` undefined ist.
- Test: `issue_442_compare_wizard_step4.test.ts` — „AC-1: Step4Layout verwendet Context-Key 'compare-wizard-state'" (Source-Inspection: kein weatherMetrics-Zugriff)

**AC-5:** Given der Wizard zeigt Step 4 / When der Footer gerendert wird /
Then ist der primäre Aktions-Button immer aktiviert (`disabled` ist nicht gesetzt),
unabhängig davon ob der Nutzer Buckets konfiguriert hat oder nicht.
- Test: `issue_440_compare_wizard_state.test.ts` — `canAdvanceCurrent` default-true für Steps 3–5

**AC-6:** Given Step 4 zeigt den SMS-Tab (`activeChannel === 'sms'`) /
When der OutputLayoutEditor für SMS gerendert wird /
Then ist keine `BucketSection`-Tabelle sichtbar; stattdessen zeigt der Editor eine flache
priorisierte Liste mit ▲▼-Buttons und eine Budget-Anzeige
(`data-testid="sms-budget-display"`).
- Test: delegiert an `OutputLayoutEditor` (AC-9 in `issue_430_431_step4_layout.test.ts`)

**AC-7:** Given `CompareWizard.svelte` und `state.currentStep === 4` /
When der Wizard-Body gerendert wird /
Then ist `<Step4Layout />` eingebunden und im DOM sichtbar
(`data-testid="step4-layout"` ist vorhanden).
- Test: `issue_442_compare_wizard_step4.test.ts` — „AC-7: CompareWizard importiert Step4Layout / mountet bei currentStep === 4"

**AC-8:** Given `state.channelLayouts` ist nach Step 4 mit Daten gefüllt /
When `save()` aufgerufen wird /
Then enthält das an die API gesendete Payload-Objekt
`display_config.channel_layouts` mit den vom Nutzer konfigurierten Kanal-Layouts.
- Test: `issue_442_compare_wizard_step4.test.ts` — „AC-8: compareWizardState save() schreibt channel_layouts in display_config"

**AC-9:** Given Step4Layout wird gemountet / When der Mount-Hook läuft /
Then werden `GET /api/metrics`, `GET /api/templates` und `GET /api/metric-presets`
parallel aufgerufen; `loading` wechselt nach Abschluss aller drei Requests auf `false`.
- Test: `issue_442_compare_wizard_step4.test.ts` — „AC-9: Step4Layout importiert ChannelPreviewBlock" (Source-Inspection: api.get × 3 im onMount)

**AC-10:** Given Step4Layout wird gemountet und `catalog` ist noch leer (`{}`) /
When der `$effect` für `channelLayouts`-Sync zum ersten Mal läuft /
Then wird die Sync-Logik durch den Guard `if (loading || Object.keys(catalog).length === 0) return;`
übersprungen — `wizard.channelLayouts` bleibt unverändert bis Katalog und Loading-Flag
korrekte Werte haben.
- Test: `issue_442_compare_wizard_step4.test.ts` — „AC-10: Step4Layout enthält $effect-Timing-Guard gegen leere Katalog-Writes"

## Known Limitations

- `Step4Layout` im Compare-Kontext startet für neue Subscriptions mit leeren Buckets
  (`autoAssign([], catalog)`), da der Compare-Wizard keinen `weatherMetrics`-State aus
  Step 3 kennt. Der Nutzer muss Metriken im Editor manuell hinzufügen oder einen Preset
  anwenden.
- `OutputLayoutEditor` wird mit 4 separaten Channel-Instanzen gemountet. Das erzeugt
  beim Einstieg in Step 4 eine 4-fache Mount-Last; Performance-Profiling steht aus.
- Wenn `/api/metrics` beim Mount fehlschlägt, zeigt Step 4 einen Lade-Spinner ohne
  Fallback-Metriken. Fehler-Handling (Retry, Toast) ist nicht Teil dieser Spec.

## Changelog

- 2026-05-29: Initial spec erstellt für Issue #442 (Compare-Wizard Step 4 Layout).
  Direktes Adaptat von issue_430_431_wizard_layout_step.md mit drei Abweichungen:
  Context-Key, kein weatherMetrics-Fallback, CHANNEL_COL_BUDGET-Werte für Telegram (7) und Signal (5).
