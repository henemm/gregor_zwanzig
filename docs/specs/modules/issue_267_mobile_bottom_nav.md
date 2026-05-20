---
entity_id: issue_267_mobile_bottom_nav
type: module
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [frontend, mobile, navigation, bottom-nav, app-shell, svelte, responsive, issue-267]
---

# Issue #267 — App-Shell: Bottom-Navigation auf Mobile

## Approval

- [ ] Approved

## Purpose

Auf Viewports unter 900px fehlt eine direkte Navigation zwischen den vier Workspace-Bereichen. Nutzer müssen aktuell einen Hamburger-Drawer in 2–3 Taps öffnen, um die Route zu wechseln. Dieses Modul ergänzt die App-Shell um drei neue Komponenten (`TopAppBar`, `BottomNav`, angepasstes `Sidebar.svelte`) und orchestriert sie im `+layout.svelte`, sodass auf Mobile ein natives App-Gefühl entsteht — ein Tap genügt — während das Desktop-Sidebar-Layout vollständig erhalten bleibt.

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Kein Go-API-Code, kein Python-Backend-Code ist betroffen.

## Source

- **Files:**
  - `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte` (NEU)
  - `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` (NEU)
  - `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` (geändert)
  - `frontend/src/routes/+layout.svelte` (geändert)
  - `frontend/src/app.css` (geändert)

## Dependencies

| Entity | Type | Zweck |
|--------|------|-------|
| `frontend/src/app.css` | CSS-Datei (vorhanden) | Empfängt 2 neue Design-Tokens (`--g-paper-deep`, `--g-rule-soft`), 2 neue `@custom-variant`-Definitionen (`mobile:`, `desktop:`) und die Utility-Klasse `.mobile-scroll-pad` |
| `frontend/src/routes/+layout.svelte` | SvelteKit-Layout (vorhanden) | Orchestriert TopAppBar, Sidebar und BottomNav; hält `mobileMenuOpen`-State |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | Svelte-Komponente (vorhanden) | Wird auf Desktop-Only reduziert; erhält Locations als 4. NavItem; akzeptiert `mobileMenuOpen` als `$bindable()`-Prop |
| `lucide-svelte` | Icon-Bibliothek (vorhanden) | `LayoutDashboard`, `Route`, `GitCompare`, `MapPin`, `Menu`, `X`, `Moon`, `Sun` |
| `$app/navigation` (SvelteKit) | Framework-Utility | `page`-Store für aktive Route-Erkennung in `BottomNav` und `TopAppBar` |
| Design-System `--g-accent`, `--g-ink`, `--g-ink-muted`, `--g-paper` | CSS-Custom-Properties (vorhanden) | Farben für aktiven Zustand, Labels, Hintergrund |

## Scope

**Nur Frontend. 5 Dateien:**

- **Neu:** `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte`
- **Neu:** `frontend/src/lib/components/ui/sidebar/BottomNav.svelte`
- **Geändert:** `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` — Mobile-Blöcke entfernen, 4. NavItem Locations ergänzen, `mobileMenuOpen`-Bindung
- **Geändert:** `frontend/src/routes/+layout.svelte` — TopAppBar und BottomNav einbinden, `mobileMenuOpen`-State
- **Geändert:** `frontend/src/app.css` — 2 neue Tokens, 2 `@custom-variant`, 1 Utility-Klasse

Keine Änderungen an:
- Go-Backend, Python-Backend
- Anderen Frontend-Komponenten oder Routes

## Implementation Details

### 1. `app.css` — Neue Tokens, Varianten, Utility-Klasse

**Zwei neue Design-Tokens** ans Ende des `:root`-Blocks anfügen:

```css
--g-paper-deep: #ede9df;   /* BottomNav-Hintergrund — etwas dunkler als --g-surface-1 */
--g-rule-soft: rgba(26, 26, 24, 0.08);  /* Border/Separator für BottomNav und TopAppBar */
```

**Zwei `@custom-variant`-Definitionen** direkt nach den bestehenden Tailwind-Layer-Imports einfügen:

