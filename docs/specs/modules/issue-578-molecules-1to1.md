---
entity_id: issue-578-molecules-1to1
type: module
created: 2026-06-05
updated: 2026-06-05
status: draft
version: "1.0"
tags: [design-fidelity, foundation, epic-575, sidebar, molecules, organisms]
---

# Issue #578 — Molecules + Organisms + Sidebar 1:1

## Approval

- [ ] Approved

## Purpose

Foundation-Welle 1 (nach #576 Tokens und #577 Atoms): Sidebar, alle
Molecules und alle Organisms im SvelteKit-Frontend zeichenweise nach den
JSX-Vorlagen angleichen, damit Welle-2-Screen-Issues (#579 ff.) das
Diff-Gate `diff_pct < 10 %` reißen können. Pilot #582 (Compare-Liste)
zeigte 51,5 % Drift — Hauptursache vermutlich die Tailwind+Lucide-Sidebar.

## Source

- **Vorlagen (bindend):**
  - `claude-code-handoff/current/jsx/molecules.jsx` (1574 Z, 119
    Inline-Styles, 32 Funktionen)
  - `claude-code-handoff/current/jsx/organisms.jsx` (1341 Z, 39
    Inline-Styles, ~10 Funktionen)
  - `claude-code-handoff/current/jsx/sidebar.jsx` (Wrapper auf
    `brand-kit::BrandSidebar`)
  - `claude-code-handoff/current/jsx/brand-kit.jsx` Zeilen 229–351
    (BrandSidebar, BrandSidebarItem, BrandSidebarIcon)
- **Affected Files (Frontend / SvelteKit):**
  - `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` (Komplett-Rewrite)
  - `frontend/src/lib/components/molecules/*.svelte` (Werte-Drift fixen)
  - `frontend/src/lib/components/organisms/*.svelte` (Werte-Drift fixen)
- **Tracer-Screen (Diff-Gate-Nachweis):**
  - SOLL: `claude-code-handoff/current/soll/D-home-trip.png`
  - IST: Playwright-Screenshot `https://staging.gregor20.henemm.com/`
    nach Deploy.

## Estimated Scope

- **LoC:** ~600–900 produktiv (Sidebar ~150, Molecules-Korrekturen 30 × 5–15 LoC,
  Organisms-Korrekturen 10 × 5–15 LoC). LoC-Override auf `1500` setzen.
- **Files:** 1 Sidebar + bis zu 30 Molecules + 10 Organisms = ~40 Dateien.
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Issue #576 (Tokens) | upstream | `--g-paper-deep`, `--g-rule`, `--g-accent-deep` etc. müssen existieren |
| Issue #577 (Atoms) | upstream | Btn/Pill/g-card/Eyebrow müssen JSX-konform sein |
| Epic #575 (Drift-Korrektur) | umbrella | Welle 1 = Sidebar+Molecules+Organisms |
| `pre_issue_close_design_gate.py` | gate | Blockt Close ohne `design-diff-*.json` mit `passed:true` |
| `.claude/tools/jsx_style_inventory.py` | tool | Erzeugt die Inline-Style-Checkliste |

## Implementation Details

### A) Sidebar — Komplett-Rewrite nach `brand-kit.jsx`

`frontend/src/lib/components/ui/sidebar/Sidebar.svelte` wird so umgebaut:

- **Wurzel-`<aside>`** mit Inline-Style:
  - `width: 220px; flex: 0 0 220px;`
  - `background: var(--g-paper-deep);`
  - `border-right: 1px solid var(--g-rule);`
  - `display: flex; flex-direction: column;`
  - `padding: 24px 0 0; height: 100%;`
  - `font-family: var(--g-font-sans);`
- **Header-Block** `padding: 0 18px 24px` mit BrandWordmark (size `md`).
- **Nav-Liste** `display:flex; flex-direction:column; gap:2px; padding:0 12px`.
- **Items** (Reihenfolge **fest**, vom JSX vorgegeben):
  - `home` → "Startseite", icon `home`
  - `trips` → "Meine Trips", icon `trip`
  - `compare` → "Orts-Vergleich", icon `compare`
  - `archive` → "Archiv", icon `archive`
- **Item-Styling** (jeder `<a>`):
  - `display:flex; align-items:center; gap:10px;`
  - `padding: 8px 12px; border-radius: var(--g-r-3);`
  - Active-Background: `rgba(196,90,42,0.10)`, sonst `transparent`.
  - Active-Color: `var(--g-accent-deep)`, sonst `var(--g-ink-2)`.
  - `font-size:13px; font-weight: <600 active | 500 inactive>;`
  - `text-decoration:none; cursor:pointer; transition: background 120ms;`
- **Item-Icon** (Inline-SVG, 16×16, fest pro `kind`):
  - JSX-Pfade aus `brand-kit.jsx` Zeilen 340–349 zeichenweise übernehmen.
  - Stroke: Active `var(--g-accent)`, sonst `var(--g-ink-3)`.
- **Counts-Pille** (optional, falls `counts[id] != null`):
  - `font-family: var(--g-font-mono); font-size: 10px;`
  - Active: `color: var(--g-accent-deep); background: rgba(196,90,42,0.12);`
  - Inactive: `color: var(--g-ink-4); background: rgba(26,26,24,0.05);`
  - `padding: 1px 6px; border-radius: var(--g-r-pill); font-weight: 600;`
- **Spacer** `flex:1`.
- **Footer-Block** `padding: 16px 18px; border-top: 1px solid var(--g-rule-soft);`
  mit User-Badge (Name + Dropdown bleibt; bestehende Logik wiederverwenden).

**Behalten** (nicht aus JSX, aber operativ unverzichtbar):
- Mobile-Drawer-Slide-Logik (`mobileMenuOpen`-Prop, Backdrop, Transitions).
  JSX zeigt nur Desktop-Layout — mobile darf weiterhin via CSS-Klasse
  ein-/ausblenden. Die **Desktop-Inline-Styles** sind unangetastet.
- `data-testid="desktop-sidebar"` (E2E-Selektor).
- Lucide-Icons im Mobile-Drawer-Footer (Konto, System-Status, Dark Mode,
  Logout) bleiben, da JSX dafür keine Vorlage hat. Nur die Desktop-Nav
  bekommt die Inline-SVGs aus `brand-kit.jsx`.

### B) Molecules (32 Komponenten) — JSX-Wert-Sync

Pro Datei in `frontend/src/lib/components/molecules/`:

1. Vergleich mit JSX-Block in `molecules.jsx`.
2. Inline-Styles 1:1 (Pixel, Token-Namen, hex, rgba).
3. Sichtbarer Text wortgleich (z. B. `"aktiv"`, `"pausiert"`, `"draft"`).
4. Token-Konflikte (JSX `--g-bad/--g-ink-4` vs. Svelte `--g-danger/--g-ink-3`):
   **JSX gewinnt** ([[feedback_jsx_always_truth]]). Kontrast-Folge
   (`--g-ink-4` ist Placeholder/Disabled-Token, nicht für Hint-Text)
   wird als Design-Request `docs/design-requests/issue-578-hint-contrast.md`
   nach Close geöffnet — blockt #578 nicht.
5. Keine erfundenen Loading-/Empty-/Fallback-States.

### C) Organisms (10 Komponenten) — JSX-Wert-Sync

Wie Molecules. Sonderfall: MetricsEditor + MetricBucket + ChannelPreviewStrip
liegen historisch teilweise unter `components/edit/`. Vor Sync prüfen,
ob sie noch genutzt werden — falls ja, dort patchen, **kein Duplikat**
in `organisms/` anlegen.

### D) Tracer-Screen + Diff-Gate

Nach Deploy auf Staging:

1. Playwright-Screenshot von `https://staging.gregor20.henemm.com/`
   (Home-Trip-Screen, 1024 viewport, Pixel-Threshold 30 wie #583).
2. Vergleich gegen `claude-code-handoff/current/soll/D-home-trip.png`.
3. `docs/artifacts/issue-578-molecules-1to1/design-diff-D-home-trip.json`
   muss `"passed": true` (diff_pct < 10 %) enthalten.

## Expected Behavior

- **Input:** Keine Logik-Änderung. Nur visueller Output.
- **Output:** Sidebar+Molecules+Organisms rendern Pixel-näher (Tracer
  D-home-trip < 10 % Diff statt 51,5 %).
- **Side effects:** Bestehende Funktionen (Navigation, Mobile-Drawer,
  Dark-Mode-Toggle, Logout) bleiben unverändert.

## Acceptance Criteria

- **AC-1:** Given ich besuche `https://staging.gregor20.henemm.com/`
  als angemeldeter User / When die Seite gerendert ist / Then die
  Sidebar zeigt vier Items in der Reihenfolge „Startseite", „Meine
  Trips", „Orts-Vergleich", „Archiv" mit Wortlaut wie hier.
  - Test: Playwright gegen Staging, eingeloggt, prüft `nav` Inhalte
    und Reihenfolge.

- **AC-2:** Given ich rendere die Sidebar / When ich die berechnete
  Hintergrundfarbe und Breite lese / Then `background-color` entspricht
  dem CSS-Var-Wert von `--g-paper-deep` und die Breite ist 220 px.
  - Test: Playwright `getComputedStyle(asideEl).width === '220px'`,
    Background gegen CSS-Var-Resolved gemessen.

- **AC-3:** Given ein aktives Sidebar-Item (z. B. „Startseite") / When
  ich seine Hintergrundfarbe lese / Then ist sie `rgba(196, 90, 42, 0.1)`
  (Active-Tint aus JSX).
  - Test: Playwright `getComputedStyle(activeLink).backgroundColor`.

- **AC-4:** Given ein inaktives Sidebar-Item / When ich seine Textfarbe
  lese / Then ist sie der CSS-Var-Wert von `--g-ink-2`.
  - Test: Playwright `getComputedStyle(inactiveLink).color === cssVar('--g-ink-2')`.

- **AC-5:** Given die Sidebar / When ich sie inspeziere / Then jedes
  Item enthält ein eigenes `<svg width="16" height="16">` (kein
  Lucide-Komponenten-Tag, kein `class="lucide-*"`).
  - Test: Playwright `aside svg[width="16"]` Count = 4 (oder ≥ 4
    inkl. Counts).

- **AC-6:** Given `Field.svelte` rendert mit `error="Fehler"` / When
  ich die Error-Text-Farbe lese / Then ist sie `var(--g-bad)` aus JSX
  (zeichenweise Quell-Treue).
  - Test: Playwright + Storybook-Stub oder direkter Mount in einer
    Route, getComputedStyle.

- **AC-7:** Given ich mache einen Pixel-Diff von
  `https://staging.gregor20.henemm.com/` (Home, viewport 1024) gegen
  `claude-code-handoff/current/soll/D-home-trip.png` / When der Diff
  berechnet ist / Then `diff_pct < 10` und das Artefakt
  `docs/artifacts/issue-578-molecules-1to1/design-diff-D-home-trip.json`
  enthält `"passed": true`.
  - Test: `python3 .claude/tools/design_diff.py` (Pixel-Threshold 30).

- **AC-8:** Given alle Sidebar-Items / When ich darauf klicke / Then
  die Navigation funktioniert wie zuvor (`/`, `/trips`, `/compare`,
  `/archiv`) und der Active-State wechselt korrekt.
  - Test: Playwright klickt jedes Item nacheinander, prüft URL und
    `aria-current`/Active-Klasse-Äquivalent.

- **AC-9:** Given der Mobile-Drawer (viewport < desktop) / When ich
  das Hamburger-Icon antippe / Then der Drawer öffnet, der Backdrop ist
  klickbar und schließt den Drawer wieder.
  - Test: Playwright @ 375 viewport, klick auf Backdrop, prüft
    `mobileMenuOpen`-Klassenwechsel.

- **AC-10:** Given `frontend/build/client/_app/immutable/nodes/*.js`
  nach Deploy / When ich nach dem Tailwind-String `bg-sidebar` oder
  `bg-sidebar-accent` im Desktop-Sidebar-Markup grep / Then ist er
  nicht mehr im Desktop-Aside enthalten (Mobile-Drawer-Footer darf
  Tailwind behalten).
  - Test: Quelltext-Grep auf `Sidebar.svelte` — Desktop-`<aside>`-Block
    enthält keine `class="… bg-sidebar …"`-Tailwind-Klasse.

## Known Limitations

- LoC-Limit 250 wird klar gerissen — Override auf `1500` setzen,
  Begründung „40 Komponenten zeichenweise JSX-Sync + Sidebar-Rewrite".
- Tracer-Screen `D-home-trip` setzt voraus, dass die Home-Seite einen
  aktiven Trip anzeigt. Falls Testdaten leer sind: SOLL ist statisch,
  IST wird trotzdem gerendert und gediffed; bei < 10 % PASS, bei
  AC-1-Status „SKIP" wie in #578-Voriteration nicht akzeptabel — das
  Issue ist explizit wieder geöffnet wegen der Diff.
- Mobile-Drawer-Footer (Lucide) bleibt — JSX hat keine Vorlage. Das
  ist okay; Diff misst Desktop-Viewport.

## Changelog

- 2026-06-05: Initial spec.
