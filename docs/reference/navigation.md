# Navigation — Kanonisches URL-Modell

Dieses Dokument ist die verbindliche Referenz für URL-Navigation in der SvelteKit-Frontend-Schicht.

## ?tab= Konvention

Tab-State wird ausschließlich als Query-Parameter `?tab=<value>` kodiert, **niemals** als URL-Fragment (`#hash`).

Begründung: SvelteKit-SSR liest `#fragment` nicht aus — Query-Parameter sind server-seitig auswertbar, verlinkbar und werden korrekt in der Browser-History gespeichert.

## Valide Tab-Werte — Trip-Detail

| Wert | Label |
|------|-------|
| `overview` | Übersicht |
| `stages` | Etappen & Wegpunkte |
| `weather` | Wetter-Briefing |
| `briefings` | Reports & Kanäle |
| `alerts` | Alarmregeln |
| `preview` | Vorschau |

Unbekannte Werte fallen auf `overview` zurück.

## goto-Muster (kanonisch)

```ts
void goto(`?tab=${value}`, { replaceState: true, noScroll: true, keepFocus: true });
```

- `replaceState: true` — verhindert History-Spam beim Tab-Wechsel
- `noScroll: true` — Scroll-Position bleibt erhalten
- `keepFocus: true` — Keyboard-Navigation bleibt intakt

## 301-Redirect-Konvention

Veraltete Routen leiten mit HTTP 301 auf die kanonische URL um.

**Referenzbeispiel:** `frontend/src/routes/trips/[id]/edit/+page.server.ts` redirectet auf `/trips/[id]?tab=stages`:

```ts
import { redirect } from '@sveltejs/kit';
export const load = () => redirect(301, `/trips/${params.id}?tab=stages`);
```

Neue Routen-Aliase folgen demselben Muster: 301 auf die kanonische `?tab=`-URL.

## Warum kein Hash?

SvelteKit-SSR liest `#fragment` nicht — Hash-Werte sind rein client-seitig und werden nicht an den Server übermittelt. Query-Parameter (`?tab=`) sind dagegen:
- Server-seitig auswertbar (für SSR und Load-Funktionen)
- Verlinkbar (andere Nutzer können direkt auf einen Tab verlinken)
- Korrekt in der Browser-History (Vor/Zurück-Navigation funktioniert)
