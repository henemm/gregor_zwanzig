---
entity_id: issue_388_archiv_atomic
type: module
created: 2026-05-26
updated: 2026-05-26
status: implemented
version: "1.0"
tags: [frontend, archiv, atomic-design, phase2, table, ssr, svelte5, issue-388]
---

# Issue #388 — Archiv-Seite: Atomic-Migration + vollständige Listenansicht

## Approval

- [ ] Approved

## Purpose

Die Route `/archiv` ist bislang ein leerer Placeholder (Eyebrow + EmptyState). Sie wird zur vollständigen tabellarischen Listenansicht archivierter Touren ausgebaut, exakt nach Vorlage `screen-archive.jsx`. Gleichzeitig werden alle Inline-Helper (`ArchiveSortTab`, `ArchiveAction`) durch Library-Bausteine aus der Atomic-Bibliothek ersetzt — `Segmented` (atoms) für den Sort-Tab und `Btn variant="quiet" size="icon-sm"` (atoms) für Aktions-Buttons. Die Seite liefert damit den dritten Migrations-Schritt in Epic #368 Phase 2 (nach Home #386 und Trips #387) und verifiziert das Listen-Tabellen-Pattern mit der Atomic-Bibliothek.

> **Schicht-Hinweis:** Alle Änderungen liegen im Frontend-Layer (`frontend/src/routes/archiv/`). Go-API (`/api/trips`) und Python-Backend sind read-only konsumiert, nicht verändert.

## Source

- **Dateien (geändert):**
  - `frontend/src/routes/archiv/+page.svelte` — vollständig neu geschrieben nach `screen-archive.jsx`
  - `frontend/src/routes/archiv/+page.server.ts` — neu erstellt; SSR-Load analog zu `trips/+page.server.ts`
- **Design-Vorlage (verbindlich):** `docs/design-requests/issue_15_atomic_design/spec/screen-archive.jsx`
- **Scope-Regeln:** `docs/design-requests/issue_15_atomic_design/spec/DELIVERY-NOTE.md` §1

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/ui/segmented/Segmented.svelte` | Atom (vorhanden) | Sort-Tabs (Neueste / Genauigkeit / Etappen) — ersetzt Inline-`ArchiveSortTab` aus screen-archive.jsx; Props: `options[]`, `selected`, `onselect` |
| `frontend/src/lib/components/ui/btn/Btn.svelte` | Atom (vorhanden) | Aktions-Buttons je Zeile — ersetzt Inline-`ArchiveAction`; `variant="quiet"`, `size="icon-sm"` mit Lucide-Icon als Slot |
| `frontend/src/lib/components/molecules/Stat.svelte` | Molecule (vorhanden) | Stats-Strip (Touren / Briefings / Alarme / Forecast-Treffer); `layout="inline"`, `tone="accent"` für Treffer-Wert |
| `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte` | Atom (vorhanden) | Eyebrow-Text "Workspace · Vergangene Touren" |
| `frontend/src/lib/types.ts` | TypeScript-Typ (vorhanden, read-only) | `Trip`-Interface mit `archived_at?: string` |
| `$env/dynamic/private` (SvelteKit) | Framework-Built-in | `GZ_API_BASE`-Env für Go-API-URL im SSR-Loader |
| `@lucide/svelte/icons/history` | Lucide-Icon | Briefing-Verlauf-Button in `ArchiveRow`; Import als `HistoryIcon` |
| `@lucide/svelte/icons/copy` | Lucide-Icon | "Als Vorlage neu anlegen"-Button in `ArchiveRow`; Import als `CopyIcon` |
| `@lucide/svelte/icons/trash-2` | Lucide-Icon | Löschen-Button in `ArchiveRow`; Import als `Trash2Icon` |
| `@lucide/svelte/icons/search` | Lucide-Icon | Such-Icon links im Search-Input |
| `contrast-audit.test.ts` | Test-Suite (vorhanden, read-only) | Muss nach der Migration weiterhin grün sein (kein Hex-Literal als Farbwert, kein `--g-accent` als Text-Color) |

## Architektur-Entscheidung: AccuracyBar ohne Echtdaten

Das Go-Modell (`internal/model/trip.go`, `Trip`-Struct) hat kein `accuracy`-Feld. Die Vorlage `screen-archive.jsx` zeigt einen Balkenwert aus Mock-Daten, der aus einem Backend-Feature kommen würde, das noch nicht existiert.

**Entscheidung (explizit):** `AccuracyBar` wird in der Implementierung als page-lokale Komponente angelegt, rendert aber immer `value=0` und ist mit einem `<!-- AccuracyBar: accuracy-Daten ausstehend (kein Backend-Feld) -->` Kommentar im Template markiert. Der Balken ist sichtbar (0 %-Streifen), die Prozentzahl zeigt `—` statt `0%`. Der Stats-Strip zeigt „Forecast-Treffer Ø" ebenfalls als `—`. Sobald das Backend-Feld nachgezogen wird, ist nur `AccuracyBar` anzupassen — kein weiterer Umbau nötig.

Die `AccuracyBar`-Hex-Farben aus `screen-archive.jsx` (`#3d6b3a`, `#c08a1a`) werden auf Design-Tokens gemappt:

