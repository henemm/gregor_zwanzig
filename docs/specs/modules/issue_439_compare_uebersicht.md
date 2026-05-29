---
entity_id: issue_439_compare_uebersicht
type: module
created: 2026-05-29
updated: 2026-05-29
status: implemented
version: "1.0"
issue: 439
tags: [compare, subscriptions, frontend, svelte, table, overview, epic-438]
---

# Issue #439 — Orts-Vergleich Übersichtsseite `/compare`

## Approval

- [ ] Approved

## Purpose

Ersetzt die bestehende `/compare`-Seite (interaktiver Vergleichsrechner) durch eine tabellarische Übersicht aller gespeicherten Orts-Vergleiche (Subscriptions), analog zum `/trips`-Muster. Die neue Seite dient als zentraler Einstiegspunkt für den Orts-Vergleich-Bereich innerhalb von Epic #438 und ermöglicht das Verwalten (Pause/Play, Bearbeiten, Löschen) gespeicherter Vergleichs-Konfigurationen auf einen Blick.

## Source

- **REPLACE:** `frontend/src/routes/compare/+page.svelte` — wird vollständig neu geschrieben (~70 LoC): Page-Shell mit Header, Stats-Row, Search-Pill, delegiert Tabelle an `CompareList`
- **NEW:** `frontend/src/lib/components/compare/CompareList.svelte` — Tabellen-Skelett, gefilterte Zeilen, Dialog-State (Löschen bestätigen, Send-Stub, Preview-Stub), Toggle-Logik, Fehler-State (~140 LoC)
- **NEW:** `frontend/src/lib/components/compare/CompareRow.svelte` — eine `<Table.Row>` mit Status-Dot, Name/Pill/Region, Orte-Anzahl, Profil, Kanal-Pills, Versand, Aktionen (~70 LoC)

> **Schicht-Zuordnung:** Rein Frontend (`frontend/src/`). Kein Backend-Change — `+page.server.ts` lädt `subscriptions` bereits via `GET /api/subscriptions`. Status-Ableitung (`active`/`paused`/`draft`) geschieht ausschließlich im Frontend aus `enabled` + Vollständigkeit des Datensatzes.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `+page.server.ts` (`frontend/src/routes/compare/+page.server.ts`) | intern | SSR-Loader; lädt `subscriptions: Subscription[]` bereits — keine Änderung erforderlich |
| `Subscription` Interface (`frontend/src/lib/types.ts`) | intern | TypeScript-Typ mit `id`, `name`, `enabled`, `locations`, `schedule`, `weekday`, `time_window_start`, `send_email`, `send_signal`, `send_telegram`, `activity_profile?`, `last_run?`, `last_status?` |
| `GET /api/subscriptions` (`internal/handler/subscription.go`) | intern | Liefert `Subscription[]` für den eingeloggten User |
| `PUT /api/subscriptions/{id}` (`internal/handler/subscription.go`) | intern | Full-Replace für Pause/Play-Toggle: `{ ...sub, enabled: !sub.enabled }` |
| `DELETE /api/subscriptions/{id}` (`internal/handler/subscription.go`) | intern | Löscht Subscription; erwartet 204 |
| `subscriptionHelpers.ts` (`frontend/src/lib/`) | intern | `scheduleLabel()`, `locationsLabel()`, `formatLastRun()` — Formatierungsfunktionen für Tabellenspalten |
| `Btn`, `Pill`, `Dot`, `Eyebrow`, `Input` (`frontend/src/lib/components/atoms/index.ts`) | intern | Atom-Komponenten für Header, Stats-Row, Search, Status-Pill |
| `Table.*` (`frontend/src/lib/components/ui/table/index.js`) | intern | Tabellen-Primitives (`Table.Root`, `Table.Header`, `Table.Row`, `Table.Cell` etc.) |
| `Dialog.*` (`frontend/src/lib/components/ui/dialog/index.js`) | intern | Confirm-Dialog für Löschen-Aktion |
| `EmptyState` (`frontend/src/lib/components/ui/empty-state/index.js`) | intern | Leer-Zustand für 0 Subscriptions und 0 Suchergebnisse |
| `PauseIcon`, `PlayIcon`, `EyeIcon`, `SendIcon`, `PencilIcon`, `Trash2Icon`, `SearchIcon` (`@lucide/svelte/icons/...`) | extern | Aktions-Ikonographie |
| `goto` (`$app/navigation`) | intern | Client-seitige Navigation zu `/compare/new` und `/compare/{id}/edit` |
| `trips/+page.svelte` (`frontend/src/routes/trips/+page.svelte`) | intern | Pattern-Referenz für Eyebrow/H1/Stats-Row/Search/Table/Actions/EmptyState/Delete-Dialog |

