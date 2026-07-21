---
entity_id: issue_699_doppelter_pfad_header
type: module
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [frontend, bugfix, trip-detail, header]
---

# Issue #699 — Doppelter Pfad im Trip-Header

## Approval

- [ ] Approved

## Purpose

Behebt die doppelte Pfad-Anzeige im Header der Trip-Detailseite. Aktuell werden zwei
Pfad-Zeilen direkt untereinander gerendert (obere Breadcrumb-Bar + zweite „MEINE TRIPS ›"-Zeile).
Die Anzeige wird an die Claude-Design-Vorgabe angeglichen: **eine** Breadcrumb oben, darunter
eine Eyebrow mit Metadaten im Format `REGION · DATUMSBEREICH`.

## Source

- **File:** `frontend/src/lib/components/trip-detail/TripHeader.svelte`
- **Identifier:** Header-Markup (Breadcrumb-`<nav>` + `.trip-eyebrow-region`)
- **Begleitend:** `frontend/src/routes/trips/issue_581_trip_detail_jsx.test.ts` (AC-2 Format-Check nachziehen)

## Estimated Scope

- **LoC:** ~15
- **Files:** 2 (Komponente + bestehender Format-Test)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/routes/trips/[id]/+page.svelte` | bestehend | rendert die korrekte obere Breadcrumb-Bar („Trips / <shortcode>") — bleibt unverändert |
| `formatDateRange` (`$lib/utils/tripHero`) | bestehend | liefert den Datumsbereich für die Eyebrow |

## Implementation Details

**Claude-Design-Vorgabe (Issue-Screenshot 2):**
```
Trips / KHW 403                          ← obere Breadcrumb (+page.svelte, bleibt)
KARNISCHE ALPEN · 03.06. – 14.06.2026    ← Eyebrow: REGION · DATUMSBEREICH
Karnischer Höhenweg 403                  ← H1
```

**Ist-Zustand (TripHeader.svelte):**
```
Trips / Hermannsweg mit Astrid 2026      ← obere Breadcrumb (+page.svelte) — korrekt
MEINE TRIPS › HERMANNSWEG MIT ASTRID 2026 ← DUPLIKAT-Breadcrumb (zu entfernen)
TRIP · TEUTOBURGER WALD                   ← Eyebrow im falschen Format
Hermannsweg mit Astrid 2026              ← H1
```

**Änderung in `TripHeader.svelte`:**
1. Die doppelte Breadcrumb-`<nav data-testid="trip-detail-breadcrumb">` (mit `MEINE TRIPS › …`) **entfernen**.
2. Die `.trip-eyebrow-region` von `Trip · {region}` auf das Design-Format umstellen:
   `{REGION} · {dateRange}` (Region in Großbuchstaben — übernimmt das bestehende
   `text-transform: uppercase`; Datumsbereich aus `formatDateRange(trip)`).
   - Fällt eine Komponente weg (z.B. keine `region`), bleibt die jeweils vorhandene
     Information ohne führendes/abschließendes `·` (kein leeres Trennzeichen).
3. Den bestehenden Format-Test AC-2 (`issue_581_trip_detail_jsx.test.ts`) an das neue
   Eyebrow-Format anpassen.

## Expected Behavior

- **Input:** Trip-Objekt mit `name`, `shortcode`, `region` und Etappen-Daten.
- **Output:** Header mit genau **einer** Pfad-Zeile oben, darunter Eyebrow `REGION · DATUM`, dann H1.
- **Side effects:** keine — reine Darstellung, keine Persistenz, keine API-Calls.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet die Trip-Detailseite eines bestehenden Trips / When die
  Seite gerendert ist / Then erscheint im Header genau **eine** Breadcrumb-/Pfad-Zeile
  („Trips / <Name|Shortcode>"); die zweite Zeile „MEINE TRIPS › …" ist **nicht mehr** vorhanden.
  - Test: Playwright-E2E gegen Staging als eingeloggter Nutzer — Detailseite öffnen, prüfen dass
    der Text „MEINE TRIPS ›" nicht im Header vorkommt und die obere Breadcrumb-Bar weiterhin sichtbar ist.

- **AC-2:** Given ein Trip mit Region und Etappen-Datumsbereich / When die Detailseite gerendert
  ist / Then zeigt die Eyebrow unter der Breadcrumb das Format `REGION · DATUMSBEREICH`
  (z.B. „TEUTOBURGER WALD · 03.06. – 14.06.2026") statt „Trip · Region".
  - Test: Playwright-E2E gegen Staging — Eyebrow-Text enthält die Region (uppercase) und den
    Datumsbereich, getrennt durch „·"; der Präfix „Trip ·" kommt nicht mehr vor.

- **AC-3:** Given ein Trip ohne hinterlegte Region / When die Detailseite gerendert ist / Then
  zeigt die Eyebrow nur den Datumsbereich (bzw. nur die Region, falls kein Datum) ohne
  führendes oder verwaistes „·"-Trennzeichen.
  - Test: Playwright-E2E gegen Staging mit einem Trip ohne Region — Eyebrow beginnt/endet nicht
    mit einem alleinstehenden „·".

## Changelog

- 2026-06-10: Initial-Spec für Issue #699 (Bugfix doppelter Pfad im Trip-Header).
