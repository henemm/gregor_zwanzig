---
entity_id: issue_517_compare_hub
type: module
created: 2026-06-01
updated: 2026-06-01
status: draft
version: "1.0"
issue: 517
tags: [compare, frontend, svelte, detail-page, tabs, hub, epic-485]
---

# Issue #517 — Compare-Hub: Detail-Seite als 6-Tab-Hub

## Approval

- [ ] Approved

## Purpose

Wandelt die bestehende `/compare/[id]` Kachel-Grid-Seite in einen 6-Tab-Hub um, analog zum Trip-Hub (TripTabs.svelte). Der Hub ersetzt das Card-Grid-Layout durch eine Tab-Struktur mit den Reitern `Übersicht · Orte · Idealwerte · Layout · Versand · Vorschau`, damit Nutzer alle Aspekte eines Orts-Vergleichs ohne Seitennavigation erreichen können.

## Source

- **MODIFY:** `frontend/src/routes/compare/[id]/+page.svelte` — Page-Shell: liest `?tab=`-Query-Parameter und gibt `initialTab` an `CompareDetail` weiter (~135 LoC)
- **REPLACE:** `frontend/src/lib/components/compare/CompareDetail.svelte` — wird von ~126 LoC Card-Grid auf ~45 LoC Thin-Shell-Wrapper reduziert; delegiert an `CompareTabs`
- **NEW:** `frontend/src/lib/components/compare/CompareTabs.svelte` — Tab-Orchestrator mit 6 Tabs, URL-Sync via `history.replaceState` (~220 LoC)
- **NEW:** `frontend/src/lib/components/compare/__tests__/issue_517_compare_tabs.test.ts` — Quelltextprüf-Tests für alle Tab-Inhalte (~120 LoC)

> **Schicht-Zuordnung:** Ausschließlich Frontend `frontend/src/` (SvelteKit). Kein Go-API-Change, kein Python-Backend-Change. `+page.server.ts` bleibt unverändert.

## Estimated Scope

