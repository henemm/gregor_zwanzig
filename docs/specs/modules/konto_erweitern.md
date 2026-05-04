---
entity_id: konto_erweitern
type: module
created: 2026-04-21
updated: 2026-04-21
status: draft
version: "1.0"
tags: [sveltekit, account, system-status, templates, channels, f76]
---

# F76 — Konto-Seite erweitern: System-Status, Wetter-Templates, SMS/Satellite-Platzhalter

## Approval

- [ ] Approved

## Purpose

Erweitert die bestehende `/account`-Seite um drei neue Abschnitte: System-Status (migriert aus der verwaisten Settings-Seite), eine read-only Anzeige der Wetter-Templates sowie disabled Platzhalter-Felder fuer SMS und Satphone in der Kanäle-Card. Gleichzeitig wird die Settings-Seite entfernt und der Layout-Menülink auf `/account#system-status` korrigiert.

## Scope

### In Scope

- `frontend/src/routes/account/+page.server.ts` — Loader auf 6 parallele API-Calls erweitern (EDIT, +18 LoC)
- `frontend/src/routes/account/+page.svelte` — 3 neue Cards + 2 Platzhalter-Inputs (EDIT, +130 LoC)
- `frontend/src/routes/+layout.svelte` — Anchor-Link System-Status korrigieren (EDIT, 1 Zeile)
- `frontend/src/routes/settings/+page.svelte` — Datei loeschen (-178 LoC); 301-Redirect in `+page.server.ts` bleibt erhalten

### Out of Scope

- Benutzerdefinierte Wetter-Templates (Phase B, deferred)
- SMS/Satphone-Backend (keine Go-Aenderungen)
- Aenderungen an der bestehenden `save()`-Funktion und deren Payload (SMS/Satellite werden nicht gesendet)
- `frontend/src/routes/settings/+page.server.ts` — bleibt als Redirect erhalten

## Source

- **File:** `frontend/src/routes/account/+page.server.ts` **(EDIT)**
- **File:** `frontend/src/routes/account/+page.svelte` **(EDIT)**
- **File:** `frontend/src/routes/+layout.svelte` **(EDIT)**
- **File:** `frontend/src/routes/settings/+page.svelte` **(DELETE)**
- **Identifier:** `load` (in `+page.server.ts`), bestehende `save()` und `deleteAccount()` (unveraendert)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/auth/profile` | Go API endpoint | Profil laden — bereits im Loader vorhanden |
| `GET /api/scheduler/status` | Go API endpoint | Scheduler-Jobs fuer System-Status-Card |
| `GET /api/health` | Go API endpoint | Service-Verfuegbarkeit fuer Verfuegbarkeits-Card |
| `GET /api/templates` | Go API endpoint | Wetter-Templates fuer read-only Templates-Card |
| `GET /api/trips` | Go API endpoint | Trip-Zaehler fuer Account-Stats-Card |
| `GET /api/subscriptions` | Go API endpoint | Abo-Zaehler fuer Account-Stats-Card |
| `GET /api/locations` | Go API endpoint | Location-Zaehler + Provider-Anzeige |
| `$lib/api.ts` | SvelteKit helper | `api.put()` / `api.del()` — unveraendert |
| `$lib/components/ui/card` | UI component | Card-Container fuer neue Sections |
| `$lib/components/ui/badge` | UI component | "Kommt bald"-Badges fuer Platzhalter-Felder |
| `$env/dynamic/private` | SvelteKit | `GZ_API_BASE` im Server-Loader |
| `frontend/src/routes/settings/+page.svelte` | SvelteKit | Quelldatei fuer Migration der System-Status-Cards |

## Implementation Details

### Step 1: Loader erweitern (`+page.server.ts`)

Den bestehenden Loader (1 API-Call) auf 6 parallele `Promise.all`-Calls erweitern. Jeder Call hat einen `.catch(() => null)`-Fallback, damit ein nicht erreichbarer Service die gesamte Seite nicht blockiert.

```typescript
import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
    const session = cookies.get('gz_session');
    const h = { headers: { Cookie: `gz_session=${session}` } };

    const [profile, scheduler, health, templates, trips, subscriptions, locations] =
        await Promise.all([
            fetch(`${API()}/api/auth/profile`, h).then(r => r.ok ? r.json() : null).catch(() => null),
            fetch(`${API()}/api/scheduler/status`, h).then(r => r.ok ? r.json() : null).catch(() => null),
            fetch(`${API()}/api/health`, h).then(r => r.ok ? r.json() : null).catch(() => null),
            fetch(`${API()}/api/templates`, h).then(r => r.ok ? r.json() : null).catch(() => null),
            fetch(`${API()}/api/trips`, h).then(r => r.ok ? r.json() : []).catch(() => []),
            fetch(`${API()}/api/subscriptions`, h).then(r => r.ok ? r.json() : []).catch(() => []),
            fetch(`${API()}/api/locations`, h).then(r => r.ok ? r.json() : []).catch(() => []),
        ]);

    return { profile, scheduler, health, templates, trips, subscriptions, locations };
};
```

### Step 2: System-Status-Cards migrieren (`+page.svelte`)

Die drei Cards aus `frontend/src/routes/settings/+page.svelte` (Deine Reports, Dein Account, Verfuegbarkeit) werden 1:1 nach `/account` uebertragen. Hilfsfunktionen `timeAgo()`, `formatNextRun()`, `getProvider()` und das `userJobs`-Mapping werden aus der Settings-Datei uebernommen und in den bestehenden `<script>`-Block integriert.

Der wrapper-`<div>` der migrierten Cards erhaelt `id="system-status"`, damit der Anchor-Link aus dem Layout funktioniert:

```html
<div id="system-status" class="space-y-6">
    <!-- Card: Deine Reports -->
    <!-- Card: Dein Account -->
    <!-- Card: Verfuegbarkeit -->
