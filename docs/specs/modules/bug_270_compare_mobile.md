---
entity_id: bug_270_compare_mobile
type: bugfix
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [bugfix, mobile, compare, bottom-sheet, sticky, svelte, frontend, issue-270]
---

<!-- Issue #270 — Bug: Compare-Screen auf Mobile ohne Locations-Rail und ohne Sticky-Spalte -->

# Issue #270 — Bug-Fix: Compare-Screen Mobile-Nutzbarkeit

## Approval

- [ ] Approved

## Zweck

Der `/compare`-Screen ist auf Viewports ≤ 899 px nicht nutzbar, weil die `LocationsRail`-Sidebar mit `md:flex` (Tailwind-Standard, 768 px) statt dem Projekt-Breakpoint `desktop:flex` (900 px) gesteuert wird — auf Mobile bleibt sie unsichtbar, ohne dass der Nutzer Locations auswählen oder einen Vergleich starten kann. Der Fix ergänzt ein Bottom-Sheet-Muster für die Locations-Auswahl auf Mobile, korrigiert die Breakpoint-Klasse in `LocationsRail.svelte`, und fügt sticky erste Spalten in `CompareMatrix.svelte` und `HourlyMatrix.svelte` hinzu, damit die Vergleichsmatrix horizontal scrollbar und lesbar wird.

## Quelle / Source

**Geänderte Dateien:**
- `frontend/src/routes/compare/+page.svelte` — Mobile-State, Chip-Reihe, Bottom-Sheet-Markup
- `frontend/src/lib/components/compare/LocationsRail.svelte` — Breakpoint-Klasse korrigieren, Sichtbarkeits-Logik an Page abgeben
- `frontend/src/lib/components/compare/CompareMatrix.svelte` — Metrik-Spalte sticky
- `frontend/src/lib/components/compare/HourlyMatrix.svelte` — Zeit-Spalte sticky

**NICHT ändern:**
- Kein Go-API-Code, kein Python-Backend-Code
- `PresetHeader.svelte` — keine Änderung nötig
- Desktop-Layout (≥ 900 px) bleibt unverändert

> **Schicht-Hinweis:** Ausschließlich Frontend-Layer (`frontend/src/`). Kein Backend betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/routes/compare/+page.svelte` | SvelteKit Page | Orchestriert Layout; erhält `showLocationsSheet`-State, Desktop-Wrapper und Mobile-Chip-Reihe |
| `frontend/src/lib/components/compare/LocationsRail.svelte` | Svelte-Komponente | Locations-Liste, Suche, Chip-Filter — wird im Bottom-Sheet mit denselben Props wiederverwendet |
| `frontend/src/lib/components/compare/CompareMatrix.svelte` | Svelte-Komponente | Vergleichs-Matrix; Metrik-Spalte erhält `sticky left-0 z-10 bg-card` |
| `frontend/src/lib/components/compare/HourlyMatrix.svelte` | Svelte-Komponente | Stunden-Matrix; Zeit-Spalte erhält `sticky left-0 z-10 bg-card` |
| `frontend/src/app.css` | CSS | Definiert `@custom-variant mobile { @media (max-width: 899px) }` und `desktop { @media (min-width: 900px) }`; Token `--g-paper-deep`, `--g-rule-soft` |
| `frontend/src/routes/trips/+page.svelte` | Referenz-Pattern | Bottom-Sheet-Muster (Backdrop + Panel + Handle) aus Issue #268 |

## Implementation Details

### 1. `LocationsRail.svelte` — Breakpoint-Klasse korrigieren

Das Root-`div` hat aktuell `class="hidden w-60 … md:flex"`. Die `hidden`/`md:flex`-Logik für die Sichtbarkeit der Sidebar wird aus der Komponente herausgenommen und an den Wrapper in `+page.svelte` übertragen. Die Komponente selbst nutzt nur noch `class="w-60 flex flex-col …"` — sie ist immer als Flex-Container definiert; welcher Wrapper sie ein- oder ausblendet, entscheidet die Page.

```svelte
<!-- vorher -->
<div class="hidden w-60 flex-col border-r ... md:flex">

<!-- nachher -->
<div class="w-60 flex flex-col border-r ...">
```

### 2. `+page.svelte` — Mobile State + Desktop-Wrapper + Chip-Reihe + Bottom-Sheet

**State:**
```svelte
let showLocationsSheet = false;
```

**Desktop-Wrapper** (Sidebar unverändert sichtbar auf ≥ 900 px):
```svelte
<div class="hidden desktop:flex">
  <LocationsRail {props} />
