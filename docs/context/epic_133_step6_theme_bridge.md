---
workflow: epic_133_step6_theme_bridge
created: 2026-05-13
issue: 218
parent_epic: 133
type: context
---

# Context: Theme-Bridge — shadcn-Tailwind-Tokens an Gregor-Design-Tokens koppeln

## Request Summary

Issue #218: Im `@theme {}`-Block in `frontend/src/app.css` (Z. 3–22) sollen die shadcn-Farbtoken (`--color-background`, `--color-primary`, `--color-accent`, `--color-border`, etc.) per `var(--g-*)` an die bereits definierten Gregor-Design-Tokens (`--g-paper`, `--g-ink`, `--g-accent`, `--g-surface-1/2`, `--g-ink-muted`, `--g-ink-faint`, `--g-danger`) gekoppelt werden. Dadurch erben die ~66 Frontend-Dateien, die Tailwind-Utilities wie `bg-primary`, `bg-background`, `border-border`, `text-muted-foreground` nutzen, automatisch die Marken-Optik (Burnt-Orange-Akzent, warmes Paper-Off-White, alpines Ink-Schwarz) — **ohne Komponenten-Edit**.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/app.css` Z. 3–26 | **EDIT-Ziel:** `@theme {}`-Block — 19 Farb-Tokens werden an `var(--g-*)` gekoppelt; Radii bleiben unverändert |
| `frontend/src/app.css` Z. 28–105 | `:root`-Block mit allen `--g-*`-Tokens — Lieferanten der gekoppelten Werte (alle erforderlichen Tokens existieren bereits) |
| `frontend/src/routes/+layout.svelte` Z. 10–44 | **Wichtig:** Dark-Mode-Toggle setzt `--color-*` inline auf `document.documentElement` — überschreibt unseren `@theme`-Block, betrifft uns also nur im Light-Mode (gewollt) |
| 29 Svelte-Files mit `bg-(primary\|background\|card\|muted\|accent\|destructive\|sidebar)` | Profitieren ohne Edit von der Bridge |
| 37 Svelte-Files mit `text-foreground / text-muted / border-border / border-input` | Dito |
| `docs/reference/design_system.md` | Spec für Token-Werte und Naming (drift zu Code dokumentiert) |
| `docs/specs/modules/epic_133_tokens_and_topo.md` | Vorhergehender Epic-#133-Schritt (Tokens + Topo) — etabliert Spec-Schema |

## Pre/Post-Screenshot-Routen

| Pfad | Komponente | Priorität |
|------|------------|-----------|
| `/` | Cockpit (`+page.svelte`) | hoch (Landing) |
| `/trips` | Trip-Liste | hoch |
| `/trips/[id]` | Trip-Detail-Übersicht | hoch |
| `/trips/[id]/edit` | Trip-Editor | mittel |
| `/trips/new` | Wizard Step 1–4 (`TripWizard.svelte`) | hoch |
| `/subscriptions` | Subscription-Liste | mittel |
| `/locations` | Locations | mittel |
| `/compare` | Compare-View | mittel |
| `/weather` | Weather-Test-View | niedrig |
| `/gpx-upload` | GPX-Upload | niedrig |
| `/account`, `/settings` | Account/Settings | niedrig |
| `/login` | Login (Public-Page-Layout ohne Sidebar) | mittel |
| `/_design` | Design-Showcase | hoch (visuelle Probe-Bühne) |

## Existing Patterns

