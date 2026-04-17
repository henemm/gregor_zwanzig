---
entity_id: account_page_extend
type: module
created: 2026-04-16
updated: 2026-04-16
status: draft
version: "1.0"
tags: [sveltekit, auth, account, signal, deletion, f72, f73]
---

# F72/F73 — Account-Seite erweitern: Signal API Key + Account-Loeschung

## Approval

- [ ] Approved

## Purpose

Erweitert die bestehende `/account`-Seite (`+page.svelte`) um zwei Funktionen: ein write-only Signal-API-Key-Eingabefeld fuer Callmebot-Benachrichtigungen (Issue #73) sowie eine "Gefahrenzone"-Sektion mit einem Account-Loeschungs-Button mit Bestaetigung (Issue #72). Beide Backends existieren bereits; diese Spec betrifft ausschliesslich die Frontend-Aenderungen.

## Source

- **File:** `frontend/src/routes/account/+page.svelte` **(EDIT, ~40 LoC hinzugefuegt)**
- **Identifier:** `save` (erweitert), `deleteAccount` (neu)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `PUT /api/auth/profile` | Go API endpoint | Nimmt `signal_api_key` als optionales Feld entgegen; das Feld wird zusammen mit den anderen Profilfeldern gesendet |
| `DELETE /api/auth/account` | Go API endpoint | Loescht den Account kaskadierend; invalidiert die Session serverseitig; erwartet keine Request-Body |
| `$lib/api.ts` — `api.put()` | SvelteKit helper | Fuer das Speichern des Profils inkl. `signal_api_key` |
| `$lib/api.ts` — `api.del()` | SvelteKit helper | Fuer den DELETE-Call zur Account-Loeschung |

## Implementation Details

### Aenderung 1: Signal API Key Feld (Issue #73)

Das Feld wird direkt unterhalb des bestehenden "Signal-Nummer"-Inputs in der "Kanaele"-Card eingefuegt.

**Neuer Svelte-5-State:**
```typescript
let signalApiKey = $state('');
// Bewusst kein Initialwert aus data.profile — Backend gibt den Key nie zurueck (write-only)
```

**Markup-Block** (nach dem `signal_phone`-Input, vor Telegram):
```html
<label class="block text-sm font-medium text-gray-700">Signal API Key</label>
<input
  type="password"
  bind:value={signalApiKey}
  placeholder="Callmebot API Key"
  class="mt-1 block w-full rounded-md border-gray-300 shadow-sm ..."
/>
<p class="mt-1 text-xs text-gray-500">Callmebot API Key fuer Signal-Benachrichtigungen</p>
```

**Erweiterung der `save()`-Funktion:** `signal_api_key` wird nur dann in den Request-Body aufgenommen, wenn das Feld nicht leer ist, um unbeabsichtigtes Ueberschreiben mit leerem String zu verhindern:
```typescript
const payload: Record<string, string> = {
    mail_to: mailTo,
    signal_phone: signalPhone,
    telegram_chat_id: telegramChatId,
};
if (signalApiKey !== '') {
    payload.signal_api_key = signalApiKey;
}
await api.put('/api/auth/profile', payload);
// Nach erfolgreichem Speichern: Feld wieder leeren (write-only Semantik)
signalApiKey = '';
```

### Aenderung 2: Account-Loeschung (Issue #72)

Eine neue Card-Sektion "Gefahrenzone" wird am Ende der Seite eingefuegt, nach dem "Speichern"-Button der Profil-Card und visuell von ihr getrennt.

**Markup-Block:**
```html
<Card.Root class="border-red-200">
  <Card.Header>
    <Card.Title class="text-red-700">Gefahrenzone</Card.Title>
  </Card.Header>
  <Card.Content>
    <p class="text-sm text-gray-600 mb-4">
      Das Loeschen deines Accounts ist unwiderruflich. Alle deine Daten werden
      permanent geloescht.
    </p>
    <button
      onclick={deleteAccount}
      class="bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-4 rounded-md"
    >
      Account loeschen
    </button>
    {#if deleteErrorMsg}
      <p class="mt-2 text-sm text-red-600">{deleteErrorMsg}</p>
    {/if}
  </Card.Content>
</Card.Root>
```

**Neuer State:**
```typescript
let deleteErrorMsg = $state<string | null>(null);
```

**Neue `deleteAccount()`-Funktion:**
```typescript
async function deleteAccount() {
    const confirmed = window.confirm(
        'Bist du sicher? Alle deine Daten werden unwiderruflich geloescht.'
    );
    if (!confirmed) return;

    try {
        await api.del('/api/auth/account');
        window.location.href = '/login';
    } catch (e: unknown) {
        const body = (e as { detail?: string; error?: string });
        deleteErrorMsg = body?.detail ?? body?.error ?? 'Loeschen fehlgeschlagen';
    }
}
```

Begruendung fuer `window.location.href` statt SvelteKit `goto()`: Der DELETE-Endpoint invalidiert die Session serverseitig. Ein Hard-Reload stellt sicher, dass der SvelteKit-Client-State vollstaendig zurueckgesetzt wird und kein veralteter Auth-Zustand im Speicher bleibt.

## Expected Behavior

- **Input (Signal API Key):** Nutzer gibt einen Callmebot API Key ein und klickt "Speichern". Das Feld ist nach dem Speichern leer (write-only). Ist das Feld bereits beim Speichern leer, wird `signal_api_key` nicht im PUT-Body gesendet.
- **Input (Account loeschen):** Nutzer klickt "Account loeschen", bestaetigt den `window.confirm`-Dialog.
- **Output (Signal API Key):** Key wird via `PUT /api/auth/profile` an das Backend gesendet. Erfolg- oder Fehlermeldung ueber den bestehenden `successMsg`/`errorMsg`-Mechanismus der Seite.
- **Output (Account loeschen):** Browser navigiert zu `/login` via Hard Redirect. Alle Nutzerdaten sind im Backend geloescht.
- **Side effects:** Go-Backend schreibt `signal_api_key` verschluesselt in die DB. Go-Backend loescht beim Account-Delete kaskadierend alle zugehoerigen Datensaetze und zerstoert die Session.

### Fehlerszenarien

| Szenario | Verhalten |
|----------|-----------|
| Nutzer bricht `window.confirm` ab | Funktion bricht ab, kein API-Call, kein Redirect |
| `DELETE /api/auth/account` liefert Fehler | `deleteErrorMsg` wird gesetzt, roter Hinweistext erscheint unterhalb des Buttons |
| `PUT /api/auth/profile` mit `signal_api_key` liefert Fehler | Bestehender `errorMsg`-Banner zeigt Fehlermeldung (roter Banner) |
| Signal-Feld ist leer beim Speichern | `signal_api_key` wird nicht in den Payload aufgenommen; bestehendes Backend-Key bleibt unveraendert |

## Known Limitations

- `window.confirm` ist ein nativer Browser-Dialog ohne Custom-Styling. Ein inline Bestaetigung (z.B. "Bestaetigen"-Schritt im UI) waere UX-freundlicher, ist aber nicht Teil dieses Scopes.
- Signal API Key wird nach dem Speichern geleert; der Nutzer erhaelt keine Bestaetigung ob ein Key bereits gespeichert ist (write-only by design).
- Kein Ladezustand ("wird geloescht...") waehrend des DELETE-Calls — bei schnellen Netzwerken nicht noetig, koennte bei langsamen Verbindungen kurz irritieren.

## Changelog

- 2026-04-16: Initial spec (F72 Account-Loeschung, F73 Signal API Key, GitHub Issues #72/#73)
