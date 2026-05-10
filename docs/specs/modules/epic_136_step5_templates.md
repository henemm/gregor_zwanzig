---
entity_id: epic_136_step5_templates
type: module
created: 2026-05-09
updated: 2026-05-09
status: stub
version: "0.1"
parent_spec: epic_136_trip_wizard
issue: 165
tags: [sveltekit, frontend, wizard, stub, epic-136, templates]
---

# Epic 136 — Sub-Spec #165: Trip-Vorlagen (Stub)

## Approval

- [ ] Approved

## Status

**Stub** — wird vor Beginn von Issue #165 ausgefuellt.

## Zweck

UI-Detailspezifikation Trip-Vorlagen — rechte Spalte in Step 2: drei Schnellauswahl-Vorlagen
GR20, Karnischer Hoehenweg, Stubaier Hoehenweg. Klick auf Vorlage befuellt `state.stages` mit
vorbereiteten GPX-Daten und uebernimmt sinnvolle Defaults fuer `activity` und `shortcode`.

## Quelle

- **Komponente:** `frontend/src/lib/components/trip-wizard/templates/TemplatePicker.svelte` (NEU)
- **Daten:** vorhandene KHW-GPX-Files in `data/users/default/gpx/KHW_*` und Stubai-JSONs in `examples/stubai_*.json`. GR20-Daten muessen extern beschafft werden (siehe Master-Spec §Not In Scope) — Sub-Spec entscheidet, ob #165 ohne GR20 auskommt oder Daten-Beschaffung Vorbedingung ist.

## Verweis auf Master-Spec

Diese Sub-Spec referenziert `docs/specs/modules/epic_136_trip_wizard.md` (Epic-Master-Spec).
WizardState-API zum Vorbefuellen der Etappen ist dort definiert.

## Issue

[#165 — Trip-Vorlagen](https://github.com/henemm/gregor_zwanzig/issues/165)

## Changelog

- 2026-05-09: Stub angelegt (Phase 3 der Epic-Master-Spec).
