# Mini-Spec: fix-782 — Falsy-Zero-Fallen im GeoSphere-Parser

## Acceptance Criteria

**AC-1:** Given `pressure=0` (Pa) in `_parse_nwp_response`, When the parser processes it, Then `pressure_hpa` equals `0.0` and not `None`.

**AC-2:** Given `snow_depth_m=0.0` in `_parse_snowgrid_response`, When the parser processes it, Then `snow_depth_cm` equals `0.0` and not `None`.

**AC-3:** Given `pressure=None` in `_parse_nwp_response`, When the parser processes it, Then `pressure_hpa` is `None` (unchanged behavior).

**AC-4:** Given `snow_depth_m=None` in `_parse_snowgrid_response`, When the parser processes it, Then `snow_depth_cm` is `None` (unchanged behavior).

## Was ändert sich

- `src/providers/geosphere.py:534` (`_parse_nwp_response`):
  `if pressure else None` → `if pressure is not None else None`
- `src/providers/geosphere.py:577` (`_parse_snowgrid_response`):
  `if snow_depth_m else None` → `if snow_depth_m is not None else None`

## Was darf sich nicht ändern

- Verhalten bei echtem `None`-Input bleibt unverändert (→ `None` Output)
- Keine anderen Stellen in `geosphere.py` anfassen
- Keine API-Änderungen, kein Interface-Change

## Manuelle Test-Schritte

1. `uv run pytest tests/ -k "geosphere" -x` — alle geosphere-Tests grün
2. `uv run pytest tests/ -x` — keine Regressionen

## Inline-Tests (werden während Implementierung geschrieben)

- [ ] `_parse_nwp_response` mit `pressure=0` → `pressure_hpa = 0.0` (nicht `None`)
- [ ] `_parse_snowgrid_response` mit `snow_depth_m=0.0` → `snow_depth_cm = 0.0` (nicht `None`)
- [ ] `_parse_nwp_response` mit `pressure=None` → `pressure_hpa = None` (unverändert)
- [ ] `_parse_snowgrid_response` mit `snow_depth_m=None` → `snow_depth_cm = None` (unverändert)
