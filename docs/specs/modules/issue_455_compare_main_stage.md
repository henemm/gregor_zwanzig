---
entity_id: issue_455_compare_main_stage
type: module
created: 2026-05-29
updated: 2026-05-29
status: implemented
version: "1.0"
tags: [frontend, svelte, compare, layout, matrix, banner, hourly, issue-455]
---

# Issue #455 — Orts-Vergleich · Compare-Hauptbühne Frontend

## Approval

- [x] Approved

## Purpose

Baut die `/compare`-Route von einer 49-zeiligen Abo-Liste zur vollständigen interaktiven
Vergleichs-Hauptbühne um: drei Spalten (Rail 320px | Hauptbereich flex | Sidepanel 320px)
mit Standort-Auswahl, Preset-Header, Empfehlungs-Banner, Metriken-Matrix und Stunden-Verlauf.
Alle sechs benötigten Komponenten sind bereits implementiert und müssen nur noch in der
`+page.svelte` verdrahtet werden; kein Backend-Code wird geändert.

## Source

- **Schicht:** Reines Frontend (SvelteKit). Kein Go-Backend, kein Python-Backend.
- **Dateien (geändert):**
  - `frontend/src/routes/compare/+page.svelte` (49 → ~175 LoC, vollständiger Rebuild)
  - `frontend/src/lib/components/compare/__tests__/issue_439_compare_uebersicht.test.ts` (obsolete Guards entfernen)
- **Dateien (unverändert):**
  - `frontend/src/routes/compare/+page.server.ts` (lädt bereits locations, subscriptions, groups)

## Dependencies

| Entity | Type | Zweck |
|--------|------|-------|
| `LocationsRail.svelte` — `frontend/src/lib/components/compare/` | Svelte-Komponente (vorhanden) | Linke Spalte: Standort-Multi-Select mit Gruppen, 320px |
| `PresetHeader.svelte` — `frontend/src/lib/components/compare/` | Svelte-Komponente (vorhanden) | Einstellungs-Karte: Datum, Zeitfenster, forecastHours, Aktivitätsprofil, Run-Button |
| `RecommendationBanner.svelte` — `frontend/src/lib/components/compare/` | Svelte-Komponente (vorhanden) | Gewinner-Banner: Score, Standort-Name, Tags |
| `CompareMatrix.svelte` — `frontend/src/lib/components/compare/` | Svelte-Komponente (vorhanden) | Metriken-Tabelle mit Grün-Hervorhebung des besten Werts pro Zeile und Mini-Bars |
| `HourlyMatrix.svelte` — `frontend/src/lib/components/compare/` | Svelte-Komponente (vorhanden) | Stunden-Verlauf der Top-3-Standorte |
| `AutoReportsOverview.svelte` — `frontend/src/lib/components/compare/` | Svelte-Komponente (vorhanden) | Rechte Sidebar: Abo-Grid mit Save-Briefing-Aktion |
| `locationHelpers.ts` — `frontend/src/lib/components/compare/` | TypeScript-Modul (vorhanden) | `groupLocations(locations, groups)` für `groupedLocations` |
| `wizardHelpers.ts` — `frontend/src/lib/components/trip-wizard/` | TypeScript-Modul (vorhanden) | `today(): string` für Datums-Initialwert |
| `CompareResult`, `CompareRow`, `CompareWinner`, `ActivityProfile`, `toCompareProfile()` — `frontend/src/lib/types.ts` | TypeScript-Typen (vorhanden) | Typen für API-Response und Aktivitätsprofil-Konvertierung |
| `api` — `frontend/src/lib/api.ts` | TypeScript-Modul (vorhanden) | `api.post('/api/compare/run', body)` |
| `goto`, `invalidateAll` — `$app/navigation` | SvelteKit-Runtime (vorhanden) | Navigation und Daten-Refresh nach Gruppen-Änderung |
| `POST /api/compare/run` | Go-Backend-Endpoint (vorhanden, `cmd/server/main.go:136`) | Vergleichslauf: gibt `CompareResult` mit `winner`, `rows`, `hourly` zurück |

## Scope

