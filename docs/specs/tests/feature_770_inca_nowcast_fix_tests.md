---
entity_id: feature_770_inca_nowcast_fix_tests
type: tests
created: 2026-06-12
updated: 2026-06-12
spec: docs/specs/modules/radar_nowcast_inca_fix.md
issue: 770
---

# Test-Manifest — Feature #770: INCA-Nowcast-Pfad-Reparatur

Mock-freie Tests. Echter HTTP-Call gegen die GeoSphere-INCA-API mit fester
Wien-Koordinate (48.21 N / 16.37 E — INCA-only, lon 16.37 > RADOLAN-max 15.1).
Bei nachgewiesenem API-Ausfall (`fetch_nowcast → None`) wird geskippt, niemals
gemockt.

Testdatei: `tests/tdd/test_feature_770_inca_nowcast_fix.py`

## AC-1 — INCA wird wirklich genutzt (echter Fetch)

- `test_ac1_inca_real_fetch_returns_inca_source`
  Echter `RadarNowcastService().get_nowcast(48.21, 16.37)` → `source == "INCA"`,
  `len(frames) >= 1`, jede `precip_mm_h` numerisch ≥ 0. Kein Fallback.

## AC-2 — Alle Punkte geparst, kein AttributeError

- `test_ac2_inca_parses_all_points_no_attributeerror`
  Echter `GeoSphereProvider().fetch_nowcast(48.21, 16.37)` + direktes
  `_fetch_geosphere_inca(48.21, 16.37)` → kein AttributeError,
  `len(frames) == len(ts.data)` (kein Dry-Frame verschluckt), jeder
  `timestamp.tzinfo is not None`, jede `precip_mm_h` numerisch ≥ 0.
