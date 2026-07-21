---
entity_id: epic_133_design_system_lauf_a
type: module
created: 2026-05-08
updated: 2026-05-08
status: completed
version: "1.0"
tags: [sveltekit, frontend, css, design-system, epic-133]
---

# Epic 133 — Design-System Lauf A (Issues #141, #142, #145)

## Approval

- [x] Approved and Implemented

## Purpose

Etabliert ein einheitliches Design-Token-System (`--g-*`-Namespace) fuer das Gregor-Frontend und extrahiert die Sidebar-Navigation in eine eigenstaendige Svelte-Komponente. Damit wird eine gemeinsame visuelle Sprache (Farben, Typografie, Radii, Elevation) definiert, die alle kuenftigen UI-Komponenten als Single Source of Truth nutzen koennen, und die Navigation so modularisiert, dass sie unabhaengig weiterentwickelt und getestet werden kann.

## Source

- **Issue #141 — Design-Tokens:** `frontend/src/app.css` **(EDIT)**
- **Issue #142 — Schriften:** `frontend/src/app.html` **(EDIT)**
- **Issue #145 — Sidebar-Extraktion:**
  - `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` **(NEU)**
  - `frontend/src/lib/components/ui/sidebar/index.ts` **(NEU)**
  - `frontend/src/routes/+layout.svelte` **(EDIT)**

## Abhaengigkeiten

| Entity | Typ | Zweck |
|--------|-----|-------|
| `frontend/src/app.css` | file | Aufnahme des `@layer base`-Blocks mit `--g-*`-Tokens |
| `frontend/src/app.html` | file | Einbinden der Google-Fonts via `<link>` |
| `frontend/src/routes/+layout.svelte` | file | Wird um Sidebar-Block reduziert; importiert neue Sidebar-Komponente |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | file (neu) | Eigenstaendige Sidebar-Komponente mit Props-Interface |
| `frontend/src/lib/components/ui/sidebar/index.ts` | file (neu) | Re-Export fuer `$lib/components/ui/sidebar`-Import-Pfad |
| `frontend/e2e/nav-redesign.spec.ts` | test | 7 E2E-Tests sind Akzeptanzkriterium fuer Issue #145 |
| `lucide-svelte` | package | Icons (`LayoutDashboard`, `RouteIcon`, `GitCompare`) bleiben in Sidebar.svelte |
| Google Fonts CDN | external | Inter Tight (400/500/600) + JetBrains Mono (400) |

## Implementierungsdetails

### Issue #141 — Design-Tokens in app.css portieren

In `frontend/src/app.css` wird **nach** dem bestehenden `@theme`-Block ein neuer `@layer base`-Block eingefuegt. Der `@theme`-Block (shadcn `--color-*` und `--radius-*`) bleibt vollstaendig unberuehrt.

**Neuer Block:**

```css
@layer base {
  :root {
    /* === Gregor-Design-Tokens (--g-* Namespace) === */

    /* Primaerfarben */
    --g-accent:       #c45a2a;   /* burnt orange — Akzente, CTAs */
    --g-paper:        #f6f4ee;   /* warm off-white — Seiten-Hintergrund */
    --g-ink:          #1a1a18;   /* fast schwarz — Haupttext */

    /* Surface-Stufen */
    --g-surface-0:    #f6f4ee;   /* = paper */
    --g-surface-1:    #edeae1;   /* Card-Hintergrund */
    --g-surface-2:    #e3dfd4;   /* Hover/aktive Flaechen */

    /* Ink-Stufen */
    --g-ink-muted:    #5c5a52;   /* Sekundaertext */
    --g-ink-faint:    #9c9a90;   /* Platzhalter, Metadaten */

    /* Semantic */
    --g-success:      #3a7d44;
    --g-warning:      #c8882a;
    --g-danger:       #b33a2a;
    --g-info:         #2a6cb3;

    /* Wetter-Farben (6 Zustaende) */
    --g-wx-rain:      #4a7fb5;
    --g-wx-sun:       #e8a820;
    --g-wx-wind:      #6b8a8a;
    --g-wx-snow:      #a8c8e8;
    --g-wx-thunder:   #5a3a7a;
    --g-wx-fog:       #9a9a8a;

    /* Typografie */
    --g-font-ui:      'Inter Tight', system-ui, sans-serif;
    --g-font-data:    'JetBrains Mono', ui-monospace, monospace;

    /* Radii */
    --g-radius-xs:    0.125rem;
    --g-radius-sm:    0.25rem;
    --g-radius-md:    0.5rem;
    --g-radius-lg:    0.75rem;
    --g-radius-pill:  99rem;

    /* Elevation */
    --g-elev-1: 0 1px 3px rgba(26,26,24,0.08);
    --g-elev-2: 0 4px 12px rgba(26,26,24,0.12);
    --g-elev-3: 0 8px 24px rgba(26,26,24,0.16);
  }

  body {
    font-family: var(--g-font-ui);
  }
}
```

