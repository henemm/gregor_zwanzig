---
entity_id: fix_2110_gui_gpx_km
type: bugfix
created: 2026-08-23
updated: 2026-08-23
status: implemented
workflow: fix-2110-gui-gpx-km
---

# Fix #2110: Trip-GUI zeigt echte GPX-Distanz statt Haversine-Luftlinie

## Approval

- [ ] Approved

## Purpose

Die Trip-GUI berechnet Etappen-Distanzen aktuell ausschließlich als Haversine-Luftlinien-Summe
zwischen Wegpunkten, obwohl das Backend die real aus dem GPX-Track vermessene Distanz je
Wegpunkt (`distance_from_start_km`) bereits über die API liefert. Dieser Fix stellt alle drei
Frontend-Berechnungsstellen (Etappen-Kachel/Trip-Summe/Cockpit/E-Mail-Vorschau, Profil-Chart,
Ankunftszeiten-Vorschau) so um, dass sie die echte GPX-Distanz nutzen, wenn eine Etappe
vollständig vermessen ist, und andernfalls unverändert auf die bisherige Haversine-Berechnung
zurückfallen — ohne Anzeige-Kennzeichnung, welcher Fall gerade greift.

## Source

- **File:** `frontend/src/lib/components/email-preview/headerStats.ts`
- **Identifier:** `function computeHeaderStats`
- **File:** `frontend/src/lib/utils/fullProfile.ts`
- **Identifier:** `function buildProfilePoints`, `function computeStageBoundaries`
- **File:** `frontend/src/lib/utils/naismith.ts`
- **Identifier:** `function computeArrivalTimes`
- **File:** `frontend/src/lib/types.ts`
- **Identifier:** `interface Waypoint`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/types.ts` (`Waypoint`) | type | Neues optionales Feld `distance_from_start_km?: number` — Grundlage für alle drei Berechnungsstellen |
| `frontend/src/lib/utils/tripStats.ts` (`computeTripStats`) | module | Summiert `computeHeaderStats(stage).distanceKm` über alle Etappen — profitiert ohne Codeänderung |
| `frontend/src/routes/_home/cockpitHelpers.ts` | module | Cockpit-Dashboard nutzt `computeHeaderStats()` — profitiert ohne Codeänderung |
| `frontend/src/lib/components/email-preview/EmailPreviewHeader.svelte` + `index.ts` | module | E-Mail-Vorschau nutzt `computeHeaderStats()` — profitiert ohne Codeänderung |
| `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` | module | Rendert `computeHeaderStats(stage).distanceKm` direkt — der vom PO gemeldete Anzeigepunkt |
| Backend `distance_from_start_km` (Go/Python DTO, `docs/reference/api_contract.md` Zeile ~1022) | api | Liefert das Feld bereits optional (`omitempty`/`Optional`); `null`/fehlend heißt „nicht gemessen" |
| Issue #2109 (Datenverlust bei `distance_from_start_km`, separat in Arbeit) | upstream | Ohne #2109-Fix bleibt der konkrete PO-Fall (Etappe „03: Porzehütte → Hochweißsteinhaus") bis zum Merge dort auf Haversine — technisch korrektes Fallback-Verhalten, aber der sichtbare Nutzen für den PO tritt erst nach #2109 ein. Wird in diesem Fix NICHT angefasst. |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/types.ts` | MODIFY | `Waypoint`-Interface um `distance_from_start_km?: number` ergänzen |
| `frontend/src/lib/components/email-preview/headerStats.ts` | MODIFY | `computeHeaderStats()`: pro Etappe prüfen, ob ALLE Wegpunkte `distance_from_start_km` tragen; wenn ja, `distanceKm` aus Differenzen dieses Felds statt Haversine-Summe berechnen, sonst unverändert Haversine |
| `frontend/src/lib/utils/fullProfile.ts` | MODIFY | `buildProfilePoints()` und `computeStageBoundaries()`: dieselbe Etappen-weise Prüfung; kumulativer x-Cursor nutzt bei vollständig vermessener Etappe die echten Differenzwerte für die Segmente dieser Etappe, sonst Haversine |
| `frontend/src/lib/utils/naismith.ts` | MODIFY | `computeArrivalTimes()`: dieselbe Etappen-weise Prüfung vor der Segment-Schleife; Distanz je Segment aus `distance_from_start_km`-Differenz statt `haversineKm()`, wenn die gesamte Stage vermessen ist |
| `frontend/src/lib/components/email-preview/__tests__/headerStats.test.ts` | MODIFY | Neue Testfälle: vollständig vermessen, unvermessen (Regression), teilweise vermessen (Fallback) |
| `frontend/src/lib/utils/fullProfile.test.ts` | MODIFY | Neue Testfälle für dieselben drei Fälle, inkl. trip-übergreifendem cumKm-Verhalten |
| `frontend/src/lib/utils/naismith.test.ts` | MODIFY | Neue Testfälle für dieselben drei Fälle in `computeArrivalTimes()` |

