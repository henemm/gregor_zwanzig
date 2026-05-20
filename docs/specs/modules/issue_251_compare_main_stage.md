---
entity_id: issue_251_compare_main_stage
type: module
created: 2026-05-19
updated: 2026-05-19
status: draft
version: "1.0"
issue: 251
tags: [compare, frontend, svelte, matrix, scoring, hourly, banner, preset]
---

# Issue #251 — Compare-Hauptbühne (Frontend): Matrix, Banner, Stunden-Verlauf

## Approval

- [ ] Approved

## Purpose

Ersetzt den bestehenden monolithischen Compare-Screen (`+page.svelte`, 688 LoC, inline-Markup, Python-Endpoint) durch vier dedizierte Svelte-Komponenten (`PresetHeader`, `RecommendationBanner`, `CompareMatrix`, `HourlyMatrix`) und migriert den API-Call von `GET /api/compare` (Python-Proxy) auf `POST /api/compare/run` (Go-Engine, Issue #250). Die Page shrinks dabei von 688 auf ~280 LoC und alle neuen TypeScript-Interfaces sowie der `toCompareProfile()`-Adapter werden zentral in `types.ts` verankert, damit andere Features (z.B. Subscriptions) den System-Namespace unberührt lassen können.

## Source

- **Files:**
  - `frontend/src/lib/components/compare/PresetHeader.svelte` (NEU, ~120 LoC)
  - `frontend/src/lib/components/compare/RecommendationBanner.svelte` (NEU, ~60 LoC)
  - `frontend/src/lib/components/compare/CompareMatrix.svelte` (NEU, ~180 LoC)
  - `frontend/src/lib/components/compare/HourlyMatrix.svelte` (NEU, ~150 LoC)
  - `frontend/src/lib/types.ts` (geändert, +Interfaces +Adapter +ForecastDataPoint-Felder, ~35 LoC)
  - `frontend/src/routes/compare/+page.svelte` (geändert, API-Migration + Komponenten-Verdrahtung)

## Dependencies

| Abhängigkeit | Art | Zweck |
|---|---|---|
| `POST /api/compare/run` (Go-Engine, Issue #250) | Go-Backend-Endpoint | Nimmt `{ location_ids, date, profile }` entgegen; liefert `CompareResult` mit `rows`, `winner`, `hourly` |
| `frontend/src/lib/types.ts` — `ActivityProfile` | TypeScript-Union (vorhanden, unverändert) | System-Namespace der Aktivitätsprofile; wird in `toCompareProfile()` gemappt |
| `frontend/src/lib/types.ts` — `ForecastDataPoint` | TypeScript-Interface (vorhanden, wird erweitert) | Basis-Typ für Stundenwerte; bekommt 3 optionale Schnee-/Gefrierfelder ergänzt |
| `frontend/src/lib/types.ts` — `Location` | TypeScript-Interface (vorhanden, unverändert) | Enthält `id` + `name`; Page nutzt `locations.find(l => l.id === row.location_id)` für Namensauflösung |
| `frontend/src/lib/api.ts` | Utility (vorhanden) | `api.post('/api/compare/run', body)` zum Auslösen des Vergleichs |
| `frontend/src/routes/compare/+page.svelte` | SvelteKit-Page (geändert) | Zustandsträger für `locations`, `selectedIds`, `activityProfile`, `compareDate`, `twStart`, `twEnd`, `result` |
| Design-System (`--g-accent`, `--g-surface-2`, CSS-Klassen) | Design-Token (vorhanden) | Mini-Bars und Best-Value-Markierung nutzen CSS-Variablen statt Hardcoded-Farben |

## Scope

**Nur Frontend.** 6 Dateien:

- **Neu:** `frontend/src/lib/components/compare/PresetHeader.svelte`
- **Neu:** `frontend/src/lib/components/compare/RecommendationBanner.svelte`
- **Neu:** `frontend/src/lib/components/compare/CompareMatrix.svelte`
- **Neu:** `frontend/src/lib/components/compare/HourlyMatrix.svelte`
- **Geändert:** `frontend/src/lib/types.ts`
- **Geändert:** `frontend/src/routes/compare/+page.svelte`

Keine Änderungen an:
- `LocationsRail.svelte`, `NewLocationWizard.svelte` (Issue #249) — unberührt
- `SubscriptionForm.svelte` — unberührt; nutzt weiterhin System-Namespace
- `ActivityProfile`-Union und `ACTIVITY_PROFILE_OPTIONS` in `types.ts` — unverändert

## Implementation Details

### §1 `frontend/src/lib/types.ts` — Neue Interfaces + Adapter

**Neue Interfaces** (nach den bestehenden Location/Trip-Typen einfügen):

```typescript
export interface CompareMetrics {
  temp_min_c?: number | null;
  temp_max_c?: number | null;
  wind_max_kmh?: number | null;
  gust_max_kmh?: number | null;
  precip_sum_mm?: number | null;
  cloud_avg_pct?: number | null;
  visibility_min_m?: number | null;
  wind_chill_min_c?: number | null;
  uv_index_max?: number | null;
  dni_avg_wm2?: number | null;
  snow_depth_cm?: number | null;
  snow_new_sum_cm?: number | null;
  thunder_level_max?: string | null; // 'NONE' | 'MED' | 'HIGH'
}

export interface CompareRow {
  location_id: string;
  score: number;      // 0–100
  rank: number;       // 1 = bester
  metrics: CompareMetrics;
}

export interface CompareWinner {
  location_id: string;
  tags: string[];
}

export interface CompareResult {
  rows: CompareRow[];
  winner?: CompareWinner;
  hourly: Record<string, ForecastDataPoint[]>;
}
```

**Adapter-Funktion** (pure function, kein Side-Effect):

```typescript
export function toCompareProfile(profile: ActivityProfile): string {
  switch (profile) {
    case 'wintersport':     return 'WINTERSPORT';
    case 'wandern':         return 'ALPINE_TOURING';
    case 'summer_trekking': return 'SUMMER_TREKKING';
    case 'allgemein':       return 'ALLGEMEIN';
  }
}
```

Der Adapter wird **ausschließlich** an der API-Call-Site in `+page.svelte` (`runComparison()`) aufgerufen. Alle anderen Stellen (Subscriptions, SubscriptionForm, Wizard) verwenden weiterhin den System-Namespace direkt.

**ForecastDataPoint-Erweiterung** — drei optionale Felder ergänzen (bestehende Felder unverändert):

```typescript
snow_depth_cm?: number | null;
snow_new_24h_cm?: number | null;
freezing_level_m?: number | null;
```

### §2 `PresetHeader.svelte` — Steuerungs-Card (~120 LoC)

**Props (via `bind:` aus Page):**
- `bind:compareDate: string` — ISO-Datum ("YYYY-MM-DD")
- `bind:twStart: string` — Von-Uhr (HH:MM, nur für SubscriptionForm-Prefill, nicht an API)
- `bind:twEnd: string` — Bis-Uhr (HH:MM, nur für SubscriptionForm-Prefill, nicht an API)
- `bind:activityProfile: ActivityProfile`
- `locationCount: number` — Anzahl selektierter Locations (read-only, für Kurzinfo)
- `on:run` — Event ausgelöst wenn "Vergleich starten" geklickt
- `on:saveBriefing` — Event ausgelöst wenn "Als Auto-Briefing speichern" geklickt

**Layout:**
- Linke Seite: Datum-Picker (`<input type="date">`), Von/Bis (`<input type="time">`), 48h-Dropdown (Forecast-Horizont, aktuell Placeholder-Wert, nicht an API übergeben), Aktivitätsprofil-`<select>` (Werte aus `ACTIVITY_PROFILE_OPTIONS`)
- Rechte Seite oben: Button "Preset laden" (disabled, Placeholder), Button "Als Auto-Briefing speichern", Button "Vergleich starten" (primary)
- Kurzinfo-Zeile unter den Controls: `{locationCount} Locations · {twStart}–{twEnd} Uhr · 48h`

**Verhalten:** "Vergleich starten" dispatcht `run`-Event; die Page reagiert darauf mit `runComparison()`. Keine eigene API-Logik in der Komponente.

### §3 `RecommendationBanner.svelte` — Empfehlungs-Banner (~60 LoC)

**Props:**
- `winner: CompareWinner`
- `winnerRow: CompareRow` — `rows[0]` aus `CompareResult`
- `locations: Location[]` — für Namensauflösung

**Layout:**
- Score-Badge (groß, `winnerRow.score`/100, z.B. "87")
- Location-Name: `locations.find(l => l.id === winner.location_id)?.name ?? winner.location_id`
- Tag-Liste: `winner.tags` als Pill-Badges (ok/warn/info via Klasse je nach Tag-Inhalt; keine eigene Klassifizierungslogik — alle Tags werden mit CSS-Klasse `tag-ok` gerendert, sofern kein weiteres Mapping in Backend-Tags vorhanden)

**Bedingtes Rendering:** Die Komponente rendert nur wenn `winner` und `winnerRow` beide definiert sind. Bei leerem `result` wird kein Banner angezeigt (Page steuert das mit `{#if result?.winner}`).

### §4 `CompareMatrix.svelte` — Vergleichs-Matrix (~180 LoC)

**Props:**
- `rows: CompareRow[]` — sortiert nach Score (rank 1 zuerst)
- `locations: Location[]` — für Namensauflösung
- `profile: ActivityProfile` — bestimmt angezeigte Metriken und Reihenfolge

**Profil-spezifische Metriken** (Package-Level-Konstante im `<script>`):

| Profil | Metriken (in Reihenfolge) | higherIsBetter |
|--------|--------------------------|----------------|
| WINTERSPORT | `snow_depth_cm`, `snow_new_sum_cm`, `dni_avg_wm2`, `wind_max_kmh`, `cloud_avg_pct` | true, true, true, false, false |
| ALPINE_TOURING | `snow_new_sum_cm`, `visibility_min_m`, `wind_max_kmh` | true, true, false |
| SUMMER_TREKKING | `precip_sum_mm`, `thunder_level_max`, `wind_max_kmh`, `uv_index_max`, `visibility_min_m` | false, false, false, false, true |
| ALLGEMEIN | `temp_max_c`, `wind_max_kmh`, `precip_sum_mm`, `visibility_min_m` | true, false, false, true |

**`thunder_level_max`-Mapping:** `'NONE' → 0`, `'MED' → 1`, `'HIGH' → 2` (für Vergleich und Mini-Bar; Anzeige bleibt als String).

**Tabellenstruktur:**
- Kopfzeile: Leer-Zelle + je eine Spalte pro Location (Name aus `locations.find(...)`)
- Datenzeilen: Metrik-Label + je eine Zelle pro Location mit Wert + Mini-Bar

**Best-Value-Markierung:** Pro Zeile wird der günstigste Wert über alle Locations bestimmt (`higherIsBetter` beachten). Die zugehörige Zelle erhält CSS-Klasse `best-value`. Kein Inline-Style, kein Farb-Hack.

**Mini-Bar:** Inline-`<div>` innerhalb der Datenzelle:

```svelte
<div class="mini-bar" style="width: {pct}%"></div>
```

Prozent-Berechnung: normierter Wert relativ zum Maximalwert der Zeile (0–100%). CSS: `background: var(--g-accent); opacity: 0.4;`. Eltern-Zelle: `background: var(--g-surface-2)`.

**Null-Handling:** Zellen mit `null`/`undefined`-Wert zeigen `—` (em-dash), keine Mini-Bar, nicht als Best-Value markierbar.

### §5 `HourlyMatrix.svelte` — Stunden-Verlauf (~150 LoC)

**Props:**
- `hourly: Record<string, ForecastDataPoint[]>` — aus `CompareResult.hourly` (Top-3 LocationIDs als Keys)
- `locations: Location[]` — für Namensauflösung
- `rows: CompareRow[]` — für die Reihenfolge (rank 1, 2, 3)

**Ermittlung der Top-3:** `rows.slice(0, 3).map(r => r.location_id)` — Reihenfolge entspricht Ranking. Nur LocationIDs mit Einträgen in `hourly` werden gerendert.

**Abschnitte pro Location:** Je Location ein `<details>`-Element (collapsible):
- `<summary>`: Rang-Badge + Location-Name
- Inhalt: Tabelle der Stundenwerte

**Spalten der Stundentabelle:**
`Uhrzeit | Emoji | Temp (°C) | Wind (km/h) | Böen (km/h) | Niederschlag (mm) | Risiko`

- **Emoji:** Aus `thunder_level` und `precip_mm` des `ForecastDataPoint` abgeleitet (einfache Regeln: thunder → ⛈, regen > 1mm → 🌧, bewölkt → ☁, sonst → ☀)
- **Risiko-Pill:** `thunder_level`-Wert als farbige Pill (`NONE` → grün, `MED` → gelb, `HIGH` → rot); nutzt vorhandene Pill-Klassen

**Standardzustand:** Rank-1-Location `<details>` ist `open`, Rank-2 und -3 geschlossen.

### §6 `+page.svelte` — API-Migration + Verdrahtung (~280 LoC)

**Entfernte Teile:**
- Alle inline `CompareResult`/`CompareLocation`/`HourlyPoint`-Interface-Definitionen (jetzt in `types.ts`)
- Alle Compare-Markup-Blöcke (jetzt in den 4 neuen Komponenten)
- `GET /api/compare`-Call (Python-Proxy)

**Neue `runComparison()`-Funktion:**

```typescript
async function runComparison() {
  const ids = allSelected
    ? locations.map(l => l.id)   // kein '*'-Wildcard
    : [...selectedIds];

  const body = {
    location_ids: ids,
    date: compareDate,
    profile: toCompareProfile(activityProfile)  // einzige Stelle mit Adapter
  };

  result = await api.post<CompareResult>('/api/compare/run', body);
}
```

**Komponenten-Einbindung:**

```svelte
<PresetHeader
  bind:compareDate
  bind:twStart
  bind:twEnd
  bind:activityProfile
  locationCount={selectedIds.size}
  on:run={runComparison}
  on:saveBriefing={openSaveBriefingDialog}
/>

{#if result?.winner && result.rows[0]}
  <RecommendationBanner winner={result.winner} winnerRow={result.rows[0]} {locations} />
{/if}

{#if result?.rows?.length}
  <CompareMatrix rows={result.rows} {locations} profile={activityProfile} />
{/if}

{#if result?.hourly && Object.keys(result.hourly).length}
  <HourlyMatrix hourly={result.hourly} {locations} rows={result.rows} />
{/if}
```

**`twStart`/`twEnd`** bleiben im Page-State für `prefilledSub` (SubscriptionForm-Prefill), werden aber nicht an `POST /api/compare/run` übergeben.

### §7 LoC-Schätzung

| Datei | Inhalt | LoC |
|-------|--------|-----|
| `PresetHeader.svelte` | Controls + Kurzinfo | ~120 |
| `RecommendationBanner.svelte` | Winner + Tags | ~60 |
| `CompareMatrix.svelte` | Tabelle + Mini-Bars + Best-Value | ~180 |
| `HourlyMatrix.svelte` | Details + Stundentabellen | ~150 |
| `types.ts` | Interfaces + Adapter + ForecastDataPoint | ~35 |
| `+page.svelte` | Page (schrumpft von 688 auf ~280) | -408 |
| **Netto-Delta** | | **~137 LoC** |

LoC-Limit-Override nicht erforderlich (netto < 250).

## Expected Behavior

- **Input:** Nutzer wählt Datum, Aktivitätsprofil und Locations in `PresetHeader` und `LocationsRail`, klickt "Vergleich starten". Page ruft `POST /api/compare/run` mit expliziten `location_ids` (Array), `date` (ISO), `profile` (Go-Namespace) auf.
- **Output:** `CompareMatrix` zeigt alle selektierten Locations als Spalten mit profil-spezifischen Metriken als Zeilen und grün markiertem Best-Value; `RecommendationBanner` zeigt Rank-1-Location mit Score und Tags; `HourlyMatrix` zeigt Stundenwerte der Top-3 Locations in ausklappbaren Sektionen.
- **Side effects:**
  - Der Python-Proxy-Endpoint `GET /api/compare` bleibt unverändert aktiv.
  - `LocationsRail.svelte`, `NewLocationWizard.svelte`, `SubscriptionForm.svelte` sind nicht betroffen.
  - `ActivityProfile`-Union und `ACTIVITY_PROFILE_OPTIONS` in `types.ts` bleiben unverändert.

## Acceptance Criteria

**AC-1:** Given Compare-Engine liefert Ergebnisse / When die Matrix rendert / Then ist der Best-Value jeder Zeile grün markiert (CSS-Klasse `best-value`, kein Inline-Style) und die Mini-Bars zeigen relative Verhältnisse innerhalb der Zeile (Breite 0–100% relativ zum Zeilenmaximalwert).
  - Test: (populated after /tdd-red)

**AC-2:** Given Profil-Wechsel im Dropdown / When "Vergleich starten" geklickt wird / Then lädt die Matrix neu mit profil-spezifischen Zeilen — WINTERSPORT zeigt `snow_depth_cm` als erste Zeile, SUMMER_TREKKING zeigt `precip_sum_mm` als erste Zeile.
  - Test: (populated after /tdd-red)

**AC-3:** Given der Winner im Empfehlungs-Banner / When die Seite das Ergebnis anzeigt / Then stimmt der angezeigte Score mit `result.rows[0].score` überein und `winner.location_id` ist identisch mit `result.rows[0].location_id`.
  - Test: (populated after /tdd-red)

**AC-4:** Given ≥3 Locations im Ranking / When der Stunden-Verlauf rendert / Then werden exakt die Top-3 aus `CompareResult.hourly` angezeigt (Rank 1, 2, 3 aus `rows`), Rank-4 und weitere werden nicht dargestellt.
  - Test: (populated after /tdd-red)

**AC-5:** Given `activityProfile = 'wandern'` im Dropdown / When `runComparison()` aufgerufen wird / Then enthält der Request-Body `"profile": "ALPINE_TOURING"` (toCompareProfile-Adapter korrekt) und der System-Namespace-Wert `'wandern'` erscheint nicht im API-Call.
  - Test: (populated after /tdd-red)

**AC-6:** Given alle Locations ausgewählt (`allSelected = true`) / When Vergleich gestartet wird / Then enthält `location_ids` im Request-Body ein Array mit allen Location-IDs aus `locations.map(l => l.id)` — kein `'*'`-Wildcard-String.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Forecast-Horizont-Dropdown:** Der 48h-Wert in `PresetHeader` wird in dieser Spec nicht an `POST /api/compare/run` übergeben — die Go-Engine verwendet einen festen internen Horizont. Das Dropdown ist visuell vorhanden aber ohne Backend-Wirkung; ein späteres Issue kann den Parameter ergänzen.
- **"Preset laden":** Button ist disabled/Placeholder. Preset-Verwaltung ist nicht im Scope dieser Spec.
- **"Als Auto-Briefing speichern":** Löst `on:saveBriefing`-Event aus; der eigentliche Save-Dialog und Endpoint sind in einem separaten Issue zu spezifizieren. Der Button muss in dieser Spec noch keinen persistenten State erzeugen.
- **thunder_level_max als String:** Die Normalisierung `'NONE'→0 / 'MED'→1 / 'HIGH'→2` für Mini-Bar und Best-Value ist in CompareMatrix inline implementiert. Wenn das Backend neue Werte einführt, muss das Mapping dort angepasst werden.
- **Tag-Klassifizierung im Banner:** Alle `winner.tags` werden aktuell mit der Klasse `tag-ok` gerendert. Eine semantische ok/warn/info-Unterscheidung erfordert ein definiertes Tag-Präfix-Schema im Backend, das in dieser Spec nicht festgelegt ist.

## Changelog

- 2026-05-19: Initial spec — Issue #251. Compare-Hauptbühne Frontend: 4 neue Svelte-Komponenten (PresetHeader, RecommendationBanner, CompareMatrix, HourlyMatrix), Migration auf POST /api/compare/run, toCompareProfile-Adapter, ForecastDataPoint-Erweiterung. Netto ~137 LoC, kein LoC-Override erforderlich.
