---
entity_id: issue_494_trip_edit_design
type: module
created: 2026-05-31
updated: 2026-05-31
status: draft
version: "1.0"
tags: [frontend, svelte, ui, design-alignment, trip-edit]
---

<!-- Issue #494 — Trip-Bearbeiten-Seite ans Design angleichen -->

# Issue 494 — Trip-Bearbeiten-Seite: Design-Angleichung

## Approval

- [ ] Approved

## Purpose

Die `/trips/[id]/edit`-Route rendert derzeit `WaypointEditorPage` direkt und
umgeht damit die Tab-Übersicht vollständig. Diese Spec ersetzt das bisherige
Accordion-Layout durch die im Soll-Design (`soll-flow2A-trip-editor-overview.png`)
definierte Tab-Ansicht: Breadcrumb, H1-Tourname, Buttons oben rechts,
horizontale Tabs, Statistik-Karte und Etappen-Kachel-Grid — sodass die Seite
der genehmigten Designvorlage entspricht und das Produkt konsistent wirkt.

## Source

- **File:** `frontend/src/lib/components/edit/TripEditView.svelte` — Hauptkomponente, wird vollständig neu strukturiert
- **File:** `frontend/src/routes/trips/[id]/edit/+page.svelte` — Einstiegspunkt, delegiert auf `TripEditView` statt `WaypointEditorPage`
- **File:** `frontend/e2e/trip-edit.spec.ts` — E2E-Tests, Accordion-Testids werden auf Tab-Testids umgeschrieben
- **File:** `frontend/e2e/issue-407-waypoint-editor-screen.spec.ts` — wird mit `test.skip()` deaktiviert

> **Schicht:** Frontend / User-UI — ausschließlich SvelteKit-Komponenten in
> `frontend/src/`. Kein Go-API- oder Python-Backend-Code betroffen.

## Estimated Scope

- **LoC:** ~280 (TripEditView ~200 neu, +page.svelte ~7, trip-edit.spec.ts ~80 angepasst, issue-407.spec.ts skip-Wrapper ~5)
- **Files:** 4
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Segmented.svelte` (`$lib/components/atoms/Segmented`) | Atom-Komponente | Horizontale Tab-Navigation (Route / Etappen / Wetter / Reports / Alarmregeln) |
| `computeTripStats(trip)` (`$lib/utils/tripStats`) | Utility-Funktion | Liefert `kmTotal`, `ascentM`, `stages.length` für die Statistik-Karte |
| `formatDateRange(trip)` (`$lib/utils/tripHero`) | Utility-Funktion | Liefert Zeitraum-String (z. B. „20.05 — 01.06.2026") für die Statistik-Karte |
| `getReportSchedule(trip)` (`$lib/utils/rightColumn`) | Utility-Funktion | Prüft ob Reports konfiguriert sind; steuert Anzeige des „REPORTS KONFIGURIERT"-Badges |
| `EditRouteSection.svelte` (`$lib/components/edit`) | Sub-Komponente | Tab-Inhalt „Route": Tourname + Etappen-Routen-Editor |
| `EditStagesPanelNew.svelte` (`$lib/components/edit`) | Sub-Komponente | Tab-Inhalt „Etappen": Kachel-Grid der Etappen |
| `WeatherSummaryCard.svelte` (`$lib/components/edit`) | Sub-Komponente | Tab-Inhalt „Wetter": Wetter-Display-Config |
| `EditReportConfigSection.svelte` (`$lib/components/edit`) | Sub-Komponente | Tab-Inhalt „Reports": Report-Konfiguration |
| `AlertRulesEditor` (`$lib/components/organisms`) | Organism-Komponente | Tab-Inhalt „Alarmregeln": Alarm-Regeln-Editor |
| `normalizeAlertMetric` (`$lib/utils/alertMetricLabels`) | Utility-Funktion | Normalisiert Alert-Metriken beim Laden — bestehende Logik unverändert übernehmen |
| `stripSuggested` (`$lib/utils/waypointEditor`) | Utility-Funktion | Entfernt transiente `suggested`-Flags vor dem Speichern |
| `api.put` (`$lib/api`) | API-Client | PUT `/api/trips/:id` beim Speichern — Read-Modify-Write-Pattern (BUG-DATALOSS-Schutz) |
| `goto` (`$app/navigation`) | SvelteKit | Navigation nach Speichern / Abbrechen zu `/trips` |
| `AccordionSection.svelte` (`$lib/components/edit`) | Alt-Komponente | Wird in `TripEditView` NICHT mehr verwendet; Datei bleibt für etwaige andere Konsumenten erhalten |

## Implementation Details

### 1. `+page.svelte` — Einstiegspunkt umverdrahten

```svelte
<!-- frontend/src/routes/trips/[id]/edit/+page.svelte -->
<script lang="ts">
  import TripEditView from '$lib/components/edit/TripEditView.svelte';
  let { data } = $props();