### Estimated Changes
- Files: 7
- LoC: +140/-20

## Implementation Details

Jede der drei Berechnungsstellen bekommt dieselbe Vorprüfung pro Etappe:

```
function stageHasFullTrackDistance(wps: Waypoint[]): boolean {
  return wps.length > 0 && wps.every(
    (wp) => wp.distance_from_start_km !== undefined
         && wp.distance_from_start_km !== null
         && Number.isFinite(wp.distance_from_start_km)
  );
}
```

- **`computeHeaderStats()`:** `stageHasFullTrackDistance(wps)` einmal vor der Segment-Schleife
  prüfen. Ist die Etappe vollständig vermessen, wird `distanceKm` als
  `wps[wps.length-1].distance_from_start_km - wps[0].distance_from_start_km` berechnet
  (äquivalent zur Summe der Differenzen aufeinanderfolgender Werte, da monoton). Sonst
  unverändert die bestehende Haversine-Summierung.
- **`fullProfile.ts` (`buildProfilePoints`, `computeStageBoundaries`):** Die Prüfung erfolgt pro
  Etappe VOR dem Betreten der inneren Wegpunkt-Schleife. Der `cumKm`-Cursor läuft
  trip-übergreifend; die Owner-Etappe eines Wegpunkt-Paar-Segments ist die Etappe, in deren
  Schleifen-Iteration das zweite (jüngere) Wegpunkt der beiden liegt — das entspricht dem
  bestehenden Schleifenaufbau unverändert. Innerhalb einer als „vollständig vermessen"
  erkannten Etappe wird für jedes interne Segment die Differenz der `distance_from_start_km`-
  Werte addiert statt `haversineKm()`. Segmente, die eine Etappengrenze überschreiten (letzter
  Wegpunkt Etappe N-1 → erster Wegpunkt Etappe N), bleiben unverändert Haversine-basiert (keine
  trackbasierte Distanz über Etappengrenzen hinweg — das Backend liefert `distance_from_start_km`
  je Etappe relativ zum Etappenstart, ein Vergleich über Etappen hinweg wäre nicht sinnvoll).
- **`computeArrivalTimes()`:** Gleiche Vorprüfung vor der Segment-Schleife (`for i=1..wps.length`).
  Ist die Stage vollständig vermessen, wird `dist` je Segment aus der Differenz der
  `distance_from_start_km`-Werte von `wps[i]` und `wps[i-1]` berechnet statt `haversineKm(prev, wp)`.
  Höhen-basierte Anteile der Naismith-Formel (`ascent`/`descent`) bleiben unverändert.

Kein neuer Haversine-Code entsteht; `fullProfile.ts` behält seine eigene `haversineKm()`-Kopie
(bestehende Nicht-DRY-Situation, außerhalb dieses Fixes) und `naismith.ts` seinen bestehenden
Import aus `headerStats.ts`.

## Test Plan

### Automated Tests (TDD RED)
- [ ] Test 1 (`headerStats.test.ts`): GIVEN eine Etappe mit 3 Wegpunkten, alle mit
      `distance_from_start_km` (z.B. 0, 8.5, 17.7) WHEN `computeHeaderStats(stage)` aufgerufen
      wird THEN ist `distanceKm === 17.7`, nicht die (kleinere) Haversine-Summe der
      Koordinaten.
- [ ] Test 2 (`headerStats.test.ts`): GIVEN eine Etappe, bei der KEIN Wegpunkt
      `distance_from_start_km` trägt (heutiger Normalfall) WHEN `computeHeaderStats(stage)`
      aufgerufen wird THEN ist `distanceKm` exakt der bisherige Haversine-Wert (Regressionsschutz,
      byte-/wertgleich zum Bestandstest).
