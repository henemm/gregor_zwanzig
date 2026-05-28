---
entity_id: issue_432_step3_step5_polish
type: module
created: 2026-05-28
updated: 2026-05-28
status: draft
version: "1.0"
tags: [frontend, wizard, svelte, step3, step5, issue-432, epic-428]
---

# Issue #432 — Step 3 Wetter-Umbau + Step 5 Reports (PR 4/4 von Epic #428)

## Approval

- [ ] Approved

## Purpose

Schließt Epic #428 ab, indem Step 3 (Wetter) von hartkodiertem 6-Metriken-Layout mit Horizon-Pills
auf einen dynamischen Metrik-Katalog aus der API mit Format-Dropdown und 5 Kategorien-Gruppen
umgebaut wird, und indem Step 4 Reports zur Datei `Step5Reports.svelte` umbenannt und auf 3 Cards
(statt 4) reduziert wird: der Mehrtages-Trend wird ein Toggle in der Abend-Card, die "DEINE
KANÄLE"-Sammelkarte entfällt zugunsten einer Kanal-Chip-Reihe pro Card, und die AUTARK-Pill in der
Warnungen-Card wird entfernt.

Die Vorgänger-Spec `issue_412_422_wizard_step4.md` (DEINE-KANÄLE-Karte) wird durch diese Spec
abgelöst — AC-1 bis AC-5 aus jenem Spec sind nach diesem PR nicht mehr gültig, da die Karte
entfernt wird (PO-Entscheidung 2026-05-28).

## Source

- **Schicht:** Reines Frontend (SvelteKit). Kein Go-Backend, kein Python-Backend.
- **Dateien (geändert):**
  - `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte` (kompletter Umbau, ~182 LoC → ~280 LoC)
  - `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` (Import Step4Reports → Step5Reports, ±2 LoC)
- **Dateien (umbenannt):**
  - `frontend/src/lib/components/trip-wizard/steps/Step4Reports.svelte` → `Step5Reports.svelte` (Umbenennung + Inhalts-Umbau, ~175 LoC → ~140 LoC)
- **Dateien (gelöscht):**
  - `frontend/src/lib/components/trip-wizard/steps/Step4Reports.svelte` (nach Umbenennung entfernt)
- **Tests (angepasst):**
  - `frontend/e2e/trip-wizard-step3-wetter.spec.ts` (Horizon-Pill-Asserts entfernen, Format-Dropdown + Kategorien-Asserts ergänzen)
  - `frontend/e2e/trip-wizard-step4-reports.spec.ts` → `trip-wizard-step5-reports.spec.ts` (umbenennen, 4→3-Card-Asserts anpassen, Kanal-Chip-Asserts)
- **Tests (neu):**
  - `frontend/src/lib/components/trip-wizard/__tests__/issue_432_step3_step5.test.ts` (Source-Inspection-Pattern, node:test)

## Dependencies

