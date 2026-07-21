---
entity_id: issue_433_layout_dnd
type: module
created: 2026-05-29
updated: 2026-05-29
status: implemented
version: "1.0"
tags: [frontend, svelte, dnd, drag-and-drop, layout-editor, bucket-section, issue-433, epic-428]
---

# Issue #433 — Layout-Editor Drag-and-Drop

## Approval

- [ ] Approved

## Purpose

Ergänzt den Output-Layout-Editor (Wizard Step 4 und Trip-Detail Output-Tab) um echtes
Drag-and-Drop zum Umsortieren von Metriken innerhalb der Bucket-Listen. Die bestehenden
▲▼-Buttons bleiben als barrierefreier sekundärer Pfad erhalten; DnD erweitert die
Interaktion für Maus (Desktop) und Touch (Mobile). Die Änderung ist rein frontend-seitig
und nutzt die bereits im Projekt installierte Library `svelte-dnd-action`, deren Nutzungsmuster
aus `Step2Stages.svelte` direkt übertragen wird.

## Source

- **Schicht:** Reines Frontend (SvelteKit). Kein Go-Backend, kein Python-Backend.
- **Dateien (geändert, Bottom-Up-Reihenfolge):**
  - `frontend/src/lib/components/trip-detail/BucketSection.svelte` — Hauptänderung: dndzone + dndItems-State
  - `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` — Prop-Durchleitung `onDndReorder`
  - `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` — Consumer-Handler `onDndReorder`
  - `frontend/src/lib/components/trip-wizard/steps/Step4Layout.svelte` — Consumer-Handler `handleDndReorder`

## Dependencies

| Entity | Type | Zweck |
|--------|------|-------|
| `svelte-dnd-action` v0.9.69 — `node_modules/svelte-dnd-action` | npm-Library (bereits installiert) | `dndzone`-Direktive + `DndEvent`-Typ für Drag-and-Drop-Logik |
| `flip` — `svelte/animate` | Svelte-Built-in (vorhanden) | CSS-FLIP-Animation beim Umsortieren; `flipDurationMs: 200` konsistent mit Step2Stages |
| `Step2Stages.svelte` — `frontend/src/lib/components/trip-wizard/steps/` | Svelte-Komponente (vorhanden) | Referenz-Pattern für `dndzone`-Nutzung im Projekt |
| `EtappenStrip.svelte` — `frontend/src/lib/components/trip-detail/` | Svelte-Komponente (vorhanden) | Zweite bestehende `dndzone`-Nutzung im Projekt |
| `BucketSection.svelte` — `frontend/src/lib/components/trip-detail/` | Svelte-Komponente (geändert) | Haupt-Änderungsdatei: dndzone-Wrapper + `dndItems`-State + `onDndReorder`-Prop |
| `OutputLayoutEditor.svelte` — `frontend/src/lib/components/shared/` | Svelte-Komponente (geändert) | Prop-Durchleitung: neues `onDndReorder?`-Prop wird an BucketSection weitergeleitet |
| `WeatherMetricsTab.svelte` — `frontend/src/lib/components/trip-detail/` | Svelte-Komponente (geändert) | Consumer 1: `onDndReorder`-Handler ersetzt Bucket-Array direkt |
| `Step4Layout.svelte` — `frontend/src/lib/components/trip-wizard/steps/` | Svelte-Komponente (geändert) | Consumer 2: `handleDndReorder`-Handler aktualisiert `channelBuckets[activeChannel]` |
| `ActiveMetricRow.svelte` — `frontend/src/lib/components/trip-detail/` | Svelte-Komponente (vorhanden) | Wird als Kind in dndzone-Wrapper eingebettet (Wrapper-div nötig für `animate:flip`) |
| `metricsEditor.ts` — `frontend/src/lib/components/trip-detail/` | TypeScript-Modul (vorhanden) | `CHANNEL_COL_BUDGET` für `signalBudget`-Berechnung (bleibt korrekt, weil `dndItems` iteriert wird) |

## Implementation Details

### 1. `BucketSection.svelte` — Kern-Änderung

**Neue Imports:**

```typescript
import { dndzone, type DndEvent } from 'svelte-dnd-action';
import { flip } from 'svelte/animate';
```

**Neues Prop:**