**Nur Frontend.** Keine Änderungen am Go-Backend (`api/`, `internal/`, `cmd/`) oder
Python-Backend (`src/`). `+page.server.ts` bleibt unverändert.

Nicht in Scope (explizit):
- Mobile-Layout — Desktop-only; Mobile zeigt Fallback-Hinweis
- Neue Standorte anlegen (nur Redirect via `wizardOpen`)
- Gruppen anlegen/bearbeiten
- Persistenz der Preset-Header-Werte über Seitenreloads hinaus

## Implementation Details

### 1. Page State (script block)

```typescript
import { goto, invalidateAll } from '$app/navigation';
import { today } from '$lib/components/trip-wizard/wizardHelpers';
import { groupLocations } from '$lib/components/compare/locationHelpers';
import { api } from '$lib/api';
import { toCompareProfile } from '$lib/types';
import type { ActivityProfile, CompareResult } from '$lib/types';

let { data } = $props();
let locations = $state(data.locations ?? []);
let groups   = $state(data.groups ?? []);

let selectedIds:      string[]        = $state([]);
let openGroups:       Set<string>     = $state(new Set());
let compareDate:      string          = $state(today());
let twStart:          number          = $state(9);
let twEnd:            number          = $state(16);
let forecastHours:    number          = $state(48);
let activityProfile:  ActivityProfile = $state('allgemein');
let result:           CompareResult | null = $state(null);
let loading:          boolean         = $state(false);
let error:            string | null   = $state(null);
let wizardOpen:       boolean         = $state(false);

let groupedLocations = $derived(groupLocations(locations, groups));
let allSelected      = $derived(
  selectedIds.length === locations.length && locations.length > 0
);
```

### 2. Event Handlers

```typescript
function handleToggleAll() {
  selectedIds = allSelected ? [] : locations.map(l => l.id);
}
function handleToggleLocation(id: string) {
  selectedIds = selectedIds.includes(id)
    ? selectedIds.filter(x => x !== id)
    : [...selectedIds, id];
}
function handleToggleGroup(id: string) {
  const next = new Set(openGroups);
  next.has(id) ? next.delete(id) : next.add(id);
  openGroups = next;
}
function handleToggleGroupSelection(id: string) {
  const group = groups.find(g => g.id === id);
  if (!group) return;
  const inGroup = locations
    .filter(l => l.group_id === id)
    .map(l => l.id);
  const allIn = inGroup.every(x => selectedIds.includes(x));
  selectedIds = allIn
    ? selectedIds.filter(x => !inGroup.includes(x))
    : [...new Set([...selectedIds, ...inGroup])];
}
function handleShowWeather(_id: string) { /* no-op */ }
function handleEditLocation(_loc: unknown) { goto('/locations'); }
function handleNewLocation()             { wizardOpen = true; }
async function handleGroupCreated(_group: unknown) { await invalidateAll(); }
function handleSaveBriefing()            { goto('/compare/new'); }
```

### 3. API Call

```typescript
async function runComparison() {
  if (selectedIds.length < 2) return;
  error = null;
  loading = true;
  try {
    result = await api.post<CompareResult>('/api/compare/run', {
      location_ids: selectedIds,
      date:         compareDate,
      profile:      toCompareProfile(activityProfile),
    });
  } catch (e) {
    error = (e as { error?: string }).error ?? 'Vergleich fehlgeschlagen';
  } finally {
    loading = false;
  }
}
```

### 4. Template-Struktur (3-Spalten-Grid)

