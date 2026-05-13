# Context: Issue #220 — Topo-Hintergrundmuster auf Hero-Bereichen sichtbar machen

## Request Summary
Das neu eingeführte Topo-Hintergrundmuster (5 organische Ellipsen, Default-Opacity 0.5 aus Issue #209) wird aktuell nur in `ActiveTripCard` und im Design-Showcase angezeigt. Es soll an drei weiteren Hero-Bereichen als Marken-Element sichtbar werden: Cockpit-Top, Trip-Detail-Hero, Wizard-Header.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/ui/topo/TopoBg.svelte` | Wrapper-Atom, das die Aufgabe lösen soll — `opacity`-Prop, Snippet-Child, `relative z-Layer` |
| `frontend/src/lib/components/ui/topo/index.ts` | Barrel-Export `TopoBg` |
| `frontend/src/app.css` (`.g-topo` Z. 134–145) | CSS-Klasse mit 5 radialen Gradients + `--g-topo-opacity` Variable |
| `frontend/src/routes/+page.svelte` | **Ziel 1:** Cockpit-Topbar (`[data-testid="cockpit-topbar"]` Z. 109–150) — H1 „Guten Tag", Datum, CTAs. Soll als breites Hero-Layer mit Topo wrappen |
| `frontend/src/routes/_cockpit/ActiveTripCard.svelte` | Bestand: nutzt `<TopoBg>` bereits innerhalb der GCard → bleibt unverändert. Klarer Trenner zwischen „Cockpit-Topbar mit Topo" und „ActiveTripCard mit eigenem Topo" |
| `frontend/src/lib/components/trip-detail/TripHero.svelte` | **Ziel 2:** Hero im Overview-Tab — H1 `trip-hero-title`, Date-Range, 3 Stat-Tiles |
| `frontend/src/lib/components/trip-detail/TripOverview.svelte` | Wrapper für TripHero (rendert `<TripHero {trip} {now} />`) — keine Änderung nötig |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | **Ziel 3:** Wizard-Header — `header.mb-6` mit Eyebrow + H1 + Stepper |
| `frontend/src/routes/_design/+page.svelte` | Showcase-Referenz (Section `topo-section`) — zeigt die Standard-Verwendung |

## Existing Patterns

### TopoBg-Verwendung (aktuell)
- `ActiveTripCard.svelte`: `<TopoBg>` ohne explizite `opacity`-Prop, wrappt das gesamte Card-Innere (`p-6 space-y-3` Block).
- `_design/+page.svelte`: `<TopoBg>` ohne `opacity` als Showcase-Wrapper um einen `p-8`-Block.

### TopoBg-Atom-Struktur
```svelte
<div class="relative overflow-hidden">
  <div class="g-topo absolute inset-0" style:--g-topo-opacity={opacity}></div>
  <div class="relative">{@render children?.()}</div>
</div>
```
Atom liefert eigene Positionierung (`relative`, `overflow-hidden`) + Inner-Layer (`relative`). Issue-Vorgabe „Content auf `relative z-10`" ist daher bereits durch das Atom abgedeckt — Inner-Layer hat `position: relative`, dadurch über dem `absolute inset-0`-Pattern. Eine zusätzliche `z-10`-Klasse am Content ist nicht erforderlich, ausser ein Container darin nutzt eigene Stacking-Contexts.

### Opacity-Werte
- Default: `0.5` (aus `app.css` `--g-topo-opacity, 0.5`; TopoBg-Default-Prop `0.5`)
- Issue-Empfehlung: 0.3–0.5, sichtbar evaluieren. 0.4 als Startwert vorgegeben.

### Eyebrow/Hero-Patterns
- Cockpit-Topbar: kein GCard-Container — flacher Header direkt im `space-y-6`-Body
- TripHero: eigene Styles `padding: 1rem`, Stat-Tiles mit `background: var(--g-surface-2, rgba(0,0,0,0.03))`
- TripWizardShell: `<header class="mb-6 space-y-1">` mit Eyebrow + H1

## Dependencies
- Upstream: `TopoBg` (stabiles Atom, in Issue #209 eingeführt), `.g-topo` CSS-Klasse
- Downstream:
  - E2E `tokens-and-topo.spec.ts` (testet nur Token-Werte + Background-Image-Pattern, nicht Verwendungs-Routen)
  - E2E `trip-detail-hero.spec.ts` (TestIDs `trip-hero`, `trip-hero-title` etc. — TopoBg darf diese nicht überschreiben)
  - E2E `trip-wizard-shell.spec.ts` (TestIDs `trip-wizard-shell`, `trip-wizard-stepper`, `trip-wizard-step-N`)
  - E2E `epic-134-cockpit.spec.ts` (TestID `cockpit-topbar`)

## Existing Specs
- `docs/specs/modules/epic_133_tokens_and_topo.md` — Topo-Geometrie und Default-Opacity 0.5 (Issue #209)
- `docs/specs/modules/epic_133_design_system_lauf_b.md` — Epic-Klammer für Design-System-Sprint
- `docs/specs/modules/epic_134_startseite_cockpit.md` — Cockpit-Struktur (Topbar, ActiveTripCard, Bottom-Row)
- `docs/specs/modules/epic_135_step3_trip_hero.md` — Trip-Hero-Spec (H1 + 3 Stat-Tiles + Date-Range)
- `docs/specs/modules/epic_136_step0_shell.md` — Wizard-Shell-Spec (Header, Stepper, Steps)
- `docs/reference/design_system.md` — TopoBg als „Hero-Bereich"-Atom, Opacity 0.18–0.5

## Risks & Considerations

### R1: Doppel-Topo im Cockpit
`+page.svelte` enthält bereits indirekt einen `<TopoBg>` (über `ActiveTripCard`). Wenn die Cockpit-Topbar einen eigenen `<TopoBg>` bekommt, entsteht visuell:
- Topbar mit Topo
- Direkt darunter ActiveTripCard mit Topo

Risiko: zu viel Pattern, „unruhiges" Cockpit. Lösung: Topbar-Topo bekommt etwas geringere Opacity (~0.3), Card-Topo bleibt bei Default. Visuell evaluieren.

### R2: Stat-Tiles im TripHero haben eigene Hintergrundfarbe
Die Stat-Tiles im TripHero nutzen `background: var(--g-surface-2, rgba(0,0,0,0.03))`. Mit TopoBg dahinter könnte der Halbtransparenz-Effekt der Tiles dafür sorgen, dass das Topo-Muster durch die Tiles durchscheint. Das ist akzeptabel, sofern der Stat-Wert lesbar bleibt. Falls nötig: `--g-surface-2` auf opake Variante setzen oder Topo-Wrapper nur um Header+Date-Range (nicht Stat-Tiles).

### R3: Wizard-Stepper hat eigene Indikatoren mit `data-state`
Der Stepper rendert pro Step ein eigenes Element mit Hover/Active-State. TopoBg dahinter ist visuell unproblematisch, weil Stepper-Indikatoren ihre eigene Box-Stilistik haben. Aber: TopoBg wrappt im Issue „Stepper + Step-Titel" — der Step-Slot (Step1Profile etc.) soll NICHT eingeschlossen sein. → Topo nur um `<header>` + `<Stepper>`.

### R4: TopoBg-Atom benutzt `overflow-hidden`
Das könnte mit absoluten Positionierungen innerhalb der Hero-Bereiche kollidieren (z.B. Tooltips, Sticky-Elements). Bei den drei Targets sind aktuell keine sichtbar, aber während der Implementation prüfen.

### R5: Schmaler Topbar-Topo
Die Cockpit-Topbar ist nur ein-zeilig (Datum + H1 + CTAs). Bei `flex-wrap` kann sie auf mobile zwei Zeilen werden. TopoBg darum bekommt dann eine sehr flache Höhe — Pattern wird kaum sichtbar. Akzeptanz: trotzdem zeigen, weil auf Desktop das Hauptfall ist.

### R6: E2E-Regression
TestIDs müssen erhalten bleiben. TopoBg wrappt um (nicht in) die Test-Selektoren. Falls TopoBg einen zusätzlichen `<div>`-Container einfügt, ändert das die DOM-Tiefe nicht relevant — Playwright `getByTestId` arbeitet selektor-basiert.

## Approach Sketch (für Phase 2)

1. **+page.svelte (Cockpit)**: `<header data-testid="cockpit-topbar">` mit `<TopoBg opacity={0.3}>` wrappen. Padding-Anpassung evtl. nötig (Topbar hat aktuell kein eigenes Padding — TopoBg übernimmt Hintergrund, sodass `p-6` o.ä. ergänzt werden sollte, damit das Pattern „atmet").
2. **TripHero.svelte**: Outer-`<div data-testid="trip-hero">` mit `<TopoBg opacity={0.4}>` wrappen. Das vorhandene `padding: 1rem` bleibt in der inneren `.trip-hero`-Klasse.
3. **TripWizardShell.svelte**: Nur `<header>` + `<Stepper>` wrappen (NICHT Step-Slot, Save-Status, Footer). `<TopoBg opacity={0.4}>` mit explizitem Padding.

## Open Questions (für Analyse-Phase)

- Sollen alle drei Bereiche gleichmäßig 0.4 bekommen, oder pro Bereich kalibrieren? → Issue lässt 0.3–0.5 zu, empfiehlt 0.4 als Default.
- Cockpit-Topbar: Padding hinzufügen, oder mit der existierenden `space-y-6`-Struktur arbeiten? Das beeinflusst, wie „luftig" der Topo wirkt.
- Wizard: TopoBg nur um Header oder auch um Stepper? Issue sagt „Stepper + Step-Titel" → Eyebrow+H1+Stepper alle drei.

## Analysis Decisions (Phase 2)

**Opacity differenziert:**
- Cockpit-Topbar: `0.3` — entkoppelt visuell vom darunterliegenden `ActiveTripCard`-Topo (Default 0.5), entschärft R1.
- TripHero: `0.4` (Issue-Default). Stat-Tile-Transparenz ist Branding-konform (R2 akzeptiert).
- Wizard-Header: `0.4` (gleicher Hero-Typ).

**Padding-Strategie:**
- Cockpit-Topbar: `p-6 rounded-lg` am TopoBg-Wrapper ergänzen — Topbar hat aktuell kein Padding, ohne würde Pattern an Text kleben.
- TripHero: existierendes `.trip-hero { padding: 1rem }` bleibt. TopoBg wrappt das outer `<div data-testid="trip-hero">` außen herum, TestID bleibt am Original-Element.
- Wizard: `p-6 rounded-lg mb-6` am TopoBg-Wrapper. Existierendes `mb-6` am `<header>` entfernen, damit kein doppelter Abstand.

**Wrap-Scope Wizard (Klarstellung zu R3):**
TopoBg umschließt **ausschließlich** `<header>` + `<Stepper>`. NICHT die Step-Slots, NICHT die Save-Status-Region, NICHT den Footer.

**Implementierungs-Reihenfolge:**
1. `TripHero.svelte` (Pilot, klarster TestID-Schutz)
2. `TripWizardShell.svelte` (Scope-Disziplin)
3. `+page.svelte` Cockpit (visuelle Kalibrierung gegen ActiveTripCard zuletzt)

**TDD-Plan (neue Test-Datei):** `frontend/e2e/topo-heroes.spec.ts` (nicht `frontend/tests/e2e/...` — bestehende Konvention ist `frontend/e2e/`).
- AC-1: `getByTestId('cockpit-topbar')` enthält Descendant mit Klasse `.g-topo`
- AC-2: `getByTestId('trip-hero')` enthält `.g-topo`
- AC-3: `getByTestId('trip-wizard-shell')` enthält `.g-topo` als Ancestor von `trip-wizard-stepper`
- AC-4 (Scope-Guard): `.g-topo` ist NICHT Ancestor von `trip-wizard-step1-profile` (R3)

**Bestehende Regressions-Schranke:** `epic-134-cockpit.spec.ts`, `trip-detail-hero.spec.ts`, `trip-wizard-shell.spec.ts`, `tokens-and-topo.spec.ts` müssen unverändert grün bleiben.

**Scope:**
- 3 EDIT (Cockpit, TripHero, WizardShell) + 1 NEU (E2E-Spec) = **4 Dateien**
- Geschätzt **30–50 LoC** (Wraps + Imports + Padding-Tweaks + 4 Tests). Deutlich unter 250-LoC-Limit.

**Validierungs-Plan:**
- Pre-Screenshots vor Branch-Push: `/`, `/trips/<seed-id>`, `/trips/new`
- Post-Screenshots nach Staging-Deploy: gleiche Routen
- Sichtprüfung manuell — Branding-Entscheidung, kein automatischer Diff nötig.

**Risiken — Status:**
- R1 Doppel-Topo: gelöst durch Opacity-Differenzierung. Final via Screenshot-Review.
- R2 Stat-Tiles: akzeptiert (Branding).
- R3 Wizard-Scope: gelöst durch klare Wrap-Grenze + Scope-Guard-Test.
- R4 `overflow-hidden`: kein Issue in den 3 Targets.
- R5 Mobile-Topbar: akzeptiert.
- R6 E2E-Regression: TestIDs bleiben am Original-Element, Wrap fügt nur 2 `<div>`s drumherum — `getByTestId` selektor-basiert, kein Bruch.
