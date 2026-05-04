---
entity_id: orts_vergleich_auto_reports
type: module
created: 2026-04-18
updated: 2026-04-18
status: draft
version: "1.0"
tags: [sveltekit, frontend, ux, f76, compare, subscriptions]
---

# F76 Phase C3 — Auto-Reports im Orts-Vergleich Content

## Approval

- [ ] Approved

## Purpose

Wenn kein Vergleich aktiv ist, zeigt der Content-Bereich der /compare Seite eine Uebersicht der aktiven Auto-Reports (Subscriptions) statt eines leeren Bereichs. Nur Anzeige, kein CRUD.

Teil des UX-Redesigns (#76), Eltern-Spec: `docs/specs/ux_redesign_navigation.md` Abschnitt 3 "Content: Default-Ansicht".

## Ist-Zustand

Content-Bereich zeigt nur:
- Einstellungen-Card (Datum, Zeitfenster, Profil, Button)
- Nach Vergleich: Ergebnis-Tabelle

Wenn kein Vergleich gelaufen ist, ist der Bereich unter den Einstellungen leer.

## Soll-Zustand

Wenn `result === null` (kein Vergleich gelaufen), zeige unterhalb der Einstellungen-Card:

```
Deine Auto-Reports
━━━━━━━━━━━━━━━━━━

┌──────────────────────────────┐
│ Ski Tirol Vergleich     ✓ An │
│ Täglich 07:00 · 3 Orte      │
│ Profil: Wintersport          │
└──────────────────────────────┘

┌──────────────────────────────┐
│ Surf Spots Check        ✗ Aus│
│ Wöchentlich Do · Alle Orte   │
│ Profil: Allgemein            │
└──────────────────────────────┘

Verwalten → /subscriptions
```

Nach einem Vergleich: Auto-Reports verschwinden, Ergebnis-Tabelle erscheint (wie bisher).

## Source

- **File:** `frontend/src/routes/compare/+page.server.ts` **(EDIT, +8 LoC)**
- **File:** `frontend/src/routes/compare/+page.svelte` **(EDIT, ~70 LoC)**

## Aenderungen im Detail

### 1. Server-Loader erweitern (+page.server.ts)

Subscriptions zusaetzlich laden (parallel zu Locations):

```typescript
const [locsRes, subsRes] = await Promise.all([
  fetch(`${API()}/api/locations`, { headers }).catch(() => null),
  fetch(`${API()}/api/subscriptions`, { headers }).catch(() => null)
]);
const subscriptions = subsRes?.ok ? await subsRes.json() : [];
return { locations, subscriptions };
```

### 2. Auto-Reports Section im Content (+page.svelte)

Neuer Block zwischen Einstellungen-Card und Ergebnis-Tabelle:

```svelte
{#if !result && !loading}
  <!-- Auto-Reports Uebersicht -->
  {#if subscriptions.length > 0}
    <h2>Deine Auto-Reports</h2>
    {#each subscriptions as sub}
      <Card> Name, Schedule, Location-Count, Enabled-Badge </Card>
    {/each}
    <a href="/subscriptions">Verwalten →</a>
  {/if}
{/if}
```

### 3. Subscriptions State

```typescript
import type { Subscription } from '$lib/types.js';
let subscriptions: Subscription[] = $state(data.subscriptions);
```

### 4. Helper-Funktionen

Aus /subscriptions uebernehmen (inline, nicht als shared module):
- `scheduleLabel(sub)` — "Taeglich 07:00", "Woechentlich Montag"
- `locationsLabel(sub, locations)` — "3 Orte" oder "Alle"

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ux_redesign_navigation` | spec | Eltern-Spec |
| `orts_vergleich_master_detail` | spec | C1: Layout bereits implementiert |
| `compare/+page.server.ts` | file | Subscriptions zusaetzlich laden |
| `compare/+page.svelte` | file | Auto-Reports Section einfuegen |
| `$lib/types.ts` | types | Subscription interface |

## Was sich NICHT aendert

- Compare-Logik (runComparison, Ergebnis-Tabelle)
- Sidebar (Locations-Checkboxen)
- /subscriptions Seite (bleibt fuer CRUD)
- API-Endpunkte
- LocationForm Dialog

## Expected Behavior

- **Kein Vergleich aktiv:** Auto-Reports Cards sichtbar unterhalb der Einstellungen
- **Vergleich gelaufen:** Auto-Reports verschwinden, Ergebnis-Tabelle erscheint
- **Keine Subscriptions:** Kein Auto-Reports Block (kein Empty-State noetig)
- **Link "Verwalten":** Fuehrt zu /subscriptions fuer CRUD

## Known Limitations

- Nur Anzeige, kein Create/Edit/Delete (bleibt auf /subscriptions)
- Kein "letztes Ergebnis" oder "naechster Lauf" — das braucht Backend-Erweiterung (separate Phase)
- scheduleLabel/locationsLabel werden dupliziert statt geteilt — akzeptabel fuer 2 Funktionen

## Changelog

- 2026-04-18: Initial spec fuer Phase C3