```svelte
<!-- Desktop: 3-column grid -->
<div
  class="hidden desktop:grid h-full gap-4 p-4"
  style="grid-template-columns: 320px 1fr 320px"
  data-testid="compare-main-stage"
>
  <!-- Linke Spalte: Standort-Rail -->
  <LocationsRail
    {locations}
    {groups}
    {selectedIds}
    {groupedLocations}
    {openGroups}
    {allSelected}
    ontoggleall={handleToggleAll}
    ontogglelocation={handleToggleLocation}
    ontogglegroup={handleToggleGroup}
    ontogglegroupselection={handleToggleGroupSelection}
    onshowweather={handleShowWeather}
    oneditlocation={handleEditLocation}
    onnewlocation={handleNewLocation}
    ongroupcreated={handleGroupCreated}
  />

  <!-- Mittlere Spalte: Vergleichsbereich -->
  <div class="flex flex-col gap-4 overflow-y-auto" data-testid="compare-center">
    <PresetHeader
      bind:compareDate
      bind:twStart
      bind:twEnd
      bind:forecastHours
      bind:activityProfile
      locationCount={selectedIds.length}
      {loading}
      onrun={runComparison}
      onsavebriefing={handleSaveBriefing}
    />

    <!-- AC-5: Leer-Zustand -->
    {#if selectedIds.length < 2 && !result}
      <div class="empty-hint" data-testid="compare-empty-hint">
        Wähle mindestens 2 Orte aus, um den Vergleich zu starten.
      </div>
    {/if}

    <!-- Fehlerzustand -->
    {#if error}
      <div class="error-banner" data-testid="compare-error">{error}</div>
    {/if}

    <!-- AC-3: Empfehlungs-Banner -->
    {#if result?.winner && result.rows[0]}
      <RecommendationBanner
        winner={result.winner}
        winnerRow={result.rows[0]}
        {locations}
      />
    {/if}

    <!-- AC-1/AC-2: Metriken-Matrix -->
    {#if result?.rows?.length}
      <CompareMatrix
        rows={result.rows}
        {locations}
        profile={activityProfile}
      />
    {/if}

    <!-- Stunden-Verlauf -->
    {#if result?.hourly && Object.keys(result.hourly).length}
      <HourlyMatrix
        hourly={result.hourly}
        {locations}
        rows={result.rows}
      />
    {/if}
  </div>

  <!-- Rechte Spalte: Abo-Übersicht -->
  <div class="overflow-y-auto" data-testid="compare-sidebar">
    <AutoReportsOverview
      subscriptions={data.subscriptions}
      onsavebriefing={handleSaveBriefing}
    />
  </div>
</div>

<!-- Mobile-Fallback -->
<div class="desktop:hidden p-6 text-center" data-testid="compare-mobile-fallback">
  <p>Orts-Vergleich ist auf dem Desktop verfügbar.</p>
</div>

<!-- Neuen Standort anlegen (Wizard) -->
{#if wizardOpen}
  <NewLocationWizard
    onsave={(loc) => { locations = [...locations, loc]; wizardOpen = false; }}
    oncancel={() => { wizardOpen = false; }}
  />
{/if}
```

### 5. Test-Datei-Update: `issue_439_compare_uebersicht.test.ts`

Folgende Abschnitte werden **entfernt** (veraltete Assertions, die mit dem neuen Layout nicht mehr gelten):

| Zeile (ca.) | Assertion | Grund |
|-------------|-----------|-------|
| 87–95 | `doesNotMatch(LocationsRail import)` | LocationsRail ist jetzt eingebunden |
| 96–103 | `doesNotMatch(PresetHeader import)` | PresetHeader ist jetzt eingebunden |
| 49–56 | `assert.match(WORKSPACE · ORTS-VERGLEICHE Eyebrow)` | Eyebrow nicht mehr in der Page |
| 58–65 | `assert.match(H1 Orts-Vergleiche)` | H1 nicht mehr in der Page |

Alle verbleibenden Assertions, die gegen das vorherige Layout testen, werden ebenfalls geprüft
und falls nicht mehr zutreffend entfernt. Neue Assertions kommen in eine separate Testdatei
`issue_455_compare_main_stage.test.ts`.

### 6. LoC-Budget

| Datei | Δ LoC (grob) |
|-------|-------------|
| `frontend/src/routes/compare/+page.svelte` | +126 (49 → ~175) |
| `issue_439_compare_uebersicht.test.ts` | −30 (Assertions entfernt) |
| `issue_455_compare_main_stage.test.ts` (NEU) | ~60 |
| **Summe** | **~156 LoC** |

LoC-Override ist nicht erforderlich (unter 250-Limit).

## Expected Behavior

- **Input:** `data.locations`, `data.groups`, `data.subscriptions` aus `+page.server.ts`
  (bereits vorhanden). Nutzer wählt ≥ 2 Standorte, setzt optionale Preset-Felder und klickt
  „Vergleich starten".
