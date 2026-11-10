---
entity_id: hand_cursor_boden_regel
type: module
created: 2026-11-10
updated: 2026-11-10
status: draft
version: "1.0"
tags: [frontend, css, design-system, bug, "#2621"]
---

# Hand-Cursor-Boden-Regel

## Approval

- [ ] Approved

## Purpose

Klickbare Knöpfe zeigen beim Darüberfahren wieder die Hand, nachdem Tailwind v4 im Preflight für `<button>` `cursor: default` setzt und rohe Knöpfe (z. B. Bestätigen auf `/verify-email`) dadurch nicht klickbar wirken. Eine globale Boden-Regel ohne Spezifität stellt die Hand app-weit her, ohne 70+ Einzelstellen anzufassen.

## Source

- **File:** `frontend/src/app.css`
- **Identifier:** neue Regel in `@layer base` (`:where(button:not(:disabled):not([aria-disabled="true"]), [role="button"]:not([aria-disabled="true"]), label[for], summary) { cursor: pointer; }`), außerhalb der Mobile-Media-Query

Betroffene Dateien (Schicht: Frontend, SvelteKit):

| Datei | Änderung |
|-------|----------|
| `frontend/src/app.css` | MODIFY: Boden-Regel |
| `frontend/src/lib/__tests__/hand_cursor_boden.test.ts` | CREATE: `node --test`, Regel-Form (`@layer base`, `:where()`, Ausschlüsse) |
| `frontend/e2e/hand-cursor-auth.spec.ts` | CREATE: Playwright, berechneter Cursor im Browser |
| `docs/reference/design_system.md` | MODIFY: ein Satz zur Cursor-Boden-Regel |

Querschnitts-Prüfpunkte:

- **Trip/Ortsvergleich-Teilung:** kein Pendant, reine globale CSS-Regel, wirkt für beide Kontexte gleich.
- **Mandantentrennung:** keine Nutzerdaten bewegt, kein `user_id`-Bezug; Auth-Seiten ohne Login erreichbar.
- **Kanäle:** kein Briefing-/Alarm-Inhalt betroffen, nur Browser-Oberfläche.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/app.css` | MODIFY | Boden-Regel in `@layer base` mit `:where()`, außerhalb der Mobile-Media-Query |
| `frontend/src/lib/__tests__/hand_cursor_boden.test.ts` | CREATE | `node --test`: Regel steht in `@layer base`, in `:where()`, mit beiden Ausschlüssen (Ergänzung, nicht alleiniger Nachweis) |
| `frontend/e2e/hand-cursor-auth.spec.ts` | CREATE | Playwright: berechneter Cursor im Browser (AC-1 bis AC-6) |
| `.github/ci_e2e_specs.txt` | MODIFY (bedingt) | neue E2E-Spec aufnehmen, nur bei 3× grün, sonst Folge-Issue |
| `docs/reference/design_system.md` | MODIFY | ein Satz zur Cursor-Boden-Regel |

## Estimated Scope

- **LoC:** ca. +70 (CSS ca. 8, Rest Tests/Doku)
- **Files:** 4
- **Effort:** low (Risiko niedrig: Spezifität 0, jede Bausteinregel gewinnt weiter)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Tailwind v4 Preflight | Upstream | setzt `cursor: default` auf `<button>`; Regel steht in app.css nach dem Import und gewinnt bei gleicher Schicht über die Quellreihenfolge |
| Btn-Atom `[data-slot="btn"]` | Downstream | behält eigenes `cursor` inkl. `not-allowed` bei disabled |
| Utilities `cursor-default` / `cursor-not-allowed` (z. B. SubscriptionKebab) | Downstream | gewinnen weiter (Utilities-Schicht über base) |
| Auth-Seiten (verify-email, login, register, forgot-password, reset-password, magic-link) | Downstream | rohe `<button>` ohne Cursor-Regel |

## Implementation Details

```
@layer base {
  :where(
    button:not(:disabled):not([aria-disabled="true"]),
    [role="button"]:not([aria-disabled="true"]),
    label[for],
    summary
  ) { cursor: pointer; }
}
```

- Außerhalb der Mobile-Media-Query, damit sie auf allen Breiten gilt.
- `:where()` hält die Spezifität bei 0; gesperrte Knöpfe (`:disabled`, `aria-disabled="true"`) bekommen keine Hand.
- Kein Umbau der Auth-Seiten auf die Button-Komponente (nicht verlangt, größerer Blast Radius).

## Expected Behavior

- **Input:** Maus fährt über ein Bedienelement.
- **Output:** klickbar (aktiver Knopf, `role="button"`, Label mit `for`, `summary`) zeigt Hand; gesperrt zeigt keine Hand (Btn-Atom: „nicht erlaubt"-Cursor).
- **Side effects:** keine; bestehende Ausnahmen (`cursor-default`, `cursor-not-allowed`, Btn-Atom) bleiben unverändert.

## Definition of Done

- Auf `/verify-email` und den fünf übrigen Anmeldeseiten zeigt jeder aktive Knopf die Hand (AC-1, AC-2).
- In der eingeloggten App zeigen rohe Knöpfe ohne eigene Cursor-Klasse die Hand (AC-3).
- Gesperrte Knöpfe zeigen keine Hand; Btn-Atom gesperrt bleibt `not-allowed`; bewusste `cursor-default`-Ausnahmen bleiben (AC-4 bis AC-6).
- Neuer node-Test und neue E2E-Spec grün; CI-Positivliste nur bei 3× grün ergänzt, sonst Folge-Issue.
- Auf Staging per `/e2e-verify` nachgewiesen, nach Produktion ausgeliefert, Selftest Exit 0.

## Acceptance Criteria

- **AC-1:** Given ein Besucher ist nicht eingeloggt und öffnet `/verify-email` / When er die Maus über den Bestätigen-Knopf bewegt / Then zeigt der Knopf die Hand (berechneter Cursor `pointer`).
  - Test: Playwright `hand-cursor-auth.spec.ts` lädt `/verify-email` und prüft `getComputedStyle(knopf).cursor === "pointer"` im echten Browser.

- **AC-2:** Given ein Besucher ist nicht eingeloggt / When er auf `/login`, `/register`, `/forgot-password`, `/reset-password` und `/magic-link` die Maus über die Absende- und Zusatzknöpfe (z. B. Passkey, Erneut senden) bewegt / Then zeigt jeder aktive Knopf die Hand.
  - Test: Playwright durchläuft alle fünf Seiten und prüft je sichtbarem, nicht gesperrtem Knopf den berechneten Cursor `pointer`.

- **AC-3:** Given ein Nutzer ist eingeloggt in der App / When er die Maus über einen rohen Knopf außerhalb der Auth-Seiten bewegt (ohne eigene `cursor-pointer`-Klasse) / Then zeigt er die Hand.
  - Test: Playwright prüft auf einer eingeloggten Seite einen rohen `<button>` ohne Cursor-Klasse auf berechneten Cursor `pointer`; ergänzend `role="button"`, `label[for]` und `summary`, soweit vorhanden.

- **AC-4:** Given ein Knopf ist gesperrt (`disabled` oder `aria-disabled="true"`) / When der Nutzer die Maus darüber bewegt / Then zeigt er keine Hand.
  - Test: Playwright setzt auf einer Seite einen Knopf auf `disabled` bzw. `aria-disabled="true"` und prüft berechneten Cursor ungleich `pointer`; `node --test` sichert zusätzlich, dass beide Ausschlüsse in der Regel stehen.

- **AC-5:** Given ein gesperrter Knopf des Btn-Atoms / When der Nutzer die Maus darüber bewegt / Then zeigt er weiter den „nicht erlaubt"-Cursor (`not-allowed`) und nicht die Hand.
  - Test: Playwright prüft am gesperrten Btn-Atom `getComputedStyle(...).cursor === "not-allowed"`.

- **AC-6:** Given Bedienelemente mit bewusster Ausnahme (`cursor-default`, z. B. SubscriptionKebab, und `cursor-not-allowed`-Utilities) / When der Nutzer die Maus darüber bewegt / Then behalten sie ihren bisherigen Cursor, die Boden-Regel überschreibt sie nicht.
  - Test: Playwright (oder `node --test` mit CSS-Auswertung) prüft am Element mit `cursor-default` den berechneten Cursor `default`; `node --test` bestätigt `:where()` (Spezifität 0) in `@layer base`.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN das heutige `app.css` WHEN `hand_cursor_boden.test.ts` läuft THEN rot (keine Boden-Regel), nach dem Fix grün.
- [ ] Test 2: GIVEN `/verify-email` ohne Login WHEN der berechnete Cursor des Bestätigen-Knopfs gemessen wird THEN `pointer` (heute `default`, also rot).
- [ ] Test 3: GIVEN `/login`, `/register`, `/forgot-password`, `/reset-password`, `/magic-link` WHEN jeder aktive Knopf gemessen wird THEN `pointer`.
- [ ] Test 4: GIVEN eine eingeloggte Seite mit rohem `<button>` ohne Cursor-Klasse WHEN gemessen THEN `pointer`.
- [ ] Test 5: GIVEN ein Knopf mit `disabled` bzw. `aria-disabled="true"` WHEN gemessen THEN nicht `pointer`; gesperrtes Btn-Atom `not-allowed`; Element mit `cursor-default` bleibt `default`.

Aufruf Test 1: `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test src/lib/__tests__/hand_cursor_boden.test.ts`. Tests 2-5: `npx playwright test e2e/hand-cursor-auth.spec.ts`. Keine Mocks.

## Known Limitations

- Rohe Knöpfe bleiben rohe Knöpfe (kein Umbau auf die Button-Komponente).
- Nicht erfasst: Elemente, die nur per Klick-Handler (`onclick` auf `div`) klickbar sind, ohne `role="button"`; sie brauchen weiterhin eine eigene Cursor-Regel.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine CSS-Korrektur im Rahmen bestehender Design-Konventionen (Boden-Regel-Muster `@layer base` + `:where()`, Tailwind-v4-Upgrade-Guide); keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Editor, Test/Deploy) berührt, keine bestehende Entscheidung wird abgelöst.

## Changelog

- 2026-11-10: Initial spec created (Issue #2621)