| JSX-Farbe | Token | Kontrast-Compliance |
|---|---|---|
| `#3d6b3a` (gut, ≥90 %) | `var(--g-ink)` | WCAG-AA auf weißer Card |
| `var(--g-ink-2)` (mittel, 80–89 %) | `var(--g-ink-2)` | WCAG-AA |
| `#c08a1a` (warn, <80 %) | `var(--g-attention)` | WCAG-AA, contrast-audit-konform |

Kein einziges Hex-Literal bleibt in der Svelte-Ausgabe — ausschließlich CSS-Token.

## Implementation Details

### 1. SSR-Loader `+page.server.ts` (neu)

Analog zu `trips/+page.server.ts`, aber filtert auf archivierte Touren:

```ts
import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';
import type { Trip } from '$lib/types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
    const session = cookies.get('gz_session');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (session) headers['Cookie'] = `gz_session=${session}`;

    const res = await fetch(`${API()}/api/trips`, {
        headers,
        signal: AbortSignal.timeout(5000)
    }).catch(() => null);

    const all: Trip[] = res?.ok ? await res.json() : [];
    const trips = (Array.isArray(all) ? all : []).filter(
        (t) => t.archived_at != null
    );

    return { trips };
};
```

Der Filter `archived_at != null` entspricht der semantischen Definition "archiviert" gemäß Go-Modell-Feld `ArchivedAt *time.Time`. Der Loader ist fail-soft: bei API-Fehler liefert er leere Liste.

### 2. Page-Komponente `+page.svelte` — Struktur

Der bisherige Placeholder-Inhalt wird vollständig ersetzt. Die Seite ist strukturell identisch zur Vorlage `screen-archive.jsx`.

**Script-Block:**

```ts
import type { PageData } from './$types.js';
import Segmented from '$lib/components/ui/segmented/index.js';
import { Btn } from '$lib/components/ui/btn/index.js';
import Stat from '$lib/components/molecules/Stat.svelte';
import { Eyebrow } from '$lib/components/ui/eyebrow/index.js';
import HistoryIcon from '@lucide/svelte/icons/history';
import CopyIcon from '@lucide/svelte/icons/copy';
import Trash2Icon from '@lucide/svelte/icons/trash-2';
import SearchIcon from '@lucide/svelte/icons/search';

let { data }: { data: PageData } = $props();

const SORT_OPTIONS = [
    { value: 'recent',   label: 'Neueste' },
    { value: 'accuracy', label: 'Genauigkeit' },
    { value: 'stages',   label: 'Etappen' }
];

let query  = $state('');
let sort   = $state('recent');

const filtered = $derived(
    data.trips
        .filter((t) => t.name.toLowerCase().includes(query.toLowerCase()))
        .sort((a, b) => {
            if (sort === 'recent')
                return (b.archived_at ?? '').localeCompare(a.archived_at ?? '');
            if (sort === 'stages')
                return (b.stages?.length ?? 0) - (a.stages?.length ?? 0);
            // 'accuracy': no backend data yet — retain original order
            return 0;
        })
);

const totalBriefings = $derived(0);  // no briefings count field yet
const totalAlerts    = $derived(0);  // no alerts_triggered count field yet
```

**Template-Struktur (Hauptbereiche):**

1. **Header:** `<Eyebrow>`, H1 "Archiv", Beschreibungstext — token-basiert, kein Inline-Hex
2. **Toolbar:** Search-Input (rounded-pill, SearchIcon links) + `<Segmented options={SORT_OPTIONS} selected={sort} onselect={(v) => sort = v}>`
3. **Stats-Strip:** 4× `<Stat layout="inline">` — Touren, Briefings gesendet (`—`), Forecast-Treffer Ø (`—`), Alarme ausgelöst (`—`)
4. **Tabelle:** Card-Wrapper (padding=0), Kopfzeile mit 6-spaltigem Grid (`1.7fr 0.7fr 1.1fr 0.9fr 1.6fr auto`), dann `{#each filtered}` → `<ArchiveRow>`
5. **Empty-State-Zeile:** bei `filtered.length === 0` ein zentrierter `<p>`
6. **Footer:** `{filtered.length} von {data.trips.length} archivierten Touren · auto-archiviert nach Tour-Ende`

