---
entity_id: issue_402_trips_atomic
type: module
created: 2026-05-27
updated: 2026-05-27
status: implemented
version: "1.1"
tags: [frontend, trips, atomic-design, phase2, svelte5, issue-402]
---

# Issue #402 — Trips-Seite: Atomic-Migration (ui/ → atoms/ + Stat-Molecule)

## Approval

- [ ] Approved

## Purpose

Die Route `/trips` wurde in #282/#295 visuell redesignt, aber nie auf die Atomic-Bibliothek
(`atoms/` + `molecules/`) umgestellt — Issue #387 (Phase 2) wurde als „design-bereits-erfüllt"
geschlossen, ohne die Code-Konvention anzupassen. Diese Migration stellt die direkten
`ui/`-Importe auf die kanonischen Atom-/Molecule-Barrel um und ersetzt den handgebauten
Inline-Stats-Streifen durch das `Stat`-Molecule. Keine Logik-, keine inhaltliche Änderung;
die Status-Zähler-Zeile übernimmt das `Stat`-Aussehen **und** behält die farbigen Status-Punkte
(PO-Entscheidung, s.u.). Letzter offener Screen-Code-Schritt aus Epic #368 Phase 2 für die
Trips-Liste.

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer
> (`frontend/src/routes/trips/+page.svelte`). Go-API und Python-Backend sind nicht betroffen.

## Source