**Wichtig:** Der `body`-Selektor in `@layer base` ersetzt den bisherigen `font-family: system-ui, -apple-system, sans-serif` durch `font-family: var(--g-font-ui)`. Falls `body` bereits in `@layer base` existiert, wird nur die `font-family`-Zeile ersetzt; alle anderen `body`-Regeln bleiben erhalten.

---

### Issue #142 — Schriften einbinden

In `frontend/src/app.html` werden im `<head>` **vor** `%sveltekit.head%` drei `<link>`-Tags eingefuegt:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap">
```

Damit stehen `Inter Tight` und `JetBrains Mono` als Web-Fonts bereit, bevor die App rendert.

---

### Issue #145 — Sidebar-Komponente extrahieren

#### Schritt 1: `Sidebar.svelte` anlegen

Neue Datei `frontend/src/lib/components/ui/sidebar/Sidebar.svelte`. Die Komponente verwendet SvelteKit 5 Runes.

**Props-Interface:**

```typescript
interface SidebarProps {
  userId: string | null | undefined;  // fuer Avatar-Initial
  currentPath: string;                // fuer Active-State-Highlighting
  darkMode: boolean;                  // fuer Dark-Mode-Toggle-Icon
  ontoggleDark: () => void;           // Callback fuer Dark-Mode-Toggle
}