### 3. Page-lokale Komponenten (bleiben page-lokal, DELIVERY-NOTE §1)

**`ArchiveRow`** — Tabellenzeile, identisches 6-Spalten-Grid wie Header:
- Spalte 1: Dot (7×7 px, `--g-ink-4`) + Trip-Name (fontWeight 600, truncated) + optionaler Alert-Zähler
- Spalte 2: Etappen-Zahl + "Etappe/Etappen" Pluralisierung
- Spalte 3: Datumsbereich `from → to` in JetBrains Mono (`--g-font-mono`)
- Spalte 4: `<AccuracyBar>` (immer value=0, Platzhalter)
- Spalte 5: Headline-Text (truncated, `--g-ink-3`)
- Spalte 6: 3× `<Btn variant="quiet" size="icon-sm">` — HistoryIcon, CopyIcon, Trash2Icon. Vor Trash ein 1 px hoher vertikaler `--g-rule`-Separator. Danger-Button (Trash) behält `--g-ink-3` als Ikonfarbe (keine eigene danger-Klasse nötig, da Quiet-Variante).

Zebrastreifung: `alt`-Prop → `background: var(--g-paper-deep)` bei ungeraden Zeilen.

**`AccuracyBar`** — horizontaler Fortschrittsbalken + Prozentwert:
- Track: `height: 4px`, `background: var(--g-rule-soft)`, `border-radius: var(--g-r-pill)`, `max-width: 80px`
- Fill: `width: {value}%`, Farbe per `tone`-Prop (good → `--g-ink` | ok → `--g-ink-2` | warn → `--g-attention`)
- Zahl: `--g-font-mono`, `font-weight: 600`, `font-variant-numeric: tabular-nums`
- Solange kein Backend-Feld: `value=0`, Zahlenwert zeigt `—`

### 4. Token-Compliance-Check (kein Hex in Svelte-Ausgabe)

Die JSX-Vorlage enthält mehrere Inline-Hex-Farben. Diese dürfen **nicht** in Svelte übernommen werden:

| JSX-Wert | Ersetzen durch |
|---|---|
| `#3d6b3a` | `var(--g-ink)` |
| `#c08a1a` | `var(--g-attention)` |
| Inline `stroke={c}` | CSS-Variable im Style |

`contrast-audit.test.ts` schlägt bei Hex-Literalen an — alle müssen Token sein.

### 5. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/routes/archiv/+page.svelte` | ~180 (Neufassung aus 13 Zeilen) | ja |
| `frontend/src/routes/archiv/+page.server.ts` | ~18 (neu) | ja |
| **Gesamt (zählend)** | **~198** | **unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** SvelteKit SSR-Load-Aufruf auf `/archiv`; Go-API liefert Trip-Array (gefiltert auf `archived_at != null`)
- **Output:** Vollständig gerenderte Tabellenansicht mit Header, Toolbar (Suche + Sort-Tabs), Stats-Strip, Tabelle mit einer Zeile pro archivierten Tour, Footer-Zähler
- **Reaktivität:**
  - Search-Input: `query`-State → `filtered`-Derived → Tabelle aktualisiert sich ohne Reload
  - Sort-Tabs: `sort`-State → `filtered`-Derived neu sortiert; `Segmented` zeigt aktive Auswahl via `data-active`
- **Fail-soft:** API nicht erreichbar → leere Trip-Liste → leere Tabelle; kein Seitencrash
- **Side effects:** Keine schreibenden API-Calls auf dieser Seite (Aktionen Briefing-Verlauf, Vorlage, Löschen sind Buttons ohne Handler — sie öffnen keine Dialoge in dieser Iteration, da kein Backend-Endpunkt für Archiv-Aktionen existiert; Buttons sind sichtbar aber inaktiv)

## Acceptance Criteria

- **AC-1:** Given die Route `/archiv` wird ohne archivierte Touren aufgerufen / When der SSR-Loader `GET /api/trips` aufruft und keine Tour mit `archived_at != null` zurückkommt / Then rendert die Seite die Tabellen-Kopfzeile und den Footer-Hinweis "0 von 0 archivierten Touren", kein EmptyState-Platzhalter, kein JS-Fehler
  - Test: (populated after /tdd-red)

