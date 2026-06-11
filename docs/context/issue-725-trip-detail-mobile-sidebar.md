# Context: Issue #725 — Trip-Detail Mobile: Sidebar bleibt sichtbar (aside.hidden rendert display:flex)

## Request Summary
Bei Viewport ≤899px bleibt die 220px breite Desktop-Sidebar (`<aside>`) sichtbar, obwohl sie per `class="hidden desktop:flex"` versteckt sein sollte. Folge: `<main>` schrumpft auf ~155px (statt ~375px), alle Trip-Detail-Tabs wirken gequetscht. Die Sidebar sitzt global im Layout — der Bug betrifft alle Mobile-Seiten, entdeckt wurde er auf Trip-Detail.

## Root Cause (eindeutig)
`frontend/src/lib/components/ui/sidebar/Sidebar.svelte`, Desktop-`<aside>` (Z.64–80):
- Z.71 enthält im **Inline-`style`** die Deklaration `display: flex;`
- Z.79 trägt zugleich `class="hidden desktop:flex"`

**Inline-Styles haben höhere CSS-Spezifität als jede Utility-Klasse.** Daher überschreibt das Inline-`display: flex` die Tailwind-Klasse `.hidden { display: none }` auf **jedem** Viewport. Die Sidebar ist immer `display:flex` — die Visibility-Klassen sind wirkungslos. Das erklärt exakt den Befund „computed-style zeigt display:flex".

Tailwind v4 ist korrekt konfiguriert (app.css:50 `@custom-variant desktop { @media (min-width: 900px) }`). `hidden`/`desktop:flex` werden generiert — sie verlieren nur gegen den Inline-Style.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte:64-80` | Desktop-`<aside>` mit kollidierendem Inline-`display: flex` (Z.71) — **Fix hier** |
| `frontend/src/routes/+layout.svelte:71-86` | Bindet `<Sidebar>` + `<main flex-1>` + `<BottomNav>` global ein; Mobile-Nav = BottomNav, Desktop-aside soll versteckt sein |
| `frontend/src/app.css:49-50` | `@custom-variant mobile/desktop` (Breakpoint 900px) — korrekt |
| `frontend/src/routes/trips/+page.svelte:324` | Zweiter `hidden desktop:flex`-Fundort, **ohne** Inline-display → kein Bug |

## Mobile-Drawer (nicht betroffen)
`Sidebar.svelte` Z.51 (`{#if mobileMenuOpen}`) + Z.210 (eigener Block mit `flex translate-x-0` / `hidden -translate-x-full`) ist der separate Mobile-Hamburger-Drawer, gesteuert über `mobileMenuOpen`. Der Fix am Desktop-`<aside>` berührt ihn nicht.

## Fix-Strategie
Das `display: flex;` aus dem Inline-`style` des Desktop-`<aside>` entfernen. Danach:
- **<900px:** `.hidden` → `display:none` → Sidebar versteckt, `<main>` voll breit, BottomNav navigiert. ✓
- **≥900px:** `desktop:flex` → `display:flex`, übrige Inline-Styles (`flex-direction: column` etc.) greifen → Desktop unverändert. ✓

Kanonisches Tailwind-Pattern `hidden desktop:flex`. 1:1-JSX-Treue der übrigen Inline-Styles bleibt gewahrt (nur die `display`-Zeile entfällt, weil Visibility nun über Klassen läuft).

## Tests / Regression
- TDD-RED: Playwright @375px gegen Staging — `aside[data-testid="desktop-sidebar"]` muss `display:none` / width 0 sein; `<main>` ~ volle Viewport-Breite. RED vor Fix (220px), GRÜN nach Fix.
- Desktop-Regression: @≥900px muss die Sidebar weiterhin 220px sichtbar sein.
- Bestehende relevante Specs: `frontend/e2e/mobile-bottom-nav.spec.ts`, `bug-320-sidebar-archiv.spec.ts`, `nav-redesign.spec.ts`.

## Risks & Considerations
- **Globale Wirkung:** Fix betrifft alle Seiten (Sidebar ist im globalen Layout) — positiv, behebt das Problem überall, nicht nur Trip-Detail.
- **Desktop darf nicht brechen:** `desktop:flex` muss zuverlässig greifen (tut es; Klasse im Markup → von Tailwind generiert).
- Scope minimal (1 entfernte Inline-Deklaration), frontend-only, kein Backend/Schema.
