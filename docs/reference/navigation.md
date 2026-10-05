# Navigation — Kanonisches URL-Modell

Dieses Dokument ist die verbindliche Referenz für URL-Navigation in der SvelteKit-Frontend-Schicht.

## ?tab= Konvention

Tab-State wird ausschließlich als Query-Parameter `?tab=<value>` kodiert, **niemals** als URL-Fragment (`#hash`).

Begründung: SvelteKit-SSR liest `#fragment` nicht aus — Query-Parameter sind server-seitig auswertbar, verlinkbar und werden korrekt in der Browser-History gespeichert.

## Valide Tab-Werte — Trip-Detail und Ortsvergleich-Detail (#2287)

Beide Hubs nutzen EINE gemeinsame Reiter-Tabelle: `frontend/src/lib/components/shared/subscriptionTabs.ts`
(`subscriptionTabs(kind)`, `resolveTab(kind, raw)`, `bereinigteTabAdresse()`, Tabelle `LEGACY`).

| Wert | Label | Hinweis |
|------|-------|---------|
| `uebersicht` | Übersicht | |
| `etappen` | Etappen & Wegpunkte | nur Trip |
| `orte` | Orte | nur Ortsvergleich |
| `wetter-metriken` | Wetter-Metriken | |
| `wertebereiche` | Wertebereiche | |
| `alarme` | Alarme | |
| `versand` | Versand | |
| `vorschau` | Vorschau | |

Alte Kennungen (`overview`, `stages`, `weather`, `alerts`, `briefings`, `preview`, `idealwerte`, `layout` …) werden weiter
angenommen und einmalig per `replaceState` auf die neue Kennung umgeschrieben. Unbekannte Werte fallen auf `uebersicht`
zurück. testids folgen den Kennungen, z. B. `trip-detail-tab-uebersicht`. Die Anlage-Editoren (`TripNewEditor`,
`CompareNewEditor`) nutzen dieselben Kennungen. `compare/compareTabsResolve.ts` und `wertebereicheTabId()` sind entfallen.

## goto-Muster (kanonisch)

```ts
void goto(`?tab=${value}`, { replaceState: true, noScroll: true, keepFocus: true });
```

- `replaceState: true` — verhindert History-Spam beim Tab-Wechsel
- `noScroll: true` — Scroll-Position bleibt erhalten
- `keepFocus: true` — Keyboard-Navigation bleibt intakt

## 301-Redirect-Konvention

Veraltete Routen leiten mit HTTP 301 auf die kanonische URL um.

**Referenzbeispiel:** `frontend/src/routes/trips/[id]/edit/+page.server.ts` redirectet auf `/trips/[id]` und reicht `?tab=` unverändert durch (Hub löst alte Kennungen selbst auf, #2287):

```ts
import { redirect } from '@sveltejs/kit';
export const load = ({ params, url }) => {
  const tab = url.searchParams.get('tab');
  throw redirect(307, tab ? `/trips/${params.id}?tab=${tab}` : `/trips/${params.id}`);
};
```

Neue Routen-Aliase folgen demselben Muster: 301 auf die kanonische `?tab=`-URL.

## Warum kein Hash?

SvelteKit-SSR liest `#fragment` nicht — Hash-Werte sind rein client-seitig und werden nicht an den Server übermittelt. Query-Parameter (`?tab=`) sind dagegen:
- Server-seitig auswertbar (für SSR und Load-Funktionen)
- Verlinkbar (andere Nutzer können direkt auf einen Tab verlinken)
- Korrekt in der Browser-History (Vor/Zurück-Navigation funktioniert)
