---
entity_id: issue_409_trip_detail_overview
type: module
created: 2026-05-27
updated: 2026-05-27
status: draft
version: "1.0"
tags: [frontend, svelte, trip-detail, overview, layout, issue-409]
---

# Issue #409 — TripOverview: Linke Spalte + Hero-Kacheln + AlertsPreviewCard

## Approval

- [ ] Approved

## Purpose

Baut den Übersicht-Tab (`TripOverview.svelte`) von einem einfachen 2×2-Card-Grid in ein
vollständiges zweispaltiges Desktop-Layout um: Links (2/3 Breite) zeigen `FullProfile`-SVG
und `StageList` eine vollständige Routenübersicht; rechts (1/3 Breite) stehen vier
Preview-Karten in fester Reihenfolge. Über dem Zweispalter werden drei Hero-Kacheln
angezeigt, die den Trips-Status, die nächste Briefing-Zeit und den Etappen-Fortschritt
auf einen Blick liefern. Zusätzlich wird `AlertsPreviewCard.svelte` als neue Komponente
erstellt, die bisher fehlende vierte rechte Karte.

Das Layout schließt die Lücke zwischen dem bestehenden Tabellen-Entwurf aus Issue #302
und dem Soll-Mockup `soll-flow7B-trip-detail.png`, das FullProfile und StageList als
zentrale Elemente des Übersicht-Tabs vorsieht.

## Source

- **Files:**
  - `frontend/src/lib/components/trip-detail/TripOverview.svelte` (Komplett-Neubau, ~140 LoC)
  - `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` (NEU, ~65 LoC)
  - `frontend/src/lib/components/trip-detail/index.ts` (Export `AlertsPreviewCard` hinzufügen)
  - `frontend/e2e/issue-302-trip-detail-redesign.spec.ts` (AC-4a–4d mit `test.skip` markieren)

## Scope

**Nur Frontend.** Kein Go-Backend-Endpoint geändert. Kein Python-Backend betroffen.

Nicht geändert:
- `TripHeader.svelte` — bleibt wie durch Issue #302 implementiert
- `TripTabs.svelte` — bleibt wie durch Issue #302 implementiert
- `FullProfile.svelte`, `StageList.svelte` — werden nur eingebunden, kein interner Umbau
- `BriefingPreviewCard.svelte`, `WeatherMetricsPreviewCard.svelte`, `PreviewCard.svelte` — unverändert
- `internal/`, `src/` — kein Backend-Code betroffen

## Dependencies

| Abhängigkeit | Art | Zweck |
|---|---|---|
| `frontend/src/lib/components/trip-detail/FullProfile.svelte` | Svelte-Komponente (vorhanden) | Props: `{ trip, selectedStageId, onSelectStage, now? }` — SVG-Höhenprofil der gesamten Tour |
| `frontend/src/lib/components/trip-detail/StageList.svelte` | Svelte-Komponente (vorhanden) | Props: `{ trip, selectedStageId, onSelectStage, now? }` — Liste aller Etappen-Cards |
| `frontend/src/lib/components/trip-detail/BriefingPreviewCard.svelte` | Svelte-Komponente (vorhanden) | `data-testid="right-card-briefings"` — rechte Spalte Karte 1 |
| `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` | Svelte-Komponente (vorhanden) | `data-testid="right-card-weather"` — rechte Spalte Karte 2 |
| `frontend/src/lib/components/trip-detail/PreviewCard.svelte` | Svelte-Komponente (vorhanden) | `data-testid="right-card-preview"` — rechte Spalte Karte 4 |
| `frontend/src/lib/components/atoms/Stat.svelte` | Molecule (vorhanden) | Props: `{ label, value, sub?, unit?, tone?, layout?, size?, mono? }` — Hero-Kacheln |
| `frontend/src/lib/utils/rightColumn.ts` | Utility (vorhanden) | `getReportSchedule(trip)` → `ReportSchedule` mit morning/evening/enabled-Feldern |
| `frontend/src/lib/utils/fullProfile.ts` | Utility (vorhanden) | `getActiveStageId(trip, now)` → `string \| null` — aktive Etappe des heutigen Tages |
| `frontend/src/lib/utils/tripStats.ts` | Utility (vorhanden) | `computeTripStats(trip)` → `{ stages, kmTotal, ascentM }` |
| `frontend/src/lib/utils/tripStatus.ts` | Utility (vorhanden) | `deriveTripStatus(trip, now)` → `'planned' \| 'active' \| 'paused' \| 'archived'` — **erweitert durch `docs/specs/modules/fix_1271_status_zeitformat.md` (2026-07-16) um `draft`/`finished` (6 Zustände)** |
| `frontend/src/lib/utils/alertMetricLabels.ts` | Utility (vorhanden) | `ALERT_METRIC_LABELS`, `normalizeAlertMetric()` — Labels + Icons für Alert-Metriken in AlertsPreviewCard |
| `frontend/src/lib/types.ts` | TypeScript | `Trip`, `Stage`, `AlertRule` — keine Änderung nötig |
| `frontend/e2e/issue-302-trip-detail-redesign.spec.ts` | E2E-Test | AC-4a–4d werden mit `test.skip` + Kommentar superseded markiert |

