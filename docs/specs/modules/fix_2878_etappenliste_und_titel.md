---
entity_id: fix_2878_etappenliste_und_titel
type: bugfix
created: 2026-11-09
updated: 2026-11-09
status: draft
version: "1.0"
workflow: fix-2878-etappenliste-titel
tags: [frontend-only, trip-hub, subscription-header, paritaet, design-audit-2026-11-09]
---

# Trip-Hub: Etappenliste der Übersicht lesbar, Titel mobil ungekürzt (Issue #2878)

## Approval

- [ ] Approved

## Purpose

Zwei Darstellungsfehler aus dem Design-Audit vom 9.11.2026 (Stand `origin/main` 08e0d9f1a):

- **D1 (Computer):** In der Trip-Übersicht fehlt in der Etappenliste der Etappenname ganz, und das Datum bricht Zeichen für Zeichen senkrecht um („2026-/11-/09/·/2/WP“). Die Zeile hat ein starres Raster `60px minmax(0,1fr) 280px 100px` mit 16 px Lücke und 18 px Rand. Die festen Teile brauchen zusammen rund 524 px. Die Spalte, in der die Liste steht, ist am Computer aber nur rund 470 px breit; für den Namen bleibt nichts.
- **D2 (Handy):** Der Trip-Titel wird auf 390 px Breite auf 124 px zusammengedrückt und abgeschnitten („GR20N · GR…“), obwohl der Name nur 15 Zeichen hat. Ursache: Der Titel steht mit `truncate` (eine Zeile, Auslassungspunkte) in derselben Zeile wie Stift, Status-Schild und „in 12 Tagen“. Beim Vergleich bleibt mehr Platz, weil dort Kürzel und Tageszahl fehlen; das verletzt zusätzlich die Gleichheit von Trip und Ortsvergleich.

**Entscheidung (Tech Lead):**
- D1: Die Etappenzeile richtet sich nach der **Breite ihres Behälters**, nicht nach der Fensterbreite (CSS-Container-Query). Ist der Behälter schmaler als 640 px, entfällt die Zusammenfassungs-Spalte (wie heute schon unter 900 px Fensterbreite), und Name und Meta-Zeile bekommen die ganze Restbreite. Die Meta-Zeile bricht nur zwischen ihren Teilen um (Datum, km, Höhenmeter, Wegpunkte), nie innerhalb eines Teils.
- D2: Der Titel im gemeinsamen Baustein `SubscriptionHeader` darf auf dem Handy umbrechen (wie am Computer schon heute) statt abgeschnitten zu werden. Die Titelzeile wird umbruchfähig: reicht der Platz nicht, rutschen Status-Schild und Tageszahl unter den Titel. Der Stift bleibt direkt am Titel. Gilt für Trip und Vergleich gleich (ein Baustein).

## Source

- **Geändert:**
  - `frontend/src/lib/components/trip-detail/TripStageRow.svelte`: Raster mit Container-Query statt nur Viewport-Media-Query; Meta-Zeile als umbruchfähige Reihe unteilbarer Teile.
  - `frontend/src/lib/components/trip-detail/HubOverview.svelte`: linke Spalte bekommt `container-type: inline-size` (Bezug für die Container-Query).
  - `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte`: Titelzeile `flex-wrap`, `h1` ohne `truncate`, mit `overflow-wrap: anywhere` gegen sehr lange Wörter.
- **Neu:** `frontend/e2e/trip-hub-etappenliste-titel.spec.ts` (Playwright, isolierter Stack, Positivliste `.github/ci_e2e_specs.txt` und Ratschen in `.github/workflows/ci.yml` nachziehen).

> **Schicht:** nur Frontend (SvelteKit). Kein Go, kein Python, keine Daten.
> **Trip/Ortsvergleich-Teilung:** D2 ändert den geteilten Baustein, beide Seiten profitieren gleich. D1 betrifft die Trip-Übersicht; der Vergleich hat dort keine Ortsliste (die Orte-Zeile `CompareLocationRow` ist bereits ein flexibles Layout). Keine neue Komponente.
> **Mandantentrennung / Kanäle:** nicht betroffen.

## Estimated Scope

- **LoC:** ca. +40 / -15 Code, ca. +200 Test
- **Files:** 3 Komponenten, 1 neue E2E-Datei, CI-Positivliste und Ratsche
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `trip-detail/TripStageRow.svelte` | Komponente | Etappenzeile der Übersicht |
| `trip-detail/HubOverview.svelte` | Komponente | Zweispalten-Raster der Übersicht (`1fr 380px`) |
| `shared/subscription-header/SubscriptionHeader.svelte` | geteilter Baustein | Titelzeile von Trip und Vergleich |
| `frontend/e2e/ci-stack.sh` | Prüfstand | isolierter Offline-Stack |

## Implementation Details

1. `HubOverview.svelte`: Das Kind der linken Spalte, das die Etappenliste enthält, bekommt `container-type: inline-size; container-name: etappenliste`.
2. `TripStageRow.svelte`:
   - Grundraster bleibt `60px minmax(0,1fr) 280px 100px` für breite Behälter.
   - `@container etappenliste (max-width: 639px)`: Raster `40px minmax(0,1fr) auto`, Zusammenfassung ausgeblendet (gleiche Regel wie heute unter 900 px Fensterbreite, die Media-Query bleibt als Rückfall).
   - Meta-Zeile: jedes Teil (Datum, km, ↑, ↓, Höhe, WP) als eigenes Element mit `white-space: nowrap`, der Container `display:flex; flex-wrap:wrap; column-gap`. Der Trenner „·“ hängt am Teil, nicht frei.
