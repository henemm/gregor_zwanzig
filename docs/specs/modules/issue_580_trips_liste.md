---
entity_id: issue_580_trips_liste
type: module
created: 2026-06-04
updated: 2026-06-04
status: draft
version: "1.0"
tags: [frontend, trips, design-fidelity, svelte, atomic-design]
---

<!-- Issue #580 — Design-Fidelity: Trips-Liste 1:1 nach screen-trips.jsx -->

# Issue 580 — Design-Fidelity: Trips-Liste 1:1 nach screen-trips.jsx

## Approval

- [ ] Approved

## Purpose

Die Trips-Übersichtsseite (`/trips`) wird so umgebaut, dass das Desktop-Layout 1:1 der JSX-Vorlage `screen-trips.jsx` entspricht. Die aktuelle Svelte-Implementierung weicht in vier Bereichen ab (Stats-Bar, Grid-Tabelle, ActionBtn-Reihe, Typografie), was beim Design-Audit als Fidelity-Gap erkannt wurde — diese Spec schließt diesen Gap ohne die Mobile-Ansicht zu berühren.

## Source

- **File:** `frontend/src/routes/trips/+page.svelte` (UMBAU: Desktop-Bereich)
- **File:** `frontend/src/routes/trips/issue_580.test.ts` (NEU: Playwright-Tests)

## Estimated Scope

- **LoC:** ~150 (Umbau desktop section +page.svelte) + ~80 (Tests)
- **Files:** 2
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/components/atoms/Stat.svelte` | Atom | SummaryStat-Blöcke mit `layout="inline"` für die Stats-Bar; `tone="accent"` für "Aktiv" |
| `$lib/components/atoms/Card.svelte` | Atom | Container für die Grid-Tabelle mit `padding={0}` |
| `$lib/components/atoms/Eyebrow.svelte` | Atom | Mono-Uppercase-11px-Header-Zellen der Tabelle |
| `$lib/components/atoms/Btn.svelte` | Atom | ActionBtn-Einzelbuttons (30×30px, border, borderRadius) |
| `$lib/utils/tripStatus.ts` | Utility | Liefert normierten Status ('aktiv'/'geplant'/'fertig'/'draft') für Dot-Farbe und Mono-Caption |
| `screen-trips.jsx` | Design-Vorlage | Quelle der SOLL-Struktur: gridTemplateColumns, Farbwerte, ActionBtn-Icon-Set |

## Implementation Details

### Stats-Summary-Bar

Ersetze die bisherige Tailwind-Zahlendarstellung durch 4 `Stat`-Atoms nebeneinander im `layout="inline"`-Modus. Reihenfolge: Aktiv / Geplant / Abgeschlossen / Drafts. "Aktiv" erhält `tone="accent"`. Die Zählwerte werden aus dem bestehenden Trips-Array abgeleitet (Status-Mapping via `tripStatus.ts`).

```svelte
<div class="stats-bar">
  <Stat label="Aktiv"        value={counts.aktiv}        layout="inline" tone="accent" />
  <Stat label="Geplant"      value={counts.geplant}      layout="inline" />
  <Stat label="Abgeschlossen" value={counts.fertig}      layout="inline" />
  <Stat label="Drafts"       value={counts.draft}        layout="inline" />
</div>
```

### H1-Titel

Ändere den Titel von "Meine Trips" auf "Trips". Style: `font-size: 32px; font-weight: 600; letter-spacing: -0.025em`.

### Desktop Grid-Tabelle

Wrapping-Container: `Card padding={0}`. Darunter Header-Zeile + TripRow-Liste, beide mit CSS-Grid `gridTemplateColumns: "1.6fr 0.8fr 1.4fr auto"`.

**Header-Zeile:**
- Background: `var(--g-paper-deep)`
- Zellen: Eyebrow-Atom, 11px Mono-Uppercase
- Spalten-Labels: "Trip" / "Etappen" / "Zeitraum" / "" (leer für Actions-Spalte)

**TripRow:**
- Alternating background: gerade Zeilen transparent, ungerade `var(--g-paper-deep)`
- Spalte 1 — Name: farbiger Dot (7px, `border-radius: 50%`) + fetter Tripname + Mono-Caption `"· {status-label}"`
- Spalte 2 — Etappen: Anzahl der Stages
- Spalte 3 — Zeitraum: formatiertes Datum-Range
- Spalte 4 — Actions: 6 ActionBtns

**Dot-Farben nach Status:**
- `aktiv` → `var(--g-accent)`
- `geplant` → `#3d6b3a`
- `fertig` → `var(--g-ink-3)`
- `draft` → `var(--g-ink-4)`

