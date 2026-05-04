---
entity_id: wetter_drill_down
type: module
created: 2026-04-18
updated: 2026-04-18
status: draft
version: "1.0"
tags: [sveltekit, frontend, ux, f76, weather, compare]
---

# F76 Phase F — Wetter Drill-Down aus Sidebar

## Approval

- [ ] Approved

## Purpose

Pro Location in der Orts-Vergleich Sidebar erscheint ein Wetter-Icon-Button. Klick darauf zeigt die stuendliche Wettervorhersage dieser Location im Content-Bereich (als Alternative zum Vergleichs-Ergebnis). Damit wird die eigenstaendige /weather Seite ueberfluessig.

Teil des UX-Redesigns (#76), Eltern-Spec: `docs/specs/ux_redesign_navigation.md` Abschnitt "Wetter-Drill-Down".

## Ist-Zustand

- /weather ist eine eigenstaendige Seite (nicht mehr in Nav, aber per URL erreichbar)
- Orts-Vergleich Sidebar zeigt nur Checkboxen pro Location
- Content zeigt entweder Auto-Reports oder Vergleichs-Ergebnis

## Soll-Zustand

Sidebar: Neben jeder Location-Checkbox ein kleines Wetter-Icon (CloudSun). Klick setzt `weatherLocationId` State.

Content: Wenn `weatherLocationId` gesetzt, zeige Wetter-Detail statt Auto-Reports/Vergleich:

```
┌──────────────┐┌─────────────────────────┐
│ Meine Orte   ││ Wetter: Stubaier        │
│              ││                         │
│ ▼ Ski Tirol  ││ 48h | [Laden]           │
│   ☑ Stubaier☁││                         │
│   ☑ Hintertux││ ┌─ Forecast-Tabelle ──┐ │
│              ││ │ Zeit | Temp | Wind   │ │
│              ││ │ ...                  │ │
│              ││ └──────────────────────┘ │
│              ││                         │
│              ││ [← Zurueck]             │
└──────────────┘└─────────────────────────┘
```

"Zurueck" Button setzt `weatherLocationId = null` → Content zeigt wieder Auto-Reports/Vergleich.

## Source

- **File:** `frontend/src/routes/compare/+page.svelte` **(EDIT, ~80 LoC)**

## Aenderungen im Detail

### 1. Neuer State

```typescript
let weatherLocationId: string | null = $state(null);
let weatherForecast: ForecastResponse | null = $state(null);
let weatherLoading = $state(false);
let weatherHours = $state('48');
```

### 2. Wetter-Icon in Sidebar

Pro Location ein kleines CloudSun Icon-Button neben der Checkbox:

```svelte
<button onclick={() => showWeather(loc.id)} title="Wetter anzeigen">
  <CloudSun class="size-3.5 opacity-50 hover:opacity-100" />
</button>
```

### 3. showWeather Funktion

```typescript
async function showWeather(locId: string) {
  weatherLocationId = locId;
  weatherForecast = null;
  weatherLoading = true;
  const loc = locations.find(l => l.id === locId);
  if (!loc) return;
  try {
    weatherForecast = await api.get<ForecastResponse>(
      `/api/forecast?lat=${loc.lat}&lon=${loc.lon}&hours=${weatherHours}`
    );
  } catch { ... }
  finally { weatherLoading = false; }
}
```

### 4. Content-Bereich: Wetter-View

Conditional rendering im Content:

```svelte
{#if weatherLocationId}
  <!-- Wetter Detail -->
  <h2>Wetter: {locationName}</h2>
  <select bind:value={weatherHours}>...</select>
  <Button onclick={() => showWeather(weatherLocationId!)}>Laden</Button>
  <Button variant="ghost" onclick={() => weatherLocationId = null}>← Zurück</Button>
  
  {#if weatherForecast}
    <!-- Forecast-Tabelle (aus /weather uebernehmen) -->
  {/if}
{:else if result}
  <!-- Vergleichs-Ergebnis (wie bisher) -->
{:else}
  <!-- Auto-Reports (wie bisher) -->
{/if}
```

### 5. Forecast-Tabelle

Aus /weather/+page.svelte uebernehmen: Stuendliche Tabelle mit Emoji, Temp, Wind, Niederschlag, Bewoelkung. Imports: `weatherEmoji`, `degToCardinal` aus `$lib/utils/weatherEmoji.js`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `compare/+page.svelte` | file | Einzige betroffene Datei |
| `$lib/types.ts` | types | ForecastResponse interface |
| `$lib/utils/weatherEmoji.js` | util | Wetter-Emoji + Wind-Richtung |
| `$lib/api.ts` | module | GET /api/forecast |

## Was sich NICHT aendert

- /weather Seite bleibt erreichbar (wird nicht geloescht)
- Compare-Logik
- Auto-Reports Section
- Sidebar-Struktur (Gruppen, Checkboxen)
- API-Endpunkte

## Expected Behavior

- **Klick auf Wetter-Icon:** Content wechselt zu Wetter-Detail der Location
- **"Zurueck" Button:** Content wechselt zurueck zu Auto-Reports/Vergleich
- **Stunden-Auswahl:** 24h/48h/72h, Default 48h
- **Laden Button:** Forecast neu laden (z.B. nach Stunden-Wechsel)

## Known Limitations

- Forecast-Tabelle wird inline dupliziert (nicht als shared Komponente) — akzeptabel
- Kein Auto-Refresh des Forecasts
- /weather Seite wird nicht geloescht (kann spaeter entfernt werden)

## Changelog

- 2026-04-18: Initial spec fuer Phase F
