---
entity_id: adhoc_to_abo
type: module
created: 2026-04-22
updated: 2026-04-22
status: draft
version: "1.0"
tags: [sveltekit, frontend, compare, subscriptions, ux]
---

# Ad-hoc → Abo — "Als Auto-Report speichern" auf der Vergleichs-Seite

## Approval

- [ ] Approved

## Purpose

Ergaenzt die `/compare`-Seite um einen "Als Auto-Report speichern"-Button, der nach einem erfolgreichen Vergleich sichtbar wird. Beim Klick oeffnet sich ein Dialog mit dem `SubscriptionForm`, das mit den aktuellen Vergleichs-Parametern vorbefuellt ist. Der Nutzer ergaenzt nur Name und Zeitplan, bestaetigt einmal und die Subscription wird direkt angelegt — ohne Umweg ueber die `/subscriptions`-Seite.

## Scope

### In Scope

- `frontend/src/routes/compare/+page.svelte` — Button + Dialog + Pre-Fill-Logik + POST-Handler **(EDIT, ~30 LoC)**
- `frontend/src/lib/components/SubscriptionForm.svelte` — Einzeilige Korrektur: leere `id`-Vorbelegung nicht als gueltige ID behandeln **(EDIT, 1 Zeichen)**

### Out of Scope

- Backend-Aenderungen — `POST /api/subscriptions` ist bereits vorhanden und akzeptiert das vollstaendige Modell
- Neue Subscription-Management-UI — CRUD bleibt auf `/subscriptions`
- Report-Typ-Auswahl pro Subscription (separates Feature)
- Toast-/Notification-System
- Fehlerbehandlung bei doppeltem Subscription-Namen

## Source

- **File:** `frontend/src/routes/compare/+page.svelte` **(EDIT)**
- **File:** `frontend/src/lib/components/SubscriptionForm.svelte` **(EDIT)**
- **Identifier:** `prefilledSub` (derived), `handleSaveAsSub` (handler), `showSaveAsSubDialog` (state)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `SubscriptionForm.svelte` | Svelte-Komponente | Wiederverwendbares Formular fuer Subscription-CRUD, akzeptiert `subscription`-Prop zur Vorbefuellung |
| `compare/+page.svelte` — State-Vars | Svelte-State | `selectedIds`, `twStart`, `twEnd`, `forecastHours`, `activityProfile` als Quelle fuer Pre-Fill |
| `POST /api/subscriptions` | REST-Endpunkt | Legt neue Subscription an; erwartet vollstaendiges CompareSubscription-JSON |
| shadcn `Dialog` | UI-Komponente | `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle` — bereits auf compare page importiert |
| `$lib/api.ts` — `api.post()` | SvelteKit helper | Client-seitige POST-Anfragen mit automatischer Cookie-Weiterleitung |
| `$lib/types.ts` — `Subscription` | TypeScript-Interface | Typdefinition fuer Pre-Fill-Objekt und POST-Body |

## Implementation Details

### Schritt 1: `SubscriptionForm.svelte` (EDIT, 1 Zeichen)

In der ID-Berechnung innerhalb des `save()`-Handlers:

```typescript
// Vorher
id: subscription?.id ?? toKebab(name)

// Nachher
id: subscription?.id || toKebab(name)
```

`??` prueft nur auf `null`/`undefined`. `||` behandelt zusaetzlich den leeren String `""` als falsy — notwendig, weil das Pre-Fill-Objekt `id: ''` uebergibt und der echte Wert erst aus dem Nutzernamen generiert werden soll.

### Schritt 2: `compare/+page.svelte` — Neuer State (EDIT)

```typescript
let showSaveAsSubDialog = $state(false);
let saveSubError = $state<string | null>(null);
```

### Schritt 3: `compare/+page.svelte` — Pre-Fill via $derived

```typescript
const prefilledSub = $derived<Partial<Subscription>>({
  id: '',
  name: '',
  enabled: true,
  schedule: 'daily_morning',
  time_window_start: twStart,
  time_window_end: twEnd,
  forecast_hours: forecastHours,
  activity_profile: activityProfile,
  locations: selectedIds.length === allLocationIds.length ? ['*'] : selectedIds,
  top_n: 3,
  include_hourly: false,
  send_email: true,
  send_signal: false,
  send_telegram: false,
});
```

`allLocationIds` ist die Liste aller verfuegbaren Location-IDs aus dem bestehenden `locations`-State der Seite. Falls alle ausgewaehlt sind, wird `['*']` verwendet (Backend-Konvention fuer "alle Orte").