| Entity | Type | Zweck |
|--------|------|-------|
| `GET /api/metrics` | Go-Backend-Endpoint (vorhanden) | Metrik-Katalog beim Mount von Step 3 laden; liefert `MetricCatalog` mit Kategorie-Zuordnung |
| `CATEGORY_ORDER` — `metricsEditor.ts:47` | TypeScript-Konstante (vorhanden) | 5 Kategorien in fester Reihenfolge (`temperature`, `wind`, `precipitation`, `atmosphere`, `winter`) |
| `CATEGORY_LABELS` — `metricsEditor.ts:55` | TypeScript-Konstante (vorhanden) | Deutsche Labels pro Kategorie-Schlüssel |
| `WeatherConfigMetric` — `frontend/src/lib/types.ts:127` | TypeScript-Interface (vorhanden) | Einzel-Metrik mit `metric_id`, `enabled`, `use_friendly_format`, `horizons?` |
| `WizardState` — `wizardState.svelte.ts` | TypeScript-Klasse (vorhanden) | `wizard.weatherMetrics` (Step-3-State), `wizard.briefings` (Step-5-State), `wizard.activity` |
| `Switch` — `$lib/components/atoms` | Atom (vorhanden) | Toggle „3–7-Tage-Ausblick enthalten" in Abend-Card |
| `Eyebrow` — `$lib/components/ui/eyebrow` | Atom (vorhanden) | Gruppen-Header in Step 3 + Card-Header in Step 5 |
| `GCard` — `$lib/components/ui/g-card` | Komponente (vorhanden) | Card-Container in Step 5 |
| `Pill` — `$lib/components/ui/pill` | Atom (vorhanden) | Kanal-Chips pro Card in Step 5 (aria-pressed-Toggle) |
| `Field` — `$lib/components/molecules` | Molekül (vorhanden) | Aktivitätsprofil-Dropdown-Wrapper (bleibt unverändert) |
| `maskPhone` — `wizardHelpers.ts` | Hilfsfunktion (vorhanden) | Telefonnummern maskieren in Kanal-Chip-Untertitel (Step 5) |
| Profile-Context `trip-wizard-profile` | SvelteKit-Context (vorhanden via #412) | Kanal-Kontaktdaten (E-Mail, Signal, Telegram) in Step 5 |
| `issue_412_422_wizard_step4.md` | Vorgänger-Spec (deprecated ab #432) | DEINE-KANÄLE-Karte wird durch #432 abgelöst; alte AC-1..5 ungültig |

## Scope

**Nur Frontend.** Keine Änderungen am Go-Backend oder Python-Backend.

Nicht in Scope (explizit):
- Backend-Datenmodell für 4 Format-Optionen (Roh/Skala/Vereinfacht/Symbol) — Issue #435
- Mehrtages-Trend-Toggle Backend-Verkabelung — Issue #437
- „Inhalt im Output-Editor anpassen →"-Link Routing — Issue #436
- Per-Report-Layout-Overrides (Abend ≠ Morgen pro Kanal) — Issue #434
- Echtes Drag-and-Drop (Touch + Maus) — Issue #433
- Master-Spec `epic_136_trip_wizard.md` Update auf 5 Steps — separate Doku-Pflege
- WeatherMetricsTab.svelte oder andere Trip-Detail-Tabs — nicht berührt

## Implementation Details

### A. Step3Weather.svelte — kompletter Umbau

**1. HorizonChip-Import und -Verwendung vollständig entfernen:**

```typescript
// ENTFERNEN:
// import { HorizonChip } from '$lib/components/ui/horizon-chip';
// import type { Horizons } from '$lib/types';
// import { HORIZONS_ALL } from '$lib/types';
// Alle cloneHorizons(), ensureHorizons(), makeToggleHorizon() Funktionen
// Alle <HorizonChip ...> Tags aus dem Template
```

`WeatherConfigMetric.horizons` wird beim Save nicht mehr gesetzt (bleibt `undefined`);
der Output-Renderer löst Horizonte pro Kanal auf.

**2. API-Fetch für Metrik-Katalog beim Mount:**

```typescript
import { onMount } from 'svelte';
import { CATEGORY_ORDER, CATEGORY_LABELS } from '$lib/components/trip-detail/metricsEditor';
import type { MetricCatalog } from '$lib/types';  // oder lokale Typ-Deklaration

let catalog = $state<MetricCatalog>({});
let loading = $state(true);

onMount(async () => {
  try {
    const res = await fetch('/api/metrics');
    if (res.ok) catalog = await res.json() as MetricCatalog;
  } finally {
    loading = false;
  }
});
```

**3. Metrik-Initialisierung aus Katalog (ersetzt DEFAULT_METRICS):**

```typescript
// Nach dem Mount: wizard.weatherMetrics aus Katalog befüllen wenn noch leer
$effect(() => {
  if (loading || wizard.weatherMetrics.length > 0) return;
  const allMetrics: WeatherConfigMetric[] = [];
  for (const catKey of CATEGORY_ORDER) {
    const ids: string[] = catalog[catKey]?.metrics?.map((m: { id: string }) => m.id) ?? [];
    for (const id of ids) {
      allMetrics.push({ metric_id: id, enabled: true, use_friendly_format: false });
    }
  }
  if (allMetrics.length > 0) wizard.weatherMetrics = allMetrics;
});
```

**4. Format-Dropdown-State (Frontend-only, kein Datenmodell-Change):**

```typescript
// Lokale Map: metric_id → 'raw' | 'scale' | 'simplified' | 'symbol'
// Wird NICHT in WeatherConfigMetric.horizons oder einem neuen Feld gespeichert.
// Beim Save wird nur use_friendly_format: boolean abgeleitet:
//   raw → false, scale/simplified/symbol → true
let formatModeMap = $state<Record<string, 'raw' | 'scale' | 'simplified' | 'symbol'>>({});

function getFormatMode(metricId: string): 'raw' | 'scale' | 'simplified' | 'symbol' {
  return formatModeMap[metricId] ?? 'raw';
}

function handleFormatChange(metricId: string, mode: 'raw' | 'scale' | 'simplified' | 'symbol') {
  formatModeMap[metricId] = mode;
  const metric = wizard.weatherMetrics.find(m => m.metric_id === metricId);
  if (metric) metric.use_friendly_format = mode !== 'raw';
}
```

**5. Aktiv-Zähler für Header:**

```typescript
// Reaktiver Zähler: "METRIKEN · N AKTIV VON M"
const activeCount = $derived(wizard.weatherMetrics.filter(m => m.enabled).length);
const totalCount = $derived(wizard.weatherMetrics.length);
```

**6. Template-Struktur (Gruppen mit Sticky-Header):**

```svelte
<div class="step3-weather flex flex-col gap-6 py-4" data-testid="step3-weather">
  <!-- Aktivitätsprofil-Dropdown: unverändert -->
  <section class="flex flex-col gap-2">
    <Field label="AKTIVITÄTSPROFIL">
      <select data-testid="activity-dropdown" ...>...</select>
    </Field>
  </section>

  <!-- Metriken-Bereich mit Header + scrollbarem Container -->
  <section class="flex flex-col gap-2">
    <div class="flex items-center justify-between">
      <Eyebrow data-testid="metrics-header">
        METRIKEN · {activeCount} AKTIV VON {totalCount}
      </Eyebrow>
    </div>

    {#if loading}
      <p class="text-sm text-[var(--g-ink-muted)]">Metriken laden...</p>
    {:else}
      <!-- Scrollbarer Container mit Fade-Indikator -->
      <div class="metrics-scroll-container relative max-h-[480px] overflow-y-auto"
           data-testid="metrics-scroll-container">

        <!-- Pro Kategorie eine Gruppe -->
        {#each CATEGORY_ORDER as catKey (catKey)}
          {@const catMetrics = getMetricsForCategory(catKey)}
          {#if catMetrics.length > 0}
            <div class="metric-group" data-testid={`metric-group-${catKey}`}>
              <!-- Sticky Gruppen-Header -->
              <div
                class="sticky top-0 z-10 bg-[var(--g-paper)] py-1"
                data-testid={`metric-group-header-${catKey}`}
              >
                <Eyebrow>{CATEGORY_LABELS[catKey]}</Eyebrow>
              </div>

              <!-- Metrik-Zeilen der Gruppe -->
              {#each catMetrics as metric (metric.metric_id)}
                <div
                  data-testid={`metric-row-${metric.metric_id}`}
                  class="flex flex-wrap items-center gap-3 rounded-md border
                         border-[var(--g-ink-faint)]/20 px-3 py-2 mb-1"
                >
                  <!-- Checkbox + Label -->
                  <label class="flex items-center gap-2 text-sm min-w-[10rem]">
                    <input type="checkbox" checked={metric.enabled}
                      onchange={makeToggleEnabled(metric)} />
                    <span>{getCatalogLabel(metric.metric_id)}</span>
                  </label>

                  <!-- Format-Dropdown -->
                  <select
                    data-testid={`metric-format-select-${metric.metric_id}`}
                    value={getFormatMode(metric.metric_id)}
                    onchange={(e) => handleFormatChange(
                      metric.metric_id,
                      (e.target as HTMLSelectElement).value as 'raw'|'scale'|'simplified'|'symbol'
                    )}
                    class="h-8 rounded border border-[var(--g-ink-faint)]/40 bg-transparent
                           px-2 text-xs outline-none"
                  >
                    <option value="raw">Roh</option>
                    <option value="scale">Skala</option>
                    <option value="simplified">Vereinfacht</option>
                    <option value="symbol">Symbol</option>
                  </select>
                </div>
              {/each}
            </div>
          {/if}
        {/each}

        <!-- Fade-Indikator unten -->
        <div
          class="fade-bottom pointer-events-none sticky bottom-0 h-8
                 bg-gradient-to-t from-[var(--g-paper)] to-transparent"
          data-testid="metrics-fade-indicator"
          aria-hidden="true"
        ></div>
      </div>
    {/if}
  </section>
</div>
```

**Hilfsfunktion `getMetricsForCategory(catKey)`:**

```typescript
function getMetricsForCategory(catKey: string): WeatherConfigMetric[] {
  const catMetricIds: string[] = catalog[catKey]?.metrics?.map((m: { id: string }) => m.id) ?? [];
  return wizard.weatherMetrics.filter(m => catMetricIds.includes(m.metric_id));
}
```

---

### B. Step5Reports.svelte — Umbenennung + Inhalts-Umbau

**1. Datei umbenennen** (git mv):

```bash
git mv frontend/src/lib/components/trip-wizard/steps/Step4Reports.svelte \
        frontend/src/lib/components/trip-wizard/steps/Step5Reports.svelte
```

**2. DEINE-KANÄLE-Karte entfernen:**

```svelte
<!-- ENTFERNEN: gesamter <GCard data-testid="card-channels"> Block -->
<!-- ENTFERNEN: channelRows-Konstante, makeChannelHandler() -->
<!-- ENTFERNEN: Profile-Context-Read + maskPhone-Import bleiben,
     da sie für Kanal-Chips pro Card weiter benötigt werden -->
```

**3. Abend-Card: Mehrtages-Trend-Toggle ergänzen + Kanal-Chips:**

```svelte
<GCard data-testid="card-evening" class="...">
  <Eyebrow>Abend-Briefing</Eyebrow>
  <label class="flex items-center gap-2 text-sm">
    <input type="checkbox" checked={wizard.briefings.reports.evening.enabled}
      onchange={makeEnabledHandler('evening')} />
    Aktiv
  </label>
  <label class="flex flex-col gap-1 text-sm">
    <span class="text-[var(--g-ink-muted)]">Uhrzeit</span>
    <input type="time" lang="de" data-testid="evening-time"
      bind:value={wizard.briefings.reports.evening.time}
      class="h-9 w-36 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent
             px-2.5 font-mono outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]" />
  </label>

  <!-- Mehrtages-Trend-Toggle (Scope-Erweiterung 2026-05-28 — schließt #437) -->
  <!-- An wizard.trendEnabled gebunden; Default true (BC zu heutigem Backend-Verhalten) -->
  <div class="flex items-center gap-2 text-sm" data-testid="trend-toggle-row">
    <input
      type="checkbox"
      data-testid="evening-trend-toggle"
      bind:checked={wizard.trendEnabled}
      aria-label="3–7-Tage-Ausblick enthalten"
    />
    <span class="text-[var(--g-ink-muted)]">3–7-Tage-Ausblick enthalten</span>
  </div>

  <!-- Kanal-Chips -->
  {@render channelChips('evening')}
</GCard>
```

Lokaler State für den Toggle (UI-only, wird nicht persistiert):

```typescript
let trendEnabled = $state(false);
```

**4. Morgen-Card: Kanal-Chips ergänzen (sonst unverändert):**

```svelte
<GCard data-testid="card-morning" class="...">
  <!-- Inhalt unverändert (Eyebrow, Checkbox, Zeit-Input) -->
  ...
  <!-- Kanal-Chips -->
  {@render channelChips('morning')}
</GCard>
```

**5. Warnungen-Card: AUTARK-Pill entfernen, Kanal-Chips ergänzen:**

```svelte
<GCard data-testid="card-alerts" class="...">
  <Eyebrow>Warnungen</Eyebrow>
  <!-- ENTFERNEN: <Pill tone="accent">AUTARK</Pill> -->
  <p class="text-sm text-[var(--g-ink-muted)]">
    Warnungen werden automatisch ausgelöst, sobald eine Alarmregel überschritten wird.
  </p>
  <!-- Kanal-Chips -->
  {@render channelChips('alerts')}
</GCard>
```

**6. Mehrtages-Trend-Card entfernen:**

```svelte
<!-- ENTFERNEN: gesamter <GCard data-testid="card-trend"> Block -->
```

**7. `channelChips` Snippet (Svelte 5 `{#snippet}`):**

```svelte
{#snippet channelChips(reportKey: 'evening' | 'morning' | 'alerts')}
  <div class="channel-chips flex flex-wrap gap-1 mt-2"
       data-testid={`channel-chips-${reportKey}`}>
    {#each channelRows as row (row.key)}
      <button
        class="chip"
        data-testid={`channel-chip-${reportKey}-${row.key}`}
        aria-pressed={wizard.briefings.channels[row.key]}
        onclick={makeChannelHandler(row.key)}
        disabled={!row.contact}
      >
        {row.label}
      </button>
      {#if row.contact}
        <span class="font-mono text-xs text-[var(--g-ink-muted)]"
              data-testid={`channel-contact-${reportKey}-${row.key}`}>
          {row.contact}
        </span>
      {/if}
    {/each}
  </div>
{/snippet}
```

`channelRows` bleibt erhalten (ohne `makeChannelHandler`-Umbau nötig — Kanal-State ist geteilt
über alle Briefings).

**8. Grid-Klasse anpassen (3 statt 4 Cards):**

```svelte
<!-- War: <div class="reports-grid grid gap-4 sm:grid-cols-2"> -->
<div class="reports-grid grid gap-4 sm:grid-cols-2" data-testid="reports-grid">
  <!-- nur 3 GCard-Kinder -->
</div>
```

---

### C. TripWizardShell.svelte — Import-Anpassung

```typescript
// ENTFERNEN:
// import Step4Reports from './steps/Step4Reports.svelte';

// ERGÄNZEN:
import Step5Reports from './steps/Step5Reports.svelte';
```

```svelte
<!-- ÄNDERN (Step-Switch): -->
{:else if state.currentStep === 5}
  <Step5Reports />
```

Alle anderen Importe, stepLabels, stepTitles, stepHints, Footer-Logik bleiben byte-gleich.

---

### D. E2E-Tests anpassen

**`trip-wizard-step3-wetter.spec.ts`:**

```typescript
// ENTFERNEN: alle HorizonChip-Asserts (z.B. page.locator('[data-testid="horizon-chip-today"]'))
// ENTFERNEN: Asserts auf .format-label span mit "Roh"/"Indikator"

// ERGÄNZEN:
// Format-Dropdown pro Metrik vorhanden
await expect(page.locator('[data-testid^="metric-format-select-"]').first()).toBeVisible();
// Dropdown hat 4 Optionen
const opts = page.locator('[data-testid="metric-format-select-temperature"] option');
await expect(opts).toHaveCount(4);

// 5 Kategorien-Gruppen sichtbar
for (const cat of ['temperature','wind','precipitation','atmosphere','winter']) {
  await expect(page.locator(`[data-testid="metric-group-${cat}"]`)).toBeVisible();
}

// Metriken-Header zeigt Zähler
await expect(page.locator('[data-testid="metrics-header"]')).toContainText('AKTIV VON');
```

**`trip-wizard-step5-reports.spec.ts`** (umbenannt aus `step4-reports.spec.ts`):

```typescript
// ENTFERNEN: card-channels-Asserts, card-trend-Asserts, AUTARK-Pill-Asserts
// ÄNDERN: 4-Card-Asserts auf 3 (card-evening, card-morning, card-alerts)

// ERGÄNZEN:
// Trend-Toggle vorhanden
await expect(page.locator('[data-testid="evening-trend-toggle"]')).toBeVisible();
// Kanal-Chips pro Card
for (const card of ['evening','morning','alerts']) {
  await expect(page.locator(`[data-testid="channel-chips-${card}"]`)).toBeVisible();
}
// DEINE KANÄLE-Karte ist weg
await expect(page.locator('[data-testid="card-channels"]')).not.toBeVisible();
```

---

### LoC-Budget (Override auf 500 gesetzt)

| Datei | Δ LoC (grob) |
|-------|--------------|
| `Step3Weather.svelte` (kompletter Umbau −182 / +280) | +98 |
| `Step5Reports.svelte` (Umbenennung + Umbau −175 / +140) | −35 |
| `Step4Reports.svelte` (Datei löscht sich durch git mv) | −175 |
| `TripWizardShell.svelte` (Import-Swap) | ±2 |
| `trip-wizard-step3-wetter.spec.ts` (E2E-Umbau) | +50 |
| `trip-wizard-step5-reports.spec.ts` (NEU via Umbenennung + Umbau) | +80 |
| `issue_432_step3_step5.test.ts` (NEU, Source-Inspection) | +200 |
| **Summe** | **~+220 LoC netto** |

`workflow.py set-field loc_limit_override 500` vor Implementierungsbeginn setzen.

## Expected Behavior

- **Input:**
  - Step 3: Wizard-State nach abgeschlossenem Step 2; `/api/metrics` antwortet mit `MetricCatalog` (15+ Metriken in 5 Kategorien).
  - Step 5: Wizard-State nach abgeschlossenem Step 4; Profile-Context mit Kontaktdaten (kann null sein).

- **Output:**
  - Step 3: `wizard.weatherMetrics` enthält nach Nutzereingabe N Metriken mit `enabled: bool` und `use_friendly_format: bool` (abgeleitet aus Format-Dropdown); keine `horizons`-Felder.
  - Step 5: `wizard.briefings.channels.*` spiegelt Chip-Zustände pro Card; `wizard.briefings.reports.{evening|morning}.{enabled|time}` unverändert. `trendEnabled` ist UI-only-State, geht nicht in `toTripPayload()` ein (bis #437).

- **Side effects:**
  - Step 3: Ein `GET /api/metrics`-Call beim Mount. Kein weitere API-Calls in Step 3.
  - Step 5: Kein API-Call (Profile-Context bereits durch `+page.server.ts` geladen).
  - TripWizardShell: `Step4Reports.svelte` wird nicht mehr referenziert; kein Build-Fehler nach Dateilöschung.

## Acceptance Criteria

**AC-1:** Given `Step3Weather.svelte` im Filesystem /
When der Quellcode auf `HorizonChip`-Imports und -Tags untersucht wird /
Then enthält die Datei keinen Import aus `horizon-chip` und kein `<HorizonChip`-Tag — die Komponente ist vollständig entfernt (Source-Inspection-Test, nicht DOM-Test).

**AC-2:** Given Step 3 im Wizard ist geöffnet und die API hat den Metrik-Katalog geliefert /
When der User eine beliebige Metrik-Zeile betrachtet /
Then ist ein `<select>`-Element mit `data-testid="metric-format-select-{id}"` vorhanden, das genau 4 `<option>`-Einträge mit den Werten `raw`, `scale`, `simplified`, `symbol` enthält — keine andere Anzahl, keine anderen Werte.

**AC-3:** Given Step 3 zeigt Metrik-Zeilen aus dem API-Katalog /
When alle Kategorien gerendert sind /
Then sind genau 5 Gruppen-Container mit `data-testid="metric-group-{cat}"` sichtbar für `cat` in `[temperature, wind, precipitation, atmosphere, winter]` — in dieser Reihenfolge, gemäß `CATEGORY_ORDER`.

**AC-4:** Given Step 3 ist gerendert und der Scroll-Container hat mehr Inhalt als sichtbar /
When der Gruppen-Header einer Kategorie durch Scrollen den sichtbaren Bereich berührt /
Then bleibt der Header an der Oberkante des Scroll-Containers kleben — CSS `position: sticky; top: 0` ist auf dem Header-Element gesetzt (Source-Inspection-Test für CSS-Klasse, ergänzt durch visuellen E2E-Test).

**AC-5:** Given Step 3 wird gerendert und `wizard.weatherMetrics` ist anfangs leer /
When `/api/metrics` erfolgreich antwortet /
Then zeigt der Header `data-testid="metrics-header"` den Text „METRIKEN · N AKTIV VON M" mit N > 0 und M > 0, wobei M die Gesamtzahl der aus dem Katalog geladenen Metriken ist.

**AC-6:** Given der User wählt im Format-Dropdown einer Metrik die Option „Roh" /
When `wizard.weatherMetrics` nach der Änderung ausgewertet wird /
Then ist `use_friendly_format` für diese Metrik `false`; bei Auswahl von „Skala", „Vereinfacht" oder „Symbol" ist `use_friendly_format` `true` — das lokale `formatModeMap` wird nicht in `WeatherConfigMetric` geschrieben.

**AC-7:** Given `Step5Reports.svelte` liegt im Verzeichnis `trip-wizard/steps/` /
When das Verzeichnis aufgelistet wird /
Then existiert `Step5Reports.svelte` und `Step4Reports.svelte` existiert nicht mehr — die Umbenennung ist abgeschlossen (Source-Inspection-Test: `fs.existsSync`-Asserts).

**AC-8:** Given Step 5 im Wizard ist geöffnet /
When der DOM auf Card-Container untersucht wird /
Then sind genau 3 Cards mit `data-testid` `card-evening`, `card-morning`, `card-alerts` vorhanden — kein `card-trend`, kein `card-channels` (DOM-Count-Assert via node:test oder Playwright).

**AC-9:** Given `Step5Reports.svelte` im Filesystem /
When der Quellcode auf `<Pill`-Tags untersucht wird /
Then enthält die Datei kein `<Pill tone="accent">AUTARK</Pill>` oder gleichwertiges Markup — die AUTARK-Pill ist vollständig entfernt (Source-Inspection-Test).

**AC-10:** Given Step 5 ist gerendert /
When die Abend-Card betrachtet wird /
Then ist ein Toggle-Element mit `data-testid="evening-trend-toggle"` sichtbar und mit dem Label „3–7-Tage-Ausblick enthalten" assoziiert; der Toggle ist initial **aktiviert** (`checked=true`, BC zum heutigen Backend-Default `multi_day_trend_reports = ["evening"]` — siehe AC-18). Bei AC-10 Konsistenz: testid- und Default-Werte werden durch AC-18/AC-19 (Scope-Erweiterung 2026-05-28) festgelegt.

**AC-11:** Given Step 5 ist gerendert /
When jede der 3 Cards (Abend, Morgen, Warnungen) betrachtet wird /
Then enthält jede Card einen Kanal-Chip-Container mit `data-testid="channel-chips-{evening|morning|alerts}"`, der mindestens 1 sichtbares Chip-Element enthält — die Kanalsteuerung ist direkt in der Card, nicht in einer separaten Sammelkarte.

**AC-12:** Given `TripWizardShell.svelte` im Filesystem /
When der Quellcode auf `Step4Reports`-Referenzen untersucht wird /
Then enthält die Datei keinen `import … Step4Reports` und keinen `<Step4Reports`-Tag — nur `import … Step5Reports` und `<Step5Reports` sind vorhanden (Source-Inspection-Test).

**AC-13:** Given der Wizard wird auf Step 5 navigiert /
When der Footer gerendert wird /
Then zeigt der primäre Aktions-Button den Text „Trip speichern" (`data-testid="trip-wizard-save"`), da Step 5 das Save auslöst — TripWizardShell-Logik (`currentStep < 5`) ist durch die Umbenennung nicht verändert, der Wert 5 bleibt der Save-Trigger.

**AC-14:** Given ein Kanal hat im Profile-Context eine Kontaktangabe (z.B. `mail_to`) /
When die Kanal-Chips in der Abend-Card gerendert werden /
Then ist das Chip-Element für diesen Kanal interaktiv (`disabled`-Attribut fehlt), und die maskierte/unmaskierte Kontaktangabe ist als `data-testid="channel-contact-evening-email"` im DOM sichtbar.

**AC-15:** Given ein Kanal hat im Profile-Context keine Kontaktangabe /
When die Kanal-Chips in einer beliebigen Card gerendert werden /
Then ist das Chip-Element für diesen Kanal deaktiviert (`disabled`-Attribut gesetzt oder `aria-disabled="true"`) und `wizard.briefings.channels[key]` wird nicht automatisch aktiviert — Konsistenz mit dem bisherigen AC-4 aus `issue_412_422_wizard_step4.md`.

### Trend-Persistenz (Scope-Erweiterung 2026-05-28 — schließt Issue #437)

Der Mehrtages-Trend-Toggle in der Abend-Card wird nicht mehr UI-only ausgeliefert, sondern persistiert seinen Wert direkt in das bereits bestehende `report_config.multi_day_trend_evening`-Feld. Damit wird Issue #437 mit dieser PR mit-erledigt.

**Datenmodell ist bereits vorhanden:**
- Frontend `ReportConfig.multi_day_trend_evening?: boolean` in `frontend/src/lib/types.ts:161`
- Backend `TripReportConfig.multi_day_trend_reports: list[str]` in `src/app/models.py:673` (Default `["evening"]` — d.h. Trend ist heute by-default an)
- Backend-Renderer respektiert `multi_day_trend_reports` schon — keine Renderer-Änderung nötig

**Implementation:**

```typescript
// wizardState.svelte.ts: neues Feld
trendEnabled = $state<boolean>(true);  // Default: Trend ist by default an (BC zu heutigem Verhalten)

// toTripPayload(): zusätzlich zu rc-Block:
rc.multi_day_trend_evening = this.trendEnabled;
// Backward-kompatibel: backend mappt multi_day_trend_evening und/oder
// multi_day_trend_reports — beide Schreibwege erlaubt.

// Step5Reports.svelte: Toggle bind:checked={wizard.trendEnabled}
// (statt lokalem $state)
```

**AC-16:** Given `wizard.trendEnabled === true` (Default) /
When `toTripPayload()` aufgerufen wird /
Then enthält das Trip-Payload `report_config.multi_day_trend_evening === true` und der Backend-Renderer fügt den Mehrtages-Trend-Block in das Abend-Briefing ein.

**AC-17:** Given der User schaltet den Toggle „3–7-Tage-Ausblick enthalten" aus /
When der Trip gespeichert und neu geladen wird /
Then ist `wizard.trendEnabled === false` und das Abend-Briefing enthält keinen Mehrtages-Trend-Block mehr — die Auswahl überlebt das Speichern.

**AC-18:** Given ein alter Trip ohne `multi_day_trend_evening`-Feld wird im Wizard geöffnet /
When der WizardState aus dem geladenen Trip befüllt wird /
Then ist `wizard.trendEnabled === true` als sicherer Default (BC zu heutigem Backend-Verhalten, das `multi_day_trend_reports: ["evening"]` als Default hat).

**AC-19:** Given `wizard.trendEnabled` ist gesetzt /
When der Step5Reports-Source-Inspect prüft, ob der Toggle gebunden ist /
Then findet er einen `bind:checked={wizard.trendEnabled}` (oder eine äquivalente Zwei-Wege-Bindung) an dem `<input type="checkbox">` mit `data-testid="evening-trend-toggle"` — kein lokaler `$state`-Wert mehr.

## Out of Scope

- Backend-Datenmodell für 4 Format-Optionen (Roh/Skala/Vereinfacht/Symbol) — Issue #435; in #432 mappt das UI auf `use_friendly_format: boolean`.
- ~~Mehrtages-Trend-Toggle Backend-Verkabelung — Issue #437~~ → **mit dieser PR erledigt** (PO-Entscheidung 2026-05-28, siehe Sektion „Trend-Persistenz" oben). Issue #437 wird mit dem #432-PR geschlossen.
- „Inhalt im Output-Editor anpassen →"-Link Routing aus Step 5 — Issue #436.
- Per-Report-Layout-Overrides (Abend ≠ Morgen pro Kanal) — Issue #434.
- Echtes Drag-and-Drop (Touch + Maus) — Issue #433.
- Master-Spec `epic_136_trip_wizard.md` auf 5 Steps aktualisieren — separate Doku-Pflege.
- WeatherMetricsTab.svelte, Trip-Detail-Tabs — nicht berührt.

## Known Limitations

- **Format-Dropdown verliert Wahl nach Seitenreload:** Ein gespeicherter Trip mit `use_friendly_format=true` wird beim erneuten Wizard-Aufruf als „Skala" (Default non-raw) angezeigt — nicht als „Vereinfacht" oder „Symbol", auch wenn der User das eingestellt hatte. Issue #435 bringt das echte 4-Optionen-Datenmodell.
- ~~Mehrtages-Trend-Toggle UI-only~~ → behoben in dieser PR (Scope-Erweiterung 2026-05-28). Toggle persistiert in `report_config.multi_day_trend_evening`.
- **`/api/metrics`-Fehlerfall:** Wenn der Endpoint beim Mount fehlschlägt, bleibt `catalog` leer und `wizard.weatherMetrics` wird nicht befüllt. Ein Retry oder Fehlermeldungs-Toast ist nicht Teil dieser Spec. Der User sieht eine leere Metrik-Liste (leer, nicht Fallback auf 6 Hardcoded-Metriken).
- **Step 5 Mobile-Layout:** 3 Cards stapeln sich 1-spaltig auf Mobile (Default, durch `sm:grid-cols-2` für Desktop). Keine neue Mobile-Behandlung in dieser Spec nötig.
- **Kanal-Chip-Zustand ist geteilt:** Ein Chip-Toggle in der Abend-Card ändert `wizard.briefings.channels[key]` global — derselbe Schalter ist deshalb in der Morgen-Card und Warnungen-Card ebenfalls umgestellt. Das ist das gewünschte Verhalten (ein Kanal = ein Zustand für alle Reports), aber es wirkt auf den ersten Blick überraschend.

## Changelog

- 2026-05-28: Initial spec erstellt für Issue #432 (PR 4/4 von Epic #428). Kombiniert Step-3-Umbau (Horizon-Pills → Format-Dropdown, API-Katalog, 5 Kategorien-Gruppen) und Step-5-Umbau (3 Cards, Trend-Toggle, AUTARK-Pill entfernt, Kanal-Chips pro Card, Datei-Umbenennung). Vorgänger-Spec `issue_412_422_wizard_step4.md` ist durch diese Spec abgelöst (DEINE-KANÄLE-Karte entfernt, PO-Entscheidung 2026-05-28).
- 2026-05-28 (Scope-Erweiterung, PO-Bestätigung): Sektion „Trend-Persistenz" + AC-16..AC-19 ergänzt. Issue #437 wird mit dieser PR mit-erledigt — Trend-Toggle persistiert in `report_config.multi_day_trend_evening` (Datenmodell-Feld existiert bereits, kein Backend-Umbau).
