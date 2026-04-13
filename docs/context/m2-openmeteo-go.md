# Context: M2 — OpenMeteo Provider nach Go portieren

## Request Summary
OpenMeteo Weather Provider (678 LOC Python) nativ in Go portieren. Aktuell ist `/api/forecast` nur ein Proxy zum Python-Backend. BUG-TZ-01 (Timezone) soll beim Port direkt gefixt werden.

## Related Files

### Go (bestehend)
| File | Relevanz |
|------|----------|
| `cmd/server/main.go` | Entry point — `/api/forecast` als Proxy (Zeile 27), wird zum nativen Handler |
| `internal/handler/proxy.go` | Aktueller Proxy-Handler, wird fuer forecast ersetzt |
| `internal/config/config.go` | Config via envconfig — braucht ggf. neue Felder (Cache-Dir) |
| `internal/model/location.go` | Location Model (Lat/Lon) — Input fuer Provider |
| `internal/model/trip.go` | Trip Model mit Stages/Waypoints — hat Koordinaten |
| `internal/store/store.go` | File-based JSON Store — Pattern fuer Cache-Persistenz |

### Python (Quelle zum Portieren)
| File | Relevanz |
|------|----------|
| `src/providers/openmeteo.py` | **Hauptquelle** — 678 LOC, kompletter Provider |
| `src/providers/base.py` | WeatherProvider Protocol + Error-Hierarchie |
| `src/app/models.py` | DTOs: ForecastDataPoint, NormalizedTimeseries, ForecastMeta, ThunderLevel |

### Specs & Docs
| File | Relevanz |
|------|----------|
| `docs/specs/modules/provider_openmeteo.md` | Provider-Spec (Draft, v1.0) |
| `docs/reference/api_contract.md` | DTO-Definitionen (Single Source of Truth) |
| `docs/reference/decision_matrix.md` | Provider-Auswahl (MET vs MOSMIX) |
| `docs/project/backlog/stories/sveltekit-migration.md` | Migration Roadmap |

## Existing Patterns

### Go Handler Pattern
```go
func FooHandler(s *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        // Parse query params
        // Business logic
        // JSON encode response
    }
}
```

### Go Store/Model Pattern
- Models als structs mit JSON-Tags
- Store arbeitet file-based (JSON pro Entity)
- Kein ORM, kein DB

### Python Provider Pattern
- Regional Model Selection: 5 Modelle nach Bounds + Priority
- ECMWF als mandatory Global Fallback
- Metric Availability Probe mit 7-Tage-Cache
- Metric Fallback: Missing params vom Secondary Model holen
- UV-Index via separater Air Quality API
- Retry: 5 Versuche, exponential backoff 2-60s (tenacity)
- Thunder: WMO Codes 95, 96, 99 = HIGH

## Zu portierende Kernlogik

### 1. Regional Model Selection
5 Modelle mit Geo-Bounds + Priority:
- AROME (1.3km, Frankreich/Balearen/West-Alpen)
- ICON-D2 (2km, Deutschland/Oesterreich/Zentral-Alpen)
- MetNo Nordic (1km, Skandinavien/Baltikum)
- ICON-EU (7km, Rest Europa)
- ECMWF IFS04 (40km, Global Fallback)

### 2. API Request
- Base: `https://api.open-meteo.com`
- Endpoints pro Modell (z.B. `/v1/meteofrance`, `/v1/dwd-icon`)
- 17+ hourly Parameter
- Immer `timezone=UTC`

### 3. Metric Availability Probe (WEATHER-05a)
- Cache in `data/cache/model_availability.json`
- 7 Tage TTL
- Probt welche Metriken ein Modell liefert

### 4. Metric Fallback (WEATHER-05b)
- Erkennt fehlende Metriken im Primary Model
- Holt Secondary Model fuer fehlende Params
- Merge per Timestamp

### 5. UV-Index (WEATHER-06)
- Separate Air Quality API: `https://air-quality-api.open-meteo.com/v1/air-quality`
- Graceful degradation (UV=nil bei Fehler)

### 6. Parameter Mapping
Python → Go Mapping:
- `temperature_2m` → `T2mC`
- `wind_speed_10m` → `Wind10mKmh`
- `wind_gusts_10m` → `GustKmh`
- `precipitation` → `Precip1hMm`
- `cloud_cover` → `CloudTotalPct`
- `weather_code` → `WmoCode` + ThunderLevel
- ... (17+ Felder)

## Dependencies

### Upstream (was der Go Provider braucht)
- OpenMeteo API (extern, kein API Key noetig)
- OpenMeteo Air Quality API (extern, UV-Index)
- Go HTTP Client (stdlib `net/http`)
- Go JSON (stdlib `encoding/json`)
- Retry-Library (z.B. `cenkalti/backoff` oder eigene Logik)
- Config (DataDir fuer Cache)

### Downstream (was den Provider nutzt)
- `cmd/server/main.go` — Forecast-Handler Endpoint
- Zukuenftig: Go Scheduler (M4)
- Zukuenftig: SvelteKit Frontend (M3) via REST API

## BUG-TZ-01 Fix-Strategie

**Problem:** Alle Timestamps in UTC statt Lokalzeit.
**Root Cause:** Formatters nutzen `.hour` direkt auf UTC-Datetimes.

**Go-Fix:**
- Provider liefert weiterhin UTC (korrekt)
- Response-DTO bekommt `timezone` Feld (z.B. "Europe/Berlin")
- Frontend/Formatter konvertieren bei Anzeige
- Optional: `timezonefinder`-Equivalent in Go (`github.com/ringsaturn/tzf`)

## Risks & Considerations

1. **Scope:** Python Provider hat 678 LOC — Go wird aehnlich umfangreich
2. **Metric Fallback Komplexitaet:** Zwei API-Calls + Merge ist fehleranfaellig
3. **API Rate Limits:** OpenMeteo hat 10k req/day Free Tier
4. **Cache-Kompatibilitaet:** Go Cache-Format sollte kompatibel mit Python sein (gleiche JSON-Struktur) fuer uebergangslose Migration
5. **Kein API Key:** OpenMeteo Free Tier braucht keinen Key — vereinfacht Config
6. **Test-Strategie:** Echte API-Calls (keine Mocks!) per CLAUDE.md Konvention
