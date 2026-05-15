---
entity_id: issue_227_tripstatus_import_extension
type: bugfix
created: 2026-05-15
updated: 2026-05-15
status: draft
version: "1.0"
tags: [frontend, sveltekit, tests, bugfix, tech-debt]
---

# Issue #227 — fullProfile.ts: Import ./tripStatus braucht .ts-Endung

## Approval

- [ ] Approved

## Purpose

`frontend/src/lib/utils/fullProfile.ts:13` importiert `from './tripStatus'` ohne `.ts`-Endung. Vite/SvelteKit toleriert das (eigener Resolver), `node --experimental-strip-types --test` aber nicht — Node-ESM-Spec ist strikt. Dadurch scheitert `fullProfile.test.ts` mit `ERR_MODULE_NOT_FOUND`. Fix: `.ts`-Endung anhängen.

## Source

- **File:** `frontend/src/lib/utils/fullProfile.ts:13`
- **Identifier:** `import { deriveTripStatus } from './tripStatus';` → `from './tripStatus.ts';`

> **PFLICHT — Schicht-Hinweis:** Frontend (SvelteKit), pure-TS-Util. Keine Komponente, kein Backend.

## Acceptance Criteria

- **AC-1:** Given das Repo nach Fix / When `cd frontend && node --experimental-strip-types --test src/lib/utils/fullProfile.test.ts` läuft / Then **kein `ERR_MODULE_NOT_FOUND`**, alle Tests aus der Datei laufen und sind grün.
  - Test: (populated after /tdd-red)

- **AC-2:** Given das Repo nach Fix / When SvelteKit-Frontend gebaut wird (`npm run build` im `frontend/`-Verzeichnis) / Then **0 neue Build-Fehler oder Warnings** durch die geänderte Import-Zeile.
  - Test: (populated after /tdd-red)

## Out of Scope

- Andere Imports ohne `.ts`-Endung suchen und fixen (separate Tech-Debt-Initiative)
- Btn.test.ts Svelte-Loader (Issue #228, größerer Aufwand)

## Verification

- `cd frontend && node --experimental-strip-types --test src/lib/utils/fullProfile.test.ts` → exit 0, 27 tests pass
- `cd frontend && npm run build` → erfolgreich
- `grep -n "from './tripStatus'" frontend/src/lib/utils/fullProfile.ts` → 0 Treffer (Original-Pattern weg)
- `grep -n "from './tripStatus.ts'" frontend/src/lib/utils/fullProfile.ts` → 1 Treffer

## LoC-Estimate

1 Zeile geändert. ±0 LoC.