## Implementation Details

### §1 `+page.svelte` — Page-Shell

```svelte
<script lang="ts">
  import type { PageData } from './$types';
  export let data: PageData;
  // data.subscriptions: Subscription[]
</script>

<!-- Header -->
<Eyebrow>WORKSPACE · ORTS-VERGLEICHE</Eyebrow>
<h1>Orts-Vergleiche</h1>
<p class="intro">Übersicht über alle gespeicherten Orts-Vergleiche.</p>
<Btn variant="accent" href="/compare/new">+ Neuer Vergleich</Btn>

<!-- Stats-Row (desktop, ungefilterter Bestand) -->
<span style:color="var(--g-accent)">{activeCount} Aktiv</span>
<span>{pausedCount} Pausiert</span>
<span>{draftCount} Drafts</span>

<!-- Tabelle + Search via CompareList -->
<CompareList subscriptions={data.subscriptions} />
```

Counts werden aus `data.subscriptions` per `deriveStatus()` berechnet — keine separaten API-Calls.

### §2 Status-Ableitung (Frontend-only)

```ts
const STATUS_MAP = {
  active: { label: 'aktiv',    dot: 'var(--g-accent)' },
  paused: { label: 'pausiert', dot: 'var(--g-ink-3)'  },
  draft:  { label: 'draft',    dot: 'var(--g-ink-4)'  },
};

function deriveStatus(sub: Subscription): 'active' | 'paused' | 'draft' {
  if (!sub.name || sub.locations.length === 0) return 'draft';
  if (!sub.enabled) return 'paused';
  return 'active';
}
```

Kein Backend-Feld `status` — Ableitung rein aus `enabled` + Vollständigkeit.

### §3 `CompareList.svelte` — Tabellen-Skelett

**Props:** `subscriptions: Subscription[]`

**Lokaler State:**
- `search: string` — für Case-insensitive Name-Filter
- `items: Subscription[]` — reaktiv aus `subscriptions.filter(s => s.name.toLowerCase().includes(search.toLowerCase()))`
- `deleteTarget: Subscription | null` — für Confirm-Dialog
- `sendTarget: Subscription | null` — für Send-Stub-Dialog
- `previewTarget: Subscription | null` — für Preview-Stub-Dialog

**Pause/Play-Toggle (optimistic):**
```ts
async function toggleEnabled(sub: Subscription) {
  // 1. Lokales Array sofort mutieren
  items = items.map(s => s.id === sub.id ? { ...s, enabled: !s.enabled } : s);
  // 2. API-Call (full replace)
  await fetch(`/api/subscriptions/${sub.id}`, {
    method: 'PUT',
    body: JSON.stringify({ ...sub, enabled: !sub.enabled }),
  });
  // 3. Bei Fehler: Revert + Fehlermeldung
}
```

**Delete-Flow:**
```ts
async function confirmDelete() {
  await fetch(`/api/subscriptions/${deleteTarget!.id}`, { method: 'DELETE' });
  items = items.filter(s => s.id !== deleteTarget!.id);
  deleteTarget = null;
}
```

**Empty States:**
- `items.length === 0 && !search` → `<EmptyState>` mit CTA-Button „+ Neuer Vergleich" → `/compare/new`
- `items.length === 0 && search` → Inline-Text: „Keine Vergleiche für »{search}« gefunden."

**Tabellenspalten:** Name · Orte · Profil · Kanäle · Versand · Aktionen

### §4 `CompareRow.svelte` — Tabellenzeile

**Props:** `sub: Subscription`

**Spalte „Name":**
- Status-Dot: `<span style:background={STATUS_MAP[deriveStatus(sub)].dot} />` (Inline-Style, nicht `Dot tone` — `Dot` hat keine accent/ink-3/ink-4-Tones)
- Name (fett)
- Status-Pill: `<Pill>{STATUS_MAP[deriveStatus(sub)].label}</Pill>`
- Sub-Text: Region (wenn vorhanden aus `sub.locations`)