## Implementation Details

### 1. `AlertsPreviewCard.svelte` (NEU)

Neue Komponente für die dritte rechte Karte (`right-card-alerts`).

**Props:**
```typescript
interface Props {
  trip: Trip;
}
```

**Render-Logik:**
```svelte
<script lang="ts">
  import type { Trip } from '$lib/types';
  import { GCard } from '$lib/components/ui/g-card';
  import { Eyebrow } from '$lib/components/ui/eyebrow';
  import { ALERT_METRIC_LABELS, normalizeAlertMetric } from '$lib/utils/alertMetricLabels';

  let { trip }: Props = $props();

  const enabledRules = $derived(
    (trip.alert_rules ?? []).filter((r) => r.enabled).slice(0, 5)
  );
  const isEmpty = $derived(enabledRules.length === 0);
</script>

<GCard data-testid="right-card-alerts" class="alerts-card">
  <Eyebrow>Alarmregeln</Eyebrow>
  <h3 class="card-title">Alert-Schwellen</h3>

  {#if isEmpty}
    <p data-testid="right-card-alerts-empty" class="empty-state">
      Noch keine Alerts konfiguriert
    </p>
  {:else}
    <ul class="alert-list">
      {#each enabledRules as rule}
        <li data-testid="alert-row" class="alert-row">
          <!-- Label aus ALERT_METRIC_LABELS, Fallback auf rule.metric -->
          <span class="alert-metric">{_alertLabel(rule)}</span>
        </li>
      {/each}
    </ul>
  {/if}

  <a href="#alerts" data-testid="right-card-alerts-edit-link" class="edit-link">
    Regeln bearbeiten →
  </a>
</GCard>
```

**`_alertLabel(rule)`** (lokale Hilfsfunktion im `<script>`-Block):
```typescript
function _alertLabel(rule: AlertRule): string {
  const key = normalizeAlertMetric(rule.metric);
  const meta = key ? ALERT_METRIC_LABELS[key] : undefined;
  if (!meta) return rule.metric;
  const cmp = meta.comparison ?? '>';
  const unit = meta.unit ? ` ${meta.unit}` : '';
  return `${meta.label_de} ${cmp} ${rule.threshold}${unit}`;
}
```

**Styling:** Konsistent mit `BriefingPreviewCard.svelte` — `var(--g-surface-1)` Hintergrund,
`1px solid var(--g-ink-faint)` Border, `var(--g-s-4)` Padding, `var(--g-s-2)` Gap.
Keine Magic-Pixel, keine Hex-Farbliterale.

### 2. `TripOverview.svelte` (Komplett-Neubau)

Ersetzt das bisherige 2×2-DetailCard-Grid vollständig durch das neue zweispaltige Layout
mit Hero-Kacheln oben.

**Props:**
```typescript
interface Props {
  trip: Trip;
  now?: Date;
}
let { trip, now = new Date() }: Props = $props();
```

**Reaktive Variablen:**
```typescript
const stats      = $derived(computeTripStats(trip));
const schedule   = $derived(getReportSchedule(trip));
const status     = $derived(deriveTripStatus(trip, now));
const activeId   = $derived(getActiveStageId(trip, now));
const stages     = $derived(trip.stages ?? []);
let selectedStageId = $state<string | null>(activeId);
```

**Hero-Kacheln (drei `Stat`-Komponenten in einem 3-Spalter):**

Etappe X/Y:
```typescript
const activeIndex = $derived(
  activeId !== null ? stages.findIndex((s) => s.id === activeId) : -1
);
const etappeValue = $derived(
  activeIndex >= 0 ? `${activeIndex + 1}/${stages.length}` : `–/${stages.length}`
);
```
→ `<Stat label="ETAPPE" value={etappeValue} data-testid="trip-hero-stat-active-stage" />`

Nächstes Briefing:
```typescript
const briefingTimes = $derived(
  [
    schedule.morning_enabled && schedule.morning ? schedule.morning : null,
    schedule.evening_enabled && schedule.evening ? schedule.evening : null
  ]
    .filter(Boolean)
    .sort() as string[]
);
const nextBriefing = $derived(briefingTimes[0] ?? '–:–');
```
→ `<Stat label="BRIEFING" value={nextBriefing} data-testid="trip-hero-stat-next-briefing" />`