</script>

<TripEditView trip={data.trip} />
```

`WaypointEditorPage` wird nicht mehr direkt eingebunden. `TripEditView` übernimmt
die gesamte Darstellung.

### 2. `TripEditView.svelte` — Kompletter Neubau (Accordion → Tabs)

**State-Initialisierung (exakt aus bisheriger Implementierung übernehmen):**

```typescript
let tripName = $state(trip.name);
let stages: Stage[] = $state(JSON.parse(JSON.stringify(trip.stages ?? [])));
let reportConfig: ReportConfig | undefined = $state(
  trip.report_config ? JSON.parse(JSON.stringify(trip.report_config)) : undefined
);
let alertRules: AlertRule[] = $state(
  Array.isArray(trip.alert_rules)
    ? (JSON.parse(JSON.stringify(trip.alert_rules)) as AlertRule[]).map(r => ({
        ...r,
        metric: normalizeAlertMetric(r.metric) ?? r.metric,
      }))
    : []
);
```

**Save-Logik (exakt aus bisheriger Implementierung übernehmen — KEIN Rewrite):**

```typescript
// Read-Modify-Write — display_config aus geladenem trip unverändert durchreichen
const updated: Trip = {
  ...trip,
  name: tripName,
  stages: stripSuggested(stages),
  report_config: reportConfig,
  alert_rules: alertRules,
};
await api.put(`/api/trips/${trip.id}`, updated);
goto('/trips');
```

**Tab-Definitionen:**

```typescript
type TabId = 'route' | 'etappen' | 'wetter' | 'reports' | 'alarmregeln';
let activeTab: TabId = $state('etappen');

