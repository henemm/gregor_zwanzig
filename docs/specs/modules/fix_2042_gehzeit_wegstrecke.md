---
entity_id: fix_2042_gehzeit_wegstrecke
type: module
created: 2026-08-22
updated: 2026-08-22
status: approved
version: "1.0"
tags: [naismith, gehzeit, wegstrecke, khw]
---

# Gehzeit auf gemessener Wegstrecke statt Luftlinie (#2042)

## Approval

- [x] Approved — PO, 2026-08-22

## Purpose

Die Ankunftszeiten der Wegpunkte werden heute aus der **Luftlinie** zwischen aufeinanderfolgenden Wegpunkten berechnet und sind dadurch systematisch zu frueh. Diese Aenderung stellt beide Naismith-Implementierungen auf die seit #2036 am Wegpunkt persistierte **gemessene Wegstrecke** um, mit Rueckfall auf die Luftlinie fuer unvermessene Etappen.

## Source

- **File:** `src/core/naismith.py` — **Identifier:** `compute_stage_arrivals` (Luftlinie heute Zeile 119)
- **File:** `internal/model/naismith.go` — **Identifier:** `ComputeStageArrivals` (Luftlinie heute Zeile 118)

Schicht: **Python-Core** (`src/core/`) UND **Go-API** (`internal/model/`). Beide Implementierungen sind bewusst wortgleich — der Docstring von `compute_stage_arrivals` sagt "Spiegelt Go ComputeStageArrivals bit-genau". Die Aenderung MUSS deshalb symmetrisch erfolgen; eine einseitige Umstellung erzeugt genau die Divergenz, die der Docstring ausschliesst.

## Estimated Scope

- **LoC:** ~30 Produktivcode (je ~15 Python/Go) + Tests; Gesamt unter dem 250er-Limit
- **Files:** 2 Produktivdateien, 2 Testdateien (1 Python, 1 Go)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2036 / `Waypoint.distance_from_start_km` | Datenfeld | Liefert die gemessene Strecke; `None` = nicht gemessen. **Gemerged** (PR #2055) |
| `internal/model.Waypoint.DistanceFromStartKm` | Datenfeld | Go-Pendant, `*float64` |
| #2070 | Messung | Entscheidet, ob der KHW-Trip ueberhaupt vermessene Etappen hat. Kein Code-Abhaengigkeit — nur der Nutzen haengt daran |

## Implementation Details

Ersetzt in beiden Implementierungen die Distanzermittlung je Wegpunktpaar:

```
# heute
dist = haversine_km(prev.lat, prev.lon, wp.lat, wp.lon)

# kuenftig
dist = gemessene Differenz, wenn beide Wegpunkte eine Strecke tragen
       und die Differenz nicht negativ ist
       sonst haversine_km(...)   # unveraenderter Rueckfall
```

Die Entscheidung faellt **je Wegpunktpaar**, nicht je Etappe. Eine Etappe, in der nur ein Teil der Wegpunkte vermessen ist, rechnet die vermessenen Abschnitte gemessen und die uebrigen als Luftlinie — statt die ganze Etappe zu verwerfen.

Nicht angefasst werden: `_naismith_hours` (Summenformel), Auf-/Abstiegsanteile, Startzeit-Ermittlung, Rundung, `formatHHMM`.

## Expected Behavior

- **Input:** Eine Etappe mit Wegpunkten; je Wegpunkt optional `distance_from_start_km`.
- **Output:** `arrival_calculated` je Wegpunkt — auf vermessenen Abschnitten spaeter als heute (gemessen Faktor 1,17-1,59 gegenueber Luftlinie), auf unvermessenen unveraendert.
- **Side effects:** keine. Kein Schreibzugriff, keine Provider-Abfrage, kein Netz.

## Acceptance Criteria

- **AC-1:** Given eine Etappe, deren Wegpunkte alle eine gemessene Strecke tragen / When die Ankunftszeiten berechnet werden / Then beruht die Gehzeit je Abschnitt auf der Differenz der gemessenen Strecken, nicht auf der Luftlinie — belegt an einem Abschnitt, dessen gemessene Strecke deutlich ueber der Luftlinie liegt.
  - Test: Etappe mit zwei Wegpunkten, gemessene Differenz doppelt so gross wie die Luftlinie; die berechnete Ankunft liegt entsprechend spaeter als der Luftlinien-Wert.

- **AC-2:** Given eine Etappe, deren Wegpunkte KEINE gemessene Strecke tragen (`None`) / When die Ankunftszeiten berechnet werden / Then sind die Ergebnisse byte-identisch zum heutigen Verhalten.
  - Test: Bestandsetappe ohne gemessene Strecke; die berechneten Zeiten entsprechen exakt den heute erwarteten Werten.

- **AC-3:** Given eine Etappe, in der nur ein Teil der aufeinanderfolgenden Wegpunkte eine gemessene Strecke traegt / When die Ankunftszeiten berechnet werden / Then rechnen die vermessenen Abschnitte gemessen und die uebrigen als Luftlinie — der Rueckfall gilt je Abschnitt, nicht je Etappe.
  - Test: Etappe mit drei Wegpunkten, davon einer ohne Strecke; nachweisen, dass der vermessene Abschnitt gemessen und der andere als Luftlinie rechnet.

- **AC-4:** Given zwei aufeinanderfolgende Wegpunkte, deren gemessene Strecken eine negative Differenz ergeben / When die Ankunftszeiten berechnet werden / Then wird die Luftlinie verwendet statt einer negativen Distanz.
  - Test: Wegpunktpaar mit absteigender Strecke; die Gehzeit entspricht der Luftlinie und ist nicht kuerzer als null.

- **AC-5:** Given dieselbe Etappe mit denselben Wegpunkten und derselben Aktivitaet / When sie einmal ueber die Python- und einmal ueber die Go-Implementierung berechnet wird / Then liefern beide dieselben Ankunftszeiten — fuer vermessene wie unvermessene Etappen.
  - Test: Go-Test mit denselben Eingabewerten wie der Python-Test, gleiche erwartete `HH:MM`-Ausgaben.

## Known Limitations

- Der Nutzen fuer einen Bestandstrip haengt daran, ob die Track-Aufloesung aus #2036 die Etappe vermessen konnte (#2070). Bleibt sie unvermessen, greift AC-2 und die Zeiten bleiben wie heute — der Fehler bleibt dort bestehen, sichtbar aber unveraendert.
- Die gemessene Strecke stammt aus dem GPX-Track; ihre Genauigkeit ist die des Tracks. Eine Abweichung zwischen Track und tatsaechlich gegangenem Weg wird nicht korrigiert.
- Die Umstellung macht Ankunftszeiten **spaeter**, nicht "richtig": Naismith bleibt ein Modell, die Tempoparameter bleiben unveraendert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine Entscheidungsflaeche beruehrt — weder Kanaele, Provider, Datenmodell, Auth, Editor-Paradigma noch Test-/Deploy-Strategie. Das Datenfeld existiert bereits (#2036); hier wird nur die vorhandene Groesse anstelle einer Schaetzung benutzt.

## Changelog

- 2026-08-22: Initial spec created (#2042)
- 2026-08-22: ACs vom PO freigegeben; umgesetzt in `src/core/naismith.py` und `internal/model/naismith.go`
