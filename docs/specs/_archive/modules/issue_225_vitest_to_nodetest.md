---
entity_id: issue_225_vitest_to_nodetest
type: refactor
created: 2026-05-15
updated: 2026-05-15
status: draft
version: "1.0"
tags: [frontend, sveltekit, tests, refactor, tech-debt]
---

# Issue #225 — Frontend-Tests von Vitest auf node:test umstellen

## Approval

- [ ] Approved

## Purpose

Drei Frontend-Unit-Test-Dateien importieren `vitest`, das nicht als Dev-Dependency installiert ist. Sie scheitern mit `ERR_MODULE_NOT_FOUND` und überdecken echte Test-Failures. Die Tests werden von Vitest-API (`describe`/`test`/`expect`) auf den Projekt-Standard `node:test` + `node:assert/strict` umgestellt (wie `tripHero.test.ts`, `tripStatus.test.ts`). Damit ist die Test-Suite konsistent und ohne zweites Test-Framework.

## Source

- **Files (3):**
  - `frontend/src/lib/components/ui/btn/Btn.test.ts`
  - `frontend/src/lib/utils/fullProfile.test.ts`
  - `frontend/src/lib/utils/rightColumn.test.ts`

> **PFLICHT — Schicht-Hinweis:** Frontend (SvelteKit), nur `.test.ts`-Dateien. Keine Production-Komponenten, kein Backend.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `node:test` | Node-Standard | Test-Runner (statt vitest) |
| `node:assert/strict` | Node-Standard | Assertions (statt expect) |
| `tripHero.test.ts`, `tripStatus.test.ts` | Vorbild-Tests | Konsistenz-Pattern |

## Implementation Details

### API-Mapping Vitest → node:test

| Vitest | node:test |
|--------|-----------|
| `import { describe, test, expect } from 'vitest'` | `import { test } from 'node:test'; import assert from 'node:assert/strict'` |
| `describe('foo', () => { test('bar', ...) })` | `test('foo > bar', () => { ... })` *oder* `test('foo', async (t) => { await t.test('bar', ...) })` |
| `expect(x).toBe(y)` | `assert.equal(x, y)` |
| `expect(x).toEqual(y)` | `assert.deepEqual(x, y)` |
| `expect(x).toContain(y)` | `assert.ok(x.includes(y))` *oder* `assert.match(x, /y/)` für Strings |
| `expect(x).toBeTruthy()` | `assert.ok(x)` |
| `expect(x).toBeFalsy()` | `assert.ok(!x)` |
| `expect(x).toBeUndefined()` | `assert.equal(x, undefined)` |
| `expect(x).toBeNull()` | `assert.equal(x, null)` |
| `expect(x).toHaveLength(n)` | `assert.equal(x.length, n)` |
| `expect(fn).toThrow()` | `assert.throws(() => fn())` |

Bei `describe`-Gruppierung: Die einfachste Konvention ist `test('describe > test', ...)` (Strich-Trennung im Test-Namen). Alternative: `await t.test(...)`-Subtests. Beide sind akzeptabel.

### Header-Kommentare anpassen

Die Datei-Header sagen aktuell `cd frontend && npx vitest run src/...`. Auf:
```
cd frontend && node --experimental-strip-types --test src/.../foo.test.ts
```
umstellen.

## Expected Behavior

- **Pre-Refactor:** `node --experimental-strip-types --test 'src/**/*.test.ts'` scheitert mit `ERR_MODULE_NOT_FOUND: Cannot find package 'vitest'` für die 3 Dateien.
- **Post-Refactor:** Alle 3 Test-Dateien laufen mit `node --experimental-strip-types --test`. Test-Coverage unverändert (selbe Asserts, andere API).
- **Side effects:** Keine. `package.json` bleibt unverändert (vitest war eh nie installiert).

## Acceptance Criteria

- **AC-1:** Given die 3 Test-Dateien nach Refactor / When `cd frontend && node --experimental-strip-types --test src/lib/components/ui/btn/Btn.test.ts src/lib/utils/fullProfile.test.ts src/lib/utils/rightColumn.test.ts` läuft / Then **kein `ERR_MODULE_NOT_FOUND`**, alle Tests laufen.
  - Test: (populated after /tdd-red)

- **AC-2:** Given die 3 Test-Dateien nach Refactor / When `grep -n "from 'vitest'\|from \"vitest\"" frontend/src/` läuft / Then **0 Treffer**.
  - Test: (populated after /tdd-red)

- **AC-3:** Given die ursprünglich abgedeckten Funktionen (`buildProfilePoints`, `computeStageBoundaries`, `formatStageCode`, `getActiveStageId`, `getPresetLabel`, `getDefaultMetricsForProfile`, `getActiveMetrics`, `getReportSchedule`, Btn-Variants, -Sizes, href-Switch, disabled-State) / When die migrierten Tests laufen / Then werden **dieselben Verhalten** getestet wie vorher (Test-Anzahl darf abweichen, weil `describe`/`subtest` ggf. flach gemacht wird, aber die getestete Funktionalität bleibt). Mindestens **alle Asserts der ursprünglichen Datei** sind im migrierten Test vorhanden.
  - Test: (populated after /tdd-red)

## Out of Scope

- `vitest` als Dev-Dependency aufnehmen (anti-Empfehlung, weil zweites Framework)
- Tests komplett löschen (Coverage bleibt erhalten)
- Andere Test-Dateien ändern
- Test-Inhalt erweitern (nur Migration, keine neuen Asserts)

## Verification

- **Direct:** `cd frontend && node --experimental-strip-types --test src/lib/components/ui/btn/Btn.test.ts src/lib/utils/fullProfile.test.ts src/lib/utils/rightColumn.test.ts` → exit 0, keine `ERR_MODULE_NOT_FOUND`
- **Grep:** `grep -rn "from 'vitest'\|from \"vitest\"" frontend/src/ --include='*.ts'` → 0 Treffer
- **Konsistenz:** `grep -rn "from 'node:test'" frontend/src/ --include='*.test.ts' | wc -l` → ≥ 3 (vorher war es 0 für diese Dateien)

## LoC-Estimate

- 3 Dateien à ~150-300 LoC, im Schnitt 20-50 Edits pro Datei
- Erwartetes LoC-Delta: ±0 (Translation), netto leicht positiv durch zusätzlichen `assert`-Import + längere Asserts

## Risks

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Test-Behavior ändert sich durch API-Translation (z. B. asynchrone Asserts) | niedrig | Test-Lauf vor/nach verifiziert dasselbe Ergebnis |
| `describe`-Gruppierung geht verloren / Test-Output unübersichtlicher | niedrig | Konvention `'foo > bar'` als Test-Name; Output bleibt lesbar |
| Btn.test.ts nutzt `svelte/server.render` — kompatibel mit node:test? | niedrig | API unabhängig vom Test-Framework, nur reine TS-Imports |

## Changelog

- 2026-05-15: Initial spec created (Issue #225)