**Spalte „Orte":** `locationsLabel(sub.locations)` (z.B. „3 Orte")

**Spalte „Profil":** `sub.activity_profile?.name ?? '—'`

**Spalte „Kanäle":** Pills für jeden aktiven Kanal:
- `send_email` → `<Pill>E-Mail</Pill>`
- `send_signal` → `<Pill>Signal</Pill>`
- `send_telegram` → `<Pill>Telegram</Pill>`
- (Kein SMS — `CompareSubscription` hat kein `send_sms`-Feld)

**Spalte „Versand":**
- `scheduleLabel(sub)` (z.B. „tgl. 06:30" oder „Sa 06:00")
- Sub-Text: `formatLastRun(sub.last_run)` (z.B. „Zuletzt: 28.05.2026, 06:00") oder leer wenn undefined

**Spalte „Aktionen"** (Buttons: 30×30, `border: 1px solid var(--g-rule-soft)`, `border-radius: var(--g-r-2)`):
1. **Pause/Play:** `PauseIcon` wenn `enabled`, `PlayIcon` wenn pausiert → `on:click={() => dispatch('toggle', sub)}`
2. **Send:** `SendIcon` → öffnet Send-Stub-Dialog (kein API-Endpoint vorhanden → Modal mit „Funktion folgt in #440")
3. **Preview:** `EyeIcon` → öffnet Preview-Stub-Dialog (analog zu Send)
4. `|` visueller Separator
5. **Edit:** `PencilIcon` → `goto(\`/compare/${sub.id}/edit\`)`
6. **Delete:** `Trash2Icon` → `dispatch('delete', sub)` (öffnet Confirm-Dialog in `CompareList`)

### §5 Bestehende Tests

`frontend/src/lib/issue_390_compare_atomic_migration.test.ts` und `frontend/src/lib/components/compare/__tests__/issue_390_atomic_migration.test.ts` referenzieren Interna der alten `/compare`-Seite. Bei Implementierung prüfen ob Tests noch valide — ggf. auf neue Komponenten-Struktur anpassen oder als obsolet markieren (Issue-#439-Scope).

### §6 LoC-Schätzung

| Datei | Änderung | LoC |
|-------|---------|-----|
| `frontend/src/routes/compare/+page.svelte` | Kompletter Ersatz | ~70 |
| `frontend/src/lib/components/compare/CompareList.svelte` | Neue Komponente | ~140 |
| `frontend/src/lib/components/compare/CompareRow.svelte` | Neue Komponente | ~70 |
| **Summe** | | **~280 LoC** |

LoC-Override vor Implementierungsstart erforderlich: `workflow.py set-field loc_limit_override 300`

## Expected Behavior

- **Input:** `data.subscriptions: Subscription[]` aus SSR-Loader (`+page.server.ts`); User-Interaktionen (Search, Toggle, Delete, Navigate).
- **Output:**
  - Tabelle aller Subscriptions mit Status-Dot, Name, Orte, Profil, Kanal-Pills, Versand-Schedule, Aktions-Buttons.
  - Stats-Row mit Anzahl aktiver, pausierter und Entwurfs-Subscriptions (ungefilterter Bestand).
  - Optimistisch getoggelter `enabled`-State nach Pause/Play — API-Call im Hintergrund.
  - Subscription aus lokaler Liste entfernt nach bestätigtem Delete.
  - Gefilterte Tabellenzeilen bei Sucheingabe (case-insensitive auf `name`).
- **Side effects:**
  - `PUT /api/subscriptions/{id}` bei Pause/Play-Toggle.
  - `DELETE /api/subscriptions/{id}` nach Confirm-Dialog.
  - `goto('/compare/new')` bei „+ Neuer Vergleich"-CTA.
  - `goto('/compare/{id}/edit')` bei Edit-Aktion.

## Acceptance Criteria

**AC-1:** Given der User öffnet `/compare` mit mindestens einer gespeicherten Subscription / When die Seite lädt / Then wird eine Tabelle mit den Spalten Name, Orte, Profil, Kanäle, Versand und Aktionen angezeigt.
  - Test: (populated after /tdd-red)

**AC-2:** Given die Seite lädt / When der Header gerendert wird / Then ist der Eyebrow-Text `WORKSPACE · ORTS-VERGLEICHE`, die H1 lautet „Orts-Vergleiche", ein Intro-Subtext ist sichtbar, und der Button „+ Neuer Vergleich" verlinkt auf `/compare/new`.
  - Test: (populated after /tdd-red)

**AC-3:** Given Subscriptions sind geladen / When der User Text in das Search-Feld eingibt / Then werden nur Subscriptions angezeigt, deren Name den Suchbegriff case-insensitiv enthält.
  - Test: (populated after /tdd-red)

**AC-4:** Given die Seite lädt / When die Stats-Row gerendert wird / Then zeigen drei Zähler die Anzahl aktiver (in `--g-accent`-Farbe), pausierter und Entwurfs-Subscriptions aus dem ungefiltertem Gesamtbestand.
  - Test: (populated after /tdd-red)

**AC-5:** Given eine Subscription mit `enabled: true` und vollständigen Pflichtfeldern (`name`, `locations.length > 0`) / When die Tabellenzeile gerendert wird / Then ist der Status-Dot `var(--g-accent)` (aktiv); bei `enabled: false` ist er `var(--g-ink-3)` (pausiert); bei fehlendem `name` oder leeren `locations` ist er `var(--g-ink-4)` (draft).
  - Test: (populated after /tdd-red)

**AC-6:** Given eine aktive Subscription in der Tabelle / When der User den Pause-Button klickt / Then wechselt der Status-Dot sofort zu „pausiert" (optimistic update) und `PUT /api/subscriptions/{id}` wird mit `{ ...sub, enabled: false }` aufgerufen.
  - Test: (populated after /tdd-red)

**AC-7:** Given eine Subscription in der Tabelle / When der User den Edit-Button klickt / Then navigiert die App zu `/compare/{id}/edit`.
  - Test: (populated after /tdd-red)

**AC-8:** Given eine Subscription in der Tabelle / When der User den Delete-Button klickt / Then öffnet sich ein Confirm-Dialog, und die Subscription wird erst nach Bestätigung via `DELETE /api/subscriptions/{id}` aus der Liste entfernt.
  - Test: (populated after /tdd-red)

**AC-9:** Given keine Subscriptions vorhanden (`data.subscriptions = []`) und kein Suchbegriff / When die Seite lädt / Then wird ein `EmptyState` mit CTA „+ Neuer Vergleich" → `/compare/new` angezeigt.
  - Test: (populated after /tdd-red)

**AC-10:** Given Subscriptions vorhanden, aber keine stimmt mit dem Suchbegriff überein / When der User sucht / Then wird der Text „Keine Vergleiche für »{search}« gefunden." angezeigt (kein generischer EmptyState).
  - Test: (populated after /tdd-red)

## Known Limitations

- **Send-Now ohne API:** Kein `POST /api/subscriptions/{id}/send`-Endpoint vorhanden. Der Send-Button öffnet einen Stub-Dialog mit dem Hinweis „Funktion folgt in #440". Keine funktionale Implementierung in diesem Issue.
- **Preview ohne API:** Kein dedizierten Preview-Endpoint für Subscriptions. Preview-Button analog als Stub, ohne Daten-Ladung.
- **Draft-Status nicht persistiert:** `draft` wird rein aus Frontend-Logik (`!name || locations.length === 0`) abgeleitet — nicht im Backend persistiert. Echter Draft-Zustand folgt mit dem Wizard in #440.
- **SMS-Kanal fehlt:** `CompareSubscription` hat kein `send_sms`-Feld im Go-Modell — keine SMS-Pill in der Tabelle.
- **Kein Mobile-Layout:** Diese Seite ist ein Desktop-Planungstool. Mobile-Optimierung ist kein Scope von #439.
- **Kein Paging/Sorting:** Tabelle zeigt alle Subscriptions ungepaged. Bei sehr großen Listen (>50) könnte Performance leiden — im aktuellen Nutzungsrahmen unkritisch.

## Changelog

- 2026-05-29: Initial spec — Issue #439. Tabellarische Übersicht aller Orts-Vergleiche als Ersatz des interaktiven Vergleichsrechners; 3 Dateien (~280 LoC), rein Frontend, kein Backend-Change. Teil von Epic #438.
