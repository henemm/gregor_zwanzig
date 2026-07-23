# Context: #1143 — Météo-France AROME Direktprovider (Slice FR von Epic #1127)

## Analysis

### Type
Feature (Slice FR aus Epic #1127, Cross-Provider-Fallback zweite Stufe). Abhängigkeit Slice 0 (#1141) geschlossen; Slice AT (#1142, GeoSphere) fertig und dient als 1:1-Vorlage.

### Feasibility-Spike (echte API, 2026-07-22)
- **Zugang:** `GZ_METEOFRANCE_APIKEY` schaltet **AROME HIGHRES 0.01° France** frei (GetCapabilities/DescribeCoverage HTTP 200). ARPEGE (global) ist gesperrt (403) — für FR nicht nötig.
- **Format:** WCS 2.0.1, Rohdaten als **GRIB2-Gitter** (kein JSON).
- **GRIB2 lesbar mit vorhandenen Mitteln:** GDAL 3.12.1 via `rasterio` 1.5.0 hat den GRIB-Treiber (`'GRIB' in rasterio.Env().drivers()` → True). **Keine neue schwergewichtige Dependency nötig** (eccodes/cfgrib/pygrib entfallen).
- **Metriken vorhanden:** TEMPERATURE (2 m via height-Subset), U/V_COMPONENT_OF_WIND (→ Betrag), TOTAL_PRECIPITATION (kumulativ → 1h-Differenz). Bonus: CAPE, Wolken, Blitzdichte. Kein fertiger Wetter-Code/`symbol`.
- **Echte AROME-Domäne:** long −12…16, lat 37,5…55,4 (aus DescribeCoverage).
- **WCS-Backend zickig:** sporadische 500/404 („backend error") → Retry + saubere `ProviderRequestError` nötig (wie GeoSphere `_request` mit tenacity).

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| `src/providers/meteofrance.py` | CREATE | Neuer AROME-WCS-Direktprovider; Vorlage `geosphere.py` (`_vector_to_speed_kmh`, U/V→Wind, Precip-Differenz) + `GeoSphereDirectProvider` (httpx→ProviderRequestError) |
| `src/providers/regional_stubs.py` | MODIFY | `make_fr_direct` (Z.101) von Stub auf echten Provider umstellen |
| `src/providers/base.py` | MODIFY | `_load_providers()` (Z.188-189): `fr_direct` auf neuen Provider registrieren |
| `src/app/models.py` | MODIFY | `Provider`-Enum um `METEOFRANCE` (Z.22-30) für `ForecastMeta` |
| `src/providers/region_routing.py` | MODIFY | FR-Box (Z.36) nach Osten erweitern → Korsika/GR20 einschließen (s. offene Frage 1) |
| `docs/reference/decision_matrix.md` | MODIFY | `fr_direct` als echten Forecast-Provider fortschreiben |
| `src/providers/openmeteo.py` | KEINE | Seam (Z.922-945) fängt bereits alle 3 Exceptions — F001-Annahme im Issue veraltet |

### Datenmodell (verifiziert)
`NormalizedTimeseries(meta, data)` (models.py:159); Messwerte auf `ForecastDataPoint` (models.py:91): `t2m_c`(°C), `wind10m_kmh`(km/h), `precip_1h_mm`(mm), `symbol`(überall None — Symbol wird downstream aus `wmo_code`/Wolken/DNI abgeleitet, nicht hier). `__post_init__` erzwingt naive-UTC (provider_tz_normalization Pflicht).

### Coverage-Routing (verifiziert)
`region_routing.py`: `_RegionBounds`(min/max lat/lon + provider), `direct_provider_for(lat,lon)` erste treffende Region (AT→DE→FR). Keine Bounds-Prüfung IM Provider — nur im Routing. FR-Box aktuell 41,3–51,1N / −5,2–8,3E.

### Nicht-Kaschieren-Invariante (ADR-0018, verbindlich)
Jedes Ausweichen markiert (`fallback_model`/`fallback_reason`); 4xx bleibt sichtbar (kein drittes Ausweichen); 5xx/Timeout → `has_error` bleibt. Seam setzt `fallback_reason="cross_provider_total_outage"` bereits.

### Scope Assessment
- Files: 1 CREATE + 4-5 MODIFY
- LoC: ~150–250 (Provider-Kern), im/nahe Workflow-Limit
- Risk: MEDIUM (GRIB2-Lesen gelöst; Restrisiko WCS-Flakiness + Abrufstrategie)

### Technical Approach (Empfehlung)
1. Provider `meteofrance.py` nach GeoSphere-Muster: httpx-Client + tenacity-Retry (retry 502/503/504 + 500), httpx-Fehler → `ProviderRequestError(status_code)`.
2. **Abrufstrategie effizient:** pro Parameter EIN GetCoverage mit lat/long-Subset + voller Zeitachse (alle Stundenschritte als GRIB-Bänder in einer Antwort) → ~3–4 Calls statt Dutzende. GRIB2 via `rasterio.open()` → Punktwert je Band.
3. Wind aus U/V via `_vector_to_speed_kmh`; Precip kumulativ→1h-Differenz (GeoSphere-Muster); Temp height(2)-Subset.
4. `symbol`/`wmo_code` bleiben None (wie andere Provider) — s. offene Frage 2.

### PO-Entscheidungen (2026-07-22)
- [x] **1 (Korsika): JA** — FR-Box nach Osten auf ~9,7°O erweitern, damit GR20/Korsika beim Totalausfall auf Météo-France ausweicht.
- [x] **2 (Symbol): weglassen (minimal)** — nur t2m_c/wind10m_kmh/precip_1h_mm; `symbol`/`wmo_code` bleiben None wie bei GeoSphere/Open-Meteo.