```css
@custom-variant mobile (&:is(:where([data-viewport=mobile]) *));
/* Breakpoint < 900px — aktiviert auf body[data-viewport="mobile"] */

@custom-variant desktop (&:is(:where([data-viewport=desktop]) *));
/* Breakpoint >= 900px — aktiviert auf body[data-viewport="desktop"] */
```

Alternativ als echte Media-Query-Varianten (bevorzugt, da kein JS-Datenbindung nötig):

```css
@custom-variant mobile { @media (max-width: 899px) { @slot; } }
@custom-variant desktop { @media (min-width: 900px) { @slot; } }
```

**Utility-Klasse `.mobile-scroll-pad`** (kann nicht als Tailwind-Arbitrary-Value ausgedrückt werden, weil `env()` runtime-only ist):

```css
.mobile-scroll-pad {
  padding-bottom: calc(64px + env(safe-area-inset-bottom));
}
```

**Alle bestehenden `md:`-Klassen** in `Sidebar.svelte` und `+layout.svelte` auf `desktop:` umstellen — der bisherige Tailwind-Breakpoint `md:` bricht bei 768px statt 900px.

### 2. `TopAppBar.svelte` (NEU, ~38 LoC)

Aufbau und Props:

```typescript
interface Props {
  mobileMenuOpen: boolean;
}
let { mobileMenuOpen = $bindable() }: Props = $props();
```

Layout-Struktur (Höhe 56px, `position: fixed; top: 0; left: 0; right: 0; z-index: 60`):

```
[Hamburger-Button] -------- [Gregor 20] -------- [Dark-Mode-Toggle]
```

- **Links:** `<button>` mit Lucide `Menu`- oder `X`-Icon je nach `mobileMenuOpen`-State; `onclick` togglet `mobileMenuOpen`
- **Mitte:** `<span class="font-bold">Gregor 20</span>`
- **Rechts:** Dark-Mode-Toggle-Button mit `Moon`/`Sun`-Icon (liest und schreibt `document.documentElement.dataset.theme` oder das bestehende Dark-Mode-Store-Pattern des Projekts)
- **Styling:** `background: var(--g-paper); border-bottom: 1px solid var(--g-rule-soft);`
- **Nur auf Mobile sichtbar:** `class="desktop:hidden"`

### 3. `BottomNav.svelte` (NEU, ~62 LoC)

```typescript
// Keine Props — Route-Erkennung intern via page-Store
import { page } from '$app/stores';

const NAV_ITEMS = [
  { label: 'Übersicht', href: '/',          icon: LayoutDashboard },
  { label: 'Trips',     href: '/trips',     icon: Route           },
  { label: 'Vergleich', href: '/compare',   icon: GitCompare      },
  { label: 'Locations', href: '/locations', icon: MapPin          },
] as const;
```

Layout und Styling:

- `position: fixed; bottom: 0; left: 0; right: 0; z-index: 50`
- Höhe: 64px + `env(safe-area-inset-bottom)` → `padding-bottom: env(safe-area-inset-bottom)`
- Hintergrund: `var(--g-paper-deep)`, `border-top: 1px solid var(--g-rule-soft)`
- 4-spaltiges Grid: `display: grid; grid-template-columns: repeat(4, 1fr);`
- **Nur auf Mobile sichtbar:** `class="desktop:hidden"`

Jedes Grid-Item (`<a href={item.href}>`):

- Aktiv-Erkennung: `$derived($page.url.pathname === item.href)` (für `/` exakter Match, für andere: `$page.url.pathname.startsWith(item.href)`)
- Icon-Größe: 22px
- Label: 10px, `font-weight: 600` aktiv / `500` inaktiv
- Farbe: `var(--g-ink)` aktiv / `var(--g-ink-muted)` inaktiv
- Akzent-Linie oben bei aktivem Item: `box-shadow: inset 0 2px 0 var(--g-accent)`
- Touch-Target: Mindesthöhe 44px innerhalb der 64px-Leiste

### 4. `Sidebar.svelte` — Anpassungen (~100 LoC, Netto −51)