let { userId, currentPath, darkMode, ontoggleDark }: SidebarProps = $props();
```

**Interner State:**

```typescript
let mobileMenuOpen = $state(false);
let userMenuOpen = $state(false);
```

**Nav-Items (KRITISCH: Label muss exakt 'Meine Touren' sein):**

```typescript
const navItems = [
  { href: '/',        label: 'Startseite',    icon: LayoutDashboard },
  { href: '/trips',   label: 'Meine Touren',  icon: RouteIcon },
  { href: '/compare', label: 'Orts-Vergleich', icon: GitCompare },
];
```

**Extrahierter Inhalt aus `+layout.svelte`:**

- Mobile Top-Bar (`<div class="fixed top-0 ... md:hidden">`)
- Mobile-Overlay (`<div class="fixed inset-0 z-40 bg-black/50 md:hidden">`)
- Das `<nav>`-Element mit allen Nav-Items und dem User-Menu-Dropdown

Der Active-State-Vergleich (`currentPath === item.href`) bleibt identisch zur bisherigen Logik in `+layout.svelte`.

#### Schritt 2: `index.ts` anlegen

Neue Datei `frontend/src/lib/components/ui/sidebar/index.ts`:

```typescript
export { default as Sidebar } from './Sidebar.svelte';
```

#### Schritt 3: `+layout.svelte` anpassen

- `import { Sidebar } from '$lib/components/ui/sidebar';` hinzufuegen
- Den extrahierten Sidebar-Block durch `<Sidebar userId={data.userId} currentPath={page.url.pathname} darkMode={darkMode} ontoggleDark={toggleDark} />` ersetzen
- `mobileMenuOpen`-State und zugehoerige Overlay-Logik aus `+layout.svelte` entfernen (liegen nun in Sidebar.svelte)
- `darkVars`, `applyDarkMode()`, `toggleDark()` bleiben in `+layout.svelte` (Dark-Mode-Logik bleibt zentral)
- Das aeussere `<div class="flex h-screen">` bleibt in `+layout.svelte`
- Das `<main>`-Element (inkl. `pt-16 md:pt-6`-Padding) bleibt in `+layout.svelte`
- Icon-Imports fuer extrahierte Nav-Items (`LayoutDashboard`, `RouteIcon`, `GitCompare`) wandern nach `Sidebar.svelte`; nur noch verwendete Icons bleiben in `+layout.svelte`

---

## Expected Behavior

- **Input:** User oeffnet die App im Browser
- **Output:**
  - Schriftart der gesamten App ist Inter Tight (vorher system-ui)
  - Alle `--g-*`-CSS-Tokens sind global verfuegbar und koennen von beliebigen Komponenten genutzt werden
  - Sidebar rendert identisch zum Ist-Zustand (Mobile Top-Bar, Overlay, Nav, User-Menu)
  - Nav-Label fuer `/trips` lautet 'Meine Touren' (Bug-Fix gegenueber bisherigem 'Meine Trips')
- **Active-State:** Highlighting des aktuellen Nav-Eintrags funktioniert unveraendert per pathname-Match
- **Side effects:**
  - 7 E2E-Tests in `frontend/e2e/nav-redesign.spec.ts` muessen nach Extraktion gruen bleiben
  - Keine visuellen Regressionen in bestehenden Seiten (Token-System ist additiv, aendert keine bestehenden Klassen)

## Was sich NICHT aendert

- Bestehender `@theme`-Block in `app.css` (shadcn `--color-*` und `--radius-*`) bleibt vollstaendig unveraendert
- Keine npm-Pakete werden hinzugefuegt oder entfernt
- Routen, Datenbankschema, API-Endpoints — unveraendert
- User-Menu-Logik (Konto, System-Status, Dark Mode, Abmelden) — unveraendert
- Dark-Mode-Logik bleibt zentral in `+layout.svelte`

## Akzeptanzkriterien

| # | Kriterium | Pruefung | Status |
|---|-----------|----------|--------|
| 1 | `--g-accent`, `--g-paper`, `--g-ink` sind im Browser-DevTools unter `:root` sichtbar | DevTools → Computed → filter `--g-` | PASS (alle 30 Tokens sichtbar) |
| 2 | Inter Tight wird als Schriftart geladen | DevTools → Network → Fonts | PASS (fonts.googleapis.com link vorhanden) |
| 3 | Nav-Label `/trips` lautet 'Meine Touren' | Sidebar visuell + E2E | PASS (in Sidebar.svelte gesetzt) |
| 4 | E2E-Tests passen (nav-redesign + design-system) | `npx playwright test` | PASS (7 + 8 = 15 Tests gruen) |
| 5 | Keine visuellen Regressionen auf Startseite, Trips, Orts-Vergleich | Screenshot-Vergleich | PASS (keine Regressionen) |

## Known Limitations

- Google Fonts erfordert Netzwerkverbindung beim ersten Load; bei Offline-Nutzung faellt die App auf system-ui / ui-monospace zurueck (kein funktionaler Schaden)
- `--g-*`-Tokens werden in diesem Lauf nur definiert, nicht auf bestehende Komponenten angewendet — das ist Lauf B

## Changelog

- 2026-05-08: Implementation completed — 30 CSS Tokens, Google Fonts integrated, Sidebar extracted to component
- 2026-05-08: Initial spec fuer Epic 133 Lauf A (Issues #141, #142, #145)
