---
entity_id: radar_nowcast_inca_fix
type: module
created: 2026-06-12
updated: 2026-06-12
status: draft
version: "1.0"
tags: [providers, weather, nowcast, inca, geosphere, austria, bugfix]
---

# Nowcast: INCA-Pfad-Reparatur — korrekte Attributnamen + Dry-Frames (Issue #770)

## Approval

- [x] Approved

## Purpose

Repariert den seit jeher defekten österreichischen INCA-Nowcast-Pfad im
`RadarNowcastService`. `_fetch_geosphere_inca` liest zwei nicht existierende
Attribute vom `ForecastDataPoint` (`precipitation_mm`, `time`) → bei JEDEM
AT-Nowcast-Abruf fliegt ein `AttributeError`, der Fail-Soft-Handler gibt `[]`
zurück → Österreichs dediziertes INCA-Radar (1 km, höchste Auflösung für AT)
wird nie genutzt; die Kette fällt still auf ICON-D2/best_match zurück.

## Source

- **File:** `src/services/radar_service.py` (Bugfix)
- **Identifier:** `RadarNowcastService._fetch_geosphere_inca`
- **Schicht:** Python-Backend (`src/services/`) — kein Go, kein Frontend.

## Estimated Scope

- **LoC:** ~6 produktiv + mock-freie Tests
- **Files:** 1 produktiv + 1 Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.radar_service.RadarNowcastService` | service | Quellen-Kette (RADOLAN→INCA→AROME-FR→ICON-D2→global) |
| `providers.geosphere.GeoSphereProvider.fetch_nowcast` | provider | Liefert `NormalizedTimeseries` aus INCA-Endpoint `nowcast-v1-15min-1km` |
| `app.models.ForecastDataPoint` | dataclass | Felder: `ts` (datetime), `precip_1h_mm` (Optional[float]) |
| `providers.brightsky.RadarFrame` | dataclass | Gemeinsames Frame-Format (`timestamp`, `precip_mm_h`) |

## Implementation Details

### Bug (IST — kaputt)
```python
for dp in ts.data:
    if dp.precipitation_mm is not None:        # AttributeError: 'ForecastDataPoint'
        mm_h = float(dp.precipitation_mm) * 4.0 #   has no attribute 'precipitation_mm'
        frames.append(RadarFrame(
            timestamp=dp.time if dp.time.tzinfo else ...,  # dp.time existiert auch nicht
            precip_mm_h=mm_h,
        ))
```

### Fix (SOLL)
```python
for dp in ts.data:
    raw = dp.precip_1h_mm                       # korrektes Feld
    mm_h = float(raw) * 4.0 if raw is not None else 0.0   # None → Dry-Frame (0 mm/h)
    ts_val = dp.ts if dp.ts.tzinfo else dp.ts.replace(tzinfo=timezone.utc)
    frames.append(RadarFrame(timestamp=ts_val, precip_mm_h=mm_h))