3. `SubscriptionHeader.svelte`: Titelzeile `flex-wrap: wrap`; `h1` ohne `truncate`, `min-width: 0`, `overflow-wrap: anywhere`; der Stift-Knopf steht im selben Element-Paar wie der Titel, damit er beim Umbruch nicht allein in eine neue Zeile springt (Titel und Stift in einer inneren Gruppe `flex: 1 1 auto; min-width: 0`).
4. Pflicht-Mutationen für die Gegenprobe: (a) `truncate` wieder an den `h1`, (b) Container-Query entfernen, (c) `white-space: nowrap` der Meta-Teile entfernen. Jede muss mindestens einen AC rot machen.

## Expected Behavior

- **Input:** Trip-Hub (Übersicht) am Computer 1280 × 900 und am Handy 390 × 844; Vergleichs-Hub am Handy.
- **Output:** Etappenname und Datum lesbar; Titel vollständig sichtbar, ggf. zweizeilig.
- **Side effects:** Auf dem Handy kann die Titelzeile eine Zeile höher werden, wenn Status und Tageszahl darunter rutschen. Gewollt.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit drei Etappen (Namen mit 12 bis 30 Zeichen) im Trip-Hub, Reiter Übersicht, bei 1280 × 900 Pixel / When die Etappenliste betrachtet wird / Then ist in jeder Etappenzeile der Name sichtbar (Breite des Namens-Elements größer als 80 Pixel, Text nicht leer) und das Datum steht in einer einzigen Zeile (Höhe des Datums-Elements höchstens 1,5 × seine Zeilenhöhe).
  - Test: Playwright `trip-hub-etappenliste-titel.spec.ts` EL-1, `boundingBox()` von `[data-testid^="trip-stage-row-"] .stage-name` und des Datums-Teils; DE und EN.

- **AC-2:** Given derselbe Trip bei 1280 × 900 und bei 1440 × 900 Pixel / When die Etappenzeile vermessen wird / Then läuft keine Zeile waagerecht über ihren Behälter hinaus (`scrollWidth` der Zeile ≤ `clientWidth`), und bei einem Behälter ab 640 Pixel Breite ist die Zusammenfassung weiterhin sichtbar.
  - Test: Playwright EL-2; Behälterbreite per `boundingBox()` gemessen, Sichtbarkeit der Zusammenfassung je nach gemessener Breite geprüft.

- **AC-3:** Given ein Trip mit dem 15 Zeichen langen Namen „Korsika Nordteil“ / When der Trip-Hub bei 390 × 844 Pixel geöffnet wird / Then ist der Titel vollständig sichtbar: kein Auslassungszeichen, `scrollWidth` des Titels ≤ `clientWidth`, und der sichtbare Text enthält den ganzen Namen; auf Deutsch und Englisch.
  - Test: Playwright EL-3, `getComputedStyle(h1).textOverflow` ≠ `ellipsis` bzw. keine Überbreite, `innerText` enthält den Namen.

- **AC-4:** Given ein Trip mit einem 60 Zeichen langen Namen / When der Trip-Hub bei 390 × 844 Pixel geöffnet wird / Then bricht der Titel auf mehrere Zeilen um, der ganze Name ist lesbar, die Seite läuft nicht waagerecht über (`document.documentElement.scrollWidth` ≤ 390), und der Stift-Knopf steht direkt neben oder unter dem Titelende (nicht abgeschnitten, Tippfläche ≥ 44 × 44 Pixel).
  - Test: Playwright EL-4.

- **AC-5:** Given ein Trip und ein Ortsvergleich mit gleich langem Namen (15 Zeichen) / When beide Hubs bei 390 × 844 Pixel geöffnet werden / Then sind bei beiden die Titel vollständig sichtbar, und die Titel-Elemente tragen dieselben Umbruch-Stile (`white-space`, `overflow-wrap`, `text-overflow`).
  - Test: Playwright EL-5, Vergleich Trip gegen Vergleich per `getComputedStyle`.

## Test Plan

- Playwright EL-1 bis EL-5 am isolierten Stack (`frontend/e2e/ci-stack.sh`), DE und EN.
- RED-Nachweis: EL-1 und EL-3 schlagen auf `origin/main` fehl (Name 0 Pixel breit, Titel abgeschnitten).

## Definition of Done

- AC-1 bis AC-5 grün, Adversary VERIFIED mit den drei Pflicht-Mutationen gefangen.
- PR mit allen 6 CI-Checks grün gemergt.
- Staging-Prüfung und Prod-Deploy über `/e2e-verify` und `/70-deploy` (Server-Sitzung).

## Known Limitations

- Der Vergleich hat in der Übersicht keine Ortsliste; ein Gleichstand für D1 ist daher nicht messbar.
- Die Übersicht wird mit #2794 nicht umgebaut; die Lösung bleibt danach gültig.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine. Reiner Darstellungsfehler; wendet ADR-0097 (geteilter Baustein) an.

## Changelog

- 2026-11-09: Initial spec (Issue #2878).