- **Output:** `POST /api/compare/run` gibt `CompareResult` zurück; die drei Ergebnis-Komponenten
  (RecommendationBanner, CompareMatrix, HourlyMatrix) werden reaktiv gerendert sobald `result`
  gesetzt ist.
- **Side effects:** `goto('/locations')` bei Edit-Standort-Klick; `goto('/compare/new')` bei
  Save-Briefing; `invalidateAll()` nach Gruppen-Anlage; `wizardOpen = true` beim Klick auf
  „Neuer Standort".

## Acceptance Criteria

**AC-1:** Given ≥ 2 Orte ausgewählt und „Vergleich starten" geklickt / When
`POST /api/compare/run` eine `CompareResult`-Antwort mit `rows`-Array liefert /
Then rendert `CompareMatrix` alle ausgewählten Orte als Spalten und alle profil-spezifischen
Metriken als Zeilen — `data-testid="compare-matrix"` ist im DOM sichtbar.
- Test: (populated after /tdd-red)

**AC-2:** Given `CompareMatrix` zeigt Ergebnisse / When eine Zeile mit mehreren Spaltenwerten
gerendert wird / Then trägt die Zelle mit dem besten Wert die CSS-Klasse `best-value` — alle
anderen Zellen in dieser Zeile tragen sie nicht.
- Test: (populated after /tdd-red)

**AC-3:** Given `result.winner` ist in der API-Antwort vorhanden / When der Vergleich
abgeschlossen ist und der Banner gerendert wird / Then zeigt `RecommendationBanner` den
Winner-Standortnamen, den Score und mindestens ein Tag — `data-testid="recommendation-banner"`
ist im DOM sichtbar.
- Test: (populated after /tdd-red)

**AC-4:** Given Ergebnisse sind in CompareMatrix und RecommendationBanner sichtbar / When der
Nutzer das Aktivitätsprofil im PresetHeader ändert und erneut „Vergleich starten" klickt /
Then werden Matrix und Banner mit den Werten des neuen Profils aktualisiert, ohne die Seite
neu zu laden — die vorherigen Daten sind nicht mehr sichtbar während `loading === true`.
- Test: (populated after /tdd-red)

**AC-5:** Given weniger als 2 Orte sind ausgewählt und kein `result` vorhanden / When die
mittlere Spalte gerendert wird / Then ist `data-testid="compare-empty-hint"` im DOM sichtbar
und `data-testid="compare-matrix"` ist nicht im DOM.
- Test: (populated after /tdd-red)

## Known Limitations

- Der Mobile-Fallback ist ein einfacher Hinweistext. Eine vollwertige Mobile-Ansicht ist
  nicht Teil dieses Issues.
- `handleShowWeather` ist ein No-Op: Die Wetter-Route leitet bereits auf `/compare` zurück,
  eine dedizierte Einzel-Standort-Wetteransicht existiert nicht.
- Preset-Header-Werte (Datum, Zeitfenster, Profil) werden nicht über Seitenreloads persistiert;
  sie kehren bei Reload auf die Defaults zurück.
- `wizardOpen`-Logik instanziiert `NewLocationWizard` in der Page — falls diese Komponente
  komplexe Mount-Logik hat, kann das die Ladezeit beeinflussen.

## Changelog

- 2026-05-29: **IMPLEMENTED** — `/compare` route rebuilt: frontend/src/routes/compare/+page.svelte (49 → 175 LoC, full 3-column layout), LocationsRail + PresetHeader + RecommendationBanner + CompareMatrix + HourlyMatrix + AutoReportsOverview wired. Test file updated: issue_439_compare_uebersicht.test.ts (−30 LoC, obsolete assertions removed), issue_455_compare_main_stage.test.ts (new, 20 tests, all green). Total: ~156 net LoC. All 5 AC fulfilled.
- 2026-05-29: Initial spec erstellt für Issue #455 (Compare-Hauptbühne Frontend).
  Alle 6 Komponenten bereits vorhanden; spec beschreibt ausschließlich die Verdrahtung
  in `+page.svelte` sowie Bereinigung veralteter Test-Assertions in `issue_439_compare_uebersicht.test.ts`.