</div>
```

**Mobile-Chip-Reihe** (oberhalb der Matrix, nur auf Mobile sichtbar):
```svelte
<div class="desktop:hidden flex gap-2 flex-wrap px-4 py-2">
  {#each selectedLocations as loc}
    <span class="chip">{loc.name}</span>
  {/each}
  <button on:click={() => showLocationsSheet = true}>
    Orte wählen
  </button>
</div>
```

**Bottom-Sheet** (erscheint bei `showLocationsSheet === true`):
```svelte
{#if showLocationsSheet}
  <!-- Backdrop -->
  <div
    class="fixed inset-0 z-[70] bg-black/50 desktop:hidden"
    on:click={() => showLocationsSheet = false}
    role="presentation"
  />
  <!-- Panel -->
  <div
    class="fixed bottom-0 left-0 right-0 z-[75] desktop:hidden rounded-t-2xl border-t"
    style="background: var(--g-paper-deep); border-color: var(--g-rule-soft);
           padding-bottom: env(safe-area-inset-bottom); max-height: 85vh; overflow-y: auto;"
    data-testid="compare-locations-sheet"
  >
    <!-- Handle -->
    <div class="flex justify-center pt-3 pb-2">
      <div class="w-10 h-1 rounded-full bg-muted-foreground/25" />
    </div>
    <LocationsRail {props} />
  </div>
{/if}
```

### 3. `CompareMatrix.svelte` — Metrik-Spalte sticky

Auf dem `<th>`- und allen `<td>`-Elementen der ersten Spalte (Metrik-Label) wird `sticky left-0 z-10` ergänzt. Hintergrundfarbe muss explizit gesetzt werden, damit der sticky-Header die darunter liegenden Zellen nicht durchscheinen lässt:

```svelte
<!-- Header-Zelle erste Spalte -->
<th class="sticky left-0 z-10 bg-card ...">Metrik</th>

<!-- Body-Zellen erste Spalte -->
<td class="sticky left-0 z-10 bg-card ...">{ metricLabel }</td>
```

### 4. `HourlyMatrix.svelte` — Zeit-Spalte sticky

Gleiche Behandlung wie `CompareMatrix.svelte`, angewandt auf die erste Spalte (Zeit-Label):

```svelte
<th class="sticky left-0 z-10 bg-card ...">Zeit</th>
<td class="sticky left-0 z-10 bg-card ...">{ timeLabel }</td>
```

### LoC-Budget

| Datei | Δ LoC |
|-------|--------|
| `frontend/src/routes/compare/+page.svelte` | +35 |
| `frontend/src/lib/components/compare/LocationsRail.svelte` | −2 (Breakpoint-Klassen entfernt) |
| `frontend/src/lib/components/compare/CompareMatrix.svelte` | +8 |
| `frontend/src/lib/components/compare/HourlyMatrix.svelte` | +8 |
| **Gesamt** | **~+49 (< 250 LoC-Limit)** |

## Expected Behavior

- **Input:** Viewport-Breite ≤ 899 px (Mobile) oder ≥ 900 px (Desktop)
- **Output (Mobile):**
  - Desktop-Sidebar `LocationsRail` wird vom `hidden desktop:flex`-Wrapper ausgeblendet
  - Oberhalb der Matrix erscheint eine Chip-Reihe der gewählten Locations
  - "Orte wählen"-Button öffnet Bottom-Sheet mit `<LocationsRail>` (voller Funktionsumfang: Suche, Chips, Toggle, Neu)
  - Bottom-Sheet schließt bei Klick auf Backdrop
  - Vergleichsmatrix (CompareMatrix, HourlyMatrix) scrollt horizontal; erste Spalte bleibt fixiert
- **Output (Desktop ≥ 900 px):**
  - Sidebar unverändert sichtbar, kein Bottom-Sheet-Markup aktiv
  - Sticky-Klassen schaden nicht (Tabelle scrollt auf Desktop ggf. nicht horizontal)
- **Side effects:** Keine Backend-Calls, keine Store-Änderungen — reine UI-Ergänzung

## Acceptance Criteria

**AC-1:** Given ein Viewport ≤ 899 px, When der `/compare`-Screen geladen wird, Then ist der `hidden desktop:flex`-Wrapper der Desktop-Sidebar nicht sichtbar (CSS `display: none`)

**AC-2:** Given ein Viewport ≤ 899 px und mindestens eine gewählte Location, When der `/compare`-Screen angezeigt wird, Then ist eine horizontale Chip-Reihe mit den Namen der gewählten Locations oberhalb der Matrix sichtbar

**AC-3:** Given ein Viewport ≤ 899 px, When der Nutzer auf "Orte wählen" tippt, Then öffnet sich ein Bottom-Sheet mit `data-testid="compare-locations-sheet"` das `<LocationsRail>` enthält

**AC-4:** Given das Bottom-Sheet ist geöffnet, When der Nutzer auf den Backdrop tippt, Then schließt das Bottom-Sheet (`showLocationsSheet = false`)

**AC-5:** Given ein Viewport ≥ 900 px, When der `/compare`-Screen geladen wird, Then ist die Desktop-Sidebar sichtbar und kein Bottom-Sheet aktiv

**AC-6:** Given die `CompareMatrix` wird auf Mobile horizontal gescrollt, When der Nutzer nach rechts scrollt, Then bleibt die erste Spalte (Metrik-Label) fixiert und sichtbar (`position: sticky; left: 0`)

**AC-7:** Given die `HourlyMatrix` wird auf Mobile horizontal gescrollt, When der Nutzer nach rechts scrollt, Then bleibt die erste Spalte (Zeit-Label) fixiert und sichtbar (`position: sticky; left: 0`)

## Known Limitations

- Tablets im Bereich 768–899 px sehen neu die Mobile-Ansicht (Bottom-Sheet statt Sidebar). Das ist korrekt gemäß Projekt-Konvention (`desktop` = ≥ 900 px) — war aber bisher via `md:flex` (768 px) als Desktop eingestuft. Bewusste Änderung.
- `bg-card` als sticky-Hintergrund in `CompareMatrix`/`HourlyMatrix` setzt voraus, dass `--g-card`-Token im Design-System definiert ist. Falls die Tabellenzellen einen anderen Hintergrund haben, muss der Klassen-Wert an den tatsächlichen Hintergrund angepasst werden.

## Changelog

- 2026-05-20: Initial spec created