- [ ] Test 3 (`headerStats.test.ts`): GIVEN eine Etappe mit 3 Wegpunkten, bei der NUR der mittlere
      Wegpunkt `distance_from_start_km` NICHT trägt WHEN `computeHeaderStats(stage)` aufgerufen
      wird THEN fällt die GESAMTE Etappe auf Haversine zurück (kein Mischen), Ergebnis identisch
      zu Test 2 mit denselben Koordinaten.
- [ ] Test 4 (`fullProfile.test.ts`): GIVEN ein Trip mit zwei Etappen, Etappe 1 vollständig
      vermessen, Etappe 2 unvermessen WHEN `buildProfilePoints(trip)` und
      `computeStageBoundaries(trip)` aufgerufen werden THEN nutzen die x-Werte innerhalb Etappe 1
      die Track-Differenzen, die x-Werte innerhalb Etappe 2 bleiben Haversine-basiert, und der
      kumulative Cursor ist an der Etappengrenze konsistent (kein Sprung/keine Lücke).
- [ ] Test 5 (`naismith.test.ts`): GIVEN eine Stage mit 2 Wegpunkten, beide mit
      `distance_from_start_km` (Differenz z.B. 5.0 km, abweichend von der Haversine-Distanz der
      Koordinaten) WHEN `computeArrivalTimes(stage, '08:00')` aufgerufen wird THEN basiert die
      berechnete Ankunftszeit des zweiten Wegpunkts auf der Track-Distanz (5.0 km), nicht auf der
      Haversine-Distanz.
- [ ] Test 6 (`naismith.test.ts`): GIVEN eine Stage ohne `distance_from_start_km` an irgendeinem
      Wegpunkt (heutiger Normalfall) WHEN `computeArrivalTimes(stage, '08:00')` aufgerufen wird
      THEN ist das Ergebnis-Array wertgleich zum Bestandsverhalten vor diesem Fix
      (Regressionsschutz).

## Acceptance Criteria

- **AC-1:** Given eine Etappe, bei der ALLE Wegpunkte `distance_from_start_km` tragen / When
  `computeHeaderStats(stage)` aufgerufen wird / Then entspricht `distanceKm` der Differenz aus
  letztem und erstem `distance_from_start_km`-Wert der Etappe, nicht der Haversine-Summe der
  Koordinaten.
  - Test: `headerStats.test.ts` mit Fixture, deren Track-Distanz (17.7 km) sich klar von der
    Haversine-Distanz derselben Koordinaten (12.8 km) unterscheidet — Assertion auf 17.7, nicht
    auf einen String im Dateiinhalt.

- **AC-2:** Given eine Etappe, bei der KEIN Wegpunkt `distance_from_start_km` trägt / When
  `computeHeaderStats(stage)` aufgerufen wird / Then bleibt `distanceKm` exakt der bisherige
  Haversine-Wert — bestehende Trips ohne GPX-Zuordnung zeigen unverändert dieselbe Zahl wie vor
  diesem Fix.
  - Test: Bestandsfixtures aus `headerStats.test.ts` laufen unverändert grün; zusätzlicher Test
    vergleicht den Rückgabewert explizit mit dem manuell berechneten Haversine-Referenzwert.

- **AC-3:** Given eine Etappe mit mindestens einem Wegpunkt OHNE `distance_from_start_km`, aber
  mindestens einem MIT / When `computeHeaderStats(stage)` aufgerufen wird / Then fällt die
  GESAMTE Etappe auf Haversine zurück (kein segmentweises Mischen aus echten und geschätzten
  Teilstrecken innerhalb derselben Etappe).
  - Test: Fixture mit genau einem fehlenden Wert in der Mitte einer 3-Wegpunkte-Etappe;
    Assertion, dass das Ergebnis exakt dem reinen-Haversine-Fall (Test 2-Fixture mit denselben
    Koordinaten) entspricht.

- **AC-4:** Given ein Trip mit mehreren Etappen unterschiedlichen Vermessungsstands / When
  `buildProfilePoints(trip)` bzw. `computeStageBoundaries(trip)` aufgerufen werden / Then nutzt
  die x-Achsen-Skalierung des Profil-Charts pro Etappe dieselbe Etappen-weise Fallback-Regel wie
  `computeHeaderStats()` (vollständig vermessene Etappe → Track-Distanz, sonst Haversine), und der
  trip-übergreifende kumulative Distanz-Cursor bleibt an Etappengrenzen konsistent ohne Sprung
  oder Lücke.
  - Test: `fullProfile.test.ts` mit zwei Etappen unterschiedlichen Vermessungsstands; Assertion
    auf konkrete x-Werte je Punkt, nicht nur auf Monotonie.

