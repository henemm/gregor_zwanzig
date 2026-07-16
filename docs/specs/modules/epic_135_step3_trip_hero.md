---
entity_id: epic_135_step3_trip_hero
type: module
created: 2026-05-12
updated: 2026-05-12
status: approved
version: "1.0"
parent_spec: epic_135_trip_detail
related: epic_135_step2_trip_detail_actions
issue: 154
tags: [frontend, sveltekit, svelte5, trip-detail, epic-135, issue-154]
---

# Epic 135 — Sub-Spec #154: Trip-Detail Hero (Overview-Tab)

## Approval

- [x] Approved (2026-05-12)

## Purpose

Ersetzt den Placeholder „Inhalt folgt mit Issue #154" im Overview-Tab der Trip-Detail-Seite durch die `TripHero`-Komponente: eine strukturierte Bühne mit Trip-Name (H1), Zeitraum-Subtext und drei Status-Kacheln (Aktive Etappe, Nächstes Briefing, Tage bis Start/Verlauf). Der Hero sitzt im Tab-Panel unterhalb der Tab-Navigation aus Step 1 und des Headers aus Step 2 — er reagiert reaktiv auf Status-Änderungen (z.B. Pausieren), die in Step 2 über `PATCH /api/trips/{id}/state` ausgelöst werden, weil `trip` bereits als `$state`-Variable in `+page.svelte` verwaltet wird.

## Source

- **NEU:** `frontend/src/lib/utils/tripHero.ts` — 4 Pure-Functions
- **NEU:** `frontend/src/lib/utils/tripHero.test.ts` — Unit-Tests (mind. 15)
- **NEU:** `frontend/src/lib/components/trip-detail/TripHero.svelte` — Hero-Komponente
- **NEU:** `frontend/e2e/trip-detail-hero.spec.ts` — Playwright E2E (mind. 8)
- **EDIT:** `frontend/src/lib/components/trip-detail/TripTabs.svelte` — `trip`-Prop + Hero im Overview-Panel
- **EDIT:** `frontend/src/routes/trips/[id]/+page.svelte` — `{trip}` an TripTabs durchreichen
- **EDIT:** `frontend/src/lib/components/trip-detail/index.ts` — Barrel-Export TripHero
- **Identifier:** `getActiveStageDisplay`, `getNextBriefing`, `getDaysLabel`, `formatDateRange`, `TripHero`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/utils/tripStatus.ts` (`deriveTripStatus`, `TripStatus`) | bestehend (Step 2) | Liefert `'planned' \| 'active' \| 'paused' \| 'archived'` für alle Status-abhängigen Kachel-Texte — **erweitert durch `docs/specs/modules/fix_1271_status_zeitformat.md` (2026-07-16) um `draft`/`finished` (6 Zustände)** |
| `frontend/src/lib/types.ts` (`Trip`) | bestehend (EDIT in Step 2) | Interface mit `name`, `stages`, `report_config`, `paused_at?`, `archived_at?` |
| `frontend/src/lib/components/ui/eyebrow/` | bestehend | Eyebrow-Label-Pattern für Stat-Kachel-Beschriftungen |
| `frontend/src/lib/components/ui/g-card/` | bestehend | Card-Container für Stat-Kacheln (optionale Nutzung für Kachel-Wrapping) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | bestehend (EDIT) | Erhält neues `trip?: Trip`-Prop; Overview-Panel-Placeholder wird durch `<TripHero {trip} />` ersetzt |
| `frontend/src/routes/trips/[id]/+page.svelte` | bestehend (EDIT) | Reicht `{trip}` an `<TripTabs>` weiter; `trip` ist bereits `$state` aus Step 2 |
| `frontend/src/lib/components/trip-detail/index.ts` | bestehend (EDIT) | Barrel: `TripHero` exportieren |
| `frontend/e2e/trip-detail-actions.spec.ts` | bestehend (Referenz) | Playwright-Pattern für Route `/trips/[id]` + Auth via `playwright/.auth/admin.json` |
| `global.setup.ts` (`e2e-cockpit-test`) | bestehend | E2E-Testdaten-Trip für alle trip-detail-Specs |
| `frontend/src/routes/_cockpit/ActiveTripCard.svelte` | bestehend (Referenz) | Stil-Vorbild für Hero: H1 + Eyebrow + Stat-Kacheln; ähnliche Stage-Anzeige im Cockpit |
| `frontend/src/routes/+page.svelte` (Z. 25–32) | bestehend (Referenz) | Cockpit-Logik für `activeTrip`, `todayStage`, `dayIndex` — Pattern für Stage-Datums-Berechnung |

## Implementation Details

### §1 Pure-Functions `frontend/src/lib/utils/tripHero.ts`

Alle vier Funktionen sind pure (kein Side-Effect, kein I/O), vollständig unit-testbar.

```typescript
import type { Trip } from '$lib/types';
import { deriveTripStatus } from './tripStatus';