- **`--g-*`-Token-Namespace** etabliert in `epic_133_tokens_and_topo` (Workflow vom 2026-05-13, gerade gemerged) — Tokens vollständig in `app.css` `:root`.
- **shadcn-Komponenten** (`button.svelte`, `input.svelte`, `badge.svelte`) nutzen `dark:`-Tailwind-Klassen; im Dark-Mode überschreibt `+layout.svelte` die `--color-*` direkt — der `@theme`-Block ist nur im Light-Mode wirksam.
- **Vorbild Btn-Komponente** (Issue #214, Phase A von #212): nutzt `[data-slot="btn"]` mit direkten `--g-*`-Tokens — kein shadcn-Bridge erforderlich, weil sie das eigene Design-System darstellt. Tailwind-basierte shadcn-Komponenten (`button.svelte`, `card.svelte`, etc.) leben parallel und werden erst über die Bridge marken-konform.

## Dependencies

- **Upstream:** `--g-*`-Tokens in `app.css` `:root` — alle benötigten Token-Namen (`--g-paper`, `--g-ink`, `--g-surface-1/2`, `--g-ink-muted`, `--g-ink-faint`, `--g-accent`, `--g-danger`) sind vorhanden.
- **Downstream:** Tailwind generiert aus dem `@theme {}`-Block die Utility-Klassen `bg-primary`, `text-primary-foreground`, `border-border`, `ring-ring` etc. Alle Komponenten, die diese Klassen nutzen, übernehmen die neue Optik automatisch.
- **Sidebar:** `--color-sidebar*` koppelt an `--g-surface-1/2` — `Sidebar.svelte` reagiert sofort.
- **Dark-Mode:** `+layout.svelte` setzt 18 von 19 `--color-*` inline beim Toggle. Token `--color-destructive` wird im Dark-Mode NICHT überschrieben — bisher hat das funktioniert, weil der `@theme {}`-Wert sichtbar blieb. Nach der Bridge zeigt es im Dark-Mode `var(--g-danger)` (Light-Mode-Rot) — unkritisch.

## Existing Specs

- `docs/specs/modules/epic_133_tokens_and_topo.md` — vorhergehender Epic-Schritt, etabliert Token-Naming und Spec-Format
- `docs/reference/design_system.md` — Soll-Werte und Naming-Spec (Drift zu Code beachten: Spec `--g-good/warn/bad/paper`, Code `--g-success/warning/danger/paper`)
- `docs/reference/design_system_tokens.css` — Begleit-CSS, ist nicht direkt geladen

## Risks & Considerations

1. **Risiko: hoch (laut Issue).** Ein 20-Zeilen-Edit ändert die visuelle Erscheinung der gesamten App in jedem Light-Mode-Kontext. Mögliche Fehlstellen:
   - **Kontrast-Drift:** `--color-primary` wechselt von Quasi-Schwarz `oklch(0.205 0 0)` auf `var(--g-ink) = #1a1a18` (kaum Unterschied, OK). Aber `--color-background` wechselt von Pure-White `oklch(1 0 0)` auf `var(--g-paper) = #f6f4ee` (sichtbar wärmer).
   - **Accent-Sprung:** `--color-accent` wechselt von hellem Grau `oklch(0.96 0 0)` auf **Burnt-Orange `#c45a2a`** — das könnte in Hover/Selected-States von Buttons/Badges/Tabs eine markante optische Veränderung verursachen (vermutlich gewollt, aber prüfen).
   - **Destructive bleibt:** `--color-destructive` koppelt von `oklch(0.577 0.245 27.325)` (warmes Rot) an `var(--g-danger) = #b33a2a` — sehr ähnlich, geringes Risiko.
   - **Muted-Foreground:** `oklch(0.45 0 0)` (mittelgrau) → `var(--g-ink-muted) = #5c5a52` (warmes Mittelgrau) — minimal sichtbar.
2. **Dark-Mode:** Im Toggle bleibt das visuelle Verhalten weitgehend gleich (Inline-Styles überschreiben), aber `--color-destructive` und `--color-ring` werden im Dark-Mode nicht überschrieben — daher übernehmen sie die neuen Light-Mode-Bridge-Werte. Unkritisch, da Burnt-Orange-Ring im Dark-Mode sogar besser sichtbar wäre.
3. **shadcn-`button.svelte`:** Nutzt `dark:`-Tailwind-Klassen für Hover/Border. Im Light-Mode ändert sich `bg-muted`, `border-border` — Hover-States müssen visuell geprüft werden.
4. **A11y:** Manueller Sichtcheck nötig: Ist `#1a1a18` auf `#f6f4ee` ausreichend kontrastreich für Body-Text? (WCAG: Kontrast ~14, sehr gut.)
5. **E2E-Tests:** Bestehende Playwright-Tests dürfen nicht brechen — sie sind nicht pixelbasiert. Erwartet OK.
6. **AC-Verifikation:** `getComputedStyle(:root).getPropertyValue('--color-primary')` muss nach Bridge den **berechneten** Wert (`#1a1a18`) liefern, nicht den literal-string `var(--g-ink)`. Browser löst CSS-Variablen in `getComputedStyle` auf — funktioniert.

## Open Questions

- **Dark-Mode-Bridge** (nicht in diesem Sprint, Issue erwähnt es explizit): Soll später der inline-Override in `+layout.svelte` durch eine zweite `--g-*-dark`-Variante ersetzt werden? → später, separate Klärung.
- **Sidebar-Ring/Border:** `--color-sidebar` nutzt Surface-1 — passt der Kontrast zur Hauptfläche (Paper) noch? Visueller Sichtcheck.

## Next Phase

Phase 2 — Analyse: Genaues Token-Mapping abstimmen, AC-Liste finalisieren, Test-Strategie schärfen (1 Playwright-Test pro AC, plus Pre/Post-Screenshot-Pipeline).
