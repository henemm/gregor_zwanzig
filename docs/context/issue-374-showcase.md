# Context: issue-374-showcase

## Request Summary
#374 (Epic #368): Showcase-Route `frontend/src/routes/_design-system/+page.svelte` — rendert ALLE Atoms + Molecules + Mobile-Primitive + Brand in allen Varianten. Regressions-Referenz für künftige UI-PRs + visuelle Gesamt-Abnahme des Atomic-Pakets (#371/#372/#373). Plus: Frontend-Doku-Abschnitt „Atomic-Design-Disziplin".

## Stand
- `routes/_design-system/` existiert NICHT (neu). `routes/_design/` existiert (ältere/andere Seite, hinter Login 302) — bleibt unberührt.
- Vorlage: `screen-design-system.jsx` (37 KB). Sektionen darin: 01 Brand, 02 Typografie, 03 Farben, 04 Bausteine, 05 Molecules (+Mobile), 06 Organisms, 07 Templates.

## Scope-Abgrenzung (WICHTIG)
- #374-Akzeptanz nennt **6 Sektionen: Brand · Typografie · Farben · Bausteine · Molecules · Voice**.
- **Organisms + Templates NICHT** in #374 (Epic #368: „Organisms erst nach #364"). Aus der Vorlage nur Brand/Typo/Farben/Atoms/Molecules + Mobile-Demo + Voice übernehmen.

## Was die Route importiert (echter Integrationstest!)
- `$lib/brand/` (BrandWordmark sm/md/lg/dark/icon-Varianten, BrandIcon, BrandIconSquare) — #370.
- `$lib/components/atoms/` (Pill alle Tones inkl. ghost, Btn alle Varianten inkl. quiet, Input sm/md/lg, Switch 3×5, WIcon, Dot, SectionH, Eyebrow, …) — #371.
- `$lib/components/molecules/` (alle 10, Desktop + dense) — #372.
- `$lib/components/mobile/` (MBtn/MInput/MSwitch/MTab/Sheet/Toast/Drawer/MobileShell — in PhoneFrame-Demo) — #373. **Verifiziert live den MobileShell-Hamburger-Fix (F001).**
- Typografie (Type-Scale xs–5xl), Farben (Surfaces/Ink/Accent/Semantic/Wetter), Voice (Tun/Lassen).

→ Wenn eine Komponente kaputt/falsch importiert ist, bricht der Build der Route. Das ist die echte Paket-Integration.

## Frontend-Doku
Abschnitt „Atomic-Design-Disziplin" in `frontend/README.md` o. `frontend/CLAUDE.md`: Lese-Regel vor UI-Arbeit + Naming-Konvention (Brand*/M*/Atoms-Molecules ohne Prefix) + Konflikt-Regel (brand-kit gewinnt).

## Akzeptanz (Issue)
- Route lädt ohne Console-Errors, zeigt jede Komponente in jeder Variante.
- Screenshot-Vergleich gegen `screen-design-system.jsx` (Spec-Source).
- Frontend-Doku-Abschnitt vorhanden.

## Risiken
- Route hinter Login (302 wie /_design) → visuelle Abnahme via eingeloggtem Screenshot (Validator-Account).
- contrast-audit/svelte-check müssen grün bleiben (die Route nutzt Komponenten, fügt evtl. eigene Demo-CSS hinzu — Token-Disziplin).
- PhoneFrame/MobileStatusBar (Demo-Rahmen, NICHT in mobile/) hier in der Route definieren (sie gehören in den Showcase, nicht die Bibliothek — siehe #373-Scope).
- Reines Frontend. **Letzter Baustein → danach gemeinsamer Prod-Deploy #371+#373+#372+#374 + Kontrast-Fixes.**