export function getActiveStageDisplay(trip: Trip, now: Date): string {
  // Bestimmt Status via deriveTripStatus(trip, now)
  // 'planned': Tage bis ersten Stage-Datum berechnen
  //   diff = 0  → "Trip startet heute"
  //   diff = 1  → "Trip startet morgen"
  //   diff > 1  → "Trip startet in X Tagen"
  // 'active': stages.findIndex(s => s.date === today) für heutige Stage
  //   Index gefunden → "Tag {index+1}/{stages.length} · {stage.name}"
  //   Kein heutiger Stage → "Trip läuft"
  // 'paused': gibt genau "Pausiert" zurück
  // 'archived': Tage seit letztem Stage-Datum berechnen
  //   → "Beendet vor X Tagen" (X >= 1); "Beendet heute" bei diff=0
}

export function getNextBriefing(trip: Trip, now: Date): string {
  // !report_config || report_config.enabled === false → "Briefings deaktiviert"
  // Sonst: HH:MM-String aus morning_time/evening_time parsen
  // Vergleich nur auf HH:MM-Ebene (lokale Zeit, kein Timezone-Overhead):
  //   if now < morning_time heute → "heute, HH:MM" (morning)
  //   elif now < evening_time heute → "heute, HH:MM" (evening)
  //   else → "morgen, HH:MM" (morgiges morning_time)
  // Kein morning_time gesetzt → nur evening auswerten; kein evening → "Briefings deaktiviert"
}

export function getDaysLabel(trip: Trip, now: Date): string {
  // deriveTripStatus → 4 Zweige:
  // 'planned': diff zu erstem Stage-Datum
  //   diff = 0 → "heute"
  //   diff = 1 → "morgen"
  //   diff > 1 → "in X Tagen"
  //   Keine Stages → "Trip noch nicht geplant"
  // 'active': dayIndex = stages.findIndex(s => s.date === today) + 1
  //   → "läuft seit Tag X"
  //   Kein heutiger Stage gefunden → "Tag 1" als Fallback
  // 'archived': diff seit letztem Stage-Datum → "beendet vor X Tagen"
  // 'paused': diff seit paused_at → "pausiert seit X Tagen" (X >= 1); "pausiert seit heute" bei diff=0
}