### ActionBtn-Reihe

6 Einzelbuttons statt DropdownMenu. Layout: `alert | weather | play | preview | <Separator> | edit | trash`. Jeder Button: `width: 30px; height: 30px; border: 1px solid var(--g-rule-soft); border-radius: var(--g-r-2)`. Jeder Button trägt ein passendes SVG-Icon.

```svelte
<div class="action-btns">
  <Btn size="icon" icon="alert"   ... />
  <Btn size="icon" icon="weather" ... />
  <Btn size="icon" icon="play"    ... />
  <Btn size="icon" icon="preview" ... />
  <span class="separator" />
  <Btn size="icon" icon="edit"    ... />
  <Btn size="icon" icon="trash"   ... />
</div>
```

### Footer

Zeile unterhalb der Tabelle: `"{N} von {M} Trips"`. Style: Mono-11px, `color: var(--g-ink-4)`.

### Mobile-Schutz

Die Mobile Card-Stack-Ansicht und Filter-Pills (`class="mobile-*"` o.ä.) bleiben vollständig unverändert. Der Desktop-Block ist in einem `@media`-Guard oder einem `{#if !mobile}`-Block isoliert, der exakt dem bisherigen Breakpoint entspricht.

## Expected Behavior

- **Input:** Trips-Array aus dem SvelteKit-Load (bestehende API, keine Änderung)
- **Output:** Seite `/trips` rendert auf Desktop (≥1024px) mit Stats-Bar, Grid-Tabelle, ActionBtns und Footer exakt nach SOLL-Mockup aus `screen-trips.jsx`
- **Side effects:** Keine — Mobile-Ansicht, Routing, API-Calls bleiben unverändert

## Acceptance Criteria

- **AC-1:** Given the Trips page at 1440px desktop width / When the page renders / Then the stats row shows 4 SummaryStat blocks (Aktiv/Geplant/Abgeschlossen/Drafts) using the Stat atom with `layout="inline"`, with "Aktiv" having `tone="accent"`
  - Test: (populated after /tdd-red)

- **AC-2:** Given the Trips page at 1440px desktop width / When trips are listed / Then the desktop table uses a CSS Grid with columns `"1.6fr 0.8fr 1.4fr auto"`, a header row with `var(--g-paper-deep)` background and Mono-uppercase-11px text
  - Test: (populated after /tdd-red)

- **AC-3:** Given the Trips page at 1440px desktop width / When trips are listed / Then each TripRow shows: colored dot (7px) + bold name + mono-caption (`"· {status}"`) / Etappen count / date range / 6 ActionBtns (alert/weather/play/preview | separator | edit/trash)
  - Test: (populated after /tdd-red)

- **AC-4:** Given the Trips page at 1440px desktop width / When each ActionBtn is rendered / Then each has `width=30px`, `height=30px`, `border="1px solid var(--g-rule-soft)"`, `border-radius=var(--g-r-2)`, and a matching SVG icon
  - Test: (populated after /tdd-red)

- **AC-5:** Given the Trips page / When it renders / Then the H1 title text is "Trips" (not "Meine Trips") and the footer shows `"{N} von {M} Trips"` in mono-11px with `var(--g-ink-4)` color
  - Test: (populated after /tdd-red)

- **AC-6:** Given the Trips page on mobile (viewport < desktop breakpoint) / When the page renders / Then the mobile Card-Stack and Filter-Pills remain unchanged and no regression occurs
  - Test: (populated after /tdd-red)

## Known Limitations

- ActionBtn-Icons müssen aus dem vorhandenen Icon-Set des Projekts stammen; falls ein Icon fehlt (z.B. "alert" oder "weather"), wird ein Platzhalter-SVG verwendet und ein Follow-up-Issue erstellt
- Die DropdownMenu-Variante entfällt vollständig auf Desktop; falls sie noch auf Mobile genutzt wird, bleibt sie dort erhalten

## Changelog

- 2026-06-04: Initial spec erstellt — Issue #580
