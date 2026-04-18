---
entity_id: startseite_kacheln
type: module
created: 2026-04-18
updated: 2026-04-18
status: draft
version: "1.0"
tags: [sveltekit, frontend, dashboard, ux, f76]
---

# F76 Phase B — Startseite: Kachel-Uebersicht

## Approval

- [ ] Approved

## Purpose

Ersetzt die technisch-orientierte Startseite (3 Stat-Karten mit Zaehler und System-Health) durch eine use-case-zentrierte Kachel-Uebersicht: Trips und Orts-Vergleiche (Subscriptions) als anklickbare Cards mit Kontext-Informationen auf einen Blick. User sieht sofort, was konfiguriert ist und wann der naechste Report laeuft — statt abstrakte Datenpunkt-Zaehler.

Teil des UX-Redesigns (#76), Eltern-Spec: `docs/specs/ux_redesign_navigation.md` (approved). Baut auf Phase A (Nav-Umbau) auf.

## Ist-Zustand

`+page.svelte` (73 LoC): 3 Stat-Cards in `md:grid-cols-3`. Kein Kontext, kein Use-Case-Bezug.

```
[Trips: 2]   [Locations: 5]   [System-Status: ok]
```

`+page.server.ts` (28 LoC): Laedt `/api/trips`, `/api/locations`, `/api/health`. Gibt nur Zaehler und Health-Daten zurueck — vollstaendige Objekte werden verworfen.

## Soll-Zustand

```
Meine Touren                   Orts-Vergleiche

┌─────────────┐ ┌─────────────┐   ┌─────────────┐ ┌─────────────┐
│ 🥾 GR20     │ │ 🥾 GR221    │   │ ⛷ Ski Tirol │ │ 🏄 Surf PT  │
│ 21. April   │ │ 10. Mai     │   │ tägl. 07:00 │ │ Do 18:00    │
│ 5 Etappen   │ │ 4 Etappen   │   │ Stubaier #1 │ │ Peniche #1  │
│ Abend 18:00 │ │ Abend 18:00 │   │             │ │             │
└─────────────┘ └─────────────┘   └─────────────┘ └─────────────┘

              [+ Neue Tour]  [+ Neuer Vergleich]
```

Empty State (keine Trips UND keine Subscriptions):

```
Willkommen bei Gregor 20

[Erste Tour anlegen]  [Ersten Vergleich erstellen]
```

## Source

- **File:** `frontend/src/routes/+page.svelte` **(REWRITE, ~100 LoC)**
- **File:** `frontend/src/routes/+page.server.ts` **(EDIT, ~35 LoC)**

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ux_redesign_navigation` | spec | Eltern-Spec, definiert Gesamt-Vision und Kachel-Design |
| `nav_redesign_phase_a` | spec | Vorgaenger-Phase (Nav-Umbau), bereits implementiert |
| `+page.svelte` | file | Einzige View-Datei, wird vollstaendig neu geschrieben |
| `+page.server.ts` | file | Server-Load-Funktion, gibt ab sofort vollstaendige Objekte zurueck |
| `GET /api/trips` | api | Liefert Trip-Array mit `id`, `name`, `stages[]`, `report_config?` |
| `GET /api/subscriptions` | api | Liefert Subscription-Array (neu hinzugefuegt in server.ts) |
| `GET /api/health` | api | Bleibt vorhanden, wird aber nicht mehr auf der Startseite angezeigt |
| shadcn-svelte `Card` | component | `Card.Root`, `Card.Header`, `Card.Title`, `Card.Content`, `Card.Footer` — bereits verwendet |
| Lucide Icons | library | `Footprints`, `GitCompare`, `Plus`, `Calendar`, `Clock` |
| Tailwind CSS 4 | library | Grid-Layout, Responsive Design |

## Server-Aenderungen (+page.server.ts)

### Neu: Subscriptions laden

```typescript
const subsRes = await fetch(`${API()}/api/subscriptions`, { headers }).catch(() => null);
const subscriptions = subsRes?.ok ? await subsRes.json() : [];
```

### Rueckgabe-Objekt

```typescript
return {
  trips: Array.isArray(trips) ? trips : [],
  subscriptions: Array.isArray(subscriptions) ? subscriptions : []
  // health wird NICHT mehr zurueckgegeben (kein Bedarf auf Startseite)
};
```

Die vollstaendigen Trip- und Subscription-Objekte werden weitergereicht — kein Informationsverlust durch vorzeitiges `length`-Reduzieren.

## Implementation Details

### 1. Daten-Mapping fuer Trip-Kacheln

Fuer jede Trip-Kachel werden folgende Felder aus dem Trip-Objekt gelesen:

```
name          → Kachel-Titel
stages.length → "N Etappen"
stages[0].date (erster Eintrag, falls vorhanden) → Datum der ersten Etappe, formatiert als "DD. Monat"
report_config?.reports[0] → Naechster Report (z.B. "Abend 18:00"), falls konfiguriert
```

Datum-Formatierung: `new Date(date).toLocaleDateString('de-DE', { day: 'numeric', month: 'long' })`.

Falls `stages` leer oder kein `date` gesetzt: Datum-Zeile wird weggelassen.
Falls kein `report_config`: Report-Zeile wird weggelassen.

### 2. Daten-Mapping fuer Subscription-Kacheln

Fuer jede Subscription-Kachel:

```
name           → Kachel-Titel
schedule       → Schedule-Label (siehe Mapping unten)
locations[0]   → Erster Ort als Beispiel-Anzeige (z.B. "Stubaier #1")
```

Schedule-Mapping:

| `schedule` | `weekday` | Anzeige |
|------------|-----------|---------|
| `daily_morning` | — | `tägl. 07:00` |
| `daily_evening` | — | `tägl. 18:00` |
| `weekly` | 0 (So) | `So HH:MM` |
| `weekly` | 1 (Mo) | `Mo HH:MM` |
| `weekly` | 4 (Do) | `Do HH:MM` |
| etc. | | |

Uhrzeit aus `time_window_start` (ISO-String oder HH:MM), erste 5 Zeichen.

Wochentag-Kuerzel: `['So','Mo','Di','Mi','Do','Fr','Sa'][weekday]`.

### 3. Layout-Struktur (+page.svelte)

```svelte
<div class="space-y-8">

  <!-- Empty State: nur wenn BEIDE Arrays leer -->
  {#if trips.length === 0 && subscriptions.length === 0}
    <EmptyState />
  {:else}

    <!-- Sektion: Meine Touren (nur wenn trips.length > 0) -->
    {#if trips.length > 0}
      <section>
        <h2>Meine Touren</h2>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {#each trips as trip}
            <TripCard {trip} />
          {/each}
        </div>
      </section>
    {/if}

    <!-- Sektion: Orts-Vergleiche (nur wenn subscriptions.length > 0) -->
    {#if subscriptions.length > 0}
      <section>
        <h2>Orts-Vergleiche</h2>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {#each subscriptions as sub}
            <SubscriptionCard {sub} />
          {/each}
        </div>
      </section>
    {/if}

    <!-- CTA-Zeile: immer sichtbar wenn mind. ein Objekt vorhanden -->
    <CtaRow />

  {/if}

</div>
```

### 4. Trip-Card

Klick auf Kachel navigiert zu `/trips` (Trip-Liste). Kein eigener Deep-Link pro Trip in Phase B.

```svelte
<Card.Root class="cursor-pointer hover:shadow-md transition-shadow" onclick={() => goto('/trips')}>
  <Card.Header>
    <Card.Title class="flex items-center gap-2">
      <FootprintsIcon class="size-4" />
      {trip.name}
    </Card.Title>
  </Card.Header>
  <Card.Content class="space-y-1 text-sm text-muted-foreground">
    {#if firstDate}
      <p><CalendarIcon class="inline size-3 mr-1" />{firstDate}</p>
    {/if}
    <p>{trip.stages.length} {trip.stages.length === 1 ? 'Etappe' : 'Etappen'}</p>
    {#if reportLabel}
      <p><ClockIcon class="inline size-3 mr-1" />{reportLabel}</p>
    {/if}
  </Card.Content>
</Card.Root>
```

### 5. Subscription-Card

Klick auf Kachel navigiert zu `/compare`.

```svelte
<Card.Root class="cursor-pointer hover:shadow-md transition-shadow" onclick={() => goto('/compare')}>
  <Card.Header>
    <Card.Title class="flex items-center gap-2">
      <GitCompareIcon class="size-4" />
      {sub.name}
    </Card.Title>
  </Card.Header>
  <Card.Content class="space-y-1 text-sm text-muted-foreground">
    <p><ClockIcon class="inline size-3 mr-1" />{scheduleLabel}</p>
    {#if sub.locations?.length > 0}
      <p>{sub.locations[0]}</p>
    {/if}
  </Card.Content>
</Card.Root>
```

### 6. Empty State

```svelte
<div class="flex flex-col items-center gap-6 py-16 text-center">
  <h1 class="text-2xl font-bold">Willkommen bei Gregor 20</h1>
  <p class="text-muted-foreground">Leg deine erste Tour oder deinen ersten Orts-Vergleich an.</p>
  <div class="flex gap-4">
    <Button href="/trips"><PlusIcon class="mr-2 size-4" />Erste Tour anlegen</Button>
    <Button variant="outline" href="/compare"><PlusIcon class="mr-2 size-4" />Ersten Vergleich erstellen</Button>
  </div>
</div>
```

### 7. CTA-Zeile (fuer nicht-leere Startseite)

```svelte
<div class="flex gap-3">
  <Button href="/trips" size="sm"><PlusIcon class="mr-2 size-4" />Neue Tour</Button>
  <Button href="/compare" size="sm" variant="outline"><PlusIcon class="mr-2 size-4" />Neuer Vergleich</Button>
</div>
```

## Expected Behavior

- **Input:** Authentifizierter User oeffnet `/`
- **Output:** Kacheln fuer alle vorhandenen Trips und Subscriptions; bei leerem Datenstand: Welcome-Screen mit zwei CTAs
- **Navigation:** Klick auf Trip-Kachel → `/trips`; Klick auf Subscription-Kachel → `/compare`; CTA-Buttons → jeweilige Ziel-Route
- **Side effects:** Keine — rein lesend, kein State wird geschrieben

### Randfaelle

| Situation | Verhalten |
|-----------|-----------|
| Trips vorhanden, keine Subscriptions | Nur "Meine Touren"-Sektion + CTA-Zeile |
| Subscriptions vorhanden, keine Trips | Nur "Orts-Vergleiche"-Sektion + CTA-Zeile |
| Trip ohne `stages` | Etappen-Zeile zeigt "0 Etappen", Datum-Zeile entfaellt |
| Trip ohne `report_config` | Report-Zeile entfaellt |
| Subscription ohne `locations` | Orts-Zeile entfaellt |
| API nicht erreichbar | Leeres Array → Empty State (kein Fehler-Crash) |

## Was sich NICHT aendert

- Alle anderen Routen (`/trips`, `/compare`, `/locations`, `/subscriptions`) bleiben unveraendert
- System-Health-Anzeige entfaellt von der Startseite (sie ist unter `/settings` weiterhin erreichbar)
- `/api/health` wird weiterhin aufgerufen in `+page.server.ts` — kann entfernt werden, da nicht mehr benoetigt; Entscheidung: wird entfernt um unnoetige Requests zu vermeiden
- E2E-Tests in `system-status.spec.ts` und anderen Specs navigieren per `page.goto()` — kein Bruch

## Known Limitations

- Trip-Kachel verlinkt zu `/trips` (Liste), nicht zu einem spezifischen Trip-Detail — kein Deep-Link-Target existiert in Phase B; wird in spaeterer Phase (Trip-Wizard) adressiert
- Subscription-Kachel verlinkt zu `/compare` (Liste), nicht zu einem spezifischen Abo-Eintrag
- `report_config` ist laut API-Datenstruktur optional — viele bestehende Trips haben es moeglicherweise nicht gesetzt; die Report-Zeile entfaellt dann einfach

## Risiken

- **Minimal** — 2 Dateien, keine neuen API-Endpunkte, kein Schema-Aenderung
- Subscription-Fetch neu: wenn `/api/subscriptions` einen Fehler wirft, faellt es auf leeres Array zurueck — kein Crash

## Changelog

- 2026-04-18: Initial spec fuer Phase B (Startseite Kacheln)
