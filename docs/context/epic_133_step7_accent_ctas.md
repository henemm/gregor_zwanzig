---
workflow: epic_133_step7_accent_ctas
created: 2026-05-13
issue: 219
parent_epic: 133
type: context
---

# Context: Marken-CTAs auf Btn variant="accent" setzen

## Request Summary

Issue #219: An 3-5 gezielten Stellen die zentralen Haupt-CTAs von `variant="primary"` (Ink-Schwarz) auf `variant="accent"` (Burnt-Orange) umstellen, damit die Markenidentität nach der Theme-Bridge auch sichtbar wird. Sparsam einsetzen — sonst geht der Akzent verloren.

## Befund nach Inspektion

**Tatsächlich zu editieren: 3 Stellen** (nicht 5 — Wizard Save ist schon `accent`, Cockpit-CTA und Startseite-CTA sind derselbe Button).

| # | Datei | Zeile | Aktuell | Neu |
|---|-------|-------|---------|-----|
| 1 | `frontend/src/routes/+page.svelte` | 142 | `<Btn variant="primary" data-testid="cta-new-trip" href="/trips/new" size="sm">Neuer Trip</Btn>` | `variant="accent"` |
| 2 | `frontend/src/routes/trips/+page.svelte` | 213 | `<Btn variant="primary" onclick={() => goto('/trips/new')}>Neuer Trip</Btn>` | `variant="accent"` |
| 3 | `frontend/src/routes/compare/+page.svelte` | 423 | `<Btn variant="primary" onclick={runComparison} disabled={loading}>...Vergleichen</Btn>` | `variant="accent"` |

**Schon korrekt (kein Edit):**
- `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` Z. 123 (Weiter), Z. 133 (Speichern) — beide schon `variant="accent"`

**Alter Wizard ignoriert:** `frontend/src/lib/components/wizard/TripWizard.svelte` nutzt noch die alte `Button`-Komponente, Cleanup in Issue #190.

## Bewusst NICHT auf accent (laut Issue):

- Speichern in Forms/Dialogen (Subscription, Location, Weather-Config) → bleibt `primary`
- Confirm in Archive-/Delete-Dialog → bleibt `primary`
- Stage-/Waypoint-CTAs ("+ Etappe hinzufügen") → bleibt `outline`
- Pause/Archive im Trip-Header → bleibt `outline`
- Test-Briefing (Cockpit) → bleibt `outline`

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/routes/+page.svelte` Z. 141-148 | **EDIT-Ziel #1:** Cockpit/Startseite-CTA |
| `frontend/src/routes/trips/+page.svelte` Z. 213 | **EDIT-Ziel #2:** Trips-Liste-CTA |
| `frontend/src/routes/compare/+page.svelte` Z. 423 | **EDIT-Ziel #3:** Compare-Button |
| `frontend/src/lib/components/ui/btn/Btn.svelte` | Btn-Atom mit `variant="accent"` (Burnt-Orange) — bereits in app.css definiert seit Issue #214 |
| `frontend/src/app.css` Z. 170-177 | `[data-slot="btn"][data-variant="accent"]` Styles — `bg-accent`, `color-paper`, mit Hover-Variante |

## Existing Patterns

- **Btn-Komponente** mit `variant`-Prop hat 7 Varianten (`primary`, `accent`, `outline`, `ghost`, `secondary`, `destructive`, `link`) — etabliert in Issue #214.
- **Accent ist sparsam:** Aktuell wird `accent` nur an wenigen Stellen genutzt (TripWizardShell, evtl. einzelne andere). Issue #219 fügt 3 weitere bewusste Stellen hinzu.
- **CTA-Pattern:** `data-testid="cta-..."` für E2E-Tests bei der Startseite-CTA — neuer "Vergleichen"-Button und Trips-Liste-CTA haben keinen `data-testid`, sind aber identifizierbar über Text/Position.

## Dependencies

- **Upstream:** `Btn`-Komponente und `--g-accent`-Token (beide stabil seit Epic #133 Step 1/2)
- **Downstream:** Bestehende E2E-Tests, die diese Buttons klicken (z.B. `dashboard.spec.ts` "Neuer Trip"-Click, `trips.spec.ts` etc.). Tests sollten weiterhin grün sein, weil das `data-testid` und Text unverändert bleiben.

## Existing Specs

- `docs/specs/modules/epic_133_step6_theme_bridge.md` — Vorgänger-Spec (Theme-Bridge), liefert `--color-accent` als Burnt-Orange
- `docs/specs/modules/btn_component.md` (falls existiert) — Btn-Komponenten-Spec mit allen Varianten

## Risks & Considerations

1. **Risiko niedrig:** 3 reine Attribut-Änderungen (`primary` → `accent`), keine Verhaltens-Änderung.
2. **E2E-Tests:** Bestehende Tests, die nach `data-testid="cta-new-trip"` greifen oder Text "Neuer Trip"/"Vergleichen" suchen, bleiben funktional.
3. **Visueller Sichtcheck:** Pre/Post-Screenshots auf 3 Routen (`/`, `/trips`, `/compare`) — die einzige sichtbare Veränderung sind die 3 Buttons in Burnt-Orange.
4. **Konsistenz:** Falls noch andere `<Btn variant="primary">Neuer Trip</Btn>` woanders existieren (z.B. Empty-State), sind die NICHT in Scope laut Issue. Wir editieren genau die im Issue genannten 3 Stellen.

## Scope

- **3 Files, 3 Single-Word-Edits** (`primary` → `accent`)
- **~3 Zeilen LoC-Delta**
- **Keine neuen Tests nötig** — bestehende E2E-Tests decken die Buttons schon ab
- **Pre/Post-Screenshots** als visuelle Verifikation

## Next Phase

Phase 2 — Analyse: Da der Scope trivial klein ist (3 Wort-Änderungen), wahrscheinlich schlanker Spec-Schritt mit ACs zum Variant-Wert und visuellem Sichtcheck.
