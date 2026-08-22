---
entity_id: fix_2082_gehzeit_plausibilitaet
type: bugfix
created: 2026-08-22
updated: 2026-08-22
status: draft
version: "1.0"
tags: [naismith, gehzeit, wegstrecke, ssot, khw]
---

# Gehzeit: eine Regel fuer "ist diese Etappe vermessen" (#2082)

## Approval

- [ ] Approved

## Purpose

Die mit #2042 eingefuehrte Distanzermittlung prueft zu schwach und auf der
falschen Ebene. Sie benutzt eine gemessene Strecke, sobald die Differenz
zweier Wegpunktwerte nicht negativ ist -- auch dann, wenn die Strecke
**kuerzer als die Luftlinie** ist, was es physikalisch nicht geben kann.
Ergebnis ist eine zu optimistische Ankunftszeit, also genau der Fehler, den
#2042 beheben sollte.

Zugleich entscheidet #2042 je Wegpunktpaar, waehrend die Ortsangabe der
Alarme ueber `stage_measured_distances()` je Etappe entscheidet. Dieselbe
Etappe kann deshalb in zwei Aussagen desselben Briefings verschieden
beurteilt werden.

Diese Aenderung beseitigt beides, indem sie die zweite Kopie **entfernt**:
Beide Naismith-Implementierungen leiten kuenftig aus der kanonischen Regel
ab, statt eine eigene mitzufuehren.

## Source

- **File:** `src/services/trip_segments.py` — **Identifier:** `stage_measured_distances`
  (kanonische Regel, unveraendert; sie ist der Massstab)
- **File:** `src/core/naismith.py` — **Identifier:** `compute_stage_arrivals`;
  `_segment_distance_km` **entfaellt**
- **File:** `internal/model/naismith.go` — **Identifier:** `ComputeStageArrivals`;
  `segmentDistanceKm` wird durch ein Etappen-Pendant ersetzt

Schicht: Python-Core (`src/`) UND Go-API (`internal/`) -- beide Naismith-Seiten
sind bit-genau gespiegelt und muessen symmetrisch geaendert werden.

## Estimated Scope

- **LoC:** ~60 Produktivcode (Python schrumpft, Go bekommt das Pendant) + Tests
- **Files:** 2 Produktiv-, 2 Testdateien
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2042 | Vorgaenger | fuehrte die zu behebende Regel ein |
| `stage_measured_distances` (#2036 AC-8/AC-9/AC-14) | Regel | strikte Monotonie + Luftlinien-Plausibilitaet, je Etappe |

## Implementation Details

```
Python  compute_stage_arrivals:
        distanzen = stage_measured_distances(stage.waypoints)
        distanzen is None  -> jede Teilstrecke = Luftlinie (Bestandsverhalten)
        sonst              -> Teilstrecke = Differenz aufeinanderfolgender Werte

Go      ComputeStageArrivals: dasselbe ueber ein neues stageMeasuredDistances(),
        das die drei Bedingungen der Python-Regel spiegelt.
```

Entscheidung (Tech Lead, 2026-08-22): **Etappen-Ebene, alles oder nichts.**
Eine teilweise vermessene Etappe waere eine Ankunftszeit, die an einer Stelle
stimmt und an der naechsten still falsch ist -- und sie widerspraeche der
Ortsangabe desselben Briefings.

Nicht angefasst: Naismith-Summenformel, Tempoparameter, Startzeit, Rundung,
die Normierung auf den Etappenstart.

## Expected Behavior

- **Input:** Etappe mit Wegpunkten, je optional `distance_from_start_km`.
- **Output:** `arrival_calculated` je Wegpunkt. Vermessene, plausible Etappen
  rechnen mit der gemessenen Strecke; alle anderen wie im Bestand.
- **Side effects:** keine.

## Acceptance Criteria

- **AC-1:** Given eine Etappe, in der EIN Abschnitt kuerzer als die Luftlinie
  zwischen seinen Wegpunkten ist / When die Ankunftszeiten berechnet werden /
  Then rechnet die GESAMTE Etappe auf Luftlinie, nicht nur dieser Abschnitt.
  - Test: drei Wegpunkte, mittlerer Abschnitt unplausibel kurz; alle
    Ankunftszeiten entsprechen dem Luftlinien-Ergebnis.

- **AC-2:** Given eine Etappe, deren gemessene Werte nicht strikt monoton
  steigen (gleicher oder kleinerer Folgewert) / When gerechnet wird / Then
  faellt die gesamte Etappe auf Luftlinie zurueck.
  - Test: je ein Fall mit gleichem und mit kleinerem Folgewert.

- **AC-3:** Given eine Etappe, in der ein einzelner Wegpunkt keinen Messwert
  traegt / When gerechnet wird / Then gilt die GANZE Etappe als unvermessen.
  - Test: drei Wegpunkte, mittlerer ohne Wert; alle Abschnitte Luftlinie.
    Dies kehrt #2042 AC-3 bewusst um -- die Gegenprobe steht in Known Limitations.

- **AC-4:** Given eine durchgehend vermessene, plausible Etappe / When
  gerechnet wird / Then beruhen die Ankunftszeiten auf der gemessenen
  Wegstrecke und liegen entsprechend spaeter als der Luftlinien-Wert.
  - Test: Regressionswaechter fuer #2042 AC-1, unveraendert gueltig.

- **AC-5:** Given die kanonische Regel `stage_measured_distances` wird zur
  Laufzeit veraendert / When die Ankunftszeiten berechnet werden / Then
  aendert sich das Ergebnis mit -- die Python-Seite fuehrt also keine zweite
  Kopie der Regel mehr.
  - Test: Mutations-Gegenprobe; die Schwelle der kanonischen Funktion
    verstellen und nachweisen, dass die Ankunftszeiten folgen.

- **AC-6:** Given dieselbe Etappe / When sie ueber die Python- und ueber die
  Go-Implementierung berechnet wird / Then liefern beide dieselben Zeiten --
  fuer vermessene, unvermessene UND unplausible Etappen.
  - Test: Go-Test mit denselben Eingaben und Erwartungswerten wie der
    Python-Test, je Fall aus AC-1 bis AC-4.

- **AC-7:** Given eine Etappe ohne jeden Messwert / When gerechnet wird /
  Then sind die Zeiten byte-identisch zum Bestand.
  - Test: Regressionswaechter fuer #2042 AC-2, unveraendert gueltig.

## Known Limitations

- **#2042 AC-3 wird bewusst zurueckgenommen.** Dort war der Rueckfall je
  Abschnitt festgelegt; diese Spec ersetzt das durch die Etappen-Regel. Der
  zugehoerige Test aus #2042 wird entsprechend umgeschrieben, nicht geloescht.
- Die Plausibilitaetspruefung erkennt nur Strecken, die KUERZER als die
  Luftlinie sind. Eine zu grosse gemessene Strecke bleibt unentdeckt -- dafuer
  gibt es keine beweisbare Obergrenze.
- Am Produktivbestand tritt der Fall heute nicht auf (Messung 2026-08-22).
  Die Aenderung schliesst eine Schutzluecke, sie behebt kein aktuell
  sichtbares Fehlverhalten.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine Entscheidungsflaeche beruehrt. Es wird eine Kopie
  entfernt und die bereits bestehende kanonische Regel zur einzigen Quelle
  gemacht -- die Richtung, die #1480/#1474 fuer andere Skalen bereits
  vorgeben.

## Changelog

- 2026-08-22: Initial spec created (#2082)
