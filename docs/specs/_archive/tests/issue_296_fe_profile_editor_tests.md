---
entity_id: issue_296_fe_profile_editor_tests
type: tests
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
tags: [tests, frontend, sveltekit, naismith, arrival-times, waypoint, profile, issue-296]
parent: issue_296_fe_profile_editor
phase: phase5_tdd_red
---

# Issue #296-FE — Profil-Editor + Naismith-Ankunftszeiten (Test-Manifest)

## Approval

- [x] Approved

## Purpose

Test-Manifest fuer den profil-basierten Trip-Editor aus
`docs/specs/modules/issue_296_fe_profile_editor.md`. Unit-Tests (Node-Runner)
pruefen die clientseitige Naismith-Live-Berechnung und die lineare
Wegpunkt-Interpolation; E2E-Tests (Playwright) decken das Editor-Verhalten
(keine Lat/Lon-Inputs, Profil + Pins, suggested/manuell, Profil-Klick,
Ankunftszeiten, Detail-View-Regression, Pausentag) ab.

Parent-Spec: `docs/specs/modules/issue_296_fe_profile_editor.md` v1.0

## Source

- **File (Unit):** `frontend/src/lib/utils/naismith.test.ts` (NEU)
- **File (Unit):** `frontend/src/lib/utils/waypointEditor.test.ts` (ERWEITERT — `interpolateWaypoint`)
- **File (E2E):** `frontend/e2e/issue-296-profile-editor.spec.ts` (NEU)

## Test Inventory

### Unit — `frontend/src/lib/utils/naismith.test.ts` (Node-Runner)

| Test (Beschreibung) | AC | Was geprueft wird |
|---|---|---|
| `naismithHours(4,0,0) === 1` | AC-6 | 4 km flach / 4 km/h = 1 h. |
| `naismithHours(0,300,0) === 1` | AC-6 | 300 Hoehenmeter Aufstieg / 300 m/h = 1 h. |
| `naismithHours(0,0,500) === 1` | AC-6 | 500 Hoehenmeter Abstieg / 500 m/h = 1 h. |
| `naismithHours summiert alle drei Terme` | AC-6 | SUMME (dist/4 + ascent/300 + descent/500), nicht max(). |
| `computeArrivalTimes` Stage 08:00, 2 WP 4 km flach | AC-5 | erste Zeit "08:00", zweite "09:00". |
| `computeArrivalTimes` Pausentag (0 WP) | AC-5 | gibt `[]` zurueck. |
| `computeArrivalTimes` Default-Startzeit | AC-5 | ohne startTime → erster WP = "08:00". |

### Unit — `frontend/src/lib/utils/waypointEditor.test.ts` (ERWEITERT)

| Test (Beschreibung) | AC | Was geprueft wird |
|---|---|---|
| `interpolateWaypoint([A,B], 0.5)` | AC-7 | lat/lon/elevation_m = Mittelpunkt, `insertAfterIndex === 0`. |
| `interpolateWaypoint([A,B], 0)` | AC-7 | Ergebnis = exakt A, `insertAfterIndex === 0`. |
| `interpolateWaypoint([A,B], 1)` | AC-7 | Ergebnis = exakt B. |

### E2E — `frontend/e2e/issue-296-profile-editor.spec.ts` (Playwright)

| Test (Beschreibung) | AC | Was geprueft wird |
|---|---|---|
| keine wp-lat/wp-lon/wp-ele | AC-1 | Koordinaten-Inputs entfernt (`toHaveCount(0)`). |
| profile-editor mit Pins | AC-2 | SVG sichtbar, ≥1 Pin pro Wegpunkt. |
| suggested zeigt Bestaetigen + Verwerfen | AC-3 | `waypoint-confirm-{i}` + `waypoint-reject-{i}` sichtbar. |
| manuell zeigt Umbenennen + Loeschen | AC-3 | `waypoint-rename-{i}` + `waypoint-delete-{i}`, kein Confirm. |
| Profil-Klick fuegt suggested WP ein | AC-4 | +1 Karte, neuer WP ist suggested. |
| Ankunftszeit wp-arrival-{i} sichtbar | AC-5 | Format "HH:MM" pro Wegpunkt. |
| Detail-View Etappen-Tab regressionsfrei | AC-9 | MapCanvas + ProfileEditor weiterhin sichtbar. |
| Pausentag → pause-stage-view | AC-10 | PauseStageView statt profile-editor. |

## Implementation Details

Tests folgen dem No-Mocks-Pattern des Projekts:
- Unit (Node-Runner `node:test` + `node:assert`): echte Pure-Function-Aufrufe,
  echte lat/lon (0.035973° ≈ exakt 4 km Haversine auf ~42° N).
- E2E (Playwright): echter Trip `e2e-cockpit-test`, echte PUT-Requests gegen die
  laufende API, echter Browser. KEINE `Mock()`, `patch()`, `MagicMock`.

In RED-Phase schlagen alle Tests fehl, weil `naismith.ts`
(`naismithHours`/`computeArrivalTimes`) und `interpolateWaypoint` in
`waypointEditor.ts` sowie `EditStagesPanelNew` + die optionalen
ProfileEditor/WaypointCard-Props noch nicht existieren.

## Expected Behavior

- **Input:** Echte lat/lon (0.035973° ≈ 4 km), Stage/Waypoint-Objekte, echter
  Trip via API-Seed.
- **Output:** Assertions ueber Naismith-Stunden, Ankunftszeiten ("HH:MM"),
  interpolierte Koordinaten, sichtbare/abwesende data-testids.
- **Side effects:** E2E-PUTs auf `e2e-cockpit-test` (Test-Trip), keine Mutation
  von Produktivdaten.

## Acceptance Criteria

- **AC-T1:** Given die Test-Dateien existieren und Implementierung fehlt /
  When `node --experimental-strip-types --test src/lib/utils/naismith.test.ts
  src/lib/utils/waypointEditor.test.ts` laeuft /
  Then schlagen die neuen Tests fehl (RED): naismith-Import-Fehler +
  `interpolateWaypoint` undefined.

- **AC-T2:** Given GREEN-Phase abgeschlossen /
  When dieselben Unit-Suiten plus die E2E-Suite (post-push gegen Staging)
  ausgefuehrt werden /
  Then sind alle Tests gruen, keine Mocks; die bestehenden
  `waypointEditor`-Tests (stripSuggested/buildMapPositions/boundingBox) bleiben
  unveraendert gruen.

## Known Limitations

- E2E laeuft post-push gegen Staging (CLAUDE.md „E2E-Verifikation"), nicht in der
  lokalen RED-Phase — der Server-/Browser-Lauf ist Teil von Phase 6.
- Interpolierte Wegpunkt-Koordinaten sind lineare Schaetzungen zwischen Nachbarn
  (keine Karte) — siehe Parent-Spec „Known Limitations".

## Changelog

- 2026-05-23: Initial — Test-Manifest fuer Issue #296-FE (Profil-Editor +
  Naismith-Ankunftszeiten). 7 Unit-Tests (naismith), 3 Unit-Tests
  (interpolateWaypoint), 8 E2E-Tests (AC-1..AC-5, AC-9, AC-10).