- **Datei (geändert):** `frontend/src/routes/trips/+page.svelte` (644 Z.)
- **Datei (Begleit-Fix, während Umsetzung entdeckt):** `frontend/src/lib/components/atoms/Input.svelte` — Bridge-Wrapper reichte `value` nicht als `$bindable()` durch; `<Input bind:value>` am Atom-Barrel brach mit svelte-check-ERROR. Behoben durch explizites `value`/`ref`/`files` als `$bindable()` (mustergetreu zu `ui/input/input.svelte` und `atoms/Switch.svelte`). Nicht-visuell.
- **Vorbild:** `frontend/src/routes/archiv/+page.svelte` (#388) — `Stat`-Strip + Atom-Imports
- **Scope-Regeln:** Issue #402 (Delivery-Note §1 Mapping)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/components/atoms` (Barrel) | Atoms (vorhanden, #371) | Liefert `Btn`, `Input`, `Dot`, `Eyebrow` als Bridge-Wrapper über `ui/` — neue Import-Quelle |
| `$lib/components/molecules` (Barrel) | Molecules (vorhanden, #372) | Liefert `Stat` — ersetzt Inline-`div + Dot + span`-Streifen |
| `frontend/src/lib/components/molecules/Stat.svelte` | Molecule (vorhanden) | `layout="inline"`, Props `label`/`value`; rendert Wert (≥22px) + Mono-Caps-Label, **kein** eigener Status-Punkt |
| `frontend/src/lib/components/atoms/Dot.svelte` | Atom (vorhanden) | Farbiger Status-Punkt (`tone`, `size="sm"`) — bleibt erhalten, neu aus `atoms` importiert |
| `frontend/src/lib/utils/tripStatus.ts` (`deriveTripStatus`) | Util (vorhanden, read-only) | Liefert Status pro Trip für die Zähler — unverändert |
| `ui/table`, `ui/dialog`, `ui/select`, `ui/empty-state`, `ui/checkbox` | UI-Komponenten (vorhanden) | **Bleiben in `ui/`** — kein Atom-/Molecule-Pendant in der Bibliothek |
| `contrast-audit.test.ts` | Test-Suite (vorhanden, read-only) | Muss nach der Migration grün bleiben |

## Architektur-Entscheidung: Status-Zähler = `Stat` + `Dot` (PO 2026-05-27)

Der heutige Stats-Streifen zeigt pro Status (Aktiv/Geplant/Pausiert/Archiviert) einen farbigen
`Dot` + Mono-Count + Normalcase-Label. Das `Stat`-Molecule hat ein festes Aussehen (Wert ≥22px,
Label uppercase Mono-Caps) und **keinen** eigenen Status-Punkt. Issue #402 fordert gleichzeitig
„keine visuelle Änderung" und „implementiert über Stat-Molecule" — das schließt sich teilweise
aus.

**Entscheidung (PO):** Variante A — `Stat`-Baustein **und** farbige Punkte behalten. Pro Status
wird `<Dot tone size="sm">` (aus `atoms`) mit `<Stat layout="inline" label value>` (aus
`molecules`) komponiert. Die Zähler-Typografie folgt dem `Stat`-Baustein (Archiv-Look #388);
die Status-Farben bleiben über die Punkte erhalten.

## Implementation Details

### 1. Import-Umstellung (Script-Block)

| Import heute (`ui/`) | Ziel | Aktion |
|---|---|---|
| `Btn` (Z. 5) | `import { Btn, Input, Dot, Eyebrow } from '$lib/components/atoms';` | konsolidieren auf einen Atom-Barrel-Import |
| `Input` (Z. 6) | s.o. | s.o. |
| `Dot` (Z. 17) | s.o. | s.o. |
| `Eyebrow` (Z. 20) | s.o. | s.o. |
| Stats-Streifen | `import { Stat } from '$lib/components/molecules';` | neuer Import |
| `Table` (Z. 7), `Dialog` (Z. 8), `Checkbox` (Z. 18), `Select` (Z. 19), `EmptyState` (Z. 21) | **unverändert** | bleiben `ui/` — kein Pendant |

### 2. Stats-Streifen-Ersatz (Z. 261–276)

Vorher (Inline-Konstruktion):

```svelte
<div class="flex items-center gap-1.5 text-sm">
  <Dot tone={stat.tone} size="sm" />
  <span class="font-mono tabular-nums">{count}</span>
  <div class="text-muted-foreground">{stat.label}</div>
</div>
```

Nachher (`Dot` + `Stat`-Molecule):

```svelte
<div class="flex items-center gap-2">
  <Dot tone={stat.tone} size="sm" />
  <Stat layout="inline" label={stat.label} value={count} />
</div>
```

Die `{#each [...]}`-Schleife über die 4 Status-Definitionen, `deriveTripStatus`-Zählung,
`hidden desktop:flex`-Sichtbarkeit und die `trips.length > 0`-Bedingung bleiben **unverändert**.

### 3. Regressions-Sentinel (neuer Test)

Analog `routes/archiv/issue_388.test.ts`: ein Source-Inspection-Test prüft, dass
`+page.svelte` Btn/Input/Dot/Eyebrow aus `$lib/components/atoms` und `Stat` aus
`$lib/components/molecules` importiert — und dass die 4 atomisierten Komponenten **nicht** mehr
direkt aus `ui/` kommen. Verhindert Zurückrutschen.

### 4. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/routes/trips/+page.svelte` | ~12 (4 Import-Zeilen → 2, Streifen-Markup) | ja |
| `frontend/src/routes/trips/issue_402.test.ts` | ~25 (neuer Sentinel) | ja |
| **Gesamt (zählend)** | **~37** | **unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** Render der Route `/trips` mit bestehenden Trip-Daten (SSR-Load unverändert).
- **Output:** Optisch identische Seite bis auf die Zähler-Zeile, die jetzt das `Stat`-Aussehen
  (größere Zahl, Kapitälchen-Label) mit vorangestelltem farbigem Status-Punkt zeigt.
- **Side effects:** Keine. Reine Komponenten-/Import-Umstellung, keine API-Calls geändert.

## Acceptance Criteria

- **AC-1:** Given die Datei `trips/+page.svelte` / When die Komponenten-Importe aufgelöst werden / Then stammen `Btn`, `Input`, `Dot`, `Eyebrow` aus `$lib/components/atoms` und `Stat` aus `$lib/components/molecules`; keiner dieser fünf wird mehr direkt aus `$lib/components/ui/...` importiert
  - Test: (populated after /tdd-red)

- **AC-2:** Given Trips mit unterschiedlichem Status existieren / When die Trips-Seite geladen wird / Then zeigt der Stats-Streifen pro Status (Aktiv/Geplant/Pausiert/Archiviert) dieselben Zähler wie bisher (via `deriveTripStatus`), implementiert über das `Stat`-Molecule mit `layout="inline"`
  - Test: (populated after /tdd-red)

- **AC-3:** Given die Status-Zähler-Zeile wird auf Desktop gerendert / When eine Zähler-Kachel angezeigt wird / Then steht vor jedem `Stat` weiterhin ein farbiger `<Dot>` mit dem zum Status passenden `tone` (success/info/warning/danger), sodass die Status-Farb-Codierung erhalten bleibt
  - Test: (populated after /tdd-red)

- **AC-4:** Given die migrierte `+page.svelte` / When `svelte-check` und `contrast-audit.test.ts` im Frontend laufen / Then sind beide ohne Fehler grün (0 Typfehler, kein Kontrast-Verstoß), und die nicht-atomisierten Importe (`Table`, `Dialog`, `Select`, `EmptyState`, `Checkbox`) bleiben unverändert aus `ui/` importiert
  - Test: `svelte-check`; `contrast-audit.test.ts` (bestehend)

## Known Limitations

- **Teil-Migration nach Bibliotheks-Abdeckung:** `Table`, `Dialog`, `Select`, `EmptyState`,
  `Checkbox` haben (noch) kein Atom-/Molecule-Pendant und bleiben aus `ui/` importiert. „Keine
  direkten `ui/`-Importe mehr" gilt nur für die fünf Komponenten mit vorhandenem Pendant. Sobald
  die Bibliothek diese Komponenten abdeckt, ist eine Folge-Migration möglich.
- **Geringe sichtbare Änderung:** Die Zähler-Zahlen werden etwas größer, Labels in Kapitälchen
  (Stat-Aussehen, konsistent mit Archiv-Seite #388) — bewusste, vom PO bestätigte Konsequenz.

## Out of Scope

- Migration von `Table`/`Dialog`/`Select`/`EmptyState`/`Checkbox` (kein Pendant; eigene Issues)
- TripTabs-Migration (eigenes Issue #403)
- Änderungen an SSR-Loader, Go-API, Python-Backend
- Mobile-Card-Stack der Trips-Liste (bereits #268, unverändert)

## Changelog

- 2026-05-27: Initial spec erstellt. Atom-Barrel-Import für Btn/Input/Dot/Eyebrow, `Stat`-Molecule
  für Stats-Streifen mit erhaltenen Status-Punkten (PO-Entscheidung Variante A), bewusste
  Scope-Grenze für nicht-atomisierte `ui/`-Komponenten, Regressions-Sentinel-Test.
- 2026-05-27: Umgesetzt (status→implemented). Begleit-Fix `atoms/Input.svelte` auf `$bindable`
  (latenter #371-Bridge-Bug, durch Migration aufgedeckt). Adversary VERIFIED (4/4 AC + 5
  Edge-Cases: count=0→„0", bind:value-Reaktivität, kein $bindable-Seiteneffekt bei anderen
  Input-Konsumenten, svelte-check/Kontrast sauber). Tests: issue_402 7/7, atoms 8/8,
  molecules 7/7, contrast-audit 5/5.
