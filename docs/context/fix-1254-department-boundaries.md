# Context: fix-1254-department-boundaries

## Request Summary
Grenzorte werden dem falschen französischen Département zugeordnet (Draguignan → 04 statt 83, Fréjus → 06 statt 83) und erhalten dadurch die Warnstufen (Vigilance + Waldbrand) des falschen Départements — sicherheitsrelevant.

## Root Cause (bestätigt)
`src/services/official_alerts/department_mapper.py:119` (`lookup_department`) ordnet eine Koordinate per euklidischem Nearest-Neighbor dem Département zu, dessen **Präfektur-Zentroid** am nächsten liegt. An Rändern mit exzentrischer Präfektur (Var: Toulon im SW-Eck) ist der halbe Département näher an einer Nachbar-Präfektur. In der Spec `issue_1035_vigilance_source.md` als "Known Limitation" notiert.

Reproduktion gegen die echte Zentroid-Tabelle:
| Ort | Soll | Ist (Bug) | nächste Zentroide |
|---|---|---|---|
| Draguignan (43.5402, 6.4665) | 83 | 04 | 04=0.598, 83=0.680 |
| Fréjus (43.4332, 6.7370) | 83 | 06 | 06=0.594, 83=0.866 |
| Brignoles | 83 | 83 ✓ | 83=0.312 |
| Toulon | 83 | 83 ✓ | 83=0.003 |

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/official_alerts/department_mapper.py` | Enthält `lookup_department` + `DEPARTMENT_CENTROIDS` — Kern des Fixes |
| `src/services/official_alerts/vigilance.py:170` | Verbraucher (Vigilance-Stufen) |
| `src/services/official_alerts/meteo_forets.py:144` | Verbraucher (Waldbrandstufen) |
| `docs/specs/modules/issue_1035_vigilance_source.md` | Bestehende Spec, "Known Limitation" |

## Existing Patterns
- Bewusst **keine** externe Geo-Bibliothek (department_mapper Docstring). Ein Fix per Point-in-Polygon muss diese Bauweise wahren (reine Python-Ray-Casting-Funktion + gebündelte Grenzdaten).
- `region_routing.py` nutzt grobe Rechteck-Bounds — Präzedenz für gebündelte statische Geo-Daten ohne Package.

## Dependencies
- Upstream: keine (reine Koordinaten-Eingabe)
- Downstream: `vigilance.py`, `meteo_forets.py` (beide official_alerts). Rückgabe-Kontrakt `Optional[str]` (Département-Code, "2A"/"2B" für Korsika) muss erhalten bleiben.

## Risks & Considerations
- Rückgabewert-Kontrakt (Code-Format inkl. Korsika 2A/2B) darf sich nicht ändern.
- Grenzdaten-Größe: kompaktes/vereinfachtes GeoJSON reicht (Département-Granularität), darf Repo nicht aufblähen.
- Punkte außerhalb Frankreichs müssen weiter `None`/sinnvollen Fallback liefern (heute liefert Nearest-Neighbor immer einen Code — Verhalten für Nicht-FR-Koordinaten klären).
- Fallback wenn Punkt in keinem Polygon (Küstenrundung/Löcher): definierter Rückfall auf Nearest-Centroid denkbar.
