---
entity_id: bug717_waypointspanel_spread_fix
type: bugfix
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [frontend, trip, stages, data-integrity, partial-update, waypointspanel]
---

# Bug #717 — WaypointsPanel: { ...trip, stages } Anti-Pattern entfernen

## Approval

- [ ] Approved

## Problem

`WaypointsPanel.svelte` sendet beim `handleSave()` den kompletten `{ ...trip }`-Spread
als Request-Body an `PUT /api/trips/{id}`. Damit schleppen alle beim Seiten-Load
geladenen Felder (`report_config`, `name`, alle Nicht-Waypoint-Daten) in den PUT-Body —
auch wenn sie seit dem Load verändert wurden. Sobald die Komponente gemountet wird,
kann ein Speichern im WaypointsPanel daher Änderungen aus anderen Tabs (z. B. einem
zwischenzeitlich gespeicherten Briefing-Zeitplan) still zurückdrehen.
Die Komponente ist aktuell über keine aktive Route erreichbar (nur als Export in
`trip-detail/index.ts`), weshalb noch kein aktiver Datenverlust aufgetreten ist —
das Anti-Pattern wartet jedoch auf den nächsten Mount und muss vor einem solchen
entfernt werden.

## Source

- **File:** `frontend/src/lib/components/trip-detail/WaypointsPanel.svelte`
- **Identifier:** `handleSave` (Zeile 42)

## Estimated Scope

- **LoC:** ~1 geänderte Zeile
- **Files:** 1
- **Effort:** low

## Root Cause

`handleSave` baut den Request-Body mit `{ ...trip, stages: localStages }`:

```typescript
// WaypointsPanel.svelte:42 — FALSCH
await api.put(`/api/trips/${trip.id}`, { ...trip, stages: localStages });
```

`trip` ist der Snapshot beim Seiten-Load. Wenn in der gleichen Sitzung ein anderer
Tab (z. B. BriefingScheduleTab) seinen Stand gespeichert hat, kennt `WaypointsPanel`
das neue `report_config` nicht. Der Spread sendet das veraltete `report_config` mit —
das Go-Backend (`UpdateTripHandler`) behandelt den gesendeten Wert als neue Wahrheit
und überschreibt die aktuell gespeicherte Version.

Dasselbe Muster wurde bereits in `TripHeader.svelte` und `BriefingScheduleTab.svelte`
behoben (Issue #707). `WaypointsPanel` ist der dritte Fundort.

## Fix

Nur `stages: localStages` senden — kein `trip`-Spread:

```typescript
// WaypointsPanel.svelte:42 — KORREKT
await api.put(`/api/trips/${trip.id}`, { stages: localStages });
```

Der Go-`UpdateTripHandler` wendet ein Pointer-basiertes Merge-Schema an: nur gesendete
Felder werden übernommen, alle anderen Felder bleiben unverändert. Der minimale Body
ist daher ausreichend und korrekt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WaypointsPanel.svelte` | Frontend-Komponente | Enthält `handleSave` — zu ändernder PUT-Aufruf |
| `internal/handler/trip.go` | Go-API | `UpdateTripHandler`: Pointer-basiertes Merge-Schema — kein Change nötig, Backend ist korrekt |
| `api.put` | Frontend-Utility | HTTP-Client (`$lib/api.js`) — sendet JSON-Body an Go-API |
| `bug707_trip_datum_overwrite.md` | Spec | Präzedenz: identischer Fix für TripHeader + BriefingScheduleTab |

## Expected Behavior

- **Input:** PUT `/api/trips/{id}` mit Body `{ stages: localStages }` — ausschließlich die geänderten Waypoint-Daten
- **Output:** Go-Backend merged nur `stages`; alle anderen Trip-Felder (`report_config`, `name`, `display_config` etc.) bleiben unverändert
- **Side effects:** keine — der lokale UI-State-Update (`onTripUpdate`) ist von diesem Change nicht betroffen

## Acceptance Criteria

**AC-1:** Given `WaypointsPanel.svelte` enthält `handleSave` / When der Quellcode auf das Anti-Pattern `{ ...trip, stages:` geprüft wird / Then ist dieses Muster nicht vorhanden — der stale Spread wurde entfernt.
- Test: `# doc-compliance-test` (Präzedenz: `frontend/src/lib/issue_523_suggested_flag_cleanup.test.ts`) — prüft via Dateiinhalt-Analyse, dass `{ ...trip, stages:` nicht in `WaypointsPanel.svelte` vorkommt. Rot vor Fix (Muster vorhanden), grün nach Fix (Muster entfernt). Gilt als Source-Code-Compliance-Guard für Anti-Pattern-Regression.

**AC-2:** Given `WaypointsPanel.svelte` enthält `handleSave` / When der Quellcode auf den korrekten minimalen PUT-Body geprüft wird / Then enthält `handleSave` ausschließlich `{ stages: localStages }` ohne vorausgehenden `...trip`-Spread.
- Test: `# doc-compliance-test` (analog AC-1) — komplementäre Assertion: das korrekte Muster ist vorhanden. Stellt sicher dass `handleSave` nicht leer bleibt oder einen anderen Body nutzt.

**AC-3:** Given ein Trip mit gespeichertem `report_config` / When via HTTP `PUT /api/trips/{id}` nur `{ "stages": [...] }` ohne `report_config` gesendet wird / Then enthält der Trip-Zustand nach dem PUT denselben `report_config`-Wert wie zuvor — das Backend-Partial-Update überschreibt keine nicht-gesendeten Felder.
- Test: Echter Backend-HTTP-Integrationstest gegen Staging-API: Trip anlegen mit `report_config`, PATCH nur Stages, Trip abrufen und `report_config` vergleichen. Belegt das Partial-Update-Versprechen des Go-Backends, auf das der minimale Frontend-Body aufbaut.

## Known Limitations

- Die Komponente ist zum Zeitpunkt des Fixes nicht über eine aktive Route erreichbar. Ein Playwright-E2E-Test (analog AC-1–AC-4 aus #707) ist daher nicht möglich; AC-1/AC-2 liefern den Source-Code-Compliance-Nachweis, AC-3 liefert den Backend-Verhaltensnachweis.
- Sollte `WaypointsPanel` künftig gemountet werden, ist ein Playwright-E2E-Test nachzuliefern (Issue-Kommentar in #717 hinterlassen).

## Changelog

- 2026-06-10: Spec erstellt — Anti-Pattern `{ ...trip, stages: localStages }` in `WaypointsPanel.svelte:42` identifiziert; Fix und doc-compliance-Teststrategie spezifiziert (Präzedenz: Bug #707).
