---
entity_id: design_optimierungen
type: module
created: 2026-04-17
updated: 2026-04-17
status: draft
version: "1.0"
tags: [sveltekit, frontend, ui, design, f74]
---

# F74 — Design-Optimierungen (Sidebar, Hintergrund, Footer, Navigation)

## Approval

- [ ] Approved

## Purpose

Verbessert die visuelle Qualitaet des SvelteKit-Frontends in vier gezielten Punkten: Entfernung der Sidebar-Trennlinie, reinweisser Hintergrund im Light Mode, gestalteter Account-Footer am unteren Sidebar-Rand sowie Umbenennung des Nav-Eintrags "Einstellungen" in "System-Status". Alle Aenderungen sind rein kosmetisch und beruehren kein Backend, keine Routes und keine Datenlogik.

## Source

- **File:** `frontend/src/routes/+layout.svelte` **(EDIT, ~15 LoC)**
- **File:** `frontend/src/app.css` **(EDIT, 1 LoC)**
- **File:** `frontend/src/routes/settings/+page.svelte` **(EDIT, 1 LoC)**
- **Identifier:** `<nav>` (Sidebar), `<main>`, Account-Footer-Block, Nav-Item-Label

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `@lucide/svelte/icons/monitor` | Icon (lucide-svelte) | Ersetzt `SettingsIcon` beim Nav-Eintrag "System-Status" — liegt bereits in `node_modules` |
| `@lucide/svelte/icons/user` | Icon (lucide-svelte) | `UserIcon` fuer den Account-Footer in der Sidebar — bereits in `+layout.svelte` importiert (Zeile 68) |

## Implementation Details

### Aenderung 1: Sidebar-Trennlinie entfernen

**Datei:** `frontend/src/routes/+layout.svelte`, Zeile 136

Das `<nav>`-Element traegt die CSS-Klasse `border-r`. Diese Klasse wird ersatzlos entfernt.

```diff
- <nav class="... border-r ...">
+ <nav class="... ...">
```

Betrifft Light Mode und Dark Mode gleichermassen.

### Aenderung 2: Reinweisser Hintergrund im Light Mode

**Datei 2a:** `frontend/src/app.css`, Zeile 4

```diff
- --color-background: oklch(0.985 0 0);
+ --color-background: oklch(1 0 0);
```

**Datei 2b:** `frontend/src/routes/+layout.svelte`, Zeile 181

Das `<main>`-Element traegt die CSS-Klasse `bg-muted/20`. Diese Klasse wird entfernt, damit der Inhaltsbereich denselben reinweissen Hintergrund wie das Root-Element verwendet.

```diff
- <main class="... bg-muted/20 ...">
+ <main class="... ...">
```

Der Dark Mode ist nicht betroffen, da `--color-background` im Dark-Mode-Scope separat definiert ist.

### Aenderung 3: Avatar-Badge mit Dropdown (Linear-Pattern)

**Datei:** `frontend/src/routes/+layout.svelte`

Der bisherige unstyled Block (Username-Text + Logout-Formular) wird durch ein Avatar-Badge mit Dropdown ersetzt. Die Sidebar nutzt `flex flex-col`, der Footer wird via `mt-auto` ans Ende gedrueckt.

**Avatar-Badge (geschlossen):** Farbiger Kreis mit Initiale des Usernamens + Username + Chevron-Icon. Klick oeffnet ein Dropdown-Menue.

**Dropdown-Inhalt:**
- Konto (Link zu `/account`)
- System-Status (Link zu `/settings`)
- Dark Mode Toggle
- Trennlinie
- Abmelden (rot hervorgehoben)

Der Nav-Eintrag "Konto" entfaellt aus der Hauptnavigation — Zugang erfolgt ueber den Footer.

Neue Imports: `ChevronUp`, `LogOut` aus `@lucide/svelte`.

### Aenderung 4: "Einstellungen" → "System-Status"

**Datei 4a:** `frontend/src/routes/+layout.svelte`

- Import: `SettingsIcon` ersetzt durch `MonitorIcon` aus `@lucide/svelte/icons/monitor`
- "Einstellungen" wird aus der Sidebar-Navigation entfernt
- Zugang zu System-Status erfolgt ueber das User-Dropdown im Footer
- Route `/settings` bleibt unveraendert — kein Dateisystem-Rename.

**Datei 4b:** `frontend/src/routes/settings/+page.svelte`, Zeile 41

```diff
- <h1 ...>Einstellungen</h1>
+ <h1 ...>System-Status</h1>
```

## Expected Behavior

- **Input:** Keine Nutzereingabe; rein visuelle Aenderungen ohne Interaktionslogik.
- **Output:** Gegenueber dem Ist-Zustand veraendertes visuelles Erscheinungsbild:
  - Keine sichtbare Trennlinie zwischen Sidebar und Inhaltsbereich
  - Inhaltsbereich erscheint im Light Mode auf reinem Weiss (`#ffffff`) statt leicht grauem Hintergrund
  - Sidebar-Footer zeigt Avatar-Badge (Initiale + Username + Chevron) mit Dropdown-Menue (Konto, System-Status, Dark Mode, Abmelden)
  - "Konto" und "System-Status" sind nur noch ueber das User-Dropdown erreichbar, nicht mehr als Sidebar-Nav-Eintraege
  - Seiten-Heading auf `/settings` lautet "System-Status"
- **Side effects:** Keine. Dark Mode, Mobile Layout (unveraendertes Spacing), Session-Handling und alle Backend-Calls bleiben unberuehrt.

### Nicht-Ziele

- Keine Aenderung an Routes, Dateinamen oder Backend-Endpunkten
- Kein neues State-Management
- Kein CSS-Framework-Wechsel

## Known Limitations

- `window.confirm` wird an keiner Stelle benutzt; nicht relevant.
- Der `border-r`-Entfernung kann je nach Theme-Konfiguration auf sehr breiten Viewports zu einem fliessenden Uebergang fuehren — visuell gewuenscht gemaess Issue #74.

## Changelog

- 2026-04-17: Initial spec (F74 Design-Optimierungen, GitHub Issue #74)
