---
entity_id: issue_675_etappen_startzeiten
type: module
created: 2026-06-09
updated: 2026-06-09
status: draft
version: "1.0"
tags: [frontend, trip-editor, naismith, etappen]
---

# Startzeiten je Etappe editieren (Issue #675)

## Approval

- [x] Approved

## Purpose

Ermöglicht dem Nutzer, im Etappen-Editor pro Etappe eine eigene Startzeit (`"HH:MM"`) zu setzen — z.B. am Anreisetag erst 15 Uhr statt 08:00. Die Naismith-Ankunftszeiten der Wegpunkte rechnen live mit der gewählten Startzeit und werden persistiert. Reines Frontend-Feature: Datenmodell, Naismith-Engine, Persistenz und PUT-Merge unterstützen `start_time` bereits.

## Source

- **File:** `frontend/src/lib/components/edit/StageTimeField.svelte` (NEU)
- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` (Handler + Rendering Desktop & Mobile)
- **Identifier:** Komponente `StageTimeField`, Handler `handleStartTimeChange`

## Estimated Scope

- **LoC:** ~120 (neue Komponente ~70, Editor-Integration ~50)
- **Files:** 2 (1 neu, 1 geändert) + Tests
- **Effort:** low–medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Stage.start_time` (`frontend/src/lib/types.ts:52`) | Datenfeld | Optionales `"HH:MM"`-Feld, bereits vorhanden |
| `computeArrivalTimes` (`frontend/src/lib/utils/naismith.ts`) | Funktion | Live-Berechnung der Ankunftszeiten aus `start_time`, Default `08:00` |
| `PUT /api/trips/{id}` (`internal/handler/trip.go`) | API | RMW-Merge persistiert `start_time` + ruft `ComputeStageArrivals` |
| `StageDateField.svelte` | Vorbild | Strukturvorbild für dünne Feld-Komponente |

## Implementation Details

```
StageTimeField.svelte (analog StageDateField):
  Props: value?: string (HH:MM | undefined), onchange?: (v: string) => void
  - <input type="time"> innerhalb gestyltem .box-Wrapper, Label "STARTZEIT"
  - Anzeige-Wert (displayValue): value ?? "08:00"  → 08:00 sichtbar wenn unset
  - handleChange(e): emit onchange(e.target.value); leeren-Zustand ("") → onchange("")

EditStagesPanelNew.svelte:
  - handleStartTimeChange(stageId, newTime):
      idx = stages.findIndex(...); if idx<0 return
      // alt-treu: nur die betroffene Etappe anfassen, immutabel
      // leerer Wert → start_time entfernen (zurück auf Default), sonst setzen
      stages = stages.map((s,i) =>
        i===idx
          ? (newTime === '' ? { ...s, start_time: undefined } : { ...s, start_time: newTime })
          : s)
  - Render StageTimeField neben StageDateField im Etappen-Header (Desktop-Block)
  - Render StageTimeField ebenfalls im Mobile-Markup (@media ≤899px)
  - Nur für Wander-Etappen, NICHT für Pausentage (activeIsPause === false)
  - `arrivals` ($derived aus activeStage.start_time) rechnet automatisch neu

Default-Treue (Tech-Lead-Entscheidung):
  - 08:00 wird nur ANGEZEIGT (displayValue), NICHT in stages geschrieben,
    solange der Nutzer nichts ändert. Öffnen des Editors mutiert Bestands-Trips nicht.
  - Erst aktive Änderung setzt start_time; geleertes Feld setzt start_time zurück.
```

## Expected Behavior

- **Input:** Nutzer wählt im Startzeit-Feld einer Etappe eine Uhrzeit (z.B. 15:00).
- **Output:** Wegpunkt-Ankunftszeiten der Etappe rechnen ab 15:00 (live, ohne Speichern sichtbar); nach „Speichern" persistiert `start_time:"15:00"` im Trip-JSON, Go-`ComputeStageArrivals` rechnet serverseitig identisch nach.
- **Side effects:** Keine kaskadierende Wirkung auf andere Etappen (Naismith rechnet pro Etappe). Pausentage haben kein Feld. Bestands-Trips ohne Interaktion bleiben byte-gleich.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit ≥1 Wander-Etappe im Etappen-Editor / When der Nutzer die Seite öffnet / Then erscheint pro Wander-Etappe ein Startzeit-Feld, das sichtbar 08:00 anzeigt, solange keine eigene Startzeit gesetzt ist.
  - Test: Playwright-E2E gegen Staging als eingeloggter Nutzer — Editor öffnen, Startzeit-Feld der aktiven Etappe sichtbar, angezeigter Wert `08:00`.

- **AC-2:** Given die aktive Etappe / When der Nutzer die Startzeit auf 15:00 setzt / Then aktualisieren sich die angezeigten Wegpunkt-Ankunftszeiten dieser Etappe sofort so, dass der erste Wegpunkt 15:00 zeigt (ohne Speichern).
  - Test: Playwright — Startzeit 15:00 eingeben, Ankunftszeit erster Wegpunkt liest 15:00, ein späterer Wegpunkt > 15:00.

- **AC-3:** Given eine auf 15:00 gesetzte Startzeit / When der Nutzer speichert und die Seite neu lädt / Then ist 15:00 weiterhin gesetzt und die Ankunftszeiten bleiben ab 15:00 (Persistenz-Roundtrip).
  - Test: Playwright/HTTP — nach Save GET `/api/trips/{id}` liefert `stages[i].start_time == "15:00"`; nach Reload zeigt Feld 15:00.

- **AC-4:** Given ein Bestands-Trip ohne `start_time` an irgendeiner Etappe / When der Nutzer den Editor nur öffnet und ohne Änderung speichert / Then enthält keine Etappe ein neu geschriebenes `start_time` (alt-treu, kein stilles Override).
  - Test: HTTP — Trip-JSON vor/nach Open+Save vergleichen: kein `start_time` hinzugefügt; Ankunftszeiten weiterhin ab 08:00.

- **AC-5:** Given eine gesetzte Startzeit / When der Nutzer das Startzeit-Feld leert / Then fällt die Etappe auf den 08:00-Default zurück (Feld zeigt wieder 08:00, Ankunftszeiten ab 08:00, `start_time` nicht mehr gesetzt).
  - Test: Playwright — Startzeit setzen, dann leeren; erster Wegpunkt liest 08:00; nach Save kein `start_time` im JSON.

- **AC-6:** Given die mobile Editor-Ansicht (Viewport ≤899px) / When der Nutzer eine Wander-Etappe öffnet / Then ist das Startzeit-Feld auch dort sichtbar und bedienbar (Desktop-Parität).
  - Test: Playwright @375px — Startzeit-Feld im sichtbaren Mobile-Markup vorhanden und editierbar (Selektor auf sichtbares DOM gescopt).

- **AC-7:** Given ein Pausentag (Etappe ohne Wegpunkte) / When der Nutzer ihn im Editor öffnet / Then wird KEIN Startzeit-Feld angezeigt.
  - Test: Playwright — Pausentag aktivieren, Startzeit-Feld nicht im DOM.

## Known Limitations

- Startzeit wirkt strikt pro Etappe; es gibt keine „alle Folge-Etappen mitverschieben"-Kaskade wie beim Datum (#498) — bewusst, da Sondertage (Anreise, früher Aufstieg) gerade nicht kaskadieren sollen.
- Sekundengenauigkeit nicht unterstützt (Format `"HH:MM"`, identisch zur Naismith-Konvention).

## Changelog

- 2026-06-09: Initial spec created (Issue #675)
