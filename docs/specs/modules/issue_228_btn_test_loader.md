---
entity_id: issue_228_btn_test_loader
type: module
created: 2026-05-16
updated: 2026-05-16
status: draft
version: "1.0"
tags: [frontend, test, stub, archive]
issue: 228
---

<!-- Issue #228 — Btn.test.ts braucht Svelte-Loader -->

# Issue #228 — `Btn.test.ts` Skip-Stub + Archiv

## Approval

- [ ] Approved

## Zweck

`Btn.test.ts` bricht mit `ERR_UNKNOWN_FILE_EXTENSION` beim Import von
`.svelte`. Node-Test-Runner `--experimental-strip-types` kann keine
Svelte-Dateien laden. Test-Suite war seit Anbeginn tot (Vitest nie
installiert), wurde erst durch Issue #225 (Vitest → node:test Migration)
sichtbar.

**Tech-Lead-Entscheidung:** Test-Code (230 Zeilen) in Archive-Block der
Original-Spec `docs/specs/modules/issue_214_btn_feature_parity.md`
verschieben. `Btn.test.ts` durch 3-Zeilen-Skip-Stub mit Verweis
ersetzen. So bleibt der Test-Code als Doku erhalten und kann bei
künftiger Vitest- oder Playwright-Component-Tests-Migration reaktiviert
werden.

**Begründung gegen Helper-Extraktion (Issue-Empfehlung Option 2):** Btn.svelte
hat keinen extrahierbaren Algorithmus — nur Tag-Switch (`<a>`/`<button>`)
und Attribut-Forwarding. Künstliche Aufspaltung in Helper würde ~50-100
LoC Code-Gerüst erzeugen ohne echten Mehrwert.

## Quelle / Source

- `frontend/src/lib/components/ui/btn/Btn.test.ts` — durch Skip-Stub ersetzen (~230 LoC → ~12 LoC)
- `docs/specs/modules/issue_214_btn_feature_parity.md` — Archive-Block am Ende anhängen

## Acceptance Criteria

- **AC-1:** Given `Btn.test.ts` / When `cd frontend && node --experimental-strip-types --test src/lib/components/ui/btn/Btn.test.ts` läuft / Then liefert es Exit-Code 0 (kein `ERR_UNKNOWN_FILE_EXTENSION`, keine Failures); der einzige Test ist `test.skip(...)` mit Verweis auf #228

- **AC-2:** Given `docs/specs/modules/issue_214_btn_feature_parity.md` / When ein zukünftiger Entwickler die Btn-Tests reaktivieren will / Then findet er den vollständigen Original-Test-Code (~230 Zeilen) in einem Code-Block-Archiv am Ende der Spec, kopierfertig

- **AC-3:** Given die Btn-Komponente selbst (`Btn.svelte`, `index.ts`) / When der Build läuft / Then sind sie UNVERÄNDERT — keine UI-Regression, kein Type-Change

- **AC-4:** Given svelte-check / When er nach den Edits läuft / Then ist die Error-Anzahl ≤ aktuelle Baseline (24) — der Stub erzeugt keine neuen Type-Errors

## Erwartetes Verhalten

### `Btn.test.ts` (neu, ~12 LoC)

```typescript
// Btn-Component-Tests sind aktuell deaktiviert (#228):
// node --experimental-strip-types --test kann keine .svelte-Imports laden.
//
// Original-Test-Code (230 Zeilen, SSR-Renders aller 7 Variants x 8 Sizes,
// href-Switch, disabled-State, ARIA-Pattern) ist archiviert in
// docs/specs/modules/issue_214_btn_feature_parity.md (Archive-Block am Ende).
//
// Reaktivierung moeglich bei kuenftiger Migration auf Vitest oder
// Playwright Component Tests (eigener Issue).

import { test } from 'node:test';

test.skip('Btn — Tests deaktiviert (siehe #228)', () => {});
```

### `issue_214_btn_feature_parity.md` (Archive-Block)

Am Ende der Spec ein neuer Abschnitt:
```markdown
## Test-Code-Archiv (#228)

Original `Btn.test.ts` ist aktuell deaktiviert wegen fehlendem Svelte-Loader
für `node:test`. Vollständiger Code zur Reaktivierung:

\```typescript
// [vollständiger Original-Test-Code, 230 Zeilen]
\```
```

## Out-of-Scope

- **Vitest installieren** — eigener strategischer Issue (zwei Test-Frameworks parallel ist Anti-Pattern).
- **Playwright Component Tests einführen** — größere Migration, eigener Issue.
- **`Btn.svelte` refactorieren** — die Komponente ist stabil und Production-Code, kein Touch.

## Tests / Verifikation

- **Node-Test:**
  ```bash
  cd frontend && node --experimental-strip-types --test src/lib/components/ui/btn/Btn.test.ts
  ```
  Erwartung: Exit 0, "1 test, 0 pass, 0 fail, 1 skipped" oder ähnlich.
- **svelte-check:** ≤ 24 Errors (Baseline).
- **Manuelle UI-Probe:** Nicht nötig, Komponente unverändert. Prod-HTTP-Smoke nach Deploy reicht.

## Risiken & Migration

- **Risiko vernachlässigbar:** Reine Test-Datei-Änderung, keine Production-Code-Anpassung.
- **Coverage-Verlust: Nein** — Tests liefen vorher nicht (Import-Error), netto kein Verlust.
- **Indirekte Coverage:** TypeScript fängt fehlerhafte Props, Playwright-E2E-Tests
  (`forms-dialogs-btn-migration.spec.ts`, `trip-header-btn-migration.spec.ts`)
  fangen visuelle Regressions.
- **Reaktivierungs-Pfad dokumentiert:** Klar im Stub-Kommentar + Spec-Archive.
