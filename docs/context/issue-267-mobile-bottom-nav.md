# Context: Issue #267 – Mobile Bottom-Navigation

## Request Summary

Auf Viewports unter 900 px fehlt eine Bottom-Navigation. Die 4 Workspace-Bereiche (Übersicht, Trips, Vergleich, Locations) sind nur über einen Hamburger-Drawer erreichbar. Ziel: `BottomNav.svelte` + angepasste App-Shell (TopAppBar + Drawer) gemäß Mobile-Design-Spec.

## Ist-Zustand

| Datei | Zustand |
|-------|---------|
| `frontend/src/routes/+layout.svelte` | Rendert immer Desktop-Sidebar; kein BottomNav; `<main>` hat `pt-16 md:pt-6` für Mobile-TopBar |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | Enthält Mobile-TopBar (`md:hidden`) + Hamburger + Slide-in-Drawer mit **allen** Nav-Items + Account-Footer |
| `frontend/src/app.css` | Kein `gz-screen-padding`, kein `--g-paper-deep`, kein `--g-rule-soft` |

**Aktuelle Nav-Items in Sidebar:** 3 Items: Startseite (`/`), Meine Touren (`/trips`), Orts-Vergleich (`/compare`)

**Fehlend:** 4. Item "Locations" (`/locations`) — Route existiert (`frontend/src/routes/locations/+page.svelte`).

## Relevante Dateien

| Datei | Relevanz |
|-------|---------|
| `frontend/src/routes/+layout.svelte` | Root-Layout — hier wird BottomNav eingebunden |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | Bestehende Sidebar + Mobile-TopBar + Drawer — Refactoring nötig |
| `frontend/src/lib/components/ui/sidebar/index.ts` | Export — ggf. neue Komponenten re-exportieren |
| `frontend/src/app.css` | Design-Tokens, Breakpoints — `gz-screen-padding` + fehlende Tokens ergänzen |
| `frontend/src/routes/locations/+page.svelte` | Bestehendes Locations-Ziel für 4. Nav-Item |

## Design-Spec (mobile-audit/2026-05-20 Branch)

**Quell-Dateien:** `docs/design/mobile/mobile-shell.jsx` + `docs/design/mobile/README.md`

### BottomNav
- Höhe: **64 px** (BOTTOMNAV_H)
- 4 Grid-Spalten: Übersicht · Trips · Vergleich · Locations
- Aktives Item: 28 × 2 px Akzent-Linie oben (`--g-accent`)
- Safe-Area: `padding-bottom: env(safe-area-inset-bottom)`
- Hintergrund: `--g-paper-deep` (in Spec; **fehlt** in `app.css` → Ersatz: `--g-surface-1`)
- Border-Top: `--g-rule-soft` (in Spec; **fehlt** in `app.css` → Ersatz: `var(--color-border)`)

### TopAppBar
- Höhe: **56 px** (TOPBAR_H)
- Links: Hamburger-Button (öffnet Drawer)
- Mitte: Titel "Gregor 20"
- Rechts: optionale Aktion (z.B. Dark-Mode-Toggle)
- Breakpoint: `md:hidden` (d.h. < 768 px mit Tailwind, aber Issue sagt 900 px → `@media (max-width: 899px)`)

### Drawer (sekundäre Navigation)
- Öffnet sich per Hamburger-Button
- Enthält: Konto, System-Status, Dark Mode, Abmelden
- Enthält NICHT mehr: Workspace-Hauptbereiche (die sind jetzt in BottomNav)

## Token-Mapping (Spec → app.css)

| Spec-Token | Status | Ersatz |
|-----------|--------|--------|
| `--g-paper-deep` | fehlt | `--g-surface-1` (#edeae1) oder neu anlegen |
| `--g-rule-soft` | fehlt | `var(--color-border)` = `--g-ink-faint` (#9c9a90) |
| `--g-ink-3` | fehlt | `--g-ink-muted` |
| `--g-accent` | ✓ | #c45a2a |
| `--g-ink` | ✓ | #1a1a18 |
| `--g-ink-faint` | ✓ | #9c9a90 |

## Breakpoint-Logik

Laut Issue-Spec: **900 px**. Tailwind `md:` = 768 px (stimmt nicht überein).
→ Neue CSS-Klassen in `app.css` mit `@media (max-width: 899px)` / `@media (min-width: 900px)`.

## Bestehende Patterns

- Dark-Mode-Toggle: via `ontoggleDark`-Callback von Root-Layout an Sidebar
- Auth-Check: `publicPages` Array in `+layout.svelte` → Navigation nur wenn NICHT Login-Page
- Active-State: `currentPath === item.href` per Prop (nicht Svelte-Router)
- Sidebar-Export: `frontend/src/lib/components/ui/sidebar/index.ts`

## Abhängigkeiten

**Upstream:** `page.url.pathname` (SvelteKit), `data.userId` vom Layout-Server
**Downstream:** `+layout.svelte` als einziger Konsument der Sidebar/Nav-Komponenten

## Risiken

1. **Token-Drift:** `--g-paper-deep` und `--g-rule-soft` in app.css fehlen → können ergänzt oder Alias-Tokens definiert werden
2. **Breakpoint-Inkonsistenz:** Tailwind `md:` (768 px) vs. Issue-Spec (900 px) → braucht explizite CSS-Media-Queries statt Tailwind-Klassen für BottomNav
3. **Sidebar-Umbau:** Bestehende `Sidebar.svelte` macht heute Mobile-Top-Bar + Drawer. Refactoring muss Desktop-Sidebar unangetastet lassen
4. **4. Nav-Item:** "Locations" bislang nicht in Sidebar — muss zum Desktop-Sidebar hinzugefügt werden (für Konsistenz)
5. **Safe-Area:** `env(safe-area-inset-bottom)` muss in `<main>` als `padding-bottom` ergänzt werden, damit Inhalte nicht unter BottomNav verschwinden

## Ähnliche Implementierungen

- `Sidebar.svelte:44–59` — Mobile-TopBar-Pattern (als Vorlage für TopAppBar)
- `Sidebar.svelte:72–87` — Desktop-Nav-Item-Pattern (active state, currentPath)