Start / Status:
```typescript
const startStage = $derived(stages.find((s) => !!s.date));
const daysValue = $derived(() => {
  if (status === 'active') return 'Läuft';
  if (!startStage?.date) return '–';
  const diff = Math.ceil(
    (new Date(startStage.date).getTime() - now.getTime()) / 86_400_000
  );
  return diff === 0 ? 'Heute' : `${diff} Tg`;
});
const daysLabel = $derived(status === 'active' ? 'STATUS' : 'START IN');
```
→ `<Stat label={daysLabel} value={daysValue} data-testid="trip-hero-stat-days" />`

**Hauptlayout:**
```svelte
<section data-testid="trip-overview" class="trip-overview">
  <!-- Hero: 3 Kacheln -->
  <div data-testid="trip-hero" class="trip-hero">
    <div data-testid="trip-hero-title" class="trip-hero-title">{trip.name}</div>
    <div class="hero-stats">
      <div data-testid="trip-hero-stat-active-stage">
        <Stat label="ETAPPE" value={etappeValue} />
      </div>
      <div data-testid="trip-hero-stat-next-briefing">
        <Stat label="BRIEFING" value={nextBriefing} />
      </div>
      <div data-testid="trip-hero-stat-days">
        <Stat label={daysLabel} value={daysValue} />
      </div>
    </div>
  </div>

  <!-- Zweispalter -->
  <div class="overview-columns">
    <div data-testid="trip-overview-left-column" class="left-column">
      <FullProfile {trip} {selectedStageId} onSelectStage={(id) => selectedStageId = id} {now} />
      <StageList  {trip} {selectedStageId} onSelectStage={(id) => selectedStageId = id} {now} />
    </div>
    <div data-testid="trip-overview-right-column" class="right-column">
      <BriefingPreviewCard {trip} />
      <WeatherMetricsPreviewCard {trip} />
      <AlertsPreviewCard {trip} />
      <PreviewCard {trip} />
    </div>
  </div>
</section>
```

**CSS (nur `var(--g-*)` Tokens):**
```css
.trip-overview {
  display: flex;
  flex-direction: column;
  gap: var(--g-s-6);
}
.trip-hero {
  display: flex;
  flex-direction: column;
  gap: var(--g-s-3);
}
.hero-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--g-s-4);
}
.overview-columns {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: var(--g-s-6);
  align-items: start;
}
.left-column, .right-column {
  display: flex;
  flex-direction: column;
  gap: var(--g-s-4);
}
/* Mobile: gestapelt */
@media (max-width: 899px) {
  .overview-columns {
    grid-template-columns: 1fr;
  }
}
```

### 3. `index.ts` — Export ergänzen

```typescript
// Neue Zeile hinzufügen:
export { default as AlertsPreviewCard } from './AlertsPreviewCard.svelte';
```

### 4. E2E-Tests `issue-302-trip-detail-redesign.spec.ts` — AC-4a–4d skippen

Die vier DetailCard-Tests prüfen `detail-card-reports`, `detail-card-alarmregeln`,
`detail-card-route` und `detail-card-datenstand`. Diese TestIDs existieren nach dem
Umbau nicht mehr — das Layout hat keine DetailCards mehr im Übersicht-Tab.

Jeder der vier Tests erhält `test.skip(...)` mit Kommentar:
```typescript
test.skip('AC-4a: Übersicht zeigt DetailCard Reports ...', async () => {
  // Superseded by Issue #409 — TripOverview nutzt jetzt FullProfile + StageList + rechte Spalte.
  // DetailCards (detail-card-reports etc.) existieren im Übersicht-Tab nicht mehr.
});
```

## Expected Behavior

- **Input:** `trip: Trip` mit optionalen Feldern `stages[]`, `alert_rules[]`, `report_config`; optionales `now: Date`
- **Output:**
  - Hero-Sektion (`trip-hero`) mit drei `Stat`-Kacheln: Etappe X/Y, Briefing-Zeit, Start-Countdown oder "Läuft"
  - Zweispaltiger Hauptbereich auf Desktop (>899px): linke Spalte (2fr) mit FullProfile + StageList, rechte Spalte (1fr) mit 4 Preview-Karten
  - Auf Mobile (≤899px): gestapelt — Hero → FullProfile → StageList → 4 Karten
  - `AlertsPreviewCard` zeigt bis zu 5 aktivierte Alert-Rules als Listenzeilen; bei keinen Rules: Empty-State-Text
