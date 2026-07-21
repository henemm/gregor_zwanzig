---
entity_id: issue_183_email_preview_header
type: module
created: 2026-05-11
updated: 2026-05-11
status: draft
version: "1.0"
tags: [frontend, email-preview, svelte, epic-140]
---

# Issue #183 — Email-Preview: Header

## Approval

- [x] Approved (Lean-Modus, da reine UI-Komponente ohne Backend-Berührung)

## Purpose

Header-Komponente für Email-Preview eines Trip-Briefings: Monospace-Eyebrow (Report-Typ + Briefing-Datum), Trip-Name + Shortcode, Datum der Etappe, Stats-Grid (Distanz, Aufstieg, Abstieg, Max-Höhe, Anzahl Segmente).

Teil von Epic #140 (Output-Vorschau Email + SMS).

## Source

- **File:** `frontend/src/lib/components/email-preview/EmailPreviewHeader.svelte` (NEU)
- **File:** `frontend/src/lib/components/email-preview/headerStats.ts` (NEU, pure-function Logik)
- **File:** `frontend/src/lib/components/email-preview/__tests__/headerStats.test.ts` (NEU)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Trip`, `Stage`-Types aus `frontend/src/lib/types.ts` | bestehend | Datenmodell |
| `Eyebrow` aus `ui/eyebrow` | bestehend | Monospace-Label-Pattern |

## Implementation Details

### Pure-function-Logik (`headerStats.ts`)

```ts
export interface HeaderStats {
  distanceKm: number;
  ascentM: number;
  descentM: number;
  maxElevationM: number;
  segmentCount: number;
}

export function computeHeaderStats(stage: Stage | null | undefined): HeaderStats {
  if (!stage || !stage.waypoints || stage.waypoints.length === 0) {
    return { distanceKm: 0, ascentM: 0, descentM: 0, maxElevationM: 0, segmentCount: 0 };
  }
  // Distanz: cumulative_distance_km vom letzten Waypoint
  // Aufstieg/Abstieg: aufsummiert aus Höhendifferenzen
  // Max-Höhe: max von waypoint.elevation_m
  // Segmente: len(waypoints) - 1 (zwischen-Segmente)
}
```

### Komponente

`EmailPreviewHeader.svelte` — Props: `{ trip: Trip, stage: Stage | null, reportType: 'morning' | 'evening', reportDate: string }`. Rendert Eyebrow + h2 + Stats-Grid.

Stil: Tailwind-Klassen passend zum bestehenden Design-System. Stats-Grid: 5 Spalten (oder 2 Reihen × 3 Spalten responsive).

## Acceptance Criteria

- **AC-1:** Given Stage mit 5 Waypoints (cumulative_distance_km=12.5 am letzten) / When `computeHeaderStats(stage)` läuft / Then `distanceKm == 12.5` und `segmentCount == 4`
- **AC-2:** Given Stage mit Waypoints elevations [800, 1200, 1100, 1500, 1400] / When `computeHeaderStats(stage)` läuft / Then `ascentM == 800` (400+400) und `descentM == 200` (100+100) und `maxElevationM == 1500`
- **AC-3:** Given Stage mit waypoints=null oder leer / When `computeHeaderStats(stage)` läuft / Then alle Stats == 0 (kein Crash)
- **AC-4:** Given stage=null / When `computeHeaderStats(null)` läuft / Then alle Stats == 0
- **AC-5:** Given EmailPreviewHeader-Komponente / When sie gerendert wird mit trip.name="Zillertal", reportType="morning" / Then enthält der DOM-Output "Morgen-Briefing" und "Zillertal"
- **AC-6:** Given Komponente / When sie gerendert wird / Then enthält der Stats-Grid 5 Labels: Distanz, Aufstieg, Abstieg, Max-Höhe, Segmente

## Expected Behavior

- **Input:** Trip + Stage + reportType + reportDate (Props)
- **Output:** Svelte-Component die DOM rendert
- **Side effects:** Keine

## Known Limitations

- `EmailPreviewHeader.svelte` wird in dieser Issue nicht in eine Route eingebaut — das passiert in #189 (Vorschau-Integration). Hier nur die Komponente selbst.
- Visuelle Übereinstimmung mit dem Email-Layout (das später gerendert wird) wird in einem Folge-Issue feinabgestimmt.

## Stand 2026-05-11 — fertig

- **Fertig:** Pure-function `computeHeaderStats()` + 6 grüne Headless-Tests + Export in `index.ts` (Commit `0268d42`).
- **Fertig (AC-5, AC-6):** `EmailPreviewHeader.svelte` als Svelte-5-Runen-Komponente; verifiziert per Playwright-E2E auf Dev-Route `/email-preview-dev` (3/3 Tests grün, Screenshot in `docs/artifacts/issue-183-email-preview-header/screenshot-header.png`).
- **Dev-Route:** `frontend/src/routes/email-preview-dev/+page.svelte` — interne Vorschau-Seite mit Mock-Daten. Auf Production via `+page.server.ts` (`if (!dev) redirect(307, '/')`) geblockt + sichtbares DEV-Banner. Wird in Issue #189 (Vorschau-Integration) entfernt, sobald die Komponente in die echte Stelle eingebunden ist.
- **Auth-Bypass:** Eintrag `/email-preview-dev` in `frontend/src/hooks.server.ts` `publicPaths` — nur wirksam wenn `dev=true`, sonst greift der Production-Redirect zuerst.

## Changelog

- 2026-05-11: Initial spec — Issue #183
- 2026-05-11: AC-5 + AC-6 implementiert (Svelte-Komponente + Dev-Route); Adversary AMBIGUOUS-Findings (F001 nicht-eindeutige test-IDs, F002 Dev-Route in Prod) gefixt — eindeutige `data-testid`-Suffixe + Production-Block in `+page.server.ts` + DEV-Banner.