const stats = computeTripStats(trip);
const dateRange = formatDateRange(trip);
const reportSchedule = getReportSchedule(trip);
const stageCount = stats.stages ?? trip.stages?.length ?? 0;
const alertCount = trip.alert_rules?.length ?? 0;
```

**HTML-Struktur (top-level `data-testid="trip-edit-view"`):**

```
<div data-testid="trip-edit-view">

  <!-- Breadcrumb -->
  <nav data-testid="edit-breadcrumb">
    MEINE TOUREN · TRIP BEARBEITEN
  </nav>

  <!-- Header: H1 + Buttons -->
  <div data-testid="edit-header">
    <h1 data-testid="edit-trip-title">{trip.name}</h1>
    <div data-testid="edit-header-actions">
      <button data-testid="edit-cancel-btn">Abbrechen</button>
      <button data-testid="edit-save-btn">Speichern</button>
    </div>
  </div>

  <!-- Horizontale Tabs via Segmented.svelte -->
  <Segmented
    data-testid="edit-tabs"
    tabs={[
      { id: 'route',      label: 'Route' },
      { id: 'etappen',    label: `Etappen ${stageCount}` },
      { id: 'wetter',     label: 'Wetter' },
      { id: 'reports',    label: 'Reports' },
      { id: 'alarmregeln',label: `Alarmregeln ${alertCount}` },
    ]}
    bind:active={activeTab}
  />

  <!-- Statistik-Karte (immer sichtbar, unabhängig vom aktiven Tab) -->
  <div data-testid="edit-stats-card">
    <div data-testid="edit-stats-distance">{stats.kmTotal} km</div>
    <div data-testid="edit-stats-ascent">↑{stats.ascentM} m</div>
    <div data-testid="edit-stats-daterange">{dateRange}</div>
    <div data-testid="edit-stats-days">{stageCount} Tage</div>
    {#if reportSchedule.enabled}
      <span data-testid="edit-stats-reports-badge">REPORTS KONFIGURIERT</span>
    {/if}
  </div>

  <!-- Tab-Inhalte -->
  {#if activeTab === 'route'}
    <EditRouteSection bind:tripName bind:stages mode="edit" />
  {:else if activeTab === 'etappen'}
    <EditStagesPanelNew bind:stages />
  {:else if activeTab === 'wetter'}
    <WeatherSummaryCard displayConfig={trip.display_config} tripId={trip.id} />
  {:else if activeTab === 'reports'}
    <EditReportConfigSection bind:reportConfig mode="edit" />
  {:else if activeTab === 'alarmregeln'}
    <AlertRulesEditor bind:rules={alertRules} />
  {/if}

  <!-- Fehleranzeige -->
  {#if saveError}
    <div data-testid="edit-save-error">{saveError}</div>
  {/if}

</div>
```

**Buttons oben rechts — KEIN Fixed-Footer mehr.** Buttons sitzen im
`edit-header`-Block, rechtsbündig via Flexbox (`justify-between`). Der
bestehende Fixed-Footer (`fixed bottom-0`) entfällt vollständig.

### 3. `trip-edit.spec.ts` — Accordion-Testids → Tab-Testids

Alle Referenzen auf `edit-section-*-header` und Accordion-Interaktionen werden
durch Tab-Interaktionen ersetzt:

- `[data-testid="edit-section-etappen-header"]` → `[data-testid="edit-tabs"]` + Tab-Click
- `[data-testid="edit-section-wetter-header"]` → Tab-Auswahl „Wetter"
- Accordion-„Open/Close"-Assertions → Tab-Visibility-Assertions (aktiver Tab-Inhalt sichtbar, inaktive nicht)

Bestehende Assertions für `edit-save-btn`, `edit-cancel-btn`, `trip-name-input`,
`stage-card-*` und `trip-edit-view` bleiben funktional erhalten.

### 4. `issue-407-waypoint-editor-screen.spec.ts` — test.skip()

Alle Tests in dieser Datei werden mit `test.skip()` versehen, da
`WaypointEditorPage` nicht mehr direkt auf `/trips/[id]/edit` gerendert wird.
Ein erläuternder Kommentar verweist auf das Folge-Issue für die klickbaren
Etappen-Kacheln.

```typescript
// Deaktiviert in #494: WaypointEditorPage ist nicht mehr der Einstieg.
// Etappen-Kacheln → WaypointEditor-Navigation folgt in Folge-Issue.
test.skip('AC-1: Desktop zeigt WaypointEditorPage ...', async ({ page }) => { ... });
```

### Etappen-Kacheln: nicht klickbar in diesem Issue

Die Etappen-Kacheln im Tab „Etappen" werden in `EditStagesPanelNew` dargestellt.
In #494 sind sie **nicht klickbar** — kein Navigation-Handler, kein Cursor-Pointer
auf Kacheln. Die Interaktivität (Klick → WaypointEditor) folgt im Folge-Issue.

### Datenschicht: Read-Modify-Write bleibt erhalten

Die `display_config`-Felder werden über `...trip` in den PUT-Body übernommen,
ohne im UI-State zu erscheinen. Das verhindert Datenverlust gemäß BUG-DATALOSS-GR221
(Issue #102). Diese Logik wird 1:1 aus der bisherigen Implementierung übernommen
und darf nicht verändert werden.

## Acceptance Criteria

- **AC-1:** Given ein User navigiert zu `/trips/[id]/edit` / When die Seite lädt / Then ist `[data-testid="trip-edit-view"]` sichtbar, `[data-testid="waypoint-editor-page"]` ist NICHT im DOM, und der aktive Tab ist „Etappen"

- **AC-2:** Given die Trip-Bearbeiten-Seite ist geladen / When der User die Seite betrachtet / Then sind Breadcrumb „MEINE TOUREN · TRIP BEARBEITEN", H1 mit dem Tournamen, Buttons „Abbrechen" und „Speichern" oben rechts sowie fünf horizontale Tabs (Route, Etappen N, Wetter, Reports, Alarmregeln N) sichtbar — kein Fixed-Footer

- **AC-3:** Given die Statistik-Karte (`[data-testid="edit-stats-card"]`) ist sichtbar / When der User keinen Tab-Wechsel durchführt / Then zeigt die Karte Gesamtstrecke in km, Höhenmeter, Zeitraum und Tage-Anzahl; bei konfiguriertem Report ist `[data-testid="edit-stats-reports-badge"]` sichtbar, bei unkonfiguriertem fehlt er

- **AC-4:** Given der User klickt auf einen Tab (z. B. „Route") / When der Tab aktiv wird / Then ist der entsprechende Tab-Inhalt sichtbar (`EditRouteSection`) und alle anderen Tab-Inhalte sind nicht im sichtbaren Bereich — die Statistik-Karte bleibt bei jedem Tab-Wechsel sichtbar

- **AC-5:** Given der User ändert den Tournamen im Tab „Route" und klickt „Speichern" / When der Save-Handler läuft / Then sendet die App ein PUT auf `/api/trips/:id` mit dem neuen Namen, dem unveränderten `display_config` aus dem geladenen Trip (Read-Modify-Write) und `stages` ohne transiente `suggested`-Flags; danach navigiert die App zu `/trips`

- **AC-6:** Given die E2E-Datei `issue-407-waypoint-editor-screen.spec.ts` / When die Tests laufen / Then sind alle Tests darin mit `test.skip()` markiert und das Kommentar gibt an, welches Folge-Issue die Klick-Navigation nachliefert

- **AC-7:** Given `trip-edit.spec.ts` läuft nach dem Umbau / When alle Tests laufen / Then schlagen keine Tests wegen fehlender Accordion-Testids (`edit-section-*-header`) fehl — alle Assertions nutzen Tab-Testids

## Expected Behavior

- **Input:** `trip: Trip`-Objekt (via `+page.server.ts`, enthält `stages`, `alert_rules`, `report_config`, `display_config`)
- **Output:** Gerenderte Seite mit Breadcrumb, H1, Buttons oben rechts, Statistik-Karte, Tab-Navigation; nach Speichern Redirect zu `/trips`
- **Side effects:** PUT `/api/trips/:id` beim Speichern; `goto('/trips')` nach Speichern oder Abbrechen; keine Änderung an `display_config` (Read-Modify-Write)

## Known Limitations

- Etappen-Kacheln im Tab „Etappen" sind in diesem Issue nicht klickbar; die Navigation zu `WaypointEditorPage` folgt im Folge-Issue
- `AccordionSection.svelte` bleibt im Dateisystem erhalten (andere Konsumenten denkbar); in `TripEditView` wird sie nicht mehr importiert
- `Segmented.svelte` existiert in zwei Pfaden (`atoms/` und `ui/segmented/`); der Implementierer wählt `$lib/components/atoms/Segmented` gemäß Design-System-Konvention

## Changelog

- 2026-05-31: Initial spec erstellt — Issue #494