```typescript
interface Props {
  // ... bestehende Props unverändert ...
  onDndReorder: (newOrder: string[]) => void;
}
```

**Lokaler DnD-State:**

```typescript
// dndzone braucht Array<{id: string|number}>.
// $effect (NICHT $derived!) synct items → dndItems, weil dndzone
// die Liste während der consider-Phase mit einem Phantom-Placeholder
// mutiert — $derived würde den Drag-Zustand nach jedem Reaktions-Tick
// zurücksetzen und den Drag abbrechen.
let dndItems = $state<{ id: string }[]>([]);

$effect(() => {
  dndItems = items.map((id) => ({ id }));
});
```

**Event-Handler:**

```typescript
function handleDndConsider(e: CustomEvent<DndEvent<{ id: string }>>) {
  dndItems = e.detail.items;
}

function handleDndFinalize(e: CustomEvent<DndEvent<{ id: string }>>) {
  dndItems = e.detail.items;
  onDndReorder(dndItems.map((x) => x.id));
}
```

**Template-Umbau (dndzone-Wrapper + animate:flip):**

```svelte
<div
  use:dndzone={{ items: dndItems, flipDurationMs: 200, dropTargetStyle: {} }}
  onconsider={handleDndConsider}
  onfinalize={handleDndFinalize}
>
  {#each dndItems as item, i (item.id)}
    <div animate:flip={{ duration: 200 }}>
      {#if bucket === 'primary' && i === signalBudget}
        <div class="signal-divider mono" data-testid="signal-divider">
          ↓ ab hier bei <strong>Signal</strong> automatisch als Detail-Zeile
          (max {signalBudget} Spalten)
        </div>
      {/if}
      {#if metricById[item.id]}
        <ActiveMetricRow
          metric={metricById[item.id]}
          short={shortById[item.id] ?? metricById[item.id].label.slice(0, 5)}
          {bucket}
          index={i}
          isFirst={i === 0}
          isLast={i === dndItems.length - 1}
          isOverLimit={bucket === 'primary' && i >= signalBudget}
          hasIndicator={indicatorCapable(item.id)}
          useIndicator={friendlyMap[item.id] ?? true}
          onMode={(v) => onMode(item.id, v)}
          onMove={(t) => onMove(item.id, t)}
          onReorder={(d) => onReorder(item.id, d)}
        />
      {/if}
    </div>
  {/each}
</div>
```

Wichtig: `animate:flip` muss auf dem direkten Kind-div von dndzone liegen, nicht auf
`<ActiveMetricRow>` selbst (Svelte-Constraint: animate-Direktive nur auf nativen Elementen).

Der Signal-Divider iteriert nach dem Umbau über `dndItems` statt `items` — der Index `i`
bleibt korrekt, weil `dndItems` die aktuelle (ggf. durch DnD verschobene) Reihenfolge
widerspiegelt.

---

### 2. `OutputLayoutEditor.svelte` — Prop-Durchleitung

**Neues Prop in der Props-Interface:**

```typescript
onDndReorder?: (bucket: 'primary' | 'secondary', newOrder: string[]) => void;
```

**Prop an BucketSection durchleiten (Standard-Branch, nicht SMS):**

```svelte
<BucketSection
  bucket="primary"
  ...
  onDndReorder={(newOrder) => onDndReorder?.('primary', newOrder)}
/>
<BucketSection
  bucket="secondary"
  ...
  onDndReorder={(newOrder) => onDndReorder?.('secondary', newOrder)}
/>
```

SMS-Branch bleibt unverändert — kein DnD, nur ▲▼-Buttons.

---

### 3. `WeatherMetricsTab.svelte` — Consumer-Handler

```typescript
function onDndReorder(bucket: 'primary' | 'secondary', newOrder: string[]) {
  buckets = { ...buckets, [bucket]: newOrder };
}
```

An `OutputLayoutEditor` übergeben:

```svelte
<OutputLayoutEditor
  ...
  onDndReorder={onDndReorder}
/>
```

---

### 4. `Step4Layout.svelte` — Consumer-Handler

```typescript
function handleDndReorder(bucket: 'primary' | 'secondary', newOrder: string[]) {
  channelBuckets = {
    ...channelBuckets,
    [activeChannel]: {
      ...channelBuckets[activeChannel],
      [bucket]: newOrder
    }
  };
}
```