</div>
```

Einzige inhaltliche Anpassung: Der Link in "Benachrichtigungen" (`href="/account"`) wird zu `href="/account#kanaele"` geaendert, falls ein Anchor-Sprung gewuenscht ist — sonst unveraendert.

Reihenfolge der Cards auf der gesamten Seite nach der Migration:
1. Profil (besteht)
2. Kanäle (besteht, + Platzhalter)
3. Passwort aendern (besteht)
4. **System-Status-Abschnitt** (`id="system-status"`):
   - Deine Reports (migriert)
   - Dein Account — Zaehler + Benachrichtigungs-Badges + Wetter-Modelle (migriert)
   - Verfuegbarkeit (migriert)
5. **Wetter-Templates** (neu)
6. Gefahrenzone (besteht)

### Step 3: Wetter-Templates-Card (`+page.svelte`)

Neue read-only Card nach dem System-Status-Abschnitt. Zeigt alle Templates aus `data.templates` (Array) tabellarisch an. Keine Editiermoeglichkeit — Templates Phase A ist rein lesend.

```html
<Card.Root>
    <Card.Header>
        <Card.Title>Wetter-Templates</Card.Title>
        <Card.Description>Systemweite Report-Vorlagen (nur lesend)</Card.Description>
    </Card.Header>
    <Card.Content>
        {#if !data.templates || data.templates.length === 0}
            <p class="text-sm text-muted-foreground">Keine Templates verfügbar.</p>
        {:else}
            <div class="space-y-2">
                {#each data.templates as tpl}
                    <div class="flex items-center justify-between text-sm">
                        <span class="font-medium">{tpl.name}</span>
                        <span class="text-muted-foreground">{tpl.description ?? tpl.type ?? ''}</span>
                    </div>
                {/each}
            </div>
        {/if}
    </Card.Content>
</Card.Root>
```

Template-Objekt-Shape (aus `GET /api/templates`): `{ id, name, description?, type? }` — genaue Felder per API-Response; Fallback auf leeren String fuer optionale Felder.

### Step 4: SMS/Satellite-Platzhalter in der Kanaele-Card (`+page.svelte`)

Zwei disabled Inputs nach dem Telegram-Feld, vor dem Speichern-Button. Kein State, kein Binding, kein Einfluss auf `save()`.

```html
<div class="space-y-2">
    <label class="text-sm font-medium text-muted-foreground flex items-center gap-2">
        SMS-Nummer
        <Badge variant="secondary" class="text-xs">Kommt bald</Badge>
    </label>
    <input
        type="text"
        disabled
        placeholder="z.B. +43664..."
        class="flex h-10 w-full rounded-md border border-input bg-muted px-3 py-2 text-sm text-muted-foreground cursor-not-allowed"
    />
</div>

<div class="space-y-2">
    <label class="text-sm font-medium text-muted-foreground flex items-center gap-2">
        Satphone (Iridium)
        <Badge variant="secondary" class="text-xs">Kommt bald</Badge>
    </label>
    <input
        type="text"
        disabled
        placeholder="Iridium-Nummer"
        class="flex h-10 w-full rounded-md border border-input bg-muted px-3 py-2 text-sm text-muted-foreground cursor-not-allowed"
    />
</div>
```

`Badge` ist bereits in anderen Seiten importiert; muss in `+page.svelte` nachimportiert werden: `import { Badge } from '$lib/components/ui/badge/index.js';`

### Step 5: Layout-Menülink korrigieren (`+layout.svelte`)

Den bestehenden `href="/account"` des "System-Status"-Eintrags (Zeile ~180) auf `href="/account#system-status"` aendern:

```html
<!-- Vorher: -->
<a href="/account" ...>
    <MonitorIcon class="size-4 opacity-70" />
    System-Status
</a>

<!-- Nachher: -->
<a href="/account#system-status" ...>
    <MonitorIcon class="size-4 opacity-70" />
    System-Status
</a>
```

### Step 6: Settings-Seite loeschen

`frontend/src/routes/settings/+page.svelte` wird geloescht. Die zugehoerige `+page.server.ts` (301-Redirect zu `/account`) bleibt unveraendert, damit alte Links nicht brechen.

## Expected Behavior

- **Input:** Eingeloggter Nutzer ruft `/account` auf
- **Output (Load):** Server fuehrt 6 parallele API-Calls aus; alle fehlschlagenden Calls liefern `null` oder `[]`; Seite rendert fehlerfrei auch bei teilweise nicht erreichbaren Endpoints
- **Output (System-Status):** Drei Cards zeigen Report-Zeitplan, Account-Zaehler und Service-Verfuegbarkeit — identisch zur bisherigen Settings-Seite
- **Output (Wetter-Templates):** Read-only Liste der 7 Systemtemplates; bei leerem oder nicht erreichbarem Endpoint wird "Keine Templates verfuegbar" angezeigt
- **Output (Platzhalter):** SMS- und Satphone-Felder sind visuell ausgegraut, interaktionslos, mit Badge "Kommt bald"
- **Output (Anchor):** Klick auf "System-Status" im Layout-Menue springt direkt zum `id="system-status"`-Abschnitt
- **Side effects:** `save()` und `deleteAccount()` funktionieren unveraendert; SMS/Satellite werden nicht in den PUT-Payload aufgenommen

### Fehlerszenarien

| Szenario | Verhalten |
|----------|-----------|
| `/api/scheduler/status` nicht erreichbar | System-Status-Card zeigt "Report-Zeitplan nicht verfuegbar" |
| `/api/health` nicht erreichbar | Verfuegbarkeits-Card zeigt roten Dot + "Nicht erreichbar" |
| `/api/templates` nicht erreichbar | Templates-Card zeigt "Keine Templates verfuegbar" |
| `/api/trips` oder `/api/subscriptions` nicht erreichbar | Zaehler zeigen 0 (leere Arrays als Fallback) |
| Settings-URL `/settings` aufgerufen | 301-Redirect zu `/account` (via verbleibende `+page.server.ts`) |

## Known Limitations

- Wetter-Templates sind ausschliesslich lesend; benutzerdefinierte Templates werden in einem spaeteren Feature (Phase B) ergaenzt
- SMS- und Satphone-Felder sind reine UI-Platzhalter ohne Backend-Anbindung; kein Speichern moeglich
- Die Zaehler in der "Dein Account"-Card (Trips, Abos, Locations) aktualisieren sich nicht live — sie spiegeln den Stand beim Seitenaufruf wider

## Changelog

- 2026-04-21: Initial spec (F76 UX Redesign — Konto erweitern, GitHub Issue #76)
