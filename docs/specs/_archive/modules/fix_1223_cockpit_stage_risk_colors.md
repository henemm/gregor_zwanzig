---
entity_id: fix_1223_cockpit_stage_risk_colors
type: module
created: 2026-07-11
updated: 2026-07-11
status: draft
version: "1.0"
tags: [frontend, weather, cockpit, bugfix]
---

# Cockpit-Etappen-Kacheln: Wetter-Risiko-Farben

## Approval

- [x] Approved (PO 'go' 2026-07-11)

## Purpose

Die live gemountete Cockpit-Etappenkachel (`HubOverview` → `TripStageRow`) soll pro Etappe die Wetter-Risiko-Ampel (grün/gelb/rot) anzeigen. Aktuell fehlt der Fetch des Risiko-Endpoints **und** das Pill-Farb-Mapping passt nicht zum Response-Format → jede Etappe erscheint immer grün/„OK". Dieses Issue macht den Nutzen von #1212 (Cockpit = dieselbe Risiko-Stufe wie das Briefing) erstmals sichtbar.

## Source

- **File:** `frontend/src/lib/components/trip-detail/HubOverview.svelte` (MODIFY — Fetch + Merge)
- **File:** `frontend/src/lib/components/trip-detail/TripStageRow.svelte` (MODIFY — `risk`-Prop + Mapping)
- **File:** `frontend/src/lib/cockpit_stage_risk_colors.test.ts` (CREATE — Verhaltenstest)
- **Identifier:** `HubOverview`, `TripStageRow`

Schicht: **Frontend / SvelteKit** (produktive Oberfläche). Backend-Endpoint existiert bereits (Go-Proxy → Python-SSoT, #1212 live), wird nur konsumiert.

## Estimated Scope

- **LoC:** ~+45 / -6
- **Files:** 3 (2 MODIFY, 1 CREATE)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/trips/{id}/stages/weather` | Backend-Endpoint | Liefert `results[stageId].risk: 'green'\|'yellow'\|'red'\|null` (Go-Proxy → Python-SSoT, #1212) |
| `StageWeatherResult` / `StagesWeatherResponse` | Typ (`types.ts:448/453`) | Response-Format |
| `Pill` (`ui/pill/Pill.svelte`) | Atom | Tones `good→success`, `warn→warning`, `bad→danger`, `neutral` |
| `StageList.svelte` / `StageDetailRow.svelte` | Referenz (toter Pfad) | Vorbild für lazy Fetch bzw. `green/yellow/red`-Mapping |

## Implementation Details

**`HubOverview.svelte` — lazy Client-Fetch (Muster `StageList.svelte:29-37`):**
```
let stageWeather: Record<string, StageWeatherResult | null> = $state({});
$effect(() => {
  if (!trip?.id) return;
  fetch(`/api/trips/${trip.id}/stages/weather`)
    .then((r) => (r.ok ? r.json() as Promise<StagesWeatherResponse> : null))
    .then((data) => { if (data) stageWeather = data.results; })
    .catch(() => {});   // fail-soft
});
// im {#each}: <TripStageRow ... risk={stageWeather[stage.id]?.risk ?? null} />
```
**Kritisch:** Der Fetch läuft ausschließlich clientseitig in `HubOverview` (Trip-Cockpit-Tab). **Niemals** im SSR-Home-Loader — Regel #386/#395 (sonst hängt `/` ~57 s).

**`TripStageRow.svelte` — expliziter `risk`-Prop + korrektes Mapping:**
```
interface Props { ...; risk?: 'green' | 'yellow' | 'red' | null; }
const pillTone = $derived(
  risk === 'red' ? 'bad' : risk === 'yellow' ? 'warn' : risk === 'green' ? 'good' : 'neutral'
);
const pillLabel = $derived(
  risk === 'red' ? 'Risiko' : risk === 'yellow' ? 'Achten' : risk === 'green' ? 'OK' : '—'
);
```
Der bestehende `(stage as Stage & { risk?: string }).risk`-Cast-Fallback entfällt zugunsten des expliziten Props.

## Expected Behavior

- **Input:** `trip.id` (Fetch) + pro Etappe `risk` aus dem Endpoint-Response.
- **Output:** Farbige Risiko-Pille je Kachel-Zeile — rot/„Risiko", gelb/„Achten", grün/„OK", bzw. neutral „—" solange keine Daten.
- **Side effects:** Ein clientseitiger GET pro Cockpit-Tab-Öffnung. Kein SSR-Fetch, kein Home-Loader-Aufruf.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Etappen, deren Endpoint-Response `risk: 'red'` bzw. `'yellow'` bzw. `'green'` liefert / When der Übersicht-Tab (`HubOverview`) gerendert ist und `TripStageRow` das jeweilige `risk` erhält / Then zeigt die Kachel eine rote Pille „Risiko" (Ton `bad`), eine gelbe „Achten" (Ton `warn`) bzw. eine grüne „OK" (Ton `good`) — jede Stufe eindeutig unterscheidbar.
  - Test: Component-Test rendert `TripStageRow` mit `risk='red'|'yellow'|'green'` und prüft `data-tone` + Label-Text der Pille.
- **AC-2:** Given eine Etappe, für die der Endpoint `risk: null` liefert oder die Daten noch laden / When die Kachel gerendert wird / Then erscheint eine **neutrale** „—"-Pille (Ton `neutral`) und **keine** grüne „OK"-Pille — kein irreführendes Falsch-Grün.
  - Test: Component-Test mit `risk={null}` bzw. ohne `risk`-Prop prüft, dass die Pille Ton `neutral`/Label „—" hat und Ton ≠ `good`.
- **AC-3:** Given der Übersicht-Tab wird für einen Trip geöffnet / When `HubOverview` mountet / Then ruft die Komponente clientseitig genau `GET /api/trips/{id}/stages/weather` auf, mappt `results[stageId].risk` in die jeweilige `TripStageRow` und ist fail-soft (Endpoint-Fehler → neutrale Pillen, kein Crash).
  - Test: Component-Test mit gemocktem `fetch` (echter Endpoint-Response als Fixture) prüft, dass die korrekte URL aufgerufen und `risk` in die Zeilen gemappt wird; ein Fetch-Reject lässt die Kacheln neutral (kein Throw).

## Known Limitations

- Der Home-/Übersichts-SSR-Loader zeigt weiterhin keine Risiko-Farben (bewusst, #386/#395) — Farben erscheinen erst nach clientseitigem Nachladen im Cockpit-Tab.
- Kein Live-Auto-Refresh: Der Fetch läuft einmal beim Mount des Tabs; Aktualisierung erst bei erneutem Öffnen/Reload.

## Test Coverage

- `frontend/src/lib/cockpit_stage_risk_colors.test.ts` (Vitest/Component): AC-1, AC-2, AC-3.