- **LoC:** ~520 netto (Override auf 550 vor Implementierungsstart: `workflow.py set-field loc_limit_override 550`)
- **Files:** 4
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ComparePreset` Interface (`frontend/src/lib/types.ts`) | intern | TypeScript-Typ mit `id`, `name`, `location_ids`, `schedule`, `profil`, `hour_from`, `hour_to`, `empfaenger`, `letzter_versand`, `display_config` |
| `Location` Interface (`frontend/src/lib/types.ts`) | intern | TypeScript-Typ mit `id`, `name`, `elevation_m`, `region` |
| `Segmented` atom (`frontend/src/lib/components/atoms/index.ts`) | intern | Tab-Selektor-Atom; IST-API: Props `options`, `selected`, `onselect` |
| `Dot`, `Pill`, `Card`, `Btn`, `Eyebrow`, `KV` (`frontend/src/lib/components/atoms/index.ts`) | intern | Atom-Komponenten für Monitoring-Streifen, Pills, Karten-Shell, Buttons |
| `CompareLocationRow` (`frontend/src/lib/components/compare/`) | intern | Orts-Zeile mit Rang, Name, Höhe — Stub aus #491, wird via Props `{loc}` und `{index}` angesprochen |
| `CompareIdealRow` (`frontend/src/lib/components/compare/`) | intern | Idealwerte-Zeile — Stub aus #491, Props: `item: { metric, range, weight }` |
| `CompareLayoutRow` (`frontend/src/lib/components/compare/`) | intern | Layout-pro-Kanal-Zeile — Stub aus #491, Props: `channel`, `cols` |
| `deriveStatusFromPreset` (`frontend/src/lib/subscriptionHelpers.ts`) | intern | Ableitung `active` / `paused` / `draft` aus Preset-Feldern |
| `presetScheduleLabel` (`frontend/src/lib/subscriptionHelpers.ts`) | intern | Formatierter Versand-Zeitplan, z.B. „Täglich 06–08 Uhr" |
| `formatLastSent` (`frontend/src/lib/subscriptionHelpers.ts`) | intern | Formatiert `letzter_versand` auf „TT.MM.JJJJ" oder „Noch kein Versand" |
| `page` (`$app/state`) | extern | SvelteKit Store; `page.url.searchParams.get('tab')` für Query-Parameter-Lesen |
| `history.replaceState` (Web-API) | extern | URL-Sync ohne Navigation: `?tab=VALUE` bei Tab-Wechsel schreiben |
| `TripTabs.svelte` (`frontend/src/lib/components/trip/TripTabs.svelte`) | intern | Referenz-Implementierung für Tab-Muster, Mobile-CSS (Pill-Scrollbar <900px) |
| `frontend/src/routes/compare/[id]/+page.server.ts` | intern | Bleibt unverändert; liefert `preset` + `locations` als PageData |
| `issue_491_compare_detail.test.ts` + `issue_493_compare_mobile.test.ts` + `compare_detail.test.ts` | intern | Bestehende Tests die nach dem Refactor grün bleiben müssen |

## Implementation Details

### §1 `CompareTabs.svelte` (neu, ~220 LoC)

**Props:**
```typescript
export let preset: ComparePreset;
export let locations: Location[];
export let initialTab: string = 'uebersicht';
```

**Tab-Definitionen:**
```typescript
const tabs = [
  { value: 'uebersicht', label: 'Übersicht' },
  { value: 'orte',       label: 'Orte' },
  { value: 'idealwerte', label: 'Idealwerte' },
  { value: 'layout',     label: 'Layout' },
  { value: 'versand',    label: 'Versand' },
  { value: 'vorschau',   label: 'Vorschau' },
];
let activeTab = initialTab;
```

**Tab-Wechsel mit URL-Sync:**
```typescript
function selectTab(value: string) {
  activeTab = value;
  const url = new URL(window.location.href);
  url.searchParams.set('tab', value);
  history.replaceState({}, '', url.toString());
}
```

**Rendering:**
```svelte
<Segmented options={tabs.map(t => t.label)} selected={activeTab} onselect={(v) => selectTab(tabs.find(t => t.label === v)?.value ?? 'uebersicht')} />
{#if activeTab === 'uebersicht'}...{/if}
{#if activeTab === 'orte'}...{/if}
{#if activeTab === 'idealwerte'}...{/if}
{#if activeTab === 'layout'}...{/if}
{#if activeTab === 'versand'}...{/if}
{#if activeTab === 'vorschau'}...{/if}
```

**Mobile CSS (<900px):** Pill-Scrollbar analog zu TripTabs.svelte (overflow-x: auto, white-space: nowrap, -webkit-overflow-scrolling: touch).

**Tab-Inhalte:**

**Tab 1 — Übersicht** (read-only):
- Monitoring-Streifen: Status-Dot + Label, „Nächster Versand" (`presetScheduleLabel(preset)`), „Zuletzt" (`formatLastSent(preset.letzter_versand)`), „Kanäle" (Anzahl `preset.empfaenger`)
- Summary: Region, Profil, Anzahl Orte
- Edit-Links als `<Btn>` mit `href`:
  - „Orte bearbeiten →" → `?tab=orte`
  - „Idealwerte bearbeiten →" → `?tab=idealwerte`
  - „Layout bearbeiten →" → `?tab=layout`
  - „Versand bearbeiten →" → `?tab=versand`

**Tab 2 — Orte** (Bearbeiten):
```typescript
const resolvedLocations = preset.location_ids.map((id, idx) => ({
  rank: idx + 1,
  loc: locations.find(l => l.id === id),
}));
```
Jede Zeile: `<CompareLocationRow {loc} index={rank} />`.
Footer-Link: „Im Wizard bearbeiten →" href `/compare/{preset.id}/edit`.

**Tab 3 — Idealwerte** (Bearbeiten):
```typescript
const idealRanges = preset.display_config?.ideal_ranges as
  Record<string, { min: number; max: number; unit?: string }> | undefined;
```
Iteriert `Object.entries(idealRanges ?? {})`:
```svelte
{#each Object.entries(idealRanges ?? {}) as [metric, r]}
  <CompareIdealRow item={{ metric, range: `${r.min}–${r.max}${r.unit ? ' ' + r.unit : ''}`, weight: 'mittel' }} />
{:else}
  <p>Keine Idealwerte konfiguriert.</p>
{/each}
```
Footer-Link: „Im Wizard bearbeiten →".

**Tab 4 — Layout** (Bearbeiten):
```typescript
const CHANNEL_COLS: Record<string, number> = {
  email: 99, telegram: 8, signal: 6, sms: 0
};
const channels = ['email', 'telegram', 'signal', 'sms'];
```
Jede Zeile: `<CompareLayoutRow channel={ch} cols={CHANNEL_COLS[ch]} />` (Email 99 wird als „∞ Spalten" angezeigt).
Footer-Link: „Im Wizard bearbeiten →".

**Tab 5 — Versand** (Bearbeiten):
- KV-Zeilen: Zeitplan (`presetScheduleLabel(preset)`), Zeitfenster (`preset.hour_from`–`preset.hour_to` Uhr), Profil (`preset.profil`)
- Empfänger: `{#each preset.empfaenger as e}<Pill>{e}</Pill>{/each}`
- Draft-Hinweis: `{#if deriveStatusFromPreset(preset) === 'draft'}<p>Noch nicht aktiv</p>{/if}`
- Footer-Link: „Im Wizard bearbeiten →".

**Tab 6 — Vorschau** (Placeholder):
- Statischer Text: „E-Mail-Vorschau folgt, sobald CompareEmail implementiert ist."
- Hinweis-Box: „Dein Briefing wird im Postfach gelesen — nicht hier."
- Button „Test-Briefing senden" → href `/compare/{preset.id}/edit` (vorläufig zum Wizard).

---

### §2 `CompareDetail.svelte` (ersetzen, ~45 LoC)

Wird von ~126 LoC auf Thin-Shell-Wrapper reduziert. Delegiert gesamten Inhalt an `CompareTabs`.

**Pflicht-Strings müssen im Script-Block oder als Kommentar erhalten bleiben** (bestehende Quelltext-Tests prüfen deren Existenz):
- `'Nächster Versand'`
- `'Zuletzt'`
- `'empfaenger'`
- `'location_ids'`
- `'elevation_m'`

```svelte
<script lang="ts">
  import type { ComparePreset } from '$lib/types';
  import type { Location } from '$lib/types';
  import CompareTabs from './CompareTabs.svelte';

  export let preset: ComparePreset;
  export let locations: Location[];
  export let initialTab: string = 'uebersicht';

  // Fields used in CompareTabs: 'Nächster Versand', 'Zuletzt', preset.empfaenger, preset.location_ids, loc.elevation_m
</script>

<CompareTabs {preset} {locations} {initialTab} />
```

---

### §3 `+page.svelte` (modifizieren, ~135 LoC)

Ergänzt das Lesen des `?tab=`-Query-Parameters:

```svelte
<script lang="ts">
  import { page } from '$app/state';
  // ... bestehende Imports ...

  export let data: PageData;

  $: initialTab = page.url.searchParams.get('tab') || 'uebersicht';
</script>

<!-- Desktop section: -->
<CompareDetail preset={data.preset} locations={data.locations} {initialTab} />

<!-- Mobile section: analog, ebenfalls {initialTab} übergeben -->
```

Desktop- und Mobile-Abschnitte bleiben strukturell unverändert (`issue_493_compare_mobile.test.ts` muss grün bleiben). `CompareIdealRow` und `CompareLayoutRow` dürfen in `+page.svelte` NICHT importiert werden (AC-9 prüft dies).

---

### §4 Test-Datei `issue_517_compare_tabs.test.ts` (neu, ~120 LoC)

Quelltextprüf-Tests (node:test-Stil, kein DOM-Rendering, kein Mock):

1. `CompareTabs.svelte` enthält alle 6 Tab-Values: `uebersicht`, `orte`, `idealwerte`, `layout`, `versand`, `vorschau`
2. `CompareTabs.svelte` enthält `history.replaceState`
3. `CompareTabs.svelte` enthält `CHANNEL_COLS` mit allen 4 Kanälen
4. `CompareTabs.svelte` enthält `Keine Idealwerte konfiguriert`
5. `CompareTabs.svelte` enthält `CompareEmail implementiert`
6. `CompareDetail.svelte` enthält alle 5 Pflicht-Strings (`Nächster Versand`, `Zuletzt`, `empfaenger`, `location_ids`, `elevation_m`)
7. `+page.svelte` enthält NICHT `CompareIdealRow` und NICHT `CompareLayoutRow`
8. `+page.svelte` enthält `searchParams.get('tab')`
9. `+page.svelte` enthält `initialTab`

---

### §5 LoC-Schätzung

| Datei | Änderung | LoC |
|-------|----------|-----|
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Neu | ~220 |
| `frontend/src/lib/components/compare/CompareDetail.svelte` | Ersetzen (126→45) | ~45 |
| `frontend/src/routes/compare/[id]/+page.svelte` | Modifizieren | ~135 |
| `frontend/src/lib/components/compare/__tests__/issue_517_compare_tabs.test.ts` | Neu | ~120 |
| **Summe** | | **~520 LoC netto** |

LoC-Override vor Implementierungsstart: `workflow.py set-field loc_limit_override 550`

## Expected Behavior

- **Input:**
  - `preset: ComparePreset` und `locations: Location[]` von `+page.server.ts` (unverändert)
  - Optional: `?tab=VALUE` in der URL (Default: `uebersicht`)
- **Output:**
  - Detail-Seite rendert 6 Tabs mit `Segmented`-Atom
  - Aktiver Tab steuert welcher Inhalt sichtbar ist (`{#if activeTab === ...}`)
  - Tab-Wechsel aktualisiert URL via `history.replaceState` ohne Seitennavigation
  - Alle 6 Tab-Inhalte entsprechen der Spezifikation (Übersicht read-only, Orte/Idealwerte/Layout/Versand mit Edit-Links, Vorschau als Placeholder)
  - Direktaufruf mit `?tab=versand` öffnet sofort den Versand-Tab
- **Side effects:**
  - `history.replaceState` schreibt `?tab=VALUE` in die Browser-URL bei jedem Tab-Wechsel
  - Keine API-Mutationen — reine Lese-Seite
  - Bestehende Tests (`issue_491_compare_detail.test.ts`, `issue_493_compare_mobile.test.ts`, `compare_detail.test.ts`) bleiben grün

## Acceptance Criteria

**AC-1:** Given die `/compare/{id}` Detail-Seite wird im Browser geöffnet / When die Seite geladen wird / Then rendert der Desktop-Bereich exakt 6 Tab-Reiter mit den Labels `Übersicht`, `Orte`, `Idealwerte`, `Layout`, `Versand`, `Vorschau` via `Segmented`-Atom.
  - Test: Quelltext-Check `CompareTabs.svelte` enthält alle 6 Strings `uebersicht`, `orte`, `idealwerte`, `layout`, `versand`, `vorschau` sowie den Import von `Segmented`.

**AC-2:** Given der `Übersicht`-Tab ist aktiv / When der Tab-Inhalt gerendert wird / Then ist der Monitoring-Streifen mit Status-Dot, „Nächster Versand", „Zuletzt" und Kanal-Anzahl sichtbar, und es gibt vier „Bearbeiten →"-Links die jeweils auf `?tab=orte`, `?tab=idealwerte`, `?tab=layout`, `?tab=versand` zeigen.
  - Test: Quelltext-Check `CompareTabs.svelte` enthält `Nächster Versand`, `Zuletzt`, `?tab=orte`, `?tab=idealwerte`, `?tab=layout`, `?tab=versand`.

**AC-3:** Given der `Orte`-Tab ist aktiv und `preset.location_ids` enthält N Einträge / When der Tab-Inhalt gerendert wird / Then rendert `CompareTabs.svelte` für jede ID eine `CompareLocationRow` mit Rang-Index (1-basiert), Orts-Name und Höhe (`elevation_m`) aus dem `locations`-Array.
  - Test: Quelltext-Check `CompareTabs.svelte` enthält `CompareLocationRow` und `location_ids` und `elevation_m`.

**AC-4:** Given der `Idealwerte`-Tab ist aktiv und `preset.display_config.ideal_ranges` enthält Einträge / When der Tab-Inhalt gerendert wird / Then rendert `CompareTabs.svelte` für jeden Eintrag eine `CompareIdealRow` mit Metrik-Name und formatiertem Wertebereich (`min–max unit`); bei leerem `ideal_ranges` erscheint „Keine Idealwerte konfiguriert."
  - Test: Quelltext-Check `CompareTabs.svelte` enthält `CompareIdealRow`, `ideal_ranges` und `Keine Idealwerte konfiguriert`.

**AC-5:** Given der `Layout`-Tab ist aktiv / When der Tab-Inhalt gerendert wird / Then rendert `CompareTabs.svelte` für die vier festen Kanäle (`email`, `telegram`, `signal`, `sms`) je eine `CompareLayoutRow` mit den Spaltenwerten Email ∞ (intern 99), Telegram 8, Signal 6, SMS 0.
  - Test: Quelltext-Check `CompareTabs.svelte` enthält `CompareLayoutRow`, `CHANNEL_COLS` und die Werte `99`, `8`, `6`, `0`.

**AC-6:** Given der `Versand`-Tab ist aktiv / When der Tab-Inhalt gerendert wird / Then zeigt `CompareTabs.svelte` den formatierten Zeitplan (`presetScheduleLabel`), Zeitfenster (`hour_from`–`hour_to` Uhr), Profil und alle Empfänger als Pills; bei Status `draft` erscheint zusätzlich „Noch nicht aktiv".
  - Test: Quelltext-Check `CompareTabs.svelte` enthält `presetScheduleLabel`, `hour_from`, `hour_to`, `empfaenger`, `Noch nicht aktiv`.

**AC-7:** Given der `Vorschau`-Tab ist aktiv / When der Tab-Inhalt gerendert wird / Then zeigt `CompareTabs.svelte` den statischen Placeholder-Text „E-Mail-Vorschau folgt, sobald CompareEmail implementiert ist." sowie den Hinweis „Dein Briefing wird im Postfach gelesen — nicht hier." und einen Button „Test-Briefing senden".
  - Test: Quelltext-Check `CompareTabs.svelte` enthält `CompareEmail implementiert ist` und `Postfach gelesen` und `Test-Briefing senden`.

**AC-8:** Given die URL enthält `?tab=versand` / When `+page.svelte` lädt / Then liest die Seite `page.url.searchParams.get('tab')` und übergibt `initialTab='versand'` an `CompareDetail`, wodurch der Versand-Tab direkt aktiv ist; bei Tab-Wechsel aktualisiert `history.replaceState` die URL auf `?tab=NEUER_WERT`.
  - Test: Quelltext-Check `+page.svelte` enthält `searchParams.get('tab')` und `initialTab`; `CompareTabs.svelte` enthält `history.replaceState` und `searchParams.set`.

**AC-9:** Given `cd frontend && npm run build` wird ausgeführt / When der TypeScript-Compiler `+page.svelte` prüft / Then enthält `+page.svelte` weder `CompareIdealRow` noch `CompareLayoutRow` als Import oder direkten Aufruf, und alle bestehenden Tests (`issue_491_compare_detail.test.ts`, `issue_493_compare_mobile.test.ts`, `compare_detail.test.ts`) laufen grün durch.
  - Test: Quelltext-Check `+page.svelte` enthält NICHT `CompareIdealRow` und NICHT `CompareLayoutRow`; `uv run pytest`-Äquivalent `cd frontend && node --test` für alle drei Testdateien ohne Fehler.

**AC-10:** Given ein mobiles Viewport (<900px) / When der Compare-Hub gerendert wird / Then sind die 6 Tab-Reiter in `CompareTabs.svelte` als horizontal scrollbare Pill-Band dargestellt (overflow-x: auto, analoges CSS zu TripTabs.svelte) ohne Zeilenumbruch.
  - Test: Quelltext-Check `CompareTabs.svelte` enthält `overflow-x` und `white-space: nowrap` im `<style>`-Block.

## Known Limitations

- **CompareEmail fehlt:** Der Vorschau-Tab ist ein statischer Placeholder. Die echte E-Mail-Vorschau mit Test-Versand folgt in einem separaten Folge-Issue.
- **`display_config` optional:** Wenn ein Preset kein `display_config` hat (ältere Daten), bleiben Idealwerte- und Layout-Tab mit leerem State — kein Fehler, nur leere Darstellung.
- **Edit-Links zeigen zum Wizard:** Alle „Im Wizard bearbeiten"-Links zeigen auf `/compare/{preset.id}/edit`. Ein inline-Editing direkt im Hub ist nicht Teil dieses Issues.
- **Segmented-API:** Verwendet IST-API (`options`/`selected`/`onselect`) des Segmented-Atoms. Bei zukünftiger API-Änderung des Atoms muss CompareTabs.svelte angepasst werden.
- **LoC-Override nötig:** Netto-LoC (~520) übersteigt das Default-Limit; `workflow.py set-field loc_limit_override 550` vor Implementierungsstart ausführen.

## Changelog

- 2026-06-01: Initial spec — Issue #517. Wandelt `/compare/[id]` Card-Grid in 6-Tab-Hub um (analog TripTabs.svelte): neuer CompareTabs.svelte-Orchestrator, CompareDetail.svelte als Thin-Shell, `?tab=`-URL-Sync in +page.svelte, 10 AC-N-Kriterien.