- **AC-2:** Given die Route `/archiv` mit mindestens einer archivierten Tour / When die Seite geladen ist und der Nutzer einen Suchbegriff ins Search-Input eingibt / Then filtert die Tabelle reaktiv (via `$derived`) ohne Seiten-Reload und zeigt nur Touren, deren Name den Suchbegriff enthält (case-insensitive), der Footer-Zähler aktualisiert sich entsprechend
  - Test: (populated after /tdd-red)

- **AC-3:** Given die Archiv-Tabelle ist sichtbar / When der Nutzer auf den "Genauigkeit"-Sort-Tab klickt / Then wechselt `Segmented` optisch auf `data-active="true"` für "Genauigkeit", die `sort`-Variable ist `"accuracy"`, und die Tabelle behält die bestehende Reihenfolge (da kein Backend-Feld; kein Crash, keine Umsortierung)
  - Test: (populated after /tdd-red)

- **AC-4:** Given die Svelte-Quelldatei `+page.svelte` und `+page.server.ts` / When `contrast-audit.test.ts` ausgeführt wird und `svelte-check` läuft / Then sind beide Tests ohne Fehler grün; kein Hex-Farbliteral (`#[0-9a-fA-F]{3,6}`) in Svelte-Ausgabe, ausschließlich CSS-Design-Tokens; svelte-check meldet 0 Typfehler
  - Test: `contrast-audit.test.ts` (bestehend); `svelte-check` im Frontend-Verzeichnis

- **AC-5:** Given die `AccuracyBar`-Komponente in einer `ArchiveRow` / When `value=0` übergeben wird (kein Backend-Feld vorhanden) / Then zeigt der Balken einen 0 %-Track (sichtbarer leerer Balken), die Prozentzahl zeigt `—` statt `0%`, und der Code-Kommentar `AccuracyBar: accuracy-Daten ausstehend` ist in der Svelte-Datei vorhanden
  - Test: (populated after /tdd-red)

- **AC-6:** Given der SSR-Loader auf `/archiv` und das Go-API antwortet nicht innerhalb von 5 Sekunden / When der Fetch mit `AbortSignal.timeout(5000)` abbricht / Then wird die Seite mit leerer Trip-Liste gerendert (fail-soft), kein unbehandelter Promise-Rejection, HTTP-Status der Seite bleibt 200
  - Test: (populated after /tdd-red)

- **AC-7:** Given eine `ArchiveRow` mit einer Tour, die `alerts > 0` hat / When die Zeile gerendert wird / Then ist ein Alert-Zähler-Text (`· N alert(s)`) in `--g-accent`-Farbe sichtbar neben dem Touren-Namen; bei `alerts === 0` ist kein Alert-Text sichtbar
  - Test: (populated after /tdd-red)

## Known Limitations

- **AccuracyBar ohne Echtdaten:** Das Go-Modell hat kein `accuracy`-Feld. `AccuracyBar` rendert mit 0 % / `—` bis das Backend-Feld nachgezogen wird. Stats-Strip zeigt "Forecast-Treffer Ø: —". Keine separate Aufgabe für diese Iteration — die Komponenten-Infrastruktur ist vorhanden, sobald das Feld da ist.
- **Aktions-Buttons ohne Handler:** Die drei Aktionen (Briefing-Verlauf, Vorlage, Löschen) sind in dieser Iteration sichtbare Buttons ohne aktiven onClick-Handler, da kein dedizierter Archiv-Aktions-Endpunkt existiert. Sie werden in einem Folge-Issue verkabelt.
- **Sortierung "Genauigkeit":** Ohne Backend-Feld behält diese Sortieroption die API-Reihenfolge. Das ist das korrekte Verhalten bis zum Backend-Feld.
- **Briefings- und Alarmzähler im Stats-Strip:** Die Felder `briefings_sent` und `alerts_triggered` existieren nicht im Trip-Struct — beide Stats-Kacheln zeigen `—`.

## Out of Scope

- Backend-Feld `accuracy` (eigenes Issue)
- Aktions-Handler für Briefing-Verlauf, Vorlage-Kopie, Löschen (eigenes Issue)
- Mobile-Card-Stack-Variante der Archiv-Seite (Folge-Issue, analog Issue #268 für Trips)
- Änderungen an Go-API, Python-Backend, `internal/model/trip.go`

## Changelog

- 2026-05-26: Initial spec erstellt. Vollständiger Neuaufbau der `/archiv`-Route nach `screen-archive.jsx`-Vorlage, Atomic-Migration (`Segmented` + `Btn quiet`), SSR-Loader mit `archived_at`-Filter, explizite AccuracyBar-Platzhalter-Entscheidung, Token-Compliance für JSX-Hex-Farben dokumentiert.
