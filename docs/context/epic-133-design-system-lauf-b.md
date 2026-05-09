# Context: Epic #133 — Design-System Lauf B

## Request Summary
Lauf B ergänzt das in Lauf A etablierte Token- und Schrift-Fundament um die wiederverwendbaren UI-Bausteine: Topo-Hintergrundmuster (`<TopoBg>` + `.g-topo`-Klasse, Issue #143), fünf neue Atom-Komponenten (`Btn`, `Card`, `Pill`, `Eyebrow`, `Dot`, Issue #144) und die `ElevSparkline`-SVG-Komponente für Höhenprofile (Issue #146). Lauf B ist rein additiv — nur neue Dateien, keine Änderungen an bestehenden Routen oder Pages.

## Related Files

| File | Relevanz |
|------|---------|
| `frontend/src/app.css` | **Edit**: `.g-topo`-Utility-Klasse hinzufügen (Issue #143) — Tokens aus Lauf A bereits vorhanden |
| `frontend/src/lib/components/ui/button/button.svelte` | Referenz-Pattern für neue `<Btn>` (`tv()` + `cn()` + `data-slot` + `WithElementRef`) |
| `frontend/src/lib/components/ui/card/card.svelte` | Referenz-Pattern für neue `<Card>` (Slot-Pattern, hover-Effekt) |
| `frontend/src/lib/components/ui/badge/badge.svelte` | Referenz-Pattern für `<Pill>` (kompakte Label-Komponente) |
| `frontend/src/lib/utils.ts` | Re-Export `cn()`. `WithElementRef` wird neu via `bits-ui` importiert |
| `frontend/src/lib/utils/cn.ts` | `cn()`-Implementierung (clsx + tailwind-merge) |
| `frontend/src/lib/types.ts` | `Waypoint.elevation_m: number` — Datenquelle für ElevSparkline-Konsumenten (späteres Epic) |
| `internal/model/trip.go` | `Waypoint.ElevationM int` — Backend-Pendant |
| `frontend/e2e/design-system-lauf-a.spec.ts` | Test-Pattern (Playwright + `login()`-Helper) — Vorbild für Lauf-B-Tests |
| `frontend/e2e/helpers.ts` | `login()`-Helper für E2E-Setup |

## Neue Dateien (zu erstellen — Lauf B)

### Topo-Hintergrundmuster (Issue #143)
| File | Inhalt |
|------|--------|
| `frontend/src/lib/components/ui/topo/TopoBg.svelte` | Wrapper-Komponente, Prop `opacity={0.04}`, rendert `<div class="g-topo">` mit Snippet-Kindern |
| `frontend/src/lib/components/ui/topo/index.ts` | `export { default as TopoBg } from './TopoBg.svelte';` |

### Atom-Komponenten (Issue #144)
| File | Inhalt |
|------|--------|
| `frontend/src/lib/components/ui/btn/Btn.svelte` | `tv()`-Varianten `accent`/`ghost`/`outline`, sizes `sm`/`md`/`lg`, nutzt `--g-accent` |
| `frontend/src/lib/components/ui/btn/index.ts` | Re-Export |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Inline Label, `tv()`-Tone `default`/`success`/`warning`/`danger`/`info`/`accent` |
| `frontend/src/lib/components/ui/pill/index.ts` | Re-Export |
| `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte` | Kleine, gesperrte Über-Überschrift (uppercase, JetBrains Mono, `--g-ink-faint`) |
| `frontend/src/lib/components/ui/eyebrow/index.ts` | Re-Export |
| `frontend/src/lib/components/ui/dot/Dot.svelte` | Status-Punkt (6 Wetter-Tones + 4 Semantic-Tones), Sizes `xs`/`sm`/`md` |
| `frontend/src/lib/components/ui/dot/index.ts` | Re-Export |
| `frontend/src/lib/components/ui/g-card/GCard.svelte` | Token-aware Card (`--g-surface-1`, `--g-elev-1/2`), nicht zu verwechseln mit shadcn `<Card>` |
| `frontend/src/lib/components/ui/g-card/index.ts` | Re-Export |

### ElevSparkline (Issue #146)
| File | Inhalt |
|------|--------|
| `frontend/src/lib/components/ui/elev-sparkline/ElevSparkline.svelte` | Reines SVG, Props: `data: number[]`, `width=120`, `height=24`, `active=false` |
| `frontend/src/lib/components/ui/elev-sparkline/index.ts` | Re-Export |

### Zusätzlich
| File | Inhalt |
|------|--------|
| `frontend/src/routes/_design/+page.svelte` | **Showcase-Route** zur visuellen Inspektion aller Atoms (kein Production-Feature, nur Dev-Hilfe) |
| `frontend/e2e/design-system-lauf-b.spec.ts` | E2E-Tests: Topo, Atoms, ElevSparkline auf der Showcase-Route |

> **Begründung Showcase-Route:** Ohne Konsument können die Atoms in E2E nicht angesprochen werden. Eine versteckte Showcase-Route (`/_design`, nicht in Sidebar verlinkt) erlaubt sowohl visuelle Verifikation als auch deterministisches E2E-Testing — analog zu Storybook-Stories, aber ohne neue Toolchain.

## Existing Patterns

- **Komponenten-Muster**: shadcn-svelte Style — `tv()` für Varianten, `cn()` für class-Merging, `data-slot`-Attribut für CSS-Hooks, `WithElementRef<HTMLAttributes>` für ref-Forwarding. Komponenten sind in `<script lang="ts" module>` deklariert (für `tv`-Variants), Props in zweitem `<script lang="ts">`-Block.
- **Tailwind 4**: `@theme`-Block für Tailwind-eigene `--color-*`/`--radius-*`-Tokens; `@layer base { :root { ... } }` für Gregor-eigene `--g-*`-Tokens. Beide koexistieren.
- **Token-Verwendung in CSS**: `var(--g-accent)` — Tailwind 4 erlaubt direkten CSS-Custom-Property-Zugriff in Klassen via Arbitrary Values (`bg-[var(--g-accent)]`).
- **Icons**: `@lucide/svelte/icons/<name>` — Default-Import.
- **Svelte 5 Runes**: `$props()`, `$state()`, `$bindable()` — kein Svelte-4-Syntax.
- **Snippet-Pattern**: `children: Snippet` aus `svelte`, gerendert via `{@render children?.()}`.

## Dependencies

- **Upstream**: SvelteKit 2, Svelte 5 (Runes), Tailwind CSS 4, `tailwind-variants`, `bits-ui` (für `WithElementRef`-Type), `clsx`, `tailwind-merge`. **Keine neuen npm-Pakete.**
- **Downstream**: Spätere Epics (#134–#140) ersetzen schrittweise shadcn-Komponenten durch Lauf-B-Atoms, sobald `--g-*`-Look auf bestehende Seiten ausgerollt wird. ElevSparkline wird in Trip-Detail-Page (Epic #134/#135) konsumiert.

## Existing Specs

- `docs/specs/modules/epic_133_design_system_lauf_a.md` — **Voraussetzung**: definiert die `--g-*`-Tokens und Schriften, auf denen Lauf B aufsetzt
- `docs/specs/modules/design_optimierungen.md` — Ältere Anpassungen (F74/F76)
- `docs/specs/modules/nav_redesign_phase_a.md` — Nav-Refresh (bereits in Prod)

## Risks & Considerations

- **Naming-Kollision Card vs. GCard**: shadcn-`Card` (`$lib/components/ui/card`) und neue `GCard` (`$lib/components/ui/g-card`) müssen sauber getrennt importierbar sein. Lauf B ändert die shadcn-Card NICHT. Alternativ: neue Atoms in eigenen `g-`-Pfaden.
- **WithElementRef-Pfad**: bestehende shadcn-Komponenten importieren `WithElementRef` aus `$lib/utils.js`, dort ist es aber nicht re-exportiert — TypeScript-Toleranz oder bestehender latenter Bug. Neue Atoms importieren direkt aus `bits-ui` (siehe Lauf-A-Context-Empfehlung).
- **Topo-Performance**: Komplexe `radial-gradient`-Stacks können Repaint-Kosten haben. Pattern soll auf einem `position:absolute`-Element mit `pointer-events:none` rendern, damit es Hover/Click nicht behindert. Der `opacity`-Prop sollte als CSS-Variable durchgereicht werden, damit kein Re-Render bei Wertänderung nötig ist.
- **ElevSparkline `data=[]`**: Edge-Case leeres Array — Komponente muss leer rendern (kein NaN, kein Crash). Single-Point-Array (`[1500]`) — flache Linie mittig.
- **ElevSparkline Y-Skalierung**: min/max aus `data` ableiten; bei min===max: horizontale Linie auf halber Höhe. `padding`-Streifen oben/unten (z.B. 2px) damit Linie nicht den Rand berührt.
- **Showcase-Route nicht in Sidebar**: `/_design` darf nicht verlinkt sein, sonst landet sie im Production-Build sichtbar. SvelteKit-`prerender = false` setzen, kein Eintrag in Sidebar-`navItems`.
- **E2E-Tests benötigen Login**: Showcase-Route hinter Login lassen (gleicher Auth-Pfad wie Rest der App). Tests nutzen `login()`-Helper.
- **Tailwind-Class-Sicherheit**: Arbitrary Values mit `var(--g-*)` müssen bei Tailwind-Build erkannt werden — Variant-Strings in `tv()` werden als String-Literal von Tailwind 4 nicht gescannt, deshalb sicherer Weg: Klassen auf statische Tailwind-Utilities (`bg-[#c45a2a]` ist statisch) oder direkt `style="background:var(--g-accent)"` im Markup.

## Analyse-Ergebnisse (Phase 2)

### 1. Greenfield bestätigt
Drei parallele Explore-Agents bestätigen: Keine bestehenden Implementierungen für Topo (`.g-topo`, `<TopoBg>`), Atoms (`<Btn>`, `<Pill>`, `<Eyebrow>`, `<Dot>`, `<GCard>`) oder `<ElevSparkline>`. Keine Konsumenten referenzieren diese Komponenten heute. Lauf B kann komplett additiv ohne Refactor-Risiko gebaut werden.

### 2. Token-Konsumption strategisch entscheiden — `data-`-Attribute statt Arbitrary-Values
Tailwind 4 + `@tailwindcss/vite` scannt automatisch alle `.svelte`-Dateien; `tv()`-Klassen werden erkannt, solange sie als statische String-Literale im Source stehen. **Risikoarmes Pattern**: `data-variant` / `data-tone`-Attribute am Root-Element + globale CSS-Selektoren in `app.css` (`[data-slot="btn"][data-variant="accent"] { background: var(--g-accent); ... }`). Das ist analog zum bereits etablierten `data-slot`-Pattern von shadcn-svelte und scan-sicher.

**Verworfene Alternativen:**
- `bg-[var(--g-accent)]` in `tv()`-Variants → Tailwind-Arbitrary-Value muss als statischer String im Source stehen, in `tv()`-Branches schwerer zu garantieren
- Inline `style="..."`-Attribute → unleserlich, nicht hover/focus-fähig

### 3. Auth-Flow für `/_design`-Route geklärt
`hooks.server.ts` whitelisted `/login`, `/register`, `/logout`, `/forgot-password`, `/reset-password`. Alle anderen Routes — inklusive einer neuen `/_design` — sind automatisch durch Session-Cookie-Verifizierung geschützt. Kein zusätzlicher Auth-Code nötig, E2E-Tests nutzen den bestehenden `login()`-Helper.

### 4. SvelteKit-Routen-Sichtbarkeit
`adapter-node` nutzt keine statische Generierung — `prerender = false` ist Standard-Verhalten. `/_design` darf einfach existieren; sie wird **nicht** in der Sidebar (`navItems`) verlinkt, ist also für End-User unsichtbar, aber direkt per URL erreichbar (Dev-Convenience).

### 5. E2E-Test-Setup steht
Playwright + Vite Preview @ Port 4173, `webServer.command = bash e2e/start-preview.sh`, Auth-State in `playwright/.auth/admin.json` gecacht. Tests laden Login-State automatisch, kein Boilerplate nötig.

### 6. Implementierungs-Reihenfolge
1. **`app.css` erweitern**: `.g-topo`-Klasse + `data-variant`/`data-tone`-Selektoren für Atoms (CSS-Schicht zuerst, damit Komponenten direkt korrekt rendern)
2. **Showcase-Route `/_design`**: Test-Anker, anfangs leer, wächst inkrementell mit jedem fertigen Atom
3. **Atoms parallel**: `<Btn>`, `<GCard>`, `<Pill>`, `<Eyebrow>`, `<Dot>` — alle gleiche Struktur, daher trivial parallelisierbar
4. **`<TopoBg>`**: Wrapper um `.g-topo`-Klasse mit `opacity`-Prop via CSS Custom Property
5. **`<ElevSparkline>`**: Eigenständiges SVG, keine Token-Abhängigkeit außer Stroke-Color
6. **E2E-Tests** (`design-system-lauf-b.spec.ts`): pro Komponente 1-2 Tests gegen `/_design`

### 7. Scope-Bestätigung
- **15 neue Dateien**:
  - 5 Atoms × 2 (`.svelte` + `index.ts`) = 10
  - `<TopoBg>` × 2 = 2
  - `<ElevSparkline>` × 2 = 2
  - Showcase: `frontend/src/routes/_design/+page.svelte` = 1
- **2 geänderte Dateien**: `frontend/src/app.css` (+ `.g-topo` + `data-`-Selektoren), `frontend/e2e/design-system-lauf-b.spec.ts` (neu)
- **Geschätzte LoC**: ~450 (etwas über initialer 378er-Schätzung wegen Showcase-Route + globalen CSS-Regeln statt Tailwind-Klassen)

### 8. Empfohlene Naming-Entscheidung: `<GCard>` statt `<Card>`
shadcn-`<Card>` und Token-aware-Card sollen sauber unterscheidbar sein. **Empfehlung**: Neue Komponente heißt `<GCard>` im Pfad `g-card/`. Vorteil: Imports bleiben unmissverständlich (`import { GCard } from '$lib/components/ui/g-card'`), keine versehentliche Verwechslung, kein Refactor-Druck auf bestehende shadcn-Konsumenten.
