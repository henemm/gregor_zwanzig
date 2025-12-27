


# Provider Mapping (Kurzreferenz)

## MOSMIX (DWD)
- Quelle: MOSMIX-L/S (Open Data)
- Mapping: 
  - TTT → t2m_c
  - FF (m/s) ×3.6 → wind10m_kmh
  - FX / FX1 (m/s) ×3.6 → gust_kmh
  - RR1c → precip_1h_mm  (und abgeleitet: precip_rate_mmph)
  - N → cloud_total_pct
  - ww → symbol (siehe symbol_mapping.md)
  - CAPE_* → cape_jkg
- Provenance: `stations_used[]`, `interp = nearest_station | idw2`

## MET Norway (Locationforecast 2.0)
- Endpoint: `/compact` (MVP)
- Mapping:
  - air_temperature → t2m_c
  - wind_speed (m/s) ×3.6 → wind10m_kmh
  - wind_speed_of_gust (m/s) ×3.6 → gust_kmh
  - cloud_area_fraction → cloud_total_pct
  - precipitation_amount (next_1h/6h) → precip_1h_mm  (Rate ableiten)
  - summary.symbol_code → symbol

## DWD NowcastMix
- Mapping:
  - radar_intensity → nowcast_radar_mmph
  - thunder_signature → nowcast_thunder (bool)
- Hinweis: Nowcast-Felder bleiben **separat**; Thunder-Ableitung setzt `thunder_level` in der Normalisierung.