- **AC-5:** Given eine Stage, bei der ALLE Wegpunkte `distance_from_start_km` tragen / When
  `computeArrivalTimes(stage, startTime)` aufgerufen wird / Then wird die Distanz je Segment aus
  der Differenz der `distance_from_start_km`-Werte berechnet statt aus `haversineKm()`, sodass
  sich die berechnete Ankunftszeit bei abweichender Track- vs. Haversine-Distanz entsprechend
  unterscheidet.
  - Test: `naismith.test.ts` mit Fixture, deren Track-Distanz und Haversine-Distanz für dasselbe
    Segment unterschiedliche Naismith-Minuten ergeben; Assertion auf den konkreten "HH:MM"-String.

- **AC-6:** Given eine Stage ohne vollständige `distance_from_start_km`-Abdeckung (unvermessen
  oder teilweise vermessen) / When `computeArrivalTimes(stage, startTime)` aufgerufen wird /
  Then ist das Ergebnis-Array wertgleich zum Bestandsverhalten vor diesem Fix (Haversine je
  Segment) — keine Regression für Trips ohne GPX-Zuordnung.
  - Test: Bestandsfixtures aus `naismith.test.ts`/`naismith_674.test.ts` laufen unverändert grün.

- **AC-7:** Given ein Fix in `computeHeaderStats()` gemäß AC-1/AC-2/AC-3 / When
  `computeTripStats()` (Trip-Summe), `cockpitHelpers.ts` (Cockpit-Dashboard) oder die
  E-Mail-Vorschau (`EmailPreviewHeader.svelte`/`index.ts`) aufgerufen werden / Then zeigen sie die
  korrigierte Distanz automatisch, ohne dass diese drei Dateien selbst geändert werden — sie
  rufen ausschließlich `computeHeaderStats()` auf und erben dessen Verhalten.
  - Test: Bestehender Test für `tripStats.ts` (falls vorhanden) bzw. manueller Nachweis, dass
    diese drei Dateien im Diff dieses Fixes NICHT verändert wurden, während ihr Verhalten sich
    über den `headerStats.ts`-Fix ändert.

## Known Limitations

- Kein sichtbarer UI-Hinweis, ob eine angezeigte km-Zahl gemessen (Track) oder geschätzt
  (Haversine) ist — explizit kein Ziel dieses Fixes (PO-Entscheid).
- Segmente, die eine Etappengrenze überschreiten (`fullProfile.ts`), bleiben grundsätzlich
  Haversine-basiert, auch wenn beide angrenzenden Etappen vollständig vermessen sind — das
  Backend liefert `distance_from_start_km` je Etappe relativ zum jeweiligen Etappenstart, ein
  direkter Vergleich der Rohwerte über Etappengrenzen hinweg wäre nicht korrekt.
- Der PO-Beispielfall (Etappe „03: Porzehütte → Hochweißsteinhaus") zeigt weiterhin 12,8 km statt
  17,7 km, bis Issue #2109 (Datenverlust bei `distance_from_start_km` im Backend) separat gemergt
  ist — dieser Fix ist unabhängig entwickel- und testbar (Fixtures mit/ohne das Feld), liefert dem
  PO aber erst nach #2109 sichtbaren Nutzen für diesen konkreten Fall.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix nach etabliertem, bereits im Backend zweimal angewendetem Muster
  („echter Wert wenn vorhanden, sonst Haversine-Fallback", siehe #2042/#2082). Keine neue
  Architekturentscheidung — die Fallback-Regel (etappen-weise statt segmentweise) ist ein
  PO-Entscheid zur Implementierungsdetail-Ebene, keine Grundsatzentscheidung im Sinne der
  ADR-Kategorien (Kanäle, Provider, Datenmodell/Persistenz, Auth, Editor-Paradigma,
  Test-/Deploy-Strategie).

## Changelog

- 2026-08-23: Initial spec created
- 2026-08-23: Implementiert (TDD GREEN, 45/45 Tests grün, voller Regressionslauf
  2760/2765 grün). Adversary-Finding F001 (Etappengrenzen-Guard in `fullProfile.ts`
  ungetestet) durch Nachtrag-Test geschlossen, eigene Mutations-Gegenprobe bestätigt
  den Fang. Adversary-Verdict: VERIFIED (7/7 ACs).