export function formatDateRange(trip: Trip): string {
  // stages.length === 0 oder kein gültiges Datum → ""
  // stages nach date sortieren (aufsteigend)
  // first = stages[0].date, last = stages[stages.length-1].date als Date-Objekte
  // Wenn first === last → "D. MonatName YYYY" (einziger Tag)
  // Wenn gleicher Monat UND gleicher Jahr: "D.–D. MonatName YYYY"
  //   Beispiel: "11.–14. Mai 2026"
  // Wenn verschiedene Monate, gleicher Jahr: "D. MonatName – D. MonatName YYYY"
  //   Beispiel: "30. Mai – 3. Juni 2026"
  // Wenn verschiedene Jahre: "D. MonatName YYYY – D. MonatName YYYY"
  //   Beispiel: "30. Dezember 2025 – 3. Januar 2026"
  // Monatsnamen: deutsch, ausgeschrieben (Januar, Februar, März, April, Mai, Juni,
  //   Juli, August, September, Oktober, November, Dezember)
  // KEIN toLocaleString — explizite Monatsnamen-Map für deterministische Tests
}
```

**Hilfsfunktion (privat, nicht exportiert):**

```typescript
function daysBetween(a: Date, b: Date): number {
  // floor((b - a) / 86400000), Zeit-normalisiert (Mitternacht)
}
```

**Datum-Normalisierung:** Tages-Granularität durch `new Date(d.toDateString())` oder `new Date(d.getFullYear(), d.getMonth(), d.getDate())`. Kein UTC-Offset-Problem, da reine Tag-Vergleiche.

### §2 Komponente `frontend/src/lib/components/trip-detail/TripHero.svelte`

**Prop-Signatur:**

```typescript
interface Props {
  trip: Trip;
  now?: Date; // default: new Date() — injizierbar für Tests
}
let { trip, now = new Date() }: Props = $props();
```

**Template-Struktur:**

```svelte
<div data-testid="trip-hero">
  <h1 data-testid="trip-hero-title">{trip.name}</h1>

  {#if dateRange}
    <p data-testid="trip-hero-date-range">{dateRange}</p>
  {/if}

  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
    {@render statTile('Aktive Etappe', activeStageText, 'trip-hero-stat-active-stage')}
    {@render statTile('Nächstes Briefing', nextBriefingText, 'trip-hero-stat-next-briefing')}
    {@render statTile('Tage bis Start', daysText, 'trip-hero-stat-days')}
  </div>
</div>

{#snippet statTile(label: string, value: string, testid: string)}
  <div data-testid={testid}>
    <!-- Eyebrow-Pattern: kleines Label oben, Wert groß darunter -->
    <span class="eyebrow">{label}</span>
    <span class="stat-value">{value}</span>
  </div>
{/snippet}
```

**Derived-Variablen:**

```typescript
const dateRange   = $derived(formatDateRange(trip));
const activeStageText = $derived(getActiveStageDisplay(trip, now));
const nextBriefingText = $derived(getNextBriefing(trip, now));
const daysText    = $derived(getDaysLabel(trip, now));
```

Alle Werte sind `$derived` — bei `trip`-Mutation (z.B. nach `PATCH /state` in Step 2) re-rendert der Hero automatisch ohne `$effect`.

**Eyebrow-Styling:** Nutzt vorhandenes CSS-Pattern aus `frontend/src/lib/components/ui/eyebrow/` (Klasse `eyebrow`). Kein Import der Komponente als Tag nötig — CSS-Klasse direkt anwenden für minimalen Overhead.

**Named-Function-Pattern (Safari-Kompatibilität):** Keine Inline-Arrows in Event-Handlern. In dieser Komponente gibt es keine interaktiven Buttons, daher kein Risiko — gilt aber für spätere Erweiterungen.

### §3 TripTabs-Edit `frontend/src/lib/components/trip-detail/TripTabs.svelte`

Neues optionales Prop:

```typescript
interface Props {
  initialTab?: string;
  badges?: Record<string, number>;
  trip?: Trip; // NEU
}
let { initialTab = 'overview', badges = {}, trip }: Props = $props();
```

Im Overview-Panel (Tab-Content für `value="overview"`) ersetzt:

```svelte
<!-- ALT: -->
<p>Inhalt folgt mit Issue #154 (Hero)</p>

<!-- NEU: -->
{#if trip}
  <TripHero {trip} />
{:else}
  <p class="text-muted-foreground">Lade Trip-Daten…</p>
{/if}
```

Import oben ergänzen: `import { TripHero } from '$lib/components/trip-detail';`

### §4 Route-Edit `frontend/src/routes/trips/[id]/+page.svelte`

`<TripTabs>` erhält das `trip`-Prop:

```svelte
<!-- ALT: -->
<TripTabs {initialTab} badges={{}} />

<!-- NEU: -->
<TripTabs {initialTab} badges={{}} {trip} />
```

`trip` ist bereits als `$state(data.trip)` aus Step 2 vorhanden — keine weitere Änderung nötig.

### §5 Barrel-Edit `frontend/src/lib/components/trip-detail/index.ts`

Zeile ergänzen:

```typescript
export { default as TripHero } from './TripHero.svelte';
```

### §6 TestID-Inventar

| TestID | Element | Zweck |
|--------|---------|-------|
| `trip-hero` | `<div>` Wrapper | Hero-Container; Existenz-Check in allen E2E-Tests |
| `trip-hero-title` | `<h1>` | Trip-Name |
| `trip-hero-date-range` | `<p>` | Zeitraum-Subtext; nur gerendert wenn `formatDateRange` nicht leer |
| `trip-hero-stat-active-stage` | `<div>` Kachel | Eyebrow „Aktive Etappe" + Status-abhängiger Wert |
| `trip-hero-stat-next-briefing` | `<div>` Kachel | Eyebrow „Nächstes Briefing" + Briefing-Zeitpunkt |
| `trip-hero-stat-days` | `<div>` Kachel | Eyebrow „Tage bis Start" + relativer Zeitwert |

### §7 Datei-Liste

| Art | Datei | Zweck | LoC |
|-----|-------|-------|-----|
| NEU | `frontend/src/lib/utils/tripHero.ts` | 4 Pure-Functions + privates `daysBetween` | ~90 |
| NEU | `frontend/src/lib/utils/tripHero.test.ts` | Unit-Tests (mind. 15) für alle Funktionen | ~150 |
| NEU | `frontend/src/lib/components/trip-detail/TripHero.svelte` | Hero-Komponente mit Snippet | ~80 |
| NEU | `frontend/e2e/trip-detail-hero.spec.ts` | Playwright E2E (mind. 8 Tests) | ~100 |
| EDIT | `frontend/src/lib/components/trip-detail/TripTabs.svelte` | `trip`-Prop + Hero im Overview-Panel | +10 |
| EDIT | `frontend/src/routes/trips/[id]/+page.svelte` | `{trip}` an TripTabs weiterreichen | +3 |
| EDIT | `frontend/src/lib/components/trip-detail/index.ts` | Barrel-Export TripHero | +1 |
| **Summe** | | | **~434 LoC** |

**LoC-Override erforderlich vor Phase 6:** `workflow.py set-field loc_limit_override 450 --name epic_135_step3_trip_hero`

## Expected Behavior

- **Input:** `Trip`-Objekt mit `name` (string), `stages[]` (mit `date`-Feldern), optionalem `report_config` (mit `morning_time`, `evening_time`, `enabled`), optionalem `paused_at?` / `archived_at?` (ISO-8601-String); optional `now: Date` (default: aktuelles Datum/Uhrzeit).
- **Output:**
  - `formatDateRange(trip)` liefert einen deutschen Zeitraum-String nach PO-Konventionen oder `""` bei fehlenden/leeren Stages.
  - `getActiveStageDisplay(trip, now)` liefert einen Status-abhängigen deutschen String für die Kachel „Aktive Etappe".
  - `getNextBriefing(trip, now)` liefert „Briefings deaktiviert" oder einen „heute/morgen, HH:MM"-String.
  - `getDaysLabel(trip, now)` liefert einen relativen Zeit-String für die Kachel „Tage bis Start".
  - `TripHero` rendert H1, optionalen Zeitraum-Absatz und 3 Stat-Kacheln mit den berechneten Werten.
  - Bei `trip.stages = []` rendert der Hero den Titel, kein `trip-hero-date-range`-Element und sinnvolle Default-Texte in den Kacheln.
- **Side effects:**
  - Keine. Alle Berechnungen sind pure. Die Reaktivität auf `trip`-Mutationen erfolgt über Svelte 5 `$derived` ohne expliziten Side-Effect.
  - `TripTabs.svelte` rendert bei fehlendem `trip`-Prop einen Lade-Platzhalter statt des Hero — kein Fehler, kein Crash.

## Acceptance Criteria

- **AC-1:** Given eine gerenderte Trip-Detail-Seite mit gültigem Trip / When das Overview-Tab aktiv ist / Then sind `data-testid="trip-hero"`, `data-testid="trip-hero-title"`, `data-testid="trip-hero-date-range"` und alle drei Kacheln (`trip-hero-stat-active-stage`, `trip-hero-stat-next-briefing`, `trip-hero-stat-days`) in genau dieser DOM-Reihenfolge sichtbar.
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Trip mit Status `planned` und erstem Stage-Datum in 3 Tagen / When `getActiveStageDisplay(trip, now)` aufgerufen wird / Then enthält der Rückgabestring „startet in 3 Tagen".
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein Trip mit Status `active`, heute entspricht Stage 2 von 5 mit Name „Vizzavona" / When `getActiveStageDisplay(trip, now)` aufgerufen wird / Then gibt die Funktion genau `"Tag 2/5 · Vizzavona"` zurück.
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein Trip mit gesetztem `paused_at` (Status `paused`) / When `getActiveStageDisplay(trip, now)` aufgerufen wird / Then gibt die Funktion genau `"Pausiert"` zurück.
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein Trip mit Status `archived` und letztem Stage-Datum vor 3 Tagen / When `getActiveStageDisplay(trip, now)` aufgerufen wird / Then enthält der Rückgabestring „Beendet vor 3 Tagen".
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein Trip ohne `report_config` / When `getNextBriefing(trip, now)` aufgerufen wird / Then gibt die Funktion genau `"Briefings deaktiviert"` zurück.
  - Test: (populated after /tdd-red)

- **AC-7:** Given ein Trip mit `report_config.morning_time = "07:00:00"` und `enabled = true`, `now = 05:30` / When `getNextBriefing(trip, now)` aufgerufen wird / Then enthält der Rückgabestring `"heute, 07:00"`.
  - Test: (populated after /tdd-red)

- **AC-8:** Given ein Trip mit `morning_time = "07:00:00"` und `evening_time = "18:00:00"`, `now = 19:00` (nach evening) / When `getNextBriefing(trip, now)` aufgerufen wird / Then enthält der Rückgabestring `"morgen, 07:00"`.
  - Test: (populated after /tdd-red)

- **AC-9:** Given ein Trip mit Status `planned` und erstem Stage-Datum in 3 Tagen / When `getDaysLabel(trip, now)` aufgerufen wird / Then gibt die Funktion `"in 3 Tagen"` zurück. Edge: 1 Tag Differenz → `"morgen"`, 0 Tage Differenz → `"heute"`.
  - Test: (populated after /tdd-red)

- **AC-10:** Given ein Trip mit Status `active`, `now` entspricht Tag 2 der Stages / When `getDaysLabel(trip, now)` aufgerufen wird / Then gibt die Funktion `"läuft seit Tag 2"` zurück.
  - Test: (populated after /tdd-red)

- **AC-11:** Given ein Trip mit Stages vom 11. Mai 2026 bis 14. Mai 2026 (gleicher Monat) / When `formatDateRange(trip)` aufgerufen wird / Then gibt die Funktion genau `"11.–14. Mai 2026"` zurück.
  - Test: (populated after /tdd-red)

- **AC-12:** Given ein Trip mit erstem Stage 30. Mai 2026 und letztem Stage 3. Juni 2026 (Monatswechsel) / When `formatDateRange(trip)` aufgerufen wird / Then gibt die Funktion genau `"30. Mai – 3. Juni 2026"` zurück.
  - Test: (populated after /tdd-red)

- **AC-13:** Given ein Trip mit erstem Stage 30. Dezember 2025 und letztem Stage 3. Januar 2026 (Jahreswechsel) / When `formatDateRange(trip)` aufgerufen wird / Then gibt die Funktion genau `"30. Dezember 2025 – 3. Januar 2026"` zurück.
  - Test: (populated after /tdd-red)

- **AC-14:** Given ein Trip mit genau einem Stage am 11. Mai 2026 (Start = Ende) / When `formatDateRange(trip)` aufgerufen wird / Then gibt die Funktion genau `"11. Mai 2026"` zurück (kein Bindestrich).
  - Test: (populated after /tdd-red)

- **AC-15:** Given ein Trip im Status `active`, der User klickt in Step 2 auf „Pausieren" / When `PATCH /state` mit `{"paused": true}` erfolgreich war und `trip`-State in `+page.svelte` aktualisiert wurde / Then zeigt `data-testid="trip-hero-stat-active-stage"` ohne Reload den Text `"Pausiert"`.
  - Test: (populated after /tdd-red)

- **AC-16:** Given eine Trip-Detail-Seite mit Hero / When das Overview-Tab aktiv ist / Then sind `data-testid="trip-detail-tab-list"` (Tab-Navigation aus Step 1) vollständig sichtbar und alle 6 Tab-Trigger klickbar; `data-testid="trip-detail-breadcrumb"` (Header aus Step 2) ist ebenfalls sichtbar.
  - Test: (populated after /tdd-red)

- **AC-17:** Given ein Trip mit `stages = []` / When `TripHero` gerendert wird / Then ist `data-testid="trip-hero-title"` sichtbar, es gibt kein Element mit `data-testid="trip-hero-date-range"` im DOM, und alle drei Stat-Kacheln zeigen sinnvolle Defaults ohne Crash (kein leerer String, kein `undefined`).
  - Test: (populated after /tdd-red)

- **AC-18:** Given ein Viewport unter 640px Breite / When `TripHero` gerendert wird / Then sind die drei Stat-Kacheln vertikal gestapelt (`grid-cols-1`); bei Viewport >= 640px sind sie in drei Spalten nebeneinander (`sm:grid-cols-3`).
  - Test: (populated after /tdd-red)

## Known Limitations

- **Region nicht im Scope:** Der Issue-Body fordert eine Region-Anzeige (z.B. „Korsika"). Das Trip-Modell hat kein `region`-Feld — alle Alternativen (neues Feld, Reverse-Geocoding, avalanche_regions-Ableitung) sprengen den Scope. Region kommt als Folge-Issue #202. Der Hero zeigt daher nur Name, Zeitraum und Stats.
- **Zeitzone:** Datum-Vergleiche arbeiten auf Tages-Granularität in lokaler Zeit (`new Date(d.toDateString())`). Uhrzeit-Vergleiche für `getNextBriefing` parsen HH:MM aus den `report_config`-Strings ohne Timezone-Konversion — Anzeige entspricht der Systemzeit des Browsers. Timezone-Handling als separates Folge-Issue falls nötig.
- **Hero ohne Hintergrundbild:** Kein TopoBg oder Stage-Foto hinter dem Hero. Falls später gewünscht, ist das TopoBg-Pattern aus dem Cockpit (`ActiveTripCard`) wiederverwendbar — kein Spec-Eingriff nötig für #154.
- **Cockpit-Code-Duplikat:** `+page.svelte` (Cockpit, Z. 25–37) und `tripHero.ts` haben strukturell ähnliche Stage-Datum-Berechnungen. Konsolidierung ist bewusst out of scope — Cockpit-Logik aggregiert über mehrere Trips, Hero arbeitet mit genau einem Trip. Konsolidierung als separates Tech-Debt-Ticket.
- **Briefings-Disabled-Anzeige ist lesend:** „Briefings deaktiviert" informiert nur. UI-Pfad zum Aktivieren/Deaktivieren von Briefings liegt bei Issue #159 (Briefing-Konfigurator).
- **Eyebrow-Label „Tage bis Start" ist statisch:** Der Eyebrow-Text wechselt nicht mit dem Status (z.B. zu „Tage seit Start" bei aktivem Trip). Das Label ist im Snippet hart kodiert als „Tage bis Start" — der eigentliche Wert (`getDaysLabel`) enthält die korrekte kontextuelle Aussage. Eine dynamische Eyebrow-Beschriftung wäre ein kosmetisches Folge-Issue.
- **`TODO(epic-135)` in `wizardState.svelte.ts`** bleibt bis zum letzten Sub-Issue von Epic #135 bestehen — explizit nicht in Scope für #154.

## Changelog

- 2026-05-12: Initial spec — Issue #154 (Epic #135 Sub-Spec: Trip-Detail Hero). 4 Pure-Functions (`getActiveStageDisplay`, `getNextBriefing`, `getDaysLabel`, `formatDateRange`), Hero-Komponente mit Svelte-5-Snippet für Stat-Kacheln, TripTabs-Edit (trip-Prop), Route-Edit (+page.svelte), Barrel-Edit. 18 Acceptance Criteria im AC-N-Format. TestID-Inventar (6 IDs). Datei-Liste (7 Dateien, ~434 LoC). PO-Entscheidungen: Region weggelassen (Folge-Issue #202), Zeitraum-Format kompakt nach deutschen Konventionen.