**Entfernen:** Alle Mobile-spezifischen Blöcke (Hamburger-Trigger, Overlay, mobile Öffnen/Schließen-Logik). Die Sidebar ist fortan ausschließlich Desktop-Only.

**Hinzufügen:** 4. NavItem für Locations:

```svelte
<a href="/locations" class:active={$page.url.pathname.startsWith('/locations')}>
  <MapPin size={18} />
  <span>Locations</span>
</a>
```

**Akzeptieren:** `mobileMenuOpen` als `$bindable()`-Prop für den Drawer-Mechanismus:

```typescript
interface Props {
  mobileMenuOpen: boolean;
}
let { mobileMenuOpen = $bindable(false) }: Props = $props();
```

Der Sidebar-Drawer öffnet sich auf Mobile nur noch für sekundäre Items (Konto, System-Status, Dark Mode, Logout). Die 4 Workspace-Routen (`/`, `/trips`, `/compare`, `/locations`) werden aus dem Drawer entfernt.

**`md:`-Klassen auf `desktop:` umstellen** — alle Vorkommen von `md:flex`, `md:hidden`, `md:block` etc. in der Sidebar-Template auf `desktop:`-Variante umstellen.

### 5. `+layout.svelte` — Orchestrierung (~88 LoC, +12)

```typescript
import TopAppBar from '$lib/components/ui/sidebar/TopAppBar.svelte';
import BottomNav from '$lib/components/ui/sidebar/BottomNav.svelte';

let mobileMenuOpen = $state(false);
```

Template-Struktur:

```svelte
<TopAppBar bind:mobileMenuOpen />

<div class="desktop:flex h-screen">
  <Sidebar bind:mobileMenuOpen />

  <main class="flex-1 overflow-y-auto mobile:scroll-pad">
    {@render children()}
  </main>
</div>

<BottomNav />
```

- `<main>` bekommt `padding-top: 56px` auf Mobile (via Tailwind `mobile:pt-14`), damit TopAppBar den Content nicht überdeckt
- `<main>` bekommt die Klasse `mobile-scroll-pad` (aus app.css), damit die BottomNav den Content nicht überdeckt
- **Alle `md:`-Klassen** im Layout auf `desktop:` umstellen

