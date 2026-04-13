# Analyse: Risk Engine nach Go portieren (#24)

**Datum:** 2026-04-13
**Workflow:** risk-engine-go
**Phase:** 2 (Analyse)

## Ist-Zustand (Python)

- risk_engine.py: 221 LOC, 9 Regeln, pure functions
- models.py (Risk-Teil): 41 LOC, RiskType/RiskLevel/Risk/RiskAssessment
- metric_catalog.py: 485 LOC, nur 7 Metriken mit risk_thresholds
- 14+ Tests in tests/integration/test_risk_engine.py

## Go-Bestand

- ThunderLevel enum in internal/model/forecast.go (NONE, MED, HIGH)
- ForecastDataPoint mit allen Wetter-Feldern als Pointer
- KEIN risk package, KEINE SegmentWeatherSummary, KEINE Risk DTOs

## Architektur-Entscheidungen

1. Package: internal/risk/ (pure functions, kein I/O)
2. DTOs: internal/model/risk.go + segment.go
3. Thresholds: Hardcoded Konstanten (kein MetricCatalog)
4. Kein RiskEngine Struct — package-level Funktionen
5. Wind Exposition als eigene Phase

## 3 Phasen

| Phase | Was | Dateien | LOC |
|-------|-----|---------|-----|
| M3a | Risk DTOs + SegmentWeatherSummary | 2 (model/risk.go, model/segment.go) | ~90 |
| M3b | Thresholds + Engine + Tests (Regeln 1-8) | 3 (risk/thresholds.go, engine.go, engine_test.go) | ~220 |
| M3c | Wind Exposition (Regel 9) | 2 (risk/exposition.go, exposition_test.go) | ~120 |

## Schwellenwerte

| Metrik | Medium | High | Typ |
|--------|--------|------|-----|
| wind | 50 km/h | 70 km/h | normal |
| gust | 50 km/h | 70 km/h | normal |
| precipitation | 20 mm | - | normal |
| rain_probability | 80% | - | normal |
| cape | 1000 J/kg | 2000 J/kg | normal |
| wind_chill | - | <-20 C | inverted |
| visibility | - | <100 m | inverted |
| wind (exposition) | 30 km/h | 50 km/h | normal |
| gust (exposition) | 40 km/h | 60 km/h | normal |
