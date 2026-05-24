---
entity_id: issue_334_triphero_cleanup
type: module
created: 2026-05-24
updated: 2026-05-24
status: draft
version: "1.0"
tags: [cleanup, dead-code, frontend, trip-detail]
---

# Issue #334 — Cleanup: TripHero.svelte (toter Code)

## Approval

- [ ] Approved

## Purpose

`TripHero.svelte` und sein Begleit-Code werden seit dem Trip-Detail-Redesign (#302) nicht mehr gerendert. Diese Spec entfernt die tote Komponente, ihren Barrel-Re-Export, den dazugehörigen toten E2E-Test und die ausschließlich von der Komponente genutzten Util-Funktionen — **ohne** noch aktiv genutzten Code (genutzt von `TripHeader.svelte`) zu beschädigen.

## Source

- **File:** `frontend/src/lib/components/trip-detail/TripHero.svelte` (zu löschen)
- **File:** `frontend/src/lib/components/trip-detail/index.ts` (Re-Export Zeile 5 entfernen)
- **File:** `frontend/e2e/trip-detail-hero.spec.ts` (zu löschen)
- **File:** `frontend/src/lib/utils/tripHero.ts` (verwaiste Funktionen entfernen, überlebende behalten)
- **File:** `frontend/src/lib/utils/tripHero.test.ts` (verwaiste Tests entfernen, überlebende behalten)
- **Identifier:** Komponente `TripHero`; Util-Funktionen `getActiveStageDisplay`, `getNextBriefing` (+ private `parseHHMM`, `compareHHMM`)

> **Schicht-Hinweis:** Reine Frontend-Arbeit (SvelteKit, `frontend/src/...`). Kein Go-, kein Python-Backend betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Konsument | Nutzt `formatDateRange` + `getDaysLabel` aus `tripHero.ts` → diese Funktionen MÜSSEN erhalten bleiben |
| `frontend/src/routes/trips/[id]/+page.svelte` | Konsument | Importiert nur `TripHeader, TripTabs` — NICHT `TripHero` (Beweis für Tot-Status) |
| `tripHero.ts` geteilte Helfer | intern | `daysBetween`, `parseStageDate`, `todayIso`, `sortedStageDates`, `MONTH_NAMES_DE`, `deriveTripStatus` → von `getDaysLabel`/`formatDateRange` genutzt, bleiben erhalten |

## Implementation Details

```
1. LÖSCHEN  frontend/src/lib/components/trip-detail/TripHero.svelte
2. ENTFERNEN frontend/src/lib/components/trip-detail/index.ts Zeile 5:
             export { default as TripHero } from './TripHero.svelte';
3. LÖSCHEN  frontend/e2e/trip-detail-hero.spec.ts
4. ENTFERNEN aus frontend/src/lib/utils/tripHero.ts:
             - getActiveStageDisplay (Z. 54–84)
             - getNextBriefing (Z. 102–117)
             - parseHHMM (Z. 86–93)   [nur von getNextBriefing genutzt]
             - compareHHMM (Z. 95–100) [nur von getNextBriefing genutzt]
             BEHALTEN: getDaysLabel, formatDateRange + alle geteilten Helfer
5. ENTFERNEN aus frontend/src/lib/utils/tripHero.test.ts:
             - die 6 getActiveStageDisplay-Tests + 4 getNextBriefing-Tests
             - die jetzt ungenutzten Importe getActiveStageDisplay, getNextBriefing
             BEHALTEN: getDaysLabel- + formatDateRange-Tests
6. LÖSCHEN  frontend/docs/artifacts/epic-135-step3-trip-hero/ (Artefakt des toten Tests)
```

## Expected Behavior

- **Input:** Bestehender Frontend-Code mit totem `TripHero`-Cluster.
- **Output:** `TripHero`-Komponente, ihr Re-Export, der tote E2E-Test und die verwaisten Util-Funktionen/Tests sind entfernt. `TripHeader.svelte` und die `/trips/[id]`-Seite funktionieren unverändert.
- **Side effects:** Keine. Reines Entfernen nachweislich toten Codes. Ein bislang dauerhaft roter E2E-Test (`trip-detail-hero.spec.ts`) verschwindet.

## Acceptance Criteria

- **AC-1:** Given das Repository / When auf `frontend/src/lib/components/trip-detail/TripHero.svelte` geprüft wird / Then existiert die Datei nicht mehr
  - Test: `tests/tdd/test_issue_334_triphero_cleanup.py::test_ac1_triphero_svelte_file_removed`

- **AC-2:** Given `frontend/src/lib/components/trip-detail/index.ts` / When `grep "TripHero"` auf die Datei ausgeführt wird / Then ist die Trefferanzahl 0 (Re-Export entfernt)
  - Test: `tests/tdd/test_issue_334_triphero_cleanup.py::test_ac2_barrel_reexport_removed`

- **AC-3:** Given das gesamte Verzeichnis `frontend/src` plus `frontend/e2e` / When `grep "TripHero"` (Komponenten-Bezeichner, case-sensitiv) ausgeführt wird / Then ist die Trefferanzahl 0 (kein Import, kein Tag, kein Re-Export irgendwo)
  - Test: `tests/tdd/test_issue_334_triphero_cleanup.py::test_ac3_no_triphero_reference_anywhere_in_frontend`

- **AC-4:** Given das Repository / When auf `frontend/e2e/trip-detail-hero.spec.ts` geprüft wird / Then existiert die Datei nicht mehr (toter E2E-Test entfernt)
  - Test: `tests/tdd/test_issue_334_triphero_cleanup.py::test_ac4_dead_e2e_spec_removed`

- **AC-5:** Given `frontend/src/lib/utils/tripHero.ts` / When `grep -E "getActiveStageDisplay|getNextBriefing|parseHHMM|compareHHMM"` ausgeführt wird / Then ist die Trefferanzahl 0 (verwaiste Funktionen + ihre privaten Helfer entfernt)
  - Test: `tests/tdd/test_issue_334_triphero_cleanup.py::test_ac5_orphan_util_functions_removed`

- **AC-6:** Given `frontend/src/lib/utils/tripHero.ts` / When nach `export function getDaysLabel` und `export function formatDateRange` gegrept wird / Then existiert je genau 1 Treffer (überlebende Funktionen unangetastet)
  - Test: `tests/tdd/test_issue_334_triphero_cleanup.py::test_ac6_surviving_util_functions_intact`

- **AC-7:** Given `frontend/src/lib/utils/tripHero.test.ts` / When `grep -E "getActiveStageDisplay|getNextBriefing"` ausgeführt wird / Then ist die Trefferanzahl 0, während `getDaysLabel`- und `formatDateRange`-Tests weiterhin vorhanden sind
  - Test: `tests/tdd/test_issue_334_triphero_cleanup.py::test_ac7_orphan_tests_removed_survivors_intact`

- **AC-8:** Given das geänderte Frontend / When `cd frontend && npm run build` (bzw. `svelte-check`) ausgeführt wird / Then schließt der Lauf ohne Fehler ab (keine gebrochenen Importe durch die Entfernung)
  - Test: Befehls-Verifikation in Phase 6/Validate (`npm run build`) — bewusst NICHT in der pytest-Suite, um den pre_commit_gate-Volllauf nicht zu verlangsamen

- **AC-9:** Given die verbliebenen Util-Tests / When `cd frontend && node --experimental-strip-types --test src/lib/utils/tripHero.test.ts` ausgeführt wird / Then ist der Exit-Code 0 (überlebende Funktionen weiterhin korrekt — Regressions-Guard)
  - Test: Befehls-Verifikation in Phase 6/Validate (`node --test`) — bewusst NICHT in der pytest-Suite

## Known Limitations

- Die historische Feature-Spec `docs/specs/modules/epic_135_step3_trip_hero.md` bleibt als Dokumentation erhalten (kein Löschen von Specs).
- Das Screenshot-Artefakt ist binär und zählt nicht zum LoC-Delta; seine Entfernung ist Hygiene, nicht testkritisch.
- Scope: ~455 LoC-Delta (fast ausschließlich Löschungen) → `loc_limit_override = 500` für diesen Workflow gesetzt.

## Changelog

- 2026-05-24: Initial spec created (Issue #334)
