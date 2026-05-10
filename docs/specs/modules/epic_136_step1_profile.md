---
entity_id: epic_136_step1_profile
type: module
created: 2026-05-09
updated: 2026-05-09
status: stub
version: "0.1"
parent_spec: epic_136_trip_wizard
issue: 161
tags: [sveltekit, frontend, wizard, stub, epic-136]
---

# Epic 136 — Sub-Spec #161: Step 1 Aktivitaetsprofil + Eckdaten (Stub)

## Approval

- [ ] Approved

## Status

**Stub** — wird vor Beginn von Issue #161 ausgefuellt.

## Zweck

UI-Detailspezifikation Step 1 — fuenf ProfileChips (Trekking, Skitour, Hochtour, Klettersteig, MTB)
plus Eingabefelder Name, Kuerzel (`shortcode`), Zeitraum. Validierungslogik fuer Pflichtfelder
und Step-Vorwaerts-Bedingung.

## Quelle

- **Komponente:** `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` (NEU)

## Verweis auf Master-Spec

Diese Sub-Spec referenziert `docs/specs/modules/epic_136_trip_wizard.md` (Epic-Master-Spec).
`ActivityType`, `Trip.shortcode`, `Trip.activity` und `mapActivityToProfile()` sind dort definiert.

## Issue

[#161 — Step 1: Aktivitaetsprofil + Eckdaten](https://github.com/henemm/gregor_zwanzig/issues/161)

## Changelog

- 2026-05-09: Stub angelegt (Phase 3 der Epic-Master-Spec).
