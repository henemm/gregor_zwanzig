---
entity_id: issue_777_geosphere_nowcast_falsy_tests
type: tests
created: 2026-06-12
updated: 2026-06-12
spec: docs/specs/modules/issue_777_geosphere_nowcast_falsy.md
issue: 777
---

# Test-Manifest — Issue #777: GeoSphere-NOWCAST 0.0 ≠ None

Mock-frei. Der Parser ist eine reine Transformation eines API-Response-Dicts; ein
real-geformter NOWCAST-Response (exakte GeoSphere-Struktur: `timestamps` +
`features[0].properties.parameters.{t2m,ff,fx,rr}.data`) läuft durch die ECHTE
`GeoSphereProvider._parse_nowcast_response` — kein Mock, kein Patch.

Testdatei: `tests/tdd/test_issue_777_geosphere_nowcast_falsy.py`

## AC-1 — Trockener Niederschlag 0.0 bleibt 0.0

- `test_ac1_dry_precip_zero_stays_zero_not_none`
  `rr=0.0` → `precip_1h_mm == 0.0` (float), nicht `None`.

## AC-2 — Windstille/keine Böe 0.0 bleibt 0.0

- `test_ac2_calm_wind_and_gust_zero_stays_zero_not_none`
  `ff=0.0`, `fx=0.0` → `wind10m_kmh == 0.0` und `gust_kmh == 0.0`, nicht `None`.

## AC-3 — Echte Datenlücke bleibt None

- `test_ac3_missing_datapoint_stays_none`
  Parameter-Array kürzer als Zeitstempel-Liste → fehlender Datenpunkt bleibt `None`
  (kein 0.0); Gegenprobe: echte 0.0-Werte im selben Response bleiben 0.0.

## AC-4 — Nicht-Null-Werte unverändert (keine Regression)

- `test_ac4_nonzero_values_unchanged_no_regression`
  `rr=1.2`, `ff=3.5`, `fx=5.0` → `precip_1h_mm==1.2`, `wind10m_kmh==12.6`,
  `gust_kmh==18.0`, `t2m_c==18.3`.
