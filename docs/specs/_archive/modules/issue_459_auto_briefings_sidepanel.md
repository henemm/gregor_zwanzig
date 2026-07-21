---
entity_id: issue_459_auto_briefings_sidepanel
type: module
created: 2026-05-30
updated: 2026-05-30
status: implemented
version: "1.0"
issue: 459
tags: [sveltekit, frontend, compare, sidepanel, presets, auto-briefings, epic-246]
---

# Issue #459 — Orts-Vergleich · Auto-Briefings Sidepanel Frontend

## Approval

- [ ] Approved

## Purpose

Baut das rechte Sidepanel der `/compare`-Route von einer Subscription-Liste auf `ComparePreset`-Typen um: `AutoReportsOverview.svelte` lädt gespeicherte Vergleichs-Presets über `GET /api/compare/presets`, zeigt sie als Kacheln mit Zeitplan-Label und letztem Versand an und bietet einen Save-Dialog (`SavePresetDialog.svelte`) sowie einen manuellen Versand-Button pro Kachel. Das Sidepanel schließt damit den Auto-Briefing-Kreislauf des Orts-Vergleichs (Epic #246): Nutzer konfigurieren einmal einen Vergleich und erhalten danach automatisch oder manuell Briefings ohne erneute Eingabe.

## Source

- **Schicht:** Rein Frontend (SvelteKit). Kein Go-Backend-Change in diesem Issue — Backend-Endpoints werden von Issue #458 bereitgestellt.
- **Dateien (geändert):**
  - `frontend/src/lib/types.ts` — `ComparePreset`-Interface hinzufügen (+18 LoC)
  - `frontend/src/lib/components/compare/subscriptionHelpers.ts` — `presetScheduleLabel` + `formatLastSent` hinzufügen (+15 LoC)
  - `frontend/src/routes/compare/+page.server.ts` — `GET /api/compare/presets` laden (+7 LoC)
  - `frontend/src/lib/components/compare/AutoReportCard.svelte` — auf `ComparePreset` umbauen + Send-Button hinzufügen (~0 netto)
  - `frontend/src/lib/components/compare/AutoReportsOverview.svelte` — auf `ComparePreset`-Daten umbauen (+9 LoC netto)
  - `frontend/src/routes/compare/+page.svelte` — `onsavebriefing`-Prop entfernen (−3 LoC)
- **Dateien (neu):**
  - `frontend/src/lib/components/compare/SavePresetDialog.svelte` (~95 LoC)
  - `frontend/src/lib/components/compare/__tests__/issue_459_auto_briefings_sidepanel.test.ts` (~120 LoC)

> **Schicht-Zuordnung:** Ausschließlich `frontend/src/`. Kein Go-Backend (`api/`, `internal/`, `cmd/`), kein Python-Backend (`src/`).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Subscription` — `frontend/src/lib/types.ts` | TypeScript-Interface (vorhanden) | Bleibt unverändert für die Subscription-Seite; wird durch `ComparePreset` nicht ersetzt |
| `ActivityProfile` — `frontend/src/lib/types.ts` | TypeScript-Type (vorhanden) | Profil-Feld im `ComparePreset`-Interface |
| `subscriptionHelpers.ts` — `frontend/src/lib/components/compare/` | TypeScript-Modul (vorhanden, erweitern) | Bestehende `scheduleLabel`-Funktion bleibt; neue `presetScheduleLabel` + `formatLastSent` werden hinzugefügt |
| `CreateGroupDialog.svelte` — `frontend/src/lib/components/compare/` | Svelte-Komponente (Referenz-Pattern) | Dialog-Pattern: `bind:open`, `Dialog.Root`, `Dialog.Footer`, `api.post`, Error-Handling |
| `SavePresetDialog.svelte` (trip-detail) | Svelte-Komponente (Referenz-Pattern) | Dialog mit `api.post`-Pattern und `onSaved`-Callback |
| `AutoReportsOverview.svelte` — `frontend/src/lib/components/compare/` | Svelte-Komponente (vorhanden, Umbau) | Bestehende Komponente; wird auf `ComparePreset`-Typ umgebaut |
| `ui/dialog` — Design-System | Atom (vorhanden) | `Dialog.Root`, `.Content`, `.Header`, `.Title`, `.Footer` für `SavePresetDialog` |
| `ui/btn` — Design-System | Atom (vorhanden) | Buttons in Dialog und Kachel (Send-Button, Save-Button) |
| `ui/dot` — Design-System | Atom (vorhanden) | Status-Indikator in `AutoReportCard` |
| `ui/pill` — Design-System | Atom (vorhanden) | Zeitplan-Label-Darstellung in `AutoReportCard` |
| `ui/eyebrow` — Design-System | Atom (vorhanden) | Sidepanel-Abschnitts-Header |
| `ui/card` — Design-System | Atom (vorhanden) | Kachel-Wrapper für `AutoReportCard` |
| `lucide-svelte/icons/send` | Icon (vorhanden) | Send-Icon für manuellen Versand-Button |
| `lucide-svelte/icons/plus` | Icon (vorhanden) | Plus-Icon in `AddReportCard` (bleibt unverändert) |
| `api` — `frontend/src/lib/api.ts` | TypeScript-Modul (vorhanden) | `api.get`, `api.post` für Preset-Lade- und Speicher-Calls |
| `GET /api/compare/presets` | Go-Backend-Endpoint (geplant, #458) | Alle gespeicherten Presets laden; Fallback auf `[]` wenn #458 noch nicht live |
| `POST /api/compare/presets` | Go-Backend-Endpoint (geplant, #458) | Neues Preset anlegen (Save-Dialog) |
| `POST /api/compare/presets/{id}/send` | Go-Backend-Endpoint (geplant, #458) | Manuellen Versand eines Presets triggern |

## Implementation Details

### §1 `ComparePreset`-Interface in `types.ts`

```typescript
export interface ComparePreset {
  id: string;
  name: string;
  location_ids: string[];
  schedule: 'daily' | 'weekly' | 'manual';
  profil: ActivityProfile;
  hour_from: number;
  hour_to: number;
  empfaenger: string[];
  letzter_versand?: string;           // ISO-8601
  top_ort_letzter_versand?: string | null;
  created_at: string;
}
```

`Subscription` bleibt unverändert im selben File. `ComparePreset` wird direkt darunter eingefügt.

### §2 `subscriptionHelpers.ts` — neue Hilfsfunktionen

```typescript
// Zeitplan-Label für ComparePreset
export function presetScheduleLabel(preset: ComparePreset): string {
  if (preset.schedule === 'daily') {
    return `Täglich ${preset.hour_from}–${preset.hour_to} Uhr`;
  }
  if (preset.schedule === 'weekly') return 'Wöchentlich';
  return 'Manuell';
}

// Letzten Versand formatieren (deutsch, kurzes Datum)
export function formatLastSent(iso?: string | null): string {
  if (!iso) return 'Noch kein Versand';
  return new Date(iso).toLocaleDateString('de-DE', {
    day: '2-digit', month: '2-digit', year: 'numeric'
  });
}
```

Die bestehende `scheduleLabel`-Funktion (für `Subscription`) bleibt unverändert.

### §3 `+page.server.ts` — Presets laden

Im bestehenden `load`-Handler wird parallel zu den anderen Daten ein Preset-Fetch ergänzt:

```typescript
const presetsRes = await fetch(`${API_BASE}/api/compare/presets`, { ... })
  .then(r => r.ok ? r.json() : null)
  .catch(() => null);

return {
  // ...bestehende Felder...
  presets: presetsRes?.presets ?? []
};
```

Fehlerfall (Endpoint noch nicht live) gibt `[]` zurück — keine Ausnahme, kein Server-Error.

### §4 `AutoReportsOverview.svelte` — Umbau

**Props vorher:**
```typescript
let { subscriptions, onsavebriefing }: {
  subscriptions: Subscription[];
  onsavebriefing: () => void;
} = $props();
```

**Props nachher:**
```typescript
let { presets }: {
  presets: ComparePreset[];
} = $props();
```

- `onsavebriefing`-Prop entfällt. Dialog öffnet sich intern via `bind:open={saveDialogOpen}`.
- `saveDialogOpen: boolean = $state(false)` als interne State-Variable.
- Iteration über `presets` statt `subscriptions`.
- Leerzustand (`presets.length === 0`): Hinweistext `data-testid="auto-reports-empty"` wird gerendert.
- `SavePresetDialog` wird via `bind:open={saveDialogOpen}` eingebunden.

**Template-Struktur:**
```svelte
<div data-testid="auto-reports-overview">
  <Eyebrow>AUTO-BRIEFINGS</Eyebrow>

  {#if presets.length === 0}
    <p data-testid="auto-reports-empty">
      Noch keine Auto-Briefings gespeichert.
    </p>
  {/if}

  {#each presets as preset (preset.id)}
    <AutoReportCard {preset} />
  {/each}

  <AddReportCard onclick={() => saveDialogOpen = true} />

  <SavePresetDialog bind:open={saveDialogOpen} />
</div>
```

### §5 `SavePresetDialog.svelte` — neues Datei

Dialog folgt dem Pattern aus `CreateGroupDialog.svelte`:

```typescript
let { open = $bindable(false) }: { open: boolean } = $props();

let name = $state('');
let schedule: 'daily' | 'weekly' | 'manual' = $state('daily');
let hour_from = $state(9);
let hour_to = $state(16);
let empfaenger = $state('');  // kommaseparierter String
let saving = $state(false);
let error: string | null = $state(null);
```

**Felder:**
- `name`: `<input type="text">`, required, `data-testid="save-preset-name"`
- `schedule`: `<Select>`, Optionen `daily | weekly | manual`, `data-testid="save-preset-schedule"`
- `hour_from` / `hour_to`: `<input type="number">`, nur sichtbar wenn `schedule === 'daily'`, `data-testid="save-preset-hour-from"` / `"save-preset-hour-to"`
- `empfaenger`: `<textarea>`, kommasepariert, `data-testid="save-preset-empfaenger"`

**Submit-Handler:**
```typescript
async function handleSave() {
  saving = true;
  error = null;
  try {
    await api.post('/api/compare/presets', {
      name,
      schedule,
      hour_from: schedule === 'daily' ? hour_from : 0,
      hour_to:   schedule === 'daily' ? hour_to   : 0,
      empfaenger: empfaenger.split(',').map(e => e.trim()).filter(Boolean)
    });
    open = false;
  } catch (e) {
    error = (e as { error?: string }).error ?? 'Speichern fehlgeschlagen';
  } finally {
    saving = false;
  }
}
```

**Fehlerzustand:** `error` wird als `data-testid="save-preset-error"` unter dem Submit-Button angezeigt.

### §6 `AutoReportCard` — Send-Button

Der Send-Button macht den API-Call direkt intern (kein Callback nach oben):

```typescript
let sending = $state(false);
let sendError: string | null = $state(null);

async function handleSend() {
  sending = true;
  sendError = null;
  try {
    await api.post(`/api/compare/presets/${preset.id}/send`, {});
  } catch (e) {
    sendError = (e as { error?: string }).error ?? 'Versand fehlgeschlagen';
  } finally {
    sending = false;
  }
}
```

**Kachel-Inhalt:**
- Preset-Name als Kachel-Titel
- `presetScheduleLabel(preset)` als Pill
- `formatLastSent(preset.letzter_versand)` als Untertitel
- `top_ort_letzter_versand` (wenn vorhanden) als Dot-Label
- Send-Button mit `lucide/send`-Icon, `data-testid="auto-report-send-{preset.id}"`

### §7 `+page.svelte` — Anpassung

```svelte
<!-- vorher -->
<AutoReportsOverview
  subscriptions={data.subscriptions}
  onsavebriefing={handleSaveBriefing}
/>

<!-- nachher -->
<AutoReportsOverview presets={data.presets} />
```

`handleSaveBriefing`-Funktion und `goto('/compare/new')`-Aufruf werden aus der Page entfernt, sofern sie nur für `AutoReportsOverview` existierten. `PresetHeader` behält seinen `onsavebriefing`-Handler unverändert.

### §8 LoC-Budget

| Datei | Art | Δ LoC |
|-------|-----|-------|
| `frontend/src/lib/types.ts` | Änderung | +18 |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | Änderung | +15 |
| `frontend/src/routes/compare/+page.server.ts` | Änderung | +7 |
| `frontend/src/lib/components/compare/SavePresetDialog.svelte` | Neu | ~95 |
| `frontend/src/lib/components/compare/AutoReportCard.svelte` | Umbau | ~0 netto |
| `frontend/src/lib/components/compare/AutoReportsOverview.svelte` | Änderung | +9 |
| `frontend/src/routes/compare/+page.svelte` | Änderung | −3 |
| `frontend/src/lib/components/compare/__tests__/issue_459_auto_briefings_sidepanel.test.ts` | Neu | ~120 |
| **Summe** | | **~261 LoC** |

LoC-Override erforderlich: `workflow.py set-field loc_limit_override 300`

## Expected Behavior

- **Input:** `data.presets` (aus `+page.server.ts`, Typ `ComparePreset[]`). Bei noch nicht live geschaltetem Backend-Endpoint (#458) ist das Array leer — kein Fehler, Leerzustand wird angezeigt.
- **Output:**
  - Sidepanel zeigt alle gespeicherten Presets als Kacheln mit Name, Zeitplan-Label, letztem Versand und optionalem Gewinner-Ort.
  - Leerzustand rendert `data-testid="auto-reports-empty"` mit Hinweistext.
  - Save-Dialog öffnet sich bei Klick auf `AddReportCard`, speichert via `POST /api/compare/presets`.
  - Send-Button triggert `POST /api/compare/presets/{id}/send` und gibt Fehler lokal in der Kachel aus.
- **Side effects:**
  - `open`-Binding schließt `SavePresetDialog` nach erfolgreichem Speichern.
  - `sending`-State deaktiviert den Send-Button während des API-Calls.
  - `error`/`sendError` werden bei API-Fehlern in der jeweiligen Komponente angezeigt.

## Acceptance Criteria

**AC-1:** Given `GET /api/compare/presets` liefert eine Liste von Presets / When `AutoReportsOverview` gerendert wird / Then sind alle zurückgegebenen Presets als Kacheln mit Name und `presetScheduleLabel`-Pill sichtbar — `data-testid="auto-reports-overview"` enthält für jedes Preset genau eine Kachel mit dem korrekten Namen.
- Test: (populated after /tdd-red)

**AC-2:** Given der Nutzer klickt auf `AddReportCard` und füllt Name, Zeitplan und Empfänger aus / When er den Save-Button im Dialog betätigt / Then wird `POST /api/compare/presets` mit den eingegebenen Werten aufgerufen — `empfaenger` ist ein Array aus einzelnen Adressen (Split auf Komma, Trim, Leerstrings entfernt) und der Dialog schließt sich bei Erfolg.
- Test: (populated after /tdd-red)

**AC-3:** Given eine Preset-Kachel ist sichtbar / When der Nutzer den Send-Button (`data-testid="auto-report-send-{id}"`) klickt / Then wird `POST /api/compare/presets/{id}/send` aufgerufen — während des Calls ist der Button deaktiviert; bei Fehler erscheint eine Fehlermeldung direkt in der Kachel.
- Test: (populated after /tdd-red)

**AC-4:** Given `GET /api/compare/presets` gibt `[]` zurück (oder der Endpoint ist noch nicht live) / When `AutoReportsOverview` gerendert wird / Then ist `data-testid="auto-reports-empty"` sichtbar und enthält einen erklärendenHinweistext — keine Preset-Kacheln sind im DOM.
- Test: (populated after /tdd-red)

## Known Limitations

- **Backend #458 noch nicht live:** `GET /api/compare/presets` und `POST`-Endpoints existieren beim Zeitpunkt der Frontend-Implementierung noch nicht. Der `+page.server.ts`-Load-Handler degradiert graceful auf `[]` via `.catch(() => null)`. Save- und Send-Aktionen schlagen im Frontend mit einer Fehlermeldung fehl, die Komponenten bleiben aber stabil.
- **Kein Reload nach Speichern:** Nach erfolgreichem Speichern via `SavePresetDialog` wird die Preset-Liste nicht automatisch aktualisiert — ein Seitenreload ist nötig, bis `invalidateAll()` oder ein reaktiver Reload ergänzt wird. Folge-Issue auf Wunsch.
- **Kein Reload nach manuellem Versand:** `letzter_versand`-Feld auf der Kachel aktualisiert sich nicht nach einem erfolgreichen Send — erst nach Seitenreload. Folge-Issue auf Wunsch.
- **Keine Preset-Bearbeitung oder -Löschung:** Kacheln zeigen nur den aktuellen Zustand und ermöglichen manuellen Versand. Bearbeiten/Löschen ist nicht Teil von #459.

## Changelog

- 2026-05-30: Initial spec erstellt für Issue #459 (Auto-Briefings Sidepanel Frontend). `AutoReportsOverview` auf `ComparePreset` umgebaut, `SavePresetDialog` neu, `subscriptionHelpers` erweitert, Backend-Fallback auf `[]`. 8 Dateien (~261 LoC), rein Frontend. Sub-Issue von Epic #246.
