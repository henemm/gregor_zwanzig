# Context: Issue #262 — Re-Validierung Compare-Engine (AC-1/AC-2/AC-6)

## Request Summary

Issue #250 (Compare-Engine Backend) ist vollständig implementiert und auf Production live. Der External Validator konnte am 2026-05-19 drei ACs (AC-1, AC-2, AC-6) nicht prüfen, weil OpenMeteo das Tageslimit (HTTP 429) erreicht hatte. Issue #262 ist eine reine Re-Validierung — kein Code muss geändert werden.

## Status am 2026-05-20

| Was | Status |
|-----|--------|
| OpenMeteo API | **verfügbar** — antwortet mit echten Daten |
| Staging | **up** — `/api/health` → `{"status":"ok"}` |
| Validator-Auth | aktiv — `validator-issue110` / Cookie-Login funktioniert |
| Verfügbare Locations | einzelort, finkenberg, hall-in-tirol, hintertux, innsbruck, mayrhofen, ortler-testort |

## Ausstehende ACs

### AC-1
Higher Rainfall → Lower Score, Rank-Order korrekt.  
**Test:** POST `/api/compare/run` mit 2 Locations, `profile: "ALLGEMEIN"` → Response enthält 2 `rows` mit `score` 0–100, Rank 1 = höchster Score.

### AC-2
Cache-Speedup: Zweiter identischer Request < erster.  
**Test:** Selben Request zweimal innerhalb 15 Min. → Zweiter Request deutlich schneller, `score` identisch.

### AC-6
ALPINE_TOURING ohne Lawinenstufe-Fehler.  
**Test:** POST mit `profile: "ALPINE_TOURING"` → kein Error, Ranking basiert auf Wind/Schnee/Sicht, alle Locations gleicher Lawinenstufen-Beitrag (0).

## Implementierungsdateien (Issue #250)

| File | Zweck |
|------|-------|
| `internal/compare/engine.go` | Core: Goroutines, Cache, Aggregation |
| `internal/compare/scoring.go` | Profil-gewichtetes Scoring |
| `internal/compare/cache.go` | 15-Min In-Memory-Cache |
| `internal/compare/types.go` | DTOs: CompareRequest, CompareResult, CompareRow |
| `internal/handler/compare_run.go` | HTTP-Handler POST /api/compare/run |
| `internal/handler/compare_run_test.go` | Integrationstests |

## Validator-Befehl

```bash
bash .claude/validate-external.sh docs/specs/modules/issue_250_compare_engine.md
```

## Nächster Schritt

Phase 2 → Validator direkt ausführen. Kein Code-Change nötig.
