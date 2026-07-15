---
entity_id: issue_1254_department_boundaries
type: feature
created: 2026-07-15
updated: 2026-07-15
status: draft
version: "1.0"
workflow: fix-1254-department-boundaries
tags: [official-alerts, meteofrance, geo, bugfix]
---

# Département-Grenzen für lookup_department (Issue #1254)

## Approval

- [ ] Approved

## Purpose

`lookup_department(lat, lon)` ordnet eine Koordinate dem französischen
Département zu, dessen amtliche Warn-/Waldbrandstufe (Vigilance, Météo des
Forêts) für diesen Ort gilt. Der Fix ersetzt die reine Nächster-Präfektur-
Zentroid-Näherung durch echte Point-in-Polygon-Prüfung gegen die tatsächlichen
Département-Grenzen, damit Orte an exzentrischen Rändern (z.B. Draguignan,
Fréjus im Département Var) nicht fälschlich einem entfernten Nachbar-
Département zugeordnet werden — mit direkter Auswirkung auf die angezeigte
Gefahrenstufe.

## Source

- **File:** `src/services/official_alerts/department_mapper.py`
- **Identifier:** `def lookup_department`

> **Schicht-Hinweis:** Python-Core / Domain-Backend
> (`src/services/official_alerts/`, FastAPI Core über `api.main:app`). Kein
> Frontend- und kein Go-API-Anteil in diesem Fix.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `massif_zones._point_in_ring` (bzw. extrahierter geteilter Ray-Cast-Helper) | function | Wiederverwendete Jordan-Kurven-Test-Implementierung — KEINE zweite Copy-Paste-Implementierung (Projekt-Konsolidierungsregel) |
| `src/services/official_alerts/vigilance.py:170` | module | Verbraucher — nutzt `lookup_department` zur Ermittlung der Vigilance-Warnstufe; filtert vorher per Frankreich-Bounding-Box, behandelt `None` als "keine Warnungen" |
| `src/services/official_alerts/meteo_forets.py:144` | module | Verbraucher — nutzt `lookup_department` zur Ermittlung der Waldbrandstufe; gleiches `None`-Verhalten wie vigilance.py |
| `data/massif_polygons.json` (Muster) | data | Vorbild für Bündelung/Fail-soft-Ladepfad der neuen `department_polygons.json` |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/official_alerts/department_mapper.py` | MODIFY | `lookup_department`: erst Point-in-Polygon gegen Département-Polygone, dann Nearest-Centroid-Fallback |
| `src/services/official_alerts/geo_ray_cast.py` (oder vergleichbarer Name) | CREATE (ggf. optional) | Geteilter Ray-Cast-Helper (`_point_in_ring`-Extraktion), von `massif_zones.py` und `department_mapper.py` gemeinsam genutzt |
| `src/services/official_alerts/massif_zones.py` | MODIFY (nur falls Helper extrahiert wird) | Import des geteilten Helpers statt lokaler Kopie |
| `src/services/official_alerts/data/department_polygons.json` | CREATE | Generierte, gebündelte Département-Polygondaten (zählt nicht zum LoC-Limit) |
| `tests/.../test_department_boundary_lookup.py` | CREATE | Kern-Tests für AC-1..AC-7 gegen die echte gebündelte Polygondatei |

### Estimated Changes

- **Files:** ~3-5 (department_mapper.py, optional geteilter Helper, optional massif_zones.py-Anpassung, neue Datendatei, neue Testdatei)
- **LoC:** ~60-100 (Datendatei ist generiert und zählt nicht zum LoC-Limit)
- **Effort:** medium

## Implementation Details

**Root Cause:** `lookup_department` (Zeile 119) sucht per euklidischer
Nächster-Nachbar-Distanz den Département-Zentroid (Präfektur-Koordinate), der
der Koordinate am nächsten liegt. An Grenzen mit exzentrischer Präfektur führt
das zu Fehlzuordnungen: Draguignan (43.5402, 6.4665) und Fréjus (43.4332,
6.7370) liegen real im Département Var (83), dessen Präfektur Toulon aber im
Südwest-Eck des Départements sitzt — näher liegen die Präfekturen von
Alpes-de-Haute-Provence (04, Digne) bzw. Alpes-Maritimes (06, Nice), sodass
der Nearest-Neighbor-Ansatz "04" bzw. "06" statt "83" liefert.

**Fix-Ansatz (verbindlich, Wiederverwendung des im Projekt existierenden
Musters aus `massif_zones.py`):**

1. Point-in-Polygon über echte Département-Konturen als primäre Auflösung.
   Ray-Casting-Logik (`_point_in_ring`) wird aus `massif_zones.py`
   wiederverwendet — entweder direkt importiert oder in ein geteiltes Modul
   extrahiert, das `massif_zones.py` UND `department_mapper.py` importieren.
   Keine zweite Implementierung der Jordan-Kurven-Logik.
2. Koordinaten-Konvention identisch zu `massif_zones.py`: Ring-Punkte sind
   `[lon, lat]` (GeoJSON-Konvention), die öffentliche Funktions-API bleibt
   `(lat, lon)`.
3. Neue gebündelte Datendatei `data/department_polygons.json` (generiert,
   nicht Teil des LoC-Limits). Erzeugung offline in einem Scratch-venv
   (NICHT im Projekt-Repo), analog zum in `massif_zones.py` dokumentierten
   Rezept:
   - Quelle: öffentliche Département-Konturen der französischen Metropole
     inkl. Korsika (Codes "01".."95", Korsika als "2A"/"2B"), z.B. IGN
     ADMIN-EXPRESS, data.gouv.fr oder das Repo `gregoiredavid/france-geojson`
     (`departements.geojson`).
   - Vereinfachung mit `shapely` `.simplify(~0.005, preserve_topology=True)`
     (grobe Toleranz ~200-500m, für Département-Granularität ausreichend).
   - Exterior-Ringe UND Interior-Ringe (Holes) je Polygon übernommen —
     Holes sind für die korrekte Enklaven-Behandlung nötig (AC-8, Enclave
     des Papes: 84-Exklave als Loch in 26). Datenformat trennt je Polygon
     Exterior und Holes.
   - Property je Feature = Département-Code.
   - Das Erzeugungsskript selbst ist ein Wegwerf-Werkzeug und NICHT Teil des
     Projekts — nur das Rezept wird im Docstring/Spec dokumentiert.
4. Ablauf in `lookup_department(lat, lon)`:
   - Schritt 1: Iteriere über geladene Département-Polygone, teste
     Point-in-Polygon; erster Treffer gewinnt (Rückgabe: Département-Code).
   - Schritt 2 (Fallback): Kein Polygon-Treffer ODER Polygondatei fehlt/ist
     leer (fail-soft) → bestehende Nearest-Centroid-Logik
     (`DEPARTMENT_CENTROIDS`) unverändert als Rückfallebene.
   - Rückgabe-Kontrakt bleibt `Optional[str]` unverändert, Korsika weiterhin
     als "2A"/"2B".
5. Fail-soft-Ladepfad wie `massif_zones._load_massifs`: fehlende oder kaputte
   Polygondatei darf NIE den Import von `services.official_alerts` reißen —
   stattdessen Warnung loggen und stillschweigend auf den
   Nearest-Centroid-Pfad zurückfallen.

Verbraucher (`vigilance.py:170`, `meteo_forets.py:144`) bleiben unverändert:
sie rufen weiterhin `lookup_department(lat, lon)` auf, filtern vorher per
Frankreich-Bounding-Box und behandeln `None` als "keine Warnungen".

## Expected Behavior

- **Input:** `lat: float, lon: float` — eine geografische Koordinate
  innerhalb oder nahe der französischen Metropole/Korsika.
- **Output:** `Optional[str]` — Département-Code ("01".."95", "2A", "2B")
  oder `None` nur in dem praktisch nie eintretenden Fall, dass sowohl
  Polygon-Daten als auch die Zentroid-Tabelle leer wären.
- **Side effects:** keine (reine Lookup-Funktion). Fail-soft-Logging beim
  Fehlen/Defekt der Polygondatei.

## Test Plan

### Automated Tests (TDD RED)

Kern-Schicht (deterministisch, keine Mocks, gegen die echte gebündelte
`department_polygons.json`). Testdatei nach Verhalten benennen, NICHT nach
Issue-Nummer (z.B. `tests/.../test_department_boundary_lookup.py`).

- [ ] Test 1: GIVEN die Koordinate von Draguignan (43.5402, 6.4665) WHEN
  `lookup_department` aufgerufen wird THEN ist das Ergebnis "83".
- [ ] Test 2: GIVEN die Koordinate von Fréjus (43.4332, 6.7370) WHEN
  `lookup_department` aufgerufen wird THEN ist das Ergebnis "83".
- [ ] Test 3: GIVEN eine Referenzliste echter Grenzorte (Draguignan→83,
  Fréjus→83, Brignoles→83, Toulon→83, Manosque→04, Castellane→04,
  Barcelonnette→04, Menton→06) WHEN jeder Ort per `lookup_department`
  aufgelöst wird THEN landet jeder im tatsächlichen Département seiner
  realen Lage.
- [ ] Test 4: GIVEN die Koordinaten von Ajaccio (41.9192, 8.7386) und Bastia
  (42.6979, 9.4508) WHEN `lookup_department` aufgerufen wird THEN ist das
  Ergebnis "2A" bzw. "2B" (Korsika-Kontrakt bleibt erhalten).
- [ ] Test 5: GIVEN eine Koordinate innerhalb der Frankreich-Bounding-Box,
  die in keinem Département-Polygon liegt (küstennahe Rundungslücke) WHEN
  `lookup_department` aufgerufen wird THEN liefert der
  Nearest-Centroid-Fallback einen plausiblen Département-Code (nicht `None`,
  kein Crash).
- [ ] Test 6: GIVEN die Polygondatei fehlt oder ist beschädigt WHEN das
  Modul importiert und `lookup_department` aufgerufen wird THEN wird eine
  Warnung geloggt, der Import von `services.official_alerts` bleibt intakt,
  und die Auflösung fällt fail-soft auf Nearest-Centroid zurück.
- [ ] Test 7: GIVEN bestehende korrekt aufgelöste Orte (Toulon→83,
  Manosque→04, Menton→06, Brignoles→83) WHEN der Fix aktiv ist THEN bleiben
  diese Ergebnisse unverändert korrekt (keine Regression bei bisher
  richtigen Orten).

## Acceptance Criteria

- **AC-1:** Given die Koordinate von Draguignan (43.5402, 6.4665), When `lookup_department` aufgerufen wird, Then ist das Ergebnis "83" (Var).
  - Test: `lookup_department(43.5402, 6.4665) == "83"` gegen echte gebündelte Polygondaten.

- **AC-2:** Given die Koordinate von Fréjus (43.4332, 6.7370), When `lookup_department` aufgerufen wird, Then ist das Ergebnis "83" (Var).
  - Test: `lookup_department(43.4332, 6.7370) == "83"` gegen echte gebündelte Polygondaten.

- **AC-3:** Given eine Referenzliste echter Grenzorte [Draguignan→83, Fréjus→83, Brignoles(43.4055,6.0619)→83, Toulon(43.1258,5.9304)→83, Manosque(43.8339,5.7870)→04, Castellane(43.8470,6.5127)→04, Barcelonnette(44.3866,6.6521)→04, Menton(43.7765,7.5027)→06], When jeder Ort per `lookup_department` aufgelöst wird, Then landet jeder im tatsächlichen Département seiner realen Lage.
  - Test: parametrisierte Prüfung über alle acht Orte gegen das erwartete Département.

- **AC-4:** Given die Koordinaten von Ajaccio (41.9192, 8.7386) und Bastia (42.6979, 9.4508), When `lookup_department` aufgerufen wird, Then ist das Ergebnis "2A" bzw. "2B" (Korsika-Kontrakt bleibt erhalten).
  - Test: `lookup_department(41.9192, 8.7386) == "2A"` und `lookup_department(42.6979, 9.4508) == "2B"`.

- **AC-5:** Given eine Koordinate innerhalb der Frankreich-Bounding-Box, die in keinem Département-Polygon liegt (z.B. küstennahe Rundungslücke), When `lookup_department` aufgerufen wird, Then liefert der Nearest-Centroid-Fallback einen plausiblen Département-Code (nicht None, kein Crash).
  - Test: gezielt gewählte Koordinate außerhalb aller vereinfachten Polygone liefert einen String-Code aus `DEPARTMENT_CENTROIDS`, keine Exception.

- **AC-6:** Given die Polygondatei fehlt oder ist beschädigt, When das Modul importiert und `lookup_department` aufgerufen wird, Then wird eine Warnung geloggt, der Import von `services.official_alerts` bleibt intakt, und die Auflösung fällt fail-soft auf Nearest-Centroid zurück.
  - Test: Polygondatei-Pfad temporär auf nicht existierende/kaputte Datei umgebogen, Import + Aufruf schlagen nicht fehl, Ergebnis entspricht der alten Centroid-Logik, Warnung im Log vorhanden.

- **AC-7:** Given bestehende korrekt aufgelöste Orte (z.B. Toulon→83, Manosque→04, Menton→06, Brignoles→83), When der Fix aktiv ist, Then bleiben diese Ergebnisse unverändert korrekt (keine Regression bei bisher richtigen Orten).
  - Test: Regressions-Assertion über die bereits vorher korrekten Orte, identisch zu AC-3-Subset.

- **AC-8:** Given die Orte der Enclave des Papes — Valréas (44.3796, 4.9895), Visan (44.3311, 4.9291), Grillon (44.3626, 4.9455) —, die als Exklave des Départements Vaucluse (84) vollständig vom Département Drôme (26) umschlossen sind, When `lookup_department` aufgerufen wird, Then ist das Ergebnis jeweils "84" (nicht "26"). Voraussetzung: Die Polygon-Prüfung berücksichtigt Löcher (Enklaven), d.h. ein Punkt, der im Loch eines Département-Polygons liegt, gilt NICHT als in diesem Département.
  - Test: `lookup_department(44.3796, 4.9895) == "84"` (analog Visan, Grillon) gegen die neu erzeugte, Löcher enthaltende Polygondatei.

## Known Limitations

- Die vereinfachten Polygone (`.simplify(~0.005, preserve_topology=True)`,
  Toleranz ~200-500m) folgen den Département-Grenzen nicht meterexakt. An
  mikroskopisch feinen Grenzverläufen (unmittelbar auf der Linie) ist eine
  Fehlzuordnung theoretisch weiterhin möglich, ist aber angesichts der
  Département-Granularität der Vigilance-/Waldbrand-Daten praktisch
  irrelevant — der Nearest-Centroid-Fallback fängt zusätzlich Lücken ab.
- Die in Test Plan/AC-3 und AC-7 gewählten Test-Orte liegen bewusst nicht
  grenzstrichgenau, sondern in eindeutig einem Département zuordenbarer
  Lage — Ziel ist die Behebung der groben Fehlzuordnung (Draguignan/Fréjus),
  nicht meterexakte Grenzverifikation.
- Holes in Département-Polygonen (Enklaven) werden berücksichtigt
  (AC-8): Ein Punkt gilt nur dann als in einem Département, wenn er im
  Exterior-Ring UND in keinem seiner Holes liegt. Damit werden bewohnte
  Exklaven wie die Enclave des Papes (Valréas/Visan/Grillon → 84) korrekt
  zugeordnet. Der geteilte `_point_in_ring`-Helper bleibt unverändert
  (Ring-Test); die Loch-Behandlung geschieht in der Département-
  Auswertungsschicht, ohne das Massiv-Muster (`massif_zones.py`, das Holes
  weiterhin bewusst ignoriert) zu berühren.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Bugfix-Konsolidierung eines bereits im Projekt
  etablierten Musters (Point-in-Polygon mit reinem Ray-Casting, analog
  `massif_zones.py`, Issue #1037). Keine neue Architekturentscheidung, keine
  neue Laufzeit-Abhängigkeit, kein neuer Systemgrenzen-Schnitt.

## Changelog

- 2026-07-15: Initial spec created
- 2026-07-15: AC-8 ergänzt (Enclave des Papes / Loch-Behandlung). PO-Entscheidung nach Adversary-Befund F001: die zuvor als "Known Limitation" akzeptierte Holes-Ignorierung wird für Départements aufgehoben — bewohnte Exklaven (Valréas/Visan/Grillon → 84) werden korrekt zugeordnet. Datengenerierung erzeugt jetzt Holes; Auswertung berücksichtigt sie. Massiv-Muster unberührt.
