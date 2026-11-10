# Context: fix-2621-hand-cursor

## Request Summary
Auf /verify-email zeigt der Bestätigen-Knopf keinen Hand-Cursor und wirkt nicht klickbar (PO-Beobachtung Prod, 26.10.). Gleiche Prüfung für die übrigen Auth-Seiten.

## Ursache
Tailwind v4 (`frontend/package.json`: `tailwindcss ^4.2.2`) setzt in Preflight für `<button>` `cursor: default` (v3 hatte `cursor: pointer`). Nur Elemente mit eigener Regel zeigen die Hand: Btn-Atom `[data-slot="btn"]` (`app.css` ~Z. 434), Segmented-Item (~Z. 641) und 5 Stellen mit expliziter Klasse `cursor-pointer`.

## Related Files
| File | Relevance |
|------|-----------|
| frontend/src/app.css | Ort der Korrektur: globale Boden-Regel in `@layer base` (Muster wie Block ab Z. 771 mit `:where()`) |
| frontend/src/routes/verify-email/+page.svelte:27 | rohes `<button type="submit">` ohne cursor-pointer (Auslöser) |
| frontend/src/routes/login/+page.svelte:210,240,292 | rohe Buttons (Resend, Passkey, Submit) |
| frontend/src/routes/register/+page.svelte:93 | rohes Submit |
| frontend/src/routes/forgot-password/+page.svelte:37 | rohes Submit |
| frontend/src/routes/reset-password/+page.svelte:45 | rohes Submit |
| frontend/src/routes/magic-link/+page.svelte:46 | rohes Submit |

App-weit: 74 Svelte-Dateien mit rohem `<button>`, nur 5 mit `cursor-pointer` — der Fehler betrifft nicht nur Auth-Seiten.

## Existing Patterns
- Tailwind-v4-Upgrade-Guide empfiehlt genau: `@layer base { button:not(:disabled), [role="button"]:not(:disabled) { cursor: pointer; } }`.
- Repo-Muster „Boden-Regel": `@layer base` + `:where()` hält Spezifität bei 0, jede Bausteinregel (z. B. `cursor: not-allowed` am Btn-Atom ~Z. 568) gewinnt.
- Tests: CSS-Aussagen werden per `node --test` gegen app.css geprüft (z. B. `src/lib/__tests__/danger_flaeche_kontrast.test.ts`); Verhalten aus Nutzersicht per Playwright in `frontend/e2e/` (CI-Job `e2e`), Auth-Seiten sind ohne Login erreichbar.

## Dependencies
- Upstream: Tailwind v4 Preflight.
- Downstream: alle Knöpfe der App. Gesperrte Knöpfe (`:disabled`) dürfen keine Hand zeigen; Btn-Atom behält eigenes `cursor`.

## Existing Specs
- `docs/specs/modules/design_system_drift_fixes.md`, `docs/reference/design_system.md` (Design-Regeln; Doku-Ergänzung prüfen).

## Risks & Considerations
- Spezifität: Regel mit `:where()` in `@layer base`, damit `cursor-not-allowed`/`cursor-default`-Utilities und Bausteinregeln weiter gewinnen.
- `aria-disabled="true"`-Knöpfe ebenfalls ausnehmen.
- Kein Svelte-Umbau der Auth-Seiten auf die Button-Komponente nötig (größerer Blast Radius, nicht verlangt).
- Nachweis aus Nutzersicht: berechneter Cursor (`getComputedStyle(...).cursor`) im Browser auf allen sechs Auth-Seiten, plus gesperrter Knopf bleibt ohne Hand.

## Analysis

### Type
Bug (Regression durch Tailwind-v4-Preflight: `<button>` erbt `cursor: default`).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/app.css | MODIFY | Boden-Regel in `@layer base`: `:where(button:not(:disabled):not([aria-disabled="true"]), [role="button"]:not([aria-disabled="true"]), label[for], summary) { cursor: pointer; }` (Spezifität 0, außerhalb der Mobile-Media-Query) |
| frontend/src/lib/__tests__/hand_cursor_boden.test.ts | CREATE | `node --test` gegen app.css: Regel vorhanden, in `@layer base`, in `:where()`, schließt `:disabled`/`aria-disabled` aus |
| frontend/e2e/hand-cursor-auth.spec.ts | CREATE | Playwright: `getComputedStyle(btn).cursor === "pointer"` auf /verify-email, /login, /register, /forgot-password, /reset-password, /magic-link; gesperrter Knopf ≠ pointer; Btn-Atom disabled bleibt `not-allowed` |
| docs/reference/design_system.md | MODIFY | Ein Satz zur Cursor-Boden-Regel |

### Scope Assessment
- Files: 4
- Estimated LoC: +~70/-0 (CSS ~8, Rest Tests/Doku)
- Risk Level: LOW — reine CSS-Boden-Regel ohne Spezifität; jede bestehende Bausteinregel/Utility (`cursor-not-allowed`, `cursor-default` in SubscriptionKebab, Btn-Atom `not-allowed`) gewinnt weiter.

### Technical Approach
Globale Boden-Regel statt 70+ Einzelstellen (Tailwind-v4-Upgrade-Guide-Empfehlung, Repo-Muster `@layer base` + `:where()`). Kein Umbau der Auth-Seiten auf die Button-Komponente. Nachweis aus Nutzersicht über berechneten Cursor im Browser (CI-Job `e2e`, Auth-Seiten ohne Login erreichbar).

### Dependencies
Tailwind v4 Preflight (Upstream); alle Knöpfe der App (Downstream). Reihenfolge der Layer: Preflight liegt ebenfalls in `base`, unsere Regel steht in app.css nach dem Import und gewinnt bei gleicher Schicht über Quellreihenfolge — im Test explizit prüfen (berechneter Cursor, nicht nur Dateiinhalt).

### Open Questions
- keine (Produktverhalten eindeutig: klickbar = Hand, gesperrt = keine Hand)
