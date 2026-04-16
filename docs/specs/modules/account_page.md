---
entity_id: account_page
type: module
created: 2026-04-16
updated: 2026-04-16
status: implemented
version: "1.0"
tags: [sveltekit, auth, account, profile, f61]
---

# F61 — SvelteKit Account-Seite

## Approval

- [x] Approved

## Purpose

Neue `/account`-Route im SvelteKit-Frontend, auf der eingeloggte Nutzer ihre Kanal-Einstellungen (Report-E-Mail, Signal-Nummer, Telegram-ID) einsehen und bearbeiten koennen. Die Seite laedt das Profil ueber einen Server-Load-Aufruf und speichert Aenderungen via `PUT /api/auth/profile` an den bestehenden Go-Backend-Endpoint.

## Scope

### In Scope

- `frontend/src/routes/account/+page.server.ts` — Server Load: Profil mit Session-Cookie laden (NEU)
- `frontend/src/routes/account/+page.svelte` — Formular mit Profilfeldern, Speichern via `api.put()` (NEU)
- `frontend/src/routes/+layout.svelte` — Account-Link in Nav-Gruppe hinzufuegen (EDIT)

### Out of Scope

- Go-Backend (`GET /api/auth/profile`, `PUT /api/auth/profile`) — bereits implementiert, keine Aenderungen
- Passwort-Aenderung — separates Feature
- Account-Loeschung — UI bereits in F15 implementiert
- `signal_api_key` — write-only, wird nicht im GET zurueckgegeben; kein Eingabefeld in dieser Seite

## Source

- **File:** `frontend/src/routes/account/+page.server.ts` **(NEU)**
- **File:** `frontend/src/routes/account/+page.svelte` **(NEU)**
- **File:** `frontend/src/routes/+layout.svelte` **(EDIT)**
- **Identifier:** `load` (in `+page.server.ts`), `savePage` (in `+page.svelte`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/auth/profile` | Go API endpoint | Profil laden: `id`, `email`, `mail_to`, `signal_phone`, `telegram_chat_id`, `created_at` |
| `PUT /api/auth/profile` | Go API endpoint | Profil-Felder aktualisieren: `mail_to`, `signal_phone`, `telegram_chat_id` |
| `$lib/api.ts` | SvelteKit helper | `api.put()` fuer client-seitige PUT-Anfragen mit automatischer Cookie-Weiterleitung |
| `$lib/components/ui/card` | UI component | Card-Container, analog zu bestehenden Seiten |
| `$env/dynamic/private` | SvelteKit | `GZ_API_BASE` fuer Go-API-URL im Server-Load |
| `frontend/src/routes/+layout.svelte` | SvelteKit | `navGroups` Array — Account-Eintrag wird ergaenzt |

## Implementation Details

### Step 1: `frontend/src/routes/account/+page.server.ts` (NEU, ~15 LoC)

Muster analog zu `frontend/src/routes/settings/+page.server.ts`: Session-Cookie auslesen, fetch mit Cookie-Header, Daten zurueckgeben.

```typescript
import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
    const session = cookies.get('gz_session');
    const resp = await fetch(`${API()}/api/auth/profile`, {
        headers: { Cookie: `gz_session=${session}` },
    });
    if (!resp.ok) return { profile: null };
    const profile = await resp.json();
    return { profile };
};
```

### Step 2: `frontend/src/routes/account/+page.svelte` (NEU, ~100 LoC)

Formularstruktur:

- Nicht-editierbare Anzeige-Felder (read-only Text, kein Input):
  - "Benutzername" — `data.profile.id`
  - "Mitglied seit" — `data.profile.created_at` (formatiert als `DD.MM.YYYY`)

- Editierbare Felder (type="email" bzw. type="text"):
  - "E-Mail fuer Reports" — gebunden an `mail_to` (nicht `email`, das ist der Login-Name)
  - "Signal-Nummer" — gebunden an `signal_phone`
  - "Telegram-ID" — gebunden an `telegram_chat_id`

- Submit-Button "Speichern" — loest `save()`-Funktion aus

Zustandsverwaltung mit Svelte 5 Runes:

```typescript
let mailTo = $state(data.profile?.mail_to ?? '');
let signalPhone = $state(data.profile?.signal_phone ?? '');
let telegramChatId = $state(data.profile?.telegram_chat_id ?? '');
let successMsg = $state<string | null>(null);
let errorMsg = $state<string | null>(null);