### Schritt 4: `compare/+page.svelte` — POST-Handler

```typescript
async function handleSaveAsSub(sub: Subscription) {
  saveSubError = null;
  try {
    await api.post('/api/subscriptions', sub);
    showSaveAsSubDialog = false;
  } catch (e: unknown) {
    const body = e as { detail?: string; error?: string };
    saveSubError = body?.detail ?? body?.error ?? 'Speichern fehlgeschlagen';
  }
}
```

Nach erfolgreichem POST wird der Dialog geschlossen. Kein Reload der Seite noetig — die compare-Ergebnisse bleiben erhalten.

### Schritt 5: `compare/+page.svelte` — Button + Dialog (Markup)

Der Button erscheint innerhalb des `{#if result && !loading}`-Blocks, unterhalb der Ergebnis-Tabelle:

```svelte
{#if result && !loading}
  <!-- bestehende Ergebnis-Tabelle -->

  <button
    onclick={() => (showSaveAsSubDialog = true)}
    class="mt-4 text-sm text-blue-600 hover:underline"
  >
    Als Auto-Report speichern
  </button>
{/if}

<Dialog bind:open={showSaveAsSubDialog}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Als Auto-Report speichern</DialogTitle>
    </DialogHeader>
    <SubscriptionForm
      subscription={prefilledSub}
      locations={locations}
      onsave={handleSaveAsSub}
      oncancel={() => (showSaveAsSubDialog = false)}
    />
    {#if saveSubError}
      <p class="mt-2 text-sm text-red-600">{saveSubError}</p>
    {/if}
  </DialogContent>
</Dialog>
```

Der Dialog-Import ist bereits vorhanden. `SubscriptionForm` muss oben in der `<script>`-Sektion importiert werden.

## Expected Behavior

- **Input:** Nutzer hat einen Vergleich ausgefuehrt (result != null). Klick auf "Als Auto-Report speichern".
- **Output:** Dialog oeffnet sich mit vorbefuelltem SubscriptionForm. Nutzer gibt Name und optionalen Zeitplan ein, bestaetigt. POST an `/api/subscriptions` wird ausgefuehrt. Bei Erfolg: Dialog schliesst sich, Vergleichs-Ergebnis bleibt sichtbar. Bei Fehler: Fehlermeldung unterhalb des Formulars.
- **Side effects:** Eine neue Subscription wird in der Datenbank angelegt und erscheint beim naechsten Besuch von `/subscriptions` in der Liste.

### Pre-Fill-Mapping

| Compare-Parameter | Subscription-Feld | Fallback |
|---|---|---|
| `selectedIds` (alle) | `locations: ['*']` | — |
| `selectedIds` (Teilmenge) | `locations: selectedIds` | — |
| `twStart` | `time_window_start` | — |
| `twEnd` | `time_window_end` | — |
| `forecastHours` | `forecast_hours` | — |
| `activityProfile` | `activity_profile` | — |
| _(kein Aequivalent)_ | `name: ''` | Nutzer gibt Namen ein |
| _(kein Aequivalent)_ | `schedule: 'daily_morning'` | Sinnvoller Default |
| _(kein Aequivalent)_ | `top_n: 3` | Standard |
| _(kein Aequivalent)_ | `send_email: true` | Standard |

### Fehlerszenarien

| Szenario | Verhalten |
|----------|-----------|
| Nutzer schliesst Dialog ohne Speichern | Dialog schliesst sich, kein POST, Fehlerzustand wird zurueckgesetzt |
| POST schlaegt fehl (Netzwerk, 4xx, 5xx) | `saveSubError` wird gesetzt, Fehlermeldung rot unterhalb des Formulars |
| Name bereits vergeben | Backend antwortet mit Fehlermeldung, wird inline angezeigt |
| Kein Vergleich aktiv | Button nicht sichtbar (`{#if result && !loading}`) |

## Known Limitations

- Kein Erfolgs-Feedback nach dem Schliessen des Dialogs (kein Toast) — Nutzer muss `/subscriptions` besuchen um die neue Subscription zu bestaetigen. Akzeptabel fuer MVP.
- `allLocationIds` muss aus dem bestehenden `locations`-State der Seite abgeleitet werden — falls die Seite Locations lazy laedt, koennte der Vergleich "alle ausgewaehlt" falsch bewerten. Pruefe bei Implementierung ob `locations` zur Zeit des Klicks vollstaendig geladen ist.

## Changelog

- 2026-04-22: Initial spec (Ad-hoc → Abo)
