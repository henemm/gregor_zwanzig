---
entity_id: issue_374_showcase
type: module
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
tags: [frontend, atomic-design, showcase, route, epic-368, issue-374]
---

<!-- Issue #374 — Showcase-Route /_design-system (Regressions-Referenz) -->

# Issue #374 — Showcase-Route `/_design-system`

## Approval

- [ ] Approved

## Zweck

Showcase-Route `frontend/src/routes/_design-system/+page.svelte` (Epic #368), die ALLE Brand-, Atom-, Molecule- und Mobile-Bausteine in allen Varianten rendert. Zweck: (a) **visuelle Gesamt-Abnahme** des Atomic-Pakets (#371/#372/#373) — die Route importiert die echten Komponenten, also ist ihr erfolgreicher Build der Integrationsbeweis; (b) **Regressions-Referenz** für künftige UI-PRs (ein Pattern muss hier sichtbar sein, bevor es in eine echte Route geht). Letzter Baustein vor dem gebündelten Prod-Deploy.

## Quelle / Source

**Kanonische Vorlage:** `docs/design-requests/issue_15_atomic_design/spec/screen-design-system.jsx` + `body-15-atomic-design-library.md` §Showcase-Route.

**Neue Dateien:**
- `frontend/src/routes/_design-system/+page.svelte` (Showcase-Seite)
- evtl. lokale Demo-Helfer in derselben Datei/Ordner (Section-Wrapper, Swatch, PhoneFrame/MobileStatusBar-Demo-Rahmen — diese gehören in den Showcase, NICHT in `mobile/`).

**Geänderte Dateien:**
- `frontend/README.md` (oder `frontend/CLAUDE.md`) — Abschnitt „Atomic-Design-Disziplin" ergänzen.

**Neue Test-Datei:** `frontend/src/routes/_design-system/showcase.test.ts` (Source-Inspection: importiert alle vier Schichten + rendert Pflicht-Varianten; node:test, keine Mocks).

**NICHT in #374 (Epic #368, Out of Scope):** Organisms- und Templates-Sektionen aus der Vorlage (Organisms erst nach #364). `routes/_design/` bleibt unberührt.

> **Schicht-Hinweis:** Reine Frontend-Änderung (SvelteKit `frontend/src/routes/`). Keine Go/Python-Schicht.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/brand/` (#370) | Brand-Schicht | BrandWordmark/BrandIcon/BrandIconSquare-Varianten |
| `$lib/components/atoms/` (#371) | Atom-Schicht | Pill/Btn/Input/Switch/WIcon/Dot/SectionH/Eyebrow |
| `$lib/components/molecules/` (#372) | Molecule-Schicht | alle 10 Molecules (Desktop + dense) |
| `$lib/components/mobile/` (#373) | Mobile-Schicht | MBtn/MInput/MSwitch/MTab/Sheet/Toast/Drawer/MobileShell |
| `screen-design-system.jsx` | Spec-Vorlage | Sektions-Aufbau + gezeigte Varianten |
| `frontend/src/app.css` (#369) | CSS-Tokens | Farben-Sektion + Token-basiertes Demo-CSS (C1) |

## Implementation Details

### Route `_design-system/+page.svelte` — 6 Sektionen (aus Vorlage, Organisms/Templates weglassen)
1. **Brand** — BrandWordmark sm/md/lg, dark, icon left/only/none; BrandIcon; BrandIconSquare 64/48/32/16.
2. **Typografie** — Type-Scale xs/sm/md/lg/xl/2xl/3xl/4xl/5xl.
3. **Farben** — Surface-Stack, Ink-Skala, Accent, Semantic, Wetter-Farben (Swatches mit Token-Namen).
4. **Bausteine (Atoms)** — Pills (alle Tones inkl. ghost), Buttons (alle Varianten inkl. quiet, 4 Größen), Inputs (sm/md/lg), Switches (3 Größen × 5 Tones), WIcons (alle kinds), Dot, Eyebrow, SectionH, AvatarStack.
5. **Molecules** — Field, DetailRow, StagePill (alle 4 States), ChannelRow (Desktop + dense), ChannelChip (default + compact), Stat (stack + inline + 3 Größen), AlertRow (3 Varianten), BriefingTimelineRow (default + dense), BriefingScheduleRow, ThresholdRow (default + divider=solid).
6. **Voice** — Tun-/Lassen-Beispiele.
+ Mobile-Demo: Mobile-Primitive in einem lokalen PhoneFrame (MBtn/MSwitch/MTab/Sheet/Toast/MobileShell) — verifiziert MobileShell-Hamburger live.

### Demo-Helfer
Section-Wrapper, Swatch, PhoneFrame/MobileStatusBar lokal in der Route (Token-basiert). Diese sind Showcase-spezifisch, NICHT Bibliothek.

### Frontend-Doku
`frontend/README.md` Abschnitt „Atomic-Design-Disziplin": Lese-Regel (Showcase vor UI-Arbeit ansehen), Naming (Brand*/M*/Atoms-Molecules-ohne-Prefix), Konflikt-Regel (brand-kit gewinnt, dann atoms).

## Expected Behavior

- **Input:** keiner — statische Showcase-Seite.
- **Output:** `/_design-system` rendert ohne Console-Errors; jede Komponente in jeder Pflicht-Variante sichtbar.
- **Side effects:** keine; keine bestehende Route betroffen (`/_design` bleibt).

## Acceptance Criteria

- **AC-1:** Given die Showcase-Route / When `frontend/src/routes/_design-system/+page.svelte` existiert / Then importiert sie aus allen vier Schichten (`$lib/brand`, `$lib/components/atoms`, `$lib/components/molecules`, `$lib/components/mobile`) und der Frontend-Build (`svelte-check`/`vite build`) kompiliert die Route ohne Fehler (Integrationsbeweis des Pakets).
  - Test: (populated after /tdd-red)

- **AC-2:** Given die Route / When man die gerenderten Sektionen prüft / Then enthält sie die 6 Sektionen Brand, Typografie, Farben, Bausteine, Molecules, Voice (KEINE Organisms/Templates), mit den in Implementation Details gelisteten Varianten.
  - Test: (populated after /tdd-red)

- **AC-3:** Given die Mobile-Demo / When MobileShell im Showcase gerendert wird / Then funktioniert der Hamburger-Toggle (F001-Fix live) und MBtn/MSwitch/Sheet/Toast erscheinen in ihren Varianten.
  - Test: (populated after /tdd-red)

- **AC-4:** Given Token-/Kontrast-Disziplin / When man die Route + Demo-Helfer prüft / Then nutzen sie `var(--g-*)` (kein verbotener Inline-Hex), und `contrast-audit.test.ts` (#377) bleibt grün.
  - Test: (populated after /tdd-red)

- **AC-5:** Given die Frontend-Doku / When man `frontend/README.md` (o. CLAUDE.md) liest / Then existiert der Abschnitt „Atomic-Design-Disziplin" mit Lese-Regel, Naming-Konvention und Konflikt-Regel.
  - Test: (populated after /tdd-red)

- **AC-6:** Given die visuelle Abnahme / When `/_design-system` auf Staging (eingeloggt) gerendert wird / Then zeigt der Screenshot alle Bausteine konsistent zur Sandbox `screen-design-system.jsx`, ohne Layout-Schäden oder fehlende Komponenten.
  - Test: (populated after /tdd-red) — Staging-Screenshot in E2E-Phase

## Known Limitations

- **F002 (Adversary, LOW):** `Drawer` (Mobile-Schicht) ist im Showcase nicht eigens demonstriert (AC-3 verlangt nur MBtn/MSwitch/Sheet/Toast). Drawer ist via MobileShell-`drawer`-Slot integrierbar; eigene Demo als kosmetische Folge-Ergänzung.
- **F001 (Adversary, LOW):** AC-4-Test ist ein Presence-Check (`var(--g-` vorhanden), kein Absence-Gate für nackten Hex. Die Route ist verifiziert hex-frei (manuell + contrast-audit); Test-Härtung optional.
- **F003 (Adversary, MEDIUM, behoben):** `docs/reference/frontend_components.md` fehlte der `molecules`-Eintrag (Folge von #372) → `test_issue_316` rot. Behoben: Abschnitt „Atomic-Design-Bibliothek (Epic #368)" ergänzt (brand/atoms/molecules/mobile + Showcase).
- Organisms/Templates-Sektionen folgen nach #364 (eigenes Issue).
- `/_design` (ältere Seite) bleibt vorerst; Konsolidierung/Entfernung optional als Folge.
- Screen-Migration (echte Routes auf die Bibliothek umstellen) ist #368 Phase 2.

## Changelog

- 2026-05-26: Initial spec created (Issue #374, Showcase-Route)