async function save() {
    errorMsg = null;
    successMsg = null;
    try {
        await api.put('/api/auth/profile', {
            mail_to: mailTo,
            signal_phone: signalPhone,
            telegram_chat_id: telegramChatId,
        });
        successMsg = 'Profil gespeichert';
        setTimeout(() => (successMsg = null), 4000);
    } catch (e: unknown) {
        const body = (e as { detail?: string; error?: string });
        errorMsg = body?.detail ?? body?.error ?? 'Speichern fehlgeschlagen';
    }
}
```

Feedback-Banner:

- Erfolg (gruen): sichtbar wenn `successMsg !== null`, verschwindet nach 4 Sekunden automatisch
- Fehler (rot): sichtbar wenn `errorMsg !== null`, bleibt bis naechstem Speichern

UI-Struktur: Card-Container, Ueberschrift "Mein Konto", Sektion "Kanaele" mit den editierbaren Feldern — analog zu `locations/+page.svelte`.

### Step 3: `frontend/src/routes/+layout.svelte` (EDIT, +2 Zeilen)

In `navGroups` einen Eintrag fuer die Account-Seite in der passenden Gruppe ergaenzen:

```typescript
// In der bestehenden navGroups-Definition (Zeilen 69-87) wird ein Eintrag hinzugefuegt:
{ href: '/account', label: 'Konto', icon: User }
```

Das `User`-Icon wird aus `lucide-svelte` importiert (analog zu anderen Icons in der Datei).

## Expected Behavior

- **Input:** Eingeloggter Nutzer ruft `/account` auf; Browser sendet Session-Cookie automatisch mit
- **Output (Load):** Server laedt Profildaten und gibt `{ profile }` an die Seite; bei fehlgeschlagenem Fetch `{ profile: null }`
- **Output (Save):** Bei Erfolg gruener Banner "Profil gespeichert" fuer 4 Sekunden; aktualisierte Werte bleiben in den Feldern
- **Side effects:** Go-Backend aktualisiert die Profil-Felder in der Datenbank

### Fehlerszenarien

| Szenario | Verhalten |
|----------|-----------|
| Session abgelaufen / nicht eingeloggt | `hooks.server.ts` leitet bereits vor dem Load zu `/login` weiter |
| Go-Backend nicht erreichbar (Load) | `profile: null` — Seite zeigt leere Felder |
| Go-Backend Fehler (Save) | Roter Banner mit Fehlermeldung aus `detail` oder `error` Feld |
| Leeres `mail_to`-Feld | Go-Backend akzeptiert leere Strings; keine client-seitige Pflichtfeld-Validierung |

### Nicht zurueckgegebene Felder

`signal_api_key` ist write-only im Backend und wird im GET-Response nicht geliefert. Das Feld erscheint nicht auf der Account-Seite (separates Feature, falls benoetigt).

## Known Limitations

- `email` (Login-Name) ist nicht editierbar — dafuer waere ein separater Endpoint mit Passwort-Bestaetigung noetig
- Keine client-seitige Validierung der Signal-Nummer oder Telegram-ID (Format-Pruefung)
- Kein optimistisches UI-Update — Felder behalten ihren lokalen Wert, werden nicht vom Server-Response ueberschrieben

## Changelog

- 2026-04-16: Initial spec (F61 — SvelteKit Account-Seite, GitHub Issue #61)
- 2026-04-16: Implemented and approved — +page.server.ts, +page.svelte created; nav link added to +layout.svelte
