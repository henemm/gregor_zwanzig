---
entity_id: epic_136_step3_waypoints
type: module
created: 2026-05-09
updated: 2026-05-09
status: stub
version: "0.1"
parent_spec: epic_136_trip_wizard
issue: 163
tags: [sveltekit, frontend, wizard, stub, epic-136, ai-waypoints]
---

# Epic 136 — Sub-Spec #163: Step 3 KI-Waypoints bestaetigen (Stub)

## Approval

- [ ] Approved

## Status

**Stub** — wird vor Beginn von Issue #163 ausgefuellt.

## Zweck

UI-Detailspezifikation Step 3 — Etappen-Liste links, Waypoint-Confirm-UI rechts (Hoehenprofil
+ Waypoint-Liste, Bestaetigen/Verwerfen-Buttons, gestrichelte KI-Pins). Nutzt vorhandene
Backend-Pipeline `POST /api/gpx/parse` (`src/core/elevation_analysis.py` +
`src/core/hybrid_segmentation.py`). Wegpunkte mit `suggested === true` werden orange-gestrichelt
gerendert; nach User-Bestaetigung wird das Flag entfernt, beim Verwerfen wird der Wegpunkt aus
`stage.waypoints[]` entfernt.

## Quelle

- **Komponente:** `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte` (NEU)
- **Hilfskomponenten:** noch zu definieren (WaypointRow, ProfileChart)

## Verweis auf Master-Spec

Diese Sub-Spec referenziert `docs/specs/modules/epic_136_trip_wizard.md` (Epic-Master-Spec).
`Waypoint.suggested` (transient) ist dort definiert; das Flag wird in `toTripPayload()` vor
dem POST gestrippt.

## Issue

[#163 — Step 3: KI-Waypoints bestaetigen](https://github.com/henemm/gregor_zwanzig/issues/163)

## Changelog

- 2026-05-09: Stub angelegt (Phase 3 der Epic-Master-Spec).
