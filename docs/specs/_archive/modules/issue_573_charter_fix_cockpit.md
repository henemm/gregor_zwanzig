---
entity_id: issue_573_charter_fix_cockpit
type: module
created: 2026-06-03
updated: 2026-06-03
status: approved
version: "1.0"
tags: [frontend, home, cockpit, design-compliance, tokens, atoms]
---

<!-- Issue #573 — Charter-Verstöße in Startseite-Cockpit beheben -->

# Issue 573 — Startseite-Cockpit: Charter-Compliance-Fix

## Approval

- [x] Approved

## Purpose

Das Startseite-Cockpit (#568/#571) weist systematische Abweichungen von der Design-Charter auf.
Diese Spec beschreibt die nötigen Korrekturen ohne funktionale Änderungen.

## Source

- **File:** `frontend/src/routes/+page.svelte`
- **File:** `frontend/src/lib/components/molecules/SetupResumeCard.svelte`
- **File:** `frontend/src/lib/components/molecules/QuickAction.svelte`
- **File:** `frontend/src/lib/components/molecules/CompareStatusRow.svelte` (Audit)

> **Schicht:** Frontend / Molecules + Page — ausschließlich SvelteKit (`frontend/src/`).
> Kein Backend-Berührpunkt.

## Estimated Scope

- **LoC:** ~80–150 (Ersetzungen, keine neue Logik)
- **Files:** 4
- **Effort:** small

## Violations (Befunde)

### V1 — Symbole/Emoji verboten (Charter §5)
- `SetupResumeCard.svelte`: `'✓'` und `'○'` als Schritt-Status → `<Dot>` atom
- `QuickAction.svelte`: ◆◷◉◐▸‖ als Glyphen → Catalog-Icons oder Lucide-Fallback

### V2 — Custom-Elemente statt Atoms (Charter §4)
- `SetupResumeCard.svelte`: hand-styled `<a>` als CTA → `<Btn>`
- `+page.svelte`: custom `<header>` → `<PageHeader>`

### V3 — Nicht-Token-Schriftgrößen (Charter §5)
Folgende Werte außerhalb der Scale (11/13/15/17/20/24/32/44/60 px):
- 12 px → `var(--g-text-xs)` = 11 px (nächste)
- 14 px → `var(--g-text-sm)` = 13 px
- 22 px → `var(--g-text-xl)` = 20 px
- 28 px → `var(--g-text-2xl)` = 24 px

### V4 — Nicht-Token-Letter-Spacing (Charter §5)
- `-0.005em` → `var(--g-track-normal)` = 0 (für Titel-Body)
- `0.08em` → `var(--g-track-caps)` = 0.12em (für Mono-Eyebrow)

### V5 — Falsche/fehlende Token-Namen (Charter §5)
- `--g-success` → `--g-good`
- `--g-ink-on-accent` → `var(--g-paper)` (weiß auf Akzent)
- Literal `#ffffff` → `var(--g-paper)`

### V6 — Semantik-Fehler
- `<Dot tone="bad" />` in Live-Pill → `tone="good"` (aktiver Trip = grüner Status)

### V7 — Spacing-Literal-Werte (Charter §5)
Überall in betroffenen Dateien: freie Pixel-Werte → `--g-s-*`-Tokens.
Mapping: 4→`--g-s-1`, 8→`--g-s-2`, 12→`--g-s-3`, 16→`--g-s-4`, 20→`--g-s-5`, 24→`--g-s-6`, 32→`--g-s-8`, 40→`--g-s-10`.

## Implementation Details

### 1. `SetupResumeCard.svelte` — Checkliste-Icons

Ersetze ✓/○ durch `<Dot>` atom:
```svelte
<Dot tone={step.done ? 'good' : 'neutral'} size={8} />
```
Importiere `<Dot>` aus `$lib/components/atoms`.

### 2. `SetupResumeCard.svelte` — CTA-Button

Ersetze hand-styled `<a>` durch:
```svelte
<Btn href={ctaHref} variant={isAccent ? 'accent' : 'primary'} size="md">
  {ctaLabel} →
</Btn>
```

### 3. `+page.svelte` — Page-Header

Ersetze custom `<header>` durch `<PageHeader>`:
```svelte
<PageHeader eyebrow="Übersicht · {todayPretty}" title="Deine Touren & Vergleiche" sub="...">
  {#snippet right()}
    <Btn href="/compare" variant="ghost" size="sm">Neuer Vergleich</Btn>
    <Btn href="/trips/new" variant="primary" size="sm">+ Neuer Trip</Btn>
  {/snippet}
</PageHeader>
```

### 4. `QuickAction.svelte` — Glyphen

Verwende Lucide-Icons aus dem bestehenden `$lib/icons`-System (sofern vorhanden)
oder ersetze Unicode-Sonderzeichen durch druckbare ASCII-Monospace-Zeichen
die keine Sonderzeichen sind. Prüfe zuerst ob `WIcon` oder ein Lucide-Atom
die nötigen Glyphen hat.

### 5. Token-Korrekturen überall

- `--g-success` → `--g-good`
- `--g-ink-on-accent` entfernen, Fallback `#ffffff` → `var(--g-paper)`
- Alle Literal-Hex → Token
- Spacing-Pixel → `--g-s-*`
- Font-Größen auf Token-Scale anpassen
- Letter-Spacing → `--g-track-*`

### 6. Live-Pill

`<Dot tone="bad" />` → `<Dot tone="good" />` in der aktiv-Trip-Pill.

## Acceptance Criteria

**AC-1:** Given `SetupResumeCard` rendert Schritt-Checkliste, When ein Schritt erledigt ist, Then zeigt `<Dot tone="good">` statt `✓`-Zeichens; offene Schritte zeigen `<Dot tone="neutral">` statt `○`.

**AC-2:** Given `SetupResumeCard` rendert CTA-Bereich, When `tone="accent"`, Then ist der CTA-Link ein `<Btn variant="accent">` Atom (kein hand-styled `<a>`).

**AC-3:** Given `+page.svelte` rendert den Seiten-Header, When die Seite geladen wird, Then ist der Header ein `<PageHeader>`-Atom mit `eyebrow`, `title` und `sub`-Props (kein custom `<header>`).

**AC-4:** Given die betroffenen Dateien `+page.svelte`, `SetupResumeCard.svelte`, `QuickAction.svelte`, When `grep -rn '[0-9]\+px' frontend/src/routes/+page.svelte frontend/src/lib/components/molecules/SetupResumeCard.svelte frontend/src/lib/components/molecules/QuickAction.svelte` läuft, Then gibt es keine freien Pixel-Werte mehr für Schriftgrößen außerhalb der Token-Scale.

**AC-5:** Given die betroffenen Dateien, When `grep -n 'g-success\|g-ink-on-accent\|#ffffff\|#[0-9a-fA-F]\{3,6\}' <files>` läuft, Then gibt es keine Treffer mehr (alle Token-Namen korrekt, kein Inline-Hex).

**AC-6:** Given `+page.svelte` rendert die aktiv-Trip-Pill, When ein Trip aktiv ist, Then zeigt die Pill `<Dot tone="good" />` (grün), nicht `tone="bad"` (rot).

**AC-7:** Given `QuickAction.svelte` rendert Glyph-Icons, When Glyphen angezeigt werden, Then sind es keine Unicode-Sonderzeichen (◆◷◉◐▸‖) — stattdessen Catalog-Icons oder `<WIcon>`.

**AC-8:** Given alle betroffenen Dateien, When `grep -n 'letter-spacing: "[0-9]\+\.[0-9]\+em"' <files>` läuft, Then gibt es keine freien em-Werte mehr (nur `var(--g-track-*)` Referenzen).

**AC-9:** Given die Seite im Browser auf Staging, When die Startseite geladen wird, Then sind alle drei Modi (planning/compare/trip) optisch unverändert bis auf die korrigierten Details (kein Regressionstest auf Farbwerte, die bereits korrekt waren).

**AC-10:** Given `uv run pytest tests/` nach dem Fix, When alle Tests laufen, Then ist kein Test rot geworden.

## Known Limitations

- `PageHeader`-Atom muss `right`-Slot unterstützen — ggf. Prop-Erweiterung nötig
- `QuickAction`-Glyphen: Falls kein passendes Catalog-Icon, bleibt ASCII-Fallback mit Kommentar erlaubt (z.B. `▶` → `>` in Mono)
- Spacing-Token-Migration: `.cockpit-hero` CSS-Grid-Werte im `<style>`-Block sind von dieser Spec explizit ausgenommen (Strukturwerte, kein Spacing-Token-Ersatz nötig)

## Changelog

- 2026-06-03: Spec erstellt nach Code-Audit von #568/#571