```

**Zwei Korrekturen:**
1. **Attributnamen:** `precipitation_mm`→`precip_1h_mm`, `time`→`ts`
   (Quelle der Wahrheit: `src/app/models.py:84–96`; `geosphere.py:_parse_nowcast_response`
   füllt exakt `precip_1h_mm`/`ts`).
2. **Dry-Frame-Konsistenz:** `None`-Niederschlag → `0.0` (statt Frame zu überspringen),
   exakt analog zum `_fetch_openmeteo_15`-Pfad. Damit liefert INCA bei vorhandenen
   Daten zuverlässig nicht-leere Frames → INCA ist verlässlich die Quelle für AT,
   nicht nur bei Regen.

### Einheiten-Verifikation (Issue-Punkt 2 — kein Fix nötig)
- Endpoint `nowcast-v1-15min-1km` → **15-Minuten-Schritte**.
- `rr`-Parameter = Niederschlagssumme je 15-min-Intervall (mm/15min), gespeichert in
  `precip_1h_mm` (Feldname ist ein Misnomer, der Wert ist per-Schritt).
- **×4-Umrechnung mm/15min → mm/h ist KORREKT** (4 × 15 min = 60 min). Die ×4-Logik
  bleibt unverändert.

## Expected Behavior

- **Input:** Reale österreichische Koordinate (INCA-only, d.h. außerhalb der RADOLAN-Box),
  z.B. Wien 48.21 N / 16.37 E.
- **Output:** `NowcastResult` mit `source == "INCA"` und ≥1 realen Frame.
- **Side effects:** Keine (reiner Lese-/Fetch-Pfad, fail-soft beibehalten).

## Acceptance Criteria

- **AC-1:** Given eine reale österreichische INCA-only-Koordinate (außerhalb der RADOLAN-Box, z.B. Wien 48.21 N / 16.37 E) / When `RadarNowcastService.get_nowcast(lat, lon)` aufgerufen wird / Then ist `result.source == "INCA"` und `result.frames` enthält ≥1 realen Frame mit numerischer Niederschlagsrate (mm/h ≥ 0) — NICHT der Fallback `ICON-D2`/`minutely_15`.
  - Test: Echter HTTP-Call gegen die GeoSphere-INCA-API mit fester Wien-Koordinate; assert `source=="INCA"`, ≥1 Frame, alle Raten numerisch ≥ 0. Kein Mock. (Bug rot vor Fix: `source != "INCA"` / Frames leer; grün nach Fix: `source=="INCA"`.)

- **AC-2:** Given `_fetch_geosphere_inca` mit einer realen `NormalizedTimeseries` von `fetch_nowcast` / When die Datenpunkte zu `RadarFrame`s geparst werden / Then wirft die Schleife KEINEN `AttributeError` mehr und jeder `ForecastDataPoint` (auch trockene mit `precip_1h_mm is None`) ergibt genau einen Frame mit korrektem `timestamp` (aus `dp.ts`, timezone-aware) und `precip_mm_h == precip_1h_mm × 4` (bzw. `0.0` bei `None`).
  - Test: Echter `GeoSphereProvider.fetch_nowcast`-Call gegen Wien; assert `len(frames) == len(ts.data)` (kein Dry-Frame verschluckt), alle `timestamp.tzinfo is not None`, jede `precip_mm_h` numerisch ≥ 0. Mock-frei.

## AC-Test-Mapping (Test-Plan)

| AC | Testfunktion |
|----|--------------|
| AC-1 | `test_ac1_inca_real_fetch_returns_inca_source` |
| AC-2 | `test_ac2_inca_parses_all_points_no_attributeerror` |

Testdatei: `tests/tdd/test_feature_770_inca_nowcast_fix.py` (mock-frei).

## Known Limitations

- **Netzwerk-/API-Abhängigkeit im Test:** Die mock-freien Tests rufen die echte
  GeoSphere-INCA-API. Fail-soft (`[]` bei Exception) bleibt erhalten; bei API-Ausfall
  fällt die Kette weiterhin sauber auf ICON-D2/best_match zurück.
- **RADOLAN-Überlappung:** Die INCA-Box überlappt im Westen/Norden Österreichs die
  RADOLAN-Box (47.0–55.1 N / 5.8–15.1 E). West-AT-Koordinaten (z.B. Innsbruck) treffen
  weiterhin zuerst RADOLAN — beabsichtigt. Eine saubere INCA-only-Test-Koordinate muss
  `lon > 15.1` oder `lat < 47.0` erfüllen (Wien: `lon 16.37 > 15.1`).
- **Keine echte Blitz-Quelle:** Gewitter-Klassifikation aus INCA-Niederschlag/Daten, kein
  kommerzieller Blitz-Feed (unverändert wie #656).

## Changelog

- 2026-06-12: Initial spec created (Issue #770) — INCA-Attributnamen korrigiert
  (`precip_1h_mm`/`ts`), Dry-Frame-Konsistenz analog Open-Meteo-Pfad; ×4-Einheit als korrekt verifiziert.