An `OutputLayoutEditor` übergeben:

```svelte
<OutputLayoutEditor
  ...
  onDndReorder={handleDndReorder}
/>
```

---

### LoC-Budget

| Datei | Δ LoC (netto) |
|-------|--------------|
| `BucketSection.svelte` | +30 |
| `OutputLayoutEditor.svelte` | +8 |
| `WeatherMetricsTab.svelte` | +6 |
| `Step4Layout.svelte` | +8 |
| **Summe** | **~52 LoC** |

Kein LoC-Override nötig (Standard-Limit 250 ausreichend).

## Expected Behavior

- **Input:** Benutzer greift ein Metrik-Row in einem BucketSection-Bucket per Maus (Desktop) oder Touch (Mobile) und zieht es an eine andere Position innerhalb desselben Buckets.
- **Output:** Nach dem Loslassen (finalize) wird `onDndReorder` mit dem neuen `string[]`-Array der Metrik-IDs aufgerufen. Der Consumer (`WeatherMetricsTab` oder `Step4Layout`) ersetzt den Bucket-Array direkt — ohne weitere Konvertierung. Die `▲▼`-Buttons bleiben funktional und nutzen weiterhin den bestehenden `onReorder(id, dir)`-Pfad.
- **Side effects:** Während des Drags (consider-Phase) mutiert `dndzone` `dndItems` mit einem Phantom-Placeholder-Eintrag — dieser ist nur lokal in `BucketSection` sichtbar und wird nie nach außen propagiert. Cross-Bucket-Drag ist deaktiviert (dndzone-Default ohne `dropFromOthersDisabled`-Override ist ein separater Drop-Target je Instanz; da jeder Bucket eine eigene dndzone-Instanz ist, kann nicht zwischen Buckets gezogen werden). Die bestehende `onMove`-Logik bleibt der einzige Weg zum Cross-Bucket-Verschieben.

## Acceptance Criteria

**AC-1:** Given der Layout-Editor zeigt einen Bucket mit mindestens zwei Metriken auf einem Desktop-Browser /
When der User eine Metrik-Zeile mit der Maus greift und an eine andere Position im selben Bucket zieht und loslässt /
Then wird `onDndReorder` mit dem aktualisierten `string[]` aufgerufen und die Bucket-Liste in der UI zeigt die neue Reihenfolge — ohne Seiten-Reload und ohne Nutzung der ▲▼-Buttons.

**AC-2:** Given der Layout-Editor zeigt einen Bucket mit mindestens zwei Metriken auf einem Touch-Gerät (Mobile) /
When der User eine Metrik-Zeile mit dem Finger greift und an eine andere Position zieht und loslässt /
Then wird `onDndReorder` mit dem aktualisierten `string[]` aufgerufen und die Bucket-Liste zeigt die neue Reihenfolge — Touch-Drag funktioniert via `svelte-dnd-action`-Touch-Support ohne zusätzliche Konfiguration.

**AC-3:** Given der Layout-Editor zeigt einen Bucket /
When der User die ▲- oder ▼-Schaltfläche einer Metrik-Zeile klickt /
Then ändert sich die Reihenfolge über den bestehenden `onReorder(id, dir)`-Pfad — die ▲▼-Buttons sind weiterhin funktional und unverändert.

**AC-4:** Given der Output-Layout-Editor ist im SMS-Branch (`channel === 'sms'`) /
When der User die SMS-Ansicht öffnet /
Then ist kein dndzone-Element sichtbar und kein DnD-Interaktion möglich — der SMS-Branch nutzt ausschließlich ▲▼-Buttons (eigenständige UX, flache priorisierte Liste).

**AC-5:** Given zwei Buckets (primary und secondary) sind gleichzeitig sichtbar /
When der User eine Metrik aus dem primary-Bucket zieht /
Then kann die Metrik nur innerhalb des primary-Buckets abgelegt werden — Cross-Bucket-Drag per Maus/Touch ist nicht möglich; Cross-Bucket-Verschieben bleibt dem `onMove`-Button-Pfad vorbehalten.

