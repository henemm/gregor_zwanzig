---
issue: 596
title: Breadcrumb-Inkonsistenz „MEINE TRIPS" vs „MEINE TOUREN"
status: approved
---

# Spec: Bug #596 — Breadcrumb-Inkonsistenz

## Problem

Auf `/trips/[id]/edit` zeigt der Breadcrumb „MEINE TOUREN" statt „MEINE TRIPS".
Auf `/trips/[id]` (TripHeader) ist es bereits korrekt „MEINE TRIPS".

Verstoß gegen Terminologie-Konvention: Trip (englisch) — „Touren" ist verboten.

## Betroffene Datei

`frontend/src/lib/components/edit/TripEditView.svelte:107`

## Acceptance Criteria

**AC-1:** Given ein eingeloggter Nutzer befindet sich auf der Trip-Bearbeiten-Seite (`/trips/[id]/edit`), When er den Breadcrumb-Bereich betrachtet, Then enthält `[data-testid="edit-breadcrumb"]` den Text „MEINE TRIPS" (nicht „MEINE TOUREN").

**AC-2:** Given die Codebase wird auf „MEINE TOUREN" durchsucht, When alle `.svelte`-Dateien geprüft werden, Then kommt der String „MEINE TOUREN" in keiner Svelte-Komponente mehr vor.