### 6. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/app.css` | +12 | ja |
| `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte` | +38 (NEU) | ja |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` | +62 (NEU) | ja |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | −51 (Netto) | ja |
| `frontend/src/routes/+layout.svelte` | +12 | ja |
| **Gesamt** | **~73** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Keine externen Daten-Inputs; alle Komponenten reagieren auf `$page.url.pathname` (SvelteKit-Store) und den lokalen `mobileMenuOpen`-State
- **Output (visuell):**
  - Viewport < 900px: TopAppBar oben, BottomNav unten fixiert, Sidebar nur als Drawer für sekundäre Items
  - Viewport ≥ 900px: Sidebar links wie bisher, TopAppBar und BottomNav nicht sichtbar (`desktop:hidden`)
- **Side effects:** `mobileMenuOpen`-State steuert Drawer-Öffnung via `$bindable()`-Binding zwischen `+layout.svelte`, `TopAppBar.svelte` und `Sidebar.svelte`. Kein API-Call, kein Backend-Zugriff.

## Acceptance Criteria

**AC-1:** Given ein Viewport kleiner als 900px / When eine beliebige Route der App geöffnet wird / Then ist eine fixierte TopAppBar (Höhe 56px) mit Hamburger-Button links, Titel "Gregor 20" in der Mitte und Dark-Mode-Toggle rechts sichtbar, und die Desktop-Sidebar ist nicht sichtbar.

**AC-2:** Given ein Viewport kleiner als 900px / When eine beliebige Route der App geöffnet wird / Then ist eine fixierte BottomNav (Höhe 64px) mit genau 4 Items — "Übersicht", "Trips", "Vergleich", "Locations" — sichtbar, und das aktuell aktive Item zeigt eine farbige Akzent-Linie oben sowie einen fettgedruckten Label.

**AC-3:** Given die BottomNav auf Mobile angezeigt wird / When der Nutzer auf "Trips" tippt / Then navigiert die App zur Route `/trips`, und nur das "Trips"-Item zeigt die Akzent-Linie (`box-shadow: inset 0 2px 0 var(--g-accent)`); alle anderen Items haben keine Akzent-Linie.

**AC-4:** Given ein Viewport kleiner als 900px / When der Hamburger-Button in der TopAppBar getippt wird / Then öffnet sich der Drawer und zeigt ausschließlich sekundäre Items (Konto, System-Status, Dark Mode, Logout) — die 4 Workspace-Routen sind im Drawer nicht vorhanden.

**AC-5:** Given ein Gerät mit `env(safe-area-inset-bottom)` > 0 (z.B. iPhone mit Home-Indicator) / When die BottomNav gerendert wird / Then hat die BottomNav ein `padding-bottom` von mindestens `env(safe-area-inset-bottom)`, sodass kein Nav-Item hinter dem System-UI-Bereich verdeckt wird, und der Haupt-Content-Bereich (`<main>`) hat unten genügend Abstand, um nicht hinter der BottomNav zu enden.

**AC-6:** Given ein Viewport größer oder gleich 900px / When eine beliebige Route der App geöffnet wird / Then ist die Desktop-Sidebar mit allen 4 Workspace-Routen (Übersicht, Trips, Vergleich, Locations) sichtbar, und TopAppBar sowie BottomNav sind nicht sichtbar; das bestehende Layout-Verhalten auf Desktop ist unverändert.

**AC-7:** Given die Desktop-Sidebar auf einem Viewport ≥ 900px / When der Nutzer auf "Locations" in der Sidebar klickt / Then navigiert die App zur Route `/locations` und das "Locations"-NavItem ist als aktiv markiert — konsistent zur Markierung in der BottomNav auf Mobile.

## Known Limitations

- **`env(safe-area-inset-bottom)` nur via CSS-Klasse:** Tailwind-Arbitrary-Values unterstützen `env()` nicht zuverlässig als statischer Wert — daher die explizite `.mobile-scroll-pad`-Klasse in `app.css` erforderlich.
- **`$bindable()` Svelte 5:** Die bidirektionale Bindung von `mobileMenuOpen` erfordert Svelte 5-Syntax in allen beteiligten Komponenten. Falls ältere Svelte-Version aktiv ist, muss stattdessen ein Callback-Props-Muster verwendet werden.
- **Breakpoint 900px vs. `md:` (768px):** Alle bestehenden `md:`-Klassen in `Sidebar.svelte` und `+layout.svelte` müssen auf `desktop:` (900px) umgestellt werden — ein vergessenes `md:` würde für Viewports 768–899px ein kaputtes Hybrid-Layout erzeugen.
- **Dark-Mode-Toggle:** Die konkrete Implementierung des Dark-Mode-Toggles hängt vom bestehenden Dark-Mode-Store-Pattern des Projekts ab — hier wird nur der Button-Slot reserviert; der tatsächliche Store-Anschluss wird beim Implementieren verifiziert.

## Affected Files

| Datei | Änderung |
|-------|---------|
| `frontend/src/app.css` | +2 Design-Tokens, +2 `@custom-variant`, +1 Utility-Klasse `.mobile-scroll-pad` |
| `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte` | NEU — fixierte Leiste oben: Hamburger, Titel, Dark-Mode-Toggle |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` | NEU — fixierte Leiste unten: 4 Workspace-NavItems mit Route-Erkennung und Safe-Area |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | Mobile-Blöcke entfernen, `mobileMenuOpen`-Bindung, 4. NavItem Locations, `md:` → `desktop:` |
| `frontend/src/routes/+layout.svelte` | TopAppBar + BottomNav einbinden, `mobileMenuOpen`-State, `md:` → `desktop:` |

## Changelog

- 2026-05-20: Initial spec erstellt (Issue #267 — Mobile Bottom-Navigation + TopAppBar für App-Shell).
