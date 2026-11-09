# Navigation — Kanonisches URL-Modell

Dieses Dokument ist die verbindliche Referenz für URL-Navigation in der SvelteKit-Frontend-Schicht.

## ?tab= Konvention

Tab-State wird ausschließlich als Query-Parameter `?tab=<value>` kodiert, **niemals** als URL-Fragment (`#hash`).

Begründung: SvelteKit-SSR liest `#fragment` nicht aus — Query-Parameter sind server-seitig auswertbar, verlinkbar und werden korrekt in der Browser-History gespeichert.

## Valide Tab-Werte — Trip-Detail und Ortsvergleich-Detail (#2287)

Beide Hubs nutzen EINE gemeinsame Reiter-Definition: `frontend/src/lib/components/shared/subscriptionTabs.ts`
(`REITER_DEFINITION`, `subscriptionTabs(kind)` für die Hub-Leiste, `anlegeKette(kind)` für die Anlege-Seiten,
`resolveTab(kind, raw)`, `bereinigteTabAdresse()`, Tabelle `LEGACY`). Es gibt keine zweite Reiterliste.

| Wert | Label | Hinweis |
|------|-------|---------|
| `uebersicht` | Übersicht | |
| `etappen` | Etappen & Wegpunkte | nur Trip |
| `orte` | Orte | nur Ortsvergleich |
| `wetter` | Wetter | bündelt Wetter-Metriken und Wertebereiche |
| `zustellung` | Zustellung | bündelt Versand (Briefing-Zeiten, Layout/Kanal, Stundenverlauf, Ausblick, Nachtblock; Anker `#versand`) und Alarme |

Seit Epic #2791 S3a Teil-PR 2 (2026-11-09) hat die Leiste **vier Reiter** (Trip und Ortsvergleich, gleiche Reihenfolge):
Übersicht · Etappen (Trip) bzw. Orte (Vergleich) · Wetter · Zustellung. „Zustellung" ist bis S3b ein Übergangsreiter
(ADR-0109). Die Speicherwege sind unverändert. Die früheren Reiter Wetter-Metriken, Wertebereiche, Alarme sind in
„Wetter" bzw. „Zustellung" aufgegangen; „Versand" und „Vorschau" waren bereits mit #1743 entfallen:

- **Versand** ist ein Abschnitt im Reiter Zustellung (Anker `#versand`, Baustein
  `shared/zustellung-tab/ZustellungTab.svelte` mit `shared/WetterMetrikenVersandPanel.svelte`, `context="route"|"vergleich"`).
  Beim Ortsvergleich steht dort zusätzlich die Aktivierungs-Karte (Pausieren/Aktivieren).
- **Vorschau** entfällt ersatzlos (samt Endpoint `GET /api/briefings/{id}/preview` und den verwaisten Resten
  `CompareChatBubble`/`CompareChannelSwitch`, PO-Entscheid 2026-10-22). Es bleibt nur die Alarm-Vorschau im Reiter
  Alarme (`POST /api/briefings/{id}/alert-preview`); weitere Kanal-Vorschauen gibt es in der Oberfläche nicht mehr.

Alte Kennungen (`overview`, `stages`, `weather`, `alerts`, `briefings`, `preview`, `versand`, `vorschau`, `idealwerte`, `layout`,
`wetter-metriken`, `wertebereiche`, `alarme`) werden weiter angenommen (Tabelle `LEGACY`; `weather`, `alerts`, `idealwerte`,
`layout`, `wetter-metriken`, `wertebereiche` → `wetter`; `alarme`, `briefings`, `versand` → `zustellung`; die kind-fremde
Punkte-Kennung `etappen`/`orte` wird auf die eigene umgeschrieben). Konkret:

- `versand`, `briefings` → `zustellung` mit Anker `#versand` (`?tab=zustellung#versand`); ein `#versand`-Anker gewinnt gegen den Reiter
- `vorschau`, `preview` → `uebersicht`

Die Adresse wird einmalig per `replaceState` auf die neue Kennung umgeschrieben. Unbekannte Werte fallen auf `uebersicht`
zurück. testids folgen den Kennungen, z. B. `trip-detail-tab-uebersicht`. Die Anlage-Editoren (`TripNewEditor`,
`CompareNewEditor`) nutzen dieselben Kennungen; die Anlege-Ketten heißen Route · Etappen · Wegpunkte · Wetter · Zustellung
(Trip) bzw. Vergleich · Orte · Wetter · Zustellung (Vergleich); „Fertig/Anlegen" wird nach dem Besuch von „Zustellung"
freigeschaltet. Optik: Desktop eine Grundlinie, aktiver Reiter Gewicht 600 mit 2px-Akzentunterstrich, Badges Mono 10px
neutral; mobil Pill-Form (`mobile/MTabBar.svelte`). `compare/compareTabsResolve.ts`
und `wertebereicheTabId()` sind entfallen.

## goto-Muster (kanonisch)

```ts
void goto(`?tab=${value}`, { replaceState: true, noScroll: true, keepFocus: true });
```

- `replaceState: true` — verhindert History-Spam beim Tab-Wechsel
- `noScroll: true` — Scroll-Position bleibt erhalten
- `keepFocus: true` — Keyboard-Navigation bleibt intakt

## Redirect-Konvention (307)

Veraltete Routen leiten per `redirect(307, …)` auf die kanonische URL um (Ist-Stand im Code beider
Beispielrouten; frühere Fassung dieses Dokuments nannte 301). Zweites Beispiel:
`frontend/src/routes/compare/[id]/edit/+page.server.ts` → `/compare/[id]` (Epic #1273 S3, ohne `?tab=`-Durchreichung).

**Referenzbeispiel:** `frontend/src/routes/trips/[id]/edit/+page.server.ts` redirectet auf `/trips/[id]` und reicht `?tab=` unverändert durch (Hub löst alte Kennungen selbst auf, #2287):

```ts
import { redirect } from '@sveltejs/kit';
export const load = ({ params, url }) => {
  const tab = url.searchParams.get('tab');
  throw redirect(307, tab ? `/trips/${params.id}?tab=${tab}` : `/trips/${params.id}`);
};
```

Neue Routen-Aliase folgen demselben Muster: 307 auf die kanonische `?tab=`-URL.

## Warum kein Hash?

SvelteKit-SSR liest `#fragment` nicht — Hash-Werte sind rein client-seitig und werden nicht an den Server übermittelt. Query-Parameter (`?tab=`) sind dagegen:
- Server-seitig auswertbar (für SSR und Load-Funktionen)
- Verlinkbar (andere Nutzer können direkt auf einen Tab verlinken)
- Korrekt in der Browser-History (Vor/Zurück-Navigation funktioniert)
