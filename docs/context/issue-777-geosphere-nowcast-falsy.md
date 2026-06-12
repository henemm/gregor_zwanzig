# Context: Issue #777 — GeoSphere-Nowcast speichert 0.0 mm als None (Falsy-Check)

## Request Summary
`GeoSphereProvider._parse_nowcast_response` macht für mehrere Felder einen Truthiness-Check
`round(x, 1) if x else None`. Bei einem exakten Wert `0.0` (trocken / windstill) ist `0.0` falsy
→ wird als `None` gespeichert. Damit ist „trocken/windstill" (0.0) nicht von „kein Datenpunkt" (None)
unterscheidbar. Fix: `if x is not None`.

## Betroffene Stellen (alle in `_parse_nowcast_response`)
| Zeile | Code | Bug |
|------|------|-----|
| `src/providers/geosphere.py:628` | `precip_1h_mm=round(precip, 1) if precip else None` | 0.0 mm (trocken) → None (Haupt-Befund F002) |
| `src/providers/geosphere.py:620` | `wind_kmh = round(wind * 3.6, 1) if wind else None` | 0.0 m/s (windstill) → None |
| `src/providers/geosphere.py:621` | `gust_kmh = round(gust * 3.6, 1) if gust else None` | 0.0 (keine Böe) → None |

Bereits korrekt (`is not None`): `t2m_c` (625), `humidity_pct` (629).

## Impact (echte Konsumenten, die None ≠ 0.0 behandeln)
Diese filtern `if dp.X is not None` → trockene/windstille Intervalle, die fälschlich als `None`
gespeichert sind, **fallen aus Summen/Mittelwerten/Zählungen heraus** → verzerrte Aggregation:
- `src/services/weather_metrics.py:787` — Niederschlags-Summe filtert None raus
- `src/services/comparison_engine.py:376` — Orts-Vergleich filtert None raus
- `src/services/trip_report_scheduler.py:1090-1094` — Hourly precip/wind/gust filtert None raus
- `src/services/aggregation.py:167` — Aggregations-Lambda auf precip_1h_mm

**Kein Impact** (None und 0.0 identisch behandelt):
- `src/services/radar_service.py:197-199` — INCA-Pfad: `mm_h = raw*4 if raw is not None else 0.0`
  (deshalb war #770 vom Bug nicht betroffen — bestätigt Issue-Notiz)
- `helpers.py:767,932` — nutzt `(dp.precip_1h_mm or 0.0)`

## Existing Patterns
- Test-Referenz: `tests/tdd/test_geosphere_parsing.py` — „Raw API JSON → expected transformed
  values", `GeoSphereValidator` (`src/validation`), `pytest.mark.live`.
- Parser ist reine Transformation eines API-Response-Dicts → deterministischer Verhaltenstest
  möglich, indem ein real-geformter NOWCAST-Response mit `rr=0.0/ff=0.0/fx=0.0` durch den echten
  Parser läuft (kein Mock — echte Parser-Logik auf echt-geformten Daten).

## Risks & Considerations
- **Schema-Datei `src/providers/geosphere.py`** ist nicht in der Schema-Liste (models/trip/loader/
  store) → kein Migrations-Risiko, reine Parse-Logik.
- Sehr kleiner Fix (3 Zeilen). Backend-only, keine GET-Route → Deploy wie #770/#761 (Findings
  SKIPPED, prod_selftest SKIPPED_ALL).
- `cli.py:123` hat einen analogen Falsy-Display-Bug (`if dp.wind10m_kmh`), ist aber **Konsument,
  nicht Parser** → out-of-scope (separater Nebenbefund, ggf. Folge-Issue).
