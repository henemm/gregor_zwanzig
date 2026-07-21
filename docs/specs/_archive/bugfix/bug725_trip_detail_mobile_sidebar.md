---
entity_id: bug725_trip_detail_mobile_sidebar
type: bugfix
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [frontend, layout, sidebar, mobile, responsive, data-integrity]
---

# Bug #725 — Trip-Detail Mobile: Sidebar bleibt sichtbar (aside.hidden rendert display:flex)

## Approval

- [x] Approved (2026-06-10)

## Problem

Bei Viewport ≤899px bleibt die 220px breite Desktop-Sidebar (`<aside>`) sichtbar,
obwohl sie per `class="hidden desktop:flex"` auf Mobile ausgeblendet sein soll.
Folge: der `<main>`-Content schrumpft auf ~155px (bei 375px Viewport, statt ~375px),
und alle Trip-Detail-Tabs (Übersicht, Etappen, Wetter, Alerts) wirken gequetscht.
Die Sidebar sitzt im **globalen Layout** (`+layout.svelte`) — der Defekt betrifft alle
Mobile-Seiten gleichermaßen; entdeckt wurde er auf der Trip-Detail-Seite während der
#702-Staging-Validierung (Playwright, 375×812px).

## Source

- **File:** `frontend/src/lib/components/ui/sidebar/Sidebar.svelte`
- **Identifier:** Desktop-`<aside data-testid="desktop-sidebar">` (Z.64–80), Inline-`style` Z.71

## Estimated Scope

- **LoC:** ~1 entfernte Inline-Deklaration
- **Files:** 1
- **Effort:** low

## Root Cause

Der Desktop-`<aside>` trägt gleichzeitig:

```svelte
<aside
  style="… display: flex; flex-direction: column; …"   <!-- Z.71 -->
  class="hidden desktop:flex"                            <!-- Z.79 -->
>
```

**Inline-Styles haben höhere CSS-Spezifität als jede Utility-Klasse.** Das
Inline-`display: flex` überschreibt daher die Tailwind-Klasse `.hidden { display: none }`
auf **jedem** Viewport. Die Sidebar ist permanent `display:flex` — die Visibility-Klassen
`hidden desktop:flex` sind wirkungslos. Das erklärt exakt den Befund
„computed-style zeigt display:flex".

Tailwind v4 ist korrekt konfiguriert (`app.css:50` —
`@custom-variant desktop { @media (min-width: 900px) }`); die Klassen werden generiert.
Beweis im selben Codebase: `frontend/src/routes/trips/+page.svelte:324` nutzt
`class="hidden desktop:flex"` **ohne** Inline-`display` und blendet auf Mobile korrekt aus.

## Fix

Das `display: flex;` aus dem Inline-`style` des Desktop-`<aside>` entfernen. Die
Sichtbarkeit wird dann ausschließlich über die Klassen gesteuert:

```svelte
<aside
  style="… flex-direction: column; …"   <!-- display: flex entfernt -->
  class="hidden desktop:flex"
>
```

Verhalten danach:
- **<900px:** `.hidden` → `display:none` → Sidebar versteckt, `<main>` volle Breite, BottomNav navigiert.
- **≥900px:** `desktop:flex` → `display:flex`, übrige Inline-Styles (`flex-direction: column` etc.) greifen → Desktop unverändert.

Die übrigen Inline-Styles (1:1-JSX-Treue nach `brand-kit.jsx`) bleiben unangetastet;
nur die `display`-Zeile entfällt, weil die Visibility nun über die Klassen läuft.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Sidebar.svelte` | Frontend-Komponente | Enthält den Desktop-`<aside>` mit dem kollidierenden Inline-`display` — zu ändern |
| `+layout.svelte` | Layout | Bindet `<Sidebar>` + `<main flex-1>` + `<BottomNav>` global ein — kein Change nötig |
| `app.css` | Stylesheet | `@custom-variant desktop` (900px-Breakpoint) — korrekt, kein Change |
| BottomNav | Frontend-Komponente | Mobile-Navigation; übernimmt, wenn die Sidebar versteckt ist — kein Change |

## Expected Behavior

- **Input:** Trip-Detail-Seite `/trips/{id}` (und jede andere App-Seite) bei Viewport <900px
- **Output:** Desktop-`<aside>` ist `display:none` (Breite 0); `<main>` nutzt die volle Viewport-Breite
- **Side effects:** Auf Desktop (≥900px) bleibt die Sidebar unverändert 220px sichtbar; der separate Mobile-Drawer (`mobileMenuOpen`) bleibt voll funktionsfähig

## Acceptance Criteria

**AC-1:** Given die Trip-Detail-Seite `/trips/{id}` ist als eingeloggter Nutzer bei Viewport 375×812px geladen / When der gerenderte DOM geprüft wird / Then ist `aside[data-testid="desktop-sidebar"]` nicht sichtbar (computed `display: none` bzw. `getBoundingClientRect().width === 0`) und der `<main>`-Content-Bereich nimmt nahezu die volle Viewport-Breite ein (Breite > 320px bei 375px Viewport).
- Test: Playwright-E2E gegen Staging als eingeloggter Nutzer, `viewport={width:375,height:812}`. Rot vor Fix (aside.width ≈ 220, main.width ≈ 155), grün nach Fix (aside.width = 0, main.width > 320).

**AC-2:** Given dieselbe Seite bei Desktop-Viewport 1280×800px / When der DOM geprüft wird / Then ist `aside[data-testid="desktop-sidebar"]` sichtbar mit Breite 220px (Desktop-Darstellung unverändert) — keine Regression durch den Fix.
- Test: Playwright-E2E gegen Staging, `viewport={width:1280,height:800}`. Grün vor und nach Fix (Regression-Schutz für Desktop).

**AC-3:** Given die App bei Viewport 375×812px / When der Nutzer das mobile Navigations-Menü öffnet (`mobileMenuOpen` über den TopAppBar-Toggle) / Then erscheint der separate Mobile-Drawer korrekt (sichtbar, eingeblendet) — der Fix am Desktop-`<aside>` beeinträchtigt den Mobile-Drawer nicht.
- Test: Playwright-E2E gegen Staging @375px: Hamburger/Menü-Toggle klicken, prüfen dass der Mobile-Drawer sichtbar wird. Regression-Schutz für die getrennte Mobile-Navigation.

## Known Limitations

- Der Fix wirkt **global** (Sidebar im Layout) — er behebt das Mobile-Sidebar-Problem auf allen Seiten, nicht nur auf Trip-Detail. Das ist beabsichtigt und positiv.
- AC-1/AC-3 prüfen das Layout bei genau einer Mobile-Breite (375px, repräsentativ); andere Mobile-Breiten <900px verhalten sich per Media-Query identisch.

## Changelog

- 2026-06-10: Spec erstellt — Inline-`display: flex` auf dem Desktop-`<aside>` (Sidebar.svelte:71) als Root Cause identifiziert (überschreibt `.hidden` per Spezifität); Fix = Inline-`display` entfernen, Visibility via `hidden desktop:flex`. Belegt durch funktionierenden zweiten Fundort `trips/+page.svelte:324`.
