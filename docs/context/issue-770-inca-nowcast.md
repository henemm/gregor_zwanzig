# Context: Issue #770 — INCA-Nowcast-Pfad dauerhaft defekt

## Request Summary
`_fetch_geosphere_inca` liest falsche Attributnamen vom `ForecastDataPoint`
(`precipitation_mm`/`time` statt `precip_1h_mm`/`ts`) → bei jedem AT-Nowcast
AttributeError → Exception-Handler gibt `[]` zurück → Österreichs dediziertes
INCA-Radar (1 km) wird nie genutzt, die Kette fällt still durch.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/radar_service.py` (Z.187–209) | **Bug-Herd:** `_fetch_geosphere_inca` mit falschen Attributnamen + ×4-Umrechnung |
| `src/app/models.py` (Z.84–96) | `ForecastDataPoint`: korrekte Felder `ts`, `precip_1h_mm` |
| `src/providers/geosphere.py` (Z.315–333) | `fetch_nowcast` → `_parse_nowcast_response` füllt `precip_1h_mm` aus `rr` |
| `src/providers/geosphere.py` (Z.67–92) | Endpoint `nowcast-v1-15min-1km`, `NOWCAST_PARAMS` inkl. `rr` |
| `tests/tdd/test_feature_761_icon_d2_nowcast.py` | Test-Muster: realer Fetch, `source==…`, `≥1` Frame |

## Existing Patterns
- **Quellen-Kette** (`_fetch_frames_with_fallback`): RADOLAN → INCA → AROME-FR → ICON-D2 → global. INCA wird nur erreicht, wenn Koordinate NICHT in RADOLAN-Box (47.0–55.1N / 5.8–15.1E) liegt. Saubere INCA-only-Koordinate: **Wien 48.21N / 16.37E** (lon > 15.1 → kein RADOLAN; in INCA-Box 46.3–49.1N / 9.5–17.2E).
- **Open-Meteo-Pfad** (`_fetch_openmeteo_15`): baut Frame pro Zeitschritt, behandelt `None`-Niederschlag als `0.0` (Dry-Frame). Der INCA-Pfad überspringt dagegen `None`-Frames → INCA liefert bei trockener Lage `[]` und fällt durch. Für konsistentes Routing sollte INCA ebenfalls Dry-Frames erzeugen.
- **mock-freie Tests** (#656/#734/#761): echter API-Call gegen reale Koordinate.

## Einheiten-Verifikation (Issue-Punkt 2)
- Endpoint: `nowcast-v1-15min-1km` → **15-min-Schritte**.
- `rr` = Niederschlagssumme je 15-min-Intervall (mm/15min), in `precip_1h_mm` gespeichert (Feldname ist Misnomer, Wert ist per-Schritt).
- **×4-Umrechnung mm/15min → mm/h ist KORREKT** (4 × 15min = 60min). Kein Einheiten-Fix nötig, nur Attributnamen + Dry-Frame-Handling.

## Dependencies
- Upstream: `GeoSphereProvider.fetch_nowcast` (GeoSphere INCA API), `RadarFrame`.
- Downstream: `_derive_result` → `NowcastResult` → `format_now_text` (Telegram `/now`, E-Mail-Nowcast).

## Existing Specs
- `docs/specs/modules/radar_nowcast.md` (#656)

## Risks & Considerations
- INCA-Box überlappt RADOLAN-Box im Westen/Norden Österreichs → Test-Koordinate
  muss INCA-only sein (Wien), sonst greift RADOLAN/BrightSky zuerst.
- Trockene Lage: ohne Dry-Frame-Fix bleibt INCA bei Test ggf. leer → Test flaky.
  Fix: `None`→`0.0` analog Open-Meteo-Pfad, damit INCA bei vorhandenen Daten
  zuverlässig Quelle ist.
- GeoSphere-API-Verfügbarkeit (Netzwerk) im Test — fail-soft beibehalten.