**AC-6:** Given `BucketSection` erhält `items: string[]` als Prop /
When der Wert von `items` sich von außen ändert (z.B. nach `onDndReorder`-Callback) /
Then synct der `$effect`-Block `dndItems` auf den neuen Wert — `$derived` wird NICHT verwendet, weil `dndzone` während der consider-Phase den lokalen `dndItems`-Array mit einem Phantom-Placeholder mutiert und `$derived` diesen Zustand zerstören würde.

**AC-7:** Given der User zieht eine Metrik in einem Bucket um /
When das finalize-Event von `dndzone` ausgelöst wird /
Then enthält der `newOrder`-Array in `onDndReorder` die Metrik-IDs in der finalen Reihenfolge als `string[]` (nicht als `{id: string}[]`) — die Konvertierung `dndItems.map(x => x.id)` erfolgt in `handleDndFinalize` vor dem Callback.

**AC-8:** Given der primary-Bucket hat mehr als `CHANNEL_COL_BUDGET.signal` (5) Metriken /
When der User die Metriken per DnD umsortiert /
Then wird der Signal-Divider korrekt nach der fünften Metrik in der aktuellen Reihenfolge angezeigt — der Divider iteriert über `dndItems` (nicht `items`), sodass der Index nach dem Drag korrekt bleibt.

**AC-9:** Given `BucketSection` verwendet `animate:flip` /
When der User eine Metrik zieht und andere Metriken ausweichen /
Then läuft die FLIP-Animation mit `duration: 200` — konsistent mit dem in `Step2Stages.svelte` etablierten Muster; kein Standard-Drop-Target-Highlight (da `dropTargetStyle: {}` gesetzt ist).

**AC-10:** Given `WeatherMetricsTab` oder `Step4Layout` implementiert `onDndReorder` /
When `onDndReorder('primary', newOrder)` aufgerufen wird /
Then ersetzt der Handler den `buckets.primary`-Array per Spread-Zuweisung (`{ ...buckets, primary: newOrder }`) — die anderen Bucket-Felder (`secondary`, `off`) bleiben unverändert.

## Out of Scope

- SMS-Branch DnD — bewusst ausgeschlossen; SMS hat eigenständige UX (flache Liste, 140-Zeichen-Limit)
- Cross-Bucket-Drag (primary↔secondary per Drag) — bleibt dem `onMove`-Button-Pfad vorbehalten
- Drag-Handle-Icon in `ActiveMetricRow` — das gesamte Row ist Drag-Quelle; ein dediziertes Handle-Icon ist nicht Teil dieser Spec
- Keyboard-Drag-Unterstützung (ARIA-DnD) — `svelte-dnd-action` hat eingeschränkten Keyboard-Support; vollständige ARIA-DnD-Konformität ist ein separates Accessibility-Issue
- DnD in der `BucketSectionOff`-Sektion — Off-Metriken werden per Button in einen Bucket verschoben, kein DnD nötig

## Known Limitations

- `svelte-dnd-action` setzt während der consider-Phase einen Phantom-Placeholder-Eintrag in `dndItems`. Dieser Eintrag hat eine synthetische ID und kein entsprechendes `metricById`-Lookup. Der `{#if metricById[item.id]}` Guard in der Template-Schleife verhindert, dass der Placeholder eine sichtbare Zeile rendert — er bleibt unsichtbar, hält aber den Drop-Slot offen.
- `animate:flip` kann auf Svelte-Komponenten nicht direkt gesetzt werden (Svelte-Constraint); deshalb ist ein Wrapper-`<div>` um `<ActiveMetricRow>` nötig. Dieses Wrapper-div hat keine visuelle Bedeutung, erzeugt aber ein zusätzliches DOM-Element pro Zeile.
- Touch-DnD auf iOS Safari kann bei schnellem Scrollen gelegentlich mit dem nativen Scroll-Behavior kollidieren. `svelte-dnd-action` setzt `touch-action: none` auf Drag-Elemente; das ist established behavior für Touch-DnD und entspricht dem Referenz-Pattern in `Step2Stages.svelte`.

## Changelog

- 2026-05-29: Initial spec erstellt für Issue #433 (DnD in Layout-Editor). Rein frontend-seitig, nutzt bestehende `svelte-dnd-action`-Library. ▲▼-Buttons bleiben als sekundärer Pfad erhalten.