- **Side effects:**
  - Klick auf FullProfile-Hit-Area oder StageList-Card synchronisiert `selectedStageId` bidirektional (Svelte-State, kein API-Call)
  - Klick auf `right-card-alerts-edit-link` navigiert zu `#alerts` (Tab-Wechsel via URL-Hash)

## Acceptance Criteria

**AC-1:** Given ein Trip ist geöffnet und der Übersicht-Tab ist aktiv / When die Seite gerendert wird / Then sind `data-testid="trip-hero"`, `data-testid="trip-overview-left-column"` und `data-testid="trip-overview-right-column"` alle sichtbar im DOM.

**AC-2:** Given ein Trip hat heute eine aktive Etappe (Etappe 2 von 3) / When `trip-hero-stat-active-stage` gerendert wird / Then zeigt die Kachel den Text "2/3" und kein "undefined" oder "–/3".

**AC-3:** Given ein Trip mit `morning_time='07:00'` und `morning_enabled=true`, `evening_enabled=false` / When `trip-hero-stat-next-briefing` gerendert wird / Then zeigt die Kachel "07:00" als früheste aktivierte Zeit, nicht "–:–".

**AC-4:** Given ein Trip hat `status='active'` / When `trip-hero-stat-days` gerendert wird / Then zeigt die Kachel den Text "Läuft" mit Label "STATUS", nicht "START IN".

**AC-5:** Given der Übersicht-Tab ist auf Desktop (>899px) sichtbar / When die Seite gerendert wird / Then liegen `trip-overview-left-column` und `trip-overview-right-column` nebeneinander im Grid (2fr / 1fr), nicht untereinander.

**AC-6:** Given die rechte Spalte ist gerendert / When die DOM-Reihenfolge geprüft wird / Then folgen die Karten exakt in der Reihenfolge `right-card-briefings` → `right-card-weather` → `right-card-alerts` → `right-card-preview`.

**AC-7:** Given ein Trip ohne aktivierte Alert-Rules (`alert_rules = []` oder alle `enabled: false`) / When `right-card-alerts` gerendert wird / Then ist `data-testid="right-card-alerts-empty"` sichtbar mit Text "Noch keine Alerts konfiguriert", und kein `data-testid="alert-row"` ist im DOM.

**AC-8:** Given ein Trip mit 3 aktivierten Alert-Rules und einer deaktivierten Rule / When `right-card-alerts` gerendert wird / Then sind exakt 3 Elemente mit `data-testid="alert-row"` vorhanden; die deaktivierte Rule wird nicht angezeigt.

**AC-9:** Given `right-card-alerts` ist gerendert (leer oder mit Regeln) / When der Edit-Link angeklickt wird / Then hat der Link `href="#alerts"` mit `data-testid="right-card-alerts-edit-link"` und ist immer sichtbar, unabhängig vom Leer-/Gefüllt-Zustand.

**AC-10:** Given ein User klickt auf eine Stage-Card in der `StageList` / When der Klick verarbeitet wird / Then wechselt die Auswahl-Markierung in `FullProfile` zur entsprechenden Stage (bidirektionale `selectedStageId`-Synchronisation via Svelte-State).

**AC-11:** Given der Viewport ist ≤899px / When die Seite gerendert wird / Then sind linke und rechte Spalte gestapelt (single column), `FullProfile` vor `StageList` vor den 4 rechten Karten.

**AC-12:** Given die `issue-302-trip-detail-redesign.spec.ts` Tests AC-4a–4d / When die Test-Suite läuft / Then sind diese vier Tests mit `test.skip` markiert und enthalten den Kommentar "Superseded by Issue #409".

## Known Limitations

- `Stat.svelte` hat kein natives `data-testid`-Prop — die Hero-TestIDs werden durch umgebende `<div data-testid="...">` Wrapper realisiert.
- Die linke Spalte zeigt `FullProfile` und `StageList` immer zusammen; ein getrenntes "nur Profil"- oder "nur Liste"-Layout ist in dieser Iteration nicht vorgesehen.
- `AlertsPreviewCard` zeigt maximal 5 Regeln. Bei mehr als 5 aktivierten Regeln wird nur die Anzahl implizit durch den Edit-Link adressiert (kein "+N weitere"-Hinweis in dieser Iteration).
- Der `now`-Parameter fließt durch zu `FullProfile`, `StageList` und den Hero-Berechnungen — für Server-Side-Rendering wird `new Date()` als Default verwendet.

## Changelog

- 2026-05-27: Initial spec erstellt (Issue #409 — TripOverview: linke Spalte + Hero-Kacheln + AlertsPreviewCard).
